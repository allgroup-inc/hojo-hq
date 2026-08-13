# glow-ma: レター発送 個別QRコード生成 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 発送日を指定すると、その日に発送予定の企業ごとに個別トラッキングURLをQRコード画像化し、Google Driveへ保存・結果一覧をシート出力する機能を追加する。

**Architecture:** 既存の`shippingContent.js`(発送日ベースの対象抽出)・`letterContent.js`(トラッキングURL組み立て)のロジックを再利用し、新規の純粋ロジックファイル`qrContent.js`でQR生成対象一覧(企業ID・会社名・トラッキングURL)を組み立てる。実際のQR画像生成(外部API呼び出し)・Drive保存・結果シート書き込みは新規GAS実行層`QrRunner.gs`が担う。既存の「発送日でCSV出力」メニューと同じ操作感の新規メニュー項目として提供する。

**Tech Stack:** Google Apps Script(GAS)、外部QR生成API(`api.qrserver.com`、APIキー不要)、Google Drive(`DriveApp`)、Node.js(`node --test`、純粋ロジックのテスト)。

## Global Constraints

- UMD形式(`(function(global){...})(typeof window!=="undefined"?window:globalThis)`)を新規`.js`ファイルすべてに適用し、`module.exports`(Node)/`global.GlowXxx`(GAS)の両対応にする。`.gs`ファイルはGAS専用でNode側テスト対象外(既存の全`.gs`ファイルと同じ扱い)。
- 既存の再利用可能なロジックは重複実装せず、必ず呼び出す: `GlowAlerting.toDate`(日付パース、alerting.js)、`GlowLetterContent.buildTrackingUrl`(トラッキングURL組み立て、letterContent.js)、`readCompanyRecords_`(企業マスタ読み込み、ImportRunner.gs)、`readLetterDrafts_`(レター下書き読み込み、ShippingRunner.gs)。
- 既存のScript Property `TRACKING_BASE_URL`(Phase 4で設定済み)をそのまま使う。新しい設定項目は追加しない。
- 1社のQR生成失敗が全体の処理を止めないよう障害隔離する(LetterRunner.gs等の既存方針を踏襲)。
- `var`のみを使う(`let`/`const`不使用)。既存の`.gs`/`.js`ファイル群のコーディング規約と完全に一致させる。
- 印刷用ラベルシート等の物理作業前提の出力形式は本計画のスコープ外(設計書2026-08-13-glow-ma-letter-qr-fulfillment-design.mdの「作らないもの」を参照。業者との差し込み印刷可否の結果待ち)。

---

