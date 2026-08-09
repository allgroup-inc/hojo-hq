# GLOW M&A台帳 Phase 16(レター発送日の記録・発送業者連携用CSV出力)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「レター下書き」タブに「発送日」列を追加し、(1)発送日ごとに宛先一覧(企業ID・会社名・所在地・窓口担当者名)をCSV出力して発送業者にそのまま連携できるようにし、(2)発送日が入力されたら対応履歴ログに「手紙送付」を自動記録し、企業マスタの「次回アクション予定日」が未設定の場合のみ発送日+10日を自動セットしてフォロー架電の見落としを防ぐ。

**Architecture:** 日付計算・CSV組み立てロジック(発送日での絞り込み・企業マスタとの突合・CSV文字列化)はGAS/Node両対応のUMD形式プレーンJSとして`glow-ma/src/shippingContent.js`に実装し、`node --test`でユニットテストする。この中で`glow-ma/src/alerting.js`の`GlowAlerting.toDate`をそのまま再利用し、日付パースロジックをこのファイルで重複させない。GAS専用の`ShippingRunner.gs`(onEditトリガーによる自動記録・CSV出力ダイアログ)は、ロジックを`shippingContent.js`に委譲する薄いグルーコードとする。

**Tech Stack:** Google Apps Script(V8ランタイム、`HtmlService`、インストール型`onEdit`トリガー)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの背景:** 三名体制レビュー(`docs/superpowers/specs/2026-08-07-glow-ma-letter-shipping-triangle-review.md`)で「採用(条件付き)」の裁定を得た設計(`docs/superpowers/specs/2026-08-07-glow-ma-letter-shipping-design.md`)を実装する。README記載の完了フェーズはPhase 1〜15のため、本機能はPhase 16とする。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データ(企業名・住所等)を一切コミットしない
- 「発送日」は「投函完了日(実際に送った日、または発送業者への依頼が完了し発送が確定した日)」を意味する、単一の意味で統一する(これから依頼する予定日ではない)
- 企業マスタの「次回アクション予定日」の自動セットは、**既存の値が空の場合のみ**行う(担当者が既に個別設定した予定日を上書きしない)
- 対応履歴ログへの自動記録は、同じ下書きID由来の重複記録を防ぐ(発送日セルの訂正で複数回onEditが発火しても、同じ企業への「手紙送付」記録が増殖しないようにする)
- CSVの発送業者への送信は自動化しない。人がダウンロードしたファイルを自分の判断で業者に渡す運用に留める
- CSV列は「発送日・企業ID・会社名・所在地・窓口担当者名」の5列のみとする(手紙本文は含めない)
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する
- 企業マスタ・対応履歴ログへの書き込みは`LockService`で保護する。対応履歴ログへの書き込みは追記(1行分の`setValues`)のみで、シート全体を書き直さない
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する(Phase 1〜15と同じ扱い)

---

## File Structure

```
glow-ma/src/
  schema.js          — 既存ファイルを修正: LETTER_DRAFT_HEADERSの末尾に「発送日」を追加(Task 1)
  shippingContent.js  — 新規: 日付計算・CSV組み立て・CSV文字列化(GlowShippingContent)(Task 2, 3)
  ShippingRunner.gs    — 新規: onEditトリガーによる自動記録・CSV出力メニュー(Task 4, 5、GAS専用)
  ShareRunner.gs       — 既存ファイルを修正: onOpen()にメニュー項目を追加(Task 5)
tests/
  glow_ma_schema.test.mjs           — 既存ファイルを修正(Task 1)
  glow_ma_shippingContent.test.mjs  — 新規(Task 2, 3)
glow-ma/README.md      — Phase 16のセットアップ・使い方を追記(Task 6)
```

---

### Task 1: `schema.js` — レター下書きタブに「発送日」列を追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.LETTER_DRAFT_HEADERS`が`["下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス", "発送日"]`になる(末尾に「発送日」を追加)。Task 3(CSV組み立て)とTask 4(onEditトリガー)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs`の68〜75行目の既存テストを以下に置き換える(既存の`LETTER_DRAFT_HEADERS`の期待値配列に`"発送日"`を追加する):

