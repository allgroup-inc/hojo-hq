# GLOW M&A台帳 Phase 4(レター下書き生成・反応計測・ナーチャリング配信)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude APIでスコア・業種・提案順序方針に応じたレター文面の下書きを自動生成し、「レター下書き」タブに蓄積する(人が確認して送付)。レターに載せるパーソナライズURLへのアクセスを、非公開Web App経由で対応履歴ログに自動記録する。関係構築中以降で接触が空いているランクB以下の企業には、ナーチャリング配信用の下書きも同じ仕組みで定期生成する。

**Architecture:** 文面組み立て・対象選定ロジック(提案順序ガイドラインの適用・プロンプト構築・ナーチャリング対象抽出)はGAS/Node両対応のUMD形式プレーンJSとして`glow-ma/src/letterContent.js`に実装し、`node --test`でユニットテストする。この中でPhase 3の`GlowAlerting.daysBetween`をそのまま再利用し、日付計算ロジックを重複させない。GAS専用の`LetterRunner.gs`(Claude API呼び出し)と`TrackingWebApp.gs`(反応計測Web App)は、文面/対象選定を`letterContent.js`に委譲する薄いグルーコードとする。

**Tech Stack:** Google Apps Script(V8ランタイム、`UrlFetchApp`、`HtmlService`、Web Appデプロイ)、Claude API(`https://api.anthropic.com/v1/messages`、モデルID `claude-sonnet-5`)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの範囲について:** 設計書10章(レター生成・反応計測)・11章(ナーチャリング配信)を実装する。12章(ダッシュボード)は対象外(別Plan)。レターの自動送信は行わない(下書き生成までで、送付は必ず人が行う)。反応計測はWeb Appのデプロイという人間の手作業を伴うため、本Planは`doGet`ハンドラのコードを用意するところまでが責務であり、実際のデプロイ・URL発行は範囲外(READMEに手順を明記する)。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データ・Claude APIキー・Web AppのURLを一切コミットしない。APIキーはGASの「スクリプト プロパティ」(`ANTHROPIC_API_KEY`)で管理し、コードに直接書かない
- レターの自動送信は行わない。生成されるのは「レター下書き」タブへの下書きのみで、ステータスは常に`"下書き"`で作成し、送付は人が行ってから手動で`"送付済み"`に更新する運用とする
- 提案順序は設計書7章の方針(紹介ルートは直接M&A提案も可、それ以外は保険・経営相談を入口にする)に従う
- ナーチャリング配信の対象条件(設計書11章): ステージが「関係構築中」以降(関係構築中・提案中・案件化)、ランクB以下(B/C/D)、直近接触から90日以上経過。この条件は`letterContent.js`の設定オブジェクトで管理し、値を変更しやすくする
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する。`letterContent.js`は`glow-ma/src/alerting.js`の`daysBetween`に依存するため、Node側では`require("./alerting.js")`で読み込み、GAS側では`global.GlowAlerting`をそのまま参照する(重複実装しない)
- 対応履歴ログへの自動書き込み(Web Appからの反応記録)は、企業マスタと同様に`LockService`で保護する。書き込みは追記(1行分の`setValues`)のみで、シート全体を書き直さない
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する(Phase 1〜3と同じ扱い)

---

## File Structure

```
glow-ma/src/
  schema.js          — 既存ファイルを修正: レター下書きタブの名称・見出し・種別・ステータス定数を追加(Task 1)
  letterContent.js    — 新規: 提案順序判定・トラッキングURL生成・プロンプト構築・ナーチャリング対象選定(GlowLetterContent)(Task 2, 3, 4)
  SheetSetup.gs        — 既存ファイルを修正: レター下書きタブの作成+ステータスのプルダウン(Task 5)
  LetterRunner.gs       — 新規: Claude APIでのレター下書き生成(初回DM・ナーチャリング)(Task 6、GAS専用)
  TrackingWebApp.gs      — 新規: パーソナライズURLアクセスの反応計測(doGet、GAS専用Web App)(Task 7、GAS専用)
tests/
  glow_ma_letterContent.test.mjs   — 新規(Task 2, 3, 4)
glow-ma/README.md      — Phase 4のセットアップ・使い方を追記(Task 8)
```

---

