#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — X告知の自動投稿(公式API・OAuth1.0a)
本文に告知文を投稿し、リプ欄に記事URLをぶら下げる(リンクは本文に入れない=リーチ設計)。

規約準拠: X公式API経由の予約・自動投稿は許可されている(スクレイピング・ブラウザ操作は不使用)。
自動「返信ボット」ではない(自アカウントの告知投稿のみ)。

必要なシークレット(GitHub Secrets):
  X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET
  (developer.x.com でアプリ作成→Keys and tokens。従量課金プランで投稿$0.015/件)

使い方:
  python scripts/post_x_announce.py --text "告知文" --reply-url https://note.com/...
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--reply-url", required=True)
    args = ap.parse_args()

    # 出荷ゲート(運用規程1-3): X本文はファイルを持たないため、機械で検査できる層だけ適用する
    # (禁止表現・lin.ee直貼り)。引っかかったら投稿しない。
    import shipping_gate
    bad = shipping_gate.check_forbidden(args.text)
    if bad:
        print("[ng] 出荷ゲート未通過のためX投稿を中止します(運用規程1-3)")
        for b in bad:
            print(f"  - {b}")
        return 1

    keys = {k: os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")}
    if not all(keys.values()):
        missing = [k for k, v in keys.items() if not v]
        print(f"skipped=no_x_secrets({','.join(missing)})")
        return 0

    import tweepy

    client = tweepy.Client(
        consumer_key=keys["X_API_KEY"],
        consumer_secret=keys["X_API_SECRET"],
        access_token=keys["X_ACCESS_TOKEN"],
        access_token_secret=keys["X_ACCESS_SECRET"],
    )
    main_post = client.create_tweet(text=args.text)
    tweet_id = main_post.data["id"]
    client.create_tweet(text=args.reply_url, in_reply_to_tweet_id=tweet_id)
    print(f"posted=https://x.com/kekka_mag/status/{tweet_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
