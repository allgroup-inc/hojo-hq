import os
import tempfile
import unittest
from datetime import date

from scripts.churn.contact_log import load_contacts
from scripts.churn.dialog import dialog_effect

MB = date(2026, 2, 1)   # これより前の契約＝成熟


def R(cid, early, cancel=None):
    return {"customer_id": cid, "apply_id": cid, "apply_date": date(2025, 1, 1),
            "cancel_date": cancel, "is_resolved": True, "is_early_churn": early}


def K(cid, contact, approach="", concern="", medium=""):
    return {"customer_id": cid, "apply_id": cid, "apply_date": date(2025, 1, 1),
            "contact_date": contact, "action": "保全", "approach": approach,
            "concern": concern, "medium": medium}


class TestDialogEffect(unittest.TestCase):
    def test_effect_by_approach(self):
        # 返し方「家計の見直し提案」=解約0/2、「様子見」=解約2/2。低い順（効いた順）。
        recs = [R("A", 0), R("B", 0),
                R("C", 1, date(2025, 3, 1)), R("D", 1, date(2025, 3, 1))]
        cons = [K("A", date(2025, 2, 1), approach="家計の見直し提案"),
                K("B", date(2025, 2, 1), approach="家計の見直し提案"),
                K("C", date(2025, 2, 1), approach="様子見"),
                K("D", date(2025, 2, 1), approach="様子見")]
        rows = dialog_effect(recs, cons, MB, field="approach")
        self.assertEqual(rows[0]["value"], "家計の見直し提案")
        self.assertEqual(rows[0]["rate"], 0.0)
        self.assertEqual(rows[-1]["value"], "様子見")
        self.assertTrue(rows[0]["reference"])   # n=2 < MIN_RELIABLE_N

    def test_effect_by_concern(self):
        recs = [R("A", 0), R("C", 1, date(2025, 3, 1))]
        cons = [K("A", date(2025, 2, 1), concern="保険料負担"),
                K("C", date(2025, 2, 1), concern="必要性の疑問")]
        vals = {r["value"] for r in dialog_effect(recs, cons, MB, field="concern")}
        self.assertEqual(vals, {"保険料負担", "必要性の疑問"})

    def test_post_cancel_not_counted(self):
        recs = [R("X", 1, date(2025, 3, 1))]
        cons = [K("X", date(2025, 4, 1), approach="再説明")]   # 解約後
        self.assertEqual(dialog_effect(recs, cons, MB, field="approach"), [])

    def test_empty_value_skipped(self):
        recs = [R("A", 0)]
        cons = [K("A", date(2025, 2, 1), approach="")]         # 空タグは数えない
        self.assertEqual(dialog_effect(recs, cons, MB, field="approach"), [])


class TestContactLogExtended(unittest.TestCase):
    def test_parses_new_fields(self):
        cmap = {"customer_id": "顧客ID", "apply_date": "契約日", "contact_date": "接触日",
                "action": "対応内容", "medium": "接触手段", "concern": "懸念",
                "approach": "返し方", "next_action": "次アクション"}
        content = ("顧客ID,契約日,接触日,対応内容,接触手段,懸念,返し方,次アクション\n"
                   "C1,2025-01-01,2025-02-01,保全,訪問,保険料負担,家計の見直し提案,再訪問\n")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "log.csv")
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            rows = load_contacts(p, cmap)
        r = rows[0]
        self.assertEqual(r["medium"], "訪問")
        self.assertEqual(r["concern"], "保険料負担")
        self.assertEqual(r["approach"], "家計の見直し提案")
        self.assertEqual(r["next_action"], "再訪問")


if __name__ == "__main__":
    unittest.main()
