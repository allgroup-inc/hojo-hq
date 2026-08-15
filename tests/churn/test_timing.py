import unittest
from datetime import date

from scripts.churn.timing import churn_hazard_by_tenure, peak_window


def churner(days):
    """契約→解約が days 日の、成熟した早期解約レコード。"""
    ad = date(2025, 1, 1)
    cd = date.fromordinal(ad.toordinal() + days)
    return {"apply_date": ad, "cancel_date": cd, "is_resolved": True, "is_early_churn": 1}


def survivor():
    return {"apply_date": date(2025, 1, 1), "cancel_date": None,
            "is_resolved": True, "is_early_churn": 0}


class TestHazard(unittest.TestCase):
    def test_buckets_and_shares(self):
        recs = [churner(5), churner(10), churner(20), churner(40)]  # bkt0:2 bkt1:1 bkt2:1
        h = churn_hazard_by_tenure(recs, bucket_days=15)
        self.assertEqual(h["total"], 4)
        self.assertEqual(h["rows"][0]["count"], 2)
        self.assertAlmostEqual(h["rows"][0]["share"], 0.5)
        self.assertEqual((h["rows"][0]["lo"], h["rows"][0]["hi"]), (0, 15))
        self.assertEqual(h["rows"][1]["count"], 1)   # 15-30
        self.assertEqual(h["rows"][2]["count"], 1)   # 30-45

    def test_ignores_survivors_and_continuing(self):
        recs = [churner(5), survivor(),
                {"apply_date": date(2026, 7, 1), "cancel_date": None,
                 "is_resolved": False, "is_early_churn": None}]  # 継続中
        h = churn_hazard_by_tenure(recs, bucket_days=15)
        self.assertEqual(h["total"], 1)

    def test_cumulative_share_reaches_one(self):
        recs = [churner(5), churner(20), churner(40)]
        h = churn_hazard_by_tenure(recs, bucket_days=15)
        nonzero = [r for r in h["rows"] if r["count"]]
        self.assertAlmostEqual(nonzero[-1]["cum_share"], 1.0)

    def test_small_sample_is_reference(self):
        recs = [churner(5), churner(10)]
        h = churn_hazard_by_tenure(recs, bucket_days=15)
        self.assertTrue(h["reference"])   # 2 < MIN_RELIABLE_N

    def test_peak_window_is_densest_bucket(self):
        recs = [churner(5), churner(10), churner(12), churner(40)]  # bkt0 が最多
        h = churn_hazard_by_tenure(recs, bucket_days=15)
        self.assertEqual(peak_window(h), (0, 15))


if __name__ == "__main__":
    unittest.main()
