import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const csvImport = require("../glow-ma/src/csvImport.js");

test("buildCompanyId: 連番を6桁ゼロ埋めのIDに変換する", () => {
  assert.equal(csvImport.buildCompanyId(1), "C000001");
  assert.equal(csvImport.buildCompanyId(42), "C000042");
  assert.equal(csvImport.buildCompanyId(7000), "C007000");
});

test("parseCompanyCsvRow: 見出しマッピングに従って値を取り出す", () => {
  const headerRow = ["法人名", "業種区分", "所在地欄"];
  const dataRow = ["テスト商事株式会社", "小売業", "那覇市"];
  const columnMap = { 会社名: "法人名", 業種: "業種区分", 所在地: "所在地欄" };

  const record = csvImport.parseCompanyCsvRow(headerRow, dataRow, columnMap, 1, "2026-07-26");

  assert.equal(record.企業ID, "C000001");
  assert.equal(record.会社名, "テスト商事株式会社");
  assert.equal(record.業種, "小売業");
  assert.equal(record.所在地, "那覇市");
  assert.deepEqual(record.流入ルート, ["②手紙DM"]);
  assert.equal(record.現在ステージ, "未接触");
  assert.equal(record.登録日, "2026-07-26");
});

test("parseCompanyCsvRow: columnMapに存在しない列は空文字になる", () => {
  const headerRow = ["法人名"];
  const dataRow = ["テスト商事株式会社"];
  const columnMap = { 会社名: "法人名", 代表者名: "存在しない見出し" };

  const record = csvImport.parseCompanyCsvRow(headerRow, dataRow, columnMap, 1, "2026-07-26");

  assert.equal(record.会社名, "テスト商事株式会社");
  assert.equal(record.代表者名, "");
});

test("parseCompanyCsvRow: 連絡不要にマッピングされた列の値がTRUEなら真偽値trueになる", () => {
  const headerRow = ["法人名", "DNC区分"];
  const dataRow = ["テスト商事株式会社", "TRUE"];
  const columnMap = { 会社名: "法人名", 連絡不要: "DNC区分" };

  const record = csvImport.parseCompanyCsvRow(headerRow, dataRow, columnMap, 1, "2026-07-26");

  assert.equal(record.連絡不要, true);
});

test("parseCompanyCsvRow: 連絡不要が空文字またはマッピングされていない場合はfalse", () => {
  const headerRow = ["法人名", "DNC区分"];
  const columnMap = { 会社名: "法人名", 連絡不要: "DNC区分" };

  const recordEmptyValue = csvImport.parseCompanyCsvRow(headerRow, ["テスト商事株式会社", ""], columnMap, 1, "2026-07-26");
  assert.equal(recordEmptyValue.連絡不要, false);

  const recordUnmapped = csvImport.parseCompanyCsvRow(headerRow, ["テスト商事株式会社", "TRUE"], { 会社名: "法人名" }, 1, "2026-07-26");
  assert.equal(recordUnmapped.連絡不要, false);
});

test("電話番号: マッピングされていなければ空文字、マッピングされていれば文字列の値になる", () => {
  const headerRow = ["法人名", "電話"];
  const columnMap = { 会社名: "法人名" };

  const recordUnmapped = csvImport.parseCompanyCsvRow(headerRow, ["テスト商事株式会社", "098-000-0001"], columnMap, 1, "2026-07-26");
  assert.equal(recordUnmapped.電話番号, "");

  const recordMapped = csvImport.parseCompanyCsvRow(headerRow, ["テスト商事株式会社", "098-000-0001"], { 会社名: "法人名", 電話番号: "電話" }, 1, "2026-07-26");
  assert.equal(recordMapped.電話番号, "098-000-0001");
});
