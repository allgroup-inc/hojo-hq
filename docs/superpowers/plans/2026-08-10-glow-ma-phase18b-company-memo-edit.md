# glow-ma Phase 18b: 関係メモ編集機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GLOW企業リレーション台帳の管理画面Web Appで、企業詳細ドロワーの「関係メモ」欄を閲覧するだけでなく、その場で編集・保存できるようにする。

**Architecture:** 既存のPhase 18a/紹介パートナー開拓状況ビューと同じGAS単一プロジェクト構成をそのまま踏襲する。新しい`google.script.run`呼び出し`updateCompanyMemo(companyId, memo)`を`AdminRunner.gs`に追加し、保存前に更新前の内容を「対応履歴ログ」へ自動記録してから企業マスタの「関係メモ」列を上書きする。クライアント側(`adminApp.js`)は既存のドロワー内に編集ボタン・テキストエリア・保存/キャンセルボタンを追加し、状態はトグル表示(DOM再生成なし)で管理する。

**Tech Stack:** Google Apps Script (GAS) + Google Sheets、`HtmlService`、`google.script.run`。テストはNode.js標準の`node --test`(GAS依存部分はNode単体テスト対象外、既存パターンを踏襲)。

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-08-10-glow-ma-phase18b-company-memo-edit-design.md`(以下「設計書」)の内容に従う
- 関数名の末尾に`_`を付けてはいけない箇所: `google.script.run`から呼ばれる`updateCompanyMemo`(Apps Scriptは末尾`_`の関数を非公開扱いにし、呼び出しても無反応になる。Phase 18a最終レビューで発見)
- `updateCompanyMemo`の冒頭で必ず`requireAdminAccess_()`を呼ぶ(多層防御。他の全公開関数と同じパターン)
- 保存失敗時にクライアント側で誤って「保存しました」と表示してはいけない(`.withSuccessHandler`/`.withFailureHandler`を正しく分ける)
- 対応履歴ログへの記録(更新前の内容)が失敗したら、企業マスタの「関係メモ」列は上書きしない(設計書3章・4章)
- `COMPANY_MASTER_HEADERS`・`INTERACTION_LOG_HEADERS`の列順は変更しない(既存データ破損防止。末尾追加のみ許可されるが、今回は列追加ではなく`INTERACTION_TYPES`という値リストへの追加のみ)
- テストは`node --test tests/glow_ma_*.test.mjs`で実行し、既存237件を含めすべてPASSする状態を保つ

---

### Task 1: schema.js に「関係メモ更新」種別を追加

**Files:**
- Modify: `glow-ma/src/schema.js:25-31`(`INTERACTION_TYPES`配列)
- Modify: `tests/glow_ma_schema.test.mjs:57-66`(既存テストの期待値配列を更新)

**Interfaces:**
- Produces: `GlowSchema.INTERACTION_TYPES`に文字列`"関係メモ更新"`が含まれる(Task 3の`appendMemoUpdateInteractionLog_`が対応履歴ログの「種別」列に書き込む値として使う)

- [ ] **Step 1: 既存テストを新しい期待値に書き換える(先にテストを失敗させる)**

`tests/glow_ma_schema.test.mjs`の`対応履歴ログの種別(INTERACTION_TYPES)が...`テスト(57〜66行目)を以下に置き換える:

```javascript
test("対応履歴ログの種別(INTERACTION_TYPES)が設計書5.2節の15種+連絡不要受領+工程遷移イベント+入電+関係メモ更新と一致する", () => {
  const expected = [
    "手紙送付", "電話", "入電", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領",
    "NDA締結", "意向表明受領", "DD開始", "関係メモ更新"
  ];
  assert.deepEqual(schema.INTERACTION_TYPES, expected);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`関係メモ更新`が実際の配列に含まれていないため`assert.deepEqual`が失敗する)

- [ ] **Step 3: schema.jsのINTERACTION_TYPESに追加する**

`glow-ma/src/schema.js`の`INTERACTION_TYPES`配列(25〜31行目)の末尾に`"関係メモ更新"`を追加する:

```javascript
  var INTERACTION_TYPES = [
    "手紙送付", "電話", "入電", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領",
    "NDA締結", "意向表明受領", "DD開始", "関係メモ更新"
  ];
```

- [ ] **Step 4: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 対応履歴ログの種別に「関係メモ更新」を追加"
```

---

### Task 2: adminAccess.js に resolveStaffName を追加

**Files:**
- Modify: `glow-ma/src/adminAccess.js`(既存の`normalizeEmail_`関数の近くに追加、`api`オブジェクトへのエクスポートも追加)
- Modify: `tests/glow_ma_adminAccess.test.mjs`(新規テスト追加)

**Interfaces:**
- Consumes: なし(純粋関数)
- Produces: `GlowAdminAccess.resolveStaffName(email, staffRows)` — `staffRows`は`[{ email: string, name: string }, ...]`形式の配列。一致する`email`(大文字小文字・前後空白を無視して比較。既存の`normalizeEmail_`を再利用)があれば対応する`name`を返す。一致しない、または一致した行の`name`が空の場合は文字列`"不明"`を返す。Task 3の`appendMemoUpdateInteractionLog_`が対応履歴ログの「担当者」列に書き込む値を得るために使う

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminAccess.test.mjs`の`buildAccessDeniedHtml`のテストの直後に追加する:

```javascript
test("resolveStaffName: メールアドレスが一致すればスタッフの氏名を返す", () => {
  const staffRows = [
    { email: "koyanagi@example.com", name: "小柳" },
    { email: "fukuda@example.com", name: "福田" }
  ];
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", staffRows), "小柳");
});

test("resolveStaffName: 大文字小文字・前後空白の違いを無視して一致判定する", () => {
  const staffRows = [{ email: " Koyanagi@Example.com ", name: "小柳" }];
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", staffRows), "小柳");
});

test("resolveStaffName: 一致しなければ「不明」を返す", () => {
  const staffRows = [{ email: "koyanagi@example.com", name: "小柳" }];
  assert.equal(adminAccess.resolveStaffName("other@example.com", staffRows), "不明");
});

test("resolveStaffName: スタッフ一覧が空でも「不明」を返す(例外を投げない)", () => {
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", []), "不明");
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", undefined), "不明");
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: FAIL(`adminAccess.resolveStaffName is not a function`)

- [ ] **Step 3: adminAccess.jsに実装を追加する**

`glow-ma/src/adminAccess.js`の`buildAccessDeniedHtml`関数の直後(58行目の`}`の後)に追加する:

```javascript
  function resolveStaffName(email, staffRows) {
    var target = normalizeEmail_(email);
    var match = (staffRows || []).filter(function (staff) {
      return normalizeEmail_(staff.email) === target;
    })[0];
    return match && match.name ? match.name : "不明";
  }
