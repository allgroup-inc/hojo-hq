import unittest
import tempfile
import os
from scripts.churn import fit, report_list, actions


def rec(product, early=None, resolved=True, apply_id="A", **ov):
    base = {"apply_id": apply_id, "product": product, "channel": "催事",
            "apply_form": "f", "amount_band": "a", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}
    base.update(ov)
    return base


def build_model():
    recs = [rec("X", 1) for _ in range(40)] + [rec("Y", 0) for _ in range(40)]
    return fit.fit_model(recs)


class TestReportList(unittest.TestCase):
    def test_rows_sorted_by_risk_desc(self):
        model = build_model()
        scoreable = [rec("Y", None, False, "LOW"), rec("X", None, False, "HIGH")]
        rows = report_list.build_rows(scoreable, model)
        self.assertEqual(rows[0]["apply_id"], "HIGH")
        self.assertGreaterEqual(rows[0]["risk"], rows[1]["risk"])

    def test_action_maps_band(self):
        self.assertIn("安心コール", actions.action_for_band("high"))
        self.assertEqual(actions.action_for_band("low"), "通常運用")

    def test_render_csv_and_html(self):
        model = build_model()
        rows = report_list.build_rows([rec("X", None, False, "HIGH")], model)
        for ext, render in ((".csv", report_list.render_csv), (".html", report_list.render_html)):
            fd, path = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            try:
                render(rows, path)
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("HIGH", content)
            finally:
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
