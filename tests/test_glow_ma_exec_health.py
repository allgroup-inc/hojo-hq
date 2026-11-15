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


# --- 2026-11-15 日次メンテナンスの失敗を見つけて LINE でも知らせる(企業IDなどはすべて架空) ---
OK_ALL = "日次メンテナンスがすべて完了しました。"
FAIL_SCORE = "日次メンテナンス: 「スコア・ランクの再計算」が失敗しました: Exception: Service Spreadsheets failed while accessing document with id 1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789."
STOP_PRE = ("日次メンテナンス: 「お断り(連絡不要)の反映」が失敗しました: Error: 企業マスタの書き込みを止めました。"
            "書く前の確認で止めました(企業マスタは変更していません): 数式が入っているセルが 1か所あります(8行目の総合スコア)。")
STOP_WRITE = ("日次メンテナンス: 「スコア・ランクの再計算」が失敗しました: Error: 企業マスタの書き込みを止めました。"
              "書き込みの途中で止まりました(1500/3300社まで書きました。会社の行の位置は変わらないため…): Exception: Service Spreadsheets failed")
STOP_VERIFY = ("日次メンテナンス: 「スコア・ランクの再計算」が失敗しました: Error: 企業マスタの書き込みを止めました。"
               "書いた後の照合で違いが見つかりました(余った行は消していません。…): 見つからない企業ID 1件(C900010)")


