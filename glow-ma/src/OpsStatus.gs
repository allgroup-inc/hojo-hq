/**
 * GLOW企業リレーション台帳: 稼働状況の記録・失敗通知・自己修復
 *
 * 背景(2026-10-16): BlueBean架電履歴の同期が少なくとも10/3から台帳に1件も入っていないのに、
 * 誰も気づけなかった。失敗通知はSlack専用で、SLACK_WEBHOOK_URL未設定だと黙ってスキップされ、
 * 実行ログはApps Scriptエディタを開かないと見えないため。
 * そこで次の3つを入れる(2026-10-16 小柳さん承認・docs/議事_20261016_glow-ma自動反映と自己修復.md)。
 *
 *   1. 稼働状況タブ: 処理ごとの最終実行・結果を台帳の「稼働状況」タブに上書き記録する。
 *      エディタを開かずにスプレッドシートだけで「動いているか」が分かる
 *   2. 失敗通知のメール代替: Slack未設定ならスクリプト所有者へメール。同じ処理は1日1通まで
 *   3. 自己修復: ダッシュボードの欠落・非表示、BlueBean同期トリガー・日次メンテナンストリガーの欠落を
 *      自動で直す。毎分動く音声ログ処理から6時間に1回呼ぶ(人がエディタで関数を押す必要をなくす)
 */

var OPS_STATUS_SHEET_NAME = "稼働状況";
var OPS_STATUS_HEADERS = ["処理", "最終実行", "結果", "内容"];
var SELF_HEAL_INTERVAL_MS = 6 * 60 * 60 * 1000;

/** 処理ごとの最終結果を「稼働状況」タブへ上書きする。記録の失敗で本処理を止めない。 */
function recordOpsStatus_(processName, ok, detail) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(OPS_STATUS_SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(OPS_STATUS_SHEET_NAME);
      sheet.getRange(1, 1, 1, OPS_STATUS_HEADERS.length).setValues([OPS_STATUS_HEADERS]);
      sheet.setFrozenRows(1);
    }
    var row = [
      processName,
      Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm"),
      ok ? "成功" : "失敗",
      String(detail || "").slice(0, 500)
    ];
    var lastRow = sheet.getLastRow();
    if (lastRow >= 2) {
      var names = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
      for (var i = 0; i < names.length; i++) {
        if (names[i][0] === processName) {
          sheet.getRange(i + 2, 1, 1, row.length).setValues([row]);
          return;
        }
      }
    }
    sheet.appendRow(row);
  } catch (error) {
    Logger.log("稼働状況の記録に失敗しました(" + processName + "): " + error);
  }
}

/**
 * 失敗を人に届ける。Slackが設定されていればSlack、なければスクリプト所有者へメール。
 * 毎時・毎分の処理が同じ失敗を繰り返しても、処理ごとに1日1通に抑える。
 */
function notifyOpsFailure_(processName, message) {
  var props = PropertiesService.getScriptProperties();
  var today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var key = "OPS_NOTIFIED_" + processName;
  if (props.getProperty(key) === today) return;
  var text = "【GLOW台帳】「" + processName + "」が失敗しました。\n" + message +
    "\n\n台帳の「" + OPS_STATUS_SHEET_NAME + "」タブに最新の結果があります。";
  try {
    if (props.getProperty("SLACK_WEBHOOK_URL")) {
      postToSlack_(text);
    } else {
      var to = Session.getEffectiveUser().getEmail();
      if (!to) throw new Error("通知先メールアドレスを取得できません");
      MailApp.sendEmail(to, "【GLOW台帳】" + processName + " が失敗しました", text);
    }
    props.setProperty(key, today);
  } catch (error) {
    Logger.log("失敗通知を送れませんでした(" + processName + "): " + error);
  }
}

/** 6時間に1回だけ自己修復を走らせる(毎分の音声ログ処理から呼ぶ)。 */
function runSelfHealIfDue_() {
  var props = PropertiesService.getScriptProperties();
  var last = Number(props.getProperty("SELF_HEAL_LAST_RUN_MS") || 0);
  if (Date.now() - last < SELF_HEAL_INTERVAL_MS) return;
  props.setProperty("SELF_HEAL_LAST_RUN_MS", String(Date.now()));
  runSelfHeal();
}

/**
 * 自己修復。エディタから手動実行してもよい(冪等)。
 * 各項目は独立して失敗しうるので、1つの失敗で残りを止めない。
 */
function runSelfHeal() {
  var results = [];
  var failures = [];
  var checks = [
    { name: "ダッシュボードの表示", run: ensureDashboardVisible_ },
    { name: "BlueBean同期トリガー", run: ensureCtiSyncTrigger_ },
    { name: "日次メンテナンストリガー", run: ensureDailyMaintenanceTrigger_ },
    { name: "過去記録の取り込みタブ", run: function () { return ensureHistoryImportSheet_() ? "作成" : "あり"; } },
    { name: "録音ファイルの受付フォルダ", run: ensureVoiceDriveFolder_ }
  ];
  checks.forEach(function (check) {
    try {
      results.push(check.name + ": " + check.run());
    } catch (error) {
      failures.push(check.name + ": " + error);
    }
  });
  var detail = results.concat(failures).join(" / ");
  recordOpsStatus_("自己点検・修復", failures.length === 0, detail);
  if (failures.length > 0) notifyOpsFailure_("自己点検・修復", failures.join("\n"));
  // console.log は Cloud Logging に残る(外から点検結果を確認できる)
  console.log("自己点検・修復: " + detail);
}

function ensureDashboardVisible_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);
  if (!sheet) {
    ensureTab_(ss, GlowSchema.DASHBOARD_SHEET_NAME, GlowSchema.DASHBOARD_PLACEHOLDER_HEADERS);
    updateDashboard();
    return "無かったため作成して集計";
  }
  if (sheet.isSheetHidden()) {
    sheet.showSheet();
    return "非表示だったため表示に戻した";
  }
  return "正常";
}

function hasTrigger_(handlerName) {
  return ScriptApp.getProjectTriggers().some(function (t) {
    return t.getHandlerFunction() === handlerName;
  });
}

function ensureCtiSyncTrigger_() {
  var props = PropertiesService.getScriptProperties();
  var missing = ["BLUEBEAN_DOMAIN", "BLUEBEAN_USERNAME", "BLUEBEAN_PASSWORD", "BLUEBEAN_CAMPAIGN_ID"]
    .filter(function (key) { return !props.getProperty(key); });
  if (missing.length > 0) {
    throw new Error("スクリプト プロパティが未設定: " + missing.join(", "));
  }
  if (hasTrigger_("syncCtiCallHistory")) return "登録済み";
  installCtiSyncTrigger();
  return "未登録だったため登録した";
}

function ensureDailyMaintenanceTrigger_() {
  if (hasTrigger_("runDailyMaintenance")) return "登録済み";
  installDailyMaintenanceTrigger();
  return "未登録だったため登録した";
}
