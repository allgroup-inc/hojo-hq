"""公開用 seido.json の更新保留(scripts/fetch_fukugiiro.py)のテスト。実行: python3 -m unittest tests/test_fetch_publish.py
外部サイトへは接続しない(到達性・robots の確認を差し替えて、収集処理をそのまま動かす)。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fetch_fukugiiro as ff  # noqa: E402

REQ = {"fk-kuni-a", "fk-kuni-b"}


def items(*ids):
    return [{"id": i} for i in ids]


class Decide(unittest.TestCase):
    def d(self, prev, new, failed=None, legit=None):
        return ff.decide_publish(prev, new, failed or {}, legit or {}, REQ, "2026-11-04 10:00")

    def test_normal_and_first_run(self):
        self.assertTrue(self.d(items("fk-kuni-a", "fk-kuni-b", "x"), items("fk-kuni-a", "fk-kuni-b", "x", "y"))["publish"])
        s = self.d(None, items("fk-kuni-a"))
        self.assertTrue(s["publish"])
        self.assertEqual(s["required_missing"], ["fk-kuni-b"])

    def test_failure_of_published_item_holds_regardless_of_count(self):
        s = self.d(items("fk-kuni-a", "fk-kuni-b", "x"), items("fk-kuni-a", "fk-kuni-b"), failed={"x": "URL到達不可"})
        self.assertFalse(s["publish"])
        self.assertIn("取得に失敗", s["reasons"][0])

    def test_failure_of_item_not_in_previous_public_does_not_hold_but_is_reported(self):
        # 本番の児童扶養手当: 前回の公開データにも無いので、公開データは減らない
        s = self.d(items("fk-kuni-a", "x"), items("fk-kuni-a", "x"), failed={"fk-kuni-b": "URL到達不可"})
        self.assertTrue(s["publish"])
        self.assertEqual(s["required_missing"], ["fk-kuni-b"])
        self.assertEqual(s["failed"], [{"id": "fk-kuni-b", "reason": "URL到達不可", "in_previous_public": False}])

    def test_unexplained_loss_up_to_two_publishes_three_holds(self):
        prev = items("fk-kuni-a", "fk-kuni-b", "p1", "p2", "p3", "z")
        self.assertTrue(self.d(prev, items("fk-kuni-a", "fk-kuni-b", "p3", "z"))["publish"])
        s = self.d(prev, items("fk-kuni-a", "fk-kuni-b", "z"))
        self.assertFalse(s["publish"])
        self.assertEqual(s["unexplained_lost"], ["p1", "p2", "p3"])

    def test_required_loss_holds_even_one(self):
        s = self.d(items("fk-kuni-a", "fk-kuni-b"), items("fk-kuni-a"))
        self.assertFalse(s["publish"])
        self.assertIn("必須制度", " ".join(s["reasons"]))
        # 保留したので前回の公開データ(fk-kuni-b を含む)が公開されたまま。公開中の必須制度は欠けていない
        self.assertEqual(s["required_missing"], [])

    def test_legit_removal_is_allowed_with_evidence(self):
        s = self.d(items("fk-kuni-a", "fk-kuni-b", "e1", "e2", "e3"), items("fk-kuni-a", "fk-kuni-b"),
                   legit={"e1": "締切終了(deadline 2026-10-30)", "e2": "締切終了(deadline 2026-10-30)", "e3": "廃止記録(2026-11-01: 制度終了 / 公式発表URL)"})
        self.assertTrue(s["publish"])
        self.assertEqual([x["id"] for x in s["legit_removed"]], ["e1", "e2", "e3"])
        self.assertIn("廃止記録", s["legit_removed"][2]["evidence"])
        # 必須制度でも、根拠があれば保留しない
        self.assertTrue(self.d(items("fk-kuni-a", "fk-kuni-b"), items("fk-kuni-a"), legit={"fk-kuni-b": "廃止記録(x)"})["publish"])


class Pipeline(unittest.TestCase):
    """収集処理(main)をそのまま、複製した作業場所で動かす。"""

    def run_fetch(self, prev_extra=(), unreachable=(), all_down=False, end_id=None, drop_id=None, retire_id=None,
                  prev_exclude=(), unreachable_ids=(), down_code="HTTP 503", seed_patch=None):
        w = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, w)
        shutil.copytree(os.path.join(ROOT, "scripts"), os.path.join(w, "scripts"))
        os.makedirs(os.path.join(w, "data", "fukugiiro"))
        os.makedirs(os.path.join(w, "site", "fukugiiro"))
        sys.path.insert(0, os.path.join(w, "scripts"))
        # 前回の公開データ: 全シードが取れた状態に、テスト用の追加分を足したもの
        seeds = [s["id"] for s in ff.SEEDS if s.get("area") not in ff.HIDDEN_AREAS and s["id"] not in prev_exclude]
        prev = {"updated_at": "2026-11-03 04:00", "count": 0, "items": [{"id": i} for i in seeds] + [{"id": i} for i in prev_extra]}
        down_urls = [s["source_url"] for s in ff.SEEDS if s["id"] in unreachable_ids]
        prev["count"] = len(prev["items"])
        with open(os.path.join(w, "site", "fukugiiro", "seido.json"), "w") as fh:
            json.dump(prev, fh)
        code = f"""
