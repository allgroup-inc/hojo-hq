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

    def test_flag_shown(self):
        today = [{"customer_id": "C1", "trigger": "高リスク", "flags": ["解約意向・次アクション無し"]}]
        h = render_console(today, date(2026, 8, 18))
        self.assertIn("解約意向・次アクション無し", h)

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

    def test_churn_intent_without_next_action_is_top_flag(self):
        # 解約意向を聞いたのに次アクション無し＝日数無関係・最優先
        today = [{"customer_id": "C1", "trigger": "高リスク"}]
        contacts = [{"customer_id": "C1", "contact_date": date(2026, 8, 19),
                     "result": "解約意向", "next_action": ""}]
        self.assertIn("解約意向・次アクション無し",
                      annotate_flags(today, contacts, self.AS_OF)[0]["flags"])

    def test_churn_intent_with_next_action_no_flag(self):
        contacts = [{"customer_id": "C1", "contact_date": date(2026, 8, 19),
                     "result": "解約意向", "next_action": "再架電"}]
        self.assertEqual(annotate_flags([{"customer_id": "C1"}], contacts, self.AS_OF)[0]["flags"], [])

    def test_long_no_contact_flag(self):
        # 90日以上の未接触＝長期未接触（14日のような短間隔では出さない）
        contacts = [{"customer_id": "C1", "contact_date": date(2026, 5, 1),
                     "result": "検討中", "next_action": "様子見"}]   # 111日前
        self.assertIn("111日未接触", annotate_flags([{"customer_id": "C1"}], contacts, self.AS_OF)[0]["flags"])

    def test_recent_contact_no_flag(self):
        contacts = [{"customer_id": "C1", "contact_date": date(2026, 8, 1),
                     "result": "検討中", "next_action": "再架電"}]   # 19日前=90日未満
        self.assertEqual(annotate_flags([{"customer_id": "C1"}], contacts, self.AS_OF)[0]["flags"], [])

    def test_never_contacted_no_flag(self):
        self.assertEqual(annotate_flags([{"customer_id": "C1"}], [], self.AS_OF)[0]["flags"], [])


if __name__ == "__main__":
    unittest.main()
