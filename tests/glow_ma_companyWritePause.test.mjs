// 企業マスタの書き込みの緊急停止スイッチ(companyWritePause.js・CompanyWritePauseRunner.gs)の試験。
// 台帳・設定・画面・メールはすべて偽物。会社名・ID・メールアドレスはすべて架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const P = require("../glow-ma/src/companyWritePause.js");
const src = (name) => readFileSync(new URL("../glow-ma/src/" + name, import.meta.url), "utf8");

const OWNER = "owner@example.invalid";
const STAFF = "staff@example.invalid";

// ---------- 判定だけの試験 ----------

test("状態の読み取り: 未設定は稼働中。正しい記録は停止中。読めない値・形の違う値は停止中として扱う(止まる側)", () => {
  assert.deepEqual(P.parseState(null), { paused: false });
  assert.deepEqual(P.parseState(""), { paused: false });
  const s = P.parseState(P.buildStopState("2026-11-16 09:00", STAFF, "件数が合わない"));
  assert.deepEqual(s, { paused: true, at: "2026-11-16 09:00", by: STAFF, reason: "件数が合わない" });
  for (const broken of ["{", "true", "0", '{"paused":false}', '{"paused":"yes"}', "停止"]) {
    const b = P.parseState(broken);
    assert.equal(b.paused, true, broken);
    assert.equal(b.unreadable, true, broken);
  }
});

test("理由・承認の記録は必須。空・空白だけは通さない。長すぎる分は切る", () => {
  assert.equal(P.validateNote("").ok, false);
  assert.equal(P.validateNote("  \n ").ok, false);
  assert.equal(P.validateNote(null).ok, false);
  assert.deepEqual(P.validateNote("  件数が\n合わない "), { ok: true, note: "件数が 合わない" });
  assert.equal(P.validateNote("あ".repeat(500)).note.length, 120);
});

test("再開できるのは台帳の持ち主だけ。アドレスが分からないときは断る", () => {
  assert.equal(P.canResume(OWNER, OWNER).ok, true);
  assert.equal(P.canResume("Owner@Example.Invalid", OWNER).ok, true, "大文字・小文字の違いは同じ人");
  assert.equal(P.canResume(STAFF, OWNER).ok, false);
  assert.match(P.canResume(STAFF, OWNER).reason, /持ち主\(代表者\)だけ/);
  assert.equal(P.canResume("", OWNER).ok, false);
  assert.equal(P.canResume(OWNER, "").ok, false);
  assert.equal(P.canResume("", "").ok, false, "どちらも分からないときに、同じ人とみなさない");
});

test("再開の合い言葉は「再開」だけ", () => {
  assert.equal(P.isResumePhrase("再開"), true);
  assert.equal(P.isResumePhrase(" 再開 "), true);
  for (const x of ["", "再開する", "はい", "resume", "さいかい", null]) assert.equal(P.isResumePhrase(x), false, String(x));
});

test("操作の記録: 新しい順に足し、件数と長さの上限を超えた古い分を落とす", () => {
  let h = "";
  for (let i = 1; i <= 30; i++) h = P.appendHistory(h, { at: "2026-11-16 09:" + String(i).padStart(2, "0"), action: "stop", by: STAFF, note: "理由" + i });
  const list = P.readHistory(h);
  assert.equal(list.length, P.HISTORY_MAX_ENTRIES);
  assert.equal(list[0].note, "理由30");
  let long = "";
  for (let i = 0; i < 12; i++) long = P.appendHistory(long, { at: "2026-11-16 09:00", action: "stop", by: "x".repeat(200) + "@example.invalid", note: "あ".repeat(120) });
  assert.ok(long.length <= P.HISTORY_MAX_CHARS, "長さ " + long.length);
  assert.ok(P.readHistory(long).length >= 1);
  assert.deepEqual(P.readHistory("壊れた値"), []);
  assert.match(P.describeHistory(h), /2026-11-16 09:30 停止 \/ staff@example\.invalid \/ 理由30/);
  assert.equal(P.describeHistory(""), "(操作の記録はありません)");
});

