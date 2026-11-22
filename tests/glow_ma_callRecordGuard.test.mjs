// 架電結果の記録の直前の確認(callMode.js の checkCallRecordAllowed)の試験。会社名・人名はすべて架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const m = require("../glow-ma/src/callMode.js");

const COMPANY = { "企業ID": "C9000301", "会社名": "架空商事301", "連絡不要": false, "現在ステージ": "未接触" };
const TODAY_OTHER = [{ "担当者": "架空担当A" }];

test("一覧が古く、台帳に会社が無いときは記録しない(理由: stale)", () => {
  const r = m.checkCallRecordAllowed(null, [], {});
  assert.equal(r.ok, false);
  assert.equal(r.reason, "stale");
});

test("連絡不要の会社は、確認があっても記録しない", () => {
  const r = m.checkCallRecordAllowed({ ...COMPANY, "連絡不要": true }, [], { confirmDuplicate: true, confirmWon: true });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "doNotContact");
});

test("今日すでに記録がある会社は、確認なしでは記録しない(担当者名を示す)", () => {
  const r = m.checkCallRecordAllowed(COMPANY, TODAY_OTHER, {});
  assert.equal(r.ok, false);
  assert.equal(r.reason, "duplicateToday");
  assert.match(r.errors[0], /架空担当A/);
});

test("今日の記録があっても、二件目として確認すれば記録できる", () => {
  const r = m.checkCallRecordAllowed(COMPANY, TODAY_OTHER, { confirmDuplicate: true });
  assert.equal(r.ok, true);
});

test("今日の記録が無ければ、通常どおり記録できる", () => {
  assert.equal(m.checkCallRecordAllowed(COMPANY, [], {}).ok, true);
});

test("成約済みの会社は、確認なしでは記録しない。確認すれば記録できる", () => {
  const won = { ...COMPANY, "現在ステージ": "成約" };
  assert.equal(m.checkCallRecordAllowed(won, [], {}).reason, "won");
  assert.equal(m.checkCallRecordAllowed(won, [], { confirmWon: true }).ok, true);
});

test("見送りの会社は、時期が来た再掘り起こしとして記録できる(これまでどおり)", () => {
  const dropped = { ...COMPANY, "現在ステージ": "見送り" };
  assert.equal(m.checkCallRecordAllowed(dropped, [], {}).ok, true);
});

test("担当者名が空の記録でも、理由を空にせず示す", () => {
  const r = m.checkCallRecordAllowed(COMPANY, [{ "担当者": "" }], {});
  assert.match(r.errors[0], /担当者不明/);
});

// GAS 側の配線の確認: 記録の直前の確認は、ロックの中で、書き込みより前に行う(別の担当者の同時記録を見逃さないため)
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

test("記録の処理は、ロックの中で確認してから書き込む(静的な確認)", () => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const src = fs.readFileSync(path.join(here, "..", "glow-ma", "src", "AdminRunner.gs"), "utf8");
  const start = src.indexOf("function recordCallOutcome(");
  const end = src.indexOf("\n}\n", start);
  const body = src.slice(start, end);
  const lockAt = body.indexOf("tryLock(10000)");
  const guardAt = body.indexOf("GlowCallMode.checkCallRecordAllowed(");
  const writeAt = body.indexOf("setValues([row])");
  assert.ok(lockAt !== -1 && guardAt !== -1 && writeAt !== -1, "ロック・確認・書き込みが揃っている");
  assert.ok(lockAt < guardAt && guardAt < writeAt, "ロック → 確認 → 書き込みの順");
  assert.match(body, /guardFailed/, "確認に失敗したら記録を止める");
});
