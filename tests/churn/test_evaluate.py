import unittest
from datetime import date
from scripts.churn import evaluate


class TestEvaluate(unittest.TestCase):
    def test_auc_perfect_separation(self):
        pairs = [(0.9, 1), (0.8, 1), (0.2, 0), (0.1, 0)]
        self.assertAlmostEqual(evaluate.auc(pairs), 1.0, places=6)

    def test_auc_single_class_is_half(self):
        self.assertEqual(evaluate.auc([(0.9, 1), (0.8, 1)]), 0.5)

    def test_split_by_apply_date(self):
        recs = [
            {"apply_date": date(2025, 1, 1), "is_resolved": True},
            {"apply_date": date(2026, 6, 1), "is_resolved": True},
            {"apply_date": date(2026, 6, 1), "is_resolved": False},  # 未成熟は除外
        ]
        train, test = evaluate.split_by_apply_date(recs, date(2026, 1, 1))
        self.assertEqual(len(train), 1)
        self.assertEqual(len(test), 1)

    def test_backtest_reports_metrics(self):
        def r(product, early, apply_d):
            return {"product": product, "channel": "c", "apply_form": "f",
                    "amount_band": "a", "age_band": "20代", "gender": "女",
                    "area": "那覇", "agent_id": "S1", "apply_date": apply_d,
                    "is_resolved": True, "is_early_churn": early}
        recs = ([r("X", 1, date(2025, i % 12 + 1, 1)) for i in range(40)]
                + [r("Y", 0, date(2025, i % 12 + 1, 1)) for i in range(40)]
                + [r("X", 1, date(2026, 6, 1)) for _ in range(10)]
                + [r("Y", 0, date(2026, 6, 1)) for _ in range(10)])
        m = evaluate.backtest(recs, date(2026, 1, 1))
        self.assertEqual(m["n_test"], 20)
        self.assertGreaterEqual(m["auc"], 0.8)  # X/Yで綺麗に分かれる
        # 较正と精度@キャパも返す
        self.assertIn("ece", m)
        self.assertIn("precision_at_capacity", m)
        self.assertTrue(0.0 <= m["precision_at_capacity"] <= 1.0)


class TestCalibration(unittest.TestCase):
    def test_perfect_calibration_low_ece(self):
        # 予測=実測に近い → ECE小さい
        scored = ([(0.1, 0)] * 9 + [(0.1, 1)] * 1        # 予測10%・実測10%
                  + [(0.9, 1)] * 9 + [(0.9, 0)] * 1)     # 予測90%・実測90%
        rows, ece = evaluate.calibration(scored, bins=10)
        self.assertLess(ece, 0.05)
        self.assertEqual(sum(r["n"] for r in rows), 20)

    def test_miscalibration_high_ece_warns(self):
        # 予測90%なのに誰も解約しない → ECE大
        scored = [(0.9, 0)] * 20
        rows, ece = evaluate.calibration(scored, bins=10)
        self.assertGreater(ece, 0.5)

    def test_precision_at_capacity_takes_top_k(self):
        scored = [(0.9, 1), (0.8, 1), (0.7, 0), (0.2, 0), (0.1, 1)]
        # 上位3件の実解約率 = (1+1+0)/3
        self.assertAlmostEqual(evaluate.precision_at_capacity(scored, 3), 2 / 3, places=6)

    def test_precision_at_capacity_empty(self):
        self.assertEqual(evaluate.precision_at_capacity([], 3), 0.0)


if __name__ == "__main__":
    unittest.main()
