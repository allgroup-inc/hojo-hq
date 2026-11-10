// もらいわすれ堂 診断改善の第1段階(見た目を変えない計測だけ)を確かめる。
// 実行: node --test tests/measurement_v1.test.mjs(Playwright と python3 が必要)
//
// 確かめること
//   1. 計測の共通部品(fg-analytics.js)が、すべての計測に画面の版の印(top_v / ui_v / support_v)を添える
//      - 既存の計測の名前と、ページが渡す中身はそのまま
//      - トップを通った人は、同じタブの間 top_v が他のページの計測にも付く
//      - 版の印を持たないページでは何も足さない
//   2. 診断の結果の「公式ページで確認する」で result_official_click(制度IDつき)が送られる
//   3. 診断の完了に resumed(保存した答えを開き直したか)が付く
//   4. 申請準備シートの5ステップの2つ目・4つ目で、補助指標(相談できた・申請できた)が
//      同じ端末・同じ制度で1回だけ送られる。ほかのステップでは送られない
//   5. 見た目は変わらない(ボタン・文言・並びはそのまま)
// 外部への通信は遮断する。
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ANALYTICS = fs.readFileSync(path.join(ROOT, "site", "fukugiiro", "assets", "fg-analytics.js"), "utf-8");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg" };

// ---- 1. 共通部品(ブラウザを使わず、最小の window を用意して動かす) ----
function fakeWindow(versions, session) {
  const head = { appendChild() {} };
  const w = {
    FG_ANALYTICS: { provider: "ga4", measurementId: "G-TEST" },
    navigator: { webdriver: false },
    document: { head, createElement: () => ({}) },
    sessionStorage: {
      getItem: (k) => (k in session ? session[k] : null),
      setItem: (k, v) => { session[k] = String(v); },
    },
  };
  if (versions) w.FG_VERSIONS = versions;
  w.window = w;
  w.navigator = w.navigator;
  vm.runInNewContext(ANALYTICS, w);
  return w;
}
function lastEvent(w) {
  // 別の実行環境(vm)で作られた値なので、比べる前に写し取る
  const a = JSON.parse(JSON.stringify(Array.from(w.dataLayer[w.dataLayer.length - 1])));
  return { type: a[0], name: a[1], params: a[2] };
}

test("共通部品: 計測に、そのページの版の印を添える(名前と中身はそのまま)", () => {
  const w = fakeWindow({ ui_v: 1 }, {});
  w.fgTrack("shindan_complete", { results: 3, resumed: false });
  assert.deepEqual(lastEvent(w), { type: "event", name: "shindan_complete", params: { results: 3, resumed: false, ui_v: 1 } });
  w.fgTrack("kit_click");
  assert.deepEqual(lastEvent(w).params, { ui_v: 1 }, "中身の無い計測にも印だけ付く");
});

test("共通部品: トップを通った人は、同じタブの間 top_v が他のページの計測にも付く", () => {
  const session = {};
  const top = fakeWindow({ top_v: 1 }, session);
  top.fgTrack("shindan_cta_click");
  assert.deepEqual(lastEvent(top).params, { top_v: 1 });
  assert.equal(session.fg_top_v, "1", "同じタブに覚えておく");
  const shindan = fakeWindow({ ui_v: 1 }, session);
  shindan.fgTrack("result_official_click", { seido: "fk-x" });
  assert.deepEqual(lastEvent(shindan).params, { seido: "fk-x", ui_v: 1, top_v: 1 });
});

test("共通部品: 版の印を持たないページ・トップを通っていない人には、何も足さない", () => {
  const w = fakeWindow(null, {});
  w.fgTrack("line_add_click", { pos: "header" });
  assert.deepEqual(lastEvent(w).params, { pos: "header" });
  const broken = fakeWindow(null, { fg_top_v: "abc" });
  broken.fgTrack("x");
  assert.deepEqual(lastEvent(broken).params, {}, "数字でない値は付けない");
});

test("共通部品: 自動操縦のブラウザ(監視・点検)は今までどおり計測しない", () => {
  const session = {};
  const w = { FG_ANALYTICS: { provider: "ga4", measurementId: "G-TEST" }, navigator: { webdriver: true }, document: { head: { appendChild() {} }, createElement: () => ({}) }, sessionStorage: { getItem: () => null, setItem() {} }, FG_VERSIONS: { ui_v: 1 } };
  w.window = w;
  vm.runInNewContext(ANALYTICS, w);
  w.fgTrack("shindan_start");
  assert.equal(w.dataLayer, undefined, "GA4 を読み込まず、何も送らない");
  assert.deepEqual(session, {});
});

// ---- 2〜5. 実ブラウザ(moradou.jp と同じ配信ツリー) ----
let tree, server, port, browser;

