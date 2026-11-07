"""もらいわすれ堂のLINE友だち数の記録(読み取り専用)と、遥さんへの通知の承認制を確かめる。

外部への通信はしない(urlopen はすべて差し替える)。トークン・宛先IDは合成の値を使う。
実行: python -m unittest tests/test_moradou_line.py
"""
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import notify_haruka  # noqa: E402
import record_moradou_line as rec  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 9, 9, 5, tzinfo=JST)
FAKE_TOKEN = "TEST-TOKEN-should-never-appear-0123456789"
FAKE_USER = "U-test-user-id-should-never-appear"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_returning(body, calls):
    def _open(req, timeout=None):
        calls.append(req)
        return FakeResponse(json.dumps(body).encode("utf-8"))
    return _open


def opener_must_not_be_called(req, timeout=None):
    raise AssertionError("通信してはいけない場面で通信した")


class Record(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "moradou_line_followers.json")

    def tearDown(self):
        self.tmp.cleanup()

    def run_record(self, env, opener):
        out = io.StringIO()
        with redirect_stdout(out):
            data = rec.record(env=env, now=NOW, path=self.path, opener=opener)
        with open(self.path, encoding="utf-8") as f:
            saved = f.read()
        return data, out.getvalue(), saved

    def test_no_token_records_unconnected_without_network(self):
        data, out, saved = self.run_record({}, opener_must_not_be_called)
        self.assertEqual(data["last_status"], "未接続(トークン未登録)")
        self.assertEqual(data["history"], [])
        self.assertEqual(data["last_checked"], "2026-11-09 09:05")
        self.assertIn("記録しません", out)

    def test_ready_records_followers_with_read_only_get(self):
        calls = []
        body = {"status": "ready", "followers": 42, "targetedReaches": 40, "blocks": 1}
        data, out, saved = self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, opener_returning(body, calls))
        self.assertEqual(len(calls), 1)
        req = calls[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertIn("/v2/bot/insight/followers?date=20261108", req.full_url)
        self.assertNotIn("/message/", req.full_url)  # 送信用の API は呼ばない
        self.assertIsNone(req.data)                   # 送る本文が無い
        self.assertEqual(data["last_status"], "ready")
        self.assertEqual(data["history"][-1], {"date": "2026-11-08", "followers": 42,
                                                "targeted_reaches": 40, "blocks": 1})
        self.assertEqual(data["last_success_at"], "2026-11-09 09:05")
        for text in (out, saved):
            self.assertNotIn(FAKE_TOKEN, text)

    def test_same_day_is_replaced_not_duplicated(self):
        calls = []
        self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, opener_returning({"status": "ready", "followers": 1}, calls))
        data, _, _ = self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, opener_returning({"status": "ready", "followers": 2}, calls))
        self.assertEqual([h["followers"] for h in data["history"]], [2])

    def test_http_error_keeps_status_code_and_hides_token(self):
        def _open(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        data, out, saved = self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, _open)
        self.assertEqual(data["last_status"], "取得不可(HTTP 401)")
        for text in (out, saved):
            self.assertNotIn(FAKE_TOKEN, text)

    def test_not_ready_and_network_error(self):
        data, _, _ = self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, opener_returning({"status": "unready"}, []))
        self.assertEqual(data["last_status"], "集計待ち(status=unready)")

        def _boom(req, timeout=None):
            raise TimeoutError()
        data, _, _ = self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, _boom)
        self.assertEqual(data["last_status"], "取得不可(TimeoutError)")

    def test_summary_for_report(self):
        self.assertIn("未接続", rec.summary(self.path))  # 記録なし
        self.run_record({}, opener_must_not_be_called)
        self.assertEqual(rec.summary(self.path), "未取得: 未接続(トークン未登録)(確認 2026-11-09 09:05)")
        self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, opener_returning({"status": "ready", "followers": 42}, []))
        self.assertEqual(rec.summary(self.path), "**42人**(2026-11-08時点・取得 2026-11-09 09:05)")

        def _open(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        self.run_record({rec.TOKEN_ENV: FAKE_TOKEN}, _open)
        s = rec.summary(self.path)
        self.assertIn("**42人**", s)                       # 最後に取れた数は残す
        self.assertIn("⚠ 最新の取得: 取得不可(HTTP 403)", s)  # 失敗の状態も出す

    def test_weekly_report_uses_moradou_file_not_mikata(self):
        import weekly_report_fukugiiro as wr
        kpi = os.path.join(self.tmp.name, "kpi")
        os.makedirs(kpi)
        rec.save({"history": [{"date": "2026-11-08", "followers": 7}], "last_status": "ready",
                  "last_success_at": "2026-11-09 09:05", "last_checked": "2026-11-09 09:05"},
                 os.path.join(kpi, "moradou_line_followers.json"))
        # ミカタの記録に別の数を置き、混ざらないことを確かめる
        rec.save({"history": [{"date": "2026-11-08", "followers": 999}]}, os.path.join(kpi, "line_followers.json"))
        with mock.patch.object(wr, "KPI_DIR", kpi):
            out = wr.north_star_section({})
        self.assertIn("**7人**(2026-11-08時点", out)
        self.assertNotIn("999", out)


class NotifyHaruka(unittest.TestCase):
    ENV = {"FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN": FAKE_TOKEN, "HARUKA_LINE_USER_ID": FAKE_USER}

    def run_main(self, env):
        sent = []
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("urllib.request.urlopen", opener_must_not_be_called):
            rc = notify_haruka.main(env=env, sender=lambda t, to, text: sent.append((t, to, text)))
        return rc, sent, out.getvalue()

    def test_secrets_set_but_no_approval_does_not_send(self):
        rc, sent, out = self.run_main(dict(self.ENV))
        self.assertEqual(rc, 0)
        self.assertEqual(sent, [])
        self.assertIn("承認なしのため送信しません", out)
        self.assertIn("承認コード:", out)
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertNotIn(FAKE_USER, out)

    def test_wrong_or_stale_approval_does_not_send(self):
        rc, sent, out = self.run_main(dict(self.ENV, NOTIFY_HARUKA_APPROVAL="0000000000000000"))
        self.assertEqual(sent, [])
        self.assertIn("一致しない", out)

    def test_code_changes_when_content_or_recipient_changes(self):
        a = notify_haruka.approval_code("本文A")
        self.assertNotEqual(a, notify_haruka.approval_code("本文B"))
        self.assertNotEqual(a, notify_haruka.approval_code("本文A", recipient="someone-else"))

    def test_matching_approval_sends_once_to_haruka(self):
        code = notify_haruka.approval_code(notify_haruka.build_text())
        rc, sent, out = self.run_main(dict(self.ENV, NOTIFY_HARUKA_APPROVAL=code))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1], FAKE_USER)
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertNotIn(FAKE_USER, out)

    def test_approval_without_secrets_does_not_send(self):
        code = notify_haruka.approval_code(notify_haruka.build_text())
        rc, sent, out = self.run_main({"NOTIFY_HARUKA_APPROVAL": code})
        self.assertEqual(sent, [])


