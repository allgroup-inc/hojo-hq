#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glow-ma(営業管理システム)の実行記録(Cloud Logging)から、各処理が動いているかを集計する。

使い方(GitHub Actions から): CLASPRC_JSON と GCP_PROJECT を環境変数で渡す。
  python3 scripts/glow_ma_exec_health.py --hours 48

公開リポジトリの Actions ログに出るため、出力は「処理名・件数・最終時刻・エラーの先頭」だけにする。
ログ本文(会社名などを含みうる Logger.log の中身)は出さない。
"""
import argparse
import collections
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
# エラー文のうち、出してよい定型の先頭部分だけを残す(数字の羅列・メールアドレス等は伏せる)
SAFE_ERROR_LEN = 70


def access_token(clasprc):
    data = json.loads(clasprc)
    cands = []
    def walk(o):
        if isinstance(o, dict):
            if o.get("refresh_token") and o.get("client_id") and o.get("client_secret"):
                cands.append(o)
            for v in o.values():
                walk(v)
    walk(data)
    if not cands:
        sys.exit("CLASPRC_JSON にリフレッシュトークンが見つかりません")
    c = cands[0]
    body = urllib.parse.urlencode({
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": c["refresh_token"], "grant_type": "refresh_token",
    }).encode()
    res = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body, timeout=30))
    return res["access_token"]


def list_entries(token, project, since):
    flt = ('resource.type="app_script_function" AND timestamp>="%s"' % since)
    entries, page = [], None
    while True:
        req = {"resourceNames": ["projects/" + project], "filter": flt,
               "orderBy": "timestamp desc", "pageSize": 1000}
        if page:
            req["pageToken"] = page
        r = urllib.request.Request("https://logging.googleapis.com/v2/entries:list",
                                   data=json.dumps(req).encode(), method="POST",
                                   headers={"Authorization": "Bearer " + token,
                                            "Content-Type": "application/json"})
        res = json.load(urllib.request.urlopen(r, timeout=60))
        entries += res.get("entries", [])
        page = res.get("nextPageToken")
        if not page or len(entries) >= 20000:
            return entries


def safe_error(text):
    t = re.sub(r"AKfyc\S*", "(デプロイID)", str(text))
    t = re.sub(r"[A-Za-z0-9_\-]{25,}", "(ID)", t)
    t = re.sub(r"\S+@\S+", "(メール)", t)
    t = re.sub(r"\d{6,}", "(番号)", t)
    return t.replace("\n", " ")[:SAFE_ERROR_LEN]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48)
    args = ap.parse_args()
    project = os.environ["GCP_PROJECT"].strip()
    token = access_token(os.environ["CLASPRC_JSON"])
    since = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = list_entries(token, project, since)

    stats = collections.defaultdict(lambda: {"count": 0, "errors": 0, "last": "", "msgs": collections.Counter()})
    for e in entries:
        fn = e.get("resource", {}).get("labels", {}).get("function_name", "(不明)")
        s = stats[fn]
        s["count"] += 1
        ts = e.get("timestamp", "")
        if ts > s["last"]:
            s["last"] = ts
        if e.get("severity") in ("ERROR", "CRITICAL", "ALERT", "EMERGENCY"):
            s["errors"] += 1
            # メッセージ欄だけを見る(serviceContext 等にはデプロイIDが入っているため出さない)
            payload = e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or "(詳細なし)"
            s["msgs"][safe_error(payload)] += 1

    print(f"## 直近{args.hours}時間の実行記録(ログ {len(entries)} 件)")
    if not entries:
        print("::warning::実行記録が1件もありません(トリガーが止まっている可能性)")
    for fn, s in sorted(stats.items(), key=lambda kv: kv[1]["last"], reverse=True):
        last = datetime.strptime(s["last"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(JST)
        print(f"- {fn}: ログ{s['count']}件 / エラー{s['errors']}件 / 最終 {last:%m-%d %H:%M}(日本時間)")
        for msg, n in s["msgs"].most_common(3):
            print(f"    エラー例({n}件): {msg}")


if __name__ == "__main__":
    main()
