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


if __name__ == "__main__":
    unittest.main()
