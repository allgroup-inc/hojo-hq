import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const core = require("../apo-kanri/src/apoCore.js");

function apo(overrides) {
  return Object.assign({
    "アポID": "APO-20260814-0001",
    "日付": "2026-08-14",
    "開始時刻": "10:00",
    "所要分": 60,
    "顧客名": "テスト商店",
    "形式": "訪問",
    "場所またはURL": "那覇市",
    "担当営業": "営業一郎",
    "アポ入れ担当": "アポ花子",
    "温度感": "高",
    "ステータス": "スケジュール調整中",
    "メモ": ""
  }, overrides || {});
}

test("generateApoId: APO-yyyymmdd-XXXX 形式で採番される", () => {
  const id = core.generateApoId(new Date(2026, 7, 14, 9, 30), () => 0.5);
  assert.match(id, /^APO-20260814-[A-Z0-9]{4}$/);
});

test("normalizeDateString: Dateも文字列も yyyy-MM-dd に正規化する", () => {
  assert.equal(core.normalizeDateString(new Date(2026, 7, 5)), "2026-08-05");
  assert.equal(core.normalizeDateString("2026-08-14"), "2026-08-14");
  assert.equal(core.normalizeDateString(""), "");
  assert.equal(core.normalizeDateString(null), "");
});

test("normalizeTimeString: Dateも文字列も HH:mm に正規化する", () => {
  assert.equal(core.normalizeTimeString(new Date(1899, 11, 30, 9, 5)), "09:05");
  assert.equal(core.normalizeTimeString("14:30"), "14:30");
  assert.equal(core.normalizeTimeString("9:05"), "09:05");
  assert.equal(core.normalizeTimeString(""), "");
});

test("sortAppointments: 日付→開始時刻→顧客名の昇順", () => {
  const list = [
    apo({ "アポID": "c", "日付": "2026-08-15", "開始時刻": "09:00" }),
    apo({ "アポID": "b", "日付": "2026-08-14", "開始時刻": "13:00" }),
    apo({ "アポID": "a", "日付": "2026-08-14", "開始時刻": "09:00" })
  ];
  assert.deepEqual(core.sortAppointments(list).map((a) => a["アポID"]), ["a", "b", "c"]);
});

test("buildDayView: 指定日のみ・時刻順・サマリー付き(未確定=予定/スケジュール調整中)", () => {
  const list = [
    apo({ "アポID": "a", "開始時刻": "13:00", "ステータス": "アポ確定" }),
    apo({ "アポID": "b", "開始時刻": "09:00", "ステータス": "スケジュール調整中" }),
    apo({ "アポID": "c", "日付": "2026-08-15" }),
    apo({ "アポID": "d", "開始時刻": "11:00", "ステータス": "スケジュール調整中" })
  ];
  const view = core.buildDayView(list, "2026-08-14", null);
  assert.deepEqual(view.items.map((a) => a["アポID"]), ["b", "d", "a"]);
  assert.deepEqual(view.summary, { total: 3, unconfirmed: 2 });
});

test("buildDayView: 担当営業で絞り込める", () => {
  const list = [
    apo({ "アポID": "a", "担当営業": "営業一郎" }),
    apo({ "アポID": "b", "担当営業": "両方次郎" })
  ];
  const view = core.buildDayView(list, "2026-08-14", "両方次郎");
  assert.deepEqual(view.items.map((a) => a["アポID"]), ["b"]);
});

test("buildDayView: 日付のない壊れた行はスキップして落ちない", () => {
  const list = [apo({ "アポID": "a" }), apo({ "アポID": "broken", "日付": null })];
  const view = core.buildDayView(list, "2026-08-14", null);
  assert.deepEqual(view.items.map((a) => a["アポID"]), ["a"]);
});

