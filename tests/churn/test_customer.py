import unittest
from datetime import date, timedelta
from scripts.churn import fit, customer
from scripts.churn.config import FOLLOWUP_DAYS


def app(cid, product, early=None, resolved=True, scoreable=False, apply_id="A", cancel=None):
    return {"customer_id": cid, "apply_id": apply_id, "product": product,
            "channel": "催事", "apply_form": "対面", "amount_band": "3千〜1万",
            "age_band": "20代", "gender": "女", "area": "那覇", "agent_id": "S1",
            "apply_date": date(2026, 1, 1), "cancel_date": cancel, "cancel_reason": "",
            "is_early_churn": early, "is_resolved": resolved, "is_scoreable": scoreable}


def inter(cid, d, kind):
    return {"customer_id": cid, "date": d, "kind": kind, "agent": "東さん",
            "content": "案内", "memo": ""}


def build_model():
    recs = [app("m", "X", 1) for _ in range(30)] + [app("m", "Y", 0) for _ in range(90)]
    return fit.fit_model(recs)


class TestCustomer(unittest.TestCase):
    def test_highest_band(self):
        self.assertEqual(customer.highest_band(["low", "high", "med"]), "high")
        self.assertIsNone(customer.highest_band([]))

    def test_rollup_counts_and_timeline(self):
        model = build_model()
        apps = [app("C1", "X", 1, apply_id="A1", cancel=date(2026, 3, 1)),   # 早期解約
                app("C1", "Y", None, resolved=False, scoreable=True, apply_id="A2")]  # 継続中
        inters = [inter("C1", date(2026, 2, 1), "架電"),
                  inter("C1", date(2026, 3, 5), "追加案内")]
        cs = customer.build_customers(apps, inters, model, date(2026, 4, 1))
        c = cs["C1"]
        self.assertEqual(c["n_applications"], 2)
        self.assertEqual(c["n_active"], 1)
        self.assertEqual(c["n_cancelled"], 1)
        self.assertEqual(c["n_early_churn"], 1)
        self.assertEqual(c["n_additional_guidance"], 1)
        self.assertEqual(c["interactions"][0]["date"], date(2026, 3, 5))  # 降順
        self.assertEqual(c["last_contact_date"], date(2026, 3, 5))
        # Early-churned app (resolved, not scoreable) should have risk=None
        self.assertIsNone(c["applications"][0]["risk"])
        # Active app (not resolved, scoreable) should have risk assigned
        self.assertIsNotNone(c["applications"][1]["risk"])

    def test_unlinked_records_excluded(self):
        model = build_model()
        apps = [app(None, "X", 1), app("", "Y", 0)]
        cs = customer.build_customers(apps, [], model, date(2026, 4, 1))
        self.assertEqual(cs, {})

    def test_needs_followup_high_risk_no_recent_contact(self):
        model = build_model()
        # 継続中・高リスク(product=X)で、接触が28日以上前 → 要フォロー
        apps = [app("C2", "X", None, resolved=False, scoreable=True)]
        inters = [inter("C2", date(2026, 3, 1), "架電")]
        cs = customer.build_customers(apps, inters, model, date(2026, 4, 1))  # 31日経過
        self.assertTrue(cs["C2"]["needs_followup"])
        self.assertEqual(cs["C2"]["max_risk_band"], "high")

    def test_needs_followup_boundary(self):
        """Boundary of needs_followup: exactly FOLLOWUP_DAYS is NOT overdue, FOLLOWUP_DAYS+1 IS."""
        model = build_model()
        as_of = date(2026, 4, 1)
        apps = [app("C3", "X", None, resolved=False, scoreable=True)]  # 高リスク

        # Contact exactly FOLLOWUP_DAYS ago → still on edge, not overdue
        on_edge = [inter("C3", as_of - timedelta(days=FOLLOWUP_DAYS), "架電")]
        self.assertFalse(customer.build_customers(apps, on_edge, model, as_of)["C3"]["needs_followup"])

        # Contact FOLLOWUP_DAYS+1 days ago → overdue
        over = [inter("C3", as_of - timedelta(days=FOLLOWUP_DAYS + 1), "架電")]
        self.assertTrue(customer.build_customers(apps, over, model, as_of)["C3"]["needs_followup"])

    def test_needs_followup_high_risk_recent_contact(self):
        """High risk with recent contact → should NOT need followup."""
        model = build_model()
        apps = [app("C4", "X", None, resolved=False, scoreable=True)]  # 高リスク
        inters = [inter("C4", date(2026, 3, 31), "架電")]  # 1日前
        cs = customer.build_customers(apps, inters, model, date(2026, 4, 1))
        self.assertFalse(cs["C4"]["needs_followup"])
        self.assertEqual(cs["C4"]["max_risk_band"], "high")

    def test_needs_followup_low_risk(self):
        """Low/med risk customer → should NOT need followup, even with no contact."""
        model = build_model()
        apps = [app("C5", "Y", None, resolved=False, scoreable=True)]  # 低リスク(product=Y)
        cs = customer.build_customers(apps, [], model, date(2026, 4, 1))
        self.assertFalse(cs["C5"]["needs_followup"])
        self.assertNotEqual(cs["C5"]["max_risk_band"], "high")

    def test_unlinked_counts(self):
        apps = [app(None, "X", 1), app("", "Y", 0), app("C1", "X", 0)]
        inters = [inter(None, date(2026, 1, 1), "架電"), inter("", date(2026, 1, 2), "架電"),
                  inter("C1", date(2026, 1, 3), "架電")]
        out = customer.unlinked_counts(apps, inters)
        self.assertEqual(out, {"apps": 2, "interactions": 2})

    def test_unlinked_counts_all_linked(self):
        apps = [app("C1", "X", 1)]
        inters = [inter("C1", date(2026, 1, 1), "架電")]
        out = customer.unlinked_counts(apps, inters)
        self.assertEqual(out, {"apps": 0, "interactions": 0})


if __name__ == "__main__":
    unittest.main()
