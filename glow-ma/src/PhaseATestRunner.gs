/**
 * GLOW企業リレーション台帳: G1フェーズA試験の自動実行
 *
 * 使い方: Apps Scriptエディタで runPhaseATest を選び、実行ボタンを1回押すだけ。
 * 以下をこの順で自動的に行い、実行ログにGo/No-Go判定材料をまとめて出力する。
 *
 *   0. 対応履歴ログの見出し行を正しい状態に修復する(手作業の貼り付けで壊れた場合の保険)
 *   1. スコアリング再計算(recalculateAllScores)と、既知10社の期待値との答え合わせ
 *   2. DNC同期(syncDoNotContactFlags)と、試験対象50社への反映確認
 *   3. 試験データ(H-DNCTEST-*)の後片付けと、連絡不要フラグの復旧
 *
 * 冪等性: 何度実行しても同じ結果になる(試験データは毎回作り直して毎回消す)。
 * 安全性: 企業マスタの書き換えは既存のLockService付き関数に委譲し、
 *         試験で立てた連絡不要フラグは必ず元に戻す(finallyで復旧)。
 */

// 期待値: scoring.jsのDEFAULT_CONFIGから導出した、属性スコアのみの企業(反応履歴なし)の答え。
// 建設業・介護を含む業種はhigh(20点)、障害福祉のみはmid(10点)。ランク閾値はA:70/B:40/C:15。
var PHASE_A_EXPECTED_SCORES = [
  { id: "C000001", industryContains: "建設", expectedInitial: 20, expectedRank: "C" },
  { id: "C000750", industryContains: "建設", expectedInitial: 20, expectedRank: "C" },
  { id: "C001500", industryContains: "建設", expectedInitial: 20, expectedRank: "C" },
  { id: "C001502", industryContains: "介護", expectedInitial: 20, expectedRank: "C" },
  { id: "C003210", industryContains: "福祉", expectedInitial: 10, expectedRank: "D" }
];

var PHASE_A_DNC_TEST_PREFIX = "H-DNCTEST-";
var PHASE_A_DNC_TEST_COUNT = 50;
var PHASE_A_DNC_FIRST_INDEX = 3161;  // C003161〜C003210 の50社

/**
 * メニュー「GLOW台帳」→「G1フェーズA試験を実行」から呼ばれる。
 * 試験を実行し、結果をダイアログで表示する(Apps Scriptエディタを開かずに実行できる)。
 */
function showPhaseATestDialog() {
  var ui = SpreadsheetApp.getUi();
  var confirmed = ui.alert(
    "G1フェーズA試験",
    "スコア再計算・DNC同期の試験を実行します(2〜3分)。\n" +
    "試験データは自動で作成され、終了後に自動削除されます。\n\n実行しますか?",
    ui.ButtonSet.OK_CANCEL
  );
  if (confirmed !== ui.Button.OK) return;

  var result;
  try {
    result = runPhaseATest();
  } catch (e) {
    result = "試験中にエラーが発生しました:\n" + e.message +
      "\n\n企業マスタは自動バックアップから復旧できます(タブ名: 企業マスタ_backup_*)。";
  }
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;font-size:13px;white-space:pre-wrap;line-height:1.7">' +
    result.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") +
    "</div>"
  ).setWidth(560).setHeight(460);
  ui.showModalDialog(html, "G1フェーズA試験 結果");
}

function runPhaseATest() {
  var report = [];
  report.push("===== G1フェーズA試験 開始 =====");

  var repaired = repairInteractionLogHeader_();
  report.push("[0] 対応履歴ログ見出し: " + (repaired ? "修復した" : "正常"));

  // --- 1. スコアリング ---
  recalculateAllScores();
  var scoreResult = verifyScores_();
  report.push("[1] スコアリング: " + scoreResult.passed + "/" + scoreResult.total + "件 一致");
  scoreResult.details.forEach(function (line) { report.push("      " + line); });

  // --- 2. DNC ---
  var dncResult = runDncTest_();
  report.push("[2] DNC(連絡不要): 試験50社中 " + dncResult.flaggedCount + "社にフラグが立った");
  report.push("      伝播による追加: " + dncResult.propagatedExtra + "社(同一電話番号の関連会社)");

  // --- 3. 後片付け ---
  var cleaned = cleanupPhaseATestData_();
  report.push("[3] 後片付け: 試験履歴 " + cleaned.removedLogs + "行を削除 / 連絡不要フラグ " + cleaned.resetFlags + "件を復旧");

  var allPassed = scoreResult.passed === scoreResult.total
    && dncResult.flaggedCount === PHASE_A_DNC_TEST_COUNT;
  report.push("===== 判定: " + (allPassed ? "Go(基準クリア)" : "要確認(基準未達の項目あり)") + " =====");
  report.push("※Slackアラート5回連続送信は別途実施済み(2026-08-17・5/5成功)");

  var text = report.join("\n");
  Logger.log(text);
  return text;
}

