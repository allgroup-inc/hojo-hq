#!/usr/bin/env python3
"""もらいわすれ堂 診断ページ監視の障害Issueと、LINE通知の送信担当。

サブコマンド:
  incident  15分監視の結果から障害Issueを更新し、知らせる必要があれば送信要求を書く(diagnosis-monitor.yml)
  watchdog  監視の停止・送信担当の停滞・公開用制度データの保留を調べ、Issueと送信要求を書く(diagnosis-monitor-watchdog.yml)
  sender-reserve / sender-push / sender-record
            ただ1つの送信担当(diagnosis-line-sender.yml)。予約・送信・記録を別々のジョブで行い、書き込みの権限と
            LINE のトークンを同じジョブに置かない。重要度の高い順(診断ページの障害 → 監視システムの故障 → 制度データの注意)
  sender    予約・送信・記録を続けて行う(手元の確認用)。--mode check は確認モード(送らない・書き換えない)

障害は3種類に分ける(混ぜると、監視が壊れただけで「診断ページ異常」と通知してしまう):
  診断ページの障害   diagnosis-monitor
  監視システムの故障 diagnosis-monitor-system(この間、診断ページの状態は不明)
  制度データの注意   diagnosis-data-hold(公開用データの更新保留・必須制度の欠け)

送信要求は障害Issueの本文・コメントに埋め込む(<!-- line-want -->)。障害の記録と同じ1回の書き込みなので、
片方だけ残ることがない。送信担当は送信記録(bot/diagnosis-line-state ブランチの state.json)を、Contents API の
sha 一致を条件に書き換える(比較交換)。上限の判定と送信の予約を同じ書き換えで行い、競合した・書いた内容を
読み直せないときは送らない。LINE には要求IDを再試行キー(X-Line-Retry-Key)として渡すので、送った直後に
落ちて送り直しても二重には届かない。監視からのLINEは24時間3通・30日15通まで。制度データの注意は、
最後の1通を診断ページの障害のために残す。
"""
import argparse
import base64
import copy
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

PAGE = "diagnosis-monitor"
SYSTEM = "diagnosis-monitor-system"
DATA = "diagnosis-data-hold"
LABELS = {
    PAGE: ("B60205", "もらいわすれ堂 診断ページの障害(15分監視)"),
    SYSTEM: ("D93F0B", "診断ページの監視システムの故障(ページの状態は不明)"),
    DATA: ("FBCA04", "診断ページの公開用制度データの更新保留・必須制度の欠け"),
}
STATE_BRANCH = "bot/diagnosis-line-state"
STATE_PATH = "diagnosis-line/state.json"
PUBLISH_STATUS_PATH = "data/fukugiiro/publish_status.json"
CHECK_STEP = "Check diagnosis page"
INCIDENT_STEP = "Update incident issue"

CAP_24H = int(os.environ.get("LINE_CAP_24H", "3"))
CAP_30D = int(os.environ.get("LINE_CAP_30D", "15"))
LINE_RESERVE = int(os.environ.get("LINE_RESERVE", "50"))
ESCALATE_MIN = int(os.environ.get("ESCALATE_MIN", "240"))
MAX_GAP_MIN = int(os.environ.get("MAX_GAP_MIN", "360"))
PREP_FAIL_RUNS = int(os.environ.get("PREP_FAIL_RUNS", "4"))
REQUEST_TTL_H = 24 * 7  # 上限・送信枠で遅れても失わない。古すぎる知らせだけは取りやめる(記録は残す)
RETRY_KEY_TTL_H = 23    # LINE の再試行キーの有効期間(24時間)より前に打ち切る
STUCK_H = 6
BRAND = "【もらいわすれ堂】"

WANT_RE = re.compile(r"<!-- line-want id:([0-9a-f-]{36}) -->\n<!-- line-text\n(.*?)\n-->", re.S)
RESULT_RE = re.compile(r"<!-- line-result id:([0-9a-f-]{36}) state:(\w+)(?: reason=(.*?))? -->")
COUNTED = ("sending", "sent", "unknown")  # LINEの通数を使った(かもしれない)送信
# 解消してIssueを閉じたコメントの印。これより前の送信要求は、まだ送れていなければ取り下げる
# (解消した後に「異常」だけが遅れて届くのを防ぐ。同じコメントの復旧の知らせは送る)
RESOLVED = "<!-- resolved -->"


class GitHubError(Exception):
    pass


class NotFound(GitHubError):
    pass


class Conflict(GitHubError):
    pass


