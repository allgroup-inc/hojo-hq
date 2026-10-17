import hashlib
import math
import unittest

from datetime import date

from scripts.churn.experiment import (
    assign_arm, wilson_interval, uplift, assignment_ledger,
    compare_naive_vs_controlled, max_consecutive_streak, imminent_lapse_uplift,
    relapse_uplift,
)


def _u(cid):
    """テスト用の決定的な一様乱数[0,1)（実装とは独立に成果を仕込む）。"""
    h = hashlib.md5(("outcome|" + cid).encode()).hexdigest()
    return int(h[:16], 16) / 16 ** 16


def _matured(cid, churn):
    return {"customer_id": cid, "is_resolved": True, "is_early_churn": churn}


class TestAssign(unittest.TestCase):
    def test_deterministic_and_valued(self):
        a = assign_arm("C123")
        self.assertIn(a, ("先行", "後発"))
        self.assertEqual(a, assign_arm("C123"))  # 実行間で不変

    def test_splits_by_fraction(self):
        ids = [f"E{i}" for i in range(3000)]
        half = sum(1 for c in ids if assign_arm(c, 0.5) == "先行")
        self.assertTrue(0.45 < half / 3000 < 0.55)
        third = sum(1 for c in ids if assign_arm(c, 0.3) == "先行")
        self.assertTrue(0.25 < third / 3000 < 0.35)

    def test_salt_changes_assignment(self):
        ids = [f"E{i}" for i in range(2000)]
        diff = sum(1 for c in ids if assign_arm(c, 0.5, "waveA") != assign_arm(c, 0.5, "waveB"))
        self.assertGreater(diff, 200)  # 別ウェーブでは割付が変わる

    def test_ledger_counts(self):
        ids = [f"E{i}" for i in range(100)]
        led = assignment_ledger(ids, 0.5)
        self.assertEqual(led["先行"] + led["後発"], 100)
        self.assertEqual(led["total"], 100)


class TestWilson(unittest.TestCase):
    def test_basic_bounds(self):
        lo, hi = wilson_interval(5, 10)
        self.assertTrue(0.0 < lo < 0.5 < hi < 1.0)

    def test_zero_events_nonneg(self):
        lo, hi = wilson_interval(0, 10)
        self.assertGreaterEqual(lo, 0.0)
        self.assertLess(hi, 1.0)

    def test_empty(self):
        self.assertEqual(wilson_interval(0, 0), (0.0, 0.0))


class TestUplift(unittest.TestCase):
    def _recs(self, treat_rate, ctrl_rate, n=3000):
        recs = []
        for i in range(n):
            cid = f"E{i}"
            arm = assign_arm(cid)
            rate = treat_rate if arm == "先行" else ctrl_rate
            recs.append(_matured(cid, 1 if _u(cid) < rate else 0))
        return recs

    def test_positive_uplift_when_treatment_reduces_churn(self):
        # 先行群(介入)=5% / 後発群(対照)=15% → diff=対照−介入 は正、CIは0を跨がない
        res = uplift(self._recs(0.05, 0.15))
        self.assertGreater(res["diff"], 0.0)
        self.assertGreater(res["diff_ci"][0], 0.0)     # 下限>0＝有意に減少
        self.assertFalse(res["reference"])
        self.assertGreaterEqual(res["diff"], res["diff_ci"][0])
        self.assertLessEqual(res["diff"], res["diff_ci"][1])

    def test_zero_effect_ci_spans_zero(self):
        res = uplift(self._recs(0.10, 0.10))
        self.assertLessEqual(res["diff_ci"][0], 0.0)
        self.assertGreaterEqual(res["diff_ci"][1], 0.0)  # 効果なし＝CIが0を含む

    def test_small_sample_is_reference(self):
        recs = [_matured("A", 0), _matured("B", 1), _matured("C", 0)]
        res = uplift(recs)
        self.assertTrue(res["reference"])   # 母数不足は参考

    def test_ignores_unresolved(self):
        recs = [{"customer_id": "X", "is_resolved": False, "is_early_churn": 1}]
        res = uplift(recs)
        self.assertEqual(res["n_treat"] + res["n_ctrl"], 0)


