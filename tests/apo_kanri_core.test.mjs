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

test("buildDayView: 指定日のみ・時刻順・サマリー付き(未確定=予定/再調整中)", () => {
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

test("detectOverlap: 差し戻し・開始時刻なしは対象外、自分自身も除外(編集時)", () => {
  const list = [
    apo({ "アポID": "a", "ステータス": "差し戻し" }),
    apo({ "アポID": "b", "ステータス": "スケジュール調整中", "開始時刻": "" }),
    apo({ "アポID": "self" })
  ];
  const candidate = apo({ "アポID": "self" });
  assert.deepEqual(core.detectOverlap(list, candidate), []);
});

// 議事_20260821: 共通語彙は❷に2値しか許さないため、旧「予定(枠を押さえる)」と
// 旧「再調整中(押さえない)」の違いは開始時刻の有無で表す。仮日程でも枠は押さえる。
test("detectOverlap: スケジュール調整中でも開始時刻があれば枠を押さえる", () => {
  const list = [apo({ "アポID": "kari", "ステータス": "スケジュール調整中" })];
  const found = core.detectOverlap(list, apo({ "アポID": "new" }));
  assert.deepEqual(found.map((a) => a["アポID"]), ["kari"]);
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
