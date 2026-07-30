#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — SNS自動投稿(Facebookページ+Instagram)
議事_20260730(議題2「構築を進める」)の実装。

- 投稿素材は generate_sns.py / generate_images.py が生成済みの
  posts/launch/<nn>_<slug>.md(キャプション) + posts/images/<nn>_<slug>.png(画像)
  をそのまま使う(締切3層ルール・原文照合はスクリプト側で担保済み)
- 選定: 日付ローテーション(同じ日は同じ投稿=再実行しても二重投稿しにくい)
- Secrets未設定時は「未接続」と明記してスキップ(静かに欠損させない)

必要なSecrets(Meta Business Suite連携後に登録):
  FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN / IG_USER_ID
使い方:
  python scripts/post_social.py            # 本番投稿(Secrets必須)
  python scripts/post_social.py --dry-run  # 選定とキャプションの確認のみ
"""
import glob
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(__file__), "..")
RAW_BASE = "https://raw.githubusercontent.com/allgroup-inc/hojo-hq/main/posts/images/"
GRAPH = "https://graph.facebook.com/v21.0"
JST = timezone(timedelta(hours=9))


def pick_post():
    """日付でローテーション選定。md と png が揃っている素材のみ対象。"""
    mds = sorted(glob.glob(os.path.join(BASE, "posts", "launch", "*.md")))
    pairs = []
    for md in mds:
        stem = os.path.splitext(os.path.basename(md))[0]
        png = os.path.join(BASE, "posts", "images", stem + ".png")
        if os.path.exists(png):
            pairs.append((md, stem))
    if not pairs:
        raise SystemExit("[ng] 投稿素材が見つかりません(posts/launch + posts/images)")
    idx = date.today().toordinal() % len(pairs)
    return pairs[idx]


def extract_caption(md_path):
    text = open(md_path, encoding="utf-8").read()
    m = re.search(r"## キャプション\n(.*?)(?:\n## |\Z)", text, re.S)
    if not m:
        raise SystemExit(f"[ng] キャプション欄が見つかりません: {md_path}")
    return m.group(1).strip()


def api(path, params):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(GRAPH + path, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    dry = "--dry-run" in sys.argv
    md, stem = pick_post()
    caption = extract_caption(md)
    image_url = RAW_BASE + stem + ".png"
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    print(f"[info] {now} JST / 本日の投稿素材: {stem}")
    print(f"[info] 画像: {image_url}")
    print("[info] キャプション先頭: " + caption.splitlines()[0])

    if dry:
        print("[ok] dry-run: 選定とキャプション抽出のみ実施(投稿なし)")
        return

    page_id = os.environ.get("FB_PAGE_ID", "")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    ig_user = os.environ.get("IG_USER_ID", "")

    posted = []
    if page_id and token:
        res = api(f"/{page_id}/photos",
                  {"url": image_url, "caption": caption, "access_token": token})
        print(f"[ok] Facebook投稿 完了: id={res.get('id') or res.get('post_id')}")
        posted.append("facebook")
    else:
        print("[skip] Facebook: 未接続(FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN 未設定)")

    if ig_user and token:
        c = api(f"/{ig_user}/media",
                {"image_url": image_url, "caption": caption, "access_token": token})
        creation_id = c["id"]
        last_err = None
        for _ in range(3):  # コンテナ処理待ちを考慮して公開を最大3回試行
            try:
                pub = api(f"/{ig_user}/media_publish",
                          {"creation_id": creation_id, "access_token": token})
                print(f"[ok] Instagram投稿 完了: id={pub.get('id')}")
                posted.append("instagram")
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(10)
        if last_err:
            raise SystemExit(f"[ng] Instagram公開に失敗: {last_err}")
    else:
        print("[skip] Instagram: 未接続(IG_USER_ID 未設定)")

    if not posted:
        print("[warn] どのSNSにも未接続のため投稿は行われていません(Meta連携後にSecretsを登録してください)")


if __name__ == "__main__":
    main()
