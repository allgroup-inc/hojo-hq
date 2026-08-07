import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const shippingContent = require("../glow-ma/src/shippingContent.js");

test("computeFollowUpDate: 発送日からN日後の日付をyyyy-MM-dd形式で返す", () => {
  assert.equal(shippingContent.computeFollowUpDate("2026-08-07", 10), "2026-08-17");
});

test("computeFollowUpDate: 月をまたぐ場合も正しく計算する", () => {
  assert.equal(shippingContent.computeFollowUpDate("2026-08-25", 10), "2026-09-04");
});

test("computeFollowUpDate: 不正な日付や空文字ならnullを返す", () => {
  assert.equal(shippingContent.computeFollowUpDate("", 10), null);
  assert.equal(shippingContent.computeFollowUpDate(null, 10), null);
  assert.equal(shippingContent.computeFollowUpDate("不正な値", 10), null);
});
