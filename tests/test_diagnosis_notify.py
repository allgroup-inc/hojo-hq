"""scripts/diagnosis_notify.py の単体テスト。実行: python3 -m unittest tests/test_diagnosis_notify.py
GitHub は時刻を進められるメモリ上の偽物(ファイルの比較交換・古い版の読み出し・他の処理の割り込みを再現できる)、
LINE は再試行キーで重複を弾く偽物で試す。ネットワークは使わない。"""
import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import diagnosis_notify as dn  # noqa: E402

T0 = datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc)
Q_OK = ({"type": "limited", "value": 200}, {"totalUsage": 20})
SECRET = "dummy-secret-token-for-test"


class FakeGH:
    def __init__(self):
        self.now = T0
        self.items = []
        self.next_id = 1000
        self.fail = set()
        self.files = {}          # (branch, path) -> {"text", "sha"}
        self.history = {}        # (branch, path) -> 以前の版
        self.branches = {"main"}
        self.stale_reads = 0     # 次の get_file を古い版で返す回数(反映の遅れ)
        self.before_put = None   # put_file の直前に割り込む処理(他の送信担当など)
        self.wf = {"state": "active", "created_at": dn.iso(T0 - timedelta(days=10))}
        self.run_list, self.job_map = [], {}
        self.sha_seq = 0

    def tick(self, minutes=15):
        self.now += timedelta(minutes=minutes)

    def _chk(self, op):
        if op in self.fail:
            raise dn.GitHubError(op)

    def _issue(self, number):
        return next(i for i in self.items if i["number"] == number)

    def ensure_label(self, name):
        pass

    def issues(self, label, state="all"):
        self._chk("issues")
        sel = [i for i in self.items if label in i["labels"] and (state == "all" or i["state"] == state)]
        return sorted(sel, key=lambda i: (i["created_at"], i["number"]), reverse=True)

    def comments(self, number):
        self._chk("comments")
        return list(self._issue(number)["comments"])

    def create_issue(self, title, body, label):
        self._chk("create_issue")
        n = len(self.items) + 1
        self.items.append({"number": n, "title": title, "body": body, "labels": [label], "state": "open",
                           "created_at": dn.iso(self.now), "updated_at": dn.iso(self.now), "closed_at": None, "comments": []})
        return {"number": n}

    def comment(self, number, body):
        self._chk("comment")
        iss = self._issue(number)
        self.next_id += 1
        c = {"id": self.next_id, "created_at": dn.iso(self.now), "body": body}
        iss["comments"].append(c)
        iss["updated_at"] = dn.iso(self.now)
        return c

    def close(self, number):
        self._chk("close")
        iss = self._issue(number)
        iss["state"], iss["closed_at"], iss["updated_at"] = "closed", dn.iso(self.now), dn.iso(self.now)

    def workflow(self, file):
        return self.wf

    def runs(self, file, per_page=100):
        return self.run_list

    def jobs(self, run_id):
        return self.job_map[run_id]

    def get_file(self, path, ref):
        self._chk("get_file")
        key = (ref, path)
        if ref not in self.branches or key not in self.files:
            return None, None
        if self.stale_reads and self.history.get(key):
            self.stale_reads -= 1
            old = self.history[key][-1]
            return old["text"], old["sha"]
        return self.files[key]["text"], self.files[key]["sha"]

    def put_file(self, path, branch, text, sha, message):
        self._chk("put_file")
        if self.before_put:
            hook, self.before_put = self.before_put, None
            hook(self)
        if branch not in self.branches:
            raise dn.NotFound(branch)
        key = (branch, path)
        cur = self.files.get(key)
        if (cur is None and sha is not None) or (cur is not None and sha != cur["sha"]):
            raise dn.Conflict(path)
        self.sha_seq += 1
        new = {"text": text, "sha": f"sha{self.sha_seq}"}
        if cur:
            self.history.setdefault(key, []).append(cur)
        self.files[key] = new
        return new["sha"]

    def ensure_branch(self, branch):
        self._chk("ensure_branch")
        self.branches.add(branch)

    # 検査用
    def open_with(self, label):
        return [i for i in self.items if label in i["labels"] and i["state"] == "open"]

    def state(self):
        f = self.files.get((dn.STATE_BRANCH, dn.STATE_PATH))
        return json.loads(f["text"]) if f else None

    def all_text(self):
        return json.dumps(self.items, ensure_ascii=False) + json.dumps(list(self.files.values()), ensure_ascii=False)