class LineError(Exception):
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
            raise GitHubError(f"{method} {path}: {type(e).__name__}") from e
        if r.returncode != 0:
            m = re.search(r"HTTP (\d{3})", r.stderr)
            code = int(m.group(1)) if m else None
            msg = f"{method} {path.split('?')[0]}: HTTP {code}"
            if code == 404:
                raise NotFound(msg)
            if code in (409, 422):
                raise Conflict(msg)
            raise GitHubError(msg)
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

    def comments(self, number):
        return self._api("GET", f"repos/{self.repo}/issues/{number}/comments?per_page=100")

    def create_issue(self, title, body, label):
        self.ensure_label(label)
        return self._api("POST", f"repos/{self.repo}/issues", {"title": title, "body": body, "labels": [label]})

    def comment(self, number, body):
        return self._api("POST", f"repos/{self.repo}/issues/{number}/comments", {"body": body})

    def close(self, number):
        self._api("PATCH", f"repos/{self.repo}/issues/{number}", {"state": "closed", "state_reason": "completed"})

    def workflow(self, file):
        return self._api("GET", f"repos/{self.repo}/actions/workflows/{file}")

    def runs(self, file, per_page=100):
        return self._api("GET", f"repos/{self.repo}/actions/workflows/{file}/runs?event=schedule&per_page={per_page}")["workflow_runs"]

    def jobs(self, run_id):
        return self._api("GET", f"repos/{self.repo}/actions/runs/{run_id}/jobs")["jobs"]

    def get_file(self, path, ref):
        """(本文, sha)。ファイルかブランチが無ければ (None, None)。"""
        try:
            r = self._api("GET", f"repos/{self.repo}/contents/{path}?ref={ref}")
        except NotFound:
            return None, None
        return base64.b64decode(r["content"]).decode("utf-8"), r["sha"]

    def put_file(self, path, branch, text, sha, message):
        """sha が今のファイルと一致したときだけ書き換える(一致しなければ Conflict)。新しい sha を返す。"""
        payload = {"message": message, "content": base64.b64encode(text.encode("utf-8")).decode(), "branch": branch}
        if sha:
            payload["sha"] = sha
        return self._api("PUT", f"repos/{self.repo}/contents/{path}", payload)["content"]["sha"]

    def ensure_branch(self, branch):
        try:
            self._api("GET", f"repos/{self.repo}/git/ref/heads/{branch}")
            return
        except NotFound:
            pass
        main_sha = self._api("GET", f"repos/{self.repo}/git/ref/heads/main")["object"]["sha"]
        try:
            self._api("POST", f"repos/{self.repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": main_sha})
        except Conflict:
            pass  # 同時に作られた


