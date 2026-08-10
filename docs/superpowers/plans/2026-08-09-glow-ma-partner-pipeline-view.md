# glow-ma 管理画面: 紹介パートナー開拓状況ビュー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** glow-maの管理画面(Phase 18a: adminApp.js/AdminRunner.gs)に、企業一覧と切り替えて見られる「紹介パートナー開拓状況」ビューを追加する。紹介パートナーマスタ・パートナー対応履歴ログ(新設)・紹介実績ログ(新設)を読み取り専用で可視化する。

**Architecture:** Phase 18aで確立済みのWeb App・許可リスト認証(小柳・福田・嶺井の3名、`Session.getActiveUser()`+スタッフタブのメールアドレス照合)をそのまま再利用し、新しいデプロイやURLは作らない。`adminApp.js`(単一ページ)に画面切り替えスイッチャーを追加し、既存の企業一覧ビューと新規のパートナー一覧ビューをクライアント側で切り替える。サーバー側は`AdminRunner.gs`に`getPartnerList`/`getPartnerDetail`を追加し、既存の`readPartnerRecords_`(`DashboardRunner.gs`)を再利用する。

**Tech Stack:** Google Apps Script(V8ランタイム、`HtmlService`、`google.script.run`)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの背景:** `docs/superpowers/specs/2026-08-09-glow-ma-partner-pipeline-view-design.md`に基づく。土台となる沖縄県内M&A紹介パートナー開拓の方針は`docs/superpowers/specs/2026-08-09-glow-ma-partner-development-design.md`(三名体制レビュー済み)を参照。紹介実績ログの閲覧権限(小柳・福田・嶺井の3名とも閲覧可)は2026-08-09に小柳さんが直接決裁済み。

## Global Constraints

- **`google.script.run`から呼ぶサーバー関数(`getPartnerList`・`getPartnerDetail`)の名前は、末尾に`_`を絶対に付けない。** Apps Scriptは末尾が`_`の関数を非公開扱いにし、`google.script.run`から呼び出せなくする(呼んでもエラーにすらならず、単に何も起きない)。これはPhase 18a最終レビューで実際に発生した不具合であり、各タスクで明示的に確認すること
- アクセス制御は関数名ではなく、各公開関数の冒頭で呼ぶ`requireAdminAccess_()`だけが担う(Phase 18aと同じ多層防御)。新規追加する`getPartnerList`・`getPartnerDetail`も両方とも冒頭で`requireAdminAccess_()`を呼ぶ
- 紹介実績ログ(紹介料率・契約内容という金額情報)の閲覧は、Phase 18aの許可リスト3名(小柳・福田・嶺井)全員が対象。追加のアクセス制御は不要(2026-08-09小柳さん決裁)
- 本フェーズは読み取り専用。パートナー候補の新規登録・対応履歴の入力・紹介実績の入力は行わない。書き込み系の`google.script.run`呼び出しを一切含めない
- 対応履歴ログ・パートナー対応履歴ログの日付は`Date`オブジェクトで返る可能性があるため、既存の`GlowAdminAccess.sortInteractionsByDateDesc`(内部で`normalizeDateForDisplay_`を使い日付を`"yyyy-MM-dd"`文字列に正規化する)を再利用し、文字列比較の不具合(Phase 18a最終レビューで発生済み)を再発させない
- 新規タブ(パートナー対応履歴ログ・紹介実績ログ)は`ensureLedgerTabs`(`SheetSetup.gs`)で自動作成する。個々のテーブル定義はスキーマの配列末尾に追加する形にする(既存の企業マスタ等と同じ、途中への列挿入禁止の慣習に従う)
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する
- HTML画面は独立した`.html`アセットではなく、`adminApp.js`内で文字列として組み立てる(既存の慣習)
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する

---

## File Structure

```
glow-ma/src/
  schema.js       — 既存修正: PARTNER_INTERACTION_LOG_SHEET_NAME/HEADERS、
                     REFERRAL_RECORD_SHEET_NAME/HEADERSを追加(Task 1)
  SheetSetup.gs   — 既存修正: ensureLedgerTabsに新規2タブの自動作成を追加(Task 2)
  AdminRunner.gs  — 既存修正: readPartnerInteractionsByPartnerId_・getPartnerList(Task 3)、
                     readReferralRecordsByPartnerId_・getPartnerDetail(Task 4)を追加
  adminApp.js     — 既存修正: 画面切り替えスイッチャー・パートナー一覧(Task 5)、
                     パートナードロワー(概要・対応履歴・紹介実績の3タブ)(Task 6)を追加
tests/
  glow_ma_schema.test.mjs   — 既存修正(Task 1)
  glow_ma_adminApp.test.mjs — 既存修正(Task 5, 6)
docs/glow-ma_本番投入手順書_統合版.md — セットアップ・動作確認チェックリストを追記(Task 7)
glow-ma/README.md                    — セットアップ・使い方を追記(Task 7)
```

---

