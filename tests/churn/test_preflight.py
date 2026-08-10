import json
import os
import tempfile
import unittest
from datetime import date
from scripts.churn.preflight import preflight_report

# 実列に近い最小ヘッダ（必須列を揃える）
FULL_HEADER = "顧客ID,契約日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由"
CMAP = {"customer_id": "顧客ID", "apply_date": "契約日", "product": "商品",
        "channel": "集客", "apply_form": "申込形態", "amount": "金額", "age": "年齢",
        "gender": "性別", "area": "地域", "agent_id": "営業担当",
        "cancel_date": "解約日", "cancel_reason": "解約理由"}
AS_OF = date(2026, 8, 1)


def _write(dirpath, header, rows):
    p = os.path.join(dirpath, "apps.csv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join([header] + rows) + "\n")
    return p


class TestPreflight(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_missing_column_detected(self):
        # ヘッダに「営業担当」が無い → 対応列が見つからず ok=False
        header = "顧客ID,契約日,商品,集客,申込形態,金額,年齢,性別,地域,解約日,解約理由"
        csv = _write(self.d, header, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,2025-03-01,負担"])
        rep = preflight_report(csv, CMAP, AS_OF)
        self.assertIn("営業担当", rep["missing_columns"])
        self.assertFalse(rep["ok"])

    def test_missing_key_detected(self):
        cmap = {k: v for k, v in CMAP.items() if k != "agent_id"}
        csv = _write(self.d, FULL_HEADER, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担"])
        rep = preflight_report(csv, cmap, AS_OF)
        self.assertIn("agent_id", rep["missing_keys"])
        self.assertFalse(rep["ok"])

    def test_unparseable_date_reported(self):
        csv = _write(self.d, FULL_HEADER, ["C1,毎月,医療,ネット,単発,5000,25,女,那覇,S1,,"])
        rep = preflight_report(csv, CMAP, AS_OF)
        self.assertGreaterEqual(rep["date_parse_fails"]["apply_date"], 1)
        self.assertFalse(rep["ok"])

    def test_counts_when_valid(self):
        rows = ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担",
                "C2,2025-01-01,学資,紹介,継続,5000,40,男,名護,S2,,",
                ",2026-07-01,医療,ネット,単発,5000,25,女,那覇,S1,,"]  # 未紐付
        csv = _write(self.d, FULL_HEADER, rows)
        rep = preflight_report(csv, CMAP, AS_OF)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["n_total"], 3)
        self.assertEqual(rep["n_unlinked"], 1)
        self.assertEqual(rep["n_resolved"], 2)      # C1(解約)・C2(成熟生存)
        self.assertEqual(rep["n_scoreable"], 1)     # 2026-07 継続中

    def test_report_is_pii_free_and_serializable(self):
        csv = _write(self.d, FULL_HEADER, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担"])
        rep = preflight_report(csv, CMAP, AS_OF)
        # 顧客値を含まない集計レポート（JSON化できる・件数と列名のみ）
        json.dumps(rep, ensure_ascii=False)
        self.assertNotIn("C1", json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
