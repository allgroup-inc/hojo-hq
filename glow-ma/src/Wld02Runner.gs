/**
 * GLOW企業リレーション台帳: 世界の架け橋 WLD-02 の記録タブと、毎週の相談企業KPI(2026-11-07 小柳さん承認・改善⑦)
 *
 * 設計書(非公開リポジトリ glow-docs-private の WLD-02 設計書 v0 §2・§3・§6・§9)の段階4・5にあたる。
 * - 記録タブを4つ用意する(既にあれば触らない。既存のタブの列は変えない)
 *     面談確認記録 / 掲載契約記録 / 企業ID対応表 / 週次KPI(世界の架け橋)
 * - 日次メンテナンスの中で、まだ集計していない週があれば、前の週(月曜〜日曜)を集計して週次KPIに書く
 *   (月曜の朝に前の週を数える。同じ週は上書きし、二重に数えない。読めない記録があれば「取得不能」とし、
 *    集計済みの週を上書きしない — 計算は wld02Kpi.js)
 * - 法人番号の点検(nameMatch.js の auditCorporateNumbers)の件数を、稼働状況タブに書く(番号そのものは書かない)
 * 名寄せの候補は人の確認を待つ。企業IDの統合はここでは一切しない(企業ID対応表は人が記録する)。
 */

var WLD02_DONE_WEEK_PROPERTY = "WLD02_LAST_DONE_WEEK";

function wld02Tabs_() {
  return {
    confirmations: { name: "面談確認記録", headers: ["確認ID", "企業ID", "元の履歴ID", "面談日", "形式", "事業", "判定", "確認者", "確認日時", "取消", "取消の理由", "取消した人", "取消日時", "メモ"] },
    contracts: { name: "掲載契約記録", headers: ["契約ID", "企業ID", "契約成立日", "状態", "状態が変わった日", "理由", "記録者", "記録日時"] },
    idMap: { name: "企業ID対応表", headers: ["旧企業ID", "統合後の企業ID", "統合日", "理由", "記録者", "取消"] },
    weekly: { name: "週次KPI(世界の架け橋)", headers: GlowWld02Kpi.WEEKLY_FIELDS }
  };
}

/** タブが無ければ見出し付きで作る。あれば何も変えない(人が足した列や書式を消さない)。作ったら true */
function ensureWld02Tab_(ss, def) {
  var sheet = ss.getSheetByName(def.name);
  if (sheet) return false;
  sheet = ss.insertSheet(def.name);
  sheet.getRange(1, 1, 1, def.headers.length).setValues([def.headers]);
  sheet.setFrozenRows(1);
  return true;
}

/** 1行目を見出しとして、2行目以降を {見出し: 値} の配列にする。タブが無ければ null(=読めなかった) */
function readSheetObjects_(sheet) {
  if (!sheet) return null;
  var lastRow = sheet.getLastRow(), lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol < 1) return [];
  var values = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  var headers = values[0].map(function (h) { return String(h || "").trim(); });
  return values.slice(1).filter(function (r) {
    return r.some(function (v) { return v !== "" && v !== null && v !== false; });
  }).map(function (r) {
    var o = {};
    headers.forEach(function (h, i) { if (h) o[h] = r[i]; });
    return o;
  });
}

/** 日次メンテナンスから呼ぶ。まだ集計していない前の週があれば集計する。結果を1行で返す */
function runWld02WeeklyIfDue_() {
  var props = PropertiesService.getScriptProperties();
  var weekStart = GlowWld02Kpi.previousWeekStart(Date.now());
  if (props.getProperty(WLD02_DONE_WEEK_PROPERTY) === weekStart) return "済み(" + weekStart + " の週)";

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tabs = wld02Tabs_();
  var created = Object.keys(tabs).filter(function (k) { return ensureWld02Tab_(ss, tabs[k]); });

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : null;
  var sources = {
    confirmations: readSheetObjects_(ss.getSheetByName(tabs.confirmations.name)),
    contracts: readSheetObjects_(ss.getSheetByName(tabs.contracts.name)),
    idMap: readSheetObjects_(ss.getSheetByName(tabs.idMap.name)),
    history: readSheetObjects_(ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME)),
    companies: companies
  };
  var now = new Date();
  var result = GlowWld02Kpi.buildWeeklyRow(sources, {
    weekStart: weekStart,
    runAt: Utilities.formatDate(now, "Asia/Tokyo", "yyyy-MM-dd HH:mm"),
    runId: Utilities.getUuid().slice(0, 8)
  });
  var row = result.row;

  var weeklySheet = ss.getSheetByName(tabs.weekly.name);
  // 「2026-11-02」と書いた週の開始日は、シートが日付に変えて返すことがある。日付の文字にそろえてから比べる
  // (そろえないと同じ週を別の週とみなし、行が二重に増える)
  var existing = (readSheetObjects_(weeklySheet) || []).map(function (r) {
    var w = r["週の開始日"];
    if (Object.prototype.toString.call(w) === "[object Date]") r["週の開始日"] = Utilities.formatDate(w, "Asia/Tokyo", "yyyy-MM-dd");
    return r;
  });
  var plan = GlowWld02Kpi.planWeeklyUpsert(existing, row);
  var values = [GlowWld02Kpi.WEEKLY_FIELDS.map(function (f) { return row[f] === undefined ? "" : row[f]; })];
  if (plan.action === "update") {
    weeklySheet.getRange(plan.index + 2, 1, 1, values[0].length).setValues(values);
  } else if (plan.action === "append") {
    weeklySheet.getRange(weeklySheet.getLastRow() + 1, 1, 1, values[0].length).setValues(values);
  }

  var ok = row["状態"] === "集計済み";
  if (ok) props.setProperty(WLD02_DONE_WEEK_PROPERTY, weekStart);
  var detail = weekStart + " の週: " + row["状態"] +
    (ok ? " / 相談 " + row["相談企業数_累計"] + "社(週内 " + row["相談企業数_週内の新規"] + ")" +
      " / 掲載契約 " + row["掲載契約企業数_累計"] + "社 / 確認待ちの面談 " + row["確認待ちの面談数"] + "件" : "") +
    (plan.action === "keep" ? " / 集計済みの値を残した" : "") +
    (created.length ? " / タブを作成: " + created.map(function (k) { return tabs[k].name; }).join("・") : "") +
    (result.problems.length ? " / 要確認 " + result.problems.length + "件" : "");
  recordOpsStatus_("世界の架け橋 週次KPI", ok, detail);
  if (result.problems.length) console.warn("世界の架け橋 週次KPI の要確認: " + result.problems.join(" | "));

  if (companies) {
    var c = GlowWld02NameMatch.auditCorporateNumbers(companies).counts;
    recordOpsStatus_("法人番号の点検", true, "確かめた " + c.確かめた会社 + "社 / 正しい形 " + c.正しい形 +
      " / 未入力 " + c.未入力 + " / 正しくない " + c.正しくない + " / 重複の組 " + c.重複の組);
  }
  return detail;
}
