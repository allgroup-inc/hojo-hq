/**
 * GLOW企業リレーション台帳: 掘り起こしアラート(日次バッチ)
 *
 * 使い方:
 * 1. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で
 *    SLACK_WEBHOOK_URL を設定する(コードにWebhook URLを直接書かない)
 * 2. Apps Scriptエディタの「トリガー」画面で runDailyAlerts を時間主導トリガー
 *    (毎日 朝など)に手動登録する(トリガー登録自体は本ファイルでは行わない)。
 *    このとき「エラー通知設定」を必ず「毎回通知」にする(README「耐障害性」章を参照)。
 * 3. 即時アラート(Speed to Lead)を有効にするため、Apps Scriptエディタで
 *    installInteractionLogEditTrigger を実行する(冪等なので安全に再実行できる)
 *
 * 実行すると、企業マスタ全件から GlowAlerting.buildDailyAlertList で
 * 掘り起こし対象を抽出し、ランク・ネクストベストアクションとともにSlackへ通知する。
 *
 * 耐障害性(2026-08-07 resilient-agent-design + glow-ma-triangle-review確定):
 * - べき等性: 同じ日に二重実行されても、Slackへの二重送信を防ぐ(Script Propertiesに
 *   送信完了日を記録し、当日分が完了済みならスキップする)。正当な再送(Slack障害からの
 *   復旧後の再送信等)が必要な場合は forceResendDailyAlerts を実行すること。
 * - リトライ: Slack送信が一時的に失敗した場合(429/5xx/ネットワーク例外)は最大3回、
 *   2秒→10秒のバックオフで再試行する。認証エラー等の恒久的な失敗は再試行しない。
 * - 可視化: 最終送信日・最終エラーをScript Propertiesに残す。全リトライが尽きた場合は
 *   例外をthrowし、GASのトリガー失敗通知(オーナーへのメール)を発火させる。
 */
var MAX_ALERT_LINES = 50;
var SCRIPT_PROP_LAST_ALERT_SENT_DATE = "LAST_DAILY_ALERT_SENT_DATE";
var SCRIPT_PROP_LAST_ALERT_ERROR = "LAST_DAILY_ALERT_ERROR";
var SCRIPT_PROP_LAST_ALERT_ERROR_AT = "LAST_DAILY_ALERT_ERROR_AT";

function runDailyAlerts() {
  runDailyAlerts_(false);
}

/**
 * runDailyAlerts のべき等性ガードを無視して強制的に再送する。
 * Slack障害からの復旧後など、本日分をもう一度送り直したい場合に
 * Apps Scriptエディタから手動で実行する。
 */
function forceResendDailyAlerts() {
  runDailyAlerts_(true);
}

function runDailyAlerts_(forceResend) {
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var scriptProperties = PropertiesService.getScriptProperties();

  if (!forceResend) {
    var lastSentDate = scriptProperties.getProperty(SCRIPT_PROP_LAST_ALERT_SENT_DATE);
    if (GlowResilience.isAlreadyCompletedToday(lastSentDate, todayString)) {
      Logger.log(
        "本日分の掘り起こしアラートは送信済みのためスキップしました(" + todayString + ")。" +
        "再送したい場合は forceResendDailyAlerts を実行してください。"
      );
      return;
    }
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }

  var records = readCompanyRecords_(companySheet);
  var alerts = GlowAlerting.buildDailyAlertList(records, todayString);

  var unscoredCount = GlowAlerting.countUnscoredCompanies(records);
  if (unscoredCount > 0) {
    Logger.log("ランク未設定の企業: " + unscoredCount + "件(recalculateAllScoresを先に実行してください)");
  }

  if (alerts.length === 0) {
    Logger.log("本日の掘り起こし対象はありません。");
    scriptProperties.setProperty(SCRIPT_PROP_LAST_ALERT_SENT_DATE, todayString);
    return;
  }

  var linesToRender = alerts.slice(0, MAX_ALERT_LINES);
  var lines = linesToRender.map(function (alert) {
    return "・" + alert["会社名"] + "(" + alert["ランク"] + "ランク" +
      (alert["紹介ルート特例"] ? "・紹介ルート特例" : "") + ") — " + alert["ネクストベストアクション"];
  });
  if (alerts.length > MAX_ALERT_LINES) {
    lines.push("…ほか " + (alerts.length - MAX_ALERT_LINES) + "件");
  }
  var message = "【本日の掘り起こし対象】" + alerts.length + "件\n" + lines.join("\n");

  try {
    postToSlackWithRetry_(message);
  } catch (error) {
    scriptProperties.setProperty(SCRIPT_PROP_LAST_ALERT_ERROR, String(error));
    scriptProperties.setProperty(SCRIPT_PROP_LAST_ALERT_ERROR_AT, todayString);
    throw error;
  }

  scriptProperties.setProperty(SCRIPT_PROP_LAST_ALERT_SENT_DATE, todayString);
  Logger.log("掘り起こしアラート送信完了: " + alerts.length + "件");
}

