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
