/**
 * GLOW企業リレーション台帳: 管理画面Web App(Phase 18a: 企業一覧・詳細の閲覧)
 *
 * 既存の TrackingWebApp.gs の doGet に ?page=admin での分岐が追加されており、
 * この分岐先が本ファイルの renderAdminPage_ を呼ぶ。実処理はすべてこのファイルに
 * 委譲し、doGet 自体はルーティングのみを行う(三名体制レビュー2026-08-09裁定3)。
 *
 * セットアップ(人間が一度だけ行う):
 * 1. 「スタッフ」タブに、管理画面へのアクセスを許可する人の「氏名」「メールアドレス」を
 *    入力し、「有効」列にチェックを入れる(Slack User IDは対面連携機能専用で、
 *    本機能の利用には不要)
 * 2. `clasp push` で最新コードを反映する
 * 3. Apps Scriptエディタの「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」で、
 *    トラッキング用(Phase 4)とは別に新規デプロイを作成する。実行ユーザー: 自分。
 *    アクセスできるユーザー: 「Googleアカウントを持つ全員」
 * 4. デプロイ後に発行されるURLの末尾に `?page=admin` を付けたものを、
 *    「スタッフ」タブに登録した人へ共有する
 *
 * 認証は Session.getActiveUser().getEmail()(実際のアクセス者のメールアドレス)を
 * 「スタッフ」タブの登録メールアドレスと照合する方式。個人Gmail運用(Workspace
 * ドメインなし)のため、Web Appのアクセス設定(「Googleアカウントを持つ全員」)だけでは
 * 利用者を限定できず、この許可リスト照合が唯一の防御線になる。そのため
 * getCompanyList_・getCompanyDetail_ など公開される関数それぞれの冒頭でも
 * requireAdminAccess_ を呼ぶ(doGetでの一度きりのチェックに依存しない多層防御。
 * 三名体制レビュー2026-08-09裁定1・2)。
 */
function isAdminUser_() {
  var email = Session.getActiveUser().getEmail();
  var staffRows = readStaffAllowlistEmails_();
  return GlowAdminAccess.isAllowedEmail(email, staffRows);
}

function requireAdminAccess_() {
  if (!isAdminUser_()) {
    throw new Error("この操作を行う権限がありません。");
  }
}

function readStaffAllowlistEmails_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var emailIndex = headers.indexOf("メールアドレス");
  var activeIndex = headers.indexOf("有効");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[emailIndex]; })
    .map(function (row) { return { email: row[emailIndex] }; });
}

function renderAdminPage_() {
  if (!isAdminUser_()) {
    return HtmlService.createHtmlOutput(GlowAdminAccess.buildAccessDeniedHtml());
  }
  return HtmlService.createHtmlOutput(GlowAdminApp.buildAdminAppHtml())
    .setTitle("GLOW企業リレーション台帳");
}
