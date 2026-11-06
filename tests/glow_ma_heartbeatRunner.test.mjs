// glow-ma 生存信号の入口(HeartbeatRunner.gs)を、GASのサービスを偽物にして動かすテスト。
// 本物の台帳・本物の healthchecks.io には一切つながない。URLは架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const URL = "https://hc-ping.com/00000000-0000-4000-8000-000000000000";
const src = (p) => readFileSync(new URL_(p, import.meta.url), "utf8");
const URL_ = globalThis.URL;

function makeContext({ pingUrl = URL, state = null, core, fetch, elapsedMs = 20000 } = {}) {
  const props = { HEALTHCHECKS_PING_URL: pingUrl, HEALTHCHECKS_LAST_PING: state };
  const calls = { fetch: [], ops: [], logs: [] };
  const ctx = {
    console: {
      warn: (m) => calls.logs.push(String(m)),
      error: (m) => calls.logs.push(String(m)),
      log: (m) => calls.logs.push(String(m)),
    },
    Logger: { log: (m) => calls.logs.push(String(m)) },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: (k) => (props[k] === undefined ? null : props[k]),
        setProperty: (k, v) => { props[k] = v; },
      }),
    },
    UrlFetchApp: {
      fetch: (u, opt) => {
        calls.fetch.push({ u, opt });
        if (fetch) return fetch(u, opt);
        return { getResponseCode: () => 200 };
      },
    },
    recordOpsStatus_: (name, ok, detail) => calls.ops.push({ name, ok, detail }),
    processQueuedVoiceLogsCore_: () => { if (core) core(ctx); },
    voiceRunElapsedMs_: () => elapsedMs,
    VOICE_RUN_STEP_ERRORS: 0,
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src("../glow-ma/src/heartbeatPing.js"), ctx);
  vm.runInContext(src("../glow-ma/src/HeartbeatRunner.gs"), ctx);
  return { ctx, props, calls };
}

test("最後まで正常に終わったら、決まったURLへGETを1回送り、結果を記録する", () => {
  const { ctx, props, calls } = makeContext();
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
  assert.equal(calls.fetch[0].u, URL);
  assert.equal(calls.fetch[0].opt.method, "get");
  assert.equal(calls.fetch[0].opt.payload, undefined); // 中身は何も送らない
  assert.equal(JSON.parse(props.HEALTHCHECKS_LAST_PING).ok, true);
  assert.equal(calls.ops[0].ok, true);
});

test("続けて動いても、1時間以内は送らない", () => {
  const { ctx, calls } = makeContext();
  ctx.processQueuedVoiceLogs();
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
});

test("送り先が未設定・形が違うなら何も送らない(今までどおり動く)", () => {
  for (const pingUrl of [null, "", "https://example.com/x"]) {
    const { ctx, calls } = makeContext({ pingUrl });
    ctx.processQueuedVoiceLogs();
    assert.equal(calls.fetch.length, 0);
    assert.equal(calls.ops.length, 0);
  }
});

test("本体が止まったら送らず、例外はそのまま上へ(トリガーの失敗通知が届く)", () => {
  const { ctx, calls } = makeContext({ core: () => { throw new Error("台帳を開けません"); } });
  assert.throws(() => ctx.processQueuedVoiceLogs(), /台帳を開けません/);
  assert.equal(calls.fetch.length, 0);
});

test("台帳の処理が1つでも失敗した実行では送らない", () => {
  const { ctx, calls } = makeContext({ core: (c) => { c.VOICE_RUN_STEP_ERRORS++; } });
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 0);
});

test("前の実行の失敗数を持ち越さない(実行ごとに0から数える)", () => {
  const { ctx, calls } = makeContext();
  ctx.VOICE_RUN_STEP_ERRORS = 3;
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
});

test("送信が例外になっても台帳の処理へ持ち込まず、URLはログに出さない", () => {
  const { ctx, props, calls } = makeContext({
    fetch: (u) => { throw new Error("DNS error: " + u); },
  });
  assert.doesNotThrow(() => ctx.processQueuedVoiceLogs());
  assert.equal(JSON.parse(props.HEALTHCHECKS_LAST_PING).ok, false);
  const written = calls.logs.join("\n") + JSON.stringify(calls.ops);
  assert.ok(!written.includes("hc-ping.com/0000"), written);
  assert.equal(calls.ops[0].ok, false);
});

test("HTTPの失敗(500など)も失敗として記録し、10分後まで送り直さない", () => {
  const { ctx, props, calls } = makeContext({ fetch: () => ({ getResponseCode: () => 500 }) });
  ctx.processQueuedVoiceLogs();
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
  assert.equal(JSON.parse(props.HEALTHCHECKS_LAST_PING).ok, false);
  assert.match(calls.ops[0].detail, /HTTP 500/);
});

test("記録(稼働状況タブ・プロパティ)が壊れても台帳の処理を止めない", () => {
  const { ctx, calls } = makeContext();
  ctx.recordOpsStatus_ = () => { throw new Error("タブに書けません"); };
  assert.doesNotThrow(() => ctx.processQueuedVoiceLogs());
  assert.equal(calls.fetch.length, 1);
  const broken = makeContext();
  broken.ctx.PropertiesService = { getScriptProperties: () => { throw new Error("プロパティを読めません"); } };
  assert.doesNotThrow(() => broken.ctx.processQueuedVoiceLogs());
});

test("実行開始から4分を過ぎていたら送らない", () => {
  const { ctx, calls } = makeContext({ elapsedMs: 4 * 60 * 1000 });
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 0);
});

test("設定の確かめ用の表示に、送り先のURLを出さない", () => {
  const { ctx } = makeContext();
  const shown = ctx.showHeartbeatStatus();
  assert.match(shown, /設定済み/);
  assert.ok(!shown.includes("hc-ping.com"));
});
