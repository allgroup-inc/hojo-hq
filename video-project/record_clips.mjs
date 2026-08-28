// LP使い方動画v2: 画面収録(作り直し版)。旧posts/video/clipsは使わない。
// 品質改善: タップ波紋の可視化・選択欄のハイライト・ナレーション実尺に合わせた尺。
// 実行: node video-project/record_clips.mjs
import { chromium } from "playwright";
import { mkdirSync, renameSync } from "fs";

const SITE = "https://allgroup-inc.github.io/hojo-hq/";
const OUT = "video-project/clips";
mkdirSync(OUT, { recursive: true });

const VP = { width: 390, height: 844 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// タップ波紋+要素ハイライトを注入
const FX = `
  const st = document.createElement('style');
  st.textContent = \`
    .hfx-ripple{position:fixed;width:64px;height:64px;border-radius:50%;
      background:rgba(248,136,0,.45);border:3px solid rgba(248,136,0,.9);
      transform:translate(-50%,-50%) scale(.4);pointer-events:none;z-index:99999;
      animation:hfxr .7s ease-out forwards;}
    @keyframes hfxr{to{transform:translate(-50%,-50%) scale(1.6);opacity:0;}}
    .hfx-glow{outline:4px solid #F88800 !important;outline-offset:3px;border-radius:8px;
      transition:outline .15s;}
  \`;
  document.head.appendChild(st);
  window.hfxTap = (x,y) => { const d=document.createElement('div');
    d.className='hfx-ripple'; d.style.left=x+'px'; d.style.top=y+'px';
    document.body.appendChild(d); setTimeout(()=>d.remove(),750); };
  window.hfxGlow = (sel,ms=1200) => { const el=document.querySelector(sel);
    if(!el) return; el.classList.add('hfx-glow');
    el.scrollIntoView({behavior:'smooth',block:'center'});
    setTimeout(()=>el.classList.remove('hfx-glow'),ms); };
`;

async function tapAt(page, selector) {
  const box = await page.locator(selector).boundingBox();
  if (!box) return;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.evaluate(([x, y]) => window.hfxTap(x, y), [x, y]);
  await sleep(350);
  await page.click(selector);
}

async function glowSelect(page, sel, label) {
  await page.evaluate(([s]) => window.hfxGlow(s), [sel]);
  await sleep(900);
  await page.selectOption(sel, { label });
  await sleep(700);
}

async function smoothTo(page, selector, ms = 2200, block = "start") {
  await page.evaluate(([sel, b]) => {
    const el = document.querySelector(sel);
    if (el) el.scrollIntoView({ behavior: "smooth", block: b });
  }, [selector, block]);
  await sleep(ms);
}

async function record(name, fn, { preFill = false } = {}) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: VP, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    recordVideo: { dir: OUT, size: VP },
    userAgent: "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
  });
  const page = await ctx.newPage();
  await page.goto(SITE, { waitUntil: "networkidle" });
  await page.evaluate(FX);
  await sleep(1500); // 初期アニメの落ち着き待ち(この間は後でトリム)
  if (preFill) {
    await page.selectOption("#f-area", { label: "那覇市" });
    await page.selectOption("#f-biz", { label: "飲食・宿泊" });
    await page.selectOption("#f-emp", { label: "5名以下" });
    await page.click('#f-theme .chip[data-v="setsubi"]');
  }
  try { await fn(page); } catch (e) { console.error(`[ng] ${name}:`, e.message); }
  await sleep(500);
  await ctx.close();
  const video = await page.video().path();
  renameSync(video, `${OUT}/${name}.webm`);
  await browser.close();
  console.log(`[ok] ${name}.webm`);
}

// ① s1 フック: 診断ボタン→結果が出る瞬間(約8s)
await record("hook_result", async (p) => {
  await smoothTo(p, "#match-btn", 1200, "center");
  await tapAt(p, "#match-btn");
  await sleep(1800);
  await smoothTo(p, "#match-result", 1200);
  await p.evaluate(() => window.scrollBy({ top: 420, behavior: "smooth" }));
  await sleep(2600);
}, { preFill: true });

