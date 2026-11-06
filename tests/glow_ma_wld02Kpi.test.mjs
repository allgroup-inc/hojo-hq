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

// ---- 2026-11-06 §9・§9-7: 問い合わせ・割合・目標までの残り、足りなかったテスト5つ(すべて合成データ) ----
const WORLD = "④世界の架け橋(Alibaba)";

test("問い合わせ企業数: 流入ルート④の会社で、入電・返信・資料請求・面談実施がある会社を1社ずつ数える", () => {
  const companies = [
    { 企業ID: "C900001", 流入ルート: WORLD },
    { 企業ID: "C900002", 流入ルート: WORLD },
    { 企業ID: "C900003", 流入ルート: "②手紙DM" }, // ④でない → 数えない
    { 企業ID: "C900004", 流入ルート: WORLD },
    { 企業ID: "C900005", 流入ルート: WORLD },
  ];
  const history = [
    { 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-10-20", 種別: "入電" },
    { 履歴ID: "H2", 企業ID: "C900001", 日付: "2026-11-03", 種別: "資料請求" }, // 同じ会社の2回目
    { 履歴ID: "H3", 企業ID: "C900002", 日付: "2026-11-04", 種別: "返信" },
    { 履歴ID: "H4", 企業ID: "C900003", 日付: "2026-11-04", 種別: "入電" },
    { 履歴ID: "H5", 企業ID: "C900004", 日付: "2026-10-01", 種別: "入電" }, // 10/4より前 → 数えない
    { 履歴ID: "H6", 企業ID: "C900005", 日付: "2026-11-04", 種別: "手紙送付" }, // 問い合わせの種別でない
  ];
  const { row } = run(sources({ companies, history }));
  assert.equal(row.問い合わせ企業数_累計, 2);
  assert.equal(row.問い合わせ企業数_週内の新規, 1); // C900002(C900001の最初は10/20)
});

test("問い合わせ: 統合前の企業IDに④が付いていても、統合後の会社として1社に数える", () => {
  const companies = [{ 企業ID: "C900001", 流入ルート: WORLD }, { 企業ID: "C900002", 流入ルート: "" }];
  const idMap = [{ 旧企業ID: "C900001", 統合後の企業ID: "C900002" }];
  const history = [
    { 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-11-03", 種別: "入電" },
    { 履歴ID: "H2", 企業ID: "C900002", 日付: "2026-11-04", 種別: "返信" },
  ];
  const { row } = run(sources({ companies, history, idMap }));
  assert.equal(row.問い合わせ企業数_累計, 1);
});

test("割合は、母数が10社より少なければ出さない(「—」)。10社以上なら%で小数1桁", () => {
  assert.equal(k.ratio(3, 9), "—");
  assert.equal(k.ratio(0, 0), "—");
  assert.equal(k.ratio(3, 10), 30);
  assert.equal(k.ratio(1, 3 * 10 + 0), 3.3);
  assert.equal(k.RATIO_MIN_BASE, 10);
});

test("週次の行に、問い合わせ→相談・相談→掲載契約の割合が入る(母数が足りなければ「—」)", () => {
  const ids = Array.from({ length: 12 }, (_, i) => "C9100" + String(i + 10));
  const companies = ids.map((id) => ({ 企業ID: id, 流入ルート: WORLD }));
  const history = ids.map((id, i) => ({ 履歴ID: "H" + i, 企業ID: id, 日付: "2026-10-20", 種別: "入電" }));
  const confirmations = ids.slice(0, 3).map((id) => confirm({ 企業ID: id, 面談日: "2026-10-25" }));
  const { row } = run(sources({ companies, history, confirmations }));
  assert.equal(row.問い合わせ企業数_累計, 12);
  assert.equal(row.相談企業数_累計, 3);
  assert.equal(row.問い合わせから相談の割合, 25);
  assert.equal(row.相談から掲載契約の割合, "—"); // 相談が10社未満
});

test("目標までの残り: 100社までの残り・目標日までの週数・1週あたりに必要な相談数", () => {
  // 2026-11-02の週 → 週の終わり 11-09。11-09〜2027-04-04 は147日 → 21週
  assert.deepEqual(k.goalPace(0, "2026-11-09"), { remaining: 100, weeks: 21, perWeek: 5 });
  assert.deepEqual(k.goalPace(37, "2026-11-09"), { remaining: 63, weeks: 21, perWeek: 3 });
  assert.deepEqual(k.goalPace(100, "2026-11-09"), { remaining: 0, weeks: 21, perWeek: 0 });
  assert.deepEqual(k.goalPace(120, "2027-05-03"), { remaining: 0, weeks: 0, perWeek: 0 });
  assert.deepEqual(k.goalPace(80, "2027-05-03"), { remaining: 20, weeks: 0, perWeek: "—" }); // 目標日を過ぎた
  const { row } = run(sources());
  assert.equal(row.目標までの残り社数, 100);
  assert.equal(row.目標日までの残り週数, 21);
  assert.equal(row.必要な週あたりの相談数, 5);
});

test("[不足1] 契約成立日が空の行(申込の予定・見込み)は、掲載契約に数えない", () => {
  const contracts = [
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "", 状態: "有効" },
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-20", 状態: "有効" },
  ];
  const { row } = run(sources({ contracts }));
  assert.equal(row.掲載契約企業数_累計, 1);
  assert.equal(row.掲載契約企業数_有効, 1);
});

test("[不足2] 掲載契約の今の状態は、行の順番ではなく「状態が変わった日」で決める", () => {
  const contracts = [
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "解除", 状態が変わった日: "2026-10-30" },
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "有効", 状態が変わった日: "2026-10-10" }, // 後の行だが古い
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-12", 状態: "解除", 状態が変わった日: "2026-10-15" },
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-12", 状態: "有効", 状態が変わった日: "2026-10-20" }, // 再開
  ];
  const { row } = run(sources({ contracts }));
  assert.equal(row.掲載契約企業数_累計, 2);
  assert.equal(row.掲載契約企業数_有効, 1); // C900002 だけ
});

