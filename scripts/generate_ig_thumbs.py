#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LP用のInstagram投稿プレビューサムネを生成する(2026-08-26 小柳さん指示)。

「サイトからインスタに行ってもらうには、アイコンではなく投稿そのものを見せるのが
最も効く」という調査結果に基づき、週次で自動生成される投稿画像
(site/staff/haruka/img/ig1-5.png・1080px)から、LP掲載用の軽量サムネ
(360px WebP)を3枚つくる。fukugiiro-weekly-report が毎週これを再実行するため、
LPのプレビューは常に「今週の投稿」に自動で入れ替わる。

出力: site/fukugiiro/assets/ig/ig1.webp〜ig3.webp(各20KB前後)
元画像が無い週はスキップ(前回のサムネが残り、LPは壊れない)。
"""
import os
from PIL import Image

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(BASE, "site", "staff", "haruka", "img")
OUT = os.path.join(BASE, "site", "fukugiiro", "assets", "ig")


def main():
    os.makedirs(OUT, exist_ok=True)
    made = 0
    for i in (1, 2, 3):
        src = os.path.join(SRC, f"ig{i}.png")
        if not os.path.exists(src):
            print(f"[info] {src} なし: スキップ(前回サムネを維持)")
            continue
        im = Image.open(src).convert("RGB")
        im.thumbnail((360, 360), Image.LANCZOS)
        dst = os.path.join(OUT, f"ig{i}.webp")
        im.save(dst, "WEBP", quality=78)
        made += 1
        print(f"ok: {dst} ({os.path.getsize(dst)//1024}KB)")
    print(f"IGサムネ生成: {made}枚")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