// ① s2 トップ表示(約7s): ヒーローをじっくり
await record("top", async (p) => {
  await sleep(4500);
  await p.evaluate(() => window.scrollBy({ top: 260, behavior: "smooth" }));
  await sleep(2200);
});

// ① s3 毎日更新の実績(約8s)
await record("stats", async (p) => {
  await smoothTo(p, ".reality", 2400);
  await sleep(2200);
  await p.evaluate(() => window.scrollBy({ top: 300, behavior: "smooth" }));
  await sleep(2400);
});

// ① s4 無料診断へ移動(約10s)
await record("to_shindan", async (p) => {
  await sleep(1800);
  await p.evaluate(() => window.hfxGlow(".hero-cta", 1500));
  await sleep(1400);
  await tapAt(p, ".hero-cta");
  await sleep(3200);
  await p.evaluate(() => window.scrollBy({ top: 200, behavior: "smooth" }));
  await sleep(2400);
});

// ① s5 条件を選ぶ(約11s)
await record("select", async (p) => {
  await smoothTo(p, "#f-area", 1400, "center");
  await glowSelect(p, "#f-area", "那覇市");
  await glowSelect(p, "#f-biz", "飲食・宿泊");
  await glowSelect(p, "#f-emp", "5名以下");
  await p.evaluate(() => window.hfxGlow('#f-theme', 1200));
  await sleep(800);
  await tapAt(p, '#f-theme .chip[data-v="setsubi"]');
  await sleep(1400);
});

// ① s6 GビズIDチェック(約8s)
await record("gbiz", async (p) => {
  await smoothTo(p, "#f-nogbiz", 2000, "center");
  await p.evaluate(() => window.hfxGlow("#f-nogbiz", 1600));
  await sleep(1400);
  await tapAt(p, "#f-nogbiz");
  await sleep(2600);
}, { preFill: true });

// ① s7 診断実行(約9.5s)
await record("diagnose", async (p) => {
  await smoothTo(p, "#match-btn", 1800, "center");
  await p.evaluate(() => window.hfxGlow("#match-btn", 1500));
  await sleep(1300);
  await tapAt(p, "#match-btn");
  await sleep(2200);
  await smoothTo(p, "#match-result", 1500);
  await sleep(2000);
}, { preFill: true });

// ① s8 結果と金額(約8s)
await record("result", async (p) => {
  await p.click("#match-btn");
  await sleep(1500);
  await smoothTo(p, "#match-result", 1400);
  await p.evaluate(() => window.scrollBy({ top: 480, behavior: "smooth" }));
  await sleep(2400);
  await p.evaluate(() => window.scrollBy({ top: 380, behavior: "smooth" }));
  await sleep(2200);
}, { preFill: true });

// ② s2 締切がある(HOW IT WORKSの説明・約8.5s)
await record("howit", async (p) => {
  await smoothTo(p, ".how", 2600);
  await sleep(2200);
  await p.evaluate(() => window.scrollBy({ top: 340, behavior: "smooth" }));
  await sleep(2600);
});

// ② s3 LINE登録ボタン(約9.5s)
await record("footer_cta", async (p) => {
  await smoothTo(p, ".cta", 2800);
  await sleep(1600);
  await p.evaluate(() => window.hfxGlow(".cta .line-btn, .cta a", 2000));
  await sleep(3600);
});

// ② s4 結果ぜんぶ(マスク解除の説明ブロック・約7.5s)
await record("result_full", async (p) => {
  await p.click("#match-btn");
  await sleep(1500);
  await smoothTo(p, "#match-result", 1200);
  await p.evaluate(() => window.scrollBy({ top: 620, behavior: "smooth" }));
  await sleep(3200);
}, { preFill: true });

// ② s5 締切1か月前のお知らせ(参ブロック・約11s)
await record("alert", async (p) => {
  await smoothTo(p, ".how", 2200);
  await p.evaluate(() => window.scrollBy({ top: 520, behavior: "smooth" }));
  await sleep(3000);
  await sleep(3400);
});

console.log("done");