```

`api`オブジェクト(161〜173行目)に`resolveStaffName: resolveStaffName,`を追加する:

```javascript
  var api = {
    isAllowedEmail: isAllowedEmail,
    buildAccessDeniedHtml: buildAccessDeniedHtml,
    resolveStaffName: resolveStaffName,
    COMPANY_LIST_FIELDS: COMPANY_LIST_FIELDS,
    DEFAULT_LIST_LIMIT: DEFAULT_LIST_LIMIT,
    hasAnyFilter: hasAnyFilter,
    applyCompanyFilters: applyCompanyFilters,
    buildCompanyListResult: buildCompanyListResult,
    sortInteractionsByDateDesc: sortInteractionsByDateDesc,
    normalizeDateForDisplay: normalizeDateForDisplay,
    buildPartnerListRows: buildPartnerListRows,
    normalizeReferralRecords: normalizeReferralRecords
  };
```

- [ ] **Step 4: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): メールアドレスからスタッフ氏名を解決するresolveStaffNameを追加"
```

---

### Task 3: AdminRunner.gs に updateCompanyMemo を追加

**Files:**
- Modify: `glow-ma/src/AdminRunner.gs`(`readStaffAllowlistEmails_`を拡張、新規関数3つを末尾に追加)

**Interfaces:**
- Consumes: `GlowAdminAccess.resolveStaffName(email, staffRows)`(Task 2)、`GlowSchema.COMPANY_MASTER_HEADERS`・`GlowSchema.INTERACTION_LOG_HEADERS`・`GlowSchema.INTERACTION_LOG_SHEET_NAME`(既存)
- Produces: `google.script.run`から呼び出し可能な`updateCompanyMemo(companyId, memo)`。成功時は戻り値なし(`undefined`)。企業が見つからない場合・対応履歴ログタブが無い場合・ロック取得に失敗した場合は`Error`を投げる(クライアント側は`.withFailureHandler`で受け取る、Task 6で実装)

