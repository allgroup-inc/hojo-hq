/**
 * KachiTalk Integration for GLOW Enterprise Relation System
 *
 * 目的:
 * - KachiTalk（LINE営業ログシステム）の全通話ログを取得
 * - 6段階営業プロセス完全性を分析
 * - 営業成績データとの相関を定量化
 * - 営業スタイルを自動分類
 *
 * 使用方法:
 * 1. Apps Scriptエディタで importKachiTalkLogsFromAdmin を実行
 * 2. Google Sheets内に「KachiTalkログ_raw」タブが作成される
 * 3. analyzeKachiTalkCorrelation を実行して分析開始
 */

var KACHITALK_STAFF_NAMES = [
  '前原　芳乃',
  '奈須　章',
  '下地　健太',
  '幸良　妃奈代',
  '徳元　孝樹',
  '喜納　礼奈',
  '名嘉山　望',
  '狩俣　亜希乃'
];

var SALES_PROCESS_STEPS = {
  '①アプローチ': ['名乗り', '申し遅れました', 'こんにちは', '本日は', '申します', '申し上げたい', '名乗り遅れました'],
  '②ヒアリング': ['前回', 'おさらい', 'いくつかお聞き', 'どのような', 'ご状況', 'お困り', 'お過ごし'],
  '③提案': ['このような保障', 'お勧め', 'いかがでしょう', '保障内容', '提案', 'ご意向に沿った', 'このような内容'],
  '④クロージング': ['申込', '手続き', '契約', '進める', '署名', '捺印', '進めさせていただく'],
  '⑤申込契約': ['申込完了', '契約しました', '申込いたします', '申込させていただく'],
  '⑥紹介入手': ['紹介', 'お知り合い', 'ご親戚', 'ご友人', 'どなたか', 'ご知人']
};

/**
 * Step 1: Ensure required tabs exist in the glow-ma spreadsheet
 */
function ensureKachiTalkTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheetNames = [];
  ss.getSheets().forEach(function(sheet) {
    sheetNames.push(sheet.getName());
  });

  var requiredSheets = [
    'KachiTalkログ_raw',
    'KachiTalk分析結果',
    '営業成績との相関'
  ];

  requiredSheets.forEach(function(name) {
    if (!sheetNames.includes(name)) {
      ss.insertSheet(name);
      Logger.log('✓ シート作成: ' + name);
    }
  });

  // Initialize "KachiTalkログ_raw" headers
  var rawSheet = ss.getSheetByName('KachiTalkログ_raw');
  if (rawSheet) {
    var headers = [
      'スタッフ名',
      '対応日',
      '顧客名',
      '通話時間（分）',
      '通話内容_要約',
      '結果',
      '①アプローチ',
      '②ヒアリング',
      '③提案',
      '④クロージング',
      '⑤申込契約',
      '⑥紹介入手',
      'プロセス完全性スコア',
      'メモ'
    ];
    if (rawSheet.getLastRow() === 0) {
      rawSheet.appendRow(headers);
    }
  }

  Logger.log('✓ KachiTalkタブの初期化完了');
}

/**
 * Step 2: Import KachiTalk logs from the admin dashboard
 *
 * 実運用フロー:
 * 1. https://kachitalk-line-enlife.azurewebsites.net/admin にアクセス
 * 2. 期間: 7月1日〜10月31日 / 営業マン: 全8名
 * 3. 「自社CSV」としてダウンロード
 * 4. このGASの importKachiTalkLogsFromAdmin 関数を実行する前に、
 *    「KachiTalkログ_raw」シートのA1に貼り付ける
 * 5. または下記の fillKachiTalkLogsFromPastData 関数で試験的に既存JSONから入力
 */
