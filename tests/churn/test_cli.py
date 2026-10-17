import unittest
import tempfile
import os
import json
from scripts.churn import cli

COLUMN_MAP = {
    "apply_id": "申込ID", "apply_date": "申込日", "product": "商品",
    "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}

# X商品は解約多め、Y商品は継続。末尾に継続中(6ヶ月未満)の採点対象を2件。
def make_csv():
    lines = ["申込ID,申込日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由"]
    for i in range(40):
        lines.append(f"X{i},2025-01-01,X,催事,対面,5000,25,女,那覇,S1,2025-03-01,高い")
        lines.append(f"Y{i},2025-01-01,Y,紹介,オンライン,8000,42,男,浦添,S2,,")
    lines.append("NEW_X,2026-06-01,X,催事,対面,5000,25,女,那覇,S1,,")
    lines.append("NEW_Y,2026-06-01,Y,紹介,オンライン,8000,42,男,浦添,S2,,")
    return "\n".join(lines) + "\n"


class TestCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.csv = os.path.join(self.dir, "data.csv")
        self.cmap = os.path.join(self.dir, "map.json")
        self.model = os.path.join(self.dir, "model.json")
        with open(self.csv, "w", encoding="utf-8") as f:
            f.write(make_csv())
        with open(self.cmap, "w", encoding="utf-8") as f:
            json.dump(COLUMN_MAP, f, ensure_ascii=False)

    def test_fit_then_score_produces_list(self):
        cli.main(["fit", "--csv", self.csv, "--column-map", self.cmap,
                  "--model", self.model, "--as-of", "2026-07-25"])
        self.assertTrue(os.path.exists(self.model))
        prefix = os.path.join(self.dir, "list")
        n = cli.cmd_score(self.csv, self.cmap, self.model, prefix, "2026-07-25")
        self.assertEqual(n, 2)  # 採点対象は NEW_X, NEW_Y
        self.assertTrue(os.path.exists(prefix + ".csv"))
        self.assertTrue(os.path.exists(prefix + ".html"))

    def test_backtest_returns_metrics(self):
        m = cli.cmd_backtest(self.csv, self.cmap, "2025-06-01", "2026-07-25")
        self.assertIn("auc", m)

    def test_cmd_card_writes_html_for_existing_apply_id(self):
        cli.cmd_fit(self.csv, self.cmap, self.model, "2026-07-25")
        out_path = os.path.join(self.dir, "card.html")
        card = cli.cmd_card(self.csv, self.cmap, self.model, "NEW_X", out_path, "2026-07-25")
        self.assertEqual(card["apply_id"], "NEW_X")
        self.assertTrue(os.path.exists(out_path))
        with open(out_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("NEW_X", content)

    def test_cmd_report_writes_html(self):
        out_path = os.path.join(self.dir, "report.html")
        sections = cli.cmd_report(self.csv, self.cmap, out_path, "2026-07-25")
        self.assertTrue(os.path.exists(out_path))
        self.assertTrue(sections)
        with open(out_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("解約傾向レポート", content)


if __name__ == "__main__":
    unittest.main()
