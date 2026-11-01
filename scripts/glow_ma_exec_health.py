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
SAFE_ERROR_LEN = 120


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


def report_web_deployments(token, script_id):
    """Web公開(デプロイ)の設定を読み取って出す(読み取りのみ。URL・デプロイID・スクリプトIDは出さない)。
    2026-10-31: 管理画面は「アクセスしている人のメール」でスタッフか判定するため、実行ユーザーが「自分」だと
    個人Gmail運用では持ち主以外のメールが空になり入れない(CLAUDE.md GAS Web App規律)。実際の設定を確かめる。"""
    def get(path):
        r = urllib.request.Request("https://script.googleapis.com/v1/projects/%s/%s" % (script_id, path),
                                   headers={"Authorization": "Bearer " + token})
        return json.load(urllib.request.urlopen(r, timeout=30))
    print("## Web公開(デプロイ)の設定")
    try:
        deps = get("deployments?pageSize=50").get("deployments", [])
        versions = get("versions?pageSize=50").get("versions", [])
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", "")
        print(f"::warning::デプロイの設定を読めませんでした({type(e).__name__} {code})")
        return
    latest = max((v.get("versionNumber", 0) for v in versions), default=0)
    print(f"- 保存済みの版: 最新 {latest}")
    for i, d in enumerate(deps, 1):
        cfg = d.get("deploymentConfig", {}) or {}
        ver = cfg.get("versionNumber", "HEAD(最新のコード)")
        desc = safe_error(cfg.get("description", ""), 40) or "(説明なし)"
        for ep in d.get("entryPoints", []) or []:
            if ep.get("entryPointType") != "WEB_APP":
                continue
            wc = (ep.get("webApp", {}) or {}).get("entryPointConfig", {}) or {}
            print(f"- デプロイ{i}: 説明={desc} / 版={ver} / 実行ユーザー={wc.get('executeAs', '?')} / "
                  f"アクセス={wc.get('access', '?')} / 更新 {str(d.get('updateTime', ''))[:10]}")


