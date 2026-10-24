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
  summary: 'サマリー',
  consolidated_dashboard: '統合ダッシュボード',
  performance_data: '営業成績データ'
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
  initializeConsolidatedDashboardHeaders_(ss.getSheetByName(SHEET_NAMES.consolidated_dashboard));
  initializePerformanceDataHeaders_(ss.getSheetByName(SHEET_NAMES.performance_data));

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
 * Initialize consolidated dashboard with all data in one view
 */
function initializeConsolidatedDashboardHeaders_(sheet) {
  sheet.clear();

  // Main title
  sheet.getRange('A1:H1').merge().setValue('【KachiTalk品質管理 統合ダッシュボード】')
    .setFontSize(18).setFontWeight('bold').setHorizontalAlignment('center')
    .setBackground('#1f4788').setFontColor('#ffffff');

  // Refresh date
  sheet.getRange('A2').setValue('更新日時: ').setFontWeight('bold');
  sheet.getRange('B2').setValue('=NOW()').setNumberFormat('yyyy/m/d hh:mm:ss');

  // Section 1: Team overview (Row 4-6)
  sheet.getRange('A4:B4').merge().setValue('チーム全体統計').setFontWeight('bold').setBackground('#e8f4f8');
  sheet.getRange('A5').setValue('平均品質スコア');
  sheet.getRange('B5').setValue('=IFERROR(AVERAGE(品質分析!K2:K9),"-")').setHorizontalAlignment('center').setNumberFormat('0.0');
  sheet.getRange('C5').setValue('点');

  sheet.getRange('A6').setValue('総通話件数');
  sheet.getRange('B6').setValue('=IFERROR(SUM(品質分析!C2:C9),"-")').setHorizontalAlignment('center');
  sheet.getRange('C6').setValue('件');

  // Section 2: Rankings (Row 8-17)
  sheet.getRange('A8:H8').merge().setValue('営業マン別品質スコア・実施率一覧').setFontWeight('bold').setBackground('#e8f4f8');

  const headers = ['順位', '営業マン', '品質スコア', '評価', '①実施', '②実施', '③実施', '④実施'];
  sheet.getRange('A9:H9').setValues([headers]).setFontWeight('bold').setBackground('#4a90e2').setFontColor('#ffffff');

  // Placeholder rows for rankings (actual data filled by buildConsolidatedDashboard)
  for (let i = 0; i < 8; i++) {
    sheet.getRange(`A${10 + i}:H${10 + i}`).setBackground(i % 2 === 0 ? '#ffffff' : '#f5f5f5');
  }

  // Section 3: 6-step implementation rates (Row 19-20)
  sheet.getRange('A19:H19').merge().setValue('⑤申込・⑥紹介の実施率分析').setFontWeight('bold').setBackground('#e8f4f8');
  const strengthHeaders = ['営業マン', '⑤申込契約', '⑥紹介入手', '改善優先度'];
  sheet.getRange('A20:D20').setValues([strengthHeaders.slice(0, 4)]).setFontWeight('bold').setBackground('#50c878').setFontColor('#ffffff');

  for (let i = 0; i < 8; i++) {
    sheet.getRange(`A${21 + i}:D${21 + i}`).setBackground(i % 2 === 0 ? '#ffffff' : '#f5f5f5');
  }

  // Section 4: Performance data (訪問記録) (Row 31-32)
  sheet.getRange('A31:F31').merge().setValue('営業マン訪問記録（KachiTalk admin）').setFontWeight('bold').setBackground('#e8f4f8');
  const perfHeaders = ['営業マン', '対象月', '訪問件数', '平均スコア', '平均完了率', 'OK件数'];
  sheet.getRange('A32:F32').setValues([perfHeaders]).setFontWeight('bold').setBackground('#4caf50').setFontColor('#ffffff');

  for (let i = 0; i < 8; i++) {
    sheet.getRange(`A${33 + i}:F${33 + i}`).setBackground(i % 2 === 0 ? '#ffffff' : '#f5f5f5');
  }

  // Set column widths
  sheet.setColumnWidth(1, 120);  // A
  sheet.setColumnWidth(2, 120);  // B
  sheet.setColumnWidth(3, 100);  // C
  sheet.setColumnWidth(4, 80);   // D
  sheet.setColumnWidth(5, 80);   // E
  sheet.setColumnWidth(6, 80);   // F
  sheet.setColumnWidth(7, 80);   // G
  sheet.setColumnWidth(8, 80);   // H
  sheet.setColumnWidth(9, 100);  // I
  sheet.setColumnWidth(10, 100); // J
}

