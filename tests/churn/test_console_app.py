import unittest
from datetime import date

from scripts.churn.console_app import render_console, PICKLISTS


class TestRenderConsole(unittest.TestCase):
    def test_row_has_form_and_picklists(self):
        today = [{"customer_id": "C1", "trigger": "未払消滅目前", "channel": "架電",
                  "saveable": 35000, "recommendation": "架電で入金のご相談"}]
        h = render_console(today, date(2026, 8, 18))
        self.assertIn("C1", h)
        self.assertIn("未払消滅目前", h)
        self.assertIn('action="/record"', h)          # 記録の送信先
        self.assertIn('name="customer_id"', h)
        for opt in PICKLISTS["result"]:
            self.assertIn(opt, h)                      # 結果の選択肢が出ている
        self.assertIn("35,000円", h)                   # 守れる金額

    def test_saved_marker_only_on_saved_row(self):
        today = [{"customer_id": "C1", "trigger": "不着"},
                 {"customer_id": "C2", "trigger": "初動"}]
        h = render_console(today, date(2026, 8, 18), saved_cid="C1")
        self.assertEqual(h.count("記録しました"), 1)

    def test_empty_list_ok(self):
        h = render_console([], date(2026, 8, 18))
        self.assertIn("今日の要接触 0件", h)


if __name__ == "__main__":
    unittest.main()
