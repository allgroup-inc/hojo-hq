import unittest
import tempfile
import os
from datetime import date
from scripts.churn import intake

COLUMN_MAP = {
    "apply_id": "申込ID", "apply_date": "申込日", "product": "商品",
    "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}

CSV = (
    "申込ID,申込日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由\n"
    "A1,2026-01-01,X,催事,対面,5000,25,女,那覇,S1,2026-03-01,高い\n"
    "A2,2026-01-10,Y,紹介,オンライン,8000,42,男,浦添,S2,,\n"
)


class TestIntake(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(CSV)

    def tearDown(self):
        os.remove(self.path)

    def test_read_rows(self):
        rows = intake.read_rows(self.path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["商品"], "X")

    def test_load_records_normalizes(self):
        recs = intake.load_records(self.path, COLUMN_MAP, date(2026, 7, 25))
        self.assertEqual(recs[0]["is_early_churn"], 1)
        self.assertEqual(recs[1]["product"], "Y")


if __name__ == "__main__":
    unittest.main()
