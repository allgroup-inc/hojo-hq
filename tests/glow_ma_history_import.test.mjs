import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const h = require("../glow-ma/src/historyImport.js");

const OPTS = { today: "2026-10-25", nextSequence: 3213, staffName: "" };
const HEADER = ["会社名", "電話番号", "手紙送付日", "架電日", "通話結果", "備考"];

function existing() {
  return [
    { 企業ID: "C000010", 会社名: "株式会社テスト建設", 電話番号: "098-111-2222", 流入ルート: [], 現在ステージ: "未接触", 最終接触日: "" },
    { 企業ID: "C000011", 会社名: "有限会社 うみかぜ", 電話番号: "", 流入ルート: ["①紹介"], 現在ステージ: "相談実施", 最終接触日: "2026-10-01" },
  ];
}

test("台帳にある会社(電話番号一致)は新規登録せず、既存の企業IDに履歴を付ける", () => {
  const recs = existing();
  const plan = h.planHistoryImport(HEADER, [["テスト建設", "0981112222", "2026/09/10", "2026/09/20", "不在", ""]], recs, [], OPTS);
  assert.equal(plan.newRecords.length, 0);
  assert.equal(plan.summary.matched, 1);
  assert.deepEqual(plan.logs.map((l) => [l.企業ID, l.日付, l.種別]), [
    ["C000010", "2026-09-10", "手紙送付"],
    ["C000010", "2026-09-20", "電話"],
  ]);
  assert.equal(recs[0].現在ステージ, "電話済み");
  assert.equal(recs[0].最終接触日, "2026-09-20");
  assert.deepEqual(recs[0].流入ルート, ["②手紙DM"]);
  assert.match(plan.logs[1].内容メモ, /結果: 不在/);
});

test("電話番号が無くても会社名(空白・全角の違いを無視)で突き合わせる", () => {
  const recs = existing();
  const plan = h.planHistoryImport(HEADER, [["有限会社うみかぜ", "", "2026-09-05", "", "", ""]], recs, [], OPTS);
  assert.equal(plan.newRecords.length, 0);
  assert.equal(plan.logs[0].企業ID, "C000011");
});

test("ステージは後戻りさせない(相談実施の会社に手紙記録を足しても相談実施のまま)", () => {
  const recs = existing();
  h.planHistoryImport(HEADER, [["有限会社うみかぜ", "", "2026-09-05", "", "", ""]], recs, [], OPTS);
  assert.equal(recs[1].現在ステージ, "相談実施");
  assert.equal(recs[1].最終接触日, "2026-10-01");
  assert.deepEqual(recs[1].流入ルート, ["①紹介", "②手紙DM"]);
});

test("台帳に無い会社は、企業マスタの列名で新規登録する", () => {
  const plan = h.planHistoryImport(HEADER, [["株式会社あたらし", "098-999-0000", "2026-09-01", "", "", "社長ご不在"]], existing(), [], OPTS);
  assert.equal(plan.newRecords.length, 1);
  const r = plan.newRecords[0];
  assert.equal(r.企業ID, "C003213");
  assert.equal(r.会社名, "株式会社あたらし");
  assert.equal(r.現在ステージ, "アプローチ実施");
  assert.deepEqual(r.流入ルート, ["②手紙DM"]);
  assert.equal(r.登録日, "2026-10-25");
  assert.ok(!("企業名" in r) && !("ステージ" in r), "旧版の誤った列名を使わない");
});

test("同じ会社・同じ日・同じ種別の履歴は、既にあれば書かない(再実行しても増えない)", () => {
  const plan = h.planHistoryImport(HEADER, [["テスト建設", "0981112222", "2026/09/10", "", "", ""]], existing(),
    [{ 企業ID: "C000010", 日付: "2026-09-10", 種別: "手紙送付" }], OPTS);
  assert.equal(plan.logs.length, 0);
});

