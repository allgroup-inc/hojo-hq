/* GLOW企業リレーション台帳: 「今日の連絡先」(2026-11-07 小柳さん承認・改善③)
 *
 * 3,000社を超える台帳から、毎朝「今日はここに連絡する」という短いリストを作る。台帳は書き換えない。
 * 並べる順(上から埋めて、決めた件数で止める):
 *   1. 予定日     … 次回アクション予定日が今日まで(人が決めた予定を最優先する。7日以内に連絡していても出す)
 *   2. フォロー   … 電話などをしたことがあり、ランクごとの間隔(掘り起こしアラートと同じ A30・B90・C180・D365日。
 *                    紹介①はA扱い)を過ぎた会社。長く空いた順
 *   3. 手紙のあと … 手紙を送って5〜45日たち、そのあと電話などをしていない会社(手紙 → 架電の流れ)。送った日の古い順
 *   4. 新規       … まだ連絡したことの無い会社。事前選定ランクS → 事前選定スコア → 総合スコアの高い順
 * 出さない会社: 連絡不要・成約/見送り・電話番号なし・7日以内に連絡済み(予定日の会社を除く)
 *
 * GAS(global.GlowTodayList)と Node(module.exports)の両方で動く UMD 形式。
 * テスト: tests/glow_ma_todayList.test.mjs
 */
