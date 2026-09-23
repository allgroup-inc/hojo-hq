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

/**
 * Task 7 Step 1: 本番デプロイ前チェックリスト — コード品質チェック
 *
 * Tasks 1-6 で定義されているはずの主要関数が全て存在するかを確認する。
 * (docs/superpowers/plans/2026-09-22-daily-report-automation.md Task 7 Step 1 のコードをそのまま使用)
 */
function validateCodeQuality() {
  Logger.log("=== Code Quality Validation ===");

  // Check all required functions exist
  const requiredFunctions = [
    "getYesterday",
    "countLettersByDate",
    "countCallsByDateRange",
    "getRankDistribution",
    "compileDailyReport",
    "formatReportEmail",
    "writeReportToSheet",
    "sendDailyReportEmail",
    "createDailyReportTrigger",
    "sendDailyReport"
  ];

  let allDefined = true;
  requiredFunctions.forEach(fn => {
    if (typeof globalThis[fn] !== "function") {
      Logger.log("✗ Missing function: " + fn);
      allDefined = false;
    }
  });

  if (allDefined) {
    Logger.log("✓ All required functions defined");
  } else {
    throw new Error("Code quality validation failed: missing required functions");
  }
}

/**
 * Task 7 Step 3: 本番デプロイ前チェックリスト — 月末・月初境界テスト
 *
 * getMonthDateRange() が月境界(9/30→10/1)を正しく扱えるかを確認する。
 * (docs/superpowers/plans/2026-09-22-daily-report-automation.md Task 7 Step 3 のコードをそのまま使用)
 */
function testDateBoundaries() {
  Logger.log("=== Date Boundary Tests ===");

  let allTestsPassed = true;

  // Test 1: Sept 30 should return Sept 1 - Sept 30 (month index 8)
  const sept30 = new Date(2026, 8, 30); // Sept 30
  const septRange = getMonthDateRange(sept30);
  Logger.log("Sept 30 month range: " + septRange.startDate.toLocaleDateString() + " to " + septRange.endDate.toLocaleDateString());

  if (septRange.startDate.getMonth() !== 8 || septRange.startDate.getDate() !== 1) {
    Logger.log("✗ Sept 30 start date test failed: expected month 8, date 1");
    allTestsPassed = false;
  } else if (septRange.endDate.getMonth() !== 8 || septRange.endDate.getDate() !== 30) {
    Logger.log("✗ Sept 30 end date test failed: expected month 8, date 30");
    allTestsPassed = false;
  } else {
    Logger.log("✓ Sept 30 month range correct (Sept 1 - Sept 30)");
  }

  // Test 2: Oct 1 should return Oct 1 - Oct 1 (month index 9)
  const oct1 = new Date(2026, 9, 1); // Oct 1
  const octRange = getMonthDateRange(oct1);
  Logger.log("Oct 1 month range: " + octRange.startDate.toLocaleDateString() + " to " + octRange.endDate.toLocaleDateString());

  if (octRange.startDate.getMonth() !== 9 || octRange.startDate.getDate() !== 1) {
    Logger.log("✗ Oct 1 start date test failed: expected month 9, date 1");
    allTestsPassed = false;
  } else if (octRange.endDate.getMonth() !== 9 || octRange.endDate.getDate() !== 1) {
    Logger.log("✗ Oct 1 end date test failed: expected month 9, date 1");
    allTestsPassed = false;
  } else {
    Logger.log("✓ Oct 1 month range correct (Oct 1 - Oct 1)");
  }

  if (!allTestsPassed) {
    throw new Error("Date boundary tests failed");
  }
}
