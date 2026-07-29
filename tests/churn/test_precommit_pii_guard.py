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


if __name__ == "__main__":
    unittest.main()
