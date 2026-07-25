import unittest
import tempfile
import os
from scripts.churn import fit, report_card


def rec(product, early=None, resolved=True, apply_id="A", **ov):
    base = {"apply_id": apply_id, "product": product, "channel": "催事",
            "apply_form": "対面", "amount_band": "3千〜1万", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}
    base.update(ov)
    return base


class TestReportCard(unittest.TestCase):
    def setUp(self):
        recs = [rec("X", 1) for _ in range(30)] + [rec("Y", 0) for _ in range(90)]
        self.model = fit.fit_model(recs)

    def test_build_card_has_reasons(self):
        card = report_card.build_card(rec("X", None, False, "NEW"), self.model)
        self.assertEqual(card["apply_id"], "NEW")
        self.assertEqual(card["band"], "high")
        self.assertTrue(card["reasons"])
        self.assertIn("安心コール", card["action"])

    def test_render_html_contains_id_and_pct(self):
        card = report_card.build_card(rec("X", None, False, "NEW"), self.model)
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            report_card.render_html(card, path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("NEW", content)
            self.assertIn("%", content)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
