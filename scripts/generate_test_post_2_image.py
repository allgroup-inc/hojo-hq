#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate test post 2 image (Template2, okinawa_ric-3 事業承継推進事業). 1080x1350."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "ig_posts_test", "test_post_2.png")
W, H = 1080, 1350
NAVY, ORANGE, WHITE = (0, 51, 92), (248, 136, 0), (255, 255, 255)
FONTS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
         "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
         "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"]

def font(size):
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def center(d, text, y, f, fill):
    w = d.textbbox((0, 0), text, font=f)[2]
    d.text(((W - w) // 2, y), text, font=f, fill=fill)

img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
for y in range(H):
    r = y / H
    d.line([(0, y), (W, y)], fill=tuple(int(NAVY[i] * (1 - r) + ORANGE[i] * r) for i in range(3)))

center(d, "沖縄県で", 170, font(60), WHITE)
center(d, "事業承継の支援を", 260, font(66), WHITE)
center(d, "受けられるって知ってますか？", 360, font(56), WHITE)

# 3-step flow (panel keeps text readable over the gradient)
d.rounded_rectangle([90, 560, 990, 1010], radius=24, fill=(0, 31, 63))
steps = [("1", "相談", "LINEで気軽に相談"),
         ("2", "確認", "公式ページで支援内容を確認（要確認）"),
         ("3", "申込", "申込方法・締切を確認（要確認）")]
y = 600
for n, label, desc in steps:
    d.ellipse([130, y, 210, y + 80], fill=ORANGE)
    d.text((155, y + 12), n, font=font(44), fill=WHITE)
    d.text((240, y + 2), label, font=font(40), fill=WHITE)
    d.text((240, y + 56), desc, font=font(26), fill=(220, 230, 240))
    y += 135

center(d, "事業承継推進事業（沖縄県産業振興公社）", 1080, font(30), WHITE)
center(d, "金額・締切・費用は要確認 / 相談受付中", 1140, font(28), WHITE)
center(d, "沖縄企業のミカタ", 1250, font(26), WHITE)
img.save(OUT)
print("saved", OUT)