### Task 1: schema.js — QR生成結果タブの定義を追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Test: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.QR_RESULT_SHEET_NAME`("QR生成結果")、`GlowSchema.QR_RESULT_HEADERS`(`["企業ID", "会社名", "トラッキングURL", "QR画像リンク", "ステータス"]`)。Task 3(SheetSetup.gs)・Task 4(QrRunner.gs)がこれを使う。

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs`の末尾に追加:

```javascript
test("QR生成結果タブの名称・見出しが定義されている", () => {
  assert.equal(schema.QR_RESULT_SHEET_NAME, "QR生成結果");
  assert.deepEqual(schema.QR_RESULT_HEADERS, [
    "企業ID", "会社名", "トラッキングURL", "QR画像リンク", "ステータス"
  ]);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: `QR_RESULT_SHEET_NAME`が`undefined`でFAIL

- [ ] **Step 3: 実装する**

`glow-ma/src/schema.js`の`PRE_SCREENING_MISMATCH_HEADERS`定義の直後に追加:

```javascript
  var QR_RESULT_SHEET_NAME = "QR生成結果";
  var QR_RESULT_HEADERS = [
    "企業ID", "会社名", "トラッキングURL", "QR画像リンク", "ステータス"
  ];
```

`var api = {...}`の末尾(`PRE_SCREENING_MISMATCH_HEADERS: PRE_SCREENING_MISMATCH_HEADERS`の直後)に追加:

```javascript
    QR_RESULT_SHEET_NAME: QR_RESULT_SHEET_NAME,
    QR_RESULT_HEADERS: QR_RESULT_HEADERS
```

(直前の行の末尾にカンマを追加するのを忘れないこと)

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): QR生成結果タブの定義を追加"
```

---

### Task 2: qrContent.js — QR生成対象一覧の抽出ロジック新規作成

**Files:**
- Create: `glow-ma/src/qrContent.js`
- Test: `tests/glow_ma_qrContent.test.mjs`(新規作成)

**Interfaces:**
- Consumes: `GlowAlerting.toDate(value)`(既存、alerting.js)、`GlowLetterContent.buildTrackingUrl(companyId, baseUrl)`(既存、letterContent.js)
- Produces: `GlowQrContent.buildQrManifestRows(letterDrafts, companies, targetDate, baseUrl)` →
  `[{ 企業ID, 会社名, trackingUrl }]`。Task 4(QrRunner.gs)がこの一覧の各行についてQR画像を生成する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_qrContent.test.mjs`を新規作成:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const qrContent = require("../glow-ma/src/qrContent.js");

test("buildQrManifestRows: 指定した発送日に一致する下書きのみ、企業マスタと突合してトラッキングURL付きの一覧を作る", () => {
  const letterDrafts = [
    { 下書きID: "D-1", 企業ID: "C000001", 発送日: "2026-08-20" },
    { 下書きID: "D-2", 企業ID: "C000002", 発送日: "2026-08-21" }
  ];
  const companies = [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社" },
    { 企業ID: "C000002", 会社名: "サンプル建設株式会社" }
  ];
  const rows = qrContent.buildQrManifestRows(
    letterDrafts, companies, "2026-08-20", "https://example.com/track"
  );
  assert.deepEqual(rows, [
    { "企業ID": "C000001", "会社名": "テスト商事株式会社", trackingUrl: "https://example.com/track?id=C000001" }
  ]);
});

test("buildQrManifestRows: 発送日が未入力の下書きは対象外", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: "" }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = qrContent.buildQrManifestRows(
    letterDrafts, companies, "2026-08-20", "https://example.com/track"
  );
  assert.deepEqual(rows, []);
});

test("buildQrManifestRows: 一致する発送日がなければ空配列を返す", () => {
  const rows = qrContent.buildQrManifestRows([], [], "2026-08-20", "https://example.com/track");
  assert.deepEqual(rows, []);
});

test("buildQrManifestRows: 企業マスタに一致する企業が見つからない下書き行はスキップする(障害隔離)", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C999999", 発送日: "2026-08-20" }];
  const rows = qrContent.buildQrManifestRows(letterDrafts, [], "2026-08-20", "https://example.com/track");
  assert.deepEqual(rows, []);
});

test("buildQrManifestRows: 発送日がDateオブジェクト(getValues由来)でも突合できる", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: new Date(2026, 7, 20) }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = qrContent.buildQrManifestRows(
    letterDrafts, companies, "2026-08-20", "https://example.com/track"
  );
  assert.deepEqual(rows, [
    { "企業ID": "C000001", "会社名": "テスト商事株式会社", trackingUrl: "https://example.com/track?id=C000001" }
  ]);
});

