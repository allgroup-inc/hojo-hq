import unittest
from datetime import date
from scripts.churn import fit
from scripts.churn.cohort import cohort_rows, overall_rate

AS_OF = date(2026, 8, 1)


def rec(apply, resolved, early):
    return {"apply_date": apply, "is_resolved": resolved, "is_early_churn": early}


def frec(apply, resolved, early, scoreable=False, product="医療"):
    """score可能な要因つきレコード（着地見込みの推計に使う）。"""
    return {"apply_date": apply, "is_resolved": resolved, "is_early_churn": early,
            "is_scoreable": scoreable, "product": product, "channel": "ネット",
            "apply_form": "単発", "amount_band": "3千〜1万", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1"}


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

    def test_observing_is_calendar_based_not_churn_ratio(self):
        # 直近コホートで解約が多く resolved/total が高くても、暦上6ヶ月未経過なら観測中
        recs = ([rec(date(2026, 6, 5), True, 1) for _ in range(8)]
                + [rec(date(2026, 6, 6), False, None) for _ in range(2)])
        row = {r["ym"]: r for r in cohort_rows(recs, AS_OF)}["2026-06"]
        self.assertTrue(row["observing"])   # maturity=0.8でも暦で未成熟

    def test_overall_rate_none_when_no_mature(self):
        recs = [rec(date(2026, 7, 5), True, 1) for _ in range(5)]  # 暦上 観測中のみ
        o = overall_rate(cohort_rows(recs, AS_OF))
        self.assertIsNone(o["rate"])        # 算出不能（0%と断定しない）


class TestProjectedLanding(unittest.TestCase):
    def _model(self):
        # X商品=解約多・Y商品=解約なし で学習 → 継続中Xは高リスクと推計される
        train = ([frec(date(2025, 1, 1), True, 1, product="X") for _ in range(40)]
                 + [frec(date(2025, 1, 1), True, 0, product="Y") for _ in range(40)])
        return fit.fit_model(train)

    def test_observing_cohort_gets_projection_separate_from_confirmed(self):
        model = self._model()
        # 観測中コホート(2026-07): 継続中のX契約が多い → 着地見込みは高め
        recs = [frec(date(2026, 7, 1), False, None, scoreable=True, product="X") for _ in range(10)]
        row = {r["ym"]: r for r in cohort_rows(recs, AS_OF, model=model)}["2026-07"]
        self.assertTrue(row["observing"])
        self.assertIsNone(row["rate"])                 # 確定値は無い（混同しない）
        self.assertIsNotNone(row["projected_rate"])    # 見込みは出る
        self.assertGreater(row["projected_rate"], 0.0)

    def test_no_model_means_no_projection(self):
        recs = [frec(date(2026, 7, 1), False, None, scoreable=True) for _ in range(5)]
        row = {r["ym"]: r for r in cohort_rows(recs, AS_OF)}["2026-07"]
        self.assertIsNone(row["projected_rate"])       # モデル無しなら推計しない

    def test_projection_blends_confirmed_and_predicted(self):
        model = self._model()
        # 確定=Y(解約0) 5件 + 継続中=X(高リスク) 5件 の月 → 見込みは0と高リスクの中間
        recs = ([frec(date(2026, 7, 1), True, 0, product="Y") for _ in range(5)]
                + [frec(date(2026, 7, 1), False, None, scoreable=True, product="X") for _ in range(5)])
        row = {r["ym"]: r for r in cohort_rows(recs, AS_OF, model=model)}["2026-07"]
        self.assertTrue(0.0 < row["projected_rate"] < 1.0)


if __name__ == "__main__":
    unittest.main()
