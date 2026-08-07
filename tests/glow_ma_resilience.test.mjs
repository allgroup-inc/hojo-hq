import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const resilience = require("../glow-ma/src/resilience.js");

test("isRetryableHttpStatus: 429と5xxのみ再試行対象", () => {
  assert.equal(resilience.isRetryableHttpStatus(429), true);
  assert.equal(resilience.isRetryableHttpStatus(500), true);
  assert.equal(resilience.isRetryableHttpStatus(503), true);
  assert.equal(resilience.isRetryableHttpStatus(599), true);
  assert.equal(resilience.isRetryableHttpStatus(600), false);
  assert.equal(resilience.isRetryableHttpStatus(401), false);
  assert.equal(resilience.isRetryableHttpStatus(403), false);
  assert.equal(resilience.isRetryableHttpStatus(404), false);
  assert.equal(resilience.isRetryableHttpStatus(200), false);
});

test("withRetry: 初回で成功すればリトライしない", () => {
  let calls = 0;
  const result = resilience.withRetry(() => {
    calls++;
    return "ok";
  });
  assert.equal(result, "ok");
  assert.equal(calls, 1);
});

test("withRetry: 一時失敗の後に成功すればその値を返す", () => {
  let calls = 0;
  const sleeps = [];
  const result = resilience.withRetry(
    () => {
      calls++;
      if (calls < 3) throw new Error("一時エラー");
      return "recovered";
    },
    { sleepFn: (ms) => sleeps.push(ms) }
  );
  assert.equal(result, "recovered");
  assert.equal(calls, 3);
  assert.deepEqual(sleeps, [2000, 10000]);
});

test("withRetry: maxAttempts回失敗し続けたら最後のエラーをthrowする", () => {
  let calls = 0;
  assert.throws(() => {
    resilience.withRetry(
      () => {
        calls++;
        throw new Error("恒久エラー" + calls);
      },
      { maxAttempts: 3, sleepFn: () => {} }
    );
  }, /恒久エラー3/);
  assert.equal(calls, 3);
});

test("withRetry: isRetryableがfalseを返すエラーは即座にthrowしリトライしない(認証エラー等)", () => {
  let calls = 0;
  assert.throws(() => {
    resilience.withRetry(
      () => {
        calls++;
        const err = new Error("権限エラー");
        err.statusCode = 401;
        throw err;
      },
      {
        maxAttempts: 3,
        sleepFn: () => {},
        isRetryable: (err) => resilience.isRetryableHttpStatus(err.statusCode)
      }
    );
  }, /権限エラー/);
  assert.equal(calls, 1);
});

test("withRetry: onRetryはリトライのたびに呼ばれるが最終成功時の試行では呼ばれない", () => {
  let calls = 0;
  const retryLog = [];
  resilience.withRetry(
    () => {
      calls++;
      if (calls < 2) throw new Error("一時エラー");
      return "ok";
    },
    { sleepFn: () => {}, onRetry: (err, attempt) => retryLog.push(attempt) }
  );
  assert.deepEqual(retryLog, [1]);
});

test("isAlreadyCompletedToday: 前回完了日が今日と一致すればtrue", () => {
  assert.equal(resilience.isAlreadyCompletedToday("2026-08-07", "2026-08-07"), true);
  assert.equal(resilience.isAlreadyCompletedToday("2026-08-06", "2026-08-07"), false);
  assert.equal(resilience.isAlreadyCompletedToday("", "2026-08-07"), false);
  assert.equal(resilience.isAlreadyCompletedToday(null, "2026-08-07"), false);
  assert.equal(resilience.isAlreadyCompletedToday(undefined, "2026-08-07"), false);
});
