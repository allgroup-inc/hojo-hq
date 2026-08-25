// LP使い方動画用: 実際のサイト操作を録画してクリップ化する(2026-08-26 小柳さん指示)
// スマホ表示(390x844)・ゆっくり操作。出力: posts/video/clips/*.webm
// 使い方: node scripts/record_usage_clips.mjs
import { chromium } from "playwright";
import { mkdirSync } from "fs";

const SITE = "https://allgroup-inc.github.io/hojo-hq/";
const OUT = "posts/video/clips";
mkdirSync(OUT, { recursive: true });

const VP = { width: 390, height: 844 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function record(name, fn) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: VP,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    recordVideo: { dir: OUT, size: VP },
    userAgent:
      "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
  });
  const page = await ctx.newPage();
  await page.goto(SITE, { waitUntil: "networkidle" });
  await sleep(1200);
  try {
    await fn(page);
  } catch (e) {
    console.error(`[ng] ${name}:`, e.message);
  }
  await sleep(800);
  await ctx.close(); // 動画はclose時に確定
  const video = await page.video().path();
  const { renameSync } = await import("fs");
  renameSync(video, `${OUT}/${name}.webm`);
  await browser.close();
  console.log(`[ok] ${name}.webm`);
}

// なめらかスクロール(ゆっくり)
async function smoothTo(page, selector, ms = 2200) {
  await page.evaluate(
    ([sel]) => {
      const el = document.querySelector(sel);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [selector]
  );
  await sleep(ms);
}

// ① シーン2-3: トップ表示 → ゆっくり下へ(実績・毎日更新)
await record("c01_top_scroll", async (p) => {
  await sleep(2500); // ヒーローをじっくり見せる
  await smoothTo(p, ".reality", 2600);
  await sleep(1500);
});

// ① シーン4: 診断セクションへ移動(ヒーローの「無料診断」ボタンから)
await record("c02_to_shindan", async (p) => {
  await sleep(1500);
  await p.click(".hero-cta");
  await sleep(2500);
});

// ① シーン5: 条件を選ぶ(市町村→業種→従業員数→テーマ)
await record("c03_select", async (p) => {
  await smoothTo(p, "#match", 1500);
  await p.selectOption("#f-area", { label: "那覇市" });
  await sleep(1400);
  await p.selectOption("#f-biz", { label: "飲食・宿泊" });
  await sleep(1400);
  await p.selectOption("#f-emp", { label: "5名以下" });
  await sleep(1400);
  await p.click('#f-theme .chip[data-v="setsubi"]');
  await sleep(1600);
});

// ① シーン6: GビズIDチェック
await record("c04_gbiz", async (p) => {
  await smoothTo(p, "#f-nogbiz", 1500);
  await p.selectOption("#f-area", { label: "那覇市" });
  await p.selectOption("#f-biz", { label: "飲食・宿泊" });
  await p.check("#f-nogbiz");
  await sleep(1800);
});

// ① シーン7-8: 診断ボタンを押す → 結果が出る
await record("c05_diagnose_result", async (p) => {
  await smoothTo(p, "#match", 1200);
  await p.selectOption("#f-area", { label: "那覇市" });
  await sleep(600);
  await p.selectOption("#f-biz", { label: "飲食・宿泊" });
  await sleep(600);
  await p.click('#f-theme .chip[data-v="setsubi"]');
  await sleep(800);
  await smoothTo(p, "#match-btn", 1200);
  await p.click("#match-btn");
  await sleep(2000);
  await smoothTo(p, "#match-result", 1500);
  await sleep(2500);
  // 結果をゆっくり下へ
  await p.evaluate(() => window.scrollBy({ top: 500, behavior: "smooth" }));
  await sleep(2200);
});

// ② シーン3-4: 結果からLINE登録ボタンへ(合計マスク→CTA)
await record("c06_result_line_cta", async (p) => {
  await smoothTo(p, "#match", 1000);
  await p.selectOption("#f-area", { label: "那覇市" });
  await sleep(400);
  await p.selectOption("#f-biz", { label: "飲食・宿泊" });
  await sleep(400);
  await p.click("#match-btn");
  await sleep(1800);
  await smoothTo(p, "#match-result", 1200);
  await p.evaluate(() => window.scrollBy({ top: 600, behavior: "smooth" }));
  await sleep(2400);
});

// ② シーン5: 締切アラート説明(HOW IT WORKS 参ブロック)
await record("c07_alert_howit", async (p) => {
  await smoothTo(p, ".how", 2200);
  await p.evaluate(() => window.scrollBy({ top: 400, behavior: "smooth" }));
  await sleep(2400);
});

// ② シーン8: フッターのLINE登録CTA
await record("c08_footer_cta", async (p) => {
  await smoothTo(p, ".cta", 2400);
  await sleep(2500);
});

// ①予備: 目的別にさがす
await record("c09_themes_nav", async (p) => {
  await smoothTo(p, ".themes-nav", 2400);
  await sleep(2200);
});

console.log("done");
