import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const alerting = require("../glow-ma/src/alerting.js");

test("toDate: yyyy-MM-dd形式の文字列をDateに変換する", () => {
  const d = alerting.toDate("2026-07-27");
  assert.equal(d.getFullYear(), 2026);
  assert.equal(d.getMonth(), 6);
  assert.equal(d.getDate(), 27);
});

test("toDate: Dateオブジェクトはそのまま返す(GASがセルを日付型として読む場合に対応)", () => {
  const original = new Date(2026, 6, 27);
  assert.equal(alerting.toDate(original), original);
});

test("toDate: 空文字・null・不正な形式はnull", () => {
  assert.equal(alerting.toDate(""), null);
  assert.equal(alerting.toDate(null), null);
  assert.equal(alerting.toDate(undefined), null);
  assert.equal(alerting.toDate("不正な値"), null);
});

test("daysBetween: 日数差を正しく計算する", () => {
  assert.equal(alerting.daysBetween("2026-07-01", "2026-07-27"), 26);
});

test("daysBetween: 文字列とDateオブジェクトが混在していても計算できる", () => {
  assert.equal(alerting.daysBetween(new Date(2026, 6, 1), "2026-07-27"), 26);
});

test("daysBetween: どちらかが不正な日付ならnull", () => {
  assert.equal(alerting.daysBetween("", "2026-07-27"), null);
  assert.equal(alerting.daysBetween("2026-07-01", null), null);
});

test("resolveEffectiveRank: 紹介ルートを含む企業は常にAランク相当を返す", () => {
  const record = { 流入ルート: ["①紹介"], ランク: "D" };
  assert.equal(alerting.resolveEffectiveRank(record, alerting.DEFAULT_CONFIG), "A");
});

test("resolveEffectiveRank: 紹介ルートを含まない企業はランクをそのまま返す", () => {
  const record = { 流入ルート: ["②手紙DM"], ランク: "C" };
  assert.equal(alerting.resolveEffectiveRank(record, alerting.DEFAULT_CONFIG), "C");
});

test("resolveEffectiveRank: 流入ルートが未設定でもエラーにならない", () => {
  const record = { ランク: "B" };
  assert.equal(alerting.resolveEffectiveRank(record, alerting.DEFAULT_CONFIG), "B");
});

test("isOverdue: 次回アクション予定日が今日以前なら掘り起こし対象(サイクルより優先)", () => {
  const record = { ランク: "D", 流入ルート: [], 次回アクション予定日: "2026-07-26", 最終接触日: "2026-07-26" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), true);
});

test("isOverdue: 次回アクション予定日が未来ならサイクルを超過していても対象外", () => {
  const record = { ランク: "A", 流入ルート: [], 次回アクション予定日: "2026-08-01", 最終接触日: "2026-01-01" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), false);
});

test("isOverdue: 次回アクション予定日が未設定ならランク別サイクルで判定する", () => {
  const overdue = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "2026-04-01" };
  // Bランクは90日サイクル。2026-04-01→2026-07-27は117日経過 → 対象
  assert.equal(alerting.isOverdue(overdue, "2026-07-27", alerting.DEFAULT_CONFIG), true);

  const notYet = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "2026-07-01" };
  // 26日しか経過していない → 対象外
  assert.equal(alerting.isOverdue(notYet, "2026-07-27", alerting.DEFAULT_CONFIG), false);
});

test("isOverdue: 紹介ルートの企業はランクに関わらず30日サイクルで判定する", () => {
  const record = { ランク: "D", 流入ルート: ["①紹介"], 次回アクション予定日: "", 最終接触日: "2026-06-01" };
  // Dランクなら365日サイクルだが、紹介ルートなので30日サイクルを適用 → 56日経過で対象
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), true);
});

test("isOverdue: 最終接触日が未設定なら登録日を代わりに使う", () => {
  const record = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "", 登録日: "2026-04-01" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), true);
});

test("isOverdue: 日付を一切計算できない場合は対象外(誤検知を避ける)", () => {
  const record = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "", 登録日: "" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), false);
});

test("determineNextBestAction: Aランク×未接触系ステージは至急電話推奨", () => {
  const record = { ランク: "A", 流入ルート: [], 現在ステージ: "未接触" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "至急電話推奨(最優先ランク)");
});

test("determineNextBestAction: Bランク×未接触は電話推奨", () => {
  const record = { ランク: "B", 流入ルート: [], 現在ステージ: "未接触" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "電話推奨");
});

test("determineNextBestAction: Cランク×電話済みはゆんたく相談室の再案内", () => {
  const record = { ランク: "C", 流入ルート: [], 現在ステージ: "電話済み" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "ゆんたく相談室の再案内");
});

test("determineNextBestAction: Dランクはステージによらずナーチャリング配信の対象", () => {
  const record = { ランク: "D", 流入ルート: [], 現在ステージ: "関係構築中" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "ナーチャリング配信の対象に追加");
});

test("determineNextBestAction: どのルールにも一致しない場合は汎用アクションを返す", () => {
  const record = { ランク: "B", 流入ルート: [], 現在ステージ: "案件化" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "対応履歴を確認し次のアクションを検討");
});

test("buildDailyAlertList: 掘り起こし対象のみ抽出し、ランクA→Dの順に並べる", () => {
  const records = [
    { 企業ID: "C1", 会社名: "D社", ランク: "D", 流入ルート: [], 現在ステージ: "関係構築中", 次回アクション予定日: "", 最終接触日: "2020-01-01" },
    { 企業ID: "C2", 会社名: "A社", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01" },
    { 企業ID: "C3", 会社名: "対象外社", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-27" }
  ];
  const alerts = alerting.buildDailyAlertList(records, "2026-07-27", alerting.DEFAULT_CONFIG);
  assert.equal(alerts.length, 2);
  assert.deepEqual(alerts.map((a) => a["企業ID"]), ["C2", "C1"]);
  assert.equal(alerts[0]["ネクストベストアクション"], "至急電話推奨(最優先ランク)");
});

test("buildDailyAlertList: 対象企業がなければ空配列", () => {
  assert.deepEqual(alerting.buildDailyAlertList([], "2026-07-27", alerting.DEFAULT_CONFIG), []);
});