test("同じ表に同じ会社が2行あっても、新規登録は1社だけ", () => {
  const plan = h.planHistoryImport(HEADER, [
    ["株式会社ふたつ", "098-777-0000", "2026-09-01", "", "", ""],
    ["株式会社ふたつ", "098-777-0000", "", "2026-09-15", "話せた", ""],
  ], existing(), [], OPTS);
  assert.equal(plan.newRecords.length, 1);
  assert.equal(plan.logs.length, 2);
  assert.equal(plan.newRecords[0].現在ステージ, "電話済み");
});

test("見出しの言い換え(企業名・TEL・DM送付日)を受け付ける", () => {
  const plan = h.planHistoryImport(["企業名", "TEL", "DM送付日"], [["株式会社テスト建設", "098-111-2222", "2026年9月10日"]], existing(), [], OPTS);
  assert.equal(plan.summary.matched, 1);
  assert.equal(plan.logs[0].日付, "2026-09-10");
});

test("日付が読めない行・空行は取り込まず、理由を返す", () => {
  const plan = h.planHistoryImport(HEADER, [["株式会社テスト建設", "", "未定", "", "", ""], ["", "", "", "", "", ""]], existing(), [], OPTS);
  assert.equal(plan.logs.length, 0);
  assert.equal(plan.skipped.length, 1);
  assert.equal(plan.skipped[0].line, 2);
});

test("会社名も電話番号の列も無い表は、エラーを返して何もしない", () => {
  const plan = h.planHistoryImport(["メモ"], [["x"]], existing(), [], OPTS);
  assert.ok(plan.error);
});

test("対応履歴の種別は台帳の語彙(INTERACTION_TYPES)に含まれる", () => {
  const schema = require("../glow-ma/src/schema.js");
  const plan = h.planHistoryImport(HEADER, [["株式会社テスト建設", "", "2026-09-10", "2026-09-11", "", ""]], existing(), [], OPTS);
  plan.logs.forEach((l) => assert.ok(schema.INTERACTION_TYPES.includes(l.種別), l.種別));
  Object.keys(plan.logs[0]).forEach((k) => assert.ok(schema.INTERACTION_LOG_HEADERS.includes(k), k));
});

test("Date型の日付(シートから読んだ値)も扱える", () => {
  assert.equal(h.toDateString(new Date(2026, 8, 7)), "2026-09-07");
});

test("年の無い日付(9月18日・9/24)は、取り込み日以前で一番近い年として読む", () => {
  assert.equal(h.toDateString("9月18日", "2026-10-28"), "2026-09-18");
  assert.equal(h.toDateString("9/24", "2026-10-28"), "2026-09-24");
  assert.equal(h.toDateString("12月20日", "2026-10-28"), "2025-12-20");
  assert.equal(h.toDateString("９月１８日", "2026-10-28"), "2026-09-18");
  assert.equal(h.toDateString("9月18日"), "", "基準日が無ければ年を推測しない");
  assert.equal(h.toDateString("13月1日", "2026-10-28"), "");
  assert.equal(h.toDateString("2026/09/10", "2026-10-28"), "2026-09-10");
});

test("年の無い日付の表(福田さんの手紙100通分の形)も、履歴として取り込める", () => {
  const header = ["会社名", "電話番号", "手紙送付日", "架電日", "通話結果", "所在地", "代表者名", "業種", "備考"];
  const plan = h.planHistoryImport(header, [["株式会社テスト建設", "098-111-2222", "9月18日", "9月24日", "担当不在", "", "", "", ""]],
    existing(), [], { today: "2026-10-28", nextSequence: 3213, staffName: "" });
  assert.equal(plan.skipped.length, 0);
  assert.deepEqual(plan.logs.map((l) => [l.日付, l.種別]), [["2026-09-18", "手紙送付"], ["2026-09-24", "電話"]]);
  assert.ok(plan.logs[1].内容メモ.includes("担当不在"));
});

