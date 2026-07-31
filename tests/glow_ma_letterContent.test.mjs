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

test("buildLetterPrompt: 会社名・案内する商品・トラッキングURLを含むプロンプトを組み立てる", () => {
  const record = { 会社名: "テスト商事株式会社", 業種: "建設業", 流入ルート: ["②手紙DM"] };
  const prompt = letterContent.buildLetterPrompt(record, "https://example.com/track?id=C000001", letterContent.DEFAULT_CONFIG);
  assert.match(prompt, /テスト商事株式会社/);
  assert.match(prompt, /法人保険・経営相談/);
  assert.match(prompt, /https:\/\/example\.com\/track\?id=C000001/);
});

test("buildLetterPrompt: 紹介ルートの企業はM&Aを案内する文面指示になり、矛盾する禁止指示は含まない", () => {
  const record = { 会社名: "サンプル建設株式会社", 業種: "建設業", 流入ルート: ["①紹介"] };
  const prompt = letterContent.buildLetterPrompt(record, "https://example.com/track?id=C000002", letterContent.DEFAULT_CONFIG);
  assert.match(prompt, /M&A/);
  assert.match(prompt, /M&Aの話から入って構わない/);
  assert.doesNotMatch(prompt, /いきなりM&Aの話から入らないこと/);
});

test("buildLetterPrompt: 非紹介ルートの企業はM&Aの話から入らない指示になる", () => {
  const record = { 会社名: "テスト商事株式会社", 業種: "小売業", 流入ルート: ["②手紙DM"] };
  const prompt = letterContent.buildLetterPrompt(record, "https://example.com/track?id=C000003", letterContent.DEFAULT_CONFIG);
  assert.match(prompt, /いきなりM&Aの話から入らないこと/);
  assert.doesNotMatch(prompt, /M&Aの話から入って構わない/);
});

test("buildLetterPrompt: 業種が未設定でもエラーにならない", () => {
  const record = { 会社名: "テスト商事株式会社", 流入ルート: [] };
  const prompt = letterContent.buildLetterPrompt(record, "https://example.com/track?id=C000003", letterContent.DEFAULT_CONFIG);
  assert.match(prompt, /テスト商事株式会社/);
});

test("selectNurturingTargets: ステージ・ランク・接触間隔の条件を満たす企業のみ抽出する", () => {
  const records = [
    { 企業ID: "C1", 現在ステージ: "関係構築中", ランク: "B", 最終接触日: "2026-01-01" }, // 対象
    { 企業ID: "C2", 現在ステージ: "未接触", ランク: "B", 最終接触日: "2026-01-01" }, // ステージ対象外
    { 企業ID: "C3", 現在ステージ: "提案中", ランク: "A", 最終接触日: "2026-01-01" }, // ランク対象外(Aは除外)
    { 企業ID: "C4", 現在ステージ: "案件化", ランク: "C", 最終接触日: "2026-07-20" } // 直近すぎる(7日前)
  ];
  const targets = letterContent.selectNurturingTargets(records, "2026-07-27", letterContent.DEFAULT_CONFIG);
  assert.deepEqual(targets.map((r) => r["企業ID"]), ["C1"]);
});

test("selectNurturingTargets: 最終接触日が未設定なら登録日を代わりに使う", () => {
  const records = [
    { 企業ID: "C5", 現在ステージ: "関係構築中", ランク: "D", 最終接触日: "", 登録日: "2026-01-01" }
  ];
  const targets = letterContent.selectNurturingTargets(records, "2026-07-27", letterContent.DEFAULT_CONFIG);
  assert.deepEqual(targets.map((r) => r["企業ID"]), ["C5"]);
});

test("selectNurturingTargets: 連絡不要の企業は、他の条件を満たしていても対象外", () => {
  const records = [
    { 企業ID: "C6", 現在ステージ: "関係構築中", ランク: "B", 連絡不要: true, 最終接触日: "2026-01-01" }
  ];
  const targets = letterContent.selectNurturingTargets(records, "2026-07-27", letterContent.DEFAULT_CONFIG);
  assert.deepEqual(targets, []);
});

test("selectNurturingTargets: 対象企業がなければ空配列", () => {
  assert.deepEqual(letterContent.selectNurturingTargets([], "2026-07-27", letterContent.DEFAULT_CONFIG), []);
});
