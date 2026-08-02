#!/usr/bin/env python3
"""[1] 収集: config/sources.yml の情報源を巡回し、新規アイテムを data/raw/pending/ に保存する。

既に処理済みのアイテム(data/state/seen.json に記録)はスキップするので、
毎回の実行では「新しく増えた情報」だけが下流に流れる。
"""
import hashlib
import html
import json
import re
import sys
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = ROOT / "data" / "raw" / "pending"
STATE_FILE = ROOT / "data" / "state" / "seen.json"
USER_AGENT = "pipeline-starter-bot/1.0 (+see repository README)"


def load_seen() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return set()


def save_seen(seen: set) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=1), encoding="utf-8")


def item_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def fetch(url: str) -> str:
    resp = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        # robots.txt が取得できない場合は保守的にスキップ
        return False
    return rp.can_fetch(USER_AGENT, url)


def strip_tags(text: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _find_text(elem: ET.Element, *names: str) -> str:
    """名前空間の有無を問わずタグ名の末尾一致で最初のテキストを返す。"""
    for child in elem.iter():
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def parse_feed(xml_text: str) -> list:
    """RSS 1.0 / 2.0 / Atom のいずれもタグ末尾一致でパースする簡易パーサ。"""
    root = ET.fromstring(xml_text)
    entries = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1].lower()
        if tag not in ("item", "entry"):
            continue
        link = _find_text(elem, "link")
        if not link:
            # Atomは <link href="..."/> 形式
            for child in elem.iter():
                if child.tag.rsplit("}", 1)[-1].lower() == "link" and child.get("href"):
                    link = child.get("href")
                    break
        entries.append({
            "title": _find_text(elem, "title"),
            "link": link,
            "published": _find_text(elem, "pubdate", "date", "published", "updated"),
            "body": strip_tags(_find_text(elem, "description", "summary", "content")),
        })
    return [e for e in entries if e["link"]]


def collect_source(source: dict, seen: set, budget: int) -> int:
    new_count = 0
    if source["type"] == "rss":
        entries = parse_feed(fetch(source["url"]))
    elif source["type"] == "html":
        if not robots_allows(source["url"]):
            print(f"  ! robots.txt が許可していないためスキップ: {source['url']}")
            return 0
        entries = [{
            "title": source["name"],
            "link": source["url"],
            "published": "",
            "body": strip_tags(fetch(source["url"]))[:20000],
        }]
    else:
        print(f"  ! 未対応のtype: {source['type']}")
        return 0

    for entry in entries:
        if new_count >= budget:
            break
        iid = item_id(entry["link"])
        if iid in seen:
            continue
        record = {
            "id": iid,
            "source_id": source["id"],
            "source_name": source["name"],
            "url": entry["link"],
            "title": entry["title"],
            "published": entry["published"],
            "body": entry["body"][:20000],
        }
        (PENDING_DIR / f"{iid}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        seen.add(iid)
        new_count += 1
    return new_count


def main() -> int:
    config = yaml.safe_load((ROOT / "config" / "sources.yml").read_text(encoding="utf-8"))
    budget = int(config.get("max_items_per_run", 20))
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    seen = load_seen()

    total = 0
    for source in config.get("sources", []):
        if not source.get("enabled", True):
            continue
        print(f"収集中: {source['name']} ({source['url']})")
        try:
            n = collect_source(source, seen, budget - total)
            print(f"  新規 {n} 件")
            total += n
        except Exception as e:  # 1情報源の失敗で全体を止めない
            print(f"  ! エラー: {e}")

    save_seen(seen)
    print(f"合計 新規 {total} 件を data/raw/pending/ に保存しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
