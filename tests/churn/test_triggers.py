import unittest
from datetime import date, timedelta
from scripts.churn.triggers import (
    prevention_trigger, prevention_candidates,
    initial_contact_trigger, initial_contact_candidates,
    unpaid_trigger,
)
from scripts.churn.effect_learning import _contacts_index

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


def orec(**over):
    base = {"is_scoreable": True, "customer_id": "C1", "apply_id": None,
            "apply_date": AS_OF - timedelta(days=5)}
    base.update(over)
    return base


def contact(cid, contact_date, apply_id=None, apply_date=None, action="初回架電"):
    return {"customer_id": cid, "apply_id": apply_id, "apply_date": apply_date,
            "contact_date": contact_date, "action": action}


class TestInitialContact(unittest.TestCase):
    def test_new_contract_without_contact_is_flagged(self):
        # 契約後5日・未接触の継続契約 → 初動
        r = orec(customer_id="N1", apply_date=AS_OF - timedelta(days=5))
        idx = _contacts_index([])
        self.assertEqual(initial_contact_trigger(r, idx, AS_OF, days=14), "初動")

    def test_contacted_new_contract_is_not_flagged(self):
        r = orec(customer_id="N2", apply_date=AS_OF - timedelta(days=5))
        idx = _contacts_index([contact("N2", AS_OF - timedelta(days=2),
                                       apply_date=AS_OF - timedelta(days=5))])
        self.assertIsNone(initial_contact_trigger(r, idx, AS_OF, days=14))

    def test_past_onboarding_window_is_not_initial(self):
        # 契約後30日＝初動窓(14日)を過ぎている → 初動ではない
        r = orec(customer_id="N3", apply_date=AS_OF - timedelta(days=30))
        idx = _contacts_index([])
        self.assertIsNone(initial_contact_trigger(r, idx, AS_OF, days=14))

    def test_not_scoreable_is_not_initial(self):
        r = orec(customer_id="N4", is_scoreable=False, apply_date=AS_OF - timedelta(days=5))
        self.assertIsNone(initial_contact_trigger(r, _contacts_index([]), AS_OF, days=14))

    def test_apply_id_join_prefers_contract_level(self):
        # 同一顧客が同日2契約(A1未接触,A2接触)。A1は初動、A2は初動でない
        a1 = orec(customer_id="D", apply_id="A1", apply_date=AS_OF - timedelta(days=3))
        a2 = orec(customer_id="D", apply_id="A2", apply_date=AS_OF - timedelta(days=3))
        idx = _contacts_index([contact("D", AS_OF - timedelta(days=1), apply_id="A2")])
        self.assertEqual(initial_contact_trigger(a1, idx, AS_OF, days=14), "初動")
        self.assertIsNone(initial_contact_trigger(a2, idx, AS_OF, days=14))

    def test_candidates_collects_initial(self):
        recs = [orec(customer_id="N1", apply_date=AS_OF - timedelta(days=5)),
                orec(customer_id="N3", apply_date=AS_OF - timedelta(days=30))]
        got = initial_contact_candidates(recs, [], AS_OF, days=14)
        self.assertEqual([(r["customer_id"], t) for r, t in got], [("N1", "初動")])


def urec(months, scoreable=True):
    return {"is_scoreable": scoreable, "unpaid_months": months}


class TestUnpaidTrigger(unittest.TestCase):
    def test_three_consecutive_is_imminent(self):
        # 直近3ヶ月連続未収（5・6・7月）→ 4ヶ月目で消滅 → 未払消滅目前
        r = urec([(2026, 7), (2026, 6), (2026, 5)])
        self.assertEqual(unpaid_trigger(r, AS_OF), "未払消滅目前")

    def test_two_consecutive(self):
        r = urec([(2026, 7), (2026, 6)])
        self.assertEqual(unpaid_trigger(r, AS_OF), "未収2連続")

    def test_one_month_no_trigger(self):
        self.assertIsNone(unpaid_trigger(urec([(2026, 7)]), AS_OF))

    def test_gap_breaks_streak(self):
        # 7月と5月（6月なし）→ 連続は1 → トリガーなし
        self.assertIsNone(unpaid_trigger(urec([(2026, 7), (2026, 5)]), AS_OF))

    def test_not_scoreable(self):
        self.assertIsNone(unpaid_trigger(urec([(2026, 7), (2026, 6), (2026, 5)], scoreable=False), AS_OF))

    def test_year_boundary(self):
        # 2025-12 と 2026-01 が連続（年跨ぎ）。as_of 2026-02 なら直近2連続
        r = urec([(2026, 1), (2025, 12)])
        self.assertEqual(unpaid_trigger(r, date(2026, 2, 1)), "未収2連続")


if __name__ == "__main__":
    unittest.main()
