// 世界の架け橋 WLD-02 の台帳への組み込み(Wld02Runner.gs)を、台帳を偽物にして動かすテスト。会社名・IDは架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const src = (p) => readFileSync(new URL(p, import.meta.url), "utf8");

// 2次元の値を持つ偽のシート(getRange で読み書きできる)。asDateCols の列は読むときに Date に変わる(シートの癖)
function fakeSheet(name, rows = [], { asDateCols = [] } = {}) {
  const s = {
    name, rows: rows.map((r) => r.slice()),
    getName: () => name,
    getLastRow: () => s.rows.length,
    getLastColumn: () => Math.max(0, ...s.rows.map((r) => r.length)),
    setFrozenRows: () => {},
    getRange: (row, col, nRows, nCols) => ({
      getValues: () => s.rows.slice(row - 1, row - 1 + nRows).map((r, i) =>
        Array.from({ length: nCols }, (_, j) => {
          const v = r[col - 1 + j] === undefined ? "" : r[col - 1 + j];
          return row - 1 + i > 0 && asDateCols.includes(j) && /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(v + "T00:00:00+09:00") : v;
        })),
      setValues: (vals) => { vals.forEach((v, i) => { s.rows[row - 1 + i] = v.slice(); }); },
    }),
  };
  return s;
}

