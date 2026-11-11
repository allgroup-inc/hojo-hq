// 企業マスタの書き込み(ImportRunner.gs の writeCompanyRecords_)を、台帳を偽物にして動かすテスト。
// 2026-11-11 FK-010(書き込みの途中の Google 側エラーで企業マスタの約6割が消えた)の再発防止。会社名・IDはすべて架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const src = (p) => readFileSync(new URL(p, import.meta.url), "utf8");

// 2次元の値を持つ偽のシート。failWhen(row, nRows) が "throw" を返すとその書き込みは失敗、
// "partial" を返すと前半だけ書いてから失敗する(Sheets の大きな書き込みが途中まで反映されて止まる形)
function fakeSheet(name, rows, { failWhen = () => null } = {}) {
  const s = {
    name, rows: rows.map((r) => r.slice()), writes: 0, clears: 0,
    getName: () => name,
    getLastRow: () => {
      for (let i = s.rows.length - 1; i >= 0; i--) {
        if ((s.rows[i] || []).some((v) => v !== "" && v !== null && v !== undefined)) return i + 1;
      }
      return 0;
    },
    getRange: (row, col, nRows, nCols) => ({
      getValues: () => Array.from({ length: nRows }, (_, i) =>
        Array.from({ length: nCols }, (_, j) => {
          const v = (s.rows[row - 1 + i] || [])[col - 1 + j];
          return v === undefined ? "" : v;
        })),
      setValues: (vals) => {
        s.writes++;
        const mode = failWhen(row, nRows, s.writes);
        const n = mode === "partial" || mode === "cellpartial" ? Math.floor(vals.length / 2) : mode === "throw" ? 0 : vals.length;
        for (let i = 0; i < n; i++) {
          const target = s.rows[row - 1 + i] || [];
          vals[i].forEach((v, j) => { target[col - 1 + j] = v; });
          s.rows[row - 1 + i] = target;
        }
        // "cellpartial": 次の1行は、左から10列だけ書いたところで止まる(1行の中に2つの会社の値が混ざる形)
        if (mode === "cellpartial" && n < vals.length) {
          const target = s.rows[row - 1 + n] || [];
          vals[n].slice(0, 10).forEach((v, j) => { target[col - 1 + j] = v; });
          s.rows[row - 1 + n] = target;
        }
        if (mode) throw new Error("Exception: Service Spreadsheets failed while accessing document");
      },
      clearContent: () => {
        s.clears++;
        for (let i = 0; i < nRows; i++) {
          const target = s.rows[row - 1 + i];
          if (!target) continue;
          for (let j = 0; j < nCols; j++) target[col - 1 + j] = "";
        }
      },
    }),
  };
  return s;
}

