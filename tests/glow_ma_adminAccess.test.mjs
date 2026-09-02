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

test("resolveStaffName: メールアドレスが一致すればスタッフの氏名を返す", () => {
  const staffRows = [
    { email: "koyanagi@example.com", name: "小柳" },
    { email: "fukuda@example.com", name: "福田" }
  ];
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", staffRows), "小柳");
});

test("resolveStaffName: 大文字小文字・前後空白の違いを無視して一致判定する", () => {
  const staffRows = [{ email: " Koyanagi@Example.com ", name: "小柳" }];
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", staffRows), "小柳");
});

test("resolveStaffName: 一致しなければ「不明」を返す", () => {
  const staffRows = [{ email: "koyanagi@example.com", name: "小柳" }];
  assert.equal(adminAccess.resolveStaffName("other@example.com", staffRows), "不明");
});

test("resolveStaffName: スタッフ一覧が空でも「不明」を返す(例外を投げない)", () => {
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", []), "不明");
  assert.equal(adminAccess.resolveStaffName("koyanagi@example.com", undefined), "不明");
});

const SAMPLE_COMPANIES = [
  { 企業ID: "C000001", 会社名: "テスト商事株式会社", ランク: "A", 現在ステージ: "提案中", 次回アクション予定日: "2026-08-20", 担当者: "たかし", 携帯番号: "090-0000-0001", 関係メモ: "極秘メモ1" },
  { 企業ID: "C000002", 会社名: "サンプル建設株式会社", ランク: "B", 現在ステージ: "未接触", 次回アクション予定日: "2026-08-10", 担当者: "嶺井さん", 携帯番号: "090-0000-0002", 関係メモ: "極秘メモ2" },
  { 企業ID: "C000003", 会社名: "デモ工業株式会社", ランク: "A", 現在ステージ: "成約", 次回アクション予定日: "", 担当者: "たかし", 携帯番号: "090-0000-0003", 関係メモ: "極秘メモ3" }
];

