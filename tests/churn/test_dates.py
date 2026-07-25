import unittest
from datetime import date
from scripts.churn.dates import add_months, has_reached_months, is_within_months


class TestDates(unittest.TestCase):
    def test_add_months_simple(self):
        self.assertEqual(add_months(date(2026, 1, 15), 6), date(2026, 7, 15))

    def test_add_months_clamps_end_of_month(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_add_months_crosses_year(self):
        self.assertEqual(add_months(date(2025, 10, 10), 6), date(2026, 4, 10))

    def test_has_reached_months_true_on_boundary(self):
        self.assertTrue(has_reached_months(date(2026, 1, 1), date(2026, 7, 1), 6))

    def test_has_reached_months_false_before(self):
        self.assertFalse(has_reached_months(date(2026, 1, 1), date(2026, 6, 30), 6))

    def test_is_within_months_inclusive_boundary(self):
        self.assertTrue(is_within_months(date(2026, 1, 1), date(2026, 7, 1), 6))

    def test_is_within_months_excludes_after(self):
        self.assertFalse(is_within_months(date(2026, 1, 1), date(2026, 7, 2), 6))


if __name__ == "__main__":
    unittest.main()
