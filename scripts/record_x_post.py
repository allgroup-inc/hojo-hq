#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — X告知投稿の結果をお題キューへ記録する(publish-recordワークフロー用)

X投稿は副作用(公開・課金)なので、成功したら投稿URLを data/tanpatsu_topics.json に
残して監査ログ化する(resilient-agent-design 原則③: 状態はGit管理のJSONへ)。
同じお題に x_post_url が既にあれば上書きしない(先勝ち)。

使い方:
  python scripts/record_x_post.py --id 19 --x-url https://x.com/kekka_mag/status/xxxx
出力: recorded=1 / recorded=0(該当お題なし・記録済み)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
TOPICS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "tanpatsu_topics.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="記事ID(例: 19)")
    ap.add_argument("--x-url", required=True, help="X投稿のURL")
    args = ap.parse_args()

    try:
        topics = json.load(open(TOPICS_PATH, encoding="utf-8"))
    except FileNotFoundError:
        print("recorded=0")
        return 0

    recorded = False
    for t in topics.get("queue", []):
        if t.get("id") == args.id and not t.get("x_post_url"):
            t["x_post_url"] = args.x_url
            t["x_posted_at"] = datetime.now(JST).date().isoformat()
            recorded = True
    if recorded:
        json.dump(topics, open(TOPICS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"recorded={1 if recorded else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
