import unittest
from datetime import date, timedelta
from scripts.churn import karte_effect
from scripts.churn.config import MIN_RELIABLE_N


def app(cid, early, apply_d=date(2025, 1, 1), cancel=None):
    return {"customer_id": cid, "apply_date": apply_d, "is_resolved": True,
            "is_early_churn": early, "cancel_date": cancel}


def inter(cid, d, kind="架電"):
    return {"customer_id": cid, "date": d, "kind": kind}


class TestKarteEffect(unittest.TestCase):
    def test_was_contacted_window(self):
        by_cid = {"C1": [inter("C1", date(2025, 2, 1))]}
        self.assertTrue(karte_effect.was_contacted(
            "C1", date(2025, 1, 1), by_cid, ("架電",), 90))
        self.assertFalse(karte_effect.was_contacted(
            "C2", date(2025, 1, 1), by_cid, ("架電",), 90))

    def test_was_contacted_boundary_within_days(self):
        apply_d = date(2025, 1, 1)
        by_cid = {"C1": [inter("C1", apply_d + timedelta(days=90))]}
        self.assertTrue(karte_effect.was_contacted(
            "C1", apply_d, by_cid, ("架電",), 90))

    def test_was_contacted_boundary_within_days_plus_one(self):
        apply_d = date(2025, 1, 1)
        by_cid = {"C1": [inter("C1", apply_d + timedelta(days=91))]}
        self.assertFalse(karte_effect.was_contacted(
            "C1", apply_d, by_cid, ("架電",), 90))

    def test_was_contacted_before_apply_date_excluded(self):
        apply_d = date(2025, 1, 1)
        by_cid = {"C1": [inter("C1", apply_d - timedelta(days=1))]}
        self.assertFalse(karte_effect.was_contacted(
            "C1", apply_d, by_cid, ("架電",), 90))

    def test_was_contacted_after_cancel_date_excluded(self):
        """免疫時間バイアス対策：解約後の接触は「保全接触あり」に数えない。"""
        apply_d = date(2025, 1, 1)
        cancel_d = date(2025, 1, 10)
        by_cid = {"C1": [inter("C1", date(2025, 1, 20))]}  # apply後90日以内だが解約後
        self.assertFalse(karte_effect.was_contacted(
            "C1", apply_d, by_cid, ("架電",), 90, cancel_date=cancel_d))
        # 解約前の接触なら引き続きTrue
        by_cid2 = {"C1": [inter("C1", date(2025, 1, 5))]}
        self.assertTrue(karte_effect.was_contacted(
            "C1", apply_d, by_cid2, ("架電",), 90, cancel_date=cancel_d))

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

    def test_contact_effect_reference_true_when_small_sample(self):
        apps = [app("C1", 0), app("C2", 0), app("C3", 1), app("C4", 1)]
        inters = [inter("C1", date(2025, 2, 1)), inter("C2", date(2025, 2, 1))]
        out = karte_effect.contact_effect(apps, inters, kinds=("架電",), within_days=90)
        self.assertIs(out["reference"], True)

    def test_contact_effect_reference_false_when_both_groups_reliable(self):
        n = MIN_RELIABLE_N
        apps = ([app(f"K{i}", 0) for i in range(n)]
                + [app(f"NK{i}", 1) for i in range(n)])
        inters = [inter(f"K{i}", date(2025, 2, 1)) for i in range(n)]
        out = karte_effect.contact_effect(apps, inters, kinds=("架電",), within_days=90)
        self.assertEqual(out["n_contacted"], n)
        self.assertEqual(out["n_not_contacted"], n)
        self.assertIs(out["reference"], False)

    def test_contact_effect_excludes_post_cancel_contact(self):
        """解約後の接触は保全効果ありとみなさない(免疫時間バイアス排除)。"""
        apply_d = date(2025, 1, 1)
        cancel_d = date(2025, 1, 10)
        apps = [app("C1", 1, apply_d=apply_d, cancel=cancel_d)]
        inters = [inter("C1", date(2025, 1, 20))]  # 解約後の接触
        out = karte_effect.contact_effect(apps, inters, kinds=("架電",), within_days=90)
        self.assertEqual(out["n_contacted"], 0)
        self.assertEqual(out["n_not_contacted"], 1)


if __name__ == "__main__":
    unittest.main()
