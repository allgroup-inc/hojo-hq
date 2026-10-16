"""IG 自動化(沖縄企業のミカタ) Task 14: verify_mikata_seido.py の検査。

通信とAPIはすべて差し替える(FakeClaude / FakeGemini / fake getter)。
実データは毎日の巡回で締切が動くため、固定の today(2026-09-29)で判定する。
"""
import datetime as dt
import json
import os
import socket
import sys
import urllib.error
from types import SimpleNamespace

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import verify_mikata_seido as vm  # noqa: E402
from verify_mikata_seido import (  # noqa: E402
    is_priority_1,
    run,
    stale_info,
    verify_subsidy_dual_check,
)

REAL_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "subsidies.json")
TODAY = dt.date(2026, 9, 29)
NOW = dt.datetime(2026, 9, 29, 3, 0, 0, tzinfo=dt.timezone.utc)
SCHEMA_KEYS = {"claude_verified", "gemini_verified", "timestamp", "conflict", "details"}
DETAIL_KEYS = {"amount_match", "deadline_match", "source_reachable", "error_msg"}


# ------------------------------------------------------------------ fakes

class FakeClaude:
    """anthropic.Anthropic の client.beta.messages.create だけを真似る。"""

    def __init__(self, answer=None, exc=None):
        self.answer, self.exc, self.calls = answer, exc, 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        if self.exc:
            raise self.exc
        text = SimpleNamespace(type="text", text=json.dumps(self.answer))
        return SimpleNamespace(stop_reason="end_turn", content=[text])


class FakeGemini:
    def __init__(self, answer=None):
        self.answer, self.calls = answer, 0

    def extract(self, prompt):
        self.calls += 1
        return self.answer  # None = API失敗


def ext(deadline="2026-12-31", amount=450_000_000, area="全国", is_free=True):
    return {"deadline_date": deadline, "days_to_deadline": None,
            "max_amount_yen": amount, "target_area": area, "is_free": is_free}


def html_getter(body="<html><body>制度の本文</body></html>", robots=None):
    def getter(url, timeout):
        if url.endswith("/robots.txt"):
            if robots is None:
                raise urllib.error.HTTPError(url, 404, "nf", {}, None)
            return robots.encode()
        return body.encode("utf-8")
    return getter


def error_getter(exc, counter=None):
    def getter(url, timeout):
        if url.endswith("/robots.txt"):
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        if counter is not None:
            counter.append(url)
        raise exc
    return getter


def subsidy(sid="s1", priority=1, amount=450_000_000, deadline="2026-12-31",
            area="全国", url=None):
    return {"id": sid, "name": f"テスト制度{sid}", "ig_priority": priority,
            "max_amount": amount, "deadline": deadline, "target_area": area,
            "source_url": url or f"https://example.go.jp/{sid}", "status": "募集中"}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(vm.time, "sleep", lambda s: None)


def check(s, claude, gemini=None, getter=None):
    return verify_subsidy_dual_check(s, claude, gemini, timeout=5,
                                     getter=getter or html_getter(), today=TODAY, now=NOW)


# ------------------------------------------------------------------ brief の3本

def test_verify_priority_1_first():
    """優先1(ig_priority<=5・1億円以上・残り30日以上)は Claude+Gemini の両方で照合し、
    それ以外は Claude 単独(Gemini を呼ばない)。"""
    with open(REAL_DATA, encoding="utf-8") as f:
        items = json.load(f)["items"]
    p1 = [s for s in items if is_priority_1(s, TODAY)]
    assert p1, "実データに優先1が1件もない(選定条件か data を確認)"
    for s in p1:
        assert s["ig_priority"] <= 5
        assert (s.get("max_amount_yen") or s.get("max_amount")) >= 100_000_000

    target = dict(p1[0])
    agree = ext(deadline=target["deadline"], amount=target["max_amount"], area=target["target_area"])
    api = json.dumps({"result": [{"title": target["name"], "acceptance_end_datetime": None,
                                  "subsidy_max_limit": target["max_amount"],
                                  "target_area_search": target["target_area"], "detail": "本文"}]})
    getter = html_getter(api)
    claude, gemini = FakeClaude(agree), FakeGemini(agree)
    result = check(target, claude, gemini, getter)

    assert set(result) == SCHEMA_KEYS and DETAIL_KEYS <= set(result["details"])
    assert claude.calls == 1 and gemini.calls == 1, "優先1はダブルチェックする"
    assert result["claude_verified"] is True and result["gemini_verified"] is True
    assert result["conflict"] is False
    dt.datetime.strptime(result["timestamp"], "%Y-%m-%dT%H:%M:%SZ")

    # 優先1でない制度(1億円未満)は Gemini を呼ばない
    small = subsidy("small", priority=2, amount=5_000_000)
    claude2, gemini2 = FakeClaude(ext(amount=5_000_000)), FakeGemini(ext(amount=5_000_000))
    r2 = check(small, claude2, gemini2)
    assert claude2.calls == 1 and gemini2.calls == 0
    assert r2["gemini_verified"] is None and r2["claude_verified"] is True
    assert r2["details"]["dual_check"] == "claude_only"