### Task 1: `schema.js` — レター下書きタブの定義を追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.LETTER_DRAFT_SHEET_NAME`(string)、`GlowSchema.LETTER_DRAFT_HEADERS`(string[])、`GlowSchema.LETTER_DRAFT_TYPES`(string[]、`["初回DM", "ナーチャリング配信"]`)、`GlowSchema.LETTER_DRAFT_STATUSES`(string[]、`["下書き", "送付済み", "見送り"]`)。Task 5(タブ作成・プルダウン)とTask 6(LetterRunner.gsの書き込み先)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs` の末尾に追記:

```js
test("レター下書きタブの名称・見出し・種別・ステータスが定義されている", () => {
  assert.equal(schema.LETTER_DRAFT_SHEET_NAME, "レター下書き");
  assert.deepEqual(schema.LETTER_DRAFT_HEADERS, [
    "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス"
  ]);
  assert.deepEqual(schema.LETTER_DRAFT_TYPES, ["初回DM", "ナーチャリング配信"]);
  assert.deepEqual(schema.LETTER_DRAFT_STATUSES, ["下書き", "送付済み", "見送り"]);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`schema.LETTER_DRAFT_SHEET_NAME`が`undefined`)

- [ ] **Step 3: `glow-ma/src/schema.js` に定義を追加**

`SETTINGS_HEADERS`の定義の直後に追加する:

```js
  var LETTER_DRAFT_SHEET_NAME = "レター下書き";
  var LETTER_DRAFT_HEADERS = [
    "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス"
  ];
  var LETTER_DRAFT_TYPES = ["初回DM", "ナーチャリング配信"];
  var LETTER_DRAFT_STATUSES = ["下書き", "送付済み", "見送り"];
```

`api`オブジェクトに追加する(既存のプロパティはそのまま残し、以下を追記):

```js
    LETTER_DRAFT_SHEET_NAME: LETTER_DRAFT_SHEET_NAME,
    LETTER_DRAFT_HEADERS: LETTER_DRAFT_HEADERS,
    LETTER_DRAFT_TYPES: LETTER_DRAFT_TYPES,
    LETTER_DRAFT_STATUSES: LETTER_DRAFT_STATUSES
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト + 新規1テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): レター下書きタブのスキーマ定義を追加"
```

---

### Task 2: `letterContent.js` — 提案順序判定とトラッキングURL生成

**Files:**
- Create: `glow-ma/src/letterContent.js`
- Test: `tests/glow_ma_letterContent.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowLetterContent`オブジェクト。`DEFAULT_CONFIG`(object)、`determineLeadProduct(record, config)`: string(設計書7章の提案順序ガイドラインに基づき、最初に案内する商品を返す。紹介ルートを含む企業は`"M&A"`、それ以外は`"法人保険・経営相談"`)、`buildTrackingUrl(companyId, baseUrl)`: string(`baseUrl`に`?id=企業ID`または`&id=企業ID`を付与したURL。`companyId`か`baseUrl`が空なら空文字列)

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_letterContent.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const letterContent = require("../glow-ma/src/letterContent.js");

test("determineLeadProduct: 紹介ルートを含む企業は直接M&Aを案内してよい", () => {
  const record = { 流入ルート: ["①紹介"] };
  assert.equal(letterContent.determineLeadProduct(record, letterContent.DEFAULT_CONFIG), "M&A");
});

test("determineLeadProduct: 紹介ルートを含まない企業は法人保険・経営相談を入口にする", () => {
  const record = { 流入ルート: ["②手紙DM"] };
  assert.equal(letterContent.determineLeadProduct(record, letterContent.DEFAULT_CONFIG), "法人保険・経営相談");
});

test("determineLeadProduct: 流入ルートが未設定でもエラーにならない", () => {
  const record = {};
  assert.equal(letterContent.determineLeadProduct(record, letterContent.DEFAULT_CONFIG), "法人保険・経営相談");
});

test("buildTrackingUrl: 企業IDをクエリパラメータとして付与する", () => {
  assert.equal(
    letterContent.buildTrackingUrl("C000001", "https://example.com/track"),
    "https://example.com/track?id=C000001"
  );
});

test("buildTrackingUrl: baseUrlに既にクエリ文字列がある場合は&で繋ぐ", () => {
  assert.equal(
    letterContent.buildTrackingUrl("C000001", "https://example.com/track?x=1"),
    "https://example.com/track?x=1&id=C000001"
  );
});

test("buildTrackingUrl: companyIdまたはbaseUrlが空なら空文字列を返す", () => {
  assert.equal(letterContent.buildTrackingUrl("", "https://example.com/track"), "");
  assert.equal(letterContent.buildTrackingUrl("C000001", ""), "");
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_letterContent.test.mjs`
Expected: FAIL(`glow-ma/src/letterContent.js`が存在しない)

