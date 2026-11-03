"""scripts/diagnosis_notify.py の単体テスト。実行: python3 -m unittest tests/test_diagnosis_notify.py
GitHub は時刻を進められるメモリ上の偽物、LINEの送信枠は差し替えた応答で試す(ネットワークを使わない)。"""
import argparse
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import diagnosis_notify as dn  # noqa: E402

T0 = datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc)
QUOTA_OK = ({"type": "limited", "value": 200}, {"totalUsage": 20})


class FakeGH:
    def __init__(self):
        self.now = T0
        self.items = []
        self.next_id = 1000
        self.fail = set()
        self.before_ledger_comment = None
        self.wf = {"state": "active", "created_at": dn.iso(T0 - timedelta(days=10))}
        self.run_list = []
        self.job_map = {}

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

    def comments(self, number, since=None):
        self._chk("comments")
        cs = self._issue(number)["comments"]
        return [c for c in cs if since is None or dn.parse_ts(c["created_at"]) >= since]

    def create_issue(self, title, body, label):
        self._chk("create_issue")
        n = len(self.items) + 1
        self.items.append({"number": n, "title": title, "body": body, "labels": [label], "state": "open",
                           "created_at": dn.iso(self.now), "closed_at": None, "comments": []})
        return {"number": n}

    def comment(self, number, body):
        self._chk("comment")
        iss = self._issue(number)
        if dn.LEDGER in iss["labels"] and self.before_ledger_comment:
            hook, self.before_ledger_comment = self.before_ledger_comment, None
            hook(self, number)
        self.next_id += 1
        c = {"id": self.next_id, "created_at": dn.iso(self.now), "body": body}
        iss["comments"].append(c)
        return c

    def close(self, number):
        self._chk("close")
        iss = self._issue(number)
        iss["state"], iss["closed_at"] = "closed", dn.iso(self.now)

    def delete_comment(self, comment_id):
        self._chk("delete_comment")
        for i in self.items:
            i["comments"] = [c for c in i["comments"] if c["id"] != comment_id]

    def workflow(self, file):
        return self.wf

    def runs(self, file, per_page=100):
        return self.run_list

    def jobs(self, run_id):
        return self.job_map[run_id]

    # 検査用
    def open_with(self, label):
        return [i for i in self.items if label in i["labels"] and i["state"] == "open"]

    def ledger_count(self):
        return sum(1 for i in self.items if dn.LEDGER in i["labels"] for c in i["comments"] if "line-ledger" in c["body"])