/**
 * postToSlack_ を最大3回まで再試行するラッパー。
 * 429/5xx/ネットワーク例外のみ再試行し、それ以外(Webhook URL誤り等の設定不備で
 * 発生する4xx)は再試行せず即座にthrowする(resilient-agent-design原則⑤)。
 */
function postToSlackWithRetry_(message) {
  return GlowResilience.withRetry(
    function () { return postToSlack_(message); },
    {
      maxAttempts: 3,
      backoffMs: [2000, 10000],
      sleepFn: Utilities.sleep,
      isRetryable: function (error) {
        return !error.statusCode || GlowResilience.isRetryableHttpStatus(error.statusCode);
      },
      onRetry: function (error, attempt) {
        Logger.log("Slack通知を再試行します(" + attempt + "回目失敗): " + error);
      }
    }
  );
}

/**
 * SLACK_WEBHOOK_URL が未設定の場合は「設定されていないだけ」として通知をスキップする
 * (再試行しても直らないため postToSlackWithRetry_ の対象外の正常系)。
 * Webhook呼び出し自体が失敗した場合は、responseCode を持つ Error を throw して
 * 呼び出し元(postToSlackWithRetry_)にリトライ可否の判断を委ねる。
 */
function postToSlack_(message) {
  var webhookUrl = PropertiesService.getScriptProperties().getProperty("SLACK_WEBHOOK_URL");
  if (!webhookUrl) {
    Logger.log("SLACK_WEBHOOK_URL が未設定のため通知をスキップしました: " + message);
    return;
  }
  var response = UrlFetchApp.fetch(webhookUrl, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ text: message }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    var error = new Error(
      "Slackへの通知に失敗しました(HTTP " + responseCode + "): " + response.getContentText()
    );
    error.statusCode = responseCode;
    throw error;
  }
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
 * Apps Scriptエディタから**人間が手動で実行**して、認可済みの「インストール型トリガー」
 * として登録する必要がある(初回実行時に認可(オーソリ)を求めるダイアログが出るのは正常な挙動)。
 * installInteractionLogEditTrigger は冪等であり、実行前に同名の既存トリガーを削除してから
 * 登録し直すため、安全に何度でも再実行できる。
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
  postToSlackWithRetry_(
    "【即時アラート】" + companyName + "(" + companyId + ") が反応しました(" + newType + ")。至急対応してください。"
  );
}

/**
 * handleInteractionLogEdit をインストール型のonEditトリガーとして登録する。
 * Apps Scriptエディタから人間が手動で実行すること(実行時に認可ダイアログが出る)。
 * この関数は冪等: 実行時にまず同じハンドラ関数を指す既存トリガーをすべて削除してから
 * 新規登録するため、重複登録を心配せずに安全に再実行できる。
 */
function installInteractionLogEditTrigger() {
  var existingTriggers = ScriptApp.getProjectTriggers();
  existingTriggers.forEach(function (trigger) {
    if (trigger.getHandlerFunction() === "handleInteractionLogEdit") {
      ScriptApp.deleteTrigger(trigger);
    }
  });

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
