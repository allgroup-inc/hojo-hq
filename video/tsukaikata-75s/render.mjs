// もらいわすれ堂 LP紹介ムービー レンダラ
// index.html の全CSSアニメーションを1フレームずつシークして撮影し、
// H.264 MP4 に書き出す(決定的レンダリング)。
//
// 使い方:
//   npm i playwright-core ffmpeg-static   (どこかの作業ディレクトリで)
//   NODE_PATH=<そのnode_modules> node render.mjs [出力.mp4]
//   CHROMIUM=/opt/pw-browsers/chromium など環境に合わせて上書き可
import { createRequire } from 'module';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright-core');
const ffmpegPath = require('ffmpeg-static');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = process.argv[2] || path.join(process.env.OUTDIR || __dirname, 'moraiwasuredo_lp_60s.mp4');
const FPS = 30;
const W = 1080, H = 1920;

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium',
  args: ['--allow-file-access-from-files', '--force-color-profile=srgb', '--hide-scrollbars', '--force-device-scale-factor=1'],
});
const ctx = await browser.newContext({ viewport: { width: W, height: H } });
const page = await ctx.newPage();
await page.goto('file://' + path.join(__dirname, 'index.html'), { waitUntil: 'load' });
await page.evaluate(() => document.fonts.ready);
await page.evaluate(() => Promise.all(
  [...document.images].map(img => img.complete ? 0 : new Promise(r => { img.onload = img.onerror = r; }))
));
const total = Math.round((await page.evaluate(() => window.FILM_DURATION)) * FPS);
const nAnims = await page.evaluate(() => {
  window.__anims = document.getAnimations();
  window.__anims.forEach(a => a.pause());
  return window.__anims.length;
});
console.log(`animations: ${nAnims}, frames: ${total}, out: ${OUT}`);

const ff = spawn(ffmpegPath, [
  '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-i', 'pipe:0',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
  '-movflags', '+faststart', OUT,
], { stdio: ['pipe', 'ignore', 'pipe'] });
let ffErr = '';
ff.stderr.on('data', d => { ffErr += d; if (ffErr.length > 40000) ffErr = ffErr.slice(-20000); });

const t0 = Date.now();
for (let f = 0; f < total; f++) {
  const ms = (f / FPS) * 1000;
  await page.evaluate(t => { window.__anims.forEach(a => { a.currentTime = t; }); }, ms);
  const buf = await page.screenshot({ type: 'jpeg', quality: 88 });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  if (f % 150 === 0) {
    const el = (Date.now() - t0) / 1000;
    console.log(`frame ${f}/${total} (${(f / total * 100).toFixed(0)}%) elapsed ${el.toFixed(0)}s`);
  }
}
ff.stdin.end();
await new Promise((res, rej) => ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg exit ' + c + '\n' + ffErr.slice(-3000)))));
await browser.close();
console.log('done:', OUT, `(${((Date.now() - t0) / 1000).toFixed(0)}s)`);