class Workflow(unittest.TestCase):
    """定期実行の設定から誤送信の経路が無いことを、設定ファイルで確かめる。"""

    @classmethod
    def setUpClass(cls):
        import yaml
        with open(os.path.join(ROOT, ".github", "workflows", "fukugiiro-weekly-report.yml"), encoding="utf-8") as f:
            cls.wf = yaml.safe_load(f)
        cls.steps = cls.wf["jobs"]["report"]["steps"]

    def step(self, needle):
        return next(s for s in self.steps if needle in (s.get("run") or ""))

    def test_notify_step_gets_no_secrets_and_no_approval(self):
        s = self.step("notify_haruka.py")
        env = s.get("env") or {}
        for key in ("FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN", "HARUKA_LINE_USER_ID", "NOTIFY_HARUKA_APPROVAL"):
            self.assertNotIn(key, env)

    def test_no_step_hands_haruka_id_or_approval(self):
        for s in self.steps:
            env = s.get("env") or {}
            self.assertNotIn("HARUKA_LINE_USER_ID", env, s.get("name"))
            self.assertNotIn("NOTIFY_HARUKA_APPROVAL", env, s.get("name"))

    def test_token_goes_only_to_read_only_recorder(self):
        holders = [s for s in self.steps if "FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN" in (s.get("env") or {})]
        self.assertEqual([s["run"].strip() for s in holders], ["python scripts/record_moradou_line.py"])
        names = [s.get("run", "") for s in self.steps]
        rec_i = next(i for i, r in enumerate(names) if "record_moradou_line.py" in r)
        rep_i = next(i for i, r in enumerate(names) if "weekly_report_fukugiiro.py" in r)
        self.assertLess(rec_i, rep_i)  # 記録してからレポートを作る

    def test_record_file_is_committed(self):
        commit = self.step("git commit")["run"]
        self.assertIn("data/kpi/moradou_line_followers.json", commit)

    def test_board_is_not_regenerated_on_push(self):
        s = self.step("generate_ig_neta.py")
        self.assertEqual(s.get("if"), "github.event_name != 'push'")

    def test_recorder_never_calls_send_api(self):
        with open(os.path.join(ROOT, "scripts", "record_moradou_line.py"), encoding="utf-8") as f:
            src = f.read()
        urls = re.findall(r"https://api\.line\.me/[^\"' ]+", src)
        self.assertEqual(urls, ["https://api.line.me/v2/bot/insight/followers?date={date}"])
        self.assertNotIn("/message/", src)


if __name__ == "__main__":
    unittest.main()
