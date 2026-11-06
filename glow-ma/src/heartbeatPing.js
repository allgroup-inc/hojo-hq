/* GLOW企業リレーション台帳 生存信号(healthchecks.io への ping)の判定ロジック
 *
 * 2026-11-06 小柳さん承認(監視C+D方式・まずローカル実装と合成テストまで)。
 * 毎分の処理(processQueuedVoiceLogs)が最後まで正常に終わったことを確かめてから、
 * 1時間に1回だけ healthchecks.io へ「生きています」の信号を送る。信号が途切れたら
 * healthchecks.io 側が知らせる(GitHub の定期実行に頼らない監視)。
 *
 * 守ること:
 * - 送るのは決まった形の hc-ping.com のURLへの GET だけ。台帳の中身・顧客情報は一切送らない
 * - 送れなくても台帳の通常処理を止めない(呼び出し側 HeartbeatRunner.gs が例外をすべて受け止める)
 * - 送り先のURLはログに出さない(URLを知る人は誰でも生存信号を送れてしまうため)
 *
 * GAS(global.GlowHeartbeat)と Node(module.exports)の両方で動く UMD 形式。
 * Node 側は tests/glow_ma_heartbeatPing.test.mjs で検証する。
 */
(function (global) {
  "use strict";

  var PING_INTERVAL_MS = 60 * 60 * 1000;      // うまく送れたら、次は60分後
  var RETRY_INTERVAL_MS = 10 * 60 * 1000;     // 送れなかったら、10分あけて送り直す
  var MAX_ELAPSED_MS = 4 * 60 * 1000;         // 実行開始から4分を過ぎたら送らない(6分の上限に近づけない)

  // https://hc-ping.com/<UUID> または https://hc-ping.com/<ping key 22文字>/<slug>
  var UUID_PATH = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  var KEY_SLUG_PATH = /^[A-Za-z0-9_-]{22}\/[a-z0-9-]+$/;
  var PREFIX = "https://hc-ping.com/";

  function normalizePingUrl(raw) {
    var s = String(raw === null || raw === undefined ? "" : raw).trim().replace(/\/+$/, "");
    if (s.indexOf(PREFIX) !== 0) return "";
    var path = s.slice(PREFIX.length);
    if (UUID_PATH.test(path.toLowerCase()) && path.indexOf("/") < 0) return PREFIX + path.toLowerCase();
    if (KEY_SLUG_PATH.test(path)) return s;
    return "";
  }

  /* input: { nowMs, state: {at, ok} | null, completed, stepErrors, elapsedMs }
   * 戻り値: { send: boolean, reason: 送らない理由(送るときは "") } */
  function decidePing(input) {
    var p = input || {};
    if (!p.completed) return { send: false, reason: "処理が最後まで終わっていない" };
    if (p.stepErrors > 0) return { send: false, reason: "この実行で台帳の処理が失敗している" };
    if (!(p.elapsedMs < MAX_ELAPSED_MS)) return { send: false, reason: "実行の残り時間が少ない" };
    var state = p.state;
    if (!state) return { send: true, reason: "" };
    var since = p.nowMs - state.at;
    if (since < 0) return { send: true, reason: "" };
    var wait = state.ok ? PING_INTERVAL_MS : RETRY_INTERVAL_MS;
    if (since < wait) return { send: false, reason: "前回から時間がたっていない" };
    return { send: true, reason: "" };
  }

  function parseState(raw) {
    if (!raw) return null;
    try {
      var o = JSON.parse(String(raw));
      if (!o || typeof o.at !== "number" || !isFinite(o.at) || o.at < 0) return null;
      return { at: o.at, ok: o.ok === true };
    } catch (e) {
      return null;
    }
  }

  function serializeState(state) {
    return JSON.stringify({ at: state.at, ok: state.ok === true });
  }

  function isPingSuccess(statusCode) {
    return statusCode === 200;
  }

  function describeError(error) {
    if (error === null || error === undefined) return "不明なエラー";
    var text = String(error && error.message ? error.message : error);
    return text.replace(/https?:\/\/\S+/g, "(送り先URL)").slice(0, 200);
  }

  var api = {
    PING_INTERVAL_MS: PING_INTERVAL_MS,
    RETRY_INTERVAL_MS: RETRY_INTERVAL_MS,
    MAX_ELAPSED_MS: MAX_ELAPSED_MS,
    normalizePingUrl: normalizePingUrl,
    decidePing: decidePing,
    parseState: parseState,
    serializeState: serializeState,
    isPingSuccess: isPingSuccess,
    describeError: describeError
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowHeartbeat = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
