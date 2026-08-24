#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ(@kekka_mag)のXポスト削除(公式API・自アカウントのみ)

用途: 誤投稿(例: 2026-08-22 プレースホルダー指示文のままの告知=ニドナシ台帳#16)の削除。
削除は不可逆のため、実行は小柳さん決裁済みのIDに限る(x-maintenanceワークフローの入力欄に明記)。

使い方:
  python scripts/delete_x_post.py --ids 2091050099258388910[,別ID...]
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
    ap.add_argument("--ids", required=True, help="削除するポストID(カンマ区切り)")
    args = ap.parse_args()

    keys = {k: os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")}
    if not all(keys.values()):
        missing = [k for k, v in keys.items() if not v]
        print(f"エラー: Xシークレット未設定({','.join(missing)})", file=sys.stderr)
        return 1

    import tweepy

    client = tweepy.Client(
        consumer_key=keys["X_API_KEY"],
        consumer_secret=keys["X_API_SECRET"],
        access_token=keys["X_ACCESS_TOKEN"],
        access_token_secret=keys["X_ACCESS_SECRET"],
    )
    failed = 0
    for tid in [i.strip() for i in args.ids.split(",") if i.strip()]:
        try:
            res = client.delete_tweet(tid)
            ok = bool(res.data and res.data.get("deleted"))
            print(f"{'deleted' if ok else 'not_deleted'}={tid}")
            if not ok:
                failed += 1
        except Exception as e:  # 既に削除済み等も含めて結果を正直に出す
            print(f"error={tid} {e}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
