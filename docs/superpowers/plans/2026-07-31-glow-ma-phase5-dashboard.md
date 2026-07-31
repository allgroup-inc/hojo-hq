# GLOW M&A台帳 Phase 5(ダッシュボード自動集計)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 企業マスタ・紹介パートナーマスタから、ルート別×ステージ別ファネル・提案商品別サマリー・ランク別サマリー(滞留企業数・掘り起こし待ち件数)・紹介パートナー別サマリーを自動集計し、「ダッシュボード」タブに書き出す。

**Architecture:** 集計ロジック(ファネル・サマリーの計算)はGAS/Node両対応のUMD形式プレーンJSとして`glow-ma/src/dashboard.js`に実装し、`node --test`でユニットテストする。ランク別サマリーはPhase 3の`GlowAlerting.resolveEffectiveRank`/`isOverdue`をそのまま再利用する。**Phase 4最終レビューで見つかった「モジュール読み込み時にトップレベルで他モジュールを参照すると、GASのファイル読み込み順序に依存して壊れる」不具合を踏まえ、`dashboard.js`は最初から関数呼び出し時の遅延解決(`getGlowAlerting_()`ヘルパー)でGlowAlertingを参照する。** GAS専用の`DashboardRunner.gs`は、企業マスタ・紹介パートナーマスタを読み、`dashboard.js`の関数で集計し、「ダッシュボード」タブに書き出すだけの薄いグルーコードとする。

**Tech Stack:** Google Apps Script(V8ランタイム、`LockService`)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの範囲について:** 設計書12章(ダッシュボード)を実装する。ダッシュボードは既存タブ(企業マスタ・紹介パートナーマスタ)を読み取るのみで、書き込みは「ダッシュボード」タブのみに限定する(他タブへの副作用なし)。グラフ化・可視化の装飾(色分け・チャート化等)は範囲外とし、集計値を表形式で書き出すところまでとする。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データを一切コミットしない(本Planは実データを一切扱わない)
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する
- **`dashboard.js`が`GlowAlerting`を参照する箇所は、モジュールのトップレベルではなく関数呼び出し時に`getGlowAlerting_()`ヘルパー経由で遅延解決すること**(Phase 4最終レビューFinding 1と同じ理由。GASのファイル読み込み順序に依存する不具合を作らない)
- ダッシュボード集計は企業マスタ・紹介パートナーマスタの読み取り専用。ダッシュボード集計処理が他のタブ(企業マスタ・対応履歴ログ等)の内容を書き換えることは一切ない
- 「ダッシュボード」タブへの書き込みはシート全体を`clearContents()`してから作り直す方式とし、`LockService`で保護する(企業マスタ等の既存の書き込みパターンと同様)
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する(Phase 1〜4と同じ扱い)

---

## File Structure

```
glow-ma/src/
  schema.js          — 既存ファイルを修正: ダッシュボードタブの名称・プレースホルダー見出しを追加(Task 1)
  dashboard.js         — 新規: ファネル・サマリー集計ロジック(GlowDashboard)(Task 2, 3, 4)
  SheetSetup.gs         — 既存ファイルを修正: ダッシュボードタブの作成(Task 5)
  DashboardRunner.gs      — 新規: ダッシュボード集計・書き出し(Task 6、GAS専用)
tests/
  glow_ma_dashboard.test.mjs   — 新規(Task 2, 3, 4)
glow-ma/README.md      — Phase 5の使い方を追記(Task 7)
```

---

### Task 1: `schema.js` — ダッシュボードタブの定義を追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.DASHBOARD_SHEET_NAME`(string、`"ダッシュボード"`)、`GlowSchema.DASHBOARD_PLACEHOLDER_HEADERS`(string[]、1要素)。Task 5(タブ作成)とTask 6(書き込み先確認)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs` の末尾に追記:

