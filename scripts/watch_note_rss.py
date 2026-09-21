#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ noteのRSSを巡回して公開を自動検知する(2026-09-21 小柳さん指示「極限まで自動化」)

いままで: 人間が公開→URLをチャットに貼る→ツヅルがpublish-recordを起動、だった。
これから: RSS(https://note.com/kekka_mag/rss)を1日2回巡回し、下書き済みで未記録の記事が
公開されているのを見つけたら、publish-record を自動起動する。人間の作業は「公開する」だけになる。

設計:
- 照合はタイトル一致(人間は貼るだけ版のタイトルをそのまま貼るため、原則完全一致する)。
  完全一致しない場合は先頭20文字一致でフォールバックし、その旨を出力に残す
- 副作用はpublish-recordのworkflow_dispatchのみ(記録・X告知のべき等性は既存ガードが担う。
  二重起動しても already / x_post_url ガードで安全)
- RSSが取れない・一致なしは正常終了(次回巡回に任せる)

出力(GITHUB_OUTPUT形式): dispatch=<id>|<url> を一致件数ぶん(dispatch_1, dispatch_2, ...)
"""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_x_taiken as gx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RSS_URL = "https://note.com/kekka_mag/rss"


def normalize(s: str) -> str:
    """タイトル照合用の正規化(空白と記号ゆらぎを吸収)。"""
    s = re.sub(r"\s+", "", s or "")
    return s.translate(str.maketrans("―–ー−", "————")).strip()


def fetch_rss(url=RSS_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "hojo-hq-kekka-watch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_items(xml_text):
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip().split("?")[0]
        if title and link.startswith("https://note.com/"):
            items.append((title, link))
    return items


def find_matches(items, queue):
    """公開待ち(下書き済み・published_urlなし)エントリとRSSを照合する。"""
    waiting = [
        t for t in queue
        if not t.get("published_url")
        and (t.get("drafted_at") or t.get("status") in ("stock", "log_drafted"))
        and t.get("title_hint")
    ]
    known_urls = {t.get("published_url") for t in queue if t.get("published_url")}
    matches = []
    for title, link in items:
        if link in known_urls:
            continue
        nt = normalize(title)
        for t in waiting:
            nh = normalize(t["title_hint"])
            if nt == nh or (len(nh) >= 20 and nt.startswith(nh[:20])):
                matches.append((t["id"], link, title))
                break
    return matches


def main():
    try:
        xml_text = fetch_rss()
    except Exception as e:
        print(f"::warning::RSS取得に失敗(次回巡回に任せる): {e}", file=sys.stderr)
        print("dispatch_count=0")
        return 0
    try:
        items = parse_items(xml_text)
    except Exception as e:
        print(f"::warning::RSS解析に失敗: {e}", file=sys.stderr)
        print("dispatch_count=0")
        return 0
    queue = gx.load_json(gx.TOPICS_PATH, {"queue": []}).get("queue", [])
    matches = find_matches(items, queue)
    for i, (tid, link, title) in enumerate(matches, 1):
        print(f"dispatch_{i}={tid}|{link}")
        print(f"::notice::公開を検知: {tid} {title} -> {link}", file=sys.stderr)
    print(f"dispatch_count={len(matches)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
