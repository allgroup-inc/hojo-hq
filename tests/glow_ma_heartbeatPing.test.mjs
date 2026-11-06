// glow-ma 生存信号(healthchecks.io への ping)の判定ロジックのテスト。URL・IDはすべて架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const h = require("../glow-ma/src/heartbeatPing.js");

const UUID_URL = "https://hc-ping.com/00000000-0000-4000-8000-000000000000";
const SLUG_URL = "https://hc-ping.com/AAAAAAAAAAAAAAAAAAAAAA/glow-ma-test";
const MIN = 60 * 1000;
const NOW = Date.UTC(2026, 10, 6, 3, 0, 0);

function decide(over) {
  return h.decidePing({ nowMs: NOW, state: null, completed: true, stepErrors: 0, elapsedMs: 30 * 1000, ...over });
}

test("送り先は hc-ping.com の決まった形だけを受け付ける", () => {
  assert.equal(h.normalizePingUrl(UUID_URL), UUID_URL);
  assert.equal(h.normalizePingUrl("  " + UUID_URL + "/ "), UUID_URL);
  assert.equal(h.normalizePingUrl(SLUG_URL), SLUG_URL);
  // 未設定・空
  assert.equal(h.normalizePingUrl(""), "");
  assert.equal(h.normalizePingUrl(null), "");
  assert.equal(h.normalizePingUrl(undefined), "");
  // http・別のホスト・似せたホスト・クエリ付き・成功以外の末尾は送らない
  assert.equal(h.normalizePingUrl(UUID_URL.replace("https:", "http:")), "");
  assert.equal(h.normalizePingUrl("https://example.com/00000000-0000-4000-8000-000000000000"), "");
  assert.equal(h.normalizePingUrl("https://hc-ping.com.example.com/00000000-0000-4000-8000-000000000000"), "");
  assert.equal(h.normalizePingUrl(UUID_URL + "?rid=1"), "");
  assert.equal(h.normalizePingUrl(UUID_URL + "/fail"), "");
  assert.equal(h.normalizePingUrl(UUID_URL + "/start"), "");
  assert.equal(h.normalizePingUrl("https://hc-ping.com/not-a-uuid"), "");
  assert.equal(h.normalizePingUrl("https://hc-ping.com/AAAAAAAAAAAAAAAAAAAAAA/Glow_MA"), ""); // slug は小文字・数字・ハイフン
});

test("最初の1回は送る", () => {
  assert.deepEqual(decide({}), { send: true, reason: "" });
});

test("処理が最後まで終わっていなければ送らない", () => {
  const d = decide({ completed: false });
  assert.equal(d.send, false);
  assert.match(d.reason, /最後まで/);
});

test("この実行で台帳の処理が1つでも失敗していたら送らない(次のきれいな実行に回す)", () => {
  const d = decide({ stepErrors: 1 });
  assert.equal(d.send, false);
  assert.match(d.reason, /失敗/);
});

test("前回うまく送れたら、60分たつまで送らない", () => {
  const state = { at: NOW - 59 * MIN, ok: true };
  assert.equal(decide({ state }).send, false);
  assert.equal(decide({ state: { at: NOW - 60 * MIN, ok: true } }).send, true);
});

test("前回送れなかったら、10分あけて送り直す(毎分は叩かない)", () => {
  assert.equal(decide({ state: { at: NOW - 9 * MIN, ok: false } }).send, false);
  assert.equal(decide({ state: { at: NOW - 10 * MIN, ok: false } }).send, true);
});

test("前回の時刻が未来(時計のずれ・壊れた値)なら、待たずに送る", () => {
  assert.equal(decide({ state: { at: NOW + 30 * MIN, ok: true } }).send, true);
});

test("実行の残り時間が少ないときは送らず、次の実行に回す(6分の上限を越えない)", () => {
  assert.equal(decide({ elapsedMs: 4 * MIN }).send, false);
  assert.equal(decide({ elapsedMs: 4 * MIN - 1 }).send, true);
});

test("記録した状態は読み戻せ、壊れた値は「記録なし」として扱う", () => {
  const s = h.serializeState({ at: NOW, ok: true });
  assert.deepEqual(h.parseState(s), { at: NOW, ok: true });
  assert.deepEqual(h.parseState(h.serializeState({ at: NOW, ok: false })), { at: NOW, ok: false });
  assert.equal(h.parseState(""), null);
  assert.equal(h.parseState(null), null);
  assert.equal(h.parseState("{壊れた"), null);
  assert.equal(h.parseState('{"at":"x","ok":true}'), null);
  assert.equal(h.parseState('{"at":-5,"ok":true}'), null);
});

test("成功は 200 だけ", () => {
  assert.equal(h.isPingSuccess(200), true);
  [0, 201, 301, 404, 429, 500].forEach((c) => assert.equal(h.isPingSuccess(c), false));
});

test("ログに出すエラー文から、送り先のURLを消す(URLを知ると誰でも生存信号を送れるため)", () => {
  const msg = h.describeError(new Error("DNS error: " + UUID_URL + " (Address unavailable)"));
  assert.ok(!msg.includes("hc-ping.com/0000"));
  assert.match(msg, /DNS error/);
  assert.equal(h.describeError(null), "不明なエラー");
  assert.ok(h.describeError("x".repeat(500)).length <= 200);
});
