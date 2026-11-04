// scripts/diagnosis_monitor.mjs の自己テスト。実行: node --test tests/diagnosis_monitor.test.mjs
// 本物の診断ページ(site/fukugiiro/shindan)を moradou.jp と同じURL配置でローカル配信し、
// 正常系が通ること、各異常系が「そのシナリオ固有の」エラーコードで落ちることを確かめる。
// 何でもエラーになれば合格、にしない(2026-11-03: パス違いで全シナリオが同じ接続失敗になり、
// 異常系8/8合格と誤報告した。正例が一度も通っていなかった)。
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE = path.join(ROOT, "site", "fukugiiro");
const SEIDO = path.join(ROOT, "data", "fukugiiro", "seido.json");
const SCRIPT = path.join(ROOT, "scripts", "diagnosis_monitor.mjs");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png" };

let scenario = "normal";
let seidoHits = 0;
let server;
let port;

function jstMinute(hoursAgo) {
  const d = new Date(Date.now() - hoursAgo * 3600000 + 9 * 3600000);
  return d.toISOString().slice(0, 16).replace("T", " ");
}

function seidoBody() {
  const db = JSON.parse(fs.readFileSync(SEIDO, "utf8"));
  // リポジトリ内のコピーの古さに左右されないよう、鮮度は場面ごとに決める
  db.updated_at = jstMinute(scenario === "seido_stale" ? 40 : 1);
  if (scenario === "seido_count_mismatch") db.count = db.items.length + 3;
  if (scenario === "seido_empty") { db.items = []; db.count = 0; }
  if (scenario === "seido_broken") return JSON.stringify(db).slice(0, 5000);
  return JSON.stringify(db);
}

function pageBody(file) {
  let html = fs.readFileSync(file, "utf8");
  const swap = (from, to) => {
    assert.ok(html.includes(from), `テスト前提が崩れています: 診断ページに ${from} がありません`);
    html = html.replace(from, to);
  };
  // 2026-11-02〜03 のP0と同じ壊れ方: moradou.jp に存在しないパスを読みに行く
  if (scenario === "p0_fetch_path") swap('fetch("../seido.json")', 'fetch("../../data/fukugiiro/seido.json")');
  if (scenario === "render_drops_card") swap("rs.forEach(function(r, idx){", "rs.slice(1).forEach(function(r, idx){");
  if (scenario === "browser_data_fail") swap("window.FGShindan.matchSeido(db.items", "window.FGShindan.matchSeid0(db.items");
  if (scenario === "js_syntax_error") swap("function render(){", "function render(){{");
  if (scenario === "no_event_map") swap("var EVENT_MAP", "var EVENT_TABLE");
  return html;
}

function logicBody(file) {
  const src = fs.readFileSync(file, "utf8");
  if (scenario !== "logic_returns_empty") return src;
  const out = src.replace("var api = { matchSeido: matchSeido,", "var api = { matchSeido: function(){ return []; },");
  assert.notEqual(out, src, "テスト前提が崩れています: logic.js の api 定義が見つかりません");
  return out;
}

function handle(req, res) {
  const url = new URL(req.url, "http://x");
  let p = decodeURIComponent(url.pathname);
  const send = (code, body, type) => { res.writeHead(code, { "Content-Type": type || "text/plain; charset=utf-8" }); res.end(body); };

  if (p === "/seido.json") {
    seidoHits++;
    if (scenario === "seido_404") return send(404, "not found");
    if (scenario === "seido_flaky_once" && seidoHits === 1) return send(503, "busy");
    if (scenario === "seido_timeout") return setTimeout(() => send(200, seidoBody(), TYPES[".json"]), 3000);
    return send(200, seidoBody(), TYPES[".json"]);
  }
  if (p.endsWith("/")) p += "index.html";
  const file = path.join(SITE, path.normalize(p));
  if (!file.startsWith(SITE) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return send(404, "not found");
  if (p === "/shindan/index.html") {
    if (scenario === "page_404") return send(404, "not found");
    if (scenario === "page_500") return send(500, "error");
    return send(200, pageBody(file), TYPES[".html"]);
  }
  if (p === "/shindan/logic.js") {
    if (scenario === "logic_404") return send(404, "not found");
    return send(200, logicBody(file), TYPES[".js"]);
  }
  return send(200, fs.readFileSync(file), TYPES[path.extname(file)] || "application/octet-stream");
}

before(async () => {
  server = http.createServer(handle);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  port = server.address().port;
});

after(() => server.close());

// 子プロセスで実行しないとサーバ(同じイベントループ)が応答できないため、非同期で起動する
function runMonitor(extraEnv = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "diagmon-"));
  const resultPath = path.join(dir, "result.json");
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [SCRIPT], {
      env: {
        ...process.env,
        DIAG_URL: `http://127.0.0.1:${port}/shindan/`,
        ATTEMPTS: "1",
        RETRY_WAIT_MS: "200",
        HTTP_TIMEOUT_MS: "1500",
        BROWSER_TIMEOUT_MS: "8000",
        REPORT_PATH: path.join(dir, "report.txt"),
        RESULT_PATH: resultPath,
        ...extraEnv,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let log = "";
    child.stdout.on("data", (d) => (log += d));
    child.stderr.on("data", (d) => (log += d));
    child.on("close", (code) => {
      if (!fs.existsSync(resultPath)) return reject(new Error(`結果ファイルが出ていません\n${log}`));
      resolve({ code, result: JSON.parse(fs.readFileSync(resultPath, "utf8")), log });
    });
  });
}

