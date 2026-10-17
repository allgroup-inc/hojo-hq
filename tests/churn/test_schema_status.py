import unittest
from datetime import date
from scripts.churn.schema import normalize_record

AS_OF = date(2026, 8, 1)
# status列ありの実データ想定 column_map
CMAP = {"customer_id": "顧客ID", "apply_date": "契約日", "cancel_date": "初回保険料着金日",
        "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
        "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
        "status": "現ステータス", "payment_route": "払込経路"}


def raw(status, keiyaku="2026-01-05", chakkin=""):
    return {"顧客ID": "K1", "契約日": keiyaku, "初回保険料着金日": chakkin,
            "商品": "医療", "集客": "ネット", "申込形態": "単発", "金額": "5000",
            "年齢": "30", "性別": "女", "地域": "那覇", "営業担当": "S1",
            "現ステータス": status, "払込経路": "口座振替"}


class TestSchemaStatus(unittest.TestCase):
    def test_seiritsu_matured_is_survivor(self):
        r = normalize_record(raw("成立済"), CMAP, AS_OF)  # 2026-01→6ヶ月経過
        self.assertEqual(r["is_early_churn"], 0)
        self.assertTrue(r["is_resolved"])
        self.assertEqual(r["status_category"], "継続")
        self.assertTrue(r["in_scope"])

    def test_seiritsu_with_chakkin_is_not_cancel(self):
        # 成立済で初回保険料着金日が入っていても解約日として使わない
        r = normalize_record(raw("成立済", chakkin="2026-02-01"), CMAP, AS_OF)
        self.assertEqual(r["is_early_churn"], 0)
        self.assertIsNone(r["cancel_date"])   # 成立済は着金日を解約日にしない

    def test_early_cancel_within_6mo(self):
        r = normalize_record(raw("成立後CAN【解約】", chakkin="2026-03-01"), CMAP, AS_OF)
        self.assertEqual(r["is_early_churn"], 1)
        self.assertTrue(r["is_resolved"])

    def test_unpaid_no_date_is_early_flagged(self):
        r = normalize_record(raw("不成立【引受後未入金】", chakkin=""), CMAP, AS_OF)
        self.assertEqual(r["is_early_churn"], 1)
        self.assertTrue(r["date_missing"])

    def test_death_is_excluded(self):
        r = normalize_record(raw("死亡解約", chakkin="2026-03-01"), CMAP, AS_OF)
        self.assertFalse(r["in_scope"])
        self.assertEqual(r["excluded_reason"], "死亡")
        self.assertFalse(r["is_resolved"])
        self.assertFalse(r["is_scoreable"])

    def test_out_of_scope(self):
        r = normalize_record(raw("謝絶"), CMAP, AS_OF)
        self.assertFalse(r["in_scope"])
        self.assertEqual(r["status_category"], "母集団外")

    def test_unpaid_column_parsed_into_record(self):
        cmap = dict(CMAP, unpaid="Ⅳ")
        row = raw("成立済"); row["Ⅳ"] = "●未26⑦⑥済未26⑥"
        r = normalize_record(row, cmap, AS_OF)
        self.assertEqual(r["unpaid_count"], 2)
        self.assertEqual(r["unpaid_band"], "2+")
        self.assertTrue(r["unpaid_contacted"])
        self.assertTrue(r["unpaid_konbini"])

    def test_no_unpaid_column_defaults_zero(self):
        r = normalize_record(raw("成立済"), CMAP, AS_OF)   # Ⅳ未マップ
        self.assertEqual(r["unpaid_count"], 0)
        self.assertEqual(r["unpaid_band"], "0")

    def test_backward_compatible_without_status(self):
        # status列が無いcolumn_mapなら従来どおり（cancel_date基準）
        cmap = {k: v for k, v in CMAP.items() if k != "status"}
        row = raw("成立後CAN【解約】", chakkin="2026-03-01")
        r = normalize_record(row, cmap, AS_OF)
        self.assertEqual(r["is_early_churn"], 1)      # 着金日=解約日として2ヶ月→早期
        self.assertTrue(r["in_scope"])                 # status無しは全てin_scope
        self.assertIsNone(r["status_category"])


if __name__ == "__main__":
    unittest.main()