class FakeLine:
    """再試行キーで受付済みなら二重に届けない(本物の LINE は 409 を返す)。"""

    def __init__(self, configured=True):
        self.configured = configured
        self.quota_resp = Q_OK
        self.quota_error = None
        self.accepted = set()
        self.delivered = []
        self.plan = []
        self.quota_calls = 0

    def quota(self):
        self.quota_calls += 1
        if self.quota_error:
            raise dn.LineError(self.quota_error)
        return self.quota_resp

    def push(self, text, key):
        mode = self.plan.pop(0) if self.plan else "ok"
        if key in self.accepted:
            return "delivered", "同じ再試行キーで受付済み(二重には届いていない)"
        if mode == "ok":
            self.accepted.add(key)
            self.delivered.append((key, text))
            return "delivered", ""
        if mode in ("5xx", "429"):
            return "retry", "HTTP 500" if mode == "5xx" else "HTTP 429"
        if mode == "400":
            return "rejected", "HTTP 400"
        if mode == "accept_then_timeout":  # LINE は受け付けたが、応答が届かなかった
            self.accepted.add(key)
            self.delivered.append((key, text))
            return "retry", "応答なし(TimeoutError)"
        if mode == "crash_after_accept":   # 送った直後に送信担当が落ちた
            self.accepted.add(key)
            self.delivered.append((key, text))
            raise RuntimeError("crash")
        raise AssertionError(mode)