import sys, urllib.parse
sys.path.insert(0, 'scripts')
import fetch_fukugiiro as f
f.time.sleep = lambda s: None
f.robots_ok = lambda u: True
down = {list(unreachable)!r}
down_urls = {down_urls!r}
f.reachable = lambda u: (False, {down_code!r}) if ({all_down} or urllib.parse.urlparse(u).netloc in down or u in down_urls) else (True, "HTTP 200")
ids = {{'end': {end_id!r}, 'drop': {drop_id!r}, 'retire': {retire_id!r}}}
for s in f.SEEDS:
    s.update({(seed_patch or {})!r}.get(s['id'], {{}}))
if ids['end']:
    for s in f.SEEDS:
        if s['id'] == ids['end']: s['deadline'] = '2026-01-01'; s['deadline_type'] = '期限あり'
if ids['drop'] or ids['retire']:
    gone = ids['drop'] or ids['retire']
    f.SEEDS[:] = [s for s in f.SEEDS if s['id'] != gone]
if ids['retire']:
    f.RETIRED[ids['retire']] = {{'date': '2026-11-01', 'reason': '制度終了', 'source': 'https://example.go.jp/notice'}}
f.main()
"""
        r = subprocess.run([sys.executable, "-c", code], cwd=w, capture_output=True, text=True)
        sys.path.remove(os.path.join(w, "scripts"))
        pub = json.load(open(os.path.join(w, "site", "fukugiiro", "seido.json")))
        st_path = os.path.join(w, "data", "fukugiiro", "publish_status.json")
        status = json.load(open(st_path)) if os.path.exists(st_path) else None
        data_path = os.path.join(w, "data", "fukugiiro", "seido.json")
        data = json.load(open(data_path)) if os.path.exists(data_path) else None
        return r, prev, pub, status, data

    def assertKept(self, prev, pub):
        self.assertEqual(pub["updated_at"], prev["updated_at"])
        self.assertEqual({i["id"] for i in pub["items"]}, {i["id"] for i in prev["items"]})

    def test_normal_collection_updates(self):
        r, prev, pub, status, data = self.run_fetch()
        self.assertEqual(r.returncode, 0, r.stdout[-500:] + r.stderr[-500:])
        self.assertTrue(status["publish"])
        self.assertNotEqual(pub["updated_at"], prev["updated_at"])
        self.assertEqual(pub, data)

    def test_ministry_outage_holds(self):
        r, prev, pub, status, data = self.run_fetch(unreachable=["www.mhlw.go.jp"])
        self.assertEqual(r.returncode, 0)
        self.assertFalse(status["publish"])
        self.assertKept(prev, pub)
        self.assertLess(data["count"], len(prev["items"]))  # data/ は従来どおり書かれる
        self.assertIn("::warning::公開用 seido.json の更新を保留", r.stdout)

    def test_network_down_holds(self):
        r, prev, pub, status, _ = self.run_fetch(all_down=True)
        self.assertFalse(status["publish"])
        self.assertKept(prev, pub)

    def test_production_like_jidofuyoteate_failure_still_publishes_and_reports(self):
        # 本番と同じく児童扶養手当だけが取れず(9/24の出典差し替え後、10/1以降の収集で毎回)、前回の公開データにも無い
        r, prev, pub, status, _ = self.run_fetch(prev_exclude=["fk-kuni-jidofuyoteate"], unreachable_ids=["fk-kuni-jidofuyoteate"])
        self.assertTrue(status["publish"], status["reasons"])  # 公開データは減らないので更新は止めない
        self.assertEqual(status["required_missing"], ["fk-kuni-jidofuyoteate"])  # 必須制度の欠けとして知らせる
        self.assertIn("::warning::必須制度が公開データにありません: fk-kuni-jidofuyoteate", r.stdout)
        self.assertEqual(status["failed"], [{"id": "fk-kuni-jidofuyoteate", "reason": "URL到達不可(HTTP 503)", "in_previous_public": False}])
        self.assertIn("::warning::前回の公開データに無い制度の取得に失敗しました(公開用の更新は続けます): fk-kuni-jidofuyoteate(URL到達不可(HTTP 503))", r.stdout)
        # 同じ制度が前回の公開データに載っていたら、取得失敗で保留する(件数は1件でも)
        r, prev, pub, status, _ = self.run_fetch(unreachable_ids=["fk-kuni-jidofuyoteate"])
        self.assertFalse(status["publish"])
        self.assertKept(prev, pub)

    def test_one_or_two_unexplained_missing_publishes(self):
        r, prev, pub, status, _ = self.run_fetch(prev_extra=["fk-naha-test-1", "fk-naha-test-2"])
        self.assertTrue(status["publish"])
        self.assertEqual(status["unexplained_lost"], ["fk-naha-test-1", "fk-naha-test-2"])

    def test_three_unexplained_missing_holds(self):
        r, prev, pub, status, _ = self.run_fetch(prev_extra=["fk-naha-test-1", "fk-naha-test-2", "fk-naha-test-3"])
        self.assertFalse(status["publish"])
        self.assertKept(prev, pub)

    def test_legit_end_publishes_with_evidence(self):
        target = next(s["id"] for s in ff.SEEDS if s["id"].startswith("fk-kuni-") and not s.get("deadline"))
        r, prev, pub, status, _ = self.run_fetch(end_id=target)
        self.assertTrue(status["publish"], status)
        self.assertIn({"id": target, "evidence": "締切終了(deadline 2026-01-01)"}, status["legit_removed"])
        self.assertNotIn(target, {i["id"] for i in pub["items"]})

    def test_required_removed_without_record_holds_and_with_record_publishes(self):
        target = "fk-kuni-jidoteate"
        r, prev, pub, status, _ = self.run_fetch(drop_id=target)
        self.assertFalse(status["publish"])
        self.assertIn("必須制度", " ".join(status["reasons"]))
        self.assertKept(prev, pub)
        r, prev, pub, status, _ = self.run_fetch(retire_id=target)
        self.assertTrue(status["publish"], status)
        self.assertIn("廃止記録(2026-11-01: 制度終了 / https://example.go.jp/notice)", [x["evidence"] for x in status["legit_removed"]])

    # ---- 出典URLの修正が収集・公開に与える影響(合成データ。URL は架空のもの) ----

    def test_dead_url_shared_with_unchecked_seed_is_reported(self):
        # 児童扶養手当の出典が 404。同じURLを到達性の確認なしで載せている制度を記録と警告に出す(公開の判定は変えない)
        r, prev, pub, status, _ = self.run_fetch(prev_exclude=["fk-kuni-jidofuyoteate"], unreachable_ids=["fk-kuni-jidofuyoteate"],
                                                 down_code="HTTP 404")
        self.assertTrue(status["publish"])
        shared = {x["id"]: x for x in status["source_dead_shared"]}
        self.assertIn("fk-ken-hitorioya-sodan", shared)
        self.assertEqual(shared["fk-ken-hitorioya-sodan"]["evidence"], "fk-kuni-jidofuyoteate: URL到達不可(HTTP 404)")
        self.assertIn("fk-ken-hitorioya-sodan", {i["id"] for i in pub["items"]})  # 載せ続ける(外すのは原文の確認後)
        self.assertIn("::warning::出典のページが無い(404/410)可能性があります", r.stdout)
        # 一時的な障害(503)では出さない
        r, prev, pub, status, _ = self.run_fetch(prev_exclude=["fk-kuni-jidofuyoteate"], unreachable_ids=["fk-kuni-jidofuyoteate"])
        self.assertEqual(status["source_dead_shared"], [])

    def test_fixed_url_brings_required_program_back(self):
        # 出典を取得できるページに直すと、児童扶養手当は新しく載る制度として戻り、公開は止まらない
        new_url = "https://example.lg.jp/kosodate/jidofuyoteate.html"
        r, prev, pub, status, _ = self.run_fetch(prev_exclude=["fk-kuni-jidofuyoteate"],
                                                 seed_patch={"fk-kuni-jidofuyoteate": {"source_url": new_url}})
        self.assertTrue(status["publish"], status["reasons"])
        self.assertEqual(status["required_missing"], [])
        item = next(i for i in pub["items"] if i["id"] == "fk-kuni-jidofuyoteate")
        self.assertEqual(item["source_url"], new_url)
        self.assertEqual(item["issuer"], "こども家庭庁")  # 制度IDと発行元は変えない

    def test_turning_on_check_for_published_seed_with_dead_url_holds(self):
        # 公開中の制度の到達性の確認を有効にし、そのURLが取れなければ、前回公開分の取得失敗として公開を保留する
        # (出典を直さずに assume_reachable だけ外すと、公開用データの更新が止まる)
        url = next(s["source_url"] for s in ff.SEEDS if s["id"] == "fk-ken-hitorioya-sodan")
        r, prev, pub, status, _ = self.run_fetch(unreachable_ids=["fk-ken-hitorioya-sodan"], down_code="HTTP 404",
                                                 seed_patch={"fk-ken-hitorioya-sodan": {"assume_reachable": False}})
        self.assertFalse(status["publish"])
        self.assertKept(prev, pub)
        self.assertIn("fk-ken-hitorioya-sodan", [x["id"] for x in status["failed"] if x["in_previous_public"]])
        self.assertTrue(url)


class Reachable(unittest.TestCase):
    """到達性の確認は HTTP ステータスまで残す(403=遮断と404=消滅を見分ける)。本文・URLは理由に入れない。"""

    def test_status_is_recorded(self):
        class Res:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        cases = [
            (Res(), (True, "HTTP 200")),
            (urllib.error.HTTPError("https://x/secret?q=1", 403, "Forbidden", {}, None), (False, "HTTP 403")),
            (urllib.error.HTTPError("https://x/", 404, "Not Found", {}, None), (False, "HTTP 404")),
            (urllib.error.URLError(TimeoutError("timed out")), (False, "URLError(TimeoutError)")),
            (ConnectionResetError("reset"), (False, "ConnectionResetError")),
        ]
        for effect, want in cases:
            with self.subTest(want=want):
                kw = {"return_value": effect} if isinstance(effect, Res) else {"side_effect": effect}
                with mock.patch("urllib.request.urlopen", **kw):
                    self.assertEqual(ff.reachable("https://example.go.jp/a"), want)


if __name__ == "__main__":
    unittest.main()
