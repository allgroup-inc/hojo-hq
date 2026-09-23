/**
 * DailyReportAutomation.gs
 *
 * GLOW の日次レポート自動化システム
 * Task 6: トリガー登録と本番テスト
 *
 * このファイルは ReportDataCompiler.gs / ReportEmailFormatter.gs /
 * ReportSheetWriter.gs の関数を使用して、日次レポートの生成・記録・配信を
 * オーケストレーションする
 */

function createDailyReportTrigger() {
  // 既存のトリガーを確認
  const triggers = ScriptApp.getProjectTriggers();
  const existingDailyReportTrigger = triggers.find(t =>
    t.getHandlerFunction() === 'sendDailyReport' &&
    t.getTriggerSource() === ScriptApp.TriggerSource.CLOCK
  );

  if (existingDailyReportTrigger) {
    Logger.log("Daily report trigger already exists. Skipping creation.");
    return;
  }

  // 毎日10:00 JST にトリガーを設定
  ScriptApp.newTrigger('sendDailyReport')
    .timeBased()
    .atHour(10)
    .nearMinute(0)
    .everyDays(1)
    .create();

  Logger.log("✓ Daily report trigger created for 10:00 JST");
}

function sendDailyReport() {
  try {
    const yesterday = getYesterday();
    const reportData = compileDailyReport(yesterday);
    const emailBody = formatReportEmail(reportData);

    // シートに書き込み
    writeReportToSheet(reportData);

    // メール送信
    sendDailyReportEmail(reportData, emailBody);

    Logger.log("✓ 日次レポート配信完了: " + reportData.reportDate);
  } catch (e) {
    Logger.log("✗ エラーが発生しました:");
    Logger.log(e.toString());
    Logger.log(e.stack);

    // エラーメールを送信
    try {
      GmailApp.sendEmail(
        "takeshi.koyanagi9@gmail.com",
        "【GLOW日次レポート】エラーが発生しました",
        "エラー詳細:\n" + e.toString() + "\n\nスタックトレース:\n" + e.stack
      );
    } catch (emailError) {
      Logger.log("Error sending error email: " + emailError.toString());
    }
  }
}

function testSendDailyReport() {
  Logger.log("=== Test: Daily Report Generation ===");

  try {
    const yesterday = getYesterday();
    Logger.log("Yesterday date: " + yesterday.toLocaleString("ja-JP"));

    const reportData = compileDailyReport(yesterday);
    Logger.log("Report data compiled:");
    Logger.log("  Letters (yesterday): " + reportData.letters.yesterday);
    Logger.log("  Calls (yesterday): " + reportData.calls.yesterday);
    Logger.log("  Visits (yesterday): " + reportData.visits.yesterday);

    const emailBody = formatReportEmail(reportData);
    Logger.log("Email HTML generated: " + emailBody.length + " chars");

    // NOTE: Don't actually send in test - just log success
    Logger.log("✓ Test completed successfully. Ready to send.");
    Logger.log("Run sendDailyReport() to execute with email delivery.");
  } catch (e) {
    Logger.log("✗ Test failed:");
    Logger.log(e.toString());
    Logger.log(e.stack);
  }
}
