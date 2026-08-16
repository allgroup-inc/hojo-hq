# glow-ma 事前選定スコア・ランクの取り込み Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 外部の事前選定リスト(仮ランク・仮スコア付き)を企業マスタに正しく取り込み、glow-ma独自のスコア計算にも反映されるようにする。

**Architecture:** 企業マスタに「事前選定ランク」「事前選定スコア」列を新設する。会社名の正規化・突き合わせロジックは`preScreeningImport.js`という新規の純粋関数モジュール(UMD形式、Node側でテスト)に切り出し、GAS側の`PreScreeningRunner.gs`はスプレッドシートの読み書きとロック制御のみを担う薄いオーケストレーション層にする(既存の`AdminRunner.gs`等と同じ設計思想)。`scoring.js`に事前選定スコアを取り出す純粋関数を1つ追加し、`ScoringRunner.gs`の初期スコア計算式に組み込む。

**Tech Stack:** Google Apps Script (GAS) + Google Sheets、UMD形式のJSモジュール。テストは`node --test`(GAS専用コードはNode単体テスト対象外、既存パターンを踏襲)。

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-08-11-glow-ma-pre-screening-score-import-design.md`(以下「設計書」)の内容に従う
- `COMPANY_MASTER_HEADERS`は末尾への追加のみ許可(既存データの列位置がズレて破損するため、途中への挿入は禁止。`schema.js`冒頭のコメント参照)
- `dedupe.js`の`SCALAR_FIELDS`と`schema.js`の`COMPANY_MASTER_HEADERS`は、特別扱いされる項目(流入ルート・提案商品・備考・連絡不要・関係メモ)と合わせて過不足なく一致することを検証する既存テスト
  (`tests/glow_ma_dedupe.test.mjs`の「SCALAR_FIELDS: ...スキーマ変更の検知」)がある。新しい列を`COMPANY_MASTER_HEADERS`に追加したら、同じコミット、または次のタスクで必ず`SCALAR_FIELDS`にも追加すること
- 会社名の正規化は「前後の空白・全角スペースの除去」+「全角英数字(0-9, A-Z, a-z相当)を半角に変換」のみ。全角の記号(括弧等)の変換やあいまい一致は行わない(設計書1章)
- 未一致企業は会社名一覧を「事前選定_未一致」タブに自動で書き出すが、目視確認は必須としない(設計書4.3節)
- `applyPreScreeningScores`はGAS専用(`SpreadsheetApp`依存)のためNode単体テスト対象外。ロジック部分(正規化・突き合わせ・レコードへの反映)は`preScreeningImport.js`に切り出してNode側でテストする
- テストは`node --test tests/glow_ma_*.test.mjs`で実行し、既存分を含めすべてPASSする状態を保つ

---

### Task 1: schema.js にスキーマを追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Produces: `GlowSchema.COMPANY_MASTER_HEADERS`の末尾に`"事前選定ランク"`, `"事前選定スコア"`が追加される。
  `GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME`(文字列 `"事前選定リスト"`)、
  `GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME`(文字列 `"事前選定_未一致"`)、
  `GlowSchema.PRE_SCREENING_MISMATCH_HEADERS`(配列 `["会社名", "記録日時"]`)が新規エクスポートされる。
  Task 6(`PreScreeningRunner.gs`)がこれらを使う

**注意:** このタスク完了直後、`tests/glow_ma_dedupe.test.mjs`の「SCALAR_FIELDS: ...スキーマ変更の検知」テストが
一時的に失敗する(Global Constraintsに記載の通り、`COMPANY_MASTER_HEADERS`と`SCALAR_FIELDS`の一致を見るテストのため)。
これはTask 2で解消される想定であり、このタスクの時点では失敗したままでよい。

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs`に追加する(既存の`後継者状況`列の存在チェックテストの近くに追加するとよい):

