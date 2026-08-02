#!/usr/bin/env python3
"""[1] 収集: config/sources.yml の情報源を巡回し、新規アイテムを data/raw/pending/ に保存する。

対応する情報源:
- jgrants: 国の補助金ポータル「jGrants」公開API(認証不要)。締切・上限額などの
  構造化データが取れるため、これらは prefill としてそのまま下流に渡し、
  AIには書き換えさせない(正確性最優先)
- rss / html: 汎用収集(htmlは robots.txt を確認し、許可されない場合はスキップ)

※ jGrants APIの仕様は変更されることがあります。エラーが続く場合は
  docs/FAQ.md の「jGrantsのエラー」を参照してください。
"""
import hashlib
import html
import json
import re
import sys
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = ROOT / "data" / "raw" / "pending"
STATE_FILE = ROOT / "data" / "state" / "seen.json"
USER_AGENT = "hojokin-site-starter-bot/1.0 (+see repository README)"

JGRANTS_API = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies"
JGRANTS_DETAIL_URL = "https://www.jgrants-portal.go.jp/subsidy/{id}"


def load_seen() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return set()


def save_seen(seen: set) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=1), encoding="utf-8")


def item_id(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def fetch(url: str, **kwargs) -> requests.Response:
    resp = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT}, **kwargs)
    resp.raise_for_status()
    return resp


def save_record(record: dict) -> None:
    (PENDING_DIR / f"{record['id']}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- jGrants ----------

def yen_label(value) -> str:
    """1500000 → '上限150万円' のような表記に。数値でなければ '要確認'。"""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "要確認"
    if n <= 0:
        return "要確認"
    if n >= 100_000_000:
        oku, man = divmod(n, 100_000_000)
        rest = f"{man // 10_000}万円" if man else "円"
        return f"上限{oku}億{rest}" if man else f"上限{oku}億円"
    if n >= 10_000:
        return f"上限{n // 10_000}万円" if n % 10_000 == 0 else f"上限{n:,}円"
    return f"上限{n:,}円"


def iso_to_date(value) -> str:
    """ISO日時文字列 → YYYY-MM-DD。解釈できなければ '要確認'。"""
    if not value:
        return "要確認"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return "要確認"


def collect_jgrants(source: dict, seen: set, budget: int) -> int:
    params = {
        "keyword": source.get("keyword", "中小企業"),
        "sort": "acceptance_end_datetime",
        "order": "ASC",
        "acceptance": "1",  # 受付中のみ
    }
    data = fetch(JGRANTS_API, params=params).json()
    entries = data.get("result", []) or []

    new_count = 0
    for e in entries:
        if new_count >= budget:
            break
        sid = str(e.get("id", ""))
        if not sid:
            continue
        iid = item_id(f"jgrants:{sid}")
        if iid in seen:
            continue
        url = JGRANTS_DETAIL_URL.format(id=sid)
        # 締切・上限額はAPIの構造化データを機械転記(prefill)。AIには触らせない
        prefill = {
            "title": e.get("title") or e.get("name") or "",
            "date": iso_to_date(e.get("acceptance_end_datetime")),
            "amount": yen_label(e.get("subsidy_max_limit")),
            "area": e.get("target_area_search") or "要確認",
            "agency": "jGrants掲載(詳細は原文参照)",
        }
        record = {
            "id": iid,
            "source_id": source["id"],
            "source_name": source["name"],
            "url": url,
            "title": prefill["title"],
            "published": str(e.get("acceptance_start_datetime") or ""),
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "prefill": {k: v for k, v in prefill.items() if v},
            # 原文情報としてAPIレスポンス全体を渡す(要約・対象者の平易化に使う)
            "body": json.dumps(e, ensure_ascii=False)[:20000],
        }
        save_record(record)
        seen.add(iid)
        new_count += 1
    return new_count


# ---------- RSS / HTML(汎用) ----------

def robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return False  # robots.txt が取得できない場合は保守的にスキップ
    return rp.can_fetch(USER_AGENT, url)


def strip_tags(text: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _find_text(elem: ET.Element, *names: str) -> str:
    for child in elem.iter():
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def parse_feed(xml_text: str) -> list:
    root = ET.fromstring(xml_text)
    entries = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1].lower()
        if tag not in ("item", "entry"):
            continue
        link = _find_text(elem, "link")
        if not link:
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


def collect_generic(source: dict, seen: set, budget: int) -> int:
    if source["type"] == "rss":
        text = fetch(source["url"]).text
        entries = parse_feed(text)
    else:  # html
        if not robots_allows(source["url"]):
            print(f"  ! robots.txt が許可していないためスキップ: {source['url']}")
            return 0
        resp = fetch(source["url"])
        resp.encoding = resp.apparent_encoding or resp.encoding
        entries = [{
            "title": source["name"],
            "link": source["url"],
            "published": "",
            "body": strip_tags(resp.text)[:20000],
        }]

    new_count = 0
    for entry in entries:
        if new_count >= budget:
            break
        iid = item_id(entry["link"])
        if iid in seen:
            continue
        save_record({
            "id": iid,
            "source_id": source["id"],
            "source_name": source["name"],
            "url": entry["link"],
            "title": entry["title"],
            "published": entry["published"],
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "prefill": {},
            "body": entry["body"][:20000],
        })
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
        print(f"収集中: {source['name']}")
        try:
            if source["type"] == "jgrants":
                n = collect_jgrants(source, seen, budget - total)
            elif source["type"] in ("rss", "html"):
                n = collect_generic(source, seen, budget - total)
            else:
                print(f"  ! 未対応のtype: {source['type']}")
                n = 0
            print(f"  新規 {n} 件")
            total += n
        except Exception as e:  # 1情報源の失敗で全体を止めない
            print(f"  ! エラー: {e}")

    save_seen(seen)
    print(f"合計 新規 {total} 件を data/raw/pending/ に保存しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
