import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const alerting = require("../glow-ma/src/alerting.js");

test("toDate: yyyy-MM-dd形式の文字列をDateに変換する", () => {
  const d = alerting.toDate("2026-07-27");
  assert.equal(d.getFullYear(), 2026);
  assert.equal(d.getMonth(), 6);
  assert.equal(d.getDate(), 27);
});

test("toDate: Dateオブジェクトはそのまま返す(GASがセルを日付型として読む場合に対応)", () => {
  const original = new Date(2026, 6, 27);
  assert.equal(alerting.toDate(original), original);
});

test("toDate: 空文字・null・不正な形式はnull", () => {
  assert.equal(alerting.toDate(""), null);
  assert.equal(alerting.toDate(null), null);
  assert.equal(alerting.toDate(undefined), null);
  assert.equal(alerting.toDate("不正な値"), null);
});

test("daysBetween: 日数差を正しく計算する", () => {
  assert.equal(alerting.daysBetween("2026-07-01", "2026-07-27"), 26);
});

test("daysBetween: 文字列とDateオブジェクトが混在していても計算できる", () => {
  assert.equal(alerting.daysBetween(new Date(2026, 6, 1), "2026-07-27"), 26);
});

test("daysBetween: どちらかが不正な日付ならnull", () => {
  assert.equal(alerting.daysBetween("", "2026-07-27"), null);
  assert.equal(alerting.daysBetween("2026-07-01", null), null);
});
