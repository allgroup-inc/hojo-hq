// glow-ma 生存信号の入口(HeartbeatRunner.gs)を、GASのサービスを偽物にして動かすテスト。
// 本物の台帳・本物の healthchecks.io には一切つながない。URLは架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const URL = "https://hc-ping.com/00000000-0000-4000-8000-000000000000";
const src = (p) => readFileSync(new URL_(p, import.meta.url), "utf8");
const URL_ = globalThis.URL;

function makeContext({ pingUrl = URL, state = null, core, fetch, elapsedMs = 20000, lockFree = true } = {}) {
  const props = { HEALTHCHECKS_PING_URL: pingUrl, HEALTHCHECKS_LAST_PING: state };
  const calls = { fetch: [], ops: [], logs: [], uuid: 0 };
  function makeLock(name) {
    return {
      tryLock: () => {
        if (!lockFree || ctx.__locks[name]) return false;
        ctx.__locks[name] = true;
        return true;
      },
      releaseLock: () => { ctx.__locks[name] = false; },
    };
  }
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
    // ScriptLock はスクリプト全体で1つ。UserLock は実行している人ごとに別(__user で切り替える)。
    // UserLock に頼ると、持ち主の違うトリガーどうしが排他されないことをテストで見分けられるようにする
    LockService: {
      getScriptLock: () => makeLock("script"),
      getUserLock: () => makeLock("user:" + ctx.__user),
    },
    Utilities: { getUuid: () => "attempt-" + (++calls.uuid) },
    __user: "owner",
    __locks: {},
    recordOpsStatus_: (name, ok, detail) => calls.ops.push({ name, ok, detail }),
    processQueuedVoiceLogsCore_: () => { if (core) core(ctx); },
    voiceRunElapsedMs_: () => elapsedMs,
    VOICE_RUN_STEP_ERRORS: 0,
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src("../glow-ma/src/heartbeatPing.js"), ctx);
  vm.runInContext(src("../glow-ma/src/HeartbeatRunner.gs"), ctx);
  ctx.__fetchCount = () => calls.fetch.length;
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

test("通信中に次の実行が重なっても、同じ信号を2回送らない(先に番を取ってから送る)", () => {
  let inner = null;
  const { ctx, calls } = makeContext({
    fetch: () => {
      // 1つ目の通信の最中に、2つ目の実行が最後まで走ったとみなす
      if (!inner) { inner = true; ctx.processQueuedVoiceLogs(); }
      return { getResponseCode: () => 200 };
    },
  });
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
});

test("通信の前に「送信中(失敗扱い)」を書いておき、途中で打ち切られても10分後に送り直せる", () => {
  let seen = null;
  const { ctx, props } = makeContext({
    fetch: () => { seen = JSON.parse(props.HEALTHCHECKS_LAST_PING); return { getResponseCode: () => 200 }; },
  });
  ctx.processQueuedVoiceLogs();
  assert.equal(seen.ok, false); // 通信の時点では失敗扱い → 打ち切られたら10分後に送り直す
  assert.equal(JSON.parse(props.HEALTHCHECKS_LAST_PING).ok, true); // 送れたら成功に書き換える
});

test("番を取るロックが取れなければ、待たずに諦めて次の実行に回す", () => {
  const { ctx, calls } = makeContext({ lockFree: false });
  assert.doesNotThrow(() => ctx.processQueuedVoiceLogs());
  assert.equal(calls.fetch.length, 0);
});

test("ロックの仕組みそのものが例外を出しても、台帳の処理を止めない", () => {
  const { ctx, calls } = makeContext();
  ctx.LockService = { getScriptLock: () => { throw new Error("ロックを取れません"); }, getUserLock: () => { throw new Error("ロックを取れません"); } };
  assert.doesNotThrow(() => ctx.processQueuedVoiceLogs());
  assert.equal(calls.fetch.length, 0);
});

test("通信の後はロックを放している(通信中に他の実行を止めない)", () => {
  let lockedDuringFetch = null;
  const { ctx } = makeContext({
    fetch: () => { lockedDuringFetch = Object.values(ctx.__locks).some(Boolean); return { getResponseCode: () => 200 }; },
  });
  ctx.processQueuedVoiceLogs();
  assert.equal(lockedDuringFetch, false);
  assert.equal(Object.values(ctx.__locks).some(Boolean), false);
});

test("送れなかった10分後に送り直し、成功したら次は60分後", () => {
  let code = 500;
  let t = Date.UTC(2026, 10, 6, 3, 0, 0);
  const { ctx, calls } = makeContext({ fetch: () => ({ getResponseCode: () => code }) });
  vm.runInContext("Date", ctx).now = () => t; // GAS側(仮想の環境)の時計だけを進める
  {
    ctx.processQueuedVoiceLogs();                  // 3:00 失敗
    t += 9 * 60 * 1000; ctx.processQueuedVoiceLogs();  // 3:09 まだ送らない
    t += 1 * 60 * 1000; code = 200; ctx.processQueuedVoiceLogs(); // 3:10 送り直して成功
    t += 59 * 60 * 1000; ctx.processQueuedVoiceLogs(); // 4:09 まだ送らない
    t += 1 * 60 * 1000; ctx.processQueuedVoiceLogs();  // 4:10 送る
    assert.equal(calls.fetch.length, 3);
  }
});

