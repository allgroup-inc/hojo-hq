#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ LP検査(CI用)— 性能予算と禁止表現をコードで守る
- サイズ予算: index.html 50KB以下(LP設計書の性能予算)
- 禁止表現: マモリさんの禁止語がLP文言に混入していないか
- 基本要件: lang=ja / viewport / title / description の存在
"""
import os
import re
import sys

BASE = os.path.join(os.path.dirname(__file__), "..")
LP = os.path.join(BASE, "site", "fukugiiro", "index.html")
SIZE_BUDGET = 50 * 1024

FORBIDDEN = ["必ずもらえる", "絶対", "審査なし", "誰でももらえる", "100%", "確実にもらえる", "無条件で支給"]

def main():
    errors = []
    if not os.path.exists(LP):
        print("[ERROR] site/fukugiiro/index.html がない")
        sys.exit(1)
    size = os.path.getsize(LP)
    if size > SIZE_BUDGET:
        errors.append(f"サイズ予算超過: {size}B > {SIZE_BUDGET}B(画像分離・CSS削減を)")
    html = open(LP, encoding="utf-8").read()
    # 禁止表現の検査対象は「利用者に見える文言」のみ。CSS/JSを除外する
    # (失敗台帳 FK-001: CSSの max-width:100% を禁止語『100%』と誤検知した対策)
    visible = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    for word in FORBIDDEN:
        if word in visible:
            errors.append(f"禁止表現『{word}』がLP文言に含まれる(マモリさんゲート)")
    for req, label in [('lang="ja"', "lang属性"), ("viewport", "viewportメタ"),
                       ("<title>", "title"), ('name="description"', "description")]:
        if req not in html:
            errors.append(f"基本要件欠落: {label}")
    for e in errors:
        print(f"[ERROR] {e}")
    print(f"LP検査完了: {size}B / エラー {len(errors)}")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
