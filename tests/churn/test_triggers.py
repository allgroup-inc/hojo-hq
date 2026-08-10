import unittest
from datetime import date, timedelta
from scripts.churn.triggers import prevention_trigger, prevention_candidates

AS_OF = date(2026, 8, 1)


def rec(**over):
    base = {"is_scoreable": True, "debit_result": "", "account_daily": "はい",
            "debit_due": None, "customer_id": "C1"}
    base.update(over)
    return base


class TestTriggers(unittest.TestCase):
    def test_debit_not_arrived_is_priority_alert(self):
        self.assertEqual(prevention_trigger(rec(debit_result="不着"), AS_OF), "不着")

    def test_debit_delayed_is_alert(self):
        self.assertEqual(prevention_trigger(rec(debit_result="遅延"), AS_OF), "遅延")

    def test_pre_debit_account_problem_triggers_check(self):
        # 引落前(結果なし・予定日が近い未来) × 口座いいえ → 口座確認
        r = rec(account_daily="いいえ", debit_result="", debit_due=AS_OF + timedelta(days=3))
        self.assertEqual(prevention_trigger(r, AS_OF), "口座確認")

    def test_account_ok_is_no_trigger(self):
        r = rec(account_daily="はい", debit_due=AS_OF + timedelta(days=3))
        self.assertIsNone(prevention_trigger(r, AS_OF))

    def test_already_debited_is_not_pre_debit(self):
        # 引落済み(結果あり)なら「口座確認(引落前)」にはならない
        r = rec(account_daily="いいえ", debit_result="成功", debit_due=AS_OF + timedelta(days=3))
        self.assertIsNone(prevention_trigger(r, AS_OF))

    def test_due_in_past_is_not_pre_debit_window(self):
        r = rec(account_daily="いいえ", debit_result="", debit_due=AS_OF - timedelta(days=1))
        self.assertIsNone(prevention_trigger(r, AS_OF))

    def test_not_scoreable_has_no_trigger(self):
        self.assertIsNone(prevention_trigger(rec(is_scoreable=False, debit_result="不着"), AS_OF))

    def test_candidates_collects_only_triggered(self):
        recs = [rec(debit_result="不着", customer_id="A"),
                rec(customer_id="B"),  # トリガーなし
                rec(account_daily="未確認", debit_due=AS_OF + timedelta(days=2), customer_id="C")]
        got = prevention_candidates(recs, AS_OF)
        self.assertEqual([(r["customer_id"], t) for r, t in got],
                         [("A", "不着"), ("C", "口座確認")])


if __name__ == "__main__":
    unittest.main()
