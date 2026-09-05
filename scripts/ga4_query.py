#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GA4のオンデマンド照会(「今日何人?」に即答するための読み取り専用スクリプト)。

fetch_ga4_traffic.py が週次で7日分をファイルに記録するのに対し、こちらは
実行時点の「過去30分(リアルタイム)/今日/昨日/直近7日」をジョブログに出すだけで、
ファイルには何も書かない。個人識別子は扱わず、集計値のみ表示する。
(本リポジトリはPUBLICでActionsログも公開だが、出すのは site_traffic.json と
同粒度の集計値のみ)

使い方: GitHub Actions の ga4-query ワークフロー(workflow_dispatch)から実行。
依存: google-auth, requests(ワークフロー側でインストール)
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
MORADOU_PREFIX = os.environ.get("MORADOU_PATH_PREFIX", "/hojo-hq/fukugiiro")
API = "https://analyticsdata.googleapis.com/v1beta/properties/{prop}:{method}"


def get_token(sa_json: str) -> str:
    from google.oauth2 import service_account  # noqa: PLC0415
    import google.auth.transport.requests  # noqa: PLC0415
    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def call(token: str, prop: str, method: str, body: dict) -> dict:
    req = urllib.request.Request(
        API.format(prop=prop, method=method), data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def report(token: str, prop: str, start: str, end: str, moradou_only: bool):
    body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "metrics": [{"name": "activeUsers"}, {"name": "screenPageViews"}],
    }
    if moradou_only:
        body["dimensionFilter"] = {"filter": {
            "fieldName": "pagePath",
            "stringFilter": {"matchType": "BEGINS_WITH", "value": MORADOU_PREFIX}}}
    rows = call(token, prop, "runReport", body).get("rows") or []
    if not rows:
        return (0, 0)
    v = rows[0]["metricValues"]
    return (int(v[0]["value"]), int(v[1]["value"]))


def top_pages(token: str, prop: str, start: str, end: str, limit: int = 8):
    body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "activeUsers"}],
        "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}],
        "limit": limit,
    }
    rows = call(token, prop, "runReport", body).get("rows") or []
    return [(r["dimensionValues"][0]["value"], int(r["metricValues"][0]["value"])) for r in rows]


def main():
    prop = os.environ.get("GA4_PROPERTY_ID")
    sa_json = os.environ.get("GA4_SA_JSON")
    if not prop or not sa_json:
        print("[error] GA4_PROPERTY_ID / GA4_SA_JSON が未設定です")
        return 1
    token = get_token(sa_json)
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    # 過去30分(リアルタイム)。realtimeはpagePath絞り込み不可のためドメイン全体のみ
    try:
        rt = call(token, prop, "runRealtimeReport", {"metrics": [{"name": "activeUsers"}]})
        rt_users = int(rt["rows"][0]["metricValues"][0]["value"]) if rt.get("rows") else 0
    except Exception as e:  # noqa: BLE001
        rt_users = None
        print(f"[warn] リアルタイム取得に失敗: {type(e).__name__}")

    print(f"=== GA4照会 {now.strftime('%Y-%m-%d %H:%M')} JST ===")
    print(f"realtime_30min: users={rt_users}")
    for label, s, e in (("today", today, today), ("yesterday", yesterday, yesterday),
                        ("7d", week_ago, today)):
        dv, dp = report(token, prop, s, e, moradou_only=False)
        mv, mp = report(token, prop, s, e, moradou_only=True)
        print(f"{label}: domain users={dv} pv={dp} / moradou users={mv} pv={mp}")
    print("top_pages_today:")
    for path, users in top_pages(token, prop, today, today):
        print(f"  {users:4d}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
