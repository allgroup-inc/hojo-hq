/**
 * ReportEmailFormatter.gs
 *
 * 日次レポートの集計データ組み立てと HTML メール生成
 * Task 4: メール本体の集計とフォーマット関数
 *
 * ブランドカラー: ネイビー #00335C・オレンジ #F88800(CLAUDE.md 準拠)
 */

/**
 * 日次レポートの全指標(手紙・QRスキャン・架電・訪問・ランク分布・スコア
 * セグメント・流入ルート別成約)を1つのオブジェクトに集約する
 * @param {Date} yesterdayDate - 対象日(前日 0時。getYesterday() の返り値を渡す)
 * @returns {Object} reportData
 */
function compileDailyReport(yesterdayDate) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const masterSheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  const interactionSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);

  if (!masterSheet || !interactionSheet) {
    throw new Error("Required sheets not found: Company Master or Activity Records");
  }

  // Read all records
  // 注: readMasterRecords_() / readInteractionRecords_() は
  // FukudaPerformanceReport.gs で既に定義済みのグローバル関数を再利用する
  // (GAS は全 .gs ファイルを1つのグローバルスコープとして扱うため、同名関数を
  // ここで再定義すると定義の重複=読み込み順依存の不具合を招く。再発防止メモ
  // 「同じ対象を扱う複数のスクリプトは、除外・特例のフラグを共有する」と同じ理由で、
  // 実装は1箇所に一本化する)
  const masterRecords = readMasterRecords_(masterSheet);
  const interactions = readInteractionRecords_(interactionSheet);

  // Get date ranges
  const weekRange = getWeekDateRange(yesterdayDate);
  const monthRange = getMonthDateRange(yesterdayDate);
  const prevWeekRange = {
    startDate: new Date(weekRange.startDate.getTime() - 7 * 24 * 60 * 60 * 1000),
    endDate: new Date(weekRange.endDate.getTime() - 7 * 24 * 60 * 60 * 1000)
  };
  const prevMonthRange = getPreviousMonthRange(monthRange);

  // Compile letter data
  const lettersYesterday = countLettersByDate(masterRecords, yesterdayDate);
  const lettersWeekly = countLettersByDateRange(masterRecords, weekRange.startDate, weekRange.endDate);
  const lettersWeeklyPrev = countLettersByDateRange(masterRecords, prevWeekRange.startDate, prevWeekRange.endDate);
  const lettersMonthly = countLettersByDateRange(masterRecords, monthRange.startDate, monthRange.endDate);
  const lettersMonthlyPrev = countLettersByDateRange(masterRecords, prevMonthRange.startDate, prevMonthRange.endDate);

  // Compile QR scan data
  const qrYesterday = getLineNewUsersCount(yesterdayDate);
  const qrWeekly = getLineNewUsersWeekly(weekRange);
  const qrWeeklyPrev = getLineNewUsersWeekly(prevWeekRange);
  const qrMonthly = getLineNewUsersMonthly(monthRange);
  const qrMonthlyPrev = getLineNewUsersMonthly(prevMonthRange);
  const totalLineUsers = getLineUserCountByDate(yesterdayDate);

  // Compile call data
  const callsYesterday = countCallsByDateRange(interactions, yesterdayDate, yesterdayDate);
  const callsWeekly = countCallsByDateRange(interactions, weekRange.startDate, weekRange.endDate);
  const callsWeeklyPrev = countCallsByDateRange(interactions, prevWeekRange.startDate, prevWeekRange.endDate);
  const callsMonthly = countCallsByDateRange(interactions, monthRange.startDate, monthRange.endDate);
  const callsMonthlyPrev = countCallsByDateRange(interactions, prevMonthRange.startDate, prevMonthRange.endDate);

  // Compile visit/contract data
  const visitsYesterday = countVisitsByDate(interactions, yesterdayDate);
  const visitsWeekly = countVisitsByDateRange(interactions, weekRange.startDate, weekRange.endDate);
  const visitsWeeklyPrev = countVisitsByDateRange(interactions, prevWeekRange.startDate, prevWeekRange.endDate);
  const visitsMonthly = countVisitsByDateRange(interactions, monthRange.startDate, monthRange.endDate);
  const contractsWeekly = countContractsByDateRange(interactions, weekRange.startDate, weekRange.endDate);
  const contractsWeeklyPrev = countContractsByDateRange(interactions, prevWeekRange.startDate, prevWeekRange.endDate);
  const contractsMonthly = countContractsByDateRange(interactions, monthRange.startDate, monthRange.endDate);

  // Compile rank distribution
  const rankDist = getRankDistribution(masterRecords);

  // Compile score segments
  const scoreSegs = getScoreSegments(masterRecords);

  // Compile route conversion
  const routeConv = getRouteConversionRates(masterRecords);

  return {
    reportDate: datesToLocaleDateString(yesterdayDate),
    letters: {
      yesterday: lettersYesterday,
      weekly: lettersWeekly,
      weeklyPrev: lettersWeeklyPrev,
      weeklyDiff: lettersWeekly - lettersWeeklyPrev,
      monthly: lettersMonthly,
      monthlyPrev: lettersMonthlyPrev,
      monthlyDiff: lettersMonthly - lettersMonthlyPrev,
    },
    qrScans: {
      yesterday: qrYesterday,
      weekly: qrWeekly,
      weeklyPrev: qrWeeklyPrev,
      weeklyDiff: qrWeekly - qrWeeklyPrev,
      monthly: qrMonthly,
      monthlyPrev: qrMonthlyPrev,
      monthlyDiff: qrMonthly - qrMonthlyPrev,
      totalLineUsers: totalLineUsers,
      scanRate: totalLineUsers === 0 ? "0.0%" : (totalLineUsers / (masterRecords.filter(r => r["最終手紙送付日"]).length || 1) * 100).toFixed(1) + "%",
    },
    calls: {
      yesterday: callsYesterday.total,
      yesterdayByRank: callsYesterday.byRank,
      weekly: callsWeekly.total,
      weeklyPrev: callsWeeklyPrev.total,
      weeklyDiff: callsWeekly.total - callsWeeklyPrev.total,
      monthly: callsMonthly.total,
      monthlyPrev: callsMonthlyPrev.total,
      monthlyDiff: callsMonthly.total - callsMonthlyPrev.total,
    },
    visits: {
      yesterday: visitsYesterday.total,
      yesterdayBreakdown: { visits: visitsYesterday.visits, meetings: visitsYesterday.meetings },
      weekly: visitsWeekly.total,
      weeklyContracts: contractsWeekly,
      weeklyPrevContracts: contractsWeeklyPrev,
      weeklyContractsDiff: contractsWeekly - contractsWeeklyPrev,
      monthly: visitsMonthly.total,
      monthlyContracts: contractsMonthly,
      contractRate: visitsMonthly.total === 0 ? "0.0%" : (contractsMonthly / visitsMonthly.total * 100).toFixed(1) + "%",
    },
    rankDistribution: rankDist,
    scoreSegments: scoreSegs,
    routeConversion: routeConv,
  };
}