```javascript
test("企業マスタに事前選定ランク・事前選定スコア列が存在する", () => {
  assert.ok(schema.COMPANY_MASTER_HEADERS.includes("事前選定ランク"));
  assert.ok(schema.COMPANY_MASTER_HEADERS.includes("事前選定スコア"));
});

test("事前選定リスト・事前選定_未一致タブの名称・見出しが定義されている", () => {
  assert.equal(schema.PRE_SCREENING_STAGING_SHEET_NAME, "事前選定リスト");
  assert.equal(schema.PRE_SCREENING_MISMATCH_SHEET_NAME, "事前選定_未一致");
  assert.deepEqual(schema.PRE_SCREENING_MISMATCH_HEADERS, ["会社名", "記録日時"]);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`schema.PRE_SCREENING_STAGING_SHEET_NAME is undefined`等)

- [ ] **Step 3: schema.jsに実装を追加する**

`glow-ma/src/schema.js`の`COMPANY_MASTER_HEADERS`配列(11〜18行目)の末尾に追加する:

```javascript
  var COMPANY_MASTER_HEADERS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地",
    "流入ルート", "起点担当者_紹介元", "現在ステージ", "提案商品",
    "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容",
    "担当者", "登録日", "備考",
    "電話番号", "連絡不要", "後継者状況", "関係メモ", "窓口担当者名", "携帯番号",
    "事前選定ランク", "事前選定スコア"
  ];
```

ファイル末尾付近(`STAFF_HEADERS`等が定義されている箇所の後、`var api = {`より前)に追加する:

```javascript
  var PRE_SCREENING_STAGING_SHEET_NAME = "事前選定リスト";
  var PRE_SCREENING_MISMATCH_SHEET_NAME = "事前選定_未一致";
  var PRE_SCREENING_MISMATCH_HEADERS = ["会社名", "記録日時"];
```

`api`オブジェクトに以下を追加する:

```javascript
    PRE_SCREENING_STAGING_SHEET_NAME: PRE_SCREENING_STAGING_SHEET_NAME,
    PRE_SCREENING_MISMATCH_SHEET_NAME: PRE_SCREENING_MISMATCH_SHEET_NAME,
    PRE_SCREENING_MISMATCH_HEADERS: PRE_SCREENING_MISMATCH_HEADERS,
```

- [ ] **Step 4: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 5: 全体テストを実行し、dedupeのSCALAR_FIELDSテストが予定通り失敗することを確認する**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: 「SCALAR_FIELDS: ...スキーマ変更の検知」テストのみFAIL(このタスクの時点では正常。Task 2で解消する)

- [ ] **Step 6: コミット**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 事前選定ランク・スコア列と関連タブ名を追加"
```

---

### Task 2: dedupe.js のSCALAR_FIELDSに追加

**Files:**
- Modify: `glow-ma/src/dedupe.js`

**Interfaces:**
- Consumes: `GlowSchema.COMPANY_MASTER_HEADERS`(Task 1、Node側では`schema.js`を直接require)
- Produces: `GlowDedupe.SCALAR_FIELDS`に`"事前選定ランク"`, `"事前選定スコア"`が含まれる

このタスクは新規テストを書くのではなく、Task 1で追加済みの既存テスト(`tests/glow_ma_dedupe.test.mjs`の
「SCALAR_FIELDS: ...スキーマ変更の検知」)を通すことがゴール。

- [ ] **Step 1: 現在の失敗を確認する**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: 「SCALAR_FIELDS: ...スキーマ変更の検知」テストがFAIL(Task 1から引き継いだ既知の失敗)

- [ ] **Step 2: dedupe.jsのSCALAR_FIELDSに追加する**

`glow-ma/src/dedupe.js`の`SCALAR_FIELDS`配列(39〜44行目)を以下に置き換える:

```javascript
  var SCALAR_FIELDS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地", "電話番号",
    "起点担当者_紹介元", "現在ステージ", "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容", "担当者", "登録日", "後継者状況",
    "窓口担当者名", "携帯番号", "事前選定ランク", "事前選定スコア"
  ];
```

- [ ] **Step 3: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 4: 全体テストを実行し、既存テストがすべてPASSすることを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/dedupe.js
git commit -m "feat(glow-ma): 事前選定ランク・スコアを名寄せのSCALAR_FIELDSに追加"
```

---

### Task 3: preScreeningImport.js を新規作成(正規化・突き合わせロジック)

**Files:**
- Create: `glow-ma/src/preScreeningImport.js`
- Test: `tests/glow_ma_pre_screening_import.test.mjs`

**Interfaces:**
- Consumes: なし(純粋関数のみ)
- Produces:
  - `GlowPreScreeningImport.normalizeCompanyName(name)` — 文字列を受け取り、正規化した文字列を返す
  - `GlowPreScreeningImport.matchPreScreeningRows(stagingRows, companyRecords)` —
    `stagingRows`: `[{ "会社名": string, "事前選定ランク": string, "事前選定スコア": string|number }, ...]`、
    `companyRecords`: `[{ "企業ID": string, "会社名": string, ... }, ...]`。
    戻り値: `{ matches: [{ "企業ID": string, "事前選定ランク": string, "事前選定スコア": string|number }, ...], unmatchedNames: [string, ...] }`
  - `GlowPreScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches)` —
    `companyRecords`と`matches`(上記`matches`と同じ形)を受け取り、一致した企業IDの
    「事前選定ランク」「事前選定スコア」だけを更新した**新しい**配列を返す(入力を変更しない)。
    Task 6(`PreScreeningRunner.gs`)がこれら3関数をすべて使う

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_pre_screening_import.test.mjs`を新規作成する:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const preScreeningImport = require("../glow-ma/src/preScreeningImport.js");

