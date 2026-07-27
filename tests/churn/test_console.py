import unittest
import tempfile
import os
from datetime import date
from scripts.churn import console


def prof(cid, band, apps=1, active=1, addl=0, last=None, followup=False):
    return {"customer_id": cid, "age_band": "20代", "gender": "女", "area": "那覇",
            "n_applications": apps, "n_active": active, "n_cancelled": 0,
            "n_early_churn": 0, "n_additional_guidance": addl, "applications": [],
            "interactions": [], "max_risk_band": band, "last_contact_date": last,
            "needs_followup": followup}


class TestConsole(unittest.TestCase):
    def test_karte_filename_sanitized(self):
        self.assertEqual(console.karte_filename("C-100"), "karte_C-100.html")
        self.assertEqual(console.karte_filename("a/b 学"), "karte_a_b__.html")

    def test_index_rows_sorted_followup_then_risk(self):
        customers = {
            "L": prof("L", "low"),
            "H": prof("H", "high"),
            "F": prof("F", "high", followup=True),
        }
        rows = console.build_index_rows(customers)
        self.assertEqual([r["customer_id"] for r in rows], ["F", "H", "L"])
        self.assertEqual(rows[0]["karte_file"], "karte_F.html")

    def test_render_index_links_to_karte(self):
        rows = console.build_index_rows({"C1": prof("C1", "high")})
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            console.render_index_html(rows, path)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            self.assertIn("C1", html)
            self.assertIn('href="karte_C1.html"', html)
        finally:
            os.remove(path)

    def test_generate_raises_on_karte_filename_collision(self):
        # "A/B" と "A_B" はサニタイズ後にどちらも karte_A_B.html になる。
        # 黙って上書き(=別顧客のPIIへの誤誘導)せず、大声で止める。
        customers = {
            "A/B": prof("A/B", "high"),
            "A_B": prof("A_B", "low"),
        }
        out_dir = tempfile.mkdtemp()
        with self.assertRaises(SystemExit):
            console.generate(customers, out_dir)

    def test_generate_normal_ids_no_collision(self):
        customers = {
            "C1": prof("C1", "high"),
            "C2": prof("C2", "low"),
        }
        out_dir = tempfile.mkdtemp()
        res = console.generate(customers, out_dir)
        self.assertEqual(res["n_kartes"], 2)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "karte_C1.html")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "karte_C2.html")))


if __name__ == "__main__":
    unittest.main()