/**
 * currentMonthRange と同じ日数分の、前月の同期間を計算する
 * (例: 9/1〜9/22 の22日間 → 8/1〜8/22)
 * @param {Object} currentMonthRange - {startDate: Date, endDate: Date}
 * @returns {Object} {startDate: Date, endDate: Date}
 */
function getPreviousMonthRange(currentMonthRange) {
  // 前月の同期間を計算
  const days = Math.floor((currentMonthRange.endDate - currentMonthRange.startDate) / (24 * 60 * 60 * 1000)) + 1;
  const prevMonthStart = new Date(currentMonthRange.startDate);
  prevMonthStart.setMonth(prevMonthStart.getMonth() - 1);
  prevMonthStart.setHours(0, 0, 0, 0);

  const prevMonthEnd = new Date(prevMonthStart);
  prevMonthEnd.setDate(prevMonthEnd.getDate() + days - 1);
  prevMonthEnd.setHours(23, 59, 59, 999);

  return { startDate: prevMonthStart, endDate: prevMonthEnd };
}

/**
 * LINE 公式アカウントの新規登録数(週計)を取得
 * プレースホルダー: LINE API 実装後に置き換え(getLineNewUsersCount と同様、
 * 現状は LINE 連携 API の詳細が未確定のため 0 を返す)
 * @param {Object} dateRange - {startDate: Date, endDate: Date}
 * @returns {number} 新規登録数
 */
function getLineNewUsersWeekly(dateRange) {
  // LINE 新規登録数の週計
  // プレースホルダー: LINE API 実装後に置き換え
  Logger.log("⚠ getLineNewUsersWeekly: LINE API not yet implemented");
  return 0;
}

/**
 * LINE 公式アカウントの新規登録数(月計)を取得
 * プレースホルダー: LINE API 実装後に置き換え
 * @param {Object} dateRange - {startDate: Date, endDate: Date}
 * @returns {number} 新規登録数
 */
function getLineNewUsersMonthly(dateRange) {
  // LINE 新規登録数の月計
  // プレースホルダー: LINE API 実装後に置き換え
  Logger.log("⚠ getLineNewUsersMonthly: LINE API not yet implemented");
  return 0;
}

