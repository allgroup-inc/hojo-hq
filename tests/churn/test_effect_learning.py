import os
import tempfile
import unittest
from datetime import date

from scripts.churn.contact_log import load_contacts
from scripts.churn.effect_learning import effect, learning

MB = date(2026, 2, 1)  # これより前の契約＝6ヶ月窓が完全に経過（成熟）


def R(cid, apply, early, cancel=None):
    return {"customer_id": cid, "apply_date": apply, "cancel_date": cancel,
            "is_resolved": True, "is_early_churn": early}


def K(cid, apply, contact, action):
    return {"customer_id": cid, "apply_date": apply, "contact_date": contact, "action": action}


class TestEffect(unittest.TestCase):
    def test_contacted_vs_not(self):
        recs = [R("A", date(2025, 1, 1), 0), R("B", date(2025, 1, 1), 0),
                R("C", date(2025, 1, 1), 1, date(2025, 3, 1)),
                R("D", date(2025, 1, 1), 1, date(2025, 3, 1))]
        contacts = [K("A", date(2025, 1, 1), date(2025, 2, 1), "口座確認"),
                    K("B", date(2025, 1, 1), date(2025, 2, 1), "減額提案")]
        e = effect(recs, contacts, MB)
        self.assertEqual((e["n_c"], e["rate_c"]), (2, 0.0))
        self.assertEqual((e["n_n"], e["rate_n"]), (2, 1.0))

    def test_immature_cohort_excluded(self):
        # 契約が MB 以降＝観測未確定 → 効果測定から除外
        recs = [R("E", date(2026, 5, 1), 1, date(2026, 6, 1))]
        contacts = [K("E", date(2026, 5, 1), date(2026, 5, 10), "口座確認")]
        e = effect(recs, contacts, MB)
        self.assertEqual(e["n_c"] + e["n_n"], 0)

    def test_post_cancel_contact_not_counted_as_contacted(self):
        # 解約後の接触は「あり」に数えない（免疫時間バイアス回避）→ なし群へ
        recs = [R("F", date(2025, 1, 1), 1, date(2025, 3, 1))]
        contacts = [K("F", date(2025, 1, 1), date(2025, 4, 1), "再説明")]  # 解約後
        e = effect(recs, contacts, MB)
        self.assertEqual(e["n_c"], 0)
        self.assertEqual(e["n_n"], 1)


class TestLearning(unittest.TestCase):
    def test_per_action_rate_sorted_and_reference(self):
        # 口座確認=解約0/2、再説明=解約2/2。少件数は参考。低い順に並ぶ。
        recs = [R("A", date(2025, 1, 1), 0), R("B", date(2025, 1, 1), 0),
                R("C", date(2025, 1, 1), 1, date(2025, 3, 1)),
                R("D", date(2025, 1, 1), 1, date(2025, 3, 1))]
        contacts = [K("A", date(2025, 1, 1), date(2025, 2, 1), "口座確認"),
                    K("B", date(2025, 1, 1), date(2025, 2, 1), "口座確認"),
                    K("C", date(2025, 1, 1), date(2025, 2, 1), "再説明"),
                    K("D", date(2025, 1, 1), date(2025, 2, 1), "再説明")]
        rows = learning(recs, contacts, MB)
        self.assertEqual(rows[0]["action"], "口座確認")
        self.assertEqual(rows[0]["rate"], 0.0)
        self.assertEqual(rows[-1]["action"], "再説明")
        self.assertTrue(rows[0]["reference"])  # n=2 < MIN_RELIABLE_N


class TestContactLog(unittest.TestCase):
    def test_load_parses_dates(self):
        cmap = {"customer_id": "顧客ID", "apply_date": "契約日", "contact_date": "接触日",
                "action": "対応内容", "result": "結果区分", "reaction": "顧客反応"}
        content = ("顧客ID,契約日,接触日,対応内容,結果区分,顧客反応\n"
                   "C1,2025-01-01,2025-02-01,口座確認,つながった,継続\n")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "actions.csv")
            open(p, "w", encoding="utf-8").write(content)
            rows = load_contacts(p, cmap)
        self.assertEqual(rows[0]["customer_id"], "C1")
        self.assertEqual(rows[0]["apply_date"], date(2025, 1, 1))
        self.assertEqual(rows[0]["contact_date"], date(2025, 2, 1))
        self.assertEqual(rows[0]["action"], "口座確認")


if __name__ == "__main__":
    unittest.main()
