#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scenes.jsonからナレーション音声(mp3)を生成し、実尺をtimings.jsonに書く。
使い方: python video-project/gen_narration.py
"""
import asyncio
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(__file__)
FF = os.path.join(BASE, "..", "node_modules", "ffmpeg-static", "ffmpeg.exe")

import edge_tts  # noqa: E402


def duration_of(path):
    """ffmpegのstderrからDurationを読む(ffprobeが無いため)"""
    p = subprocess.run([FF, "-i", path], capture_output=True, text=True, errors="replace")
    for line in p.stderr.splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return round(int(h) * 3600 + int(m) * 60 + float(s), 2)
    raise RuntimeError(f"duration not found: {path}")


async def main():
    cfg = json.load(open(os.path.join(BASE, "scenes.json"), encoding="utf-8"))
    voice, rate = cfg["voice"], cfg["rate"]
    timings = {}
    for v in cfg["videos"]:
        outdir = os.path.join(BASE, "audio", v["id"])
        os.makedirs(outdir, exist_ok=True)
        timings[v["id"]] = {}
        for sc in v["scenes"]:
            mp3 = os.path.join(outdir, f"{sc['id']}.mp3")
            tts = edge_tts.Communicate(sc["narr"], voice, rate=rate)
            await tts.save(mp3)
            d = duration_of(mp3)
            timings[v["id"]][sc["id"]] = d
            print(f"[ok] {v['id']}/{sc['id']}: {d}s  {sc['narr'][:20]}…")
    with open(os.path.join(BASE, "timings.json"), "w", encoding="utf-8") as f:
        json.dump(timings, f, ensure_ascii=False, indent=1)
    for vid, t in timings.items():
        print(f"{vid} 合計ナレーション: {round(sum(t.values()), 1)}s")


asyncio.run(main())
