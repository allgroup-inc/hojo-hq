"""公式ページが無い(404/410)出典のリンクだけを止める仕組み(scripts/fg_source_status.py)のテスト。
実行: python3 -m unittest tests/test_source_status.py
制度は削除せず、出典URLも書き換えず、リンクの代わりに「公式ページを確認中」を出すこと。外部サイトへは接続しない。"""
import copy
import json
import os
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.dirname(__file__))
import fg_source_status as fgsrc  # noqa: E402
import generate_area_pages as area  # noqa: E402
import generate_ig_neta as neta  # noqa: E402
import generate_kit_pages as kit  # noqa: E402
import generate_life_pages as life  # noqa: E402

DEAD = "https://www.pref.okinawa.lg.jp/kyoiku/kosodate/1008226/1008243/index.html"
NEAR = "https://www.pref.okinawa.lg.jp/kyoiku/kosodate/1008226/1008243/1026858.html"  # 404 は未確認(止めない)


def seed(i, url, **kw):
    d = {"id": i, "name": f"制度{i}", "source_url": url}
    d.update(kw)
    return d


def hrefs(html_text, url):
    """mailto(情報の訂正の連絡)以外で、そのURLへのリンクがいくつあるか。"""
    return len(re.findall(r'href="' + re.escape(url) + '"', html_text))


class Decide(unittest.TestCase):
    def test_confirmed_registry_only_has_evidence(self):
        self.assertEqual(set(fgsrc.CONFIRMED_DEAD), {DEAD})  # 推測で足さない
        for v in fgsrc.CONFIRMED_DEAD.values():
            self.assertIn(v["http"], (404, 410))
            self.assertTrue(v["confirmed_at"] and v["evidence"])

    def test_run_results(self):
        seeds = [seed("a", "https://x.lg.jp/a"), seed("b", "https://x.lg.jp/b"), seed("c", "https://x.lg.jp/c"),
                 seed("d", "https://x.lg.jp/d")]
        failed = {"a": "URL到達不可(HTTP 404)", "b": "URL到達不可(HTTP 410)", "c": "URL到達不可(HTTP 503)",
                  "d": "URL到達不可(URLError(TimeoutError))"}
        dead = fgsrc.dead_sources(seeds, failed, (), "2026-11-04 12:00")
        self.assertIn("https://x.lg.jp/a", dead)
        self.assertEqual(dead["https://x.lg.jp/b"]["http"], 410)
        self.assertNotIn("https://x.lg.jp/c", dead)   # 一時的な障害では止めない
        self.assertNotIn("https://x.lg.jp/d", dead)
        self.assertIn(DEAD, dead)                     # 記録のある確定分

    def test_opened_in_this_run_wins(self):
        dead = fgsrc.dead_sources([], {}, checked_ok={DEAD})
        self.assertNotIn(DEAD, dead)  # この回の収集で開けたなら、記録があっても止めない

    def test_mark_keeps_program_and_url_and_restores(self):
        items = [seed("fk-ken-hitorioya-sodan", DEAD), seed("fk-ken-kouto-shokugyo-kunren", NEAR), seed("x", "https://x.go.jp/")]
        before = copy.deepcopy(items)
        marked = fgsrc.mark_unavailable(items, fgsrc.dead_sources([], {}))
        self.assertEqual(marked, ["fk-ken-hitorioya-sodan"])
        self.assertEqual(len(items), 3)                                    # 制度は削除しない
        self.assertEqual([i["source_url"] for i in items], [i["source_url"] for i in before])  # URLは書き換えない
        self.assertEqual(items[0]["source_unavailable"]["reason"], "公式ページが見つかりません(HTTP 404)")
        self.assertNotIn("source_unavailable", items[1])                   # 404 未確認のURLは止めない
        # 原文で確かめた正しいURLにシードを直すと、次の収集で印が外れる
        items[0]["source_url"] = "https://www.pref.okinawa.lg.jp/new-official.html"
        self.assertEqual(fgsrc.mark_unavailable(items, fgsrc.dead_sources([], {})), [])
        self.assertNotIn("source_unavailable", items[0])

    def test_wording_does_not_say_ended(self):
        self.assertIn("制度が終わったという意味ではありません", fgsrc.NOTE)
        self.assertNotRegex(fgsrc.NOTE + fgsrc.LABEL, "終了しました|廃止されました|受付終了")


class Pipeline(unittest.TestCase):
    """収集処理(main)を、複製した作業場所でネットワークなしに動かす(test_fetch_publish の仕組みを使う)。"""

    def test_collection_marks_and_keeps_publishing(self):
        import test_fetch_publish as tfp
        case = tfp.Pipeline("run_fetch")
        try:
            # 本番と同じく、児童扶養手当(同じURL)は取れない。収集の記録(CONFIRMED_DEAD)から、ひとり親家庭支援のリンクを止める
            r, prev, pub, status, data = case.run_fetch(prev_exclude=["fk-kuni-jidofuyoteate"],
                                                        unreachable_ids=["fk-kuni-jidofuyoteate"])
            # この回の収集でそのURLが開けたなら止めない(記録より、いまの結果を優先する)
            r2, _, pub2, _, _ = case.run_fetch()
        finally:
            case.doCleanups()
        self.assertNotIn("source_unavailable", next(i for i in pub2["items"] if i["id"] == "fk-ken-hitorioya-sodan"))
        self.assertEqual(r.returncode, 0, r.stdout[-500:] + r.stderr[-500:])
        self.assertTrue(status["publish"], status["reasons"])          # 公開更新の安全装置はそのまま
        self.assertEqual({i["id"] for i in pub["items"]}, {i["id"] for i in data["items"]})
        by = {i["id"]: i for i in pub["items"]}
        self.assertIn("source_unavailable", by["fk-ken-hitorioya-sodan"])
        self.assertEqual(by["fk-ken-hitorioya-sodan"]["source_url"], DEAD)
        self.assertNotIn("source_unavailable", by["fk-ken-kouto-shokugyo-kunren"])
        self.assertIn("::warning::公式ページを確認中として出典リンクを止めた制度(掲載は続ける): fk-ken-hitorioya-sodan", r.stdout)


