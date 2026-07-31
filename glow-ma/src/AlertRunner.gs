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
 * に定義されている種別)が入力された瞬間に即座にSlack通知する。
 *
 * 注意: この関数は「onEdit」という予約名を使っていない。もし onEdit という名前にすると
 * GASの**シンプルトリガー**として自動実行されてしまうが、シンプルトリガーは権限が制限された
 * 実行コンテキストで動作し、authorizationが必要なサービス(本関数が呼ぶ postToSlack_ 内の
 * UrlFetchApp.fetch を含む)を呼び出すと例外で失敗する。そのため、この関数自体は直接トリガー
 * されない普通の関数として定義し、下記の installInteractionLogEditTrigger を
 * Apps Scriptエディタから**人間が手動で一度だけ実行**して、認可済みの「インストール型トリガー」
 * として登録する必要がある(初回実行時に認可(オーソリ)を求めるダイアログが出るのは正常な挙動)。
 * installInteractionLogEditTrigger を複数回実行すると同じトリガーが重複登録されるため、
 * 再実行する場合はApps Scriptエディタの「トリガー」画面で既存登録の有無を確認してから行うこと。
 */
function handleInteractionLogEdit(e) {
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

/**
 * handleInteractionLogEdit をインストール型のonEditトリガーとして登録する。
 * Apps Scriptエディタから人間が手動で一度だけ実行すること(実行時に認可ダイアログが出る)。
 * 既に登録済みの状態で再実行すると、同じトリガーが重複登録されるので注意。
 * 事前に「トリガー」画面で既存登録の有無を確認してから実行することを推奨する。
 */
function installInteractionLogEditTrigger() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ScriptApp.newTrigger("handleInteractionLogEdit")
    .forSpreadsheet(ss)
    .onEdit()
    .create();
  Logger.log("即時アラート用のonEditトリガーを登録しました。");
}

function lookupCompanyName_(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) return companyId;
  var records = readCompanyRecords_(companySheet);
  var match = records.filter(function (r) { return r["企業ID"] === companyId; })[0];
  return match ? match["会社名"] : companyId;
}
