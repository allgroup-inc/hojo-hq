import unittest
from scripts.churn import precommit_pii_guard as g


class TestPiiGuard(unittest.TestCase):
    def test_flags_private_dir(self):
        blocked = g.find_blocked_paths(["private/data.csv", "scripts/churn/fit.py"])
        self.assertEqual([p for p, _ in blocked], ["private/data.csv"])

    def test_flags_data_model_and_karte(self):
        paths = ["export.csv", "dir/risk_model.json", "out/karte_C1.html",
                 "book.xlsx", "site/fukugiiro/area/aguni/index.html", "docs/x.md",
                 "scripts/churn/karte.py"]
        flagged = [p for p, _ in g.find_blocked_paths(paths)]
        self.assertIn("export.csv", flagged)
        self.assertIn("dir/risk_model.json", flagged)
        self.assertIn("out/karte_C1.html", flagged)
        self.assertIn("book.xlsx", flagged)
        # 正規サイトの index.html / コード / ドキュメントは検知しない(誤検知防止)
        self.assertNotIn("site/fukugiiro/area/aguni/index.html", flagged)
        self.assertNotIn("docs/x.md", flagged)
        self.assertNotIn("scripts/churn/karte.py", flagged)

    def test_allowlist_lets_intentional_paths_through(self):
        blocked = g.find_blocked_paths(["sample.csv"], allow=["sample.csv"])
        self.assertEqual(blocked, [])

    def test_reason_is_human_readable(self):
        blocked = g.find_blocked_paths(["private/x"])
        self.assertTrue(blocked and "private/" in blocked[0][1])

    def test_content_scan_flags_customer_header_line(self):
        # 顧客データの列見出しらしき行(3個以上の該当列名)を検知する
        text = "現ステータス,契約日,生年月日,保険料,保険会社\n継続,2020-01-01,1980-05-05,5000,X社\n"
        self.assertIsNotNone(g.scan_content("list.txt", text))

    def test_content_scan_ignores_prose_and_code(self):
        # 単発の言及や通常のコードは検知しない
        self.assertIsNone(g.scan_content("notes.txt", "生年月日は年代にビン化する方針です。\n"))
        self.assertIsNone(g.scan_content("app.py", "def f():\n    return 1\n"))

    def test_content_scan_exempts_docs_and_scripts_and_tests(self):
        # docs/・scripts/・tests/ は設計文書やコードで該当語が並ぶため走査対象外
        header = "現ステータス,契約日,生年月日,保険料,保険会社\n"
        self.assertIsNone(g.scan_content("docs/x.md", header))
        self.assertIsNone(g.scan_content("scripts/churn/precommit_pii_guard.py", header))
        self.assertIsNone(g.scan_content("tests/churn/test_x.py", header))


if __name__ == "__main__":
    unittest.main()
