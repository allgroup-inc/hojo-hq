"""原文照合(scripts/verify_sources.py)の結果の状態と、原因ごとの復旧のテスト。
実行: python3 -m unittest tests/test_verify_sources_status.py
外部(Claude・Gemini・jGrants・出典サイト)へは接続しない。すべて合成データ。

2026-11-05〜11-26、Claude の鍵が無効(401)で照合が11回失敗した。失敗は「不一致」の Issue になり、
国のAPIだけの日の成功で「解消」と閉じ、失敗した日は履歴に残らなかった。その再発を止める。"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_sources as vs  # noqa: E402

AI = {"id": "ken-1", "name": "沖縄県の補助金A", "source_url": "https://www.pref.okinawa.lg.jp/a.html",
      "deadline": "2026-12-25", "max_amount": 1000000, "issuer": "沖縄県"}
AI2 = {"id": "ken-2", "name": "沖縄県の補助金B", "source_url": "https://www.pref.okinawa.lg.jp/b.html",
       "deadline": "要確認", "max_amount": None, "issuer": "沖縄県"}
JG = [{"id": f"jg{i}", "name": f"国の補助金{i}", "source_url": f"https://www.jgrants-portal.go.jp/subsidy/{i}",
       "deadline": "2026-12-31", "max_amount": 100, "issuer": "国"} for i in range(6)]


class AuthenticationError(Exception):
    status_code = 401


class Resp:
    def __init__(self, text):
        self.content = [type("B", (), {"type": "text", "text": text})()]


class FakeClaude:
    """messages.create の振る舞いを、制度の名前ごとに決める。"""

    def __init__(self, behavior="ok", issues=None):
        self.behavior, self.issues = behavior, issues or {}
        self.messages = self

    def create(self, **kw):
        if self.behavior == "auth":
            raise AuthenticationError("Error code: 401 - invalid x-api-key")
        text = kw["messages"][0]["content"]
        found = next((v for k, v in self.issues.items() if k in text), [])
        if "upheld" in json.dumps(kw.get("output_config", {})):  # 再確認は指摘を維持
            return Resp(json.dumps({"upheld": True, "evidence_quote": "原文の該当箇所", "reason": "維持"}))
        return Resp(json.dumps({"consistent": not found, "issues": found,
                                "page_mentions_subsidy": True, "amount_in_source": ""}))


def gemini(behavior="ok", issues=None):
    issues = issues or {}

    def f(item, page_text, key):
        if behavior != "ok":
            vs.GEMINI_LAST_ERROR["kind"] = behavior
            return None
        return issues.get(item["name"], []), ""
    return f


def jgrants_ok(item):
    return []


class Harness(unittest.TestCase):
    def setUp(self):
        p = [mock.patch.object(vs, "fetch", lambda url, timeout=30: b"<p>page</p>"),
             mock.patch.object(vs, "verify_jgrants", jgrants_ok),
             mock.patch.object(vs, "recheck_with_gemini", lambda *a: {"upheld": True, "evidence_quote": "", "reason": ""})]
        for x in p:
            x.start()
            self.addCleanup(x.stop)

    def day(self, date, claude, gem, items=None, prev=None, size=3):
        with mock.patch.object(vs, "verify_local_with_gemini", gem):
            return vs.run(items or (JG + [AI]), date, claude, "g-key" if gem else "", prev or {}, size=size)


class TenCases(Harness):
    def test_01_no_keys(self):
        r = vs.run(JG + [AI], "2026-11-01", None, "", {}, size=3)
        self.assertEqual(r["status"], "degraded")
        ai = next(x for x in r["records"] if x["method"] == "ai")
        self.assertEqual(ai["status"], "ai_unavailable")
        self.assertEqual(r["history"]["judge_state"], {"Claude": "unconfigured", "Gemini": "unconfigured"})
        self.assertIn("鍵が未登録", r["outage_issue"])
        self.assertEqual(r["content_issue"], "", "鍵が無いことを掲載データの誤りとして報告しない")

    def test_02_invalid_key_is_not_a_mismatch(self):
        r = self.day("2026-11-02", FakeClaude("auth"), gemini())
        self.assertEqual(r["status"], "degraded")
        self.assertEqual(r["history"]["ng"], 0)
        self.assertEqual(r["content_issue"], "")
        self.assertIn("Claude | 認証エラー", r["outage_issue"])
        self.assertIn("掲載データの誤りではありません", r["outage_issue"])
        ai = next(x for x in r["records"] if x["method"] == "ai")
        self.assertEqual((ai["status"], ai["judge_status"]["Claude"]), ("partial", "auth"))

    def test_03_api_only_run_is_its_own_status(self):
        r = self.day("2026-11-03", FakeClaude(), gemini(), items=JG)
        self.assertEqual(r["status"], "ok_api_only")
        self.assertEqual(r["history"]["judge_state"], {"Claude": "not_exercised", "Gemini": "not_exercised"})
        self.assertEqual(r["outage_issue"], "")

    def test_04_only_claude_ok(self):
        r = self.day("2026-11-04", FakeClaude(), gemini("auth"))
        self.assertEqual(r["status"], "degraded")
        self.assertIn("Gemini | 認証エラー", r["outage_issue"])
        self.assertNotIn("Claude |", r["outage_issue"])

    def test_05_only_gemini_ok(self):
        r = self.day("2026-11-05", FakeClaude("auth"), gemini())
        self.assertIn("Claude | 認証エラー", r["outage_issue"])
        self.assertNotIn("Gemini |", r["outage_issue"])

    def test_06_both_ok_closes_outage(self):
        bad = self.day("2026-11-06", FakeClaude("auth"), gemini("quota"))
        self.assertIn("Gemini | 利用上限", bad["outage_issue"])
        good = self.day("2026-11-07", FakeClaude(), gemini(), prev=bad["state"])
        self.assertEqual(good["status"], "ok")
        self.assertEqual(good["outage_issue"], "")
        self.assertEqual(set(good["changes"]["judge_changed"]), {"Claude", "Gemini"})

    def test_07_alternating_days_do_not_hide_the_outage(self):
        d1 = self.day("2026-11-08", FakeClaude("auth"), gemini())
        d2 = self.day("2026-11-09", FakeClaude("auth"), gemini(), items=JG, prev=d1["state"])
        self.assertEqual(d2["status"], "degraded", "国のAPIだけの回でも、AIの障害は解消扱いにしない")
        self.assertIn("Claude | 認証エラー", d2["outage_issue"])
        self.assertEqual(d2["changes"]["judge_changed"], [], "変化の無い日は通知しない")
        d3 = self.day("2026-11-10", FakeClaude(), gemini(), prev=d2["state"])
        self.assertEqual(d3["outage_issue"], "")

    def test_08_mismatch_and_auth_at_the_same_time(self):
        r = self.day("2026-11-11", FakeClaude("auth"),
                     gemini(issues={AI["name"]: ["締切が原文と違う"]}))
        self.assertEqual(r["status"], "mismatch")
        self.assertIn("原文と食い違う", r["content_issue"])
        self.assertIn("Claude | 認証エラー", r["outage_issue"])
        self.assertEqual(r["changes"]["new_items"], [AI["id"]])

    def test_09_unresolved_issue_stays_open(self):
        d1 = self.day("2026-11-12", FakeClaude(issues={AI["name"]: ["金額が違う"]}), gemini())
        self.assertEqual(d1["status"], "mismatch")
        # 次の日: 別の制度は国のAPIで正常、同じ制度を照合し直したが Gemini が答えない(片方だけ)
        d2 = self.day("2026-11-13", FakeClaude(), gemini("error"), items=JG + [AI, AI2], prev=d1["state"], size=3)
        again = [r for r in d2["records"] if r["id"] == AI["id"]]
        self.assertTrue(again, "未解決の制度を照合し直す")
        self.assertEqual(again[0]["status"], "partial", "照合し直したが、片方のAIだけ")
        self.assertIn(AI["source_url"], d2["content_issue"], "二重照合で確かめるまで解消にしない")
        self.assertEqual(d2["changes"]["resolved"], [])
        self.assertNotEqual(d2["status"], "ok")

    def test_10_only_the_recovered_cause_closes(self):
        bad_jg = dict(JG[0])
        with mock.patch.object(vs, "verify_jgrants", lambda it: ["締切不一致"] if it is bad_jg else []):
            d1 = self.day("2026-11-14", FakeClaude("auth"), gemini(), items=[bad_jg, AI], size=2)
        self.assertEqual(d1["status"], "mismatch")
        self.assertTrue(d1["content_issue"] and d1["outage_issue"])
        fixed = dict(bad_jg)
        d2 = self.day("2026-11-15", FakeClaude("auth"), gemini(), items=[fixed, AI], prev=d1["state"], size=2)
        self.assertEqual(d2["content_issue"], "", "照合し直して正常になった内容の問題だけ閉じる")
        self.assertIn("Claude | 認証エラー", d2["outage_issue"], "AIの障害は残る")
        self.assertEqual(d2["changes"]["resolved"], [bad_jg["id"]])


class MoreCases(Harness):
    def test_gemini_unconfigured_runs_claude_alone(self):
        r = self.day("2026-11-16", FakeClaude(), None)
        self.assertEqual(r["status"], "ok", "Gemini の鍵が無い間は、従来どおり Claude 単独で照合する")
        self.assertEqual(r["outage_issue"], "")

    def test_gemini_unconfigured_still_resolves_claude_mismatch(self):
        d1 = self.day("2026-11-17", FakeClaude(issues={AI["name"]: ["金額が違う"]}), None)
        d2 = self.day("2026-11-18", FakeClaude(), None, prev=d1["state"])
        self.assertEqual(d2["content_issue"], "")
        self.assertEqual(d2["changes"]["resolved"], [AI["id"]])

    def test_quota_midway_is_visible(self):
        calls = {"n": 0}

        def flaky(item, page_text, key):
            calls["n"] += 1
            if calls["n"] == 1:
                return [], ""
            vs.GEMINI_LAST_ERROR["kind"] = "quota"
            return None
        r = self.day("2026-11-19", FakeClaude(), flaky, items=JG + [AI, AI2], prev={
            "open_items": [{"key": AI2["id"], "url": AI2["source_url"], "name": AI2["name"], "since": "2026-11-01",
                            "status": "fetch_error", "issues": []}]}, size=3)
        self.assertEqual(r["status"], "degraded")
        self.assertIn("Gemini | 利用上限", r["outage_issue"], "途中で上限に当たった理由を障害として見せる")

    def test_history_counts_recheck_separately(self):
        d1 = self.day("2026-11-20", FakeClaude(issues={AI["name"]: ["金額が違う"]}), gemini(), items=JG + [AI, AI2], size=3)
        d2 = self.day("2026-11-21", FakeClaude(issues={AI["name"]: ["金額が違う"]}), gemini(),
                      items=JG + [AI, AI2], prev=d1["state"], size=3)
        h = d2["history"]
        rech = [x for x in h["items"] if x.get("rechecked")]
        self.assertLessEqual(h["ng"], h["sample"])
        for x in rech:
            self.assertNotIn("human_verdict", x, "照合し直した分は、人の判定欄を重ねて作らない")
        self.assertEqual(h["ng"] + h["ng_recheck"], sum(x["status"] == "mismatch" for x in h["items"]))


class Parts(unittest.TestCase):
    def test_sample_always_has_an_ai_item(self):
        for d in range(1, 31):
            s = vs.pick_sample(JG + [AI], f"2026-11-{d:02d}", 3)
            self.assertTrue(any(vs.is_ai_item(x) for x in s), d)
            self.assertEqual(len(s), 3)

    def test_sample_without_ai_items_is_unchanged(self):
        import random
        self.assertEqual(vs.pick_sample(JG, "2026-11-01", 3), random.Random("2026-11-01").sample(JG, 3))

    def test_classify_errors(self):
        self.assertEqual(vs.classify_error(AuthenticationError("x")), "auth")

        def http(code, body):
            return urllib.error.HTTPError("https://x?key=SECRET", code, "e", {}, io.BytesIO(body.encode()))
        self.assertEqual(vs.classify_error(http(400, '{"error":{"status":"INVALID_ARGUMENT","details":[{"reason":"API_KEY_INVALID"}]}}')), "auth")
        self.assertEqual(vs.classify_error(http(429, "RESOURCE_EXHAUSTED")), "quota")
        self.assertEqual(vs.classify_error(http(500, "boom")), "error")
        self.assertEqual(vs.classify_error(ValueError("not json")), "error")

    def test_redact_keys(self):
        msg = vs.redact("url https://g/v1beta/models/m:generateContent?key=AIzaREALKEY123&x=1 sk-ant-api03-abcdefSECRETSECRET")
        self.assertNotIn("AIzaREALKEY123", msg)
        self.assertNotIn("SECRETSECRET", msg)

    def test_jgrants_fetch_failure_is_not_a_mismatch(self):
        with mock.patch.object(vs, "verify_jgrants", lambda it: [f"{vs.JGRANTS_FETCH_FAILED}: timeout"]):
            r = vs.run(JG[:3], "2026-11-20", FakeClaude(), "g-key", {}, size=3)
        self.assertEqual(r["status"], "fetch_error")
        self.assertEqual(r["history"]["ng"], 0)
        self.assertIn("出典を開けない", r["content_issue"])

    def test_removed_listing_resolves(self):
        prev = {"open_items": [{"key": "gone-1", "url": "https://gone", "name": "終わった制度", "since": "2026-11-01",
                                "status": "mismatch", "issues": []}], "judges": {}}
        with mock.patch.object(vs, "verify_jgrants", jgrants_ok):
            r = vs.run(JG[:3], "2026-11-21", None, "", prev, size=3)
        self.assertEqual(r["changes"]["resolved"], ["gone-1"])
        self.assertEqual(r["content_issue"], "")

    def test_changed_source_url_is_rechecked_not_resolved(self):
        prev = {"open_items": [{"key": AI["id"], "url": "https://old", "name": AI["name"], "since": "2026-11-01",
                                "status": "fetch_error", "issues": []}], "judges": {}}
        with mock.patch.object(vs, "fetch", lambda url, timeout=30: (_ for _ in ()).throw(OSError("down"))), \
                mock.patch.object(vs, "verify_jgrants", jgrants_ok):
            r = vs.run(JG + [AI], "2026-11-22", FakeClaude(), "", prev, size=3)
        self.assertEqual(r["changes"]["resolved"], [], "出典URLを直しても、照合し直すまで解決にしない")
        self.assertIn(AI["source_url"], r["content_issue"])

    def test_unexpected_error_in_one_item_does_not_stop_the_run(self):
        def boom(it):
            raise AttributeError("'list' object has no attribute 'get'")
        with mock.patch.object(vs, "verify_jgrants", boom):
            r = vs.run(JG[:3], "2026-11-23", FakeClaude(), "", {}, size=3)
        self.assertEqual(r["status"], "fetch_error")
        self.assertEqual(len(r["history"]["items"]), 3)


def load(tmp, name):
    with open(os.path.join(tmp, name), encoding="utf-8") as f:
        return json.load(f)


class MainWritesEveryRun(unittest.TestCase):
    """失敗した回・異常終了した回も、履歴に必ず残す。"""

    def paths(self, tmp, data):
        d = os.path.join(tmp, "data.json")
        with open(d, "w", encoding="utf-8") as f:
            f.write(data)
        return [mock.patch.object(vs, "DATA_PATH", d),
                mock.patch.object(vs, "HISTORY_PATH", os.path.join(tmp, "h.json")),
                mock.patch.object(vs, "STATE_PATH", os.path.join(tmp, "s.json")),
                mock.patch.object(vs, "STATUS_PATH", os.path.join(tmp, "st.json")),
                mock.patch.object(vs, "REPORT_PATH", os.path.join(tmp, "r.txt")),
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": ""})]

    def test_failed_run_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            ps = self.paths(tmp, json.dumps({"items": JG + [AI]}))
            for p in ps:
                p.start()
            try:
                with mock.patch.object(vs, "verify_jgrants", jgrants_ok):
                    code = vs.main()
                h, st = load(tmp, "h.json"), load(tmp, "st.json")
            finally:
                for p in ps:
                    p.stop()
        self.assertEqual(code, 1)
        self.assertEqual(h[-1]["status"], "degraded")
        self.assertEqual(st["status"], "degraded")
        self.assertTrue(st["outage_issue"])

    def test_corrupt_state_is_a_crash_not_an_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            ps = self.paths(tmp, json.dumps({"items": JG + [AI]}))
            with open(os.path.join(tmp, "s.json"), "w", encoding="utf-8") as f:
                f.write("{broken")
            for p in ps:
                p.start()
            try:
                code = vs.main()
                st = load(tmp, "st.json")
            finally:
                for p in ps:
                    p.stop()
        self.assertEqual(code, 2, "状態ファイルが読めないのに空として進めると、未解決が黙って消える")
        self.assertEqual(st["status"], "crash")

    def test_crash_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            ps = self.paths(tmp, "{broken")
            for p in ps:
                p.start()
            try:
                code = vs.main()
                h, st = load(tmp, "h.json"), load(tmp, "st.json")
            finally:
                for p in ps:
                    p.stop()
        self.assertEqual(code, 2)
        self.assertEqual(h[-1]["status"], "crash")
        self.assertIn("異常終了", st["outage_issue"], "異常終了は障害の Issue に載せる(閉じる合図にしない)")
        self.assertNotIn("content_issue", st, "異常終了の回は内容の Issue を閉じる合図を出さない")


if __name__ == "__main__":
    unittest.main()
