// 毎分の処理の中での、音声ログ処理状況タブの読み取りの使い回し(LineVoiceLogRunner.gs)の試験。
// すべて架空の行・架空のLINEユーザーIDで、Googleのシートは偽物(getRange の呼び出しを数える)。
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = (f) => fs.readFileSync(path.join(here, "..", "glow-ma", "src", f), "utf8");

const HEADERS = ["処理ID", "LINEユーザーID", "ステータス", "受信日時"];

function fakeSheetFactory(rows, counter) {
  const data = rows.map((r) => r.slice());
  const sheet = {
    getLastRow: () => data.length + 1,
    getRange: (row, col, numRows, numCols) => {
      const c = numRows === undefined ? { kind: "cell", row, col } : { kind: "block", row, col, numRows, numCols };
      return {
        getValues: () => {
          counter.reads++;
          return data.map((r) => r.slice());
        },
        getValue: () => data[row - 2 >= 0 ? row - 2 : 0][col - 1],
        setValue: (v) => { data[row - 2][col - 1] = v; },
        setValues: (vals) => { data.push(vals[0].slice()); },
      };
    },
    _data: data,
  };
  return sheet;
}

function makeCtx(rows) {
  const counter = { reads: 0 };
  const sheet = fakeSheetFactory(rows, counter);
  const ss = { getSheetByName: (n) => (n === "音声ログ処理状況" ? sheet : null) };
  const ctx = {
    console,
    Logger: { log() {} },
    GlowSchema: { LINE_VOICE_LOG_SHEET_NAME: "音声ログ処理状況", LINE_VOICE_LOG_HEADERS: HEADERS },
    SpreadsheetApp: { getActiveSpreadsheet: () => ss },
    LockService: { getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }) },
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src("LineVoiceLogRunner.gs"), ctx);
  return { ctx, ss, sheet, counter };
}

const ROWS = [
  ["P1", "Uaaa", "受信済み", "2026-11-20 10:00"],
  ["P2", "Ubbb", "最終確認待ち", "2026-11-20 10:05"],
];

test("実行の外では、読み取りは毎回シートを読む(LINEの押下などの動きは変えない)", () => {
  const { ctx, counter } = makeCtx(ROWS);
  const ss = ctx.SpreadsheetApp.getActiveSpreadsheet();
  ctx.readVoiceLogRows_(ss);
  ctx.readVoiceLogRows_(ss);
  assert.equal(counter.reads, 2);
});

test("実行の中では、書き込みがなければ読み取りは1回だけ(毎分の処理の定常の形)", () => {
  const { ctx, counter } = makeCtx(ROWS);
  ctx.beginVoiceRunRowCache_();
  const ss = ctx.SpreadsheetApp.getActiveSpreadsheet();
  for (let i = 0; i < 4; i++) {
    const rows = ctx.readVoiceLogRows_(ss);
    assert.equal(rows.length, 2);
  }
  ctx.endVoiceRunRowCache_();
  assert.equal(counter.reads, 1);
});

test("実行の中でも、状態を変える書き込み(transition)が成功したら、次の読み取りは新しく読み直す", () => {
  const { ctx, counter } = makeCtx(ROWS);
  ctx.beginVoiceRunRowCache_();
  const ss = ctx.SpreadsheetApp.getActiveSpreadsheet();
  ctx.readVoiceLogRows_(ss);
  const claimed = ctx.transitionVoiceLogStatus_(ss, 2, ["受信済み"], { "ステータス": "処理中" });
  assert.equal(claimed, true);
  const after = ctx.readVoiceLogRows_(ss);
  assert.equal(after[0]["ステータス"], "処理中", "書き込み後の読み取りは新しい値を返す");
  assert.equal(counter.reads, 2);
  ctx.endVoiceRunRowCache_();
});

test("実行の中で、確認なしの書き込み(期待ステータスが違う)は読み直しを起こさない", () => {
  const { ctx, counter } = makeCtx(ROWS);
  ctx.beginVoiceRunRowCache_();
  const ss = ctx.SpreadsheetApp.getActiveSpreadsheet();
  ctx.readVoiceLogRows_(ss);
  const claimed = ctx.transitionVoiceLogStatus_(ss, 3, ["受信済み"], { "ステータス": "処理中" });
  assert.equal(claimed, false, "最終確認待ちの行は、受信済みからの確保に失敗する");
  ctx.readVoiceLogRows_(ss);
  assert.equal(counter.reads, 1, "何も書き換えていないので、使い回しを続ける");
  ctx.endVoiceRunRowCache_();
});

test("実行の中で録音を新しく追加したら(append)、次の読み取りは新しい行を含む", () => {
  const { ctx, counter } = makeCtx(ROWS);
  ctx.beginVoiceRunRowCache_();
  const ss = ctx.SpreadsheetApp.getActiveSpreadsheet();
  assert.equal(ctx.readVoiceLogRows_(ss).length, 2);
  ctx.appendVoiceLogRow_(ss, ["P3", "Uccc", "受信済み", "2026-11-20 10:10"]);
  assert.equal(ctx.readVoiceLogRows_(ss).length, 3);
  assert.equal(counter.reads, 2);
  ctx.endVoiceRunRowCache_();
});

test("実行が終わったら使い回しは消え、次の読み取りはシートを読む", () => {
  const { ctx, counter } = makeCtx(ROWS);
  ctx.beginVoiceRunRowCache_();
  const ss = ctx.SpreadsheetApp.getActiveSpreadsheet();
  ctx.readVoiceLogRows_(ss);
  ctx.endVoiceRunRowCache_();
  ctx.readVoiceLogRows_(ss);
  assert.equal(counter.reads, 2);
});

test("毎分の処理は、途中で例外になっても使い回しを必ず消す(次の実行や LINE の押下に残らない)", () => {
  const { ctx } = makeCtx(ROWS);
  ctx.processQueuedVoiceLogsBody_ = () => { throw new Error("試験用の失敗"); };
  assert.throws(() => ctx.processQueuedVoiceLogsCore_(), /試験用の失敗/);
  assert.equal(ctx.VOICE_RUN_ROW_CACHE, null);
});
