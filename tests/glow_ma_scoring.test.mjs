import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const scoring = require("../glow-ma/src/scoring.js");

test("DEFAULT_CONFIG にランク閾値A:70/B:40/C:15が設定されている(2026-07-27 triangle-review確定値)", () => {
  assert.deepEqual(scoring.DEFAULT_CONFIG.rankThresholds, { A: 70, B: 40, C: 15 });
});

test("classifyIndustryTier: 高流動性業種のキーワードを含むとhigh", () => {
  assert.equal(scoring.classifyIndustryTier("建設業", scoring.DEFAULT_CONFIG), "high");
  assert.equal(scoring.classifyIndustryTier("一般貨物自動車運送業", scoring.DEFAULT_CONFIG), "high");
});

test("classifyIndustryTier: 未一致の業種はmid(中立)扱い", () => {
  assert.equal(scoring.classifyIndustryTier("情報通信業", scoring.DEFAULT_CONFIG), "mid");
  assert.equal(scoring.classifyIndustryTier("", scoring.DEFAULT_CONFIG), "mid");
  assert.equal(scoring.classifyIndustryTier(null, scoring.DEFAULT_CONFIG), "mid");
});

test("classifyIndustryTier: configを省略した場合はDEFAULT_CONFIGが使われる", () => {
  assert.equal(scoring.classifyIndustryTier("建設業"), "high");
});
