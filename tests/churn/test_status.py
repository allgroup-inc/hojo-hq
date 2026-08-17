import unittest
from datetime import date

from scripts.churn.status import (
    classify_status, excluded_reason, status_scope, scope_summary,
)

AS_OF = date(2026, 8, 1)
AD = date(2026, 1, 1)   # 契約日（as_of時点で6ヶ月経過＝成熟）


class TestClassify(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(classify_status("成立済"), "継続")
        self.assertEqual(classify_status("成立後CAN【解約】"), "早期解約")
        self.assertEqual(classify_status("不成立【引受後未入金】"), "早期解約")
        self.assertEqual(classify_status("未払消滅"), "早期解約")
        self.assertEqual(classify_status("死亡解約"), "対象外")
        self.assertEqual(classify_status("契約取り消し【成立後】"), "対象外")
        self.assertEqual(classify_status("謝絶"), "母集団外")
        self.assertEqual(classify_status("PL申込【送信前】"), "母集団外")
        self.assertEqual(classify_status("なにか未知の値"), "不明")

    def test_excluded_reason(self):
        self.assertEqual(excluded_reason("死亡解約"), "死亡")
        self.assertEqual(excluded_reason("取消・解除【成立後】"), "告知解除")
        self.assertEqual(excluded_reason("契約取り消し【引受後】"), "クーリングオフ")
        self.assertIsNone(excluded_reason("成立済"))


class TestScope(unittest.TestCase):
    def test_continuing_matured_is_survivor(self):
        s = status_scope("成立済", AD, None, AS_OF)
        self.assertTrue(s["in_scope"])
        self.assertTrue(s["is_resolved"])
        self.assertFalse(s["is_early_churn"])
        self.assertFalse(s["is_continuing"])

    def test_continuing_young_is_scoreable(self):
        s = status_scope("成立済", date(2026, 7, 1), None, AS_OF)  # 1ヶ月
        self.assertTrue(s["is_continuing"])
        self.assertFalse(s["is_resolved"])

    def test_early_cancel_within_6mo(self):
        s = status_scope("成立後CAN【解約】", AD, date(2026, 3, 1), AS_OF)  # 2ヶ月で解約
        self.assertTrue(s["is_early_churn"])
        self.assertTrue(s["is_resolved"])

    def test_cancel_after_6mo_is_not_early(self):
        s = status_scope("成立後CAN【解約】", date(2025, 1, 1), date(2025, 10, 1), AS_OF)  # 9ヶ月後
        self.assertFalse(s["is_early_churn"])
        self.assertTrue(s["is_resolved"])   # 成熟・非早期

    def test_unpaid_no_date_is_early_and_flagged(self):
        # 不成立【引受後未入金】＝初回引落前に落ちた。解約日欠損でも早期解約、監査フラグ
        s = status_scope("不成立【引受後未入金】", AD, None, AS_OF)
        self.assertTrue(s["is_early_churn"])
        self.assertTrue(s["date_missing"])

    def test_any_early_churn_no_date_is_churn_not_survivor(self):
        # 未払消滅・失効中・CAN も解約日欠損で「生存者」に混ぜない（KPI過小防止）
        for st in ("未払消滅", "失効中", "成立後CAN【解約】", "解約予定【成立後】"):
            s = status_scope(st, AD, None, AS_OF)
            self.assertTrue(s["is_early_churn"], st)
            self.assertTrue(s["is_resolved"], st)
            self.assertTrue(s["date_missing"], st)

    def test_death_is_excluded(self):
        s = status_scope("死亡解約", AD, date(2026, 3, 1), AS_OF)
        self.assertFalse(s["in_scope"])
        self.assertEqual(s["excluded_reason"], "死亡")
        self.assertFalse(s["is_early_churn"])

    def test_out_of_scope_not_counted(self):
        s = status_scope("謝絶", AD, None, AS_OF)
        self.assertFalse(s["in_scope"])
        self.assertIsNone(s["excluded_reason"])


class TestSummary(unittest.TestCase):
    def test_counts_by_category_and_excluded_reason(self):
        statuses = ["成立済", "成立済", "成立後CAN【解約】", "死亡解約",
                    "契約取り消し【成立後】", "謝絶", "PL申込【送信前】", "不明値"]
        summ = scope_summary(statuses)
        self.assertEqual(summ["継続"], 2)
        self.assertEqual(summ["早期解約"], 1)
        self.assertEqual(summ["対象外"], 2)
        self.assertEqual(summ["母集団外"], 2)
        self.assertEqual(summ["不明"], 1)
        self.assertEqual(summ["excluded_by_reason"]["死亡"], 1)
        self.assertEqual(summ["excluded_by_reason"]["クーリングオフ"], 1)


if __name__ == "__main__":
    unittest.main()