class MaintenanceProblems(unittest.TestCase):
    def test_no_problem_on_normal_day(self):
        entries = [entry(30, "日次メンテナンス: 「スコア・ランクの再計算」が完了しました。"), entry(29, OK_ALL)]
        self.assertEqual(h.maintenance_problems(entries, NOW, 360), [])

    def test_failed_step_is_reported_with_step_name_only(self):
        # 11/11 の事故の形(Google 側のエラーで再計算が失敗)。知らせには手順名だけを出し、ログの本文は出さない
        problems = h.maintenance_problems([entry(30, FAIL_SCORE)], NOW, 360)
        self.assertEqual(len(problems), 1)
        self.assertIn("1 件の手順が失敗", problems[0])
        self.assertIn("スコア・ランクの再計算", problems[0])
        self.assertNotIn("Service Spreadsheets", problems[0])
        self.assertNotIn("1AbCdEf", problems[0])
        self.assertIn("稼働状況", problems[0])

    def test_company_write_stop_phases(self):
        pre = h.maintenance_problems([entry(30, STOP_PRE)], NOW, 360)[0]
        self.assertIn("書く前の確認で止めました(企業マスタは変更されていません)", pre)
        self.assertNotIn("8行目", pre)
        write = h.maintenance_problems([entry(30, STOP_WRITE, structured=True)], NOW, 360)[0]
        self.assertIn("途中で止まりました(途中まで書き換わっている可能性があります)", write)
        self.assertNotIn("1500", write)
        verify = h.maintenance_problems([entry(30, STOP_VERIFY)], NOW, 360)[0]
        self.assertIn("書いた後の照合で止めました", verify)
        self.assertNotIn("C900010", verify)

    def test_two_steps_and_unknown_step_name(self):
        entries = [entry(31, STOP_PRE), entry(30, FAIL_SCORE),
                   entry(29, "日次メンテナンス: 「架空の手順 C900001」が失敗しました: Error")]
        p = h.maintenance_problems(entries, NOW, 360)[0]
        self.assertIn("3 件の手順が失敗", p)
        self.assertIn("お断り(連絡不要)の反映・スコア・ランクの再計算・その他の手順", p)
        self.assertNotIn("C900001", p)

    def test_old_failure_is_not_reported(self):
        # 期間より前の失敗では知らせない(同じ失敗で何日も知らせ続けない)
        self.assertEqual(h.maintenance_problems([entry(400, FAIL_SCORE)], NOW, 360), [])
        self.assertEqual(len(h.maintenance_problems([entry(350, FAIL_SCORE)], NOW, 360)), 1)

    def test_failure_is_caught_even_when_the_scheduled_check_is_hours_late(self):
        # 実績: 定期の点検は4〜11時間あくことがある。7:32 の失敗の次の点検が10時間40分後でも拾う
        entries = [entry(640, FAIL_SCORE), entry(100, BEAT)]
        default_minutes = h.ALERT_MAINTENANCE_MINUTES
        problems = h.all_alert_problems(entries, NOW, 8, 60, default_minutes)
        self.assertEqual(len(problems), 1)
        self.assertIn("日次メンテナンス", problems[0])
        self.assertEqual(h.all_alert_problems([entry(900, FAIL_SCORE), entry(100, BEAT)], NOW, 8, 60, default_minutes), [])

    def test_wider_fetch_does_not_relax_heartbeat_check(self):
        # 実行記録を14時間ぶん取っても、稼働記録の有無は直近8時間だけで見る(10時間前の稼働記録では通さない)
        problems = h.all_alert_problems([entry(600, BEAT)], NOW, 8, 60, 840)
        self.assertEqual(len(problems), 1)
        self.assertIn("稼働記録", problems[0])
        self.assertEqual(h.all_alert_problems([entry(400, BEAT)], NOW, 8, 60, 840), [])

    def test_fetch_hours(self):
        self.assertEqual(h.fetch_hours(8, True, 840), 14)
        self.assertEqual(h.fetch_hours(8, True, 850), 15)
        self.assertEqual(h.fetch_hours(48, True, 840), 48)
        self.assertEqual(h.fetch_hours(8, False, 840), 8, "手動の点検は、指定した時間のまま")

    def test_failure_followed_by_successful_rerun_is_not_reported(self):
        entries = [entry(120, FAIL_SCORE), entry(20, OK_ALL)]
        self.assertEqual(h.maintenance_problems(entries, NOW, 360), [])
        # 成功のあとにまた失敗したら知らせる
        self.assertEqual(len(h.maintenance_problems(entries + [entry(5, FAIL_SCORE)], NOW, 360)), 1)

    def test_step_names_match_maintenance_runner(self):
        # 手順名は MaintenanceRunner.gs と同じであること(名前を変えたら、こちらも直す)
        src = open(os.path.join(ROOT, "glow-ma", "src", "MaintenanceRunner.gs"), encoding="utf-8").read()
        import re
        names = re.findall(r'\{ name: "([^"]+)", run:', src)
        self.assertEqual(tuple(names), h.MAINTENANCE_STEPS)

    def test_all_alert_problems_includes_maintenance_failure(self):
        ok = [entry(120, BEAT), entry(30, OK_ALL)]
        self.assertEqual(h.all_alert_problems(ok, NOW, 8, 60, 360), [])
        both = h.all_alert_problems([entry(5, AUTH), entry(120, BEAT), entry(30, FAIL_SCORE)], NOW, 8, 60, 360)
        self.assertEqual(len(both), 2)
        self.assertIn("承認切れ", both[0])
        self.assertIn("日次メンテナンス", both[1])

    def test_alert_output_file_carries_fixed_text_only(self):
        import tempfile
        problems = h.maintenance_problems([entry(30, STOP_WRITE)], NOW, 360) + h.alert_problems([], NOW, 8, 60)
        with tempfile.NamedTemporaryFile("r", suffix=".txt", encoding="utf-8") as tmp:
            h.write_alert_output(problems, tmp.name)
            out = open(tmp.name, encoding="utf-8").read()
        self.assertTrue(out.startswith("problems<<GLOW_MA_ALERT_END\n・"))
        self.assertTrue(out.endswith("\nGLOW_MA_ALERT_END\n"))
        self.assertEqual(out.count("\n・"), 2, "問題2件が1行ずつ入る")
        self.assertNotIn("Service Spreadsheets", out)
        h.write_alert_output(problems, "")  # 出力先が無ければ何もしない


if __name__ == "__main__":
    unittest.main()
