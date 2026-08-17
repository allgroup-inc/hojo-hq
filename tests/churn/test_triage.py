import unittest
from datetime import date
from scripts.churn import fit
from scripts.churn.triage import triage, classify, PRIORITY

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
