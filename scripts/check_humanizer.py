#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — SNS/LINE文面のhumanizer自動検査(2026-08-17 小柳さん決裁・決裁キュー14.c)

humanizerスキルが挙げるAIっぽさの型を機械検査できる範囲でチェックする。
**報告のみでパイプラインは止めない**(ウタガイ懸念: 誤検知で投稿が止まる方が害が大きい。
最終判断は承認ゲートの小柳さん。本スクリプトは承認プレビューLINEに材料を出すだけ)。

検査項目:
  1. 定型フレーズ(いかがでしょうか 等)
  2. ぼかし表現「かもしれません」の多用(1キャプション2回以上)
  3. 書き言葉ダッシュ「——」「—」による接続
  4. 丸数字の列挙(①②③…3個以上)
  5. 絵文字の過剰(1キャプション6個以上)
  6. 書き出し/締めの同一文が複数投稿で反復(バッチ横断)

使い方:
  python scripts/check_humanizer.py                       # posts/launch 全キャプション
  python scripts/check_humanizer.py --stem 09_cta         # 本日分だけ件数を出す
  python scripts/check_humanizer.py --gh-output --stem X  # GitHub Actions用 key=value出力
終了コードは常に0(報告のみ)。
"""
import argparse
import glob
import os
import re
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(__file__), "..")
POSTS_DIR = os.path.join(BASE, "posts", "launch")
CAROUSEL_CAPTION = os.path.join(BASE, "posts", "carousel", "caption.md")

STOCK_PHRASES = [
    "いかがでしょうか",
    "してみてはいかが",
    "必見です",
    "徹底解説",
    "まとめてみました",
    "ご紹介します!",
]
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002600-\U000026FF✅❗⭐]"
)
CIRCLED_RE = re.compile("[①-⑳]")  # ①〜⑳


def extract_caption(md_path):
    """post_social.py と同じ規約: 「## キャプション」節を取り出す。"""
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"## キャプション\n(.*?)(?:\n## |\Z)", text, re.S)
    return (m.group(1).strip() if m else text.strip())


def check_one(name, cap):
    findings = []
    for p in STOCK_PHRASES:
        if p in cap:
            findings.append(f"{name}: 定型フレーズ「{p}」")
    if cap.count("かもしれません") >= 2:
        findings.append(f"{name}: 「かもしれません」が{cap.count('かもしれません')}回(ぼかし過多)")
    if "——" in cap or re.search(r"[^\d]—[^\d]", cap):
        findings.append(f"{name}: ダッシュ「—」接続(書き言葉調)")
    if len(CIRCLED_RE.findall(cap)) >= 3:
        findings.append(f"{name}: 丸数字の列挙(①②③…)")
    n_emoji = len(EMOJI_RE.findall(cap))
    if n_emoji >= 6:
        findings.append(f"{name}: 絵文字{n_emoji}個(過剰)")
    return findings


def check_batch(caps):
    """書き出し行・締め行(URL行を除く)の同一反復をバッチ横断で見る。"""
    findings = []
    firsts, lasts = Counter(), Counter()
    for name, cap in caps:
        # http=URL / #=ハッシュタグ / ※=免責・注記(正確性ルール上の意図的な定型)は反復チェック対象外
        lines = [l.strip() for l in cap.splitlines()
                 if l.strip() and not l.strip().startswith(("http", "#", "※"))]
        if not lines:
            continue
        firsts[lines[0]] += 1
        lasts[lines[-1]] += 1
    for line, n in list(firsts.items()) + list(lasts.items()):
        if n >= 2:
            findings.append(f"(横断) 同一文が{n}投稿で反復: 「{line[:30]}…」" if len(line) > 30
                            else f"(横断) 同一文が{n}投稿で反復: 「{line}」")
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stem", help="本日分の投稿stem(例: 09_cta / carousel)")
    ap.add_argument("--gh-output", action="store_true", help="key=value形式で出力")
    args = ap.parse_args()

    caps = []
    for md in sorted(glob.glob(os.path.join(POSTS_DIR, "[0-9][0-9]_*.md"))):
        caps.append((os.path.splitext(os.path.basename(md))[0], extract_caption(md)))
    if os.path.exists(CAROUSEL_CAPTION):
        with open(CAROUSEL_CAPTION, encoding="utf-8") as f:
            caps.append(("carousel", f.read().strip()))

    all_findings = []
    for name, cap in caps:
        all_findings += check_one(name, cap)
    all_findings += check_batch(caps)

    today_findings = all_findings
    if args.stem:
        today_findings = [f for f in all_findings if f.startswith(args.stem + ":")]

    if args.gh_output:
        n = len(today_findings)
        head = today_findings[0].split(": ", 1)[-1] if today_findings else ""
        if n == 0:
            print("hcheck=✅文面チェック(humanizer): 指摘なし")
        else:
            print(f"hcheck=⚠️文面チェック(humanizer): {n}件(例: {head})。判断はお任せします")
    else:
        if not all_findings:
            print("[ok] humanizer検査: 指摘なし")
        for f in all_findings:
            print(f"[warn] {f}")
        print(f"[done] 検査 {len(caps)}キャプション / 指摘 {len(all_findings)}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