test("4分を過ぎた実行は送らず、次の普通の実行で送る", () => {
  const { ctx, calls } = makeContext({ elapsedMs: 4 * 60 * 1000 + 1 });
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 0);
  ctx.voiceRunElapsedMs_ = () => 15000;
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
});

// ---- 2026-11-06 レビュー対応: 古い送信結果の上書き・持ち主の違う実行どうしの排他 ----

function clock(ctx, start) {
  const c = { t: start };
  vm.runInContext("Date", ctx).now = () => c.t;
  return c;
}
const T0 = Date.UTC(2026, 10, 6, 3, 0, 0);
const MIN = 60 * 1000;
const stateOf = (props) => JSON.parse(props.HEALTHCHECKS_LAST_PING);

test("送信が長引いて次の送信が先に終わっても、古い送信の失敗で新しい成功を上書きしない", () => {
  let first = true;
  let c;
  const { ctx, props, calls } = makeContext({
    fetch: () => {
      if (first) {
        first = false;
        // 1つ目の通信が戻る前に11分たち、2つ目の実行が番を取って成功した
        c.t = T0 + 11 * MIN;
        ctx.processQueuedVoiceLogs();
        return { getResponseCode: () => 500 }; // 1つ目は遅れて失敗で戻る
      }
      return { getResponseCode: () => 200 };
    },
  });
  c = clock(ctx, T0);
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 2);
  const st = stateOf(props);
  assert.equal(st.ok, true);            // 新しい成功が残る
  assert.equal(st.at, T0 + 11 * MIN);   // 新しい送信の時刻
  assert.equal(st.id, "attempt-2");
  assert.equal(calls.ops.length, 1);    // 稼働状況タブにも、新しい結果だけを書く
  assert.equal(calls.ops[0].ok, true);
});

test("古い送信が遅れて成功で戻っても、新しい送信の失敗を消さない(10分後の送り直しが止まらない)", () => {
  let first = true;
  let c;
  const { ctx, props } = makeContext({
    fetch: () => {
      if (first) {
        first = false;
        c.t = T0 + 11 * MIN;
        ctx.processQueuedVoiceLogs(); // 2つ目は失敗
        return { getResponseCode: () => 200 }; // 1つ目は遅れて成功
      }
      return { getResponseCode: () => 500 };
    },
  });
  c = clock(ctx, T0);
  ctx.processQueuedVoiceLogs();
  const st = stateOf(props);
  assert.equal(st.ok, false);
  assert.equal(st.at, T0 + 11 * MIN);
  assert.equal(st.id, "attempt-2");
  // 古い成功(T0)で上書きされていれば、次は T0+60分まで送らないが、正しくは 2つ目+10分で送り直す
  c.t = T0 + 21 * MIN;
  const before = calls_count(ctx);
  ctx.processQueuedVoiceLogs();
  assert.equal(calls_count(ctx), before + 1);
});
function calls_count(ctx) { return ctx.__fetchCount(); }

test("持ち主の違うトリガー(別の人)の実行が番取りの最中に割り込んでも、送るのは1回だけ", () => {
  let interrupted = false;
  const { ctx, props, calls } = makeContext();
  // 番取りで状態を読んだ直後に、別の人の実行が割り込んだとみなす
  const real = ctx.PropertiesService.getScriptProperties;
  ctx.PropertiesService = {
    getScriptProperties: () => {
      const p = real();
      return {
        getProperty: (k) => {
          const v = p.getProperty(k);
          if (k === "HEALTHCHECKS_LAST_PING" && !interrupted) {
            interrupted = true;
            const me = ctx.__user;
            ctx.__user = "other-editor";
            ctx.processQueuedVoiceLogs();
            ctx.__user = me;
          }
          return v;
        },
        setProperty: p.setProperty,
      };
    },
  };
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
  assert.equal(stateOf(props).ok, true);
});

test("結果を書くときにロックが取れなければ書かず、失敗扱いのまま10分後に送り直す", () => {
  let c;
  const { ctx, props, calls } = makeContext({
    fetch: () => {
      if (calls.fetch.length === 1) ctx.__locks.script = true; // 1回目の通信中に、録音の送信が ScriptLock を取った
      return { getResponseCode: () => 200 };
    },
  });
  c = clock(ctx, T0);
  assert.doesNotThrow(() => ctx.processQueuedVoiceLogs());
  assert.equal(stateOf(props).ok, false);
  assert.equal(calls.ops.length, 0);
  ctx.__locks.script = false;
  c.t = T0 + 10 * MIN;
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 2);
  assert.equal(stateOf(props).ok, true);
});

test("識別子が無い古い形の状態(前の版で書いたもの)も読め、時期が来れば送って新しい形で書き直す", () => {
  const { ctx, props, calls } = makeContext({ state: JSON.stringify({ at: 0, ok: true }) });
  ctx.processQueuedVoiceLogs();
  assert.equal(calls.fetch.length, 1);
  assert.ok(stateOf(props).id);
});
