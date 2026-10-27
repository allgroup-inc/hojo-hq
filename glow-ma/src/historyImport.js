/* GLOW企業リレーション台帳 過去の手紙・架電記録の取り込みロジック(2026-10-25 作り直し)
 * ブラウザ相当のGAS(global.GlowHistoryImport)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_history_import.test.mjs で検証される。
 *
 * 旧版(HistoricalDataImporter.gs の独自実装)は列名が企業マスタ・対応履歴ログと合っておらず
 * (「企業名」「ステージ」「対応日時」等)、既に台帳にある会社も新規として二重登録する作りだった。
 * 一度も実行されていなかったため、データの破損は起きていない。
 *
 * 方針:
 * - 既に企業マスタにある会社(電話番号→会社名の順で突き合わせ)は、新規登録せず既存の企業IDに履歴を付ける
 * - 現在ステージは前へ進めるだけで、後戻りさせない(未接触→アプローチ実施→電話済み)
 * - 対応履歴ログは「企業ID・日付・種別」が同じものを二重に書かない(再実行しても増えない)
 */
(function (global) {
  "use strict";

  // 取り込みタブの見出しの言い換え(福田さんの手元の表の書き方をそのまま受ける)
  var HEADER_ALIASES = {
    会社名: ["会社名", "企業名", "法人名", "社名", "事業者名"],
    電話番号: ["電話番号", "電話", "TEL", "Tel", "tel", "代表電話"],
    手紙送付日: ["手紙送付日", "手紙発送日", "DM送付日", "DM発送日", "送付日", "発送日"],
    架電日: ["架電日", "電話日", "コール日", "架電日時"],
    通話結果: ["通話結果", "架電結果", "結果", "コール結果"],
    所在地: ["所在地", "住所"],
    代表者名: ["代表者名", "代表者", "代表"],
    業種: ["業種"],
    備考: ["備考", "メモ", "内容"]
  };

  var STAGE_ORDER = ["未接触", "アプローチ実施", "電話済み"];
  var LETTER_ROUTE = "②手紙DM";

  function headerIndex(headerRow) {
    var index = {};
    var cells = (headerRow || []).map(function (h) { return String(h || "").trim(); });
    Object.keys(HEADER_ALIASES).forEach(function (field) {
      var aliases = HEADER_ALIASES[field];
      for (var i = 0; i < aliases.length; i++) {
        var pos = cells.indexOf(aliases[i]);
        if (pos !== -1) { index[field] = pos; return; }
      }
    });
    return index;
  }

  function phoneDigits(value) {
    return String(value === undefined || value === null ? "" : value)
      .replace(/[０-９]/g, function (ch) { return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0); })
      .replace(/[^\d]/g, "");
  }

  function normalizeName(name) {
    return String(name || "").trim().replace(/[\s　]/g, "")
      .replace(/[０-９Ａ-Ｚａ-ｚ]/g, function (ch) { return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0); });
  }

  /** 日付をYYYY-MM-DDにする。読めない値は空文字(取り込まない)。 */
  function toDateString(value) {
    if (value === undefined || value === null || value === "") return "";
    if (Object.prototype.toString.call(value) === "[object Date]") {
      if (isNaN(value.getTime())) return "";
      return value.getFullYear() + "-" + pad2(value.getMonth() + 1) + "-" + pad2(value.getDate());
    }
    var text = String(value).trim()
      .replace(/[０-９]/g, function (ch) { return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0); });
    var m = text.match(/^(\d{4})[\/\-.年](\d{1,2})[\/\-.月](\d{1,2})日?/);
    if (!m) return "";
    var y = +m[1], mo = +m[2], d = +m[3];
    if (mo < 1 || mo > 12 || d < 1 || d > 31) return "";
    return y + "-" + pad2(mo) + "-" + pad2(d);
  }

  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  function laterDate(a, b) {
    var x = toDateString(a), y = toDateString(b);
    if (!x) return y;
    if (!y) return x;
    return x > y ? x : y;
  }

  function advanceStage(current, target) {
    var cur = String(current || "未接触");
    var curPos = STAGE_ORDER.indexOf(cur);
    if (curPos === -1) return cur; // 相談実施以降はそのまま(後戻りさせない)
    var targetPos = STAGE_ORDER.indexOf(target);
    return targetPos > curPos ? target : cur;
  }

  function buildCompanyId(sequenceNumber) {
    return "C" + String(sequenceNumber).padStart(6, "0");
  }

  /**
   * 取り込み計画を立てる(シートには書かない)。
   * rows: 取り込みタブの2行目以降(配列の配列)、headerRow: 1行目
   * existingRecords: 企業マスタのレコード(readCompanyRecords_ の形式)
   * existingLogs: 対応履歴ログの {企業ID, 日付, 種別} の配列(二重書き込み防止用)
   * options: { today: "YYYY-MM-DD", nextSequence: 次の企業ID番号, staffName: 担当者名 }
   * 戻り値: { updatedRecords, newRecords, logs, skipped, summary }
   */
  function planHistoryImport(headerRow, rows, existingRecords, existingLogs, options) {
    var idx = headerIndex(headerRow);
    if (idx.会社名 === undefined && idx.電話番号 === undefined) {
      return { error: "見出しに「会社名」か「電話番号」の列がありません", updatedRecords: [], newRecords: [], logs: [], skipped: [], summary: {} };
    }
    var byPhone = {}, byName = {};
    (existingRecords || []).forEach(function (r) {
      var p = phoneDigits(r["電話番号"]);
      if (p.length >= 10 && !byPhone[p]) byPhone[p] = r;
      var n = normalizeName(r["会社名"]);
      if (n && !byName[n]) byName[n] = r;
    });
    var logKeys = {};
    (existingLogs || []).forEach(function (l) {
      logKeys[l["企業ID"] + "|" + toDateString(l["日付"]) + "|" + l["種別"]] = true;
    });

    var seq = options.nextSequence;
    var touched = {};
    var newRecords = [], logs = [], skipped = [];
    var matchedCount = 0;

    function cell(row, field) {
      var i = idx[field];
      if (i === undefined) return "";
      var v = row[i];
      return v === undefined || v === null ? "" : v;
    }

    (rows || []).forEach(function (row, n) {
      var lineNo = n + 2;
      var name = String(cell(row, "会社名")).trim();
      var phone = phoneDigits(cell(row, "電話番号"));
      if (!name && !phone) return; // 空行
      var letter = toDateString(cell(row, "手紙送付日"));
      var call = toDateString(cell(row, "架電日"));
      var result = String(cell(row, "通話結果")).trim();
      var memo = String(cell(row, "備考")).trim();
      if (!letter && !call) {
        skipped.push({ line: lineNo, reason: "手紙送付日・架電日のどちらも読めません" });
        return;
      }

      var record = (phone.length >= 10 && byPhone[phone]) || (name && byName[normalizeName(name)]) || null;
      if (record) {
        matchedCount++;
      } else {
        if (!name) {
          skipped.push({ line: lineNo, reason: "台帳に無い電話番号で、会社名もありません" });
          return;
        }
        record = {
          企業ID: buildCompanyId(seq++),
          法人番号: "", 会社名: name, 業種: String(cell(row, "業種")), 規模: "",
          代表者名: String(cell(row, "代表者名")), 代表者年齢: "", 所在地: String(cell(row, "所在地")),
          流入ルート: [LETTER_ROUTE], 起点担当者_紹介元: "", 現在ステージ: "未接触", 提案商品: [],
          初期スコア: "", 反応スコア: "", 総合スコア: "", ランク: "",
          最終接触日: "", 次回アクション予定日: "", 次回アクション内容: "",
          担当者: options.staffName || "", 登録日: options.today, 備考: "過去の手紙・架電記録から登録",
          電話番号: String(cell(row, "電話番号")), 連絡不要: false
        };
        newRecords.push(record);
        if (phone.length >= 10) byPhone[phone] = record;
        byName[normalizeName(name)] = record;
      }

      if (letter) {
        var routes = Array.isArray(record["流入ルート"]) ? record["流入ルート"] : [];
        if (routes.indexOf(LETTER_ROUTE) === -1) record["流入ルート"] = routes.concat([LETTER_ROUTE]);
      }
      record["現在ステージ"] = advanceStage(record["現在ステージ"], call ? "電話済み" : "アプローチ実施");
      record["最終接触日"] = laterDate(record["最終接触日"], laterDate(letter, call));
      touched[record["企業ID"]] = record;

      function addLog(date, type, text) {
        var key = record["企業ID"] + "|" + date + "|" + type;
        if (logKeys[key]) return;
        logKeys[key] = true;
        logs.push({ 企業ID: record["企業ID"], 日付: date, 担当者: options.staffName || "", 種別: type,
                    対応相手: "", 内容メモ: text, 次回アクション: "" });
      }
      if (letter) addLog(letter, "手紙送付", "過去の手紙送付記録(取り込み " + options.today + ")" + (memo ? " / " + memo : ""));
      if (call) addLog(call, "電話", "過去の架電記録(取り込み " + options.today + ")" + (result ? " / 結果: " + result : "") + (!letter && memo ? " / " + memo : ""));
    });

    var newIds = {};
    newRecords.forEach(function (r) { newIds[r["企業ID"]] = true; });
    var updatedRecords = Object.keys(touched).filter(function (id) { return !newIds[id]; })
      .map(function (id) { return touched[id]; });

    return {
      updatedRecords: updatedRecords,
      newRecords: newRecords,
      logs: logs,
      skipped: skipped,
      summary: {
        matched: matchedCount,
        added: newRecords.length,
        logs: logs.length,
        skipped: skipped.length
      }
    };
  }

  var api = {
    HEADER_ALIASES: HEADER_ALIASES,
    headerIndex: headerIndex,
    toDateString: toDateString,
    advanceStage: advanceStage,
    planHistoryImport: planHistoryImport
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowHistoryImport = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