### Task 1: `schema.js` — パートナー対応履歴ログ・紹介実績ログの定義を追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME`(`"パートナー対応履歴ログ"`)、
  `GlowSchema.PARTNER_INTERACTION_LOG_HEADERS`(`["履歴ID", "パートナーID", "日付", "対応者", "内容メモ", "次回アクション"]`)、
  `GlowSchema.REFERRAL_RECORD_SHEET_NAME`(`"紹介実績ログ"`)、
  `GlowSchema.REFERRAL_RECORD_HEADERS`(`["実績ID", "パートナーID", "紹介日", "対象企業ID", "紹介料率", "契約内容メモ", "成約有無"]`)。
  Task 2(`SheetSetup.gs`)・Task 3・Task 4(`AdminRunner.gs`)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs`の末尾(ファイル最後の`});`の直後)に追記する:

```js
test("パートナー対応履歴ログのタブ名・見出しが定義されている(紹介パートナー開拓状況ビュー)", () => {
  assert.equal(schema.PARTNER_INTERACTION_LOG_SHEET_NAME, "パートナー対応履歴ログ");
  assert.deepEqual(schema.PARTNER_INTERACTION_LOG_HEADERS, [
    "履歴ID", "パートナーID", "日付", "対応者", "内容メモ", "次回アクション"
  ]);
});

test("紹介実績ログのタブ名・見出しが定義されている(紹介パートナー開拓状況ビュー)", () => {
  assert.equal(schema.REFERRAL_RECORD_SHEET_NAME, "紹介実績ログ");
  assert.deepEqual(schema.REFERRAL_RECORD_HEADERS, [
    "実績ID", "パートナーID", "紹介日", "対象企業ID", "紹介料率", "契約内容メモ", "成約有無"
  ]);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`schema.PARTNER_INTERACTION_LOG_SHEET_NAME`等が`undefined`のため)

- [ ] **Step 3: `glow-ma/src/schema.js`に定義を追加**

`STAFF_HEADERS`の定義(`var STAFF_HEADERS = ["氏名", "Slack User ID", "有効", "メールアドレス"];`)の
直後、`var api = {`の直前に追加する:

```js
  var PARTNER_INTERACTION_LOG_SHEET_NAME = "パートナー対応履歴ログ";
  var PARTNER_INTERACTION_LOG_HEADERS = [
    "履歴ID", "パートナーID", "日付", "対応者", "内容メモ", "次回アクション"
  ];

  var REFERRAL_RECORD_SHEET_NAME = "紹介実績ログ";
  var REFERRAL_RECORD_HEADERS = [
    "実績ID", "パートナーID", "紹介日", "対象企業ID", "紹介料率", "契約内容メモ", "成約有無"
  ];
```

`var api = {`オブジェクトの末尾(`STAFF_HEADERS: STAFF_HEADERS`の直後)に追加する:

```js
    PARTNER_INTERACTION_LOG_SHEET_NAME: PARTNER_INTERACTION_LOG_SHEET_NAME,
    PARTNER_INTERACTION_LOG_HEADERS: PARTNER_INTERACTION_LOG_HEADERS,
    REFERRAL_RECORD_SHEET_NAME: REFERRAL_RECORD_SHEET_NAME,
    REFERRAL_RECORD_HEADERS: REFERRAL_RECORD_HEADERS
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト全件 + 新規2テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): パートナー対応履歴ログ・紹介実績ログのスキーマ定義を追加"
```

---

### Task 2: `SheetSetup.gs` — 新規2タブの自動作成(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME`/`PARTNER_INTERACTION_LOG_HEADERS`/
  `REFERRAL_RECORD_SHEET_NAME`/`REFERRAL_RECORD_HEADERS`(Task 1)、`ensureTab_`(既存)
- Produces: `ensureLedgerTabs()`実行時に「パートナー対応履歴ログ」「紹介実績ログ」の2タブが
  (存在しなければ)作成される

- [ ] **Step 1: `glow-ma/src/SheetSetup.gs`の`ensureLedgerTabs`を修正**

ファイル冒頭のコメント(1〜14行目)の「8タブ」という記述を「10タブ」に、タブ名の列挙に
「パートナー対応履歴ログ」「紹介実績ログ」を追加する:

```js
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」
 * 「レター下書き」「ダッシュボード」「ダッシュボード履歴」「スタッフ」
 * 「パートナー対応履歴ログ」「紹介実績ログ」の10タブが
 * (存在しなければ)作成され、1行目に見出しが設定される。
```

既存の`ensureLedgerTabs`関数内、`var staffSheet = ensureTab_(ss, GlowSchema.STAFF_SHEET_NAME, GlowSchema.STAFF_HEADERS);`と
`applyStaffActiveValidation_(staffSheet);`の行の直後、関数の閉じ`}`の直前に追加する:

```js
  ensureTab_(ss, GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME, GlowSchema.PARTNER_INTERACTION_LOG_HEADERS);
  ensureTab_(ss, GlowSchema.REFERRAL_RECORD_SHEET_NAME, GlowSchema.REFERRAL_RECORD_HEADERS);
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/SheetSetup.gs /tmp/SheetSetup_check.js && node --check /tmp/SheetSetup_check.js && rm /tmp/SheetSetup_check.js` で構文チェック
2. `GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME`等の参照が、Task 1で`schema.js`に追加した定義と
   一致していることを両ファイルを読んで確認する
3. 新規2タブにはデータ検証(プルダウン等)を設定しない(パートナー対応履歴ログ・紹介実績ログの
   列にはPhase 1〜18aのような入力規則の要件が設計書に無いため)ことを確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間が確認する手順:

1. `clasp push` して、Apps Scriptエディタで`ensureLedgerTabs`を実行する
2. スプレッドシートに「パートナー対応履歴ログ」「紹介実績ログ」の2タブが新規作成され、
   1行目に見出しが設定されていることを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): パートナー対応履歴ログ・紹介実績ログタブの自動作成を追加"
