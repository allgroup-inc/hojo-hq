import unittest
from datetime import date

from scripts.churn.console_app import render_console, annotate_flags, PICKLISTS


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

    def test_result_required_others_optional(self):
        # 結果だけ必須（1タップ）／懸念・返し方などは任意
        h = render_console([{"customer_id": "C1", "trigger": "不着"}], date(2026, 8, 18))
        self.assertIn('name="result" required', h)     # 結果は必須
        self.assertIn('name="concern"', h)
        self.assertNotIn('name="concern" required', h)  # 懸念は任意
        self.assertIn("任意", h)

    def test_stale_flag_shown(self):
        today = [{"customer_id": "C1", "trigger": "高リスク", "flags": ["20日放置"]}]
        h = render_console(today, date(2026, 8, 18))
        self.assertIn("20日放置", h)

    def test_saved_marker_only_on_saved_row(self):
        today = [{"customer_id": "C1", "trigger": "不着"},
                 {"customer_id": "C2", "trigger": "初動"}]
        h = render_console(today, date(2026, 8, 18), saved_cid="C1")
        self.assertEqual(h.count("記録しました"), 1)

    def test_empty_list_ok(self):
        h = render_console([], date(2026, 8, 18))
        self.assertIn("今日の要接触 0件", h)


class TestAnnotateFlags(unittest.TestCase):
    AS_OF = date(2026, 8, 20)

    def test_stale_after_threshold(self):
        today = [{"customer_id": "C1", "trigger": "高リスク"}]
        contacts = [{"customer_id": "C1", "contact_date": date(2026, 8, 1)}]  # 19日前
        out = annotate_flags(today, contacts, self.AS_OF, stale_days=14)
        self.assertIn("19日放置", out[0]["flags"])

    def test_recent_contact_no_flag(self):
        today = [{"customer_id": "C1", "trigger": "不着"}]
        contacts = [{"customer_id": "C1", "contact_date": date(2026, 8, 18)}]  # 2日前
        self.assertEqual(annotate_flags(today, contacts, self.AS_OF)[0]["flags"], [])

    def test_never_contacted_no_stale_flag(self):
        # 未接触は「放置」ではない（これから接触するため）＝フラグなし
        out = annotate_flags([{"customer_id": "C1", "trigger": "初動"}], [], self.AS_OF)
        self.assertEqual(out[0]["flags"], [])


if __name__ == "__main__":
    unittest.main()
