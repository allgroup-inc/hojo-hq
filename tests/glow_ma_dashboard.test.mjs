import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dashboard = require("../glow-ma/src/dashboard.js");

test("buildRouteStageFunnel: ルート×ステージの組み合わせごとに件数を集計する(複数ルートを持つ企業は両方にカウントされる)", () => {
  const records = [
    { 流入ルート: ["①紹介"], 現在ステージ: "未接触" },
    { 流入ルート: ["①紹介", "②手紙DM"], 現在ステージ: "関係構築中" },
    { 流入ルート: ["③ミカタ経由"], 現在ステージ: "未接触" }
  ];
  const funnel = dashboard.buildRouteStageFunnel(records, dashboard.DEFAULT_CONFIG);
  const find = (route, stage) => funnel.find((f) => f["流入ルート"] === route && f["現在ステージ"] === stage);
  assert.equal(find("①紹介", "未接触")["件数"], 1);
  assert.equal(find("①紹介", "関係構築中")["件数"], 1);
  assert.equal(find("②手紙DM", "関係構築中")["件数"], 1);
  assert.equal(find("③ミカタ経由", "未接触")["件数"], 1);
  assert.equal(find("②手紙DM", "未接触")["件数"], 0);
  assert.equal(funnel.length, dashboard.DEFAULT_CONFIG.routes.length * dashboard.DEFAULT_CONFIG.stages.length);
});

test("buildRouteStageFunnel: 空配列なら全組み合わせが0件", () => {
  const funnel = dashboard.buildRouteStageFunnel([], dashboard.DEFAULT_CONFIG);
  assert.ok(funnel.every((f) => f["件数"] === 0));
});

test("buildProductFunnel: 提案商品ごとに提案数・案件化数・成約数を集計する", () => {
  const records = [
    { 提案商品: ["M&A"], 現在ステージ: "案件化" },
    { 提案商品: ["M&A", "不動産"], 現在ステージ: "成約" },
    { 提案商品: ["法人保険"], 現在ステージ: "提案中" }
  ];
  const summary = dashboard.buildProductFunnel(records, dashboard.DEFAULT_CONFIG);
  const find = (product) => summary.find((s) => s["商品"] === product);
  assert.deepEqual(find("M&A"), { "商品": "M&A", "提案数": 2, "案件化数": 2, "成約数": 1 });
  assert.deepEqual(find("不動産"), { "商品": "不動産", "提案数": 1, "案件化数": 1, "成約数": 1 });
  assert.deepEqual(find("法人保険"), { "商品": "法人保険", "提案数": 1, "案件化数": 0, "成約数": 0 });
});

test("buildProductFunnel: 提案商品が未設定の企業は集計対象外", () => {
  const records = [{ 現在ステージ: "未接触" }];
  const summary = dashboard.buildProductFunnel(records, dashboard.DEFAULT_CONFIG);
  summary.forEach((s) => assert.equal(s["提案数"], 0));
});

test("buildProductFunnel: 成約は案件化を経由した扱いとして案件化数にも含める(ファネルの単調性維持)", () => {
  const records = [
    { 提案商品: ["M&A"], 現在ステージ: "案件化" },
    { 提案商品: ["M&A"], 現在ステージ: "成約" },
    { 提案商品: ["M&A"], 現在ステージ: "成約" },
    { 提案商品: ["M&A"], 現在ステージ: "成約" }
  ];
  const summary = dashboard.buildProductFunnel(records, dashboard.DEFAULT_CONFIG);
  const find = (product) => summary.find((s) => s["商品"] === product);
  assert.deepEqual(find("M&A"), { "商品": "M&A", "提案数": 4, "案件化数": 4, "成約数": 3 });
});

test("buildProductFunnel: 見送りステージは案件化数・成約数に含めない(提案数のみ)", () => {
  const records = [{ 提案商品: ["M&A"], 現在ステージ: "見送り" }];
  const summary = dashboard.buildProductFunnel(records, dashboard.DEFAULT_CONFIG);
  const find = (product) => summary.find((s) => s["商品"] === product);
  assert.deepEqual(find("M&A"), { "商品": "M&A", "提案数": 1, "案件化数": 0, "成約数": 0 });
});