```js
test("レター下書きタブの名称・見出し・種別・ステータスが定義されている", () => {
  assert.equal(schema.LETTER_DRAFT_SHEET_NAME, "レター下書き");
  assert.deepEqual(schema.LETTER_DRAFT_HEADERS, [
    "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス", "発送日"
  ]);
  assert.deepEqual(schema.LETTER_DRAFT_TYPES, ["初回DM", "ナーチャリング配信"]);
  assert.deepEqual(schema.LETTER_DRAFT_STATUSES, ["下書き", "送付済み", "見送り"]);
});

test("レター下書きタブの「発送日」列が末尾に追加されている", () => {
  assert.equal(
    schema.LETTER_DRAFT_HEADERS[schema.LETTER_DRAFT_HEADERS.length - 1],
    "発送日"
  );
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(1つ目のテストが、実際の`LETTER_DRAFT_HEADERS`に`"発送日"`がまだ無いためdeepEqualで失敗する)

- [ ] **Step 3: `glow-ma/src/schema.js`の`LETTER_DRAFT_HEADERS`を修正**

```js
  var LETTER_DRAFT_HEADERS = [
    "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス", "発送日"
  ];
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト全件 + 新規1テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): レター下書きタブに発送日列を追加"
```

---

### Task 2: `shippingContent.js` — フォロー予定日の計算

**Files:**
- Create: `glow-ma/src/shippingContent.js`
- Test: `tests/glow_ma_shippingContent.test.mjs`

**Interfaces:**
- Consumes: `GlowAlerting.toDate`(`glow-ma/src/alerting.js`。**日付パースロジックを再定義しないこと**)
- Produces: `GlowShippingContent`オブジェクト。`DEFAULT_CONFIG`(object、`{ followUpDays: 10, followUpAction: "手紙フォロー架電" }`)、`computeFollowUpDate(sentDateValue, days)`: string|null(発送日から`days`日後の日付を`"yyyy-MM-dd"`文字列で返す。`sentDateValue`が不正な日付ならnull)

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_shippingContent.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const shippingContent = require("../glow-ma/src/shippingContent.js");

test("computeFollowUpDate: 発送日からN日後の日付をyyyy-MM-dd形式で返す", () => {
  assert.equal(shippingContent.computeFollowUpDate("2026-08-07", 10), "2026-08-17");
});

test("computeFollowUpDate: 月をまたぐ場合も正しく計算する", () => {
  assert.equal(shippingContent.computeFollowUpDate("2026-08-25", 10), "2026-09-04");
});

test("computeFollowUpDate: 不正な日付や空文字ならnullを返す", () => {
  assert.equal(shippingContent.computeFollowUpDate("", 10), null);
  assert.equal(shippingContent.computeFollowUpDate(null, 10), null);
  assert.equal(shippingContent.computeFollowUpDate("不正な値", 10), null);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_shippingContent.test.mjs`
Expected: FAIL(`../glow-ma/src/shippingContent.js`が存在しないためモジュール読み込みエラー)

- [ ] **Step 3: `glow-ma/src/shippingContent.js`を新規作成**

