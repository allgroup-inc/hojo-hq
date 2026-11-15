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
  for (const f of ["schema.js", "scoring.js", "dedupe.js", "companyWriteGuard.js", "companyWritePause.js"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
  for (const f of ["ImportRunner.gs", "ScoringRunner.gs", "DncRunner.gs", "CompanyWritePauseRunner.gs"]) vm.runInContext(src("../glow-ma/src/" + f), ctx);
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

function runMaintenance(failing) {
  const called = [];
  const ops = [];
  const notices = [];
  const step = (name) => () => {
    called.push(name);
    const f = failing[name];
    if (f) throw typeof f === "string" ? new Error(f) : f;
  };
  const ctx = {
    Logger: { log() {} },
    backupLedger: step("backup"), syncDoNotContactFlags: step("dnc"), recalculateAllScores: step("score"),
    updateDashboard: step("dashboard"), updateTodayList: step("today"), runWld02WeeklyIfDue_: step("wld02"), runDailyAlerts: step("alerts"),
    recordOpsStatus_: (name, ok, detail) => ops.push({ name, ok, detail }),
    notifyOpsFailure_: (name, message) => notices.push({ name, message }),
    readCompanyWritePause_: () => ({ paused: false }),
  };
  vm.createContext(ctx);
  vm.runInContext(src("../glow-ma/src/MaintenanceRunner.gs"), ctx);
  ctx.runDailyMaintenance();
  return { called, ops, notices };
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
