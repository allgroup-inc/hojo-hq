/**
 * ReportDataCompiler.gs
 *
 * 日付計算と手紙・QRスキャン集計のためのユーティリティ関数
 * Task 1: 日付計算と手紙・QRスキャン集計
 */

/**
 * テスト関数: 日付ユーティリティの検証
 * getYesterday() は前日 0時を返す
 * getWeekDateRange() は過去7日の範囲を返す
 */
function testDateFunctions() {
  // getYesterday() は前日 0時を返す
  const yesterday = getYesterday();
  const expectedDate = new Date();
  expectedDate.setDate(expectedDate.getDate() - 1);
  expectedDate.setHours(0, 0, 0, 0);
  if (yesterday.getTime() !== expectedDate.getTime()) {
    throw new Error("getYesterday failed: " + yesterday);
  }

  // getWeekDateRange() は過去7日の範囲を返す
  const range = getWeekDateRange(yesterday);
  const expectedStart = new Date(yesterday);
  expectedStart.setDate(expectedStart.getDate() - 6);
  if (range.startDate.getTime() !== expectedStart.getTime()) {
    throw new Error("getWeekDateRange start failed");
  }
  Logger.log("✓ Date functions passed");
}

/**
 * 前日の 0時を返す
 * @returns {Date} 前日の 0時の Date オブジェクト
 */
function getYesterday() {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  yesterday.setHours(0, 0, 0, 0);
  return yesterday;
}

/**
 * referenceDate から過去7日の範囲を返す
 * @param {Date} referenceDate - 基準日
 * @returns {Object} {startDate: Date, endDate: Date}
 */
function getWeekDateRange(referenceDate) {
  // referenceDate から過去7日の範囲を返す
  const endDate = new Date(referenceDate);
  endDate.setHours(23, 59, 59, 999);

  const startDate = new Date(endDate);
  startDate.setDate(startDate.getDate() - 6);
  startDate.setHours(0, 0, 0, 0);

  return { startDate, endDate };
}

/**
 * referenceDate が属する月の 1日〜referenceDate までの範囲を返す
 * @param {Date} referenceDate - 基準日
 * @returns {Object} {startDate: Date, endDate: Date}
 */
function getMonthDateRange(referenceDate) {
  // referenceDate が属する月の 1日〜referenceDate までの範囲を返す
  const monthStart = new Date(referenceDate.getFullYear(), referenceDate.getMonth(), 1);
  monthStart.setHours(0, 0, 0, 0);

  const monthEnd = new Date(referenceDate);
  monthEnd.setHours(23, 59, 59, 999);

  return { startDate: monthStart, endDate: monthEnd };
}

/**
 * Date オブジェクトを YYYY-MM-DD 形式の文字列に変換
 * @param {Date} date - 変換対象の Date オブジェクト
 * @returns {string} YYYY-MM-DD 形式の文字列
 */