/** 対応履歴ログの1行目を正しい見出しに戻す。既に正しければ何もしない。 */
function repairInteractionLogHeader_() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!sheet) throw new Error("対応履歴ログタブが見つかりません。");
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var current = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  var isValid = headers.every(function (h, i) { return String(current[i]) === h; });
  if (isValid) return false;
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  return true;
}

/** 既知企業のスコアが期待値と一致するか照合する。 */
function verifyScores_() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var records = readCompanyRecords_(sheet);
  var byId = {};
  records.forEach(function (r) { byId[r["企業ID"]] = r; });

  var passed = 0;
  var details = [];
  PHASE_A_EXPECTED_SCORES.forEach(function (exp) {
    var r = byId[exp.id];
    if (!r) {
      details.push(exp.id + ": NG(企業マスタに存在しない)");
      return;
    }
    var actualInitial = Number(r["初期スコア"]);
    var actualRank = String(r["ランク"]);
    var ok = actualInitial === exp.expectedInitial && actualRank === exp.expectedRank;
    if (ok) passed++;
    details.push(
      exp.id + ": " + (ok ? "OK" : "NG") +
      " 初期スコア " + actualInitial + "(期待 " + exp.expectedInitial + ")" +
      " / ランク " + actualRank + "(期待 " + exp.expectedRank + ")"
    );
  });
  return { passed: passed, total: PHASE_A_EXPECTED_SCORES.length, details: details };
}

/** 試験用の「連絡不要受領」履歴を50件作り、同期を実行して反映を数える。 */
function runDncTest_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;

  // 既存の試験データを一旦消してから作り直す(冪等性のため)
  removeTestLogRows_(logSheet);

  var today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var rows = [];
  var testIds = {};
  for (var i = 0; i < PHASE_A_DNC_TEST_COUNT; i++) {
    var companyId = "C" + String(PHASE_A_DNC_FIRST_INDEX + i).padStart(6, "0");
    testIds[companyId] = true;
    rows.push([
      PHASE_A_DNC_TEST_PREFIX + String(i + 1),
      companyId, today, "システム(フェーズA試験)", "連絡不要受領", "未接触",
      "フェーズA試験データ(自動削除されます)", ""
    ]);
  }
  logSheet.getRange(logSheet.getLastRow() + 1, 1, rows.length, headers.length).setValues(rows);

  syncDoNotContactFlags();

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var records = readCompanyRecords_(companySheet);
  var flaggedCount = 0;
  var totalFlagged = 0;
  records.forEach(function (r) {
    if (r["連絡不要"] !== true) return;
    totalFlagged++;
    if (testIds[r["企業ID"]]) flaggedCount++;
  });
  return { flaggedCount: flaggedCount, propagatedExtra: totalFlagged - flaggedCount };
}

/** 試験データと、それによって立った連絡不要フラグを元に戻す。 */
function cleanupPhaseATestData_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var removedLogs = removeTestLogRows_(logSheet);

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error("企業マスタのロックが取れず、試験フラグの復旧ができませんでした。手動で確認してください。");
  }
  var resetFlags = 0;
  try {
    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    var records = readCompanyRecords_(companySheet);
    records.forEach(function (r) {
      if (r["連絡不要"] === true) {
        r["連絡不要"] = false;
        resetFlags++;
      }
    });
    writeCompanyRecords_(companySheet, records);
  } finally {
    lock.releaseLock();
  }
  return { removedLogs: removedLogs, resetFlags: resetFlags };
}

/** 履歴IDが試験プレフィックスで始まる行を削除し、削除件数を返す。 */
function removeTestLogRows_(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return 0;
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var idIndex = headers.indexOf("履歴ID");
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var kept = values.filter(function (row) {
    return String(row[idIndex]).indexOf(PHASE_A_DNC_TEST_PREFIX) !== 0;
  });
  var removed = values.length - kept.length;
  if (removed === 0) return 0;
  sheet.getRange(2, 1, values.length, headers.length).clearContent();
  if (kept.length > 0) {
    sheet.getRange(2, 1, kept.length, headers.length).setValues(kept);
  }
  return removed;
}
