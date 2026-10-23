# -*- coding: utf-8 -*-
"""scripts/note_api.py のテスト(結果マガ売上自動化 Task 1)。実行: python3 -m pytest tests/test_note_api.py"""
import io
import json
import os
import socket
import sys
import urllib.error
import urllib.parse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import note_api  # noqa: E402
from note_api import NoteAPIError, NoteMetrics, fetch_note_metrics  # noqa: E402

THREE_ARTICLES = {
    "articles": [
        {
            "id": "n_a",
            "views": 1200,
            "likes": 30,
            "sales": [
                {"buyer_id": "u1", "amount_jpy": 1280, "buyer_profile": {"segment": "経営者", "follower": True}},
                {"buyer_id": "u2", "amount_jpy": 1280, "buyer_profile": {"segment": "個人事業主"}},
            ],
        },
        {
            "id": "n_b",
            "views": 800,
            "likes": 12,
            "sales": [
                {"buyer_id": "u1", "amount_jpy": 980, "buyer_profile": {"segment": "経営者", "follower": True}},
            ],
        },
        {"id": "n_c", "views": 450, "likes": 5, "sales": []},
    ]
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def install_urlopen(monkeypatch, outcomes):
    """outcomes を順に返す/投げる urlopen を仕込み、受けたリクエストを返す。"""
    calls = []
    seq = list(outcomes)

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        item = seq.pop(0)
        if isinstance(item, BaseException):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(note_api.urllib.request, "urlopen", fake_urlopen)
    return calls


def http_error(code):
    return urllib.error.HTTPError("https://example.test", code, "err", {}, io.BytesIO(b""))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("NOTE_API_TOKEN", raising=False)
    monkeypatch.setenv("NOTE_API_BASE_URL", "https://note.example.test/api")


def test_fetch_note_metrics_success(monkeypatch):
    calls = install_urlopen(monkeypatch, [THREE_ARTICLES])
    sleeps = []

    m = fetch_note_metrics("tok-123", "2026-W40", sleep=sleeps.append)

    assert isinstance(m, NoteMetrics)
    assert m.week == "2026-W40"
    assert m.views_by_article == {"n_a": 1200, "n_b": 800, "n_c": 450}
    assert m.total_likes == 47
    assert m.total_sales_jpy == 1280 + 1280 + 980
    assert m.buyer_ids == ["u1", "u2"]  # 重複購入者は1回だけ
    assert m.buyer_profiles, "buyer_profiles must be non-empty"
    assert m.buyer_profiles == [
        {"buyer_id": "u1", "segment": "経営者", "follower": True},
        {"buyer_id": "u2", "segment": "個人事業主"},
    ]
    assert sleeps == []

    req = calls[0]
    assert req.get_header("Authorization") == "Bearer tok-123"
    parsed = urllib.parse.urlparse(req.full_url)
    assert parsed.path == "/api/v1/articles"
    q = urllib.parse.parse_qs(parsed.query)
    assert q == {"published_after": ["2026-09-28"], "published_before": ["2026-10-04"]}


def test_fetch_note_metrics_api_timeout_retries(monkeypatch):
    calls = install_urlopen(
        monkeypatch,
        [socket.timeout("timed out"), urllib.error.URLError(socket.timeout("timed out")), THREE_ARTICLES],
    )
    sleeps = []

    m = fetch_note_metrics("tok-123", "2026-W40", sleep=sleeps.append)

    assert m.total_sales_jpy == 3540
    assert len(calls) == 3
    assert sleeps == [5, 10]


def test_503_retries_three_times_then_raises(monkeypatch):
    calls = install_urlopen(monkeypatch, [http_error(503)] * 4)
    sleeps = []

    with pytest.raises(NoteAPIError, match="3回リトライ"):
        fetch_note_metrics("tok-123", "2026-W40", sleep=sleeps.append)

    assert len(calls) == 4  # 初回 + 3回リトライ
    assert sleeps == [5, 10, 15]


def test_token_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("NOTE_API_TOKEN", "env-tok")
    calls = install_urlopen(monkeypatch, [THREE_ARTICLES])
    fetch_note_metrics("", "2026-W40", sleep=lambda s: None)
    assert calls[0].get_header("Authorization") == "Bearer env-tok"


def test_missing_token_raises_clear_error(monkeypatch):
    calls = install_urlopen(monkeypatch, [])
    with pytest.raises(NoteAPIError, match="NOTE_API_TOKEN"):
        fetch_note_metrics("", "2026-W40", sleep=lambda s: None)
    assert calls == []


def test_invalid_token_raises_without_retry(monkeypatch):
    calls = install_urlopen(monkeypatch, [http_error(401)])
    sleeps = []
    with pytest.raises(NoteAPIError, match="HTTP 401"):
        fetch_note_metrics("bad", "2026-W40", sleep=sleeps.append)
    assert len(calls) == 1 and sleeps == []


def test_missing_views_is_error_not_zero(monkeypatch):
    """欠損を0で埋めない(捏造ゼロ)。"""
    install_urlopen(monkeypatch, [{"articles": [{"id": "n_x", "likes": 3}]}])
    with pytest.raises(NoteAPIError, match="views"):
        fetch_note_metrics("tok", "2026-W40", sleep=lambda s: None)


def test_invalid_week_format(monkeypatch):
    install_urlopen(monkeypatch, [])
    with pytest.raises(NoteAPIError, match="YYYY-Www"):
        fetch_note_metrics("tok", "2026-10-01", sleep=lambda s: None)