async function expectSignature(name, signature, extraEnv) {
  scenario = name;
  seidoHits = 0;
  const { code, result, log } = await runMonitor(extraEnv);
  assert.equal(result.signature, signature, `${name}: 期待 [${signature || "正常"}] / 実際 [${result.signature || "正常"}]\n${log}`);
  assert.equal(code, signature ? 1 : 0, `${name}: 終了コードが違います\n${log}`);
  return result;
}

// 正例を最初に確かめる。ここが落ちる間は、下の異常系の合格に意味がない
test("正常: 本物の診断ページが通り、表示件数が本番ロジックと完全一致する", async () => {
  const r = await expectSignature("normal", "");
  const browserNotes = r.notes.filter((n) => n.startsWith("ブラウザ"));
  assert.equal(browserNotes.length, 3, r.notes.join("\n"));
  assert.ok(!browserNotes[0].startsWith("ブラウザ naha_kosodate: 0件"), "必ず該当がある回答で0件");
});

const CASES = [
  ["page_404", "PAGE_HTTP_404", "診断ページが404"],
  ["page_500", "PAGE_HTTP_500", "診断ページが500"],
  ["p0_fetch_path", "SEIDO_HTTP_404", "fetchのパスずれ(2026-11のP0)"],
  ["seido_404", "SEIDO_HTTP_404", "seido.jsonが404"],
  ["seido_timeout", "SEIDO_TIMEOUT", "seido.jsonがタイムアウト"],
  ["seido_broken", "SEIDO_JSON_BROKEN", "seido.jsonが途中で切れている"],
  ["seido_count_mismatch", "SEIDO_COUNT_MISMATCH", "countとitems件数の不一致"],
  ["seido_stale", "SEIDO_STALE", "データが30時間より古い"],
  ["seido_empty", "LOGIC_ZERO,SEIDO_EMPTY", "制度0件"],
  ["logic_404", "LOGIC_HTTP_404", "logic.jsが404"],
  ["logic_returns_empty", "LOGIC_ZERO", "ロジックが常に0件を返す"],
  ["no_event_map", "PAGE_STRUCTURE", "ページ構造の変更"],
  ["render_drops_card", "BROWSER_COUNT_MISMATCH", "画面のカードが1枚欠ける"],
  ["browser_data_fail", "BROWSER_DATA_LOAD_FAILED", "ブラウザ内で結果の計算に失敗"],
  ["js_syntax_error", "BROWSER_FLOW,BROWSER_JS_ERROR", "インラインJSの構文エラー"],
];

for (const [name, sig, label] of CASES) {
  test(`異常: ${label} → ${sig}`, async () => {
    await expectSignature(name, sig);
  });
}

test("再試行: 1回目だけ503なら、再試行で正常に戻り通知しない", async () => {
  const r = await expectSignature("seido_flaky_once", "", { ATTEMPTS: "2" });
  assert.deepEqual(r.attempts, ["SEIDO_HTTP_503", "OK"]);
});

test("再試行: 2回とも失敗なら異常として残る", async () => {
  const r = await expectSignature("seido_404", "SEIDO_HTTP_404", { ATTEMPTS: "2" });
  assert.deepEqual(r.attempts, ["SEIDO_HTTP_404", "SEIDO_HTTP_404"]);
});
