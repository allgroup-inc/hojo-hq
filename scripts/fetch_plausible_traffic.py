#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""サイトのアクセス総量(訪問者数・PV)を Plausible から取得して記録する。

背景: fetch_plausible_funnel.py は診断ファネル(イベント)しか取らず、
「サイトを何人が見たか」が残らなかった。KGI ❶(もらいわすれ堂 月1万人)の
進捗を測るには訪問者数・PVの実測が要る。本スクリプトが週次で追記する。

- PLAUSIBLE_API_KEY 未設定なら何も書かず exit 0(静かに欠損させず last_status に明記)。
- 集計値のみ(訪問者数・PV・直帰率・滞在秒)。個人識別子は扱わない。APIキーはログに出さない。
- ドメイン全体(= 企業のミカタ + もらいわすれ堂)と、もらいわすれ堂ページに絞った値の両方を記録。

使い方:
  PLAUSIBLE_API_KEY=xxx python scripts/fetch_plausible_traffic.py
環境変数(任意):
  PLAUSIBLE_SITE_ID   既定 allgroup-inc.github.io
  PLAUSIBLE_PERIOD    既定 7d(7日間)
  PLAUSIBLE_API_BASE  既定 https://plausible.io
  MORADOU_PATH_GLOB   もらいわすれ堂の絞り込み。既定 /hojo-hq/fukugiiro*
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "kpi", "site_traffic.json")
METRICS = "visitors,pageviews,bounce_rate,visit_duration"


def load():
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    return {
        "note": "サイトのアクセス総量(Plausible集計・Cookieなし)。KGI❶=もらいわすれ堂 月1万人。"
                "domain=ドメイン全体(企業のミカタ+もらいわすれ堂)、moradou=もらいわすれ堂ページのみ。",
        "kgi_target_monthly_users": 10000,
        "last_checked": None,
        "last_status": "not_connected",
        "history": [],
    }


def fetch_aggregate(api_key, site_id, period, api_base, page_glob=None):
    params = {"site_id": site_id, "period": period, "metrics": METRICS}
    if page_glob:
        params["filters"] = "event:page==" + page_glob
    url = api_base.rstrip("/") + "/api/v1/stats/aggregate?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + api_key})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    res = data.get("results", {})

    def g(k):
        v = res.get(k)
        return (v or {}).get("value") if isinstance(v, dict) else v

    return {
        "visitors": g("visitors"),
        "pageviews": g("pageviews"),
        "bounce_rate": g("bounce_rate"),
        "visit_duration": g("visit_duration"),
    }


def main():
    state = load()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    api_key = os.environ.get("PLAUSIBLE_API_KEY")
    if not api_key:
        state["last_checked"] = now
        state["last_status"] = "not_connected"
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print("[info] PLAUSIBLE_API_KEY 未設定: アクセス総量の取得をスキップ(last_status=not_connected)")
        return 0

    site_id = os.environ.get("PLAUSIBLE_SITE_ID", "allgroup-inc.github.io")
    period = os.environ.get("PLAUSIBLE_PERIOD", "7d")
    api_base = os.environ.get("PLAUSIBLE_API_BASE", "https://plausible.io")
    glob = os.environ.get("MORADOU_PATH_GLOB", "/hojo-hq/fukugiiro*")

    entry = {"date": datetime.now(JST).strftime("%Y-%m-%d"), "period": period}
    try:
        entry["domain"] = fetch_aggregate(api_key, site_id, period, api_base)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] ドメイン全体の取得に失敗: {type(e).__name__}")
        entry["domain"] = None
    try:
        entry["moradou"] = fetch_aggregate(api_key, site_id, period, api_base, page_glob=glob)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] もらいわすれ堂の絞り込み取得に失敗: {type(e).__name__}")
        entry["moradou"] = None

    # 同日エントリは上書き(重複追記を避ける)
    state["history"] = [h for h in state.get("history", []) if h.get("date") != entry["date"]]
    state["history"].append(entry)
    state["history"] = state["history"][-104:]  # 約2年分
    state["last_checked"] = now
    state["last_status"] = "ok" if entry.get("domain") else "partial"

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    dv = (entry.get("domain") or {}).get("visitors")
    mv = (entry.get("moradou") or {}).get("visitors")
    print(f"recorded {entry['date']} ({period}): domain visitors={dv}, moradou visitors={mv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