test("COMPANY_LIST_FIELDS: 一覧に必要な最小限のフィールドのみを定義する(機微情報を含まない)", () => {
  assert.deepEqual(adminAccess.COMPANY_LIST_FIELDS, [
    "企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者",
    "業種", "所在地", "流入ルート", "提案商品"
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
  const result = adminAccess.buildCompanyListResult(SAMPLE_COMPANIES, { rank: "A" }, "2026-08-15");
  assert.deepEqual(result, [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", ランク: "A", 現在ステージ: "提案中", 次回アクション予定日: "2026-08-20", 担当者: "たかし", 業種: "", 所在地: "", 流入ルート: [], 提案商品: [], urgency: "ok" },
    { 企業ID: "C000003", 会社名: "デモ工業株式会社", ランク: "A", 現在ステージ: "成約", 次回アクション予定日: "", 担当者: "たかし", 業種: "", 所在地: "", 流入ルート: [], 提案商品: [], urgency: "untouched" }
  ]);
});

test("buildCompanyListResult: 未絞り込み時は次回アクション予定日の降順で上位DEFAULT_LIST_LIMIT件のみ返す", () => {
  const result = adminAccess.buildCompanyListResult(SAMPLE_COMPANIES, {}, "2026-08-15");
  assert.deepEqual(result.map(c => c["企業ID"]), ["C000001", "C000002", "C000003"]);
  assert.ok(result.length <= adminAccess.DEFAULT_LIST_LIMIT);
});

test("buildCompanyListResult: 各行にurgency(緊急度)が付与される(一覧テーブルの緊急度ドット表示用)", () => {
  const companies = [
    { 企業ID: "C_overdue", 会社名: "A社", ランク: "A", 次回アクション予定日: "2026-08-10" },
    { 企業ID: "C_soon", 会社名: "B社", ランク: "A", 次回アクション予定日: "2026-08-17" },
    { 企業ID: "C_ok", 会社名: "C社", ランク: "A", 次回アクション予定日: "2026-09-01" },
    { 企業ID: "C_untouched", 会社名: "D社", ランク: "A", 次回アクション予定日: "" },
    { 企業ID: "C_none", 会社名: "E社", ランク: "A", 次回アクション予定日: "2026-08-10", 連絡不要: true }
  ];
  const result = adminAccess.buildCompanyListResult(companies, {}, "2026-08-15");
  const byId = {};
  result.forEach((r) => { byId[r["企業ID"]] = r.urgency; });
  assert.deepEqual(byId, {
    C_overdue: "overdue",
    C_soon: "soon",
    C_ok: "ok",
    C_untouched: "untouched",
    C_none: "none"
  });
});

test("normalizeCompanyDetailDates: 日付列(Dateオブジェクト)をyyyy-MM-dd文字列に正規化する(google.script.runがDateを含む応答を壊すのを防ぐ)", () => {
  const company = {
    "企業ID": "C000001",
    "会社名": "太田建設株式会社",
    "登録日": new Date(2026, 7, 10, 15, 0, 0),
    "最終接触日": new Date(2026, 7, 18),
    "次回アクション予定日": "",
    "電話番号": "098-933-6464"
  };
  const result = adminAccess.normalizeCompanyDetailDates(company);
  assert.equal(result["登録日"], "2026-08-10");
  assert.equal(result["最終接触日"], "2026-08-18");
  assert.equal(result["次回アクション予定日"], "");
  assert.equal(result["会社名"], "太田建設株式会社");
  assert.equal(result["電話番号"], "098-933-6464");
});

test("normalizeCompanyDetailDates: nullを渡してもそのまま返す(getCompanyDetailの未検出ケース)", () => {
  assert.equal(adminAccess.normalizeCompanyDetailDates(null), null);
});

test("buildFilterOptions: 現在ステージ・担当者・流入ルート・提案商品の選択肢を重複なく作る(getAdminBootstrapとgetFilterOptionsで共有)", () => {
  const companies = [
    { "現在ステージ": "未接触", "担当者": "たかし", "流入ルート": ["②手紙DM"], "提案商品": ["法人保険"] },
    { "現在ステージ": "未接触", "担当者": "嶺井さん", "流入ルート": ["①紹介"], "提案商品": [] },
    { "現在ステージ": "", "担当者": "", "流入ルート": [], "提案商品": ["法人保険", "M&A"] }
  ];
  const result = adminAccess.buildFilterOptions(companies);
  assert.deepEqual(result, {
    stages: ["未接触"],
    owners: ["たかし", "嶺井さん"],
    routes: ["②手紙DM", "①紹介"].sort(),
    products: ["M&A", "法人保険"]
  });
});

test("buildFilterOptions: 企業が空でも例外を投げず空の配列を返す", () => {
  assert.deepEqual(adminAccess.buildFilterOptions([]), { stages: [], owners: [], routes: [], products: [] });
  assert.deepEqual(adminAccess.buildFilterOptions(undefined), { stages: [], owners: [], routes: [], products: [] });
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

test("buildCompanyListResult: 業種・所在地・流入ルート・提案商品を含む", () => {
  const companies = [{
    "企業ID": "C000001", "会社名": "テスト建設", "ランク": "B", "現在ステージ": "未接触",
    "次回アクション予定日": "", "担当者": "", "業種": "建設業", "所在地": "沖縄県那覇市",
    "流入ルート": ["②手紙DM"], "提案商品": ["法人保険"]
  }];
  const result = adminAccess.buildCompanyListResult(companies, {});
  assert.equal(result[0]["業種"], "建設業");
  assert.equal(result[0]["所在地"], "沖縄県那覇市");
  assert.deepEqual(result[0]["流入ルート"], ["②手紙DM"]);
  assert.deepEqual(result[0]["提案商品"], ["法人保険"]);
});

test("applyCompanyFilters: 流入ルートで絞り込める", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "A社", "流入ルート": ["①紹介"] },
    { "企業ID": "C2", "会社名": "B社", "流入ルート": ["②手紙DM"] }
  ];
  const result = adminAccess.applyCompanyFilters(companies, { route: "①紹介" });
  assert.equal(result.length, 1);
  assert.equal(result[0]["企業ID"], "C1");
});

test("applyCompanyFilters: 提案商品で絞り込める", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "A社", "提案商品": ["M&A"] },
    { "企業ID": "C2", "会社名": "B社", "提案商品": ["法人保険"] }
  ];
  const result = adminAccess.applyCompanyFilters(companies, { product: "M&A" });
  assert.equal(result.length, 1);
  assert.equal(result[0]["企業ID"], "C1");
});