function datesToLocaleDateString(date) {
  // YYYY-MM-DD 形式で統一
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * 指定された日付に手紙を送付した企業の件数を数える
 * @param {Array} masterRecords - 企業マスタのレコード配列
 * @param {Date} targetDate - 対象日
 * @returns {number} 手紙送付件数
 */
function countLettersByDate(masterRecords, targetDate) {
  // 「最終手紙送付日」列の日付が targetDate に一致する件数を数える
  const targetDateStr = datesToLocaleDateString(targetDate);
  return masterRecords.filter(r => {
    const letterDate = r["最終手紙送付日"];
    if (!letterDate) return false;
    return datesToLocaleDateString(new Date(letterDate)) === targetDateStr;
  }).length;
}

/**
 * 指定された日付範囲に手紙を送付した企業の件数を数える
 * @param {Array} masterRecords - 企業マスタのレコード配列
 * @param {Date} startDate - 開始日
 * @param {Date} endDate - 終了日
 * @returns {number} 手紙送付件数
 */
function countLettersByDateRange(masterRecords, startDate, endDate) {
  // startDate ～ endDate の間に手紙を送った企業の件数
  return masterRecords.filter(r => {
    const letterDate = r["最終手紙送付日"];
    if (!letterDate) return false;
    const date = new Date(letterDate);
    return date >= startDate && date <= endDate;
  }).length;
}

/**
 * LINE 公式アカウントの新規登録ユーザー数を取得
 * @param {Date} targetDate - 対象日
 * @returns {number} 新規登録ユーザー数
 */
function getLineNewUsersCount(targetDate) {
  // LINE 公式アカウントの新規登録ユーザー数を取得
  // 現状: LINE 連携 API の詳細が不明のため、プレースホルダーを返す
  // TODO: LINE API 仕様が決まったら実装
  Logger.log("⚠ getLineNewUsersCount: LINE API not yet implemented");
  return 0;
}

/**
 * LINE 登録ユーザーの累計数を取得
 * @param {Date} targetDate - 対象日
 * @returns {number} LINE ユーザー累計数
 */
function getLineUserCountByDate(targetDate) {
  // LINE 登録ユーザーの累計数(targetDate 時点)
  // 現状: LINE 連携 API の詳細が不明のため、プレースホルダーを返す
  Logger.log("⚠ getLineUserCountByDate: LINE API not yet implemented");
  return 0;
}

/**
 * テスト関数: 架電・訪問・成約集計の検証
 */
function testCallAggregation() {
  const mockInteractions = [
    {"対応日時": new Date(2026, 8, 22), "種別": "電話", "企業ランク": "A"},
    {"対応日時": new Date(2026, 8, 22), "種別": "電話", "企業ランク": "B"},
    {"対応日時": new Date(2026, 8, 21), "種別": "電話", "企業ランク": "A"},
    {"対応日時": new Date(2026, 8, 22), "種別": "訪問", "企業ランク": "C"},
  ];

  const yesterday = new Date(2026, 8, 22);
  const count = countCallsByDate(mockInteractions, yesterday);
  if (count !== 2) {
    throw new Error("countCallsByDate failed: expected 2, got " + count);
  }

  const byRank = countCallsByDateRange(mockInteractions, yesterday, yesterday);
  if (byRank.byRank.A !== 1 || byRank.byRank.B !== 1) {
    throw new Error("countCallsByDateRange byRank failed");
  }
  Logger.log("✓ Call aggregation tests passed");
}

/**
 * 指定された日付の架電件数を数える
 * @param {Array} interactionRecords - インタラクションレコード配列
 * @param {Date} targetDate - 対象日
 * @returns {number} 架電件数
 */
function countCallsByDate(interactionRecords, targetDate) {
  const targetDateStr = datesToLocaleDateString(targetDate);
  return interactionRecords.filter(r => {
    if (r["種別"] !== "電話") return false;
    const recordDate = new Date(r["対応日時"]);
    return datesToLocaleDateString(recordDate) === targetDateStr;
  }).length;
}

/**
 * 指定された日付範囲の架電件数を企業ランク別に集計
 * @param {Array} interactionRecords - インタラクションレコード配列
 * @param {Date} startDate - 開始日
 * @param {Date} endDate - 終了日
 * @returns {Object} {total: number, byRank: {A: number, B: number, C: number, D: number}}
 */
function countCallsByDateRange(interactionRecords, startDate, endDate) {
  const filtered = interactionRecords.filter(r => {
    if (r["種別"] !== "電話") return false;
    const recordDate = new Date(r["対応日時"]);
    return recordDate >= startDate && recordDate <= endDate;
  });

  return {
    total: filtered.length,
    byRank: {
      "A": filtered.filter(r => r["企業ランク"] === "A").length,
      "B": filtered.filter(r => r["企業ランク"] === "B").length,
      "C": filtered.filter(r => r["企業ランク"] === "C").length,
      "D": filtered.filter(r => r["企業ランク"] === "D").length,
    }
  };
}

/**
 * 指定された日付の訪問・面談件数を分離して返す
 * @param {Array} interactionRecords - インタラクションレコード配列
 * @param {Date} targetDate - 対象日
 * @returns {Object} {visits: number, meetings: number, total: number}
 */
function countVisitsByDate(interactionRecords, targetDate) {
  const targetDateStr = datesToLocaleDateString(targetDate);
  const filtered = interactionRecords.filter(r => {
    if (!["訪問", "面談"].includes(r["種別"])) return false;
    const recordDate = new Date(r["対応日時"]);
    return datesToLocaleDateString(recordDate) === targetDateStr;
  });

  return {
    visits: filtered.filter(r => r["種別"] === "訪問").length,
    meetings: filtered.filter(r => r["種別"] === "面談").length,
    total: filtered.length,
  };
}

/**
 * 指定された日付範囲の訪問・面談件数を分離して返す
 * @param {Array} interactionRecords - インタラクションレコード配列
 * @param {Date} startDate - 開始日
 * @param {Date} endDate - 終了日
 * @returns {Object} {visits: number, meetings: number, total: number}
 */
function countVisitsByDateRange(interactionRecords, startDate, endDate) {
  const filtered = interactionRecords.filter(r => {
    if (!["訪問", "面談"].includes(r["種別"])) return false;
    const recordDate = new Date(r["対応日時"]);
    return recordDate >= startDate && recordDate <= endDate;
  });

  return {
    visits: filtered.filter(r => r["種別"] === "訪問").length,
    meetings: filtered.filter(r => r["種別"] === "面談").length,
    total: filtered.length,
  };
}

/**
 * 指定された日付の成約件数を数える
 * @param {Array} interactionRecords - インタラクションレコード配列
 * @param {Date} targetDate - 対象日
 * @returns {number} 成約件数
 */
function countContractsByDate(interactionRecords, targetDate) {
  const targetDateStr = datesToLocaleDateString(targetDate);
  return interactionRecords.filter(r => {
    if (r["成約"] !== true) return false;
    const recordDate = new Date(r["対応日時"]);
    return datesToLocaleDateString(recordDate) === targetDateStr;
  }).length;
}

/**
 * 指定された日付範囲の成約件数を数える
 * @param {Array} interactionRecords - インタラクションレコード配列
 * @param {Date} startDate - 開始日
 * @param {Date} endDate - 終了日
 * @returns {number} 成約件数
 */
function countContractsByDateRange(interactionRecords, startDate, endDate) {
  return interactionRecords.filter(r => {
    if (r["成約"] !== true) return false;
    const recordDate = new Date(r["対応日時"]);
    return recordDate >= startDate && recordDate <= endDate;
  }).length;
}

/**
 * 成約率を計算して%表記で返す
 * @param {number} contracts - 成約件数
 * @param {number} total - 総件数
 * @returns {string} "0.0%"形式の文字列
 */
function getConversionRate(contracts, total) {
  if (total === 0) return "0.0%";
  return (contracts / total * 100).toFixed(1) + "%";
}

/**
 * テスト関数: ランク分布の検証
 */
function testRankDistribution() {
  const mockRecords = [
    {"ランク": "A"},
    {"ランク": "A"},
    {"ランク": "B"},
    {"ランク": "C"},
    {"ランク": "D"},
  ];

  const dist = getRankDistribution(mockRecords);
  if (dist.A !== 2 || dist.B !== 1 || dist.C !== 1 || dist.D !== 1 || dist.total !== 5) {
    throw new Error("getRankDistribution failed: " + JSON.stringify(dist));
  }
  Logger.log("✓ Rank distribution test passed");
}

/**
 * 企業マスタからランク分布を集計
 * @param {Array} masterRecords - 企業マスタのレコード配列
 * @returns {Object} {A: number, B: number, C: number, D: number, total: number}
 */
function getRankDistribution(masterRecords) {
  const dist = {A: 0, B: 0, C: 0, D: 0};
  masterRecords.forEach(r => {
    const rank = r["ランク"];
    if (rank && dist[rank] !== undefined) {
      dist[rank]++;
    }
  });
  dist.total = masterRecords.length;
  return dist;
}

/**
 * 企業マスタからランク分布を集計し、前期との比較を返す
 * @param {Array} masterRecords - 企業マスタのレコード配列
 * @param {Array} previousMasterRecords - 前期の企業マスタのレコード配列
 * @returns {Object} {current: {...}, previous: {...}, changes: {A: number, B: number, C: number, D: number}}
 */
function getRankDistributionWithPrevious(masterRecords, previousMasterRecords) {
  const current = getRankDistribution(masterRecords);
  const previous = getRankDistribution(previousMasterRecords);

  return {
    current,
    previous,
    changes: {
      A: current.A - previous.A,
      B: current.B - previous.B,
      C: current.C - previous.C,
      D: current.D - previous.D,
    }
  };
}

/**
 * 企業マスタからスコアセグメント分布を集計
 * @param {Array} masterRecords - 企業マスタのレコード配列
 * @returns {Object} {"90以上": number, "70-89": number, "40-69": number, "15-39": number, "15未満": number}
 */
function getScoreSegments(masterRecords) {
  return {
    "90以上": masterRecords.filter(r => r["総合スコア"] >= 90).length,
    "70-89": masterRecords.filter(r => r["総合スコア"] >= 70 && r["総合スコア"] < 90).length,
    "40-69": masterRecords.filter(r => r["総合スコア"] >= 40 && r["総合スコア"] < 70).length,
    "15-39": masterRecords.filter(r => r["総合スコア"] >= 15 && r["総合スコア"] < 40).length,
    "15未満": masterRecords.filter(r => r["総合スコア"] < 15).length,
  };
}

/**
 * 企業マスタからスコアセグメント分布を集計し、前期との比較を返す
 * @param {Array} masterRecords - 企業マスタのレコード配列
 * @param {Array} previousMasterRecords - 前期の企業マスタのレコード配列
 * @returns {Object} {current: {...}, previous: {...}, changes: {...}}
 */
function getScoreSegmentsWithPrevious(masterRecords, previousMasterRecords) {
  const current = getScoreSegments(masterRecords);
  const previous = getScoreSegments(previousMasterRecords);

  const changes = {};
  Object.keys(current).forEach(segment => {
    changes[segment] = current[segment] - previous[segment];
  });

  return { current, previous, changes };
}

/**
 * 流入ルート別の成約率を集計
 * @param {Array} masterRecords - 企業マスタのレコード配列
 * @returns {Object} {"①紹介": {contracts: number, total: number, rate: string}, ...}
 */
function getRouteConversionRates(masterRecords) {
  const routes = ["①紹介", "②手紙DM", "③ミカタ経由", "④開拓架電"];
  const result = {};

  routes.forEach(route => {
    const total = masterRecords.filter(r => {
      const routesArray = r["流入ルート"];
      return Array.isArray(routesArray) ? routesArray.includes(route) : false;
    }).length;

    const contracts = masterRecords.filter(r => {
      const routesArray = r["流入ルート"];
      const hasRoute = Array.isArray(routesArray) ? routesArray.includes(route) : false;
      return hasRoute && r["成約"] === true;
    }).length;

    result[route] = {
      total,
      contracts,
      rate: total === 0 ? "0.0%" : (contracts / total * 100).toFixed(1) + "%"
    };
  });

  return result;
}
