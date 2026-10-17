import csv
import os
import tempfile
import unittest

from scripts.churn import gen_synthetic


class TestGenSyntheticDialogFields(unittest.TestCase):
    """合成データが対話ログ（訪問保全）の列を出すことの構造ガード。

    教育ループ（dialog/talkscript）を合成データで実演できる状態を守る回帰テスト。
    値の学習（効いた返し方の復元）は seed 依存なのでここでは検証しない（構造のみ）。
    """

    def test_actions_csv_has_dialog_columns(self):
        with tempfile.TemporaryDirectory() as d:
            gen_synthetic.gen(d, seed=42, layout="real")
            with open(os.path.join(d, "actions.csv"), encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertTrue(rows)
        for col in ("接触手段", "懸念", "返し方", "次アクション"):
            self.assertIn(col, rows[0], f"{col} 列がない")
        # 接触した保全ログには対話タグが入る（空でない）
        self.assertTrue(any(r["懸念"] and r["返し方"] for r in rows))

    def test_planted_signal_definitions_consistent(self):
        # 教育カードの仕込み（CONCERN_BEST）が返し方の語彙に含まれること。
        for concern, best in gen_synthetic.CONCERN_BEST.items():
            self.assertIn(concern, gen_synthetic.CONCERNS)
            self.assertIn(best, gen_synthetic.APPROACH_FACTOR)


if __name__ == "__main__":
    unittest.main()