test("停止からの日数: 日本時間の記録から数える。分からなければ -1", () => {
  const state = P.parseState(P.buildStopState("2026-11-16 09:00", STAFF, "理由"));
  assert.equal(P.pausedDays(state, Date.parse("2026-11-16T10:00:00+09:00")), 0);
  assert.equal(P.pausedDays(state, Date.parse("2026-11-19T09:30:00+09:00")), 3);
  assert.equal(P.pausedDays({ paused: true, at: "" }, Date.now()), -1);
  assert.equal(P.pausedDays({ paused: false }, Date.now()), -1);
});

// ---------- 台帳を偽物にして動かす試験 ----------

function fakeSheet(name, rows) {
  const s = {
    name, rows: rows.map((r) => r.slice()), writes: 0, reads: 0, clears: 0,
    getName: () => name,
    setFrozenRows() {},
    appendRow: (row) => { s.writes++; s.rows.push(row.slice()); },
    getLastRow: () => {
      for (let i = s.rows.length - 1; i >= 0; i--) {
        if ((s.rows[i] || []).some((v) => v !== "" && v !== null && v !== undefined)) return i + 1;
      }
      return 0;
    },
    getRange: (row, col, nRows = 1, nCols = 1) => ({
      getFormulas: () => { s.reads++; return Array.from({ length: nRows }, () => Array.from({ length: nCols }, () => "")); },
      getValues: () => { s.reads++; return Array.from({ length: nRows }, (_, i) => Array.from({ length: nCols }, (_, j) => {
        const v = (s.rows[row - 1 + i] || [])[col - 1 + j];
        return v === undefined ? "" : v;
      })); },
      setValues: (vals) => {
        s.writes++;
        vals.forEach((v, i) => { const t = s.rows[row - 1 + i] || []; v.forEach((x, j) => { t[col - 1 + j] = x; }); s.rows[row - 1 + i] = t; });
      },
      clearContent: () => { s.clears++; },
    }),
  };
  return s;
}

// 画面の偽物。answers に、YES/NO の答えと入力欄の答えを順に入れておく
function fakeUi(answers) {
  const shown = [];
  const ui = {
    Button: { YES: "YES", NO: "NO", OK: "OK", CANCEL: "CANCEL" },
    ButtonSet: { YES_NO: "YES_NO", OK_CANCEL: "OK_CANCEL", OK: "OK_ONLY" },
    shown,
    alert: (title, message, buttons) => {
      shown.push({ kind: "alert", title, message });
      return buttons === "OK_ONLY" ? "OK" : answers.shift();
    },
    prompt: (title, message) => {
      shown.push({ kind: "prompt", title, message });
      const a = answers.shift() || { button: "CANCEL", text: "" };
      return { getSelectedButton: () => a.button, getResponseText: () => a.text };
    },
    createMenu: (name) => {
      const menu = { name, items: [], addItem: (label, fn) => { menu.items.push({ label, fn }); return menu; }, addSeparator: () => menu, addToUi: () => { ui.menu = menu; } };
      return menu;
    },
  };
  return ui;
}