test("applyCompanyFilters: route/productとも未指定なら全件通す", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "A社", "流入ルート": ["①紹介"], "提案商品": ["M&A"] }
  ];
  const result = adminAccess.applyCompanyFilters(companies, {});
  assert.equal(result.length, 1);
});

test("computeUrgency: 連絡不要企業はnone", () => {
  const company = { "連絡不要": true, "次回アクション予定日": "2026-08-01" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "none");
});

test("computeUrgency: 次回アクション予定日が未設定ならuntouched", () => {
  const company = { "連絡不要": false, "次回アクション予定日": "" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "untouched");
});

test("computeUrgency: 次回アクション予定日が本日以前ならoverdue", () => {
  const company = { "次回アクション予定日": "2026-08-13" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "overdue");
  const past = { "次回アクション予定日": "2026-08-01" };
  assert.equal(adminAccess.computeUrgency(past, "2026-08-13"), "overdue");
});

test("computeUrgency: 3日以内ならsoon", () => {
  const company = { "次回アクション予定日": "2026-08-16" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "soon");
});

test("computeUrgency: 4日以上先ならok", () => {
  const company = { "次回アクション予定日": "2026-08-20" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "ok");
});

test("buildKpiSummary: 各項目を正しく集計する", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C1", "ランク": "A", "現在ステージ": "提案中", "次回アクション予定日": "2026-08-01",
      "連絡不要": false, "本日反応あり": false, "最終接触日": "2026-08-01", "登録日": "2026-01-01" },
    { "企業ID": "C2", "ランク": "B", "現在ステージ": "未接触", "次回アクション予定日": "",
      "連絡不要": false, "本日反応あり": true, "最終接触日": "", "登録日": "2026-08-10" },
    { "企業ID": "C3", "ランク": "D", "現在ステージ": "案件化", "次回アクション予定日": "2026-08-20",
      "連絡不要": false, "本日反応あり": false, "最終接触日": "2020-01-01", "登録日": "2020-01-01" }
  ];
  const summary = adminAccess.buildKpiSummary(companies, today);
  assert.equal(summary.total, 3);
  assert.equal(summary.overdueOrUntouched, 2); // C1(overdue) + C2(untouched)
  assert.equal(summary.hot, 1); // C2
  assert.deepEqual(summary.byRank, { A: 1, B: 1, C: 0, D: 1 });
  assert.equal(summary.deal, 2); // C1(提案中) + C3(案件化)
  assert.equal(summary.stale, 1); // C3: 最終接触2020年、標準サイクル(D=365日)の2倍以上経過
});

test("buildOwnerWorkload: 担当者ごとに集計し、担当数の多い順に並べる", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C1", "担当者": "福田", "次回アクション予定日": "2026-08-01", "連絡不要": false },
    { "企業ID": "C2", "担当者": "福田", "次回アクション予定日": "2026-08-20", "連絡不要": false },
    { "企業ID": "C3", "担当者": "宮城", "次回アクション予定日": "", "連絡不要": false },
    { "企業ID": "C4", "担当者": "", "次回アクション予定日": "2026-08-01", "連絡不要": false }
  ];
  const result = adminAccess.buildOwnerWorkload(companies, today);
  assert.equal(result.length, 2); // 担当者未設定(C4)は除外
  assert.equal(result[0].owner, "福田");
  assert.equal(result[0].total, 2);
  assert.equal(result[0].overdueOrUntouched, 1); // C1のみoverdue
  assert.equal(result[1].owner, "宮城");
  assert.equal(result[1].total, 1);
  assert.equal(result[1].overdueOrUntouched, 1); // C3はuntouched
});