class Base(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGH()
        self.line = FakeLine()
        self.tmp = tempfile.mkdtemp()
        self.result = os.path.join(self.tmp, "result.json")
        self.report = os.path.join(self.tmp, "report.txt")

    def run_check(self, ok=None, sig="", missing=False, corrupt=False):
        if missing:
            if os.path.exists(self.result):
                os.remove(self.result)
        elif corrupt:
            with open(self.result, "w") as f:
                f.write("{not json")
        else:
            errors = [] if ok else [{"code": sig.split(",")[0], "msg": f"テスト用の異常 {sig}"}]
            with open(self.result, "w") as f:
                json.dump({"ok": ok, "signature": "" if ok else sig, "errors": errors}, f)
            with open(self.report, "w") as f:
                f.write("ERROR テスト用の異常\n")
        args = argparse.Namespace(result=self.result, report=self.report, run_url="https://run/1", run_id="1")
        return dn.cmd_incident(self.gh, args, self.gh.now)

    def send(self, run_id="1", gh=None, line=None):
        gh = gh or self.gh
        return dn.cmd_sender(gh, line or self.line, "o/r", gh.now, run_id)

    def results_of(self, number):
        return [m.group(2) for c in self.gh._issue(number)["comments"] for m in dn.RESULT_RE.finditer(c["body"])]

    def page_alert(self, sig="PAGE_HTTP_500"):
        n, rid = self.run_check(ok=False, sig=sig)
        return n, rid

    def system_alert(self):
        """送信要求を1件持つ、独立したIssueを作る(同じIssueでは最新の要求だけが送られるため、件数の試験は別Issueにする)。"""
        rid, wb = dn.want_block(f"⚠️テスト通知 {len(self.gh.items) + 1}")
        n = self.gh.create_issue(f"テスト {len(self.gh.items) + 1}", "テスト\n\n" + wb, dn.SYSTEM)["number"]
        return n, rid


class Incident(Base):
    def test_first_same_change_escalate_recover_write_requests(self):
        n, rid = self.page_alert("SEIDO_HTTP_404")
        self.assertIsNotNone(rid)
        body = self.gh._issue(n)["body"]
        self.assertIn(f"<!-- line-want id:{rid} -->", body)
        self.assertIn("🚨【もらいわすれ堂】診断ページ異常", body)
        self.gh.tick()
        self.assertIsNone(self.run_check(ok=False, sig="SEIDO_HTTP_404")[1])
        self.gh.tick()
        self.assertIsNotNone(self.run_check(ok=False, sig="BROWSER_FLOW")[1])
        self.gh.tick(240)
        self.assertIsNotNone(self.run_check(ok=False, sig="BROWSER_FLOW")[1])
        self.gh.tick()
        self.assertIsNone(self.run_check(ok=False, sig="BROWSER_FLOW")[1])
        self.gh.tick()
        n2, rid = self.run_check(ok=True)
        self.assertEqual(n2, n)
        self.assertIn("約300分", self.gh._issue(n)["comments"][-1]["body"])
        self.assertEqual(self.gh.open_with(dn.PAGE), [])

    def test_setup_failure_is_system_not_page(self):
        p, _ = self.page_alert("SEIDO_STALE")
        before = list(self.gh._issue(p)["comments"])
        self.gh.tick()
        s, rid = self.run_check(missing=True)
        self.assertIn("監視が動いていません(ページの状態は不明)", self.gh._issue(s)["body"])
        self.assertNotIn("診断ページ異常", self.gh._issue(s)["body"])
        self.assertEqual(self.gh._issue(p)["comments"], before)  # 診断ページのIssueには触れない
        self.run_check(corrupt=True)
        self.assertEqual(len(self.gh.open_with(dn.SYSTEM)), 1)

    def test_system_recovery_is_announced_only_if_someone_was_told(self):
        s, _ = self.run_check(missing=True)
        self.gh.tick()
        self.run_check(ok=True)
        self.assertNotIn("line-want", self.gh._issue(s)["comments"][-1]["body"])
        s2, _ = self.run_check(missing=True)
        self.send()
        self.gh.tick()
        self.run_check(ok=True)
        self.assertIn("診断ページの監視が再開しました", self.gh._issue(s2)["comments"][-1]["body"])


class Sender(Base):
    def test_sends_once_records_result_and_url(self):
        n, rid = self.page_alert()
        self.send()
        self.assertEqual(len(self.line.delivered), 1)
        key, text = self.line.delivered[0]
        self.assertEqual(key, rid)
        self.assertTrue(text.endswith(f"/o/r/issues/{n}"))
        self.assertEqual(self.results_of(n), ["sent"])
        self.gh.tick()
        self.send()
        self.assertEqual(len(self.line.delivered), 1)  # 二度は送らない
        self.assertEqual(self.gh.state()["done"][rid]["state"], "sent")

    def test_cap_24h_then_released(self):
        issues = [self.system_alert()[0] for _ in range(4)]
        self.send()
        self.assertEqual(len(self.line.delivered), 3)
        unsent = [n for n in issues if not self.results_of(n)]
        self.assertEqual(len(unsent), 1)  # 1回の実行で送るのは最大3通
        for _ in range(2):
            self.gh.tick()
            self.send()
        self.assertEqual(self.results_of(unsent[0]), ["held"])  # 上限で保留。同じ理由は書き足さない
        self.assertEqual(len(self.line.delivered), 3)
        self.gh.tick(24 * 60)
        self.send()
        self.assertEqual(len(self.line.delivered), 4)  # 上限で遅れても失わない
        self.assertIn("時間前に検知", self.line.delivered[-1][1])

    def test_cap_30d(self):
        sent = 0
        for day in range(8):
            for _ in range(3):
                self.system_alert()
                self.gh.tick(5)
                self.send()
            self.gh.tick(24 * 60)
        sent = len(self.line.delivered)
        self.assertEqual(sent, 15)

    def test_two_senders_at_once_never_exceed_or_duplicate(self):
        # 既に2通送った状態(上限3)で、2件の送信待ちを2つの送信担当が同時に処理しようとする
        for _ in range(2):
            self.system_alert()
            self.send()
        a, _ = self.system_alert()
        b, _ = self.system_alert()

        def other_sender_runs_first(gh):
            dn.cmd_sender(gh, self.line, "o/r", gh.now, "B")
        self.gh.before_put = other_sender_runs_first
        self.send(run_id="A")  # A の予約の書き換えは、B が先に書いたため競合して送らない
        self.assertEqual(len(self.line.delivered), 3)
        self.assertEqual(len({k for k, _ in self.line.delivered}), 3)
        self.gh.tick()
        self.send()
        self.assertEqual(len(self.line.delivered), 3)  # 上限で保留

    def test_stale_read_does_not_send(self):
        self.system_alert()
        self.send()
        self.system_alert()
        self.gh.stale_reads = 1   # 反映の遅れで、最初の読み出しが古い版になる
        self.send()
        self.assertEqual(len(self.line.delivered), 1)  # 古い版のまま予約しようとして競合 → 送らない
        self.gh.tick()
        self.send()
        self.assertEqual(len(self.line.delivered), 2)

    def test_unverified_reservation_does_not_send_then_sends_once(self):
        self.system_alert()
        self.send()  # 送信記録ファイルを作る
        n, rid = self.system_alert()
        orig = self.gh.put_file

        def put_then_stale(*a, **k):
            sha = orig(*a, **k)
            self.gh.stale_reads = 1  # 書いた直後の読み直しで、まだ古い版が返る
            return sha
        self.gh.put_file = put_then_stale
        self.send()
        self.gh.put_file = orig
        self.assertEqual(len(self.line.delivered), 1)
        self.assertEqual(self.gh.state()["inflight"]["id"], rid)  # 予約は残る
        self.gh.tick()
        self.send()
        self.assertEqual([k for k, _ in self.line.delivered].count(rid), 1)

    def test_crash_after_send_is_not_duplicated(self):
        n, rid = self.system_alert()
        self.line.plan = ["crash_after_accept"]
        with self.assertRaises(RuntimeError):
            self.send()
        self.assertEqual(self.gh.state()["inflight"]["id"], rid)
        self.gh.tick()
        self.send()  # 同じ再試行キーで送り直す → LINE は受付済みとして返す
        self.assertEqual(len(self.line.delivered), 1)
        self.assertEqual(self.gh.state()["done"][rid]["state"], "sent")

    def test_5xx_and_429_retry_with_same_key(self):
        n, rid = self.system_alert()
        self.line.plan = ["5xx"]
        self.send()
        self.assertEqual(self.results_of(n), ["failed"])
        self.line.plan = ["429"]
        self.gh.tick()
        self.send()
        self.gh.tick()
        self.send()
        self.assertEqual(self.line.delivered, [(rid, self.line.delivered[0][1])])
        self.assertEqual(self.results_of(n), ["failed", "failed", "sent"])

    def test_timeout_after_accept_is_not_duplicated(self):
        n, rid = self.system_alert()
        self.line.plan = ["accept_then_timeout"]
        self.send()
        self.gh.tick()
        self.send()
        self.assertEqual(len(self.line.delivered), 1)
        self.assertEqual(self.gh.state()["done"][rid]["state"], "sent")

    def test_rejected_is_not_retried(self):
        n, rid = self.system_alert()
        self.line.plan = ["400"]
        self.send()
        self.gh.tick()
        self.send()
        self.assertEqual(self.line.delivered, [])
        self.assertEqual(self.results_of(n), ["rejected"])

    def test_retry_key_expiry_gives_up_without_duplicate(self):
        n, rid = self.system_alert()
        self.line.plan = ["5xx"]
        self.send()
        self.gh.tick(24 * 60)
        self.send()
        self.assertEqual(self.line.delivered, [])
        self.assertEqual(self.gh.state()["done"][rid]["state"], "unknown")
        self.assertIn("unknown", self.results_of(n))

    def test_newer_request_supersedes_and_old_requests_expire(self):
        n, old = self.page_alert("A")
        self.line.configured = False
        self.send()  # Secrets 未設定で保留
        self.gh.tick()
        _, new = self.run_check(ok=False, sig="B")
        self.line.configured = True
        self.send()
        self.assertEqual([k for k, _ in self.line.delivered], [new])
        self.assertEqual(self.gh.state()["done"][old]["state"], "superseded")
        s, never = self.system_alert()
        self.line.configured = False
        self.send()
        self.gh.tick(8 * 24 * 60)
        self.line.configured = True
        self.send()
        self.assertEqual(self.gh.state()["done"][never]["state"], "expired")

    def test_recovery_send_failure_is_resent(self):
        n, _ = self.page_alert()
        self.send()
        self.gh.tick()
        _, rec = self.run_check(ok=True)
        self.line.plan = ["5xx"]
        self.send()
        self.gh.tick()
        self.send()
        self.assertIn(rec, [k for k, _ in self.line.delivered])

    def test_quota_responses_fail_safe(self):
        bad = [
            ({"type": "limited", "value": 200}, {"totalUsage": True}),
            ({"type": "limited", "value": 200}, {"totalUsage": False}),
            ({"type": "limited", "value": 200}, {"totalUsage": -5}),
            ({"type": "limited", "value": 200}, {}),
            ({"type": "limited", "value": 200}, {"totalUsage": "10"}),
            ({"type": "limited", "value": 200.0}, {"totalUsage": 10}),
            ({"type": "limited", "value": True}, {"totalUsage": 0}),
            ({"type": "limited"}, {"totalUsage": 10}),
            ({"type": "NONE"}, {"totalUsage": 10}),
            ({"type": "none", "value": 100}, {"totalUsage": 10}),
            ({"type": "unlimited"}, {"totalUsage": 10}),
            ({"message": "Authentication failed"}, {"message": "x"}),
            (None, None),
            ({"type": "limited", "value": 200}, {"totalUsage": 150}),  # 残り50
        ]
        for q, c in bad:
            with self.subTest(q=q, c=c):
                self.assertFalse(dn.evaluate_quota(q, c, 50)[0])
        self.assertTrue(dn.evaluate_quota({"type": "limited", "value": 200}, {"totalUsage": 149}, 50)[0])
        self.assertTrue(dn.evaluate_quota({"type": "none"}, {"totalUsage": 9999}, 50)[0])
        n, _ = self.system_alert()
        self.line.quota_resp = ({"type": "limited", "value": 200}, {"totalUsage": False})
        self.send()
        self.line.quota_resp = Q_OK
        self.line.quota_error = "HTTP 500"
        self.gh.tick()
        self.send()
        self.assertEqual(self.line.delivered, [])
        self.assertEqual(self.results_of(n), ["held", "held"])

    def test_missing_secrets_holds_once(self):
        n, _ = self.system_alert()
        self.line.configured = False
        for _ in range(3):
            self.send()
            self.gh.tick()
        self.assertEqual(self.results_of(n), ["held"])
        self.assertEqual(self.line.quota_calls, 0)

    def test_github_failures_do_not_send(self):
        self.system_alert()
        for op in ("issues", "comments", "get_file", "put_file", "ensure_branch"):
            with self.subTest(op=op):
                self.gh.fail = {op}
                with self.assertRaises(dn.GitHubError):
                    self.send()
                self.assertEqual(self.line.delivered, [])
        self.gh.fail = set()
        self.send()
        self.gh.files[(dn.STATE_BRANCH, dn.STATE_PATH)]["text"] = "{broken"
        self.system_alert()
        with self.assertRaises(dn.GitHubError):
            self.send()
        self.assertEqual(len(self.line.delivered), 1)


class CheckMode(Base):
    def test_check_mode_reads_only(self):
        self.system_alert()
        before = json.dumps(self.gh.items, ensure_ascii=False)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dn.cmd_check(self.gh, self.line, self.gh.now)
        text = out.getvalue()
        self.assertIn("type=limited / 上限=200 / 今月の使用=20", text)
        self.assertIn("判定: 送れる(残り180通)", text)
        self.assertIn("送信待ち: 1件", text)
        self.assertEqual(self.line.delivered, [])
        self.assertIsNone(self.gh.state())                      # 送信記録を作らない
        self.assertEqual(json.dumps(self.gh.items, ensure_ascii=False), before)  # Issueにも書かない
        self.line.quota_resp = ({"type": "limited", "value": 200}, {"totalUsage": True})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dn.cmd_check(self.gh, self.line, self.gh.now)
        self.assertIn("判定: 送らない", out.getvalue())


class RealLineClient(unittest.TestCase):
    """本物の Line クラスの応答の読み方(urlopen を差し替える)。トークンを例外や結果に出さない。"""

    def resp(self, status, body=b"{}"):
        r = mock.MagicMock()
        r.__enter__.return_value = r
        r.status, r.read.return_value = status, body
        return r

    def test_push_status_mapping_and_retry_key_header(self):
        line = dn.Line(SECRET, "Uxxx")
        seen = {}

        def fake(req, timeout):
            seen["headers"] = dict(req.header_items())
            return self.resp(200)
        with mock.patch("urllib.request.urlopen", fake):
            self.assertEqual(line.push("t", "11111111-1111-1111-1111-111111111111")[0], "delivered")
        self.assertEqual(seen["headers"]["X-line-retry-key"], "11111111-1111-1111-1111-111111111111")
        for code, expect in ((409, "delivered"), (500, "retry"), (429, "retry"), (400, "rejected"), (401, "rejected")):
            err = urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b""))
            with mock.patch("urllib.request.urlopen", side_effect=err):
                self.assertEqual(line.push("t", "k")[0], expect, code)
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError(SECRET)):
            outcome, detail = line.push("t", "k")
        self.assertEqual(outcome, "retry")
        self.assertNotIn(SECRET, detail)

    def test_quota_errors_hide_token(self):
        line = dn.Line(SECRET, "Uxxx")
        for side in (urllib.error.URLError(SECRET), urllib.error.HTTPError("u", 401, SECRET, {}, io.BytesIO(b""))):
            with mock.patch("urllib.request.urlopen", side_effect=side):
                with self.assertRaises(dn.LineError) as cm:
                    line.quota()
            self.assertNotIn(SECRET, str(cm.exception))
        with mock.patch("urllib.request.urlopen", return_value=self.resp(200, b"not json")):
            with self.assertRaises(dn.LineError):
                line.quota()


