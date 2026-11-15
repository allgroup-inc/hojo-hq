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


def entry_text(e):
    return e.get("textPayload") or (e.get("jsonPayload") or {}).get("message") or ""


def alert_problems(entries, now, hours, recent_minutes):
    """自動点検で知らせる問題の一覧(空なら問題なし)。

    承認切れは「直近 recent_minutes 分」だけを数える(2026-11-05)。点検を3時間ごとにしたため、
    復旧した後も、点検の期間(hours)に残った古いエラーで通知が続かないようにする。
    稼働記録(6時間に1回)は hours 全体で探す。
    """
    recent_since = (now - timedelta(minutes=recent_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    auth = sum(1 for e in entries
               if e.get("timestamp", "") >= recent_since
               and ("Authorization is required" in entry_text(e) or "承認が必要" in entry_text(e)))
    problems = []
    if auth:
        problems.append(f"直近{recent_minutes}分に、承認切れで止まった実行が {auth} 回あります"
                        "(台帳のメニュー「GLOW台帳 → 自動処理を復旧する」を押してください)")
    if not any("録音ファイルの受付フォルダ: 稼働中" in entry_text(e) for e in entries):
        problems.append(f"直近{hours}時間に、毎分の処理が動いた記録(6時間ごとの稼働記録)がありません")
    return problems


# 日次メンテナンス(glow-ma/src/MaintenanceRunner.gs)の手順名。知らせに出すのはこの決まった名前だけ
# (ログの本文には企業IDや行番号が入りうるため、公開の Actions ログと LINE には出さない)
MAINTENANCE_STEPS = (
    "台帳のバックアップ", "お断り(連絡不要)の反映", "スコア・ランクの再計算", "ダッシュボードの更新",
    "今日の連絡先の更新", "世界の架け橋の週次KPI", "掘り起こしアラートの送信",
)
# 日次メンテナンスの失敗を数える期間(分)。点検は3時間ごとの予定だが、GitHub の定期実行は実際には
# 4〜11時間あくことがある(2026-11-05〜15 の実績)。あいだが最長でも拾える長さ(14時間)にする
ALERT_MAINTENANCE_MINUTES = 840
MAINTENANCE_FAILED = re.compile(r"日次メンテナンス: 「([^」]+)」が失敗しました")
MAINTENANCE_ALL_OK = "日次メンテナンスがすべて完了しました"
COMPANY_WRITE_STOPPED = "企業マスタの書き込みを止めました"


def company_write_phase(text):
    """企業マスタの書き込みを止めた記録が、どの段階で止めたものか(決まった文だけを返す)。"""
    if COMPANY_WRITE_STOPPED not in text:
        return ""
    if "企業マスタは変更していません" in text:
        return "企業マスタの書き込みを、書く前の確認で止めました(企業マスタは変更されていません)"
    if "書き込みの途中で止まりました" in text:
        return "企業マスタの書き込みが途中で止まりました(途中まで書き換わっている可能性があります)"
    return "企業マスタを書いた後の照合で止めました(書いた内容の確認が要ります)"


def maintenance_problems(entries, now, recent_minutes):
    """直近 recent_minutes 分の日次メンテナンスの失敗(空なら問題なし)。2026-11-15 追加。

    11/11 の企業マスタの欠落(失敗台帳 FK-010)は、失敗の通知がメール1通だけで、定期点検まで気づけなかった。
    3時間ごとの自動点検で日次メンテナンスの失敗を見つけ、LINE でも知らせる。
    失敗のあとに「すべて完了」の記録があれば(やり直して直った)、知らせない。
    """
    since = (now - timedelta(minutes=recent_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [e for e in entries if e.get("timestamp", "") >= since]
    last_ok = max((e.get("timestamp", "") for e in recent if MAINTENANCE_ALL_OK in entry_text(e)), default="")
    steps, phases = [], []
    for e in sorted(recent, key=lambda e: e.get("timestamp", "")):
        text = entry_text(e)
        m = MAINTENANCE_FAILED.search(text)
        if not m or e.get("timestamp", "") <= last_ok:
            continue
        name = m.group(1) if m.group(1) in MAINTENANCE_STEPS else "その他の手順"
        if name not in steps:
            steps.append(name)
        phase = company_write_phase(text)
        if phase and phase not in phases:
            phases.append(phase)
    if not steps:
        return []
    hours = max(recent_minutes // 60, 1)
    # 同じ失敗は、期間のあいだ点検のたびに知らせる(直るか、次の日次メンテナンスが成功するまでの念押し)
    return [f"直近{hours}時間の日次メンテナンスで {len(steps)} 件の手順が失敗しました(" + "・".join(steps) + ")。"
            + "".join(p + "。" for p in phases)
            + "台帳の「稼働状況」タブを確かめ、システム担当のチャットへ知らせてください"]


def all_alert_problems(entries, now, hours, recent_minutes, maintenance_minutes):
    """自動点検(--alert)で知らせる問題のすべて: 承認切れ・稼働記録なし・日次メンテナンスの失敗。

    entries は日次メンテナンスの期間(maintenance_minutes)まで含めて渡してよい。
    稼働記録の有無は、これまでどおり直近 hours 時間の記録だけで判定する(期間を広げても判定を甘くしない)。
    """
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    within_hours = [e for e in entries if e.get("timestamp", "") >= since]
    return alert_problems(within_hours, now, hours, recent_minutes) + maintenance_problems(entries, now, maintenance_minutes)


def fetch_hours(hours, alert, maintenance_minutes):
    """実行記録を何時間ぶん取るか。自動点検のときは、日次メンテナンスの期間まで広げる。"""
    return max(hours, -(-maintenance_minutes // 60)) if alert else hours


def write_alert_output(problems, path):
    """見つけた問題を、後のステップ(LINE通知)へ渡す。出すのは決まった文だけ(ログの本文は入れない)。"""
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write("problems<<GLOW_MA_ALERT_END\n" + "\n".join("・" + p for p in problems) + "\nGLOW_MA_ALERT_END\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--grep", default="", help="この語を含むログ(INFO含む)の先頭だけを最大5件表示する")
    ap.add_argument("--alert", action="store_true",
                    help="定期の自動点検用。承認切れ・稼働の記録なし・日次メンテナンスの失敗を見つけたら終了コード1で失敗する(LINEで通知が届く)")
    ap.add_argument("--alert-recent-minutes", type=int, default=60,
                    help="--alert で承認切れを数える期間(分)。復旧後に古いエラーで通知が続かないよう短くする")
    ap.add_argument("--alert-maintenance-minutes", type=int, default=ALERT_MAINTENANCE_MINUTES,
                    help="--alert で日次メンテナンスの失敗を数える期間(分)")
    ap.add_argument("--sample", default="", help="この処理名の最新ログ3件の中身の形(重要度・項目名・本文の先頭)を表示する")
    args = ap.parse_args()
    token = access_token(os.environ["CLASPRC_JSON"])
    script_id = re.sub(r"\s", "", os.environ.get("SCRIPT_ID", ""))
    if script_id:
        report_web_deployments(token, script_id)
    project = os.environ.get("GCP_PROJECT", "").strip()
    if not project:
        sys.exit("::error::Google Cloud のプロジェクト番号がありません(手動実行で gcp_project を1回指定すると、以後は覚えて使います)")
    shown_hours = fetch_hours(args.hours, args.alert, args.alert_maintenance_minutes)
    since = (datetime.now(timezone.utc) - timedelta(hours=shown_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    print(f"## 直近{shown_hours}時間の実行記録(ログ {len(entries)} 件)")
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
        now = datetime.now(timezone.utc)
        problems = all_alert_problems(entries, now, args.hours, args.alert_recent_minutes, args.alert_maintenance_minutes)
        write_alert_output(problems, os.environ.get("GITHUB_OUTPUT", ""))
        for p in problems:
            print(f"::error title=glow-ma の自動処理に問題があります::{p}")
        if problems:
            sys.exit(1)
        print("自動点検: 問題なし(承認切れなし・稼働記録あり・日次メンテナンスの失敗なし)")


if __name__ == "__main__":
    main()
