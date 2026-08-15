import unittest
from datetime import date, timedelta

from scripts.churn.timing import contact_timing_effect

MB = date(2026, 2, 1)
AD = date(2025, 1, 1)


def R(cid, early, cancel=None):
    return {"customer_id": cid, "apply_id": cid, "apply_date": AD,
            "cancel_date": cancel, "is_resolved": True, "is_early_churn": early}


def K(cid, tenure, action="架電"):
    return {"customer_id": cid, "apply_id": cid, "apply_date": AD,
            "contact_date": AD + timedelta(days=tenure), "action": action}


class TestContactTimingEffect(unittest.TestCase):
    def _data(self):
        recs, cons = [], []
        # 早期(経過5日)に架電＝解約0
        for i in range(6):
            recs.append(R(f"E{i}", 0)); cons.append(K(f"E{i}", 5))
        # 遅い(経過40日)に架電＝解約1（解約は59日目）
        for i in range(6):
            recs.append(R(f"L{i}", 1, cancel=AD + timedelta(days=59))); cons.append(K(f"L{i}", 40))
        # 未接触＝解約1が半分
        for i in range(6):
            recs.append(R(f"N{i}", 1 if i < 3 else 0, cancel=(AD + timedelta(days=30)) if i < 3 else None))
        return recs, cons

    def test_rate_by_contact_tenure_bucket(self):
        recs, cons = self._data()
        out = contact_timing_effect(recs, cons, MB, bucket_days=15)
        by = {(r["lo"], r["hi"]): r for r in out["rows"]}
        self.assertEqual(by[(0, 15)]["rate"], 0.0)     # 早期架電＝解約0
        self.assertEqual(by[(30, 45)]["rate"], 1.0)    # 遅い架電＝解約1
        self.assertEqual(by[(0, 15)]["n"], 6)

    def test_not_contacted_row_present(self):
        recs, cons = self._data()
        out = contact_timing_effect(recs, cons, MB, bucket_days=15)
        self.assertEqual(out["not_contacted"]["n"], 6)
        self.assertAlmostEqual(out["not_contacted"]["rate"], 0.5)

    def test_reference_flag_small_sample(self):
        recs = [R("E0", 0)]; cons = [K("E0", 5)]
        out = contact_timing_effect(recs, cons, MB, bucket_days=15)
        self.assertTrue(out["rows"][0]["reference"])

    def test_post_cancel_contact_not_counted(self):
        # 解約後の架電は「接触」に数えない（免疫時間）→ 未接触側へ
        recs = [R("X", 1, cancel=AD + timedelta(days=20))]
        cons = [K("X", 40)]  # 解約(20日)より後の接触
        out = contact_timing_effect(recs, cons, MB, bucket_days=15)
        self.assertEqual(out["not_contacted"]["n"], 1)
        self.assertEqual(sum(r["n"] for r in out["rows"]), 0)


if __name__ == "__main__":
    unittest.main()