```js
test("ダッシュボードタブの名称・プレースホルダー見出しが定義されている", () => {
  assert.equal(schema.DASHBOARD_SHEET_NAME, "ダッシュボード");
  assert.deepEqual(schema.DASHBOARD_PLACEHOLDER_HEADERS, [
    "ダッシュボード(updateDashboardを実行すると内容が生成されます)"
  ]);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`schema.DASHBOARD_SHEET_NAME`が`undefined`)

- [ ] **Step 3: `glow-ma/src/schema.js` に定義を追加**

`LETTER_DRAFT_STATUSES`の定義の直後に追加する:

```js
  var DASHBOARD_SHEET_NAME = "ダッシュボード";
  var DASHBOARD_PLACEHOLDER_HEADERS = ["ダッシュボード(updateDashboardを実行すると内容が生成されます)"];
```

`api`オブジェクトに追加する(既存のプロパティはそのまま残し、以下を追記):

```js
    DASHBOARD_SHEET_NAME: DASHBOARD_SHEET_NAME,
    DASHBOARD_PLACEHOLDER_HEADERS: DASHBOARD_PLACEHOLDER_HEADERS
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト + 新規1テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): ダッシュボードタブのスキーマ定義を追加"
```

---

### Task 2: `dashboard.js` — ルート×ステージファネルと提案商品別サマリー

**Files:**
- Create: `glow-ma/src/dashboard.js`
- Test: `tests/glow_ma_dashboard.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowDashboard`オブジェクト。`DEFAULT_CONFIG`(object。`routes`/`stages`/`products`/`ranks`の各配列を持つ)、`buildRouteStageFunnel(records, config)`: `{流入ルート, 現在ステージ, 件数}[]`(全ルート×全ステージの組み合わせを網羅し、複数ルートを持つ企業は該当する全ルートでカウントされる)、`buildProductFunnel(records, config)`: `{商品, 提案数, 案件化数, 成約数}[]`

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_dashboard.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dashboard = require("../glow-ma/src/dashboard.js");

test("buildRouteStageFunnel: ルート×ステージの組み合わせごとに件数を集計する(複数ルートを持つ企業は両方にカウントされる)", () => {
  const records = [
    { 流入ルート: ["①紹介"], 現在ステージ: "未接触" },
    { 流入ルート: ["①紹介", "②手紙DM"], 現在ステージ: "関係構築中" },
    { 流入ルート: ["③ミカタ経由"], 現在ステージ: "未接触" }
  ];
  const funnel = dashboard.buildRouteStageFunnel(records, dashboard.DEFAULT_CONFIG);
  const find = (route, stage) => funnel.find((f) => f["流入ルート"] === route && f["現在ステージ"] === stage);
  assert.equal(find("①紹介", "未接触")["件数"], 1);
  assert.equal(find("①紹介", "関係構築中")["件数"], 1);
  assert.equal(find("②手紙DM", "関係構築中")["件数"], 1);
  assert.equal(find("③ミカタ経由", "未接触")["件数"], 1);
  assert.equal(find("②手紙DM", "未接触")["件数"], 0);
  assert.equal(funnel.length, dashboard.DEFAULT_CONFIG.routes.length * dashboard.DEFAULT_CONFIG.stages.length);
});

test("buildRouteStageFunnel: 空配列なら全組み合わせが0件", () => {
  const funnel = dashboard.buildRouteStageFunnel([], dashboard.DEFAULT_CONFIG);
  assert.ok(funnel.every((f) => f["件数"] === 0));
});

test("buildProductFunnel: 提案商品ごとに提案数・案件化数・成約数を集計する", () => {
  const records = [
    { 提案商品: ["M&A"], 現在ステージ: "案件化" },
    { 提案商品: ["M&A", "不動産"], 現在ステージ: "成約" },
    { 提案商品: ["法人保険"], 現在ステージ: "提案中" }
  ];
  const summary = dashboard.buildProductFunnel(records, dashboard.DEFAULT_CONFIG);
  const find = (product) => summary.find((s) => s["商品"] === product);
  assert.deepEqual(find("M&A"), { "商品": "M&A", "提案数": 2, "案件化数": 1, "成約数": 1 });
  assert.deepEqual(find("不動産"), { "商品": "不動産", "提案数": 1, "案件化数": 0, "成約数": 1 });
  assert.deepEqual(find("法人保険"), { "商品": "法人保険", "提案数": 1, "案件化数": 0, "成約数": 0 });
});

test("buildProductFunnel: 提案商品が未設定の企業は集計対象外", () => {
  const records = [{ 現在ステージ: "未接触" }];
  const summary = dashboard.buildProductFunnel(records, dashboard.DEFAULT_CONFIG);
  summary.forEach((s) => assert.equal(s["提案数"], 0));
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: FAIL(`glow-ma/src/dashboard.js`が存在しない)

- [ ] **Step 3: `glow-ma/src/dashboard.js` を作成し `buildRouteStageFunnel` / `buildProductFunnel` を実装**

```js
/* GLOW企業リレーション台帳 ダッシュボード集計ロジック
 * ブラウザ相当のGAS(global.GlowDashboard)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_dashboard.test.mjs で検証される。
 *
 * ランク別サマリーは glow-ma/src/alerting.js の GlowAlerting をそのまま利用し、
 * 実効ランク・掘り起こし判定ロジックを重複定義しない。GASのファイル読み込み順序に
 * 依存しないよう、モジュール読み込み時ではなく関数呼び出し時に遅延解決する
 * (Phase 4最終レビューで見つかった同種の不具合の再発防止)。
 */
