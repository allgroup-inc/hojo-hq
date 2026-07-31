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