function setup({ companies = 30, actor = OWNER, props = {}, propsThrow = false, answers = [] } = {}) {
  const store = { ...props };
  const mails = [];
  const logs = [];
  const toasts = [];
  const sheets = [];
  const state = { actor, now: "2026-11-16 09:00", today: "2026-11-16" };
  const ui = fakeUi(answers);
  const ss = {
    getSheetByName: (n) => sheets.find((s) => s.name === n) || null,
    insertSheet: (n) => { const s = fakeSheet(n, []); sheets.push(s); return s; },
    getOwner: () => ({ getEmail: () => OWNER }),
    toast: (message, title) => toasts.push({ message, title }),
  };
  const ctx = {
    console: { log() {}, warn() {} },
    Logger: { log: (m) => logs.push(String(m)) },
    Utilities: { sleep() {}, formatDate: (_d, _tz, f) => (f === "yyyy-MM-dd" ? state.today : state.now) },
    LockService: { getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }) },
    Session: { getEffectiveUser: () => ({ getEmail: () => state.actor }) },
    MailApp: { sendEmail: (to, subject, body) => mails.push({ to, subject, body }) },
    PropertiesService: { getScriptProperties: () => {
      if (propsThrow) throw new Error("Service unavailable");
      return {
        getProperty: (k) => (k in store ? store[k] : null),
        setProperty: (k, v) => { store[k] = String(v); },
        deleteProperty: (k) => { delete store[k]; },
      };
    } },
    SpreadsheetApp: { flush() {}, getActiveSpreadsheet: () => ss, getUi: () => ui },
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of ["schema.js", "scoring.js", "dedupe.js", "companyWriteGuard.js", "companyWritePause.js"]) vm.runInContext(src(f), ctx);
  for (const f of ["OpsStatus.gs", "ImportRunner.gs", "ScoringRunner.gs", "DncRunner.gs", "PreScreeningRunner.gs", "PhaseATestRunner.gs",
    "HistoricalDataImporter.gs", "MaintenanceRunner.gs", "ShareRunner.gs", "CompanyWritePauseRunner.gs"]) vm.runInContext(src(f), ctx);
  const H = ctx.GlowSchema.COMPANY_MASTER_HEADERS;
  const rows = [H.slice()];
  for (let i = 1; i <= companies; i++) {
    const r = H.map(() => "");
    r[H.indexOf("企業ID")] = "C9" + String(i).padStart(5, "0");
    r[H.indexOf("会社名")] = "架空商事" + i;
    r[H.indexOf("電話番号")] = "098-000-" + String(i).padStart(4, "0");
    r[H.indexOf("総合スコア")] = 0;
    rows.push(r);
  }
  const master = fakeSheet("企業マスタ", rows);
  const log = fakeSheet("対応履歴ログ", [ctx.GlowSchema.INTERACTION_LOG_HEADERS.slice()]);
  sheets.push(master, log);
  const opsRows = () => (ss.getSheetByName("稼働状況")?.rows || []).slice(1);
  const opsOf = (name) => opsRows().find((r) => r[0] === name);
  return { ctx, store, mails, logs, toasts, sheets, master, log, ui, state, opsOf, before: master.rows.map((r) => r.slice()) };
}

const thrown = (fn) => { try { fn(); } catch (e) { return e; } return null; };
const stopAnswers = (reason = "件数が合わないため") => ["YES", { button: "OK", text: reason }];
const stopped = (extra = {}) => {
  const env = setup({ actor: STAFF, answers: stopAnswers(), ...extra });
  env.ctx.stopCompanyWrites();
  return env;
};

test("止める: 確認と理由のあと、停止の状態・履歴・稼働状況・お知らせが残る。担当者が止めても、お知らせは台帳の持ち主へ届く", () => {
  const { store, mails, opsOf, ui, ctx } = stopped();
  const state = P.parseState(store[P.STATE_PROPERTY]);
  assert.deepEqual(state, { paused: true, at: "2026-11-16 09:00", by: STAFF, reason: "件数が合わないため" });
  assert.equal(P.readHistory(store[P.HISTORY_PROPERTY]).length, 1);
  assert.equal(P.readHistory(store[P.HISTORY_PROPERTY])[0].action, "stop");
  assert.equal(opsOf(P.OPS_NAME)[2], "停止中");
  assert.match(opsOf(P.OPS_NAME)[3], /停止 2026-11-16 09:00/);
  assert.equal(mails.length, 1);
  assert.equal(mails[0].to, OWNER);
  assert.match(mails[0].subject, /企業マスタの書き込みを止めました/);
  assert.match(mails[0].body, /自動では再開しません/);
  assert.match(ui.shown.at(-1).title, /止めました/);
  // もう一度止めても、何も変わらない(履歴もお知らせも増えない)
  ctx.stopCompanyWrites();
  assert.equal(P.readHistory(store[P.HISTORY_PROPERTY]).length, 1);
  assert.equal(mails.length, 1);
  assert.match(ui.shown.at(-1).title, /すでに止まっています/);
});

