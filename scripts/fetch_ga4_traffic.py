#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""サイトのアクセス総量(訪問者数・PV)を GA4 Data API から取得して記録する。

背景: 2026-08-24 に Plausible が 402(サブスク未契約ロック)となり計測が停止。
小柳さん決裁(②GA4へ切替・議事: docs/議事_20260824_計測GA4切替.md)を受けた
GA4版の取得スクリプト。data/kpi/site_traffic.json に fetch_plausible_traffic.py と
同じ形式で追記する(entry に "source": "ga4" を付ける)。

- GA4_PROPERTY_ID / GA4_SA_JSON(サービスアカウント鍵JSON)未設定なら
  **ファイルに触らず** exit 0(移行期間中にPlausible側の記録を壊さないため)。
- 集計値のみ(訪問者数・PV・直帰率・平均セッション秒)。個人識別子は扱わない。
  鍵・トークンはログに出さない。
- ドメイン全体(= 企業のミカタ + もらいわすれ堂)と、もらいわすれ堂ページ
  (pagePath が /hojo-hq/fukugiiro で始まる)に絞った値の両方を記録。

必要な準備(小柳さん側・1回だけ):
  1. analytics.google.com でプロパティ作成 → 測定ID(G-…)をAIへ共有
  2. GCPでサービスアカウント作成 → 鍵JSONを Secrets GA4_SA_JSON に登録
  3. GA4のプロパティ設定 → アクセス管理 にサービスアカウントのメールを「閲覧者」で追加
  4. プロパティID(数字)を Secrets GA4_PROPERTY_ID に登録

使い方:
  GA4_PROPERTY_ID=123456789 GA4_SA_JSON='{"type":"service_account",...}' \
    python scripts/fetch_ga4_traffic.py
依存: pip install google-auth(Actionsのステップ内でインストール)
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "kpi", "site_traffic.json")
LAUNCH_DATE = "2026-07-23"  # サイト公開日(all_time集計の起点)
MORADOU_PREFIX = os.environ.get("MORADOU_PATH_PREFIX", "/hojo-hq/fukugiiro")


def get_token(sa_json: str) -> str:
    from google.oauth2 import service_account  # noqa: PLC0415
    import google.auth.transport.requests  # noqa: PLC0415
    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def run_report(token: str, prop: str, start: str, end: str, moradou_only: bool):
    body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "metrics": [{"name": "activeUsers"}, {"name": "screenPageViews"},
                    {"name": "bounceRate"}, {"name": "averageSessionDuration"}],
    }
    if moradou_only:
        body["dimensionFilter"] = {"filter": {
            "fieldName": "pagePath",
            "stringFilter": {"matchType": "BEGINS_WITH", "value": MORADOU_PREFIX}}}
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    rows = data.get("rows") or []
    vals = rows[0]["metricValues"] if rows else []

    def g(i, cast=float):
        try:
            return cast(vals[i]["value"])
        except Exception:  # noqa: BLE001
            return None

    bounce = g(2)
    return {
        "visitors": g(0, int),
        "pageviews": g(1, int),
        # GA4のbounceRateは0〜1の比。既存記録(%)に合わせて換算
        "bounce_rate": round(bounce * 100) if bounce is not None else None,
        "visit_duration": round(g(3) or 0) if g(3) is not None else None,
    }


def main():
    prop = os.environ.get("GA4_PROPERTY_ID")
    sa_json = os.environ.get("GA4_SA_JSON")
    if not prop or not sa_json:
        print("[info] GA4_PROPERTY_ID / GA4_SA_JSON 未設定: GA4取得をスキップ(ファイルは変更しない)")
        return 0

    token = get_token(sa_json)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    week_ago = (datetime.now(JST) - timedelta(days=7)).strftime("%Y-%m-%d")

    with open(OUT, encoding="utf-8") as f:
        state = json.load(f)

    entry = {"date": today, "period": "7d", "source": "ga4"}
    try:
        entry["domain"] = run_report(token, prop, week_ago, today, moradou_only=False)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] ドメイン全体の取得に失敗: {type(e).__name__}")
        entry["domain"] = None
    try:
        entry["moradou"] = run_report(token, prop, week_ago, today, moradou_only=True)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] もらいわすれ堂の絞り込み取得に失敗: {type(e).__name__}")
        entry["moradou"] = None

    # 全期間累計。GA4はプロパティ作成日以降しか集計できないため、
    # Plausible時代(7/23〜8/21)の累計90/53人は上書きせず、GA4分は別キーで持つ。
    try:
        at_domain = run_report(token, prop, LAUNCH_DATE, today, moradou_only=False)
        at_moradou = run_report(token, prop, LAUNCH_DATE, today, moradou_only=True)
        state["all_time_ga4"] = {"since_measured": "GA4計測開始日以降のみ", "as_of": today,
                                 "domain_visitors": at_domain.get("visitors"),
                                 "moradou_visitors": at_moradou.get("visitors"),
                                 "moradou_pageviews": at_moradou.get("pageviews")}
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 全期間累計の取得に失敗(継続): {type(e).__name__}")

    state["history"] = [h for h in state.get("history", []) if h.get("date") != entry["date"]]
    state["history"].append(entry)
    state["history"] = state["history"][-104:]
    state["last_checked"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    state["last_status"] = "ok(ga4)" if entry.get("domain") else "partial(ga4)"

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    dv = (entry.get("domain") or {}).get("visitors")
    mv = (entry.get("moradou") or {}).get("visitors")
    print(f"recorded(ga4) {today} (7d): domain visitors={dv}, moradou visitors={mv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
