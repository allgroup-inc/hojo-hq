/**
 * 福田の稼働実績をシステムから自動取得・集計
 *
 * 使用方法:
 * 1. Google Apps Script エディタでこのファイルを開く
 * 2. getFukudaPerformanceReport() 関数を実行
 * 3. ログ出力から全数値をコピー
 */

function getFukudaPerformanceReport() {
  Logger.log("=== 福田の稼働実績レポート ===");
  Logger.log("実行日時: " + new Date().toLocaleString("ja-JP"));
  Logger.log("");

  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const masterSheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    const interactionSheet = ss.getSheetByName("活動記録");

    if (!masterSheet || !interactionSheet) {
      Logger.log("✗ エラー: 必要なシートが見つかりません");
      Logger.log("  - 企業マスタシート: " + (masterSheet ? "✓" : "✗"));
      Logger.log("  - 活動記録シート: " + (interactionSheet ? "✓" : "✗"));
      return;
    }

    // データ読み込み
    const masterRecords = readMasterRecords_(masterSheet);
    const interactions = readInteractionRecords_(interactionSheet);

    Logger.log("読込完了:");
    Logger.log("  企業マスタ: " + masterRecords.length + "件");
    Logger.log("  活動記録: " + interactions.length + "件");
    Logger.log("");

    // 福田の活動レコードのみフィルタ
    const fukudaInteractions = interactions.filter(r => {
      const담당者 = r["担当者"] || r["担当者名"] || r["営業担当"];
      return 담당者 && 담当者.includes("福田");
    });

    if (fukudaInteractions.length === 0) {
      Logger.log("⚠ 福田の活動記録がありません");
      Logger.log("※ 담当者列の值を確認してください");
      return;
    }

    Logger.log("福田の活動記録: " + fukudaInteractions.length + "件");
    Logger.log("");

    // 日付範囲の計算
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    yesterday.setHours(0, 0, 0, 0);

    const weekStart = new Date(yesterday);
    weekStart.setDate(weekStart.getDate() - 6);
    weekStart.setHours(0, 0, 0, 0);

    const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
    monthStart.setHours(0, 0, 0, 0);

    // ===== 架電実績 =====
    Logger.log("■ 架電実績");

    const callsYesterday = fukudaInteractions.filter(r => {
      return r["種別"] === "電話" &&
             dateMatches_(new Date(r["対応日時"]), yesterday);
    }).length;

    const callsWeekly = fukudaInteractions.filter(r => {
      return r["種別"] === "電話" &&
             isWithinDateRange_(new Date(r["対応日時"]), weekStart, yesterday);
    }).length;

    const callsMonthly = fukudaInteractions.filter(r => {
      return r["種別"] === "電話" &&
             isWithinDateRange_(new Date(r["対応日時"]), monthStart, today);
    }).length;

    Logger.log("  昨日: " + callsYesterday + "件");
    Logger.log("  週間(過去7日): " + callsWeekly + "件");
    Logger.log("  月間(当月): " + callsMonthly + "件");

    // ランク別内訳（当月）
    const callsByRank = {A: 0, B: 0, C: 0, D: 0};
    fukudaInteractions.forEach(r => {
      if (r["種別"] === "電話" &&
          isWithinDateRange_(new Date(r["対応日時"]), monthStart, today)) {
        const rank = r["企業ランク"] || "D";
        if (callsByRank[rank] !== undefined) {
          callsByRank[rank]++;
        }
      }
    });
    Logger.log("  ランク別(当月): A=" + callsByRank.A + " B=" + callsByRank.B +
               " C=" + callsByRank.C + " D=" + callsByRank.D);
    Logger.log("");

    // ===== 訪問・面談実績 =====
    Logger.log("■ 訪問・面談実績");

    const visitsYesterday = fukudaInteractions.filter(r => {
      return ["訪問", "面談"].includes(r["種別"]) &&
             dateMatches_(new Date(r["対応日時"]), yesterday);
    }).length;

    const visitsWeekly = fukudaInteractions.filter(r => {
      return ["訪問", "面談"].includes(r["種別"]) &&
             isWithinDateRange_(new Date(r["対応日時"]), weekStart, yesterday);
    }).length;

    const visitsMonthly = fukudaInteractions.filter(r => {
      return ["訪問", "面談"].includes(r["種別"]) &&
             isWithinDateRange_(new Date(r["対応日時"]), monthStart, today);
    }).length;

    Logger.log("  昨日: " + visitsYesterday + "件");
    Logger.log("  週間(過去7日): " + visitsWeekly + "件");
    Logger.log("  月間(当月): " + visitsMonthly + "件");
    Logger.log("");

    // ===== 成約実績 =====
    Logger.log("■ 成約実績");

    const contractsYesterday = fukudaInteractions.filter(r => {
      return r["成約"] === true &&
             dateMatches_(new Date(r["対応日時"]), yesterday);
    }).length;

    const contractsWeekly = fukudaInteractions.filter(r => {
      return r["成約"] === true &&
             isWithinDateRange_(new Date(r["対応日時"]), weekStart, yesterday);
    }).length;

    const contractsMonthly = fukudaInteractions.filter(r => {
      return r["成約"] === true &&
             isWithinDateRange_(new Date(r["対応日時"]), monthStart, today);
    }).length;

    Logger.log("  昨日: " + contractsYesterday + "件");
    Logger.log("  週間(過去7日): " + contractsWeekly + "件");
    Logger.log("  月間(当月): " + contractsMonthly + "件");

    if (callsMonthly > 0) {
      const contractRate = (contractsMonthly / callsMonthly * 100).toFixed(1);
      Logger.log("  成約率(当月): " + contractRate + "% (" + contractsMonthly + "/" + callsMonthly + ")");
    }
    Logger.log("");

    // ===== 企業マスタ統計 =====
    Logger.log("■ システム全体統計");

    const totalCompanies = masterRecords.length;
    const rankDist = {A: 0, B: 0, C: 0, D: 0};
    const industryDist = {};
    const routeDist = {};
    let totalContracts = 0;

    masterRecords.forEach(r => {
      const rank = r["ランク"] || "D";
      if (rankDist[rank] !== undefined) rankDist[rank]++;

      const industry = r["業種"] || "不明";
      industryDist[industry] = (industryDist[industry] || 0) + 1;

      const routes = r["流入ルート"] || [];
      if (Array.isArray(routes)) {
        routes.forEach(route => {
          routeDist[route] = (routeDist[route] || 0) + 1;
        });
      }

      if (r["成約"] === true) totalContracts++;
    });

    Logger.log("  企業総数: " + totalCompanies + "社");
    Logger.log("  ランク分布: A=" + rankDist.A + " B=" + rankDist.B +
               " C=" + rankDist.C + " D=" + rankDist.D);

    Logger.log("  業態別:");
    Object.keys(industryDist).sort().forEach(industry => {
      Logger.log("    " + industry + ": " + industryDist[industry] + "社");
    });

    Logger.log("  流入ルート別:");
    ["①紹介", "②手紙DM", "③ミカタ経由", "④開拓架電"].forEach(route => {
      Logger.log("    " + route + ": " + (routeDist[route] || 0) + "社");
    });

    Logger.log("  成約企業総数: " + totalContracts + "社 (全体成約率: " +
               (totalCompanies > 0 ? (totalContracts / totalCompanies * 100).toFixed(1) : "0.0") + "%)");
    Logger.log("");

    Logger.log("✓ レポート生成完了");

  } catch (e) {
    Logger.log("✗ エラーが発生しました:");
    Logger.log(e.toString());
    Logger.log(e.stack);
  }
}

// ===== ユーティリティ関数 =====

function readMasterRecords_(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];

  const headers = GlowSchema.COMPANY_MASTER_HEADERS;
  const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();

  return values.filter(row => {
    // 企業IDが空の行はスキップ
    return row[headers.indexOf("企業ID")] !== "";
  }).map(row => {
    const record = {};
    headers.forEach((header, i) => {
      record[header] = row[i];
    });
    return record;
  });
}

function readInteractionRecords_(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();

  return values.map(row => {
    const record = {};
    headers.forEach((header, i) => {
      record[header] = row[i];
    });
    return record;
  });
}

function dateMatches_(date1, date2) {
  return date1.getFullYear() === date2.getFullYear() &&
         date1.getMonth() === date2.getMonth() &&
         date1.getDate() === date2.getDate();
}

function isWithinDateRange_(date, startDate, endDate) {
  return date >= startDate && date <= endDate;
}
