# GLOW M&A台帳 Phase 1(基盤構築)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GLOW企業リレーション台帳(Googleスプレッドシート+GAS)の器を作る。企業マスタ・対応履歴ログ・紹介パートナーマスタ・設定の4タブを定義し、法人番号による名寄せロジックを実装し、7000件リストの一括インポート機能を用意する。

**Architecture:** ビジネスロジック(スキーマ定義・名寄せ・CSV行のパース)はGAS/Node両対応のUMD形式プレーンJSとして`glow-ma/src/`に実装し、`node --test`でユニットテストする(既存の`tests/shindan.test.mjs`と同じパターン)。SpreadsheetApp等のGAS専用APIに触れるコード(シート作成・インポート実行)は薄いラッパーとして分離し、ユニットテスト不可能な部分を最小化する。コードはclaspでApps Scriptプロジェクトに同期する。

**Tech Stack:** Google Apps Script(V8ランタイム)、clasp、Node.js組み込み`node:test`/`node:assert`(既存リポジトリ規約に準拠、追加npm依存なし)。

**このPlanの範囲について:** 設計書(`docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md`)の実装フェーズ1(11章)のみを対象とする。スコアリング(フェーズ2)、アラート・Slack通知(フェーズ3)、レター生成・ナーチャリング(フェーズ4)、ダッシュボード(フェーズ5)は本Planの完了後に別Planとして作成する。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データ(企業名・対応履歴等の非公開情報)を一切コミットしない(設計書4.2節)
- スプレッドシートIDを含む`.clasp.json`はコミットしない。`.clasp.json.example`のみコミットする(設計書4.2節)
- 追加のnpm依存を増やさない。テストは既存リポジトリと同じ`node --test` + `node:assert/strict`を使う(`tests/shindan.test.mjs`の前例に準拠)
- 企業マスタ・対応履歴ログ・紹介パートナーマスタ・設定の列名は設計書5章の定義に厳密に従う
- 法人番号(13桁)を名寄せの主キーとする(設計書9章)
- GASとNode両方で動くファイルは`site/fukugiiro/shindan/logic.js`と同じUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する

---

## File Structure

```
glow-ma/
  README.md                 — セットアップ手順・運用手順(Task 1で雛形作成、Task 7で完成)
  appsscript.json           — GASマニフェスト(Task 1)
  .clasp.json.example       — clasp設定テンプレート(Task 1。実ファイルの.clasp.jsonはgitignore)
  src/
    schema.js               — 4タブのシート名・ヘッダー定義(GlowSchema)(Task 2)
    dedupe.js                — 法人番号の正規化・重複検出・レコード統合(GlowDedupe)(Task 3)
    csvImport.js             — CSV行→企業マスタレコード変換(GlowCsvImport)(Task 4)
    SheetSetup.gs             — 4タブを作成する ensureLedgerTabs()(Task 5、GAS専用)
    ImportRunner.gs           — 7000件インポート実行 importCompaniesFromStaging()(Task 6、GAS専用)
tests/
  glow_ma_schema.test.mjs
  glow_ma_dedupe.test.mjs
  glow_ma_csv_import.test.mjs
.github/workflows/
  glow-ma-ci.yml             — glow-ma配下のユニットテストCI(Task 7)
.gitignore                  — glow-ma/.clasp.json を追記(Task 1)
```

---

### Task 1: `glow-ma/` ディレクトリの雛形作成

**Files:**
- Create: `glow-ma/appsscript.json`
- Create: `glow-ma/.clasp.json.example`
- Create: `glow-ma/README.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: なし(最初のタスク)
- Produces: `glow-ma/src/`ディレクトリの土台。以降のタスクはこの下にファイルを追加する

- [ ] **Step 1: `glow-ma/appsscript.json` を作成**

```json
{
  "timeZone": "Asia/Tokyo",
  "dependencies": {},
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8"
}
```

- [ ] **Step 2: `glow-ma/.clasp.json.example` を作成**

```json
{
  "scriptId": "YOUR_APPS_SCRIPT_ID_HERE",
  "rootDir": "./src"
}
```

- [ ] **Step 3: `.gitignore` に以下を追記**

```
# GLOW M&A台帳(非公開スプレッドシートIDを含むため)
glow-ma/.clasp.json
```

- [ ] **Step 4: `glow-ma/README.md` の雛形を作成**

```markdown
# GLOW M&A・不動産 企業リレーション台帳

設計書: `docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md`

## これは何か

GLOWのM&A・不動産事業向けの非公開営業支援基盤。実データ(企業名・対応履歴等)は
Googleスプレッドシートに保持し、このディレクトリにはGAS(Google Apps Script)の
ロジックのみを置く。**実データは一切このリポジトリにコミットしない。**

