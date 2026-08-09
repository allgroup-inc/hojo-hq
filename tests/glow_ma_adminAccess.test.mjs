import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const adminAccess = require("../glow-ma/src/adminAccess.js");

test("isAllowedEmail: スタッフ一覧にメールアドレスが一致すればtrue", () => {
  const staffRows = [{ email: "koyanagi@example.com" }, { email: "fukuda@example.com" }];
  assert.equal(adminAccess.isAllowedEmail("koyanagi@example.com", staffRows), true);
});

test("isAllowedEmail: 一致しなければfalse", () => {
  const staffRows = [{ email: "koyanagi@example.com" }];
  assert.equal(adminAccess.isAllowedEmail("other@example.com", staffRows), false);
});

test("isAllowedEmail: 大文字小文字・前後空白の違いを無視して一致判定する", () => {
  const staffRows = [{ email: " Koyanagi@Example.com " }];
  assert.equal(adminAccess.isAllowedEmail("koyanagi@example.com", staffRows), true);
});

test("isAllowedEmail: 空文字・未認証はfalse(空リストでも許可されない)", () => {
  assert.equal(adminAccess.isAllowedEmail("", [{ email: "koyanagi@example.com" }]), false);
  assert.equal(adminAccess.isAllowedEmail(null, [{ email: "koyanagi@example.com" }]), false);
});

test("isAllowedEmail: スタッフ一覧が空なら常にfalse", () => {
  assert.equal(adminAccess.isAllowedEmail("koyanagi@example.com", []), false);
});

test("buildAccessDeniedHtml: アクセス権がない旨のHTMLを返す", () => {
  const html = adminAccess.buildAccessDeniedHtml();
  assert.ok(html.indexOf("アクセス権がありません") !== -1);
});

const SAMPLE_COMPANIES = [
  { 企業ID: "C000001", 会社名: "テスト商事株式会社", ランク: "A", 現在ステージ: "提案中", 次回アクション予定日: "2026-08-20", 担当者: "たかし", 携帯番号: "090-0000-0001", 関係メモ: "極秘メモ1" },
  { 企業ID: "C000002", 会社名: "サンプル建設株式会社", ランク: "B", 現在ステージ: "未接触", 次回アクション予定日: "2026-08-10", 担当者: "嶺井さん", 携帯番号: "090-0000-0002", 関係メモ: "極秘メモ2" },
  { 企業ID: "C000003", 会社名: "デモ工業株式会社", ランク: "A", 現在ステージ: "成約", 次回アクション予定日: "", 担当者: "たかし", 携帯番号: "090-0000-0003", 関係メモ: "極秘メモ3" }
];

test("COMPANY_LIST_FIELDS: 一覧に必要な最小限のフィールドのみを定義する(機微情報を含まない)", () => {
  assert.deepEqual(adminAccess.COMPANY_LIST_FIELDS, [
    "企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者"
  ]);
});

test("hasAnyFilter: 検索語・ランク・ステージ・担当者のいずれかが指定されていればtrue", () => {
  assert.equal(adminAccess.hasAnyFilter({}), false);
  assert.equal(adminAccess.hasAnyFilter({ search: "" }), false);
  assert.equal(adminAccess.hasAnyFilter({ search: "テスト" }), true);
  assert.equal(adminAccess.hasAnyFilter({ rank: "A" }), true);
  assert.equal(adminAccess.hasAnyFilter({ stage: "未接触" }), true);
  assert.equal(adminAccess.hasAnyFilter({ owner: "たかし" }), true);
});

test("applyCompanyFilters: 会社名の部分一致で絞り込む", () => {
  const result = adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { search: "サンプル" });
  assert.deepEqual(result.map(c => c["企業ID"]), ["C000002"]);
});

test("applyCompanyFilters: ランク・ステージ・担当者の完全一致で絞り込む", () => {
  assert.deepEqual(
    adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { rank: "A" }).map(c => c["企業ID"]),
    ["C000001", "C000003"]
  );
  assert.deepEqual(
    adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { stage: "未接触" }).map(c => c["企業ID"]),
    ["C000002"]
  );
  assert.deepEqual(
    adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { owner: "たかし" }).map(c => c["企業ID"]),
    ["C000001", "C000003"]
  );
});

test("buildCompanyListResult: 絞り込み指定時は上位100件制限をかけず、最小フィールドのみ返す(機微情報を含まない)", () => {
  const result = adminAccess.buildCompanyListResult(SAMPLE_COMPANIES, { rank: "A" });
  assert.deepEqual(result, [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", ランク: "A", 現在ステージ: "提案中", 次回アクション予定日: "2026-08-20", 担当者: "たかし" },
    { 企業ID: "C000003", 会社名: "デモ工業株式会社", ランク: "A", 現在ステージ: "成約", 次回アクション予定日: "", 担当者: "たかし" }
  ]);
});

test("buildCompanyListResult: 未絞り込み時は次回アクション予定日の降順で上位DEFAULT_LIST_LIMIT件のみ返す", () => {
  const result = adminAccess.buildCompanyListResult(SAMPLE_COMPANIES, {});
  assert.deepEqual(result.map(c => c["企業ID"]), ["C000001", "C000002", "C000003"]);
  assert.ok(result.length <= adminAccess.DEFAULT_LIST_LIMIT);
});

test("sortInteractionsByDateDesc: 対応履歴を日付の新しい順に並び替える", () => {
  const records = [
    { 履歴ID: "H-1", 日付: "2026-08-01" },
    { 履歴ID: "H-2", 日付: "2026-08-10" },
    { 履歴ID: "H-3", 日付: "2026-08-05" }
  ];
  assert.deepEqual(
    adminAccess.sortInteractionsByDateDesc(records).map(r => r["履歴ID"]),
    ["H-2", "H-3", "H-1"]
  );
});
