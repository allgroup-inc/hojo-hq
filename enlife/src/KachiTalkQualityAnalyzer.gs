/**
 * KachiTalk Call Quality Analysis System
 *
 * Purpose: Analyze enLife salespeople's call content against 6-step sales process checklist
 * and correlate with actual sales performance data
 *
 * Salespeople (営業マン): 前原芳乃, 奈須章, 下地健太, 幸良妃奈代, 徳元孝樹, 喜納礼奈, 名嘉山望, 狩俣亜希乃
 * 6-Step Process: ①アプローチ ②ヒアリング ③提案 ④クロージング ⑤申込契約 ⑥紹介入手
 */

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

const SALES_PROCESS_STEPS = [
  { id: '①', name: 'アプローチ（名乗り）', desc: '自己紹介・信頼構築' },
  { id: '②', name: 'ヒアリング', desc: '顧客の問題・ニーズ把握' },
  { id: '③', name: '提案', desc: '顧客ニーズに合致した提案' },
  { id: '④', name: 'クロージング', desc: '申込への案内' },
  { id: '⑤', name: '申込・契約', desc: '申込手続き' },
  { id: '⑥', name: '紹介入手', desc: '紹介顧客獲得' }
];

const SHEET_NAMES = {
  kachitalk_logs: 'カチトークログ',
  quality_analysis: '品質分析',
  checklist_compliance: 'チェックリスト合致度',
  correlation: '成績相関分析',
  summary: 'サマリー'
};

/**
 * Initialize KachiTalk analysis sheets
 */
function ensureKachiTalkAnalysisTabs() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Create/ensure all required sheets
  for (const [key, sheetName] of Object.entries(SHEET_NAMES)) {
    let sheet = ss.getSheetByName(sheetName);
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
    }
  }

  // Initialize headers
  initializeKachiTalkLogsHeaders_(ss.getSheetByName(SHEET_NAMES.kachitalk_logs));
  initializeQualityAnalysisHeaders_(ss.getSheetByName(SHEET_NAMES.quality_analysis));
  initializeChecklistComplianceHeaders_(ss.getSheetByName(SHEET_NAMES.checklist_compliance));
  initializeCorrelationHeaders_(ss.getSheetByName(SHEET_NAMES.correlation));
  initializeSummaryHeaders_(ss.getSheetByName(SHEET_NAMES.summary));

  console.log('✓ KachiTalk分析タブの初期化完了');
}

/**
 * Initialize headers for raw KachiTalk logs
 */
function initializeKachiTalkLogsHeaders_(sheet) {
  sheet.clear();
  const headers = [
    '営業マン',
    '日時',
    '顧客名',
    '通話時間（分）',
    '通話内容_要約',
    '①アプローチ_実施',
    '②ヒアリング_実施',
    '③提案_実施',
    '④クロージング_実施',
    '⑤申込契約_実施',
    '⑥紹介入手_実施',
    '品質スコア',
    'メモ'
  ];
  sheet.appendRow(headers);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#4a90e2');
}

/**
 * Initialize headers for quality analysis summary
 */
function initializeQualityAnalysisHeaders_(sheet) {
  sheet.clear();
  const headers = [
    '営業マン',
    '分析対象期間',
    '通話件数',
    '平均通話時間',
    '①実施率',
    '②実施率',
    '③実施率',
    '④実施率',
    '⑤実施率',
    '⑥実施率',
    '平均品質スコア',
    '評価'
  ];
  sheet.appendRow(headers);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#4a90e2');
}

/**
 * Initialize headers for checklist compliance matrix
 */
function initializeChecklistComplianceHeaders_(sheet) {
  sheet.clear();
  const headers = ['営業マン', '①アプローチ', '②ヒアリング', '③提案', '④クロージング', '⑤申込契約', '⑥紹介入手', '総合'];
  sheet.appendRow(headers);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#50c878');
}

/**
 * Initialize headers for correlation analysis with KPI
 */
function initializeCorrelationHeaders_(sheet) {
  sheet.clear();
  const headers = [
    '営業マン',
    '品質スコア',
    '①実施率',
    '②実施率',
    '③実施率',
    '④実施率',
    '⑤実施率',
    '⑥実施率',
    'ANP実績_8月',
    '契約件数_8月',
    'ANP実績_9月',
    '契約件数_9月',
    '8月成績',
    '9月成績',
    '改善領域'
  ];
  sheet.appendRow(headers);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#ff9800');
}

/**
 * Initialize headers for summary dashboard
 */
function initializeSummaryHeaders_(sheet) {
  sheet.clear();

  // Title
  sheet.getRange('A1').setValue('【エンライフ営業品質管理ダッシュボード】').setFontSize(16).setFontWeight('bold');

  // Team average section
  sheet.getRange('A3').setValue('チーム平均品質スコア').setFontWeight('bold');
  sheet.getRange('A4').setValue('スコア');
  sheet.getRange('B4').setValue('=IFERROR(AVERAGE(\'品質分析\'!L2:L9),"-")').setHorizontalAlignment('center');

  // Top performer
  sheet.getRange('A6').setValue('トップパフォーマー（品質×売上）').setFontWeight('bold');
  sheet.getRange('A7').setValue('営業マン');
  sheet.getRange('B7').setValue('品質スコア');
  sheet.getRange('C7').setValue('9月成績');
}

/**
 * Analyze KachiTalk logs and update quality metrics
 * @param {string} month - '8月' or '9月'
 */
