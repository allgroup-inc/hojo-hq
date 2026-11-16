// 公式ページが無い(404/410)出典のリンクだけを止める表示を、実ブラウザで確かめる(scripts/fg_source_status.py)。
// 実行: node --test tests/source_unavailable.test.mjs(Playwright 1.56.1 が必要)
// 診断ページ(site/fukugiiro/shindan/)とトップ(site/fukugiiro/index.html)を手元で配信し、
// 制度データの1件に source_unavailable を付けたときに、リンクの代わりに「公式ページを確認中」が出ること、
// 付けていない制度はこれまでどおりリンクが出ることを見る。外部への通信は遮断する。
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE = path.join(ROOT, "site", "fukugiiro");
const db = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "fukugiiro", "seido.json"), "utf-8"));
const LABEL = "公式ページを確認中";
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png" };

let server, port, marked = new Set(), stamp = "";

function fixture() {
  const d = structuredClone(db);
  // 鮮度の検査で落ちないよう、更新時刻を今にする
  d.updated_at = stamp;
  for (const it of d.items) {
    // 実データに付いている印(収集の結果)は外し、このテストで選んだ制度だけに付ける
    if (marked.has(it.id)) it.source_unavailable = { since: "2026-11-04 10:21", reason: "公式ページが見つかりません(HTTP 404)" };
    else delete it.source_unavailable;
  }
  return JSON.stringify(d);
}

function handle(req, res) {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p === "/fukugiiro/seido.json" || p === "/data/fukugiiro/seido.json") {
    res.writeHead(200, { "Content-Type": TYPES[".json"] });
    return res.end(fixture());
  }
  let f = p.startsWith("/fukugiiro/") ? path.join(SITE, p.slice("/fukugiiro/".length)) : path.join(ROOT, p);
  if (f.endsWith("/")) f = path.join(f, "index.html");
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
    res.writeHead(404);
    return res.end("not found");
  }
  res.writeHead(200, { "Content-Type": TYPES[path.extname(f)] || "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
}

let browser;
before(async () => {
  const jst = new Date(Date.now() + 9 * 3600e3);
  stamp = jst.toISOString().slice(0, 16).replace("T", " ");
  server = http.createServer(handle);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  port = server.address().port;
  const { chromium } = require("playwright");
  browser = await chromium.launch();
});
after(async () => {
  if (browser) await browser.close();
  server.close();
});

async function open(url) {
  const ctx = await browser.newContext();
  const origin = `http://127.0.0.1:${port}`;
  await ctx.route("**/*", (route) => (new URL(route.request().url()).origin === origin ? route.continue() : route.abort()));
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${origin}${url}`, { waitUntil: "domcontentloaded" });
  return { ctx, page, errors };
}

async function diagnose(page) {
  const click = (name) => page.getByRole("button", { name, exact: true }).first().click();
  await page.locator("#muni").waitFor();
  await page.selectOption("#muni", "那覇市");
  await click("お子さん 2人");
  await click("未就学");
  await click("小学生");
  await click("つぎへ");
  await click("入園・入学");
  await click("つぎへ");
  await click("賃貸");
  await click("診断結果を見る");
  await page.locator("#app h2", { hasText: "制度:" }).waitFor();
}

test("診断ページ: 印のある制度はリンクの代わりに「公式ページを確認中」、他はリンクのまま", async () => {
  // まず印なしで、結果に出る制度を1つ選ぶ
  marked = new Set();
  let { ctx, page, errors } = await open("/fukugiiro/shindan/");
  await diagnose(page);
  const names = await page.locator("#app .result-card h3").allTextContents();
  assert.ok(names.length >= 2, "結果が2件以上出ること");
  const target = db.items.find((it) => it.name === names[0].trim()) || db.items.find((it) => names[0].includes(it.name));
  assert.ok(target, "結果の制度をデータから引けること");
  const before = await page.locator(`#app .result-card a[href="${target.source_url}"]`).count();
  assert.ok(before >= 1, "印なしでは公式ページへのリンクが出る");
  await ctx.close();

  marked = new Set([target.id]);
  ({ ctx, page, errors } = await open("/fukugiiro/shindan/"));
  await diagnose(page);
  const card = page.locator("#app .result-card", { has: page.locator("h3", { hasText: target.name }) }).first();
  assert.equal(await card.locator(`a[href="${target.source_url}"]`).count(), 0, "印のある制度の公式リンクは出さない");
  assert.equal(await card.locator(".src-pending").textContent(), LABEL);
  assert.match(await card.textContent(), /制度が終わったという意味ではありません/);
  assert.match(await card.textContent(), /申請準備シート/, "申請準備シートへの導線は残す");
  const cards = await page.locator("#app .result-card").count();
  assert.equal(cards, names.length, "件数は変わらない(制度は削除しない)");
  const other = page.locator("#app .result-card", { has: page.locator("h3", { hasText: names[1].trim() }) }).first();
  assert.ok((await other.locator("a.cardlink").count()) >= 2, "他の制度は公式リンクのまま");
  assert.deepEqual(errors, []);
  await ctx.close();
});

test("トップ: 印のある制度は「公式ページを確認中」、他はリンクのまま", async () => {
  const shown = db.items.slice().sort((a, b) => (b.verified ? 1 : 0) - (a.verified ? 1 : 0)).slice(0, 4);
  marked = new Set([shown[0].id]);
  const { ctx, page, errors } = await open("/fukugiiro/index.html");
  await page.locator("#seido-cards .card").first().waitFor();
  const first = page.locator("#seido-cards .card").first();
  assert.equal(await first.locator("a").count(), 0);
  assert.equal(await first.locator(".src-pending").textContent(), LABEL);
  assert.match(await first.locator(".src-pending").getAttribute("title"), /制度が終わったという意味ではありません/);
  assert.equal(await page.locator("#seido-cards .card").nth(1).locator("a").count(), 1);
  assert.deepEqual(errors, []);
  await ctx.close();
});
