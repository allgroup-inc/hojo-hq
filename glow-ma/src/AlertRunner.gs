/**
 * GLOW企業リレーション台帳: 掘り起こしアラート(日次バッチ)
 *
 * 使い方:
 * 1. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で
 *    SLACK_WEBHOOK_URL を設定する(コードにWebhook URLを直接書かない)
 * 2. Apps Scriptエディタの「トリガー」画面で runDailyAlerts を時間主導トリガー
 *    (毎日 朝など)に手動登録する(トリガー登録自体は本ファイルでは行わない)
 *
 * 実行すると、企業マスタ全件から GlowAlerting.buildDailyAlertList で
 * 掘り起こし対象を抽出し、ランク・ネクストベストアクションとともにSlackへ通知する。
 */
function runDailyAlerts() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }

  var records = readCompanyRecords_(companySheet);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var alerts = GlowAlerting.buildDailyAlertList(records, todayString);

  if (alerts.length === 0) {
    Logger.log("本日の掘り起こし対象はありません。");
    return;
  }

  var lines = alerts.map(function (alert) {
    return "・" + alert["会社名"] + "(" + alert["ランク"] + "ランク) — " + alert["ネクストベストアクション"];
  });
  var message = "【本日の掘り起こし対象】" + alerts.length + "件\n" + lines.join("\n");
  postToSlack_(message);
  Logger.log("掘り起こしアラート送信完了: " + alerts.length + "件");
}

function postToSlack_(message) {
  var webhookUrl = PropertiesService.getScriptProperties().getProperty("SLACK_WEBHOOK_URL");
  if (!webhookUrl) {
    Logger.log("SLACK_WEBHOOK_URL が未設定のため通知をスキップしました: " + message);
    return;
  }
  UrlFetchApp.fetch(webhookUrl, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ text: message })
  });
}

/**
 * 即時アラート(Speed to Lead)
 * 対応履歴ログの「種別」列に、反応イベント(GlowScoring.DEFAULT_CONFIG.reactionPointsByType
 * に定義されている種別)が入力された瞬間に、シンプルトリガーとして自動実行され、
 * 即座にSlack通知する。関数名 onEdit はGASの予約された名前で、手動登録は不要。
 */
function onEdit(e) {
  if (!e || !e.range) return;
  var sheet = e.range.getSheet();
  if (sheet.getName() !== GlowSchema.INTERACTION_LOG_SHEET_NAME) return;
  if (e.range.getNumRows() !== 1 || e.range.getNumColumns() !== 1) return;

  var typeColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("種別") + 1;
  if (e.range.getColumn() !== typeColumnIndex) return;

  var row = e.range.getRow();
  if (row < 2) return;

  var newType = e.value;
  if (typeof GlowScoring.DEFAULT_CONFIG.reactionPointsByType[newType] !== "number") return;

  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var rowValues = sheet.getRange(row, 1, 1, headers.length).getValues()[0];
  var companyId = rowValues[headers.indexOf("企業ID")];

  var companyName = lookupCompanyName_(companyId);
  postToSlack_(
    "【即時アラート】" + companyName + "(" + companyId + ") が反応しました(" + newType + ")。至急対応してください。"
  );
}

function lookupCompanyName_(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) return companyId;
  var records = readCompanyRecords_(companySheet);
  var match = records.filter(function (r) { return r["企業ID"] === companyId; })[0];
  return match ? match["会社名"] : companyId;
}
