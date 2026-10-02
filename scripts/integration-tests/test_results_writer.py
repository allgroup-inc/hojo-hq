"""results_writer のユニットテスト(サーバー不要・オフラインで実行できる)。

python3 -m unittest scripts/integration-tests/test_results_writer.py
"""
import json
import tempfile
import unittest
from pathlib import Path

import results_writer as rw


class WriteResult(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "results"

    def test_ファイル名はnameそのまま_jsonで書かれる(self):
        path = rw.write_result(self.dir, "business-axis", passed=True, passed_count=10, total=10)
        self.assertEqual(path, self.dir / "business-axis.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "business-axis")
        self.assertIs(data["passed"], True)
        self.assertEqual(data["passed_count"], 10)
        self.assertIn("timestamp", data)

    def test_ディレクトリが無ければ作る(self):
        self.assertFalse(self.dir.exists())
        rw.write_result(self.dir, "api-chain", passed=False, passed_count=2, total=6)
        self.assertTrue((self.dir / "api-chain.json").exists())

    def test_passedはboolに正規化される(self):
        path = rw.write_result(self.dir, "ui", passed=0)
        self.assertIs(json.loads(path.read_text(encoding="utf-8"))["passed"], False)


class PerformanceSummary(unittest.TestCase):
    def test_最悪P95と合算エラー率で判定する(self):
        results = [
            {"endpoint": "/a", "p95_ms": 400.0, "errors": 0, "total_requests": 100},
            {"endpoint": "/b", "p95_ms": 1200.0, "errors": 3, "total_requests": 100},
        ]
        s = rw.summarize_performance(results)
        self.assertEqual(s["p95_ms"], 1200.0)
        self.assertAlmostEqual(s["error_rate"], 0.015)
        self.assertIs(s["passed"], False)

    def test_基準内ならpassed(self):
        results = [{"endpoint": "/a", "p95_ms": 900.0, "errors": 1, "total_requests": 200}]
        s = rw.summarize_performance(results)
        self.assertIs(s["passed"], True)

    def test_計測ゼロ件は不合格として扱う(self):
        s = rw.summarize_performance([])
        self.assertIs(s["passed"], False)
        self.assertEqual(s["total_requests"], 0)


class PlaywrightSummary(unittest.TestCase):
    def test_playwright_json_reporterの件数を読む(self):
        report = {"stats": {"expected": 11, "unexpected": 1, "skipped": 0, "flaky": 0}}
        s = rw.summarize_playwright(report)
        self.assertEqual(s["passed_count"], 11)
        self.assertEqual(s["failed_count"], 1)
        self.assertEqual(s["total"], 12)
        self.assertIs(s["passed"], False)

    def test_statsが無ければ不合格(self):
        s = rw.summarize_playwright({})
        self.assertIs(s["passed"], False)
        self.assertEqual(s["total"], 0)


if __name__ == "__main__":
    unittest.main()
