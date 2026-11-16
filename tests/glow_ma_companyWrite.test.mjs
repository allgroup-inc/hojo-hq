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
    name, rows: rows.map((r) => r.slice()), writes: 0, clears: 0, reads: 0,
    formulas: {},  // "行,列"(1始まり) → 数式。数式のセルを置いた台帳をまねる
    getName: () => name,
    getLastRow: () => {
      for (let i = s.rows.length - 1; i >= 0; i--) {
        if ((s.rows[i] || []).some((v) => v !== "" && v !== null && v !== undefined)) return i + 1;
      }
      return 0;
    },
    getRange: (row, col, nRows, nCols) => ({
      getFormulas: () => { s.reads++; return Array.from({ length: nRows }, (_, i) =>
        Array.from({ length: nCols }, (_, j) => s.formulas[(row + i) + "," + (col + j)] || "")); },
      getValues: () => (s.reads++, Array.from({ length: nRows }, (_, i) =>
        Array.from({ length: nCols }, (_, j) => {
          const v = (s.rows[row - 1 + i] || [])[col - 1 + j];
          return v === undefined ? "" : v;
        }))),
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
    // 緊急停止スイッチ(停止していない状態。停止中の試験は glow_ma_companyWritePause.test.mjs)
    PropertiesService: { getScriptProperties: () => ({ getProperty: () => null }) },
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of ["schema.js", "scoring.js", "dedupe.js", "companyWriteGuard.js", "companyWritePause.js", "executionBudget.js"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
  for (const f of ["ExecutionClock.gs", "ImportRunner.gs", "ScoringRunner.gs", "DncRunner.gs", "CompanyWritePauseRunner.gs"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
  // この実行が始まってからの時間(ミリ秒)。試験では clock.ms を動かして、遅い日・時間切れが近い状態をまねる
  const clock = { ms: 0 };
  ctx.executionElapsedMs_ = () => clock.ms;
  return { ctx, ops, notices, sleeps, clock };
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
  const log = fakeSheet("対応履歴ログ", [env.ctx.GlowSchema.INTERACTION_LOG_HEADERS.slice()]);
  sheets.push(master, log);
  return { ...env, master, log, before: master.rows.map((r) => r.slice()) };
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
  const { ctx, master, log, before } = setup(1500, { failWhen: (row) => (row >= 502 ? "throw" : null) });
  // 2つ目のかたまり(501行目以降)の会社が断った記録を入れる(変わる行が無ければ、そもそも書かない)
  const LH = ctx.GlowSchema.INTERACTION_LOG_HEADERS;
  const entry = LH.map(() => "");
  entry[LH.indexOf("履歴ID")] = "H-TEST-1"; entry[LH.indexOf("企業ID")] = "C900700";
  entry[LH.indexOf("日付")] = "2026-11-10"; entry[LH.indexOf("種別")] = "連絡不要受領";
  log.rows.push(entry);
  assert.throws(() => ctx.syncDoNotContactFlags(), /企業マスタの書き込みを止めました/);
  assert.deepEqual(idsOf(master), before.slice(1).map((r) => r[0]));
});

test("書く前の確認: 会社が抜けている書き込みは、何も書かずに止める", () => {
  const { ctx, master, before, notices } = setup(10);
  const records = ctx.readCompanyRecords_(master).slice(0, 7);
  assert.throws(() => ctx.writeCompanyRecords_(master, records), /書く前の確認で止めました\(企業マスタは変更していません\): 今の企業マスタにある 3社/);
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
  records[2]["会社名"] = "架空建設(変更)";  // 変わる行が無ければ、そもそも書かない
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

// --- 日次メンテナンス: 企業マスタの書き込みを止めたら、影響を受ける手順だけ止める(2026-11-15 エラー種別で判断) ---
function companyWriteError(phase, dataChanged) {
  const e = new Error("どんな文言でもよい(文言では判断しない)");
  e.companyWrite = { phase, dataChanged };
  return e;
}

// opts.onStep(name, env): 手順が動くたびに呼ぶ(時間を進める・印を覗く用)。opts.props: スクリプトプロパティの初期値
function runMaintenance(failing, opts = {}) {
  const called = [];
  const ops = [];
  const notices = [];
  const logs = [];
  const errors = [];
  const store = { ...(opts.props || {}) };
  const clock = { ms: opts.elapsedMs || 0 };
  const step = (name) => () => {
    called.push(name);
    if (opts.onStep) opts.onStep(name, { clock, store });
    const f = failing[name];
    if (f) throw typeof f === "string" ? new Error(f) : f;
  };
  const ctx = {
    Logger: { log: (m) => logs.push(String(m)) },
    console: { error: (m) => errors.push(String(m)), log() {} },
    Utilities: { formatDate: () => "2026-11-16 07:32" },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: (k) => (k in store ? store[k] : null),
      setProperty: (k, v) => { store[k] = String(v); },
      deleteProperty: (k) => { delete store[k]; },
    }) },
    executionElapsedMs_: () => clock.ms,
    backupLedger: step("backup"), syncDoNotContactFlags: step("dnc"), recalculateAllScores: step("score"),
    updateDashboard: step("dashboard"), updateTodayList: step("today"), runWld02WeeklyIfDue_: step("wld02"), runDailyAlerts: step("alerts"),
    recordOpsStatus_: (name, ok, detail) => ops.push({ name, ok, detail }),
    notifyOpsFailure_: (name, message) => notices.push({ name, message }),
    readCompanyWritePause_: () => ({ paused: false }),
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src("../glow-ma/src/executionBudget.js"), ctx);
  vm.runInContext(src("../glow-ma/src/MaintenanceRunner.gs"), ctx);
  const setNow = (ms) => vm.runInContext("Date.now = () => " + ms, ctx);
  if (opts.nowMs) setNow(opts.nowMs);
  if (opts.beforeRun) opts.beforeRun(ctx);
  const env = { called, ops, notices, logs, errors, store, clock, ctx, setNow, thrown: null };
  if (opts.dontRun) return env;
  try { ctx.runDailyMaintenance(); } catch (e) { env.thrown = e; }
  if (env.thrown && !opts.allowThrow) throw env.thrown;
  return env;
}

test("日次メンテナンス: 書き込みの途中で止まったら(企業マスタが変わった可能性)、企業マスタを読む・書く後の手順をすべて止める", () => {
  const { called, ops, notices } = runMaintenance({ dnc: companyWriteError("write", true) });
  assert.deepEqual(called, ["backup", "dnc"]);
  const status = ops.find((o) => o.name === "日次メンテナンス");
  assert.equal(status.ok, false);
  assert.match(status.detail, /掘り起こしアラートの送信: 「お断り\(連絡不要\)の反映」で企業マスタの書き込みを止めたため、実行しませんでした\(企業マスタが途中まで書き換わっている可能性/);
  assert.equal(notices.length, 1);
});

test("日次メンテナンス: 書いた後の照合で止まったときも、後の手順をすべて止める", () => {
  const { called } = runMaintenance({ score: companyWriteError("verify", true) });
  assert.deepEqual(called, ["backup", "dnc", "score"]);
});

test("日次メンテナンス: 書く前の確認で止めた(企業マスタは変わっていない)ときは、書き直す手順だけ止め、読むだけの手順は続ける", () => {
  const { called, ops } = runMaintenance({ dnc: companyWriteError("precheck", false) });
  assert.deepEqual(called, ["backup", "dnc", "dashboard", "today", "wld02", "alerts"]);
  assert.match(ops.find((o) => o.name === "日次メンテナンス").detail, /スコア・ランクの再計算: .*実行しませんでした\(企業マスタは変わっていないが/);
});

test("日次メンテナンス: 文言が「企業マスタの書き込みを止めました」でも、エラー種別が無ければ止めない(文言では判断しない)", () => {
  const { called } = runMaintenance({ dnc: "企業マスタの書き込みを止めました。書き込みの途中で止まりました" });
  assert.deepEqual(called, ["backup", "dnc", "score", "dashboard", "today", "wld02", "alerts"]);
});

test("日次メンテナンス: 企業マスタと関係ない失敗(ダッシュボード)では、これまでどおり後の手順も動かす", () => {
  const { called } = runMaintenance({ dashboard: "Exception: なにかの失敗" });
  assert.deepEqual(called, ["backup", "dnc", "score", "dashboard", "today", "wld02", "alerts"]);
});

test("日次メンテナンス: どの手順にも、企業マスタを書く・読む・使わないの区分が付いている", () => {
  const text = src("../glow-ma/src/MaintenanceRunner.gs");
  const steps = text.match(/\{ name: "[^"]+", run: [A-Za-z0-9_]+(, master: "(write|read|none)")? \}/g) || [];
  assert.equal(steps.length, 7);
  assert.ok(steps.every((s) => /master: "(write|read|none)"/.test(s)), steps.join("\n"));
});

// --- 2026-11-15 独立レビューの指摘への対応(構造化エラー・照合中の失敗・ID空欄の行・一時エラーだけのやり直し) ---
const phaseOf = (fn) => { try { fn(); } catch (e) { return e.companyWrite; } return null; };

test("エラーには phase と dataChanged が付く: 書く前の確認は precheck・変更なし", () => {
  const { ctx, master } = setup(10);
  const info = phaseOf(() => ctx.writeCompanyRecords_(master, ctx.readCompanyRecords_(master).slice(0, 7)));
  assert.deepEqual({ ...info }, { phase: "precheck", dataChanged: false });
});

test("書き込みの途中で止まったら write・変更あり", () => {
  const { ctx, master } = setup(1200, { failWhen: (row) => (row >= 502 ? "throw" : null) });
  assert.deepEqual({ ...phaseOf(() => ctx.recalculateAllScores()) }, { phase: "write", dataChanged: true });
});

test("書いた後の読み直しが失敗しても、必ず verify として記録・通知して止める(余った行は消さない)", () => {
  const { ctx, master, ops, notices } = setup(30);
  const realGetRange = master.getRange;
  let wrote = false;
  master.getRange = (row, col, n, c) => {
    const r = realGetRange(row, col, n, c);
    return {
      ...r,
      setValues: (vals) => { wrote = true; return r.setValues(vals); },
      getValues: () => { if (wrote) throw new Error("Exception: Service Spreadsheets failed while accessing document"); return r.getValues(); },
    };
  };
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "verify", dataChanged: true });
  assert.match(err.message, /書いた後の照合の途中で、企業マスタの読み書きに失敗しました/);
  assert.equal(ops.find((o) => o.name === "企業マスタの書き込み").ok, false);
  assert.equal(notices.length, 1);
  assert.equal(master.clears, 0);
});

test("企業IDが空なのに値が入っている行(人の手入力)があれば、消さずに書く前に止める(途中の行も末尾の行も)", () => {
  for (const where of ["middle", "end"]) {
    const { ctx, master } = setup(20);
    const headers = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
    const handRow = headers.map(() => "");
    handRow[headers.indexOf("会社名")] = "架空の手入力会社";
    if (where === "middle") master.rows.splice(6, 0, handRow); else master.rows.push(handRow);
    const before = master.rows.map((r) => r.slice());
    const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
    assert.ok(err, where);
    assert.deepEqual({ ...err.companyWrite }, { phase: "precheck", dataChanged: false });
    assert.match(err.message, /企業IDが空なのに値が入っている行が 1行あります\((7|22)行目\)。消さないように止めました/);
    assert.deepEqual(master.rows, before, "企業マスタは1セルも変わっていない");
  }
});

test("未チェックのチェックボックス(false)だけの行は、手入力の行とみなさない", () => {
  const { ctx, master } = setup(5);
  const headers = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
  const boxRow = headers.map(() => "");
  boxRow[headers.indexOf("連絡不要")] = false;
  master.rows.push(boxRow);
  ctx.recalculateAllScores();
  assert.equal(idsOf(master).length, 5);
});

test("書いている間に下へ別の会社の行が足されたら、その行を消さずに止める", () => {
  const { ctx, master, notices } = setup(10);
  const headers = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
  const realGetRange = master.getRange;
  master.getRange = (row, col, n, c) => {
    const r = realGetRange(row, col, n, c);
    return { ...r, setValues: (vals) => {
      r.setValues(vals);
      const extra = headers.map(() => "");
      extra[0] = "C999999";
      master.rows.push(extra);
    } };
  };
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.equal(err.companyWrite.phase, "verify");
  assert.match(err.message, /書いた範囲より下に、消してはいけない行が残っています.*書いていない会社の行が残っています\(C999999\)/);
  assert.ok(idsOf(master).includes("C999999"), "足された会社は消えていない");
  assert.equal(notices.length, 1, "通知は1回だけ(止めた理由を包み直して二重に通知しない)");
  assert.doesNotMatch(err.message, /照合の途中で/);
});

test("やり直すのは一時的なエラーだけ: 権限・範囲の誤りはすぐに止める(待たない)", () => {
  const sheets = [];
  const env = makeContext(sheets);
  const master = fakeSheet("企業マスタ", masterRows(env.ctx, 600));
  sheets.push(master, fakeSheet("対応履歴ログ", [env.ctx.GlowSchema.INTERACTION_LOG_HEADERS.slice()]));
  const realGetRange = master.getRange;
  master.getRange = (row, col, n, c) => {
    const r = realGetRange(row, col, n, c);
    return { ...r, setValues: (vals) => { if (row === 502) throw new Error("Exception: 保護されている範囲を編集しようとしています"); return r.setValues(vals); } };
  };
  const err = (() => { try { env.ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.equal(err.companyWrite.phase, "write");
  assert.deepEqual(env.sleeps, [], "やり直さず、待たない");
});

test("やり直しの待ち時間には上限がある(合計20秒まで)。上限を超えるならやり直さずに止める", () => {
  // どのかたまりも、2回目までは一時的なエラーになる(1かたまりにつき 2秒+4秒 待つ)
  const tries = {};
  const { ctx, sleeps } = setup(3000, { failWhen: (row) => { tries[row] = (tries[row] || 0) + 1; return tries[row] <= 2 ? "throw" : null; } });
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.equal(err.companyWrite.phase, "write");
  const total = sleeps.reduce((a, b) => a + b, 0);
  assert.ok(total <= 20000, "待った合計 " + total);
  assert.ok(total >= 12000, "上限までは、やり直している");
});

test("行がずれる書き込み: 桁区切り・%・日付の書き方の違いでは止めない。先頭の0が消えたら止める", () => {
  const { ctx, master } = setup(12);
  const headers = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
  const col = (h) => headers.indexOf(h);
  const records = withoutSecond(ctx, master);
  records[2]["規模"] = "1,200";
  records[3]["規模"] = "12%";
  records[5]["登録日"] = "2026/10/1";
  records[6]["電話番号"] = "0980123456";
  const realGetRange = master.getRange;
  // シートの癖をまねる: 桁区切り・%は数値に、日付は Date に、先頭0の番号は数値に変わる
  master.getRange = (row, c0, n, c) => {
    const r = realGetRange(row, c0, n, c);
    return { ...r, setValues: (vals) => r.setValues(vals.map((v) => v.map((x) => {
      if (x === "1,200") return 1200;
      if (x === "12%") return 0.12;
      if (x === "2026/10/1") return new Date("2026-10-01T00:00:00+09:00");
      if (x === "0980123456") return 980123456;
      return x;
    }))) };
  };
  const err = (() => { try { ctx.writeCompanyRecords_(master, records, { allowRemovedIds: ["C900002"], backupSheetName: BACKUP }); } catch (e) { return e; } })();
  assert.ok(err, "先頭の0が消えた電話番号で止まる");
  assert.match(err.message, /書いた内容と違う行が 1行あります\(\d+行目 C900008: 電話番号\)/);
  assert.equal(col("電話番号") >= 0, true);
});

// --- 2026-11-15 最終安全審査: 数式 ---
test("企業マスタに数式のセルがあれば、書き直すと数式が消えるため、書く前に止める(1セルも変えない)", () => {
  const { ctx, master, notices } = setup(20);
  const scoreCol = ctx.GlowSchema.COMPANY_MASTER_HEADERS.indexOf("総合スコア") + 1;
  master.formulas["8," + scoreCol] = "=M8+N8";
  const before = master.rows.map((r) => r.slice());
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "precheck", dataChanged: false });
  assert.match(err.message, /数式が入っているセルが 1か所あります\(8行目の総合スコア\)/);
  assert.deepEqual(master.rows, before);
  assert.equal(master.writes, 0);
  assert.equal(notices.length, 1);
});

test("数式の有無を確かめられなければ(読み取りの失敗)、書かずに止める", () => {
  const { ctx, master } = setup(5);
  const real = master.getRange;
  master.getRange = (...a) => ({ ...real(...a), getFormulas: () => { throw new Error("Service Spreadsheets failed"); } });
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.equal(err.companyWrite.phase, "precheck");
  assert.match(err.message, /数式の有無を確かめられませんでした/);
  assert.equal(master.writes, 0);
});

test("「=」で始まる文字を書こうとしたら、数式として入って元の文字が消えるため、書く前に止める", () => {
  const { ctx, master } = setup(10);
  const records = ctx.readCompanyRecords_(master);
  records[3]["備考"] = "=要確認";
  const before = master.rows.map((r) => r.slice());
  const err = (() => { try { ctx.writeCompanyRecords_(master, records); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "precheck", dataChanged: false });
  assert.match(err.message, /「=」で始まる文字が 1か所あります\(5行目の備考\)/);
  assert.doesNotMatch(err.message, /要確認/, "値は通知に出さない");
  assert.deepEqual(master.rows, before);
});

// --- 2026-11-15 最終安全審査: 本番と同じ規模(約3千社 × 33列)の合成データ ---
// 既定は3,300社(本番の社数は公開リポジトリに書かない)。GLOW_SCALE_ROWS で社数を変えて試せる
// 列の型は本番の企業マスタに合わせる(登録日・最終接触日は日付、スコアは数値、連絡不要は真偽値、
// 電話番号は先頭が0の文字。値はすべて架空)
const SCALE = Number(process.env.GLOW_SCALE_ROWS || 3300);
function fullMasterRows(ctx, n) {
  const H = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
  const rows = [H.slice()];
  for (let i = 1; i <= n; i++) {
    const v = {
      "企業ID": "C9" + String(i).padStart(5, "0"), "会社名": "架空商事" + i, "業種": ["建設業", "福祉", "飲食"][i % 3],
      "代表者名": "架空 代表" + i, "所在地": "架空市" + (i % 41), "流入ルート": i % 5 ? "②手紙DM" : "①紹介",
      "現在ステージ": "未接触", "提案商品": i % 7 ? "" : "法人保険", "初期スコア": i % 30, "反応スコア": i % 4,
      "総合スコア": 0, "ランク": "", "最終接触日": i % 30 ? "" : new Date(2026, 9, 1 + (i % 28)),
      "次回アクション予定日": i === 77 ? new Date(2026, 10, 20) : "", "担当者": i % 2 ? "架空担当A" : "",
      "登録日": i % 800 ? new Date(2026, 7, 1 + (i % 28)) : "", "備考": i % 9 ? "" : "架空の備考" + i,
      "電話番号": i % 15 ? "098-" + String(100 + (i % 900)) + "-" + String(i).padStart(4, "0") : "",
      "連絡不要": i % 400 === 0, "事前選定ランク": i % 3 ? "B" : "", "事前選定スコア": i % 3 ? i % 50 : "",
    };
    rows.push(H.map((h) => (h in v ? v[h] : "")));
  }
  return rows;
}
function scaleSetup(opts = {}) {
  const sheets = [];
  const env = makeContext(sheets);
  const master = fakeSheet("企業マスタ", fullMasterRows(env.ctx, SCALE), opts);
  sheets.push(master, fakeSheet("対応履歴ログ", [env.ctx.GlowSchema.INTERACTION_LOG_HEADERS.slice()]));
  return { ...env, master, before: master.rows.map((r) => r.slice()) };
}
const H_OF = (ctx) => ctx.GlowSchema.COMPANY_MASTER_HEADERS;
const SCORE_COLS = ["初期スコア", "反応スコア", "総合スコア", "ランク"];
// スコア再計算で変わってよい列以外が、1セルも変わっていないこと
function assertUntouchedExceptScores(ctx, before, after, label) {
  const H = H_OF(ctx);
  const keep = H.map((h, j) => (SCORE_COLS.includes(h) ? -1 : j)).filter((j) => j >= 0);
  for (let r = 1; r <= SCALE; r++) {
    for (const j of keep) {
      const a = before[r][j], b = after[r][j];
      const same = a instanceof Date ? b instanceof Date && a.getTime() === b.getTime() : a === b;
      if (!same) assert.fail(label + ": " + (r + 1) + "行目の" + H[j] + "が変わった");
    }
  }
}
const lostIds = (before, master, except = []) => {
  const now = new Set(idsOf(master));
  return before.slice(1).map((r) => r[0]).filter((id) => !now.has(id) && !except.includes(id));
};

test("約3千社×33列 通常のスコア再計算: 全社が残り、スコア以外の30列は1セルも変わらない。読み書きの回数を数える", (t) => {
  const { ctx, master, before, ops, sleeps } = scaleSetup();
  ctx.recalculateAllScores();
  assert.deepEqual(lostIds(before, master), []);
  assert.equal(idsOf(master).length, SCALE);
  assertUntouchedExceptScores(ctx, before, master.rows, "通常");
  assert.equal(master.writes, 7, "500行ずつ7回に分けて書く");
  assert.ok(master.reads <= 6, "読み取りは6回まで: " + master.reads);
  assert.equal(master.clears, 0, "余った行が無ければ消さない");
  assert.deepEqual(sleeps, []);
  assert.equal(ops.find((o) => o.name === "企業マスタの書き込み").ok, true);
  t.diagnostic("通常: 書き込み " + master.writes + "回 / 読み取り " + master.reads + "回 / 待ち 0秒");
});

test("約3千社×33列 書き込みの途中(4かたまり目)で失敗し続ける: 会社は1社も消えず、書いていない行は元のまま", (t) => {
  const { ctx, master, before, notices, sleeps } = scaleSetup({ failWhen: (row) => (row >= 1502 ? "throw" : null) });
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "write", dataChanged: true });
  assert.deepEqual(lostIds(before, master), []);
  assert.equal(idsOf(master).length, SCALE);
  assertUntouchedExceptScores(ctx, before, master.rows, "途中失敗");
  assert.deepEqual(master.rows.slice(1501), before.slice(1501), "書いていない1501行目以降は、スコアも含めて元のまま");
  assert.equal(master.clears, 0);
  assert.equal(notices.length, 1);
  t.diagnostic("途中失敗: 待ち合計 " + sleeps.reduce((a, b) => a + b, 0) / 1000 + "秒");
});

test("約3千社×33列 1回の書き込みが前半だけ反映されて失敗する: 会社は消えず、行は混ざらない", () => {
  const { ctx, master, before } = scaleSetup({ failWhen: (row) => (row === 1502 ? "partial" : null) });
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.equal(err.companyWrite.phase, "write");
  assert.deepEqual(lostIds(before, master), []);
  assertUntouchedExceptScores(ctx, before, master.rows, "部分書き込み");
});

test("約3千社×33列 どのかたまりも1回だけ一時的に失敗する: やり直して最後まで書き、待ちは合計14秒(上限20秒以内)", (t) => {
  const seen = {};
  const { ctx, master, before, sleeps } = scaleSetup({ failWhen: (row) => (seen[row] ? null : ((seen[row] = 1), "throw")) });
  ctx.recalculateAllScores();
  assert.deepEqual(lostIds(before, master), []);
  assertUntouchedExceptScores(ctx, before, master.rows, "やり直し");
  assert.deepEqual(sleeps, Array(7).fill(2000));
  t.diagnostic("やり直し: 書き込み " + master.writes + "回 / 待ち合計 " + sleeps.reduce((a, b) => a + b, 0) / 1000 + "秒");
});

test("約3千社×33列 一時的な失敗が続いて待ちの上限に達したら、それ以上待たずに止める(会社は消えない)", () => {
  const tries = {};
  const { ctx, master, before, sleeps } = scaleSetup({ failWhen: (row) => ((tries[row] = (tries[row] || 0) + 1) <= 2 ? "throw" : null) });
  const err = (() => { try { ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.equal(err.companyWrite.phase, "write");
  assert.ok(sleeps.reduce((a, b) => a + b, 0) <= 20000);
  assert.deepEqual(lostIds(before, master), []);
  assertUntouchedExceptScores(ctx, before, master.rows, "上限");
});

test("約3千社×33列 名寄せの統合(行がずれる)が1行の途中で止まる: 統合した会社のほかは1社も消えず、混ざった行を数えて止める", () => {
  const { ctx, master, before } = scaleSetup({ failWhen: (row) => (row === 1002 ? "cellpartial" : null) });
  const records = ctx.readCompanyRecords_(master).filter((r) => r["企業ID"] !== "C900100");
  const err = (() => { try { ctx.writeCompanyRecords_(master, records, { allowRemovedIds: ["C900100"], backupSheetName: BACKUP }); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "write", dataChanged: true });
  assert.match(err.message, /別の会社の値が混ざった行が 1行/);
  assert.match(err.message, new RegExp(BACKUP));
  assert.deepEqual(lostIds(before, master, ["C900100"]), [], "止まった時点でも、どの会社の行も台帳のどこかに残っている");
});

test("約3千社×33列 名寄せの統合が最後まで書けたら、全33列を照合して通る(日付・数値・真偽値・先頭0の電話番号で誤って止めない)", () => {
  const { ctx, master, before } = scaleSetup();
  const records = ctx.readCompanyRecords_(master).filter((r) => r["企業ID"] !== "C900100");
  ctx.writeCompanyRecords_(master, records, { allowRemovedIds: ["C900100"], backupSheetName: BACKUP });
  assert.equal(idsOf(master).length, SCALE - 1);
  assert.deepEqual(lostIds(before, master, ["C900100"]), []);
  assert.equal(master.rows[SCALE].every((v) => v === ""), true, "ずれて余った最後の行は消える");
});

// --- 2026-11-16 時間切れ対策: 変わっていないかたまりは書かない・時間の歯止め・打ち切りの検知 ---
// 台帳の読み書きに時間がかかる日をまねる: 読み・書きのたびに、実行の経過時間(clock.ms)を進める
function slowSheet(env, { writeMs = 0, readMs = 0 } = {}) {
  const real = env.master.getRange;
  env.master.getRange = (...a) => {
    const r = real(...a);
    return {
      ...r,
      getValues: () => { env.clock.ms += readMs; return r.getValues(); },
      getFormulas: () => { env.clock.ms += readMs; return r.getFormulas(); },
      setValues: (v) => { env.clock.ms += writeMs; return r.setValues(v); },
    };
  };
  return env;
}

test("変わっていない日は、企業マスタに1回も書かない(2回目の再計算は書き込み0回・照合の読み直しもしない)", () => {
  const env = setup(1200);
  env.ctx.recalculateAllScores();
  const { writes, reads } = env.master;
  const snapshot = env.master.rows.map((r) => r.slice());
  env.ctx.recalculateAllScores();
  assert.equal(env.master.writes, writes, "2回目は書かない");
  assert.ok(env.master.reads - reads <= 3, "読むのは、会社の一覧と書く前の確認だけ: " + (env.master.reads - reads));
  assert.deepEqual(env.master.rows, snapshot);
  const last = env.ops.filter((o) => o.name === "企業マスタの書き込み").at(-1);
  assert.equal(last.ok, true);
  assert.match(last.detail, /1200社\(今の内容と同じため、書き込みはしていません\)/);
});

test("変わった行のあるかたまり(500行)だけを書く。ほかのかたまりには触れない", () => {
  const env = setup(1700);
  env.ctx.recalculateAllScores();
  const base = env.master.writes;
  const records = env.ctx.readCompanyRecords_(env.master);
  records[1203]["備考"] = "架空の備考(変更)";   // 3つ目のかたまり(1001〜1500社目)
  const ranges = [];
  const real = env.master.getRange;
  env.master.getRange = (row, col, n, c) => {
    const r = real(row, col, n, c);
    return { ...r, setValues: (v) => { ranges.push([row, n]); return r.setValues(v); } };
  };
  env.ctx.writeCompanyRecords_(env.master, records);
  assert.equal(env.master.writes - base, 1);
  assert.deepEqual(ranges, [[1002, 500]]);
  const noteCol = env.ctx.GlowSchema.COMPANY_MASTER_HEADERS.indexOf("備考");
  assert.equal(env.master.rows[1204][noteCol], "架空の備考(変更)");
  assert.match(env.ops.at(-1).detail, /変わっていない 3かたまりは書かず、1かたまりを書いた/);
});

test("末尾に会社を足すときは、足したかたまりだけを書く。行がずれる書き込みは、全部のかたまりを書く", () => {
  const env = setup(1000);
  env.ctx.recalculateAllScores();
  const base = env.master.writes;
  const records = env.ctx.readCompanyRecords_(env.master);
  for (const id of ["C901001", "C901002"]) records.push({ ...records[0], "企業ID": id, "会社名": "架空新規" + id });
  env.ctx.writeCompanyRecords_(env.master, records);
  assert.equal(env.master.writes - base, 1);
  assert.equal(idsOf(env.master).length, 1002);
  const base2 = env.master.writes;
  // 2つ目のかたまりの会社を外す(1つ目のかたまりは今と同じ内容だが、行がずれる書き込みでは飛ばさずに全部書く)
  const shifted = env.ctx.readCompanyRecords_(env.master).filter((r) => r["企業ID"] !== "C900700");
  env.ctx.writeCompanyRecords_(env.master, shifted, { allowRemovedIds: ["C900700"], backupSheetName: BACKUP });
  assert.equal(env.master.writes - base2, 3, "1,001社を500行ずつ3回(行がずれるので、同じに見えるかたまりも飛ばさない)");
});

test("時間の歯止め: 開始から180秒を過ぎていたら、書き込みを始めない(企業マスタは1セルも変わらない)", () => {
  const env = setup(600);
  env.clock.ms = 180001;
  const before = env.master.rows.map((r) => r.slice());
  const err = (() => { try { env.ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "precheck", dataChanged: false });
  assert.match(err.message, /始まってから 180秒たっており.*書き込みを始めませんでした。次の回に書きます/);
  assert.equal(env.master.writes, 0);
  assert.deepEqual(env.master.rows, before);
  assert.equal(env.notices.length, 1);
  // ちょうど180秒なら書く
  const ok = setup(600);
  ok.clock.ms = 180000;
  ok.ctx.recalculateAllScores();
  assert.ok(ok.master.writes >= 1);
});

test("時間の歯止め: 行がずれる書き込み(途中で止まると値が混ざる)は、90秒を過ぎたら始めない", () => {
  const env = setup(600);
  env.clock.ms = 90001;
  const before = env.master.rows.map((r) => r.slice());
  const records = withoutSecond(env.ctx, env.master);
  const err = (() => { try { env.ctx.writeCompanyRecords_(env.master, records, { allowRemovedIds: ["C900002"], backupSheetName: BACKUP }); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "precheck", dataChanged: false });
  assert.deepEqual(env.master.rows, before);
  // 同じ時刻でも、行がずれない書き込みなら始める
  env.ctx.recalculateAllScores();
  assert.ok(env.master.writes >= 1);
});

test("時間の歯止め: 書いている途中で時間切れが近づいたら、かたまりの区切りで自分で止めて通知する(打ち切られる前に)", () => {
  const env = slowSheet(setup(3300), { writeMs: 50000 });
  const before = env.master.rows.map((r) => r.slice());
  const err = (() => { try { env.ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "write", dataChanged: true });
  assert.match(err.message, /書き込みの途中で止まりました\(2500\/3300社まで済みました。会社の行の位置は変わらないため.*会社は消えていません。残りは次の回に書きます\)/);
  assert.match(err.message, /始まってから 250秒たっており、上限\(6分\)で打ち切られる前に、区切りで止めました/);
  assert.equal(env.master.writes, 5, "50秒かかるかたまりを5つ書いたところで止める(6つ目は、残り110秒 < 遅いかたまりの3倍)");
  assert.ok(env.clock.ms < 360000, "上限の前に止まっている: " + env.clock.ms);
  assert.deepEqual(idsOf(env.master), before.slice(1).map((r) => r[0]));
  assert.deepEqual(env.master.rows.slice(2501), before.slice(2501), "まだ書いていない行は元のまま");
  assert.equal(env.notices.length, 1);
  // 次の回(速い日)は、残りのかたまりだけを書いて終わる
  env.clock.ms = 0;
  slowSheet(env, { writeMs: 0 });
  const base = env.master.writes;
  env.ctx.recalculateAllScores();
  assert.equal(env.master.writes - base, 2, "前の回に書けた5かたまりは、もう同じなので書かない");
});

test("時間の歯止め: 書く前の読み取りが遅くて時間が無くなったら、1つも書かずに止める(変更なしとして報告)", () => {
  const env = slowSheet(setup(600), { readMs: 160000 });
  const before = env.master.rows.map((r) => r.slice());
  const err = (() => { try { env.ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.equal(err.companyWrite.dataChanged, false);
  assert.equal(env.master.writes, 0);
  assert.deepEqual(env.master.rows, before);
});

test("時間の歯止め: 書き始める直前に時間が無くなったら(1かたまりも書いていない)、変更なしとして止める", () => {
  const env = setup(600);
  const before = env.master.rows.map((r) => r.slice());
  // 書く前の確認の時点では100秒、最初のかたまりを書こうとした時点では310秒(その間に時間が飛んだ)
  let calls = 0;
  env.ctx.executionElapsedMs_ = () => (calls++ === 0 ? 100000 : 310000);
  const err = (() => { try { env.ctx.recalculateAllScores(); } catch (e) { return e; } })();
  assert.deepEqual({ ...err.companyWrite }, { phase: "write", dataChanged: false });
  assert.match(err.message, /0\/600社まで済みました/);
  assert.equal(env.master.writes, 0);
  assert.deepEqual(env.master.rows, before);
});

test("日次メンテナンス: 「実行中」の印は、動いている手順の名前を持ち、最後まで来たら消える。開始と終了を記録する", () => {
  const seen = [];
  const r = runMaintenance({}, { onStep: (name, { store }) => seen.push(JSON.parse(store.DAILY_MAINTENANCE_RUNNING)) });
  assert.deepEqual(seen.map((s) => [s.step, s.master, s.done]), [
    ["台帳のバックアップ", "none", 0], ["お断り(連絡不要)の反映", "write", 1], ["スコア・ランクの再計算", "write", 2],
    ["ダッシュボードの更新", "read", 3], ["今日の連絡先の更新", "read", 4], ["世界の架け橋の週次KPI", "read", 5], ["掘り起こしアラートの送信", "read", 6],
  ]);
  assert.equal(r.store.DAILY_MAINTENANCE_RUNNING, undefined);
  assert.equal(r.logs[0], "日次メンテナンスを開始しました。");
  assert.equal(r.logs.at(-1), "日次メンテナンスを終了しました。");
  assert.deepEqual(r.ops, [{ name: "日次メンテナンス", ok: true, detail: "7件すべて完了" }]);
});

test("日次メンテナンス: 開始から270秒を過ぎたら、次の手順を始めない。失敗として記録・通知し、印は消す", () => {
  const r = runMaintenance({}, { onStep: (name, { clock }) => { if (name === "score") clock.ms = 270001; } });
  assert.deepEqual(r.called, ["backup", "dnc", "score"]);
  assert.equal(r.ops[0].ok, false);
  for (const name of ["ダッシュボードの更新", "今日の連絡先の更新", "世界の架け橋の週次KPI", "掘り起こしアラートの送信"]) {
    assert.match(r.ops[0].detail, new RegExp(name + ": この実行は始まってから 270秒たっており、上限\\(6分\\)が近いため、始めませんでした"));
  }
  assert.equal(r.notices.length, 1);
  assert.equal(r.store.DAILY_MAINTENANCE_RUNNING, undefined);
  assert.equal(r.logs.filter((l) => /時間切れが近いため始めませんでした/.test(l)).length, 4);
  assert.equal(r.logs.filter((l) => /すべて完了/.test(l)).length, 0);
});

const T0 = Date.parse("2026-11-16T07:32:22+09:00");

test("打ち切りの検知(今回の形): 7手順のあと、最後の記録の途中で打ち切られた → 後の別の実行が見つけて、失敗として記録・通知する", () => {
  // 最後の記録(稼働状況タブへの書き込み)が返ってこないまま打ち切られたことを、例外でまねる
  const r = runMaintenance({}, { nowMs: T0, allowThrow: true, beforeRun: (ctx) => { ctx.recordOpsStatus_ = () => { throw new Error("(ここで実行が打ち切られた)"); }; } });
  assert.ok(r.thrown);
  const left = JSON.parse(r.store.DAILY_MAINTENANCE_RUNNING);
  assert.deepEqual([left.step, left.done, left.startedAtMs], ["", 7, T0], "印が残っている");
  // 5分後の毎分の処理: まだ知らせない(動いている最中かもしれない)
  r.ctx.recordOpsStatus_ = (name, ok, detail) => r.ops.push({ name, ok, detail });
  r.setNow(T0 + 5 * 60 * 1000);
  assert.equal(r.ctx.checkDailyMaintenanceStale_(), false);
  assert.equal(r.notices.length, 0);
  // 9分後の毎分の処理: 打ち切りを見つける
  r.setNow(T0 + 9 * 60 * 1000);
  assert.equal(r.ctx.checkDailyMaintenanceStale_(), true);
  assert.equal(r.ops.at(-1).ok, false);
  assert.match(r.ops.at(-1).detail, /日次メンテナンスが途中で打ち切られました\(開始 2026-11-16 07:32。6分の上限、または異常終了\)。最後の記録の途中でした\(7\/7件が完了\)/);
  assert.match(r.ops.at(-1).detail, /企業マスタを書き直す手順の途中ではありません/);
  assert.equal(r.notices.length, 1);
  assert.equal(r.errors.length, 1, "実行記録にもエラーとして残す(自動点検が拾えるように)");
  assert.equal(r.store.DAILY_MAINTENANCE_RUNNING, undefined);
  // 次の分は、もう知らせない
  assert.equal(r.ctx.checkDailyMaintenanceStale_(), false);
  assert.equal(r.notices.length, 1);
});

test("打ち切りの検知: 企業マスタを書き直す手順の途中だったら、件数をバックアップと比べるよう知らせる", () => {
  const running = JSON.stringify({ startedAtMs: T0, startedAtText: "2026-11-16 07:32", step: "スコア・ランクの再計算", master: "write", done: 2 });
  const r = runMaintenance({}, { dontRun: true, nowMs: T0 + 9 * 60 * 1000, props: { DAILY_MAINTENANCE_RUNNING: running } });
  assert.equal(r.ctx.checkDailyMaintenanceStale_(), true);
  assert.match(r.ops[0].detail, /「スコア・ランクの再計算」の途中でした\(2\/7件が完了\)。企業マスタを書き直す手順の途中です.*会社は消えていないはずですが、企業マスタの件数を今朝のバックアップと比べてください/);
});

test("打ち切りの検知: 読めない印も、見逃さずに1回だけ知らせる。印が無ければ何もしない", () => {
  const r = runMaintenance({}, { dontRun: true, nowMs: T0, props: { DAILY_MAINTENANCE_RUNNING: "{壊れた値" } });
  assert.equal(r.ctx.checkDailyMaintenanceStale_(), true);
  assert.match(r.ops[0].detail, /記録が読めません/);
  assert.equal(r.ctx.checkDailyMaintenanceStale_(), false);
  const none = runMaintenance({}, { dontRun: true, nowMs: T0 });
  assert.equal(none.ctx.checkDailyMaintenanceStale_(), false);
  assert.equal(none.ops.length, 0);
});

test("打ち切られたまま誰も見つけていない印が残っていたら、次の日次メンテナンスが最初に知らせてから動く", () => {
  const running = JSON.stringify({ startedAtMs: T0 - 24 * 3600 * 1000, startedAtText: "2026-11-15 07:32", step: "ダッシュボードの更新", master: "read", done: 3 });
  const r = runMaintenance({}, { nowMs: T0, props: { DAILY_MAINTENANCE_RUNNING: running } });
  assert.equal(r.called.length, 7);
  assert.equal(r.ops[0].ok, false);
  assert.match(r.ops[0].detail, /開始 2026-11-15 07:32/);
  assert.deepEqual(r.ops.at(-1), { name: "日次メンテナンス", ok: true, detail: "7件すべて完了" });
  assert.equal(r.store.DAILY_MAINTENANCE_RUNNING, undefined);
});

test("「実行中」の印を付けられなくても(設定の読み書きの失敗)、日次メンテナンスは最後まで動く", () => {
  const r = runMaintenance({}, { beforeRun: (ctx) => { ctx.PropertiesService = { getScriptProperties: () => { throw new Error("Service unavailable"); } }; } });
  assert.equal(r.called.length, 7);
  assert.deepEqual(r.ops.at(-1), { name: "日次メンテナンス", ok: true, detail: "7件すべて完了" });
});

test("毎分の処理が、打ち切りの確認を呼んでいる(失敗しても毎分の処理は続ける)", () => {
  const text = src("../glow-ma/src/LineVoiceLogRunner.gs");
  const core = text.slice(text.indexOf("function processQueuedVoiceLogsCore_"));
  assert.match(core.slice(0, 900), /try \{\s*checkDailyMaintenanceStale_\(\);\s*\} catch \(error\) \{/);
});

test("約3千社×33列 遅い日(今回の朝と同じくらい): 変わっていない日は書かないので、時間切れに届かない", () => {
  const env = scaleSetup();
  env.ctx.recalculateAllScores();
  slowSheet(env, { writeMs: 13000, readMs: 3000 });   // 1かたまり13秒(7かたまりで約90秒。今朝の再計算は94秒)
  env.clock.ms = 16000;                                  // バックアップの後
  const base = env.master.writes;
  env.ctx.syncDoNotContactFlags();
  env.ctx.recalculateAllScores();
  assert.equal(env.master.writes, base, "お断りの反映も再計算も、変わっていなければ書かない");
  assert.ok(env.clock.ms < 60000, "経過 " + env.clock.ms / 1000 + "秒");
});

test("約3千社×33列 遅い日に全社のスコアが変わっても、上限の前に書き終えるか、区切りで止まる(会社は消えず、スコア以外の列は変わらない)", (t) => {
  for (const writeMs of [13000, 30000, 45000, 90000]) {
    const env = slowSheet(scaleSetup(), { writeMs, readMs: 3000 });
    const before = env.master.rows.map((r) => r.slice());
    env.clock.ms = 16000;
    const err = (() => { try { env.ctx.recalculateAllScores(); } catch (e) { return e; } })();
    assert.ok(env.clock.ms < 360000, writeMs + ": 経過 " + env.clock.ms);
    assert.deepEqual(lostIds(before, env.master), [], String(writeMs));
    assertUntouchedExceptScores(env.ctx, before, env.master.rows, "遅い日 " + writeMs);
    if (err) {
      assert.deepEqual({ ...err.companyWrite }, { phase: "write", dataChanged: true }, String(writeMs));
      assert.equal(env.notices.length, 1);
    }
    t.diagnostic("1かたまり" + writeMs / 1000 + "秒: " + (err ? "区切りで停止" : "書き終えた") + "(書いたかたまり " + env.master.writes + "/7・経過 " + Math.round(env.clock.ms / 1000) + "秒)");
  }
});

test("約3千社×33列 区切りで止まった次の日(速い日)は、残りだけを書いて全社がそろう", () => {
  const env = slowSheet(scaleSetup(), { writeMs: 60000 });
  const before = env.master.rows.map((r) => r.slice());
  assert.throws(() => env.ctx.recalculateAllScores(), /区切りで止めました/);
  const firstDay = env.master.writes;
  slowSheet(env, { writeMs: 0 });
  env.clock.ms = 0;
  env.ctx.recalculateAllScores();
  assert.equal(firstDay + (env.master.writes - firstDay), 7, "2日合わせて、7かたまりを1回ずつ");
  assert.deepEqual(lostIds(before, env.master), []);
  const scoreCol = env.ctx.GlowSchema.COMPANY_MASTER_HEADERS.indexOf("ランク");
  assert.ok(env.master.rows.slice(1, SCALE + 1).every((r) => r[scoreCol] !== ""), "全社にランクが入っている");
});
