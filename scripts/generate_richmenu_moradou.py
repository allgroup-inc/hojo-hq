#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂(株式会社フクギイロ)LINEリッチメニュー画像(2500x1686・6分割)

正式原稿 docs/フクギイロ_LINE運用原稿.md §B の6ボタン構成を、ブランドガイドv1の
配色(朱#B9502F・黄#F2B705・漆喰#FFFBF4)で描画する。
出力: posts/images/richmenu_moradou.png (LINE Official Account Manager にアップロード)

※「沖縄企業のミカタ」(株式会社GLOW・ネイビー/オレンジ・scripts/generate_richmenu.py)とは
  別サービス。遷移先を mikata.okinawa 側にしないこと(CLAUDE.md 混同表記の禁止)。
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "..", "posts", "images", "richmenu_moradou.png")

W, H = 2500, 1686
COLS, ROWS = 3, 2
GAP = 32

SHU = (185, 80, 47)        # 朱 #B9502F
KI = (242, 183, 5)         # 黄 #F2B705
SHIKKUI = (255, 251, 244)  # 漆喰 #FFFBF4
SUMI = (61, 42, 34)        # 本文の墨(朱に馴染む暖かい濃茶)
MUTED = (140, 116, 104)

BOLD = next((p for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/meiryob.ttc"] if os.path.exists(p)), None)
REG = next((p for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "C:/Windows/Fonts/YuGothR.ttc", "C:/Windows/Fonts/meiryo.ttc"] if os.path.exists(p)), BOLD)
if not BOLD:
    sys.exit("[error] 日本語フォントが見つかりません")


def font(bold, size):
    return ImageFont.truetype(BOLD if bold else REG, size)


# (メイン, サブ, 遷移先パス) — docs/フクギイロ_LINE運用原稿.md §B の並び順
CELLS = [
    ("3分診断",        "関係しそうな制度を見る",   "/fukugiiro/shindan/"),
    ("市町村で探す",    "お住まいの地域から",       "/fukugiiro/area/"),
    ("申請準備シート",  "持ち物と窓口の聞き方",     "/fukugiiro/kit/"),
    ("もらい忘れって?", "はじめての方へ",          "/fukugiiro/"),
    ("受給を報告する",  "「もらえた」を教えてください", "/fukugiiro/houkoku/"),
    ("よくある質問",    "不安なことをやさしく",     "/fukugiiro/#faq"),
]


def draw():
    img = Image.new("RGB", (W, H), SHU)
    d = ImageDraw.Draw(img)
    cw = (W - GAP * (COLS + 1)) // COLS
    ch = (H - GAP * (ROWS + 1)) // ROWS

    mf = font(True, 78)
    sf = font(False, 38)
    bar_h, bar_gap, line_gap = 16, 44, 30

    for i, (main, sub, _path) in enumerate(CELLS):
        col, row = i % COLS, i // COLS
        x = GAP + col * (cw + GAP)
        y = GAP + row * (ch + GAP)

        d.rounded_rectangle([x, y, x + cw, y + ch], radius=36, fill=SHIKKUI)

        mh = d.textbbox((0, 0), main, font=mf)[3]
        sh = d.textbbox((0, 0), sub, font=sf)[3]
        block = bar_h + bar_gap + mh + line_gap + sh
        ty = y + (ch - block) // 2
        tx = x + 56

        d.rounded_rectangle([tx, ty, tx + 120, ty + bar_h], radius=8, fill=KI)
        d.text((tx, ty + bar_h + bar_gap), main, font=mf, fill=SUMI)
        d.text((tx, ty + bar_h + bar_gap + mh + line_gap), sub, font=sf, fill=MUTED)

        # 和文フォントに ">" 系の字形が無いことがあるため図形で描く(豆腐回避)
        r = 44
        cx, cy = x + cw - 86, y + ch - 86
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SHU)
        d.polygon([(cx - 9, cy - 19), (cx - 9, cy + 19), (cx + 17, cy)], fill=SHIKKUI)

    return img


def main():
    img = draw()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    size_kb = os.path.getsize(OUT) / 1024
    rel = os.path.relpath(OUT, os.path.join(BASE_DIR, ".."))
    print(f"[ok] {W}x{H} 6分割リッチメニューを生成 → {rel} ({size_kb:.0f}KB)")
    # LINEのリッチメニュー画像は1MBまで
    if size_kb > 1024:
        print(f"[warn] 1MBを超えています({size_kb:.0f}KB)。LINEにアップロードできません")
        return 1
    print("\nLINE Official Account Manager でのタップ領域(テンプレート: 大・6分割)")
    for i, (main, _sub, path) in enumerate(CELLS):
        print(f"  {i+1}. {main} → https://allgroup-inc.github.io/hojo-hq{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
