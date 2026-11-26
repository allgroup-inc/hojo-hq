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

    def test_collection_publishes_fixed_sources(self):
        # 2026-11-25: 出典を直したので、児童扶養手当(必須)・ひとり親家庭支援は、印なしで公開される。
        # 404 の出典のリンクを止める仕組み自体は、上の Marking と下の AssumedSourcesAreStillChecked で確かめる
        import test_fetch_publish as tfp
        case = tfp.Pipeline("run_fetch")
        try:
            r, prev, pub, status, data = case.run_fetch()
        finally:
            case.doCleanups()
        self.assertEqual(r.returncode, 0, r.stdout[-500:] + r.stderr[-500:])
        self.assertTrue(status["publish"], status["reasons"])          # 公開更新の安全装置はそのまま
        self.assertNotIn("fk-kuni-jidofuyoteate", status["required_missing"])
        by = {i["id"]: i for i in pub["items"]}
        for sid in ("fk-kuni-jidofuyoteate", "fk-ken-hitorioya-sodan", "fk-ken-kouto-shokugyo-kunren"):
            self.assertIn(sid, by)
            self.assertNotIn("source_unavailable", by[sid], sid)
            self.assertNotEqual(by[sid]["source_url"], DEAD)
        self.assertIn("[info] 確認を省いている出典の点検:", r.stdout)


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
        # 2026-11-25 に本番の出典を直した(#651)ため、本番データにはもう 404 の出典が無い。
        # 仕組みを確かめるため、テスト用の複製でだけ、ひとり親家庭支援の出典を 404 だった旧URLに戻す
        for i in cls.items:
            if i["id"] == "fk-ken-hitorioya-sodan":
                i["source_url"] = DEAD
            if i["id"] == "fk-ken-kouto-shokugyo-kunren":   # 同じ階層だが 404 を記録していないURL(止めない側の例)
                i["source_url"] = NEAR
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



class AssumedSourcesAreStillChecked(unittest.TestCase):
    """確認を省いている出典(assume_reachable)も、順番に開いて 404/410 だけを見分ける(2026-11-25)。外部へは接続しない"""

    def setUp(self):
        import datetime as dt
        import fetch_fukugiiro as ff
        self.ff, self.dt = ff, dt

    def test_every_url_is_checked_within_a_week_and_batches_are_small(self):
        urls = [f"https://example.lg.jp/{i}.html" for i in range(207)]
        seen = set()
        start = self.dt.datetime(2026, 11, 25, 6, 0)
        for half_day in range(14):
            now = start + self.dt.timedelta(hours=12 * half_day)
            batch = self.ff.rotation_batch(urls, now)
            self.assertLessEqual(len(batch), self.ff.ROTATE_PER_RUN)
            self.assertEqual(batch, self.ff.rotation_batch(urls, now))     # 同じ回は同じ組
            seen |= set(batch)
        self.assertEqual(seen, set(urls))                                   # 7日(14回)で一回り

    def test_only_404_and_410_count_as_gone(self):
        answers = {"a": (True, "HTTP 200"), "b": (False, "HTTP 404"), "c": (False, "HTTP 403"),
                   "d": (False, "URLError(timeout)"), "e": (False, "HTTP 410"), "f": (False, "HTTP 503")}
        ok, dead = self.ff.check_assumed(list(answers), check=lambda u: answers[u], pause=0)
        self.assertEqual(ok, {"a"})
        self.assertEqual(set(dead), {"b", "e"})                             # 遮断(403)・一時的な失敗は止めない
        stop = fgsrc.dead_sources([seed("x", "b"), seed("y", "c")], {"x": dead["b"]}, ok, "2026-11-25 06:00")
        self.assertIn("b", stop)
        self.assertNotIn("c", stop)

    def test_dead_source_is_carried_until_it_opens_again(self):
        cur = self.ff.carry_assumed_dead({}, {"u1": "URL到達不可(HTTP 404)"}, set(), {"u1", "u2"}, "11-25 06:00")
        self.assertEqual(cur["u1"]["since"], "11-25 06:00")
        nxt = self.ff.carry_assumed_dead(cur, {}, {"u2"}, {"u1", "u2"}, "11-25 18:00")   # 次の回は別の組を点検
        self.assertEqual(nxt, cur)                                                         # 止めたまま(最初の日時のまま)
        self.assertEqual(self.ff.carry_assumed_dead(nxt, {}, {"u1"}, {"u1", "u2"}, "12-02 06:00"), {})   # 開けたら外す
        self.assertEqual(self.ff.carry_assumed_dead(nxt, {}, set(), {"u2"}, "12-02 06:00"), {})        # シードのURLが変われば外す

    def test_two_runs_keep_the_link_stopped(self):
        # 1回目の点検で 404 → リンクを止める。2回目はその出典を点検しない組でも、止めたままにする(2026-11-25 独立レビュー)
        import test_fetch_publish as tfp
        sid = next(s["id"] for s in self.ff.SEEDS if s.get("assume_reachable") and s.get("area") not in self.ff.HIDDEN_AREAS)
        case = tfp.Pipeline("run_fetch")
        try:
            r1, _, pub1, st1, _ = case.run_fetch(gone_ids=[sid], batch_ids=[sid])
            r2, _, pub2, st2, _ = case.run_fetch(gone_ids=[sid], batch_ids=[], prev_status=st1)
            r3, _, pub3, st3, _ = case.run_fetch(batch_ids=[sid], prev_status=st2)        # 直ったら戻る
        finally:
            case.doCleanups()
        for r in (r1, r2, r3):
            self.assertEqual(r.returncode, 0, r.stdout[-400:] + r.stderr[-400:])
        by = lambda pub: {i["id"]: i for i in pub["items"]}
        self.assertIn("source_unavailable", by(pub1)[sid])           # 制度は残し、リンクだけ止める
        self.assertIn("source_unavailable", by(pub2)[sid])
        self.assertNotIn("source_unavailable", by(pub3)[sid])
        self.assertTrue(st1["publish"] and st2["publish"] and st3["publish"])
        self.assertEqual(st3["assumed_dead"], {})

    def test_fixed_sources_no_longer_point_at_the_dead_page(self):
        by_id = {s["id"]: s for s in self.ff.SEEDS}
        for sid in ("fk-kuni-jidofuyoteate", "fk-ken-hitorioya-sodan", "fk-ken-kouto-shokugyo-kunren"):
            self.assertNotIn("1008243", by_id[sid]["source_url"], sid)


if __name__ == "__main__":
    unittest.main()
