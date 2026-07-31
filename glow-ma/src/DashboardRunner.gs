/**
 * GLOW企業リレーション台帳: ダッシュボードの自動集計
 * Apps Scriptエディタの関数選択で updateDashboard を選び、実行ボタンで手動実行する。
 * (将来的には日次・週次の時間主導トリガーに登録して自動実行することを想定しているが、
 *  トリガー登録自体は本Planの範囲外。)
 *
 * 実行すると、企業マスタ・紹介パートナーマスタを読み取り、以下5つの表を
 * 「ダッシュボード」タブに作り直す。他のタブへの書き込みは一切行わない。
 * - ルート別×ステージ別ファネル
 * - 提案商品別サマリー(提案数・案件化数・成約数)
 * - ランク別サマリー(滞留企業数・掘り起こし待ち件数)
 * - 紹介パートナー別サマリー
 * - データ品質チェック(集計対象外の件数)
 *
 * 企業マスタ・紹介パートナーマスタの読み取りと集計は、他プロセス(例:
 * importCompaniesFromStaging)による書き込み中の中間状態を拾わないよう、
 * ScoringRunner.gs と同様にロック取得後に行う。
 */
function updateDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var dashboardSheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);
  if (!dashboardSheet) {
    throw new Error("ダッシュボードタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var partnerSheet = ss.getSheetByName(GlowSchema.PARTNER_MASTER_SHEET_NAME);

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error("他の処理がダッシュボードを操作中のため、更新を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    var records = readCompanyRecords_(companySheet);
    var partnerRecords = readPartnerRecords_(partnerSheet);
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");

    var funnel = GlowDashboard.buildRouteStageFunnel(records, GlowDashboard.DEFAULT_CONFIG);
    var productSummary = GlowDashboard.buildProductFunnel(records, GlowDashboard.DEFAULT_CONFIG);
    var rankSummary = GlowDashboard.buildRankSummary(records, todayString, GlowDashboard.DEFAULT_CONFIG);
    var partnerSummary = GlowDashboard.formatPartnerSummary(partnerRecords);
    var qualitySummary = GlowDashboard.countUnclassifiedCompanies(records, GlowDashboard.DEFAULT_CONFIG);

    dashboardSheet.clearContents();
    var row = 1;
    row = writeDashboardSection_(dashboardSheet, row, "ルート別×ステージ別ファネル",
      ["流入ルート", "現在ステージ", "件数"],
      funnel.map(function (f) { return [f["流入ルート"], f["現在ステージ"], f["件数"]]; }));
    row++;
    row = writeDashboardSection_(dashboardSheet, row, "提案商品別サマリー",
      ["商品", "提案数", "案件化数", "成約数"],
      productSummary.map(function (p) { return [p["商品"], p["提案数"], p["案件化数"], p["成約数"]]; }));
    row++;
    row = writeDashboardSection_(dashboardSheet, row, "ランク別サマリー",
      ["ランク", "滞留企業数", "掘り起こし待ち件数"],
      rankSummary.map(function (r) { return [r["ランク"], r["滞留企業数"], r["掘り起こし待ち件数"]]; }));
    row++;
    row = writeDashboardSection_(dashboardSheet, row, "紹介パートナー別サマリー",
      GlowDashboard.PARTNER_SUMMARY_FIELDS,
      partnerSummary.map(function (p) {
        return GlowDashboard.PARTNER_SUMMARY_FIELDS.map(function (field) { return p[field]; });
      }));
    row++;
    row = writeDashboardSection_(dashboardSheet, row, "データ品質チェック(集計対象外の件数)",
      ["対象企業数", "未スコア企業数", "現在ステージ未分類企業数", "流入ルート未分類企業数", "提案商品未設定企業数"],
      [[qualitySummary["対象企業数"], qualitySummary["未スコア企業数"], qualitySummary["現在ステージ未分類企業数"],
        qualitySummary["流入ルート未分類企業数"], qualitySummary["提案商品未設定企業数"]]]);
    row++;
    dashboardSheet.getRange(row, 1).setValue(
      "最終更新: " + Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm")
    );
  } finally {
    lock.releaseLock();
  }

  Logger.log("ダッシュボード更新完了");
}

function writeDashboardSection_(sheet, startRow, title, headers, rows) {
  sheet.getRange(startRow, 1).setValue(title);
  var headerRow = startRow + 1;
  sheet.getRange(headerRow, 1, 1, headers.length).setValues([headers]);
  if (rows.length > 0) {
    sheet.getRange(headerRow + 1, 1, rows.length, headers.length).setValues(rows);
  }
  return headerRow + 1 + rows.length;
}

function readPartnerRecords_(sheet) {
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.PARTNER_MASTER_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    return record;
  });
}
