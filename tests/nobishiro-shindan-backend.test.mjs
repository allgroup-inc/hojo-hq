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

test("buildReportPrompt: 回答内容が全てプロンプトに含まれる", () => {
  const prompt = backend.buildReportPrompt(validAnswers);
  assert.ok(prompt.includes("飲食業"));
  assert.ok(prompt.includes("6〜20人"));
  assert.ok(prompt.includes("ガジュマルくん"));
});

test("escapeHtml: HTML特殊文字をエスケープする", () => {
  const result = backend.escapeHtml('<script>alert("x")</script>&');
  assert.equal(result, "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;&amp;");
});

test("buildReportEmailHtml: レポート本文がエスケープされ改行がbrになる", () => {
  const html = backend.buildReportEmailHtml("1行目\n2行目<b>太字</b>", validAnswers);
  assert.ok(html.includes("1行目<br>2行目&lt;b&gt;太字&lt;/b&gt;"));
  assert.ok(html.includes("ガジュマルくん"));
});

test("isValidWebhookToken: 一致すればtrue", () => {
  assert.equal(backend.isValidWebhookToken("abc123", "abc123"), true);
});

test("isValidWebhookToken: 不一致はfalse", () => {
  assert.equal(backend.isValidWebhookToken("abc123", "xyz999"), false);
});

test("isValidWebhookToken: expectedが空文字ならfalse(未設定のトークンでの誤通過防止)", () => {
  assert.equal(backend.isValidWebhookToken("", ""), false);
  assert.equal(backend.isValidWebhookToken(undefined, ""), false);
});

test("isValidWebhookToken: 型が文字列でなければfalse", () => {
  assert.equal(backend.isValidWebhookToken(null, "abc123"), false);
  assert.equal(backend.isValidWebhookToken(123, "abc123"), false);
});
