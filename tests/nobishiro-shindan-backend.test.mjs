import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const backend = require("../gas/nobishiro-shindan/Logic.gs");

const validAnswers = {
  email: "owner@example.com",
  industry: "飲食業",
  employeeCount: "6〜20人",
  monthlyRevenue: "300〜1000万円",
  costFeeling: "やや負担",
  salesChallenge: "追客",
  priority: "コスト削減",
};

test("validateSubmission: 正しい回答はvalid:true", () => {
  const result = backend.validateSubmission(validAnswers);
  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("validateSubmission: メール不正はエラー", () => {
  const result = backend.validateSubmission({ ...validAnswers, email: "not-an-email" });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("メール")));
});

test("validateSubmission: 業種が許容値外はエラー", () => {
  const result = backend.validateSubmission({ ...validAnswers, industry: "宇宙業" });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("業種")));
});

test("validateSubmission: answersがnullなら単一エラーで即返す", () => {
  const result = backend.validateSubmission(null);
  assert.equal(result.valid, false);
  assert.equal(result.errors.length, 1);
});

test("PRICE_YEN は14800", () => {
  assert.equal(backend.PRICE_YEN, 14800);
});