function makeContext({ sheets, props = {}, now = Date.UTC(2026, 10, 9, 0, 0) /* 11/9(月) 9:00 JST */ }) {
  const ops = [];
  const ctx = {
    console: { log() {}, warn() {} }, Logger: { log() {} },
    Utilities: {
      formatDate: (d) => {
        const j = new Date(d.getTime() + 9 * 3600 * 1000);
        return j.toISOString().slice(0, 10) + (arguments.length ? "" : "");
      },
      getUuid: () => "00000000-run",
    },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null), setProperty: (k, v) => { props[k] = v; } }) },
    SpreadsheetApp: {
      getActiveSpreadsheet: () => ({
        getSheetByName: (n) => sheets.find((s) => s.name === n) || null,
        insertSheet: (n) => { const s = fakeSheet(n); sheets.push(s); return s; },
      }),
    },
    GlowSchema: { COMPANY_MASTER_SHEET_NAME: "企業マスタ", INTERACTION_LOG_SHEET_NAME: "対応履歴ログ" },
    readCompanyRecords_: () => [
      { 企業ID: "C900001", 会社名: "架空物産", 法人番号: "", 流入ルート: ["④世界の架け橋(Alibaba)"] },
      { 企業ID: "C900002", 会社名: "架空商店", 法人番号: "12345", 流入ルート: [] },
    ],
    recordOpsStatus_: (name, ok, detail) => ops.push({ name, ok, detail }),
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext("Date.now = () => " + now + ";", ctx);
  for (const f of ["wld02Kpi.js", "nameMatch.js"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
  vm.runInContext(src("../glow-ma/src/Wld02Runner.gs"), ctx);
  return { ctx, props, sheets, ops };
}

const LOG = () => fakeSheet("対応履歴ログ", [["履歴ID", "企業ID", "日付", "担当者", "種別", "対応相手", "内容メモ", "次回アクション"]]);
const MASTER = () => fakeSheet("企業マスタ", [["企業ID"]]);

test("初回: 4つの記録タブを見出し付きで作り、前の週を集計して週次KPIに1行書く", () => {
  const { ctx, sheets, props, ops } = makeContext({ sheets: [LOG(), MASTER()] });
  const detail = ctx.runWld02WeeklyIfDue_();
  for (const n of ["面談確認記録", "掲載契約記録", "企業ID対応表", "週次KPI(世界の架け橋)"]) assert.ok(sheets.find((s) => s.name === n), n);
  const weekly = sheets.find((s) => s.name === "週次KPI(世界の架け橋)");
  assert.equal(weekly.rows.length, 2);
  assert.equal(weekly.rows[1][0], "2026-11-02");
  assert.equal(weekly.rows[1][2], "集計済み");
  assert.equal(props.WLD02_LAST_DONE_WEEK, "2026-11-02");
  assert.match(detail, /2026-11-02 の週: 集計済み/);
  assert.match(detail, /タブを作成/);
  const audit = ops.find((o) => o.name === "法人番号の点検");
  assert.match(audit.detail, /確かめた 2社 \/ 正しい形 0 \/ 未入力 1 \/ 正しくない 1 \/ 重複の組 0/);
});

test("同じ週は2回集計しない。翌週の月曜は次の週を足す", () => {
  const { ctx, sheets, props } = makeContext({ sheets: [LOG(), MASTER()] });
  ctx.runWld02WeeklyIfDue_();
  assert.match(ctx.runWld02WeeklyIfDue_(), /^済み/);
  vm.runInContext("Date.now = () => " + Date.UTC(2026, 10, 16, 0, 0) + ";", ctx);
  ctx.runWld02WeeklyIfDue_();
  const weekly = sheets.find((s) => s.name === "週次KPI(世界の架け橋)");
  assert.deepEqual(weekly.rows.slice(1).map((r) => r[0]), ["2026-11-02", "2026-11-09"]);
  assert.equal(props.WLD02_LAST_DONE_WEEK, "2026-11-09");
});

test("読めない記録があれば「取得不能」で書き、次の日にもう一度集計する。集計できたら同じ行を上書きする(週の開始日が日付で返っても二重にしない)", () => {
  const sheets = [LOG(), MASTER()];
  const { ctx, props } = makeContext({ sheets });
  // 企業マスタが読めない日
  ctx.readCompanyRecords_ = () => { throw new Error("読めない"); };
  ctx.SpreadsheetApp.getActiveSpreadsheet = (() => {
    const base = ctx.SpreadsheetApp.getActiveSpreadsheet();
    return () => ({ ...base, getSheetByName: (n) => (n === "企業マスタ" ? null : base.getSheetByName(n)) });
  })();
  const d1 = ctx.runWld02WeeklyIfDue_();
  assert.match(d1, /取得不能/);
  assert.equal(props.WLD02_LAST_DONE_WEEK, undefined);
  // 次の日: 読めるようになった。週次KPIの週の開始日は Date で返る(シートの癖)
  const weekly = sheets.find((s) => s.name === "週次KPI(世界の架け橋)");
  const dated = fakeSheet(weekly.name, weekly.rows, { asDateCols: [0] });
  sheets.splice(sheets.indexOf(weekly), 1, dated);
  const fresh = makeContext({ sheets, props });
  const d2 = fresh.ctx.runWld02WeeklyIfDue_();
  assert.match(d2, /集計済み/);
  assert.equal(dated.rows.length, 2); // 上書きで1行のまま
  assert.equal(dated.rows[1][2], "集計済み");
});

test("集計済みの週は、あとで記録が読めなくなっても上書きしない(前の値を残す)", () => {
  const sheets = [LOG(), MASTER()];
  const first = makeContext({ sheets });
  first.ctx.runWld02WeeklyIfDue_();
  delete first.props.WLD02_LAST_DONE_WEEK; // もう一度走らせる
  const s2 = makeContext({ sheets, props: first.props });
  s2.ctx.SpreadsheetApp.getActiveSpreadsheet = (() => {
    const base = s2.ctx.SpreadsheetApp.getActiveSpreadsheet();
    return () => ({ ...base, getSheetByName: (n) => (n === "掲載契約記録" ? null : base.getSheetByName(n)), insertSheet: () => { throw new Error("作れない"); } });
  })();
  assert.throws(() => s2.ctx.runWld02WeeklyIfDue_()); // タブを作れないときは止まる(日次メンテナンスが失敗として記録する)
  const weekly = sheets.find((s) => s.name === "週次KPI(世界の架け橋)");
  assert.equal(weekly.rows[1][2], "集計済み");
});

test("人が足した列があっても、既にある記録タブの見出しは書き換えない", () => {
  const conf = fakeSheet("面談確認記録", [["確認ID", "企業ID", "元の履歴ID", "面談日", "形式", "事業", "判定", "確認日時", "取消", "人が足した列"]]);
  const { ctx } = makeContext({ sheets: [LOG(), MASTER(), conf] });
  ctx.runWld02WeeklyIfDue_();
  assert.equal(conf.rows[0][9], "人が足した列");
});