```

---

### Task 3: `AdminRunner.gs` — パートナー一覧取得(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/AdminRunner.gs`

**Interfaces:**
- Consumes: `requireAdminAccess_()`(Phase 18a・既存)、`readPartnerRecords_`(`glow-ma/src/DashboardRunner.gs`。
  **再定義しないこと**。`(sheet)`を受け取り、`sheet`が`falsy`なら`[]`を返し、それ以外は
  `GlowSchema.PARTNER_MASTER_HEADERS`をキーとするレコード配列を返す)、
  `GlowSchema.PARTNER_MASTER_SHEET_NAME`/`PARTNER_INTERACTION_LOG_SHEET_NAME`/
  `PARTNER_INTERACTION_LOG_HEADERS`(Task 1・既存)
- Produces: `readPartnerInteractionsByPartnerId_(sheet)`: object(パートナーIDをキーに対応履歴の
  配列を持つマップ)、`getPartnerList()`: array(パートナー一覧+対応回数)。Task 5(`adminApp.js`)が
  `google.script.run`で呼ぶ契約

- [ ] **Step 1: `glow-ma/src/AdminRunner.gs`の末尾に追記**

```js
/**
 * パートナー対応履歴ログを読み、パートナーIDごとに配列へグルーピングして返す。
 * readInteractionsByCompanyId_(ScoringRunner.gs、企業向け)と同じパターンだが、
 * 対象タブ・キー列(パートナーID)が異なるため専用の関数として定義する。
 */
function readPartnerInteractionsByPartnerId_(sheet) {
  var result = {};
  if (!sheet) return result;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.PARTNER_INTERACTION_LOG_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    var partnerId = record["パートナーID"];
    if (!partnerId) return;
    if (!result[partnerId]) result[partnerId] = [];
    result[partnerId].push(record);
  });
  return result;
}

/**
 * パートナー一覧(紹介パートナーマスタ全件+パートナー対応履歴ログの記録件数)を返す。
 * 企業一覧と異なり件数が少ない想定のため、絞り込み必須・件数上限は設けない。
 *
 * この関数の名前の末尾に `_` を付けてはいけない。Apps Scriptは末尾が`_`の関数を
 * 非公開扱いにし、google.script.run から呼び出せなくする(呼んでもエラーにすら
 * ならず、単に何も起きない)。アクセス制御は関数名ではなく、冒頭で呼んでいる
 * requireAdminAccess_() だけが担う(Phase 18a最終レビュー2026-08-09 Fix 1と同じ理由)。
 */
function getPartnerList() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var partnerSheet = ss.getSheetByName(GlowSchema.PARTNER_MASTER_SHEET_NAME);
  var partners = readPartnerRecords_(partnerSheet);

  var logSheet = ss.getSheetByName(GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME);
  var interactionsByPartner = readPartnerInteractionsByPartnerId_(logSheet);

  return partners.map(function (partner) {
    var partnerId = partner["パートナーID"];
    return {
      "パートナーID": partnerId,
      "名称": partner["名称"],
      "種別": partner["種別"],
      "関係性ランク": partner["関係性ランク"],
      "対応回数": (interactionsByPartner[partnerId] || []).length
    };
  });
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/AdminRunner.gs /tmp/AdminRunner_check.js && node --check /tmp/AdminRunner_check.js && rm /tmp/AdminRunner_check.js` で構文チェック
2. `getPartnerList`が末尾に`_`を付けていないこと、冒頭で`requireAdminAccess_()`を呼んでいることを確認する
3. `readPartnerRecords_`(`DashboardRunner.gs`)の実際の実装を読み、`(sheet)`という引数と
   `PARTNER_MASTER_HEADERS`をキーとするレコード配列を返す挙動が、`getPartnerList`の呼び出し方と
   一致していることを確認する(再定義していないこと)

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Task 5完了後にまとめて検証する(最終レビューのStep参照)。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/AdminRunner.gs
git commit -m "feat(glow-ma): 管理画面Web Appのパートナー一覧取得を追加"
```

---

### Task 4: `AdminRunner.gs` — パートナー詳細取得(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/AdminRunner.gs`

**Interfaces:**
- Consumes: `requireAdminAccess_()`(既存)、`readPartnerRecords_`(既存)、
  `readPartnerInteractionsByPartnerId_`(Task 3)、`GlowAdminAccess.sortInteractionsByDateDesc`
  (`glow-ma/src/adminAccess.js`。既存、`日付`キーを持つレコード配列を日付降順に正規化して返す)、
  `GlowSchema.REFERRAL_RECORD_SHEET_NAME`/`REFERRAL_RECORD_HEADERS`(Task 1)