(function (global) {
  "use strict";

  function dep(name, file) {
    if (typeof module !== "undefined" && module.exports) return require(file);
    return global[name];
  }
  // GASではファイルの読み込み順が決まらないため、使うときに取り出す(callMode.js と同じ)
  function Alerting() { return dep("GlowAlerting", "./alerting.js"); }
  function Digest() { return dep("GlowCompanyDigest", "./companyDigest.js"); }

  var DEFAULT_SIZE = 10;
  var RECENT_DAYS = 7;
  var LETTER_MIN_DAYS = 5;
  var LETTER_MAX_DAYS = 45;
  var LETTER_TYPE = "手紙送付";
  var TODAY_LIST_SHEET_NAME = "今日の連絡先";
  var TODAY_LIST_HEADERS = [
    "順位", "区分", "理由", "企業ID", "会社名", "電話番号", "ランク", "事前選定ランク",
    "最終接触日", "次回アクション予定日", "これまで", "おすすめ"
  ];

  function toDateString(v) { return Digest().toDateString(v); }
  function daysBetween(a, b) { return Digest().daysBetween(a, b); }

  function num(v) {
    var n = Number(String(v === null || v === undefined ? "" : v).trim());
    return String(v === null || v === undefined ? "" : v).trim() === "" || isNaN(n) ? -Infinity : n;
  }

  function routesOf(c) {
    var r = c["流入ルート"];
    if (Array.isArray(r)) return r;
    return r ? String(r).split("、") : [];
  }

  /* 会社の対応履歴から、最後の連絡(手紙以外)と最後の手紙の日付 */
  function touchSummary(company, history) {
    var lastContact = toDateString(company["最終接触日"]), lastLetter = "";
    (history || []).forEach(function (h) {
      var dt = toDateString(h["日付"]);
      if (!dt) return;
      if (String(h["種別"] || "") === LETTER_TYPE) { if (dt > lastLetter) lastLetter = dt; return; }
      if (dt > lastContact) lastContact = dt;
    });
    // 最終接触日が手紙の日付と同じだけなら(手紙で最終接触日が進んだだけ)、連絡したことにしない
    var hasNonLetter = (history || []).some(function (h) { return String(h["種別"] || "") !== LETTER_TYPE && toDateString(h["日付"]); });
    if (!hasNonLetter && lastContact && lastContact === lastLetter) lastContact = "";
    return { lastContact: lastContact, lastLetter: lastLetter };
  }

  function buildTodayList(companies, interactionsByCompany, todayString, opts) {
    var size = (opts && opts.size) || DEFAULT_SIZE;
    var config = Alerting().DEFAULT_CONFIG;
    var buckets = { 予定日: [], フォロー: [], 手紙のあと: [], 新規: [] };

    (companies || []).forEach(function (c) {
      var id = String(c["企業ID"] || "").trim();
      if (!id) return;
      if (c["連絡不要"] === true) return;
      if ((config.terminalStages || []).indexOf(c["現在ステージ"]) !== -1) return;
      if (!String(c["電話番号"] || "").trim()) return;
      var history = (interactionsByCompany || {})[id] || [];
      var touch = touchSummary(c, history);
      var due = toDateString(c["次回アクション予定日"]);
      var sinceContact = touch.lastContact ? daysBetween(touch.lastContact, todayString) : null;
      var entry = { c: c, history: history, touch: touch, due: due };

      if (due && due <= todayString) {
        entry.reason = due === todayString ? "今日が予定日" : "予定日を" + daysBetween(due, todayString) + "日過ぎた";
        entry.key = [due];
        buckets.予定日.push(entry);
        return;
      }
      if (sinceContact !== null && sinceContact < RECENT_DAYS) return;
      if (touch.lastContact) {
        var rank = Alerting().resolveEffectiveRank({ 流入ルート: routesOf(c), ランク: c["ランク"] }, config);
        var cycle = config.cycleDaysByRank[rank];
        if (typeof cycle === "number" && sinceContact >= cycle) {
          entry.reason = "前回の連絡から" + sinceContact + "日(ランク" + rank + "は" + cycle + "日ごと)";
          entry.key = [-sinceContact];
          buckets.フォロー.push(entry);
        }
        return;
      }
      if (touch.lastLetter) {
        var sinceLetter = daysBetween(touch.lastLetter, todayString);
        if (sinceLetter >= LETTER_MIN_DAYS && sinceLetter <= LETTER_MAX_DAYS) {
          entry.reason = "手紙を送って" + sinceLetter + "日。まだ電話していない";
          entry.key = [-sinceLetter];
          buckets.手紙のあと.push(entry);
        }
        return; // 手紙を送ったばかり・時期を過ぎた会社は、新規には入れない
      }
      var pre = String(c["事前選定ランク"] || "").trim();
      entry.reason = "まだ連絡していない(事前選定 " + (pre || "なし") + ")";
      entry.key = [pre === "S" ? 0 : 1, -num(c["事前選定スコア"]), -num(c["総合スコア"])];
      buckets.新規.push(entry);
    });

    function cmp(a, b) {
      for (var i = 0; i < a.key.length; i++) {
        if (a.key[i] !== b.key[i]) return a.key[i] < b.key[i] ? -1 : 1;
      }
      var ia = String(a.c["企業ID"]), ib = String(b.c["企業ID"]);
      return ia < ib ? -1 : ia > ib ? 1 : 0;
    }

    var out = [];
    ["予定日", "フォロー", "手紙のあと", "新規"].forEach(function (kind) {
      buckets[kind].sort(cmp).forEach(function (e) {
        if (out.length >= size) return;
        out.push({
          順位: out.length + 1,
          区分: kind,
          理由: e.reason,
          企業ID: String(e.c["企業ID"]),
          会社名: String(e.c["会社名"] || ""),
          電話番号: String(e.c["電話番号"] || "").trim(),
          ランク: String(e.c["ランク"] || ""),
          事前選定ランク: String(e.c["事前選定ランク"] || ""),
          最終接触日: e.touch.lastContact,
          次回アクション予定日: e.due,
          これまで: Digest().buildCompanyDigest(e.history, todayString),
          おすすめ: Alerting().determineNextBestAction({ 流入ルート: routesOf(e.c), ランク: e.c["ランク"], 現在ステージ: e.c["現在ステージ"] }, config)
        });
      });
    });
    return out;
  }

  var api = {
    buildTodayList: buildTodayList,
    TODAY_LIST_SHEET_NAME: TODAY_LIST_SHEET_NAME,
    TODAY_LIST_HEADERS: TODAY_LIST_HEADERS,
    DEFAULT_SIZE: DEFAULT_SIZE
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowTodayList = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
