// 世界の架け橋 WLD-02 相談企業KPIの集計ロジックのテスト(会社名・IDはすべて架空)
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const k = require("../glow-ma/wld02/wld02Kpi.js");

const W = "世界の架け橋";
const WEEK = "2026-11-02"; // 月曜

function confirm(over) {
  return { 確認ID: "K1", 企業ID: "C900001", 元の履歴ID: "", 面談日: "2026-11-03", 形式: "対面", 事業: W, 判定: "確認済み", 取消: "", ...over };
}

function sources(over) {
  return {
    confirmations: [],
    contracts: [],
    idMap: [],
    history: [],
    companies: [],
    ...over,
  };
}

function run(src, weekStart = WEEK) {
  return k.buildWeeklyRow(src, { weekStart, runAt: "2026-11-09 09:00", runId: "R1" });
}

test("週は月曜始まり(日曜は前の月曜の週)", () => {
  assert.equal(k.weekStartMonday("2026-11-02"), "2026-11-02");
  assert.equal(k.weekStartMonday("2026-11-08"), "2026-11-02"); // 日曜
  assert.equal(k.weekStartMonday("2026-11-09"), "2026-11-09");
  assert.equal(k.weekStartMonday("2026/1/1"), "2025-12-29"); // 年をまたぐ
  assert.equal(k.weekStartMonday("2026-02-30"), ""); // 無い日付
});

test("月曜の集計は、日本時間で前の週を数える", () => {
  // 2026-11-09(月)09:00 JST = 2026-11-09 00:00 UTC
  assert.equal(k.previousWeekStart(Date.UTC(2026, 10, 9, 0, 0)), "2026-11-02");
  // 2026-11-08(日)23:30 UTC は JST では 11-09(月)08:30
  assert.equal(k.previousWeekStart(Date.UTC(2026, 10, 8, 23, 30)), "2026-11-02");
});

test("週の開始日に月曜以外を渡すと止まる", () => {
  assert.throws(() => run(sources(), "2026-11-03"), /月曜日/);
});

test("確認済み・世界の架け橋・対面/オンライン・取消でない・10/4以降だけを数える", () => {
  const rows = [
    confirm({ 企業ID: "C900001" }),
    confirm({ 企業ID: "C900002", 形式: "オンライン" }),
    confirm({ 企業ID: "C900003", 判定: "対象外" }),
    confirm({ 企業ID: "C900004", 事業: "それ以外" }),
    confirm({ 企業ID: "C900005", 形式: "電話" }),
    confirm({ 企業ID: "C900006", 取消: true }),
    confirm({ 企業ID: "C900007", 面談日: "2026-10-03" }),
    confirm({ 企業ID: "C900008", 面談日: "2026-10-04" }),
    confirm({ 企業ID: "C900009", 面談日: "" }),
  ];
  const { row } = run(sources({ confirmations: rows }));
  assert.equal(row.状態, "集計済み");
  assert.equal(row.相談企業数_累計, 3); // C900001, C900002, C900008
  assert.equal(row.相談企業数_週内の新規, 2); // 11/3 の2社
});

test("同じ会社の面談が何回あっても1社。週内の新規は最初の面談日で決める", () => {
  const rows = [
    confirm({ 企業ID: "C900001", 面談日: "2026-10-20" }),
    confirm({ 企業ID: "C900001", 面談日: "2026-11-04" }),
  ];
  const { row } = run(sources({ confirmations: rows }));
  assert.equal(row.相談企業数_累計, 1);
  assert.equal(row.相談企業数_週内の新規, 0);
});

test("集計する週より後の面談は、その週の累計に入れない", () => {
  const { row } = run(sources({ confirmations: [confirm({ 面談日: "2026-11-09" })] }));
  assert.equal(row.相談企業数_累計, 0);
});

test("企業ID対応表で統合後のIDにそろえてから重複を除く(つながりもたどる)", () => {
  const idMap = [
    { 旧企業ID: "C900002", 統合後の企業ID: "C900001" },
    { 旧企業ID: "C900003", 統合後の企業ID: "C900002" },
  ];
  const rows = [confirm({ 企業ID: "C900001" }), confirm({ 企業ID: "C900002" }), confirm({ 企業ID: "C900003" })];
  const { row } = run(sources({ confirmations: rows, idMap }));
  assert.equal(row.相談企業数_累計, 1);
});

test("統合を取り消した行が後にあれば、別の会社として数える", () => {
  const idMap = [
    { 旧企業ID: "C900002", 統合後の企業ID: "C900001" },
    { 旧企業ID: "C900002", 統合後の企業ID: "C900001", 取消: "取消" },
  ];
  const rows = [confirm({ 企業ID: "C900001" }), confirm({ 企業ID: "C900002" })];
  const { row } = run(sources({ confirmations: rows, idMap }));
  assert.equal(row.相談企業数_累計, 2);
});

test("企業ID対応表が輪になっていても止まらず、問題として返す", () => {
  const idMap = [
    { 旧企業ID: "C900001", 統合後の企業ID: "C900002" },
    { 旧企業ID: "C900002", 統合後の企業ID: "C900001" },
  ];
  const { row, problems } = run(sources({ confirmations: [confirm({})], idMap }));
  assert.equal(row.相談企業数_累計, 1);
  assert.ok(problems.some((p) => /輪/.test(p)));
});

