import unittest
from datetime import date, timedelta

from scripts.churn.timing import call_timing, call_timing_list

AS_OF = date(2026, 8, 1)
# ヤマ=契約後15〜30日 のハザード（手動構築）
HAZARD = {"rows": [{"lo": 0, "hi": 15, "count": 1},
                   {"lo": 15, "hi": 30, "count": 5},
                   {"lo": 30, "hi": 45, "count": 1}], "total": 7, "reference": False}


def cont(cid, tenure_days):
    return {"is_scoreable": True, "customer_id": cid, "apply_id": cid,
            "product": "医療", "agent_id": "S1",
            "apply_date": AS_OF - timedelta(days=tenure_days)}


class TestCallTiming(unittest.TestCase):
    def test_in_window_is_optimal(self):
        # lead=7 → 架電窓 [8,30]。経過10日はヤマ手前の窓内＝架電適期
        t = call_timing(cont("A", 10), AS_OF, HAZARD, lead_days=7)
        self.assertEqual(t["status"], "架電適期")

    def test_before_window_reports_days_to_window(self):
        t = call_timing(cont("B", 3), AS_OF, HAZARD, lead_days=7)
        self.assertEqual(t["status"], "適期前")
        self.assertEqual(t["days_to_window"], 5)   # 窓開始8 - 経過3

    def test_after_peak_is_late(self):
        t = call_timing(cont("C", 40), AS_OF, HAZARD, lead_days=7)
        self.assertEqual(t["status"], "適期後")

    def test_not_scoreable_is_none(self):
        r = cont("D", 10); r["is_scoreable"] = False
        self.assertIsNone(call_timing(r, AS_OF, HAZARD, lead_days=7))

    def test_no_hazard_peak_is_none(self):
        empty = {"rows": [{"lo": 0, "hi": 15, "count": 0}], "total": 0, "reference": True}
        self.assertIsNone(call_timing(cont("E", 10), AS_OF, empty, lead_days=7))

    def test_list_sorts_optimal_first(self):
        recs = [cont("late", 40), cont("opt", 10), cont("before", 3)]
        rows = call_timing_list(recs, AS_OF, HAZARD, lead_days=7)
        self.assertEqual(rows[0]["customer_id"], "opt")       # 架電適期が先頭
        self.assertEqual([r["status"] for r in rows][0], "架電適期")


if __name__ == "__main__":
    unittest.main()
