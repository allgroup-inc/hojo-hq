#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 印刷物用の固定QRコード画像を作る(2026-10-30 福田さんの確認事項④)

QRコードは転送先(サイト・SNS・LINE)を直接指さず、/go/<チャネル>/ を指す。
- 読み取られた回数を GA4 で経路別に数えられる(LINE以外は qr_redirect、LINEは line_redirect の channel=card)
- 転送先が変わっても、印刷したQRはそのまま使える(scripts/generate_go_pages.py の dest を変えるだけ)

使い方: pip install "qrcode[pil]" → python scripts/generate_go_qr.py
出力:   site/assets/qr/<チャネル>.png(公開してよいURLだけを入れる)
"""
import os
import sys

try:
    import qrcode
except ImportError:
    sys.exit('qrcode が無いため作れません: pip install "qrcode[pil]"')

BASE_URL = "https://allgroup-inc.github.io/hojo-hq/go/"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "assets", "qr")

# 印刷物に載せる固定QR(チャネルは scripts/generate_go_pages.py の CHANNELS にあるもの)
QR_CHANNELS = {
    "card": "沖縄企業のミカタ LINE公式",
    "qr-mikata": "沖縄企業のミカタ(サイト)",
    "qr-yuntaku": "ゆんたく経営相談室",
    "qr-world": "世界の架け橋",
    "qr-ig": "Instagram(沖縄企業のミカタ)",
    "qr-fb": "Facebook(沖縄企業のミカタ)",
}


def main():
    sys.path.insert(0, os.path.dirname(__file__))
    from generate_go_pages import CHANNELS  # noqa: PLC0415
    os.makedirs(OUT_DIR, exist_ok=True)
    for ch, label in QR_CHANNELS.items():
        if ch not in CHANNELS:
            sys.exit(f"/go/{ch}/ が CHANNELS にありません(先に generate_go_pages.py に足す)")
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=20, border=4)
        qr.add_data(f"{BASE_URL}{ch}/")
        qr.make(fit=True)
        qr.make_image(fill_color="#00335C", back_color="white").save(os.path.join(OUT_DIR, f"{ch}.png"))
        print(f"[ok] {ch}.png  {label}  → {BASE_URL}{ch}/")


if __name__ == "__main__":
    main()
