// 制度メモ30秒シリーズ 一括レンダラ。エピソードごとに ?ep=N でテンプレを開き、MP4に書き出す。
// 使い方: NODE_PATH=<node_modules> node render-series.mjs [出力ディレクトリ] [ep番号...]
import { createRequire } from 'module';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright-core');
const ffmpegPath = require('ffmpeg-static');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = process.argv[2] || __dirname;
const eps = process.argv.slice(3).length ? process.argv.slice(3) : ['1', '2', '3'];
const FPS = 30, W = 1080, H = 1920;

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium',
  args: ['--allow-file-access-from-files', '--force-color-profile=srgb', '--hide-scrollbars', '--force-device-scale-factor=1'],
});
const ctx = await browser.newContext({ viewport: { width: W, height: H } });
const page = await ctx.newPage();

for (const ep of eps) {
  const out = path.join(outDir, `seido_memo_ep${ep}.mp4`);
  await page.goto('file://' + path.join(__dirname, 'index.html') + '?ep=' + ep, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const total = Math.round((await page.evaluate(() => window.FILM_DURATION)) * FPS);
  await page.evaluate(() => { window.__anims = document.getAnimations(); window.__anims.forEach(a => a.pause()); });
  const ff = spawn(ffmpegPath, ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-i', 'pipe:0',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out],
    { stdio: ['pipe', 'ignore', 'pipe'] });
  let ffErr = '';
  ff.stderr.on('data', d => { ffErr += d; if (ffErr.length > 40000) ffErr = ffErr.slice(-20000); });
  for (let f = 0; f < total; f++) {
    await page.evaluate(t => window.__anims.forEach(a => { a.currentTime = t; }), (f / FPS) * 1000);
    const buf = await page.screenshot({ type: 'jpeg', quality: 88 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await new Promise((res, rej) => ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg exit ' + c + '\n' + ffErr.slice(-2000)))));
  console.log('done:', out);
}
await browser.close();
