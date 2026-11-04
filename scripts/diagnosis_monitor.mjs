#!/usr/bin/env node
// もらいわすれ堂の診断ページ(moradou.jp/shindan/)の死活監視。15分ごとに diagnosis-monitor.yml から実行する。
// 判定の基準は「本番で配信中の logic.js と seido.json を Node で実行した件数」で、
// 実ブラウザで本番ページを操作して画面に出た件数がこれと1件でも違えば異常(誤差0件)。
// 終了コード: 0=正常 / 1=異常。結果は REPORT_PATH(人向け)と RESULT_PATH(機械向けJSON)に書く。
import { createRequire } from "node:module";
import fs from "node:fs";
import vm from "node:vm";

const require = createRequire(import.meta.url);

const PAGE_URL = process.env.DIAG_URL || "https://moradou.jp/shindan/";
const STALE_HOURS = Number(process.env.STALE_HOURS || 30);
const HTTP_TIMEOUT_MS = Number(process.env.HTTP_TIMEOUT_MS || 20000);
const BROWSER_TIMEOUT_MS = Number(process.env.BROWSER_TIMEOUT_MS || 25000);
const ATTEMPTS = Number(process.env.ATTEMPTS || 2);
const RETRY_WAIT_MS = Number(process.env.RETRY_WAIT_MS || 60000);
const REPORT_PATH = process.env.REPORT_PATH || "diagnosis_monitor_report.txt";
const RESULT_PATH = process.env.RESULT_PATH || "diagnosis_monitor_result.json";
const UA = "moradou-diagnosis-monitor/1.0 (+https://github.com/allgroup-inc/hojo-hq)";

// mustHit: 本番データで必ず1件以上出るはずの回答。0件なら全員が「該当なし」を見ている
export const PATTERNS = [
  { key: "naha_kosodate", muni: "那覇市", children: 2, ages: ["未就学", "小学生"], events: ["入園・入学"], housing: "賃貸", mustHit: true },
  { key: "ishigaki_koukou", muni: "石垣市", children: 1, ages: ["高校生"], events: ["引越・住宅購入", "就職・転職"], housing: "持ち家" },
  { key: "kengai_nashi", muni: "県外", children: 0, ages: [], events: ["特になし"], housing: null },
];

function fail(errors, code, msg) {
  errors.push({ code, msg });
}

async function httpGet(url) {
  const t0 = Date.now();
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": UA, "Cache-Control": "no-cache" },
      signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
    });
    const body = await res.text();
    return { status: res.status, body, ms: Date.now() - t0 };
  } catch (e) {
    // 取得できなかった(タイムアウト・DNS・接続断)は「内容が違う」と区別して記録する
    const kind = e && e.name === "TimeoutError" ? "TIMEOUT" : "UNREACHABLE";
    return { status: null, kind, error: String(e && e.message ? e.message : e), ms: Date.now() - t0 };
  }
}

function httpProblem(errors, label, codePrefix, r, url) {
  if (r.status === 200) return false;
  if (r.status === null) {
    fail(errors, `${codePrefix}_${r.kind}`, `${label}を取得できません(${r.kind === "TIMEOUT" ? "タイムアウト" : "接続失敗"} ${r.ms}ms): ${url} — ${r.error}`);
  } else {
    fail(errors, `${codePrefix}_HTTP_${r.status}`, `${label}が HTTP ${r.status} を返しました: ${url}`);
  }
  return true;
}

function parseJstMinute(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/.exec(s || "");
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] - 9, +m[5]));
}

function loadLogic(source) {
  const sandbox = { module: { exports: {} } };
  sandbox.exports = sandbox.module.exports;
  sandbox.globalThis = sandbox;
  vm.runInNewContext(source, sandbox, { timeout: 2000 });
  const api = sandbox.module.exports;
  if (!api || typeof api.matchSeido !== "function") throw new Error("matchSeido が公開されていません");
  return api;
}

// ページのインライン定義(EVENT_MAP)をそのまま使う。回答→ロジック入力の変換を検査側で作り直さないため
function extractEventMap(html) {
  const m = /var EVENT_MAP\s*=\s*(\{[^;]*\});/.exec(html);
  if (!m) return null;
  try {
    return JSON.parse(m[1]);
  } catch {
    return null;
  }
}

function expectedCount(api, items, eventMap, p) {
  const answers = {
    municipality: p.muni,
    children: p.children,
    childAges: p.ages,
    lifeEvents: p.events.map((e) => eventMap[e]).filter(Boolean),
  };
  return api.matchSeido(items, answers).length;
}