test("buildWeekView: 開始日から7日分を日別に返す(空日も含む)", () => {
  const list = [
    apo({ "アポID": "a", "日付": "2026-08-14" }),
    apo({ "アポID": "b", "日付": "2026-08-16" }),
    apo({ "アポID": "out", "日付": "2026-08-21" })
  ];
  const week = core.buildWeekView(list, "2026-08-14");
  assert.equal(week.length, 7);
  assert.equal(week[0].date, "2026-08-14");
  assert.equal(week[6].date, "2026-08-20");
  assert.deepEqual(week[0].items.map((a) => a["アポID"]), ["a"]);
  assert.deepEqual(week[2].items.map((a) => a["アポID"]), ["b"]);
  assert.deepEqual(week[1].items, []);
});

test("detectOverlap: 同一営業・同日・時間帯交差だけを検知する", () => {
  const list = [
    apo({ "アポID": "a", "開始時刻": "10:00", "所要分": 60 }),
    apo({ "アポID": "b", "開始時刻": "12:00", "所要分": 60 }),
    apo({ "アポID": "other", "開始時刻": "10:00", "担当営業": "両方次郎" })
  ];
  const candidate = apo({ "アポID": "new", "開始時刻": "10:30", "所要分": 60 });
  assert.deepEqual(core.detectOverlap(list, candidate).map((a) => a["アポID"]), ["a"]);
});

test("detectOverlap: 隣接(10:00-11:00と11:00-12:00)は重複ではない", () => {
  const list = [apo({ "アポID": "a", "開始時刻": "10:00", "所要分": 60 })];
  const candidate = apo({ "アポID": "new", "開始時刻": "11:00", "所要分": 60 });
  assert.deepEqual(core.detectOverlap(list, candidate), []);
});

test("detectOverlap: 差し戻し・対象外は対象外、自分自身も除外(編集時)", () => {
  const list = [
    apo({ "アポID": "a", "ステータス": "差し戻し" }),
    apo({ "アポID": "b", "ステータス": "対象外" }),
    apo({ "アポID": "self" })
  ];
  const candidate = apo({ "アポID": "self" });
  assert.deepEqual(core.detectOverlap(list, candidate), []);
});

/* 旧「再調整中」は枠が空く扱いだったが、共通語彙への移行で「スケジュール調整中」に
   統合され、枠を押さえる側になった(2026-08-21 軸の裁定)。調整の途中で他アポに枠を
   取られると調整そのものが破綻するため。流れたときは差し戻しにして明示的に空ける */
test("detectOverlap: スケジュール調整中は枠を押さえている(重複として検知する)", () => {
  const list = [apo({ "アポID": "a", "ステータス": "スケジュール調整中" })];
  const candidate = apo({ "アポID": "new" });
  assert.deepEqual(core.detectOverlap(list, candidate).map((a) => a["アポID"]), ["a"]);
});

test("buildDelayTargets: 同一営業の同日・指定時刻以降だけを時刻順で返す", () => {
  const list = [
    apo({ "アポID": "past", "開始時刻": "09:00" }),
    apo({ "アポID": "b", "開始時刻": "16:00" }),
    apo({ "アポID": "a", "開始時刻": "14:00" }),
    apo({ "アポID": "cancelled", "開始時刻": "15:00", "ステータス": "差し戻し" }),
    apo({ "アポID": "other", "開始時刻": "15:00", "担当営業": "両方次郎" })
  ];
  const targets = core.buildDelayTargets(list, "営業一郎", "2026-08-14", "13:00");
  assert.deepEqual(targets.map((a) => a["アポID"]), ["a", "b"]);
});

test("buildChangeDiff: 変更列だけを 旧→新 形式でまとめる。差分なしは空文字", () => {
  const oldRecord = apo({});
  const newRecord = apo({ "開始時刻": "14:00", "ステータス": "アポ確定" });
  const diff = core.buildChangeDiff(oldRecord, newRecord);
  assert.equal(diff, "開始時刻: 10:00→14:00 / ステータス: スケジュール調整中→アポ確定");
  assert.equal(core.buildChangeDiff(oldRecord, apo({})), "");
});

test("buildChangeDiff: スキーマ外のキー(confirmedOverlap等の内部フラグ)は差分に漏れない", () => {
  const oldRecord = apo({});
  const newRecord = apo({});
  newRecord.confirmedOverlap = true;
  newRecord.somethingElse = "x";
  assert.equal(core.buildChangeDiff(oldRecord, newRecord), "");
});

