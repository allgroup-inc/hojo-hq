#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLOW 世界へ推進LPの「売り場のイメージ」用に、商品写真のイメージ画像を Gemini で作る。

  GEMINI_API_KEY=... python scripts/glow_gen_images.py

出力: site/go/world/assets/images/booth/ai/<名前>.webp(LPの商品カードと同じ名前。差し替えはLP側で行う)(すでにあるものは作り直さない)
すべてAIが作ったイメージ写真。実在の商品・ブランドではないので、ラベルの文字やロゴは入れない。
LP・資料では必ず「※写真はイメージです」と併記する。
"""
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request

from PIL import Image

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "go", "world", "assets", "images", "booth", "ai")
MODELS = ["gemini-2.5-flash-image", "gemini-2.5-flash-image-preview", "gemini-3-pro-image-preview"]

STYLE = ("Professional e-commerce product photograph, bright natural daylight, soft shadow, "
         "clean light cream background, shallow depth of field, high detail, appetizing, no text, "
         "no letters, no logos, no labels with writing, no watermark.")

IMAGES = {
    # 名前: (縦横比, 横幅px, 説明)  ※LPの売り場イメージの商品カードと同じ並び
    "andagi": ("1:1", 640, "Okinawan sata andagi: solid round ball-shaped fried dough snacks about the size of a golf ball, NO hole in the middle, cracked golden-brown surface, a few piled in a small ceramic dish. " + STYLE),
    "mozuku": ("1:1", 640, "Fresh Okinawan mozuku seaweed in vinegar served in a small glass bowl. " + STYLE),
    "umibudo": ("1:1", 640, "Fresh Okinawan sea grapes (umibudo) on a white dish, glossy green beads. " + STYLE),
    "pineapple": ("1:1", 640, "A whole ripe Okinawan pineapple next to a few cut golden pineapple pieces. " + STYLE),
    "soba": ("1:1", 640, "A bowl of Okinawa soba noodles with braised pork belly, pickled ginger and green onion. " + STYLE),
    "glass": ("1:1", 640, "Handmade Ryukyu glass tumblers in blue and green with tiny bubbles, sunlight through them. " + STYLE),
    "bingata": ("1:1", 640, "A neatly folded piece of colorful Okinawan bingata dyed textile with bright floral patterns. " + STYLE),
    "awamori": ("1:1", 640, "A traditional Okinawan awamori spirit in a plain ceramic bottle and a small clay cup. " + STYLE),
    "kokuto": ("1:1", 640, "Chunks of Okinawan brown sugar (kokuto) in a small wooden bowl. " + STYLE),
}


def generate(key, aspect, prompt):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}},
    }
    last = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = f"{model}: HTTP {e.code} {e.read()[:300]!r}"
            print(f"  [skip] {last}")
            continue
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    print(f"  [ok] model={model}")
                    return base64.b64decode(inline["data"])
        last = f"{model}: 画像なし {json.dumps(data)[:300]}"
        print(f"  [skip] {last}")
    raise RuntimeError(last)


def main():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        sys.exit("[error] GEMINI_API_KEY が未設定")
    os.makedirs(OUT_DIR, exist_ok=True)
    failed = []
    for name, (aspect, width, prompt) in IMAGES.items():
        path = os.path.join(OUT_DIR, f"{name}.webp")
        if os.path.exists(path):
            print(f"[keep] {name}")
            continue
        print(f"[gen] {name}")
        try:
            raw = generate(key, aspect, prompt)
        except Exception as e:
            print(f"[error] {name}: {e}")
            failed.append(name)
            continue
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        im.save(path, "WEBP", quality=80, method=6)
        print(f"[saved] {path} {im.size} {os.path.getsize(path) // 1024}KB")
    if failed:
        sys.exit(f"[error] 作れなかった画像: {', '.join(failed)}")


if __name__ == "__main__":
    main()
