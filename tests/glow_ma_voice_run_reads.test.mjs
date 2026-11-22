// 毎分の録音処理(processQueuedVoiceLogsCore_)を実際のコードで1回動かし、定常の1分で録音シートを全件読む回数を数える。
// 架空の録音行(3,300件)・偽のシート。自己点検・BlueBean・Drive 受付などの外部の処理は、読み取りを1回だけ模擬する。
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = (f) => fs.readFileSync(path.join(here, "..", "glow-ma", "src", f), "utf8");

test("毎分の録音処理: 確認待ちの録音が無い定常の1分では、録音シートの全件読み取りは1回だけ(3,300件)", () => {
  const ROWS_N = 3300;
  const data = [];
  for (let i = 0; i < ROWS_N; i++) data.push([`P${i}`, `U${i % 50}`, "確定", "2026-11-20 10:00", "", "", ""]);
  const counter = { fullReads: 0 };
  const sheet = {
    getLastRow: () => data.length + 1,
    getRange: (row, col, numRows) => ({
      getValues: () => { if (numRows !== undefined && numRows > 1) counter.fullReads++; return data.map((r) => r.slice()); },
      getValue: () => (data[row - 2] ? data[row - 2][col - 1] : ""),
      setValue: (v) => { data[row - 2][col - 1] = v; },
      setValues: (vals) => { data.push(vals[0].slice()); },
    }),
  };
  const ss = { getSheetByName: (n) => (n === "音声ログ処理状況" ? sheet : null) };
  const props = {};
  const ctx = {
    console, Logger: { log() {} }, Date,
    SpreadsheetApp: { getActiveSpreadsheet: () => ss },
    LockService: { getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }) },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: (k) => (k in props ? props[k] : null),
      setProperty: (k, v) => { props[k] = String(v); },
      deleteProperty: (k) => { delete props[k]; },
    }) },
    Utilities: { formatDate: () => "2026-11-20", sleep() {} },
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of ["schema.js", "lineVoiceLogContent.js", "voiceFileIntake.js", "LineVoiceLogRunner.gs", "DriveVoiceRunner.gs"]) {
    vm.runInContext(src(f), ctx);
  }
  Object.assign(ctx, {
    runSelfHealIfDue_: () => {}, runHistoryImportIfPending_: () => {}, runCtiSyncIfDue_: () => {},
    isGeminiBillingBlocked_: () => false,
    enqueueDriveVoiceFiles_: (s) => { ctx.readVoiceLogRows_(s); }, // Drive 受付の読み取り1回を模擬
  });
  // 1回目は一度だけの処理が走る。2回目が定常の1分
  ctx.processQueuedVoiceLogsCore_();
  counter.fullReads = 0;
  ctx.processQueuedVoiceLogsCore_();
  assert.equal(counter.fullReads, 1);
});