def safe_error(text, limit=None):
    t = re.sub(r"AKfyc\S*", "(デプロイID)", str(text))
    t = re.sub(r"[A-Za-z0-9_\-]{25,}", "(ID)", t)
    t = re.sub(r"\S+@\S+", "(メール)", t)
    t = re.sub(r"\d{6,}", "(番号)", t)
    return re.sub(r"\s+", " ", t)[:limit or SAFE_ERROR_LEN]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--grep", default="", help="この語を含むログ(INFO含む)の先頭だけを最大5件表示する")
    ap.add_argument("--alert", action="store_true",
                    help="毎日の自動点検用。承認切れ・稼働の記録なしを見つけたら終了コード1で失敗する(GitHubから通知が届く)")
    ap.add_argument("--sample", default="", help="この処理名の最新ログ3件の中身の形(重要度・項目名・本文の先頭)を表示する")
    args = ap.parse_args()
    token = access_token(os.environ["CLASPRC_JSON"])
    script_id = re.sub(r"\s", "", os.environ.get("SCRIPT_ID", ""))
    if script_id:
        report_web_deployments(token, script_id)
    project = os.environ.get("GCP_PROJECT", "").strip()
    if not project:
        sys.exit("::error::Google Cloud のプロジェクト番号がありません(手動実行で gcp_project を1回指定すると、以後は覚えて使います)")
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
        body_text = e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or ""
        # 承認切れはNOTICEで記録されるが、処理が1行も動いていない(2026-10-24〜26に見逃した)のでエラーとして数える
        auth_missing = "Authorization is required" in body_text or "承認が必要" in body_text
        if auth_missing:
            s["auth"] = s.get("auth", 0) + 1
        if e.get("severity") in ("ERROR", "CRITICAL", "ALERT", "EMERGENCY") or auth_missing:
            s["errors"] += 1
            # メッセージ欄だけを見る(serviceContext 等にはデプロイIDが入っているため出さない)
            payload = e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or "(詳細なし)"
            s["msgs"][safe_error(payload)] += 1

    if args.grep:
        shown = 0
        for e in entries:
            text = e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or ""
            if args.grep in text and shown < 5:
                fn = e.get("resource", {}).get("labels", {}).get("function_name", "(不明)")
                ts = e.get("timestamp", "")[:19]
                when = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(JST) if ts else None
                print(f"[{args.grep}] {when:%m-%d %H:%M} {fn} {e.get('severity', '')}: {safe_error(text, 400)}" if when
                      else f"[{args.grep}] {fn}: {safe_error(text)}")
                shown += 1
        hits = [e for e in entries if args.grep in (e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or "")]
        print(f"[{args.grep}] 該当 {len(hits)} 件")
        by_fn = collections.defaultdict(list)
        for e in hits:
            by_fn[e.get("resource", {}).get("labels", {}).get("function_name", "(不明)")].append(e.get("timestamp", "")[:19])
        for fn, ts in sorted(by_fn.items()):
            first = datetime.strptime(min(ts), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(JST)
            last = datetime.strptime(max(ts), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(JST)
            print(f"[{args.grep}] {fn}: {len(ts)} 件 / 最初 {first:%m-%d %H:%M} / 最後 {last:%m-%d %H:%M}(日本時間)")
        # 実行した利用者が、毎分の音声ログ処理(台帳の持ち主のトリガー)と同じかどうかだけを出す(値そのものは出さない)
        def user_key(e):
            labels = e.get("labels", {}) or {}
            return next((v for k, v in labels.items() if k.endswith("user_key")), "")
        owner = collections.Counter(user_key(e) for e in entries
                                    if e.get("resource", {}).get("labels", {}).get("function_name") == "processQueuedVoiceLogs")
        owner_key = owner.most_common(1)[0][0] if owner else ""
        same = sum(1 for e in hits if owner_key and user_key(e) == owner_key)
        print(f"[{args.grep}] 実行した利用者: 台帳の持ち主と同じ {same} 件 / 別の利用者 {len(hits) - same} 件"
              + ("" if owner_key else "(利用者の情報なし)"))
        kinds = collections.Counter(k for e in hits for k in (e.get("labels", {}) or {}).keys())
        print(f"[{args.grep}] ログの項目名: {', '.join(sorted(kinds))}")
    if args.sample:
        picked = sorted((e for e in entries if e.get("resource", {}).get("labels", {}).get("function_name") == args.sample),
                        key=lambda e: e.get("timestamp", ""), reverse=True)[:3]
        for e in picked:
            body = e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or ""
            keys = sorted((e.get("jsonPayload") or {}).keys())
            print(f"[見本 {args.sample}] {e.get('timestamp', '')[:19]} {e.get('severity', '')} "
                  f"logName末尾={e.get('logName', '').rsplit('/', 1)[-1]} 項目={keys} 本文={safe_error(body)}")
    print(f"## 直近{args.hours}時間の実行記録(ログ {len(entries)} 件)")
    if not entries:
        print("::warning::実行記録が1件もありません(トリガーが止まっている可能性)")
    for fn, s in sorted(stats.items(), key=lambda kv: kv[1]["last"], reverse=True):
        last = datetime.strptime(s["last"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(JST)
        print(f"- {fn}: ログ{s['count']}件 / エラー{s['errors']}件 / 最終 {last:%m-%d %H:%M}(日本時間)")
        if s.get("auth"):
            print(f"::error title={fn} が承認切れで止まっています::{s['auth']}回。台帳の持ち主がApps Scriptエディタで関数を1回実行し、権限を許可し直してください")
        for msg, n in s["msgs"].most_common(3):
            print(f"    エラー例({n}件): {msg}")
    if args.alert:
        problems = []
        auth = sum(st.get("auth", 0) for st in stats.values())
        if auth:
            problems.append(f"承認切れで止まった実行が {auth} 回あります(台帳のメニュー「GLOW台帳 → 自動処理を復旧する」を押してください)")
        beat = any("録音ファイルの受付フォルダ: 稼働中" in (e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or "")
                   for e in entries)
        if not beat:
            problems.append(f"直近{args.hours}時間に、毎分の処理が動いた記録(6時間ごとの稼働記録)がありません")
        for p in problems:
            print(f"::error title=glow-ma の自動処理に問題があります::{p}")
        if problems:
            sys.exit(1)
        print("自動点検: 問題なし(承認切れなし・稼働記録あり)")


if __name__ == "__main__":
    main()
