// 各クリップの「白い読み込み画面が終わる時刻」を輝度(YAVG)で自動検出する。
// 白ページ≈YAVG235前後 / コンテンツ表示後は下がる。出力: media_starts.json
import { execFileSync } from "child_process";
import { readdirSync, writeFileSync } from "fs";

const FF = "node_modules/ffmpeg-static/ffmpeg.exe";
const DIR = "video-project/clips";
const out = {};

for (const f of readdirSync(DIR).filter((f) => f.endsWith(".webm"))) {
  const name = f.replace(".webm", "");
  const r = (await import("child_process")).spawnSync(FF, ["-i", `${DIR}/${f}`, "-vf",
    "signalstats,metadata=print:key=lavfi.signalstats.YMIN",
    "-f", "null", "-"], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const stderr = r.stderr ?? "";
  // 行例: frame:12 pts:480 pts_time:0.48 → 次行 ...YMIN=235.1
  // 冒頭6秒のうち「最後に白かった(YAVG>200)」時刻を探す(黒→白→コンテンツの順のため)
  const lines = stderr.split("\n");
  let t = 0, lastWhite = -1;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/pts_time:([\d.]+)/);
    if (m) { t = parseFloat(m[1]); continue; }
    const y = lines[i].match(/YMIN=([\d.]+)/);
    if (y && t <= 6 && parseFloat(y[1]) > 180) lastWhite = t;
  }
  out[name] = +(Math.max(lastWhite, 0) + 0.2).toFixed(2);
  console.log(`${name}: 白の終わり ${lastWhite}s → media_start ${out[name]}s`);
}
writeFileSync("video-project/media_starts.json", JSON.stringify(out, null, 1));
