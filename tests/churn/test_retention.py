import json
import os
import tempfile
import unittest
from datetime import date

from scripts.churn.retention import purge_snapshots


def _make_snapshot(root, month, rows=3):
    d = os.path.join(root, month)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "apps.csv"), "w", encoding="utf-8") as f:
        f.write("a,b\n" + "\n".join("1,2" for _ in range(rows)) + "\n")
    manifest = {"snapshot_id": f"snapshot:{month}", "as_of_month": month,
                "files": [{"file": "apps.csv", "rows": rows, "sha256": "deadbeef"}]}
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)
    return d


class TestRetention(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_dry_run_lists_expired_without_deleting(self):
        old = _make_snapshot(self.root, "2019-01")
        recent = _make_snapshot(self.root, "2026-06")
        rep = purge_snapshots(self.root, date(2026, 8, 1), retention_years=6, apply=False)
        self.assertEqual(rep["expired"], ["2019-01"])
        self.assertEqual(rep["deleted"], [])
        self.assertTrue(os.path.exists(old))     # ドライランでは消さない
        self.assertTrue(os.path.exists(recent))

    def test_apply_deletes_expired_and_keeps_recent(self):
        old = _make_snapshot(self.root, "2019-01")
        recent = _make_snapshot(self.root, "2026-06")
        rep = purge_snapshots(self.root, date(2026, 8, 1), retention_years=6, apply=True)
        self.assertEqual(rep["deleted"], ["2019-01"])
        self.assertFalse(os.path.exists(old))    # 実削除
        self.assertTrue(os.path.exists(recent))

    def test_boundary_exactly_at_retention_is_expired(self):
        # 2020-08 は 6年後=2026-08 に満期。as_of 2026-08 で満期到達＝削除対象
        _make_snapshot(self.root, "2020-08")
        rep = purge_snapshots(self.root, date(2026, 8, 1), retention_years=6, apply=False)
        self.assertIn("2020-08", rep["expired"])

    def test_apply_writes_pii_free_audit_log(self):
        _make_snapshot(self.root, "2019-01")
        purge_snapshots(self.root, date(2026, 8, 1), retention_years=6, apply=True)
        log_path = os.path.join(self.root, "deletion_log.json")
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)
        self.assertEqual(log[0]["month"], "2019-01")
        self.assertEqual(log[0]["purged_as_of"], "2026-08-01")
        self.assertEqual(log[0]["files"][0]["rows"], 3)

    def test_idempotent_second_apply_is_noop(self):
        _make_snapshot(self.root, "2019-01")
        purge_snapshots(self.root, date(2026, 8, 1), retention_years=6, apply=True)
        rep2 = purge_snapshots(self.root, date(2026, 8, 1), retention_years=6, apply=True)
        self.assertEqual(rep2["deleted"], [])   # 既に無い＝べき等


if __name__ == "__main__":
    unittest.main()
