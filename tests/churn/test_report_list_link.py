import unittest
import tempfile
import os
from scripts.churn import fit, report_list


def rec(product, early=None, resolved=True, apply_id="A", cid="C1"):
    return {"customer_id": cid, "apply_id": apply_id, "product": product,
            "channel": "催事", "apply_form": "f", "amount_band": "a", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}


def build_model():
    recs = [rec("X", 1) for _ in range(30)] + [rec("Y", 0) for _ in range(90)]
    return fit.fit_model(recs)


class TestReportListLink(unittest.TestCase):
    def test_rows_carry_customer_id_and_link(self):
        model = build_model()
        rows = report_list.build_rows([rec("X", None, False, "NEW", "C-7")], model)
        self.assertEqual(rows[0]["customer_id"], "C-7")
        self.assertEqual(rows[0]["karte_link"], "karte_C-7.html")

    def test_html_links_customer_to_karte(self):
        model = build_model()
        rows = report_list.build_rows([rec("X", None, False, "NEW", "C-7")], model)
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            report_list.render_html(rows, path)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            self.assertIn('href="karte_C-7.html"', html)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
