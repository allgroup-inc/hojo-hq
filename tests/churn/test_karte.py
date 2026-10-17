import unittest
import tempfile
import os
from datetime import date
from scripts.churn import karte


def profile():
    return {
        "customer_id": "C1", "age_band": "20代", "gender": "女", "area": "那覇",
        "n_applications": 2, "n_active": 1, "n_cancelled": 1, "n_early_churn": 1,
        "n_additional_guidance": 1, "max_risk_band": "high",
        "last_contact_date": date(2026, 3, 5), "needs_followup": True,
        "applications": [
            {"apply_id": "A2", "product": "医療保険A", "amount": 5000, "channel": "催事",
             "agent_id": "東さん", "apply_date": date(2026, 3, 1), "cancel_date": None,
             "is_early_churn": None, "is_scoreable": True, "risk": 0.999,
             "band": "high", "hit_factors": [
                 {"field": "product", "value": "医療保険A", "odds_ratio": 1.7,
                  "direction": "up", "n": 40, "reference": False}]},
            {"apply_id": "A1", "product": "がん保険B", "amount": 3000, "channel": "SNS",
             "agent_id": "東さん", "apply_date": date(2025, 1, 1),
             "cancel_date": date(2025, 3, 1), "is_early_churn": 1, "is_scoreable": False,
             "risk": None, "band": None, "hit_factors": []},
        ],
        "interactions": [
            {"date": date(2026, 3, 5), "kind": "追加案内", "agent": "東さん",
             "content": "がん保険の提案", "memo": "前向き"},
            {"date": date(2026, 2, 1), "kind": "架電", "agent": "東さん",
             "content": "見直し", "memo": "不在"},
        ],
    }


class TestKarte(unittest.TestCase):
    def test_render_html_contains_key_facts(self):
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            karte.render_html(profile(), path)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            self.assertIn("C1", html)
            self.assertIn("99.0%", html)          # display_pctクランプ(100%を出さない)
            self.assertNotIn("100.0%", html)
            self.assertIn("追加案内", html)         # タイムライン
            self.assertIn("要フォロー", html)        # 放置検知
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
