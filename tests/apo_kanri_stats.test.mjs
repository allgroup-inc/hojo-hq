import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const core = require("../apo-kanri/src/apoCore.js");

function apo(overrides) {
  return Object.assign({
    "アポID": "APO-X",
    "日付": "2026-08-14",
    "開始時刻": "10:00",
    "所要分": 60,
    "顧客名": "テスト商店",
    "担当営業": "営業一郎",
    "アポ入れ担当": "アポ花子",
    "ステータス": "スケジュール調整中"
  }, overrides || {});
}

test("buildFillStats: 営業別の予約済み分数・件数・埋まり率を返す(アポゼロの営業も0で出る)", () => {
  const list = [
    apo({ "所要分": 60, "ステータス": "アポ確定" }),
    apo({ "所要分": 90, "ステータス": "スケジュール調整中" }),
    apo({ "所要分": 60, "担当営業": "営業二郎", "ステータス": "訪問済" })
  ];
  const stats = core.buildFillStats(list, "2026-08-14", ["営業一郎", "営業二郎", "両方次郎"]);
  assert.equal(stats.owners.length, 3);
  const ichiro = stats.owners[0];
  assert.equal(ichiro.owner, "営業一郎");
  assert.equal(ichiro.bookedMinutes, 150);
  assert.equal(ichiro.count, 2);
  assert.ok(Math.abs(ichiro.ratio - 150 / 540) < 1e-9);
  const jiro = stats.owners[1];
  assert.equal(jiro.bookedMinutes, 60);
  const mihari = stats.owners[2];
  assert.equal(mihari.bookedMinutes, 0);
  assert.equal(mihari.ratio, 0);
  assert.equal(stats.total.bookedMinutes, 210);
  assert.equal(stats.total.count, 3);
});

test("buildFillStats: 差し戻し・対象外・別日は空き扱い(集計しない)", () => {
  const list = [
    apo({ "ステータス": "差し戻し" }),
    apo({ "ステータス": "対象外" }),
    apo({ "日付": "2026-08-15", "ステータス": "アポ確定" })
  ];
  const stats = core.buildFillStats(list, "2026-08-14", ["営業一郎"]);
  assert.equal(stats.owners[0].bookedMinutes, 0);
  assert.equal(stats.total.count, 0);
});

test("buildFillStats: 埋まり率は100%を超えない(上限クランプ)", () => {
  const list = [apo({ "所要分": 600, "ステータス": "アポ確定" })];
  const stats = core.buildFillStats(list, "2026-08-14", ["営業一郎"]);
  assert.equal(stats.owners[0].ratio, 1);
});

test("buildConversionStats: 結果が出たアポだけを母数に、訪問実施率と申込率を返す", () => {
  const list = [
    apo({ "ステータス": "訪問済" }),
    apo({ "ステータス": "訪問済" }),
    apo({ "ステータス": "申込" }),
    apo({ "ステータス": "差し戻し" }),
    apo({ "ステータス": "スケジュール調整中" }),
    apo({ "ステータス": "アポ確定" }),
    apo({ "ステータス": "スケジュール調整中" })
  ];
  const stats = core.buildConversionStats(list, {});
  assert.equal(stats.concluded, 4);
  assert.equal(stats.completed, 3);
  assert.equal(stats.signups, 1);
  assert.ok(Math.abs(stats.visitRate - 3 / 4) < 1e-9);
  assert.ok(Math.abs(stats.signupRate - 1 / 3) < 1e-9);
});

test("buildConversionStats: 母数0のとき率はnull(0%や100%と断定しない)", () => {
  const stats = core.buildConversionStats([apo({ "ステータス": "スケジュール調整中" })], {});
  assert.equal(stats.concluded, 0);
  assert.equal(stats.visitRate, null);
  assert.equal(stats.signupRate, null);
});

test("buildTemperatureStats: 温度感ごとに訪問実施数・申込数・申込率を返す(高中低の順)", () => {
  const list = [
    apo({ "温度感": "高", "ステータス": "訪問済" }),
    apo({ "温度感": "高", "ステータス": "申込" }),
    apo({ "温度感": "高", "ステータス": "申込" }),
    apo({ "温度感": "高", "ステータス": "訪問済" }),
    apo({ "温度感": "中", "ステータス": "訪問済" }),
    apo({ "温度感": "高", "ステータス": "差し戻し" }),
    apo({ "温度感": "高", "ステータス": "スケジュール調整中" })
  ];
  const rows = core.buildTemperatureStats(list, {});
  assert.deepEqual(rows.map((r) => r.temperature), ["高", "中", "低"]);
  assert.equal(rows[0].completed, 4);
  assert.equal(rows[0].signups, 2);
  assert.ok(Math.abs(rows[0].rate - 0.5) < 1e-9);
  assert.equal(rows[1].completed, 1);
  assert.equal(rows[1].signups, 0);
  assert.equal(rows[1].rate, 0);
});