class Watchdog(Base):
    def wd(self):
        return dn.cmd_watchdog(self.gh, "o/r", argparse.Namespace(workflow="diagnosis-monitor.yml", run_url="https://run/9"), self.gh.now)

    def runs(self, specs):
        self.gh.run_list, self.gh.job_map = [], {}
        for i, (ago, check, inc) in enumerate(specs):
            self.gh.run_list.append({"id": i, "created_at": dn.iso(self.gh.now - timedelta(minutes=ago)), "status": "completed"})
            self.gh.job_map[i] = [{"name": "monitor", "steps": [{"name": dn.CHECK_STEP, "conclusion": check},
                                                                {"name": dn.INCIDENT_STEP, "conclusion": inc}]}]

    def healthy(self):
        self.runs([(5, "success", "success"), (20, "success", "success"), (35, "success", "success"), (50, "success", "success")])

    def test_stop_conditions(self):
        self.healthy()
        self.assertEqual(self.wd()[0], "")
        self.gh.wf["state"] = "disabled_inactivity"
        self.assertEqual(self.wd()[0], "WORKFLOW_DISABLED")
        self.gh.wf["state"] = "active"
        self.runs([(400, "success", "success")])
        self.assertEqual(self.wd()[0], "STALLED")
        self.runs([(5, "skipped", "success"), (20, "skipped", "success"), (35, None, None), (50, "skipped", "success")])
        self.assertEqual(self.wd()[0], "PREP_FAILING")
        self.runs([(5, "failure", "failure"), (20, "success", "failure"), (35, "success", "failure"), (50, "failure", "failure")])
        self.assertEqual(self.wd()[0], "ISSUE_UPDATE_FAILING")
        self.assertEqual(self.gh.open_with(dn.PAGE), [])

    def test_sender_stall_detected_but_holds_are_not(self):
        self.healthy()
        n, _ = self.system_alert()
        self.gh.tick(7 * 60)
        self.healthy()
        self.assertEqual(self.wd()[0], "LINE_SENDER_STALLED")
        g = FakeGH()
        self.gh = g
        self.line.configured = False
        n, _ = self.system_alert()
        self.send()   # 保留(Secrets未設定)として記録 → 停滞ではない
        self.gh.tick(7 * 60)
        self.healthy()
        self.assertEqual(self.wd()[0], "")

    def test_publish_status_opens_and_closes_data_issue_without_failing_job(self):
        self.healthy()
        status = {"checked_at": "2026-11-04 06:00", "publish": True, "reasons": [], "required_missing": ["fk-kuni-jidofuyoteate"]}
        self.gh.files[("main", dn.PUBLISH_STATUS_PATH)] = {"text": json.dumps(status), "sha": "m1"}
        problem, data = self.wd()
        self.assertEqual((problem, data), ("", "REQUIRED_MISSING"))
        d = self.gh.open_with(dn.DATA)[0]
        self.assertIn("fk-kuni-jidofuyoteate", d["body"])
        self.assertIn("line-want", d["body"])
        self.wd()
        self.assertEqual(len(d["comments"]), 0)  # 同じ内容なら書き足さない
        status.update(publish=False, reasons=["前回の公開データに載っている制度の取得に失敗しました(18件)"])
        self.gh.files[("main", dn.PUBLISH_STATUS_PATH)]["text"] = json.dumps(status)
        self.assertEqual(self.wd()[1], "DATA_HOLD")
        self.assertIn("line-want", d["comments"][-1]["body"])
        status.update(publish=True, reasons=[], required_missing=[])
        self.gh.files[("main", dn.PUBLISH_STATUS_PATH)]["text"] = json.dumps(status)
        self.assertEqual(self.wd(), ("", ""))
        self.assertEqual(self.gh.open_with(dn.DATA), [])

    def test_system_issue_closes_only_after_latest_run_checked(self):
        s, _ = self.run_check(missing=True)
        self.runs([(5, "skipped", "success"), (20, "success", "success"), (35, "success", "success"), (50, "success", "success")])
        self.wd()
        self.assertEqual(self.gh._issue(s)["state"], "open")
        self.healthy()
        self.wd()
        self.assertEqual(self.gh._issue(s)["state"], "closed")


class Secrets(Base):
    def test_token_never_written_anywhere(self):
        line = dn.Line(SECRET, "Uxxx")
        self.system_alert()
        out = io.StringIO()
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError(SECRET)), contextlib.redirect_stdout(out):
            dn.cmd_sender(self.gh, line, "o/r", self.gh.now, "1")
            dn.cmd_check(self.gh, line, self.gh.now)
        self.assertNotIn(SECRET, out.getvalue())
        self.assertNotIn(SECRET, self.gh.all_text())


if __name__ == "__main__":
    unittest.main()
