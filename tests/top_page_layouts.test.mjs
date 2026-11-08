// もらいわすれ堂のトップと診断ページが、実際の2つの配信構成のどちらでも制度データを読めることを、実ブラウザで確かめる。
// 実行: node --test tests/top_page_layouts.test.mjs(Playwright 1.56.1 と python3 が必要)
//
// なぜ要るか: 2026-11-02 に診断ページ、2026-11-05 にトップページが、moradou.jp に存在しないパス
// (../data/fukugiiro/…)を読みに行っていた。どちらも旧URL(github.io)の構成でしか試していなかったので、
// テストは通っていた。そこで、配信と同じ組み立て方で2つの構成を手元に作り、両方で開く。
//   - moradou.jp: scripts/deploy_moradou.py が組み立てる配信ツリーをルートで配信する
//   - 旧URL: update.yml と同じく site/ を /hojo-hq/ に、data/ を /hojo-hq/data/ に置く
// 外部への通信は遮断する。
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const LABEL = "公式ページを確認中";
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg" };

// moradou.jp に配信していないと分かっていて、読めなくても表示が変わらないもの(理由つき)。
// ここに無いファイルが読めなければ失敗にする。
const KNOWN_MISSING_ON_MORADOU = {
  "/data/fukugiiro/jukyu_reports.json":
    "受給報告の台帳。10世帯に達するまで表示しない(0世帯の間は表示が変わらない)。moradou.jp への配信方法は未決",
};

let tree, server, port, browser, override = null;

function send(res, file) {
  if (!file || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404);
    return res.end("not found");
  }
  res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
}

function inside(base, rel) {
  let f = path.join(base, rel);
  if (rel.endsWith("/") || rel === "") f = path.join(f, "index.html");
  return f.startsWith(base) ? f : null;
}

// 1つのサーバーで2つの構成を出し分ける: /hojo-hq/… は旧URL、それ以外は moradou.jp の配信ツリー
function handle(req, res) {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (override && override.path === p) {
    res.writeHead(200, { "Content-Type": TYPES[".json"] });
    return res.end(override.body);
  }
  if (p.startsWith("/hojo-hq/data/")) return send(res, inside(path.join(ROOT, "data"), p.slice("/hojo-hq/data/".length)));
  if (p.startsWith("/hojo-hq/")) return send(res, inside(path.join(ROOT, "site"), p.slice("/hojo-hq/".length)));
  return send(res, inside(tree, p.slice(1)));
}

before(async () => {
  tree = fs.mkdtempSync(path.join(os.tmpdir(), "moradou-tree-"));
  execFileSync("python3", [path.join(ROOT, "scripts", "deploy_moradou.py"), "--out", tree], { cwd: ROOT, stdio: "pipe" });
  server = http.createServer(handle);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  port = server.address().port;
  const { chromium } = require("playwright");
  browser = await chromium.launch();
});
after(async () => {
  if (browser) await browser.close();
  if (server) server.close();
  if (tree) fs.rmSync(tree, { recursive: true, force: true });
});

async function open(url) {
  const ctx = await browser.newContext();
  const origin = `http://127.0.0.1:${port}`;
  await ctx.route("**/*", (route) => (new URL(route.request().url()).origin === origin ? route.continue() : route.abort()));
  const page = await ctx.newPage();
  const errors = [];
  const json = []; // [パス, 応答コード]
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("response", (r) => {
    const u = new URL(r.url());
    if (u.origin === origin && u.pathname.endsWith(".json")) json.push([u.pathname, r.status()]);
  });
  await page.goto(`${origin}${url}`, { waitUntil: "networkidle" });
  return { ctx, page, errors, json };
}