## セットアップ

(Task 7で追記)

## テスト

```bash
node --test tests/glow_ma_schema.test.mjs tests/glow_ma_dedupe.test.mjs tests/glow_ma_csv_import.test.mjs
```
```

- [ ] **Step 5: Commit**

```bash
git add glow-ma/appsscript.json glow-ma/.clasp.json.example glow-ma/README.md .gitignore
git commit -m "chore(glow-ma): ディレクトリ雛形とclasp設定テンプレートを追加"
```

---

### Task 2: `schema.js` — シート構成の定義

**Files:**
- Create: `glow-ma/src/schema.js`
- Test: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema`オブジェクト(Node側は`require("../glow-ma/src/schema.js")`、GAS側はグローバル変数`GlowSchema`)。プロパティ: `COMPANY_MASTER_SHEET_NAME`(string)、`COMPANY_MASTER_HEADERS`(string[])、`INTERACTION_LOG_SHEET_NAME`(string)、`INTERACTION_LOG_HEADERS`(string[])、`PARTNER_MASTER_SHEET_NAME`(string)、`PARTNER_MASTER_HEADERS`(string[])、`SETTINGS_SHEET_NAME`(string)、`SETTINGS_HEADERS`(string[])。これらは以降の全タスクが参照する契約であり、名称・順序を変更しない

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const schema = require("../glow-ma/src/schema.js");

test("4つのシート全てのヘッダー定義が配列で存在する", () => {
  assert.ok(Array.isArray(schema.COMPANY_MASTER_HEADERS));
  assert.ok(Array.isArray(schema.INTERACTION_LOG_HEADERS));
  assert.ok(Array.isArray(schema.PARTNER_MASTER_HEADERS));
  assert.ok(Array.isArray(schema.SETTINGS_HEADERS));
});

test("企業マスタのヘッダーに重複がない", () => {
  const unique = new Set(schema.COMPANY_MASTER_HEADERS);
  assert.equal(unique.size, schema.COMPANY_MASTER_HEADERS.length);
});

test("企業マスタに設計書5.1節の必須列が含まれる", () => {
  const required = [
    "企業ID", "法人番号", "会社名", "流入ルート", "起点担当者_紹介元",
    "現在ステージ", "提案商品", "総合スコア", "ランク", "次回アクション予定日"
  ];
  required.forEach((col) => {
    assert.ok(schema.COMPANY_MASTER_HEADERS.includes(col), `${col} が企業マスタに必要`);
  });
});

test("対応履歴ログに対応相手の列が含まれる(設計書5.2節)", () => {
  assert.ok(schema.INTERACTION_LOG_HEADERS.includes("対応相手"));
});