test("buildQrManifestRows: baseUrlが空ならトラッキングURLが組み立てられないため対象外", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: "2026-08-20" }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = qrContent.buildQrManifestRows(letterDrafts, companies, "2026-08-20", "");
  assert.deepEqual(rows, []);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_qrContent.test.mjs`
Expected: `Cannot find module '../glow-ma/src/qrContent.js'`でFAIL

- [ ] **Step 3: 実装する**

`glow-ma/src/qrContent.js`を新規作成:

```javascript
/* GLOW企業リレーション台帳 レター発送 個別QRコード生成対象の抽出ロジック
 * ブラウザ相当のGAS(global.GlowQrContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_qrContent.test.mjs で検証される。
 *
 * 発送日ベースの絞り込みは glow-ma/src/shippingContent.js の buildShippingCsvRows と
 * 同じ考え方(発送日一致・企業マスタとの突合)だが、出力の形(QR生成対象一覧)が異なるため
 * 独立した実装として持つ(将来的な共通化は本ファイルのスコープ外)。
 *
 * 日付パースは glow-ma/src/alerting.js の GlowAlerting.toDate を、トラッキングURLの組み立ては
 * glow-ma/src/letterContent.js の GlowLetterContent.buildTrackingUrl をそのまま利用し、
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

  function getGlowLetterContent_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./letterContent.js");
    }
    return global.GlowLetterContent;
  }

  function formatDate_(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function buildQrManifestRows(letterDrafts, companies, targetDate, baseUrl) {
    var glowAlerting = getGlowAlerting_();
    var glowLetterContent = getGlowLetterContent_();
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
      var trackingUrl = glowLetterContent.buildTrackingUrl(draft["企業ID"], baseUrl);
      if (!trackingUrl) return;
      rows.push({
        "企業ID": draft["企業ID"],
        "会社名": company["会社名"] || "",
        trackingUrl: trackingUrl
      });
    });
    return rows;
  }

  var api = {
    buildQrManifestRows: buildQrManifestRows
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowQrContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_qrContent.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/qrContent.js tests/glow_ma_qrContent.test.mjs
git commit -m "feat(glow-ma): QR生成対象一覧の抽出ロジックbuildQrManifestRowsを追加"
```

---

### Task 3: SheetSetup.gs — QR生成結果タブの自動作成

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.QR_RESULT_SHEET_NAME` / `GlowSchema.QR_RESULT_HEADERS`(Task 1)、既存の`ensureTab_(spreadsheet, sheetName, headers)`
- Produces: `ensureLedgerTabs()`実行時に「QR生成結果」タブが(存在しなければ)作成される。Task 4のQrRunner.gsがこのタブに結果を書き込む。

Node環境ではGAS依存(`SpreadsheetApp`等)のため実行できない。この変更はNode側テスト対象外(既存の`SheetSetup.gs`内の他の`ensureTab_`呼び出しと同じ扱い)。本番投入前の目視確認で担保する。

- [ ] **Step 1: 実装する(テストなし。GAS依存のため)**

`glow-ma/src/SheetSetup.gs`の`ensureLedgerTabs()`関数内、`ensureTab_(ss, GlowSchema.REFERRAL_RECORD_SHEET_NAME, GlowSchema.REFERRAL_RECORD_HEADERS);`の直後に追加:

```javascript
  ensureTab_(ss, GlowSchema.QR_RESULT_SHEET_NAME, GlowSchema.QR_RESULT_HEADERS);
```

関数冒頭のJSDocコメント(「実行すると...の10タブが」の部分)を、タブ数と名称を更新する:

```
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」
 * 「レター下書き」「ダッシュボード」「ダッシュボード履歴」「スタッフ」
 * 「パートナー対応履歴ログ」「紹介実績ログ」「QR生成結果」の11タブが
 * (存在しなければ)作成され、1行目に見出しが設定される。
```

- [ ] **Step 2: 構文の目視確認**

`{`/`}`の対応、`ensureTab_`呼び出しの引数(シート名・見出し配列)が`GlowSchema`の実際の定数名と一致していることを確認する。

- [ ] **Step 3: コミット**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): ensureLedgerTabsにQR生成結果タブの自動作成を追加"
```

---

### Task 4: QrRunner.gs — QR生成・Drive保存・結果シート出力・メニュー登録

**Files:**
- Create: `glow-ma/src/QrRunner.gs`
- Modify: `glow-ma/src/ShareRunner.gs`(`onOpen()`にメニュー項目を追加)

**Interfaces:**
- Consumes: `GlowQrContent.buildQrManifestRows`(Task 2)、`GlowSchema.LETTER_DRAFT_SHEET_NAME` / `COMPANY_MASTER_SHEET_NAME` / `QR_RESULT_SHEET_NAME` / `QR_RESULT_HEADERS`(既存+Task 1)、`readCompanyRecords_`(既存、ImportRunner.gs)、`readLetterDrafts_`(既存、ShippingRunner.gs)、Script Property `TRACKING_BASE_URL`(既存、Phase 4で設定済み)
- Produces: `exportQrCodesForDate()`(メニューから実行される公開関数)。メニュー「GLOW台帳」→「発送日でQR出力」から呼べるようになる。

Node環境ではGAS依存(`UrlFetchApp`・`DriveApp`・`SpreadsheetApp`)のため実行できない。この関数群はNode側テスト対象外(既存の`ShippingRunner.gs`・`LetterRunner.gs`等の他のGAS実行層と同じ扱い)。本番投入前の目視確認で担保する。

- [ ] **Step 1: 実装する(テストなし。GAS依存のため)**

`glow-ma/src/QrRunner.gs`を新規作成:

```javascript
/**
 * GLOW企業リレーション台帳: レター発送 個別QRコード生成
 *
 * メニュー「GLOW台帳」→「発送日でQR出力」から実行する。指定した発送日に一致する
 * レター下書きを企業マスタと突合し、各企業のトラッキングURL(letterContent.jsの
 * buildTrackingUrlと同じもの)をQRコード画像化してGoogle Driveに保存する。
 * 外部QR生成API(api.qrserver.com、APIキー不要)を使う。生成結果(成功/失敗)は
 * 「QR生成結果」タブに一覧で書き出す。
 *
 * 1社のQR生成失敗が全体の処理を止めないよう障害隔離する(LetterRunner.gs等と同じ方針)。
 *
 * セットアップ: 既存のScript Property TRACKING_BASE_URL(Phase 4で設定済み)が前提。
 * 新しい設定項目は追加しない。
 *
 * 発送はロット単位(数社〜数十社程度)を想定している。GASの1回の実行には6分の
 * 制限があるため、対象社数が多い場合は発送日を分けて複数回実行すること。
 */
