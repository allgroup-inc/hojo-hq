// glow-ma 使いやすさの改善(③今日の連絡先・⑤これまでの要約・⑥タブの整理)のテスト。会社名・番号・人名はすべて架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const t = require("../glow-ma/src/todayList.js");
const d = require("../glow-ma/src/companyDigest.js");
const tidy = require("../glow-ma/src/tabTidy.js");

const TODAY = "2026-11-09"; // 月曜

function co(id, over) {
  return { 企業ID: id, 会社名: "架空商事" + id, 電話番号: "098-000-" + id.slice(-4), 連絡不要: false, 現在ステージ: "未接触", ランク: "B", 事前選定ランク: "B", 事前選定スコア: 10, 総合スコア: 50, ...over };
}
function log(date, type, over) {
  return { 日付: date, 種別: type, 担当者: "架空 太郎", 内容メモ: "", 次回アクション: "", ...over };
}

// ---- ⑤ これまでの要約 ----

test("要約: 記録が無ければ、無いことをはっきり書く", () => {
  assert.equal(d.buildCompanyDigest([], TODAY), "まだ連絡の記録はありません");
  assert.equal(d.buildCompanyDigest(null, TODAY), "まだ連絡の記録はありません");
});

test("要約: 回数と種別の内訳・最後の連絡(何日前・誰・メモの先頭)・次の予定を1行にまとめる", () => {
  const history = [
    log("2026-10-01", "手紙送付"),
    log("2026-10-20", "電話", { 内容メモ: "不在。折り返し待ち" }),
    log(new Date("2026-11-03T01:00:00Z"), "電話", { 内容メモ: "社長と話せた。来月に面談の候補日をもらう予定。資料を先に送る", 次回アクション: "資料を送る" }),
  ];
  const s = d.buildCompanyDigest(history, TODAY);
  assert.match(s, /^連絡 3回\(電話2・手紙送付1\)/);
  assert.match(s, /最後: 11\/3 電話\(6日前・架空 太郎\)/);
  assert.match(s, /「社長と話せた。来月に面談の候補日をもらう予定。資料を先に…」/); // 先頭28字で切る
  assert.match(s, /次: 資料を送る$/);
});