class TestCompare(unittest.TestCase):
    def test_places_both_and_concludes_with_controlled(self):
        recs = []
        for i in range(3000):
            cid = f"E{i}"
            arm = assign_arm(cid)
            rate = 0.05 if arm == "先行" else 0.15
            recs.append({"customer_id": cid, "apply_id": None,
                         "apply_date": date(2025, 1, 1), "cancel_date": None,
                         "is_resolved": True, "is_early_churn": 1 if _u(cid) < rate else 0})
        out = compare_naive_vs_controlled(recs, [], date(2026, 2, 1))
        self.assertIn("naive", out)
        self.assertIn("controlled", out)
        self.assertEqual(out["conclusion_uses"], "controlled")
        self.assertGreater(out["controlled"]["diff"], 0.0)


class TestMaxStreak(unittest.TestCase):
    def test_counts_longest_consecutive_run(self):
        # (2026,5),(6),(7) は3連続。(2026,2) は離れている＝別run
        self.assertEqual(max_consecutive_streak(
            [(2026, 2), (2026, 5), (2026, 6), (2026, 7)]), 3)

    def test_year_wrap_consecutive(self):
        self.assertEqual(max_consecutive_streak([(2025, 12), (2026, 1)]), 2)

    def test_empty_and_single(self):
        self.assertEqual(max_consecutive_streak([]), 0)
        self.assertEqual(max_consecutive_streak([(2026, 7)]), 1)

    def test_dedupes(self):
        self.assertEqual(max_consecutive_streak([(2026, 7), (2026, 7), (2026, 8)]), 2)


class TestImminentLapseUplift(unittest.TestCase):
    """A1: 未払消滅目前(最長未収連続>=3)だけを対象に先行/後発の早期解約率差を測る。"""
    def test_restricts_to_streak_population(self):
        recs = []
        # streak>=3（対象）: 先行=解約なし / 後発=解約 を仕込む
        for i in range(60):
            cid = f"S{i}"
            arm = assign_arm(cid)
            churn = 0 if arm == "先行" else 1
            recs.append({"customer_id": cid, "is_resolved": True, "is_early_churn": churn,
                         "unpaid_months": [(2026, 5), (2026, 6), (2026, 7)]})
        # streak<3（対象外・全員解約）＝結果に混ざってはいけない
        for i in range(40):
            recs.append({"customer_id": f"N{i}", "is_resolved": True, "is_early_churn": 1,
                         "unpaid_months": [(2026, 7)]})
        out = imminent_lapse_uplift(recs, min_streak=3)
        # 対象は streak>=3 の60件のみ（100件ではない）
        self.assertEqual(out["n_treat"] + out["n_ctrl"], 60)
        self.assertGreater(out["diff"], 0.0)   # 後発の方が解約多い＝先行で減った

    def test_no_target_is_empty(self):
        recs = [{"customer_id": "N1", "is_resolved": True, "is_early_churn": 1,
                 "unpaid_months": [(2026, 7)]}]
        out = imminent_lapse_uplift(recs, min_streak=3)
        self.assertEqual(out["n_treat"] + out["n_ctrl"], 0)


class TestRelapseUplift(unittest.TestCase):
    """決定1: 再発履歴(未収エピソード>=2)だけを対象に、先行/後発の早期解約率差を測る。"""
    def test_restricts_to_relapse_population(self):
        recs = []
        for i in range(60):
            cid = f"R{i}"
            arm = assign_arm(cid)
            churn = 0 if arm == "先行" else 1
            # 5月未収→7月未収（6月に解消のギャップ）＝再発履歴（2エピソード）
            recs.append({"customer_id": cid, "is_resolved": True, "is_early_churn": churn,
                         "unpaid_months": [(2026, 5), (2026, 7)]})
        # 単発エピソード（連続のみ）＝対象外・全員解約
        for i in range(40):
            recs.append({"customer_id": f"C{i}", "is_resolved": True, "is_early_churn": 1,
                         "unpaid_months": [(2026, 6), (2026, 7)]})
        out = relapse_uplift(recs)
        self.assertEqual(out["n_treat"] + out["n_ctrl"], 60)   # 再発60件のみ
        self.assertGreater(out["diff"], 0.0)

    def test_no_relapse_is_empty(self):
        recs = [{"customer_id": "C1", "is_resolved": True, "is_early_churn": 1,
                 "unpaid_months": [(2026, 6), (2026, 7)]}]   # 連続のみ＝再発でない
        self.assertEqual(relapse_uplift(recs)["n_treat"], 0)


if __name__ == "__main__":
    unittest.main()