function served(layout) {
  const file = layout === "moradou" ? path.join(tree, "seido.json") : path.join(ROOT, "site", "fukugiiro", "seido.json");
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

const LAYOUTS = [
  { name: "moradou.jp", key: "moradou", top: "/", shindan: "/shindan/", seido: "/seido.json" },
  { name: "旧URL(github.io)", key: "old", top: "/hojo-hq/fukugiiro/", shindan: "/hojo-hq/fukugiiro/shindan/", seido: "/hojo-hq/fukugiiro/seido.json" },
];

for (const L of LAYOUTS) {
  test(`${L.name}: トップが制度データを読み、件数・照合率・制度カードを表示する`, async () => {
    const db = served(L.key);
    const items = db.items;
    const total = db.count || items.length;
    const ver = items.filter((it) => it.verified === true).length;
    assert.ok(total > 0 && ver > 0, "配信される制度データに件数がある");

    const { ctx, page, errors, json } = await open(L.top);
    await page.locator("#seido-cards .card h3").first().waitFor();
    assert.equal((await page.locator("#seido-count").textContent()).trim(), String(ver), "検証済みの件数");
    assert.equal(
      (await page.locator("#seido-trust").textContent()).trim(),
      `掲載${total}件のうち${Math.round((ver / total) * 100)}%を公式ページと照合済み`,
      "照合率の一文",
    );
    const titles = (await page.locator("#seido-cards .card h3").allTextContents()).map((s) => s.trim());
    assert.equal(titles.length, 4, "制度カードは4枚");
    assert.ok(!titles.includes("制度情報を準備中です"), "初期表示のままになっていない");
    const shown = items.slice().sort((a, b) => (b.verified ? 1 : 0) - (a.verified ? 1 : 0)).slice(0, 4).map((it) => it.name);
    assert.deepEqual(titles, shown, "検証済みを先にした上位4件");

    assert.ok(json.some(([p, s]) => p === L.seido && s === 200), `制度データ(${L.seido})を読めた: ${JSON.stringify(json)}`);
    const failed = json.filter(([p, s]) => s !== 200 && !(L.key === "moradou" && p in KNOWN_MISSING_ON_MORADOU));
    assert.deepEqual(failed, [], "読めなかったデータファイルが無い");
    assert.deepEqual(errors, []);
    await ctx.close();
  });

  test(`${L.name}: 診断ページも同じ制度データを読み、結果を出す`, async () => {
    const { ctx, page, errors, json } = await open(L.shindan);
    // 診断ページは結果を出すときに制度データを読む。15分監視と同じ条件(那覇市・子ども2人)で診断する
    const click = (name) => page.getByRole("button", { name, exact: true }).first().click();
    await page.locator("#muni").waitFor();
    await page.selectOption("#muni", "那覇市");
    for (const n of ["お子さん 2人", "未就学", "小学生", "つぎへ", "入園・入学", "つぎへ", "賃貸", "診断結果を見る"]) await click(n);
    await page.locator("#app h2", { hasText: "制度:" }).waitFor();
    assert.ok((await page.locator("#app .result-card").count()) > 0, "結果が出る");
    assert.ok(json.some(([p, s]) => p === L.seido && s === 200), `制度データ(${L.seido})を読めた: ${JSON.stringify(json)}`);
    assert.deepEqual(json.filter(([, s]) => s !== 200), []);
    assert.deepEqual(errors, []);
    await ctx.close();
  });
}

test("moradou.jp: 公式ページが無いと確かめた出典は、トップでも「公式ページを確認中」になる", async () => {
  const db = structuredClone(served("moradou"));
  const shown = db.items.slice().sort((a, b) => (b.verified ? 1 : 0) - (a.verified ? 1 : 0)).slice(0, 4);
  for (const it of db.items) {
    if (it.id === shown[0].id) it.source_unavailable = { since: "2026-11-04 10:21", reason: "公式ページが見つかりません(HTTP 404)" };
    else delete it.source_unavailable;
  }
  override = { path: "/seido.json", body: JSON.stringify(db) };
  try {
    const { ctx, page, errors } = await open("/");
    await page.locator("#seido-cards .card h3").first().waitFor();
    const first = page.locator("#seido-cards .card").first();
    assert.equal((await first.locator("h3").textContent()).trim(), shown[0].name);
    assert.equal(await first.locator("a").count(), 0, "開けない公式ページへのリンクは出さない");
    assert.equal(await first.locator(".src-pending").textContent(), LABEL);
    assert.match(await first.locator(".src-pending").getAttribute("title"), /制度が終わったという意味ではありません/);
    const second = page.locator("#seido-cards .card").nth(1);
    assert.equal(await second.locator("a").getAttribute("href"), shown[1].source_url, "他の制度は公式リンクのまま");
    assert.deepEqual(errors, []);
    await ctx.close();
  } finally {
    override = null;
  }
});

test("moradou.jp の配信ツリー: ページが読みに行くファイルがすべて配信されている", () => {
  // fetch("…") の相対パスを、ページの位置から解決して、配信ツリーにあるかを見る(実ブラウザ検査の取りこぼし防止)
  const missing = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir)) {
      const f = path.join(dir, name);
      if (fs.statSync(f).isDirectory()) walk(f);
      else if (/\.(html|js)$/.test(name)) {
        const body = fs.readFileSync(f, "utf-8");
        for (const m of body.matchAll(/fetch\(\s*["']([^"']+)["']/g)) {
          const ref = m[1];
          if (/^[a-z]+:\/\//i.test(ref)) continue;
          const pageUrl = "/" + path.relative(tree, f).split(path.sep).join("/");
          const target = new URL(ref, `http://x${pageUrl}`).pathname;
          if (target in KNOWN_MISSING_ON_MORADOU) continue;
          if (!fs.existsSync(path.join(tree, target.slice(1)))) missing.push(`${pageUrl} → ${ref}(${target})`);
        }
      }
    }
  };
  walk(tree);
  assert.deepEqual(missing, [], "配信ツリーに無いファイルを読みに行くページがある");
});
