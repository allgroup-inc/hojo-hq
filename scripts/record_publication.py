#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 公開記録+X告知の自動化(ワンタップ運用の後半)
(設計: docs/note収益化_運営計画v3_月30万.md / 2026-08-06 小柳さん指示「全自動で最終確認だけ」)

人間がnoteで記事を公開したあと、GitHub Actionsの publish-record ワークフローに
記事ID(お題ID/ファイル番号)と公開URLを入れて実行すると:
 1. 記事mdの先頭に公開記録(3役短評つき)を追記
 2. お題キューの該当お題を published に更新
 3. X告知文(記事ヘッダーのA/B/C案)を抽出して出力
    → Xシークレットがあれば post_x_announce.py が自動投稿+リプ欄にURL
    → なければLINE通知に文面を同梱(人間がコピペ投稿)

使い方:
  python scripts/record_publication.py --id 19 --url https://note.com/kekka_mag/n/xxxx [--hook a]
  出力(GITHub Actions用 key=value): article=<path> title=<...> announce=<...>
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
ARTICLE_DIR = os.path.join(BASE, "posts", "note", "tanpatsu")
TOPICS_PATH = os.path.join(BASE, "data", "tanpatsu_topics.json")


def find_article(article_id: str):
    hits = sorted(glob.glob(os.path.join(ARTICLE_DIR, f"{article_id}_*.md")))
    return hits[0] if hits else None


def extract_hooks(text: str):
    """記事ヘッダーのX告知文パック(A/B/C)を抽出する。"""
    hooks = {}
    for m in re.finditer(r"^([ABC])\([^)]*\):\s*(.+)$", text, flags=re.M):
        hooks[m.group(1).lower()] = m.group(2).strip()
    return hooks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="記事ID(例: 19)")
    ap.add_argument("--url", required=True, help="noteの公開URL")
    ap.add_argument("--hook", default="a", choices=["a", "b", "c"], help="X告知文の案(既定: a)")
    args = ap.parse_args()

    if not re.match(r"^https://note\.com/", args.url):
        print(f"エラー: noteのURLではありません: {args.url}", file=sys.stderr)
        return 1

    path = find_article(args.id)
    if not path:
        print(f"エラー: 記事ID {args.id} のファイルが見つかりません", file=sys.stderr)
        return 1

    text = open(path, encoding="utf-8").read()
    today = datetime.now(JST).date().isoformat()

    # べき等性ガード: 同じURLが記録済みなら、X告知を含む後続の副作用をすべて止める
    # (idempotency_key = 記事ID+公開URL。二重実行してもX二重投稿・二重課金にならない)
    already = f"published: {args.url}" in text
    if already:
        print("already=1")
    else:
        record = (
            f"<!-- published: {args.url} {today}(記録: publish-recordワークフロー)\n"
            "スイシン: 公開URL受領・記録済み。数字は公開前チェックリスト(規程3-1)を通過した前提\n"
            "ウタガイ: 出典抜き取り確認(2件)の実施は公開者の自己申告に依存。監査(タダス)の月次抜き取り照合の対象に含めること\n"
            "ベッカイ: 反応データ(ビュー・購入)が貯まったら、この記事の告知文パターン別の反応をKPI台帳で比較する -->\n\n"
        )
        open(path, "w", encoding="utf-8").write(record + text)

    # お題キューの更新(該当IDがあれば)
    try:
        topics = json.load(open(TOPICS_PATH, encoding="utf-8"))
        for t in topics.get("queue", []):
            if t.get("id") == args.id:
                t["status"] = "published"
                t["published_url"] = args.url
                t["published_at"] = today
        json.dump(topics, open(TOPICS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except FileNotFoundError:
        pass

    # 記録済み(already)のときは告知文を出力しない → ワークフロー側のX投稿が条件で止まる
    announce = ""
    if not already:
        hooks = extract_hooks(text)
        announce = hooks.get(args.hook) or hooks.get("a") or ""
        # 誇大表現の機械検査(規程3-3。告知文にも適用)
        for w in ("必ず", "絶対", "誰でも", "楽して", "確実に稼"):
            if w in announce:
                print(f"エラー: 告知文に禁止語({w})。手動で文面を直してください", file=sys.stderr)
                return 1

    title_m = re.search(r"^# (.+)$", text, flags=re.M)
    print(f"article={os.path.relpath(path, BASE)}")
    print(f"title={title_m.group(1) if title_m else ''}")
    print(f"announce={announce}")
    print(f"url={args.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
