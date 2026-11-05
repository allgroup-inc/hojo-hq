"""scripts/glow_ma_exec_health.py の自動点検の判定(alert_problems)のテスト。
実行: python3 -m unittest tests/test_glow_ma_exec_health.py
Google への接続はしない(判定の関数だけを試す)。"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import glow_ma_exec_health as h  # noqa: E402

NOW = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
BEAT = "録音ファイルの受付フォルダ: 稼働中(共有 3 人)"
AUTH = "その操作を実行するには承認が必要です。"


def entry(minutes_ago, text, structured=False):
    ts = (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if structured:
        return {"timestamp": ts, "jsonPayload": {"message": text}}
    return {"timestamp": ts, "textPayload": text}


class AlertProblems(unittest.TestCase):
    def test_no_problem_when_heartbeat_and_no_auth_error(self):
        self.assertEqual(h.alert_problems([entry(120, BEAT)], NOW, 8, 60), [])

    def test_recent_auth_error_is_reported(self):
        entries = [entry(120, BEAT), entry(5, AUTH, structured=True), entry(4, "Authorization is required to perform that action.")]
        problems = h.alert_problems(entries, NOW, 8, 60)
        self.assertEqual(len(problems), 1)
        self.assertIn("2 回", problems[0])
        self.assertIn("自動処理を復旧する", problems[0])

    def test_old_auth_errors_after_recovery_are_not_reported(self):
        # 3時間前まで止まっていて、その後に復旧した(稼働記録あり)。古いエラーでは知らせない
        entries = [entry(200, AUTH), entry(190, AUTH), entry(170, BEAT)]
        self.assertEqual(h.alert_problems(entries, NOW, 8, 60), [])

    def test_missing_heartbeat_is_reported(self):
        problems = h.alert_problems([entry(10, "ほかの記録")], NOW, 8, 60)
        self.assertEqual(len(problems), 1)
        self.assertIn("稼働記録", problems[0])

    def test_both_problems(self):
        self.assertEqual(len(h.alert_problems([entry(1, AUTH)], NOW, 8, 60)), 2)

    def test_empty_log(self):
        self.assertEqual(len(h.alert_problems([], NOW, 8, 60)), 1)


if __name__ == "__main__":
    unittest.main()