test("[不足3] 面談日が日時(Date)のときは日本時間の日付で週を決める(0時前後)", () => {
  assert.equal(k.toDate(new Date("2026-11-08T15:30:00Z")), "2026-11-09"); // 日本時間 11/9(月) 0:30
  assert.equal(k.toDate(new Date("2026-11-08T14:30:00Z")), "2026-11-08"); // 日本時間 11/8(日) 23:30
  const late = confirm({ 面談日: new Date("2026-11-08T15:30:00Z") });
  assert.equal(run(sources({ confirmations: [late] })).row.相談企業数_累計, 0); // 11/2の週には入らない
  assert.equal(run(sources({ confirmations: [late] }), "2026-11-09").row.相談企業数_週内の新規, 1);
  const sunday = confirm({ 面談日: new Date("2026-11-08T14:30:00Z") });
  assert.equal(run(sources({ confirmations: [sunday] })).row.相談企業数_週内の新規, 1);
});

test("[不足4] 同じ面談に確認記録が複数あっても1回(取り消してから確認し直した場合も含む)", () => {
  const confirmations = [
    confirm({ 確認ID: "K1", 元の履歴ID: "H1", 確認日時: "2026-11-03 10:00", 取消: true }),
    confirm({ 確認ID: "K2", 元の履歴ID: "H1", 確認日時: "2026-11-03 11:00" }),
    confirm({ 確認ID: "K3", 元の履歴ID: "H1", 確認日時: "2026-11-03 12:00" }),
  ];
  const history = [{ 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-11-03", 種別: "面談実施" }];
  const { row } = run(sources({ confirmations, history }));
  assert.equal(row.相談企業数_累計, 1);
  assert.equal(row.確認待ちの面談数, 0);
  assert.equal(k.effectiveConfirmations(confirmations).length, 1);
});

test("[不足5] 判定をやり直したときは新しい判定を正とする(対象外→確認済み、確認済み→対象外)", () => {
  const history = [
    { 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-11-03", 種別: "面談実施" },
    { 履歴ID: "H2", 企業ID: "C900002", 日付: "2026-11-03", 種別: "面談実施" },
  ];
  const confirmations = [
    confirm({ 確認ID: "K1", 企業ID: "C900001", 元の履歴ID: "H1", 判定: "対象外", 確認日時: "2026-11-03 10:00" }),
    confirm({ 確認ID: "K2", 企業ID: "C900001", 元の履歴ID: "H1", 判定: "確認済み", 確認日時: "2026-11-04 10:00" }),
    confirm({ 確認ID: "K3", 企業ID: "C900002", 元の履歴ID: "H2", 判定: "確認済み", 確認日時: "2026-11-03 10:00" }),
    confirm({ 確認ID: "K4", 企業ID: "C900002", 元の履歴ID: "H2", 判定: "対象外", 確認日時: "2026-11-04 10:00" }),
  ];
  const { row } = run(sources({ confirmations, history }));
  assert.equal(row.相談企業数_累計, 1); // C900001 だけ
  assert.equal(row.確認待ちの面談数, 0); // どちらも判定済み
});

test("新しい列は週次KPIの末尾に足し、これまでの列の並びを変えない", () => {
  assert.deepEqual(k.WEEKLY_FIELDS.slice(0, 10), [
    "週の開始日", "集計日時", "状態", "相談企業数_累計", "相談企業数_週内の新規",
    "掲載契約企業数_累計", "掲載契約企業数_有効", "掲載契約企業数_参考_10月4日より前",
    "確認待ちの面談数", "流入経路の要確認数",
  ]);
  assert.equal(k.WEEKLY_FIELDS.length, 20);
});

// ---- 2026-11-06 PR #590 レビュー対応: 割合の母集団・取消の扱い・日付と契約の順序(すべて合成データ) ----

test("割合は同じ会社の集まりで数える: 問い合わせ企業のうち相談した会社/相談企業のうち契約した会社(100%を超えない)", () => {
  const inq = Array.from({ length: 12 }, (_, i) => "C9200" + String(i + 10)); // ④で問い合わせのある12社
  const other = Array.from({ length: 13 }, (_, i) => "C9300" + String(i + 10)); // ①紹介など、問い合わせの記録が無い13社
  const companies = inq.map((id) => ({ 企業ID: id, 流入ルート: WORLD }))
    .concat(other.map((id) => ({ 企業ID: id, 流入ルート: "①紹介" })));
  const history = inq.map((id, i) => ({ 履歴ID: "H" + i, 企業ID: id, 日付: "2026-10-20", 種別: "入電" }));
  // 相談は 問い合わせ企業から2社 + それ以外から13社 = 15社(正式KPIは全ルートで15社のまま)
  const confirmations = inq.slice(0, 2).concat(other).map((id) => confirm({ 企業ID: id, 面談日: "2026-10-25" }));
  // 契約は 相談した会社から3社 + 相談していない会社から5社
  const signed = other.slice(0, 3).concat(inq.slice(5, 10));
  const contracts = signed.map((id, i) => ({ 契約ID: "P" + i, 企業ID: id, 契約成立日: "2026-10-28", 状態: "有効" }));
  const { row } = run(sources({ companies, history, confirmations, contracts }));
  assert.equal(row.相談企業数_累計, 15);
  assert.equal(row.問い合わせ企業数_累計, 12);
  assert.equal(row.問い合わせ企業のうち相談企業数, 2);
  assert.equal(row.問い合わせから相談の割合, 16.7); // 2/12(以前の数え方なら 15/12 = 125%)
  assert.equal(row.掲載契約企業数_累計, 8);
  assert.equal(row.相談企業のうち掲載契約企業数, 3);
  assert.equal(row.相談から掲載契約の割合, 20); // 3/15(以前の数え方なら 8/15)
});

test("割合は、どんな組み合わせでも0〜100%に収まり、分子は分母を超えない(合成データ200通り)", () => {
  let seed = 20261106;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  for (let t = 0; t < 200; t++) {
    const ids = Array.from({ length: 30 }, (_, i) => "C94" + String(1000 + i));
    const companies = ids.map((id) => ({ 企業ID: id, 流入ルート: rnd() < 0.5 ? WORLD : "①紹介" }));
    const history = ids.filter(() => rnd() < 0.6).map((id, i) => ({ 履歴ID: "H" + i, 企業ID: id, 日付: "2026-10-1" + Math.floor(rnd() * 10), 種別: "入電" }));
    const confirmations = ids.filter(() => rnd() < 0.5).map((id) => confirm({ 企業ID: id, 面談日: "2026-10-2" + Math.floor(rnd() * 10) }));
    const contracts = ids.filter(() => rnd() < 0.4).map((id, i) => ({ 契約ID: "P" + i, 企業ID: id, 契約成立日: "2026-10-2" + Math.floor(rnd() * 10), 状態: "有効" }));
    const { row } = run(sources({ companies, history, confirmations, contracts }));
    assert.ok(row.問い合わせ企業のうち相談企業数 <= row.問い合わせ企業数_累計);
    assert.ok(row.相談企業のうち掲載契約企業数 <= row.相談企業数_累計);
    assert.ok(row.相談企業のうち掲載契約企業数 <= row.掲載契約企業数_累計);
    for (const r of [row.問い合わせから相談の割合, row.相談から掲載契約の割合]) {
      assert.ok(r === "—" || (r >= 0 && r <= 100), String(r));
    }
  }
});

test("取消: 新しい判定を取り消しても、古い判定は生き返らない(その面談は確認待ちに戻る)", () => {
  const history = [
    { 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-11-03", 種別: "面談実施" },
    { 履歴ID: "H2", 企業ID: "C900002", 日付: "2026-11-03", 種別: "面談実施" },
  ];
  const confirmations = [
    // H1: 確認済み → 対象外(取消) → 確認済みには戻さない
    confirm({ 確認ID: "K1", 企業ID: "C900001", 元の履歴ID: "H1", 判定: "確認済み", 確認日時: "2026-11-03 10:00" }),
    confirm({ 確認ID: "K2", 企業ID: "C900001", 元の履歴ID: "H1", 判定: "対象外", 確認日時: "2026-11-04 10:00", 取消: "取消" }),
    // H2: 対象外 → 確認済み(取消) → 対象外にも戻さない
    confirm({ 確認ID: "K3", 企業ID: "C900002", 元の履歴ID: "H2", 判定: "対象外", 確認日時: "2026-11-03 10:00" }),
    confirm({ 確認ID: "K4", 企業ID: "C900002", 元の履歴ID: "H2", 判定: "確認済み", 確認日時: "2026-11-04 10:00", 取消: true }),
  ];
  const { row } = run(sources({ confirmations, history }));
  assert.equal(row.相談企業数_累計, 0);
  assert.equal(row.確認待ちの面談数, 2);
  assert.equal(k.effectiveConfirmations(confirmations).length, 0);
});

test("取消のあとに確認し直した行があれば、その新しい判定を正とする(古い行の取消は影響しない)", () => {
  const history = [{ 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-11-03", 種別: "面談実施" }];
  const confirmations = [
    confirm({ 確認ID: "K1", 元の履歴ID: "H1", 判定: "対象外", 確認日時: "2026-11-03 10:00" }),
    confirm({ 確認ID: "K2", 元の履歴ID: "H1", 判定: "確認済み", 確認日時: "2026-11-04 10:00", 取消: true }),
    confirm({ 確認ID: "K3", 元の履歴ID: "H1", 判定: "確認済み", 確認日時: "2026-11-05 09:00" }),
  ];
  const { row } = run(sources({ confirmations, history }));
  assert.equal(row.相談企業数_累計, 1);
  assert.equal(row.確認待ちの面談数, 0);
});

test("取消: 行の並び順ではなく確認日時で新しさを決める(日時が Date でも、書き方が違っても)", () => {
  const history = [{ 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-11-03", 種別: "面談実施" }];
  // 後ろに置いた行のほうが古い。日本時間 11/4 9:05 = UTC 11/4 0:05
  const rows = [
    confirm({ 確認ID: "K2", 元の履歴ID: "H1", 判定: "確認済み", 確認日時: new Date("2026-11-04T00:05:00Z"), 取消: true }),
    confirm({ 確認ID: "K1", 元の履歴ID: "H1", 判定: "確認済み", 確認日時: "2026/11/4 9:00" }),
  ];
  const { row, problems } = run(sources({ confirmations: rows, history }));
  assert.equal(row.相談企業数_累計, 0); // 新しい K2 が取消 → 確認待ち
  assert.equal(row.確認待ちの面談数, 1);
  assert.equal(problems.length, 0);
  assert.equal(k.toStamp("2026/11/4 9:00"), "2026-11-04 09:00:00");
  assert.equal(k.toStamp(new Date("2026-11-04T00:05:00Z")), "2026-11-04 09:05:00");
  assert.equal(k.toStamp("あとで"), "");
});

test("確認日時が読めない行が同じ面談に混ざったら、並び順で決めたことを問題として返す", () => {
  const rows = [
    confirm({ 確認ID: "K1", 元の履歴ID: "H1", 判定: "対象外", 確認日時: "2026-11-03 10:00" }),
    confirm({ 確認ID: "K2", 元の履歴ID: "H1", 判定: "確認済み", 確認日時: "" }),
  ];
  const { problems } = run(sources({ confirmations: rows }));
  assert.ok(problems.some((p) => /確認日時が読めない/.test(p) && p.includes("H1")));
});

test("日付の境界: 集計の開始日(10/4)・週の終わり(次の月曜は含まない)・日本時間の0時", () => {
  const companies = ["C900001", "C900002", "C900003", "C900004"].map((id) => ({ 企業ID: id, 流入ルート: WORLD }));
  const history = [
    { 履歴ID: "H1", 企業ID: "C900001", 日付: "2026-10-03", 種別: "入電" },                       // 開始日の前日 → 数えない
    { 履歴ID: "H2", 企業ID: "C900002", 日付: "2026-10-04", 種別: "入電" },                       // 開始日 → 数える
    { 履歴ID: "H3", 企業ID: "C900003", 日付: new Date("2026-11-08T14:59:00Z"), 種別: "返信" },  // 日 23:59 JST → この週
    { 履歴ID: "H4", 企業ID: "C900004", 日付: new Date("2026-11-08T15:00:00Z"), 種別: "返信" },  // 月 0:00 JST → 次の週
  ];
  const { row } = run(sources({ companies, history }));
  assert.equal(row.問い合わせ企業数_累計, 2); // C900002, C900003
  assert.equal(row.問い合わせ企業数_週内の新規, 1); // C900003
  const next = run(sources({ companies, history }), "2026-11-09").row;
  assert.equal(next.問い合わせ企業数_累計, 3);
  assert.equal(next.問い合わせ企業数_週内の新規, 1); // C900004
});

test("目標日の前後: 目標日(4/4・日)を含む週が最後。その週の集計で残り週数は0", () => {
  assert.deepEqual(k.goalPace(90, "2027-03-29"), { remaining: 10, weeks: 1, perWeek: 10 }); // 3/22の週
  assert.deepEqual(k.goalPace(90, "2027-04-05"), { remaining: 10, weeks: 0, perWeek: "—" }); // 3/29の週(4/4を含む)
  assert.deepEqual(k.goalPace(100, "2027-04-05"), { remaining: 0, weeks: 0, perWeek: 0 });
});

test("契約の順序: 同じ日に2回状態が変わったら後の行。日時がDateでも日本時間の日付で並べる", () => {
  const contracts = [
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "有効", 状態が変わった日: "2026-10-10" },
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "解除", 状態が変わった日: "2026-10-20" },
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "有効", 状態が変わった日: "2026-10-20" }, // 同じ日の後の行
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-12", 状態: "有効", 状態が変わった日: "2026-10-12" },
    // 日本時間 10/21 0:30(UTC 10/20 15:30)の解除は、10/20の有効より後
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-12", 状態: "解除", 状態が変わった日: new Date("2026-10-20T15:30:00Z") },
    { 契約ID: "P2", 企業ID: "C900002", 契約成立日: "2026-10-12", 状態: "有効", 状態が変わった日: "2026-10-20" }, // 後の行だが古い日
  ];
  const { row, problems } = run(sources({ contracts }));
  assert.equal(row.掲載契約企業数_累計, 2);
  assert.equal(row.掲載契約企業数_有効, 1); // C900001 だけ
  assert.equal(problems.length, 0);
});

test("契約の順序: 状態を変えた行に「状態が変わった日」が無ければ、問題として返す", () => {
  const contracts = [
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "有効" }, // 最初の行は無くてよい(成立日で並べる)
    { 契約ID: "P1", 企業ID: "C900001", 契約成立日: "2026-10-10", 状態: "解除" },
  ];
  const { row, problems } = run(sources({ contracts }));
  assert.equal(row.掲載契約企業数_有効, 0); // 同じ日なら後の行
  assert.ok(problems.some((p) => /P1/.test(p) && /状態が変わった日/.test(p)));
});