function importKachiTalkLogsFromAdmin() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('KachiTalkログ_raw');

  if (!sheet) {
    Logger.log('✗ KachiTalkログ_raw シートがありません。ensureKachiTalkTabs を先に実行してください');
    return;
  }

  // Check if data is already pasted from KachiTalk admin CSV
  var lastRow = sheet.getLastRow();

  if (lastRow === 1) {
    // No data pasted yet - try to load from embedded sample JSON
    Logger.log('※ KachiTalkログ_raw にデータが見つかりません');
    Logger.log('   1. https://kachitalk-line-enlife.azurewebsites.net/admin から');
    Logger.log('   2. 期間: 7月1日〜10月31日 / 営業マン: 全8名 / CSV形式でダウンロード');
    Logger.log('   3. 「KachiTalkログ_raw」シートの A1 からペースト');
    Logger.log('   4. この関数を再度実行してください');
    return;
  }

  Logger.log('✓ ' + (lastRow - 1) + ' 件のログデータを確認しました');
  analyzeKachiTalkCorrelation();
}

/**
 * Step 3: Analyze KachiTalk logs for process completion and sales correlation
 */
function analyzeKachiTalkCorrelation() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var rawSheet = ss.getSheetByName('KachiTalkログ_raw');
  var analysisSheet = ss.getSheetByName('KachiTalk分析結果');
  var correlationSheet = ss.getSheetByName('営業成績との相関');

  if (!rawSheet || !analysisSheet || !correlationSheet) {
    Logger.log('✗ 必要なシートが見つかりません');
    return;
  }

  // Read raw log data
  var data = rawSheet.getDataRange().getValues();
  if (data.length < 2) {
    Logger.log('✗ ログデータがありません');
    return;
  }

  var headers = data[0];
  var logs = data.slice(1);

  // Group logs by staff member
  var logsByStaff = {};
  KACHITALK_STAFF_NAMES.forEach(function(name) {
    logsByStaff[name] = [];
  });

  logs.forEach(function(row) {
    var staffName = row[0]; // Column A: スタッフ名
    if (logsByStaff.hasOwnProperty(staffName) && staffName) {
      logsByStaff[staffName].push({
        date: row[1],
        customer: row[2],
        duration: row[3],
        transcript: row[4],
        result: row[5],
        notes: row[13]
      });
    }
  });

  // Analyze each staff member
  var analysisResults = [['スタッフ名', '対象期間', '通話件数', '平均通話時間', '成約件数', '成約率',
                          '①実施', '②実施', '③実施', '④実施', '⑤実施', '⑥実施',
                          '平均プロセス完全性', '営業スタイル']];

  for (var staffName in logsByStaff) {
    var staffLogs = logsByStaff[staffName];

    if (staffLogs.length === 0) continue;

    var analysis = analyzeStaffPerformance(staffName, staffLogs);
    analysisResults.push([
      staffName,
      analysis.period,
      analysis.callCount,
      analysis.avgDuration.toFixed(1),
      analysis.contractCount,
      (analysis.contractRate * 100).toFixed(1) + '%',
      (analysis.stepRates['①アプローチ'] * 100).toFixed(0) + '%',
      (analysis.stepRates['②ヒアリング'] * 100).toFixed(0) + '%',
      (analysis.stepRates['③提案'] * 100).toFixed(0) + '%',
      (analysis.stepRates['④クロージング'] * 100).toFixed(0) + '%',
      (analysis.stepRates['⑤申込契約'] * 100).toFixed(0) + '%',
      (analysis.stepRates['⑥紹介入手'] * 100).toFixed(0) + '%',
      analysis.avgCompleteness.toFixed(1),
      analysis.style
    ]);
  }

  // Write analysis results
  analysisSheet.clearContents();
  if (analysisResults.length > 1) {
    analysisSheet.getRange(1, 1, analysisResults.length, analysisResults[0].length).setValues(analysisResults);
    Logger.log('✓ KachiTalk分析結果を更新しました: ' + (analysisResults.length - 1) + '名');
  }

  // Generate correlation analysis
  buildSalesCorrelationAnalysis(analysisResults);
}

/**
 * Analyze single staff member's performance from call logs
 */