test("buildRankSummary: 実効ランクごとに滞留企業数と掘り起こし待ち件数を集計する(紹介ルートは常にAとして数える)", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01" },
    { 企業ID: "C2", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-27" },
    { 企業ID: "C3", ランク: "D", 流入ルート: ["①紹介"], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-01" }
  ];
  const summary = dashboard.buildRankSummary(records, "2026-07-27", dashboard.DEFAULT_CONFIG);
  const find = (rank) => summary.find((s) => s["ランク"] === rank);
  assert.equal(find("A")["滞留企業数"], 3);
  assert.equal(find("A")["掘り起こし待ち件数"], 1);
  assert.equal(find("D")["滞留企業数"], 0);
});

test("buildRankSummary: 対象企業がなければ全ランク0件", () => {
  const summary = dashboard.buildRankSummary([], "2026-07-27", dashboard.DEFAULT_CONFIG);
  summary.forEach((s) => {
    assert.equal(s["滞留企業数"], 0);
    assert.equal(s["掘り起こし待ち件数"], 0);
  });
});

test("buildRankSummary: 成約(終了ステージ)の企業は滞留企業数・掘り起こし待ち件数のどちらにも数えない", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 流入ルート: [], 現在ステージ: "成約", 次回アクション予定日: "", 最終接触日: "2020-01-01" },
    { 企業ID: "C2", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01" }
  ];
  const summary = dashboard.buildRankSummary(records, "2026-07-27", dashboard.DEFAULT_CONFIG);
  const find = (rank) => summary.find((s) => s["ランク"] === rank);
  assert.equal(find("A")["滞留企業数"], 1);
  assert.equal(find("A")["掘り起こし待ち件数"], 1);
});

test("countUnclassifiedCompanies: クリーンなデータなら全項目0件", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 現在ステージ: "未接触", 流入ルート: ["①紹介"], 提案商品: ["M&A"] },
    { 企業ID: "C2", ランク: "B", 現在ステージ: "成約", 流入ルート: ["②手紙DM"], 提案商品: ["不動産"] }
  ];
  const result = dashboard.countUnclassifiedCompanies(records, dashboard.DEFAULT_CONFIG);
  assert.deepEqual(result, {
    "対象企業数": 2,
    "未スコア企業数": 0,
    "現在ステージ未分類企業数": 0,
    "流入ルート未分類企業数": 0,
    "提案商品未設定企業数": 0
  });
});

test("countUnclassifiedCompanies: 未定義の現在ステージ値は現在ステージ未分類企業数に計上する", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 現在ステージ: "謎ステージ", 流入ルート: ["①紹介"], 提案商品: ["M&A"] }
  ];
  const result = dashboard.countUnclassifiedCompanies(records, dashboard.DEFAULT_CONFIG);
  assert.equal(result["現在ステージ未分類企業数"], 1);
});

test("countUnclassifiedCompanies: 流入ルートが空または未定義の値のみの場合は流入ルート未分類企業数に計上する", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 現在ステージ: "未接触", 流入ルート: [], 提案商品: ["M&A"] },
    { 企業ID: "C2", ランク: "A", 現在ステージ: "未接触", 流入ルート: ["④謎ルート"], 提案商品: ["M&A"] }
  ];
  const result = dashboard.countUnclassifiedCompanies(records, dashboard.DEFAULT_CONFIG);
  assert.equal(result["流入ルート未分類企業数"], 2);
});

test("countUnclassifiedCompanies: 提案商品が空または未定義の値のみの場合は提案商品未設定企業数に計上する", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 現在ステージ: "未接触", 流入ルート: ["①紹介"], 提案商品: [] },
    { 企業ID: "C2", ランク: "A", 現在ステージ: "未接触", 流入ルート: ["①紹介"], 提案商品: ["謎商品"] }
  ];
  const result = dashboard.countUnclassifiedCompanies(records, dashboard.DEFAULT_CONFIG);
  assert.equal(result["提案商品未設定企業数"], 2);
});

