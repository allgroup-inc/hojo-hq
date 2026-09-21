#!/usr/bin/env node
/* みらいひらけ堂 フィルムの自動試写・検査(Playwright/Chromium)。
   人が目で見ていた4点を機械で判定する:
     1. JSエラーがない
     2. 全シーンに .in が付く(コメント・ズーム・ロゴのアニメーションが発火する)
     3. ロゴ「虹と朝日」の虹が描き切られ、朝日が出る
     4. 写真と写真の境目に硬い横線がない(境目付近の行ごとの明るさの飛びを測る)
   出力: dist/miraihirake/shots/*.png と dist/miraihirake/report.json。NG があれば exit 1。

   使い方: node scripts/miraihirake/check_film.js [preview.html] [--seam-max 10] */
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const args = process.argv.slice(2);
const previewArg = args.find((a) => !a.startsWith("--"));
const seamMaxIdx = args.indexOf("--seam-max");
const SEAM_MAX = seamMaxIdx >= 0 ? Number(args[seamMaxIdx + 1]) : 10;
const ROOT = path.resolve(__dirname, "..", "..");
const PREVIEW = path.resolve(previewArg || path.join(ROOT, "dist", "miraihirake", "preview.html"));
const OUT = path.join(ROOT, "dist", "miraihirake");
const SHOTS = path.join(OUT, "shots");
const VW = 420, VH = 820;

// 境目の硬い線 = 「境目の位置(画面中央±4%)に、画面幅のほぼ全列で同時に明るさが飛ぶ行」。
// 各行で列ごとに±2行の明るさの差を取り、その下位25%点(=75%以上の列が飛んだ量)を行の点数にする。
// 写真の中の窓枠や棚、影絵や文字は幅の一部にしか無いので点数にならず、全幅の横線だけが検出される。
async function seamScore(page, png) {
  return page.evaluate(async ({ b64, band }) => {
    const img = new Image();
    img.src = "data:image/png;base64," + b64;
    await img.decode();
    const c = document.createElement("canvas");
    c.width = img.width; c.height = img.height;
    const ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0);
    const { data, width, height } = ctx.getImageData(0, 0, c.width, c.height);
    const lum = (x, y) => { const i = (y * width + x) * 4; return 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]; };
    const y0 = Math.floor(height * (0.5 - band)), y1 = Math.ceil(height * (0.5 + band));
    let max = 0, at = -1;
    for (let y = y0 + 2; y < y1 - 2; y++) {
      const d = [];
      for (let x = 0; x < width; x++) d.push(Math.abs(lum(x, y + 2) - lum(x, y - 2)));
      d.sort((a, b) => a - b);
      const q = d[Math.floor(d.length * 0.25)];
      if (q > max) { max = q; at = y; }
    }
    return { max: Math.round(max * 10) / 10, at };
  }, { b64: png.toString("base64"), band: 0.04 });
}

(async () => {
  if (!fs.existsSync(PREVIEW)) { console.error("試写ファイルがありません: " + PREVIEW); process.exit(2); }
  fs.mkdirSync(SHOTS, { recursive: true });
  const report = { preview: PREVIEW, viewport: `${VW}x${VH}`, checks: [], seams: [], ok: true };
  const fail = (name, detail) => { report.ok = false; report.checks.push({ name, ok: false, detail }); };
  const pass = (name, detail) => report.checks.push({ name, ok: true, detail });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: VW, height: VH } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("file://" + PREVIEW);
  await page.waitForTimeout(800);

  // 境目: シーン i の下端(= i*VH)を画面中央に置いて撮る
  const sceneIds = await page.$$eval(".mfilm .scene", (els) => els.map((e) => e.id));
  for (let i = 1; i < sceneIds.length - 1; i++) {
    await page.evaluate((y) => window.scrollTo(0, y), i * VH - VH / 2);
    await page.waitForTimeout(1600);
    const file = path.join(SHOTS, `seam_${sceneIds[i - 1]}_${sceneIds[i]}.png`);
    const png = await page.screenshot({ path: file });
    const s = await seamScore(page, png);
    const ok = s.max <= SEAM_MAX;
    report.seams.push({ between: `${sceneIds[i - 1]}→${sceneIds[i]}`, jump: s.max, row: s.at, ok, shot: path.relative(ROOT, file) });
    if (!ok) report.ok = false;
  }

  // 最終シーン: ロゴのアニメーション完了を待って撮る
  const last = await page.$(`#${sceneIds[sceneIds.length - 1]}`);
  await last.scrollIntoViewIfNeeded();
  await page.waitForTimeout(4200);
  await page.screenshot({ path: path.join(SHOTS, "logo_scene.png") });

  const state = await page.evaluate(() => ({
    total: document.querySelectorAll(".mfilm .scene").length,
    inScenes: [...document.querySelectorAll(".mfilm .scene.in")].map((s) => s.id),
    arcs: [...document.querySelectorAll(".dlogo .arc")].map((a) => getComputedStyle(a).strokeDashoffset),
    petal: document.querySelector(".dlogo .petal") ? getComputedStyle(document.querySelector(".dlogo .petal")).opacity : null,
    headerIcon: (document.querySelector(".mhead .hl img") || {}).naturalWidth || 0,
  }));
  await browser.close();

  errors.length ? fail("JSエラーなし", errors) : pass("JSエラーなし", []);
  state.inScenes.length === state.total ? pass("全シーンに .in", state.inScenes) : fail("全シーンに .in", state.inScenes);
  const arcsDrawn = state.arcs.length === 3 && state.arcs.every((v) => parseFloat(v) === 0);
  arcsDrawn && state.petal === "1" ? pass("ロゴ: 虹3本が描画・朝日が表示", state) : fail("ロゴ: 虹3本が描画・朝日が表示", state);
  state.headerIcon > 0 ? pass("ヘッダーのロゴ画像が読めた", state.headerIcon) : fail("ヘッダーのロゴ画像が読めた", state.headerIcon);

  fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  for (const c of report.checks) console.log(`${c.ok ? "OK " : "NG "} ${c.name}${c.ok ? "" : " → " + JSON.stringify(c.detail)}`);
  for (const s of report.seams) console.log(`${s.ok ? "OK " : "NG "} 境目 ${s.between}: 明るさの飛び ${s.jump} (上限 ${SEAM_MAX})`);
  console.log((report.ok ? "PASS" : "FAIL") + " → " + path.relative(ROOT, path.join(OUT, "report.json")));
  process.exit(report.ok ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
