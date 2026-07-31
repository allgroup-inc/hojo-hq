/**
 * GLOW企業リレーション台帳: シート初期化
 * Apps Scriptエディタの関数選択で ensureLedgerTabs を選び、実行ボタンで手動実行する。
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」
 * 「レター下書き」「ダッシュボード」の6タブが(存在しなければ)作成され、1行目に見出しが設定される。
 * 対応履歴ログの「種別」「対応相手」列、レター下書きの「ステータス」列には、
 * 表記ゆれによる集計漏れを防ぐためプルダウン入力規則を設定する。
 * 企業マスタの「電話番号」列は先頭ゼロ落ちを防ぐためプレーンテキスト形式を強制し、
 * 「連絡不要」列にはチェックボックスの入力規則を設定する。
 */
function ensureLedgerTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ensureTab_(ss, GlowSchema.COMPANY_MASTER_SHEET_NAME, GlowSchema.COMPANY_MASTER_HEADERS);
  applyPhoneNumberFormat_(companySheet);
  applyDoNotContactValidation_(companySheet);
  var logSheet = ensureTab_(ss, GlowSchema.INTERACTION_LOG_SHEET_NAME, GlowSchema.INTERACTION_LOG_HEADERS);
  applyInteractionTypeValidation_(logSheet);
  applyRespondentValidation_(logSheet);
  ensureTab_(ss, GlowSchema.PARTNER_MASTER_SHEET_NAME, GlowSchema.PARTNER_MASTER_HEADERS);
  ensureTab_(ss, GlowSchema.SETTINGS_SHEET_NAME, GlowSchema.SETTINGS_HEADERS);
  var letterDraftSheet = ensureTab_(ss, GlowSchema.LETTER_DRAFT_SHEET_NAME, GlowSchema.LETTER_DRAFT_HEADERS);
  applyLetterDraftStatusValidation_(letterDraftSheet);
  ensureTab_(ss, GlowSchema.DASHBOARD_SHEET_NAME, GlowSchema.DASHBOARD_PLACEHOLDER_HEADERS);
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

function applyRespondentValidation_(sheet) {
  var respondentColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("対応相手") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.RESPONDENT_TYPES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, respondentColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}

function applyLetterDraftStatusValidation_(sheet) {
  var statusColumnIndex = GlowSchema.LETTER_DRAFT_HEADERS.indexOf("ステータス") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.LETTER_DRAFT_STATUSES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, statusColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}

function applyPhoneNumberFormat_(sheet) {
  var phoneColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("電話番号") + 1;
  sheet.getRange(2, phoneColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setNumberFormat("@");
}

function applyDoNotContactValidation_(sheet) {
  var dncColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("連絡不要") + 1;
  var rule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  sheet.getRange(2, dncColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}
