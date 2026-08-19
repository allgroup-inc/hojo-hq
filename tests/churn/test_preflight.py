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
        # 3行目は顧客ID空（未紐付）＝母集団外に除外 → 継続中だが scoreable に数えない（徳元さん 2026-08-18）
        self.assertEqual(rep["n_scoreable"], 0)

    def test_report_is_pii_free_and_serializable(self):
        csv = _write(self.d, FULL_HEADER, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担"])
        rep = preflight_report(csv, CMAP, AS_OF)
        # 顧客値を含まない集計レポート（JSON化できる・件数と列名のみ）
        json.dumps(rep, ensure_ascii=False)
        self.assertNotIn("C1", json.dumps(rep, ensure_ascii=False))

    def test_account_flag_unexpected_counted_but_not_blocking(self):
        # 口座普段使いフラグは「はい/いいえ/未確認」想定。想定外の値は件数だけ警告（okは落とさない）
        header = FULL_HEADER + ",口座普段使い"
        cmap = dict(CMAP, account_daily="口座普段使い")
        rows = ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担,はい",
                "C2,2025-01-01,学資,紹介,継続,5000,40,男,名護,S2,,,たまに使う",  # 想定外
                "C3,2025-01-01,医療,ネット,単発,5000,30,女,那覇,S1,,,"]           # 空=未入力は数えない
        csv = _write(self.d, header, rows)
        rep = preflight_report(csv, cmap, AS_OF)
        self.assertEqual(rep["account_flag_unexpected"], 1)
        self.assertTrue(rep["ok"])  # 警告であって停止条件ではない
        self.assertNotIn("たまに使う", json.dumps(rep, ensure_ascii=False))  # 値は出さない

    def test_account_flag_absent_is_zero(self):
        # 口座列が無い/未マッピングなら 0（予防用は任意）
        csv = _write(self.d, FULL_HEADER, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担"])
        rep = preflight_report(csv, CMAP, AS_OF)
        self.assertEqual(rep["account_flag_unexpected"], 0)

    def test_name_mapping_is_blocked(self):
        # 前提: 顧客名は持ち込まずID管理。氏名系キーをマップしたら門前で不可
        header = FULL_HEADER + ",氏名"
        cmap = dict(CMAP, 氏名="氏名")
        csv = _write(self.d, header, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担,山田太郎"])
        rep = preflight_report(csv, cmap, AS_OF)
        self.assertIn("氏名", rep["forbidden_name_keys"])
        self.assertFalse(rep["ok"])
        self.assertNotIn("山田太郎", json.dumps(rep, ensure_ascii=False))  # 値は出さない

    def test_english_name_key_blocked_case_insensitive(self):
        cmap = dict(CMAP, Customer_Name="お名前")
        csv = _write(self.d, FULL_HEADER, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担"])
        rep = preflight_report(csv, cmap, AS_OF)
        self.assertIn("Customer_Name", rep["forbidden_name_keys"])
        self.assertFalse(rep["ok"])

    def test_no_name_key_is_clean(self):
        csv = _write(self.d, FULL_HEADER, ["C1,2025-01-01,医療,ネット,単発,5000,25,女,那覇,S1,2025-03-01,負担"])
        rep = preflight_report(csv, CMAP, AS_OF)
        self.assertEqual(rep["forbidden_name_keys"], [])


if __name__ == "__main__":
    unittest.main()
