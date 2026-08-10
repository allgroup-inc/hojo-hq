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

test("buildCompanyListResult: 次回アクション予定日がDateオブジェクトと文字列の混在でも正しく降順ソートし、返り値は文字列になる", () => {
  const companiesWithRealDates = [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", ランク: "A", 現在ステージ: "提案中", 次回アクション予定日: new Date(2026, 7, 20), 担当者: "たかし" },
    { 企業ID: "C000002", 会社名: "サンプル建設株式会社", ランク: "B", 現在ステージ: "未接触", 次回アクション予定日: "2026-08-10", 担当者: "嶺井さん" },
    { 企業ID: "C000003", 会社名: "デモ工業株式会社", ランク: "A", 現在ステージ: "成約", 次回アクション予定日: new Date(2026, 7, 25), 担当者: "たかし" }
  ];
  const result = adminAccess.buildCompanyListResult(companiesWithRealDates, {});
  assert.deepEqual(result.map(c => c["企業ID"]), ["C000003", "C000001", "C000002"]);
  result.forEach((c) => {
    assert.equal(typeof c["次回アクション予定日"], "string");
  });
  assert.deepEqual(result.map(c => c["次回アクション予定日"]), ["2026-08-25", "2026-08-20", "2026-08-10"]);
});

test("sortInteractionsByDateDesc: 日付がDateオブジェクトの場合も正しくソート・yyyy-MM-dd文字列に正規化し、入力を変更しない", () => {
  const records = [
    { 履歴ID: "H-1", 日付: new Date(2026, 7, 1) },
    { 履歴ID: "H-2", 日付: new Date(2026, 7, 10) },
    { 履歴ID: "H-3", 日付: "2026-08-05" }
  ];
  const result = adminAccess.sortInteractionsByDateDesc(records);
  assert.deepEqual(result.map(r => r["履歴ID"]), ["H-2", "H-3", "H-1"]);
  assert.deepEqual(result.map(r => r["日付"]), ["2026-08-10", "2026-08-05", "2026-08-01"]);
  assert.ok(records[0]["日付"] instanceof Date, "入力レコードのDateオブジェクトが変更されていない");
});

const SAMPLE_PARTNERS = [
  { パートナーID: "P-1", 名称: "沖縄社労士法人", 種別: "士業", 関係性ランク: "A" },
  { パートナーID: "P-2", 名称: "那覇商工会", 種別: "商工団体", 関係性ランク: "B" },
  { パートナーID: "P-3", 名称: "琉球信用金庫", 種別: "金融機関", 関係性ランク: "C" }
];

test("buildPartnerListRows: 対応履歴の件数を正しく集計し、対応履歴が0件・未登録のパートナーも0件として含める", () => {
  const interactionsByPartnerId = {
    "P-1": [{ 履歴ID: "H-1" }, { 履歴ID: "H-2" }],
    "P-2": []
    // P-3はマップに存在しない(対応履歴が一度も記録されていない)
  };
  const result = adminAccess.buildPartnerListRows(SAMPLE_PARTNERS, interactionsByPartnerId);
  assert.deepEqual(result, [
    { "パートナーID": "P-1", "名称": "沖縄社労士法人", "種別": "士業", "関係性ランク": "A", "対応回数": 2 },
    { "パートナーID": "P-2", "名称": "那覇商工会", "種別": "商工団体", "関係性ランク": "B", "対応回数": 0 },
    { "パートナーID": "P-3", "名称": "琉球信用金庫", "種別": "金融機関", "関係性ランク": "C", "対応回数": 0 }
  ]);
});

test("normalizeReferralRecords: 紹介日をDate・文字列いずれもyyyy-MM-dd文字列に正規化し、他フィールドは変更せず、入力配列も変更しない", () => {
  const referrals = [
    { パートナーID: "P-1", 紹介日: new Date(2026, 7, 20), 紹介料率: "10%", 契約内容メモ: "顧問契約", 成約有無: "成約" },
    { パートナーID: "P-1", 紹介日: "2026-07-01", 紹介料率: "5%", 契約内容メモ: "スポット相談", 成約有無: "未成約" }
  ];
  const result = adminAccess.normalizeReferralRecords(referrals);
  assert.deepEqual(result.map(r => r["紹介日"]), ["2026-08-20", "2026-07-01"]);
  assert.equal(result[0]["紹介料率"], "10%");
  assert.equal(result[0]["契約内容メモ"], "顧問契約");
  assert.equal(result[1]["紹介料率"], "5%");
  assert.equal(result[1]["契約内容メモ"], "スポット相談");
  assert.ok(referrals[0]["紹介日"] instanceof Date, "入力配列の要素が変更されていない");
});