/**
 * Initialize headers for performance data (営業マン訪問記録)
 */
function initializePerformanceDataHeaders_(sheet) {
  sheet.clear();
  const headers = [
    '営業マン',
    '対象月',
    '訪問件数',
    '平均スコア',
    '平均完了率',
    'OK件数'
  ];
  sheet.appendRow(headers);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#4caf50');

  // Column widths
  sheet.setColumnWidth(1, 120);  // 営業マン
  sheet.setColumnWidth(2, 100);  // 対象月
  sheet.setColumnWidth(3, 100);  // 訪問件数
  sheet.setColumnWidth(4, 100);  // 平均スコア
  sheet.setColumnWidth(5, 100);  // 平均完了率
  sheet.setColumnWidth(6, 100);  // OK件数
}

/**
 * Import performance data from CSV
 * Expects CSV format: 営業マン, 対象月, 訪問件数, 平均スコア, 平均完了率, OK件数
 */
function importPerformanceDataFromCSV(csvText) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const perfSheet = ss.getSheetByName(SHEET_NAMES.performance_data);

  if (!perfSheet) {
    console.log('✗ 営業成績データシートが見つかりません');
    return false;
  }

  // Clear existing data (keep headers)
  const range = perfSheet.getRange('A2:Z1000');
  range.clearContent();

  // Parse CSV and append rows
  const lines = csvText.split('\n').filter(line => line.trim());
  let rowCount = 0;

  lines.forEach((line, idx) => {
    if (idx === 0) return; // Skip header
    const fields = line.split(',').map(f => f.trim());
    if (fields[0]) {
      perfSheet.appendRow(fields);
      rowCount++;
    }
  });

  console.log(`✓ 営業成績データを${rowCount}件インポート`);
  return true;
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

  // Update consolidated dashboard
  buildConsolidatedDashboard();

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
 * Load performance data from performance sheet
 */
function loadPerformanceData_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const perfSheet = ss.getSheetByName(SHEET_NAMES.performance_data);

  if (!perfSheet) {
    return {};
  }

  const data = perfSheet.getDataRange().getValues();
  const perfData = {};

  data.forEach((row, idx) => {
    if (idx > 0 && row[0]) {
      const key = row[0] + '_' + row[1]; // name_month
      perfData[key] = {
        name: row[0],
        month: row[1],
        visitCount: row[2] || 0,
        avgScore: parseFloat(row[3]) || 0,
        avgCompletion: parseFloat(row[4]) || 0,
        okCount: row[5] || 0
      };
    }
  });

  return perfData;
}

/**
 * Build consolidated dashboard with all analysis data
 */
function buildConsolidatedDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const qualitySheet = ss.getSheetByName(SHEET_NAMES.quality_analysis);
  const dashboardSheet = ss.getSheetByName(SHEET_NAMES.consolidated_dashboard);

  const data = qualitySheet.getDataRange().getValues();
  const perfData = loadPerformanceData_();

  // Parse quality analysis data
  const staffData = [];
  data.forEach((row, idx) => {
    if (idx > 0 && row[0]) {
      staffData.push({
        name: row[0],
        month: row[1] || '9月',
        callCount: row[2] || 0,
        avgCallTime: row[3] || 0,
        step1Rate: row[4] || 0,
        step2Rate: row[5] || 0,
        step3Rate: row[6] || 0,
        step4Rate: row[7] || 0,
        step5Rate: row[8] || 0,
        step6Rate: row[9] || 0,
        score: parseFloat(row[10]) || 0,
        rating: row[11] || '要改善'
      });
    }
  });

  // Merge with performance data where available
  staffData.forEach(staff => {
    const perfKey = staff.name + '_' + staff.month;
    if (perfData[perfKey]) {
      staff.visitCount = perfData[perfKey].visitCount;
      staff.perfScore = perfData[perfKey].avgScore;
      staff.completion = perfData[perfKey].avgCompletion;
    }
  });

  // Sort by score (descending)
  staffData.sort((a, b) => b.score - a.score);

  // Fill rankings section (rows 10-17)
  staffData.forEach((staff, idx) => {
    const rowNum = 10 + idx;
    const colors = staff.score >= 85 ? '#c8e6c9' : staff.score >= 70 ? '#fff9c4' : '#ffccbc';

    dashboardSheet.getRange(`A${rowNum}`).setValue(idx + 1).setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`B${rowNum}`).setValue(staff.name).setBackground(colors);
    dashboardSheet.getRange(`C${rowNum}`).setValue(staff.score).setHorizontalAlignment('center').setNumberFormat('0.0').setBackground(colors);
    dashboardSheet.getRange(`D${rowNum}`).setValue(staff.rating).setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`E${rowNum}`).setValue(staff.step1Rate + '%').setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`F${rowNum}`).setValue(staff.step2Rate + '%').setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`G${rowNum}`).setValue(staff.step3Rate + '%').setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`H${rowNum}`).setValue(staff.step4Rate + '%').setHorizontalAlignment('center').setBackground(colors);
  });

  // Fill improvement focus section (rows 21-28)
  staffData.forEach((staff, idx) => {
    const rowNum = 21 + idx;

    // Determine improvement priority (lower step5/step6 rates = higher priority)
    const avgStep56 = (staff.step5Rate + staff.step6Rate) / 2;
    let priority = '◎良好';
    if (avgStep56 < 50) priority = '◆要注力';
    else if (avgStep56 < 75) priority = '▲要改善';

    dashboardSheet.getRange(`A${rowNum}`).setValue(staff.name);
    dashboardSheet.getRange(`B${rowNum}`).setValue(staff.step5Rate + '%').setHorizontalAlignment('center').setNumberFormat('0');
    dashboardSheet.getRange(`C${rowNum}`).setValue(staff.step6Rate + '%').setHorizontalAlignment('center').setNumberFormat('0');
    dashboardSheet.getRange(`D${rowNum}`).setValue(priority).setHorizontalAlignment('center');

    // Color by priority
    let bgColor = '#ffffff';
    if (priority === '◆要注力') bgColor = '#ffcccc';
    else if (priority === '▲要改善') bgColor = '#ffe0b2';
    else bgColor = '#c8e6c9';

    dashboardSheet.getRange(`A${rowNum}:D${rowNum}`).setBackground(bgColor);
  });

  // Fill performance data section (rows 33-40)
  staffData.forEach((staff, idx) => {
    const rowNum = 33 + idx;
    const colors = idx % 2 === 0 ? '#ffffff' : '#f5f5f5';

    dashboardSheet.getRange(`A${rowNum}`).setValue(staff.name).setBackground(colors);
    dashboardSheet.getRange(`B${rowNum}`).setValue(staff.month || '9月').setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`C${rowNum}`).setValue(staff.visitCount || '-').setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`D${rowNum}`).setValue(staff.perfScore || '-').setHorizontalAlignment('center').setNumberFormat('0.0').setBackground(colors);
    dashboardSheet.getRange(`E${rowNum}`).setValue(staff.completion ? staff.completion + '%' : '-').setHorizontalAlignment('center').setBackground(colors);
    dashboardSheet.getRange(`F${rowNum}`).setValue(staff.okCount || '-').setHorizontalAlignment('center').setBackground(colors);
  });

  console.log('✓ 統合ダッシュボードの更新完了');
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
