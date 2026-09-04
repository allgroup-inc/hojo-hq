#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GA4 Data API の共通クライアント(hojo-hq)。

議事: docs/議事_20260824_計測GA4切替.md(Plausible契約終了→GA4切替)の残タスク
「ファネルGA4版」の土台。fetch_ga4_traffic.py の get_token と同じ方式を共通化し、
週次レポ(weekly_report.py)・ファネル(fetch_hojo_funnel.py)・深掘り
(funnel_deep_dive.py)から使う。

プロパティは2つ(2026-08-24 有効化時の裁定):
- もらいわすれ堂プロパティ(G-TQMX3MPFSR): fukugiiroページ全体+ /go/ 12チャネル
  → Secrets GA4_PROPERTY_ID
- ミカタLPプロパティ(G-TW6M6WFB9T): 診断ファネルイベント
  (diagnosis_start / diagnosis_run / step2_done / line_cta_click{channel})
  → Secrets GA4_MIKATA_PROPERTY_ID
サービスアカウント鍵は1個(GA4_SA_JSON)を両プロパティに「閲覧者」で共有する。

- 集計値のみ。個人識別子は扱わない。鍵・トークンはログに出さない。
- 依存: google-auth + requests(Actionsのステップ内で pip install)
"""
import json
import os
import urllib.error
import urllib.request

API = "https://analyticsdata.googleapis.com/v1beta"


def env_ready():
    """GA4切替に必要なSecretsが揃っているか(ミカタ側)。"""
    return bool(os.environ.get("GA4_SA_JSON") and os.environ.get("GA4_MIKATA_PROPERTY_ID"))


def get_token(sa_json=None):
    from google.oauth2 import service_account  # noqa: PLC0415
    import google.auth.transport.requests  # noqa: PLC0415
    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json or os.environ["GA4_SA_JSON"]),
        scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def run_report(token, prop, body):
    req = urllib.request.Request(
        f"{API}/properties/{prop}:runReport",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def aggregate(token, prop, start, end):
    """訪問者・PV・直帰率(%)・平均セッション秒。取れない値はNone。"""
    data = run_report(token, prop, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "metrics": [{"name": "activeUsers"}, {"name": "screenPageViews"},
                    {"name": "bounceRate"}, {"name": "averageSessionDuration"}],
    })
    rows = data.get("rows") or []
    vals = rows[0]["metricValues"] if rows else []

    def g(i, cast=float):
        try:
            return cast(vals[i]["value"])
        except Exception:  # noqa: BLE001
            return None

    bounce = g(2)
    return {"visitors": g(0, int), "pageviews": g(1, int),
            "bounce_rate": round(bounce * 100) if bounce is not None else None,
            "visit_duration": round(g(3)) if g(3) is not None else None}


def event_counts(token, prop, start, end, names):
    """{イベント名: {"events": 回数, "users": 人数}}。names にあるものだけ返す。"""
    data = run_report(token, prop, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "eventName"}],
        "metrics": [{"name": "eventCount"}, {"name": "totalUsers"}],
        "dimensionFilter": {"filter": {"fieldName": "eventName", "inListFilter": {
            "values": list(names)}}},
        "limit": "100",
    })
    out = {}
    for row in data.get("rows") or []:
        name = row["dimensionValues"][0]["value"]
        out[name] = {"events": int(row["metricValues"][0]["value"]),
                     "users": int(row["metricValues"][1]["value"])}
    return out


def channel_breakdown(token, prop, start, end, event_name):
    """イベントの channel パラメータ内訳 [(channel, events, users), ...]。

    GA4はイベントパラメータをそのままでは集計できず、プロパティ側で
    カスタムディメンション(イベントスコープ・パラメータ名 channel)の登録が必要。
    未登録などで引けない場合は None を返す(呼び出し側で注記)。
    登録前に溜まったイベントの内訳は出ない(登録日以降のみ)。
    """
    try:
        data = run_report(token, prop, {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "customEvent:channel"}],
            "metrics": [{"name": "eventCount"}, {"name": "totalUsers"}],
            "dimensionFilter": {"filter": {"fieldName": "eventName", "stringFilter": {
                "matchType": "EXACT", "value": event_name}}},
            "limit": "50",
        })
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    rows = []
    for row in data.get("rows") or []:
        ch = row["dimensionValues"][0]["value"]
        if ch in ("", "(not set)"):
            ch = "?"
        rows.append((ch, int(row["metricValues"][0]["value"]),
                     int(row["metricValues"][1]["value"])))
    rows.sort(key=lambda r: -r[1])
    return rows