test("通話結果が「入電」「面談」なら、対応履歴の種別を入電・面談実施にして、備考を内容として残す", () => {
  const header = ["会社名", "電話番号", "手紙送付日", "架電日", "通話結果", "所在地", "代表者名", "業種", "備考"];
  const plan = h.planHistoryImport(header, [
    ["株式会社テスト建設", "", "", "10/15", "入電", "", "", "", "土地の件で相談希望"],
    ["株式会社みらい商事", "", "", "10/29", "面談", "", "", "", "後継者の件を聞いた。次は11月に決算書"]
  ], existing(), [], { today: "2026-10-30", nextSequence: 3213, staffName: "" });
  assert.deepEqual(plan.logs.map((l) => l.種別), ["入電", "面談実施"]);
  assert.ok(plan.logs[0].内容メモ.includes("土地の件で相談希望"));
  assert.ok(plan.logs[1].内容メモ.includes("次は11月に決算書"));
  assert.equal(plan.newRecords[0].会社名, "株式会社みらい商事");
  assert.equal(plan.newRecords[0].現在ステージ, "相談実施");
  const schema = require("../glow-ma/src/schema.js");
  plan.logs.forEach((l) => assert.ok(schema.INTERACTION_TYPES.includes(l.種別), l.種別));
});

test("見出しが「面談日」でも日付として読む", () => {
  const plan = h.planHistoryImport(["会社名", "面談日", "通話結果", "備考"],
    [["株式会社テスト建設", "2026-10-29", "訪問", "社長と面談"]], existing(), [], OPTS);
  assert.equal(plan.logs.length, 1);
  assert.equal(plan.logs[0].種別, "面談実施");
});

test("取込済の表は、標準の見出しの順にそろえ、空行を除いて1枚へまとめる形にする", () => {
  const rows = h.toArchiveRows(["電話番号", "企業名", "架電日"], [["098-111-2222", "株式会社テスト建設", "10/1"], ["", "", ""]], "2026-10-30 09:35");
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0], ["2026-10-30 09:35", "株式会社テスト建設", "098-111-2222", "", "10/1", "", "", "", "", "", ""]);
  assert.equal(h.ARCHIVE_FIELDS.length + 1, rows[0].length);
});

test("メール送信日の列があれば、対応履歴に「メール送信」として残す(手紙をやめてメールで案内するようになった)", () => {
  const header = ["会社名", "電話番号", "手紙送付日", "架電日", "通話結果", "所在地", "代表者名", "業種", "備考", "メール送信日"];
  const plan = h.planHistoryImport(header, [
    ["株式会社テスト建設", "", "", "", "", "", "", "", "補助金の案内", "10/28"],
    ["株式会社テスト建設", "", "", "", "", "", "", "", "", "10/30"]
  ], existing(), [], { today: "2026-10-30", nextSequence: 3213, staffName: "" });
  assert.equal(plan.skipped.length, 0);
  assert.deepEqual(plan.logs.map((l) => [l.日付, l.種別]), [["2026-10-28", "メール送信"], ["2026-10-30", "メール送信"]]);
  assert.ok(plan.logs[0].内容メモ.includes("補助金の案内"));
  const schema = require("../glow-ma/src/schema.js");
  plan.logs.forEach((l) => assert.ok(schema.INTERACTION_TYPES.includes(l.種別), l.種別));
  assert.equal(h.ARCHIVE_FIELDS[h.ARCHIVE_FIELDS.length - 1], "メール送信日", "列は末尾に足す");
});

test("取り込み時刻は毎日8時と22時(日本時間)。時刻をまたぐと値が変わる", () => {
  const jst = (s) => Date.parse(s + "+09:00");
  assert.equal(h.currentImportSlot(jst("2026-10-30T07:59:00")), "2026-10-29 22");
  assert.equal(h.currentImportSlot(jst("2026-10-30T08:00:00")), "2026-10-30 08");
  assert.equal(h.currentImportSlot(jst("2026-10-30T21:59:00")), "2026-10-30 08");
  assert.equal(h.currentImportSlot(jst("2026-10-30T22:00:00")), "2026-10-30 22");
  assert.equal(h.currentImportSlot(jst("2026-10-31T00:30:00")), "2026-10-30 22");
  assert.equal(h.currentImportSlot(jst("2026-11-01T03:00:00")), "2026-10-31 22", "月またぎ");
});