def test_conflict_detection():
    """Claude と Gemini が締切で割れたら conflict=True・deadline_match=False・両方 False。
    自動修正せず、人の確認へ回す(掲載データは書き換えない)。"""
    s = subsidy("test_conflict", amount=450_000_000, deadline="2026-12-31")
    before = dict(s)
    result = check(s, FakeClaude(ext(deadline="2026-12-31")),
                   FakeGemini(ext(deadline="2027-01-15")))

    assert result["conflict"] is True
    assert result["details"]["deadline_match"] is False
    assert result["details"]["amount_match"] is True
    assert result["claude_verified"] is False and result["gemini_verified"] is False
    assert result["details"]["needs_manual_review"] is True
    assert "deadline" in result["details"]["conflict_fields"]
    # 両AIの抽出値は人が見比べられるよう残す
    assert result["details"]["claude_extracted"]["deadline"] == "2026-12-31"
    assert result["details"]["gemini_extracted"]["deadline"] == "2027-01-15"
    assert s == before, "照合は掲載データを自動修正しない"


def test_source_unreachable_handling():
    """403/404/タイムアウトは source_reachable=False で記録し、全体は止めない。
    403 と 404 はステータスまで分けて記録。4xx は再試行せず、タイムアウトは2回再試行。"""
    calls_403, calls_404, calls_to = [], [], []
    e403 = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    e404 = urllib.error.HTTPError("u", 404, "Not Found", {}, None)

    r403 = check(subsidy("a"), FakeClaude(ext()), getter=error_getter(e403, calls_403))
    r404 = check(subsidy("b"), FakeClaude(ext()), getter=error_getter(e404, calls_404))
    rto = check(subsidy("c"), FakeClaude(ext()), getter=error_getter(socket.timeout(), calls_to))

    for r in (r403, r404, rto):
        assert r["details"]["source_reachable"] is False
        assert r["claude_verified"] is None and r["gemini_verified"] is None
        assert r["conflict"] is False
    assert r403["details"]["error_msg"] == "HTTPError 403"
    assert r404["details"]["error_msg"] == "HTTPError 404"
    assert rto["details"]["error_msg"] == "Timeout after 5s"
    assert len(calls_403) == 1 and len(calls_404) == 1, "403/404 は再試行しない"
    assert len(calls_to) == 1 + vm.MAX_RETRIES, "タイムアウトは再試行する"

    # 実行環境のプロキシ拒否は、サイト側の 403 と区別して記録する
    proxy = urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))
    rpx = check(subsidy("d"), FakeClaude(ext()), getter=error_getter(proxy))
    assert rpx["details"]["error_msg"].startswith("ProxyBlocked")
    assert rpx["details"]["source_reachable"] is False

    # run() は1件が取得不可でも残りを照合し続ける
    good, bad = subsidy("good"), subsidy("bad", url="https://okinawa-ric.jp/x.html")

    def mixed(url, timeout):
        if url.endswith("/robots.txt"):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        if "okinawa-ric" in url:
            raise e403
        return b"<p>ok</p>"

    logs = []
    recs = run([bad, good], FakeClaude(ext()), None, timeout=5, today=TODAY, now=NOW,
               getter=mixed, log=logs.append)
    assert [r["source_reachable"] for r in recs] == [False, True]
    assert bad["verified"]["details"]["error_msg"] == "HTTPError 403"
    assert good["verified"]["claude_verified"] is True


# ------------------------------------------------------------------ 追加の約束

def test_gemini_missing_is_claude_only_fallback():
    """GEMINI_API_KEY 未設定(gemini_client=None)は優先1でもエラーにせず Claude 単独。"""
    r = check(subsidy("p1"), FakeClaude(ext()), None)
    assert r["claude_verified"] is True and r["gemini_verified"] is None
    assert r["details"]["dual_check"] == "required(gemini_unavailable)"
    assert r["details"]["error_msg"] is None