function exportQrCodesForDate() {
  var ui = SpreadsheetApp.getUi();
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var response = ui.prompt(
    "発送日でQR出力",
    "対象の発送日を yyyy-MM-dd 形式で入力してください(空欄なら本日: " + todayString + ")",
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() !== ui.Button.OK) return;
  var targetDate = response.getResponseText().trim() || todayString;

  var baseUrl = PropertiesService.getScriptProperties().getProperty("TRACKING_BASE_URL");
  if (!baseUrl) {
    ui.alert("スクリプトプロパティ TRACKING_BASE_URL が未設定です。先に設定してください。");
    return;
  }

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
  var manifest = GlowQrContent.buildQrManifestRows(letterDrafts, companies, targetDate, baseUrl);
  if (manifest.length === 0) {
    ui.alert("発送日「" + targetDate + "」に該当するデータがありません。");
    return;
  }

  var folder = getOrCreateQrFolder_(targetDate);
  var results = manifest.map(function (row) {
    return generateAndSaveQr_(row, folder);
  });

  writeQrResultSheet_(ss, results);
  var successCount = results.filter(function (r) { return r["ステータス"] === "成功"; }).length;
  ui.alert(
    "発送日「" + targetDate + "」のQR出力が完了しました(" + successCount + "/" + results.length + "件成功)。" +
    "Driveフォルダ「" + folder.getName() + "」と「" + GlowSchema.QR_RESULT_SHEET_NAME + "」タブを確認してください。"
  );
}

/**
 * 発送日ごとのQR画像保存先フォルダを取得または新規作成する。
 * 同名フォルダが既にあれば再利用する(同じ発送日で再実行しても重複フォルダを作らない)。
 */
function getOrCreateQrFolder_(targetDate) {
  var folderName = "QR_" + targetDate;
  var folders = DriveApp.getFoldersByName(folderName);
  if (folders.hasNext()) return folders.next();
  return DriveApp.createFolder(folderName);
}

/**
 * 1社分のQRコード画像を外部API経由で生成し、Driveフォルダへ保存する。
 * API呼び出し・画像保存のいずれかが失敗しても例外を投げず、ステータス付きの
 * 結果オブジェクトを返す(1社の失敗で全体の処理を止めないため)。
 */
function generateAndSaveQr_(row, folder) {
  var qrApiUrl = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" +
    encodeURIComponent(row.trackingUrl);
  try {
    var response = UrlFetchApp.fetch(qrApiUrl, { muteHttpExceptions: true });
    if (response.getResponseCode() !== 200) {
      return {
        "企業ID": row["企業ID"], "会社名": row["会社名"], "トラッキングURL": row.trackingUrl,
        "QR画像リンク": "", "ステータス": "QR生成失敗(HTTP " + response.getResponseCode() + ")"
      };
    }
    var blob = response.getBlob().setName(row["企業ID"] + ".png");
    var file = folder.createFile(blob);
    return {
      "企業ID": row["企業ID"], "会社名": row["会社名"], "トラッキングURL": row.trackingUrl,
      "QR画像リンク": file.getUrl(), "ステータス": "成功"
    };
  } catch (err) {
    return {
      "企業ID": row["企業ID"], "会社名": row["会社名"], "トラッキングURL": row.trackingUrl,
      "QR画像リンク": "", "ステータス": "QR生成失敗(" + err.message + ")"
    };
  }
}