function analyzeKachiTalkQuality(month = '9月') {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const kachitalkSheet = ss.getSheetByName(SHEET_NAMES.kachitalk_logs);
  const analysisSheet = ss.getSheetByName(SHEET_NAMES.quality_analysis);

  // Get data from kachitalk logs
  const data = kachitalkSheet.getDataRange().getValues();

  // Process each salesperson
  const analysis = {};
  STAFF_NAMES.forEach(name => {
    analysis[name] = calculateMetricsForSalesperson_(data, name, month);
  });

  // Write to analysis sheet
  analysisSheet.clearContents();
  analysisSheet.appendRow([
    '営業マン', '分析対象期間', '通話件数', '平均通話時間',
    '①実施率', '②実施率', '③実施率', '④実施率', '⑤実施率', '⑥実施率',
    '平均品質スコア', '評価'
  ]);

  Object.entries(analysis).forEach(([name, metrics]) => {
    const rating = metrics.averageScore >= 85 ? '優秀' : metrics.averageScore >= 70 ? '良好' : '要改善';
    analysisSheet.appendRow([
      name, month, metrics.callCount, metrics.avgCallTime,
      metrics.step1Rate, metrics.step2Rate, metrics.step3Rate, metrics.step4Rate, metrics.step5Rate, metrics.step6Rate,
      metrics.averageScore, rating
    ]);
  });

  console.log('✓ 品質分析の更新完了: ' + month);
}

/**
 * Calculate metrics for a single salesperson
 */
function calculateMetricsForSalesperson_(data, staffName, month) {
  const rows = data.filter((row, idx) => idx > 0 && row[0] === staffName && String(row[1]).includes(month));

  if (rows.length === 0) {
    return {
      callCount: 0,
      avgCallTime: 0,
      step1Rate: 0,
      step2Rate: 0,
      step3Rate: 0,
      step4Rate: 0,
      step5Rate: 0,
      step6Rate: 0,
      averageScore: 0
    };
  }

  let totalTime = 0;
  let scores = [];
  const stepCounts = [0, 0, 0, 0, 0, 0];

  rows.forEach(row => {
    totalTime += parseInt(row[3]) || 0;
    scores.push(parseInt(row[11]) || 0);

    // Count step execution (columns 5-10)
    for (let i = 0; i < 6; i++) {
      if (row[5 + i] === true || row[5 + i] === 'TRUE' || row[5 + i] === '○') {
        stepCounts[i]++;
      }
    }
  });

  return {
    callCount: rows.length,
    avgCallTime: Math.round(totalTime / rows.length * 10) / 10,
    step1Rate: Math.round((stepCounts[0] / rows.length) * 100),
    step2Rate: Math.round((stepCounts[1] / rows.length) * 100),
    step3Rate: Math.round((stepCounts[2] / rows.length) * 100),
    step4Rate: Math.round((stepCounts[3] / rows.length) * 100),
    step5Rate: Math.round((stepCounts[4] / rows.length) * 100),
    step6Rate: Math.round((stepCounts[5] / rows.length) * 100),
    averageScore: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10
  };
}

/**
 * Build correlation analysis between quality and sales performance
 */
function buildCorrelationAnalysis() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const qualitySheet = ss.getSheetByName(SHEET_NAMES.quality_analysis);
  const correlationSheet = ss.getSheetByName(SHEET_NAMES.correlation);
  const perfSheet = ss.getSheetByName('KPI分析');

  if (!perfSheet) {
    console.log('※ KPI分析シートが見つかりません。KPI分析シートを作成してからご実行ください');
    return;
  }

  // Get quality data
  const qualityData = qualitySheet.getDataRange().getValues();
  const perfData = perfSheet.getDataRange().getValues();

  // Build correlation matrix
  correlationSheet.clearContents();
  correlationSheet.appendRow([
    '営業マン', '品質スコア', '①実施率', '②実施率', '③実施率', '④実施率', '⑤実施率', '⑥実施率',
    'ANP実績_8月', '契約件数_8月', 'ANP実績_9月', '契約件数_9月', '8月成績', '9月成績', '改善領域'
  ]);

  // Fill in data (simplified - actual implementation would cross-reference KPI sheet)
  qualityData.forEach((row, idx) => {
    if (idx > 0 && row[0]) {
      correlationSheet.appendRow([
        row[0], row[10], row[4], row[5], row[6], row[7], row[8], row[9],
        '-', '-', '-', '-', '-', '-', ''
      ]);
    }
  });

  console.log('✓ 相関分析の更新完了');
}

/**
 * Get summary for dashboard
 */
function getSalesQualitySummary() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const qualitySheet = ss.getSheetByName(SHEET_NAMES.quality_analysis);
  const data = qualitySheet.getDataRange().getValues();

  let topPerfomer = { name: '', score: 0 };
  let avgScore = 0;
  let count = 0;

  data.forEach((row, idx) => {
    if (idx > 0 && row[0]) {
      const score = parseFloat(row[10]) || 0;
      avgScore += score;
      count++;

      if (score > topPerfomer.score) {
        topPerfomer = { name: row[0], score: score };
      }
    }
  });

  avgScore = Math.round((avgScore / count) * 10) / 10;

  console.log('\n【営業品質管理サマリー】');
  console.log('チーム平均スコア: ' + avgScore);
  console.log('トップパフォーマー: ' + topPerfomer.name + ' (' + topPerfomer.score + '点)');
  console.log('対象営業マン数: ' + count);
}
