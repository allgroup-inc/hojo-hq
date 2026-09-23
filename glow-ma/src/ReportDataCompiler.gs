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
