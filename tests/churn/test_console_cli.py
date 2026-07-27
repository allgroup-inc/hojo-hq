import unittest
import tempfile
import os
import json
from scripts.churn import cli

AMAP = {"customer_id": "顧客ID", "apply_id": "申込ID", "apply_date": "申込日",
        "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
        "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
        "cancel_date": "解約日", "cancel_reason": "解約理由"}
IMAP = {"customer_id": "顧客ID", "date": "接触日", "kind": "種別",
        "agent": "担当", "content": "案内内容", "memo": "メモ"}


def make_apps():
    lines = ["顧客ID,申込ID,申込日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由"]
    for i in range(30):
        lines.append(f"M{i},X{i},2025-01-01,X,催事,対面,5000,25,女,那覇,S1,2025-03-01,高い")
        lines.append(f"N{i},Y{i},2025-01-01,Y,紹介,オンライン,8000,42,男,浦添,S2,,")
    lines.append("C1,NEW1,2026-06-01,X,催事,対面,5000,25,女,那覇,S1,,")
    return "\n".join(lines) + "\n"


class TestConsoleCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.acsv = os.path.join(self.dir, "apps.csv")
        self.icsv = os.path.join(self.dir, "inter.csv")
        self.amap = os.path.join(self.dir, "amap.json")
        self.imap = os.path.join(self.dir, "imap.json")
        self.model = os.path.join(self.dir, "model.json")
        self.out = os.path.join(self.dir, "console")
        with open(self.acsv, "w", encoding="utf-8") as f:
            f.write(make_apps())
        with open(self.icsv, "w", encoding="utf-8") as f:
            f.write("顧客ID,接触日,種別,担当,案内内容,メモ\nC1,2026-06-10,架電,東さん,見直し,不在\n")
        json.dump(AMAP, open(self.amap, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(IMAP, open(self.imap, "w", encoding="utf-8"), ensure_ascii=False)

    def test_console_generates_index_and_kartes(self):
        cli.main(["fit", "--csv", self.acsv, "--column-map", self.amap,
                  "--model", self.model, "--as-of", "2026-07-26"])
        res = cli.cmd_console(self.acsv, self.amap, self.icsv, self.imap,
                              self.model, self.out, "2026-07-26")
        self.assertTrue(os.path.exists(os.path.join(self.out, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(self.out, "followups.html")))
        self.assertTrue(os.path.exists(os.path.join(self.out, "karte_C1.html")))
        self.assertGreaterEqual(res["n_kartes"], 1)
        with open(os.path.join(self.out, "index.html"), encoding="utf-8") as f:
            self.assertIn('href="karte_C1.html"', f.read())


if __name__ == "__main__":
    unittest.main()