class Base(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGH()
        self.tmp = tempfile.mkdtemp()
        self.result = os.path.join(self.tmp, "result.json")
        self.report = os.path.join(self.tmp, "report.txt")
        for k in ("LINE_TOKEN", "LINE_TO_SET"):
            os.environ.pop(k, None)
        os.environ["LINE_TOKEN"] = "dummy-token-for-test"
        os.environ["LINE_TO_SET"] = "true"

    def run_check(self, ok=None, sig="", missing=False, corrupt=False):
        if missing:
            if os.path.exists(self.result):
                os.remove(self.result)
        elif corrupt:
            open(self.result, "w").write("{not json")
        else:
            import json
            errors = [] if ok else [{"code": sig.split(",")[0], "msg": f"テスト用の異常 {sig}"}]
            json.dump({"ok": ok, "signature": "" if ok else sig, "errors": errors}, open(self.result, "w"))
            open(self.report, "w").write("ERROR テスト用の異常\n")
        args = argparse.Namespace(result=self.result, report=self.report, run_url="https://run/1", run_id="1")
        return dn.cmd_incident(self.gh, "o/r", args, self.gh.now)

    def gate(self, issue, quota=QUOTA_OK, run_id="1"):
        def fetch(token):
            if isinstance(quota, Exception):
                raise quota
            return quota
        args = argparse.Namespace(issue=issue, run_url="https://run/1", run_id=run_id)
        return dn.cmd_gate(self.gh, "o/r", args, self.gh.now, quota_fetcher=fetch)

    def record(self, issue, outcome):
        dn.cmd_record(self.gh, "o/r", argparse.Namespace(issue=issue, outcome=outcome, run_url="https://run/1"), self.gh.now)

    def comments_of(self, number):
        return [c["body"] for c in self.gh._issue(number)["comments"]]


class PageIncident(Base):
    def test_first_same_change_escalate_recover(self):
        n, msg = self.run_check(ok=False, sig="SEIDO_HTTP_404")
        self.assertTrue(msg.startswith("🚨【もらいわすれ堂】診断ページ異常"))
        self.assertEqual(self.gh.open_with(dn.SYSTEM), [])
        self.gh.tick()
        self.assertEqual(self.run_check(ok=False, sig="SEIDO_HTTP_404")[1], "")
        self.gh.tick()
        self.assertIn("症状が変わりました", self.run_check(ok=False, sig="BROWSER_FLOW")[1])
        self.gh.tick(240)
        self.assertIn("4時間以上", self.run_check(ok=False, sig="BROWSER_FLOW")[1])
        self.gh.tick()
        self.assertEqual(self.run_check(ok=False, sig="BROWSER_FLOW")[1], "")
        self.gh.tick()
        n2, msg = self.run_check(ok=True)
        self.assertEqual(n2, n)
        self.assertIn("復旧しました", msg)
        self.assertIn("約300分", msg)  # 15+15+240+15+15分
        self.assertEqual(self.gh.open_with(dn.PAGE), [])
        self.gh.tick()
        self.assertEqual(self.run_check(ok=True)[1], "")

    def test_failed_send_is_resent_once(self):
        n, _ = self.run_check(ok=False, sig="PAGE_HTTP_500")
        self.record(n, "failure")
        self.gh.tick()
        _, msg = self.run_check(ok=False, sig="PAGE_HTTP_500")
        self.assertIn("(再送)", msg)
        self.record(n, "success")
        self.gh.tick()
        self.assertEqual(self.run_check(ok=False, sig="PAGE_HTTP_500")[1], "")

    def test_recovery_send_failure_is_resent_within_24h(self):
        n, _ = self.run_check(ok=False, sig="PAGE_HTTP_500")
        self.record(n, "success")
        self.gh.tick()
        _, msg = self.run_check(ok=True)
        self.assertIn("復旧しました", msg)
        self.record(n, "failure")
        self.gh.tick()
        target, msg = self.run_check(ok=True)
        self.assertEqual(target, n)
        self.assertIn("(再送)診断ページは復旧しています", msg)
        self.record(n, "success")
        self.gh.tick()
        self.assertEqual(self.run_check(ok=True)[1], "")

    def test_recovery_resend_expires_after_24h(self):
        n, _ = self.run_check(ok=False, sig="PAGE_HTTP_500")
        self.gh.tick()
        self.run_check(ok=True)
        self.record(n, "failure")
        self.gh.tick(25 * 60)
        self.assertEqual(self.run_check(ok=True)[1], "")


class SystemIncident(Base):
    def test_setup_failure_is_not_a_page_incident(self):
        n, msg = self.run_check(missing=True)
        self.assertIn("監視が動いていません(ページの状態は不明)", msg)
        self.assertNotIn("診断ページ異常", msg)
        self.assertEqual(self.gh.open_with(dn.PAGE), [])
        self.assertEqual([i["number"] for i in self.gh.open_with(dn.SYSTEM)], [n])
        self.gh.tick()
        self.assertEqual(self.run_check(missing=True)[1], "")

    def test_corrupt_result_is_system(self):
        self.run_check(corrupt=True)
        self.assertEqual(len(self.gh.open_with(dn.SYSTEM)), 1)

    def test_open_page_incident_is_left_alone_while_monitor_is_broken(self):
        p, _ = self.run_check(ok=False, sig="SEIDO_STALE")
        before = list(self.comments_of(p))
        self.gh.tick()
        self.run_check(missing=True)
        self.assertEqual(self.comments_of(p), before)
        self.assertEqual(self.gh._issue(p)["state"], "open")

    def test_system_closes_when_check_runs_again_and_notifies_only_if_told(self):
        s, _ = self.run_check(missing=True)
        self.gh.tick()
        target, msg = self.run_check(ok=True)
        self.assertEqual(self.gh._issue(s)["state"], "closed")
        self.assertEqual(msg, "")  # 誰にも知らせていなければ再開も知らせない
        s2, _ = self.run_check(missing=True)
        self.record(s2, "success")
        self.gh.tick()
        target, msg = self.run_check(ok=True)
        self.assertEqual(target, s2)
        self.assertIn("監視が再開しました", msg)


class Gate(Base):
    def new_page(self):
        return self.run_check(ok=False, sig="PAGE_HTTP_500")[0]

    def test_missing_secrets(self):
        n = self.new_page()
        os.environ["LINE_TO_SET"] = "false"
        self.assertFalse(self.gate(n))
        self.assertIn("Secretsが未設定", self.comments_of(n)[-1])
        self.assertEqual(self.gh.ledger_count(), 0)

    def test_quota_errors_and_shapes_fail_safe(self):
        n = self.new_page()
        cases = [
            (OSError("timeout"), False),
            (({"type": "limited", "value": 200}, {"totalUsage": 150}), False),  # 残り50
            (({"type": "limited", "value": 200}, {"totalUsage": 149}), True),   # 残り51
            (({"type": "unknown"}, {"totalUsage": 1}), False),
            (({"type": "limited"}, {"totalUsage": 1}), False),
            (({"type": "limited", "value": 200}, {}), False),
            ((None, None), False),
            (({"type": "none"}, {"totalUsage": 999}), True),
        ]
        for quota, expect in cases:
            with self.subTest(quota=quota):
                self.gh.tick(24 * 60)  # 通数上限に当たらないよう日を進める
                self.assertEqual(self.gate(n, quota=quota), expect)

    def test_token_never_written_to_issue(self):
        n = self.new_page()
        self.gate(n, quota=OSError("boom dummy-token-for-test"))
        self.assertTrue(all("dummy-token-for-test" not in b for b in self.comments_of(n)))

    def test_cap_24h_and_30d(self):
        n = self.new_page()
        allowed = []
        for _ in range(4):
            allowed.append(self.gate(n))
            self.gh.tick(60)
        self.assertEqual(allowed, [True, True, True, False])
        self.gh.tick(24 * 60)
        self.assertTrue(self.gate(n))
        # 30日枠: 1日3通ずつ送れても、30日で15通を超えない
        self.gh = FakeGH()
        n = self.new_page()
        sent = 0
        for _ in range(10):
            for _ in range(3):
                sent += self.gate(n)
                self.gh.tick(60)
            self.gh.tick(24 * 60)
        self.assertEqual(sent, 15)
        self.assertEqual(self.gh.ledger_count(), 15)

    def test_held_reason_is_recorded_once(self):
        n = self.new_page()
        os.environ["LINE_TO_SET"] = "false"
        for _ in range(5):
            self.gate(n)
            self.gh.tick()
        held = [b for b in self.comments_of(n) if "line: held" in b]
        self.assertEqual(len(held), 1)

    def test_parallel_send_cannot_exceed_cap(self):
        n = self.new_page()
        self.assertTrue(self.gate(n, run_id="a"))
        self.assertTrue(self.gate(n, run_id="b"))

        # 自分が事前の数え上げを通った直後、別の実行が先に記録した
        def other_run_reserves_first(gh, ledger_no):
            gh.next_id += 1
            gh._issue(ledger_no)["comments"].append({"id": gh.next_id, "created_at": dn.iso(gh.now), "body": "<!-- line-ledger run:x -->"})
        self.gh.before_ledger_comment = other_run_reserves_first
        self.assertFalse(self.gate(n, run_id="c"))
        self.assertEqual(self.gh.ledger_count(), 3)  # 取りやめた側の記録は消える
        self.assertIn("同時に送ろうとした", self.comments_of(n)[-1])

    def test_later_parallel_reservation_loses(self):
        n = self.new_page()
        self.gate(n, run_id="a")
        self.gate(n, run_id="b")
        own = {}

        def other_run_reserves_after(gh, ledger_no):
            own["ledger"] = ledger_no
        self.gh.before_ledger_comment = other_run_reserves_after
        self.assertTrue(self.gate(n, run_id="c"))
        # 後から来た実行は、事前の数え上げの時点で上限に当たる
        self.assertFalse(self.gate(n, run_id="d"))
        self.assertEqual(self.gh.ledger_count(), 3)

    def test_github_failure_fails_safe(self):
        # 台帳がまだ無い: 予約を書いた後の数え直しで失敗 → 送らず、予約も取り下げる
        n = self.new_page()
        self.gh.fail = {"comments"}
        self.assertFalse(self.gate(n))
        self.assertEqual(self.gh.ledger_count(), 0)
        # 台帳がある: 最初の数え上げで失敗 → 予約を書かずに送らない
        self.gh.fail = set()
        self.assertTrue(self.gate(n))
        self.gh.fail = {"comments"}
        self.assertFalse(self.gate(n))
        self.assertEqual(self.gh.ledger_count(), 1)
        # 台帳の一覧そのものが取れない
        self.gh.fail = {"issues"}
        self.assertFalse(self.gate(n))
        self.assertEqual(self.gh.ledger_count(), 1)

    def test_void_delete_failure_still_blocks(self):
        n = self.new_page()
        self.gate(n, run_id="a")
        self.gate(n, run_id="b")

        def other(gh, ledger_no):
            gh.next_id += 1
            gh._issue(ledger_no)["comments"].append({"id": gh.next_id, "created_at": dn.iso(gh.now), "body": "<!-- line-ledger run:x -->"})
            gh.fail = {"delete_comment"}
        self.gh.before_ledger_comment = other
        self.assertFalse(self.gate(n, run_id="c"))
        self.assertEqual(self.gh.ledger_count(), 4)  # 消せなかった分は多めに数える(安全側)


class Watchdog(Base):
    def wd(self):
        return dn.cmd_watchdog(self.gh, "o/r", argparse.Namespace(workflow="diagnosis-monitor.yml", run_url="https://run/9"), self.gh.now)

    def runs(self, specs):
        """specs: [(何分前, 検査ステップの結論, Issue更新ステップの結論)] 新しい順"""
        self.gh.run_list, self.gh.job_map = [], {}
        for i, (ago, check, inc) in enumerate(specs):
            self.gh.run_list.append({"id": i, "created_at": dn.iso(self.gh.now - timedelta(minutes=ago)), "status": "completed"})
            self.gh.job_map[i] = [{"name": "monitor", "steps": [{"name": dn.CHECK_STEP, "conclusion": check},
                                                                {"name": dn.INCIDENT_STEP, "conclusion": inc}]}]

    def test_healthy_with_gaps_under_6h(self):
        self.runs([(10, "success", "success"), (130, "success", "success"), (300, "failure", "success"), (400, "success", "success")])
        self.assertEqual(self.wd()[2], "")

    def test_disabled_stalled_never(self):
        self.runs([(10, "success", "success")])
        self.gh.wf["state"] = "disabled_inactivity"
        self.assertEqual(self.wd()[2], "WORKFLOW_DISABLED")
        self.gh.wf["state"] = "active"
        self.runs([(400, "success", "success")])
        self.assertEqual(self.wd()[2], "STALLED")
        self.runs([])
        self.gh.wf["created_at"] = dn.iso(self.gh.now - timedelta(minutes=30))
        self.assertEqual(self.wd()[2], "")
        self.gh.wf["created_at"] = dn.iso(self.gh.now - timedelta(hours=7))
        self.assertEqual(self.wd()[2], "NEVER_SCHEDULED")

    def test_prep_failure_detected(self):
        self.runs([(5, "skipped", "success"), (20, "skipped", "success"), (35, None, None), (50, "skipped", "success")])
        target, msg, problem = self.wd()
        self.assertEqual(problem, "PREP_FAILING")
        self.assertIn("監視が動いていません", msg)
        self.assertEqual(self.gh.open_with(dn.PAGE), [])

    def test_issue_update_failure_detected(self):
        self.runs([(5, "failure", "failure"), (20, "success", "failure"), (35, "success", "failure"), (50, "failure", "failure")])
        self.assertEqual(self.wd()[2], "ISSUE_UPDATE_FAILING")

    def test_does_not_close_system_issue_until_latest_run_checked(self):
        s, _ = self.run_check(missing=True)
        self.runs([(5, "skipped", "success"), (20, "success", "success"), (35, "success", "success"), (50, "success", "success")])
        self.wd()
        self.assertEqual(self.gh._issue(s)["state"], "open")
        self.runs([(5, "success", "success"), (20, "skipped", "success"), (35, "success", "success"), (50, "success", "success")])
        self.wd()
        self.assertEqual(self.gh._issue(s)["state"], "closed")


class Outputs(unittest.TestCase):
    def test_multiline_output_format(self):
        path = tempfile.mktemp()
        os.environ["GITHUB_OUTPUT"] = path
        try:
            dn.write_output(issue=3, message="一行目\n二行目", handled="true")
            text = open(path, encoding="utf-8").read()
        finally:
            del os.environ["GITHUB_OUTPUT"]
        self.assertIn("issue=3\n", text)
        self.assertIn("message<<__EOF__\n一行目\n二行目\n__EOF__\n", text)
        self.assertIn("handled=true\n", text)


if __name__ == "__main__":
    unittest.main()