test("buildNextActionQueue: 反応あり→未着手→期限超過→まもなくの順に並べ、上限件数で切る", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C_ok", "次回アクション予定日": "2026-09-01", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_soon", "次回アクション予定日": "2026-08-15", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_overdue", "次回アクション予定日": "2026-08-01", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_untouched", "次回アクション予定日": "", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_hot", "次回アクション予定日": "2026-09-01", "連絡不要": false, "本日反応あり": true }
  ];
  const result = adminAccess.buildNextActionQueue(companies, today, 8);
  const ids = result.map(function (c) { return c["企業ID"]; });
  assert.deepEqual(ids, ["C_hot", "C_untouched", "C_overdue", "C_soon"]); // C_okは対象外
  assert.equal(result[0].urgency, "ok"); // C_hotは次回アクション予定日自体はok
  assert.equal(result[1].urgency, "untouched");
});

test("buildNextActionQueue: limitで件数を絞る", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C1", "次回アクション予定日": "", "連絡不要": false },
    { "企業ID": "C2", "次回アクション予定日": "", "連絡不要": false },
    { "企業ID": "C3", "次回アクション予定日": "", "連絡不要": false }
  ];
  const result = adminAccess.buildNextActionQueue(companies, today, 2);
  assert.equal(result.length, 2);
});

test("buildNextActionQueue: 次回アクション予定日がDateオブジェクトでもpickCompanyListFields_と同じnormalizeDateForDisplayでyyyy-MM-dd文字列に正規化して返す(最終レビュー Finding 3)", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C_overdue_date", "次回アクション予定日": new Date(2026, 7, 1), "連絡不要": false, "本日反応あり": false }
  ];
  const result = adminAccess.buildNextActionQueue(companies, today, 8);
  assert.equal(result.length, 1);
  assert.equal(typeof result[0]["次回アクション予定日"], "string");
  assert.equal(result[0]["次回アクション予定日"], "2026-08-01");
});

test("buildNextActionQueue: 登録日・最終接触日がDateオブジェクトでも文字列に正規化する(google.script.runの応答全体が壊れるのを防ぐ。2026-08-31 getAdminBootstrap導入時に発覚した不具合の再発防止)", () => {
  const today = "2026-08-13";
  const companies = [
    {
      "企業ID": "C_untouched_date",
      "登録日": new Date(2026, 7, 10, 15, 0, 0),
      "最終接触日": new Date(2026, 7, 5),
      "次回アクション予定日": "",
      "連絡不要": false,
      "本日反応あり": false
    }
  ];
  const result = adminAccess.buildNextActionQueue(companies, today, 8);
  assert.equal(result.length, 1);
  assert.equal(result[0]["登録日"], "2026-08-10");
  assert.equal(result[0]["最終接触日"], "2026-08-05");
});

// ---- buildPartnerRegistration(新規パートナー登録) ----

test("buildPartnerRegistration: 名称だけでも登録でき、IDはP-001から自動採番・紹介数/成約数は0・最終接触日は当日で初期化される", () => {
  const result = adminAccess.buildPartnerRegistration(
    { "名称": " 沖縄第一銀行 " },
    [],
    "2026-08-31"
  );
  assert.equal(result.ok, true);
  assert.equal(result.partnerId, "P-001");
  assert.equal(result.record["名称"], "沖縄第一銀行");
  assert.equal(result.record["累計紹介数"], 0);
  assert.equal(result.record["成約数"], 0);
  assert.equal(result.record["最終接触日"], "2026-08-31");
  // 行配列はPARTNER_MASTER_HEADERSの並び順に一致する
  assert.equal(result.row.length, 12);
  assert.equal(result.row[0], "P-001");
  assert.equal(result.row[1], "沖縄第一銀行");
});

