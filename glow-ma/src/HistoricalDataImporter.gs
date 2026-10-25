/**
 * GLOW企業リレーション台帳: 過去の手紙・架電記録の取り込み(2026-10-25 作り直し)
 *
 * 福田さんが手元(Excel・BlueBean)で管理してきた「手紙を送った会社・電話した会社」の記録を、
 * 企業マスタと対応履歴ログへ取り込む。判断のロジックは historyImport.js(テストあり)。
 *
 * 使い方(福田さん):
 * 1. 台帳の「福田_履歴インポート」タブを開く(無ければ自己点検で自動作成される)
 * 2. 1行目の見出しはそのまま、2行目以降に手元の表を貼り付ける
 *    必須: 会社名 か 電話番号 / 手紙送付日 か 架電日。任意: 通話結果・所在地・代表者名・業種・備考
 *    (見出しは「企業名」「TEL」「DM送付日」等の言い換えも受け付ける。historyImport.js の HEADER_ALIASES)
 * 2. 数分以内に自動で取り込まれ、結果が「福田_インポート結果」タブに出る。
 *    取り込んだ表は「福田_履歴インポート_取込済_日時」へ名前を変えて残し、空のタブを作り直す(二重取り込み防止)
 *
 * 既に台帳にある会社(電話番号→会社名で突き合わせ)は新規登録せず、既存の会社に履歴を付ける。
 * 同じ会社・同じ日・同じ種別の履歴は二重に書かない。
 */

var FUKUDA_STAGING_SHEET_NAME = "福田_履歴インポート";
var FUKUDA_RESULT_SHEET_NAME = "福田_インポート結果";
var FUKUDA_STAGING_HEADERS = ["会社名", "電話番号", "手紙送付日", "架電日", "通話結果", "所在地", "代表者名", "業種", "備考"];
var FUKUDA_RESULT_HEADERS = ["実行日時", "読んだ行数", "既存の会社に追加", "新規登録", "対応履歴の追加", "取り込めなかった行", "取り込めなかった理由(先頭5件)"];

/** メニュー「福田データ：100件インポート」から手動で実行する入口 */
function importFukudaHistoricalData() {
  var result = runHistoryImport_();
  if (!result) {
    throw new Error("「" + FUKUDA_STAGING_SHEET_NAME + "」タブに取り込む行がありません。2行目以降に貼り付けてください。");
  }
  return result;
}

/** 毎分のトリガー(processQueuedVoiceLogs)から呼ぶ。取り込む行があるときだけ動く */
function runHistoryImportIfPending_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(FUKUDA_STAGING_SHEET_NAME);
  if (!sheet || sheet.getLastRow() < 2) return null;
  try {
    var result = runHistoryImport_();
    if (result) {
      recordOpsStatus_("過去の手紙・架電記録の取り込み", true,
        "既存に追加 " + result.summary.matched + "社 / 新規 " + result.summary.added +
        "社 / 履歴 " + result.summary.logs + "件 / 取り込めず " + result.summary.skipped + "行");
    }
    return result;
  } catch (error) {
    recordOpsStatus_("過去の手紙・架電記録の取り込み", false, String(error));
    notifyOpsFailure_("過去の手紙・架電記録の取り込み", String(error));
    return null;
  }
}

/** 取り込みタブが無ければ見出しつきで作る(自己点検から呼ぶ) */
function ensureHistoryImportSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (ss.getSheetByName(FUKUDA_STAGING_SHEET_NAME)) return false;
  var sheet = ss.insertSheet(FUKUDA_STAGING_SHEET_NAME);
  sheet.getRange(1, 1, 1, FUKUDA_STAGING_HEADERS.length).setValues([FUKUDA_STAGING_HEADERS]).setFontWeight("bold");
  sheet.setFrozenRows(1);
  return true;
}

function runHistoryImport_() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(60000)) {
    throw new Error("他の処理が台帳を操作中のため、取り込みを開始できません。");
  }
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var staging = ss.getSheetByName(FUKUDA_STAGING_SHEET_NAME);
    if (!staging || staging.getLastRow() < 2) return null;
    var values = staging.getDataRange().getValues();
    var headerRow = values[0];
    var rows = values.slice(1);

    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
    var existingRecords = readCompanyRecords_(companySheet);
    var existingLogs = readHistoryLogKeys_(logSheet);

    var plan = GlowHistoryImport.planHistoryImport(headerRow, rows, existingRecords, existingLogs, {
      today: Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd"),
      nextSequence: GlowDedupe.nextSequenceNumber(existingRecords),
      staffName: ""
    });
    if (plan.error) throw new Error(plan.error);

    // 既存レコードは plan の中で直接更新されている。新規分を足して書き戻す
    if (plan.updatedRecords.length || plan.newRecords.length) {
      writeCompanyRecords_(companySheet, existingRecords.concat(plan.newRecords));
    }
    appendHistoryLogs_(logSheet, plan.logs);

    var result = { rowsRead: rows.length, summary: plan.summary, skipped: plan.skipped };
    writeHistoryImportResult_(ss, result);
    archiveStagingSheet_(ss, staging);
    return result;
  } finally {
    lock.releaseLock();
  }
}

function readHistoryLogKeys_(logSheet) {
  if (!logSheet || logSheet.getLastRow() < 2) return [];
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var values = logSheet.getRange(2, 1, logSheet.getLastRow() - 1, headers.length).getValues();
  var idI = headers.indexOf("企業ID"), dateI = headers.indexOf("日付"), typeI = headers.indexOf("種別");
  return values.filter(function (r) { return r[idI]; }).map(function (r) {
    return { 企業ID: r[idI], 日付: r[dateI], 種別: r[typeI] };
  });
}

function appendHistoryLogs_(logSheet, logs) {
  if (!logs.length) return;
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var rows = logs.map(function (log) {
    log["履歴ID"] = "H-" + Utilities.getUuid();
    return headers.map(function (h) { return log[h] === undefined ? "" : log[h]; });
  });
  logSheet.getRange(logSheet.getLastRow() + 1, 1, rows.length, headers.length).setValues(rows);
}

function writeHistoryImportResult_(ss, result) {
  var sheet = ss.getSheetByName(FUKUDA_RESULT_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(FUKUDA_RESULT_SHEET_NAME);
  }
  if (sheet.getLastRow() === 0 || String(sheet.getRange(1, 2).getValue()) !== FUKUDA_RESULT_HEADERS[1]) {
    sheet.getRange(1, 1, 1, FUKUDA_RESULT_HEADERS.length).setValues([FUKUDA_RESULT_HEADERS]).setFontWeight("bold");
  }
  var reasons = result.skipped.slice(0, 5).map(function (s) { return s.line + "行目: " + s.reason; }).join(" / ");
  sheet.appendRow([
    Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm"),
    result.rowsRead, result.summary.matched, result.summary.added, result.summary.logs,
    result.summary.skipped, reasons
  ]);
}

/** 取り込み済みの表を名前を変えて残し、空の取り込みタブを作り直す(二重取り込み防止) */
function archiveStagingSheet_(ss, staging) {
  var stamp = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyyMMdd_HHmm");
  staging.setName(FUKUDA_STAGING_SHEET_NAME + "_取込済_" + stamp);
  ensureHistoryImportSheet_();
}
