import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const shindan = require("../site/nobishiro/shindan/logic.js");

const validAnswers = {
  email: "owner@example.com",
  industry: "飲食業",
  employeeCount: "6〜20人",
  monthlyRevenue: "300〜1000万円",
  costFeeling: "やや負担",
  salesChallenge: "追客",
  priority: "コスト削減",
};

test("validateForm: 正しい回答はvalid:true", () => {
  const result = shindan.validateForm(validAnswers);
  assert.equal(result.valid, true);
});

test("validateForm: メール未入力はエラー", () => {
  const result = shindan.validateForm({ ...validAnswers, email: "" });
  assert.equal(result.valid, false);
});

test("submitDiagnosis: バリデーション失敗ならfetchを呼ばずreject", async () => {
  let called = false;
  const fakeFetch = async () => {
    called = true;
    return { json: async () => ({}) };
  };
  await assert.rejects(
    shindan.submitDiagnosis({ ...validAnswers, email: "" }, "https://example.com/exec", fakeFetch)
  );
  assert.equal(called, false);
});

test("submitDiagnosis: 成功時はCheckout URLを返す", async () => {
  const fakeFetch = async (url, opts) => {
    assert.ok(url.includes("?type=submit"));
    assert.equal(opts.method, "POST");
    const body = JSON.parse(opts.body);
    assert.deepEqual(body.answers, validAnswers);
    return { json: async () => ({ url: "https://checkout.stripe.com/xyz" }) };
  };
  const url = await shindan.submitDiagnosis(validAnswers, "https://example.com/exec", fakeFetch);
  assert.equal(url, "https://checkout.stripe.com/xyz");
});

test("submitDiagnosis: サーバーがerrorを返したらreject", async () => {
  const fakeFetch = async () => ({ json: async () => ({ error: "validation_failed" }) });
  await assert.rejects(shindan.submitDiagnosis(validAnswers, "https://example.com/exec", fakeFetch));
});