def test_priority1_gemini_failure_does_not_assert():
    """優先1で Gemini だけ失敗したら、Claude の一致は断定しない(None)。
    ただし Claude が検知した不一致(False)は隠さない。"""
    r = check(subsidy("p1"), FakeClaude(ext()), FakeGemini(None))
    assert r["claude_verified"] is None and r["gemini_verified"] is None
    assert r["conflict"] is False and r["details"]["dual_check"] == "incomplete"

    r2 = check(subsidy("p1"), FakeClaude(ext(amount=1)), FakeGemini(None))
    assert r2["claude_verified"] is False


def test_both_ais_agree_listing_is_wrong():
    """両AIが一致して掲載値と違う → conflict ではなく両方 False(掲載の誤り候補)。"""
    r = check(subsidy("p1"), FakeClaude(ext(amount=300_000_000)),
              FakeGemini(ext(amount=300_000_000)))
    assert r["conflict"] is False
    assert r["claude_verified"] is False and r["gemini_verified"] is False
    assert r["details"]["amount_match"] is False and r["details"]["deadline_match"] is True


def test_unlisted_value_is_not_a_mismatch():
    """掲載が「要確認」/None の項目は比較しない(未掲載は矛盾ではない・議事_20260817)。"""
    s = subsidy("local", priority=3, amount=None, deadline="要確認", area="沖縄県")
    r = check(s, FakeClaude(ext(deadline="2026-11-30", amount=2_000_000, area="沖縄県")))
    assert r["claude_verified"] is True  # 地域だけ比較できて一致
    assert r["details"]["deadline_match"] is None and r["details"]["amount_match"] is None

    r2 = check(s, FakeClaude(ext(deadline=None, amount=None, area="")))
    assert r2["claude_verified"] is None, "比較できる項目がなければ断定しない"


def test_robots_unreadable_is_permitted_but_disallow_blocks():
    """robots.txt が取れない(403)ときは許可扱い。明示の Disallow は取得しない。"""
    assert vm.robots_allows("https://a.jp/x", getter=error_getter(
        urllib.error.HTTPError("u", 403, "F", {}, None))) is True
    r = check(subsidy("r", priority=9), FakeClaude(ext()),
              getter=html_getter(robots="User-agent: *\nDisallow: /\n"))
    assert r["details"]["source_reachable"] is False
    assert "robots" in r["details"]["error_msg"]


def test_stale_verification_flagged():
    s = subsidy("old")
    s["verified"] = {"timestamp": "2026-08-01T00:00:00Z"}
    age, stale = stale_info(s, NOW)
    assert age == 59 and stale is True
    s["verified"] = {"timestamp": "2026-09-20T00:00:00Z"}
    assert stale_info(s, NOW)[1] is False
    assert stale_info(subsidy("never"), NOW) is None

    logs = []
    s["verified"] = {"timestamp": "2026-08-01T00:00:00Z"}
    run([s], FakeClaude(ext()), None, timeout=5, today=TODAY, now=NOW,
        getter=html_getter(), log=logs.append)
    assert any(line.startswith("[stale]") for line in logs)


def test_claude_api_failure_is_null_not_crash():
    r = check(subsidy("x", priority=9), FakeClaude(exc=RuntimeError("overloaded")))
    assert r["claude_verified"] is None and r["details"]["source_reachable"] is True
    assert "overloaded" in r["details"]["error_msg"]


def test_output_schema_compatible_with_task13_reader():
    """Task 13 の _verified_ng がこの結果を正しく読めること(矛盾は NG、未照合は NG にしない)。"""
    import generate_ig_posts_mikata as gen
    conflict = check(subsidy("c"), FakeClaude(ext(deadline="2026-12-31")),
                     FakeGemini(ext(deadline="2027-01-15")))
    ok = check(subsidy("o"), FakeClaude(ext()), FakeGemini(ext()))
    unreachable = check(subsidy("u"), FakeClaude(ext()),
                        getter=error_getter(urllib.error.HTTPError("u", 403, "F", {}, None)))
    assert gen._verified_ng({"verified": conflict}) is True
    assert gen._verified_ng({"verified": ok}) is False
    assert gen._verified_ng({"verified": unreachable}) is False


def test_main_without_api_key_does_not_write(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    p = tmp_path / "subsidies.json"
    original = json.dumps({"items": [subsidy("k")]}, ensure_ascii=False)
    p.write_text(original, encoding="utf-8")
    assert vm.main(["--data", str(p), "--audit-log", str(tmp_path / "a.jsonl")]) == 2
    assert p.read_text(encoding="utf-8") == original