- Produces: `readReferralRecordsByPartnerId_(sheet)`: object(パートナーIDをキーに紹介実績の配列を
  持つマップ)、`getPartnerDetail(partnerId)`: `{partner, history, referrals}` または `null`。
  Task 6(`adminApp.js`)が`google.script.run`で呼ぶ契約

- [ ] **Step 1: `glow-ma/src/AdminRunner.gs`の末尾に追記**

```js
function readReferralRecordsByPartnerId_(sheet) {
  var result = {};
  if (!sheet) return result;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.REFERRAL_RECORD_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    var partnerId = record["パートナーID"];
    if (!partnerId) return;
    if (!result[partnerId]) result[partnerId] = [];
    result[partnerId].push(record);
  });
  return result;
}

/**
 * パートナー1件分の基本情報+対応履歴(日付降順)+紹介実績を返す。
 * 該当パートナーが見つからない場合はnullを返す。
 *
 * 紹介実績は件数が少ない想定のため、この時点では並び替えを行わずシート上の
 * 順序のまま返す(対応履歴のような大量データではないため、Task 5・6の時点では
 * ソートの必要性が薄いと判断。必要になれば後続フェーズで追加する)。
 *
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function getPartnerDetail(partnerId) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var partnerSheet = ss.getSheetByName(GlowSchema.PARTNER_MASTER_SHEET_NAME);
  var partners = readPartnerRecords_(partnerSheet);
  var partner = partners.filter(function (p) { return p["パートナーID"] === partnerId; })[0];
  if (!partner) return null;

  var logSheet = ss.getSheetByName(GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME);
  var interactionsByPartner = readPartnerInteractionsByPartnerId_(logSheet);
  var history = GlowAdminAccess.sortInteractionsByDateDesc(interactionsByPartner[partnerId] || []);

  var referralSheet = ss.getSheetByName(GlowSchema.REFERRAL_RECORD_SHEET_NAME);
  var referrals = readReferralRecordsByPartnerId_(referralSheet)[partnerId] || [];

  return { partner: partner, history: history, referrals: referrals };
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/AdminRunner.gs /tmp/AdminRunner_check.js && node --check /tmp/AdminRunner_check.js && rm /tmp/AdminRunner_check.js` で構文チェック
2. `getPartnerDetail`が末尾に`_`を付けていないこと、冒頭で`requireAdminAccess_()`を呼んでいることを確認する
3. `GlowAdminAccess.sortInteractionsByDateDesc`(`adminAccess.js`)の実装を読み、`日付`キーを持つ
   レコード配列を受け取る関数であることと、`interactionsByPartner[partnerId]`(パートナー対応履歴ログの
   `日付`列を含むレコード)がその入力形式と一致していることを確認する
