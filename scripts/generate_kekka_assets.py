#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ(kekka_mag)ブランドアセット生成
アイコン(note/X共用)・Xヘッダー・note記事アイキャッチを生成する。

ブランド定義(2026-08-06):
- 配色: 墨黒 #101418 × 白 #FFFFFF × マーカー黄 #FFD400(研究ノートの蛍光マーカーのイメージ)
- ミカタ(ネイビー×オレンジ)とは意図的に別配色(名義分離)
- フォント: IPAゴシック(リポジトリ環境・Actions両方で利用可能)

使い方:
  python scripts/generate_kekka_assets.py                 # アイコン+Xヘッダー
  python scripts/generate_kekka_assets.py --eyecatch "記事タイトル" --out assets/kekka/eyecatch_05.png
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(BASE, "assets", "kekka")
FONT_PATHS = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
]

INK = (16, 20, 24)       # 墨黒
WHITE = (255, 255, 255)
MARKER = (255, 212, 0)   # マーカー黄

MAG_NAME = "結果の出し方がわかってしまうマガジン"
TAGLINE = "世の中の実例と失敗しない方法を、出典つきで「共通の型」に。"
BYLINE = "AI編集部"


def font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise RuntimeError("日本語フォントが見つかりません")


def bold_text(draw, xy, text, fnt, fill, anchor=None, stroke=2):
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=fill)


def make_icon(path):
    """1024x1024 アイコン(正式版・2026-08-06 小柳さん決裁「一番伸びる組み合わせ」):
    マーカー黄地に黒の「結」+黒下線。小サイズ表示での視認性最優先。"""
    img = Image.new("RGB", (1024, 1024), MARKER)
    d = ImageDraw.Draw(img)
    bold_text(d, (512, 470), "結", font(600), INK, anchor="mm", stroke=10)
    d.rounded_rectangle([252, 810, 772, 858], radius=24, fill=INK)
    img.save(path)


def make_x_header(path):
    """1500x500 Xヘッダー。"""
    img = Image.new("RGB", (1500, 500), INK)
    d = ImageDraw.Draw(img)
    bold_text(d, (750, 195), MAG_NAME, font(64), WHITE, anchor="mm", stroke=2)
    d.rounded_rectangle([430, 262, 1070, 278], radius=8, fill=MARKER)
    d.text((750, 330), TAGLINE, font=font(34), fill=(200, 205, 210), anchor="mm")
    d.text((750, 410), f"{BYLINE}|AIが下書き、人間が検品してから出します", font=font(28), fill=(140, 146, 152), anchor="mm")
    img.save(path)


def wrap(text, fnt, max_w, draw):
    lines, line = [], ""
    for ch in text:
        if draw.textlength(line + ch, font=fnt) > max_w:
            lines.append(line)
            line = ch
        else:
            line += ch
    if line:
        lines.append(line)
    return lines


def make_eyecatch(title, path):
    """1280x670 note記事アイキャッチ: 黄ラベル+白タイトル。"""
    img = Image.new("RGB", (1280, 670), INK)
    d = ImageDraw.Draw(img)
    # 上部ラベル(マガジン名)
    label_f = font(30)
    lw = d.textlength(MAG_NAME, font=label_f)
    d.rounded_rectangle([70, 70, 70 + lw + 44, 128], radius=12, fill=MARKER)
    d.text((92, 99), MAG_NAME, font=label_f, fill=INK, anchor="lm")
    # タイトル(折り返し・最大4行)
    title_f = font(72)
    lines = wrap(title, title_f, 1140, d)[:4]
    y = 220
    for ln in lines:
        bold_text(d, (70, y), ln, title_f, WHITE, stroke=2)
        y += 96
    # 下部
    d.rounded_rectangle([70, 586, 250, 600], radius=7, fill=MARKER)
    d.text((1210, 594), BYLINE, font=font(30), fill=(160, 166, 172), anchor="rm")
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eyecatch", help="記事タイトル(アイキャッチのみ生成)")
    ap.add_argument("--out", help="出力パス(--eyecatch使用時)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    if args.eyecatch:
        out = args.out or os.path.join(OUT_DIR, "eyecatch.png")
        make_eyecatch(args.eyecatch, out)
        print(f"生成: {out}")
        return
    make_icon(os.path.join(OUT_DIR, "icon.png"))
    make_x_header(os.path.join(OUT_DIR, "header_x.png"))
    print(f"生成: {OUT_DIR}/icon.png, header_x.png")


if __name__ == "__main__":
    main()