test("止める操作の取り消し: 確認で「いいえ」・理由の取り消し・理由が空なら、止まらない", () => {
  // 「いいえ」のあとに理由の答えを積んでおく(確認を飛ばして理由の入力へ進んだら、止まってしまうことが分かるように)
  for (const answers of [["NO", { button: "OK", text: "理由" }], ["YES", { button: "CANCEL", text: "理由" }], ["YES", { button: "OK", text: "   " }]]) {
    const { ctx, store, mails } = setup({ answers });
    ctx.stopCompanyWrites();
    assert.equal(store[P.STATE_PROPERTY], undefined);
    assert.equal(store[P.HISTORY_PROPERTY], undefined);
    assert.equal(mails.length, 0);
  }
});

test("停止中: スコアの再計算・お断りの反映は、企業マスタを1セルも読まず・書かずに止まる。失敗の通知は出さない", () => {
  const { ctx, master, before, mails } = stopped({ companies: 3300 });
  const mailsAfterStop = mails.length;
  for (const fn of ["recalculateAllScores", "syncDoNotContactFlags"]) {
    const reads = master.reads;
    const err = thrown(() => ctx[fn]());
    assert.ok(err, fn);
    assert.deepEqual({ ...err.companyWrite }, { phase: "paused", dataChanged: false, paused: true });
    assert.match(err.message, /停止中のため、書きませんでした\(企業マスタは変更していません\)/);
    assert.match(err.message, /代表者の承認の後/);
    assert.equal(master.writes, 0, fn);
    assert.equal(master.clears, 0, fn);
    // 読むだけ(会社の一覧を読む)は構わないが、書き込みの中の読み直しは起きない
    assert.ok(master.reads - reads <= 1, fn + " reads " + (master.reads - reads));
  }
  assert.deepEqual(master.rows, before);
  assert.equal(mails.length, mailsAfterStop, "停止中に書こうとしても、失敗の通知は出さない");
});

test("停止中: インポート・事前選定・フェーズA試験は、バックアップのタブや試験データを作る前に止まる", () => {
  const { ctx, sheets, log, master, before } = stopped();
  // 対応履歴ログの見出しを崩しておく(フェーズA試験は最初に見出しを直す。停止中は、それもしない)
  log.rows[0][0] = "崩れた見出し";
  const tabs = sheets.map((s) => s.name).join(",");
  for (const fn of ["importCompaniesFromStaging", "applyPreScreeningScores", "runPhaseATest"]) {
    const err = thrown(() => ctx[fn]());
    assert.ok(err, fn);
    assert.equal(err.companyWrite && err.companyWrite.paused, true, fn + ": " + err.message);
  }
  assert.equal(sheets.map((s) => s.name).join(","), tabs, "タブは増えていない");
  assert.equal(log.writes, 0, "対応履歴ログには何も書いていない(見出しの直しも、試験データも)");
  assert.deepEqual(master.rows, before);
});

test("停止中: 過去記録の取り込みは試さない。貼られた行は残り、稼働状況に「停止中」と出る。失敗の通知は出さない", () => {
  const { ctx, sheets, mails, opsOf } = stopped();
  const staging = fakeSheet(ctx.FUKUDA_STAGING_SHEET_NAME, [["会社名", "日付"], ["架空商事1", "2026/11/1"]]);
  sheets.push(staging);
  let attempted = 0;
  for (const helper of ["restageYearlessHistoryOnce_", "mergeOldArchiveSheetsOnce_", "updateStagingHeadersIfEmpty_", "restageMissedRowsOnce_"]) ctx[helper] = () => {};
  ctx.historyImportSlotDue_ = () => true;
  ctx.runHistoryImport_ = () => { attempted++; return null; };
  const mailsBefore = mails.length;
  assert.equal(ctx.runHistoryImportIfPending_(), null);
  assert.equal(attempted, 0);
  assert.equal(staging.rows.length, 2);
  assert.equal(opsOf("過去の手紙・架電記録の取り込み")[2], "停止中");
  assert.equal(mails.length, mailsBefore);
});

function maintenanceSpies(ctx, failing = {}) {
  const called = [];
  const step = (name) => () => { called.push(name); if (failing[name]) throw new Error(failing[name]); };
  Object.assign(ctx, {
    backupLedger: step("backup"), syncDoNotContactFlags: step("dnc"), recalculateAllScores: step("score"),
    updateDashboard: step("dashboard"), updateTodayList: step("today"), runWld02WeeklyIfDue_: step("wld02"), runDailyAlerts: step("alerts"),
  });
  return called;
}

