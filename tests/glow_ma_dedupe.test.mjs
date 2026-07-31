import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dedupe = require("../glow-ma/src/dedupe.js");

test("normalizeCorporateNumber: 13桁の数字はそのまま正規化される", () => {
  assert.equal(dedupe.normalizeCorporateNumber("1234567890123"), "1234567890123");
});

test("normalizeCorporateNumber: ハイフンや空白が入っていても13桁なら正規化される", () => {
  assert.equal(dedupe.normalizeCorporateNumber(" 1234-5678-90123 "), "1234567890123");
});

test("normalizeCorporateNumber: 13桁でない場合はnull", () => {
  assert.equal(dedupe.normalizeCorporateNumber("123456789012"), null);
});

test("normalizeCorporateNumber: null/undefined/空文字はnull", () => {
  assert.equal(dedupe.normalizeCorporateNumber(null), null);
  assert.equal(dedupe.normalizeCorporateNumber(undefined), null);
  assert.equal(dedupe.normalizeCorporateNumber(""), null);
});

test("findDuplicateGroups: 同じ法人番号のレコードが1グループにまとまる", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "1234567890123" },
    { 企業ID: "C000002", 法人番号: "1234567890123" },
    { 企業ID: "C000003", 法人番号: "9999999999999" }
  ];
  const groups = dedupe.findDuplicateGroups(companies);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].length, 2);
  assert.deepEqual(groups[0].map((c) => c.企業ID), ["C000001", "C000002"]);
});

test("findDuplicateGroups: 重複がなければ空配列", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "1234567890123" },
    { 企業ID: "C000002", 法人番号: "9999999999999" }
  ];
  assert.deepEqual(dedupe.findDuplicateGroups(companies), []);
});

test("findDuplicateGroups: 法人番号が空のレコードはグループ化対象外", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "" },
    { 企業ID: "C000002", 法人番号: "" }
  ];
  assert.deepEqual(dedupe.findDuplicateGroups(companies), []);
});