test("紹介パートナーマスタに紹介料率と逆紹介履歴の列が含まれる(設計書5.3節)", () => {
  assert.ok(schema.PARTNER_MASTER_HEADERS.includes("紹介料率"));
  assert.ok(schema.PARTNER_MASTER_HEADERS.includes("逆紹介履歴"));
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`glow-ma/src/schema.js`が存在しないため`require`がエラーになる)

- [ ] **Step 3: `glow-ma/src/schema.js` を実装**

```js
/* GLOW企業リレーション台帳 シート構成の定義(スキーマ)
 * ブラウザ相当のGAS(global.GlowSchema)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_schema.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  var COMPANY_MASTER_SHEET_NAME = "企業マスタ";
  var COMPANY_MASTER_HEADERS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地",
    "流入ルート", "起点担当者_紹介元", "現在ステージ", "提案商品",
    "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容",
    "担当者", "登録日", "備考"
  ];

  var INTERACTION_LOG_SHEET_NAME = "対応履歴ログ";
  var INTERACTION_LOG_HEADERS = [
    "履歴ID", "企業ID", "日付", "担当者", "種別", "対応相手", "内容メモ", "次回アクション"
  ];

  var PARTNER_MASTER_SHEET_NAME = "紹介パートナーマスタ";
  var PARTNER_MASTER_HEADERS = [
    "パートナーID", "名称", "種別", "担当者名", "関係性ランク", "累計紹介数", "成約数",
    "提供済み情報ログ", "紹介料率", "逆紹介履歴", "最終接触日", "次回アクション予定日"
  ];

  var SETTINGS_SHEET_NAME = "設定";
  var SETTINGS_HEADERS = ["キー", "値", "説明"];

  var api = {
    COMPANY_MASTER_SHEET_NAME: COMPANY_MASTER_SHEET_NAME,
    COMPANY_MASTER_HEADERS: COMPANY_MASTER_HEADERS,
    INTERACTION_LOG_SHEET_NAME: INTERACTION_LOG_SHEET_NAME,
    INTERACTION_LOG_HEADERS: INTERACTION_LOG_HEADERS,
    PARTNER_MASTER_SHEET_NAME: PARTNER_MASTER_SHEET_NAME,
    PARTNER_MASTER_HEADERS: PARTNER_MASTER_HEADERS,
    SETTINGS_SHEET_NAME: SETTINGS_SHEET_NAME,
    SETTINGS_HEADERS: SETTINGS_HEADERS
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowSchema = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(5 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 企業マスタ等4タブのスキーマ定義を追加"
```

---

### Task 3: `dedupe.js` — 法人番号による名寄せロジック

**Files:**
- Create: `glow-ma/src/dedupe.js`
- Test: `tests/glow_ma_dedupe.test.mjs`

**Interfaces:**
- Consumes: なし(企業レコードはプレーンオブジェクト。`法人番号`はstring、`流入ルート`/`提案商品`はstring[]、`企業ID`はstring)
- Produces: `GlowDedupe`オブジェクト。`normalizeCorporateNumber(raw: string|null|undefined): string|null`、`findDuplicateGroups(companies: object[]): object[][]`(法人番号が一致するレコードの配列の配列。単独レコードは含まない)、`mergeCompanyRecords(records: object[]): {merged: object, absorbedIds: string[]}`。Task 6の`ImportRunner.gs`がこれらをそのまま呼び出す

#### 3-1. `normalizeCorporateNumber`

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_dedupe.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dedupe = require("../glow-ma/src/dedupe.js");

test("normalizeCorporateNumber: 13桁の数字はそのまま正規化される", () => {
  assert.equal(dedupe.normalizeCorporateNumber("1234567890123"), "1234567890123");
});

test("normalizeCorporateNumber: ハイフンや空白が入っていても13桁なら正規化される", () => {
  assert.equal(dedupe.normalizeCorporateNumber(" 1234-5678-90123 "), "1234567890123");
});

test("normalizeCorporateNumber: 13桁でない場合はnull", () => {
  assert.equal(dedupe.normalizeCorporateNumber("123456789012"), null);
});

test("normalizeCorporateNumber: null/undefined/空文字はnull", () => {
  assert.equal(dedupe.normalizeCorporateNumber(null), null);
  assert.equal(dedupe.normalizeCorporateNumber(undefined), null);
  assert.equal(dedupe.normalizeCorporateNumber(""), null);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: FAIL(`glow-ma/src/dedupe.js`が存在しない)

- [ ] **Step 3: `glow-ma/src/dedupe.js` を作成し `normalizeCorporateNumber` を実装**

```js
/* GLOW企業リレーション台帳 法人番号による名寄せロジック
 * ブラウザ相当のGAS(global.GlowDedupe)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_dedupe.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function normalizeCorporateNumber(raw) {
    if (raw === null || raw === undefined) return null;
    var digits = String(raw).replace(/[^0-9]/g, "");
    if (digits.length !== 13) return null;
    return digits;
  }

  var api = {
    normalizeCorporateNumber: normalizeCorporateNumber
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowDedupe = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: PASS(4 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dedupe.js tests/glow_ma_dedupe.test.mjs
git commit -m "feat(glow-ma): 法人番号の正規化ロジックを追加"
```

#### 3-2. `findDuplicateGroups`

- [ ] **Step 6: 失敗するテストを追記**

`tests/glow_ma_dedupe.test.mjs` に追記:

```js
test("findDuplicateGroups: 同じ法人番号のレコードが1グループにまとまる", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "1234567890123" },
    { 企業ID: "C000002", 法人番号: "1234567890123" },
    { 企業ID: "C000003", 法人番号: "9999999999999" }
  ];
  const groups = dedupe.findDuplicateGroups(companies);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].length, 2);
  assert.deepEqual(groups[0].map((c) => c.企業ID), ["C000001", "C000002"]);
});

test("findDuplicateGroups: 重複がなければ空配列", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "1234567890123" },
    { 企業ID: "C000002", 法人番号: "9999999999999" }
  ];
  assert.deepEqual(dedupe.findDuplicateGroups(companies), []);
});

test("findDuplicateGroups: 法人番号が空のレコードはグループ化対象外", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "" },
    { 企業ID: "C000002", 法人番号: "" }
  ];
  assert.deepEqual(dedupe.findDuplicateGroups(companies), []);
});
```

- [ ] **Step 7: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: FAIL(`dedupe.findDuplicateGroups is not a function`)

- [ ] **Step 8: `findDuplicateGroups` を実装**

`glow-ma/src/dedupe.js` の `normalizeCorporateNumber` 関数の直後に追加し、`api`オブジェクトにも追加する:

```js
  function findDuplicateGroups(companies) {
    var byNumber = {};
    var order = [];
    companies.forEach(function (company) {
      var num = normalizeCorporateNumber(company["法人番号"]);
      if (!num) return;
      if (!byNumber[num]) {
        byNumber[num] = [];
        order.push(num);
      }
      byNumber[num].push(company);
    });
    var groups = [];
    order.forEach(function (num) {
      if (byNumber[num].length > 1) groups.push(byNumber[num]);
    });
    return groups;
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    normalizeCorporateNumber: normalizeCorporateNumber,
    findDuplicateGroups: findDuplicateGroups
  };
```

- [ ] **Step 9: テストが通ることを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: PASS(7 tests)

- [ ] **Step 10: Commit**

```bash
git add glow-ma/src/dedupe.js tests/glow_ma_dedupe.test.mjs
git commit -m "feat(glow-ma): 法人番号による重複グループ検出を追加"
```

#### 3-3. `mergeCompanyRecords`

- [ ] **Step 11: 失敗するテストを追記**

`tests/glow_ma_dedupe.test.mjs` に追記:

```js
test("mergeCompanyRecords: 流入ルートと提案商品は重複なく統合される", () => {
  const records = [
    { 企業ID: "C000001", 会社名: "沖縄物産株式会社", 流入ルート: ["①紹介"], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 会社名: "", 流入ルート: ["②手紙DM"], 提案商品: ["法人保険"], 備考: "" }
  ];
  const { merged, absorbedIds } = dedupe.mergeCompanyRecords(records);
  assert.deepEqual(merged.流入ルート, ["①紹介", "②手紙DM"]);
  assert.deepEqual(merged.提案商品, ["法人保険"]);
  assert.deepEqual(absorbedIds, ["C000002"]);
});

test("mergeCompanyRecords: スカラー項目は先頭レコードの値を優先し、空なら後続を採用する", () => {
  const records = [
    { 企業ID: "C000001", 会社名: "", 業種: "小売業", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 会社名: "沖縄物産株式会社", 業種: "卸売業", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { merged } = dedupe.mergeCompanyRecords(records);
  assert.equal(merged.会社名, "沖縄物産株式会社");
  assert.equal(merged.業種, "小売業");
});

test("mergeCompanyRecords: 統合した企業IDを備考に記録する", () => {
  const records = [
    { 企業ID: "C000001", 流入ルート: [], 提案商品: [], 備考: "既存メモ" },
    { 企業ID: "C000002", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { merged } = dedupe.mergeCompanyRecords(records);
  assert.match(merged.備考, /既存メモ/);
  assert.match(merged.備考, /名寄せ統合: C000002 を統合/);
});

test("mergeCompanyRecords: レコードが空配列なら例外を投げる", () => {
  assert.throws(() => dedupe.mergeCompanyRecords([]));
});
```

- [ ] **Step 12: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: FAIL(`dedupe.mergeCompanyRecords is not a function`)

- [ ] **Step 13: `mergeCompanyRecords` を実装**

`glow-ma/src/dedupe.js` の `findDuplicateGroups` 関数の直後に追加する:

```js
  var SCALAR_FIELDS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地",
    "起点担当者_紹介元", "現在ステージ", "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容", "担当者", "登録日"
  ];

  function unionArrayField(records, field) {
    var seen = {};
    var result = [];
    records.forEach(function (record) {
      (record[field] || []).forEach(function (value) {
        if (!seen[value]) {
          seen[value] = true;
          result.push(value);
        }
      });
    });
    return result;
  }

  function mergeCompanyRecords(records) {
    if (!records || records.length === 0) {
      throw new Error("mergeCompanyRecords requires at least one record");
    }
    var merged = {};
    SCALAR_FIELDS.forEach(function (field) {
      merged[field] = "";
      for (var i = 0; i < records.length; i++) {
        var value = records[i][field];
        if (value !== undefined && value !== null && value !== "") {
          merged[field] = value;
          break;
        }
      }
    });

    merged["流入ルート"] = unionArrayField(records, "流入ルート");
    merged["提案商品"] = unionArrayField(records, "提案商品");

    var absorbedIds = records.slice(1).map(function (r) { return r["企業ID"]; }).filter(Boolean);
    var noteParts = [];
    if (records[0]["備考"]) noteParts.push(records[0]["備考"]);
    if (absorbedIds.length > 0) {
      noteParts.push("名寄せ統合: " + absorbedIds.join("、") + " を統合");
    }
    merged["備考"] = noteParts.join(" / ");

    return { merged: merged, absorbedIds: absorbedIds };
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    normalizeCorporateNumber: normalizeCorporateNumber,
    findDuplicateGroups: findDuplicateGroups,
    mergeCompanyRecords: mergeCompanyRecords
  };
```

- [ ] **Step 14: テストが通ることを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: PASS(11 tests)

- [ ] **Step 15: Commit**

```bash
git add glow-ma/src/dedupe.js tests/glow_ma_dedupe.test.mjs
git commit -m "feat(glow-ma): 重複企業レコードの統合ロジックを追加"
```

---

### Task 4: `csvImport.js` — CSV行から企業マスタレコードへの変換

**Files:**
- Create: `glow-ma/src/csvImport.js`
- Test: `tests/glow_ma_csv_import.test.mjs`

**Interfaces:**
- Consumes: `GlowSchema.COMPANY_MASTER_HEADERS`は参照しない(このモジュールは呼び出し側が渡す`columnMap`のみに依存し、疎結合を保つ)
- Produces: `GlowCsvImport`オブジェクト。`buildCompanyId(sequenceNumber: number): string`(例: `1` → `"C000001"`)、`parseCompanyCsvRow(headerRow: string[], dataRow: string[], columnMap: object, sequenceNumber: number, todayString: string): object`(企業マスタの1レコード相当のプレーンオブジェクトを返す。`流入ルート`は`["②手紙DM"]`固定、`現在ステージ`は`"未接触"`固定、`登録日`は引数の`todayString`をそのまま使う)。Task 6の`ImportRunner.gs`がこの2関数を呼び出す

#### 4-1. `buildCompanyId`

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_csv_import.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const csvImport = require("../glow-ma/src/csvImport.js");

test("buildCompanyId: 連番を6桁ゼロ埋めのIDに変換する", () => {
  assert.equal(csvImport.buildCompanyId(1), "C000001");
  assert.equal(csvImport.buildCompanyId(42), "C000042");
  assert.equal(csvImport.buildCompanyId(7000), "C007000");
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_csv_import.test.mjs`
Expected: FAIL(`glow-ma/src/csvImport.js`が存在しない)

- [ ] **Step 3: `glow-ma/src/csvImport.js` を作成し `buildCompanyId` を実装**

```js
/* GLOW企業リレーション台帳 CSV行→企業マスタレコード変換
 * ブラウザ相当のGAS(global.GlowCsvImport)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_csv_import.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function buildCompanyId(sequenceNumber) {
    return "C" + String(sequenceNumber).padStart(6, "0");
  }

  var api = {
    buildCompanyId: buildCompanyId
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCsvImport = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_csv_import.test.mjs`
Expected: PASS(1 test)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/csvImport.js tests/glow_ma_csv_import.test.mjs
git commit -m "feat(glow-ma): 企業IDの連番生成ロジックを追加"
```

#### 4-2. `parseCompanyCsvRow`

- [ ] **Step 6: 失敗するテストを追記**

`tests/glow_ma_csv_import.test.mjs` に追記:

```js
test("parseCompanyCsvRow: 見出しマッピングに従って値を取り出す", () => {
  const headerRow = ["法人名", "業種区分", "所在地欄"];
  const dataRow = ["沖縄物産株式会社", "小売業", "那覇市"];
  const columnMap = { 会社名: "法人名", 業種: "業種区分", 所在地: "所在地欄" };

  const record = csvImport.parseCompanyCsvRow(headerRow, dataRow, columnMap, 1, "2026-07-26");

  assert.equal(record.企業ID, "C000001");
  assert.equal(record.会社名, "沖縄物産株式会社");
  assert.equal(record.業種, "小売業");
  assert.equal(record.所在地, "那覇市");
  assert.deepEqual(record.流入ルート, ["②手紙DM"]);
  assert.equal(record.現在ステージ, "未接触");
  assert.equal(record.登録日, "2026-07-26");
});

test("parseCompanyCsvRow: columnMapに存在しない列は空文字になる", () => {
  const headerRow = ["法人名"];
  const dataRow = ["沖縄物産株式会社"];
  const columnMap = { 会社名: "法人名", 代表者名: "存在しない見出し" };

  const record = csvImport.parseCompanyCsvRow(headerRow, dataRow, columnMap, 1, "2026-07-26");

  assert.equal(record.会社名, "沖縄物産株式会社");
  assert.equal(record.代表者名, "");
});
```

- [ ] **Step 7: テストが失敗することを確認**

Run: `node --test tests/glow_ma_csv_import.test.mjs`
Expected: FAIL(`csvImport.parseCompanyCsvRow is not a function`)

- [ ] **Step 8: `parseCompanyCsvRow` を実装**

`glow-ma/src/csvImport.js` の `buildCompanyId` 関数の直後に追加する:

```js
  function parseCompanyCsvRow(headerRow, dataRow, columnMap, sequenceNumber, todayString) {
    var record = {
      企業ID: buildCompanyId(sequenceNumber),
      法人番号: "", 会社名: "", 業種: "", 規模: "", 代表者名: "", 代表者年齢: "", 所在地: "",
      流入ルート: ["②手紙DM"],
      起点担当者_紹介元: "", 現在ステージ: "未接触", 提案商品: [],
      初期スコア: "", 反応スコア: "", 総合スコア: "", ランク: "",
      最終接触日: "", 次回アクション予定日: "", 次回アクション内容: "",
      担当者: "", 登録日: todayString, 備考: ""
    };

    Object.keys(columnMap).forEach(function (targetField) {
      var sourceHeader = columnMap[targetField];
      var columnIndex = headerRow.indexOf(sourceHeader);
      if (columnIndex === -1) return;
      var value = dataRow[columnIndex];
      record[targetField] = value === undefined || value === null ? "" : String(value);
    });

    return record;
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    buildCompanyId: buildCompanyId,
    parseCompanyCsvRow: parseCompanyCsvRow
  };
```

- [ ] **Step 9: テストが通ることを確認**

Run: `node --test tests/glow_ma_csv_import.test.mjs`
Expected: PASS(3 tests)

- [ ] **Step 10: Commit**

```bash
git add glow-ma/src/csvImport.js tests/glow_ma_csv_import.test.mjs
git commit -m "feat(glow-ma): CSV行から企業マスタレコードへの変換ロジックを追加"
```

---

### Task 5: `SheetSetup.gs` — 4タブの作成(GAS専用・手動検証)

このタスクのコードは`SpreadsheetApp`(GAS専用API)を使うため`node --test`では検証できない。Apps Scriptエディタ上での手動実行で検証する。

**Files:**
- Create: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema`(Task 2、GAS上ではグローバル変数として利用可能)
- Produces: `ensureLedgerTabs()`関数(引数なし、戻り値なし)。Task 6より前に一度だけ手動実行する運用

- [ ] **Step 1: `glow-ma/src/SheetSetup.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: シート初期化
 * Apps Scriptエディタの関数選択で ensureLedgerTabs を選び、実行ボタンで手動実行する。
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」の
 * 4タブが(存在しなければ)作成され、1行目に見出しが設定される。
 */
function ensureLedgerTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureTab_(ss, GlowSchema.COMPANY_MASTER_SHEET_NAME, GlowSchema.COMPANY_MASTER_HEADERS);
  ensureTab_(ss, GlowSchema.INTERACTION_LOG_SHEET_NAME, GlowSchema.INTERACTION_LOG_HEADERS);
  ensureTab_(ss, GlowSchema.PARTNER_MASTER_SHEET_NAME, GlowSchema.PARTNER_MASTER_HEADERS);
  ensureTab_(ss, GlowSchema.SETTINGS_SHEET_NAME, GlowSchema.SETTINGS_HEADERS);
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
```

- [ ] **Step 2: 手動検証**

1. `clasp push`(Task 7のセットアップ手順に従って認証・スクリプトID設定を済ませておく)
2. Apps Scriptエディタで対象プロジェクトを開く
3. 関数選択ドロップダウンで `ensureLedgerTabs` を選び「実行」を押す
4. 初回はGoogleの権限承認ダイアログが出るので許可する
5. 紐付けたスプレッドシートを開き、「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」の4タブが作成され、1行目に見出しが入り、1行目が固定表示になっていることを確認する

Expected: 4タブが作成され、各タブの見出しが`glow-ma/src/schema.js`の定義と一致する

- [ ] **Step 3: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): 台帳4タブを初期化するensureLedgerTabsを追加"
```

---

### Task 6: `ImportRunner.gs` — 7000件リストの一括インポート(GAS専用・手動検証)

このタスクのコードも`SpreadsheetApp`/`Utilities`/`Logger`(GAS専用API)に依存するため`node --test`では検証できない。サンプルデータでの手動実行で検証する。

**Files:**
- Create: `glow-ma/src/ImportRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema`(Task 2)、`GlowDedupe.findDuplicateGroups`/`GlowDedupe.mergeCompanyRecords`(Task 3)、`GlowCsvImport.parseCompanyCsvRow`(Task 4)
- Produces: `importCompaniesFromStaging()`関数(引数なし)。「インポート待ち」タブのデータを読み、企業マスタへ書き込む

- [ ] **Step 1: `glow-ma/src/ImportRunner.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: 7000件リストの一括インポート
 *
 * 使い方:
 * 1. スプレッドシートに「インポート待ち」という名前のタブを作る
 * 2. 1行目に元データの見出し、2行目以降にデータを貼り付ける
 * 3. 下の IMPORT_COLUMN_MAP の右辺を、実際の見出し文字列に合わせて書き換える
 * 4. Apps Scriptエディタで importCompaniesFromStaging を実行する
 *
 * 実行すると、企業マスタの既存データと突き合わせて法人番号が一致するものは
 * GlowDedupe.mergeCompanyRecords で統合し、企業マスタを丸ごと書き直す。
 */
var IMPORT_COLUMN_MAP = {
  // 左が企業マスタの列名、右が「インポート待ち」タブの見出し文字列。
  // 実データの見出しに合わせてここを書き換えてから実行する(設計書15章オープンクエスチョン)。
  "会社名": "会社名",
  "法人番号": "法人番号",
  "業種": "業種",
  "規模": "規模",
  "代表者名": "代表者名",
  "代表者年齢": "代表者年齢",
  "所在地": "所在地"
};
var STAGING_SHEET_NAME = "インポート待ち";

function importCompaniesFromStaging() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var staging = ss.getSheetByName(STAGING_SHEET_NAME);
  if (!staging) {
    throw new Error("「" + STAGING_SHEET_NAME + "」タブが見つかりません。元データを貼り付けてから実行してください。");
  }
  var values = staging.getDataRange().getValues();
  if (values.length < 2) {
    Logger.log("インポート対象のデータ行がありません。");
    return;
  }
  var headerRow = values[0].map(String);
  var dataRows = values.slice(1).filter(function (row) {
    return !row.every(function (cell) { return cell === "" || cell === null; });
  });

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }

  var existingRecords = readCompanyRecords_(companySheet);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");

  var newRecords = dataRows.map(function (row, index) {
    var sequenceNumber = existingRecords.length + index + 1;
    return GlowCsvImport.parseCompanyCsvRow(headerRow, row, IMPORT_COLUMN_MAP, sequenceNumber, todayString);
  });

  var combined = existingRecords.concat(newRecords);
  var duplicateGroups = GlowDedupe.findDuplicateGroups(combined);

  var absorbedIdSet = {};
  var mergedByFirstId = {};
  duplicateGroups.forEach(function (group) {
    var result = GlowDedupe.mergeCompanyRecords(group);
    mergedByFirstId[group[0]["企業ID"]] = result.merged;
    result.absorbedIds.forEach(function (id) { absorbedIdSet[id] = true; });
  });

  var finalRecords = combined
    .filter(function (record) { return !absorbedIdSet[record["企業ID"]]; })
    .map(function (record) { return mergedByFirstId[record["企業ID"]] || record; });

  writeCompanyRecords_(companySheet, finalRecords);
  Logger.log(
    "インポート完了: 新規読込 " + newRecords.length + "件 / 名寄せ統合 " +
    Object.keys(absorbedIdSet).length + "件 / 最終件数 " + finalRecords.length + "件"
  );
}

function readCompanyRecords_(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.COMPANY_MASTER_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    record["流入ルート"] = record["流入ルート"] ? String(record["流入ルート"]).split("、") : [];
    record["提案商品"] = record["提案商品"] ? String(record["提案商品"]).split("、") : [];
    return record;
  });
}

function writeCompanyRecords_(sheet, records) {
  var headers = GlowSchema.COMPANY_MASTER_HEADERS;
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, headers.length).clearContent();
  }
  if (records.length === 0) return;
  var rows = records.map(function (record) {
    return headers.map(function (header) {
      var value = record[header];
      if (Array.isArray(value)) return value.join("、");
      return value === undefined || value === null ? "" : value;
    });
  });
  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
}
```

- [ ] **Step 2: 手動検証(サンプルデータで名寄せを含めて確認)**

1. `clasp push` で最新コードを反映する
2. スプレッドシートに「インポート待ち」タブを作り、1行目に `会社名, 法人番号, 業種, 規模, 代表者名, 代表者年齢, 所在地` を入力する
3. 2行目以降にサンプル行を3行入力する。うち2行は同じ法人番号にして名寄せを検証する:
   - `沖縄物産株式会社, 1234567890123, 小売業, 50名, 山田太郎, 65, 那覇市`
   - `沖縄物産(株), 1234567890123, 小売業, 50名, , , ` (同じ法人番号・一部項目が空)
   - `やんばる建設株式会社, 9999999999999, 建設業, 20名, 佐藤次郎, 58, 名護市`
4. Apps Scriptエディタで `ensureLedgerTabs` を先に実行済みであることを確認する(Task 5)
5. `importCompaniesFromStaging` を実行する
6. 実行ログ(表示 > ログ)に「新規読込 3件 / 名寄せ統合 1件 / 最終件数 2件」と出ることを確認する
7. 「企業マスタ」タブを開き、法人番号`1234567890123`の行が1行に統合され、会社名が「沖縄物産株式会社」(先頭行の値が優先される)になっていること、備考欄に「名寄せ統合」の記録があることを確認する

Expected: 3行入力→2行に統合され、企業マスタに正しく書き込まれる

- [ ] **Step 3: Commit**

```bash
git add glow-ma/src/ImportRunner.gs
git commit -m "feat(glow-ma): 7000件リストの一括インポート機能を追加"
```

---

### Task 7: CI設定とREADME完成

**Files:**
- Create: `.github/workflows/glow-ma-ci.yml`
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜6で作成した全ファイル
- Produces: PR時に自動でユニットテストが走るCIゲート。GLOWチームがセットアップ〜運用できる完成したREADME

- [ ] **Step 1: `.github/workflows/glow-ma-ci.yml` を作成**

```yaml
name: glow-ma-ci

on:
  push:
    paths:
      - "glow-ma/**"
      - "tests/glow_ma_*.test.mjs"
  pull_request:
    paths:
      - "glow-ma/**"
      - "tests/glow_ma_*.test.mjs"
  workflow_dispatch: {}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-node@v6
        with:
          node-version: "22"

      - name: GLOW M&A台帳 ロジック単体テスト
        run: node --test tests/glow_ma_schema.test.mjs tests/glow_ma_dedupe.test.mjs tests/glow_ma_csv_import.test.mjs
```

- [ ] **Step 2: ローカルでも同じコマンドが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs tests/glow_ma_dedupe.test.mjs tests/glow_ma_csv_import.test.mjs`
Expected: PASS(全19テスト: schema 5件 + dedupe 11件 + csvImport 3件)

- [ ] **Step 3: `glow-ma/README.md` を完成させる**

`glow-ma/README.md` の `## セットアップ` セクションを次の内容に置き換える:

```markdown
## セットアップ(初回のみ)

1. `npm install -g @google/clasp` (未導入の場合)
2. `clasp login` でGoogleアカウント認証
3. Apps Scriptプロジェクトを新規作成し、スタンドアロンスクリプトとして
   GLOW企業リレーション台帳のスプレッドシートに紐付ける(スプレッドシートの
   拡張機能 > Apps Script から作成すると自動的に紐付く)
4. `glow-ma/.clasp.json.example` を `glow-ma/.clasp.json` としてコピーし、
   `scriptId` を実際のスクリプトIDに書き換える(このファイルはコミットしない)
5. `cd glow-ma && clasp push` でコードをApps Scriptに反映する
6. Apps Scriptエディタで `ensureLedgerTabs` を一度だけ手動実行し、4タブを作成する

## 7000件リストのインポート

1. スプレッドシートに「インポート待ち」タブを作り、元データを貼り付ける
2. `glow-ma/src/ImportRunner.gs` の `IMPORT_COLUMN_MAP` を実際の見出しに合わせて書き換える
3. `clasp push` して `importCompaniesFromStaging` を実行する
4. 実行ログで新規読込・名寄せ統合・最終件数を確認する

## 次のフェーズ

スコアリング・掘り起こしアラート・レター生成・ダッシュボードは、
`docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md` の
フェーズ2以降として別Planで実装する。
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/glow-ma-ci.yml glow-ma/README.md
git commit -m "docs(glow-ma): セットアップ手順を完成させCIを追加"
```

---

## Self-Review

**Spec coverage(設計書との対応)**

- 5.1〜5.4節(企業マスタ・対応履歴ログ・紹介パートナーマスタ・設定のスキーマ)→ Task 2
- 9章(法人番号による名寄せ)→ Task 3
- 11章フェーズ1(器作成+7000件インポート)→ Task 4, 5, 6
- 4.2節(公開リポジトリに実データ・認証情報を置かない)→ Task 1(`.clasp.json`のgitignore)、全タスクでサンプル以外の実データを使わない
- スコアリング(6章)・提案順序方針(7章)・アラート(8章)・レター生成(10章)・ナーチャリング(11章)・ダッシュボード(12章)は次フェーズのPlanで対応(本Planの範囲外であることを冒頭に明記済み)

**Placeholder scan:** TBD/TODO等の記述なし。`IMPORT_COLUMN_MAP`は実データの見出しが未確定なため書き換え前提のコードだが、動作するデフォルト値と手順(Task 6 Step 2, Task 7 README)を明記しており、プレースホルダーではなく運用可能な実装。

**Type consistency:** `GlowSchema`/`GlowDedupe`/`GlowCsvImport`の関数名・戻り値の形は各タスクのInterfacesと実装コードで一致させた(`findDuplicateGroups`が返す配列の各要素は元の企業レコードそのもの、`mergeCompanyRecords`は`{merged, absorbedIds}`で統一)。`ImportRunner.gs`(Task 6)はTask 3・4で定義した関数シグネチャをそのまま呼び出しており、名前・引数の食い違いはない。
