#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 配布用QRカード生成(体制総点検_20260801 T1)
催事・商談・既存顧客接点で手渡しする紙物のデータを生成する。
QRは /go/card/ 経由(go-link-discipline: 紙経路もチャネル計測する)。

出力: posts/card/card_meishi.png (名刺サイズ 91x55mm/350dpi)
      posts/card/card_a6.png     (A6 POP 105x148mm/350dpi)
使い方: python scripts/generate_card.py
"""
import os
import sys

import qrcode
from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "posts", "card")
QR_URL = "https://allgroup-inc.github.io/hojo-hq/go/card/"
NAVY = (0, 51, 92)
ORANGE = (248, 136, 0)
WHITE = (247, 245, 241)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\meiryob.ttc",
    r"C:\Windows\Fonts\meiryo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_qr(px):
    q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(QR_URL)
    q.make(fit=True)
    img = q.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((px, px), Image.NEAREST)


def center(draw, text, f, y, width, fill):
    w = draw.textlength(text, font=f)
    draw.text(((width - w) / 2, y), text, font=f, fill=fill)


def card_meishi():
    """名刺サイズ 91x55mm @350dpi = 1254x758"""
    W, H = 1254, 758
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 10], fill=ORANGE)
    center(d, "沖縄企業のミカタ", font(86), 60, W - 420, WHITE)
    center(d, "沖縄で使える補助金・助成金、毎日ぜんぶ。", font(40), 180, W - 420, WHITE)
    center(d, "運営: 株式会社GLOW", font(32), 250, W - 420, (180, 200, 220))
    d.rounded_rectangle([70, 330, W - 490, 470], radius=18, fill=ORANGE)
    center(d, "LINE登録 無料", font(52), 358, W - 420, NAVY)
    for i, line in enumerate([
        "✓ 30秒診断で貴社に合う制度がわかる",
        "✓ 締切の約1か月前からLINEでお知らせ",
        "✓ 登録企業の利用料はずっと無料",
    ]):
        d.text((84, 510 + i * 62), line, font=font(38), fill=WHITE)
    qr = make_qr(330)
    im.paste(qr, (W - 390, H // 2 - 165))
    # ラベルはQRの中心に合わせて中央揃え(2026-08-11 小柳さん指示)
    label = "QRでLINE登録"
    f_label = font(34)
    qr_cx = (W - 390) + 165
    d.text((qr_cx - d.textlength(label, font=f_label) / 2, H // 2 + 175),
           label, font=f_label, fill=WHITE)
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, "card_meishi.png"))
    print("[ok] card_meishi.png (1254x758 / 91x55mm 350dpi)")


def card_a6():
    """A6 POP 105x148mm @350dpi = 1447x2039"""
    W, H = 1447, 2039
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 14], fill=ORANGE)
    center(d, "御社が使える補助金、", font(96), 120, W, WHITE)
    center(d, "眠っていませんか?", font(96), 240, W, WHITE)
    center(d, "沖縄で使える補助金・助成金を毎日自動チェック", font(46), 420, W, (200, 214, 228))
    d.rounded_rectangle([120, 540, W - 120, 700], radius=24, fill=ORANGE)
    center(d, "30秒診断 無料", font(84), 570, W, NAVY)
    # チェックリストはブロックごと中央配置(行頭の✓は縦に揃えたまま全体を中央へ。
    # 2026-08-11 小柳さん指示「文字関係を中央に揃える」)
    checks = [
        "✓ 市町村・業種などを選ぶだけ",
        "✓ 貴社に合う制度と金額の目安がわかる",
        "✓ 締切の約1か月前からLINEでお知らせ",
        "✓ 登録企業の利用料はずっと無料",
    ]
    f_check = font(52)
    block_w = max(d.textlength(s, font=f_check) for s in checks)
    x0 = (W - block_w) / 2
    for i, line in enumerate(checks):
        d.text((x0, 790 + i * 84), line, font=f_check, fill=WHITE)
    qr = make_qr(620)
    im.paste(qr, ((W - 620) // 2, 1180))
    center(d, "QRを読み取ってLINE登録", font(52), 1830, W, WHITE)
    center(d, "沖縄企業のミカタ|運営: 株式会社GLOW", font(38), 1930, W, (180, 200, 220))
    im.save(os.path.join(OUT, "card_a6.png"))
    print("[ok] card_a6.png (1447x2039 / A6 350dpi)")


if __name__ == "__main__":
    card_meishi()
    card_a6()