test("buildPartnerRegistration: 既存IDの最大値+1で採番する(欠番・P-形式でないIDは無視)", () => {
  const existing = [
    { "パートナーID": "P-002", "名称": "A信金" },
    { "パートナーID": "P-010", "名称": "B税理士事務所" },
    { "パートナーID": "レガシー01", "名称": "C商工会" }
  ];
  const result = adminAccess.buildPartnerRegistration({ "名称": "D銀行" }, existing, "2026-08-31");
  assert.equal(result.ok, true);
  assert.equal(result.partnerId, "P-011");
});

test("buildPartnerRegistration: 名称が空ならok:falseとエラー文言を返す", () => {
  const result = adminAccess.buildPartnerRegistration({ "名称": "  " }, [], "2026-08-31");
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((e) => e.includes("名称")));
});

test("buildPartnerRegistration: 同じ名称が既に登録済みならok:falseを返す(前後の空白は無視して比較)", () => {
  const existing = [{ "パートナーID": "P-001", "名称": "沖縄第一銀行" }];
  const result = adminAccess.buildPartnerRegistration({ "名称": " 沖縄第一銀行" }, existing, "2026-08-31");
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((e) => e.includes("既に登録")));
});

test("buildPartnerRegistration: 日付欄がyyyy-MM-dd形式でなければok:falseを返す", () => {
  const result = adminAccess.buildPartnerRegistration(
    { "名称": "E銀行", "次回アクション予定日": "9月1日" },
    [],
    "2026-08-31"
  );
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((e) => e.includes("yyyy-MM-dd")));
});

test("buildPartnerRegistration: 種別・担当者名・関係性ランク・紹介料率・メモ・次回アクション予定日も行に反映される", () => {
  const result = adminAccess.buildPartnerRegistration(
    {
      "名称": "F信用金庫",
      "種別": "信用金庫",
      "担当者名": "比嘉様",
      "関係性ランク": "B",
      "紹介料率": "成約報酬の10%",
      "提供済み情報ログ": "8月に提携の挨拶訪問",
      "最終接触日": "2026-08-25",
      "次回アクション予定日": "2026-09-10"
    },
    [],
    "2026-08-31"
  );
  assert.equal(result.ok, true);
  assert.equal(result.record["種別"], "信用金庫");
  assert.equal(result.record["担当者名"], "比嘉様");
  assert.equal(result.record["関係性ランク"], "B");
  assert.equal(result.record["紹介料率"], "成約報酬の10%");
  assert.equal(result.record["提供済み情報ログ"], "8月に提携の挨拶訪問");
  assert.equal(result.record["逆紹介履歴"], "");
  assert.equal(result.record["最終接触日"], "2026-08-25");
  assert.equal(result.record["次回アクション予定日"], "2026-09-10");
});

// ---- buildFollowUpReminders(要対応ポップアップ) ----

test("buildFollowUpReminders: 次回アクション予定日が本日・期限超過の企業だけを抽出し、古い順に並べて遅延日数を付ける", () => {
  const today = "2026-08-31";
  const companies = [
    { "企業ID": "C1", "会社名": "本日予定の会社", "担当者": "山田", "次回アクション予定日": "2026-08-31", "連絡不要": false },
    { "企業ID": "C2", "会社名": "3日遅れの会社", "担当者": "田中", "次回アクション予定日": "2026-08-28", "連絡不要": false },
    { "企業ID": "C3", "会社名": "未来予定の会社", "次回アクション予定日": "2026-09-05", "連絡不要": false },
    { "企業ID": "C4", "会社名": "予定なしの会社", "次回アクション予定日": "", "連絡不要": false }
  ];
  const result = adminAccess.buildFollowUpReminders(companies, today, 10);
  assert.equal(result.total, 2);
  assert.equal(result.items.length, 2);
  assert.equal(result.items[0]["企業ID"], "C2");
  assert.equal(result.items[0]["遅延日数"], 3);
  assert.equal(result.items[1]["企業ID"], "C1");
  assert.equal(result.items[1]["遅延日数"], 0);
});

test("buildFollowUpReminders: 連絡不要の企業は除外する", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "連絡不要の会社", "次回アクション予定日": "2026-08-01", "連絡不要": true }
  ];
  const result = adminAccess.buildFollowUpReminders(companies, "2026-08-31", 10);
  assert.equal(result.total, 0);
});

