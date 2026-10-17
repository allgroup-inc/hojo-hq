import json
import os
import tempfile
import unittest
from datetime import date
from scripts.churn.pipeline import run_pipeline

HEADER = ("顧客ID,契約日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由,"
          "口座普段使い,初回引落結果,引落予定日")
CMAP = {"customer_id": "顧客ID", "apply_id": "顧客ID", "apply_date": "契約日",
        "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
        "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
        "cancel_date": "解約日", "cancel_reason": "解約理由",
        "account_daily": "口座普段使い", "debit_result": "初回引落結果", "debit_due": "引落予定日"}


def _rows():
    r = []
    for i in range(5):
        r.append(f"K{i},2025-01-05,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担,,,")
    for i in range(5):
        r.append(f"S{i},2025-01-05,学資,紹介,継続,5000,40,男,名護,S2,,,,,")
    r.append("N1,2026-07-01,医療,ネット,単発,5000,25,女,那覇,S1,,,いいえ,不着,")
    return "\n".join([HEADER] + r) + "\n"


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.csv = os.path.join(self.d, "apps.csv")
        with open(self.csv, "w", encoding="utf-8") as f:
            f.write(_rows())
        self.cmap = os.path.join(self.d, "cmap.json")
        with open(self.cmap, "w", encoding="utf-8") as f:
            json.dump(CMAP, f, ensure_ascii=False)
        self.out = os.path.join(self.d, "out")

    def _run(self, **kw):
        return run_pipeline(self.csv, self.cmap, self.out, date(2026, 8, 1),
                            date(2025, 7, 1), "2026-08-01", notify=lambda *_: None, **kw)

    def test_auc_gate_stops_and_does_not_publish(self):
        st = self._run(auc_min=0.99)
        self.assertEqual(st["status"], "stopped_auc")
        self.assertIsNotNone(st["auc"])
        self.assertFalse(os.path.exists(os.path.join(self.out, "today.html")))

    def test_happy_path_completes_and_publishes(self):
        st = self._run(auc_min=0.0)
        self.assertEqual(st["status"], "completed")
        for f in ("list.csv", "today.html", "cohort.html"):
            self.assertTrue(os.path.exists(os.path.join(self.out, f)), f)
        self.assertIn("backtest", st["completed_steps"])

    def test_schema_invalid_stops(self):
        bad = {k: v for k, v in CMAP.items() if k != "agent_id"}
        badmap = os.path.join(self.d, "bad.json")
        with open(badmap, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
        st = run_pipeline(self.csv, badmap, self.out, date(2026, 8, 1),
                          date(2025, 7, 1), "2026-08-01", auc_min=0.0, notify=lambda *_: None)
        self.assertEqual(st["status"], "stopped_schema")

    def test_idempotent_skip_on_second_run(self):
        self._run(auc_min=0.0)
        st2 = self._run(auc_min=0.0)
        self.assertEqual(st2["status"], "completed")
        self.assertTrue(st2.get("idempotent_skip"))

    def test_initial_contact_surfaces_in_today_when_contacts_given(self):
        # 契約直後・未接触の継続契約 → 保全ログを渡すと today.html に「初動」が出る
        csv2 = os.path.join(self.d, "apps2.csv")
        rows = list(_rows().splitlines())
        # 2026-07-25 契約（as_of 2026-08-01 の7日前）・継続中・口座OK・引落問題なし＝初動のみ
        rows.append("R1,2026-07-25,医療,ネット,単発,5000,25,女,那覇,S1,,,はい,,")
        with open(csv2, "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
        cpath = os.path.join(self.d, "contacts.csv")
        with open(cpath, "w", encoding="utf-8") as f:
            f.write("顧客ID,契約日,接触日,対応内容\n")  # 接触ゼロ（未接触）
        cmap2 = os.path.join(self.d, "contactmap.json")
        with open(cmap2, "w", encoding="utf-8") as f:
            json.dump({"customer_id": "顧客ID", "apply_date": "契約日",
                       "contact_date": "接触日", "action": "対応内容"}, f, ensure_ascii=False)
        st = run_pipeline(csv2, self.cmap, os.path.join(self.d, "o2"), date(2026, 8, 1),
                          date(2025, 7, 1), "2026-08-01", auc_min=0.0, notify=lambda *_: None,
                          contacts_path=cpath, contact_map_path=cmap2)
        self.assertEqual(st["status"], "completed")
        with open(os.path.join(self.d, "o2", "today.html"), encoding="utf-8") as f:
            self.assertIn("初動", f.read())


if __name__ == "__main__":
    unittest.main()
