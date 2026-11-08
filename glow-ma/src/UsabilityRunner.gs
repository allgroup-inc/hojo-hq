/**
 * GLOW企業リレーション台帳: 使いやすさの改善(2026-11-07 小柳さん承認「7つとも推奨で進める」)
 *
 * ③ 今日の連絡先: 毎朝の日次メンテナンスの中で「今日の連絡先」タブを作り直す(todayList.js)
 * ⑤ これまでの要約: 管理画面の詳細と「今日の連絡先」に1行の要約を出す(companyDigest.js)。外部のAIには送らない
 * ⑥ 使っていないタブ: 自己点検の中で1回だけ非表示にする(tabTidy.js)。消さない
 *
 * どれも失敗しても台帳の他の処理を止めない(日次メンテナンス・自己点検の各ステップとして独立して動く)。
 */

var TODAY_LIST_SIZE_PROPERTY = "TODAY_LIST_SIZE";
var TAB_TIDY_DONE_PROPERTY = "TAB_TIDY_V1_DONE";

/** セルに書く文字の先頭が = + - @ のときは数式と読まれないよう ' を付ける */
function todayListCellText_(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return value;
  var text = String(value);
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

/**
 * 「今日の連絡先」タブを作り直す(日次メンテナンスから呼ぶ。エディタから手で実行してもよい)。
 * 台帳の企業マスタ・対応履歴ログは読むだけで、書き換えない。
 */
function updateTodayList() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) throw new Error("企業マスタのタブが見つかりません");
  var companies = readCompanyRecords_(companySheet);
  var logs = readInteractionsByCompanyId_(ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME));
  var today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var size = Number(PropertiesService.getScriptProperties().getProperty(TODAY_LIST_SIZE_PROPERTY)) || GlowTodayList.DEFAULT_SIZE;
  var list = GlowTodayList.buildTodayList(companies, logs, today, { size: size });

  var headers = GlowTodayList.TODAY_LIST_HEADERS;
  var sheet = ss.getSheetByName(GlowTodayList.TODAY_LIST_SHEET_NAME) || ss.insertSheet(GlowTodayList.TODAY_LIST_SHEET_NAME);
  sheet.clearContents();
  var values = [headers].concat(list.map(function (e) {
    return headers.map(function (h) { return todayListCellText_(e[h]); });
  }));
  // 電話番号の先頭の0が消えないよう、文字として書く
  sheet.getRange(1, 1, values.length, headers.length).setNumberFormat("@").setValues(values);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1).setNote(today + " に自動で作成(毎朝の日次メンテナンス)。台帳の記録は書き換えていません");
  return list.length + "件";
}

/** 使っていないタブを1回だけ非表示にする(自己点検から呼ぶ)。2回目以降は何もしない。 */
function tidyUnusedTabsOnce_() {
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty(TAB_TIDY_DONE_PROPERTY)) return "済み";
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = ss.getSheets().map(function (s) {
    return { name: s.getName(), hidden: s.isSheetHidden(), rows: Math.max(s.getLastRow() - 1, 0) };
  });
  var names = GlowTabTidy.planHide(sheets);
  names.forEach(function (name) {
    var sheet = ss.getSheetByName(name);
    if (sheet && !sheet.isSheetHidden()) sheet.hideSheet();
  });
  props.setProperty(TAB_TIDY_DONE_PROPERTY, Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm"));
  return names.length ? names.length + "個を非表示にした(" + names.join("・") + ")" : "非表示にするタブは無かった";
}