test("countUnclassifiedCompanies: ランク未設定の企業はalerting.countUnscoredCompaniesと同じ基準で未スコア企業数に計上する", () => {
  const records = [
    { 企業ID: "C1", ランク: "", 現在ステージ: "未接触", 流入ルート: ["①紹介"], 提案商品: ["M&A"] },
    { 企業ID: "C2", 現在ステージ: "未接触", 流入ルート: ["①紹介"], 提案商品: ["M&A"] }
  ];
  const result = dashboard.countUnclassifiedCompanies(records, dashboard.DEFAULT_CONFIG);
  assert.equal(result["未スコア企業数"], 2);
});

test("formatPartnerSummary: パートナーマスタの表示用フィールドを整形する", () => {
  const partners = [
    { 名称: "テスト税理士法人", 累計紹介数: 5, 成約数: 1, 関係性ランク: "高", 提供済み情報ログ: "建設業向け資料を提供", 逆紹介履歴: "サンプル建設を紹介" }
  ];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.deepEqual(summary, [
    { "名称": "テスト税理士法人", "累計紹介数": 5, "成約数": 1, "関係性ランク": "高", "提供済み情報ログ": "建設業向け資料を提供", "逆紹介履歴": "サンプル建設を紹介", "成約率": "20.0%" }
  ]);
});

test("formatPartnerSummary: 欠損フィールドは空文字で埋める(成約率は累計紹介数0のため空文字)", () => {
  const summary = dashboard.formatPartnerSummary([{ 名称: "テスト銀行" }]);
  assert.deepEqual(summary[0], { "名称": "テスト銀行", "累計紹介数": "", "成約数": "", "関係性ランク": "", "提供済み情報ログ": "", "逆紹介履歴": "", "成約率": "" });
});

test("formatPartnerSummary: 空配列なら空配列", () => {
  assert.deepEqual(dashboard.formatPartnerSummary([]), []);
});

test("formatPartnerSummary: 成約率は成約数/累計紹介数を百分率(小数点1桁)で返す", () => {
  const partners = [{ 名称: "A", 累計紹介数: 3, 成約数: 1 }];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.equal(summary[0]["成約率"], "33.3%");
});

test("formatPartnerSummary: 累計紹介数が0なら成約率は空文字(ゼロ除算しない)", () => {
  const partners = [{ 名称: "A", 累計紹介数: 0, 成約数: 0 }];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.equal(summary[0]["成約率"], "");
});

test("formatPartnerSummary: 累計紹介数が3未満なら成約率は空文字(母数不足)", () => {
  const partners = [{ 名称: "新規パートナー", 累計紹介数: 1, 成約数: 1 }];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.equal(summary[0]["成約率"], "");
});

test("formatPartnerSummary: 累計紹介数が2でも成約率は空文字(母数不足)", () => {
  const partners = [{ 名称: "新規パートナー", 累計紹介数: 2, 成約数: 1 }];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.equal(summary[0]["成約率"], "");
});

test("buildHistorySnapshot: ランク別滞留企業数・掘り起こし待ち件数合計・成約企業数・連絡不要企業数を集計する", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: false },
    { 企業ID: "C2", ランク: "B", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-27", 連絡不要: false },
    { 企業ID: "C3", ランク: "D", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: true },
    { 企業ID: "C4", ランク: "A", 流入ルート: [], 現在ステージ: "成約", 提案商品: ["M&A"], 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: false }
  ];
  const snapshot = dashboard.buildHistorySnapshot(records, "2026-07-27", dashboard.DEFAULT_CONFIG);
  assert.equal(snapshot["対象企業数"], 4);
  assert.equal(snapshot["ランクA_滞留企業数"], 1);
  assert.equal(snapshot["ランクB_滞留企業数"], 1);
  assert.equal(snapshot["ランクD_滞留企業数"], 1);
  // C1は掘り起こし対象(30日サイクル超過)。C3は連絡不要のためisOverdueがfalseを返し対象外。
  // C4は成約(終了ステージ)のためbuildRankSummary上は滞留企業数・掘り起こし待ちどちらにも数えない
  assert.equal(snapshot["掘り起こし待ち件数合計"], 1);
  assert.equal(snapshot["成約企業数"], 1);
  assert.equal(snapshot["連絡不要企業数"], 1);
});

