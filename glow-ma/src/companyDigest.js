/* GLOW企業リレーション台帳: 会社ごとの「これまで」の要約(2026-11-07 小柳さん承認・改善⑤)
 *
 * 対応履歴から、電話の前に3秒で経緯が分かる1行を作る。外部のAIには送らない(決まった形に並べるだけ)。
 * 例: 「連絡 3回(電話2・手紙送付1) / 最後: 11/3 電話(6日前・担当者)「メモの先頭…」 / 次: 資料を送る」
 *
 * GAS(global.GlowCompanyDigest)と Node(module.exports)の両方で動く UMD 形式。
 * テスト: tests/glow_ma_todayList.test.mjs
 */
(function (global) {
  "use strict";

  var MEMO_HEAD_LENGTH = 28;
  var NO_HISTORY = "まだ連絡の記録はありません";

  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  /* Date(日本時間の日付にそろえる)・"2026/11/3"・"2026-11-03 10:00" を "YYYY-MM-DD" にする。読めなければ "" */
  function toDateString(v) {
    if (v instanceof Date) {
      if (isNaN(v.getTime())) return "";
      var jst = new Date(v.getTime() + 9 * 60 * 60 * 1000);
      return jst.getUTCFullYear() + "-" + pad2(jst.getUTCMonth() + 1) + "-" + pad2(jst.getUTCDate());
    }
    var m = /^(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})/.exec(String(v === null || v === undefined ? "" : v).trim());
    if (!m) return "";
    var dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
    if (dt.getUTCMonth() !== Number(m[2]) - 1) return "";
    return m[1] + "-" + pad2(Number(m[2])) + "-" + pad2(Number(m[3]));
  }

  function daysBetween(from, to) {
    if (!from || !to) return null;
    return Math.round((Date.parse(to + "T00:00:00Z") - Date.parse(from + "T00:00:00Z")) / 86400000);
  }

  function text(v) { return String(v === null || v === undefined ? "" : v).replace(/\s+/g, " ").trim(); }

  function buildCompanyDigest(history, todayString) {
    var rows = (history || []).map(function (h, i) { return { h: h, d: toDateString(h["日付"]), i: i }; })
      .filter(function (r) { return r.d; });
    if (!rows.length) return NO_HISTORY;
    rows.sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : a.i - b.i; });

    var counts = {}, order = [];
    rows.forEach(function (r) {
      var type = text(r.h["種別"]) || "その他";
      if (!counts[type]) { counts[type] = 0; order.push(type); }
      counts[type]++;
    });
    order.sort(function (a, b) { return counts[b] - counts[a]; });
    var parts = ["連絡 " + rows.length + "回(" + order.map(function (k) { return k + counts[k]; }).join("・") + ")"];

    var last = rows[rows.length - 1];
    var p = last.d.split("-");
    var ago = daysBetween(last.d, todayString);
    var who = text(last.h["担当者"]);
    var memo = text(last.h["内容メモ"]);
    if (memo.length > MEMO_HEAD_LENGTH) memo = memo.slice(0, MEMO_HEAD_LENGTH) + "…";
    var info = [ago === null ? "" : (ago === 0 ? "今日" : ago + "日前"), who].filter(Boolean).join("・");
    parts.push("最後: " + Number(p[1]) + "/" + Number(p[2]) + " " + (text(last.h["種別"]) || "その他") +
      (info ? "(" + info + ")" : "") + (memo ? "「" + memo + "」" : ""));

    var next = text(last.h["次回アクション"]);
    if (next) parts.push("次: " + next);
    return parts.join(" / ");
  }

  var api = {
    buildCompanyDigest: buildCompanyDigest,
    toDateString: toDateString,
    daysBetween: daysBetween,
    NO_HISTORY: NO_HISTORY
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCompanyDigest = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
