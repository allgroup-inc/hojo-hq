#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TV出演報告のIG投稿カード(1080x1350)。許諾不要素材のみ(嶺井さん本人写真+文字)。
使い方: python scripts/generate_tv_card.py → posts/tv/tv_shutsuen.png"""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "posts", "tv")
NAVY = (10, 27, 51); NAVY2 = (14, 36, 64); ORANGE = (248, 136, 0); WHITE = (255, 255, 255)
F = [r"C:\Windows\Fonts\meiryob.ttc", r"C:\Windows\Fonts\meiryo.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]

def font(size):
    for p in F:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def center(d, text, f, y, W, fill):
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)

W, H = 1080, 1350
im = Image.new("RGB", (W, H), NAVY)
d = ImageDraw.Draw(im)
for y in range(H):  # 上下グラデーション
    t = y / H
    d.line([(0, y), (W, y)], fill=tuple(int(NAVY2[i] + (NAVY[i] - NAVY2[i]) * t) for i in range(3)))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, 10], fill=ORANGE)

# ブランド
bf = font(40)
d.text((70, 56), "沖縄企業のミカタ", font=bf, fill=WHITE)
d.line([(70, 116), (330, 116)], fill=ORANGE, width=5)

# 丸型写真
photo = Image.open(os.path.join(BASE, "site", "assets", "minei.webp")).convert("RGB")
size = 460
photo = ImageOps.fit(photo, (size, size), Image.LANCZOS)
mask = Image.new("L", (size, size), 0)
ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
ring = Image.new("RGB", (size + 16, size + 16), ORANGE)
rmask = Image.new("L", (size + 16, size + 16), 0)
ImageDraw.Draw(rmask).ellipse([0, 0, size + 16, size + 16], fill=255)
im.paste(ring, ((W - size - 16) // 2, 180), rmask)
im.paste(photo, ((W - size) // 2, 188), mask)

center(d, "ミカタ監修の嶺井が、", font(76), 720, W, WHITE)
center(d, "テレビに出ます", font(76), 830, W, WHITE)
center(d, "「リゾートキングダム」10月10日放送", font(48), 980, W, ORANGE)
center(d, "元・沖縄振興開発金融公庫(在籍34年)", font(38), 1080, W, (200, 214, 228))
center(d, "補助金・助成金のことは、プロフィールのリンクから", font(34), 1220, W, WHITE)

os.makedirs(OUT, exist_ok=True)
im.save(os.path.join(OUT, "tv_shutsuen.png"), optimize=True)
print("[ok] posts/tv/tv_shutsuen.png (1080x1350)")
