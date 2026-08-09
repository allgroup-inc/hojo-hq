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
 * getCompanyList・getCompanyDetail など公開される関数それぞれの冒頭でも
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

/**
 * 企業一覧(絞り込み・並び替え済み、最小フィールドのみ)を返す。
 * google.script.run 経由で adminApp.js の画面から呼ばれる。
 *
 * 以下3関数(getCompanyList・getCompanyDetail・getFilterOptions)は名前の末尾に
 * `_` を付けてはいけない。Apps Scriptは末尾が`_`の関数を非公開扱いにし、
 * google.script.run から呼び出せなくする(呼んでもエラーにすらならず、単に
 * 何も起きない)。アクセス制御は関数名ではなく、各関数の冒頭で呼んでいる
 * requireAdminAccess_() だけが担う(最終レビュー2026-08-09 Fix 1)。
 */
function getCompanyList(filters) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  return GlowAdminAccess.buildCompanyListResult(companies, filters || {});
}

/**
 * 企業1社分の全項目(機微情報を含む)と、対応履歴ログ(日付降順)を返す。
 * 該当企業が見つからない場合はnullを返す。
 */
function getCompanyDetail(companyId) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var company = companies.filter(function (c) { return c["企業ID"] === companyId; })[0];
  if (!company) return null;

  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var interactionsByCompany = logSheet ? readInteractionsByCompanyId_(logSheet) : {};
  var history = GlowAdminAccess.sortInteractionsByDateDesc(interactionsByCompany[companyId] || []);

  return { company: company, history: history };
}

/**
 * 一覧画面の「現在ステージ」「担当者」フィルタの選択肢を、企業マスタに実在する
 * 値から重複なく作る(ランクはA/B/C/Dで固定のため画面側にハードコードする)。
 */
function getFilterOptions() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];

  var stageSet = {};
  var ownerSet = {};
  companies.forEach(function (company) {
    if (company["現在ステージ"]) stageSet[company["現在ステージ"]] = true;
    if (company["担当者"]) ownerSet[company["担当者"]] = true;
  });

  return {
    stages: Object.keys(stageSet).sort(),
    owners: Object.keys(ownerSet).sort()
  };
}