(function (global) {
  "use strict";

  function getGlowAlerting_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./alerting.js");
    }
    return global.GlowAlerting;
  }

  var DEFAULT_CONFIG = {
    routes: ["①紹介", "②手紙DM", "③ミカタ経由"],
    stages: ["未接触", "アプローチ実施", "電話済み", "相談実施", "関係構築中", "提案中", "案件化", "成約", "見送り"],
    products: ["M&A", "不動産", "法人保険"],
    ranks: ["A", "B", "C", "D"]
  };

  function buildRouteStageFunnel(records, config) {
    config = config || DEFAULT_CONFIG;
    var counts = {};
    config.routes.forEach(function (route) {
      counts[route] = {};
      config.stages.forEach(function (stage) {
        counts[route][stage] = 0;
      });
    });
    (records || []).forEach(function (record) {
      var routes = record["流入ルート"] || [];
      var stage = record["現在ステージ"];
      routes.forEach(function (route) {
        if (counts[route] && Object.prototype.hasOwnProperty.call(counts[route], stage)) {
          counts[route][stage]++;
        }
      });
    });
    var result = [];
    config.routes.forEach(function (route) {
      config.stages.forEach(function (stage) {
        result.push({ "流入ルート": route, "現在ステージ": stage, "件数": counts[route][stage] });
      });
    });
    return result;
  }

  function buildProductFunnel(records, config) {
    config = config || DEFAULT_CONFIG;
    var counts = {};
    config.products.forEach(function (product) {
      counts[product] = { "提案数": 0, "案件化数": 0, "成約数": 0 };
    });
    (records || []).forEach(function (record) {
      var products = record["提案商品"] || [];
      var stage = record["現在ステージ"];
      products.forEach(function (product) {
        if (!counts[product]) return;
        counts[product]["提案数"]++;
        if (stage === "案件化") counts[product]["案件化数"]++;
        if (stage === "成約") counts[product]["成約数"]++;
      });
    });
    return config.products.map(function (product) {
      return {
        "商品": product,
        "提案数": counts[product]["提案数"],
        "案件化数": counts[product]["案件化数"],
        "成約数": counts[product]["成約数"]
      };
    });
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    buildRouteStageFunnel: buildRouteStageFunnel,
    buildProductFunnel: buildProductFunnel
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowDashboard = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

`getGlowAlerting_`はこの時点では未使用だが、Task 3で使うため先に定義しておく(brief通りの構成)。

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: PASS(4 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dashboard.js tests/glow_ma_dashboard.test.mjs
git commit -m "feat(glow-ma): ルート×ステージファネルと提案商品別サマリーの集計ロジックを追加"
```

---

### Task 3: `dashboard.js` — ランク別サマリー

**Files:**
- Modify: `glow-ma/src/dashboard.js`
- Modify: `tests/glow_ma_dashboard.test.mjs`

**Interfaces:**
- Consumes: `GlowAlerting.resolveEffectiveRank`/`isOverdue`(`glow-ma/src/alerting.js`、Phase 3。`getGlowAlerting_()`経由で遅延解決)
- Produces: `buildRankSummary(records, todayValue, config)`: `{ランク, 滞留企業数, 掘り起こし待ち件数}[]`。Task 6の`DashboardRunner.gs`が呼び出す

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_dashboard.test.mjs` に追記:

```js
test("buildRankSummary: 実効ランクごとに滞留企業数と掘り起こし待ち件数を集計する(紹介ルートは常にAとして数える)", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01" },
    { 企業ID: "C2", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-27" },
    { 企業ID: "C3", ランク: "D", 流入ルート: ["①紹介"], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-01" }
  ];
  const summary = dashboard.buildRankSummary(records, "2026-07-27", dashboard.DEFAULT_CONFIG);
  const find = (rank) => summary.find((s) => s["ランク"] === rank);
  assert.equal(find("A")["滞留企業数"], 3);
  assert.equal(find("A")["掘り起こし待ち件数"], 1);
  assert.equal(find("D")["滞留企業数"], 0);
});

test("buildRankSummary: 対象企業がなければ全ランク0件", () => {
  const summary = dashboard.buildRankSummary([], "2026-07-27", dashboard.DEFAULT_CONFIG);
  summary.forEach((s) => {
    assert.equal(s["滞留企業数"], 0);
    assert.equal(s["掘り起こし待ち件数"], 0);
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: FAIL(`dashboard.buildRankSummary is not a function`)

- [ ] **Step 3: `buildRankSummary` を実装**

`glow-ma/src/dashboard.js` の `buildProductFunnel` 関数の直後に追加する:

```js
  function buildRankSummary(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var alerting = getGlowAlerting_();
    var counts = {};
    config.ranks.forEach(function (rank) {
      counts[rank] = { "滞留企業数": 0, "掘り起こし待ち件数": 0 };
    });
    (records || []).forEach(function (record) {
      var effectiveRank = alerting.resolveEffectiveRank(record);
      if (!counts[effectiveRank]) return;
      counts[effectiveRank]["滞留企業数"]++;
      if (alerting.isOverdue(record, todayValue)) {
        counts[effectiveRank]["掘り起こし待ち件数"]++;
      }
    });
    return config.ranks.map(function (rank) {
      return {
        "ランク": rank,
        "滞留企業数": counts[rank]["滞留企業数"],
        "掘り起こし待ち件数": counts[rank]["掘り起こし待ち件数"]
      };
    });
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    buildRouteStageFunnel: buildRouteStageFunnel,
    buildProductFunnel: buildProductFunnel,
    buildRankSummary: buildRankSummary
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: PASS(6 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dashboard.js tests/glow_ma_dashboard.test.mjs
git commit -m "feat(glow-ma): ランク別サマリー(滞留企業数・掘り起こし待ち件数)の集計ロジックを追加"
```

---

### Task 4: `dashboard.js` — 紹介パートナー別サマリーの整形

**Files:**
- Modify: `glow-ma/src/dashboard.js`
- Modify: `tests/glow_ma_dashboard.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `formatPartnerSummary(partnerRecords)`: `{名称, 累計紹介数, 成約数, 関係性ランク, 提供済み情報ログ, 逆紹介履歴}[]`(欠損フィールドは空文字で埋める)。Task 6の`DashboardRunner.gs`が呼び出す

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_dashboard.test.mjs` に追記:

```js
test("formatPartnerSummary: パートナーマスタの表示用フィールドを整形する", () => {
  const partners = [
    { 名称: "テスト税理士法人", 累計紹介数: 5, 成約数: 1, 関係性ランク: "高", 提供済み情報ログ: "建設業向け資料を提供", 逆紹介履歴: "サンプル建設を紹介" }
  ];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.deepEqual(summary, [
    { "名称": "テスト税理士法人", "累計紹介数": 5, "成約数": 1, "関係性ランク": "高", "提供済み情報ログ": "建設業向け資料を提供", "逆紹介履歴": "サンプル建設を紹介" }
  ]);
});

test("formatPartnerSummary: 欠損フィールドは空文字で埋める", () => {
  const summary = dashboard.formatPartnerSummary([{ 名称: "テスト銀行" }]);
  assert.deepEqual(summary[0], { "名称": "テスト銀行", "累計紹介数": "", "成約数": "", "関係性ランク": "", "提供済み情報ログ": "", "逆紹介履歴": "" });
});

test("formatPartnerSummary: 空配列なら空配列", () => {
  assert.deepEqual(dashboard.formatPartnerSummary([]), []);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: FAIL(`dashboard.formatPartnerSummary is not a function`)

- [ ] **Step 3: `formatPartnerSummary` を実装**

`glow-ma/src/dashboard.js` の `buildRankSummary` 関数の直後に追加する:

```js
  var PARTNER_SUMMARY_FIELDS = ["名称", "累計紹介数", "成約数", "関係性ランク", "提供済み情報ログ", "逆紹介履歴"];

  function formatPartnerSummary(partnerRecords) {
    return (partnerRecords || []).map(function (partner) {
      var summary = {};
      PARTNER_SUMMARY_FIELDS.forEach(function (field) {
        var value = partner[field];
        summary[field] = value === undefined || value === null ? "" : value;
      });
      return summary;
    });
  }
```

`api`オブジェクトを次のように更新する(最終形):

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    buildRouteStageFunnel: buildRouteStageFunnel,
    buildProductFunnel: buildProductFunnel,
    buildRankSummary: buildRankSummary,
    formatPartnerSummary: formatPartnerSummary
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: PASS(9 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dashboard.js tests/glow_ma_dashboard.test.mjs
git commit -m "feat(glow-ma): 紹介パートナー別サマリーの整形ロジックを追加"
```

---

### Task 5: `SheetSetup.gs` — ダッシュボードタブの作成(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.DASHBOARD_SHEET_NAME`/`DASHBOARD_PLACEHOLDER_HEADERS`(Task 1)
- Produces: `ensureLedgerTabs()`実行時に「ダッシュボード」タブが(存在しなければ)作成される

- [ ] **Step 1: `glow-ma/src/SheetSetup.gs` を修正**

`ensureLedgerTabs()`関数の末尾(`applyLetterDraftStatusValidation_(letterDraftSheet);`の直後)に以下を追加する:

```js
  ensureTab_(ss, GlowSchema.DASHBOARD_SHEET_NAME, GlowSchema.DASHBOARD_PLACEHOLDER_HEADERS);
```

ファイル冒頭のコメントも、タブが6個になったことがわかるように更新する(「5タブ」を「6タブ」に、タブ名の列挙に「ダッシュボード」を追加)。**既存の`ensureTab_`・`applyInteractionTypeValidation_`・`applyRespondentValidation_`・`applyLetterDraftStatusValidation_`関数と、それらの呼び出しは変更・削除しないこと。**

- [ ] **Step 2: 静的チェック**

Run: `cp glow-ma/src/SheetSetup.gs /tmp/SheetSetup_check.js && node --check /tmp/SheetSetup_check.js && rm /tmp/SheetSetup_check.js`
Expected: 構文エラーなし

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. `ensureLedgerTabs` を実行
3. 「ダッシュボード」タブが作成され、A1セルにプレースホルダー文言が入っていることを確認する
4. 既存の5タブ(企業マスタ・対応履歴ログ・紹介パートナーマスタ・設定・レター下書き)が壊れていないことも確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): ダッシュボードタブの作成を追加"
```

---

### Task 6: `DashboardRunner.gs` — ダッシュボード集計・書き出し(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/DashboardRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.COMPANY_MASTER_SHEET_NAME`/`PARTNER_MASTER_SHEET_NAME`/`PARTNER_MASTER_HEADERS`/`DASHBOARD_SHEET_NAME`(Phase 1・Task 1)、`GlowDashboard.buildRouteStageFunnel`/`buildProductFunnel`/`buildRankSummary`/`formatPartnerSummary`(Task 2〜4)、`readCompanyRecords_`(`glow-ma/src/ImportRunner.gs`。**再定義しないこと**)
- Produces: `updateDashboard()`関数(引数なし)。「ダッシュボード」タブの内容を集計結果で作り直す

- [ ] **Step 1: `glow-ma/src/DashboardRunner.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: ダッシュボードの自動集計
 * Apps Scriptエディタの関数選択で updateDashboard を選び、実行ボタンで手動実行する。
 * (将来的には日次・週次の時間主導トリガーに登録して自動実行することを想定しているが、
 *  トリガー登録自体は本Planの範囲外。)
 *
 * 実行すると、企業マスタ・紹介パートナーマスタを読み取り、以下4つの表を
 * 「ダッシュボード」タブに作り直す。他のタブへの書き込みは一切行わない。
 * - ルート別×ステージ別ファネル
 * - 提案商品別サマリー(提案数・案件化数・成約数)
 * - ランク別サマリー(滞留企業数・掘り起こし待ち件数)
 * - 紹介パートナー別サマリー
 */
function updateDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var dashboardSheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);
  if (!dashboardSheet) {
    throw new Error("ダッシュボードタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var partnerSheet = ss.getSheetByName(GlowSchema.PARTNER_MASTER_SHEET_NAME);

  var records = readCompanyRecords_(companySheet);
  var partnerRecords = readPartnerRecords_(partnerSheet);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");

  var funnel = GlowDashboard.buildRouteStageFunnel(records, GlowDashboard.DEFAULT_CONFIG);
  var productSummary = GlowDashboard.buildProductFunnel(records, GlowDashboard.DEFAULT_CONFIG);
  var rankSummary = GlowDashboard.buildRankSummary(records, todayString, GlowDashboard.DEFAULT_CONFIG);
  var partnerSummary = GlowDashboard.formatPartnerSummary(partnerRecords);

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error("他の処理がダッシュボードを操作中のため、更新を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    dashboardSheet.clearContents();
    var row = 1;
    row = writeDashboardSection_(dashboardSheet, row, "ルート別×ステージ別ファネル",
      ["流入ルート", "現在ステージ", "件数"],
      funnel.map(function (f) { return [f["流入ルート"], f["現在ステージ"], f["件数"]]; }));
    row++;
    row = writeDashboardSection_(dashboardSheet, row, "提案商品別サマリー",
      ["商品", "提案数", "案件化数", "成約数"],
      productSummary.map(function (p) { return [p["商品"], p["提案数"], p["案件化数"], p["成約数"]]; }));
    row++;
    row = writeDashboardSection_(dashboardSheet, row, "ランク別サマリー",
      ["ランク", "滞留企業数", "掘り起こし待ち件数"],
      rankSummary.map(function (r) { return [r["ランク"], r["滞留企業数"], r["掘り起こし待ち件数"]]; }));
    row++;
    row = writeDashboardSection_(dashboardSheet, row, "紹介パートナー別サマリー",
      ["名称", "累計紹介数", "成約数", "関係性ランク", "提供済み情報ログ", "逆紹介履歴"],
      partnerSummary.map(function (p) {
        return [p["名称"], p["累計紹介数"], p["成約数"], p["関係性ランク"], p["提供済み情報ログ"], p["逆紹介履歴"]];
      }));
    row++;
    dashboardSheet.getRange(row, 1).setValue(
      "最終更新: " + Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm")
    );
  } finally {
    lock.releaseLock();
  }

  Logger.log("ダッシュボード更新完了");
}

function writeDashboardSection_(sheet, startRow, title, headers, rows) {
  sheet.getRange(startRow, 1).setValue(title);
  var headerRow = startRow + 1;
  sheet.getRange(headerRow, 1, 1, headers.length).setValues([headers]);
  if (rows.length > 0) {
    sheet.getRange(headerRow + 1, 1, rows.length, headers.length).setValues(rows);
  }
  return headerRow + 1 + rows.length;
}

function readPartnerRecords_(sheet) {
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.PARTNER_MASTER_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    return record;
  });
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/DashboardRunner.gs /tmp/DashboardRunner_check.js && node --check /tmp/DashboardRunner_check.js && rm /tmp/DashboardRunner_check.js` で構文チェック
2. `GlowSchema.*`/`GlowDashboard.*`の参照が、実際の`schema.js`/`dashboard.js`の定義と一致していることを、両ファイルを読んで確認する。特に`GlowSchema.PARTNER_MASTER_HEADERS`(Phase 1で定義済み)の列順と`readPartnerRecords_`の読み取りロジックが対応していることを確認する
3. 企業マスタが空(0件)・紹介パートナーマスタが空(0件)の場合でも、`updateDashboard`が例外を投げずに4つの空セクション+最終更新時刻を書き出すことをコードを目でたどって確認する
4. `writeDashboardSection_`が返す`row`の値を手計算し、4セクション分の見出し・データ行数から最終更新時刻が書き込まれる行番号が正しく求まることを確認する(例: ルート別ファネル27行+見出し1行+タイトル1行=29行、次のセクションのタイトルは31行目から、という具合に)

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. 企業マスタ・紹介パートナーマスタにテスト用のデータを数件用意する(Phase 2の`recalculateAllScores`も実行してランクを入れておくとランク別サマリーが確認しやすい)
3. `updateDashboard` を実行する
4. 「ダッシュボード」タブに4つの表(ルート別×ステージ別ファネル/提案商品別サマリー/ランク別サマリー/紹介パートナー別サマリー)と最終更新時刻が表示され、テストデータの内容と一致することを確認する
5. 再度 `updateDashboard` を実行し、前回の内容が正しく上書きされること(重複して残らないこと)を確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/DashboardRunner.gs
git commit -m "feat(glow-ma): ダッシュボードの自動集計・書き出し機能を追加"
```

---

### Task 7: READMEにPhase 5の使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜6の全成果物
- Produces: GLOWチームがダッシュボードを運用できるようになるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の「## 次のフェーズ」の直前に以下を追記**

```markdown
## ダッシュボード(Phase 5)

企業マスタ・紹介パートナーマスタから、ルート別×ステージ別ファネル・提案商品別
サマリー・ランク別サマリー(滞留企業数・掘り起こし待ち件数)・紹介パートナー別
サマリーを自動集計し、「ダッシュボード」タブに書き出す。

**使い方**

1. `clasp push` で最新コードを反映する
2. Apps Scriptエディタで `updateDashboard` を実行する
3. 「ダッシュボード」タブの内容が最新の集計結果に更新される(実行のたびに
   タブの内容は作り直される)

**現時点の制約:**
- グラフ化・色分け等の視覚的な装飾は行っていない。集計値の表のみ
- 定期実行(日次・週次トリガー登録)は人間が手動で設定する運用とする
```

- [ ] **Step 2: `glow-ma/README.md` の「## 次のフェーズ」の内容を、ダッシュボードが実装済みになったことを反映して更新する(該当する文があれば「ダッシュボード」の記載を削除し、それ以外に未実装の項目がなければセクション自体の文言を「Phase 1〜5ですべての実装フェーズが完了しました」のような趣旨に更新する)**

- [ ] **Step 3: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): ダッシュボード(Phase 5)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage(設計書との対応)**

- 12章(ダッシュボード: ルート別×ステージ別ファネル・提案商品別サマリー・ランク別サマリー・紹介パートナー別サマリー)→ Task 2〜4, 6
- 13章の実装フェーズ5「ダッシュボード自動集計」→ 本Plan全体で対応

**Placeholder scan:** TBD/TODO等の記述なし。

**Type consistency:** `GlowDashboard`の関数名・引数・戻り値は各Taskの Interfaces と実装コードで一致させた。`buildRankSummary`は`GlowAlerting.resolveEffectiveRank`/`isOverdue`(Phase 3で確定済みのシグネチャ)をそのまま呼び出しており、名前・引数の食い違いはない。`GlowAlerting`の参照はPhase 4最終レビューの教訓を踏まえ、モジュール読み込み時ではなく関数呼び出し時に遅延解決する設計とし、同種の不具合を未然に防いだ。`DashboardRunner.gs`は`readCompanyRecords_`(Phase 1)を再定義せず、`readPartnerRecords_`は新規に必要になったため新設した(紹介パートナーマスタの読み取りは本Planが初出のため重複ではない)。ダッシュボード集計は読み取り専用であり、企業マスタ・対応履歴ログ等の既存タブを書き換えないことを設計・実装の両方で担保している。