test("buildChangeDiff: 登録日時・最終更新日時は差分に含めない", () => {
  const oldRecord = apo({ "登録日時": "x", "最終更新日時": "x" });
  const newRecord = apo({ "登録日時": "y", "最終更新日時": "y" });
  assert.equal(core.buildChangeDiff(oldRecord, newRecord), "");
});

/* ---- 今日やること(要対応の浮上)・埋まっていない訪問枠 ----
 * 新しい入力を1つも増やさず、既存の列だけから導けることを固定する。
 * 「放置されているものが自動で浮上する」が5システム共通の前提【4】。
 */

const TODAY = "2026-08-14";
const attn = (list, options) =>
  core.buildAttentionList(list, Object.assign({ today: TODAY, now: "12:00" }, options));

test("buildAttentionList: 訪問時間が終わって猶予も過ぎたのに結果が入っていないアポを最優先で出す", () => {
  const list = [
    apo({ "アポID": "done", "開始時刻": "09:00", "所要分": 60, "ステータス": "訪問済" }),
    apo({ "アポID": "pending", "開始時刻": "09:00", "所要分": 60, "担当営業": "営業二郎", "ステータス": "アポ確定" }),
    apo({ "アポID": "soon", "開始時刻": "11:30", "所要分": 60, "ステータス": "アポ確定" })
  ];
  const items = attn(list);
  assert.deepEqual(items.map((i) => i.apo["アポID"]), ["pending"]);
  assert.equal(items[0].kind, "result");
});

test("buildAttentionList: 猶予中(終了直後)はまだ出さない。押させるのは一息ついてから", () => {
  const list = [apo({ "アポID": "justEnded", "開始時刻": "10:00", "所要分": 60, "ステータス": "アポ確定" })];
  assert.equal(attn(list, { now: "11:10" }).length, 0);
  assert.equal(attn(list, { now: "12:31" })[0].kind, "result");
});

test("buildAttentionList: 過去のアポも結果待ちとして出るが、さかのぼりすぎない(古すぎる分は出さない)", () => {
  const list = [
    apo({ "アポID": "yesterday", "日付": "2026-08-13", "ステータス": "アポ確定" }),
    apo({ "アポID": "ancient", "日付": "2026-06-01", "ステータス": "アポ確定" })
  ];
  assert.deepEqual(attn(list).map((i) => i.apo["アポID"]), ["yesterday"]);
});

test("buildAttentionList: 差し戻し・対象外は手当て不要なので出さない", () => {
  const list = [
    apo({ "アポID": "a", "日付": "2026-08-13", "ステータス": "差し戻し" }),
    apo({ "アポID": "b", "日付": "2026-08-13", "ステータス": "対象外" })
  ];
  assert.deepEqual(attn(list), []);
});

test("buildAttentionList: 訪問日が迫っているのに未確定・行き先が空のアポを出す", () => {
  const list = [
    apo({ "アポID": "unconf", "日付": "2026-08-15", "開始時刻": "10:00", "ステータス": "スケジュール調整中" }),
    apo({ "アポID": "noplace", "日付": "2026-08-15", "開始時刻": "13:00", "場所またはURL": "", "ステータス": "アポ確定" }),
    apo({ "アポID": "online", "日付": "2026-08-15", "開始時刻": "15:00", "形式": "オンライン", "場所またはURL": "", "ステータス": "アポ確定" }),
    apo({ "アポID": "faraway", "日付": "2026-08-31", "ステータス": "スケジュール調整中" })
  ];
  const items = attn(list);
  // オンラインは行き先が要らない。遠い先の未確定は毎日出続けると見なくなるので射程外
  assert.deepEqual(items.map((i) => i.apo["アポID"]), ["unconf", "noplace"]);
  assert.deepEqual(items.map((i) => i.kind), ["unconfirmed", "place"]);
});

test("buildAttentionList: 担当営業が空なら通知が誰にも届かないので出す", () => {
  const list = [apo({ "アポID": "x", "日付": "2026-08-15", "担当営業": "", "ステータス": "アポ確定" })];
  const items = attn(list);
  assert.equal(items[0].kind, "owner");
  assert.ok(items[0].reason.includes("誰にも"));
});