function send(res, file) {
  if (!file || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end("not found"); }
  res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
}
function handle(req, res) {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  let f = path.join(tree, p.slice(1));
  if (p.endsWith("/")) f = path.join(f, "index.html");
  return send(res, f.startsWith(tree) ? f : null);
}

before(async () => {
  tree = fs.mkdtempSync(path.join(os.tmpdir(), "moradou-measure-"));
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

async function newCtx() {
  const ctx = await browser.newContext();
  const origin = `http://127.0.0.1:${port}`;
  await ctx.route("**/*", (route) => (new URL(route.request().url()).origin === origin ? route.continue() : route.abort()));
  return { ctx, origin };
}
// 自動操縦のブラウザでは計測が止まる作りなので、読み込み後に計測の入口だけを差し替えて、送られる内容を記録する
async function capture(page) {
  await page.evaluate(() => { window.__ev = []; window.fgTrack = (n, p) => window.__ev.push([n, p || {}]); });
}
const events = (page) => page.evaluate(() => window.__ev);

async function runDiagnosis(page) {
  const click = (name) => page.getByRole("button", { name, exact: true }).first().click();
  await page.locator("#muni").waitFor();
  await page.selectOption("#muni", "那覇市");
  for (const n of ["お子さん 2人", "未就学", "小学生", "つぎへ", "入園・入学", "つぎへ", "賃貸", "診断結果を見る"]) await click(n);
  await page.locator("#app h2", { hasText: "制度:" }).waitFor();
}

test("診断: 結果の公式ページへの移動を result_official_click(制度IDつき)で数え、完了に resumed を付ける", async () => {
  const { ctx, origin } = await newCtx();
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${origin}/shindan/`, { waitUntil: "networkidle" });
  assert.deepEqual(await page.evaluate(() => window.FG_VERSIONS), { ui_v: 1 });
  await capture(page);
  await runDiagnosis(page);
  const done = (await events(page)).find(([n]) => n === "shindan_complete");
  assert.ok(done, "診断の完了が送られる");
  assert.equal(done[1].resumed, false, "最初から答えた人は resumed=false");
  assert.ok(done[1].results > 0);

  const link = page.locator("#app a.cardlink", { hasText: "公式ページで確認する" }).first();
  await link.evaluate((a) => a.addEventListener("click", (e) => e.preventDefault())); // 外へは移動しない
  await link.click();
  const off = (await events(page)).filter(([n]) => n === "result_official_click");
  assert.equal(off.length, 1, "公式ページへの移動が1回送られる");
  assert.match(off[0][1].seido, /^fk-/, "制度IDが付く");

  // 開き直した人
  await page.goto(`${origin}/shindan/`, { waitUntil: "networkidle" });
  await capture(page);
  await page.getByRole("button", { name: "前回の結果をもう一度見る" }).click();
  await page.locator("#app h2", { hasText: "制度:" }).waitFor();
  const again = (await events(page)).find(([n]) => n === "shindan_complete");
  assert.equal(again[1].resumed, true, "保存した答えを開き直した人は resumed=true");
  assert.deepEqual(errors, []);
  await ctx.close();
});

// 読み込み中に送られる計測も記録できるよう、ページの読み込み前から計測の入口を固定する
async function newCapturedPage() {
  const { ctx, origin } = await newCtx();
  await ctx.addInitScript(() => {
    window.__ev = [];
    Object.defineProperty(window, "fgTrack", {
      configurable: true,
      get() { return (n, p) => window.__ev.push([n, p || {}]); },
      set() {}, // 共通部品による差し替え(自動操縦のブラウザでは止める作り)を無視する
    });
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  return { ctx, origin, page, errors };
}

test("診断: URL(?resume=1)から前回の結果を開いた人も resumed=true で数える", async () => {
  const { ctx, origin, page, errors } = await newCapturedPage();
  await page.goto(`${origin}/shindan/`, { waitUntil: "networkidle" });
  await runDiagnosis(page);
  await page.goto(`${origin}/shindan/?resume=1`, { waitUntil: "networkidle" });
  await page.locator("#app h2", { hasText: "制度:" }).waitFor();
  const ev = await events(page);
  assert.ok(ev.some(([n]) => n === "shindan_resume"), "開き直しの計測が送られる");
  const done = ev.find(([n]) => n === "shindan_complete");
  assert.ok(done, "結果の表示が送られる");
  assert.equal(done[1].resumed, true, "URLから開いた人も resumed=true");
  assert.deepEqual(errors, []);
  await ctx.close();
});

test("診断: 途中の段(Q2到達など)に resumed を付け、途中から再開した人を分けられる", async () => {
  const { ctx, origin, page, errors } = await newCapturedPage();
  await page.goto(`${origin}/shindan/`, { waitUntil: "networkidle" });
  await page.locator("#muni").waitFor();
  await page.selectOption("#muni", "那覇市"); // 市町村を選ぶと Q2 へ進む
  await page.getByRole("button", { name: "お子さん 2人", exact: true }).first().waitFor();
  let ev = await events(page);
  assert.deepEqual(ev.find(([n]) => n === "shindan_start")[1], { resumed: false }, "ページを開いた数は今までどおり");
  assert.deepEqual(ev.find(([n]) => n === "shindan_step_q2")[1], { resumed: false }, "最初から答えた人は resumed=false");

  // 同じ端末で開き直し、「つづきから」で再開する
  await page.goto(`${origin}/shindan/`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /つづきから/ }).click();
  await page.getByRole("button", { name: "お子さん 2人", exact: true }).first().waitFor();
  ev = await events(page);
  const q2 = ev.filter(([n]) => n === "shindan_step_q2");
  assert.equal(q2.length, 1);
  assert.equal(q2[0][1].resumed, true, "途中から再開した人は resumed=true(前の質問を今回は通っていない)");

  // 「最初からやり直す」を選んだ人は、再開扱いにしない
  await page.goto(`${origin}/shindan/`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "最初からやり直す" }).click();
  await page.selectOption("#muni", "那覇市");
  await page.getByRole("button", { name: "お子さん 2人", exact: true }).first().waitFor();
  ev = await events(page);
  assert.equal(ev.find(([n]) => n === "shindan_step_q2")[1].resumed, false, "最初からやり直した人は resumed=false");
  assert.deepEqual(errors, []);
  await ctx.close();
});

test("申請準備シート: 2つ目・4つ目のステップで相談できた・申請できたを1回だけ送る", async () => {
  const id = fs.readdirSync(path.join(tree, "kit")).find((d) => d.startsWith("fk-"));
  const { ctx, origin } = await newCtx();
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${origin}/kit/${id}/`, { waitUntil: "networkidle" });
  assert.deepEqual(await page.evaluate(() => window.FG_VERSIONS), { support_v: 1 });
  await capture(page);
  const step = (i) => page.locator("ol.track input[type=checkbox]").nth(i);

  await step(0).check();
  await step(2).check();
  await step(4).check();
  let ev = (await events(page)).map(([n]) => n);
  assert.ok(!ev.includes("jukyu_step_soudan") && !ev.includes("jukyu_step_shinsei"), `ほかのステップでは送らない: ${ev}`);
  assert.equal(ev.filter((n) => n === "kit_step").length, 1, "既存の kit_step は今までどおり最初の1回");

  await step(1).check();
  await step(1).uncheck();
  await step(1).check();
  ev = await events(page);
  const soudan = ev.filter(([n]) => n === "jukyu_step_soudan");
  assert.equal(soudan.length, 1, "相談できたは1回だけ(外して付け直しても増えない)");
  assert.deepEqual(soudan[0][1], { seido: id }, "送るのは制度IDだけ");

  // 開き直しても、同じ端末・同じ制度では送らない
  await page.reload({ waitUntil: "networkidle" });
  await capture(page);
  if (!(await step(1).isChecked())) await step(1).check();
  await step(1).uncheck();
  await step(1).check();
  await step(3).check();
  ev = await events(page);
  assert.equal(ev.filter(([n]) => n === "jukyu_step_soudan").length, 0, "開き直しても相談できたは増えない");
  assert.deepEqual(ev.filter(([n]) => n === "jukyu_step_shinsei").map(([, p]) => p), [{ seido: id }], "申請できたは1回");
  assert.deepEqual(errors, []);
  await ctx.close();
});

test("見た目は変えない: 診断とシートのボタン・ステップの文言はそのまま", async () => {
  const { ctx, origin } = await newCtx();
  const page = await ctx.newPage();
  const id = fs.readdirSync(path.join(tree, "kit")).find((d) => d.startsWith("fk-"));
  await page.goto(`${origin}/kit/${id}/`, { waitUntil: "networkidle" });
  const labels = (await page.locator("ol.track li").allTextContents()).map((s) => s.trim());
  assert.deepEqual(labels, [
    "公式ページで「対象」と「締切」を見る",
    "窓口に電話して「私の場合の持ち物」を聞く(下に台本があります)",
    "持ち物をそろえる(全部なくても大丈夫)",
    "窓口で申請する(会話はこのとおりでOK)",
    "結果と受け取りを確認する(受け取れたらLINEで報告)",
  ]);
  await page.goto(`${origin}/shindan/`, { waitUntil: "networkidle" });
  assert.equal(await page.locator("#muni").count(), 1, "15分監視が使う市町村の選択欄はそのまま");
  await ctx.close();
});