test("normalizeCompanyName: 前後の空白を除去する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("  太田建設株式会社  "), "太田建設株式会社");
});

test("normalizeCompanyName: 全角スペースを除去する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("株式会社　つながり"), "株式会社つながり");
});

test("normalizeCompanyName: 文中の半角・全角スペースもすべて除去する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("有限会社 ケア センター"), "有限会社ケアセンター");
});

test("normalizeCompanyName: 全角英数字を半角に変換する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("株式会社ＷＡＮ　ＳＴＹＬＥ１２３"), "株式会社WANSTYLE123");
});

test("normalizeCompanyName: 空文字・null・undefinedは空文字を返す", () => {
  assert.equal(preScreeningImport.normalizeCompanyName(""), "");
  assert.equal(preScreeningImport.normalizeCompanyName(null), "");
  assert.equal(preScreeningImport.normalizeCompanyName(undefined), "");
});

const SAMPLE_COMPANIES = [
  { "企業ID": "C000001", "会社名": "太田建設株式会社" },
  { "企業ID": "C000002", "会社名": "株式会社　南西工業" },
  { "企業ID": "C000003", "会社名": "仲程土建株式会社" }
];

test("matchPreScreeningRows: 正規化した会社名が一致した行をmatchesに含める", () => {
  const stagingRows = [
    { "会社名": "太田建設株式会社", "事前選定ランク": "仮S", "事前選定スコア": "37" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, [
    { "企業ID": "C000001", "事前選定ランク": "仮S", "事前選定スコア": "37" }
  ]);
  assert.deepEqual(result.unmatchedNames, []);
});

test("matchPreScreeningRows: 空白の入り方(半角/全角)が違っても同じ会社名なら一致する", () => {
  const stagingRows = [
    // 企業マスタ側は「株式会社　南西工業」(全角スペース)。半角スペース版でも一致するはずの確認
    { "会社名": "株式会社 南西工業", "事前選定ランク": "A", "事前選定スコア": "29" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, [
    { "企業ID": "C000002", "事前選定ランク": "A", "事前選定スコア": "29" }
  ]);
  assert.deepEqual(result.unmatchedNames, []);
});

test("matchPreScreeningRows: 部分一致では一致しない(完全一致のみ)", () => {
  const stagingRows = [
    // 企業マスタ側は「株式会社　南西工業」であり、「南西工業」だけでは一致しない
    { "会社名": "南西工業", "事前選定ランク": "A", "事前選定スコア": "29" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, []);
  assert.deepEqual(result.unmatchedNames, ["南西工業"]);
});

test("matchPreScreeningRows: 一致しない行はunmatchedNamesに元の会社名(正規化前)で入る", () => {
  const stagingRows = [
    { "会社名": "存在しない株式会社", "事前選定ランク": "B", "事前選定スコア": "10" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, []);
  assert.deepEqual(result.unmatchedNames, ["存在しない株式会社"]);
});

test("matchPreScreeningRows: 複数行を正しく振り分ける", () => {
  const stagingRows = [
    { "会社名": "太田建設株式会社", "事前選定ランク": "仮S", "事前選定スコア": "37" },
    { "会社名": "株式会社南西工業", "事前選定ランク": "仮S", "事前選定スコア": "37" },
    { "会社名": "未知の会社", "事前選定ランク": "C", "事前選定スコア": "5" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.equal(result.matches.length, 2);
  assert.deepEqual(result.unmatchedNames, ["未知の会社"]);
});

test("applyMatchesToCompanyRecords: 一致した企業のみ事前選定ランク・スコアを更新する", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "", "事前選定スコア": "" },
    { "企業ID": "C000002", "会社名": "株式会社南西工業", "事前選定ランク": "", "事前選定スコア": "" }
  ];
  const matches = [{ "企業ID": "C000001", "事前選定ランク": "仮S", "事前選定スコア": "37" }];
  const result = preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(result[0]["事前選定ランク"], "仮S");
  assert.equal(result[0]["事前選定スコア"], "37");
  assert.equal(result[1]["事前選定ランク"], "");
});

test("applyMatchesToCompanyRecords: 入力配列を変更しない", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "", "事前選定スコア": "" }
  ];
  const matches = [{ "企業ID": "C000001", "事前選定ランク": "仮S", "事前選定スコア": "37" }];
  preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(companyRecords[0]["事前選定ランク"], "");
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_pre_screening_import.test.mjs`
Expected: FAIL(`Cannot find module '../glow-ma/src/preScreeningImport.js'`)

- [ ] **Step 3: preScreeningImport.jsを実装する**

`glow-ma/src/preScreeningImport.js`を新規作成する:

```javascript
/* GLOW企業リレーション台帳 事前選定スコア・ランクの取り込みロジック(会社名の正規化・突き合わせ)
 * ブラウザ相当のGAS(global.GlowPreScreeningImport)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_pre_screening_import.test.mjs で検証される。
 *
 * 設計書: docs/superpowers/specs/2026-08-11-glow-ma-pre-screening-score-import-design.md
 */
(function (global) {
  "use strict";

  var FULLWIDTH_ALNUM_START = 0xFF10; // 全角"0"
  var FULLWIDTH_ALNUM_END = 0xFF5A;   // 全角"z"

  /**
   * 会社名を正規化する: 前後の空白除去、文中の半角・全角スペース除去、
   * 全角英数字(0-9, A-Z, a-z相当)を半角に変換する。
   * あいまい一致(表記ゆれ吸収)は行わない(設計書1章、スコープ外)。
   */
  function normalizeCompanyName(name) {
    var text = String(name || "").trim();
    text = text.replace(/[\s　]/g, "");
    text = text.replace(/[０-９Ａ-Ｚａ-ｚ]/g, function (ch) {
      var code = ch.charCodeAt(0);
      if (code < FULLWIDTH_ALNUM_START || code > FULLWIDTH_ALNUM_END) return ch;
      return String.fromCharCode(code - 0xFEE0);
    });
    return text;
  }

  /**
   * 事前選定リストの各行を、企業マスタの会社名(正規化して比較)と突き合わせる。
   * 一致したものはmatches、一致しなかったものはunmatchedNames(元の会社名、正規化前)に振り分ける。
   */
  function matchPreScreeningRows(stagingRows, companyRecords) {
    var companyIdByNormalizedName = {};
    (companyRecords || []).forEach(function (record) {
      var normalized = normalizeCompanyName(record["会社名"]);
      if (normalized) companyIdByNormalizedName[normalized] = record["企業ID"];
    });

    var matches = [];
    var unmatchedNames = [];
    (stagingRows || []).forEach(function (row) {
      var normalized = normalizeCompanyName(row["会社名"]);
      var companyId = companyIdByNormalizedName[normalized];
      if (companyId) {
        matches.push({
          "企業ID": companyId,
          "事前選定ランク": row["事前選定ランク"],
          "事前選定スコア": row["事前選定スコア"]
        });
      } else {
        unmatchedNames.push(row["会社名"]);
      }
    });

    return { matches: matches, unmatchedNames: unmatchedNames };
  }

  /**
   * 企業マスタのレコード配列に、matchesの内容(事前選定ランク・事前選定スコア)を反映した
   * 新しい配列を返す。入力配列・要素は変更しない。一致しなかった企業のレコードはそのまま返す。
   */
  function applyMatchesToCompanyRecords(companyRecords, matches) {
    var matchByCompanyId = {};
    (matches || []).forEach(function (match) {
      matchByCompanyId[match["企業ID"]] = match;
    });
    return (companyRecords || []).map(function (record) {
      var match = matchByCompanyId[record["企業ID"]];
      if (!match) return record;
      var updated = {};
      Object.keys(record).forEach(function (key) {
        updated[key] = record[key];
      });
      updated["事前選定ランク"] = match["事前選定ランク"];
      updated["事前選定スコア"] = match["事前選定スコア"];
      return updated;
    });
  }

  var api = {
    normalizeCompanyName: normalizeCompanyName,
    matchPreScreeningRows: matchPreScreeningRows,
    applyMatchesToCompanyRecords: applyMatchesToCompanyRecords
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowPreScreeningImport = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_pre_screening_import.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 5: 全体テストを実行し、既存テストがすべてPASSすることを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 6: コミット**

```bash
git add glow-ma/src/preScreeningImport.js tests/glow_ma_pre_screening_import.test.mjs
git commit -m "feat(glow-ma): 事前選定スコア取り込みの正規化・突き合わせロジックを追加"
```

---

### Task 4: scoring.js に事前選定スコアを取り出す関数を追加

**Files:**
- Modify: `glow-ma/src/scoring.js`
- Modify: `tests/glow_ma_scoring.test.mjs`

**Interfaces:**
- Consumes: なし(純粋関数)
- Produces: `GlowScoring.calculatePreScreeningScore(record)` — 企業レコード(`{ "事前選定スコア": ... }`を含む
  オブジェクト)を受け取り、数値を返す。空欄・非数値・undefinedの場合は`0`を返す。
  Task 5(`ScoringRunner.gs`)がこの関数を使う

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_scoring.test.mjs`に追加する(既存の`calculateRouteBonus`のテストの近くに追加するとよい):

```javascript
test("calculatePreScreeningScore: 事前選定スコアが数値ならそのまま返す", () => {
  assert.equal(scoring.calculatePreScreeningScore({ "事前選定スコア": 37 }), 37);
});

test("calculatePreScreeningScore: 事前選定スコアが数値の文字列でも変換して返す", () => {
  assert.equal(scoring.calculatePreScreeningScore({ "事前選定スコア": "37" }), 37);
});

test("calculatePreScreeningScore: 空欄・未設定・非数値は0を返す", () => {
  assert.equal(scoring.calculatePreScreeningScore({ "事前選定スコア": "" }), 0);
  assert.equal(scoring.calculatePreScreeningScore({}), 0);
  assert.equal(scoring.calculatePreScreeningScore({ "事前選定スコア": "未評価" }), 0);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: FAIL(`scoring.calculatePreScreeningScore is not a function`)

- [ ] **Step 3: scoring.jsに実装を追加する**

`glow-ma/src/scoring.js`の`calculateRouteBonus`関数(94〜102行目)の直後に追加する:

```javascript
  /**
   * 事前選定スコア(外部の選定作業による評価点)を数値として取り出す。
   * 空欄・非数値は0として扱い、既存の計算結果に影響しない
   * (設計書: docs/superpowers/specs/2026-08-11-glow-ma-pre-screening-score-import-design.md)。
   */
  function calculatePreScreeningScore(record) {
    var n = Number(record["事前選定スコア"]);
    return isNaN(n) ? 0 : n;
  }
```

`api`オブジェクト(138〜147行目)に`calculatePreScreeningScore: calculatePreScreeningScore,`を追加する:

```javascript
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    classifyIndustryTier: classifyIndustryTier,
    calculateSizeBandPoints: calculateSizeBandPoints,
    calculateAgeBandPoints: calculateAgeBandPoints,
    calculateAttributeScore: calculateAttributeScore,
    calculateRouteBonus: calculateRouteBonus,
    calculatePreScreeningScore: calculatePreScreeningScore,
    calculateReactionScore: calculateReactionScore,
    calculateRank: calculateRank
  };
```

- [ ] **Step 4: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 5: 全体テストを実行し、既存テストがすべてPASSすることを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 6: コミット**

```bash
git add glow-ma/src/scoring.js tests/glow_ma_scoring.test.mjs
git commit -m "feat(glow-ma): scoring.jsに事前選定スコアを取り出すcalculatePreScreeningScoreを追加"
```

---

### Task 5: ScoringRunner.gs の初期スコア計算式を変更

**Files:**
- Modify: `glow-ma/src/ScoringRunner.gs`

**Interfaces:**
- Consumes: `GlowScoring.calculatePreScreeningScore(record)`(Task 4)
- Produces: なし(既存の`recalculateAllScores`の内部処理を変更するのみ)

このタスクはGAS専用(`SpreadsheetApp`依存)のためNode単体テスト対象外。既存のNodeテストが
壊れていないことと、コードレビューで正しさを確認する。

- [ ] **Step 1: recalculateAllScores内の初期スコア計算を変更する**

`glow-ma/src/ScoringRunner.gs`の50〜54行目を以下に置き換える:

```javascript
    records.forEach(function (record) {
      var interactionRows = interactionsByCompanyId[record["企業ID"]] || [];
      var initialScore = GlowScoring.calculateAttributeScore(record)
        + GlowScoring.calculatePreScreeningScore(record)
        + GlowScoring.calculateRouteBonus(record["流入ルート"]);
      var reactionScore = GlowScoring.calculateReactionScore(interactionRows);
      var totalScore = initialScore + reactionScore;
```

(この後に続く`record["初期スコア"] = initialScore;`以降の4行は変更しない)

またファイル冒頭のコメント(6〜9行目)を、事前選定スコアも計算式に含まれることが分かるように更新する:

```javascript
 * 企業マスタの「初期スコア」= 属性スコア(業種+規模+代表者年齢) + 事前選定スコア(外部評価。
 * 空欄なら0) + 流入ルートボーナス
 * 「反応スコア」= 対応履歴ログの反応イベントの合算(GlowScoring.calculateReactionScore)
 * 「総合スコア」= 初期スコア + 反応スコア、「ランク」= 総合スコアからA〜Dを判定
```

- [ ] **Step 2: 全体テストを実行し、既存テストがすべてPASSすることを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全テスト。`ScoringRunner.gs`自体はNodeで実行されないため、この実行は既存テスト全体の
回帰確認のみ)

- [ ] **Step 3: コミット**

```bash
git add glow-ma/src/ScoringRunner.gs
git commit -m "feat(glow-ma): 初期スコア計算式に事前選定スコアを組み込む"
```

---

### Task 6: PreScreeningRunner.gs を新規作成、ImportRunner.gsにコメント追記

**Files:**
- Create: `glow-ma/src/PreScreeningRunner.gs`
- Modify: `glow-ma/src/ImportRunner.gs`

**Interfaces:**
- Consumes: `GlowPreScreeningImport.matchPreScreeningRows`, `GlowPreScreeningImport.applyMatchesToCompanyRecords`
  (Task 3)、`readCompanyRecords_` / `writeCompanyRecords_`(`ImportRunner.gs`、既存)、`ensureTab_`
  (`SheetSetup.gs`、既存)、`GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME` /
  `GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME` / `GlowSchema.PRE_SCREENING_MISMATCH_HEADERS`(Task 1)
- Produces: Apps Scriptエディタから手動実行する`applyPreScreeningScores()`関数

このタスクはGAS専用のためNode単体テスト対象外。ロジックの正しさはTask 3のテストで担保済みのため、
このタスクでは「スプレッドシートの読み書きを正しく呼び出しているか」に注意してレビューする。

- [ ] **Step 1: PreScreeningRunner.gsを作成する**

`glow-ma/src/PreScreeningRunner.gs`を新規作成する:

```javascript
/**
 * GLOW企業リレーション台帳: 事前選定スコア・ランクの取り込み(遡及反映)
 *
 * 使い方:
 * 1. スプレッドシートに「事前選定リスト」という名前のタブを作る
 * 2. 1行目に元データの見出し、2行目以降にデータを貼り付ける
 * 3. 下の PRE_SCREENING_COLUMN_MAP の右辺を、実際の見出し文字列に合わせて書き換える
 * 4. Apps Scriptエディタで applyPreScreeningScores を実行する
 *
 * 実行すると、企業マスタの会社名と「事前選定リスト」の会社名を(空白除去・全角英数字の半角変換のみの
 * 正規化で)突き合わせ、一致した企業の「事前選定ランク」「事前選定スコア」だけを更新する。
 * 一致しなかった行は件数をログに出し、会社名一覧を「事前選定_未一致」タブに書き出す
 * (目視確認は必須ではない。設計書4.3節参照)。
 *
 * 見出しが異なる複数のファイルを取り込む場合は、PRE_SCREENING_COLUMN_MAP を書き換えて
 * ファ​イルごとに複数回実行する。
 *
 * 設計書: docs/superpowers/specs/2026-08-11-glow-ma-pre-screening-score-import-design.md
 */
var PRE_SCREENING_COLUMN_MAP = {
  // 左が企業マスタの列名、右が「事前選定リスト」タブの見出し文字列。
  // 実データの見出しに合わせてここを書き換えてから実行する。
  "会社名": "正式商号",
  "事前選定ランク": "仮ランク",
  "事前選定スコア": "仮スコア"
};

function applyPreScreeningScores() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error(
      "他の処理が企業マスタを操作中のため、取り込みを開始できませんでした。" +
      "しばらく待ってから再実行してください。"
    );
  }
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var stagingSheet = ss.getSheetByName(GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME);
    if (!stagingSheet) {
      throw new Error(
        "「" + GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME + "」タブが見つかりません。" +
        "元データを貼り付けてから実行してください。"
      );
    }
    var values = stagingSheet.getDataRange().getValues();
    if (values.length < 2) {
      Logger.log("取り込み対象のデータ行がありません。");
      return;
    }
    var headerRow = values[0].map(String);

    var missingHeaders = Object.keys(PRE_SCREENING_COLUMN_MAP)
      .map(function (targetField) { return PRE_SCREENING_COLUMN_MAP[targetField]; })
      .filter(function (sourceHeader) { return headerRow.indexOf(sourceHeader) === -1; });
    if (missingHeaders.length > 0) {
      throw new Error(
        "PRE_SCREENING_COLUMN_MAP が「" + GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME +
        "」タブの見出しと一致しません。見つからない見出し: " + missingHeaders.join("、") +
        " / PRE_SCREENING_COLUMN_MAP を実際の見出しに合わせて書き換えてから再実行してください。"
      );
    }

    var stagingRows = values.slice(1).map(function (row) {
      var stagingRow = {};
      Object.keys(PRE_SCREENING_COLUMN_MAP).forEach(function (targetField) {
        var sourceHeader = PRE_SCREENING_COLUMN_MAP[targetField];
        var columnIndex = headerRow.indexOf(sourceHeader);
        stagingRow[targetField] = row[columnIndex];
      });
      return stagingRow;
    });

    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    if (!companySheet) {
      throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
    }
    var companyRecords = readCompanyRecords_(companySheet);

    var matchResult = GlowPreScreeningImport.matchPreScreeningRows(stagingRows, companyRecords);
    var updatedRecords = GlowPreScreeningImport.applyMatchesToCompanyRecords(companyRecords, matchResult.matches);
    writeCompanyRecords_(companySheet, updatedRecords);

    Logger.log(
      "事前選定スコア取り込み完了: 一致 " + matchResult.matches.length + "件 / " +
      "未一致 " + matchResult.unmatchedNames.length + "件"
    );

    if (matchResult.unmatchedNames.length > 0) {
      var mismatchSheet = ss.getSheetByName(GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME);
      if (!mismatchSheet) {
        mismatchSheet = ensureTab_(ss, GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME, GlowSchema.PRE_SCREENING_MISMATCH_HEADERS);
      }
      var recordedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
      var mismatchRows = matchResult.unmatchedNames.map(function (name) {
        return [name, recordedAt];
      });
      var nextRow = mismatchSheet.getLastRow() + 1;
      mismatchSheet.getRange(nextRow, 1, mismatchRows.length, GlowSchema.PRE_SCREENING_MISMATCH_HEADERS.length)
        .setValues(mismatchRows);
    }
  } finally {
    lock.releaseLock();
  }
}
```

- [ ] **Step 2: ImportRunner.gsに事前選定ランク・スコアの追加マッピング例をコメントで追記する**

`glow-ma/src/ImportRunner.gs`の`IMPORT_COLUMN_MAP`(13〜27行目)の既存コメント(24〜26行目、
「将来、取り込み元リストにDNC...」のくだり)の直後に追加する:

```javascript
  // 将来、取り込み元リストに事前選定ランク・事前選定スコアの列がある場合は、
  // "事前選定ランク": "<実データの見出し>", "事前選定スコア": "<実データの見出し>" を
  // ここに追加すればよい(csvImport.jsの汎用マッピング処理がそのまま対応する)。
```

- [ ] **Step 3: 全体テストを実行し、既存テストがすべてPASSすることを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 4: コミット**

```bash
git add glow-ma/src/PreScreeningRunner.gs glow-ma/src/ImportRunner.gs
git commit -m "feat(glow-ma): 事前選定スコアの遡及反映機能applyPreScreeningScoresを追加"
```

---

### Task 7: ドキュメント更新

**Files:**
- Modify: `glow-ma/README.md`
- Modify: `docs/glow-ma_本番投入手順書_統合版.md`

**Interfaces:**
- Consumes: なし
- Produces: なし(ドキュメントのみ)

- [ ] **Step 1: README.mdに事前選定スコア取り込みのセクションを追加する**

`glow-ma/README.md`の「次のフェーズ」セクションの直前に、新しいセクションを追加する:

```markdown
## 事前選定スコア・ランクの取り込み

外部で事前に選定作業(業種別の許認可情報・指定情報等をもとにしたTier/仮ランク判定)が完了している
リストを企業マスタに反映する機能です。

- 企業マスタに「事前選定ランク」「事前選定スコア」列があります。この2列は`applyPreScreeningScores`
  (`PreScreeningRunner.gs`)で反映するか、`importCompaniesFromStaging`の`IMPORT_COLUMN_MAP`に
  マッピングを追加すれば新規取り込み時にも反映されます
- 既存企業への遡及反映は以下の手順で行います:
  1. スプレッドシートに「事前選定リスト」タブを作り、元データを貼り付ける
  2. `PreScreeningRunner.gs`の`PRE_SCREENING_COLUMN_MAP`を実データの見出しに合わせて書き換える
  3. Apps Scriptエディタで`applyPreScreeningScores`を実行する
  4. 見出しが異なる複数のファイルを取り込む場合は、2〜3を繰り返す
- 一致しなかった企業は件数がログに出るとともに、会社名一覧が「事前選定_未一致」タブに自動で
  書き出されます(目視確認は必須ではありません)
- 事前選定スコアは、`recalculateAllScores`実行時の「初期スコア」計算に恒久的に加算されます
  (対応履歴が全く無い企業でも、外部評価をもとにした優先度が付く仕組みです)
```

- [ ] **Step 2: README.mdの「次のフェーズ」セクションに完了を反映する**

「次のフェーズ」セクション冒頭の一文に、この機能が完了したことを追記する形で更新する
(既存の文面の最後に一文追加する形):

```markdown
事前選定スコア・ランクの取り込み機能も完了しています(外部の事前選定リストを企業マスタに反映し、
初期スコア計算にも組み込み済み)。
```

- [ ] **Step 3: 本番投入前チェックリストに確認項目を追加する**

`docs/glow-ma_本番投入手順書_統合版.md`の「関係メモ編集(Phase 18b) セットアップ・動作確認チェックリスト」
セクションの直後に、以下のセクションを新設する:

```markdown
### 事前選定スコア・ランクの取り込み セットアップ・動作確認チェックリスト

**セットアップ:**
- [ ] `clasp push`で最新コードを反映する
- [ ] スプレッドシートに「事前選定リスト」タブを作り、取り込み元データを貼り付ける
- [ ] `PreScreeningRunner.gs`の`PRE_SCREENING_COLUMN_MAP`を実データの見出しに合わせて書き換える

**動作確認:**
- [ ] `applyPreScreeningScores`を実行し、実行ログに「一致 ○件 / 未一致 ○件」と表示されることを確認する
- [ ] 企業マスタの「事前選定ランク」「事前選定スコア」列に値が反映されていることを確認する
- [ ] 未一致が1件以上あった場合、「事前選定_未一致」タブに会社名一覧が自動で追記されていることを確認する
- [ ] `recalculateAllScores`を実行し、「初期スコア」に事前選定スコアが加算されていることを確認する
      (事前選定スコアが0の企業は、加算前と同じ初期スコアになっていることも確認する)
- [ ] 見出しが異なる2つ目以降のファイルを取り込む場合、`PRE_SCREENING_COLUMN_MAP`を書き換えてから
      再実行することを確認する
```

- [ ] **Step 4: コミット**

```bash
git add glow-ma/README.md docs/glow-ma_本番投入手順書_統合版.md
git commit -m "docs(glow-ma): 事前選定スコア取り込み機能のREADME・本番投入手順書を更新"
```

---

## 最終確認(全タスク完了後)

- [ ] `node --test tests/glow_ma_*.test.mjs` を実行し、既存分+今回追加分すべてPASSすることを確認する
- [ ] `PreScreeningRunner.gs`・`ScoringRunner.gs`の変更をひと通り読み返し、`applyPreScreeningScores`が
      `requireAdminAccess_`のような認証を必要としないApps Scriptエディタ手動実行専用の関数であることを
      再確認する(Web App経由で公開される関数ではないため、`AdminRunner.gs`系とは異なりアクセス制御は不要)
