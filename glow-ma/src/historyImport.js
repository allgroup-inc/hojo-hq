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
    架電日: ["架電日", "電話日", "コール日", "架電日時", "面談日", "対応日"],
    通話結果: ["通話結果", "架電結果", "結果", "コール結果"],
    所在地: ["所在地", "住所"],
    代表者名: ["代表者名", "代表者", "代表"],
    業種: ["業種"],
    備考: ["備考", "メモ", "内容"],
    メール送信日: ["メール送信日", "メール送付日", "メール日", "メール"]
  };

  var STAGE_ORDER = ["未接触", "アプローチ実施", "電話済み", "相談実施"];
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

  /**
   * 日付をYYYY-MM-DDにする。読めない値は空文字(取り込まない)。
   * 年の無い「9月18日」「9/18」は、today(YYYY-MM-DD)を渡したときだけ読む。today以前で一番近い日付にする
   * (2026-10-28: 福田さんの表は年なしで、100行すべてが「日付が読めない」で取り込めなかった)。
   */
  function toDateString(value, today) {
    if (value === undefined || value === null || value === "") return "";
    if (Object.prototype.toString.call(value) === "[object Date]") {
      if (isNaN(value.getTime())) return "";
      return value.getFullYear() + "-" + pad2(value.getMonth() + 1) + "-" + pad2(value.getDate());
    }
    var text = String(value).trim()
      .replace(/[０-９]/g, function (ch) { return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0); });
    var m = text.match(/^(\d{4})[\/\-.年](\d{1,2})[\/\-.月](\d{1,2})日?/);
    if (!m) {
      var md = text.match(/^(\d{1,2})[\/\-.月](\d{1,2})日?/);
      var base = /^\d{4}-\d{2}-\d{2}$/.test(String(today || "")) ? String(today) : "";
      if (!md || !base) return "";
      var guessYear = +base.slice(0, 4);
      if (pad2(+md[1]) + "-" + pad2(+md[2]) > base.slice(5)) guessYear -= 1;
      m = [text, String(guessYear), md[1], md[2]];
    }
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

  /**
   * 通話結果の欄から、対応履歴の種別を決める(2026-10-30 福田さん: 入電や、録音できなかった面談もこのタブで残したい)。
   * 「面談」「訪問」「来店」「来社」→ 面談実施 / 「入電」→ 入電 / 「アポ」→ アポ獲得 / それ以外 → 電話
   */
  function callTypeOf(result) {
    var text = String(result || "");
    if (/面談|訪問|来店|来社/.test(text)) return "面談実施";
    if (/入電/.test(text)) return "入電";
    if (/アポ/.test(text)) return "アポ獲得";
    return "電話";
  }

  var CALL_LOG_LABELS = { 電話: "過去の架電記録", 入電: "入電の記録", アポ獲得: "アポ獲得の記録", 面談実施: "面談の記録" };

  /**
   * 取り込んだ表を、取込済タブ(1枚にまとめる)へ足す形にする(2026-10-30 福田さん: 取込済タブが増え続ける)。
   * 見出しの言い換えは標準の見出し(FIELDS)にそろえる。空行は除く。
   * 戻り値: [取込日時, 会社名, 電話番号, 手紙送付日, 架電日, 通話結果, 所在地, 代表者名, 業種, 備考] の配列
   */
  var ARCHIVE_FIELDS = ["会社名", "電話番号", "手紙送付日", "架電日", "通話結果", "所在地", "代表者名", "業種", "備考", "メール送信日"];
  function toArchiveRows(headerRow, rows, stamp) {
    var idx = headerIndex(headerRow);
    return (rows || []).map(function (row) {
      return [stamp].concat(ARCHIVE_FIELDS.map(function (f) {
        var v = idx[f] === undefined ? "" : row[idx[f]];
        if (Object.prototype.toString.call(v) === "[object Date]") return toDateString(v);
        return v === undefined || v === null ? "" : v;
      }));
    }).filter(function (r) {
      return r.slice(1).some(function (v) { return String(v).trim() !== ""; });
    });
  }

  /**
   * 取り込みを行う時間帯(2026-10-30 福田さん: 入力の途中で取り込まれてしまうため、時刻を決めてほしい)。
   * 毎日 8時と22時(日本時間)。nowMs の時点で最後に来た取り込み時刻を "YYYY-MM-DD HH" で返す。
   * 呼び出し側は、前回の値と違うときだけ取り込む(=各時刻に1回)。
   */
  var IMPORT_HOURS = [8, 22];
  function currentImportSlot(nowMs) {
    var jst = new Date(Number(nowMs) + 9 * 60 * 60 * 1000);
    var hour = jst.getUTCHours();
    var slotHour = -1;
    IMPORT_HOURS.forEach(function (h) { if (hour >= h) slotHour = h; });
    if (slotHour === -1) {
      jst = new Date(jst.getTime() - 24 * 60 * 60 * 1000);
      slotHour = IMPORT_HOURS[IMPORT_HOURS.length - 1];
    }
    return jst.getUTCFullYear() + "-" + pad2(jst.getUTCMonth() + 1) + "-" + pad2(jst.getUTCDate()) + " " + pad2(slotHour);
  }

  /**
   * 取り込みのあいだに書き換えられた行・書き足された行を返す(取り込みタブに残して次回に回す)。
   * 2026-10-30 13:46: 福田さんが日付を書いている途中に取り込みが走り、日付の無い行として取り込めず、
   * その直後に日付の入った行が取込済へ移されて台帳に載らなかった。読んだときと同じ行だけを取込済へ移す。
   */
  function changedRows(plannedRows, currentRows) {
    function key(row) {
      return JSON.stringify((row || []).map(function (v) {
        if (Object.prototype.toString.call(v) === "[object Date]") return "D" + v.getTime();
        return v === undefined || v === null ? "" : String(v);
      }).join("\u0001").replace(/\u0001+$/, ""));
    }
    return (currentRows || []).filter(function (row, i) {
      var empty = !(row || []).some(function (v) { return String(v === undefined || v === null ? "" : v).trim() !== ""; });
      if (empty) return false;
      return i >= (plannedRows || []).length || key(row) !== key(plannedRows[i]);
    });
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
      var letter = toDateString(cell(row, "手紙送付日"), options.today);
      var call = toDateString(cell(row, "架電日"), options.today);
      var mail = toDateString(cell(row, "メール送信日"), options.today);
      var result = String(cell(row, "通話結果")).trim();
      var memo = String(cell(row, "備考")).trim();
      if (!letter && !call && !mail) {
        skipped.push({ line: lineNo, reason: "手紙送付日・架電日・メール送信日のどれも読めません" });
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
      var callType = callTypeOf(result);
      record["現在ステージ"] = advanceStage(record["現在ステージ"],
        !call ? "アプローチ実施" : callType === "面談実施" ? "相談実施" : "電話済み");
      record["最終接触日"] = laterDate(record["最終接触日"], laterDate(laterDate(letter, call), mail));
      touched[record["企業ID"]] = record;

      function addLog(date, type, text) {
        var key = record["企業ID"] + "|" + date + "|" + type;
        if (logKeys[key]) return;
        logKeys[key] = true;
        logs.push({ 企業ID: record["企業ID"], 日付: date, 担当者: options.staffName || "", 種別: type,
                    対応相手: "", 内容メモ: text, 次回アクション: "" });
      }
      // 備考は、入電・面談などの記録があればそちらへ(内容そのものなので)、無ければ手紙の記録へ付ける
      var memoOnCall = call && (!letter || callType !== "電話");
      if (letter) addLog(letter, "手紙送付", "過去の手紙送付記録(取り込み " + options.today + ")" + (memo && !memoOnCall ? " / " + memo : ""));
      if (mail) addLog(mail, "メール送信", "メール送信の記録(取り込み " + options.today + ")" + (memo && !memoOnCall && !letter ? " / " + memo : ""));
      if (call) {
        addLog(call, callType, CALL_LOG_LABELS[callType] + "(取り込み " + options.today + ")" +
          (result && callType === "電話" ? " / 結果: " + result : "") + (memo && memoOnCall ? " / " + memo : ""));
      }
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
    callTypeOf: callTypeOf,
    IMPORT_HOURS: IMPORT_HOURS,
    currentImportSlot: currentImportSlot,
    ARCHIVE_FIELDS: ARCHIVE_FIELDS,
    toArchiveRows: toArchiveRows,
    changedRows: changedRows,
    planHistoryImport: planHistoryImport
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowHistoryImport = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
