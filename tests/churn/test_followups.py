import unittest
import tempfile
import os
from datetime import date
from scripts.churn import followups


def cust(cid, needs, last):
    return {"customer_id": cid, "needs_followup": needs, "last_contact_date": last,
            "max_risk_band": "high", "n_active": 1, "age_band": "20代",
            "area": "那覇", "n_applications": 1}


class TestFollowups(unittest.TestCase):
    def test_list_only_needs_followup_sorted_oldest_first(self):
        customers = {
            "A": cust("A", True, date(2026, 3, 1)),
            "B": cust("B", False, date(2026, 3, 20)),
            "C": cust("C", True, None),   # 接触なし → 最優先
        }
        rows = followups.list_followups(customers)
        self.assertEqual([r["customer_id"] for r in rows], ["C", "A"])

    def test_render_html(self):
        rows = followups.list_followups({"A": cust("A", True, date(2026, 3, 1))})
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            followups.render_html(rows, path)
            with open(path, encoding="utf-8") as f:
                self.assertIn("A", f.read())
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
