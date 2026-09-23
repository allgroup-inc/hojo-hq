function ensureReportSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName("日次レポート");

  if (!sheet) {
    sheet = ss.insertSheet("日次レポート");

    // ヘッダー行を作成
    const headers = [
      "配信日",
      "手紙発送(昨日)",
      "手紙発送(週間)",
      "手紙発送(月間)",
      "QRスキャン(昨日)",
      "QRスキャン(週間)",
      "QRスキャン(月間)",
      "累計QRスキャン率",
      "架電(昨日)",
      "架電(週間)",
      "架電(月間)",
      "訪問・面談(昨日)",
      "訪問・面談(週間)",
      "訪問・面談(月間)",
      "成約(月間)",
      "成約率",
      "ランクA",
      "ランクB",
      "ランクC",
      "ランクD",
      "企業総数",
      "①紹介成約",
      "②手紙DM成約",
      "③ミカタ経由成約",
      "④開拓架電成約",
      "記録時刻"
    ];

    sheet.appendRow(headers);
  }

  return sheet;
}

function writeReportToSheet(reportData) {
  const sheet = ensureReportSheet();

  const row = [
    reportData.reportDate,
    reportData.letters.yesterday,
    reportData.letters.weekly,
    reportData.letters.monthly,
    reportData.qrScans.yesterday,
    reportData.qrScans.weekly,
    reportData.qrScans.monthly,
    reportData.qrScans.scanRate,
    reportData.calls.yesterday,
    reportData.calls.weekly,
    reportData.calls.monthly,
    reportData.visits.yesterday,
    reportData.visits.weekly,
    reportData.visits.monthly,
    reportData.visits.monthlyContracts,
    reportData.visits.contractRate,
    reportData.rankDistribution.A,
    reportData.rankDistribution.B,
    reportData.rankDistribution.C,
    reportData.rankDistribution.D,
    reportData.rankDistribution.total,
    reportData.routeConversion["①紹介"].contracts,
    reportData.routeConversion["②手紙DM"].contracts,
    reportData.routeConversion["③ミカタ経由"].contracts,
    reportData.routeConversion["④開拓架電"].contracts,
    new Date().toLocaleString("ja-JP")
  ];

  sheet.appendRow(row);
}

function sendDailyReportEmail(reportData, emailBody) {
  const recipientEmail = "takeshi.koyanagi9@gmail.com";
  const subject = `【GLOW日次レポート】${reportData.reportDate}`;

  GmailApp.sendEmail(
    recipientEmail,
    subject,
    "", // plaintext body (minimal)
    {
      htmlBody: emailBody
    }
  );

  Logger.log("✓ Email sent to " + recipientEmail);
}
