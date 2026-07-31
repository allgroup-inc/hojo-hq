import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const letterContent = require("../glow-ma/src/letterContent.js");

test("determineLeadProduct: 紹介ルートを含む企業は直接M&Aを案内してよい", () => {
  const record = { 流入ルート: ["①紹介"] };
  assert.equal(letterContent.determineLeadProduct(record, letterContent.DEFAULT_CONFIG), "M&A");
});

test("determineLeadProduct: 紹介ルートを含まない企業は法人保険・経営相談を入口にする", () => {
  const record = { 流入ルート: ["②手紙DM"] };
  assert.equal(letterContent.determineLeadProduct(record, letterContent.DEFAULT_CONFIG), "法人保険・経営相談");
});

test("determineLeadProduct: 流入ルートが未設定でもエラーにならない", () => {
  const record = {};
  assert.equal(letterContent.determineLeadProduct(record, letterContent.DEFAULT_CONFIG), "法人保険・経営相談");
});

test("buildTrackingUrl: 企業IDをクエリパラメータとして付与する", () => {
  assert.equal(
    letterContent.buildTrackingUrl("C000001", "https://example.com/track"),
    "https://example.com/track?id=C000001"
  );
});

test("buildTrackingUrl: baseUrlに既にクエリ文字列がある場合は&で繋ぐ", () => {
  assert.equal(
    letterContent.buildTrackingUrl("C000001", "https://example.com/track?x=1"),
    "https://example.com/track?x=1&id=C000001"
  );
});

test("buildTrackingUrl: companyIdまたはbaseUrlが空なら空文字列を返す", () => {
  assert.equal(letterContent.buildTrackingUrl("", "https://example.com/track"), "");
  assert.equal(letterContent.buildTrackingUrl("C000001", ""), "");
});