test("buildTemperatureStats: 訪問実施ゼロの温度感は率null(断定しない)、sinceDateで絞れる", () => {
  const rows = core.buildTemperatureStats([
    apo({ "温度感": "低", "ステータス": "申込", "日付": "2026-07-01" })
  ], { sinceDate: "2026-08-01" });
  rows.forEach((row) => {
    assert.equal(row.completed, 0);
    assert.equal(row.rate, null);
  });
});

test("buildSubstituteCandidates: キャンセル枠が空いている営業を、前後のアポ情報付きで返す", () => {
  const cancelled = apo({ "アポID": "X", "開始時刻": "14:00", "所要分": 60, "担当営業": "営業一郎" });
  const list = [
    cancelled,
    apo({ "アポID": "a", "担当営業": "営業二郎", "開始時刻": "13:00", "所要分": 60, "場所またはURL": "那覇市おもろまち", "ステータス": "アポ確定" }),
    apo({ "アポID": "b", "担当営業": "営業二郎", "開始時刻": "16:00", "所要分": 60, "場所またはURL": "浦添市", "ステータス": "スケジュール調整中" }),
    apo({ "アポID": "c", "担当営業": "両方次郎", "開始時刻": "14:30", "所要分": 60, "ステータス": "アポ確定" })
  ];
  const candidates = core.buildSubstituteCandidates(list, cancelled, ["営業一郎", "営業二郎", "両方次郎", "営業三郎"]);
  const names = candidates.map((c) => c.owner);
  assert.ok(!names.includes("営業一郎"), "元の担当営業は候補外");
  assert.ok(!names.includes("両方次郎"), "時間帯が重なる営業は候補外");
  assert.deepEqual(names, ["営業二郎", "営業三郎"], "前後にアポがある営業を先頭に");
  const jiro = candidates[0];
  assert.equal(jiro.before["開始時刻"], "13:00");
  assert.equal(jiro.before["場所またはURL"], "那覇市おもろまち");
  assert.equal(jiro.after["開始時刻"], "16:00");
  assert.equal(candidates[1].before, null);
  assert.equal(candidates[1].after, null);
});

test("buildSubstituteCandidates: キャンセル済みアポは前後情報に含めない・別日は無関係", () => {
  const cancelled = apo({ "アポID": "X", "開始時刻": "14:00", "担当営業": "営業一郎" });
  const list = [
    cancelled,
    apo({ "アポID": "a", "担当営業": "営業二郎", "開始時刻": "13:00", "ステータス": "差し戻し" }),
    apo({ "アポID": "b", "担当営業": "営業二郎", "開始時刻": "10:00", "日付": "2026-08-15", "ステータス": "アポ確定" })
  ];
  const candidates = core.buildSubstituteCandidates(list, cancelled, ["営業二郎"]);
  assert.equal(candidates[0].before, null);
  assert.equal(candidates[0].after, null);
});

test("buildConversionStats: sinceDate以降の日付だけを集計する", () => {
  const list = [
    apo({ "日付": "2026-07-01", "ステータス": "申込" }),
    apo({ "日付": "2026-08-10", "ステータス": "訪問済" })
  ];
  const stats = core.buildConversionStats(list, { sinceDate: "2026-07-15" });
  assert.equal(stats.concluded, 1);
  assert.equal(stats.signups, 0);
});

/* ---- 本日の全体表(営業×時間の帯)と結果集計 ---- */

const DAY = "2026-08-14";