test("buildFollowUpReminders: limitを超える分はitemsから外れるがtotalには含まれる", () => {
  const companies = [1, 2, 3, 4, 5].map((n) => ({
    "企業ID": "C" + n, "会社名": "会社" + n, "次回アクション予定日": "2026-08-2" + n, "連絡不要": false
  }));
  const result = adminAccess.buildFollowUpReminders(companies, "2026-08-31", 3);
  assert.equal(result.total, 5);
  assert.equal(result.items.length, 3);
});

test("buildFollowUpReminders: 次回アクション予定日がDateオブジェクトでも文字列に正規化して返す(google.script.run対策)", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "Date型の会社", "次回アクション予定日": new Date(2026, 7, 28), "連絡不要": false }
  ];
  const result = adminAccess.buildFollowUpReminders(companies, "2026-08-31", 10);
  assert.equal(result.total, 1);
  assert.equal(result.items[0]["次回アクション予定日"], "2026-08-28");
  assert.equal(typeof result.items[0]["次回アクション予定日"], "string");
});

test("buildFollowUpReminders: 次回アクション内容も一緒に返す(何をする予定だったか思い出せるように)", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "会社A", "担当者": "山田", "次回アクション予定日": "2026-08-30",
      "次回アクション内容": "資料持参で再訪問", "連絡不要": false }
  ];
  const result = adminAccess.buildFollowUpReminders(companies, "2026-08-31", 10);
  assert.equal(result.items[0]["次回アクション内容"], "資料持参で再訪問");
  assert.equal(result.items[0]["担当者"], "山田");
});

// ---- buildVisitSchedule(訪問・架電スケジュール表) ----

test("buildVisitSchedule: 今日からN日分の日付ブロックを返し、各日に予定企業を割り当てる", () => {
  const today = "2026-08-31";
  const companies = [
    { "企業ID": "C1", "会社名": "本日の会社", "担当者": "山田", "ランク": "A", "次回アクション予定日": "2026-08-31", "次回アクション内容": "架電", "連絡不要": false },
    { "企業ID": "C2", "会社名": "明日の会社", "担当者": "田中", "ランク": "B", "次回アクション予定日": "2026-09-01", "連絡不要": false },
    { "企業ID": "C3", "会社名": "範囲外の会社", "次回アクション予定日": "2026-12-01", "連絡不要": false }
  ];
  const result = adminAccess.buildVisitSchedule(companies, today, 7);
  assert.equal(result.today, "2026-08-31");
  assert.equal(result.days.length, 7);
  assert.equal(result.days[0].date, "2026-08-31");
  assert.equal(result.days[0]["曜日"], "月");
  assert.equal(result.days[0].items.length, 1);
  assert.equal(result.days[0].items[0]["会社名"], "本日の会社");
  assert.equal(result.days[1].items[0]["会社名"], "明日の会社");
  assert.equal(result.days[6].date, "2026-09-06");
  // 範囲外(12月)はどの日にも現れない
  const allNames = result.days.flatMap((d) => d.items.map((i) => i["会社名"]));
  assert.ok(!allNames.includes("範囲外の会社"));
});

test("buildVisitSchedule: 期限超過はoverdueに古い順でまとめ、連絡不要・予定日なしは除外する", () => {
  const today = "2026-08-31";
  const companies = [
    { "企業ID": "C1", "会社名": "3日遅れ", "次回アクション予定日": "2026-08-28", "連絡不要": false },
    { "企業ID": "C2", "会社名": "10日遅れ", "次回アクション予定日": "2026-08-21", "連絡不要": false },
    { "企業ID": "C3", "会社名": "連絡不要の会社", "次回アクション予定日": "2026-08-01", "連絡不要": true },
    { "企業ID": "C4", "会社名": "予定なし", "次回アクション予定日": "", "連絡不要": false }
  ];
  const result = adminAccess.buildVisitSchedule(companies, today, 7);
  assert.equal(result.overdue.total, 2);
  assert.equal(result.overdue.items[0]["会社名"], "10日遅れ");
  assert.equal(result.overdue.items[1]["会社名"], "3日遅れ");
});