test("buildHistorySnapshot: 成約企業数は提案商品数によらず企業1社につき1件として数える(buildProductFunnelの成約数とは別概念)", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 流入ルート: [], 現在ステージ: "成約", 提案商品: ["M&A", "不動産", "法人保険"], 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: false },
    { 企業ID: "C2", ランク: "B", 流入ルート: [], 現在ステージ: "成約", 提案商品: ["M&A"], 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: false },
    { 企業ID: "C3", ランク: "C", 流入ルート: [], 現在ステージ: "提案中", 提案商品: ["M&A"], 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: false }
  ];
  const snapshot = dashboard.buildHistorySnapshot(records, "2026-07-27", dashboard.DEFAULT_CONFIG);
  // C1は提案商品3件を持つが、成約企業数は「企業単位」で1件としてのみ数える(3件と数えない)
  assert.equal(snapshot["成約企業数"], 2);
});

test("buildHistorySnapshot: 対象企業がなければ全項目0", () => {
  const snapshot = dashboard.buildHistorySnapshot([], "2026-07-27", dashboard.DEFAULT_CONFIG);
  assert.equal(snapshot["対象企業数"], 0);
  assert.equal(snapshot["掘り起こし待ち件数合計"], 0);
  assert.equal(snapshot["成約企業数"], 0);
  assert.equal(snapshot["連絡不要企業数"], 0);
});

test("buildDealStageProgressSummary: 企業ごとに最新の工程遷移イベントを現在の工程とみなし、工程別に滞留企業数・平均滞留日数を集計する", () => {
  const interactionRecords = [
    { 企業ID: "C1", 日付: "2026-07-01", 種別: "NDA締結" },
    { 企業ID: "C2", 日付: "2026-06-01", 種別: "NDA締結" },
    { 企業ID: "C2", 日付: "2026-07-11", 種別: "意向表明受領" },
    { 企業ID: "C3", 日付: "2026-06-21", 種別: "DD開始" },
    { 企業ID: "C4", 日付: "2026-07-01", 種別: "電話" }
  ];
  const summary = dashboard.buildDealStageProgressSummary(interactionRecords, "2026-07-31", dashboard.DEFAULT_CONFIG);
  assert.deepEqual(summary, [
    { "工程": "NDA締結", "滞留企業数": 1, "平均滞留日数": 30 },
    { "工程": "意向表明受領", "滞留企業数": 1, "平均滞留日数": 20 },
    { "工程": "DD開始", "滞留企業数": 1, "平均滞留日数": 40 }
  ]);
});

test("buildDealStageProgressSummary: 同じ工程に複数企業がいる場合は平均滞留日数を四捨五入して返す", () => {
  const interactionRecords = [
    { 企業ID: "C1", 日付: "2026-07-21", 種別: "NDA締結" }, // 10日
    { 企業ID: "C2", 日付: "2026-07-11", 種別: "NDA締結" }  // 20日
  ];
  const summary = dashboard.buildDealStageProgressSummary(interactionRecords, "2026-07-31", dashboard.DEFAULT_CONFIG);
  assert.equal(summary[0]["滞留企業数"], 2);
  assert.equal(summary[0]["平均滞留日数"], 15);
});

test("buildDealStageProgressSummary: 対象工程のイベントがない企業は集計から除外される", () => {
  const interactionRecords = [
    { 企業ID: "C1", 日付: "2026-07-01", 種別: "電話" },
    { 企業ID: "C1", 日付: "2026-07-05", 種別: "面談実施" }
  ];
  const summary = dashboard.buildDealStageProgressSummary(interactionRecords, "2026-07-31", dashboard.DEFAULT_CONFIG);
  summary.forEach(function (row) { assert.equal(row["滞留企業数"], 0); });
});

test("buildDealStageProgressSummary: 対応履歴が空配列なら全工程0件", () => {
  const summary = dashboard.buildDealStageProgressSummary([], "2026-07-31", dashboard.DEFAULT_CONFIG);
  assert.deepEqual(summary, [
    { "工程": "NDA締結", "滞留企業数": 0, "平均滞留日数": 0 },
    { "工程": "意向表明受領", "滞留企業数": 0, "平均滞留日数": 0 },
    { "工程": "DD開始", "滞留企業数": 0, "平均滞留日数": 0 }
  ]);
});