このタスクはGAS専用(`SpreadsheetApp`・`Session`・`LockService`・`Utilities`に依存)のため、Node単体テストの対象外(`getCompanyDetail`等の既存関数と同じ扱い。設計書7章)。**このタスクの完了確認は既存Nodeテストがすべて通ること(コードに構文ミスがないこと)とコードレビューで行う。**

- [ ] **Step 1: readStaffAllowlistEmails_を拡張して氏名も返すようにする**

`glow-ma/src/AdminRunner.gs`の`readStaffAllowlistEmails_`関数(39〜52行目)を以下に置き換える(`nameIndex`の取得と`map`の返り値に`name`を追加):

```javascript
function readStaffAllowlistEmails_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var emailIndex = headers.indexOf("メールアドレス");
  var activeIndex = headers.indexOf("有効");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[emailIndex]; })
    .map(function (row) { return { email: row[emailIndex], name: row[nameIndex] }; });
}
```

(既存の呼び出し元`isAdminUser_`は戻り値の`.email`だけを使う`GlowAdminAccess.isAllowedEmail`に渡しているため、`name`フィールドが増えても影響しない)

- [ ] **Step 2: 企業マスタの行番号を探すヘルパーを追加する**

`glow-ma/src/AdminRunner.gs`の末尾(`getPartnerDetail`関数の後)に追加する:

```javascript
/**
 * 企業マスタの中から「企業ID」が一致する行の行番号(1始まり、ヘッダー行込み)を返す。
 * 見つからなければ-1を返す。updateCompanyMemoが書き込み先の行を特定するために使う。
 */
function findCompanyRowIndex_(sheet, companyId) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return -1;
  var idColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("企業ID") + 1;
  var ids = sheet.getRange(2, idColumnIndex, lastRow - 1, 1).getValues();
  for (var i = 0; i < ids.length; i++) {
    if (ids[i][0] === companyId) return i + 2;
  }
  return -1;
}
```

- [ ] **Step 3: 対応履歴ログへの自動記録関数を追加する**

`findCompanyRowIndex_`の直後に追加する(`LetterRunner.gs`の`appendNurturingInteractionLog_`と同じロックパターンを踏襲):

```javascript
/**
 * 関係メモが上書きされる直前に、更新前の内容を対応履歴ログへ1行自動記録する
 * (設計書4章。専用の変更履歴テーブルを作らず、既存の対応履歴ログの仕組みで
 * 「上書きされる前の情報」を追跡可能にする)。
 * この記録が失敗した場合は例外を投げ、呼び出し元(updateCompanyMemo)で
 * 関係メモの上書き自体を行わせない。
 */
function appendMemoUpdateInteractionLog_(companyId, oldMemo) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) {
    throw new Error("対応履歴ログタブが見つかりません。");
  }
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("他の処理が対応履歴ログを操作中のため、保存を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    var nextRow = logSheet.getLastRow() + 1;
    var logId = "H-" + Utilities.getUuid();
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
    var staffRows = readStaffAllowlistEmails_();
    var staffName = GlowAdminAccess.resolveStaffName(Session.getActiveUser().getEmail(), staffRows);
    var oldMemoText = oldMemo ? String(oldMemo) : "(更新前は未記入)";
    logSheet.getRange(nextRow, 1, 1, GlowSchema.INTERACTION_LOG_HEADERS.length).setValues([[
      logId, companyId, todayString, staffName, "関係メモ更新", "未接触",
      "関係メモを更新しました(更新前の内容: " + oldMemoText + ")", ""
    ]]);
  } finally {
    lock.releaseLock();
  }
}
```

