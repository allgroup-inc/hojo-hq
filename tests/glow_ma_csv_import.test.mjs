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
  const dataRow = ["沖縄物産株式会社", "小売業", "那覇市"];
  const columnMap = { 会社名: "法人名", 業種: "業種区分", 所在地: "所在地欄" };

  const record = csvImport.parseCompanyCsvRow(headerRow, dataRow, columnMap, 1, "2026-07-26");

  assert.equal(record.企業ID, "C000001");
  assert.equal(record.会社名, "沖縄物産株式会社");
  assert.equal(record.業種, "小売業");
  assert.equal(record.所在地, "那覇市");
  assert.deepEqual(record.流入ルート, ["②手紙DM"]);
  assert.equal(record.現在ステージ, "未接触");
  assert.equal(record.登録日, "2026-07-26");
});

test("parseCompanyCsvRow: columnMapに存在しない列は空文字になる", () => {
  const headerRow = ["法人名"];
  const dataRow = ["沖縄物産株式会社"];
  const columnMap = { 会社名: "法人名", 代表者名: "存在しない見出し" };

  const record = csvImport.parseCompanyCsvRow(headerRow, dataRow, columnMap, 1, "2026-07-26");

  assert.equal(record.会社名, "沖縄物産株式会社");
  assert.equal(record.代表者名, "");
});
