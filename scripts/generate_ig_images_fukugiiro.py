#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 IG投稿画像 自動生成(遥さん運用・2026-08-15 小柳さん決裁「投稿は遥がやる」)

data/fukugiiro/ig_neta.json の各ネタから 1080x1080 の投稿画像を生成し、
site/staff/haruka/img/ig<no>.png に置く(遥さんボードから長押し保存→そのまま投稿)。

デザイン: もらいわすれ堂ブランドガイドv1(朱#B9502F・黄#F2B705・漆喰#FFFBF4)。
文字は image_text(画像用の短い文)があればそれを、なければ title を使用。
正確性: 画像には断定的な金額・期日を入れない(ig_neta 側の caution を尊重し、
詳細は「プロフィールのリンクから」へ誘導する)。
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.join(os.path.dirname(__file__), "..")
NETA = os.path.join(BASE, "data", "fukugiiro", "ig_neta.json")
OUT_DIR = os.path.join(BASE, "site", "staff", "haruka", "img")

SHIPPORI = os.path.expanduser("~/.fonts/ShipporiMincho-SemiBold.ttf")
SHIPPORI_ALT = "fonts/ShipporiMincho-SemiBold.ttf"  # CI用(リポジトリ外キャッシュ or 事前DL)
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

SHU = (185, 80, 47)      # 朱(琉球赤瓦)#B9502F
KI = (242, 183, 5)       # 黄 #F2B705
SHIKKUI = (255, 251, 244)  # 漆喰 #FFFBF4
INK = (59, 50, 43)       # 墨
UMI = (111, 174, 164)    # 島の海


def font(path_candidates, size):
    for p in path_candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    """日本語向けの単純折返し(文字単位)。句読点の行頭は避ける。"""
    lines, cur = [], ""
    for ch in text:
        t = cur + ch
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if ch in "、。!?)」』・":
                lines.append(cur[:-1] if cur else cur)
                cur = (cur[-1] if cur else "") + ch
            else:
                lines.append(cur)
                cur = ch
    if cur:
        lines.append(cur)
    return lines


def rainbow(draw, cx, cy, scale=1.0):
    """ロゴモチーフの三色虹(簡易)。単独使用不可ルールがあるため朝日(花)も添える。"""
    for r, color in [(int(70 * scale), SHU), (int(48 * scale), KI), (int(26 * scale), UMI)]:
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=180, end=360, fill=color,
                 width=int(16 * scale))
    # おはなのひざし(朝日)
    sx, sy = cx + int(88 * scale), cy - int(74 * scale)
    pr = int(7 * scale)
    for dx, dy in [(-1.6, 0), (1.6, 0), (0, -1.6), (0, 1.6), (-1.1, -1.1), (1.1, -1.1), (-1.1, 1.1), (1.1, 1.1)]:
        draw.ellipse([sx + dx * pr * 1.9 - pr, sy + dy * pr * 1.9 - pr,
                      sx + dx * pr * 1.9 + pr, sy + dy * pr * 1.9 + pr], fill=(245, 206, 110))
    draw.ellipse([sx - pr * 1.7, sy - pr * 1.7, sx + pr * 1.7, sy + pr * 1.7], fill=(242, 193, 78))


def make_image(item):
    W = H = 1080
    img = Image.new("RGB", (W, H), SHIKKUI)
    d = ImageDraw.Draw(img)
    # 上下の帯
    d.rectangle([0, 0, W, 14], fill=KI)
    d.rectangle([0, H - 120, W, H], fill=SHU)

    f_brand = font([SHIPPORI, SHIPPORI_ALT, NOTO], 44)
    f_title = font([SHIPPORI, SHIPPORI_ALT, NOTO], 76)
    f_sub = font([NOTO, SHIPPORI, SHIPPORI_ALT], 38)
    f_foot = font([NOTO, SHIPPORI, SHIPPORI_ALT], 36)

    # ブランド名(上部)
    d.text((W / 2, 96), "もらいわすれ堂", font=f_brand, fill=SHU, anchor="mm")
    d.text((W / 2, 152), "あなたが受け取るまで、いっしょに。", font=font([NOTO], 30), fill=UMI, anchor="mm")

    # タイトル(中央)
    text = item.get("image_text") or item["title"]
    lines = wrap(d, text, f_title, 900)[:5]
    lh = 104
    y0 = 470 - lh * (len(lines) - 1) / 2
    for i, ln in enumerate(lines):
        d.text((W / 2, y0 + i * lh), ln, font=f_title, fill=INK, anchor="mm")

    # サブ(あれば)
    sub = item.get("image_sub", "")
    if sub:
        d.text((W / 2, y0 + len(lines) * lh + 30), sub, font=f_sub, fill=SHU, anchor="mm")

    # 虹と朝日(下部中央・帯の上)
    rainbow(d, W / 2, H - 190, scale=0.9)

    # フッター帯
    d.text((W / 2, H - 60), "くわしくは プロフィールのリンクから", font=f_foot, fill=SHIKKUI, anchor="mm")
    return img


def main():
    with open(NETA, encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(OUT_DIR, exist_ok=True)
    n = 0
    for item in data.get("items", []):
        img = make_image(item)
        out = os.path.join(OUT_DIR, f"ig{item['no']}.png")
        img.save(out, optimize=True)
        n += 1
    print(f"IG投稿画像 生成: {n}枚 → site/staff/haruka/img/")


if __name__ == "__main__":
    main()