/**
 * QR生成結果一覧を「QR生成結果」タブに書き込む。実行のたびに既存の内容(見出し行を除く)を
 * クリアしてから書き込む(前回の発送日の結果が残らないようにするため)。
 */
function writeQrResultSheet_(ss, results) {
  var sheet = ss.getSheetByName(GlowSchema.QR_RESULT_SHEET_NAME);
  if (!sheet) return;
  var headers = GlowSchema.QR_RESULT_HEADERS;
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, headers.length).clearContent();
  }
  if (results.length === 0) return;
  var rows = results.map(function (result) {
    return headers.map(function (header) { return result[header] || ""; });
  });
  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
}
```

`glow-ma/src/ShareRunner.gs`の`onOpen()`関数内、`.addItem("発送日でCSV出力", "exportShippingCsvForDate")`の直後に追加:

```javascript
    .addItem("発送日でQR出力", "exportQrCodesForDate")
```

(既存の`.addToUi();`の前に挿入すること)

- [ ] **Step 2: 構文の目視確認**

`{`/`}`の対応、`grep -rn "function exportQrCodesForDate\|function getOrCreateQrFolder_\|function generateAndSaveQr_\|function writeQrResultSheet_" glow-ma/src/`で名前衝突がないことを確認する(それぞれ1件ずつ、`QrRunner.gs`内にあることを確認)。

- [ ] **Step 3: コミット**

```bash
git add glow-ma/src/QrRunner.gs glow-ma/src/ShareRunner.gs
git commit -m "feat(glow-ma): QrRunner.gs(QR生成・Drive保存・結果出力)とメニュー登録を追加"
```

---

### Task 5: README追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: なし(ドキュメントのみ)

- [ ] **Step 1: README.mdに新機能の説明を追記する**

`glow-ma/README.md`の「レター発送日の記録・発送業者連携用CSV出力(Phase 16)」セクションの直後に追記する:

```markdown
## レター発送 個別QRコード生成(2026-08-13)

発送日を指定すると、その日に発送予定の企業ごとに個別トラッキングURL(Phase 4のレター
追跡と同じもの)をQRコード画像化し、Google Driveに保存する。

**使い方:**
1. スプレッドシートのメニュー「GLOW台帳」→「発送日でQR出力」を実行する
2. 発送日(yyyy-MM-dd)を入力する
3. 対象企業のQR画像がGoogle Driveの「QR_発送日」フォルダに、企業IDをファイル名として保存される
4. 生成結果(成功・失敗、QR画像へのリンク)は「QR生成結果」タブで確認できる

**前提条件:** Script Property `TRACKING_BASE_URL`(Phase 4で設定済み)が必要。未設定の場合はエラーメッセージが表示される。

**注意事項:**
- QRコードの生成には外部API(`api.qrserver.com`)を利用する。トラッキングURLは元々手紙に
  印字して公開する情報のため、外部サービスに渡しても機密性の懸念はない
- 1社のQR生成に失敗しても他の企業の処理は継続する(失敗した行は「QR生成結果」タブに
  「QR生成失敗」のステータスで記録される)
- GASの1回の実行には6分の制限があるため、対象社数が多い場合(目安: 数十社を超える場合)は
  発送日を分けて複数回実行すること
- 印刷して封筒に貼付する用のラベルシート等の出力形式は未対応(発送業者との調整結果を
  踏まえて別途検討)
```

- [ ] **Step 2: コミット**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): レター発送 個別QRコード生成の使い方を追記"
```

---

## 最終レビュー後の想定作業(本Planの範囲外、SDD完了後に別途実施)

- 全タスク完了後、`node --test tests/glow_ma_*.test.mjs`で全体テストを実行し、最終コードレビューを行う
- `finishing-a-development-branch`スキルでmainへマージする
- 本番環境で`clasp push`→`ensureLedgerTabs`再実行(QR生成結果タブ作成)→メニュー動作確認を、ユーザーと一緒にスクリーンショットベースで行う