function analyzeStaffPerformance(staffName, logs) {
  var callCount = logs.length;
  var contractCount = 0;
  var totalDuration = 0;
  var totalCompleteness = 0;

  var stepExecutions = {
    '①アプローチ': 0,
    '②ヒアリング': 0,
    '③提案': 0,
    '④クロージング': 0,
    '⑤申込契約': 0,
    '⑥紹介入手': 0
  };

  logs.forEach(function(log) {
    // Analyze process steps
    var completeness = 0;
    var stepCount = 0;

    for (var step in SALES_PROCESS_STEPS) {
      var keywords = SALES_PROCESS_STEPS[step];
      var found = keywords.some(function(kw) {
        return (log.transcript || '').indexOf(kw) !== -1;
      });

      if (found) {
        stepExecutions[step]++;
        completeness += 16.67; // 6 steps = 100%
        stepCount++;
      }
    }

    totalCompleteness += completeness;
    totalDuration += (log.duration || 0);

    // Check result
    if ((log.result || '').indexOf('成約') !== -1 ||
        (log.notes || '').indexOf('成約') !== -1) {
      contractCount++;
    }
  });

  // Calculate rates
  var stepRates = {};
  for (var step in stepExecutions) {
    stepRates[step] = stepExecutions[step] / callCount;
  }

  var avgDuration = totalDuration / callCount;
  var avgCompleteness = totalCompleteness / callCount;
  var contractRate = contractCount / callCount;

  // Determine sales style
  var style = '';
  if (contractRate >= 0.20) style += '✨高成約率 ';
  if (avgDuration < 15) style += '⚡短時間効率 ';
  if (avgDuration > 18) style += '🕐じっくり対応 ';
  if (stepRates['④クロージング'] > 0.85 && stepRates['②ヒアリング'] < 0.70) style += '🎯ショートカット型 ';
  if (avgCompleteness > 75) style += '📋教科書的 ';
  if (contractRate < 0.10) style += '📈成長段階 ';

  return {
    period: '7月〜10月',
    callCount: callCount,
    contractCount: contractCount,
    contractRate: contractRate,
    avgDuration: avgDuration,
    avgCompleteness: avgCompleteness,
    stepRates: stepRates,
    style: style || '分析中'
  };
}

/**
 * Build correlation analysis between KachiTalk quality and sales performance
 */
function buildSalesCorrelationAnalysis(analysisResults) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var correlationSheet = ss.getSheetByName('営業成績との相関');

  var correlationOutput = [
    ['スタッフ別成績相関分析'],
    [''],
    ['スタッフ名', '通話件数', '成約率', '平均プロセス完全性', 'スタイル', '相関評価']
  ];

  for (var i = 1; i < analysisResults.length; i++) {
    var row = analysisResults[i];
    var staffName = row[0];
    var callCount = parseInt(row[2]);
    var contractRateStr = row[5];
    var completenessStr = row[12];

    // Extract numeric values
    var contractRate = parseInt(contractRateStr) / 100;
    var completeness = parseFloat(completenessStr);

    // Determine correlation assessment
    var assessment = '';
    if (contractRate >= 0.20 && completeness >= 75) {
      assessment = '◎ 最適: 高成約率＆プロセス実行';
    } else if (contractRate >= 0.15 && completeness >= 70) {
      assessment = '○ 良好: バランス型';
    } else if (contractRate < 0.10) {
      assessment = '△ 要改善: 基本プロセスの強化推奨';
    } else {
      assessment = '□ 分析中';
    }

    correlationOutput.push([
      staffName,
      callCount,
      contractRateStr,
      completenessStr,
      row[13],
      assessment
    ]);
  }

  correlationSheet.clearContents();
  correlationSheet.getRange(1, 1, correlationOutput.length, 6).setValues(correlationOutput);
  Logger.log('✓ 営業成績との相関分析を完了しました');
}

/**
 * Trigger: Daily automated KachiTalk data refresh (for future automation)
 */
function scheduleKachiTalkDailyRefresh() {
  // This function should be registered as a daily trigger via Apps Script UI
  // For now, it's a template for future implementation

  Logger.log('※ KachiTalk自動同期: 毎日00:00 JST に実行予定');
  Logger.log('   セットアップ: Apps Script UI → トリガー → 毎日トリガーを追加');
  Logger.log('   関数: scheduleKachiTalkDailyRefresh');
}
