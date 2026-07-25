#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ガジュマル(仮称)サイト LP検査(CI用)— 性能予算と禁止表現をコードで守る
- サイズ予算: 各ページ 50KB以下
- 禁止表現: 誇大な断定表現の混入チェック(守り部ゲート)
- 基本要件: lang=ja / viewport / title / description の存在
"""
import glob
import os
import re
import sys

BASE = os.path.join(os.path.dirname(__file__), "..")
SITE_DIR = os.path.join(BASE, "site", "gajumaru")
SITE_GLOB = os.path.join(SITE_DIR, "**", "*.html")
SIZE_BUDGET = 50 * 1024

FORBIDDEN = [
    "業界最安", "絶対", "100%削減", "必ず成功",
    "誰でも儲かる", "確実に安くなる", "保証します",
]


def main():
    pages = sorted(set(glob.glob(SITE_GLOB, recursive=True)))
    if not pages:
        print(f"[ERROR] {SITE_DIR} に検査対象のHTMLがない")
        sys.exit(1)

    errors = []
    for path in pages:
        rel = os.path.relpath(path, BASE)
        size = os.path.getsize(path)
        if size > SIZE_BUDGET:
            errors.append(f"{rel}: サイズ予算超過 {size}B > {SIZE_BUDGET}B")
        html = open(path, encoding="utf-8").read()
        # 禁止表現の検査対象は「利用者に見える文言」のみ。CSS/JSを除外する
        visible = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
        for word in FORBIDDEN:
            if word in visible:
                errors.append(f"{rel}: 禁止表現『{word}』(マモリさんゲート)")
        for req, label in [
            ('lang="ja"', "lang属性"),
            ("viewport", "viewportメタ"),
            ("<title>", "title"),
            ('name="description"', "description"),
        ]:
            if req not in html:
                errors.append(f"{rel}: 基本要件欠落 {label}")

    for e in errors:
        print(f"[ERROR] {e}")
    print(f"サイト検査完了: {len(pages)}ページ / エラー {len(errors)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
