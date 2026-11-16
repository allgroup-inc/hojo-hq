"""scripts/diagnosis_heartbeat.py(外部監視A案のハートビート)のテスト。実行: python3 -m unittest tests/test_diagnosis_heartbeat.py
外部サービスへは接続しない(urlopen を差し替える)。ハートビートのURLは鍵なので、どの出力にも出ないことを確かめる。"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import diagnosis_heartbeat as hb  # noqa: E402

URL = "https://hc-ping.com/0f1e2d3c-secret-uuid-for-test"


class Res:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.result = os.path.join(self.tmp, "result.json")
        self.calls = []

    def write(self, obj):
        with open(self.result, "w", encoding="utf-8") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))

    def run_main(self, env, effects=None):
        effects = list(effects or [Res()])

        def fake(req, timeout=None):
            self.calls.append((req.full_url, req.data.decode("utf-8")))
            e = effects.pop(0) if effects else Res()
            if isinstance(e, Exception):
                raise e
            return e
        out = io.StringIO()
        with mock.patch("urllib.request.urlopen", side_effect=fake), contextlib.redirect_stdout(out):
            rc = hb.main(env, self.result)
        self.assertEqual(rc, 0)  # どの場合も監視ジョブは赤にしない
        self.assertNotIn("secret-uuid", out.getvalue())
        return out.getvalue()


class Decide(Base):
    def test_signals(self):
        self.assertEqual(hb.decide(self.result, "true")[0], "fail")             # 検査まで届かない(結果なし)
        self.write("{broken")
        self.assertEqual(hb.decide(self.result, "true")[0], "fail")
        self.write({"ok": True, "signature": "", "errors": []})
        self.assertEqual(hb.decide(self.result, "true"), ("success", "checked: 診断ページは正常"))
        self.assertEqual(hb.decide(self.result, "")[0], "fail")                 # 障害Issueを更新できなかった
        self.write({"ok": False, "signature": "SEIDO_HTTP_404,BROWSER_FLOW<script>", "errors": []})
        sig, body = hb.decide(self.result, "true")
        self.assertEqual(sig, "success")  # ページの異常は監視が動いた結果(知らせるのは障害Issue・LINE)
        self.assertIn("SEIDO_HTTP_404,BROWSER_FLOWscript", body)


class Send(Base):
    def test_not_configured_or_invalid_sends_nothing(self):
        self.write({"ok": True})
        self.assertIn("未設定", self.run_main({"HEARTBEAT_URL": "", "HANDLED": "true"}))
        self.assertIn("形式が想定外", self.run_main({"HEARTBEAT_URL": "http://hc-ping.com/x", "HANDLED": "true"}))
        self.assertIn("形式が想定外", self.run_main({"HEARTBEAT_URL": "https://hc-ping.com/x y", "HANDLED": "true"}))
        self.assertEqual(self.calls, [])

    def test_success_and_fail_endpoints(self):
        self.write({"ok": True})
        out = self.run_main({"HEARTBEAT_URL": URL, "HANDLED": "true"})
        self.assertEqual(self.calls[-1][0], URL)
        self.assertIn("生存(成功)", out)
        os.remove(self.result)
        out = self.run_main({"HEARTBEAT_URL": URL + "/", "HANDLED": "true"})
        self.assertEqual(self.calls[-1][0], URL + "/fail")
        self.assertIn("MONITOR_SETUP", self.calls[-1][1])
        self.assertIn("監視の故障(失敗)", out)

    def test_errors_are_reported_without_url_and_retried_sensibly(self):
        self.write({"ok": True})
        err5 = urllib.error.HTTPError(URL, 503, "busy " + URL, {}, None)
        out = self.run_main({"HEARTBEAT_URL": URL, "HANDLED": "true"}, [err5, err5, err5])
        self.assertEqual(len(self.calls), 3)            # 一時的な障害は3回まで試す
        self.assertIn("送れませんでした", out)
        self.assertIn("HTTP 503", out)
        self.calls.clear()
        err4 = urllib.error.HTTPError(URL, 404, "nf " + URL, {}, None)
        self.run_main({"HEARTBEAT_URL": URL, "HANDLED": "true"}, [err4])
        self.assertEqual(len(self.calls), 1)            # URLの誤りは繰り返さない
        self.calls.clear()
        out = self.run_main({"HEARTBEAT_URL": URL, "HANDLED": "true"},
                            [urllib.error.URLError(OSError(URL)), Res()])
        self.assertEqual(len(self.calls), 2)
        self.assertIn("送りました", out)
        out = self.run_main({"HEARTBEAT_URL": URL, "HANDLED": "true"}, [RuntimeError(URL)] * 3)
        self.assertIn("RuntimeError", out)


class Workflow(unittest.TestCase):
    """diagnosis-monitor.yml: ハートビートの Secret は送るステップだけが読み、失敗してもジョブを赤にしない。"""

    def test_secret_scope(self):
        with open(os.path.join(ROOT, ".github", "workflows", "diagnosis-monitor.yml"), encoding="utf-8") as f:
            text = f.read()
        steps = re.split(r"\n      - ", text)
        users = [s for s in steps if "secrets.DIAG_HEARTBEAT_URL" in s]
        self.assertEqual(len(users), 2)  # 監視ジョブの最後と、予備ジョブ
        for s in users:
            self.assertIn("continue-on-error: true", s)
            self.assertIn("if: always()", s)
            self.assertNotRegex(s, r"echo[^\n]*\$\{?HEARTBEAT_URL\}?\s*($|\")")  # URLを表示しない
        self.assertNotIn("LINE_", "".join(users))


if __name__ == "__main__":
    unittest.main()
