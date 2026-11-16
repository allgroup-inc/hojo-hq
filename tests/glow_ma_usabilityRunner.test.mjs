// glow-ma 使いやすさの改善の GAS 側(UsabilityRunner.gs)を、台帳を偽物にして動かすテスト。会社名・番号は架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const src = (p) => readFileSync(new URL(p, import.meta.url), "utf8");

function fakeSheet(name, { hidden = false, lastRow = 1 } = {}) {
  const s = {
    name, hidden, lastRow, written: null, format: null, note: null, cleared: false,
    getName: () => name, isSheetHidden: () => s.hidden, hideSheet: () => { s.hidden = true; },
    getLastRow: () => s.lastRow, clearContents: () => { s.cleared = true; }, setFrozenRows: () => {},
    getRange: () => ({
      setNumberFormat: (f) => { s.format = f; return { setValues: (v) => { s.written = v; } }; },
      setNote: (n) => { s.note = n; },
    }),
  };
  return s;
}

function makeContext({ sheets, props = {} }) {
  const ctx = {
    console, Logger: { log() {} },
    Utilities: { formatDate: () => "2026-11-09" },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = v; } }) },
    SpreadsheetApp: {
      getActiveSpreadsheet: () => ({
        getSheets: () => sheets,
        getSheetByName: (n) => sheets.find((s) => s.name === n) || null,
        insertSheet: (n) => { const s = fakeSheet(n); sheets.push(s); return s; },
      }),
    },
    GlowSchema: { COMPANY_MASTER_SHEET_NAME: "企業マスタ", INTERACTION_LOG_SHEET_NAME: "対応履歴ログ" },
    readCompanyRecords_: () => [
      { 企業ID: "C9000001", 会社名: "=架空工業", 電話番号: "0980000001", 連絡不要: false, 現在ステージ: "未接触", ランク: "B", 事前選定ランク: "S", 事前選定スコア: 30 },
      { 企業ID: "C9000002", 会社名: "架空商店", 電話番号: "098-000-0002", 連絡不要: false, 現在ステージ: "未接触", ランク: "B", 事前選定スコア: 10 },
    ],
    readInteractionsByCompanyId_: () => ({}),
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of ["alerting.js", "companyDigest.js", "todayList.js", "tabTidy.js"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
  vm.runInContext(src("../glow-ma/src/UsabilityRunner.gs"), ctx);
  return { ctx, props, sheets };
}

test("今日の連絡先: タブを作り、見出しと会社を書く。電話番号は文字として書き、= で始まる名前は数式にしない", () => {
  const { ctx, sheets } = makeContext({ sheets: [fakeSheet("企業マスタ"), fakeSheet("対応履歴ログ")] });
  assert.equal(ctx.updateTodayList(), "2件");
  const tab = sheets.find((s) => s.name === "今日の連絡先");
  assert.ok(tab.cleared);
  assert.equal(tab.format, "@");
  assert.equal(tab.written[0][0], "順位");
  const nameCol = tab.written[0].indexOf("会社名"), telCol = tab.written[0].indexOf("電話番号");
  assert.equal(tab.written[1][nameCol], "'=架空工業"); // 事前選定S が先頭
  assert.equal(tab.written[1][telCol], "0980000001");
  assert.match(tab.note, /2026-11-09/);
});

test("今日の連絡先: 件数はスクリプトプロパティ TODAY_LIST_SIZE で変えられる", () => {
  const { ctx } = makeContext({ sheets: [fakeSheet("企業マスタ"), fakeSheet("対応履歴ログ")], props: { TODAY_LIST_SIZE: "1" } });
  assert.equal(ctx.updateTodayList(), "1件");
});

test("使っていないタブ: 対象だけを非表示にし、1回やったら次からは何もしない", () => {
  const sheets = [fakeSheet("企業マスタ"), fakeSheet("シート1"), fakeSheet("企業マスタ_backup_2026-08-11_034603"), fakeSheet("QR生成結果", { lastRow: 1 }), fakeSheet("インポート待ち")];
  const { ctx, props } = makeContext({ sheets });
  assert.match(ctx.tidyUnusedTabsOnce_(), /^3個を非表示にした/);
  assert.deepEqual(sheets.filter((s) => s.hidden).map((s) => s.name), ["シート1", "企業マスタ_backup_2026-08-11_034603", "QR生成結果"]);
  assert.ok(props.TAB_TIDY_V1_DONE);
  sheets[0].hidden = false;
  const later = fakeSheet("シート5"); sheets.push(later);
  assert.equal(ctx.tidyUnusedTabsOnce_(), "済み");
  assert.equal(later.hidden, false); // 人が後で足したタブは、勝手に隠さない
});