class Line:
    """LINE Messaging API(管理者への通知専用)。トークンはログ・例外文面に出さない。"""

    API = "https://api.line.me"

    def __init__(self, token, to, timeout=15):
        self.token, self.to, self.timeout = token or "", to or "", timeout

    @property
    def configured(self):
        return bool(self.token and self.to)

    def _req(self, method, path, body=None, headers=None):
        h = {"Authorization": "Bearer " + self.token}
        h.update(headers or {})
        req = urllib.request.Request(self.API + path, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return res.status, res.read()
        except urllib.error.HTTPError as e:
            return e.code, b""
        except Exception as e:
            raise LineError(type(e).__name__) from None

    def quota(self):
        out = []
        for path in ("/v2/bot/message/quota", "/v2/bot/message/quota/consumption"):
            status, body = self._req("GET", path)
            if status != 200:
                raise LineError(f"HTTP {status}")
            try:
                out.append(json.loads(body.decode("utf-8")))
            except Exception:
                raise LineError("JSONとして読めない応答") from None
        return out[0], out[1]

    def push(self, text, retry_key):
        """('delivered'|'retry'|'rejected', 説明)。同じ再試行キーで受付済みなら 409 が返る(=届いている)。"""
        body = json.dumps({"to": self.to, "messages": [{"type": "text", "text": text[:4900]}]}).encode("utf-8")
        try:
            status, _ = self._req("POST", "/v2/bot/message/push", body,
                                  {"Content-Type": "application/json", "X-Line-Retry-Key": retry_key})
        except LineError as e:
            return "retry", f"応答なし({e})"
        if status == 200:
            return "delivered", ""
        if status == 409:
            return "delivered", "同じ再試行キーで受付済み(二重には届いていない)"
        if status == 429 or status >= 500:
            return "retry", f"HTTP {status}"
        return "rejected", f"HTTP {status}"


def _nonneg_int(v):
    return type(v) is int and v >= 0  # bool は int の子クラスなので type で比べる


def evaluate_quota(quota, consumption, reserve):
    """(送ってよいか, 理由)。公式仕様の形(type=none / type=limited + value)以外はすべて送らない。"""
    if not isinstance(quota, dict) or not isinstance(consumption, dict):
        return False, "LINEの送信枠を読み取れません(上限不明)"
    used = consumption.get("totalUsage")
    if not _nonneg_int(used):
        return False, "LINEの今月の使用量が0以上の整数ではありません(上限不明)"
    kind = quota.get("type")
    if kind == "none":
        if quota.get("value") is not None:
            return False, "LINEの送信枠の形式が想定外です(type=none に上限値がある)"
        return True, "上限なしのプラン"
    if kind == "limited":
        value = quota.get("value")
        if not _nonneg_int(value):
            return False, "LINEの送信枠の上限値が0以上の整数ではありません(上限不明)"
        remaining = value - used
        if remaining <= reserve:
            return False, f"LINEの今月の残りが{remaining}通で、顧客向け配信のための確保分({reserve}通)以下"
        return True, f"残り{remaining}通"
    return False, f"LINEの送信枠の種類が想定外です(type={str(kind)[:20]!r}・上限不明)"


# ---------- 障害Issue ----------

def want_block(message):
    rid = str(uuid.uuid4())
    text = message.replace("-->", "->").strip()
    return rid, f"<!-- line-want id:{rid} -->\n<!-- line-text\n{text}\n-->"


def thread_texts(gh, issue):
    return [issue.get("body") or ""] + [c.get("body") or "" for c in gh.comments(issue["number"])]


def last_sig(texts):
    found = ""
    for t in texts:
        for m in re.finditer(r"<!-- sig: (\S+) -->", t):
            found = m.group(1)
    return found


def was_delivered(texts):
    return any(m.group(2) == "sent" for t in texts for m in RESULT_RE.finditer(t))


def issue_url(repo, number):
    return f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/issues/{number}"


KINDS = {
    SYSTEM: {"title": "⚠️ 診断ページの監視が動いていません",
             "intro": "自動検知: 診断ページの**監視が動いていません**。この間、診断ページの状態は分かりません(診断ページの障害とは限りません)。",
             "first": f"⚠️{BRAND}診断ページの監視が動いていません(ページの状態は不明)",
             "change": f"⚠️{BRAND}診断ページの監視の不調が続いています(内容が変わりました)",
             "recover": f"✅{BRAND}診断ページの監視が再開しました"},
    DATA: {"title": "⚠️ 診断ページの制度データに注意が必要です",
           "intro": "自動検知: 診断ページが読む公開用の制度データ(site/fukugiiro/seido.json)に注意が必要です。",
           "first": f"⚠️{BRAND}診断ページの制度データに注意が必要です",
           "change": f"⚠️{BRAND}診断ページの制度データの注意の内容が変わりました",
           "recover": f"✅{BRAND}診断ページの制度データの注意が解消しました"},
}


def raise_issue(gh, label, sig, reason, run_url):
    """監視システムの故障・制度データの注意を起票する。初回と内容の変化のときだけ送信要求を書く。"""
    k = KINDS[label]
    opened = gh.issues(label, "open")
    if not opened:
        rid, wb = want_block(f"{k['first']}\n{reason}")
        body = f"<!-- sig: {sig} -->\n{k['intro']}\n\n- 内容: {reason}\n- 実行: {run_url}\n\n{wb}\n"
        return gh.create_issue(f"{k['title']}: {sig[:60]}", body, label)["number"], rid
    iss = opened[0]
    if last_sig(thread_texts(gh, iss)) != sig:
        rid, wb = want_block(f"{k['change']}\n{reason}")
        gh.comment(iss["number"], f"<!-- sig: {sig} -->\n⚠️ 内容が変わりました: {reason}\n- 実行: {run_url}\n\n{wb}")
        return iss["number"], rid
    return iss["number"], None


def resolve_issues(gh, label, run_url, why):
    """解消を確かめたら閉じる。誰かにLINEで知らせていた場合だけ、解消も知らせる。"""
    for iss in gh.issues(label, "open"):
        body = f"{RESOLVED}\n✅ {why}。自動クローズします。 {run_url}"
        if was_delivered(thread_texts(gh, iss)):
            body += "\n\n" + want_block(KINDS[label]["recover"])[1]
        gh.comment(iss["number"], body)
        gh.close(iss["number"])


def cmd_incident(gh, args, now):
    result = None
    if os.path.exists(args.result):
        try:
            with open(args.result, encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            result = None
    if result is None:
        # 検査まで届かなかった(Playwright導入失敗・検査スクリプトの異常終了など)。ページの障害とは扱わない
        return raise_issue(gh, SYSTEM, "MONITOR_SETUP", "監視の準備(ブラウザの導入など)で失敗し、診断ページを検査できませんでした", args.run_url)

    resolve_issues(gh, SYSTEM, args.run_url, "診断ページの検査が再び実行できました")
    report = ""
    if os.path.exists(args.report):
        with open(args.report, encoding="utf-8") as f:
            report = f.read()
    sig = result.get("signature") or ""
    errs = result.get("errors") or []
    summary = errs[0]["msg"][:120] if errs else sig
    opened = gh.issues(PAGE, "open")

    if result.get("ok"):
        if opened:
            iss = opened[0]
            mins = int((now - parse_ts(iss["created_at"])).total_seconds() // 60)
            rid, wb = want_block(f"✅{BRAND}診断ページが復旧しました\n障害の継続: 約{mins}分")
            gh.comment(iss["number"], f"{RESOLVED}\n✅ 復旧: 診断ページが正常に戻りました(障害の継続 約{mins}分)。自動クローズします。 {args.run_url}\n\n{wb}")
            gh.close(iss["number"])
            return iss["number"], rid
        return None, None

    body = f"<!-- sig: {sig} -->\n- 実行: {args.run_url}\n\n```\n{report.rstrip()}\n```\n"
    if not opened:
        rid, wb = want_block(f"🚨{BRAND}診断ページ異常\n{summary}")
        iss = gh.create_issue(f"🚨 診断ページ異常: {sig}",
                              "自動検知: もらいわすれ堂の診断ページで、利用者が制度を検索できない可能性があります。\n\n" + body + "\n" + wb, PAGE)
        return iss["number"], rid
    iss = opened[0]
    texts = thread_texts(gh, iss)
    prev = last_sig(texts)
    mins = int((now - parse_ts(iss["created_at"])).total_seconds() // 60)
    if sig != prev:
        rid, wb = want_block(f"⚠️{BRAND}診断ページの症状が変わりました\n{summary}")
        gh.comment(iss["number"], f"⚠️ 症状が変わりました({prev} → {sig})\n\n{body}\n{wb}")
        return iss["number"], rid
    if mins >= ESCALATE_MIN and not any("<!-- escalated -->" in t for t in texts):
        rid, wb = want_block(f"⏰{BRAND}診断ページの異常が4時間以上つづいています\n{summary}")
        gh.comment(iss["number"], f"<!-- escalated -->\n⏰ 異常が4時間以上つづいています(約{mins}分)。\n\n{body}\n{wb}")
        return iss["number"], rid
    return iss["number"], None


# ---------- 送信担当 ----------
#
# 送信担当は3つのジョブに分かれる(diagnosis-line-sender.yml)。書き込みの権限と LINE のトークンを同じジョブに置かない。
#   予約 sender-reserve: 送信要求を選び、上限を判定して送信記録に予約を書く(contents: write・LINEのトークンなし)
#   送信 sender-push:    予約を読み直して一致を確かめ、送信枠を確かめて LINE へ送る(contents: read・LINEのトークンあり)
#   記録 sender-record:  送信の結果を送信記録と障害Issueに残す(contents: write・LINEのトークンなし)
# ジョブの間で受け渡すのは要求ID・結果の種類・短い理由(HTTPコードなど)だけ。通知の文面は送信記録の予約から読む。
# 送信や記録の途中で落ちても予約が残り、次の起動が同じ要求IDを再試行キーとして送り直す(二重には届かない)。
# 1回の起動で送るのは1通まで。

# 重要度の高い順。診断ページの障害を最優先にし、制度データの注意は最後の1通を診断ページの障害のために残す
PRIORITY = {PAGE: 0, SYSTEM: 1, DATA: 2}
KEEP_FOR_URGENT = {DATA: 1}
OUTCOMES = ("delivered", "retry", "rejected", "held", "skip")
RID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def collect_requests(gh, now):
    """送信要求(line-want)と、その処理結果(line-result)を障害Issueから集める。"""
    reqs, results, seen = [], {}, set()
    for label in (PAGE, SYSTEM, DATA):
        for iss in gh.issues(label, "all"):
            if now - parse_ts(iss.get("updated_at") or iss["created_at"]) > timedelta(days=31):
                continue
            entries = [(iss["created_at"], iss.get("body") or "")]
            entries += [(c["created_at"], c.get("body") or "") for c in gh.comments(iss["number"])]
            last_resolved = max((i for i, (_, t) in enumerate(entries) if RESOLVED in t), default=-1)
            for idx, (at, text) in enumerate(entries):
                for m in WANT_RE.finditer(text):
                    if m.group(1) not in seen:
                        seen.add(m.group(1))
                        reqs.append({"id": m.group(1), "issue": iss["number"], "label": label, "at": at, "text": m.group(2),
                                     "resolved_before_sent": idx < last_resolved})
                for m in RESULT_RE.finditer(text):
                    results.setdefault(m.group(1), []).append((m.group(2), (m.group(3) or "").strip()))
    return sorted(reqs, key=lambda r: (r["at"], r["id"])), results


def empty_state():
    return {"version": 1, "log": [], "done": {}, "attempts": {}, "inflight": None}


def load_state(gh, create):
    text, sha = gh.get_file(STATE_PATH, STATE_BRANCH)
    if text is None:
        if not create:
            return empty_state(), None
        gh.ensure_branch(STATE_BRANCH)
        try:
            gh.put_file(STATE_PATH, STATE_BRANCH, json.dumps(empty_state()), None, "[skip ci] 診断監視のLINE送信記録を作成")
        except Conflict:
            pass  # 同時に作られた
        text, sha = gh.get_file(STATE_PATH, STATE_BRANCH)
        if text is None:
            raise GitHubError("送信記録を作成できません")
    try:
        st = json.loads(text)
        assert isinstance(st.get("log"), list) and isinstance(st.get("done"), dict)
        st.setdefault("attempts", {})
        st.setdefault("inflight", None)
    except Exception:
        raise GitHubError("送信記録の形式が壊れています(安全側で送らない)") from None
    return st, sha


def prune(st, now):
    st["log"] = [e for e in st["log"] if now - parse_ts(e["at"]) <= timedelta(days=31)]
    st["done"] = {k: v for k, v in st["done"].items() if now - parse_ts(v["at"]) <= timedelta(days=40)}
    st["attempts"] = {k: v for k, v in st["attempts"].items() if now - parse_ts(v["first_at"]) <= timedelta(days=40)}
    return st


def cas(gh, st, sha, apply, now, message):
    """比較交換で書き換える。他の処理が先に書いていれば Conflict(書き換えない)。"""
    new = prune(apply(copy.deepcopy(st)), now)
    new_sha = gh.put_file(STATE_PATH, STATE_BRANCH, json.dumps(new, ensure_ascii=False, indent=1), sha, "[skip ci] " + message)
    return new, new_sha


def cap_check(st, now, exclude, keep=0):
    """24時間3通・30日15通の上限。keep は重要度の高い通知のために残しておく通数。"""
    for hours, cap, label in ((24, CAP_24H, "24時間で"), (24 * 30, CAP_30D, "30日で")):
        n = sum(1 for e in st["log"] if e["id"] != exclude and e["status"] in COUNTED
                and now - parse_ts(e["at"]) <= timedelta(hours=hours))
        if n >= cap:
            return False, f"監視からのLINEは{label}{cap}通まで(上限に達しました)"
        if keep and n >= cap - keep:
            return False, f"監視からのLINEは{label}{cap}通まで。最後の{keep}通は診断ページの障害のために残しています"
    return True, ""


RESULT_TEXT = {
    "sent": "📨 LINEで通知しました。",
    "held": "📵 LINE通知を保留しています: {r}。条件が整いしだい送ります。",
    "failed": "⚠️ LINE送信が完了しませんでした({r})。次回に同じ再試行キーで送り直します(二重には届きません)。",
    "rejected": "⚠️ LINEが通知を受け付けませんでした({r})。この通知は送り直しません。",
    "superseded": "↪️ この通知は取り下げました({r})。",
    "expired": "⌛ 長く送れなかったため、この通知は取りやめました({r})。",
    "unknown": "❓ 送信の結果を確かめられないまま再試行の期限が近づいたため、二重送信を避けて取りやめました。届いていない可能性があります。",
}


def note_result(gh, req, state, reason, results):
    """処理結果を障害Issueに残す。同じ保留理由が続く間は書き足さない。"""
    past = results.get(req["id"], [])
    if state == "held" and past and past[-1] == ("held", reason):
        return
    try:
        gh.comment(req["issue"], f"<!-- line-result id:{req['id']} state:{state} reason={reason} -->\n" + RESULT_TEXT[state].format(r=reason))
        results.setdefault(req["id"], []).append((state, reason))
    except GitHubError as e:
        print(f"::warning::処理結果の記録に失敗しました: {e}")


def sender_reserve(gh, now, run_id, configured):
    """送信要求を1件選び、上限を判定して予約を書く。送るものがあれば {'rid', 'issue'} を返す(LINEには触れない)。"""
    reqs, results = collect_requests(gh, now)
    st, sha = load_state(gh, create=True)
    pending = [r for r in reqs if r["id"] not in st["done"]]

    # 同じIssueでは最新の要求だけを送る。古い要求と、長く送れなかった要求は取りやめる
    newest = {r["issue"]: r["id"] for r in pending}
    changes = []
    for r in pending:
        if newest[r["issue"]] != r["id"]:
            changes.append((r, "superseded", "同じIssueに新しい通知"))
        elif r.get("resolved_before_sent") and r["id"] != (st.get("inflight") or {}).get("id"):
            changes.append((r, "superseded", "送る前に解消した"))
        elif now - parse_ts(r["at"]) > timedelta(hours=REQUEST_TTL_H) and r["id"] not in st["attempts"]:
            changes.append((r, "expired", f"要求から{REQUEST_TTL_H}時間"))
    if changes:
        def close_out(s):
            for r, state, _ in changes:
                s["done"][r["id"]] = {"state": state, "at": iso(now)}
                if (s.get("inflight") or {}).get("id") == r["id"]:
                    s["inflight"] = None
            return s
        try:
            st, sha = cas(gh, st, sha, close_out, now, "診断監視のLINE: 取り下げ・期限切れを記録")
        except Conflict:
            print("::warning::送信記録を別の処理が先に書き換えました。安全側で、この回は送りません")
            return None
        for r, state, reason in changes:
            note_result(gh, r, state, reason, results)
    pending = [r for r in pending if r["id"] not in st["done"]]
    if not pending:
        print("送信待ちの要求はありません")
        return None
    if not configured:
        for r in pending:
            note_result(gh, r, "held", "LINEのSecretsが未設定", results)
        return None

    # 送信か記録の途中で止まった予約があれば、まずそれを同じ再試行キーで送り直す(通数は予約のときに数え済み)。
    # それ以外は重要度の高い順(診断ページの障害 → 監視システムの故障 → 制度データの注意)、同じ重要度なら古い順
    inflight = (st.get("inflight") or {}).get("id")
    pending.sort(key=lambda r: (r["id"] != inflight, PRIORITY[r["label"]], r["at"]))
    for r in pending:
        att = st["attempts"].get(r["id"])
        if att and now - parse_ts(att["first_at"]) > timedelta(hours=RETRY_KEY_TTL_H):
            def give_up(s, rid=r["id"]):
                s["done"][rid] = {"state": "unknown", "at": iso(now)}
                for e in s["log"]:
                    if e["id"] == rid:
                        e["status"] = "unknown"
                if (s.get("inflight") or {}).get("id") == rid:
                    s["inflight"] = None
                return s
            try:
                st, sha = cas(gh, st, sha, give_up, now, "診断監視のLINE: 結果不明で打ち切り")
            except Conflict:
                print("::warning::送信記録を別の処理が先に書き換えました。安全側で、この回は送りません")
                return None
            note_result(gh, r, "unknown", "", results)
            continue
        if r["id"] == inflight:
            print(f"途中で止まった予約(#{r['issue']})を同じ再試行キーで送り直します")
            return {"rid": r["id"], "issue": r["issue"]}
        ok, reason = cap_check(st, now, exclude=r["id"], keep=KEEP_FOR_URGENT.get(r["label"], 0))
        if not ok:
            # 先頭(いちばん重要な要求)が送れないなら、後ろの要求も送れない
            note_result(gh, r, "held", reason, results)
            return None

        def reserve(s, r=r):
            fresh = r["id"] not in s["attempts"]
            s["inflight"] = {"id": r["id"], "issue": r["issue"], "label": r["label"], "text": r["text"],
                             "requested_at": r["at"], "at": iso(now), "run": str(run_id), "fresh": fresh}
            s["attempts"].setdefault(r["id"], {"first_at": iso(now), "count": 0})["count"] += 1
            if not any(e["id"] == r["id"] for e in s["log"]):
                s["log"].append({"id": r["id"], "issue": r["issue"], "at": iso(now), "status": "sending"})
            return s
        try:
            _, reserved_sha = cas(gh, st, sha, reserve, now, f"診断監視のLINE: #{r['issue']} の送信を予約")
        except Conflict:
            print("::warning::送信記録を別の処理が先に書き換えました。安全側で、この回は送りません")
            return None
        # 書いた内容をGitHubから読み直せることを確かめる(確かめられなければ送らない。予約は次回に送り直す)
        check, check_sha = load_state(gh, create=False)
        if check_sha != reserved_sha or (check.get("inflight") or {}).get("id") != r["id"]:
            print("::warning::予約した送信記録を読み直せませんでした。安全側で、この回は送りません(次回に送り直します)")
            return None
        return {"rid": r["id"], "issue": r["issue"]}
    return None


def sender_push(gh, line, repo, now, rid):
    """予約を読み直して送る。('delivered'|'retry'|'rejected'|'held'|'skip', 理由)。送信記録には書かない。"""
    if not line.configured:
        return "held", "LINEのSecretsが未設定"
    st, _ = load_state(gh, create=False)
    inf = st.get("inflight") or {}
    if inf.get("id") != rid or not inf.get("text"):
        return "skip", "予約が見つかりません(別の送信担当が処理した)"
    try:
        quota, consumption = line.quota()
    except LineError as e:
        return "held", f"LINEの送信枠を取得できません({e})"
    ok, reason = evaluate_quota(quota, consumption, LINE_RESERVE)
    if not ok:
        return "held", reason
    late_h = int((now - parse_ts(inf.get("requested_at") or inf["at"])).total_seconds() // 3600)
    late = f"\n(約{late_h}時間前に検知。通数の上限などで遅れて届いています)" if late_h >= 1 else ""
    return line.push(f"{inf['text']}{late}\n{issue_url(repo, inf['issue'])}", rid)


def sender_record(gh, now, rid, outcome, detail):
    """送信の結果を送信記録と障害Issueに残す。結果が無い(送信ジョブが途中で止まった)ときは予約を残す。"""
    if outcome not in OUTCOMES:
        print("::warning::送信の結果が分かりません(送信ジョブが途中で止まった可能性)。予約を残し、次回に同じ再試行キーで送り直します")
        return
    if outcome == "skip":
        print(f"送りませんでした: {detail}")
        return

    def apply(s):
        inf = s.get("inflight") or {}
        mine = inf.get("id") == rid
        if outcome == "held":
            # 送っていないので、通数に数えない。初めての予約だった場合は、予約ごと取り消す
            if mine:
                if inf.get("fresh"):
                    s["log"] = [e for e in s["log"] if not (e["id"] == rid and e["status"] == "sending")]
                    s["attempts"].pop(rid, None)
                s["inflight"] = None
            return s
        for e in s["log"]:
            if e["id"] == rid:
                e["status"] = {"delivered": "sent", "retry": "unknown", "rejected": "rejected"}[outcome]
        if outcome == "delivered":
            s["done"][rid] = {"state": "sent", "at": iso(now)}
        elif outcome == "rejected":
            s["done"][rid] = {"state": "rejected", "at": iso(now)}
        if mine:
            s["inflight"] = None
        return s
    st, sha = load_state(gh, create=False)
    for _ in range(3):
        try:
            cas(gh, st, sha, apply, now, f"診断監視のLINE: 送信結果を記録({outcome})")
            break
        except Conflict:
            st, sha = load_state(gh, create=False)
    else:
        # 結果を残せなかった。予約が残るので、次回は同じ再試行キーで送り直す(届いていれば LINE が 409 を返す)
        raise GitHubError("送信結果を記録できませんでした")
    reqs, results = collect_requests(gh, now)
    req = next((r for r in reqs if r["id"] == rid), None)
    if req:
        note_result(gh, req, {"delivered": "sent", "retry": "failed", "rejected": "rejected", "held": "held"}[outcome], detail, results)


def cmd_sender(gh, line, repo, now, run_id):
    """予約 → 送信 → 記録を1つの処理で続けて行う(手元の確認・テスト用。本番はジョブを分ける)。"""
    res = sender_reserve(gh, now, run_id, line.configured)
    if not res:
        return 0
    outcome, detail = sender_push(gh, line, repo, now, res["rid"])
    sender_record(gh, now, res["rid"], outcome, detail)
    return 0


def cmd_check(gh, line, now):
    """LINE確認モード: 送らず、送信記録も書き換えずに、送信枠・使用量・送信待ちを表示する。"""
    lines = ["LINE確認モード(送信しない・記録を書き換えない)"]
    if not line.configured:
        lines.append("- LINEのSecrets: 未設定(送信担当は送らずに保留する)")
    else:
        try:
            quota, consumption = line.quota()
            ok, reason = evaluate_quota(quota, consumption, LINE_RESERVE)
            q_type = quota.get("type") if isinstance(quota, dict) else None
            q_val = quota.get("value") if isinstance(quota, dict) else None
            used = consumption.get("totalUsage") if isinstance(consumption, dict) else None
            lines.append(f"- 送信枠: type={str(q_type)[:20]} / 上限={q_val!s:.10} / 今月の使用={used!s:.10}")
            lines.append(f"- 判定: {'送れる' if ok else '送らない'}({reason})")
        except LineError as e:
            lines.append(f"- 送信枠: 取得できません({e}) → 送らない")
    try:
        reqs, results = collect_requests(gh, now)
        st, sha = load_state(gh, create=False)
        for hours, cap, label in ((24, CAP_24H, "24時間"), (24 * 30, CAP_30D, "30日")):
            n = sum(1 for e in st["log"] if e["status"] in COUNTED and now - parse_ts(e["at"]) <= timedelta(hours=hours))
            lines.append(f"- 監視からの送信: 直近{label} {n}/{cap}通")
        pending = sorted((r for r in reqs if r["id"] not in st["done"]), key=lambda r: (PRIORITY[r["label"]], r["at"]))
        lines.append(f"- 送信待ち: {len(pending)}件(送る順)" + ("(送信記録はまだありません)" if sha is None else ""))
        for r in pending[:10]:
            last = results.get(r["id"], [("", "")])[-1]
            age = int((now - parse_ts(r["at"])).total_seconds() // 60)
            kind = {PAGE: "診断ページの障害", SYSTEM: "監視システムの故障", DATA: "制度データの注意"}[r["label"]]
            lines.append(f"  - #{r['issue']}({kind})約{age}分前 {r['text'].splitlines()[0][:40]} / 最後の結果: {last[0] or 'なし'} {last[1]}")
    except GitHubError as e:
        lines.append(f"- 送信記録・送信待ち: 読み取れません({e})")
    text = "\n".join(lines)
    print(text)
    write_summary(text)
    return 0


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
    if not problem:
        # 送信担当が止まっていないか: 保留ではない送信待ちが長く残っていれば止まっている
        try:
            reqs, results = collect_requests(gh, now)
            st, _ = load_state(gh, create=False)
            stuck = [r for r in reqs if r["id"] not in st["done"] and now - parse_ts(r["at"]) > timedelta(hours=STUCK_H)
                     and (results.get(r["id"]) or [("", "")])[-1][0] != "held"]
            if stuck:
                problem = ("LINE_SENDER_STALLED", f"LINE通知の送信要求が{STUCK_H}時間以上処理されていません({len(stuck)}件)。diagnosis-line-sender を確認してください")
        except GitHubError as e:
            print(f"::warning::送信待ちを確認できませんでした: {e}")

    day_ago = now - timedelta(hours=24)
    times = sorted(parse_ts(r["created_at"]) for r in runs if parse_ts(r["created_at"]) >= day_ago)
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(times, times[1:])]
    stats = f"直近24時間の起動: {len(times)}回(設定上は96回)/ 最大間隔: {int(max(gaps)) if gaps else 0}分(取得{len(runs)}件の範囲)"
    write_summary(stats)
    print(stats)

    # 制度データの注意は Issue と LINE で知らせるだけにし、停止検知のジョブは赤にしない(監視の故障と見分けるため)
    data_notice = check_publish_status(gh, args.run_url)
    if problem:
        print(f"::error::{problem[1]}")
        raise_issue(gh, SYSTEM, problem[0], problem[1], args.run_url)
        return problem[0], data_notice
    # 閉じるのは、最新の回で検査まで届いたと確かめられたときだけ(準備失敗が続き始めた段階で閉じると、起票と通知を繰り返す)
    if checked and checked[0]:
        resolve_issues(gh, SYSTEM, args.run_url, "監視が動いていることを確認しました")
    return "", data_notice


def check_publish_status(gh, run_url):
    """収集が残した公開用データの判定記録を読み、保留・必須制度の欠けがあれば制度データの注意として起票する。"""
    try:
        text, _ = gh.get_file(PUBLISH_STATUS_PATH, "main")
    except GitHubError as e:
        print(f"::warning::公開用データの判定記録を読めませんでした: {e}")
        return ""
    if text is None:
        return ""
    try:
        s = json.loads(text)
        hold, missing = not s["publish"], list(s.get("required_missing") or [])
    except Exception:
        return ""
    data_notice(gh, hold, missing, s, run_url)
    if not hold and not missing:
        return ""
    return "DATA_HOLD" if hold else "REQUIRED_MISSING"


def _parse_data_sig(sig):
    """'HOLD|id1,id2' → (保留中か, 欠けている必須制度の組)。"""
    state, _, ids = (sig or "").partition("|")
    return state == "HOLD", frozenset(i for i in ids.split(",") if i)


def data_notice(gh, hold, missing, status, run_url):
    """制度データの注意。LINE を送るのは、欠けている必須制度の組み合わせが変わったときと、保留が始まったときだけ。
    保留の解除は Issue に書くだけで LINE は送らない(保留と公開が入れ替わるたびに通数を使い、診断ページの障害の通知を遅らせないため)。"""
    ids = frozenset(missing)
    sig = ("HOLD" if hold else "PUBLISHED") + "|" + ",".join(sorted(ids))
    opened = gh.issues(DATA, "open")
    prev_hold, prev_ids = _parse_data_sig(last_sig(thread_texts(gh, opened[0]))) if opened else (False, frozenset())
    k = KINDS[DATA]
    if not hold and not ids:
        if opened:
            why = "公開用の制度データは更新されており、必須制度の欠けもありません"
            # 欠けていた必須制度が戻ったときだけ、LINEで知らせていた相手に解消を知らせる(保留の解除だけなら Issue のみ)
            for iss in opened:
                body = f"<!-- sig: {sig} -->\n{RESOLVED}\n✅ {why}。自動クローズします。 {run_url}"
                if prev_ids and was_delivered(thread_texts(gh, iss)):
                    body += "\n\n" + want_block(k["recover"])[1]
                gh.comment(iss["number"], body)
                gh.close(iss["number"])
        return
    parts = []
    if hold:
        parts.append("公開用データの更新を保留しています(前回の公開データを表示中): " + " / ".join(status.get("reasons") or []))
    if ids:
        parts.append(f"必須制度(国の制度)が公開データにありません: {', '.join(sorted(ids)[:10])}")
    reason = "。".join(parts) + f"(収集 {status.get('checked_at', '')})"
    if not opened:
        rid, wb = want_block(f"{k['first']}\n{reason}")
        gh.create_issue(f"{k['title']}: {sig[:60]}", f"<!-- sig: {sig} -->\n{k['intro']}\n\n- 内容: {reason}\n- 実行: {run_url}\n\n{wb}\n", DATA)
        return
    if (hold, ids) == (prev_hold, prev_ids):
        return
    n = opened[0]["number"]
    if ids != prev_ids or (hold and not prev_hold):
        rid, wb = want_block(f"{k['change']}\n{reason}")
        gh.comment(n, f"<!-- sig: {sig} -->\n⚠️ 内容が変わりました: {reason}\n- 実行: {run_url}\n\n{wb}")
    else:
        # 欠けている必須制度は同じで、保留だけが解除された
        gh.comment(n, f"<!-- sig: {sig} -->\nℹ️ 公開用データの更新の保留が解除されました(LINEは送りません)。{reason}\n- 実行: {run_url}")


# ---------- 入出力 ----------

def safe_detail(text):
    """ジョブ間で渡す短い理由。改行・制御文字・記号を落とす(出力の書式を壊さない。トークン等はもともと含まない)。"""
    return re.sub(r"[^\w ()()\-:./=、。・]", "", text or "")[:120]


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


def main(argv=None, gh=None, line=None, now=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    run_url = "{}/{}/actions/runs/{}".format(os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
                                            os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_RUN_ID", ""))
    a = sub.add_parser("incident")
    a.add_argument("--result", default="diagnosis_monitor_result.json")
    a.add_argument("--report", default="diagnosis_monitor_report.txt")
    w = sub.add_parser("watchdog")
    w.add_argument("--workflow", default="diagnosis-monitor.yml")
    s = sub.add_parser("sender", help="予約・送信・記録を続けて行う(手元の確認用)。--mode check は確認モード")
    s.add_argument("--mode", choices=["send", "check"], default="send")
    sr = sub.add_parser("sender-reserve", help="予約ジョブ(LINEのトークンを使わない)")
    sp_ = sub.add_parser("sender-push", help="送信ジョブ(送信記録を書き換えない)")
    sp_.add_argument("--rid", required=True)
    rc = sub.add_parser("sender-record", help="記録ジョブ(LINEのトークンを使わない)")
    rc.add_argument("--rid", required=True)
    rc.add_argument("--outcome", default="")
    rc.add_argument("--detail", default="")
    for sp in (a, w, s, sr, sp_, rc):
        sp.add_argument("--run-url", default=run_url)
        sp.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "0"))
    args = p.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    gh = gh or GitHub(repo)
    now = now or datetime.now(timezone.utc)
    if getattr(args, "rid", None) is not None and not RID_RE.match(args.rid):
        print("::error::要求IDの形式が想定外です(送らない)")
        return 1

    if args.cmd == "incident":
        target, rid = cmd_incident(gh, args, now)
        write_output(issue=target or "", request=rid or "", handled="true")
    elif args.cmd == "watchdog":
        problem, data_notice = cmd_watchdog(gh, repo, args, now)
        write_output(problem=problem, data=data_notice)
    elif args.cmd == "sender-reserve":
        # 予約ジョブには LINE のトークンを渡さない。Secrets が設定済みかどうかだけを真偽値で受け取る
        res = sender_reserve(gh, now, args.run_id, os.environ.get("LINE_CONFIGURED") == "true")
        write_output(rid=(res or {}).get("rid", ""))
    elif args.cmd == "sender-push":
        line = line or Line(os.environ.get("LINE_TOKEN"), os.environ.get("LINE_TO"))
        outcome, detail = sender_push(gh, line, repo, now, args.rid)
        print(f"送信の結果: {outcome} {detail}")
        write_output(outcome=outcome, detail=safe_detail(detail))
    elif args.cmd == "sender-record":
        sender_record(gh, now, args.rid, args.outcome, safe_detail(args.detail))
    else:
        line = line or Line(os.environ.get("LINE_TOKEN"), os.environ.get("LINE_TO"))
        if args.mode == "check":
            return cmd_check(gh, line, now)
        return cmd_sender(gh, line, repo, now, args.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