- [ ] **Step 4: updateCompanyMemo本体を追加する**

`appendMemoUpdateInteractionLog_`の直後に追加する:

```javascript
/**
 * 企業詳細ドロワーから呼ばれる、関係メモの更新関数。
 *
 * この関数の名前の末尾に `_` を付けてはいけない(getCompanyList等と同じ理由。
 * Apps Scriptは末尾が`_`の関数を非公開扱いにし、google.script.runから呼び出せなくする)。
 *
 * 対応履歴ログへの記録(appendMemoUpdateInteractionLog_)が完了してから
 * 関係メモを上書きする順序を守ること(設計書3章。記録なき上書きを避けるため)。
 */
function updateCompanyMemo(companyId, memo) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。");
  }
  var rowIndex = findCompanyRowIndex_(companySheet, companyId);
  if (rowIndex === -1) {
    throw new Error("該当する企業が見つかりません: " + companyId);
  }
  var memoColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("関係メモ") + 1;
  var oldMemo = companySheet.getRange(rowIndex, memoColumnIndex).getValue();

  appendMemoUpdateInteractionLog_(companyId, oldMemo);

  companySheet.getRange(rowIndex, memoColumnIndex).setValue(memo);
}
```

- [ ] **Step 5: 全Node テストを実行し、既存テストが壊れていないことを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全テスト。AdminRunner.gsはNode側でrequireされないため、この実行はTask 1・2で追加した分も含めた既存テスト全体の回帰確認のみ)

- [ ] **Step 6: コミット**

```bash
git add glow-ma/src/AdminRunner.gs
git commit -m "feat(glow-ma): 関係メモ更新のサーバー関数updateCompanyMemoを追加"
```

---

### Task 4: adminApp.js に関係メモ編集UIのスタイル・マークアップを追加

**Files:**
- Modify: `glow-ma/src/adminApp.js`(`STYLE`変数・`DRAWER`関連の`renderDrawer`が生成するHTML)
- Modify: `tests/glow_ma_adminApp.test.mjs`(新規テスト追加)

**Interfaces:**
- Consumes: なし(このタスクはマークアップとスタイルのみ。イベントハンドラの実装はTask 5)
- Produces: `renderDrawer`が生成するHTML内に、`id="memoEditBtn"`・`id="memoValue"`・`id="memoTextarea"`・`id="memoEditControls"`・`id="memoSaveBtn"`・`id="memoCancelBtn"`・`id="memoStatus"`を持つ要素が含まれる(Task 5がこれらの要素にイベントリスナーを付ける)

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminApp.test.mjs`の`書き込み系のgoogle.script.run呼び出しを一切含まない(読み取り専用の担保)`テスト(30〜35行目)を以下に置き換える(Phase 18bで関係メモ編集という書き込みが入るため、担保する境界が変わる):

```javascript
test("buildAdminAppHtml: google.script.runでupdateCompanyMemoを呼ぶ(Phase 18b: 関係メモ編集)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".updateCompanyMemo(") !== -1);
});

test("buildAdminAppHtml: 関係メモ編集以外の書き込み系google.script.run呼び出しを含まない(Phase 18b範囲の担保)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["shareCompanyWithStaff", "appendInteractionLog", "addPartner", "logPartnerInteraction", "recordReferral"].forEach((forbidden) => {
    assert.equal(html.indexOf(forbidden), -1, forbidden + " への呼び出しが含まれてはいけない(Phase 18b範囲外の機能)");
  });
});

