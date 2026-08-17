import unittest
from scripts.churn.transitions import status_transitions


def rec(cid, aid, cat, unpaid):
    return {"customer_id": cid, "apply_id": aid, "status_category": cat, "unpaid_count": unpaid}


class TestTransitions(unittest.TestCase):
    def _data(self):
        prev = [rec("A", "a1", "継続", 2),   # 前月：未収で継続＝リスク
                rec("B", "b1", "継続", 1),   # リスク
                rec("C", "c1", "継続", 0),   # 未収なし＝対象外（前月リスクでない）
                rec("D", "d1", "継続", 3)]   # リスク
        curr = [rec("A", "a1", "継続", 0),   # 未収解消＝救えた
                rec("B", "b1", "早期解約", 2),  # 解約＝失った
                rec("C", "c1", "継続", 0),   # 前月リスクでない→集計外
                rec("D", "d1", "継続", 3)]   # 未収残＝継続(未収残)
        return prev, curr

    def test_counts(self):
        prev, curr = self._data()
        t = status_transitions(prev, curr)
        self.assertEqual(t["救えた"], 1)
        self.assertEqual(t["失った"], 1)
        self.assertEqual(t["継続(未収残)"], 1)
        self.assertAlmostEqual(t["recovery_rate"], 0.5)   # 救えた/(救えた+失った)

    def test_by_contact(self):
        prev, curr = self._data()
        contacted = {("A", "a1"), ("B", "b1")}   # AもBも保全接触あり
        t = status_transitions(prev, curr, contacted_keys=contacted)
        self.assertEqual(t["by_contact"]["接触あり"]["救えた"], 1)
        self.assertEqual(t["by_contact"]["接触あり"]["失った"], 1)
        self.assertEqual(t["by_contact"]["接触なし"]["救えた"], 0)

    def test_ignores_new_and_disappeared(self):
        prev = [rec("A", "a1", "継続", 2)]
        curr = [rec("Z", "z9", "継続", 0)]   # 前月に存在しない→集計外
        t = status_transitions(prev, curr)
        self.assertEqual(t["救えた"] + t["失った"] + t["継続(未収残)"], 0)

    def test_recovery_rate_none_when_no_resolved(self):
        prev = [rec("A", "a1", "継続", 2)]
        curr = [rec("A", "a1", "継続", 2)]   # 未収残のまま＝救えた/失った 0
        t = status_transitions(prev, curr)
        self.assertIsNone(t["recovery_rate"])   # 分母0＝算出不能（断定しない）


if __name__ == "__main__":
    unittest.main()
