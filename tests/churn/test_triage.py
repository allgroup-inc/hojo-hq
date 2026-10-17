import unittest
from datetime import date
from scripts.churn import fit
from scripts.churn.triage import (triage, classify, PRIORITY, recommend_action,
                                  contact_channel)

AS_OF = date(2026, 8, 1)


class TestTriage(unittest.TestCase):
    def test_orders_by_priority_then_saveable(self):
        cands = [
            {"trigger": "高リスク", "saveable": 100.0},
            {"trigger": "不着", "saveable": 10.0},
            {"trigger": "遅延", "saveable": 50.0},
            {"trigger": "不着", "saveable": 80.0},
        ]
        today, carry, stats = triage(cands, capacity=10)
        # 不着(80,10) → 遅延(50) → 高リスク(100)
        self.assertEqual([c["saveable"] for c in today], [80.0, 10.0, 50.0, 100.0])

    def test_capacity_and_carryover_no_silent_cap(self):
        cands = [{"trigger": "不着", "saveable": float(x)} for x in (5, 4, 3, 2, 1)]
        today, carry, stats = triage(cands, capacity=3)
        self.assertEqual(len(today), 3)
        self.assertEqual(len(carry), 2)
        self.assertEqual(stats["carry_count"], 2)          # 落とした件数を明示
        self.assertEqual(stats["carry_max_saveable"], 2.0)  # 繰り越しの最高“守れる金額”

    def test_priority_map_order(self):
        self.assertLess(PRIORITY["未払消滅目前"], PRIORITY["不着"])   # 消滅目前が最上位
        self.assertLess(PRIORITY["不着"], PRIORITY["遅延"])
        self.assertLess(PRIORITY["遅延"], PRIORITY["未収2連続"])
        self.assertLess(PRIORITY["未収2連続"], PRIORITY["口座確認"])
        self.assertLess(PRIORITY["口座確認"], PRIORITY["初動"])
        self.assertLess(PRIORITY["初動"], PRIORITY["高リスク"])

    def test_classify_picks_unpaid_imminent(self):
        r = {"is_scoreable": True, "customer_id": "U1", "apply_id": None,
             "apply_date": date(2026, 7, 1), "product": "医療", "agent_id": "S1",
             "amount": 5000, "debit_result": "", "account_daily": "はい", "debit_due": None,
             "unpaid_months": [(2026, 7), (2026, 6), (2026, 5)]}
        model = fit.fit_model([])
        cands = classify([r], model, AS_OF)
        self.assertIn("未払消滅目前", [c["trigger"] for c in cands])

    def test_recommend_action_by_trigger(self):
        self.assertIn("消滅目前", recommend_action("未払消滅目前"))
        self.assertIn("不着", recommend_action("不着"))
        self.assertIn("初回のごあいさつ", recommend_action("初動"))
        # 口座不備は再設定を促す文言を足す
        self.assertIn("口座不備", recommend_action("未収2連続", account_issue=True))

    def test_visit_channel_escalation(self):
        # 高リスク×守れる金額大 → 訪問。金額小 or 非高リスクは架電
        self.assertEqual(contact_channel("high", 150000, "高リスク"), "訪問")
        self.assertEqual(contact_channel("high", 5000, "高リスク"), "架電")   # 金額小
        self.assertEqual(contact_channel("low", 150000, "初動"), "架電")      # 非高リスク
        # 未払消滅目前×守れる金額大は帯によらず訪問
        self.assertEqual(contact_channel("med", 150000, "未払消滅目前"), "訪問")

    def test_recommend_action_visit_prefix(self):
        a = recommend_action("未払消滅目前", channel="訪問")
        self.assertIn("訪問", a)
        self.assertIn("消滅目前", a)

    def test_classify_enriches_recommendation_and_stage(self):
        r = {"is_scoreable": True, "customer_id": "U1", "apply_id": None,
             "apply_date": date(2026, 7, 1), "product": "医療", "agent_id": "S1",
             "amount": 5000, "debit_result": "", "account_daily": "はい", "debit_due": None,
             "unpaid_months": [(2026, 7), (2026, 6), (2026, 5)], "unpaid_account_issue": True}
        c = classify([r], fit.fit_model([]), AS_OF)[0]
        self.assertEqual(c["unpaid_streak"], 3)
        self.assertTrue(c["account_issue"])
        self.assertIn("消滅目前", c["recommendation"])

    def test_triage_orders_by_saveable_within_band(self):
        # 帯内は守れる金額順（streakは二次キーにしない＝不着等を金額順から外さない）
        cands = [{"trigger": "未払消滅目前", "saveable": 50.0, "unpaid_streak": 5},
                 {"trigger": "未払消滅目前", "saveable": 300.0, "unpaid_streak": 3}]
        today, _, _ = triage(cands, capacity=10)
        self.assertEqual([c["saveable"] for c in today], [300.0, 50.0])

    def test_classify_includes_matured_continuing_with_streak(self):
        # 6ヶ月超の成立済(is_scoreable=False)でも、未払消滅目前なら今日の要接触に載せる
        r = {"is_scoreable": False, "status_category": "継続", "customer_id": "M1",
             "apply_id": None, "product": "医療", "agent_id": "S1", "amount": 5000,
             "debit_result": "", "account_daily": "はい", "debit_due": None,
             "unpaid_months": [(2026, 7), (2026, 6), (2026, 5)]}
        model = fit.fit_model([])
        cands = classify([r], model, AS_OF)
        self.assertEqual([c["trigger"] for c in cands], ["未払消滅目前"])

    def test_classify_excludes_empty_id_even_with_unpaid_streak(self):
        # 顧客ID空＝母集団外(is_scoreable=False かつ status_category!="継続")。
        # 3ヶ月未収の連続があっても、ID漏れの行は今日の要接触に載せない（打ち手を打てないため）。
        r = {"is_scoreable": False, "status_category": "母集団外", "customer_id": "",
             "apply_id": None, "product": "医療", "agent_id": "S1", "amount": 5000,
             "debit_result": "", "account_daily": "はい", "debit_due": None,
             "unpaid_months": [(2026, 7), (2026, 6), (2026, 5)]}
        model = fit.fit_model([])
        self.assertEqual(classify([r], model, AS_OF), [])

    def test_classify_picks_up_initial_when_contacts_given(self):
        # 契約後3日・未接触の継続契約 → contacts を渡すと「初動」きっかけが立つ
        r = {"is_scoreable": True, "customer_id": "N1", "apply_id": None,
             "apply_date": date(2026, 7, 30), "product": "医療", "agent_id": "S1",
             "amount": 5000, "debit_result": "", "account_daily": "はい", "debit_due": None}
        model = fit.fit_model([])
        no_contact = classify([r], model, AS_OF, contacts=[])
        self.assertIn("初動", [c["trigger"] for c in no_contact])
        # 接触済みなら初動きっかけは消える
        contacted = classify([r], model, AS_OF, contacts=[
            {"customer_id": "N1", "apply_id": None, "apply_date": date(2026, 7, 30),
             "contact_date": date(2026, 7, 31), "action": "初回架電"}])
        self.assertNotIn("初動", [c["trigger"] for c in contacted])

    def test_classify_without_contacts_does_not_flag_initial(self):
        # contacts 未指定なら従来どおり初動は拾わない（後方互換）
        r = {"is_scoreable": True, "customer_id": "N1", "apply_id": None,
             "apply_date": date(2026, 7, 30), "product": "医療", "agent_id": "S1",
             "amount": 5000, "debit_result": "", "account_daily": "はい", "debit_due": None}
        model = fit.fit_model([])
        self.assertNotIn("初動", [c["trigger"] for c in classify([r], model, AS_OF)])


