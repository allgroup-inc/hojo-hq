import unittest
from datetime import date
from scripts.churn import karte_effect


def app(cid, early, apply_d=date(2025, 1, 1)):
    return {"customer_id": cid, "apply_date": apply_d, "is_resolved": True,
            "is_early_churn": early}


def inter(cid, d, kind="架電"):
    return {"customer_id": cid, "date": d, "kind": kind}


class TestKarteEffect(unittest.TestCase):
    def test_was_contacted_window(self):
        by_cid = {"C1": [inter("C1", date(2025, 2, 1))]}
        self.assertTrue(karte_effect.was_contacted(
            "C1", date(2025, 1, 1), by_cid, ("架電",), 90))
        self.assertFalse(karte_effect.was_contacted(
            "C2", date(2025, 1, 1), by_cid, ("架電",), 90))

    def test_contact_effect_diff(self):
        apps = [app("C1", 0), app("C2", 0), app("C3", 1), app("C4", 1)]
        # C1,C2 に保全接触あり(解約せず) / C3,C4 は接触なし(解約)
        inters = [inter("C1", date(2025, 2, 1)), inter("C2", date(2025, 2, 1))]
        out = karte_effect.contact_effect(apps, inters, kinds=("架電",), within_days=90)
        self.assertEqual(out["n_contacted"], 2)
        self.assertEqual(out["n_not_contacted"], 2)
        self.assertAlmostEqual(out["contacted_rate"], 0.0)
        self.assertAlmostEqual(out["not_contacted_rate"], 1.0)
        self.assertAlmostEqual(out["diff"], -1.0)


if __name__ == "__main__":
    unittest.main()
