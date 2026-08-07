import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const scoring = require("../glow-ma/src/scoring.js");
const schema = require("../glow-ma/src/schema.js");

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

test("calculateAgeBandPoints: 上限120を超える値(列マッピング誤りで西暦年などが混入した場合)は0点", () => {
  // 「代表者年齢」は運用者が設定するCSV列マッピングの値をそのまま使うため、
  // 例えば「創業年」列(例: 1955)を誤って年齢列にマッピングすると、
  // 上限がInfinityだと70歳以上バンド(15点)に誤って乗ってしまう。120を上限とすることで防ぐ。
  assert.equal(scoring.calculateAgeBandPoints("1955", scoring.DEFAULT_CONFIG), 0);
});

test("calculateAgeBandPoints: 上限120以内の72歳は引き続き70〜120バンド(15点)に該当する", () => {
  assert.equal(scoring.calculateAgeBandPoints("72歳", scoring.DEFAULT_CONFIG), 15);
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

test("calculateRouteBonus: 複数ルートがある場合は最大値を採用する", () => {
  assert.equal(scoring.calculateRouteBonus(["②手紙DM", "①紹介"], scoring.DEFAULT_CONFIG), 30);
  assert.equal(scoring.calculateRouteBonus(["③ミカタ経由"], scoring.DEFAULT_CONFIG), 20);
  assert.equal(scoring.calculateRouteBonus(["②手紙DM"], scoring.DEFAULT_CONFIG), 0);
});

test("calculateRouteBonus: ルートが空配列なら0", () => {
  assert.equal(scoring.calculateRouteBonus([], scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateRouteBonus(undefined, scoring.DEFAULT_CONFIG), 0);
});

test("calculateReactionScore: 種別ごとの加点を合算する", () => {
  const rows = [
    { 種別: "レターURLアクセス", 対応相手: "未接触" },
    { 種別: "ゆんたく相談実施", 対応相手: "経理・総務等の窓口担当" }
  ];
  // レターURLアクセス(5) + ゆんたく相談実施(25) = 30
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 30);
});

test("calculateReactionScore: 対応相手がオーナー社長本人なら種別を問わず+15", () => {
  const rows = [{ 種別: "電話", 対応相手: "オーナー社長本人" }];
  // 電話は反応イベント対象外(0) + 意思決定者ボーナス(15) = 15
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 15);
});

test("calculateReactionScore: 反応イベント対象外の種別(手紙送付・電話等)は加点しない", () => {
  const rows = [
    { 種別: "手紙送付", 対応相手: "未接触" },
    { 種別: "ミカタ接点確認", 対応相手: "未接触" }
  ];
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 0);
});

test("calculateReactionScore: 履歴が空なら0", () => {
  assert.equal(scoring.calculateReactionScore([], scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateReactionScore(undefined, scoring.DEFAULT_CONFIG), 0);
});

test("calculateReactionScore: 返信(15点)・面談実施(25点)・資料請求(10点)が個別に加点される", () => {
  assert.equal(
    scoring.calculateReactionScore([{ 種別: "返信", 対応相手: "未接触" }], scoring.DEFAULT_CONFIG),
    15
  );
  assert.equal(
    scoring.calculateReactionScore([{ 種別: "面談実施", 対応相手: "未接触" }], scoring.DEFAULT_CONFIG),
    25
  );
  assert.equal(
    scoring.calculateReactionScore([{ 種別: "資料請求", 対応相手: "未接触" }], scoring.DEFAULT_CONFIG),
    10
  );
});

test("calculateReactionScore: 入電(20点)は企業側からの反応イベントとして加点される", () => {
  assert.equal(
    scoring.calculateReactionScore([{ 種別: "入電", 対応相手: "未接触" }], scoring.DEFAULT_CONFIG),
    20
  );
});

test("reactionPointsByTypeのキーはすべてGlowSchema.INTERACTION_TYPESに含まれる(一文字のズレで壊れないことを保証)", () => {
  Object.keys(scoring.DEFAULT_CONFIG.reactionPointsByType).forEach((key) => {
    assert.ok(schema.INTERACTION_TYPES.includes(key), key + " is not in INTERACTION_TYPES");
  });
});

// 反応スコアの上限化に関する回帰テスト。
// 根拠: docs/superpowers/specs/2026-07-27-glow-ma-reaction-score-cap-triangle-review.md
// (同一種別の繰り返しは加点せず、意思決定者ボーナスも企業ごとに最大1回)
test("calculateReactionScore: 同一種別を複数回記録しても加点は1回分のみ", () => {
  const rows = [
    { 種別: "レターURLアクセス", 対応相手: "未接触" },
    { 種別: "レターURLアクセス", 対応相手: "未接触" }
  ];
  // レターURLアクセス(5) × 1回のみ = 5(2回分の10にはならない)
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 5);
});

test("calculateReactionScore: 対応相手がオーナー社長本人の行が複数あっても意思決定者ボーナスは1回のみ(電話5件で75点になるバグの回帰テスト)", () => {
  const rows = [
    { 種別: "電話", 対応相手: "オーナー社長本人" },
    { 種別: "電話", 対応相手: "オーナー社長本人" },
    { 種別: "電話", 対応相手: "オーナー社長本人" },
    { 種別: "電話", 対応相手: "オーナー社長本人" },
    { 種別: "電話", 対応相手: "オーナー社長本人" }
  ];
  // 電話は反応イベント対象外(0) + 意思決定者ボーナスは最大1回(15) = 15(75にはならない)
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 15);
});

test("calculateRank: 閾値どおりにA〜Dへ分類する", () => {
  assert.equal(scoring.calculateRank(70, scoring.DEFAULT_CONFIG), "A");
  assert.equal(scoring.calculateRank(100, scoring.DEFAULT_CONFIG), "A");
  assert.equal(scoring.calculateRank(69, scoring.DEFAULT_CONFIG), "B");
  assert.equal(scoring.calculateRank(40, scoring.DEFAULT_CONFIG), "B");
  assert.equal(scoring.calculateRank(39, scoring.DEFAULT_CONFIG), "C");
  assert.equal(scoring.calculateRank(15, scoring.DEFAULT_CONFIG), "C");
  assert.equal(scoring.calculateRank(14, scoring.DEFAULT_CONFIG), "D");
  assert.equal(scoring.calculateRank(0, scoring.DEFAULT_CONFIG), "D");
});
