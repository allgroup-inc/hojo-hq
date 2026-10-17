import unittest
from datetime import date

from scripts.churn.playbook import segment_playbook

MB = date(2026, 2, 1)  # これより前の契約＝成熟


def R(cid, early, cancel=None, product="医療", reason=""):
    return {"customer_id": cid, "apply_id": cid, "apply_date": date(2025, 1, 1),
            "cancel_date": cancel, "is_resolved": True, "is_early_churn": early,
            "product": product, "cancel_reason": reason}


def K(cid, action):
    return {"customer_id": cid, "apply_id": cid, "apply_date": date(2025, 1, 1),
            "contact_date": date(2025, 2, 1), "action": action}


class TestPlaybook(unittest.TestCase):
    def _data(self):
        recs, cons = [], []
        # 医療: 減額提案=解約0（効く） / 様子見=解約1・理由「負担」（効かない）
        for i in range(6):
            recs.append(R(f"G{i}", 0, product="医療"))
            cons.append(K(f"G{i}", "減額提案"))
        for i in range(6):
            recs.append(R(f"B{i}", 1, cancel=date(2025, 3, 1), product="医療", reason="負担"))
            cons.append(K(f"B{i}", "様子見"))
        return recs, cons

    def test_recommends_effective_action_per_segment(self):
        recs, cons = self._data()
        rows = {r["segment"]: r for r in segment_playbook(recs, cons, MB, segment_field="product")}
        med = rows["医療"]
        self.assertEqual(med["recommended_action"], "減額提案")  # 最も解約率が低い一手
        self.assertEqual(med["action_rate"], 0.0)

    def test_surfaces_top_cancel_reason(self):
        recs, cons = self._data()
        rows = {r["segment"]: r for r in segment_playbook(recs, cons, MB, segment_field="product")}
        self.assertEqual(rows["医療"]["top_reason"], "負担")
        self.assertEqual(rows["医療"]["reason_count"], 6)

    def test_small_sample_marked_reference(self):
        recs = [R("A", 0), R("B", 1, cancel=date(2025, 3, 1), reason="負担")]
        cons = [K("A", "減額提案"), K("B", "様子見")]
        rows = {r["segment"]: r for r in segment_playbook(recs, cons, MB, segment_field="product")}
        self.assertTrue(rows["医療"]["reference"])   # n< MIN_RELIABLE_N

    def test_segments_split_by_field(self):
        recs = [R("A", 0, product="医療"), R("B", 0, product="学資")]
        cons = [K("A", "減額提案"), K("B", "再説明")]
        segs = {r["segment"] for r in segment_playbook(recs, cons, MB, segment_field="product")}
        self.assertEqual(segs, {"医療", "学資"})


if __name__ == "__main__":
    unittest.main()
