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


if __name__ == "__main__":
    unittest.main()
