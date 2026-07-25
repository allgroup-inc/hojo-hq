import unittest
from scripts.churn import fit, score


def rec(product, early, resolved=True, **extra):
    base = {"product": product, "channel": "c", "apply_form": "f",
            "amount_band": "a", "age_band": "20代", "gender": "女",
            "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}
    base.update(extra)
    return base


def build_model():
    recs = [rec("X", 1) for _ in range(30)] + [rec("Y", 0) for _ in range(90)]
    return fit.fit_model(recs)


class TestScore(unittest.TestCase):
    def test_high_risk_product_scores_higher_than_low(self):
        model = build_model()
        high = score.score_record(rec("X", None, resolved=False), model)
        low = score.score_record(rec("Y", None, resolved=False), model)
        self.assertGreater(high["risk"], low["risk"])
        self.assertEqual(high["band"], "high")

    def test_hit_factors_top3_sorted_by_impact(self):
        model = build_model()
        out = score.score_record(rec("X", None, resolved=False), model)
        self.assertLessEqual(len(out["hit_factors"]), 3)
        impacts = [abs(f["odds_ratio"] - 1) for f in out["hit_factors"]]
        self.assertEqual(impacts, sorted(impacts, reverse=True))
        self.assertEqual(out["hit_factors"][0]["direction"], "up")

    def test_risk_between_0_and_1(self):
        model = build_model()
        out = score.score_record(rec("X", None, resolved=False), model)
        self.assertTrue(0.0 <= out["risk"] <= 1.0)

    def test_low_n_factor_flagged_reference(self):
        recs = [rec("X", 1)] + [rec("Y", 0) for _ in range(60)]
        model = fit.fit_model(recs)
        out = score.score_record(rec("X", None, resolved=False), model)
        x_hit = [f for f in out["hit_factors"] if f["field"] == "product" and f["value"] == "X"]
        self.assertTrue(x_hit and x_hit[0]["reference"])


class TestDisplayPct(unittest.TestCase):
    def test_saturated_risk_caps_at_99_not_100(self):
        self.assertEqual(score.display_pct(0.99999), 99.0)
        self.assertEqual(score.display_pct(1.0), 99.0)

    def test_near_zero_risk_floors_at_0_1_not_0(self):
        self.assertEqual(score.display_pct(0.0000001), 0.1)
        self.assertEqual(score.display_pct(0.0), 0.1)

    def test_mid_risk_unaffected(self):
        self.assertEqual(score.display_pct(0.4321), 43.2)


class TestBandOfReachability(unittest.TestCase):
    def test_low_base_rate_mid_risk_is_med(self):
        # base_rate=0.1 -> high_cut=0.2, low_cut=0.1 (unchanged from before the ceiling)
        self.assertEqual(score.band_of(0.15, 0.1), "med")
        self.assertEqual(score.band_of(0.25, 0.1), "high")
        self.assertEqual(score.band_of(0.05, 0.1), "low")

    def test_high_base_rate_high_risk_still_reachable(self):
        # base_rate=0.6 -> naive high_cut would be 1.2 (unreachable). Ceiling caps it at 0.9.
        self.assertEqual(score.band_of(0.95, 0.6), "high")

    def test_high_base_rate_below_ceiling_is_not_high(self):
        # low_cut=0.6, high_cut=min(1.2, 0.9)=0.9 -> 0.75 falls in the med band
        self.assertEqual(score.band_of(0.75, 0.6), "med")


if __name__ == "__main__":
    unittest.main()