test("buildAttentionList: 時間の重なりは1組につき1回だけ出す(同じ組を2行にしない)", () => {
  const list = [
    apo({ "アポID": "a", "日付": "2026-08-15", "開始時刻": "10:00", "所要分": 60, "ステータス": "アポ確定" }),
    apo({ "アポID": "b", "日付": "2026-08-15", "開始時刻": "10:30", "所要分": 60, "ステータス": "アポ確定" })
  ];
  const overlaps = attn(list).filter((i) => i.kind === "overlap");
  assert.equal(overlaps.length, 1);
});

test("buildAttentionList: 担当営業で絞り込める(自分の分だけ見る)", () => {
  const list = [
    apo({ "アポID": "mine", "開始時刻": "09:00", "ステータス": "アポ確定" }),
    apo({ "アポID": "other", "開始時刻": "09:00", "担当営業": "営業二郎", "ステータス": "アポ確定" })
  ];
  assert.deepEqual(attn(list, { owner: "営業一郎" }).map((i) => i.apo["アポID"]), ["mine"]);
});

test("buildOpenSlots: 営業時間の中の空き時間を営業ごとに返す(前後の端も含む)", () => {
  const list = [apo({ "担当営業": "営業一郎", "開始時刻": "10:00", "所要分": 60, "ステータス": "アポ確定" })];
  const days = core.buildOpenSlots(list, TODAY, ["営業一郎"], { days: 1, minGapMinutes: 60 });
  assert.equal(days.length, 1);
  assert.deepEqual(days[0].slots.map((s) => s.from + "-" + s.to), ["09:00-10:00", "11:00-18:00"]);
});

test("buildOpenSlots: 短すぎる隙間は空きとして出さない(移動も入らない時間を勧めない)", () => {
  const list = [
    apo({ "担当営業": "営業一郎", "開始時刻": "09:00", "所要分": 60, "ステータス": "アポ確定" }),
    apo({ "担当営業": "営業一郎", "開始時刻": "10:30", "所要分": 450, "ステータス": "アポ確定" })
  ];
  const days = core.buildOpenSlots(list, TODAY, ["営業一郎"], { days: 1, minGapMinutes: 90 });
  assert.deepEqual(days[0].slots, []);
});

test("buildOpenSlots: 差し戻し・対象外の枠は空きとして出す(枠が空いた=入れられる)", () => {
  const list = [apo({ "担当営業": "営業一郎", "開始時刻": "10:00", "所要分": 60, "ステータス": "差し戻し" })];
  const days = core.buildOpenSlots(list, TODAY, ["営業一郎"], { days: 1, minGapMinutes: 60 });
  assert.deepEqual(days[0].slots.map((s) => s.from + "-" + s.to), ["09:00-18:00"]);
});

test("buildOpenSlots: アポが重なっていても空きを二重に数えない", () => {
  const list = [
    apo({ "担当営業": "営業一郎", "開始時刻": "10:00", "所要分": 120, "ステータス": "アポ確定" }),
    apo({ "担当営業": "営業一郎", "開始時刻": "10:30", "所要分": 60, "ステータス": "アポ確定" })
  ];
  const days = core.buildOpenSlots(list, TODAY, ["営業一郎"], { days: 1, minGapMinutes: 60 });
  assert.deepEqual(days[0].slots.map((s) => s.from + "-" + s.to), ["09:00-10:00", "12:00-18:00"]);
});

test("buildAttentionList: すでに始まった時間の重なりは出さない(直しようがないものを並べない)", () => {
  const past = [
    apo({ "アポID": "a", "開始時刻": "09:00", "所要分": 60, "ステータス": "訪問済" }),
    apo({ "アポID": "b", "開始時刻": "09:30", "所要分": 60, "ステータス": "訪問済" })
  ];
  assert.deepEqual(attn(past, { now: "12:00" }).filter((i) => i.kind === "overlap"), []);
  // まだ始まっていない重なりは出す
  assert.equal(attn(past, { now: "08:00" }).filter((i) => i.kind === "overlap").length, 1);
});
