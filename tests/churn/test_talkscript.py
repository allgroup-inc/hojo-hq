import unittest
from datetime import date

from scripts.churn.talkscript import concern_playbook

MB = date(2026, 2, 1)


def R(cid, early, cancel=None):
    return {"customer_id": cid, "apply_id": cid, "apply_date": date(2025, 1, 1),
            "cancel_date": cancel, "is_resolved": True, "is_early_churn": early}


def K(cid, contact, concern, approach):
    return {"customer_id": cid, "apply_id": cid, "apply_date": date(2025, 1, 1),
            "contact_date": contact, "concern": concern, "approach": approach}


class TestConcernPlaybook(unittest.TestCase):
    def _data(self):
        recs, cons = [], []
        # 懸念「保険料負担」: 家計の見直し提案=解約0/2、様子見=解約2/2
        for cid, early in [("A", 0), ("B", 0)]:
            recs.append(R(cid, early))
            cons.append(K(cid, date(2025, 2, 1), "保険料負担", "家計の見直し提案"))
        for cid in ("C", "D"):
            recs.append(R(cid, 1, date(2025, 3, 1)))
            cons.append(K(cid, date(2025, 2, 1), "保険料負担", "様子見"))
        return recs, cons

    def test_best_approach_per_concern(self):
        recs, cons = self._data()
        rows = {r["concern"]: r for r in concern_playbook(recs, cons, MB)}
        card = rows["保険料負担"]
        self.assertEqual(card["best_approach"], "家計の見直し提案")   # 効いた返し方
        self.assertEqual(card["rate"], 0.0)
        self.assertTrue(card["reference"])                           # 少数=参考
        # 次点に様子見が入る
        self.assertIn("様子見", [a["approach"] for a in card["alternatives"]])

    def test_thin_lucky_cell_does_not_outrank_well_evidenced(self):
        # 「確実」= n=25 で解約1/25(4%)、「まぐれ」= n=2 で解約0/2(0%)。
        # 生率だと まぐれ(0%) が勝つが、少数の偶然で「効いた型」に祭り上げてはいけない。
        # 確信をもって低い（Wilson上限が低い）確実を best に選ぶ。
        recs, cons = [], []
        for i in range(25):
            cid = f"S{i}"
            recs.append(R(cid, 1 if i == 0 else 0, date(2025, 3, 1) if i == 0 else None))
            cons.append(K(cid, date(2025, 2, 1), "手続き不明", "確実"))
        for i in range(2):
            cid = f"L{i}"
            recs.append(R(cid, 0))
            cons.append(K(cid, date(2025, 2, 1), "手続き不明", "まぐれ"))
        card = {r["concern"]: r for r in concern_playbook(recs, cons, MB)}["手続き不明"]
        self.assertEqual(card["best_approach"], "確実")
        self.assertIn("まぐれ", [a["approach"] for a in card["alternatives"]])

    def test_post_cancel_pair_not_counted(self):
        recs = [R("X", 1, date(2025, 3, 1))]
        cons = [K("X", date(2025, 4, 1), "必要性", "再説明")]        # 解約後
        self.assertEqual(concern_playbook(recs, cons, MB), [])

    def test_requires_both_tags(self):
        recs = [R("A", 0)]
        cons = [{"customer_id": "A", "apply_id": "A", "apply_date": date(2025, 1, 1),
                 "contact_date": date(2025, 2, 1), "concern": "保険料負担", "approach": ""}]
        self.assertEqual(concern_playbook(recs, cons, MB), [])       # 片方空は数えない


if __name__ == "__main__":
    unittest.main()
