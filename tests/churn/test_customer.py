import unittest
from datetime import date
from scripts.churn import fit, customer


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
        self.assertEqual(c["n_early_churn"], 1)
        self.assertEqual(c["n_additional_guidance"], 1)
        self.assertEqual(c["interactions"][0]["date"], date(2026, 3, 5))  # 降順
        self.assertEqual(c["last_contact_date"], date(2026, 3, 5))

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


if __name__ == "__main__":
    unittest.main()
