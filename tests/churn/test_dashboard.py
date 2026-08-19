import unittest
from datetime import date

from scripts.churn import fit
from scripts.churn.dashboard import dashboard_summary, retained_premium

AS_OF = date(2026, 8, 1)


def rec(cid, months=None, scoreable=True, cat="継続", amount=5000,
        early=None, resolved=False, apply_d=date(2026, 5, 1), cancel=None):
    return {"customer_id": cid, "apply_id": None, "product": "医療", "agent_id": "S1",
            "channel": "催事", "apply_form": "対面", "amount": amount, "age_band": "20代",
            "amount_band": "中", "gender": "女", "area": "那覇",
            "apply_date": apply_d, "cancel_date": cancel,
            "is_scoreable": scoreable, "is_resolved": resolved, "is_early_churn": early,
            "status_category": cat, "in_scope": True, "unpaid_months": months or [],
            "debit_result": "", "account_daily": "", "debit_due": None,
            "unpaid_account_issue": False}


class TestDashboardSummary(unittest.TestCase):
    def test_headline_counts(self):
        recs = [
            rec("IMM", months=[(2026, 5), (2026, 6), (2026, 7)]),         # 未払消滅目前(streak3)
            rec("REL", months=[(2026, 3), (2026, 6), (2026, 7)]),         # 再発(ギャップあり)
            rec("OK", months=[]),                                         # 何もなし
        ]
        s = dashboard_summary(recs, AS_OF, fit.fit_model([]), capacity=30)
        self.assertEqual(s["imminent_count"], 1)          # A1
        self.assertEqual(s["relapse_count"], 1)           # A3
        self.assertIn("overall", s)                       # 3%スコアボード
        self.assertIn("today_total", s)                   # 今日の要接触
        self.assertEqual(s["today_capacity"], 30)

    def test_keys_present(self):
        s = dashboard_summary([rec("A")], AS_OF, fit.fit_model([]))
        for k in ("overall", "excluded", "today_total", "peaks",
                  "relapse_count", "imminent_count", "retained_premium"):
            self.assertIn(k, s)


class TestRetainedPremium(unittest.TestCase):
    def test_continuing_tenure_times_amount(self):
        # 契約2026-05-01→as_of2026-08-01＝約92日=3ヶ月・月額5000 → 15000
        r = rec("A", apply_d=date(2026, 5, 1), amount=5000)
        self.assertEqual(retained_premium([r], AS_OF), 15000)

    def test_excludes_out_of_scope_and_non_continuing(self):
        out = dict(rec("X", apply_d=date(2026, 5, 1)), in_scope=False)
        churned = dict(rec("Y", apply_d=date(2026, 5, 1)),
                       is_scoreable=False, status_category="早期解約")
        self.assertEqual(retained_premium([out, churned], AS_OF), 0)


if __name__ == "__main__":
    unittest.main()
