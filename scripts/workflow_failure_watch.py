#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定時実行(schedule)が失敗し続けているワークフローを、1つの Issue にまとめて知らせる。

2026-11-24 の点検で、定時実行の失敗がそれぞれ気づかれないまま続いていた:
  - 結果マガの週次集計: 2026-10-12 から7週すべて失敗(トークン未登録)
  - 単発記事の下書き: 2026-10-22 から失敗(APIキーが無効)
  - Lighthouse: 2026-10-03 から毎日失敗(51日)
  - 制度収集の出荷ゲート: 2026-11-15 から毎回失敗(点検期限切れ)
ワークフローごとの Issue や失敗メールはあっても、「どれが何日止まっているか」を
1か所で見る場所が無かった。ここで、main の定時実行を新しい順にたどり、
いま連続で失敗しているワークフローを一覧にする。

判定: 直近の定時実行から数えて失敗(failure / timed_out / startup_failure)が
MIN_STREAK 回以上続いている、または2回以上の失敗が MIN_DAYS 日を超えて続いているもの
(週1回の処理でも拾う)。1回だけの失敗(一時的な不具合)は載せない。
ワークフローごとに直近 PER_WORKFLOW 件の定時実行を取る(全体の新しい順だと、
定時の多いリポジトリでは週1回の処理が数日分しか見えないため)。

使い方:
  GH_TOKEN=... GITHUB_REPOSITORY=owner/repo python scripts/workflow_failure_watch.py > body.md
  python scripts/workflow_failure_watch.py --self-test
出力の末尾に <!-- failing: a,b --> を付ける(前回との差分=新しく止まったものの判定に使う)。
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import urllib.request

FAIL = {"failure", "timed_out", "startup_failure"}
OK = {"success"}
MIN_STREAK = 3
MIN_DAYS = 2
PER_WORKFLOW = 30
JST = dt.timezone(dt.timedelta(hours=9))


# いま定時実行の設定(schedule)があるワークフローだけを見る。定時を止めた処理
# (2026-10-25 に止めた Fukuda・note マガジン等)は、止める前の失敗が残っていても載せない
SCHEDULE_LINE = re.compile(r"^\s+schedule:\s*(#.*)?$", re.M)