async function checkHttpAndData(errors, notes) {
  const page = await httpGet(PAGE_URL);
  if (httpProblem(errors, "診断ページ", "PAGE", page, PAGE_URL)) return null;
  notes.push(`診断ページ 200 (${page.body.length} bytes, ${page.ms}ms)`);
  const html = page.body;

  const fetchM = /fetch\("([^"]*seido\.json[^"]*)"\)/.exec(html);
  const logicM = /<script src="([^"]*logic\.js[^"]*)"/.exec(html);
  const eventMap = extractEventMap(html);
  if (!html.includes('id="app"')) fail(errors, "PAGE_STRUCTURE", '診断ページに描画先(id="app")がありません');
  if (!fetchM) fail(errors, "PAGE_STRUCTURE", "診断ページに seido.json の読み込み処理がありません");
  if (!logicM) fail(errors, "PAGE_STRUCTURE", "診断ページに logic.js の読み込みがありません");
  if (!eventMap) fail(errors, "PAGE_STRUCTURE", "診断ページの EVENT_MAP を読み取れません(ページ構造の変更)");
  if (!fetchM || !logicM || !eventMap) return null;

  // ブラウザと同じ解決規則で、ページが実際に取りに行くURLを求める(2026-11 のP0はここが404だった)
  const seidoUrl = new URL(fetchM[1], PAGE_URL).href;
  const logicUrl = new URL(logicM[1], PAGE_URL).href;

  const [seido, logic] = await Promise.all([httpGet(seidoUrl), httpGet(logicUrl)]);
  const seidoBad = httpProblem(errors, "制度データ(seido.json)", "SEIDO", seido, seidoUrl);
  const logicBad = httpProblem(errors, "診断ロジック(logic.js)", "LOGIC", logic, logicUrl);
  if (seidoBad || logicBad) return null;

  let db;
  try {
    db = JSON.parse(seido.body);
  } catch (e) {
    fail(errors, "SEIDO_JSON_BROKEN", `seido.json が壊れています(JSONとして読めない): ${String(e.message).slice(0, 120)}`);
    return null;
  }
  const items = db && db.items;
  if (!Array.isArray(items)) {
    fail(errors, "SEIDO_SCHEMA", "seido.json に items(配列)がありません");
    return null;
  }
  if (db.count !== undefined && db.count !== items.length) {
    fail(errors, "SEIDO_COUNT_MISMATCH", `seido.json の count(${db.count}) と items の件数(${items.length}) が一致しません`);
  }
  if (items.length === 0) fail(errors, "SEIDO_EMPTY", "seido.json の制度が0件です");

  const upd = parseJstMinute(db.updated_at);
  if (!upd) {
    fail(errors, "SEIDO_UPDATED_AT", `seido.json の updated_at を読み取れません: ${JSON.stringify(db.updated_at)}`);
  } else {
    const ageH = (Date.now() - upd.getTime()) / 3600000;
    if (ageH > STALE_HOURS) {
      fail(errors, "SEIDO_STALE", `制度データが古い: 最終更新 ${db.updated_at}(${ageH.toFixed(1)}時間前、基準${STALE_HOURS}時間)`);
    } else {
      notes.push(`seido.json ${items.length}件 / 最終更新 ${db.updated_at}(${ageH.toFixed(1)}時間前) / ${seido.ms}ms`);
    }
  }

  let api;
  try {
    api = loadLogic(logic.body);
  } catch (e) {
    fail(errors, "LOGIC_BROKEN", `logic.js を実行できません: ${String(e.message).slice(0, 160)}`);
    return null;
  }

  const expected = {};
  for (const p of PATTERNS) {
    try {
      expected[p.key] = expectedCount(api, items, eventMap, p);
    } catch (e) {
      fail(errors, "LOGIC_BROKEN", `matchSeido が例外を出しました(${p.key}): ${String(e.message).slice(0, 160)}`);
      return null;
    }
    if (p.mustHit && expected[p.key] === 0) {
      fail(errors, "LOGIC_ZERO", `必ず該当があるはずの回答(${p.key})で0件です。全員に「該当なし」が出ている可能性`);
    }
  }
  return { expected, origin: new URL(PAGE_URL).origin };
}

async function clickButton(page, name) {
  await page.getByRole("button", { name, exact: true }).first().click({ timeout: BROWSER_TIMEOUT_MS });
}

