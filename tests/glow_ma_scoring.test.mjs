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

test("calculateSizeBandPoints: 10〜50名は10点", () => {
  assert.equal(scoring.calculateSizeBandPoints("30名", scoring.DEFAULT_CONFIG), 10);
  assert.equal(scoring.calculateSizeBandPoints("10名", scoring.DEFAULT_CONFIG), 10);
  assert.equal(scoring.calculateSizeBandPoints("50名", scoring.DEFAULT_CONFIG), 10);
});

test("calculateSizeBandPoints: 5〜9名・51〜100名は5点", () => {
  assert.equal(scoring.calculateSizeBandPoints("7名", scoring.DEFAULT_CONFIG), 5);
  assert.equal(scoring.calculateSizeBandPoints("80名", scoring.DEFAULT_CONFIG), 5);
});

test("calculateSizeBandPoints: 範囲外・空・数字なしは0点", () => {
  assert.equal(scoring.calculateSizeBandPoints("2名", scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateSizeBandPoints("", scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateSizeBandPoints(null, scoring.DEFAULT_CONFIG), 0);
});

test("calculateAgeBandPoints: 年齢帯ごとの加点", () => {
  assert.equal(scoring.calculateAgeBandPoints("72歳", scoring.DEFAULT_CONFIG), 15);
  assert.equal(scoring.calculateAgeBandPoints("65", scoring.DEFAULT_CONFIG), 10);
  assert.equal(scoring.calculateAgeBandPoints("55歳", scoring.DEFAULT_CONFIG), 5);
  assert.equal(scoring.calculateAgeBandPoints("40歳", scoring.DEFAULT_CONFIG), 0);
});

test("calculateAgeBandPoints: データ欠損時は0点(任意加点、モデルを歪ませない)", () => {
  assert.equal(scoring.calculateAgeBandPoints("", scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateAgeBandPoints(undefined, scoring.DEFAULT_CONFIG), 0);
});

test("calculateAttributeScore: 業種・規模・年齢の加点を合算する", () => {
  const company = { 業種: "建設業", 規模: "30名", 代表者年齢: "72歳" };
  // 業種high(20) + 規模30名(10) + 年齢72歳(15) = 45
  assert.equal(scoring.calculateAttributeScore(company, scoring.DEFAULT_CONFIG), 45);
});

test("calculateAttributeScore: 代表者年齢が空でも他の加点は計算される", () => {
  const company = { 業種: "情報通信業", 規模: "200名", 代表者年齢: "" };
  // 業種mid(10) + 規模200名は範囲外(0) + 年齢なし(0) = 10
  assert.equal(scoring.calculateAttributeScore(company, scoring.DEFAULT_CONFIG), 10);
});
