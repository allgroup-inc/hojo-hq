#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""もらいわすれ堂 Instagram 投稿画像(1080x1080)を統一デザインで生成する。

デザイン原則:
- ヘッダーの主役は「もらいわすれ堂」ロゴ(icon-512-tile.png / 朱色アイコン)。
- 運営元「株式会社フクギイロ」は最下部に小さくクレジット(フクギの木マーク)。
- 絵文字(🌿🌺)や見切れた装飾は使わない。ブランド配色のみで構成。
- 配色: 朱#B9502F・黄#F2B705・漆喰#FFFBF4・深緑#1A6B52・墨#1F2A2E。

各投稿は (見出し行, サブ行) のテキストだけ差し替える。見出しは幅に合わせて自動縮小。
事実(制度名・金額・締切)は含めない。締切表現は「約1か月前から」で統一(7日前は誤り)。
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

W = H = 1080
SHIKKUI = (255, 251, 244); SHU = (185, 80, 47); FUKAMIDORI = (26, 107, 82)
SUMI = (31, 42, 46); KI = (242, 183, 5); MUTED = (120, 110, 95); SAGE = (150, 178, 160)
ASSETS = os.path.join(os.path.dirname(__file__), "..", "site", "fukugiiro", "assets")
OUT = os.path.join(os.path.dirname(__file__), "..", "posts", "moradou")
FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def font(sz, bold=True):
    return ImageFont.truetype(FB if bold else FR, sz)


def fit_headline(draw, lines, max_w, start=92, floor=58):
    """見出しが max_w に収まる最大フォントサイズを返す。"""
    sz = start
    while sz > floor:
        f = font(sz)
        if all(draw.textlength(ln, font=f) <= max_w for ln in lines):
            return sz
        sz -= 2
    return floor


def make_post(headline, sub, out_name):
    img = Image.new("RGB", (W, H), SHIKKUI)
    d = ImageDraw.Draw(img)

    # 上部の帯 + ドット列
    d.rectangle([0, 0, W, 26], fill=FUKAMIDORI)
    x, i = 20, 0
    while x < W - 10:
        d.ellipse([x - 7, 44 - 7, x + 7, 44 + 7], fill=[KI, SHIKKUI, SAGE][i % 3])
        x += 34; i += 1

    # ヘッダー: もらいわすれ堂ロゴ
    logo = Image.open(os.path.join(ASSETS, "icon-512-tile.png")).convert("RGBA").resize((104, 104), Image.LANCZOS)
    img.paste(logo, (70, 82), logo)
    d.text((194, 92), "もらいわすれ堂", font=font(50), fill=SHU)
    d.text((196, 154), "@moradou.okinawa", font=font(30, False), fill=SUMI)

    # 見出し(自動フィット・2行想定)
    hz = fit_headline(d, headline, W - 140)
    hy = 356
    lh = int(hz * 1.32)
    # 2行なら中心を合わせて配置
    total = lh * len(headline)
    hy = 300 + (300 - total) // 2 if len(headline) <= 2 else 300
    for j, ln in enumerate(headline):
        d.text((70, hy + j * lh), ln, font=font(hz), fill=SHU)

    # サブ
    sy = 624
    for j, ln in enumerate(sub):
        d.text((70, sy + j * 66), ln, font=font(46), fill=SUMI)

    # 波線
    d.line([(x, 880 + int(14 * math.sin(x / 70.0))) for x in range(0, W + 1, 6)], fill=SAGE, width=4)

    # フッター文言
    d.text((70, 934), '沖縄の給付金・手当の"もらい忘れ"を防ぐ', font=font(34, False), fill=MUTED)

    # 3分診断ピル
    pw, ph = 232, 74; px, py = W - 70 - pw, 924
    d.rounded_rectangle([px, py, px + pw, py + ph], radius=ph // 2, fill=SHU)
    t = "3分診断"; ft = font(40); tb = d.textbbox((0, 0), t, font=ft)
    d.text((px + (pw - (tb[2] - tb[0])) // 2 - tb[0], py + (ph - (tb[3] - tb[1])) // 2 - tb[1]), t, font=ft, fill=(255, 255, 255))

    # 運営元クレジット
    mark = Image.open(os.path.join(ASSETS, "fukugiiro-corp-mark-512.png")).convert("RGBA").resize((40, 40), Image.LANCZOS)
    img.paste(mark, (70, 1016), mark)
    d.text((118, 1024), "運営: 株式会社フクギイロ", font=font(24, False), fill=MUTED)

    path = os.path.join(OUT, out_name)
    img.save(path, "PNG")
    print("saved", out_name, "headline_size", hz)


POSTS = [
    (["知らないだけで、", "もらい忘れ。"], ["沖縄の給付金・手当、", "あなたの世帯は大丈夫?"], "ig-1.png"),
    (["沖縄のひとり親", "家庭の方へ。"], ["使えるかもしれない制度、", "いくつ知ってる?"], "ig-2.png"),
    (["「要確認」と、", "正直に書く理由。"], ["確認しきれないことは、", "隠さない。"], "ig-3.png"),
    (["名前も住所も、", "いりません。"], ["3分診断は匿名。", "回答は端末の中だけ。"], "ig-4.png"),
    (["「締切7日前」じゃ、", "間に合わない。"], ["だからLINEで、", "約1か月前からお知らせ。"], "ig-5.png"),
]

if __name__ == "__main__":
    for hl, sub, name in POSTS:
        make_post(hl, sub, name)
