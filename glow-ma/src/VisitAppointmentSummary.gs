/**
 * 対応履歴ログから訪問・アポ・QRアクセスを集計してダッシュボードセクションを生成
 * 対応履歴ログの「種別」列から訪問・アポ設定・レターURLアクセスを抽出し、当月のみを集計
 */
function buildVisitAppointmentSummary(records, interactionRecords, todayString) {
  var visits = 0;
  var appointments = 0;
  var qrAccesses = 0;

  interactionRecords.forEach(function(log) {
    var type = String(log["種別"] || "").trim();
    var date = String(log["日付"] || "").trim();

    // 当月のレコードのみカウント
    if (isCurrentMonth_(date, todayString)) {
      if (type === "訪問") {
        visits++;
      } else if (type === "アポ獲得") {
        appointments++;
      } else if (type === "レターURLアクセス") {
        qrAccesses++;
      }
    }
  });

  return [
    ["訪問・アポ・QRアクセスサマリー(当月)"],
    ["カテゴリ", "件数"],
    ["訪問実績", visits],
    ["アポ設定", appointments],
    ["QRコードアクセス", qrAccesses],
    ["合計営業活動", visits + appointments + qrAccesses]
  ];
}

function isCurrentMonth_(dateString, todayString) {
  if (!dateString) return false;
  try {
    var date = new Date(dateString);
    var today = new Date(todayString);
    return date.getFullYear() === today.getFullYear() &&
           date.getMonth() === today.getMonth();
  } catch (e) {
    return false;
  }
}