test("buildVisitSchedule: 同じ日の中はランク順(A→D)、月をまたいでも日付が正しい", () => {
  const today = "2026-08-30";
  const companies = [
    { "企業ID": "C1", "会社名": "Cランクの会社", "ランク": "C", "次回アクション予定日": "2026-09-02", "連絡不要": false },
    { "企業ID": "C2", "会社名": "Aランクの会社", "ランク": "A", "次回アクション予定日": "2026-09-02", "連絡不要": false }
  ];
  const result = adminAccess.buildVisitSchedule(companies, today, 7);
  const day = result.days.find((d) => d.date === "2026-09-02");
  assert.equal(day.items[0]["会社名"], "Aランクの会社");
  assert.equal(day.items[1]["会社名"], "Cランクの会社");
});

test("buildVisitSchedule: 予定日がDateオブジェクトでも文字列に正規化される", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "Date型", "次回アクション予定日": new Date(2026, 8, 1), "連絡不要": false }
  ];
  const result = adminAccess.buildVisitSchedule(companies, "2026-08-31", 7);
  const day = result.days.find((d) => d.date === "2026-09-01");
  assert.equal(day.items.length, 1);
});

// ---- buildNextActionUpdate(次回アクションの直接編集) ----

test("buildNextActionUpdate: 正しい日付と内容ならok、前後の空白は除去", () => {
  const result = adminAccess.buildNextActionUpdate(" 2026-09-05 ", " 資料持参で再訪問 ");
  assert.equal(result.ok, true);
  assert.equal(result.date, "2026-09-05");
  assert.equal(result.note, "資料持参で再訪問");
});

test("buildNextActionUpdate: 日付が不正な形式ならok:false", () => {
  const result = adminAccess.buildNextActionUpdate("9月5日", "架電");
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((e) => e.includes("yyyy-MM-dd")));
});

test("buildNextActionUpdate: 日付を空にして予定を消すことも許可する", () => {
  const result = adminAccess.buildNextActionUpdate("", "");
  assert.equal(result.ok, true);
  assert.equal(result.date, "");
});

// ---- buildActivitySummary(行動量の実績ダッシュボード) ----

test("buildActivitySummary: 週(月曜はじまり)ごとに種別を指標に分類して集計する", () => {
  // 2026-08-31は月曜日 → 今週=08-31〜09-06、先週=08-24〜08-30
  const interactions = [
    { "日付": "2026-08-31", "担当者": "山田", "種別": "電話" },
    { "日付": "2026-09-02", "担当者": "山田", "種別": "アポ獲得" },
    { "日付": "2026-09-03", "担当者": "田中", "種別": "面談実施" },
    { "日付": "2026-08-25", "担当者": "山田", "種別": "手紙送付" },
    { "日付": "2026-08-26", "担当者": "山田", "種別": "提案(M&A)" },
    { "日付": "2026-08-27", "担当者": "田中", "種別": "成約" }
  ];
  const result = adminAccess.buildActivitySummary(interactions, "2026-08-31", 4);
  assert.deepEqual(result.metrics, ["手紙", "架電", "アポ獲得", "面談・訪問", "提案", "成約"]);
  assert.equal(result.weeks.length, 4);
  assert.equal(result.weeks[0].label, "今週");
  assert.equal(result.weeks[0].start, "2026-08-31");
  assert.equal(result.weeks[0].end, "2026-09-06");
  assert.equal(result.weeks[0].total["架電"], 1);
  assert.equal(result.weeks[0].total["アポ獲得"], 1);
  assert.equal(result.weeks[0].total["面談・訪問"], 1);
  assert.equal(result.weeks[1].label, "先週");
  assert.equal(result.weeks[1].total["手紙"], 1);
  assert.equal(result.weeks[1].total["提案"], 1);
  assert.equal(result.weeks[1].total["成約"], 1);
});

