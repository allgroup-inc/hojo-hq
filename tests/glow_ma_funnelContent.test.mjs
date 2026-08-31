import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const funnel = require("../glow-ma/src/funnelContent.js");

// 2026-08-31は月曜日 → 今週=08-31〜09-06、先週=08-24〜08-30
const TODAY = "2026-08-31";

function makeActivity() {
  return {
    metrics: ["手紙", "架電", "アポ獲得", "面談・訪問", "提案", "成約"],
    weeks: [
      { label: "今週", start: "2026-08-31", end: "2026-09-06",
        total: { "手紙": 0, "架電": 3, "アポ獲得": 1, "面談・訪問": 2, "提案": 1, "成約": 0 }, byOwner: {} },
      { label: "先週", start: "2026-08-24", end: "2026-08-30",
        total: { "手紙": 5, "架電": 8, "アポ獲得": 2, "面談・訪問": 1, "提案": 0, "成約": 1 }, byOwner: {} }
    ]
  };
}

test("buildWeeklyFunnel: 週ごとにLP閲覧・LINE友だち・新規登録・面談・成約を1つの表に揃える", () => {
  const input = {
    siteTraffic: [
      { date: "2026-08-25", period: "24h", domain: { visitors: 10 } },
      { date: "2026-08-26", period: "24h", domain: { visitors: 15 } },
      { date: "2026-08-31", period: "24h", domain: { visitors: 7 } }
    ],
    lineFollowers: [
      { date: "2026-08-23", followers: 5 },
      { date: "2026-08-30", followers: 8 },
      { date: "2026-08-31", followers: 9 }
    ],
    kgiTarget: 1000,
    companies: [
      { "企業ID": "C1", "登録日": "2026-08-25", "流入ルート": ["③ミカタ経由"] },
      { "企業ID": "C2", "登録日": "2026-08-26", "流入ルート": ["①紹介"] },
      { "企業ID": "C3", "登録日": "2026-08-31", "流入ルート": ["②手紙DM"] },
      { "企業ID": "C4", "登録日": "2026-07-01", "流入ルート": [] }
    ],
    activity: makeActivity()
  };
  const result = funnel.buildWeeklyFunnel(input, TODAY, 2);
  assert.equal(result.weeks.length, 2);
  const thisWeek = result.weeks[0];
  assert.equal(thisWeek.label, "今週");
  assert.equal(thisWeek.lpVisitors, 7);
  assert.equal(thisWeek.lineFollowersEnd, 9);
  assert.equal(thisWeek.lineNet, 1); // 9 - 8(前週末)
  assert.equal(thisWeek.newCompanies, 1);
  assert.deepEqual(thisWeek.newByRoute, { "①紹介": 0, "②手紙DM": 1, "③ミカタ経由": 0 });
  assert.equal(thisWeek.meetings, 2);
  assert.equal(thisWeek.proposals, 1);
  assert.equal(thisWeek.closings, 0);
  const lastWeek = result.weeks[1];
  assert.equal(lastWeek.lpVisitors, 25);
  assert.equal(lastWeek.lineFollowersEnd, 8);
  assert.equal(lastWeek.lineNet, 3); // 8 - 5
  assert.equal(lastWeek.newCompanies, 2);
  assert.equal(lastWeek.closings, 1);
});

test("buildWeeklyFunnel: KGI進捗(最新の友だち数と1,000社に対する割合)を返す", () => {
  const result = funnel.buildWeeklyFunnel({
    siteTraffic: [], lineFollowers: [{ date: "2026-08-30", followers: 8 }],
    kgiTarget: 1000, companies: [], activity: makeActivity()
  }, TODAY, 2);
  assert.equal(result.kgi.current, 8);
  assert.equal(result.kgi.target, 1000);
  assert.equal(result.kgi.ratePercent, 0.8);
});

test("buildWeeklyFunnel: データが欠けている週はnullを返す(0と区別して「取得できず」を表示するため)", () => {
  const result = funnel.buildWeeklyFunnel({
    siteTraffic: [{ date: "2026-08-31", period: "24h", domain: null }],
    lineFollowers: [],
    kgiTarget: 1000, companies: [], activity: makeActivity()
  }, TODAY, 2);
  assert.equal(result.weeks[0].lpVisitors, null);
  assert.equal(result.weeks[0].lineFollowersEnd, null);
  assert.equal(result.weeks[0].lineNet, null);
  assert.equal(result.kgi.current, null);
  assert.equal(result.weeks[0].newCompanies, 0);
});

test("buildWeeklyFunnel: 24h集計がない週は7d集計の値で代用する(Plausible収集が不安定な期間への対応)", () => {
  const result = funnel.buildWeeklyFunnel({
    siteTraffic: [
      { date: "2026-08-26", period: "7d", domain: { visitors: 42 } }
    ],
    lineFollowers: [], kgiTarget: 1000, companies: [], activity: makeActivity()
  }, TODAY, 2);
  assert.equal(result.weeks[1].lpVisitors, 42);
});

test("buildWeeklyFunnel: 登録日がDateオブジェクトでも週に割り当てられる", () => {
  const result = funnel.buildWeeklyFunnel({
    siteTraffic: [], lineFollowers: [], kgiTarget: 1000,
    companies: [{ "企業ID": "C1", "登録日": new Date(2026, 7, 31), "流入ルート": [] }],
    activity: makeActivity()
  }, TODAY, 2);
  assert.equal(result.weeks[0].newCompanies, 1);
});
