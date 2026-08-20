import os
import tempfile
import unittest

from scripts.churn.contact_log import append_contact, load_contacts

CMAP = {"customer_id": "顧客ID", "contact_date": "接触日", "medium": "接触手段",
        "concern": "懸念", "approach": "返し方", "result": "結果区分",
        "next_action": "次アクション"}


class TestAppendContact(unittest.TestCase):
    def test_creates_file_with_header_then_roundtrips(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "contacts.csv")
            append_contact(p, CMAP, {"customer_id": "C1", "contact_date": "2026-08-18",
                                     "medium": "架電", "concern": "保険料負担",
                                     "approach": "家計の見直し提案", "result": "検討中",
                                     "next_action": "再架電"})
            self.assertTrue(os.path.exists(p))
            rows = load_contacts(p, CMAP)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["customer_id"], "C1")
            self.assertEqual(rows[0]["concern"], "保険料負担")
            self.assertEqual(rows[0]["result"], "検討中")

    def test_appends_second_row_without_duplicating_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "contacts.csv")
            append_contact(p, CMAP, {"customer_id": "C1", "contact_date": "2026-08-18",
                                     "result": "つながった"})
            append_contact(p, CMAP, {"customer_id": "C2", "contact_date": "2026-08-18",
                                     "result": "入金いただけた"})
            rows = load_contacts(p, CMAP)
            self.assertEqual([r["customer_id"] for r in rows], ["C1", "C2"])
            with open(p, encoding="utf-8-sig") as f:
                self.assertEqual(sum(1 for _ in f), 3)   # header + 2 rows

    def test_missing_values_are_blank_not_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "contacts.csv")
            append_contact(p, CMAP, {"customer_id": "C9", "contact_date": "2026-08-18"})
            rows = load_contacts(p, CMAP)
            self.assertEqual(rows[0]["concern"], "")   # 未指定は空


if __name__ == "__main__":
    unittest.main()
