import unittest
from datetime import date

from scripts.churn.relapse import unpaid_episodes, is_relapse, relapse_candidates

AS_OF = date(2026, 8, 1)


def rec(cid, months, scoreable=True, cat="継続", amount=5000):
    return {"customer_id": cid, "apply_id": None, "product": "医療", "agent_id": "S1",
            "amount": amount, "is_scoreable": scoreable, "status_category": cat,
            "unpaid_months": months}


class TestEpisodes(unittest.TestCase):
    def test_splits_consecutive_runs(self):
        # 5,6月＝run1  /  8月＝run2（7月は解消＝ギャップ）
        eps = unpaid_episodes([(2026, 5), (2026, 6), (2026, 8)])
        self.assertEqual(eps, [[(2026, 5), (2026, 6)], [(2026, 8)]])

    def test_year_wrap_consecutive(self):
        self.assertEqual(unpaid_episodes([(2025, 12), (2026, 1)]), [[(2025, 12), (2026, 1)]])

    def test_drops_yearless_and_dedupes(self):
        eps = unpaid_episodes([(None, 5), (2026, 6), (2026, 6)])
        self.assertEqual(eps, [[(2026, 6)]])

    def test_empty(self):
        self.assertEqual(unpaid_episodes([]), [])


class TestIsRelapse(unittest.TestCase):
    def test_two_episodes_recent_is_relapse(self):
        # 5,6月未収→7月解消→8月また未収（直近）＝再発
        self.assertTrue(is_relapse(rec("A", [(2026, 5), (2026, 6), (2026, 8)]), AS_OF))

    def test_single_episode_is_not_relapse(self):
        # 連続だけ（解消をはさまない）＝再発ではない（未収連鎖トリガーの領域）
        self.assertFalse(is_relapse(rec("B", [(2026, 6), (2026, 7)]), AS_OF))

    def test_old_relapse_excluded_by_recency(self):
        # 2エピソードあるが最新が半年以上前＝いま再発中ではない
        self.assertFalse(is_relapse(rec("C", [(2026, 1), (2026, 2), (2026, 4)]), AS_OF))

    def test_not_active_excluded(self):
        r = rec("D", [(2026, 5), (2026, 6), (2026, 8)], scoreable=False, cat="母集団外")
        self.assertFalse(is_relapse(r, AS_OF))


class TestRelapseCandidates(unittest.TestCase):
    def test_lists_and_sorts_by_episodes_then_amount(self):
        recs = [
            rec("A", [(2026, 5), (2026, 8)], amount=3000),                 # 2エピソード
            rec("B", [(2026, 2), (2026, 5), (2026, 8)], amount=1000),      # 3エピソード（上位）
            rec("Z", [(2026, 6), (2026, 7)]),                             # 連続のみ＝除外
        ]
        out = relapse_candidates(recs, AS_OF)
        self.assertEqual([c["customer_id"] for c in out], ["B", "A"])
        self.assertEqual(out[0]["episodes"], 3)
        self.assertEqual(out[0]["last_unpaid"], (2026, 8))


if __name__ == "__main__":
    unittest.main()