function makeContext(sheets) {
  const ops = [];
  const notices = [];
  const sleeps = [];
  const ctx = {
    console: { log() {}, warn() {} }, Logger: { log() {} },
    Utilities: { sleep: (ms) => sleeps.push(ms), formatDate: () => "2026-11-11" },
    LockService: { getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }) },
    SpreadsheetApp: {
      flush() {},
      getActiveSpreadsheet: () => ({ getSheetByName: (n) => sheets.find((s) => s.name === n) || null }),
    },
    recordOpsStatus_: (name, ok, detail) => ops.push({ name, ok, detail }),
    notifyOpsFailure_: (name, message) => notices.push({ name, message }),
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of ["schema.js", "scoring.js", "dedupe.js", "companyWriteGuard.js"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
  for (const f of ["ImportRunner.gs", "ScoringRunner.gs", "DncRunner.gs"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
  return { ctx, ops, notices, sleeps };
}

// 架空の会社を n 社持つ企業マスタ(見出しは本物の列の並び)
function masterRows(ctx, n, { trailingBlank = 0 } = {}) {
  const headers = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
  const col = (h) => headers.indexOf(h);
  const rows = [headers.slice()];
  for (let i = 1; i <= n; i++) {
    const r = headers.map(() => "");
    r[col("企業ID")] = "C9" + String(i).padStart(5, "0");
    r[col("会社名")] = "架空建設" + i;
    r[col("業種")] = i % 2 ? "建設業" : "福祉";
    r[col("電話番号")] = "000-0000-" + String(i).padStart(4, "0");
    r[col("流入ルート")] = "②手紙DM";
    r[col("総合スコア")] = 0;
    rows.push(r);
  }
  for (let i = 0; i < trailingBlank; i++) rows.push(headers.map(() => ""));
  return rows;
}

const idsOf = (sheet) => sheet.rows.slice(1).map((r) => r[0]).filter((v) => v !== "" && v !== undefined);
const LOG = (ctx) => ({ name: "対応履歴ログ", ...fakeSheet("対応履歴ログ", [ctx.GlowSchema.INTERACTION_LOG_HEADERS.slice()]) });

function setup(n, opts = {}) {
  const sheets = [];
  const env = makeContext(sheets);
  const master = fakeSheet("企業マスタ", masterRows(env.ctx, n, opts), opts);
  sheets.push(master, fakeSheet("対応履歴ログ", [env.ctx.GlowSchema.INTERACTION_LOG_HEADERS.slice()]));
  return { ...env, master, before: master.rows.map((r) => r.slice()) };
}

test("ふだんのスコア再計算: 1,200社すべて残り、スコアが入り、稼働状況に照合済みと残る", () => {
  const { ctx, master, ops } = setup(1200);
  ctx.recalculateAllScores();
  const ids = idsOf(master);
  assert.equal(ids.length, 1200);
  assert.equal(new Set(ids).size, 1200);
  const scoreCol = ctx.GlowSchema.COMPANY_MASTER_HEADERS.indexOf("総合スコア");
  assert.ok(master.rows.slice(1).every((r) => r[scoreCol] !== ""));
  assert.ok(master.writes >= 3, "500行ずつに分けて書く");
  const done = ops.find((o) => o.name === "企業マスタの書き込み");
  assert.equal(done.ok, true);
  assert.match(done.detail, /1200社\(書き込み後に企業IDを照合済み\)/);
});

test("今回の事故の形: 書き込みの途中で失敗し続けても、会社は1社も消えない。止めて通知する", () => {
  // 3つ目のかたまり(1001行目以降)が何度やり直しても失敗する
  const { ctx, master, ops, notices, sleeps, before } = setup(3000, { failWhen: (row) => (row >= 1002 ? "throw" : null) });
  assert.throws(() => ctx.recalculateAllScores(), /企業マスタの書き込みを止めました。書き込みの途中で止まりました\(1000\/3000社まで/);
  const ids = idsOf(master);
  assert.equal(ids.length, 3000, "3,000社のまま");
  assert.deepEqual(ids, before.slice(1).map((r) => r[0]), "企業IDの並びも元のまま(重複・欠番なし)");
  // まだ書いていない行(1001社目以降)は元のデータのまま
  assert.deepEqual(master.rows[1500], before[1500]);
  assert.equal(master.clears, 0, "余りの行の消去もしていない");
  assert.equal(sleeps.length, 2, "一時的なエラーとして2回待ってやり直した");
  assert.equal(ops.find((o) => o.name === "企業マスタの書き込み").ok, false);
  assert.equal(notices.length, 1);
  assert.match(notices[0].message, /まだ書いていない行には元のデータが残っています/);
});

test("1回の書き込みが前半だけ反映されて失敗しても、会社は消えない", () => {
  const { ctx, master, before } = setup(1200, { failWhen: (row) => (row === 502 ? "partial" : null) });
  assert.throws(() => ctx.recalculateAllScores(), /書き込みの途中で止まりました/);
  assert.deepEqual(idsOf(master), before.slice(1).map((r) => r[0]));
});

test("一時的なエラーが1回だけなら、その場でやり直して最後まで書く", () => {
  const { ctx, master, ops, sleeps } = setup(1200, { failWhen: (row, n, count) => (count === 2 ? "throw" : null) });
  ctx.recalculateAllScores();
  assert.equal(idsOf(master).length, 1200);
  assert.deepEqual(sleeps, [2000]);
  assert.equal(ops.find((o) => o.name === "企業マスタの書き込み").ok, true);
});

test("お断り(連絡不要)の反映も同じ書き込みを使い、途中で失敗しても会社は消えない", () => {
  const { ctx, master, before } = setup(1500, { failWhen: (row) => (row >= 502 ? "throw" : null) });
  assert.throws(() => ctx.syncDoNotContactFlags(), /企業マスタの書き込みを止めました/);
  assert.deepEqual(idsOf(master), before.slice(1).map((r) => r[0]));
});

test("書く前の確認: 会社が抜けている書き込みは、何も書かずに止める", () => {
  const { ctx, master, before, notices } = setup(10);
  const records = ctx.readCompanyRecords_(master).slice(0, 7);
  assert.throws(() => ctx.writeCompanyRecords_(master, records), /書き込む前の確認で止めました\(企業マスタは変更していません\): 今の企業マスタにある 3社/);
  assert.deepEqual(master.rows, before);
  assert.equal(master.writes, 0);
  assert.equal(notices.length, 1);
});

test("書く前の確認: 0社で上書きしようとしたら止める(以前は企業マスタが空になった)", () => {
  const { ctx, master, before } = setup(10);
  assert.throws(() => ctx.writeCompanyRecords_(master, []), /0社/);
  assert.deepEqual(master.rows, before);
});

test("名寄せの統合(インポート): 名指しした会社だけ外し、余った行は照合のあとで消す。重複を残さない", () => {
  const { ctx, master } = setup(5);
  const records = ctx.readCompanyRecords_(master).filter((r) => r["企業ID"] !== "C900002");
  records.push({ ...records[0], 企業ID: "C900006", 会社名: "架空新規" });
  ctx.writeCompanyRecords_(master, records, { allowRemovedIds: ["C900002"] });
  assert.deepEqual(idsOf(master), ["C900001", "C900003", "C900004", "C900005", "C900006"]);
  assert.equal(master.clears, 0, "行数が同じなので消す行は無い");
  const shrink = setup(5);
  const fewer = shrink.ctx.readCompanyRecords_(shrink.master).filter((r) => r["企業ID"] !== "C900004");
  shrink.ctx.writeCompanyRecords_(shrink.master, fewer, { allowRemovedIds: ["C900004"] });
  assert.deepEqual(idsOf(shrink.master), ["C900001", "C900002", "C900003", "C900005"]);
  assert.equal(shrink.master.clears, 1, "余った1行を消した");
});

test("書いた後の照合: 書いた内容が読み直しと違えば、余った行を消さずに止める", () => {
  const sheets = [];
  const env = makeContext(sheets);
  const master = fakeSheet("企業マスタ", masterRows(env.ctx, 6));
  sheets.push(master);
  const realGetRange = master.getRange;
  // 書き込みが黙って1行ずれて反映される(ありえない壊れ方の想定)
  master.getRange = (row, col, n, c) => {
    const r = realGetRange(row, col, n, c);
    return { ...r, setValues: (vals) => realGetRange(row + 1, col, n, c).setValues(vals) };
  };
  const records = env.ctx.readCompanyRecords_(master).slice(0, 5);
  assert.throws(
    () => env.ctx.writeCompanyRecords_(master, records, { allowRemovedIds: ["C900006"] }),
    /書いた後の照合で違いが見つかりました\(余った行は消していません。/
  );
  assert.equal(master.clears, 0);
});

test("末尾に書式だけの空行があっても、件数を誤らない", () => {
  const { ctx, master } = setup(20, { trailingBlank: 30 });
  ctx.recalculateAllScores();
  assert.equal(idsOf(master).length, 20);
});

test("企業マスタを書き直す呼び出しは6か所で、消してよい会社を名指しするのは名寄せのインポートだけ", () => {
  const files = ["ImportRunner.gs", "ScoringRunner.gs", "DncRunner.gs", "PreScreeningRunner.gs", "HistoricalDataImporter.gs", "PhaseATestRunner.gs"];
  let calls = 0;
  let allowing = 0;
  for (const f of files) {
    const text = src("../glow-ma/src/" + f);
    const found = text.match(/writeCompanyRecords_\([^)]*\)/g) || [];
    const realCalls = found.filter((c) => !/^writeCompanyRecords_\(sheet, records, options\)$/.test(c));
    calls += realCalls.length;
    allowing += (text.match(/writeCompanyRecords_\([^;]*allowRemovedIds/g) || []).length;
  }
  assert.equal(calls, 6);
  assert.equal(allowing, 1);
});

// --- 行がずれる書き込み(名寄せの統合など)の全列照合(2026-11-12 追加) ---
const BACKUP = "企業マスタ_backup_2026-11-12_090000";
const withoutSecond = (ctx, master) => ctx.readCompanyRecords_(master).filter((r) => r["企業ID"] !== "C900002");

test("行がずれる書き込みが最後まで書けたら、全列を照合してから余った行を消す", () => {
  const { ctx, master, ops } = setup(1200);
  ctx.writeCompanyRecords_(master, withoutSecond(ctx, master), { allowRemovedIds: ["C900002"], backupSheetName: BACKUP });
  const ids = idsOf(master);
  assert.equal(ids.length, 1199);
  assert.equal(new Set(ids).size, 1199);
  const nameCol = ctx.GlowSchema.COMPANY_MASTER_HEADERS.indexOf("会社名");
  assert.equal(master.rows[2][nameCol], "架空建設3", "3社目が2社目の行へ上がり、会社名も同じ会社のもの");
  assert.match(ops.find((o) => o.name === "企業マスタの書き込み").detail, /企業IDと全列を照合済み/);
});

test("行がずれる書き込みで、1行の途中の列で止まった: 混ざった行を数え、バックアップのタブからの戻し方を示して止める", () => {
  const { ctx, master, notices } = setup(1200, { failWhen: (row) => (row === 502 ? "cellpartial" : null) });
  const before = master.rows.map((r) => r.slice());
  assert.throws(
    () => ctx.writeCompanyRecords_(master, withoutSecond(ctx, master), { allowRemovedIds: ["C900002"], backupSheetName: BACKUP }),
    /1行の中に別の会社の値が混ざった行が 1行、まだ書けていない行が \d+行あります。戻すときは、書く前に作ったバックアップのタブ「企業マスタ_backup_2026-11-12_090000」/
  );
  assert.equal(master.clears, 0, "余った行は消していない");
  // 外してよい1社を除き、元の会社は1社も消えていない(重複は残りうるので、照合で止めて人が戻す)
  const left = new Set(idsOf(master));
  for (const id of before.slice(1).map((r) => r[0]).filter((id) => id !== "C900002")) assert.ok(left.has(id), id);
  assert.match(notices[0].message, /バックアップのタブ/);
});

test("行がずれる書き込みで、企業IDは合っているのに他の列が違えば(全列の照合)、余った行を消さずに止める", () => {
  const { ctx, master } = setup(30);
  const headers = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
  const phoneCol = headers.indexOf("電話番号");
  const realGetRange = master.getRange;
  // 書いたあと、10行目の電話番号だけが別の値になって読み戻される(壊れ方の想定)
  master.getRange = (row, col, n, c) => {
    const r = realGetRange(row, col, n, c);
    return { ...r, setValues: (vals) => {
      r.setValues(vals);
      if (row <= 10 && row + n > 10 && col === 1) master.rows[9][phoneCol] = "000-0000-9999";
    } };
  };
  assert.throws(
    () => ctx.writeCompanyRecords_(master, withoutSecond(ctx, master), { allowRemovedIds: ["C900002"], backupSheetName: BACKUP }),
    /書いた後の全列の照合で違いが見つかりました\(余った行は消していません。.*\): 書いた内容と違う行が 1行あります\(10行目 C900010: 電話番号\)/
  );
  assert.equal(master.clears, 0);
});

test("ふだんの再計算(行がずれない)では全列の照合はしない。シートが値の形を変えても誤って止めない", () => {
  const { ctx, master, ops } = setup(20);
  const dateCol = ctx.GlowSchema.COMPANY_MASTER_HEADERS.indexOf("最終接触日");
  master.rows.slice(1).forEach((r) => { r[dateCol] = new Date("2026-10-01T00:00:00+09:00"); });
  ctx.recalculateAllScores();
  assert.equal(idsOf(master).length, 20);
  assert.match(ops.find((o) => o.name === "企業マスタの書き込み").detail, /企業IDを照合済み/);
});

test("事前選定の取り込みも、書く前に作るバックアップのタブ名を戻し方として渡す", () => {
  assert.match(src("../glow-ma/src/PreScreeningRunner.gs"), /writeCompanyRecords_\(companySheet, updatedRecords, \{ backupSheetName: backupName \}\)/);
  assert.match(src("../glow-ma/src/ImportRunner.gs"), /allowRemovedIds: absorbedExistingIds, backupSheetName: backupName/);
});

// --- 日次メンテナンス: 企業マスタの書き込みを止めたら、後の手順も止める ---
function runMaintenance(failing) {
  const called = [];
  const ops = [];
  const notices = [];
  const step = (name) => () => {
    called.push(name);
    if (failing[name]) throw new Error(failing[name]);
  };
  const ctx = {
    Logger: { log() {} },
    backupLedger: step("backup"), syncDoNotContactFlags: step("dnc"), recalculateAllScores: step("score"),
    updateDashboard: step("dashboard"), updateTodayList: step("today"), runWld02WeeklyIfDue_: step("wld02"), runDailyAlerts: step("alerts"),
    recordOpsStatus_: (name, ok, detail) => ops.push({ name, ok, detail }),
    notifyOpsFailure_: (name, message) => notices.push({ name, message }),
  };
  vm.createContext(ctx);
  vm.runInContext(src("../glow-ma/src/MaintenanceRunner.gs"), ctx);
  ctx.runDailyMaintenance();
  return { called, ops, notices };
}

test("日次メンテナンス: お断りの反映で企業マスタの書き込みを止めたら、再計算・今日の連絡先・アラートは動かさない", () => {
  const { called, ops, notices } = runMaintenance({ dnc: "企業マスタの書き込みを止めました。書き込みの途中で止まりました" });
  assert.deepEqual(called, ["backup", "dnc"]);
  const status = ops.find((o) => o.name === "日次メンテナンス");
  assert.equal(status.ok, false);
  assert.match(status.detail, /掘り起こしアラートの送信: 「お断り\(連絡不要\)の反映」で企業マスタの書き込みを止めたため、実行しませんでした/);
  assert.equal(notices.length, 1);
});

test("日次メンテナンス: 企業マスタと関係ない失敗(ダッシュボード)では、これまでどおり後の手順も動かす", () => {
  const { called } = runMaintenance({ dashboard: "Exception: なにかの失敗" });
  assert.deepEqual(called, ["backup", "dnc", "score", "dashboard", "today", "wld02", "alerts"]);
});
