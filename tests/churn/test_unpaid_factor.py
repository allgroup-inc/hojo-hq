import unittest
from datetime import date

from scripts.churn import fit
from scripts.churn.schema import normalize_record
from scripts.churn.score import score_record

AS_OF = date(2026, 8, 1)
CMAP = {"customer_id": "顧客ID", "apply_date": "契約日", "cancel_date": "初回保険料着金日",
        "status": "現ステータス", "unpaid": "Ⅳ", "payment_route": "払込経路",
        "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
        "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当"}


def row(status, iv, chakkin=""):
    return {"顧客ID": "K", "契約日": "2025-01-05", "初回保険料着金日": chakkin,
            "現ステータス": status, "Ⅳ": iv, "払込経路": "口座振替",
            "商品": "医療", "集客": "ネット", "申込形態": "単発", "金額": "5000",
            "年齢": "30", "性別": "女", "地域": "那覇", "営業担当": "S1"}


class TestUnpaidFactor(unittest.TestCase):
    def _fit(self):
        recs = []
        # 未収0: 40件・解約4件（10%）
        for _ in range(4):
            recs.append(normalize_record(row("成立後CAN【解約】", "", "2025-03-01"), CMAP, AS_OF))
        for _ in range(36):
            recs.append(normalize_record(row("成立済", ""), CMAP, AS_OF))
        # 未収2+: 30件・解約21件（70%）
        for _ in range(21):
            recs.append(normalize_record(row("未払消滅", "●未26⑦⑥", "2025-03-01"), CMAP, AS_OF))
        for _ in range(9):
            recs.append(normalize_record(row("成立済", "未26⑦⑥"), CMAP, AS_OF))
        return fit.fit_model(recs)

    def test_model_learns_unpaid_band_ordering(self):
        model = self._fit()
        f = model["factors"]["unpaid_band"]
        self.assertIn("2+", f)
        self.assertIn("0", f)
        # 繰り返し未収ほど高リスク＝オッズ比が大きい
        self.assertGreater(f["2+"]["odds_ratio"], f["0"]["odds_ratio"])
        self.assertGreater(f["2+"]["rate"], f["0"]["rate"])

    def test_score_higher_for_unpaid(self):
        model = self._fit()
        # 同一プロフィールで Ⅳ の有無だけ変える → 未収ありの方が高リスク
        r_clean = normalize_record(row("成立済", ""), CMAP, AS_OF)
        r_unpaid = normalize_record(row("成立済", "●未26⑦⑥"), CMAP, AS_OF)
        self.assertGreater(score_record(r_unpaid, model)["risk"],
                           score_record(r_clean, model)["risk"])


if __name__ == "__main__":
    unittest.main()