def rec(product, **over):
    base = {"customer_id": "C1", "apply_id": "A1", "product": product,
            "channel": "c", "apply_form": "f", "amount_band": "a", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1", "amount": 10000,
            "is_scoreable": True, "debit_result": "", "account_daily": "はい", "debit_due": None}
    base.update(over)
    return base


def build_model():
    def r(p, e):
        return {"product": p, "channel": "c", "apply_form": "f", "amount_band": "a",
                "age_band": "20代", "gender": "女", "area": "那覇", "agent_id": "S1",
                "is_resolved": True, "is_early_churn": e}
    return fit.fit_model([r("X", 1) for _ in range(30)] + [r("Y", 0) for _ in range(90)])


class TestClassify(unittest.TestCase):
    def test_payment_alert_becomes_candidate_with_saveable(self):
        model = build_model()
        cands = classify([rec("Y", customer_id="A", debit_result="不着")], model, AS_OF)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["trigger"], "不着")
        self.assertGreater(cands[0]["saveable"], 0)

    def test_low_risk_no_trigger_is_excluded(self):
        model = build_model()
        cands = classify([rec("Y", customer_id="B")], model, AS_OF)  # 低リスク・問題なし
        self.assertEqual(cands, [])


if __name__ == "__main__":
    unittest.main()