test("確認されていない「面談実施」は数えず、確認待ちとして数える(過去分も含む)", () => {
  const history = [
    { 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-09-01", 種別: "面談実施" },
    { 履歴ID: "H2", 企業ID: "C900002", 日付: "2026-11-03", 種別: "面談実施" },
    { 履歴ID: "H3", 企業ID: "C900003", 日付: "2026-11-03", 種別: "電話" },
    { 履歴ID: "H4", 企業ID: "C900004", 日付: "2026-11-03", 種別: "面談実施" },
  ];
  const confirmations = [
    confirm({ 企業ID: "C900002", 元の履歴ID: "H2" }),
    confirm({ 企業ID: "C900004", 元の履歴ID: "H4", 取消: true }), // 取り消された確認 → 確認待ちに戻る
  ];
  const { row } = run(sources({ confirmations, history }));
  assert.equal(row.相談企業数_累計, 1);
  assert.equal(row.確認待ちの面談数, 2); // H1, H4
});

test("「対象外」と判定された面談は確認待ちにしない", () => {
  const history = [{ 履歴ID: "H1", 企業ID: "C900001", 種別: "面談実施" }];
  const confirmations = [confirm({ 元の履歴ID: "H1", 判定: "対象外" })];
  const { row } = run(sources({ confirmations, history }));
  assert.equal(row.確認待ちの面談数, 0);
  assert.equal(row.相談企業数_累計, 0);
});

test("流入経路④が外れても累計に残し、要確認として数える", () => {
  const companies = [
    { 企業ID: "C900001", 流入ルート: "④世界の架け橋(Alibaba)" },
    { 企業ID: "C900002", 流入ルート: "①紹介" },
    { 企業ID: "C900003", 流入ルート: ["②手紙DM", "④世界の架け橋(Alibaba)"] },
  ];
  const rows = ["C900001", "C900002", "C900003"].map((id) => confirm({ 企業ID: id }));
  const { row } = run(sources({ confirmations: rows, companies }));
  assert.equal(row.相談企業数_累計, 3);
  assert.equal(row.流入経路の要確認数, 1);
});

test("掲載契約は解除・取消でも累計に残し、有効な数は別に数える", () => {
  const contracts = [
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "有効" },
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-12", 状態: "有効" },
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-12", 状態: "解除" }, // 後の行が今の状態
    { 契約ID: "P3", 企業ID: "C900003", 契約成立日: "2026-10-15", 状態: "取消" },
    { 契約ID: "P4", 企業ID: "C900004", 契約成立日: "2026-10-15", 状態: "誤登録" },
    { 契約ID: "P5", 企業ID: "C900001", 契約成立日: "2026-10-20", 状態: "有効" }, // 同じ会社の2件目
  ];
  const { row } = run(sources({ contracts }));
  assert.equal(row.掲載契約企業数_累計, 3); // C900001, C900002, C900003
  assert.equal(row.掲載契約企業数_有効, 1); // C900001
});

test("10/4より前の掲載契約は参考実績として別に数え、正式な累計には足さない", () => {
  const contracts = [
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-09-20", 状態: "有効" },
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-03", 状態: "解除" },
    { 契約ID: "P3", 企業ID: "C900003", 契約成立日: "2026-10-04", 状態: "有効" },
    { 契約ID: "P4", 企業ID: "C900004", 契約成立日: "2026-09-01", 状態: "誤登録" },
    // 10/4より前にも後にも契約がある会社は、正式な累計の側だけに数える
    { 契約ID: "P5", 企業ID: "C900005", 契約成立日: "2026-09-10", 状態: "解除" },
    { 契約ID: "P6", 企業ID: "C900005", 契約成立日: "2026-10-15", 状態: "有効" },
  ];
  const { row } = run(sources({ contracts }));
  assert.equal(row.掲載契約企業数_累計, 2); // C900003, C900005
  assert.equal(row.掲載契約企業数_有効, 2);
  assert.equal(row.掲載契約企業数_参考_10月4日より前, 2); // C900001, C900002
});

test("記録が1つでも読めなければ「取得不能」。数字は0ではなく空にする", () => {
  const { row, problems } = run(sources({ contracts: null }));
  assert.equal(row.状態, "取得不能");
  assert.equal(row.相談企業数_累計, "");
  assert.equal(row.掲載契約企業数_累計, "");
  assert.ok(problems[0].includes("contracts"));
  assert.equal(run(undefined).row.状態, "取得不能");
});

test("同じ週の行は上書きし、無ければ足す(再実行で二重に数えない)", () => {
  const existing = [
    { 週の開始日: "2026-10-26", 状態: "集計済み" },
    { 週の開始日: "2026-11-02", 状態: "集計済み" },
  ];
  assert.deepEqual(k.planWeeklyUpsert(existing, { 週の開始日: "2026-11-02", 状態: "集計済み" }), { action: "update", index: 1 });
  assert.deepEqual(k.planWeeklyUpsert(existing, { 週の開始日: "2026-11-09", 状態: "集計済み" }), { action: "append", index: -1 });
});

test("取得不能の行で、集計済みの週を上書きしない(前の値を残す)", () => {
  const existing = [{ 週の開始日: "2026-11-02", 状態: "集計済み" }];
  assert.deepEqual(k.planWeeklyUpsert(existing, { 週の開始日: "2026-11-02", 状態: "取得不能" }), { action: "keep", index: 0 });
  const failed = [{ 週の開始日: "2026-11-02", 状態: "取得不能" }];
  assert.deepEqual(k.planWeeklyUpsert(failed, { 週の開始日: "2026-11-02", 状態: "集計済み" }), { action: "update", index: 0 });
});

test("週次KPIの行は決まった列だけを持つ", () => {
  const { row } = run(sources());
  assert.deepEqual(Object.keys(row), k.WEEKLY_FIELDS);
  assert.equal(row.相談企業数_累計, 0);
});
