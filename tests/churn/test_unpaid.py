import unittest
from scripts.churn.unpaid import parse_unpaid, bin_unpaid_count


class TestParseUnpaid(unittest.TestCase):
    def test_year_and_months(self):
        u = parse_unpaid("未26⑦⑥")
        self.assertEqual(u["unpaid_count"], 2)
        self.assertIn((2026, 7), u["unpaid_months"])
        self.assertIn((2026, 6), u["unpaid_months"])
        self.assertTrue(u["parse_ok"])

    def test_markers(self):
        u = parse_unpaid("●未26⑦⑥済未26⑥●未26③")
        self.assertEqual(u["unpaid_count"], 3)          # (26,7)(26,6)(26,3) 重複除去
        self.assertTrue(u["contacted"])                  # 済
        self.assertTrue(u["konbini_sent"])               # ●
        self.assertFalse(u["account_issue"])

    def test_account_issue_and_no_year(self):
        u = parse_unpaid("済未⑤★")
        self.assertTrue(u["account_issue"])              # ★
        self.assertTrue(u["contacted"])
        self.assertEqual(u["unpaid_count"], 1)           # (None,5)

    def test_two_years(self):
        u = parse_unpaid("未26①未25⑫")
        self.assertEqual(u["unpaid_count"], 2)
        self.assertIn((2026, 1), u["unpaid_months"])
        self.assertIn((2025, 12), u["unpaid_months"])

    def test_dedup_same_month(self):
        u = parse_unpaid("未26⑦未26⑦⑥")
        self.assertEqual(u["unpaid_count"], 2)           # (26,7)(26,6)

    def test_empty(self):
        for v in ("", None):
            u = parse_unpaid(v)
            self.assertEqual(u["unpaid_count"], 0)
            self.assertFalse(u["contacted"])
            self.assertTrue(u["parse_ok"])

    def test_ten_eleven_twelve(self):
        u = parse_unpaid("未25⑫⑪⑩")
        self.assertEqual(set(u["unpaid_months"]), {(2025, 12), (2025, 11), (2025, 10)})

    def test_unknown_token_flags_not_ok(self):
        u = parse_unpaid("未26⑦？")
        self.assertFalse(u["parse_ok"])                  # 未知トークンは監査に残す
        self.assertEqual(u["unpaid_count"], 1)           # 拾えた分は拾う


class TestBin(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(bin_unpaid_count(0), "0")
        self.assertEqual(bin_unpaid_count(1), "1")
        self.assertEqual(bin_unpaid_count(2), "2+")
        self.assertEqual(bin_unpaid_count(5), "2+")


if __name__ == "__main__":
    unittest.main()
