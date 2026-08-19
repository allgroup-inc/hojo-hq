/**
 * アポ管理台帳: シート初期化
 *
 * 使い方(人間が一度だけ行う):
 * 1. アポ管理専用のスプレッドシートを新規作成する(glow-maのM&A台帳とは別ファイル。
 *    共有相手もアポ管理のスタッフのみにする)
 * 2. 拡張機能 > Apps Script からこのプロジェクトを紐付け、`clasp push` でコードを反映する
 * 3. Apps Scriptエディタで ensureApoTabs を一度実行する(冪等。何度実行しても安全)
 *
 * 注意: 各タブに列を手動で追加しないこと。読み書きは列位置に依存するため、
 * 列を増やす場合は schema.js の配列末尾に追加して ensureApoTabs を再実行する。
 */
function ensureApoTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureTabWithHeaders_(ss, ApoSchema.STAFF_SHEET_NAME, ApoSchema.STAFF_HEADERS);
  ensureTabWithHeaders_(ss, ApoSchema.APPOINTMENT_SHEET_NAME, ApoSchema.APPOINTMENT_HEADERS);
  ensureTabWithHeaders_(ss, ApoSchema.HISTORY_SHEET_NAME, ApoSchema.HISTORY_HEADERS);
  ensureTabWithHeaders_(ss, ApoSchema.SETTINGS_SHEET_NAME, ApoSchema.SETTINGS_HEADERS);
  applyValidations_(ss);
  Logger.log("アポ管理台帳の4タブを確認・作成しました。");
}

function ensureTabWithHeaders_(ss, sheetName, headers) {
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }
  var range = sheet.getRange(1, 1, 1, headers.length);
  var current = range.getValues()[0];
  var needsWrite = headers.some(function (header, index) { return current[index] !== header; });
  if (needsWrite) {
    range.setValues([headers]);
    sheet.setFrozenRows(1);
  }
}

/**
 * 表記ゆれ防止のプルダウン(入力規則)を設定する。
 * シート直接編集は運用上禁止(READMEに明記)だが、万一の編集時の事故を減らすための保険。
 */
function applyValidations_(ss) {
  var maxRows = 1000;

  var staffSheet = ss.getSheetByName(ApoSchema.STAFF_SHEET_NAME);
  setDropdown_(staffSheet, ApoSchema.STAFF_HEADERS, "役割", ApoSchema.STAFF_ROLES, maxRows);
  var activeIndex = ApoSchema.STAFF_HEADERS.indexOf("有効") + 1;
  staffSheet.getRange(2, activeIndex, maxRows, 1).insertCheckboxes();

  var apoSheet = ss.getSheetByName(ApoSchema.APPOINTMENT_SHEET_NAME);
  setDropdown_(apoSheet, ApoSchema.APPOINTMENT_HEADERS, "形式", ApoSchema.APPOINTMENT_FORMATS, maxRows);
  setDropdown_(apoSheet, ApoSchema.APPOINTMENT_HEADERS, "温度感", ApoSchema.TEMPERATURES, maxRows);
  setDropdown_(apoSheet, ApoSchema.APPOINTMENT_HEADERS, "ステータス", ApoSchema.APPOINTMENT_STATUSES, maxRows);
  setDropdown_(apoSheet, ApoSchema.APPOINTMENT_HEADERS, "アポ種別", ApoSchema.APPOINTMENT_KINDS, maxRows);
}

function setDropdown_(sheet, headers, columnName, values, maxRows) {
  var columnIndex = headers.indexOf(columnName) + 1;
  if (columnIndex === 0) return;
  var rule = SpreadsheetApp.newDataValidation().requireValueInList(values, true).build();
  sheet.getRange(2, columnIndex, maxRows, 1).setDataValidation(rule);
}
