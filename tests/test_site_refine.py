"""もらいわすれ堂 サイトデザイン洗練(第1弾・2026-11-21)を確かめる。

見た目は変えたが、次は変えていないことを確かめる:
- 上の帯のリンク・計測(LINE登録の line_add_click、Instagram の ig_click)はすべて残す(メニューの中に入れただけ)
- 制度カードの「公式ページ」「申請準備シート」のリンク先は変えない(ボタンの見た目にしただけ)
- 41市町村はすべて一覧に出る(市 / 町・村に分けただけ)
- 申請準備シート一覧の絞り込みは端末の中だけで動く(送信・保存をしない)
- 仕上げのCSSは新しい色を足さず、文節分割系のCSS(性能規律)を使わない。山梨版と共用の fg-base.css は触らない
"""
import json
import os
import re
import sys
import unittest

BASE = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(BASE, "scripts"))
import generate_area_pages as area  # noqa: E402
import generate_kit_pages as kit  # noqa: E402
import generate_life_pages as life  # noqa: E402

DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
REFINE = os.path.join(BASE, "site", "fukugiiro", "assets", "fg-refine.css")
STATIC = ["shindan", "houkoku", "teisei", "privacy"]


class SiteRefine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA, encoding="utf-8") as f:
            db = json.load(f)
        cls.items = [i for i in db["items"] if i.get("area") not in area.HIDDEN_MUNIS]
        u = "2026-11-21"
        cls.pages = {"area/index": area.index_page(u), "kit/index": kit.index_page(cls.items, u),
                     "life/index": life.index_page(cls.items, u)}
        for name, slug in area.VISIBLE_MUNIS:
            cls.pages[f"area/{slug}"] = area.muni_page(name, cls.items, u)
        for slug, events, heading, kw in life.EVENTS:
            cls.pages[f"life/{slug}"] = life.life_page(slug, events, heading, kw, cls.items, u)
        for it in cls.items[:20]:
            cls.pages[f"kit/{it['id']}"] = kit.kit_page(it, u)
        for name in STATIC:
            with open(os.path.join(BASE, "site", "fukugiiro", name, "index.html"), encoding="utf-8") as f:
                cls.pages[name] = f.read()

    def header(self, html):
        return re.search(r'<header class="siteheader sh2">([\s\S]*?)</header>', html).group(1)

    def test_header_is_one_row_and_keeps_every_link(self):
        for key, html in self.pages.items():
            with self.subTest(page=key):
                self.assertEqual(html.count('<header class="siteheader'), 1)
                h = self.header(html)
                self.assertEqual(h.count('class="hcta"'), 1)
                self.assertIn('<details class="hmenu">', h)
                nav = re.search(r"<nav>([\s\S]*?)</nav>", h).group(1)
                for text in ("3分診断</a>", "市町村</a>", "準備シート</a>", "LINE登録</a>"):
                    self.assertIn(text, nav)
                self.assertIn("fgTrack('line_add_click')", nav)
                self.assertIn("fgTrack('ig_click',{pos:'header'})", nav)
                self.assertIn('/go/fg-', nav)                       # LINE導線は /go/ 経由のまま

    def test_refine_css_is_loaded_after_page_styles(self):
        for key, html in self.pages.items():
            with self.subTest(page=key):
                head = html[:html.index("</head>")]
                self.assertEqual(head.count("assets/fg-refine.css"), 1)
                self.assertGreater(head.index("assets/fg-refine.css"), head.index("assets/fg-base.css"))
                if "<style>" in head:
                    self.assertGreater(head.index("assets/fg-refine.css"), head.rindex("</style>"))

    def test_seido_cards_become_buttons_with_same_links(self):
        n = 0
        for key, html in self.pages.items():
            if not (key.startswith("area/") or key.startswith("life/")) or key.endswith("index"):
                continue
            with self.subTest(page=key):
                self.assertNotIn('<p style="display:flex;gap:16px;flex-wrap:wrap;margin:0">', html)
                cards = re.findall(r'<div class="card">([\s\S]*?)</div>', html)
                for c in cards:
                    if "申請準備シート</a>" not in c:
                        continue
                    n += 1
                    self.assertRegex(c, r'<p class="acts">.*<a class="kitlink" href="\.\./\.\./kit/[^"]+/">申請準備シート</a></p>')
        self.assertGreater(n, 100)

    def test_every_municipality_is_listed_once(self):
        html = self.pages["area/index"]
        for name, slug in area.VISIBLE_MUNIS:
            with self.subTest(muni=name):
                self.assertEqual(html.count(f'<li><a href="{slug}/">{name}</a></li>'), 1)
        cities = sum(1 for n, _ in area.VISIBLE_MUNIS if n.endswith("市"))
        self.assertIn(f"市({cities})", html)
        self.assertIn(f"町・村({len(area.VISIBLE_MUNIS) - cities})", html)

    def test_kit_search_runs_only_on_the_device(self):
        html = self.pages["kit/index"]
        self.assertIn('id="kitsearch"', html)
        self.assertEqual(html.count("class='kitgroup'"), 3)
        script = re.findall(r"<script>\n// 一覧の絞り込み[\s\S]*?</script>", html)
        self.assertEqual(len(script), 1)
        for ng in ("fetch(", "XMLHttpRequest", "localStorage", "sendBeacon", "fgTrack"):
            self.assertNotIn(ng, script[0])
        for it in self.items:
            self.assertIn(f'<li><a href="{kit.esc(it["id"])}/">', html)

    def test_refine_css_rules(self):
        with open(REFINE, encoding="utf-8") as f:
            css = f.read()
        body = re.sub(r"/\*[\s\S]*?\*/", "", css)
        self.assertEqual(set(re.findall(r"#[0-9A-Fa-f]{3,6}\b", body)) - {"#fff"}, set())  # 新しい色は足さない
        self.assertNotIn("auto-phrase", body)
        self.assertNotIn("text-wrap", body)

    def test_yamanashi_header_is_untouched(self):
        import fg_yamanashi
        self.assertNotIn("sh2", fg_yamanashi.HEADER)
        with open(os.path.join(BASE, "site", "fukugiiro", "assets", "fg-base.css"), encoding="utf-8") as f:
            base = f.read()
        self.assertNotIn(".sh2", base)


if __name__ == "__main__":
    unittest.main()