test("要約: 日付の新しい順に並んでいなくても、最後の連絡を正しく選ぶ", () => {
  const history = [log("2026-11-05", "面談実施", { 内容メモ: "訪問" }), log("2026-09-01", "電話", { 内容メモ: "古い" })];
  assert.match(d.buildCompanyDigest(history, TODAY), /最後: 11\/5 面談実施\(4日前/);
});

// ---- ③ 今日の連絡先 ----

test("今日の連絡先: 連絡不要・成約/見送り・電話番号なし・7日以内に連絡済みは出さない", () => {
  const companies = [
    co("C9000001"),
    co("C9000002", { 連絡不要: true }),
    co("C9000003", { 現在ステージ: "成約" }),
    co("C9000004", { 現在ステージ: "見送り" }),
    co("C9000005", { 電話番号: "" }),
    co("C9000006", { 最終接触日: "2026-11-05", 現在ステージ: "電話済み" }),
  ];
  const logs = { C9000006: [log("2026-11-05", "電話")] };
  assert.deepEqual(t.buildTodayList(companies, logs, TODAY).map((e) => e.企業ID), ["C9000001"]);
});

test("今日の連絡先: 予定日 → フォロー → 手紙のあと → 新規の順に、決めた件数まで出す", () => {
  const companies = [
    co("C9000011"), // 新規(事前選定スコア10)
    co("C9000012", { 事前選定スコア: 30 }), // 新規(スコア高)
    co("C9000013", { 次回アクション予定日: "2026-11-08" }), // 予定日(昨日)
    co("C9000014", { 最終接触日: "2026-07-01", 現在ステージ: "電話済み", ランク: "B" }), // フォロー(Bは90日)
    co("C9000015"), // 手紙のあと(10日前)
  ];
  const logs = {
    C9000014: [log("2026-07-01", "電話")],
    C9000015: [log("2026-10-30", "手紙送付")],
  };
  const list = t.buildTodayList(companies, logs, TODAY, { size: 4 });
  assert.deepEqual(list.map((e) => [e.企業ID, e.区分]), [
    ["C9000013", "予定日"], ["C9000014", "フォロー"], ["C9000015", "手紙のあと"], ["C9000012", "新規"],
  ]);
  assert.deepEqual(list.map((e) => e.順位), [1, 2, 3, 4]);
  assert.ok(list.every((e) => typeof e.理由 === "string" && e.理由.length > 0));
});

test("今日の連絡先: 予定日のある会社は、7日以内に連絡していても予定日どおり出す", () => {
  const companies = [co("C9000021", { 最終接触日: "2026-11-06", 次回アクション予定日: "2026-11-09", 現在ステージ: "電話済み" })];
  const logs = { C9000021: [log("2026-11-06", "電話")] };
  assert.deepEqual(t.buildTodayList(companies, logs, TODAY).map((e) => e.区分), ["予定日"]);
});

test("今日の連絡先: 手紙のあとは、送ってから5〜45日で、そのあと電話などをしていない会社だけ", () => {
  const companies = ["C9000031", "C9000032", "C9000033", "C9000034"].map((id) => co(id));
  const logs = {
    C9000031: [log("2026-11-06", "手紙送付")], // 3日前 → まだ早い(新規にも出さない)
    C9000032: [log("2026-09-01", "手紙送付")], // 69日前 → 時期を過ぎた(フォロー対象でもない)
    C9000033: [log("2026-10-20", "手紙送付"), log("2026-10-25", "電話")], // 手紙のあと電話済み
    C9000034: [log("2026-10-25", "手紙送付")], // 15日前 → 出す
  };
  const list = t.buildTodayList(companies, logs, TODAY);
  assert.deepEqual(list.filter((e) => e.区分 === "手紙のあと").map((e) => e.企業ID), ["C9000034"]);
  assert.ok(!list.some((e) => e.企業ID === "C9000031"));
});

test("今日の連絡先: 新規は、事前選定ランクS → 事前選定スコア → 総合スコアの順", () => {
  const companies = [
    co("C9000041", { 事前選定ランク: "A", 事前選定スコア: 40, 総合スコア: 10 }),
    co("C9000042", { 事前選定ランク: "S", 事前選定スコア: 20, 総合スコア: 10 }),
    co("C9000043", { 事前選定ランク: "B", 事前選定スコア: 40, 総合スコア: 60 }),
    co("C9000044", { 事前選定ランク: "C", 事前選定スコア: "", 総合スコア: 99 }), // スコアが空は後ろ
  ];
  assert.deepEqual(t.buildTodayList(companies, {}, TODAY).map((e) => e.企業ID), ["C9000042", "C9000043", "C9000041", "C9000044"]);
});

test("今日の連絡先: フォローは、ランクごとの間隔(A30・B90・C180日)を過ぎ、長く空いた順", () => {
  const companies = [
    co("C9000051", { ランク: "A", 最終接触日: "2026-10-01", 現在ステージ: "電話済み" }), // 39日 ≥ 30
    co("C9000052", { ランク: "C", 最終接触日: "2026-07-01", 現在ステージ: "電話済み" }), // 131日 < 180 → 出さない
    co("C9000053", { ランク: "B", 最終接触日: "2026-06-01", 現在ステージ: "電話済み" }), // 161日 ≥ 90
  ];
  const logs = { C9000051: [log("2026-10-01", "電話")], C9000052: [log("2026-07-01", "電話")], C9000053: [log("2026-06-01", "電話")] };
  assert.deepEqual(t.buildTodayList(companies, logs, TODAY).map((e) => e.企業ID), ["C9000053", "C9000051"]);
});

test("今日の連絡先: 紹介(①)の会社はAランクとして扱う(既存の掘り起こしアラートと同じ)", () => {
  const companies = [co("C9000061", { ランク: "C", 流入ルート: ["①紹介"], 最終接触日: "2026-10-01", 現在ステージ: "電話済み" })];
  const logs = { C9000061: [log("2026-10-01", "電話")] };
  assert.deepEqual(t.buildTodayList(companies, logs, TODAY).map((e) => e.区分), ["フォロー"]);
});

test("今日の連絡先: 「これまで」の要約と、日付は文字列で入る(Dateをそのまま返さない)", () => {
  const companies = [co("C9000071", { 次回アクション予定日: new Date("2026-11-08T15:00:00Z") })]; // 日本時間 11/9 0:00
  const [e] = t.buildTodayList(companies, {}, TODAY);
  assert.equal(e.区分, "予定日");
  assert.equal(e.次回アクション予定日, "2026-11-09");
  assert.equal(e.これまで, "まだ連絡の記録はありません");
});

test("今日の連絡先: 件数の既定は10件。会社が多くても10件で止める", () => {
  const companies = Array.from({ length: 30 }, (_, i) => co("C91" + String(10000 + i)));
  assert.equal(t.buildTodayList(companies, {}, TODAY).length, 10);
  assert.equal(t.TODAY_LIST_HEADERS[0], "順位");
});

// ---- ⑥ 使っていないタブの整理 ----

test("タブの整理: 「シート数字」・企業マスタのバックアップ・空のQR生成結果だけを非表示にする(消さない)", () => {
  const sheets = [
    { name: "企業マスタ", hidden: false }, { name: "対応履歴ログ", hidden: false }, { name: "ダッシュボード", hidden: false },
    { name: "シート1", hidden: false }, { name: "シート9", hidden: false }, { name: "シート2", hidden: true },
    { name: "企業マスタ_backup_2026-08-11_034603", hidden: false }, { name: "QR生成結果", hidden: false, rows: 0 },
    { name: "インポート待ち", hidden: false }, { name: "シートA", hidden: false },
  ];
  assert.deepEqual(tidy.planHide(sheets), ["シート1", "シート9", "企業マスタ_backup_2026-08-11_034603", "QR生成結果"]);
});

test("タブの整理: QR生成結果に行があれば残す。見えるタブが1つも残らなくなるなら何もしない", () => {
  assert.deepEqual(tidy.planHide([{ name: "企業マスタ", hidden: false }, { name: "QR生成結果", hidden: false, rows: 3 }]), []);
  assert.deepEqual(tidy.planHide([{ name: "シート1", hidden: false }]), []);
  assert.deepEqual(tidy.planHide([]), []);
});