test("buildActivitySummary: 担当者別の内訳を持ち、担当者未記入は「未記入」に集計する", () => {
  const interactions = [
    { "日付": "2026-08-31", "担当者": "山田", "種別": "電話" },
    { "日付": "2026-08-31", "担当者": "山田", "種別": "電話" },
    { "日付": "2026-08-31", "担当者": "", "種別": "電話" }
  ];
  const result = adminAccess.buildActivitySummary(interactions, "2026-08-31", 1);
  assert.equal(result.weeks[0].byOwner["山田"]["架電"], 2);
  assert.equal(result.weeks[0].byOwner["未記入"]["架電"], 1);
  assert.equal(result.weeks[0].total["架電"], 3);
});

test("buildActivitySummary: 指標に該当しない種別(返信・関係メモ更新など)や範囲外の日付は数えない", () => {
  const interactions = [
    { "日付": "2026-08-31", "担当者": "山田", "種別": "返信" },
    { "日付": "2026-08-31", "担当者": "山田", "種別": "関係メモ更新" },
    { "日付": "2026-01-01", "担当者": "山田", "種別": "電話" }
  ];
  const result = adminAccess.buildActivitySummary(interactions, "2026-08-31", 4);
  result.weeks.forEach((week) => {
    result.metrics.forEach((metric) => {
      assert.equal(week.total[metric], 0, week.label + "の" + metric + "が0でない");
    });
  });
});

test("buildActivitySummary: 日付がDateオブジェクトでも集計できる(getValues由来)", () => {
  const interactions = [
    { "日付": new Date(2026, 7, 31, 10, 30), "担当者": "山田", "種別": "ゆんたく相談実施" }
  ];
  const result = adminAccess.buildActivitySummary(interactions, "2026-08-31", 1);
  assert.equal(result.weeks[0].total["面談・訪問"], 1);
});

test("buildActivitySummary: 週の途中(木曜)でも月曜はじまりで正しく区切る", () => {
  // 2026-09-03は木曜日 → 今週=08-31〜09-06
  const interactions = [
    { "日付": "2026-08-31", "担当者": "山田", "種別": "電話" },
    { "日付": "2026-08-30", "担当者": "山田", "種別": "電話" }
  ];
  const result = adminAccess.buildActivitySummary(interactions, "2026-09-03", 2);
  assert.equal(result.weeks[0].start, "2026-08-31");
  assert.equal(result.weeks[0].total["架電"], 1);
  assert.equal(result.weeks[1].start, "2026-08-24");
  assert.equal(result.weeks[1].total["架電"], 1);
});

// ---- validateQuickLog(詳細ドロワーからのクイック記録・v1.6.0) ----

test("validateQuickLog: 企業IDと正しい種別ならok。メモは前後の空白を除去", () => {
  const result = adminAccess.validateQuickLog({ "企業ID": "C1", "種別": "電話", "内容メモ": " 不在。夕方かけ直す " });
  assert.equal(result.ok, true);
  assert.equal(result.memo, "不在。夕方かけ直す");
});

test("validateQuickLog: メモが空でも種別だけで記録できる(電話不在などの最速記録)", () => {
  const result = adminAccess.validateQuickLog({ "企業ID": "C1", "種別": "電話", "内容メモ": "" });
  assert.equal(result.ok, true);
  assert.equal(result.memo, "");
});

test("validateQuickLog: 企業IDなし・不正な種別はok:false", () => {
  assert.equal(adminAccess.validateQuickLog({ "企業ID": "", "種別": "電話" }).ok, false);
  const bad = adminAccess.validateQuickLog({ "企業ID": "C1", "種別": "存在しない種別" });
  assert.equal(bad.ok, false);
  assert.ok(bad.errors.some((e) => e.includes("種別")));
});

test("validateQuickLog: 長すぎるメモ(2000文字超)は拒否する", () => {
  const result = adminAccess.validateQuickLog({ "企業ID": "C1", "種別": "電話", "内容メモ": "あ".repeat(2001) });
  assert.equal(result.ok, false);
});
