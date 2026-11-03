#!/usr/bin/env python3
"""もらいわすれ堂 診断ページ監視の通知制御(diagnosis-monitor.yml / diagnosis-monitor-watchdog.yml から呼ぶ)。

サブコマンド:
  incident  15分監視の結果から障害Issueを更新し、送るLINE文面を決める
  watchdog  監視そのものの停止・準備失敗を調べ、監視システム側のIssueを更新する
  gate      LINEを送ってよいかを判定する(通数の台帳・LINEの残り通数)。送れないときは障害Issueに記録する
  record    LINE送信の成否を障害Issueに記録する(失敗・保留は次回の再送対象)

障害は2種類に分けて扱う(混ぜると、監視が壊れただけで「診断ページ異常」と通知してしまう):
  診断ページの障害   ラベル diagnosis-monitor
  監視システムの故障 ラベル diagnosis-monitor-system(この間、診断ページの状態は不明)

LINEは顧客向け配信と同じ公式アカウントの通数を使うため、この監視からは24時間3通・30日15通まで。
送る前に台帳Issue(diagnosis-line-ledger)へ記録してから数え直し、上限を超えた側は記録を消して送らない
(同時に動いても上限を突破しない)。数えられない・LINEの残りが読めないときは送らない(安全側)。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

PAGE = "diagnosis-monitor"
SYSTEM = "diagnosis-monitor-system"
LEDGER = "diagnosis-line-ledger"
LABELS = {
    PAGE: ("B60205", "もらいわすれ堂 診断ページの障害(15分監視)"),
    SYSTEM: ("D93F0B", "診断ページの監視システムの故障(ページの状態は不明)"),
    LEDGER: ("BFD4F2", "診断監視のLINE送信記録(通数の上限管理)"),
}
CHECK_STEP = "Check diagnosis page"
INCIDENT_STEP = "Update incident issue"

CAP_24H = int(os.environ.get("LINE_CAP_24H", "3"))
CAP_30D = int(os.environ.get("LINE_CAP_30D", "15"))
LINE_RESERVE = int(os.environ.get("LINE_RESERVE", "50"))
ESCALATE_MIN = int(os.environ.get("ESCALATE_MIN", "240"))
RECOVERY_RESEND_H = int(os.environ.get("RECOVERY_RESEND_H", "24"))
MAX_GAP_MIN = int(os.environ.get("MAX_GAP_MIN", "360"))
PREP_FAIL_RUNS = int(os.environ.get("PREP_FAIL_RUNS", "4"))

BRAND = "【もらいわすれ堂】"


class GitHubError(Exception):
    pass


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class GitHub:
    """gh api の薄いラッパ。リポジトリは GITHUB_REPOSITORY で明示する(checkout に依存しない)。"""

    def __init__(self, repo):
        self.repo = repo

    def _api(self, method, path, payload=None):
        args = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
        data = None
        if payload is not None:
            args += ["--input", "-"]
            data = json.dumps(payload)
        try:
            r = subprocess.run(args, input=data, capture_output=True, text=True, timeout=60)
        except Exception as e:
            raise GitHubError(f"{method} {path}: {e}") from e
        if r.returncode != 0:
            raise GitHubError(f"{method} {path}: {r.stderr.strip()[:200]}")
        return json.loads(r.stdout) if r.stdout.strip() else None

    def ensure_label(self, name):
        color, desc = LABELS[name]
        try:
            self._api("POST", f"repos/{self.repo}/labels", {"name": name, "color": color, "description": desc})
        except GitHubError:
            pass  # 既にある

    def issues(self, label, state="all"):
        out = self._api("GET", f"repos/{self.repo}/issues?labels={label}&state={state}&per_page=50&sort=created&direction=desc")
        return [i for i in out if "pull_request" not in i]

    def comments(self, number, since=None):
        q = f"&since={iso(since)}" if since else ""
        return self._api("GET", f"repos/{self.repo}/issues/{number}/comments?per_page=100{q}")

    def create_issue(self, title, body, label):
        self.ensure_label(label)
        return self._api("POST", f"repos/{self.repo}/issues", {"title": title, "body": body, "labels": [label]})

    def comment(self, number, body):
        return self._api("POST", f"repos/{self.repo}/issues/{number}/comments", {"body": body})

    def close(self, number):
        self._api("PATCH", f"repos/{self.repo}/issues/{number}", {"state": "closed", "state_reason": "completed"})

    def delete_comment(self, comment_id):
        self._api("DELETE", f"repos/{self.repo}/issues/comments/{comment_id}")

    def workflow(self, file):
        return self._api("GET", f"repos/{self.repo}/actions/workflows/{file}")

    def runs(self, file, per_page=100):
        return self._api("GET", f"repos/{self.repo}/actions/workflows/{file}/runs?event=schedule&per_page={per_page}")["workflow_runs"]

    def jobs(self, run_id):
        return self._api("GET", f"repos/{self.repo}/actions/runs/{run_id}/jobs")["jobs"]


# ---------- 障害Issueの状態 ----------

def thread_texts(gh, issue):
    return [issue.get("body") or ""] + [c["body"] or "" for c in gh.comments(issue["number"])]


def last_marker(texts, pattern):
    found = None
    for t in texts:
        for m in re.finditer(pattern, t):
            found = m
    return found


def last_sig(texts):
    m = last_marker(texts, r"<!-- sig: (\S+) -->")
    return m.group(1) if m else ""


def line_state(texts):
    """障害Issue上の最後のLINE送信状態: ok / failed / held / ""(まだ送っていない)。"""
    m = last_marker(texts, r"<!-- line: (ok|failed|held)(?: reason=([^>]*?))? -->")
    return (m.group(1), (m.group(2) or "").strip()) if m else ("", "")


def issue_url(repo, number):
    return f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/issues/{number}"


def report_block(report):
    return "```\n" + report.rstrip() + "\n```"


def first_error(result):
    errs = (result or {}).get("errors") or []
    return errs[0]["msg"][:120] if errs else ""


def handle_system(gh, repo, now, sig, reason, run_url):
    """監視システム側の故障。開いていなければ起票、内容が変われば追記、未達の通知があれば再送。"""
    opened = gh.issues(SYSTEM, "open")
    if not opened:
        body = (f"<!-- sig: {sig} -->\n自動検知: 診断ページの**監視が動いていません**。この間、診断ページの状態は分かりません"
                f"(診断ページの障害とは限りません)。\n\n- 内容: {reason}\n- 実行: {run_url}\n")
        iss = gh.create_issue(f"⚠️ 診断ページの監視が動いていません: {sig}", body, SYSTEM)
        return iss["number"], f"⚠️{BRAND}診断ページの監視が動いていません(ページの状態は不明)\n{reason}\n{issue_url(repo, iss['number'])}"
    iss = opened[0]
    texts = thread_texts(gh, iss)
    if last_sig(texts) != sig:
        gh.comment(iss["number"], f"<!-- sig: {sig} -->\n⚠️ 監視の不調の内容が変わりました: {reason}\n- 実行: {run_url}")
        return iss["number"], f"⚠️{BRAND}診断ページの監視の不調が続いています(内容が変わりました)\n{reason}\n{issue_url(repo, iss['number'])}"
    if line_state(texts)[0] in ("failed", "held"):
        return iss["number"], f"🔁{BRAND}(再送)診断ページの監視が動いていません(ページの状態は不明)\n{reason}\n{issue_url(repo, iss['number'])}"
    return iss["number"], ""


def close_system(gh, repo, run_url, why):
    """監視が動いたことを確認できたら、監視システム側のIssueを閉じる。誰かに知らせていた場合だけ再開を通知する。"""
    msg, target = "", None
    for iss in gh.issues(SYSTEM, "open"):
        texts = thread_texts(gh, iss)
        gh.comment(iss["number"], f"✅ {why}。自動クローズします。 {run_url}")
        gh.close(iss["number"])
        if "<!-- line: ok -->" in "".join(texts) and not msg:
            msg, target = f"✅{BRAND}診断ページの監視が再開しました\n{issue_url(repo, iss['number'])}", iss["number"]
    return target, msg


def cmd_incident(gh, repo, args, now):
    run_url = args.run_url
    result = None
    if os.path.exists(args.result):
        try:
            with open(args.result, encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            result = None
    if result is None:
        # 検査まで届かなかった(Playwright導入失敗・検査スクリプトの異常終了など)。ページの障害とは扱わない
        return handle_system(gh, repo, now, "MONITOR_SETUP", "監視の準備(ブラウザの導入など)で失敗し、診断ページを検査できませんでした", run_url)

    sys_target, sys_msg = close_system(gh, repo, run_url, "診断ページの検査が再び実行できました")
    report = ""
    if os.path.exists(args.report):
        with open(args.report, encoding="utf-8") as f:
            report = f.read()
    sig = result.get("signature") or ""
    summary = first_error(result) or sig
    opened = gh.issues(PAGE, "open")

    if result.get("ok"):
        if opened:
            iss = opened[0]
            mins = int((now - parse_ts(iss["created_at"])).total_seconds() // 60)
            gh.comment(iss["number"], f"✅ 復旧: 診断ページが正常に戻りました(障害の継続 約{mins}分)。自動クローズします。 {run_url}")
            gh.close(iss["number"])
            return iss["number"], f"✅{BRAND}診断ページが復旧しました\n障害の継続: 約{mins}分\n{issue_url(repo, iss['number'])}"
        # 直近に閉じた障害の復旧通知が届いていなければ送り直す
        for iss in gh.issues(PAGE, "closed")[:1]:
            closed = iss.get("closed_at")
            if closed and now - parse_ts(closed) <= timedelta(hours=RECOVERY_RESEND_H):
                if line_state(thread_texts(gh, iss))[0] in ("failed", "held"):
                    return iss["number"], f"🔁{BRAND}(再送)診断ページは復旧しています\n{issue_url(repo, iss['number'])}"
        return sys_target, sys_msg

    body = f"<!-- sig: {sig} -->\n- 実行: {run_url}\n\n{report_block(report)}\n"
    if not opened:
        iss = gh.create_issue(f"🚨 診断ページ異常: {sig}",
                              "自動検知: もらいわすれ堂の診断ページで、利用者が制度を検索できない可能性があります。\n\n" + body, PAGE)
        return iss["number"], f"🚨{BRAND}診断ページ異常\n{summary}\n{issue_url(repo, iss['number'])}"
    iss = opened[0]
    texts = thread_texts(gh, iss)
    prev = last_sig(texts)
    mins = int((now - parse_ts(iss["created_at"])).total_seconds() // 60)
    url = issue_url(repo, iss["number"])
    if sig != prev:
        gh.comment(iss["number"], f"⚠️ 症状が変わりました({prev} → {sig})\n\n{body}")
        return iss["number"], f"⚠️{BRAND}診断ページの症状が変わりました\n{summary}\n{url}"
    if mins >= ESCALATE_MIN and not any("<!-- escalated -->" in t for t in texts):
        gh.comment(iss["number"], f"<!-- escalated -->\n⏰ 異常が4時間以上つづいています(約{mins}分)。\n\n{body}")
        return iss["number"], f"⏰{BRAND}診断ページの異常が4時間以上つづいています\n{summary}\n{url}"
    if line_state(texts)[0] in ("failed", "held"):
        return iss["number"], f"🔁{BRAND}(再送)診断ページの異常がつづいています\n{summary}\n{url}"
    return iss["number"], ""


# ---------- 停止検知 ----------

def cmd_watchdog(gh, repo, args, now):
    wf = gh.workflow(args.workflow)
    runs = gh.runs(args.workflow)
    problem = ""
    if wf.get("state") != "active":
        problem = ("WORKFLOW_DISABLED", f"監視ワークフローが無効になっています(state={wf.get('state')})。Actions画面から有効化してください")
    elif not runs:
        age = (now - parse_ts(wf["created_at"])).total_seconds() / 60
        if age > MAX_GAP_MIN:
            problem = ("NEVER_SCHEDULED", f"監視ワークフローが一度もスケジュール起動していません(登録から約{int(age)}分)")
    else:
        gap = (now - parse_ts(runs[0]["created_at"])).total_seconds() / 60
        if gap > MAX_GAP_MIN:
            problem = ("STALLED", f"監視が約{int(gap)}分起動していません(最終起動 {runs[0]['created_at']})")
    checked, incident_failed = [], []
    if not problem and runs:
        # 「起動はしたが検査まで届かない」は、起動の途絶とは別に見る(Playwright導入失敗・checkout失敗・中断など)
        done = [r for r in runs if r.get("status") == "completed"][:PREP_FAIL_RUNS]
        for r in done:
            steps = {s["name"]: s.get("conclusion") for j in gh.jobs(r["id"]) if j["name"] == "monitor" for s in j.get("steps", [])}
            checked.append(steps.get(CHECK_STEP) in ("success", "failure"))
            incident_failed.append(steps.get(INCIDENT_STEP) == "failure")
        if len(done) >= PREP_FAIL_RUNS and not any(checked):
            problem = ("PREP_FAILING", f"監視は起動していますが、直近{len(done)}回とも診断ページの検査まで進めていません(準備段階の失敗・中断)")
        elif len(done) >= PREP_FAIL_RUNS and all(incident_failed):
            problem = ("ISSUE_UPDATE_FAILING", f"直近{len(done)}回とも障害Issueの更新に失敗しています(通知が届かない可能性)")

    day_ago = now - timedelta(hours=24)
    times = sorted(parse_ts(r["created_at"]) for r in runs if parse_ts(r["created_at"]) >= day_ago)
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(times, times[1:])]
    stats = f"直近24時間の起動: {len(times)}回(設定上は96回)/ 最大間隔: {int(max(gaps)) if gaps else 0}分(取得{len(runs)}件の範囲)"
    write_summary(stats)
    print(stats)
    if problem:
        print(f"::error::{problem[1]}")
        target, msg = handle_system(gh, repo, now, problem[0], problem[1], args.run_url)
        return target, msg, problem[0]
    # 閉じるのは、最新の回で検査まで届いたと確かめられたときだけ(準備失敗が続き始めた段階で閉じると、起票と通知を繰り返す)
    if checked and checked[0]:
        target, msg = close_system(gh, repo, args.run_url, "監視が動いていることを確認しました")
        return target, msg, ""
    return None, "", ""


# ---------- LINE送信の可否 ----------

def evaluate_quota(quota, consumption, reserve):
    """(送ってよいか, 理由)。形が想定と違えば「上限不明」として送らない。"""
    if not isinstance(quota, dict) or not isinstance(consumption, dict):
        return False, "LINEの送信枠を読み取れません(上限不明)"
    used = consumption.get("totalUsage")
    if not isinstance(used, int):
        return False, "LINEの使用量を読み取れません(上限不明)"
    if quota.get("type") == "none":
        return True, "上限なしのプラン"
    if quota.get("type") != "limited" or not isinstance(quota.get("value"), int):
        return False, f"LINEの送信枠の形式が想定外です(上限不明: {str(quota)[:60]})"
    remaining = quota["value"] - used
    if remaining <= reserve:
        return False, f"LINEの今月の残りが{remaining}通で、顧客向け配信のための確保分({reserve}通)以下"
    return True, f"残り{remaining}通"


def fetch_quota(token, timeout=10):
    def get(path):
        req = urllib.request.Request("https://api.line.me" + path, headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    return get("/v2/bot/message/quota"), get("/v2/bot/message/quota/consumption")


def ledger_entries(gh, now):
    since = now - timedelta(days=30)
    out = []
    for iss in gh.issues(LEDGER, "all"):
        for c in gh.comments(iss["number"], since=since):
            if "<!-- line-ledger" in (c.get("body") or ""):
                out.append(c)
    return out


def within_cap(entries, now, own_id=None):
    """台帳から上限内かを判定する。own_id を渡すと、その記録が古い順で上限内に入るかを見る。"""
    order = sorted(entries, key=lambda c: (c["created_at"], c["id"]))
    for hours, cap in ((24, CAP_24H), (24 * 30, CAP_30D)):
        window = [c for c in order if now - parse_ts(c["created_at"]) <= timedelta(hours=hours)]
        if own_id is None:
            if len(window) >= cap:
                return False, f"監視からのLINEは{'24時間で' if hours == 24 else '30日で'}{cap}通まで(上限に達しました)"
        else:
            ids = [c["id"] for c in window]
            if own_id in ids and ids.index(own_id) >= cap:
                return False, "同時に送ろうとした通知があり、上限を超えるため取りやめました"
    return True, ""


def note_held(gh, issue, reason):
    """送らなかった理由を障害Issueに残す。同じ理由が続く間は書き足さない(15分ごとの書き込みを防ぐ)。"""
    try:
        state, last_reason = line_state(thread_texts(gh, {"number": issue, "body": ""}))
        if state == "held" and last_reason == reason:
            return
        gh.comment(issue, f"<!-- line: held reason={reason} -->\n📵 LINE通知は送っていません: {reason}。次回の監視で送り直します。")
    except GitHubError as e:
        print(f"::warning::保留の記録に失敗しました: {e}")


def cmd_gate(gh, repo, args, now, quota_fetcher=fetch_quota):
    issue = args.issue
    token = os.environ.get("LINE_TOKEN", "")
    if not token or os.environ.get("LINE_TO_SET") != "true":
        note_held(gh, issue, "LINEのSecretsが未設定")
        return False
    # 監視側の上限を先に見る(上限で保留が続く間に、15分ごとにLINE APIを呼ばない)
    try:
        ok, reason = within_cap(ledger_entries(gh, now), now)
    except GitHubError as e:
        note_held(gh, issue, "送信記録を確認できないため、安全側で送りません")
        print(f"::warning::{e}")
        return False
    if not ok:
        note_held(gh, issue, reason)
        return False
    try:
        quota, consumption = quota_fetcher(token)
    except Exception as e:
        # 理由には例外の種類名だけを書く(応答の中身やURLは残さない)
        note_held(gh, issue, f"LINEの送信枠を取得できません({type(e).__name__})")
        return False
    ok, reason = evaluate_quota(quota, consumption, LINE_RESERVE)
    if not ok:
        note_held(gh, issue, reason)
        return False
    mine = None

    def withdraw():
        if mine:
            try:
                gh.delete_comment(mine["id"])
            except GitHubError:
                pass  # 消せなくても、多めに数えるだけ(安全側)

    try:
        ledgers = gh.issues(LEDGER, "open")
        if ledgers:
            ledger_no = ledgers[0]["number"]
        else:
            ledger_no = gh.create_issue("診断監視のLINE送信記録(通数の上限管理)",
                                        "このIssueには、診断ページ監視がLINEを送ろうとした記録が自動で付きます。閉じないでください。", LEDGER)["number"]
        mine = gh.comment(ledger_no, f"<!-- line-ledger run:{args.run_id} issue:{issue} -->\nLINE送信: #{issue}")
        # 書いてから数え直す。同時に書いた側と順位を比べ、上限を超えた側は取り消す
        ok, reason = within_cap(ledger_entries(gh, now), now, own_id=mine["id"])
        if not ok:
            withdraw()
            note_held(gh, issue, reason)
            return False
    except GitHubError as e:
        withdraw()
        note_held(gh, issue, "送信記録を確認できないため、安全側で送りません")
        print(f"::warning::{e}")
        return False
    return True


def cmd_record(gh, repo, args, now):
    if args.outcome == "success":
        gh.comment(args.issue, "<!-- line: ok -->\n📨 LINEで通知しました。")
    else:
        gh.comment(args.issue, f"<!-- line: failed -->\n⚠️ LINE通知の送信に失敗しました。次回の監視で送り直します。 {args.run_url}")


# ---------- 入出力 ----------

def write_output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    lines = []
    for k, v in kv.items():
        v = "" if v is None else str(v)
        lines.append(f"{k}<<__EOF__\n{v}\n__EOF__" if "\n" in v else f"{k}={v}")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))


def write_summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main(argv=None, gh=None, now=None, quota_fetcher=fetch_quota):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    run_url = "{}/{}/actions/runs/{}".format(os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
                                            os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_RUN_ID", ""))
    a = sub.add_parser("incident")
    a.add_argument("--result", default="diagnosis_monitor_result.json")
    a.add_argument("--report", default="diagnosis_monitor_report.txt")
    w = sub.add_parser("watchdog")
    w.add_argument("--workflow", default="diagnosis-monitor.yml")
    g = sub.add_parser("gate")
    g.add_argument("--issue", type=int, required=True)
    r = sub.add_parser("record")
    r.add_argument("--issue", type=int, required=True)
    r.add_argument("--outcome", choices=["success", "failure"], required=True)
    for sp in (a, w, g, r):
        sp.add_argument("--run-url", default=run_url)
        sp.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "0"))
    args = p.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    gh = gh or GitHub(repo)
    now = now or datetime.now(timezone.utc)

    if args.cmd == "incident":
        target, msg = cmd_incident(gh, repo, args, now)
        write_output(issue=target or "", message=msg, handled="true")
    elif args.cmd == "watchdog":
        target, msg, problem = cmd_watchdog(gh, repo, args, now)
        write_output(issue=target or "", message=msg, problem=problem)
    elif args.cmd == "gate":
        allowed = cmd_gate(gh, repo, args, now, quota_fetcher)
        write_output(allowed="true" if allowed else "false")
    elif args.cmd == "record":
        cmd_record(gh, repo, args, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
