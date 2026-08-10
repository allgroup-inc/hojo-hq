import unittest
from datetime import date
from scripts.churn.cohort import cohort_rows, overall_rate

AS_OF = date(2026, 8, 1)


def rec(apply, resolved, early):
    return {"apply_date": apply, "is_resolved": resolved, "is_early_churn": early}


class TestCohort(unittest.TestCase):
    def test_rate_over_resolved_only(self):
        recs = ([rec(date(2025, 1, 5), True, 1) for _ in range(2)]
                + [rec(date(2025, 1, 6), True, 0) for _ in range(6)]
                + [rec(date(2025, 1, 7), False, None) for _ in range(2)])  # 継続中
        row = {r["ym"]: r for r in cohort_rows(recs, AS_OF)}["2025-01"]
        self.assertEqual(row["total"], 10)
        self.assertEqual(row["resolved"], 8)
        self.assertEqual(row["rate"], 0.25)      # 2/8（確定分のみ）
        self.assertFalse(row["observing"])       # maturity 0.8 → 観測中でない

    def test_low_maturity_cohort_is_observing(self):
        recs = ([rec(date(2026, 5, 5), True, 1) for _ in range(2)]
                + [rec(date(2026, 5, 6), False, None) for _ in range(8)])  # 大半が継続中
        row = {r["ym"]: r for r in cohort_rows(recs, AS_OF)}["2026-05"]
        self.assertTrue(row["observing"])

    def test_overall_excludes_observing(self):
        mature = [rec(date(2025, 1, 5), True, 1) for _ in range(2)] + \
                 [rec(date(2025, 1, 6), True, 0) for _ in range(6)]
        observing = [rec(date(2026, 5, 5), True, 1) for _ in range(2)] + \
                    [rec(date(2026, 5, 6), False, None) for _ in range(8)]
        rows = cohort_rows(mature + observing, AS_OF)
        o = overall_rate(rows)
        self.assertEqual(o["rate"], 0.25)   # 成熟コホートの 2/8 のみ（観測中の 2/2 は除外）
        self.assertEqual(o["resolved"], 8)

    def test_small_n_is_reference(self):
        recs = [rec(date(2025, 3, 5), True, 0) for _ in range(5)]
        row = {r["ym"]: r for r in cohort_rows(recs, AS_OF)}["2025-03"]
        self.assertTrue(row["reference"])   # 5 < MIN_RELIABLE_N


if __name__ == "__main__":
    unittest.main()
