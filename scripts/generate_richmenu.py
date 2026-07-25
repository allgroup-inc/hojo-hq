#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq デザイン部(エガクさん) — LINEリッチメニュー画像(2500x1686, 2x2)
docs/LINE運用設計.md §2 の4ボタン案をブランド配色で描画する。
出力: posts/images/richmenu.png (LINE Official Account Manager にアップロード)
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(__file__)
OUT = os.path.join(BASE_DIR, "..", "posts", "images", "richmenu.png")

W, H = 2500, 1686
GAP = 36
NAVY = (0, 51, 92)
SUMI = (2, 28, 48)
GOLD = (248, 136, 0)
WHITE = (247, 245, 241)

BOLD = next((p for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/meiryob.ttc"] if os.path.exists(p)), None)
REG = next((p for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/YuGothR.ttc", "C:/Windows/Fonts/meiryo.ttc"] if os.path.exists(p)), BOLD)
if not BOLD:
    sys.exit("[error] 日本語フォントなし")


def font(bold, size):
    return ImageFont.truetype(BOLD if bold else REG, size)


# (メイン, サブ, マーク)
CELLS = [
    ("制度をさがす",   "使える補助金を今すぐチェック", "→"),
    ("会社情報を登録", "貴社専用の制度通知を受け取る", "→"),
    ("専門家に相談",   "申請サポートにおつなぎ",       "→"),
    ("事業承継の相談", "後継ぎ・M&Aのご相談(秘密厳守)", "→"),
]

img = Image.new("RGB", (W, H), SUMI)
d = ImageDraw.Draw(img)
cw, ch = (W - GAP * 3) // 2, (H - GAP * 3) // 2

for i, (main, sub, mark) in enumerate(CELLS):
    col, row = i % 2, i // 2
    x = GAP + col * (cw + GAP)
    y = GAP + row * (ch + GAP)
    # カード(ネイビーグラデ風: 上下2色)
    d.rounded_rectangle([x, y, x + cw, y + ch], radius=40, fill=NAVY,
                        outline=GOLD, width=6)
    # 金のアクセントバー
    d.rounded_rectangle([x + 64, y + 88, x + 220, y + 104], radius=8, fill=GOLD)
    # メイン
    mf = font(True, 120)
    d.text((x + 64, y + 160), main, font=mf, fill=WHITE)
    # サブ
    sf = font(False, 56)
    d.text((x + 64, y + 330), sub, font=sf, fill=(176, 196, 214))
    # 右下の矢印サークル
    r = 64
    cx, cy = x + cw - 120, y + ch - 120
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD)
    af = font(True, 72)
    aw = d.textlength(mark, font=af)
    d.text((cx - aw / 2, cy - 46), mark, font=af, fill=SUMI)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
img.save(OUT, "PNG", optimize=True)
print(f"[ok] richmenu.png (2500x1686) を生成 → posts/images/richmenu.png")
