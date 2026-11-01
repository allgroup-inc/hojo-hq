/**
 * LINE Official Account からの問い合わせを集計してダッシュボードセクションを生成
 * LINE音声ログシートの「ステータス」列を元に、受信・対応待ち・対応済み件数を集計
 */
function readVoiceLogRecords_(sheet) {
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.LINE_VOICE_LOG_HEADERS;
  var statusIndex = headers.indexOf("ステータス");
  if (statusIndex === -1) return [];

  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var records = [];
  values.forEach(function (row) {
    if (!row[0]) return;
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    records.push(record);
  });
  return records;
}

function collectLineInquiries() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var voiceLogSheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!voiceLogSheet) {
    Logger.log("LINE音声ログシートが見つかりません。LINE問い合わせ集計をスキップします");
    return { "本日受信": 0, "対応待ち": 0, "対応済み": 0 };
  }

  var voiceLogs = readVoiceLogRecords_(voiceLogSheet);
  var stats = {
    "本日受信": 0,
    "対応待ち": 0,
    "対応済み": 0
  };

  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");

  voiceLogs.forEach(function(log) {
    var status = String(log["ステータス"] || "").trim();
    var receivedDate = String(log["受信日時"] || "").trim();

    // 本日受信の集計
    if (receivedDate.indexOf(todayString) === 0) {
      stats["本日受信"]++;
    }

    // ステータス別集計
    if (status === "受信済み" || status === "企業選択待ち" || status === "新規企業確認待ち" || status === "最終確認待ち") {
      stats["対応待ち"]++;
    } else if (status === "確定") {
      stats["対応済み"]++;
    }
  });

  return stats;
}

function buildLineInquirySummary() {
  var stats = collectLineInquiries();
  return [
    ["LINE問い合わせサマリー"],
    ["カテゴリ", "件数"],
    ["本日受信", stats["本日受信"]],
    ["対応待ち", stats["対応待ち"]],
    ["対応済み", stats["対応済み"]]
  ];
}
