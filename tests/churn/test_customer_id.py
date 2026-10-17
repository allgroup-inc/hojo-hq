import unittest
from datetime import date
from scripts.churn import schema

COLUMN_MAP = {
    "customer_id": "顧客ID", "apply_id": "申込ID", "apply_date": "申込日",
    "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}


def raw(**over):
    base = {"顧客ID": "C1", "申込ID": "A1", "申込日": "2026-01-01", "商品": "X",
            "集客": "催事", "申込形態": "対面", "金額": "5000", "年齢": "25",
            "性別": "女", "地域": "那覇", "営業担当": "S1", "解約日": "", "解約理由": ""}
    base.update(over)
    return base


class TestCustomerId(unittest.TestCase):
    def test_customer_id_extracted(self):
        r = schema.normalize_record(raw(), COLUMN_MAP, date(2026, 3, 1))
        self.assertEqual(r["customer_id"], "C1")

    def test_customer_id_absent_is_none(self):
        cmap = {k: v for k, v in COLUMN_MAP.items() if k != "customer_id"}
        r = schema.normalize_record(raw(), cmap, date(2026, 3, 1))
        self.assertIsNone(r["customer_id"])


if __name__ == "__main__":
    unittest.main()