class Pages(unittest.TestCase):
    """申請準備シート・場面別ページ・市町村別ページの出力。"""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "data", "fukugiiro", "seido.json"), encoding="utf-8") as f:
            cls.db = json.load(f)
        # 本番の seido.json は毎日の収集で更新され、2026-11-04 からは「公式ページを確認中」の印
        # (source_unavailable)が本番データにも入っている。本番データをそのまま「印の無い制度」として
        # 使うと前提が崩れるため、テスト専用の複製を2つ作る(本番データ・ファイルは書き換えない)。
        #   items  = 印をすべて外した複製(②警告が無い場合)
        #   marked = items に、この仕組みで印を付け直した複製(①警告がある場合)
        cls.items = [copy.deepcopy(i) for i in cls.db["items"] if i.get("area") not in kit.HIDDEN_MUNIS]
        for i in cls.items:
            i.pop("source_unavailable", None)
        cls.marked = copy.deepcopy(cls.items)
        fgsrc.mark_unavailable(cls.marked, fgsrc.dead_sources([], {}))

    def test_fixtures_cover_both_cases(self):
        """前提の自己点検: ②印の無い複製には印が1件も無く、①印を付けた複製では対象の制度だけに印がある。"""
        self.assertFalse([i["id"] for i in self.items if fgsrc.unavailable(i)])
        self.assertTrue(fgsrc.unavailable(self.one(self.marked, "fk-ken-hitorioya-sodan")))
        self.assertFalse(fgsrc.unavailable(self.one(self.marked, "fk-ken-kouto-shokugyo-kunren")))
        self.assertEqual(self.one(self.items, "fk-ken-hitorioya-sodan")["source_url"], DEAD)  # URLは変えていない

    def one(self, items, i):
        return next(x for x in items if x["id"] == i)

    def test_kit_page(self):
        it = self.one(self.marked, "fk-ken-hitorioya-sodan")
        out = kit.kit_page(it, "2026-11-04")
        self.assertEqual(hrefs(out, DEAD), 0)
        self.assertIn(fgsrc.LABEL, out)
        self.assertIn("制度が終わったという意味ではありません", out)
        self.assertIn("mailto:info@fukugiiro.com", out)              # 情報の訂正の連絡先は残す
        ld = json.loads(re.search(r'<script type="application/ld\+json">\n(\{.*?\})\n</script>', out, re.S).group(1))
        self.assertNotIn("url", ld)
        # 印の無い制度は、これまでどおりリンクを出す
        plain = kit.kit_page(self.one(self.items, "fk-ken-hitorioya-sodan"), "2026-11-04")
        self.assertEqual(hrefs(plain, DEAD), 3)
        self.assertNotIn(fgsrc.LABEL, plain)
        near = kit.kit_page(self.one(self.marked, "fk-ken-kouto-shokugyo-kunren"), "2026-11-04")
        self.assertGreater(hrefs(near, NEAR), 0)                       # 404 未確認のURLは止めない

    def test_life_pages(self):
        for slug, events, heading, kw in life.EVENTS:
            out = life.life_page(slug, events, heading, kw, self.marked, "2026-11-04")
            with self.subTest(slug=slug):
                self.assertEqual(hrefs(out, DEAD), 0)
                if any(life.match(it, events) and it["id"] == "fk-ken-hitorioya-sodan" for it in self.marked):
                    self.assertIn(fgsrc.LABEL, out)
                    self.assertEqual(out.count(fgsrc.NOTE), 1)       # 説明はページに1回だけ
        plain = life.life_page("kosodate", ["子育て"], "子育て中", "子育て", self.items, "2026-11-04")
        self.assertNotIn(fgsrc.LABEL, plain)

    def test_area_page_marks_any_unavailable(self):
        items = copy.deepcopy(self.items)
        target = next(i for i in items if i["area"] == "那覇市")
        target["source_unavailable"] = {"since": "2026-11-04", "reason": "公式ページが見つかりません(HTTP 404)"}
        out = area.muni_page("那覇市", items, "2026-11-04")
        self.assertEqual(hrefs(out, target["source_url"]), 0)
        self.assertIn(fgsrc.LABEL, out)
        self.assertNotIn(fgsrc.LABEL, area.muni_page("那覇市", self.items, "2026-11-04"))

    def test_ig_neta_skips_unavailable(self):
        s = {"id": "a", "name": "A", "source_url": "https://x.go.jp/a", "verified": True, "deadline_type": "常時"}
        ok = neta.candidates({"items": [s]}, set(), set())
        self.assertEqual([x["id"] for x in ok], ["a"])
        s["source_unavailable"] = {"reason": "公式ページが見つかりません(HTTP 404)"}
        self.assertEqual(neta.candidates({"items": [s]}, set(), set()), [])


if __name__ == "__main__":
    unittest.main()