async function runPattern(browser, origin, p) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: "ja-JP", userAgent: UA });
  // 監視の操作をGA4等の利用実績に混ぜない(15分ごと×回答パターン数の偽の診断完了が計上されるため)
  await ctx.route("**/*", (route) => {
    const u = new URL(route.request().url());
    return u.origin === origin ? route.continue() : route.abort();
  });
  const page = await ctx.newPage();
  const jsErrors = [];
  page.on("pageerror", (err) => jsErrors.push(String(err && err.message ? err.message : err)));
  try {
    await page.goto(PAGE_URL, { waitUntil: "domcontentloaded", timeout: BROWSER_TIMEOUT_MS });
    await page.locator("#muni").waitFor({ timeout: BROWSER_TIMEOUT_MS });
    await page.selectOption("#muni", p.muni);
    await clickButton(page, `お子さん ${p.children >= 3 ? "3人以上" : p.children + "人"}`);
    if (p.children > 0) {
      for (const a of p.ages) await clickButton(page, a);
      await clickButton(page, "つぎへ");
    }
    for (const ev of p.events) await clickButton(page, ev);
    await clickButton(page, "つぎへ");
    if (p.housing) await clickButton(page, p.housing);
    await clickButton(page, "診断結果を見る");

    const heading = page.locator("#app h2", { hasText: "制度:" });
    const loadErr = page.getByText("データの読み込みに失敗しました");
    await Promise.race([
      heading.waitFor({ timeout: BROWSER_TIMEOUT_MS }),
      loadErr.waitFor({ timeout: BROWSER_TIMEOUT_MS }),
    ]);
    if (await loadErr.count()) return { loadFailed: true, jsErrors };
    const text = (await heading.first().textContent()) || "";
    const m = /制度:\s*(\d+)件/.exec(text);
    const cards = await page.locator("#app .result-card").count();
    return { shown: m ? Number(m[1]) : null, cards, jsErrors };
  } catch (e) {
    return { stuck: String(e && e.message ? e.message : e).split("\n")[0].slice(0, 200), jsErrors };
  } finally {
    await ctx.close();
  }
}

async function checkBrowser(errors, notes, ctx) {
  const { chromium } = require("playwright");
  const browser = await chromium.launch();
  try {
    for (const p of PATTERNS) {
      const exp = ctx.expected[p.key];
      const r = await runPattern(browser, ctx.origin, p);
      if (r.jsErrors.length) fail(errors, "BROWSER_JS_ERROR", `診断ページでJSエラー(${p.key}): ${r.jsErrors[0].slice(0, 160)}`);
      if (r.stuck) {
        fail(errors, "BROWSER_FLOW", `診断の操作が途中で進めません(${p.key}): ${r.stuck}`);
      } else if (r.loadFailed) {
        fail(errors, "BROWSER_DATA_LOAD_FAILED", `ブラウザで「データの読み込みに失敗しました」が表示されました(${p.key})`);
      } else if (r.shown !== exp || r.cards !== exp) {
        fail(errors, "BROWSER_COUNT_MISMATCH", `表示件数が本番ロジックの結果と一致しません(${p.key}): 期待${exp}件 / 見出し${r.shown}件 / カード${r.cards}枚`);
      } else {
        notes.push(`ブラウザ ${p.key}: ${exp}件(見出し・カードとも一致)`);
      }
    }
  } finally {
    await browser.close();
  }
}

export async function checkOnce() {
  const errors = [];
  const notes = [];
  const ctx = await checkHttpAndData(errors, notes);
  // HTTP・データで落ちていてもブラウザ検査は行わない(原因が1つなら通知も1種類にするため)
  if (ctx && errors.length === 0) await checkBrowser(errors, notes, ctx);
  return { errors, notes };
}

export function signatureOf(errors) {
  return [...new Set(errors.map((e) => e.code))].sort().join(",");
}

async function main() {
  const started = new Date();
  const history = [];
  let result;
  for (let i = 1; i <= ATTEMPTS; i++) {
    result = await checkOnce();
    history.push(signatureOf(result.errors) || "OK");
    if (result.errors.length === 0 || i === ATTEMPTS) break;
    // 一瞬の配信揺れで鳴らさない: 時間を置いてもう一度だけ確かめる
    await new Promise((r) => setTimeout(r, RETRY_WAIT_MS));
  }
  const ok = result.errors.length === 0;
  const out = {
    ok,
    signature: signatureOf(result.errors),
    url: PAGE_URL,
    checked_at: started.toISOString(),
    attempts: history,
    errors: result.errors,
    notes: result.notes,
  };
  const lines = [
    `もらいわすれ堂 診断ページ監視 — ${ok ? "正常" : "異常"}`,
    `対象: ${PAGE_URL}`,
    `時刻(UTC): ${started.toISOString().slice(0, 16).replace("T", " ")}`,
    `試行: ${history.join(" → ")}`,
    "",
    ...result.errors.map((e) => `ERROR [${e.code}] ${e.msg}`),
    ...result.notes.map((n) => `ok    ${n}`),
  ];
  fs.writeFileSync(RESULT_PATH, JSON.stringify(out, null, 1) + "\n");
  fs.writeFileSync(REPORT_PATH, lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  process.exitCode = ok ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => {
    console.error(e);
    process.exitCode = 1;
  });
}
