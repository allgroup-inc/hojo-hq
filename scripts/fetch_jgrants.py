#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq 収集部(シュウくん)
jGrants APIから沖縄県で使える補助金・助成金を取得し data/subsidies.json を更新する。
GitHub Actions cron で1日4回実行(6時間おき)。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
API_BASE = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies"
DETAIL_BASE = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies/id"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subsidies.json")

# 沖縄で使える制度 = 「沖縄」指定 + 全国対象(沖縄企業も申請可)
KEYWORDS = ["沖縄"]
NATIONWIDE_KEYWORDS = ["事業承継", "M&A", "引継ぎ", "ものづくり", "IT導入", "小規模事業者"]

def fetch_json(url: str, retries: int = 3) -> dict:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hojo-hq/1.0"})
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except Exception as e:
            print(f"[warn] fetch failed ({i+1}/{retries}): {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    return {}

def search(keyword: str, acceptance: str = "1") -> list:
    """acceptance=1: 募集中のみ"""
    params = {
        "keyword": keyword,
        "sort": "acceptance_end_datetime",
        "order": "ASC",
        "acceptance": acceptance,
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    data = fetch_json(url)
    return data.get("result", [])

def normalize(item: dict, tag: str) -> dict:
    def dt(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST).strftime("%Y-%m-%d")
        except Exception:
            return None

    deadline = dt(item.get("acceptance_end_datetime"))
    max_amount = item.get("subsidy_max_limit")
    return {
        "id": item.get("id"),
        "name": item.get("title") or item.get("name"),
        "issuer": item.get("subsidy_catch_phrase") or "",
        "target_area": item.get("target_area_search") or "",
        "target_biz": item.get("industry") or "",
        "employees": item.get("target_number_of_employees") or "",
        "max_amount": max_amount,
        "deadline": deadline or "要確認",
        "source_url": f"https://www.jgrants-portal.go.jp/subsidy/{item.get('id')}",
        "tag": tag,  # okinawa / nationwide / shokei(承継・M&A)
        "fetched_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "status": "募集中",
    }

def main() -> None:
    results: dict[str, dict] = {}

    # 1) 沖縄指定の制度
    for kw in KEYWORDS:
        for item in search(kw):
            n = normalize(item, "okinawa")
            if n["id"]:
                results[n["id"]] = n
        time.sleep(1)

    # 2) 全国対象(沖縄企業も使える)+ 承継・M&A系は専用タグ
    for kw in NATIONWIDE_KEYWORDS:
        tag = "shokei" if kw in ("事業承継", "M&A", "引継ぎ") else "nationwide"
        for item in search(kw):
            area = (item.get("target_area_search") or "")
            if "沖縄" in area or "全国" in area or area == "":
                n = normalize(item, tag)
                if n["id"] and n["id"] not in results:
                    results[n["id"]] = n
                elif n["id"] in results and tag == "shokei":
                    results[n["id"]]["tag"] = "shokei"
        time.sleep(1)

    items = sorted(results.values(), key=lambda x: x["deadline"] or "9999")
    payload = {
        "updated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "count": len(items),
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[ok] {len(items)} 件を書き出しました → data/subsidies.json")

if __name__ == "__main__":
    main()