test("停止中の日次メンテナンス: バックアップと読むだけの手順は続け、書く手順(お断りの反映・再計算)だけ見送る。失敗とは記録しない", () => {
  const { ctx, opsOf, mails, logs, state } = stopped();
  const called = maintenanceSpies(ctx);
  state.now = "2026-11-19 07:32"; state.today = "2026-11-19";
  // 台帳のコードが見る「今」を、停止(11/16 09:00)から丸3日たった後にする
  vm.runInContext("Date.now = () => " + Date.parse("2026-11-19T09:30:00+09:00"), ctx);
  ctx.runDailyMaintenance(); ctx.runDailyMaintenance();
  assert.deepEqual(called, ["backup", "dashboard", "today", "wld02", "alerts", "backup", "dashboard", "today", "wld02", "alerts"]);
  const row = opsOf("日次メンテナンス");
  assert.equal(row[2], "停止中");
  assert.match(row[3], /5件完了 \/ 見送り 2件\(お断り\(連絡不要\)の反映・スコア・ランクの再計算\): 企業マスタの書き込みが停止中/);
  assert.match(opsOf(P.OPS_NAME)[3], /停止から 3日/);
  const reminders = mails.filter((m) => /停止中です/.test(m.subject));
  assert.equal(reminders.length, 1, "同じ日に2回動いても、お知らせは1通");
  assert.equal(reminders[0].to, OWNER);
  assert.match(reminders[0].body, /お断り\(連絡不要\)の反映も止まっています/);
  // LINE の自動点検(PR #617)は「が失敗しました」の記録で知らせる。見送りでは、その記録を出さない
  assert.equal(logs.filter((l) => /が失敗しました/.test(l)).length, 0);
  assert.equal(logs.filter((l) => /日次メンテナンスがすべて完了しました/.test(l)).length, 0, "見送りがある日は「すべて完了」とは書かない");
  assert.equal(logs.filter((l) => /停止中のため見送りました/.test(l)).length, 4);
});

test("停止中に別の手順が失敗したら、日次メンテナンスは失敗として記録し、見送りも併せて書く", () => {
  const { ctx, opsOf } = stopped();
  maintenanceSpies(ctx, { alerts: "Slack に送れませんでした" });
  ctx.runDailyMaintenance();
  const row = opsOf("日次メンテナンス");
  assert.equal(row[2], "失敗");
  assert.match(row[3], /掘り起こしアラートの送信: Error: Slack に送れませんでした \/ 見送り 2件/);
});

test("止めていない日の日次メンテナンスは、これまでどおり7件すべて動く", () => {
  const { ctx, opsOf, mails } = setup();
  const called = maintenanceSpies(ctx);
  ctx.runDailyMaintenance();
  assert.deepEqual(called, ["backup", "dnc", "score", "dashboard", "today", "wld02", "alerts"]);
  assert.equal(opsOf("日次メンテナンス")[2], "成功");
  assert.equal(mails.length, 0);
});

test("再開: 台帳の持ち主でなければ断る(停止のまま)。断ったことも履歴に残る", () => {
  const { ctx, store, ui } = stopped();
  ctx.resumeCompanyWrites();
  assert.equal(P.parseState(store[P.STATE_PROPERTY]).paused, true);
  assert.match(ui.shown.at(-1).title, /再開できません/);
  assert.equal(P.readHistory(store[P.HISTORY_PROPERTY])[0].action, "resume_refused");
  assert.equal(P.readHistory(store[P.HISTORY_PROPERTY])[0].by, STAFF);
});