```js
/* GLOW企業リレーション台帳 レター発送日の記録・発送業者連携用CSV出力ロジック
 * ブラウザ相当のGAS(global.GlowShippingContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_shippingContent.test.mjs で検証される。
 *
 * 日付パースは glow-ma/src/alerting.js の GlowAlerting.toDate をそのまま利用し、
 * このファイルで重複定義しない。
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
    followUpDays: 10,
    followUpAction: "手紙フォロー架電"
  };

  function formatDate_(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function computeFollowUpDate(sentDateValue, days) {
    var date = getGlowAlerting_().toDate(sentDateValue);
    if (!date) return null;
    var result = new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
    return formatDate_(result);
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    computeFollowUpDate: computeFollowUpDate
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowShippingContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_shippingContent.test.mjs`
Expected: PASS(3テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/shippingContent.js tests/glow_ma_shippingContent.test.mjs
git commit -m "feat(glow-ma): フォロー予定日の計算ロジックを追加"
```

---

### Task 3: `shippingContent.js` — CSV組み立てと文字列化

**Files:**
- Modify: `glow-ma/src/shippingContent.js`
- Modify: `tests/glow_ma_shippingContent.test.mjs`

**Interfaces:**
- Consumes: `GlowAlerting.toDate`(Task 2と同じ)、`formatDate_`(Task 2でこのファイル内に定義済み)
- Produces: `GlowShippingContent.buildShippingCsvRows(letterDrafts, companies, targetDate)`: string[][](ヘッダー行を含む2次元配列。`letterDrafts`は「発送日」列を含むレター下書きレコードの配列、`companies`は企業マスタレコードの配列)、`GlowShippingContent.toCsvString(rows)`: string(2次元配列をCSV文字列に変換。カンマ・改行・ダブルクォートを含む値はダブルクォートでエスケープする)。ShippingRunner.gs(Task 5)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_shippingContent.test.mjs`の末尾に追記:

```js
test("buildShippingCsvRows: 指定した発送日に一致する下書きのみ、企業マスタと突合してCSV行を作る", () => {
  const letterDrafts = [
    { 下書きID: "D-1", 企業ID: "C000001", 発送日: "2026-08-10" },
    { 下書きID: "D-2", 企業ID: "C000002", 発送日: "2026-08-11" }
  ];
  const companies = [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", 所在地: "沖縄県那覇市1-1-1", 窓口担当者名: "山田" },
    { 企業ID: "C000002", 会社名: "サンプル建設株式会社", 所在地: "沖縄県浦添市2-2-2", 窓口担当者名: "田中" }
  ];
  const rows = shippingContent.buildShippingCsvRows(letterDrafts, companies, "2026-08-10");
  assert.deepEqual(rows, [
    ["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"],
    ["2026-08-10", "C000001", "テスト商事株式会社", "沖縄県那覇市1-1-1", "山田"]
  ]);
});

test("buildShippingCsvRows: 発送日が未入力の下書きは対象外", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: "" }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = shippingContent.buildShippingCsvRows(letterDrafts, companies, "2026-08-10");
  assert.deepEqual(rows, [["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"]]);
});

test("buildShippingCsvRows: 一致する発送日がなければヘッダー行のみ返す", () => {
  const rows = shippingContent.buildShippingCsvRows([], [], "2026-08-10");
  assert.deepEqual(rows, [["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"]]);
});

test("buildShippingCsvRows: 企業マスタに一致する企業が見つからない下書き行はスキップする(障害隔離)", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C999999", 発送日: "2026-08-10" }];
  const rows = shippingContent.buildShippingCsvRows(letterDrafts, [], "2026-08-10");
  assert.deepEqual(rows, [["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"]]);
});

test("toCsvString: カンマを含む値をダブルクォートで囲む", () => {
  const rows = [["発送日", "会社名"], ["2026-08-10", "テスト,商事株式会社"]];
  assert.equal(
    shippingContent.toCsvString(rows),
    '発送日,会社名\r\n2026-08-10,"テスト,商事株式会社"'
  );
});

test("toCsvString: ダブルクォートを含む値は二重にしてエスケープする", () => {
  const rows = [["会社名"], ['テスト"商事"株式会社']];
  assert.equal(
    shippingContent.toCsvString(rows),
    '会社名\r\n"テスト""商事""株式会社"'
  );
});

test("toCsvString: 空配列なら空文字列を返す", () => {
  assert.equal(shippingContent.toCsvString([]), "");
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_shippingContent.test.mjs`
Expected: FAIL(`shippingContent.buildShippingCsvRows`/`toCsvString`が`undefined`)

- [ ] **Step 3: `glow-ma/src/shippingContent.js`に実装を追加**

`formatDate_`関数の直後、`var api = {`の直前に追加する:

```js
  var CSV_HEADER_ROW = ["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"];

  function buildShippingCsvRows(letterDrafts, companies, targetDate) {
    var glowAlerting = getGlowAlerting_();
    var companyById = {};
    (companies || []).forEach(function (company) {
      companyById[company["企業ID"]] = company;
    });

    var rows = [];
    (letterDrafts || []).forEach(function (draft) {
      var sentDateValue = draft["発送日"];
      if (!sentDateValue) return;
      var sentDate = glowAlerting.toDate(sentDateValue);
      if (!sentDate) return;
      if (formatDate_(sentDate) !== targetDate) return;
      var company = companyById[draft["企業ID"]];
      if (!company) return;
      rows.push([
        targetDate,
        draft["企業ID"],
        company["会社名"] || "",
        company["所在地"] || "",
        company["窓口担当者名"] || ""
      ]);
    });
    return [CSV_HEADER_ROW].concat(rows);
  }

  function escapeCsvField_(value) {
    var stringValue = value === null || value === undefined ? "" : String(value);
    if (/[",\r\n]/.test(stringValue)) {
      return "\"" + stringValue.replace(/"/g, "\"\"") + "\"";
    }
    return stringValue;
  }

  function toCsvString(rows) {
    return (rows || []).map(function (row) {
      return row.map(escapeCsvField_).join(",");
    }).join("\r\n");
  }
```

`api`オブジェクトに追加する(既存のプロパティはそのまま残し、以下を追記):

```js
    buildShippingCsvRows: buildShippingCsvRows,
    toCsvString: toCsvString
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_shippingContent.test.mjs`
Expected: PASS(既存3テスト + 新規7テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/shippingContent.js tests/glow_ma_shippingContent.test.mjs
git commit -m "feat(glow-ma): 発送日ごとのCSV組み立て・文字列化ロジックを追加"
```

---

### Task 4: `ShippingRunner.gs` — 発送日入力時の自動記録(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/ShippingRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.LETTER_DRAFT_SHEET_NAME`/`LETTER_DRAFT_HEADERS`/`COMPANY_MASTER_SHEET_NAME`/`COMPANY_MASTER_HEADERS`/`INTERACTION_LOG_SHEET_NAME`/`INTERACTION_LOG_HEADERS`(Task 1・既存Phase 1〜2)、`GlowShippingContent.DEFAULT_CONFIG`/`computeFollowUpDate`(Task 2)
- Produces: `handleLetterDraftEdit(e)`関数(インストール型onEditトリガーのハンドラ)、`installLetterDraftEditTrigger()`関数(冪等なトリガー登録)

- [ ] **Step 1: `glow-ma/src/ShippingRunner.gs`を新規作成**

```js
/**
 * GLOW企業リレーション台帳: レター発送日の記録・発送業者連携用CSV出力
 *
 * 「発送日」は「投函完了日」(実際に送った日、または発送業者への依頼が完了し
 * 発送が確定した日)を意味する。これから依頼する予定日ではない。
 *
 * セットアップ(人間が一度だけ行う):
 * 1. `clasp push` で最新コードを反映する
 * 2. Apps Scriptエディタで installLetterDraftEditTrigger を一度だけ手動実行する
 *    (冪等なので安全に再実行できる。初回実行時に認可ダイアログが出るのは正常な挙動)
 *
 * 使い方:
 * 1. 「レター下書き」タブで、送付した下書きの行の「発送日」列に日付(yyyy-MM-dd)を入力する
 * 2. 自動的に以下が行われる:
 *    - 企業マスタの当該企業の「次回アクション予定日」が空の場合のみ、発送日+10日を
 *      セットする(既に別の予定日が設定されている場合は上書きしない)
 *    - 対応履歴ログに「手紙送付」が自動追記される(同じ下書きIDでの重複記録はしない)
 *
 * 注意: この関数は「onEdit」という予約名を使っていない。もし onEdit という名前にすると
 * GASの**シンプルトリガー**として自動実行されてしまうが、シンプルトリガーは権限が制限された
 * 実行コンテキストで動作し、LockServiceを使う本関数は認可が必要なため失敗する。そのため
 * この関数自体は直接トリガーされない普通の関数として定義し、installLetterDraftEditTrigger を
 * Apps Scriptエディタから**人間が手動で実行**して、認可済みの「インストール型トリガー」
 * として登録する必要がある(AlertRunner.gsのhandleInteractionLogEditと同じ設計)。
 */
function handleLetterDraftEdit(e) {
  if (!e || !e.range) return;
  var sheet = e.range.getSheet();
  if (sheet.getName() !== GlowSchema.LETTER_DRAFT_SHEET_NAME) return;
  if (e.range.getNumRows() !== 1 || e.range.getNumColumns() !== 1) return;

  var shippedDateColumnIndex = GlowSchema.LETTER_DRAFT_HEADERS.indexOf("発送日") + 1;
  if (e.range.getColumn() !== shippedDateColumnIndex) return;

  var row = e.range.getRow();
  if (row < 2) return;

  var sentDateValue = e.value;
  if (!sentDateValue) return;

  var headers = GlowSchema.LETTER_DRAFT_HEADERS;
  var rowValues = sheet.getRange(row, 1, 1, headers.length).getValues()[0];
  var draftId = rowValues[headers.indexOf("下書きID")];
  var companyId = rowValues[headers.indexOf("企業ID")];

  updateFollowUpDateIfEmpty_(companyId, sentDateValue);
  appendShippedInteractionLogIfNew_(companyId, draftId, sentDateValue);
}

/**
 * 企業マスタの「次回アクション予定日」が空の場合のみ、発送日+設定日数をセットする。
 * 既に値がある場合は何もしない(担当者が個別設定した予定日を上書きしないため)。
 */
function updateFollowUpDateIfEmpty_(companyId, sentDateValue) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    Logger.log(
      "企業マスタのロック取得に失敗したため、次回アクション予定日の自動セットをスキップしました: " + companyId
    );
    return;
  }
  try {
    var headers = GlowSchema.COMPANY_MASTER_HEADERS;
    var lastRow = companySheet.getLastRow();
    if (lastRow < 2) return;
    var values = companySheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
    var companyIdIndex = headers.indexOf("企業ID");
    var nextActionDateIndex = headers.indexOf("次回アクション予定日");
    var nextActionContentIndex = headers.indexOf("次回アクション内容");

    for (var i = 0; i < values.length; i++) {
      if (values[i][companyIdIndex] !== companyId) continue;
      if (values[i][nextActionDateIndex]) return;

      var followUpDate = GlowShippingContent.computeFollowUpDate(
        sentDateValue, GlowShippingContent.DEFAULT_CONFIG.followUpDays
      );
      if (!followUpDate) return;

      var sheetRow = i + 2;
      companySheet.getRange(sheetRow, nextActionDateIndex + 1).setValue(followUpDate);
      companySheet.getRange(sheetRow, nextActionContentIndex + 1).setValue(
        GlowShippingContent.DEFAULT_CONFIG.followUpAction
      );
      return;
    }
  } finally {
    lock.releaseLock();
  }
}

/**
 * 対応履歴ログに「手紙送付」を自動追記する。同じ下書きID由来の記録が既に
 * 存在する場合はスキップする(発送日セルを後から訂正しても重複記録しないため)。
 */
function appendShippedInteractionLogIfNew_(companyId, draftId, sentDateValue) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    Logger.log("対応履歴ログのロック取得に失敗したため、手紙送付の自動記録をスキップしました: " + companyId);
    return;
  }
  try {
    var headers = GlowSchema.INTERACTION_LOG_HEADERS;
    var marker = "下書きID: " + draftId;
    var lastRow = logSheet.getLastRow();
    if (lastRow >= 2) {
      var memoIndex = headers.indexOf("内容メモ");
      var values = logSheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
      for (var i = 0; i < values.length; i++) {
        if (String(values[i][memoIndex]).indexOf(marker) !== -1) return;
      }
    }

    var nextRow = logSheet.getLastRow() + 1;
    var logId = "H-" + Utilities.getUuid();
    logSheet.getRange(nextRow, 1, 1, headers.length).setValues([[
      logId, companyId, sentDateValue, "システム(自動記録)", "手紙送付", "未接触",
      "発送日の記録により自動追記(" + marker + ")", ""
    ]]);
  } finally {
    lock.releaseLock();
  }
}

/**
 * handleLetterDraftEdit をインストール型のonEditトリガーとして登録する。
 * 冪等: 実行時にまず同じハンドラ関数を指す既存トリガーをすべて削除してから
 * 新規登録するため、重複登録を心配せずに安全に再実行できる。
 */
function installLetterDraftEditTrigger() {
  var existingTriggers = ScriptApp.getProjectTriggers();
  existingTriggers.forEach(function (trigger) {
    if (trigger.getHandlerFunction() === "handleLetterDraftEdit") {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ScriptApp.newTrigger("handleLetterDraftEdit")
    .forSpreadsheet(ss)
    .onEdit()
    .create();
  Logger.log("発送日記録用のonEditトリガーを登録しました。");
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/ShippingRunner.gs /tmp/ShippingRunner_check.js && node --check /tmp/ShippingRunner_check.js && rm /tmp/ShippingRunner_check.js` で構文チェック
2. `GlowSchema.*`/`GlowShippingContent.*`の参照が、実際の`schema.js`(Task 1)・`shippingContent.js`(Task 2・3)の定義と一致していることを、両ファイルを読んで確認する
3. `updateFollowUpDateIfEmpty_`が、企業マスタの`次回アクション予定日`に既に値がある行では`return`し、`setValue`を呼ばずに終了することをコードを目でたどって確認する
4. `appendShippedInteractionLogIfNew_`が、同じ`下書きID`を含む`内容メモ`の行が既に存在する場合に`setValues`を呼ばずに`return`することを確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間が確認する手順:

1. `clasp push` で反映し、Apps Scriptエディタで`installLetterDraftEditTrigger`を実行する(初回は認可ダイアログが出る)
2. 企業マスタにテスト用の1社(次回アクション予定日が空)を用意し、対応する「レター下書き」タブの行の「発送日」列に本日の日付を入力する
3. 数秒後、企業マスタの当該企業の「次回アクション予定日」に発送日+10日、「次回アクション内容」に「手紙フォロー架電」がセットされていることを確認する
4. 対応履歴ログに「手紙送付」の行が1件追記されていることを確認する
5. 同じ「発送日」セルを別の日付に訂正し、対応履歴ログに重複して行が追加されないことを確認する
6. 別のテスト企業で、あらかじめ「次回アクション予定日」に何らかの日付を手動設定してから「発送日」を入力し、その予定日が上書きされないことを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/ShippingRunner.gs
git commit -m "feat(glow-ma): 発送日入力時の次回アクション予定日自動セット・対応履歴ログ自動記録を追加"
```

---

### Task 5: `ShippingRunner.gs` — 発送日でCSV出力メニュー(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/ShippingRunner.gs`
- Modify: `glow-ma/src/ShareRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.LETTER_DRAFT_SHEET_NAME`/`LETTER_DRAFT_HEADERS`/`COMPANY_MASTER_SHEET_NAME`(既存)、`readCompanyRecords_`(`glow-ma/src/ImportRunner.gs`。**再定義しないこと**)、`GlowShippingContent.buildShippingCsvRows`/`toCsvString`(Task 3)
- Produces: `exportShippingCsvForDate()`関数(メニューから実行するCSV出力ダイアログ表示)

- [ ] **Step 1: `glow-ma/src/ShippingRunner.gs`の末尾に追記**

```js
/**
 * メニュー「GLOW台帳」→「発送日でCSV出力」から実行する。
 * 指定した発送日に一致するレター下書きを、企業マスタと突合してCSV化し、
 * ダウンロードリンク付きのダイアログで表示する。業者への送信は行わない
 * (人がダウンロードしたファイルを自分の判断で業者に渡す運用)。
 */
function exportShippingCsvForDate() {
  var ui = SpreadsheetApp.getUi();
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var response = ui.prompt(
    "発送日でCSV出力",
    "対象の発送日を yyyy-MM-dd 形式で入力してください(空欄なら本日: " + todayString + ")",
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() !== ui.Button.OK) return;
  var targetDate = response.getResponseText().trim() || todayString;

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var draftSheet = ss.getSheetByName(GlowSchema.LETTER_DRAFT_SHEET_NAME);
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!draftSheet || !companySheet) {
    ui.alert(
      "「" + GlowSchema.LETTER_DRAFT_SHEET_NAME + "」または「" + GlowSchema.COMPANY_MASTER_SHEET_NAME +
      "」タブが見つかりません。先に ensureLedgerTabs を実行してください。"
    );
    return;
  }

  var letterDrafts = readLetterDrafts_(draftSheet);
  var companies = readCompanyRecords_(companySheet);
  var rows = GlowShippingContent.buildShippingCsvRows(letterDrafts, companies, targetDate);
  if (rows.length <= 1) {
    ui.alert("発送日「" + targetDate + "」に該当するデータがありません。");
    return;
  }

  var csvString = GlowShippingContent.toCsvString(rows);
  var html = buildCsvDownloadHtml_(csvString, targetDate);
  var output = HtmlService.createHtmlOutput(html).setWidth(480).setHeight(420);
  ui.showModalDialog(output, "発送日「" + targetDate + "」のCSV(" + (rows.length - 1) + "件)");
}

function readLetterDrafts_(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.LETTER_DRAFT_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row) {
    var record = {};
    headers.forEach(function (header, i) { record[header] = row[i]; });
    return record;
  });
}

function buildCsvDownloadHtml_(csvString, targetDate) {
  var base64Csv = Utilities.base64Encode(csvString, Utilities.Charset.UTF_8);
  var escapedCsv = csvString
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return "<div style=\"font-family:sans-serif;padding:0.75rem\">" +
    "<p><a download=\"letter_shipping_" + targetDate + ".csv\" " +
    "href=\"data:text/csv;charset=utf-8;base64," + base64Csv + "\">CSVをダウンロード</a></p>" +
    "<pre style=\"white-space:pre-wrap;font-size:0.8rem;border:1px solid #ccc;padding:0.5rem;" +
    "max-height:220px;overflow:auto\">" + escapedCsv + "</pre></div>";
}
```

- [ ] **Step 2: `glow-ma/src/ShareRunner.gs`の`onOpen()`にメニュー項目を追加**

既存の`onOpen()`(37〜42行目)を以下に置き換える(GASプロジェクト内で`onOpen`は1つしか持てないため、新規の`onOpen`は作らずこの既存関数に追記する):

```js
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("GLOW台帳")
    .addItem("選択中の企業を連携する", "showShareDialog")
    .addItem("発送日でCSV出力", "exportShippingCsvForDate")
    .addToUi();
}
```

- [ ] **Step 3: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/ShippingRunner.gs /tmp/ShippingRunner_check.js && node --check /tmp/ShippingRunner_check.js && rm /tmp/ShippingRunner_check.js` で構文チェック
2. `cp glow-ma/src/ShareRunner.gs /tmp/ShareRunner_check.js && node --check /tmp/ShareRunner_check.js && rm /tmp/ShareRunner_check.js` で構文チェック
3. `readLetterDrafts_`が返すレコードのキー(`GlowSchema.LETTER_DRAFT_HEADERS`の各要素)と、`GlowShippingContent.buildShippingCsvRows`が読む`draft["発送日"]`/`draft["企業ID"]`のキー名が一致していることを確認する
4. `exportShippingCsvForDate`が、CSVを業者へ送信するコード(`UrlFetchApp.fetch`等の外部送信)を一切含まず、ダイアログ表示のみで完結していることを確認する(設計書の「自動送信はしない」制約の遵守確認)

- [ ] **Step 4: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間が確認する手順:

1. `clasp push` して、スプレッドシートを開き直す
2. Task 4の手動検証で「発送日」を入力済みの状態から、メニュー「GLOW台帳」→「発送日でCSV出力」を実行する
3. プロンプトにその発送日を入力し、OKを押す
4. ダイアログにCSVプレビューとダウンロードリンクが表示され、リンクをクリックするとCSVファイルがダウンロードされることを確認する。列が「発送日・企業ID・会社名・所在地・窓口担当者名」の5列であることを確認する
5. 存在しない発送日(データが無い日付)を入力し、「該当するデータがありません」という案内が表示されることを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/ShippingRunner.gs glow-ma/src/ShareRunner.gs
git commit -m "feat(glow-ma): 発送日でCSV出力するメニューを追加"
```

---

### Task 6: READMEにPhase 16のセットアップ・使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜5の全成果物

- [ ] **Step 1: `glow-ma/README.md`の「## 対面連携: Slack DMでの即時共有(Phase 15)」セクションの直後、「## 次のフェーズ」の直前に新セクションを追加**

```markdown
## レター発送日の記録・発送業者連携用CSV出力(Phase 16)

「レター下書き」タブに「発送日」列を追加し、発送業者にそのまま連携できる宛先一覧CSVの
出力と、フォロー架電の見落とし防止を行う。CLAUDE.mdの三名体制ルールに基づき、
glow-ma-triangle-reviewで議事を確定してから実装した
(`docs/superpowers/specs/2026-08-07-glow-ma-letter-shipping-triangle-review.md`。
見直し期限: 2026-11-07)。

**「発送日」の意味:** 実際に発送した日、または発送業者への依頼が完了し発送が確定した日
(投函完了日)。これから業者に依頼する予定日ではない。

**セットアップ**

1. `clasp push` で最新コードを反映する
2. Apps Scriptエディタで `installLetterDraftEditTrigger` を一度だけ手動実行する
   (冪等なので安全に再実行できる。初回実行時に認可ダイアログが出るのは正常な挙動)

**使い方**

1. 「レター下書き」タブで、送付した下書きの行の「発送日」列に日付(`yyyy-MM-dd`)を入力する
2. 自動的に、企業マスタの当該企業の「次回アクション予定日」が空の場合のみ発送日+10日が
   セットされ(既に別の予定日がある場合は上書きしない)、対応履歴ログに「手紙送付」が
   自動追記される
3. 発送業者に渡す一覧が必要なときは、メニュー「GLOW台帳」→「発送日でCSV出力」を実行し、
   対象の発送日を入力する。表示されたダイアログからCSVをダウンロードし、内容を確認した上で
   自分の判断で発送業者に渡す(自動送信はしない)

**安全設計(glow-ma-triangle-review確定事項)**

- 次回アクション予定日は、担当者が個別に設定済みの場合は自動セットで上書きしない
- 対応履歴ログへの自動記録は下書きIDで重複チェックを行い、発送日セルを訂正しても
  記録が増殖しない
- CSVの発送業者への受け渡しは自動化せず、必ず人の判断を介する
- CSV列は宛先情報(発送日・企業ID・会社名・所在地・窓口担当者名)のみとし、手紙本文は
  含めない

**現時点の制約:**
- 発送業者への所在地・窓口担当者名の受け渡しについて、委託契約の要否は守り部への確認が
  未完了(本機能の実装はブロックしていないが、実運用開始前に確認すること)
- CSV出力は1つの発送日ごとの実行のみで、期間範囲での一括出力には対応していない
```

- [ ] **Step 2: 「## 次のフェーズ」セクションを更新**

`glow-ma/README.md`の「## 次のフェーズ」セクションを以下に置き換える:

```markdown
## 次のフェーズ

Phase 1〜16の実装フェーズが完了しました。
`docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md` の
各章に対応する機能(企業マスタ・スコアリング・アラート・レター生成・
ダッシュボード・電話番号/連絡不要フラグ・紹介パートナー成約率/ダッシュボード履歴・
ディールステージ細分化/工程別滞留状況・後継者状況フィールド・関係メモ・
入電の把握・担当者別ワークロード/長期検討企業の検知・窓口担当者名/携帯番号・
Slack通知/Claude API呼び出しの耐障害性・対面連携(Slack DM即時共有)・
レター発送日の記録/発送業者連携用CSV出力)はすべて実装済みです。
今後の改善点は各セクションの「現時点の制約」、および「本番投入前チェックリスト」を参照。
```

- [ ] **Step 3: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): Phase 16のセットアップ・使い方をREADMEに追記"
```

---

### 最終レビュー

- [ ] **Step 1: 全テストを実行**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全ファイル、既存テスト+Task 1・2・3で追加したテストすべて)

- [ ] **Step 2: 三名体制レビューの裁定事項が実装に反映されていることを確認**

`docs/superpowers/specs/2026-08-07-glow-ma-letter-shipping-triangle-review.md`の
「結論(裁定)」4点(次回アクション予定日は既存値がある場合は上書きしない/発送日は
投函完了日として単一の意味に統一/CSVの業者への送信は自動化しない/対応履歴ログの
対応相手は「未接触」で統一)が、それぞれTask 4・5・6のコード・READMEに反映されている
ことをファイルを読んで再確認する。

- [ ] **Step 3: GAS専用ファイルの静的チェックを再実行**

```bash
cp glow-ma/src/ShippingRunner.gs /tmp/ShippingRunner_check.js && node --check /tmp/ShippingRunner_check.js && rm /tmp/ShippingRunner_check.js
cp glow-ma/src/ShareRunner.gs /tmp/ShareRunner_check.js && node --check /tmp/ShareRunner_check.js && rm /tmp/ShareRunner_check.js
```

Expected: どちらも構文エラーなし

- [ ] **Step 4: 未実施の手動検証をレポートにまとめる**

Task 4・5の「手動検証(このサンドボックス環境では実行できない)」セクションの内容を
まとめ、Google Apps Script実行環境で人間が確認すべき手順としてレポートに明記する。

- [ ] **Step 5: 最終Commit(必要な場合のみ)**

レビューで修正が発生した場合のみ、修正内容をコミットする。修正がなければこのステップは
スキップする。
