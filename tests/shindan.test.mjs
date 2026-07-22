// フクギイロ 診断ロジック トラジェクトリeval(診断フロー設計v1のeval設計に準拠)
// CI(fukugiiro-ci.yml)で node --test により実行。落ちたらマージ不可。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const { matchSeido } = require("../site/fukugiiro/shindan/logic.js");

const db = JSON.parse(readFileSync(new URL("../data/fukugiiro/seido.json", import.meta.url), "utf-8"));
const items = db.items;

const names = (rs) => rs.map((r) => r.item.name);

test("正例: 那覇市・子2人(小学生)は児童手当が出る", () => {
  const rs = matchSeido(items, { municipality: "那覇市", children: 2, childAges: ["小学生"], lifeEvents: [] });
  assert.ok(names(rs).some((n) => n.includes("児童手当")), "児童手当が出るべき");
});

test("負例: 子0人・イベントなしでは子育て制度が出ない", () => {
  const rs = matchSeido(items, { municipality: "那覇市", children: 0, childAges: [], lifeEvents: [] });
  assert.ok(!names(rs).some((n) => n.includes("児童手当")), "児童手当が出てはいけない");
});

test("守り: 医療・健康カテゴリ(高額療養費等)は診断結果に出ない", () => {
  const rs = matchSeido(items, { municipality: "那覇市", children: 2, childAges: ["小学生"], lifeEvents: ["病気・けが"] });
  assert.ok(rs.every((r) => r.item.category !== "医療・健康"), "医療・健康は診断から除外");
});

test("失業イベントで住居確保給付金・求職者支援が「高」で出る", () => {
  const rs = matchSeido(items, { municipality: "沖縄市", children: 0, childAges: [], lifeEvents: ["失業"] });
  const high = rs.filter((r) => r.likelihood === "高").map((r) => r.item.name);
  assert.ok(high.some((n) => n.includes("住居確保給付金")));
});

test("妊娠・出産イベントは子0人でも妊婦向け給付が出る", () => {
  const rs = matchSeido(items, { municipality: "浦添市", children: 0, childAges: [], lifeEvents: ["妊娠・出産"] });
  assert.ok(names(rs).some((n) => n.includes("出産") || n.includes("妊婦")), "妊娠・出産系が出るべき");
});

test("教育: 高校生の子がいる世帯に就学支援金系が出る", () => {
  const rs = matchSeido(items, { municipality: "うるま市", children: 1, childAges: ["高校生"], lifeEvents: [] });
  assert.ok(names(rs).some((n) => n.includes("就学支援") || n.includes("修学支援") || n.includes("奨学給付金")));
});

test("教育: 未就学児のみの世帯に高校向け制度は出ない", () => {
  const rs = matchSeido(items, { municipality: "うるま市", children: 1, childAges: ["未就学"], lifeEvents: [] });
  assert.ok(!names(rs).some((n) => n.includes("就学支援金")));
});

test("禁止表現: 出力ラベルと制度文言に断定語が含まれない", () => {
  const forbidden = ["必ずもらえる", "絶対", "審査なし", "誰でももらえる", "確実にもらえる"];
  const rs = matchSeido(items, { municipality: "那覇市", children: 3, childAges: ["未就学", "小学生", "高校生"], lifeEvents: ["妊娠・出産", "失業", "入園・入学"] });
  for (const r of rs) {
    const textAll = [r.likelihood, r.item.name, r.item.target_household, r.item.amount_note, r.item.notes].join(" ");
    for (const w of forbidden) assert.ok(!textAll.includes(w), `禁止語 ${w}`);
  }
});

test("安定性: 高が中より先に並ぶ", () => {
  const rs = matchSeido(items, { municipality: "那覇市", children: 1, childAges: ["未就学"], lifeEvents: ["妊娠・出産"] });
  const firstMid = rs.findIndex((r) => r.likelihood === "中");
  const lastHigh = rs.map((r) => r.likelihood).lastIndexOf("高");
  if (firstMid >= 0 && lastHigh >= 0) assert.ok(lastHigh < firstMid);
});