/**
 * reportData を GLOW ブランドカラー(ネイビー #00335C・オレンジ #F88800)の
 * レスポンシブ HTML メール本文に整形する
 * @param {Object} reportData - compileDailyReport() の返り値
 * @returns {string} HTML文字列
 */
function formatReportEmail(reportData) {
  const html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: 'Segoe UI', 'Noto Sans JP', Tahoma, Geneva, Verdana, sans-serif;
      color: #333;
      background-color: #f5f5f5;
      margin: 0;
      padding: 20px;
    }
    .container {
      max-width: 800px;
      margin: 0 auto;
      background-color: white;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .header {
      background-color: #00335C;
      color: white;
      padding: 30px 20px;
      text-align: center;
    }
    .header h1 {
      margin: 0;
      font-size: 24px;
      font-weight: bold;
    }
    .header p {
      margin: 10px 0 0 0;
      font-size: 12px;
      opacity: 0.9;
    }
    .section {
      margin: 20px;
      padding: 15px;
      border-left: 4px solid #F88800;
      background-color: #fafafa;
    }
    .section h2 {
      margin: 0 0 15px 0;
      font-size: 16px;
      font-weight: bold;
      color: #00335C;
    }
    .metric {
      display: inline-block;
      width: 48%;
      margin: 10px 1%;
      vertical-align: top;
    }
    .metric-value {
      font-size: 28px;
      font-weight: bold;
      color: #00335C;
      line-height: 1.2;
    }
    .metric-label {
      color: #999;
      font-size: 12px;
      margin-top: 5px;
    }
    .metric-compare {
      color: #F88800;
      font-weight: bold;
      font-size: 12px;
    }
    .rank-breakdown {
      font-size: 12px;
      color: #666;
      margin-top: 5px;
    }
    .footer {
      border-top: 1px solid #ddd;
      padding: 15px 20px;
      font-size: 12px;
      color: #999;
      text-align: center;
    }
    hr {
      border: none;
      border-top: 1px solid #ddd;
      margin: 30px 0;
    }
    @media only screen and (max-width: 480px) {
      body { padding: 10px; }
      .metric { width: 98%; margin: 8px 1%; }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>【GLOW日次レポート】${reportData.reportDate}</h1>
      <p>配信時刻: ${new Date().toLocaleString("ja-JP")}</p>
    </div>

    <div class="section">
      <h2>■ 手紙発送</h2>
      <div class="metric">
        <div class="metric-label">昨日</div>
        <div class="metric-value">${reportData.letters.yesterday}</div>
        <div class="metric-label">通</div>
      </div>
      <div class="metric">
        <div class="metric-label">週間合計</div>
        <div class="metric-value">${reportData.letters.weekly}</div>
        <div class="metric-label">通 <span class="metric-compare">(前週: ${reportData.letters.weeklyPrev}, ${reportData.letters.weeklyDiff >= 0 ? '+' : ''}${reportData.letters.weeklyDiff})</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">月間合計</div>
        <div class="metric-value">${reportData.letters.monthly}</div>
        <div class="metric-label">通 <span class="metric-compare">(前月同期: ${reportData.letters.monthlyPrev}, ${reportData.letters.monthlyDiff >= 0 ? '+' : ''}${reportData.letters.monthlyDiff})</span></div>
      </div>
    </div>

    <div class="section">
      <h2>■ QRスキャン</h2>
      <div class="metric">
        <div class="metric-label">昨日</div>
        <div class="metric-value">${reportData.qrScans.yesterday}</div>
        <div class="metric-label">件</div>
      </div>
      <div class="metric">
        <div class="metric-label">週間合計</div>
        <div class="metric-value">${reportData.qrScans.weekly}</div>
        <div class="metric-label">件 <span class="metric-compare">(前週: ${reportData.qrScans.weeklyPrev}, ${reportData.qrScans.weeklyDiff >= 0 ? '+' : ''}${reportData.qrScans.weeklyDiff})</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">月間合計</div>
        <div class="metric-value">${reportData.qrScans.monthly}</div>
        <div class="metric-label">件 <span class="metric-compare">(前月同期: ${reportData.qrScans.monthlyPrev})</span></div>
      </div>
      <div style="clear:both; margin-top: 10px; font-size: 12px; color: #666;">
        累計スキャン率: ${reportData.qrScans.scanRate} (${reportData.qrScans.totalLineUsers}/${(reportData.letters.monthly + reportData.letters.monthlyPrev) || 0}通)
      </div>
    </div>

    <div class="section">
      <h2>■ 架電数</h2>
      <div class="metric">
        <div class="metric-label">昨日</div>
        <div class="metric-value">${reportData.calls.yesterday}</div>
        <div class="rank-breakdown">A:${reportData.calls.yesterdayByRank.A} B:${reportData.calls.yesterdayByRank.B} C:${reportData.calls.yesterdayByRank.C} D:${reportData.calls.yesterdayByRank.D}</div>
      </div>
      <div class="metric">
        <div class="metric-label">週間合計</div>
        <div class="metric-value">${reportData.calls.weekly}</div>
        <div class="metric-label">件 <span class="metric-compare">(前週: ${reportData.calls.weeklyPrev}, ${reportData.calls.weeklyDiff >= 0 ? '+' : ''}${reportData.calls.weeklyDiff})</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">月間合計</div>
        <div class="metric-value">${reportData.calls.monthly}</div>
        <div class="metric-label">件 <span class="metric-compare">(前月同期: ${reportData.calls.monthlyPrev})</span></div>
      </div>
    </div>

    <div class="section">
      <h2>■ 訪問・面談</h2>
      <div class="metric">
        <div class="metric-label">昨日</div>
        <div class="metric-value">${reportData.visits.yesterday}</div>
        <div class="rank-breakdown">訪問:${reportData.visits.yesterdayBreakdown.visits} 面談:${reportData.visits.yesterdayBreakdown.meetings}</div>
      </div>
      <div class="metric">
        <div class="metric-label">週間合計</div>
        <div class="metric-value">${reportData.visits.weekly}</div>
        <div class="metric-label">件 <span class="metric-compare">(成約: ${reportData.visits.weeklyContracts}, 前週: ${reportData.visits.weeklyPrevContracts})</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">月間合計</div>
        <div class="metric-value">${reportData.visits.monthly}</div>
        <div class="metric-label">件 <span class="metric-compare">(成約: ${reportData.visits.monthlyContracts})</span></div>
      </div>
      <div style="clear:both; margin-top: 10px; font-size: 12px; color: #666;">
        成約率: ${reportData.visits.contractRate}
      </div>
    </div>

    <div class="section">
      <h2>■ 企業ランク分布</h2>
      <div style="font-size: 14px; line-height: 1.8;">
        A: <strong>${reportData.rankDistribution.A}</strong>社<br>
        B: <strong>${reportData.rankDistribution.B}</strong>社<br>
        C: <strong>${reportData.rankDistribution.C}</strong>社<br>
        D: <strong>${reportData.rankDistribution.D}</strong>社<br>
        <strong>合計: ${reportData.rankDistribution.total}社</strong>
      </div>
    </div>

    <div class="section">
      <h2>■ スコアセグメント</h2>
      <div style="font-size: 14px; line-height: 1.8;">
        90点以上: <strong>${reportData.scoreSegments["90以上"]}</strong>社<br>
        70-89点: <strong>${reportData.scoreSegments["70-89"]}</strong>社<br>
        40-69点: <strong>${reportData.scoreSegments["40-69"]}</strong>社<br>
        15-39点: <strong>${reportData.scoreSegments["15-39"]}</strong>社<br>
        15点未満: <strong>${reportData.scoreSegments["15未満"]}</strong>社
      </div>
    </div>

    <div class="section">
      <h2>■ 流入ルート別成約</h2>
      <div style="font-size: 14px; line-height: 1.8;">
        ①紹介: <strong>${reportData.routeConversion["①紹介"].contracts}</strong>成約 (${reportData.routeConversion["①紹介"].total}社, <span class="metric-compare">${reportData.routeConversion["①紹介"].rate}</span>)<br>
        ②手紙DM: <strong>${reportData.routeConversion["②手紙DM"].contracts}</strong>成約 (${reportData.routeConversion["②手紙DM"].total}社, <span class="metric-compare">${reportData.routeConversion["②手紙DM"].rate}</span>)<br>
        ③ミカタ経由: <strong>${reportData.routeConversion["③ミカタ経由"].contracts}</strong>成約 (${reportData.routeConversion["③ミカタ経由"].total}社, <span class="metric-compare">${reportData.routeConversion["③ミカタ経由"].rate}</span>)<br>
        ④開拓架電: <strong>${reportData.routeConversion["④開拓架電"].contracts}</strong>成約 (${reportData.routeConversion["④開拓架電"].total}社, <span class="metric-compare">${reportData.routeConversion["④開拓架電"].rate}</span>)
      </div>
    </div>

    <div class="footer">
      <p>このレポートは毎日 10:00 JST に自動生成されました。</p>
      <p>架電実績は BlueBean CTI システムから自動取得しています。</p>
      <p>週間比較 = 過去7日 vs その前7日 / 月間比較 = 当月1日〜今日 vs 前月同期</p>
    </div>
  </div>
</body>
</html>
  `;
  return html;
}