test("再開: 持ち主でも、合い言葉が違う・取り消した・承認の記録が空なら、停止のまま", () => {
  const cases = [
    [{ button: "OK", text: "はい" }],
    [{ button: "CANCEL", text: "再開" }],
    [{ button: "OK", text: "再開" }, { button: "OK", text: "  " }],
    [{ button: "OK", text: "再開" }, { button: "CANCEL", text: "承認済み" }],
  ];
  for (const answers of cases) {
    const env = stopped();
    env.state.actor = OWNER;
    // 画面の答えを積み直す
    const ui2 = fakeUi(answers.slice());
    env.ctx.SpreadsheetApp.getUi = () => ui2;
    env.ctx.resumeCompanyWrites();
    assert.equal(P.parseState(env.store[P.STATE_PROPERTY]).paused, true, JSON.stringify(answers));
    assert.equal(P.readHistory(env.store[P.HISTORY_PROPERTY]).filter((h) => h.action === "resume").length, 0);
  }
});

test("再開: 持ち主が「再開」と入力し、承認の記録を書いたときだけ再開する。履歴・稼働状況・お知らせに残り、書き込みが動く", () => {
  const env = stopped();
  env.state.actor = OWNER;
  env.state.now = "2026-11-17 10:00";
  const ui2 = fakeUi([{ button: "OK", text: "再開" }, { button: "OK", text: "11/17 件数の一致を確認・代表者承認" }]);
  env.ctx.SpreadsheetApp.getUi = () => ui2;
  env.ctx.resumeCompanyWrites();
  assert.equal(env.store[P.STATE_PROPERTY], undefined);
  const h = P.readHistory(env.store[P.HISTORY_PROPERTY]);
  assert.deepEqual(h.map((x) => x.action), ["resume", "stop"]);
  assert.equal(h[0].by, OWNER);
  assert.equal(h[0].note, "11/17 件数の一致を確認・代表者承認");
  assert.equal(env.opsOf(P.OPS_NAME)[2], "稼働中");
  assert.match(env.opsOf(P.OPS_NAME)[3], /承認の記録: 11\/17 件数の一致を確認・代表者承認/);
  assert.match(env.mails.at(-1).subject, /再開しました/);
  assert.match(ui2.shown[0].message, /「再開」と入力してください/);
  // 再開の後は、書き込みが動く
  env.ctx.recalculateAllScores();
  assert.ok(env.master.writes >= 1);
  // 止まっていないときの再開は、何もしない
  const ui3 = fakeUi([]);
  env.ctx.SpreadsheetApp.getUi = () => ui3;
  env.ctx.resumeCompanyWrites();
  assert.match(ui3.shown[0].title, /止まっていません/);
});

