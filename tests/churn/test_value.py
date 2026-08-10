import unittest
from scripts.churn.value import saveable


class TestValue(unittest.TestCase):
    def test_saveable_is_risk_times_annual_premium(self):
        # リスク50% × 月額1万 ×12ヶ月 = 6万円
        self.assertEqual(saveable(0.5, 10000), 60000.0)

    def test_saveable_missing_amount_is_zero(self):
        self.assertEqual(saveable(0.5, None), 0.0)

    def test_saveable_zero_risk_is_zero(self):
        self.assertEqual(saveable(0.0, 10000), 0.0)


if __name__ == "__main__":
    unittest.main()
