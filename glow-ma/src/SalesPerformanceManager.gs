/**
 * GLOW営業成績管理システム
 *
 * 営業マンの月別KPI実績を管理・集計・分析するシステム。
 * 使用方法:
 * 1. ensureSalesPerformanceTabs() で「営業成績（月別）」「KPI分析」タブを作成
 * 2. importSalesPerformanceFromExcel() で Excelファイルからデータインポート
 * 3. updatePerformanceAnalysis() で平均値・ランキングを自動計算
 */

const SALES_PERFORMANCE_SHEET_NAME = "営業成績（月別）";
const PERFORMANCE_ANALYSIS_SHEET_NAME = "KPI分析";
const STAFF_NAMES = [
  '前原　芳乃',
  '奈須　章',
  '下地　健太',
  '幸良　妃奈代',
  '徳元　孝樹',
  '喜納　礼奈',
  '名嘉山　望',
  '狩俣　亜希乃'
];

const KPI_HEADERS = [
  'ANP実績',
  '契約件数',
  '契約世帯',
  '世帯取り',
  '世帯単価',
  '世帯率',
  '落ち率',
  '新規訪問',
  '再アポ訪問',
  'その他訪問',
  '合計訪問',
  '自己アポ作成',
  '自己アポ訪問実績',
  '供給アポ実績'
];

const MONTHS = ['5月', '6月', '7月', '8月', '9月'];

/**
 * 営業成績管理タブの初期化
 */
function ensureSalesPerformanceTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // 「営業成績（月別）」タブの作成
  var performanceSheet = ensureSalesTab_(ss, SALES_PERFORMANCE_SHEET_NAME);
  setupSalesPerformanceHeaders_(performanceSheet);

  // 「KPI分析」タブの作成
  var analysisSheet = ensureSalesTab_(ss, PERFORMANCE_ANALYSIS_SHEET_NAME);
  setupAnalysisHeaders_(analysisSheet);

  Logger.log("✓ 営業成績管理タブの初期化完了");
}

function ensureSalesTab_(spreadsheet, sheetName) {
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  return sheet;
}

/**
 * 「営業成績（月別）」シートのヘッダー設定
 * 形式: 営業マン名 | 月 | KPI1 | KPI2 | ... | KPI14
 */
function setupSalesPerformanceHeaders_(sheet) {
  var headers = ['営業マン', '月'].concat(KPI_HEADERS);
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
}

/**
 * 「KPI分析」シートのヘッダー設定
 * 形式: KPI指標 | 5月平均 | 6月平均 | 7月平均 | 8月平均 | 9月平均 | 総平均 | トップ（5月） | トップ（6月） | ...
 */
function setupAnalysisHeaders_(sheet) {
  var headers = ['KPI指標', '5月平均', '6月平均', '7月平均', '8月平均', '9月平均', '総平均'];
  MONTHS.forEach(function(month) {
    headers.push('トップ（' + month + '）');
  });
  headers.push('総トップ');
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
}

/**
 * Excelファイルからのデータインポート（月別形式）
 *
 * 呼び出し例: importSalesPerformanceFromExcel()
 * 事前に以下をシートに手動で配置:
 * - 5月〜9月の月別データ（営業マン名 × KPI指標）
 */
function importSalesPerformanceFromExcel() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SALES_PERFORMANCE_SHEET_NAME);
  if (!sheet) {
    Logger.log("✗ エラー: 営業成績（月別）シートが見つかりません");
    return;
  }

  // データ構造: {営業マン: {月: {KPI: 値}}}
  var data = {
    '前原　芳乃': {
      '5月': {'ANP実績': 0, '契約件数': 0, '契約世帯': 0, '世帯取り': 0, '世帯単価': 0, '世帯率': 0, '落ち率': 0, '新規訪問': 0, '再アポ訪問': 0, 'その他訪問': 0, '合計訪問': 0, '自己アポ作成': 0, '自己アポ訪問実績': 0, '供給アポ実績': 0},
    },
  };

  // 実装時は Excelファイルから実データを抽出する
  Logger.log("📝 Excelデータインポート機能は手動設定が必要です。");
  Logger.log("   営業成績（月別）シートに営業マン×月×KPI形式でデータを入力してください");
}

/**
 * 営業成績分析の自動更新
 * 月別平均値、ランキングを計算して「KPI分析」シートに反映
 */
function updatePerformanceAnalysis() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var perfSheet = ss.getSheetByName(SALES_PERFORMANCE_SHEET_NAME);
  var analysisSheet = ss.getSheetByName(PERFORMANCE_ANALYSIS_SHEET_NAME);

  if (!perfSheet || !analysisSheet) {
    Logger.log("✗ エラー: 必要なシートが見つかりません");
    return;
  }

  // データ読み込み
  var perfData = readPerformanceData_(perfSheet);

  // KPI ごとの分析
  var analysisData = [];
  KPI_HEADERS.forEach(function(kpi) {
    var row = calculateKpiAnalysis_(kpi, perfData);
    analysisData.push(row);
  });

  // 分析結果をシートに書き込み
  writeAnalysisResults_(analysisSheet, analysisData);
  Logger.log("✓ KPI分析の更新完了: " + KPI_HEADERS.length + " 指標を集計");
}