def scheduled_paths(base="."):
    out = set()
    for p in glob.glob(os.path.join(base, ".github", "workflows", "*.y*ml")):
        try:
            with open(p, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if SCHEDULE_LINE.search(text):
            out.add(os.path.relpath(p, base).replace(os.sep, "/"))
    return out


def _ts(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def _get(url, token, opener):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    with opener(req, timeout=30) as r:
        return json.load(r)


def fetch_runs(repo, token, opener=urllib.request.urlopen):
    api = f"https://api.github.com/repos/{repo}/actions"
    wfs = _get(f"{api}/workflows?per_page=100", token, opener).get("workflows", [])
    runs = []
    for wf in wfs:
        if wf.get("state") != "active":
            continue
        got = _get(f"{api}/workflows/{wf['id']}/runs?branch=main&event=schedule"
                   f"&status=completed&per_page={PER_WORKFLOW}", token, opener)
        for r in got.get("workflow_runs", []):
            r.setdefault("name", wf.get("name"))
            runs.append(r)
    return runs


def summarize(runs, now=None, only_paths=None):
    """ワークフローごとに、新しい順で連続している失敗を数える。
    同じ名前のワークフロー(別ファイル)が混ざらないよう、ファイル(workflow_id / path)ごとに分ける。
    only_paths を渡すと、そのファイルだけを見る(いま定時の設定があるもの)。"""
    now = now or dt.datetime.now(dt.timezone.utc)
    by = {}
    for r in runs:
        if only_paths is not None and r.get("path") not in only_paths:
            continue
        key = r.get("workflow_id") or r.get("path") or r.get("name")
        by.setdefault(key, []).append(r)
    names = {}
    for rs in by.values():
        names.setdefault(rs[0].get("name"), set()).add(rs[0].get("path"))
    out = []
    for rs in by.values():
        name = rs[0].get("name")
        if len(names.get(name, ())) > 1:          # 同じ名前が2つ以上 → ファイル名を添える
            name = f"{name}({os.path.basename(rs[0].get('path') or '')})"
        rs.sort(key=lambda r: r["created_at"], reverse=True)
        streak = []
        last_ok = None
        for r in rs:
            c = r.get("conclusion")
            if c in FAIL:
                if last_ok is None:
                    streak.append(r)
                continue
            if c in OK:
                last_ok = r
                break
            # cancelled / skipped などは数えずに飛ばす
        if not streak:
            continue
        since = _ts(streak[-1]["created_at"])
        days = (now - since).total_seconds() / 86400
        if len(streak) < MIN_STREAK and not (len(streak) >= 2 and days >= MIN_DAYS):
            continue
        out.append({
            "name": name, "streak": len(streak), "since": since, "days": days,
            "last_ok": _ts(last_ok["created_at"]) if last_ok else None,
            "url": streak[0].get("html_url", ""),
            "complete": last_ok is not None,   # 見た範囲に成功が無ければ、失敗はもっと前から
        })
    out.sort(key=lambda x: -x["days"])
    return out


def _d(t):
    return t.astimezone(JST).strftime("%Y-%m-%d") if t else "—"


def render(rows, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not rows:
        return ""
    lines = [f"定時実行が失敗し続けているワークフローが **{len(rows)}件** あります"
             f"({_d(now)} 時点・main の定時実行のみ)。",
             f"1回だけの失敗は載せていません(連続{MIN_STREAK}回以上、または2回以上の失敗が{MIN_DAYS}日以上続いているもの)。",
             "", "| ワークフロー | 連続失敗 | 失敗が始まった日 | 最後の成功 | 最新の失敗 |",
             "|---|---|---|---|---|"]
    for r in rows:
        since = _d(r["since"]) + ("" if r["complete"] else " 以前")
        lines.append(f"| {r['name']} | {r['streak']}回({r['days']:.0f}日) | {since} | "
                     f"{_d(r['last_ok'])} | [ログ]({r['url']}) |")
    lines += ["", "原因はログの最初のエラー行で確かめる。秘密情報(トークン・APIキー)の登録切れは、"
              "コードでは直せないので人が登録し直す。",
              "", f"<!-- failing: {','.join(sorted(r['name'] for r in rows))} -->"]
    return "\n".join(lines)


def new_names(body, prev_body):
    def names(b):
        for line in (b or "").splitlines():
            if line.startswith("<!-- failing:"):
                return {n for n in line[len("<!-- failing:"):].rstrip("->").strip().split(",") if n}
        return set()
    return sorted(names(body) - names(prev_body))


def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    now = dt.datetime(2026, 11, 24, 0, 0, tzinfo=dt.timezone.utc)

    def run(name, day, concl, hour=0):
        t = dt.datetime(2026, 11, day, hour, 0, tzinfo=dt.timezone.utc)
        return {"name": name, "created_at": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "conclusion": concl, "html_url": f"https://x/{name}/{day}/{hour}"}

    runs = [
        # 毎日失敗が続く(Lighthouse 型)
        *[run("daily-broken", d, "failure") for d in range(18, 24)], run("daily-broken", 17, "success"),
        # 1回だけの失敗(一時的)→ 載せない
        run("flaky", 23, "failure"), run("flaky", 22, "success"),
        # 週1回で2回連続・14日(結果マガ型)→ 日数で載せる
        run("weekly-broken", 23, "failure"), run("weekly-broken", 16, "failure"),
        # 週1回の1回だけの失敗(5日前)→ 載せない
        run("weekly-once", 19, "failure"), run("weekly-once", 12, "success"),
        # 直近は成功 → 載せない
        run("recovered", 23, "success"), run("recovered", 22, "failure"), run("recovered", 21, "failure"),
        # 取り消しは数えずに飛ばす
        run("cancel-mixed", 23, "failure"), run("cancel-mixed", 22, "cancelled"),
        run("cancel-mixed", 21, "failure"), run("cancel-mixed", 20, "failure"), run("cancel-mixed", 19, "success"),
        # 見た範囲に成功が無い
        *[run("never-ok", 23, "failure", h) for h in (1, 2, 3)],
    ]
    rows = summarize(runs, now)
    names = [r["name"] for r in rows]
    check("毎日の失敗が載る", "daily-broken" in names)
    check("1回だけの失敗は載らない", "flaky" not in names)
    check("週1回の2回連続(14日)は日数で載る", "weekly-broken" in names)
    check("直近が成功なら載らない", "recovered" not in names)
    check("1回だけの失敗は日数がたっても載らない", "weekly-once" not in names)

    # 同じ名前の別ファイル: 片方の成功で、もう片方の失敗を隠さない
    twin = [dict(run("Post X", d, "failure"), workflow_id=1, path=".github/workflows/a.yml") for d in (21, 22, 23)]
    twin += [dict(run("Post X", d, "success", 1), workflow_id=2, path=".github/workflows/b.yml") for d in (21, 22, 23)]
    tw = summarize(twin, now)
    check("同じ名前の別ファイルを混ぜない", len(tw) == 1 and tw[0]["streak"] == 3 and "a.yml" in tw[0]["name"])
    # 定時を止めたファイルは載せない
    only = summarize(twin, now, only_paths={".github/workflows/b.yml"})
    check("定時の設定が無いファイルは載せない", only == [])
    check("schedule の行を見つける", bool(SCHEDULE_LINE.search("on:\n  schedule:\n    - cron: x\n")))
    check("コメントにした schedule は見ない", not SCHEDULE_LINE.search("on:\n  # schedule:\n  workflow_dispatch: {}\n"))
    cm = next((r for r in rows if r["name"] == "cancel-mixed"), None)
    check("取り消しは飛ばして失敗を数える", cm is not None and cm["streak"] == 3)
    db = next(r for r in rows if r["name"] == "daily-broken")
    check("連続回数と最後の成功", db["streak"] == 6 and db["last_ok"].day == 17)
    check("長く止まっている順", names[0] == "weekly-broken")
    nv = next(r for r in rows if r["name"] == "never-ok")
    check("成功が見つからなければ「以前」と書く", not nv["complete"] and "以前" in render([nv], now))
    md = render(rows, now)
    check("一覧と差分の印", "<!-- failing: cancel-mixed,daily-broken,never-ok,weekly-broken -->" in md)
    check("何も無ければ空", render([], now) == "")
    check("新しく止まったものだけを拾う",
          new_names(md, "<!-- failing: daily-broken,weekly-broken -->") == ["cancel-mixed", "never-ok"])
    check("前回が無ければ全部が新しい", len(new_names(md, "")) == 4)

    import io

    class Resp:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return io.StringIO(json.dumps(self.data))

        def __exit__(self, *a):
            return False
    calls = []

    def opener(req, timeout=None):
        calls.append(req.full_url)
        if "/workflows?" in req.full_url:
            return Resp({"workflows": [{"id": 1, "name": "a", "state": "active"},
                                       {"id": 2, "name": "b", "state": "disabled_manually"},
                                       {"id": 3, "name": "c", "state": "active"}]})
        return Resp({"workflow_runs": [{"created_at": "2026-11-23T00:00:00Z", "conclusion": "failure"}]})
    got = fetch_runs("o/r", "t", opener=opener)
    check("止めてあるワークフローは見ない", len(calls) == 3 and not any("/workflows/2/" in c for c in calls))
    check("main の定時実行だけを取る", all("branch=main&event=schedule" in c for c in calls[1:]))
    check("ワークフロー名を付ける", [r["name"] for r in got] == ["a", "c"])

    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--new-since", metavar="PREV_BODY_FILE",
                    help="前回の本文と比べ、新しく止まったワークフロー名を1行ずつ出す(本文は標準入力)")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.new_since:
        body = sys.stdin.read()
        try:
            with open(a.new_since, encoding="utf-8") as f:
                prev = f.read()
        except OSError:
            prev = ""
        print("\n".join(new_names(body, prev)))
        return 0
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_TOKEN")
    if not repo or not token:
        print("GITHUB_REPOSITORY と GH_TOKEN が必要です", file=sys.stderr)
        return 2
    md = render(summarize(fetch_runs(repo, token), only_paths=scheduled_paths()))
    if md:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
