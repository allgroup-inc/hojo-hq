import unittest
import tempfile
import os
from datetime import date
from scripts.churn import interactions

IMAP = {"customer_id": "顧客ID", "date": "接触日", "kind": "種別",
        "agent": "担当", "content": "案内内容", "memo": "メモ"}

CSV = (
    "顧客ID,接触日,種別,担当,案内内容,メモ\n"
    "C1,2026-02-01,電話,東さん,医療保険の見直し,不在\n"
    "C1,2026-03-05,追加案内,東さん,がん保険の提案,前向き\n"
)


class TestInteractions(unittest.TestCase):
    def test_normalize_kind(self):
        self.assertEqual(interactions.normalize_kind("電話"), "架電")
        self.assertEqual(interactions.normalize_kind("謎の種別"), "謎の種別")
        self.assertEqual(interactions.normalize_kind(""), "その他")

    def test_normalize_interaction(self):
        raw = {"顧客ID": "C1", "接触日": "2026-02-01", "種別": "電話",
               "担当": "東さん", "案内内容": "見直し", "メモ": "不在"}
        r = interactions.normalize_interaction(raw, IMAP)
        self.assertEqual(r["customer_id"], "C1")
        self.assertEqual(r["date"], date(2026, 2, 1))
        self.assertEqual(r["kind"], "架電")
        self.assertEqual(r["agent"], "東さん")

    def test_load_interactions(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(CSV)
        try:
            recs = interactions.load_interactions(path, IMAP)
            self.assertEqual(len(recs), 2)
            self.assertEqual(recs[1]["kind"], "追加案内")
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