test("buildAdminAppHtml: 企業詳細ドロワーに関係メモ編集用の要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["memoEditBtn", "memoValue", "memoTextarea", "memoEditControls", "memoSaveBtn", "memoCancelBtn", "memoStatus"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL(`.updateCompanyMemo(`と`memoEditBtn`等のidがまだ存在しない)

- [ ] **Step 3: STYLEに関係メモ編集用のスタイルを追加する**

`glow-ma/src/adminApp.js`の`STYLE`配列(13〜54行目)の末尾要素`".viewPane.active{display:block}"`の後にカンマ区切りで追加する:

```javascript
    ".viewPane.active{display:block}",
    ".field .label{display:flex;align-items:center;justify-content:space-between;gap:0.5rem}",
    ".btn-small{padding:0.25rem 0.6rem;border:1px solid #d8dee1;border-radius:0.3rem;",
    "background:#fff;cursor:pointer;font:inherit;font-size:0.76rem;text-transform:none;letter-spacing:normal}",
    ".btn-small:disabled{opacity:0.5;cursor:default}",
    ".btn-primary{background:#00335c;color:#fff;border-color:#00335c}",
    "#memoTextarea{width:100%;min-height:6rem;font:inherit;font-size:0.92rem;padding:0.5rem;",
    "border:1px solid #d8dee1;border-radius:0.35rem;box-sizing:border-box;margin-top:0.3rem}",
    "#memoEditControls{margin-top:0.4rem;display:flex;align-items:center;gap:0.5rem}",
    "#memoStatus{font-size:0.78rem;color:#4a5a66}",
    "#memoStatus.error{color:#b3261e}"
```

(注: `.field .label`はすでにパートナードロワー等でも共用されているクラスのため、`display:flex`化しても既存の見た目に大きな影響はない想定。もし他のラベル表示が崩れる場合は、`.label`に汎用の`flex`を当てず`#memoField .label`のような限定セレクタに変更すること)

- [ ] **Step 4: renderDrawer内のfields配列から「関係メモ」を除外し、専用のメモブロックを追加する**

`glow-ma/src/adminApp.js`の`SCRIPT`配列内、`renderDrawer`関数(170〜194行目)を以下に置き換える:

```javascript
    "function renderDrawer(detail){",
    "if (!detail){ document.getElementById('drawerCompanyName').textContent = '該当する企業が見つかりません';",
    "document.getElementById('paneOverview').innerHTML = ''; document.getElementById('paneHistory').innerHTML = ''; return; }",
    "var c = detail.company;",
    "document.getElementById('drawerCompanyName').textContent = c['会社名'] || '(社名未登録)';",
    "document.getElementById('drawerCompanyId').textContent = c['企業ID'];",
    "var fields = [",
    "['業種', c['業種']], ['代表者名', c['代表者名']], ['所在地', c['所在地']],",
    "['電話番号', c['電話番号']], ['窓口担当者名', c['窓口担当者名']], ['携帯番号', c['携帯番号']],",
    "['ランク', c['ランク']], ['初期スコア', c['初期スコア']], ['反応スコア', c['反応スコア']],",
    "['総合スコア', c['総合スコア']], ['現在ステージ', c['現在ステージ']],",
    "['後継者状況', c['後継者状況']]",
    "];",
    "document.getElementById('paneOverview').innerHTML = fields.map(function(f){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(f[0]) + '</div>' +",
    "'<div class=\"value\">' + (escapeHtml(f[1]) || '—') + '</div></div>';",
    "}).join('') + renderMemoField(c['関係メモ']);",
    "attachMemoHandlers(c['企業ID'], c['関係メモ']);",
    "var history = detail.history || [];",
    "document.getElementById('paneHistory').innerHTML = history.length === 0",
    "? '<div class=\"empty\">対応履歴がありません</div>'",
    ": history.map(function(h){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(h['日付']) + '・' + escapeHtml(h['種別']) + '</div>' +",
    "'<div class=\"value\">' + escapeHtml(h['内容メモ']) + '</div></div>';",
    "}).join('');",
    "}",

    "function renderMemoField(memoValue){",
    "return '<div class=\"field\" id=\"memoField\"><div class=\"label\">関係メモ' +",
    "'<button class=\"btn-small\" id=\"memoEditBtn\" type=\"button\">編集</button></div>' +",
    "'<div class=\"value\" id=\"memoValue\">' + (escapeHtml(memoValue) || '—') + '</div>' +",
    "'<textarea id=\"memoTextarea\" style=\"display:none\"></textarea>' +",
    "'<div id=\"memoEditControls\" style=\"display:none\">' +",
    "'<button class=\"btn-small btn-primary\" id=\"memoSaveBtn\" type=\"button\">保存</button>' +",
    "'<button class=\"btn-small\" id=\"memoCancelBtn\" type=\"button\">キャンセル</button>' +",
    "'<span id=\"memoStatus\"></span></div></div>';",
    "}",

    "function attachMemoHandlers(companyId, originalMemo){}"
```

- [ ] **Step 5: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: PASS(全テスト。ただし`.updateCompanyMemo(`を呼ぶテストはまだ失敗する可能性がある — Task 5でsaveMemo内に呼び出しを実装するまでは失敗のままでよい。このステップでは`memoEditBtn`等の要素IDの存在テストがPASSすることを確認する)

- [ ] **Step 6: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): 企業詳細ドロワーに関係メモ編集用のマークアップ・スタイルを追加"
```

---

### Task 5: adminApp.js に関係メモ編集の状態管理・保存処理・離脱確認を実装

**Files:**
- Modify: `glow-ma/src/adminApp.js`(`SCRIPT`配列: 状態変数・`attachMemoHandlers`の正式実装・`startMemoEdit`/`cancelMemoEdit`/`saveMemo`の追加・`closeDrawer`の変更)
- Modify: `tests/glow_ma_adminApp.test.mjs`(新規テスト追加)

**Interfaces:**
- Consumes: Task 4で追加したマークアップの要素ID(`memoEditBtn`等)、GAS側の`updateCompanyMemo(companyId, memo)`(Task 3)
- Produces: なし(最終タスク。UIの完成)

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminApp.test.mjs`に追加する:

```javascript
test("buildAdminAppHtml: 関係メモの保存に成功/失敗した場合の表示分岐を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("保存しました") !== -1, "保存成功時のメッセージがない");
  assert.ok(html.indexOf("保存に失敗しました") !== -1, "保存失敗時のメッセージがない");
});

test("buildAdminAppHtml: 未保存の変更がある状態でドロワーを閉じようとすると確認する", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("confirm(") !== -1, "confirm()による離脱確認がない");
  assert.ok(html.indexOf("保存されていない変更があります") !== -1, "離脱確認のメッセージがない");
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL(`保存に失敗しました`・`confirm(`等がまだ存在しない)

- [ ] **Step 3: 状態変数を追加する**

`glow-ma/src/adminApp.js`の`SCRIPT`配列の先頭、`"var currentFilters = ..."`の直後に追加する:

```javascript
    "var memoEditing = false;",
    "var memoCompanyId = null;",
    "var memoOriginalValue = '';",
```

- [ ] **Step 4: attachMemoHandlers・startMemoEdit・cancelMemoEdit・saveMemoを実装する**

Task 4のStep 4で追加した仮の`"function attachMemoHandlers(companyId, originalMemo){}"`を、以下の4関数に置き換える:

```javascript
    "function attachMemoHandlers(companyId, originalMemo){",
    "memoEditing = false; memoCompanyId = companyId; memoOriginalValue = originalMemo || '';",
    "document.getElementById('memoEditBtn').addEventListener('click', startMemoEdit);",
    "document.getElementById('memoSaveBtn').addEventListener('click', saveMemo);",
    "document.getElementById('memoCancelBtn').addEventListener('click', cancelMemoEdit);",
    "}",

    "function startMemoEdit(){",
    "memoEditing = true;",
    "document.getElementById('memoValue').style.display = 'none';",
    "var ta = document.getElementById('memoTextarea');",
    "ta.value = memoOriginalValue; ta.style.display = 'block';",
    "document.getElementById('memoEditControls').style.display = 'flex';",
    "document.getElementById('memoStatus').className = ''; document.getElementById('memoStatus').textContent = '';",
    "}",

    "function cancelMemoEdit(){",
    "memoEditing = false;",
    "document.getElementById('memoTextarea').style.display = 'none';",
    "document.getElementById('memoEditControls').style.display = 'none';",
    "document.getElementById('memoValue').style.display = 'block';",
    "document.getElementById('memoStatus').className = ''; document.getElementById('memoStatus').textContent = '';",
    "}",

    "function saveMemo(){",
    "var newValue = document.getElementById('memoTextarea').value;",
    "document.getElementById('memoSaveBtn').disabled = true;",
    "document.getElementById('memoCancelBtn').disabled = true;",
    "document.getElementById('memoStatus').className = '';",
    "document.getElementById('memoStatus').textContent = '保存中...';",
    "google.script.run.withSuccessHandler(function(){",
    "memoOriginalValue = newValue; memoEditing = false;",
    "document.getElementById('memoValue').textContent = newValue || '—';",
    "document.getElementById('memoTextarea').style.display = 'none';",
    "document.getElementById('memoEditControls').style.display = 'none';",
    "document.getElementById('memoValue').style.display = 'block';",
    "document.getElementById('memoSaveBtn').disabled = false;",
    "document.getElementById('memoCancelBtn').disabled = false;",
    "document.getElementById('memoStatus').textContent = '保存しました';",
    "}).withFailureHandler(function(){",
    "document.getElementById('memoSaveBtn').disabled = false;",
    "document.getElementById('memoCancelBtn').disabled = false;",
    "document.getElementById('memoStatus').className = 'error';",
    "document.getElementById('memoStatus').textContent = '保存に失敗しました。もう一度お試しください。';",
    "}).updateCompanyMemo(memoCompanyId, newValue);",
    "}",
```

- [ ] **Step 5: closeDrawerに離脱確認を追加する**

`SCRIPT`配列内の`closeDrawer`関数(196〜199行目)を以下に置き換える:

```javascript
    "function closeDrawer(){",
    "if (memoEditing && !confirm('保存されていない変更があります。破棄しますか?')) { return; }",
    "memoEditing = false;",
    "document.getElementById('drawer').classList.remove('open');",
    "document.getElementById('overlay').classList.remove('open');",
    "}",
```

- [ ] **Step 6: テストを実行してPASSすることを確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: PASS(全テスト。Task 4で追加した`.updateCompanyMemo(`呼び出しのテストもこの時点でPASSする)

- [ ] **Step 7: 全体のNodeテストを実行し、237件+今回追加分すべてPASSすることを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全テスト)

- [ ] **Step 8: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): 関係メモ編集の保存処理・離脱確認を実装(Phase 18b完成)"
```

---

### Task 6: ドキュメント更新

**Files:**
- Modify: `glow-ma/README.md`(「次のフェーズ」section・新規機能の使い方セクション)
- Modify: `docs/glow-ma_本番投入手順書_統合版.md`(本番投入前チェックリストへの追加)

**Interfaces:**
- Consumes: なし
- Produces: なし(ドキュメントのみ)

- [ ] **Step 1: README.mdの「次のフェーズ」セクションを更新する**

`glow-ma/README.md`の555〜562行目付近、「次のフェーズ」セクションを以下に置き換える:

```markdown
## 次のフェーズ

Phase 1〜16、Phase 18a(管理画面Web App: 企業一覧・詳細の閲覧)、紹介パートナー開拓状況ビュー
(読み取り専用)、Phase 18b(関係メモ編集)が完了しました。企業詳細ドロワーの「関係メモ」欄を
管理画面から直接編集・保存でき、更新前の内容は対応履歴ログに自動で残ります
(`docs/superpowers/specs/2026-08-10-glow-ma-phase18b-company-memo-edit-design.md`参照)。

対応履歴ログ入力(Phase 18b-2、仮称)・スタッフ共有(Slack DM)・手紙URLモーダル・KPIカードは
それぞれ後続フェーズとして計画中(区切り・順序は暫定案。
`docs/superpowers/specs/2026-08-09-glow-ma-admin-webapp-phase18a-design.md`参照)。
今後の改善点は各セクションの「現時点の制約」、および「本番投入前チェックリスト」を参照。
```

- [ ] **Step 2: README.mdに関係メモ編集の使い方セクションを追加する**

「次のフェーズ」セクションの直前に、以下のセクションを新設する:

```markdown
## 関係メモ編集(Phase 18b)

企業詳細ドロワーの「関係メモ」欄の「編集」ボタンから、内容を書き換えて「保存」できます。

- 保存すると、更新前の内容が対応履歴ログに「関係メモ更新」種別の行として自動で記録されます
  (誰が更新したかは、アクセスした人のGoogleアカウントのメールアドレスを「スタッフ」タブの
  氏名と突き合わせて記録されます。突き合わせできない場合は「不明」と記録されます)
- 保存に失敗した場合は「保存に失敗しました」と表示され、入力内容は消えません。もう一度
  「保存」を押してください
- 未保存の変更がある状態でドロワーを閉じようとすると、破棄してよいか確認されます
- 同時に複数人が同じ企業の関係メモを編集した場合、後から保存した内容が反映されます
  (先着順ではなく後勝ち)。過去の内容は対応履歴ログから確認できます
```

- [ ] **Step 3: 本番投入前チェックリストに確認項目を追加する**

`docs/glow-ma_本番投入手順書_統合版.md`の「紹介パートナー開拓状況ビュー セットアップ・動作確認チェックリスト」セクションの直後に、以下のセクションを新設する:

```markdown
### 関係メモ編集(Phase 18b) セットアップ・動作確認チェックリスト

- [ ] 企業詳細ドロワーの関係メモ欄で「編集」→内容を書き換えて「保存」し、「保存しました」と
      表示されることを確認する
- [ ] 保存後、対応履歴ログタブに「関係メモ更新」種別の行が自動で追加され、担当者欄に自分の
      氏名(「スタッフ」タブに登録した氏名)が入っていることを確認する
- [ ] 関係メモ欄の内容が保存後の値に更新されて表示されることを確認する
- [ ] 「編集」→内容を書き換えて「キャンセル」を押すと、変更前の内容に戻ることを確認する
- [ ] 「編集」→内容を書き換えた状態でドロワーを閉じようとすると、「保存されていない変更が
      あります。破棄しますか?」の確認が出ることを確認する
- [ ] (可能であれば)存在しない企業IDに対して`updateCompanyMemo`を実行するなど、意図的に
      保存を失敗させた場合に「保存に失敗しました」と表示され、対応履歴ログ・関係メモの
      どちらも変更されていないことを確認する
```

- [ ] **Step 4: コミット**

```bash
git add glow-ma/README.md docs/glow-ma_本番投入手順書_統合版.md
git commit -m "docs(glow-ma): Phase 18b(関係メモ編集)のREADME・本番投入手順書を更新"
```

---

## 最終確認(全タスク完了後)

- [ ] `node --test tests/glow_ma_*.test.mjs` を実行し、既存237件+今回追加分すべてPASSすることを確認する
- [ ] `AdminRunner.gs`・`adminApp.js`の変更をひと通り読み返し、`updateCompanyMemo`が`_`で終わっていないこと、`requireAdminAccess_()`が冒頭にあることを再確認する(GASの落とし穴・多層防御の担保)
