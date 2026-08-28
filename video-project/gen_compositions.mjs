// scenes.json + timings.json から Hyperframesコンポジション(HTML)を生成する。
// 実行: node video-project/gen_compositions.mjs → video-project/hf/v1.html, v2.html
import { readFileSync, writeFileSync, mkdirSync } from "fs";

const cfg = JSON.parse(readFileSync("video-project/scenes.json", "utf8"));
const timings = JSON.parse(readFileSync("video-project/timings.json", "utf8"));
const mediaStarts = JSON.parse(readFileSync("video-project/media_starts.json", "utf8"));
mkdirSync("video-project/hf", { recursive: true });

const PAD = 0.9;          // ナレーション後の間
const AUDIO_DELAY = 0.3;  // シーン頭の間

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");

function buildVideo(v, epLabel) {
  const t = timings[v.id];
  let cursor = 0;
  const scenes = v.scenes.map((sc) => {
    const narr = t[sc.id];
    const dur = +(narr + AUDIO_DELAY + PAD).toFixed(2);
    const s = { ...sc, start: +cursor.toFixed(2), dur, narr };
    cursor += dur;
    return s;
  });
  const total = +cursor.toFixed(2);
  const n = scenes.length;

  const sceneHtml = scenes
    .map((s, i) => {
      const dots = scenes
        .map((_, j) => `<span class="dot${j === i ? " on" : ""}"></span>`)
        .join("");
      const media = s.clip
        ? `<div class="phone"><video src="../clips/${s.clip}.webm" muted
             data-start="${s.start}" data-duration="${s.dur}"
             data-media-start="${mediaStarts[s.clip] ?? 0.5}" data-volume="0"></video></div>`
        : `<div class="bigcap-wrap"><p class="bigcap">${esc(s.cap).split("\n").join("<br>")}</p>
           <p class="bigsub">${esc(s.sub)}</p></div>`;
      const caps = s.clip
        ? `<p class="cap">${esc(s.cap).split("\n").join("<br>")}</p>` +
          `<p class="sub">${esc(s.sub)}</p>`
        : "";
      return `
  <div class="clip scene" data-start="${s.start}" data-duration="${s.dur}">
    <header><span class="brand">沖縄企業のミカタ</span><span class="ep">${epLabel}</span></header>
    ${caps}
    ${media}
    <div class="dots">${dots}</div>
    <audio src="../audio/${v.id}/${s.id}.mp3" data-start="${+(s.start + AUDIO_DELAY).toFixed(2)}" data-duration="${s.narr}"></audio>
  </div>`;
    })
    .join("\n");

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@500;700;900&display=swap" rel="stylesheet">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  #root { font-family:"Noto Sans JP","Meiryo",sans-serif; }
  .scene { position:absolute; inset:0;
    background:linear-gradient(180deg,#0E2440 0%,#0A1B33 55%,#071426 100%); }
  header { position:absolute; top:64px; left:80px; right:80px;
    display:flex; align-items:center; justify-content:space-between; }
  .brand { color:#fff; font-weight:900; font-size:36px; letter-spacing:.04em;
    border-bottom:5px solid #F88800; padding-bottom:10px; }
  .ep { color:#F88800; font-weight:700; font-size:30px;
    border:3px solid #F88800; border-radius:999px; padding:8px 26px; }
  .cap { position:absolute; top:172px; left:60px; right:60px; text-align:center;
    color:#fff; font-weight:900; font-size:68px; line-height:1.32;
    text-wrap:balance; }
  .sub { position:absolute; bottom:150px; left:60px; right:60px; text-align:center;
    color:#F88800; font-weight:700; font-size:40px; }
  .phone { position:absolute; top:388px; left:50%; transform:translateX(-50%);
    width:576px; height:1180px; border-radius:48px; overflow:hidden;
    border:3px solid rgba(255,255,255,.22);
    box-shadow:0 40px 90px rgba(0,0,0,.55), 0 0 0 12px rgba(255,255,255,.06); }
  .phone video { width:100%; height:100%; object-fit:cover; object-position:top; }
  .bigcap-wrap { position:absolute; top:0; bottom:0; left:80px; right:80px;
    display:flex; flex-direction:column; justify-content:center; align-items:center;
    gap:56px; text-align:center; }
  .bigcap { color:#fff; font-weight:900; font-size:96px; line-height:1.4;
    text-wrap:balance; }
  .bigsub { color:#F88800; font-weight:700; font-size:46px; }
  .dots { position:absolute; bottom:84px; left:0; right:0; text-align:center; }
  .dot { display:inline-block; width:16px; height:16px; border-radius:50%;
    background:rgba(255,255,255,.22); margin:0 9px; }
  .dot.on { background:#F88800; }
</style>
</head>
<body>
<div id="root" data-composition-id="root" data-width="1080" data-height="1920" data-duration="${total}">
${sceneHtml}
</div>
</body>
</html>`;
}

for (const v of cfg.videos) {
  const ep = v.id === "v1" ? "① さがす・診断する" : "② LINEで見逃さない";
  const html = buildVideo(v, ep);
  writeFileSync(`video-project/hf/${v.id}.html`, html);
  const t = timings[v.id];
  const total = v.scenes.reduce((a, s) => a + t[s.id] + 1.2, 0);
  console.log(`[ok] hf/${v.id}.html  ${v.scenes.length}シーン 約${Math.round(total)}s`);
}
