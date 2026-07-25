import unittest
from scripts.churn import report_agg


def rec(agent, early, resolved=True):
    return {"agent_id": agent, "is_resolved": resolved, "is_early_churn": early}


class TestReportAgg(unittest.TestCase):
    def test_aggregate_by_agent_sorted_by_rate(self):
        recs = [rec("S1", 1), rec("S1", 1), rec("S2", 0), rec("S2", 0),
                rec("S3", None, resolved=False)]  # 未成熟は無視
        rows = report_agg.aggregate_by(recs, "agent_id")
        self.assertEqual(rows[0]["value"], "S1")
        self.assertAlmostEqual(rows[0]["churn_rate"], 1.0)
        self.assertEqual(sum(r["n"] for r in rows), 4)

    def test_effect_compare_diff(self):
        followed = [rec("S1", 0), rec("S1", 0), rec("S1", 1)]      # 1/3
        not_followed = [rec("S2", 1), rec("S2", 1), rec("S2", 0)]  # 2/3
        out = report_agg.effect_compare(followed, not_followed)
        self.assertAlmostEqual(out["followed_rate"], 1 / 3, places=6)
        self.assertAlmostEqual(out["not_followed_rate"], 2 / 3, places=6)
        self.assertAlmostEqual(out["diff"], -1 / 3, places=6)


if __name__ == "__main__":
    unittest.main()