test("buildDayTimeline: 営業ごとに帯を返し、位置と幅は営業時間に対する割合で出す", () => {
  const list = [apo({ "担当営業": "営業一郎", "開始時刻": "09:00", "所要分": 60, "ステータス": "アポ確定" })];
  const timeline = core.buildDayTimeline(list, DAY, ["営業一郎", "営業二郎"], { now: "12:00" });
  assert.deepEqual(timeline.rows.map((r) => r.owner), ["営業一郎", "営業二郎"]);
  const bar = timeline.rows[0].bars[0];
  // 9:00〜18:00(540分)の先頭1時間 = 左端0%・幅は約11%
  assert.equal(bar.left, 0);
  assert.ok(Math.abs(bar.width - (60 / 540) * 100) < 0.001);
  assert.equal(timeline.rows[1].bars.length, 0, "アポゼロの営業も行として出す");
  assert.equal(timeline.hours.length, 10, "9時から18時まで1時間ごとの目盛り");
});

test("buildDayTimeline: 営業時間の外にはみ出すアポも端で切って必ず見える", () => {
  const list = [apo({ "担当営業": "営業一郎", "開始時刻": "08:00", "所要分": 120, "ステータス": "アポ確定" })];
  const bar = core.buildDayTimeline(list, DAY, ["営業一郎"], {}).rows[0].bars[0];
  assert.equal(bar.left, 0);
  assert.ok(bar.width > 0);
});

test("buildDayTimeline: 対象外(架電禁止・アポ禁)は枠を占めないので出さない", () => {
  const list = [apo({ "担当営業": "営業一郎", "ステータス": "対象外" })];
  assert.deepEqual(core.buildDayTimeline(list, DAY, ["営業一郎"], {}).rows[0].bars, []);
});

test("buildDayTimeline: スタッフ表にない担当営業も行として出す(黙って消さない)", () => {
  const list = [apo({ "担当営業": "退職済 太郎", "ステータス": "アポ確定" })];
  const owners = core.buildDayTimeline(list, DAY, ["営業一郎"], {}).rows.map((r) => r.owner);
  assert.deepEqual(owners, ["営業一郎", "退職済 太郎"]);
});

test("buildDayTimeline: 担当営業が空でも行が消えず「(担当なし)」に集まる", () => {
  const list = [apo({ "担当営業": "", "ステータス": "アポ確定" })];
  const owners = core.buildDayTimeline(list, DAY, [], {}).rows.map((r) => r.owner);
  assert.deepEqual(owners, ["(担当なし)"]);
});

test("buildDayResultStats: これから/結果待ち/訪問済/申込/差し戻しの5つに束ねて数える", () => {
  const list = [
    apo({ "担当営業": "営業一郎", "開始時刻": "09:00", "所要分": 60, "ステータス": "アポ確定" }),
    apo({ "担当営業": "営業一郎", "開始時刻": "16:00", "所要分": 60, "ステータス": "アポ確定" }),
    apo({ "担当営業": "営業一郎", "開始時刻": "10:00", "所要分": 60, "ステータス": "訪問済" }),
    apo({ "担当営業": "営業二郎", "開始時刻": "11:00", "所要分": 60, "ステータス": "申込" }),
    apo({ "担当営業": "営業二郎", "開始時刻": "13:00", "所要分": 60, "ステータス": "差し戻し" })
  ];
  const stats = core.buildDayResultStats(list, DAY, ["営業一郎", "営業二郎"], { now: "14:00" });
  const ichiro = stats.owners[0];
  assert.equal(ichiro.pending, 1, "9時のアポは終わって猶予も過ぎたのに結果がない");
  assert.equal(ichiro.ahead, 1, "16時のアポはまだこれから");
  assert.equal(ichiro.visited, 1);
  assert.equal(ichiro.total, 3);
  assert.equal(stats.owners[1].signed, 1);
  assert.equal(stats.owners[1].returned, 1);
  assert.equal(stats.totals.total, 5);
});

test("buildDayResultStats: 成立・保全中も申込として数える(ファネルと同じ定義を使う)", () => {
  const list = [
    apo({ "担当営業": "営業一郎", "ステータス": "成立" }),
    apo({ "担当営業": "営業一郎", "ステータス": "保全中" }),
    apo({ "担当営業": "営業一郎", "ステータス": "追客中" })
  ];
  const stats = core.buildDayResultStats(list, DAY, ["営業一郎"], { now: "18:00" });
  assert.equal(stats.totals.signed, 2);
  assert.equal(stats.totals.visited, 1);
});

test("buildDayResultStats: アポゼロでも営業は行として出る(0件と分かる)", () => {
  const stats = core.buildDayResultStats([], DAY, ["営業一郎"], { now: "12:00" });
  assert.equal(stats.owners.length, 1);
  assert.equal(stats.owners[0].total, 0);
  assert.equal(stats.totals.total, 0);
});
