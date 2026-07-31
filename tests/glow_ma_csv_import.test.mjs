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
