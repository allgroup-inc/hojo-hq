import unittest
from datetime import date
from scripts.churn import schema
from scripts.churn.config import AMOUNT_EDGES

COLUMN_MAP = {
    "apply_id": "申込ID", "apply_date": "申込日", "product": "商品",
    "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}


def raw(**over):
    base = {"申込ID": "A1", "申込日": "2026-01-01", "商品": "X", "集客": "催事",
            "申込形態": "対面", "金額": "5,000円", "年齢": "25", "性別": "女",
            "地域": "那覇", "営業担当": "S1", "解約日": "", "解約理由": ""}
    base.update(over)
    return base


class TestSchema(unittest.TestCase):
    def test_bin_age(self):
        self.assertEqual(schema.bin_age(25), "20代")
        self.assertEqual(schema.bin_age(None), "不明")

    def test_bin_amount(self):
        self.assertEqual(schema.bin_amount(5000, AMOUNT_EDGES), "3千〜1万")
        self.assertEqual(schema.bin_amount(None, AMOUNT_EDGES), "不明")

    def test_parse_amount_strips_symbols(self):
        self.assertEqual(schema.parse_amount("5,000円"), 5000.0)
        self.assertIsNone(schema.parse_amount(""))

    def test_early_churn_within_6_months(self):
        r = schema.normalize_record(raw(解約日="2026-04-01"), COLUMN_MAP, date(2026, 7, 25))
        self.assertEqual(r["is_early_churn"], 1)
        self.assertTrue(r["is_resolved"])
        self.assertFalse(r["is_scoreable"])

    def test_late_cancel_is_not_early_churn(self):
        r = schema.normalize_record(raw(解約日="2026-09-01"), COLUMN_MAP, date(2026, 12, 1))
        self.assertEqual(r["is_early_churn"], 0)
        self.assertTrue(r["is_resolved"])

    def test_survived_active_past_6_months(self):
        r = schema.normalize_record(raw(), COLUMN_MAP, date(2026, 8, 1))
        self.assertEqual(r["is_early_churn"], 0)
        self.assertTrue(r["is_resolved"])
        self.assertFalse(r["is_scoreable"])

    def test_active_under_6_months_is_scoreable_not_resolved(self):
        r = schema.normalize_record(raw(), COLUMN_MAP, date(2026, 3, 1))
        self.assertIsNone(r["is_early_churn"])
        self.assertFalse(r["is_resolved"])
        self.assertTrue(r["is_scoreable"])

    def test_prevention_fields_normalized(self):
        cmap = dict(COLUMN_MAP, account_daily="口座普段使い",
                    debit_result="初回引落結果", debit_due="引落予定日")
        r = schema.normalize_record(
            raw(口座普段使い="いいえ", 初回引落結果="不着", 引落予定日="2026-09-01"),
            cmap, date(2026, 7, 25))
        self.assertEqual(r["account_daily"], "いいえ")
        self.assertEqual(r["debit_result"], "不着")
        self.assertEqual(r["debit_due"], date(2026, 9, 1))

    def test_prevention_fields_absent_default(self):
        r = schema.normalize_record(raw(), COLUMN_MAP, date(2026, 8, 1))
        self.assertEqual(r["account_daily"], "")
        self.assertEqual(r["debit_result"], "")
        self.assertIsNone(r["debit_due"])


if __name__ == "__main__":
    unittest.main()
