import unittest
import tempfile
import os
from scripts.churn import fit


def rec(product, early, resolved=True):
    return {"product": product, "channel": "c", "apply_form": "f",
            "amount_band": "a", "age_band": "20代", "gender": "女",
            "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}


class TestFit(unittest.TestCase):
    def test_base_rate_uses_resolved_only(self):
        recs = [rec("X", 1), rec("X", 0), rec("Y", 0),
                rec("Z", None, resolved=False)]  # 未成熟は除外
        model = fit.fit_model(recs)
        self.assertAlmostEqual(model["base_rate"], 1 / 3, places=6)
        self.assertEqual(model["n_resolved"], 3)

    def test_high_risk_factor_has_odds_ratio_above_one(self):
        recs = [rec("X", 1) for _ in range(40)] + [rec("Y", 0) for _ in range(40)]
        model = fit.fit_model(recs)
        self.assertGreater(model["factors"]["product"]["X"]["odds_ratio"], 1.0)
        self.assertLess(model["factors"]["product"]["Y"]["odds_ratio"], 1.0)

    def test_smoothing_pulls_small_n_toward_base(self):
        # Xは1件だけ全部解約。スムージングで rate は 1.0 より十分低い。
        recs = [rec("X", 1)] + [rec("Y", 0) for _ in range(40)] + [rec("Y", 1) for _ in range(10)]
        model = fit.fit_model(recs, smoothing_k=30)
        self.assertLess(model["factors"]["product"]["X"]["rate"], 0.6)
        self.assertEqual(model["factors"]["product"]["X"]["n"], 1)

    def test_save_and_load_roundtrip(self):
        model = fit.fit_model([rec("X", 1), rec("X", 0)])
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            fit.save_model(model, path)
            loaded = fit.load_model(path)
            self.assertEqual(loaded["n_resolved"], model["n_resolved"])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
