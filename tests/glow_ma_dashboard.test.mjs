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
  assert.deepEqual(find("M&A"), { "商品": "M&A", "提案数": 2, "案件化数": 1, "成約数": 1 });
  assert.deepEqual(find("不動産"), { "商品": "不動産", "提案数": 1, "案件化数": 0, "成約数": 1 });
  assert.deepEqual(find("法人保険"), { "商品": "法人保険", "提案数": 1, "案件化数": 0, "成約数": 0 });
});

test("buildProductFunnel: 提案商品が未設定の企業は集計対象外", () => {
  const records = [{ 現在ステージ: "未接触" }];
  const summary = dashboard.buildProductFunnel(records, dashboard.DEFAULT_CONFIG);
  summary.forEach((s) => assert.equal(s["提案数"], 0));
});
