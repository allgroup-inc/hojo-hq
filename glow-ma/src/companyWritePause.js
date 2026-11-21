/**
 * GLOW企業リレーション台帳: 企業マスタの書き込みの緊急停止スイッチ(判定だけの純ロジック)
 *
 * 背景(2026-11-16 小柳さん指示): 企業マスタを一括で書き直す処理(writeCompanyRecords_)を、人の判断で
 * 止められるようにする。止める場所は台帳のセルではなく、スクリプトプロパティに置く
 * (企業マスタのセルを使う止め方は採らない)。Apps Script 側の操作は CompanyWritePauseRunner.gs。
 *
 * 決まり:
 *   - 止めるのは、台帳を編集できる人なら誰でもよい(気づいた人がすぐ止められるように)。確認と理由が要る
 *   - 再開できるのは台帳の持ち主(代表者)だけ。「再開」と入力し、承認の記録(誰がいつ承認したか)を書く
 *   - 自動では再開しない(期限なし)。値が壊れている・読めないときは「停止中」として扱う(止まる側に倒す)
 *   - 止めた・再開した・再開を断った記録を、直近の分だけ残す(全件は通知メールと実行記録に残る)
 */
(function (global) {
  "use strict";

  var STATE_PROPERTY = "COMPANY_WRITE_PAUSE";
  var HISTORY_PROPERTY = "COMPANY_WRITE_PAUSE_HISTORY";
  var OPS_NAME = "企業マスタの書き込み停止スイッチ";
  var RESUME_PHRASE = "再開";
  var REASON_MAX = 120;
  // スクリプトプロパティは1つの値につき約9KBまで。日本語は1文字3バイトとして、余裕を持って切る
  var HISTORY_MAX_ENTRIES = 12;
  var HISTORY_MAX_CHARS = 2400;

  function text(value) {
    return value === undefined || value === null ? "" : String(value).replace(/\s+/g, " ").trim();
  }

  /**
   * 保存されている停止の状態を読む。空(未設定)なら動いている。
   * 空ではないのに読めない値は、停止中として扱う(止まる側に倒す)。
   */
  function parseState(raw) {
    if (raw === undefined || raw === null || raw === "") return { paused: false };
    try {
      var parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && parsed.paused === true) {
        return { paused: true, at: text(parsed.at), by: text(parsed.by), reason: text(parsed.reason) };
      }
    } catch (error) {
      // 下で停止中として扱う
    }
    return { paused: true, at: "", by: "", reason: "停止の記録が読めないため、停止中として扱っています", unreadable: true };
  }

  /** 理由・承認の記録(必ず書いてもらう)。空なら ok:false */
  function validateNote(value) {
    var note = text(value);
    if (note === "") return { ok: false, note: "" };
    return { ok: true, note: note.slice(0, REASON_MAX) };
  }

  function buildStopState(at, by, reason) {
    return JSON.stringify({ paused: true, at: text(at), by: text(by), reason: text(reason).slice(0, REASON_MAX) });
  }

  /** 再開してよい人か。台帳の持ち主だけ。どちらかのアドレスが分からないときは断る */
  function canResume(actorEmail, ownerEmail) {
    var actor = text(actorEmail).toLowerCase();
    var owner = text(ownerEmail).toLowerCase();
    if (actor === "" || owner === "") {
      return { ok: false, reason: "操作している人、または台帳の持ち主を確かめられませんでした" };
    }
    if (actor !== owner) {
      return { ok: false, reason: "再開できるのは台帳の持ち主(代表者)だけです" };
    }
    return { ok: true, reason: "" };
  }

  function isResumePhrase(value) {
    return text(value) === RESUME_PHRASE;
  }

  /** 操作の記録を1件足す(新しい順)。件数と長さの上限を超えた古い分は落とす */
  function appendHistory(historyRaw, entry) {
    var list = readHistory(historyRaw);
    list.unshift({
      at: text(entry.at), action: text(entry.action), by: text(entry.by),
      note: text(entry.note).slice(0, REASON_MAX)
    });
    list = list.slice(0, HISTORY_MAX_ENTRIES);
    while (list.length > 1 && JSON.stringify(list).length > HISTORY_MAX_CHARS) list.pop();
    return JSON.stringify(list);
  }

  function readHistory(historyRaw) {
    try {
      var parsed = JSON.parse(historyRaw || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }

  var ACTION_LABELS = { stop: "停止", resume: "再開", resume_refused: "再開を断った" };

  function describeHistory(historyRaw) {
    var list = readHistory(historyRaw);
    if (list.length === 0) return "(操作の記録はありません)";
    return list.map(function (e) {
      return e.at + " " + (ACTION_LABELS[e.action] || e.action) + " / " + e.by + " / " + e.note;
    }).join("\n");
  }

  /** 停止中の説明(稼働状況タブ・画面・通知に出す) */
  function describeState(state) {
    if (!state || !state.paused) return "動いています(停止していません)";
    if (state.unreadable) return state.reason;
    return "停止中(停止 " + state.at + " / 操作 " + state.by + " / 理由: " + state.reason + ")";
  }

  /** 停止してから何日たったか(分からなければ -1) */
  function pausedDays(state, nowMs) {
    if (!state || !state.paused || !state.at) return -1;
    var started = Date.parse(String(state.at).replace(" ", "T") + ":00+09:00");
    if (isNaN(started)) return -1;
    return Math.floor((Number(nowMs) - started) / (24 * 60 * 60 * 1000));
  }

  /** 止めている間に、書こうとした処理へ返す文 */
  function pausedMessage(state) {
    return "企業マスタの書き込みは停止中のため、書きませんでした(企業マスタは変更していません)。" +
      describeState(state) + "。再開は、代表者の承認の後、台帳のメニュー「GLOW台帳 → 企業マスタの書き込みを再開する」から";
  }

  var api = {
    STATE_PROPERTY: STATE_PROPERTY,
    HISTORY_PROPERTY: HISTORY_PROPERTY,
    OPS_NAME: OPS_NAME,
    RESUME_PHRASE: RESUME_PHRASE,
    HISTORY_MAX_ENTRIES: HISTORY_MAX_ENTRIES,
    HISTORY_MAX_CHARS: HISTORY_MAX_CHARS,
    parseState: parseState,
    validateNote: validateNote,
    buildStopState: buildStopState,
    canResume: canResume,
    isResumePhrase: isResumePhrase,
    appendHistory: appendHistory,
    readHistory: readHistory,
    describeHistory: describeHistory,
    describeState: describeState,
    pausedDays: pausedDays,
    pausedMessage: pausedMessage
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCompanyWritePause = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
