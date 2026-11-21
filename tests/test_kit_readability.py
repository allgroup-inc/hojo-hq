"""申請準備シートの見やすさ(2026-11-21 利用者の声「詰まりすぎ・文字が多すぎ」で組み直し)を確かめる。

並べ方は変えたが、次は変えていないことを全制度で確かめる:
- 制度の文(対象・金額・窓口・併用の注意)は seido.json のまま、1文字も書き換えない(絶対ルール1)
- 持ち物のチェック・メモの保存先(順番)は以前と同じ。端末に残っている記録がずれない
- 計測イベント・LINEの文言(締切の約1か月前から)・代筆しない旨の注意書きは残す
- たたんだ項目は印刷の直前に開く(閉じたままだと持ち物やメモ欄が紙に出ない)
"""
import json
import os
import re
import sys
import unittest

BASE = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(BASE, "scripts"))
import generate_kit_pages as kit  # noqa: E402

DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")


class KitReadability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA, encoding="utf-8") as f:
            db = json.load(f)
        cls.items = [i for i in db["items"] if i.get("area") not in kit.HIDDEN_MUNIS]
        cls.pages = {i["id"]: kit.kit_page(i, "2026-11-21") for i in cls.items}

    def body(self, out):
        return out[out.index('<div class="wrap">'):]

    def test_seido_text_is_unchanged(self):
        for it in self.items:
            out = self.pages[it["id"]]
            with self.subTest(id=it["id"]):
                for key in ("target_household", "amount_note", "how_to_apply"):
                    self.assertIn(f"<dd>{kit.esc(it[key])}</dd>", out)
                note = (it.get("combine") or {}).get("note")
                if note:
                    self.assertIn(kit.esc(note), out)

    def test_summary_comes_first(self):
        for it in self.items:
            b = self.body(self.pages[it["id"]])
            with self.subTest(id=it["id"]):
                self.assertLess(b.index('<dl class="sum">'), b.index("やることは4つ"))
                self.assertLess(b.index('<dl class="sum">'), b.index("電話で3つ聞く"))

    def test_four_tasks_without_duplicated_steps(self):
        for it in self.items:
            b = self.body(self.pages[it["id"]])
            with self.subTest(id=it["id"]):
                self.assertNotIn("申請までの5ステップ", b)
                self.assertNotIn('class="track"', b)
                tasks = re.findall(r'<details class="fold task"( open)?>', b)
                self.assertEqual(len(tasks), 4)
                self.assertEqual([t == " open" for t in tasks], [True, False, False, False])

    def test_saved_checks_and_memos_keep_their_order(self):
        for it in self.items:
            b = self.body(self.pages[it["id"]])
            events = []
            for ev in it.get("life_events", []):
                for x in kit.EVENT_ITEMS.get(ev, []):
                    if x not in events and x not in kit.CORE_ITEMS:
                        events.append(x)
            with self.subTest(id=it["id"]):
                self.assertEqual(re.findall(r'data-m="(\d)"', b), ["0", "1", "2", "3"])
                keys = re.findall(r'<input type="checkbox" data-k="(\d+)">', b)
                self.assertEqual(keys, [str(i) for i in range(len(kit.CORE_ITEMS) + len(events))])
                self.assertIn('var KEY = "fk_kit_' + it["id"] + '"', b)

    def test_print_opens_folded_sections(self):
        b = self.body(next(iter(self.pages.values())))
        self.assertIn('addEventListener("beforeprint"', b)
        self.assertIn('addEventListener("afterprint"', b)

    def test_tracking_and_required_wording_remain(self):
        for it in self.items:
            b = self.body(self.pages[it["id"]])
            with self.subTest(id=it["id"]):
                for ev in ("kit_print", "kit_copy", "kit_copy_say", "kit_conbini", "kit_check",
                           "jukyu_report_link_kit", "line_add_click", "teisei_mail"):
                    self.assertIn(ev, b)
                if kit.fg_madoguchi.get(it.get("area")):
                    self.assertIn("fgTrack('kit_tel')", b)
                    self.assertIn("kit_map", b)
                self.assertIn("締切の約1か月前から", b)
                self.assertIn("申請書の作成代行・代筆は行っていません", b)
                for ng in ("締切7日前", "締切の7日前", "7日前アラート"):
                    self.assertNotIn(ng, b)

    def test_combine_label_says_what_it_is_about(self):
        exclusive = [i for i in self.items if (i.get("combine") or {}).get("note")
                     and (i.get("combine") or {}).get("type", "exclusive") == "exclusive"]
        self.assertTrue(exclusive, "併用できない制度がデータに無いと、この検査は意味をなさない")
        for it in exclusive:
            with self.subTest(id=it["id"]):
                b = self.body(self.pages[it["id"]])
                self.assertIn("ほかの制度と併用できない場合あり", b)
                self.assertNotIn(">どちらか一方<", b)


if __name__ == "__main__":
    unittest.main()