4. `getPartnerDetail`が見つからない場合に`null`を返し、例外を投げないことを確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Task 6完了後にまとめて検証する(最終レビューのStep参照)。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/AdminRunner.gs
git commit -m "feat(glow-ma): 管理画面Web Appのパートナー詳細取得を追加"
```

---

### Task 5: `adminApp.js` — 画面切り替えスイッチャー・パートナー一覧

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Modify: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getPartnerList()`(Task 3。画面内の`google.script.run`呼び出し先として名前が一致している必要がある)
- Produces: 画面上部の「企業一覧」「紹介パートナー開拓状況」切り替えスイッチャー、パートナー一覧
  テーブル、パートナードロワーの開閉(中身の描画はTask 6)

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminApp.test.mjs`の末尾に追記:

```js
test("buildAdminAppHtml: 画面切り替えスイッチャー・パートナー一覧・パートナードロワーの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["viewCompanyBtn", "viewPartnerBtn", "companyView", "partnerView", "partnerTableBody",
   "partnerEmptyState", "partnerDrawer", "partnerDrawerName", "partnerDrawerId", "partnerDrawerClose"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetPartnerListを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getPartnerList(") !== -1);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL(`viewCompanyBtn`等の要素、`.getPartnerList(`呼び出しがまだ存在しないため)

- [ ] **Step 3: `glow-ma/src/adminApp.js`を修正**

`STYLE`配列の末尾(`"#overlay.open{display:block}"`の行)を以下に置き換える:

```js
    "#overlay,#partnerOverlay{position:fixed;inset:0;background:rgba(17,32,44,0.25);display:none}",
    "#overlay.open,#partnerOverlay.open{display:block}",
    "#viewSwitcher{display:flex;gap:0;background:#00335c}",
    "#viewSwitcher button{flex:none;padding:0.6rem 1.1rem;border:0;background:none;",
    "color:rgba(255,255,255,0.7);cursor:pointer;font:inherit;border-bottom:2px solid transparent}",
    "#viewSwitcher button.active{color:#fff;border-bottom-color:#f88800;font-weight:600}",
    ".viewPane{display:none}",
    ".viewPane.active{display:block}"
```

同じ`STYLE`配列内の以下3箇所を、それぞれパートナードロワー用のIDも同じスタイルを共有するように置き換える(既存の値は変えず、セレクタにパートナー版を追加するだけ):

```js
    "#drawer{position:fixed;top:0;right:0;bottom:0;width:min(420px,100%);background:#fff;",
```
→
```js
    "#drawer,#partnerDrawer{position:fixed;top:0;right:0;bottom:0;width:min(420px,100%);background:#fff;",
```

```js
    "#drawer.open{transform:translateX(0)}",
```
→
```js
    "#drawer.open,#partnerDrawer.open{transform:translateX(0)}",
```

```js
    "#drawerHeader{padding:1rem 1.25rem;border-bottom:1px solid #e5e9eb;display:flex;",
```
→
```js
    "#drawerHeader,#partnerDrawerHeader{padding:1rem 1.25rem;border-bottom:1px solid #e5e9eb;display:flex;",
```

```js
    "#drawerClose{border:0;background:none;font-size:1.1rem;cursor:pointer;color:#4a5a66}",
```
→
```js
    "#drawerClose,#partnerDrawerClose{border:0;background:none;font-size:1.1rem;cursor:pointer;color:#4a5a66}",
```

```js
    "#drawerBody{overflow-y:auto;padding:1rem 1.25rem;flex:1}",
```
→
```js
    "#drawerBody,#partnerDrawerBody{overflow-y:auto;padding:1rem 1.25rem;flex:1}",
```

`HEADER_AND_FILTERS`変数の1行目を置き換える:

```js
    "<header><h1>GLOW企業リレーション台帳</h1></header>",
```
→
```js
    "<header><h1>GLOW企業リレーション台帳</h1></header>",
    "<div id=\"viewSwitcher\"><button id=\"viewCompanyBtn\" class=\"active\">企業一覧</button>",
    "<button id=\"viewPartnerBtn\">紹介パートナー開拓状況</button></div>",
```

`TABLE`変数全体を以下に置き換える(既存の内容を`<div id="companyView" class="viewPane active">`で
囲み、閉じタグを追加するだけで中身は変更しない):

```js
  var TABLE = [
    "<div id=\"companyView\" class=\"viewPane active\">",
    "<table><thead><tr><th>会社名</th><th>ランク</th><th>現在ステージ</th>",
    "<th>次回アクション予定日</th><th>担当者</th></tr></thead>",
    "<tbody id=\"companyTableBody\"></tbody></table>",
    "<div class=\"empty\" id=\"emptyState\" style=\"display:none\">該当する企業が見つかりません</div>",
    "</div>"
  ].join("");
```

`TABLE`変数の直後に新しい変数`PARTNER_VIEW`を追加する:

```js
  var PARTNER_VIEW = [
    "<div id=\"partnerView\" class=\"viewPane\">",
    "<table><thead><tr><th>名称</th><th>種別</th><th>関係性ランク</th><th>対応回数</th></tr></thead>",
    "<tbody id=\"partnerTableBody\"></tbody></table>",
    "<div class=\"empty\" id=\"partnerEmptyState\" style=\"display:none\">該当するパートナーが見つかりません</div>",
    "</div>"
  ].join("");
```

`DRAWER`変数の直後に新しい変数`PARTNER_DRAWER`を追加する(Task 6で中身のタブ・ペインを使うが、
この時点では骨組みのみ):

```js
  var PARTNER_DRAWER = [
    "<div id=\"partnerOverlay\"></div>",
    "<div id=\"partnerDrawer\">",
    "<div id=\"partnerDrawerHeader\"><div><div id=\"partnerDrawerName\" style=\"font-weight:700\"></div>",
    "<div id=\"partnerDrawerId\" style=\"font-size:0.8rem;color:#7a828a\"></div></div>",
    "<button id=\"partnerDrawerClose\">&times;</button></div>",
    "<div id=\"partnerDrawerBody\"></div>",
    "</div>"
  ].join("");
```

`SCRIPT`配列の中の`"function closeDrawer(){"`ブロックの直後(`"}"`で終わった直後)、
`"function switchTab(target){"`ブロックの直前に、以下を追加する:

```js
    "function switchView(target){",
    "var isCompany = target === 'company';",
    "document.getElementById('viewCompanyBtn').classList.toggle('active', isCompany);",
    "document.getElementById('viewPartnerBtn').classList.toggle('active', !isCompany);",
    "document.getElementById('companyView').classList.toggle('active', isCompany);",
    "document.getElementById('partnerView').classList.toggle('active', !isCompany);",
    "}",

    "function loadPartnerList(){",
    "google.script.run.withSuccessHandler(renderPartnerTable).withFailureHandler(function(error){",
    "document.getElementById('partnerTableBody').innerHTML = '';",
    "var empty = document.getElementById('partnerEmptyState');",
    "empty.style.display = 'block'; empty.textContent = '読み込みに失敗しました。再読み込みしてください。';",
    "}).getPartnerList();",
    "}",

    "function renderPartnerTable(rows){",
    "var tbody = document.getElementById('partnerTableBody'); tbody.innerHTML = '';",
    "var empty = document.getElementById('partnerEmptyState');",
    "if (!rows || rows.length === 0){ empty.style.display = 'block';",
    "empty.textContent = '該当するパートナーが見つかりません'; return; }",
    "empty.style.display = 'none';",
    "rows.forEach(function(row){",
    "var tr = document.createElement('tr');",
    "tr.innerHTML = '<td>' + escapeHtml(row['名称']) + '</td>' +",
    "'<td>' + escapeHtml(row['種別']) + '</td>' +",
    "'<td>' + escapeHtml(row['関係性ランク']) + '</td>' +",
    "'<td>' + escapeHtml(row['対応回数']) + '</td>';",
    "tr.addEventListener('click', function(){ openPartnerDrawer(row['パートナーID']); });",
    "tbody.appendChild(tr);});",
    "}",

    "function openPartnerDrawer(partnerId){",
    "document.getElementById('partnerDrawer').classList.add('open');",
    "document.getElementById('partnerOverlay').classList.add('open');",
    "document.getElementById('partnerDrawerName').textContent = '読み込み中…';",
    "document.getElementById('partnerDrawerId').textContent = partnerId;",
    "google.script.run.withSuccessHandler(renderPartnerDrawer).withFailureHandler(function(){",
    "document.getElementById('partnerDrawerName').textContent = '読み込みに失敗しました。再読み込みしてください。';",
    "}).getPartnerDetail(partnerId);",
    "}",

    "function renderPartnerDrawer(detail){",
    "if (!detail){ document.getElementById('partnerDrawerName').textContent = '該当するパートナーが見つかりません'; return; }",
    "document.getElementById('partnerDrawerName').textContent = detail.partner['名称'] || '(名称未登録)';",
    "}",

    "function closePartnerDrawer(){",
    "document.getElementById('partnerDrawer').classList.remove('open');",
    "document.getElementById('partnerOverlay').classList.remove('open');",
    "}",
```

`SCRIPT`配列の末尾付近、既存の`"document.getElementById('tabHistoryBtn').addEventListener(...)"`の行の
直後、`"loadFilterOptions();"`の直前に、以下を追加する:

```js
    "document.getElementById('viewCompanyBtn').addEventListener('click', function(){ switchView('company'); });",
    "document.getElementById('viewPartnerBtn').addEventListener('click', function(){ switchView('partner'); });",
    "document.getElementById('partnerDrawerClose').addEventListener('click', closePartnerDrawer);",
    "document.getElementById('partnerOverlay').addEventListener('click', closePartnerDrawer);",
```

`SCRIPT`配列の最後の行`"loadList();"`を以下に置き換える:

```js
    "loadList();",
    "loadPartnerList();"
```

`buildAdminAppHtml`関数内の組み立て行を修正する:

```js
      HEADER_AND_FILTERS + TABLE + DRAWER +
```
→
```js
      HEADER_AND_FILTERS + TABLE + PARTNER_VIEW + DRAWER + PARTNER_DRAWER +
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: PASS(既存テスト全件 + 新規2テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): 管理画面に紹介パートナー開拓状況ビューの切り替え・一覧を追加"
```

---

### Task 6: `adminApp.js` — パートナードロワー(概要・対応履歴・紹介実績)

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Modify: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getPartnerDetail(partnerId)`(Task 4。`{partner, history, referrals}` または `null`を返す契約)
- Produces: パートナードロワーの概要・対応履歴・紹介実績の3タブとその中身の描画

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminApp.test.mjs`の末尾に追記:

```js
test("buildAdminAppHtml: パートナードロワーに概要・対応履歴・紹介実績の3タブを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["tabPartnerOverviewBtn", "tabPartnerHistoryBtn", "tabPartnerReferralsBtn",
   "panePartnerOverview", "panePartnerHistory", "panePartnerReferrals"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetPartnerDetailを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getPartnerDetail(") !== -1);
});

test("buildAdminAppHtml: 書き込み系のgoogle.script.run呼び出しを一切含まない(紹介パートナー開拓状況ビューも読み取り専用)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["addPartner", "logPartnerInteraction", "recordReferral"].forEach((forbidden) => {
    assert.equal(html.indexOf(forbidden), -1, forbidden + " への呼び出しが含まれてはいけない(後続フェーズの機能)");
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL(`tabPartnerOverviewBtn`等の要素、`.getPartnerDetail(`呼び出しがまだ存在しないため)

- [ ] **Step 3: `glow-ma/src/adminApp.js`を修正**

Task 5で追加した`PARTNER_DRAWER`変数を以下に置き換える(タブとペインを追加):

```js
  var PARTNER_DRAWER = [
    "<div id=\"partnerOverlay\"></div>",
    "<div id=\"partnerDrawer\">",
    "<div id=\"partnerDrawerHeader\"><div><div id=\"partnerDrawerName\" style=\"font-weight:700\"></div>",
    "<div id=\"partnerDrawerId\" style=\"font-size:0.8rem;color:#7a828a\"></div></div>",
    "<button id=\"partnerDrawerClose\">&times;</button></div>",
    "<div class=\"tabs\"><button id=\"tabPartnerOverviewBtn\" class=\"active\">概要</button>",
    "<button id=\"tabPartnerHistoryBtn\">対応履歴</button>",
    "<button id=\"tabPartnerReferralsBtn\">紹介実績</button></div>",
    "<div id=\"partnerDrawerBody\">",
    "<div id=\"panePartnerOverview\"></div>",
    "<div id=\"panePartnerHistory\" style=\"display:none\"></div>",
    "<div id=\"panePartnerReferrals\" style=\"display:none\"></div>",
    "</div></div>"
  ].join("");
```

Task 5で追加した`SCRIPT`配列内の`renderPartnerDrawer`関数を、以下に置き換える:

```js
    "function renderPartnerDrawer(detail){",
    "if (!detail){ document.getElementById('partnerDrawerName').textContent = '該当するパートナーが見つかりません';",
    "document.getElementById('panePartnerOverview').innerHTML = '';",
    "document.getElementById('panePartnerHistory').innerHTML = '';",
    "document.getElementById('panePartnerReferrals').innerHTML = ''; return; }",
    "var p = detail.partner;",
    "document.getElementById('partnerDrawerName').textContent = p['名称'] || '(名称未登録)';",
    "document.getElementById('partnerDrawerId').textContent = p['パートナーID'];",
    "var fields = [",
    "['種別', p['種別']], ['担当者名', p['担当者名']], ['関係性ランク', p['関係性ランク']],",
    "['累計紹介数', p['累計紹介数']], ['成約数', p['成約数']],",
    "['提供済み情報ログ', p['提供済み情報ログ']], ['逆紹介履歴', p['逆紹介履歴']]",
    "];",
    "document.getElementById('panePartnerOverview').innerHTML = fields.map(function(f){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(f[0]) + '</div>' +",
    "'<div class=\"value\">' + (escapeHtml(f[1]) || '—') + '</div></div>';",
    "}).join('');",
    "var history = detail.history || [];",
    "document.getElementById('panePartnerHistory').innerHTML = history.length === 0",
    "? '<div class=\"empty\">対応履歴がありません</div>'",
    ": history.map(function(h){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(h['日付']) + '</div>' +",
    "'<div class=\"value\">' + escapeHtml(h['内容メモ']) + '</div></div>';",
    "}).join('');",
    "var referrals = detail.referrals || [];",
    "document.getElementById('panePartnerReferrals').innerHTML = referrals.length === 0",
    "? '<div class=\"empty\">紹介実績がありません</div>'",
    ": referrals.map(function(r){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(r['紹介日']) + '・紹介料率: ' + escapeHtml(r['紹介料率']) + '</div>' +",
    "'<div class=\"value\">' + escapeHtml(r['契約内容メモ']) + '(成約有無: ' + escapeHtml(r['成約有無']) + ')</div></div>';",
    "}).join('');",
    "}",
```

`SCRIPT`配列内の`switchTab`関数の直後(`"}"`の直後)に、パートナー用のタブ切り替え関数を追加する:

```js
    "function switchPartnerTab(target){",
    "var isOverview = target === 'overview';",
    "var isHistory = target === 'history';",
    "document.getElementById('tabPartnerOverviewBtn').classList.toggle('active', isOverview);",
    "document.getElementById('tabPartnerHistoryBtn').classList.toggle('active', isHistory);",
    "document.getElementById('tabPartnerReferralsBtn').classList.toggle('active', !isOverview && !isHistory);",
    "document.getElementById('panePartnerOverview').style.display = isOverview ? 'block' : 'none';",
    "document.getElementById('panePartnerHistory').style.display = isHistory ? 'block' : 'none';",
    "document.getElementById('panePartnerReferrals').style.display = (!isOverview && !isHistory) ? 'block' : 'none';",
    "}",
```

`SCRIPT`配列内、Task 5で追加した`"document.getElementById('partnerOverlay').addEventListener('click', closePartnerDrawer);"`の
直後に、以下を追加する:

```js
    "document.getElementById('tabPartnerOverviewBtn').addEventListener('click', function(){ switchPartnerTab('overview'); });",
    "document.getElementById('tabPartnerHistoryBtn').addEventListener('click', function(){ switchPartnerTab('history'); });",
    "document.getElementById('tabPartnerReferralsBtn').addEventListener('click', function(){ switchPartnerTab('referrals'); });",
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: PASS(既存テスト全件 + 新規3テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): パートナードロワーに概要・対応履歴・紹介実績タブを追加"
```

---

### Task 7: ドキュメント追記

**Files:**
- Modify: `docs/glow-ma_本番投入手順書_統合版.md`
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜6の全成果物

- [ ] **Step 1: `docs/glow-ma_本番投入手順書_統合版.md`の「## Phase 18a セットアップ・動作確認チェックリスト」セクションの直後に新セクションを追加**

```markdown
## 紹介パートナー開拓状況ビュー セットアップ・動作確認チェックリスト

**セットアップ**

- [ ] `clasp push` で最新コードを反映する
- [ ] Apps Scriptエディタで `ensureLedgerTabs` を再実行する(「パートナー対応履歴ログ」
      「紹介実績ログ」の2タブが追加される)
- [ ] 「紹介パートナーマスタ」タブに、開拓先候補を登録する(パートナーID・名称・種別等)。
      対応履歴・紹介実績を記録したい場合は、「パートナー対応履歴ログ」「紹介実績ログ」に
      直接行を追加する(この段階では画面からの入力はできない)

**動作確認**

- [ ] 管理画面(`?page=admin`)を開き、画面上部の「紹介パートナー開拓状況」をクリックして
      画面が切り替わることを確認する
- [ ] パートナー一覧に、紹介パートナーマスタに登録した候補が表示されることを確認する
- [ ] 「パートナー対応履歴ログ」に対応履歴を追加した候補について、一覧の「対応回数」が
      正しくカウントされることを確認する
- [ ] パートナーの行をクリックし、詳細ドロワーに概要・対応履歴・紹介実績の3タブが表示され、
      それぞれのタブ切り替えが機能することを確認する
- [ ] 「紹介実績ログ」に案件を追加した候補について、紹介実績タブに紹介料率・契約内容メモ・
      成約有無が表示されることを確認する
- [ ] 小柳・福田・嶺井のいずれのアカウントでも、紹介実績ログの内容(紹介料率・契約内容)が
      閲覧できることを確認する(2026-08-09小柳さん決裁: 3名とも閲覧可)

**現時点の制約:**
- 読み取り専用。パートナー候補の新規登録・対応履歴の入力・紹介実績の入力は
  スプレッドシートを直接編集する運用
- 提携部(musubu.md)との役割分担・紹介料率の扱い方針・パイロット対象の詳細は
  `docs/superpowers/specs/2026-08-09-glow-ma-partner-development-design.md`を参照
```

- [ ] **Step 2: `glow-ma/README.md`に新セクションを追加**

`glow-ma/README.md`の「## 管理画面Web App: 企業一覧・詳細の閲覧(Phase 18a)」セクションの直後に
追加する:

```markdown
## 管理画面Web App: 紹介パートナー開拓状況ビュー

Phase 18aの管理画面に、企業一覧と切り替えて見られる「紹介パートナー開拓状況」ビューを追加した。
沖縄県内M&A紹介パートナー開拓(候補一覧・プレイブック)の設計は
`docs/superpowers/specs/2026-08-09-glow-ma-partner-development-design.md`、システム部分の設計は
`docs/superpowers/specs/2026-08-09-glow-ma-partner-pipeline-view-design.md`を参照。

Phase 18aと同じ認証(小柳・福田・嶺井の3名)をそのまま使う。紹介料率・契約内容という金額情報も
含めて3名とも閲覧可能(2026-08-09小柳さん決裁)。読み取り専用で、パートナー候補の新規登録・
対応履歴の入力・紹介実績の入力はスプレッドシートを直接編集する運用。

**セットアップ・動作確認**: `docs/glow-ma_本番投入手順書_統合版.md`の「紹介パートナー開拓状況
ビュー セットアップ・動作確認チェックリスト」を参照。
```

- [ ] **Step 3: Commit**

```bash
git add docs/glow-ma_本番投入手順書_統合版.md glow-ma/README.md
git commit -m "docs(glow-ma): 紹介パートナー開拓状況ビューのセットアップ・使い方を追記"
```

---

### 最終レビュー

- [ ] **Step 1: 全テストを実行**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全ファイル、既存テスト+Task 1・5・6で追加したテストすべて)

- [ ] **Step 2: 命名規則の再確認(Global Constraints)**

```bash
grep -n "^function getPartnerList\|^function getPartnerDetail" glow-ma/src/AdminRunner.gs
```

Expected: どちらも末尾に`_`が付いていないこと

- [ ] **Step 3: 多層防御の再確認**

`getPartnerList`・`getPartnerDetail`の両方が、冒頭で`requireAdminAccess_()`を呼んでいることを
ファイルを読んで再確認する。

- [ ] **Step 4: GAS専用ファイルの静的チェックを再実行**

```bash
cp glow-ma/src/SheetSetup.gs /tmp/SheetSetup_check.js && node --check /tmp/SheetSetup_check.js && rm /tmp/SheetSetup_check.js
cp glow-ma/src/AdminRunner.gs /tmp/AdminRunner_check.js && node --check /tmp/AdminRunner_check.js && rm /tmp/AdminRunner_check.js
```

Expected: どちらも構文エラーなし

- [ ] **Step 5: `doGet`の一意性を再確認**

`grep -rn "^function doGet" glow-ma/src/*.gs` を実行し、`doGet`が`TrackingWebApp.gs`の1箇所にのみ
定義されていることを確認する(本Planでは`doGet`を変更していないはずだが、念のため再確認する)。

- [ ] **Step 6: 未実施の手動検証をレポートにまとめる**

Task 2・3・4の「手動検証(このサンドボックス環境では実行できない)」内容と、
`docs/glow-ma_本番投入手順書_統合版.md`の「紹介パートナー開拓状況ビュー セットアップ・動作確認
チェックリスト」の内容をまとめ、Google Apps Script実行環境で人間が確認すべき手順として
レポートに明記する。

- [ ] **Step 7: 最終Commit(必要な場合のみ)**

レビューで修正が発生した場合のみ、修正内容をコミットする。修正がなければこのステップは
スキップする。
