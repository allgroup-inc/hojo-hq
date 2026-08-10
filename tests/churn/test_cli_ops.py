import json
import os
import tempfile
import unittest
from scripts.churn.cli import main

HEADER = ("顧客ID,契約日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,"
          "解約日,解約理由,口座普段使い,初回引落結果,引落予定日")
CMAP = {"customer_id": "顧客ID", "apply_id": "顧客ID", "apply_date": "契約日",
        "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
        "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
        "cancel_date": "解約日", "cancel_reason": "解約理由",
        "account_daily": "口座普段使い", "debit_result": "初回引落結果", "debit_due": "引落予定日"}


def _rows():
    r = []
    # 成熟・解約（早期）3件 と 成熟・生存 3件（fit用）
    for i in range(3):
        r.append(f"K{i},2025-01-05,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担,,,")
    for i in range(3):
        r.append(f"S{i},2025-01-05,学資,紹介,継続,5000,40,男,名護,S2,,,,,")
    # 継続中・不着（today の候補）
    r.append("N1,2026-07-01,医療,ネット,単発,5000,25,女,那覇,S1,,,いいえ,不着,")
    # 継続中・引落前×口座いいえ
    r.append("A1,2026-07-10,医療,ネット,単発,5000,26,女,那覇,S1,,,いいえ,,2026-08-05")
    return "\n".join([HEADER] + r) + "\n"


class TestCliOps(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.csv = os.path.join(self.d, "apps.csv")
        with open(self.csv, "w", encoding="utf-8") as f:
            f.write(_rows())
        self.cmap = os.path.join(self.d, "cmap.json")
        with open(self.cmap, "w", encoding="utf-8") as f:
            json.dump(CMAP, f, ensure_ascii=False)

    def _read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_cohort_writes_output(self):
        out = os.path.join(self.d, "cohort.html")
        main(["cohort", "--csv", self.csv, "--column-map", self.cmap,
              "--out", out, "--as-of", "2026-08-01"])
        self.assertTrue(os.path.exists(out))
        self.assertIn("コホート", self._read(out))

    def test_snapshot_creates_dated_dir(self):
        outdir = os.path.join(self.d, "snap")
        main(["snapshot", "--csv", self.csv, "--month", "2026-08", "--out-dir", outdir])
        self.assertTrue(os.path.exists(os.path.join(outdir, "2026-08", "manifest.json")))

    def test_today_writes_output(self):
        model = os.path.join(self.d, "model.json")
        main(["fit", "--csv", self.csv, "--column-map", self.cmap,
              "--model", model, "--as-of", "2026-08-01"])
        out = os.path.join(self.d, "today.html")
        main(["today", "--csv", self.csv, "--column-map", self.cmap,
              "--model", model, "--out", out, "--as-of", "2026-08-01"])
        self.assertTrue(os.path.exists(out))
        self.assertIn("今日の要接触", self._read(out))


if __name__ == "__main__":
    unittest.main()
