/**
 * GLOW企業リレーション台帳: シート初期化
 * Apps Scriptエディタの関数選択で ensureLedgerTabs を選び、実行ボタンで手動実行する。
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」の
 * 4タブが(存在しなければ)作成され、1行目に見出しが設定される。
 * 対応履歴ログの「種別」列には、表記ゆれによる反応スコア集計漏れを防ぐため
 * プルダウン入力規則(GlowSchema.INTERACTION_TYPES)を設定する。
 */
function ensureLedgerTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureTab_(ss, GlowSchema.COMPANY_MASTER_SHEET_NAME, GlowSchema.COMPANY_MASTER_HEADERS);
  var logSheet = ensureTab_(ss, GlowSchema.INTERACTION_LOG_SHEET_NAME, GlowSchema.INTERACTION_LOG_HEADERS);
  applyInteractionTypeValidation_(logSheet);
  ensureTab_(ss, GlowSchema.PARTNER_MASTER_SHEET_NAME, GlowSchema.PARTNER_MASTER_HEADERS);
  ensureTab_(ss, GlowSchema.SETTINGS_SHEET_NAME, GlowSchema.SETTINGS_HEADERS);
}

function ensureTab_(spreadsheet, sheetName, headers) {
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  return sheet;
}

function applyInteractionTypeValidation_(sheet) {
  var typeColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("種別") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.INTERACTION_TYPES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, typeColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}