/**
 * 営業成績シートからデータを読み込む
 * 戻り値: {営業マン: {月: {KPI: 値}}}
 */
function readPerformanceData_(sheet) {
  var data = {};
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();

  if (lastRow <= 1) {
    return data;
  }

  var range = sheet.getRange(2, 1, lastRow - 1, lastCol);
  var values = range.getValues();

  values.forEach(function(row) {
    var staffName = row[0];
    var month = row[1];

    if (!staffName || !month) return;

    if (!data[staffName]) data[staffName] = {};
    if (!data[staffName][month]) data[staffName][month] = {};

    // KPI値をセット（列2以降）
    for (var i = 0; i < KPI_HEADERS.length; i++) {
      var kpi = KPI_HEADERS[i];
      var value = parseFloat(row[2 + i]) || 0;
      data[staffName][month][kpi] = value;
    }
  });

  return data;
}

/**
 * KPI指標ごとの分析を計算
 */
function calculateKpiAnalysis_(kpi, perfData) {
  var row = [kpi];

  // 月別平均値の計算
  var monthlyAverages = {};
  MONTHS.forEach(function(month) {
    var values = [];
    Object.keys(perfData).forEach(function(staff) {
      if (perfData[staff][month] && perfData[staff][month][kpi] !== undefined) {
        values.push(perfData[staff][month][kpi]);
      }
    });
    var avg = values.length > 0 ? values.reduce(function(a, b) { return a + b; }) / values.length : 0;
    monthlyAverages[month] = avg;
    row.push(avg);
  });

  // 総平均
  var allValues = [];
  MONTHS.forEach(function(month) {
    Object.keys(perfData).forEach(function(staff) {
      if (perfData[staff][month] && perfData[staff][month][kpi] !== undefined) {
        allValues.push(perfData[staff][month][kpi]);
      }
    });
  });
  var totalAvg = allValues.length > 0 ? allValues.reduce(function(a, b) { return a + b; }) / allValues.length : 0;
  row.push(totalAvg);

  // 月別トップパフォーマー
  MONTHS.forEach(function(month) {
    var topStaff = findTopPerformer_(kpi, month, perfData);
    row.push(topStaff || "—");
  });

  // 総トップパフォーマー
  var overallTop = findOverallTopPerformer_(kpi, perfData);
  row.push(overallTop || "—");

  return row;
}

/**
 * 指定月の KPI トップパフォーマーを探す
 */
function findTopPerformer_(kpi, month, perfData) {
  var maxValue = -Infinity;
  var topStaff = null;

  Object.keys(perfData).forEach(function(staff) {
    if (perfData[staff][month] && perfData[staff][month][kpi] !== undefined) {
      var value = perfData[staff][month][kpi];
      if (value > maxValue) {
        maxValue = value;
        topStaff = staff;
      }
    }
  });

  return topStaff;
}

/**
 * KPI の総合トップパフォーマーを探す（全月の平均値で判定）
 */
function findOverallTopPerformer_(kpi, perfData) {
  var staffAverages = {};

  Object.keys(perfData).forEach(function(staff) {
    var values = [];
    MONTHS.forEach(function(month) {
      if (perfData[staff][month] && perfData[staff][month][kpi] !== undefined) {
        values.push(perfData[staff][month][kpi]);
      }
    });
    if (values.length > 0) {
      staffAverages[staff] = values.reduce(function(a, b) { return a + b; }) / values.length;
    }
  });

  var topStaff = null;
  var maxAvg = -Infinity;
  Object.keys(staffAverages).forEach(function(staff) {
    if (staffAverages[staff] > maxAvg) {
      maxAvg = staffAverages[staff];
      topStaff = staff;
    }
  });

  return topStaff;
}

/**
 * 分析結果をシートに書き込む
 */
function writeAnalysisResults_(sheet, analysisData) {
  // 既存データを削除（ヘッダー以外）
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.deleteRows(2, lastRow - 1);
  }

  if (analysisData.length === 0) {
    return;
  }

  // 新規データを書き込み
  var range = sheet.getRange(2, 1, analysisData.length, analysisData[0].length);
  range.setValues(analysisData);

  // 数値カラムのフォーマット
  var numericColumns = [2, 3, 4, 5, 6, 7]; // 月別平均値
  numericColumns.forEach(function(col) {
    sheet.getRange(2, col, analysisData.length, 1).setNumberFormat("0.00");
  });
}

/**
 * 月別営業成績のサマリーを取得（ロギング用）
 */
function getSalesPerformanceSummary() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SALES_PERFORMANCE_SHEET_NAME);

  if (!sheet) {
    Logger.log("✗ 営業成績（月別）シートが見つかりません");
    return;
  }

  var perfData = readPerformanceData_(sheet);

  Logger.log("【営業成績サマリー】");
  STAFF_NAMES.forEach(function(staff) {
    if (perfData[staff]) {
      Logger.log("\n" + staff + ":");
      MONTHS.forEach(function(month) {
        if (perfData[staff][month]) {
          var kpis = perfData[staff][month];
          Logger.log("  " + month + ": ANP実績=" + kpis['ANP実績'] + " 契約件数=" + kpis['契約件数'] + " 合計訪問=" + kpis['合計訪問']);
        }
      });
    }
  });
}
