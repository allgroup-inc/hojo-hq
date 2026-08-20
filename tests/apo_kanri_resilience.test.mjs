import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const resilience = require("../apo-kanri/src/resilience.js");

test("isRetryableHttpStatus: 429と5xxのみ再試行対象", () => {
  assert.equal(resilience.isRetryableHttpStatus(429), true);
  assert.equal(resilience.isRetryableHttpStatus(500), true);
  assert.equal(resilience.isRetryableHttpStatus(503), true);
  assert.equal(resilience.isRetryableHttpStatus(200), false);
  assert.equal(resilience.isRetryableHttpStatus(403), false);
  assert.equal(resilience.isRetryableHttpStatus(404), false);
});

test("withRetry: 一時エラーは最大3回まで再試行し、成功したら値を返す", () => {
  let calls = 0;
  const result = resilience.withRetry(() => {
    calls++;
    if (calls < 3) throw new Error("temporary");
    return "ok";
  });
  assert.equal(result, "ok");
  assert.equal(calls, 3);
});

test("withRetry: isRetryableがfalseなら即座に投げ直す", () => {
  let calls = 0;
  assert.throws(() => {
    resilience.withRetry(() => {
      calls++;
      throw new Error("permanent");
    }, { isRetryable: () => false });
  }, /permanent/);
  assert.equal(calls, 1);
});

test("withRetry: 全試行失敗で最後のエラーを投げ、バックオフが呼ばれる", () => {
  const sleeps = [];
  assert.throws(() => {
    resilience.withRetry(() => { throw new Error("always"); }, {
      sleepFn: (ms) => sleeps.push(ms)
    });
  }, /always/);
  assert.deepEqual(sleeps, [2000, 10000]);
});
