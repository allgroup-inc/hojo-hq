#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — うごくAIレシピ ブランドアセット生成
アイコン(note/X/LINE共用)・Xヘッダー・noteヘッダー・記事アイキャッチを生成する。

ブランド定義(2026-08-09):
- コンセプト: 「実行ログ」がアイデンティティ。ターミナル(黒い実行画面)×実行OKの緑
- 配色: ターミナル黒 #0D1117 × 実行緑 #3FB950 × 白 #FFFFFF(補助グレー #8B949E)
- 他ブランドと意図的に別配色: ミカタ(ネイビー×オレンジ)/結果マガ(墨黒×マーカー黄)/
  フクギイロ(朱×黄×漆喰)のどれとも重ねない
- フォント: IPAゴシック(リポジトリ環境・Actions両方で利用可能)

使い方:
  python scripts/generate_airecipe_assets.py                    # アイコン+ヘッダー2種
  python scripts/generate_airecipe_assets.py --eyecatch "記事タイトル" --out assets/airecipe/eyecatch_01.png
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(BASE, "assets", "airecipe")
FONT_PATHS = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
]

TERM = (13, 17, 23)      # ターミナル黒
GREEN = (63, 185, 80)    # 実行緑
WHITE = (255, 255, 255)
GRAY = (139, 148, 158)

MAG_NAME = "うごくAIレシピ"
TAGLINE = "公開前に、機械で実際に動かしたAIレシピだけ。"
BYLINE = "生成も検証も機械|公開前に人間がひと目"


def font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise RuntimeError("日本語フォントが見つかりません")


def bold_text(draw, xy, text, fnt, fill, anchor=None, stroke=2):
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=fill)


def term_dots(d, x, y, r=14, gap=44):
    """ターミナルウィンドウの3点(飾り)。"""
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = x + i * gap
        d.ellipse([cx - r, y - r, cx + r, y + r], fill=c)


def make_icon(path):
    """1024x1024 アイコン。ターミナル黒地に実行緑のプロンプト「>」+カーソル。
    小サイズ表示での視認性最優先(文字は入れない)。"""
    img = Image.new("RGB", (1024, 1024), TERM)
    d = ImageDraw.Draw(img)
    # 枠(うっすら緑のターミナル枠)
    d.rounded_rectangle([28, 28, 996, 996], radius=96, outline=GREEN, width=10)
    # プロンプト「>」
    bold_text(d, (330, 512), ">", font(560), GREEN, anchor="mm", stroke=24)
    # カーソル(点滅ブロック)
    d.rounded_rectangle([560, 380, 800, 660], radius=28, fill=GREEN)
    img.save(path)


def make_x_header(path):
    """1500x500 Xヘッダー。"""
    img = Image.new("RGB", (1500, 500), TERM)
    d = ImageDraw.Draw(img)
    term_dots(d, 90, 80)
    d.text((90, 170), "$ run recipe …… OK", font=font(40), fill=GREEN)
    bold_text(d, (750, 265), MAG_NAME, font(96), WHITE, anchor="mm", stroke=3)
    d.text((750, 375), TAGLINE, font=font(40), fill=GRAY, anchor="mm")
    d.text((750, 440), BYLINE, font=font(28), fill=(90, 98, 108), anchor="mm")
    img.save(path)


def make_note_header(path):
    """1280x670 noteプロフィールヘッダー。"""
    img = Image.new("RGB", (1280, 670), TERM)
    d = ImageDraw.Draw(img)
    term_dots(d, 80, 80)
    d.text((80, 170), "$ run recipe …… OK", font=font(36), fill=GREEN)
    bold_text(d, (640, 330), MAG_NAME, font(104), WHITE, anchor="mm", stroke=3)
    d.text((640, 460), TAGLINE, font=font(42), fill=GRAY, anchor="mm")
    d.rounded_rectangle([440, 540, 840, 596], radius=28, outline=GREEN, width=4)
    d.text((640, 568), "実行ログつきで週2回", font=font(30), fill=GREEN, anchor="mm")
    img.save(path)


def wrap(draw, text, fnt, max_w):
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
    """1280x670 記事アイキャッチ(ターミナルウィンドウ風)。タイトルを流し込む。"""
    img = Image.new("RGB", (1280, 670), (24, 30, 38))
    d = ImageDraw.Draw(img)
    # ターミナルウィンドウ
    d.rounded_rectangle([60, 56, 1220, 614], radius=24, fill=TERM, outline=(60, 70, 82), width=2)
    d.rounded_rectangle([60, 56, 1220, 132], radius=24, fill=(30, 38, 48))
    d.rectangle([60, 108, 1220, 132], fill=(30, 38, 48))
    term_dots(d, 120, 94, r=12, gap=40)
    d.text((640, 94), MAG_NAME, font=font(28), fill=GRAY, anchor="mm")
    # プロンプト+タイトル
    d.text((120, 200), "$", font=font(48), fill=GREEN)
    title_f = font(64)
    y = 270
    for line in wrap(d, title, title_f, 1000)[:4]:
        bold_text(d, (120, y), line, title_f, WHITE, stroke=1)
        y += 92
    # フッター: 実行済みバッジ
    d.rounded_rectangle([120, 520, 560, 576], radius=28, fill=GREEN)
    d.text((340, 548), "実行ログつき ▶ 検証済み", font=font(30), fill=TERM, anchor="mm")
    d.text((1160, 548), "週2回更新", font=font(28), fill=GRAY, anchor="rm")
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eyecatch", help="記事タイトル(アイキャッチのみ生成)")
    ap.add_argument("--out", help="アイキャッチ出力パス")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    if args.eyecatch:
        out = args.out or os.path.join(OUT_DIR, "eyecatch.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        make_eyecatch(args.eyecatch, out)
        print(f"生成: {out}")
        return

    make_icon(os.path.join(OUT_DIR, "icon.png"))
    make_x_header(os.path.join(OUT_DIR, "header_x.png"))
    make_note_header(os.path.join(OUT_DIR, "header_note.png"))
    print(f"生成: {OUT_DIR}/icon.png, header_x.png, header_note.png")


if __name__ == "__main__":
    main()