- [ ] **Step 3: `glow-ma/src/letterContent.js` を作成し `determineLeadProduct` / `buildTrackingUrl` を実装**

```js
/* GLOW企業リレーション台帳 レター文面組み立て・ナーチャリング対象選定ロジック
 * ブラウザ相当のGAS(global.GlowLetterContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_letterContent.test.mjs で検証される。
 *
 * daysBetween は glow-ma/src/alerting.js の GlowAlerting をそのまま利用し、
 * 日付計算ロジックをこのファイルで重複定義しない。
 */
(function (global) {
  "use strict";

  var GlowAlerting = (typeof module !== "undefined" && module.exports)
    ? require("./alerting.js")
    : global.GlowAlerting;

  var DEFAULT_CONFIG = {
    referralRoute: "①紹介",
    leadProductForReferral: "M&A",
    leadProductDefault: "法人保険・経営相談"
  };

  function determineLeadProduct(record, config) {
    config = config || DEFAULT_CONFIG;
    var routes = record["流入ルート"] || [];
    if (routes.indexOf(config.referralRoute) !== -1) {
      return config.leadProductForReferral;
    }
    return config.leadProductDefault;
  }

  function buildTrackingUrl(companyId, baseUrl) {
    if (!companyId || !baseUrl) return "";
    var separator = baseUrl.indexOf("?") === -1 ? "?" : "&";
    return baseUrl + separator + "id=" + encodeURIComponent(companyId);
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    determineLeadProduct: determineLeadProduct,
    buildTrackingUrl: buildTrackingUrl
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLetterContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_letterContent.test.mjs`
Expected: PASS(6 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/letterContent.js tests/glow_ma_letterContent.test.mjs
git commit -m "feat(glow-ma): 提案順序判定とトラッキングURL生成ロジックを追加"
```

---

### Task 3: `letterContent.js` — レタープロンプトの組み立て

**Files:**
- Modify: `glow-ma/src/letterContent.js`
- Modify: `tests/glow_ma_letterContent.test.mjs`

**Interfaces:**
- Consumes: Task 2の`determineLeadProduct`
- Produces: `buildLetterPrompt(record, trackingUrl, config)`: string(Claude APIに渡すプロンプト文字列)。Task 6の`LetterRunner.gs`が呼び出す

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_letterContent.test.mjs` に追記:

```js
test("buildLetterPrompt: 会社名・案内する商品・トラッキングURLを含むプロンプトを組み立てる", () => {
  const record = { 会社名: "テスト商事株式会社", 業種: "建設業", 流入ルート: ["②手紙DM"] };
  const prompt = letterContent.buildLetterPrompt(record, "https://example.com/track?id=C000001", letterContent.DEFAULT_CONFIG);
  assert.match(prompt, /テスト商事株式会社/);
  assert.match(prompt, /法人保険・経営相談/);
  assert.match(prompt, /https:\/\/example\.com\/track\?id=C000001/);
});

test("buildLetterPrompt: 紹介ルートの企業はM&Aを案内する文面指示になる", () => {
  const record = { 会社名: "サンプル建設株式会社", 業種: "建設業", 流入ルート: ["①紹介"] };
  const prompt = letterContent.buildLetterPrompt(record, "https://example.com/track?id=C000002", letterContent.DEFAULT_CONFIG);
  assert.match(prompt, /M&A/);
});

test("buildLetterPrompt: 業種が未設定でもエラーにならない", () => {
  const record = { 会社名: "テスト商事株式会社", 流入ルート: [] };
  const prompt = letterContent.buildLetterPrompt(record, "https://example.com/track?id=C000003", letterContent.DEFAULT_CONFIG);
  assert.match(prompt, /テスト商事株式会社/);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_letterContent.test.mjs`
Expected: FAIL(`letterContent.buildLetterPrompt is not a function`)

- [ ] **Step 3: `buildLetterPrompt` を実装**

`glow-ma/src/letterContent.js` の `buildTrackingUrl` 関数の直後に追加する:

```js
  function buildLetterPrompt(record, trackingUrl, config) {
    config = config || DEFAULT_CONFIG;
    var leadProduct = determineLeadProduct(record, config);
    var lines = [
      "あなたは沖縄の中小企業向けM&A・不動産・法人保険を扱う株式会社GLOWの営業担当です。",
      "以下の企業宛てに送る手紙の文面を、丁寧で押しつけがましくない経営相談ベースのトーンで下書きしてください。",
      "",
      "企業名: " + (record["会社名"] || ""),
      "業種: " + (record["業種"] || "不明"),
      "最初にご案内する内容: " + leadProduct,
      "",
      "条件:",
      "- 「売り込み」ではなく「無料の経営相談・情報提供」という体裁にすること",
      "- いきなりM&Aの話から入らないこと(紹介ルートの場合を除く)",
      "- 文末に次のURLへの案内を自然に含めること: " + (trackingUrl || ""),
      "- 断定的な成果保証をしないこと",
      "",
      "300〜500字程度の手紙文面のみを出力してください。"
    ];
    return lines.join("\n");
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    determineLeadProduct: determineLeadProduct,
    buildTrackingUrl: buildTrackingUrl,
    buildLetterPrompt: buildLetterPrompt
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_letterContent.test.mjs`
Expected: PASS(9 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/letterContent.js tests/glow_ma_letterContent.test.mjs
git commit -m "feat(glow-ma): レター下書き用のClaude APIプロンプト組み立てを追加"
```

---

### Task 4: `letterContent.js` — ナーチャリング配信対象の選定

**Files:**
- Modify: `glow-ma/src/letterContent.js`
- Modify: `tests/glow_ma_letterContent.test.mjs`

**Interfaces:**
- Consumes: `GlowAlerting.daysBetween`(`glow-ma/src/alerting.js`、Phase 3)
- Produces: `selectNurturingTargets(records, todayValue, config)`: 企業マスタレコードの配列(設計書11章の対象条件に合う企業のみ)。Task 6の`LetterRunner.gs`が呼び出す

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_letterContent.test.mjs` に追記:

```js
test("selectNurturingTargets: ステージ・ランク・接触間隔の条件を満たす企業のみ抽出する", () => {
  const records = [
    { 企業ID: "C1", 現在ステージ: "関係構築中", ランク: "B", 最終接触日: "2026-01-01" }, // 対象
    { 企業ID: "C2", 現在ステージ: "未接触", ランク: "B", 最終接触日: "2026-01-01" }, // ステージ対象外
    { 企業ID: "C3", 現在ステージ: "提案中", ランク: "A", 最終接触日: "2026-01-01" }, // ランク対象外(Aは除外)
    { 企業ID: "C4", 現在ステージ: "案件化", ランク: "C", 最終接触日: "2026-07-20" } // 直近すぎる(7日前)
  ];
  const targets = letterContent.selectNurturingTargets(records, "2026-07-27", letterContent.DEFAULT_CONFIG);
  assert.deepEqual(targets.map((r) => r["企業ID"]), ["C1"]);
});

test("selectNurturingTargets: 最終接触日が未設定なら登録日を代わりに使う", () => {
  const records = [
    { 企業ID: "C5", 現在ステージ: "関係構築中", ランク: "D", 最終接触日: "", 登録日: "2026-01-01" }
  ];
  const targets = letterContent.selectNurturingTargets(records, "2026-07-27", letterContent.DEFAULT_CONFIG);
  assert.deepEqual(targets.map((r) => r["企業ID"]), ["C5"]);
});

test("selectNurturingTargets: 対象企業がなければ空配列", () => {
  assert.deepEqual(letterContent.selectNurturingTargets([], "2026-07-27", letterContent.DEFAULT_CONFIG), []);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_letterContent.test.mjs`
Expected: FAIL(`letterContent.selectNurturingTargets is not a function`)

- [ ] **Step 3: `selectNurturingTargets` を実装**

`glow-ma/src/letterContent.js` の `DEFAULT_CONFIG` 定義を、ナーチャリング条件を含む形に置き換える:

```js
  var DEFAULT_CONFIG = {
    referralRoute: "①紹介",
    leadProductForReferral: "M&A",
    leadProductDefault: "法人保険・経営相談",
    nurturing: {
      eligibleStages: ["関係構築中", "提案中", "案件化"],
      eligibleRanks: ["B", "C", "D"],
      minIntervalDays: 90
    }
  };
```

`buildLetterPrompt` 関数の直後に追加する:

```js
  function selectNurturingTargets(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var nurturing = config.nurturing || DEFAULT_CONFIG.nurturing;
    return (records || []).filter(function (record) {
      if (nurturing.eligibleStages.indexOf(record["現在ステージ"]) === -1) return false;
      if (nurturing.eligibleRanks.indexOf(record["ランク"]) === -1) return false;
      var lastTouch = record["最終接触日"] || record["登録日"];
      var days = GlowAlerting.daysBetween(lastTouch, todayValue);
      if (days === null) return false;
      return days >= nurturing.minIntervalDays;
    });
  }
```

`api`オブジェクトを次のように更新する(最終形):

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    determineLeadProduct: determineLeadProduct,
    buildTrackingUrl: buildTrackingUrl,
    buildLetterPrompt: buildLetterPrompt,
    selectNurturingTargets: selectNurturingTargets
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_letterContent.test.mjs`
Expected: PASS(12 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/letterContent.js tests/glow_ma_letterContent.test.mjs
git commit -m "feat(glow-ma): ナーチャリング配信対象の選定ロジックを追加"
```

---

### Task 5: `SheetSetup.gs` — レター下書きタブの作成(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.LETTER_DRAFT_SHEET_NAME`/`LETTER_DRAFT_HEADERS`/`LETTER_DRAFT_STATUSES`(Task 1)
- Produces: `ensureLedgerTabs()`実行時に「レター下書き」タブが作成され、「ステータス」列にプルダウンが設定される

- [ ] **Step 1: `glow-ma/src/SheetSetup.gs` を修正**

現在のファイル全体を次の内容に置き換える(既存の`ensureTab_`・`applyInteractionTypeValidation_`・`applyRespondentValidation_`はそのまま残す):

```js
/**
 * GLOW企業リレーション台帳: シート初期化
 * Apps Scriptエディタの関数選択で ensureLedgerTabs を選び、実行ボタンで手動実行する。
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」
 * 「レター下書き」の5タブが(存在しなければ)作成され、1行目に見出しが設定される。
 * 対応履歴ログの「種別」「対応相手」列、レター下書きの「ステータス」列には、
 * 表記ゆれによる集計漏れを防ぐためプルダウン入力規則を設定する。
 */
function ensureLedgerTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureTab_(ss, GlowSchema.COMPANY_MASTER_SHEET_NAME, GlowSchema.COMPANY_MASTER_HEADERS);
  var logSheet = ensureTab_(ss, GlowSchema.INTERACTION_LOG_SHEET_NAME, GlowSchema.INTERACTION_LOG_HEADERS);
  applyInteractionTypeValidation_(logSheet);
  applyRespondentValidation_(logSheet);
  ensureTab_(ss, GlowSchema.PARTNER_MASTER_SHEET_NAME, GlowSchema.PARTNER_MASTER_HEADERS);
  ensureTab_(ss, GlowSchema.SETTINGS_SHEET_NAME, GlowSchema.SETTINGS_HEADERS);
  var letterDraftSheet = ensureTab_(ss, GlowSchema.LETTER_DRAFT_SHEET_NAME, GlowSchema.LETTER_DRAFT_HEADERS);
  applyLetterDraftStatusValidation_(letterDraftSheet);
}

function ensureTab_(spreadsheet, sheetName, headers) {
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  return sheet;
}

function applyInteractionTypeValidation_(sheet) {
  var typeColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("種別") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.INTERACTION_TYPES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, typeColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}

function applyRespondentValidation_(sheet) {
  var respondentColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("対応相手") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.RESPONDENT_TYPES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, respondentColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}

function applyLetterDraftStatusValidation_(sheet) {
  var statusColumnIndex = GlowSchema.LETTER_DRAFT_HEADERS.indexOf("ステータス") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.LETTER_DRAFT_STATUSES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, statusColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}
```

**注意:** `applyInteractionTypeValidation_`・`applyRespondentValidation_`は既存コード(Phase 2で追加済み)。書き換える際は削除・変更せず、`applyLetterDraftStatusValidation_`の追加と`ensureLedgerTabs()`内の呼び出し追加のみを行うこと。

- [ ] **Step 2: 静的チェック**

Run: `cp glow-ma/src/SheetSetup.gs /tmp/SheetSetup_check.js && node --check /tmp/SheetSetup_check.js && rm /tmp/SheetSetup_check.js`
Expected: 構文エラーなし

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. `ensureLedgerTabs` を実行
3. 「レター下書き」タブが作成され、見出しが`GlowSchema.LETTER_DRAFT_HEADERS`と一致すること、「ステータス」列にプルダウン(下書き/送付済み/見送り)が設定されていることを確認する
4. 既存の4タブ(企業マスタ・対応履歴ログ・紹介パートナーマスタ・設定)が壊れていないことも確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): レター下書きタブの作成とステータスのプルダウンを追加"
```

---

### Task 6: `LetterRunner.gs` — Claude APIでのレター下書き生成(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/LetterRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.COMPANY_MASTER_SHEET_NAME`/`LETTER_DRAFT_SHEET_NAME`/`LETTER_DRAFT_HEADERS`(Task 1)、`GlowLetterContent.buildTrackingUrl`/`buildLetterPrompt`/`selectNurturingTargets`(Task 2〜4)、`readCompanyRecords_`(`glow-ma/src/ImportRunner.gs`。**再定義しないこと**)
- Produces: `generateLetterDraftForCompany(companyId)`関数(1社分の初回DM下書きを生成)、`generateNurturingDraftsForEligibleCompanies()`関数(引数なし、対象企業全件分のナーチャリング下書きを生成)

- [ ] **Step 1: `glow-ma/src/LetterRunner.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: レター下書き生成(Claude API)
 *
 * 使い方:
 * 1. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で
 *    ANTHROPIC_API_KEY を設定する(コードにAPIキーを直接書かない)
 * 2. TRACKING_BASE_URL(Task 7でデプロイするWeb AppのURL)も同様に設定する
 *    (未設定の場合、トラッキングURLなしで下書きが生成される)
 * 3. 1社分だけ生成したい場合は、Apps Scriptエディタでこのファイルの末尾に
 *    一時的に `generateLetterDraftForCompany("C000001");` のような呼び出し行を足して実行する
 * 4. ナーチャリング対象全件分をまとめて生成する場合は generateNurturingDraftsForEligibleCompanies
 *    を実行する
 *
 * 生成された下書きは「レター下書き」タブに追記される。ステータスは常に
 * 「下書き」で作成され、自動送信は行わない。必ず人が内容を確認してから送付すること。
 */
function generateLetterDraftForCompany(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var records = readCompanyRecords_(companySheet);
  var record = records.filter(function (r) { return r["企業ID"] === companyId; })[0];
  if (!record) {
    throw new Error("企業ID " + companyId + " が企業マスタに見つかりません。");
  }
  writeLetterDraft_(record, "初回DM");
  Logger.log("レター下書きを生成しました: " + companyId);
}

function generateNurturingDraftsForEligibleCompanies() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var records = readCompanyRecords_(companySheet);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var targets = GlowLetterContent.selectNurturingTargets(records, todayString);
  targets.forEach(function (record) {
    writeLetterDraft_(record, "ナーチャリング配信");
  });
  Logger.log("ナーチャリング下書き生成完了: " + targets.length + "件");
}

function writeLetterDraft_(record, draftType) {
  var baseUrl = PropertiesService.getScriptProperties().getProperty("TRACKING_BASE_URL");
  var trackingUrl = baseUrl ? GlowLetterContent.buildTrackingUrl(record["企業ID"], baseUrl) : "";
  var prompt = GlowLetterContent.buildLetterPrompt(record, trackingUrl);
  var draftBody = callClaudeApi_(prompt);

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var draftSheet = ss.getSheetByName(GlowSchema.LETTER_DRAFT_SHEET_NAME);
  if (!draftSheet) {
    throw new Error("レター下書きタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var nextRow = draftSheet.getLastRow() + 1;
  var draftId = "D-" + Utilities.getUuid();
  var generatedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
  draftSheet.getRange(nextRow, 1, 1, GlowSchema.LETTER_DRAFT_HEADERS.length).setValues([[
    draftId, record["企業ID"], draftType, generatedAt, draftBody, "下書き"
  ]]);
}

function callClaudeApi_(prompt) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("ANTHROPIC_API_KEY");
  if (!apiKey) {
    throw new Error("ANTHROPIC_API_KEY が未設定です。スクリプト プロパティで設定してください。");
  }
  var response = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", {
    method: "post",
    contentType: "application/json",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01"
    },
    payload: JSON.stringify({
      model: "claude-sonnet-5",
      max_tokens: 1024,
      messages: [{ role: "user", content: prompt }]
    }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    throw new Error("Claude APIの呼び出しに失敗しました(ステータスコード " + responseCode + "): " + response.getContentText());
  }
  var body = JSON.parse(response.getContentText());
  return body.content && body.content[0] && body.content[0].text ? body.content[0].text : "";
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/LetterRunner.gs /tmp/LetterRunner_check.js && node --check /tmp/LetterRunner_check.js && rm /tmp/LetterRunner_check.js` で構文チェック
2. `GlowSchema.*`/`GlowLetterContent.*`の参照が、実際の`schema.js`/`letterContent.js`の定義と一致していることを、両ファイルを読んで確認する
3. `generateNurturingDraftsForEligibleCompanies`が`GlowLetterContent.selectNurturingTargets`の戻り値をそのまま`forEach`していること、`writeLetterDraft_`が常にステータス`"下書き"`で書き込むこと(自動送信をしていないこと)をコードを目でたどって確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境・Claude APIキーが必要なため、この環境では実行できない。以下は人間が確認する手順:

1. `clasp push` で反映
2. スクリプト プロパティに `ANTHROPIC_API_KEY` を設定する
3. 企業マスタにテスト用の1社を追加し、`generateLetterDraftForCompany("<その企業ID>")` を実行する
4. 「レター下書き」タブに1行追記され、本文がそれらしい手紙文面になっていること、ステータスが「下書き」であることを確認する
5. ナーチャリング対象になりそうな企業(現在ステージ=関係構築中、ランクB、最終接触日が90日以上前)を用意し、`generateNurturingDraftsForEligibleCompanies` を実行して同様に確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報・Claude APIキーがないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/LetterRunner.gs
git commit -m "feat(glow-ma): Claude APIによるレター下書き生成機能を追加"
```

---

### Task 7: `TrackingWebApp.gs` — パーソナライズURLの反応計測(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/TrackingWebApp.gs`

**Interfaces:**
- Consumes: `GlowSchema.INTERACTION_LOG_SHEET_NAME`/`INTERACTION_LOG_HEADERS`(Phase 1〜2)
- Produces: `doGet(e)`(GAS Web Appの予約された関数名。デプロイすると自動的にHTTPエンドポイントになる)

- [ ] **Step 1: `glow-ma/src/TrackingWebApp.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: レターURLアクセスの反応計測(Web App)
 *
 * デプロイ手順(人間が一度だけ行う):
 * 1. Apps Scriptエディタの「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」を選ぶ
 * 2. 「実行ユーザー」は必ず「自分」を選ぶ(「アクセスしているユーザー」にすると、
 *    匿名の訪問者がスプレッドシートを操作する権限を持たずアクセスできない)
 * 3. 「アクセスできるユーザー」は「全員」を選ぶ(手紙を受け取った企業側の担当者が
 *    Googleアカウントなしでもアクセスできるようにするため)
 * 4. デプロイ後に発行されるURLを、スクリプト プロパティの TRACKING_BASE_URL に設定する
 * 5. スクリプト プロパティに TRACKING_REDIRECT_URL(アクセス後に案内する実際の
 *    遷移先ページ、例: 沖縄企業のミカタのトップページ)を設定する
 *
 * URL(例: <Web AppのURL>?id=C000001)へのアクセスがあると、対応履歴ログに
 * 「レターURLアクセス」として1行追記してから TRACKING_REDIRECT_URL へ案内する。
 * 存在しない企業IDでアクセスされた場合も記録は残すが(対応履歴ログ側で
 * 企業マスタに一致しないIDとして後から検知できる)、エラーにはしない。
 */
function doGet(e) {
  var companyId = e && e.parameter && e.parameter.id;
  if (companyId) {
    logTrackingAccess_(companyId);
  }
  var redirectUrl = PropertiesService.getScriptProperties().getProperty("TRACKING_REDIRECT_URL");
  if (!redirectUrl) {
    return HtmlService.createHtmlOutput("<p>ページが見つかりません。</p>");
  }
  var html = "<html><head><meta http-equiv=\"refresh\" content=\"0; url=" + redirectUrl + "\"></head>" +
    "<body>移動しています... <a href=\"" + redirectUrl + "\">こちら</a></body></html>";
  return HtmlService.createHtmlOutput(html);
}

function logTrackingAccess_(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) return;
  try {
    var nextRow = logSheet.getLastRow() + 1;
    var logId = "H-" + Utilities.getUuid();
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
    logSheet.getRange(nextRow, 1, 1, GlowSchema.INTERACTION_LOG_HEADERS.length).setValues([[
      logId, companyId, todayString, "システム(自動記録)", "レターURLアクセス", "未接触",
      "パーソナライズURL経由のアクセス", ""
    ]]);
  } finally {
    lock.releaseLock();
  }
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/TrackingWebApp.gs /tmp/TrackingWebApp_check.js && node --check /tmp/TrackingWebApp_check.js && rm /tmp/TrackingWebApp_check.js` で構文チェック
2. `GlowSchema.INTERACTION_LOG_HEADERS`の列順(履歴ID/企業ID/日付/担当者/種別/対応相手/内容メモ/次回アクション)と、`logTrackingAccess_`が`setValues`に渡す配列の順序が一致していることを、`glow-ma/src/schema.js`を読んで確認する
3. `companyId`が空(`e.parameter.id`が渡されない直接アクセス)の場合、`logTrackingAccess_`が呼ばれず、`doGet`が例外を投げずにリダイレクトHTMLを返すことをコードを目でたどって確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間が確認する手順:

1. 上記のデプロイ手順1〜5を実施する
2. `<Web AppのURL>?id=<実在する企業ID>` にブラウザでアクセスし、TRACKING_REDIRECT_URLへ自動的に遷移することを確認する
3. 対応履歴ログに、その企業ID・種別「レターURLアクセス」の行が追記されていることを確認する
4. `<Web AppのURL>`(idパラメータなし)にアクセスしても、エラーにならずリダイレクトのみ行われることを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がなく、Web Appのデプロイもできないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/TrackingWebApp.gs
git commit -m "feat(glow-ma): レターURLアクセスの反応計測Web Appを追加"
```

---

### Task 8: READMEにPhase 4のセットアップ・使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜7の全成果物
- Produces: GLOWチームがレター下書き生成・反応計測を運用できるようになるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の「## 次のフェーズ」の直前に以下を追記**

```markdown
## レター下書き生成・反応計測・ナーチャリング配信(Phase 4)

Claude APIで、企業ごとの提案順序(紹介ルートは直接M&A、それ以外は法人保険・
経営相談を入口)に沿ったレター文面の下書きを自動生成する。生成された下書きは
「レター下書き」タブに追記され、**自動送信はされない**。必ず内容を確認してから
送付し、送付後は手動でステータスを「送付済み」に更新すること。

**セットアップ**

1. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で
   `ANTHROPIC_API_KEY` を設定する(**コードには書かない**)
2. `clasp push` で最新コードを反映する
3. 反応計測を使う場合は、`glow-ma/src/TrackingWebApp.gs` のコメントに従って
   Web Appをデプロイし(実行ユーザー: 自分 / アクセスできるユーザー: 全員)、
   発行されたURLを `TRACKING_BASE_URL` に、遷移先ページのURLを
   `TRACKING_REDIRECT_URL` にそれぞれスクリプト プロパティで設定する

**使い方**

- 1社分の初回DM下書きを作る: `generateLetterDraftForCompany("<企業ID>")` を実行する
- ナーチャリング対象企業(関係構築中以降・ランクB以下・最終接触から90日以上)
  全件分の下書きをまとめて作る: `generateNurturingDraftsForEligibleCompanies` を実行する
- レターに載せるURLは `<TRACKING_BASE_URLのWeb App>?id=<企業ID>` の形になる。
  アクセスがあると対応履歴ログに「レターURLアクセス」として自動記録される

**現時点の制約:**
- レター文面のトーン・構成はプロンプトのたたき台であり、実際に送った反応を
  見ながら調整が必要
- ナーチャリング配信のコンテンツソース(成功事例・税制改正情報等)は
  Claude APIが一般知識から生成する。社内の実際の成功事例を反映させる仕組みは
  今後の課題(設計書15章オープンクエスチョン)
```

- [ ] **Step 2: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): レター下書き生成・反応計測(Phase 4)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage(設計書との対応)**

- 10章(レター生成・反応計測)→ Task 2, 3, 6, 7
- 11章(ナーチャリング配信)→ Task 4, 6
- 7章(提案順序ガイドライン)→ Task 2の`determineLeadProduct`で実装
- 12章(ダッシュボード)は本Planの範囲外(冒頭に明記済み)

**Placeholder scan:** TBD/TODO等の記述なし。レター文面のプロンプトは初版であることをREADMEに明記済み(プレースホルダーではなく動作する実装)。

**Type consistency:** `GlowLetterContent`の関数名・引数・戻り値は各Taskの Interfaces と実装コードで一致させた。`selectNurturingTargets`が`GlowAlerting.daysBetween`を呼び出す箇所は、Phase 3で確定済みのシグネチャ(`daysBetween(fromValue, toValue): number|null`)とそのまま整合する。`LetterRunner.gs`/`TrackingWebApp.gs`は`readCompanyRecords_`(Phase 1)を再定義せず、GASのグローバルスコープ経由でそのまま呼び出す設計とした。自動送信を行わない制約は、`writeLetterDraft_`が常に`"下書き"`ステータスで書き込むことで担保している。
