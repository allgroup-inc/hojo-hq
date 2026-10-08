/**
 * ダッシュボード表示問題の診断・修復ツール
 *
 * 福田さんのダッシュボードが見えない問題に対応するため、
 * 以下の診断・修復機能を提供する。
 *
 * 使用方法：
 * 1. Apps Scriptエディタで DashboardDiagnostics.gs を開く
 * 2. ドロップダウンから診断したい関数を選ぶ
 * 3. 実行ボタン(▶)をクリック
 * 4. 実行ログでエラーや状態を確認
 *
 * 関数一覧：
 * - diagnoseDashboardVisibility() : 全体診断
 * - fixHiddenDashboard() : 非表示シートの表示化
 * - recreateDashboardSheet() : ダッシュボードシートの再作成
 * - updateDashboardData() : ダッシュボードデータの即座更新
 */

function diagnoseDashboardVisibility() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var allSheets = ss.getSheets();

  Logger.log("========== ダッシュボード表示診断 ==========");
  Logger.log("スプレッドシート名: " + ss.getName());
  Logger.log("総シート数: " + allSheets.length);
  Logger.log("");

  // 可視シートの一覧
  var visibleSheets = [];
  var hiddenSheets = [];

  allSheets.forEach(function(sheet) {
    var sheetName = sheet.getName();
    var isHidden = sheet.isSheetHidden();
    if (isHidden) {
      hiddenSheets.push(sheetName);
    } else {
      visibleSheets.push(sheetName);
    }
  });

  Logger.log("--- 可視シート ---");
  visibleSheets.forEach(function(name) {
    Logger.log("  ✓ " + name);
  });

  Logger.log("");
  Logger.log("--- 隠されたシート ---");
  if (hiddenSheets.length === 0) {
    Logger.log("  (なし)");
  } else {
    hiddenSheets.forEach(function(name) {
      Logger.log("  × " + name);
    });
  }

  Logger.log("");

  // ダッシュボードシート検索
  var dashboardSheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);
  if (dashboardSheet) {
    Logger.log("✓ ダッシュボードシート: 見つかりました");
    Logger.log("  隠れている: " + (dashboardSheet.isSheetHidden() ? "はい" : "いいえ"));
    Logger.log("  行数: " + dashboardSheet.getLastRow());
    Logger.log("  列数: " + dashboardSheet.getLastColumn());
    if (dashboardSheet.getLastRow() === 1) {
      Logger.log("  ⚠️  見出しのみで、データがありません。ステップ 2 を実行してください。");
    }
  } else {
    Logger.log("× ダッシュボードシート: 見つかりません");
    Logger.log("  → ステップ 3 (recreateDashboardSheet) を実行してください。");
  }

  Logger.log("");
  Logger.log("========== 診断完了 ==========");
}

function fixHiddenDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var dashboardSheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);

  Logger.log("========== 非表示シートの表示化 ==========");

  if (!dashboardSheet) {
    Logger.log("✗ ダッシュボードシートが見つかりません。");
    Logger.log("  recreateDashboardSheet() を実行してください。");
    return;
  }

  if (dashboardSheet.isSheetHidden()) {
    Logger.log("ダッシュボードシートは現在隠されています。表示化します...");
    dashboardSheet.showSheet();
    Logger.log("✓ ダッシュボードシートが表示されました。");
  } else {
    Logger.log("✓ ダッシュボードシートは既に表示されています。");
  }

  Logger.log("========== 完了 ==========");
}

function recreateDashboardSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var existingSheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);

  Logger.log("========== ダッシュボードシート再作成 ==========");

  // 既存シートを削除（存在する場合）
  if (existingSheet) {
    Logger.log("既存のダッシュボードシートを削除中...");
    ss.deleteSheet(existingSheet);
  }

  // 新規作成
  Logger.log("新しいダッシュボードシートを作成中...");
  ensureTab_(ss, GlowSchema.DASHBOARD_SHEET_NAME, GlowSchema.DASHBOARD_PLACEHOLDER_HEADERS);

  Logger.log("✓ ダッシュボードシートを再作成しました。");
  Logger.log("次に updateDashboardData() を実行してデータを投入してください。");

  Logger.log("========== 完了 ==========");
}

function updateDashboardData() {
  Logger.log("========== ダッシュボードデータ更新 ==========");
  Logger.log("ダッシュボード集計を実行中...");

  try {
    updateDashboard();
    Logger.log("✓ ダッシュボードが正常に更新されました。");
    Logger.log("Google Sheets をリロード (F5 または Ctrl+Shift+R) して確認してください。");
  } catch (e) {
    Logger.log("✗ エラーが発生しました: " + e.message);
    Logger.log("スタックトレース: " + e.stack);
  }

  Logger.log("========== 完了 ==========");
}

function quickRepairDashboard() {
  Logger.log("========== クイック修復: ダッシュボード可視化 ==========");

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var dashboardSheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);

  if (!dashboardSheet) {
    Logger.log("ステップ 1: ダッシュボードシートが見つかりません。作成中...");
    recreateDashboardSheet();
    dashboardSheet = ss.getSheetByName(GlowSchema.DASHBOARD_SHEET_NAME);
  }

  if (dashboardSheet.isSheetHidden()) {
    Logger.log("ステップ 2: ダッシュボードシートが隠れています。表示中...");
    fixHiddenDashboard();
  }

  Logger.log("ステップ 3: ダッシュボードデータを更新中...");
  updateDashboardData();

  Logger.log("");
  Logger.log("========== クイック修復完了 ==========");
  Logger.log("以下を確認してください:");
  Logger.log("1. Google Sheets を再度開く（F5 キーでリロード）");
  Logger.log("2. シート一覧にダッシュボードが表示されているか");
  Logger.log("3. ダッシュボードシートにデータが表示されているか");
}

// 既存の ensureTab_ をここでも使用（SheetSetup.gs から）
function ensureTab_(spreadsheet, sheetName, headers) {
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  return sheet;
}