test("自動では再開しない: 日がたっても、日次メンテナンスが何度動いても、停止のまま", () => {
  const { ctx, store, state } = stopped();
  maintenanceSpies(ctx);
  for (const day of ["2026-11-17", "2026-11-25", "2026-12-25", "2027-06-01"]) {
    state.today = day; state.now = day + " 07:32";
    ctx.runDailyMaintenance();
    assert.equal(P.parseState(store[P.STATE_PROPERTY]).paused, true, day);
  }
  // 停止の記録を消すのは、再開の操作(resumeCompanyWrites)の1か所だけ
  const all = readdirSync(new URL("../glow-ma/src/", import.meta.url)).filter((f) => /\.(gs|js)$/.test(f)).map(src).join("\n");
  assert.equal((all.match(/deleteProperty\(GlowCompanyWritePause\.STATE_PROPERTY\)/g) || []).length, 1);
  assert.equal((all.match(/COMPANY_WRITE_PAUSE"/g) || []).length, 1, "プロパティ名を直接書く場所は定義の1か所だけ");
  const runner = src("CompanyWritePauseRunner.gs");
  const resume = runner.slice(runner.indexOf("function resumeCompanyWrites"), runner.indexOf("function showCompanyWritePauseStatus"));
  assert.match(resume, /deleteProperty\(GlowCompanyWritePause\.STATE_PROPERTY\)/);
});

test("止まる側に倒す: 停止の記録が壊れている・設定を読めないときは、書かない", () => {
  for (const extra of [{ props: { [P.STATE_PROPERTY]: "{壊れた値" } }, { propsThrow: true }]) {
    const { ctx, master, before } = setup(extra);
    const err = thrown(() => ctx.recalculateAllScores());
    assert.equal(err.companyWrite.paused, true);
    assert.equal(master.writes, 0);
    assert.deepEqual(master.rows, before);
  }
  // 壊れた記録の上からでも、止める操作で正しい停止の記録に直せる
  const env = setup({ props: { [P.STATE_PROPERTY]: "{壊れた値" }, answers: stopAnswers("記録が壊れていたため") });
  env.ctx.stopCompanyWrites();
  assert.equal(P.parseState(env.store[P.STATE_PROPERTY]).unreadable, undefined);
  assert.equal(P.parseState(env.store[P.STATE_PROPERTY]).reason, "記録が壊れていたため");
});

test("メニューを開けないとき: エディタから止められる(画面を使わない)。再開の関数はメニュー用の1つだけ", () => {
  const { ctx, store, mails } = setup({ actor: OWNER });
  ctx.emergencyStopCompanyWrites();
  const s = P.parseState(store[P.STATE_PROPERTY]);
  assert.equal(s.paused, true);
  assert.equal(s.reason, "エディタからの緊急停止");
  assert.equal(mails.length, 1);
  ctx.emergencyStopCompanyWrites();
  assert.equal(mails.length, 1, "2回目は何も変えない");
});

test("メニューと、台帳を開いたときのお知らせ", () => {
  const env = stopped();
  env.ctx.onOpen();
  const labels = env.ui.menu.items.map((i) => i.label + "→" + i.fn);
  for (const want of ["企業マスタの書き込みを止める(緊急停止)→stopCompanyWrites", "企業マスタの書き込みを再開する(代表者のみ)→resumeCompanyWrites", "企業マスタの書き込みの状態・履歴を見る→showCompanyWritePauseStatus"]) {
    assert.ok(labels.includes(want), want);
  }
  for (const fn of ["stopCompanyWrites", "resumeCompanyWrites", "showCompanyWritePauseStatus"]) assert.equal(typeof env.ctx[fn], "function", fn);
  assert.equal(env.toasts.length, 1);
  assert.match(env.toasts[0].title, /停止中です/);
  env.ctx.showCompanyWritePauseStatus();
  assert.match(env.ui.shown.at(-1).message, /停止中\(停止 2026-11-16 09:00/);
  assert.match(env.ui.shown.at(-1).message, /直近の操作:\n2026-11-16 09:00 停止/);
  // 止まっていないときは、開いても何も出さない。お知らせが出せなくても、台帳は開ける
  const running = setup();
  running.ctx.onOpen();
  assert.equal(running.toasts.length, 0);
  const broken = stopped();
  broken.ctx.SpreadsheetApp.getActiveSpreadsheet().toast = () => { throw new Error("toast failed"); };
  broken.ctx.onOpen();
});

test("企業マスタを一括で書き直す処理は、すべて停止スイッチを通る(writeCompanyRecords_ の最初で確かめる)", () => {
  const runner = src("ImportRunner.gs");
  const body = runner.slice(runner.indexOf("function writeCompanyRecords_("));
  const firstStatement = body.slice(body.indexOf("{") + 1).split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("//"))[0];
  assert.equal(firstStatement, "assertCompanyWriteNotPaused_();");
  // シートを全部消してから書く・複数行をまとめて書く処理が、企業マスタに対して writeCompanyRecords_ の外に無いこと
  const others = readdirSync(new URL("../glow-ma/src/", import.meta.url)).filter((f) => f.endsWith(".gs") && f !== "ImportRunner.gs");
  for (const f of others) {
    assert.doesNotMatch(src(f), /(companySheet|masterSheet)\.getRange\([^;]*\)\.clearContent\(/, f);
  }
});

test("稼働状況の結果の欄: 真偽値はこれまでどおり「成功・失敗」、文字はそのまま出る", () => {
  const { ctx, opsOf } = setup();
  ctx.recordOpsStatus_("架空の処理A", true, "ok");
  ctx.recordOpsStatus_("架空の処理B", false, "ng");
  ctx.recordOpsStatus_("架空の処理C", "停止中", "paused");
  assert.equal(opsOf("架空の処理A")[2], "成功");
  assert.equal(opsOf("架空の処理B")[2], "失敗");
  assert.equal(opsOf("架空の処理C")[2], "停止中");
});
