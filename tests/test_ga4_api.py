# -*- coding: utf-8 -*-
"""scripts/ga4_api.py のテスト(結果マガ売上自動化 Task 2)。実行: python3 -m pytest tests/test_ga4_api.py"""
import io
import json
import logging
import os
import socket
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import ga4_api  # noqa: E402
from ga4_api import GA4APIError, GA4Metrics, compute_ctr, fetch_ga4_metrics  # noqa: E402

TOKEN = "ya29.SECRET-TOKEN-DO-NOT-LOG"
PROPERTY = "123456789"


def token_provider():
    return TOKEN


def mrow(*metrics, dims=()):
    row = {"metricValues": [{"value": str(m)} for m in metrics]}
    if dims:
        row["dimensionValues"] = [{"value": d} for d in dims]
    return row


TOTALS = {"rows": [mrow(420, 1350)], "rowCount": 1}
ARTICLE_EVENTS = {
    "rows": [
        mrow(200, dims=("page_view", "n_a")),
        mrow(30, dims=("article_click", "n_a")),
        mrow(100, dims=("page_view", "n_b")),          # クリック無し → CTR 0.0
        mrow(5, dims=("article_click", "n_c")),        # PV無し → CTR を作らない
        mrow(900, dims=("page_view", "(not set)")),    # article_id 無し → 除外
        mrow(2, dims=("article_click", "")),
    ],
    "rowCount": 6,
}
SEGMENTS = {"rows": [mrow(310, dims=("new",)), mrow(95, dims=("returning",))], "rowCount": 2}


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


def http_error(code, message=""):
    body = json.dumps({"error": {"code": code, "message": message}}).encode("utf-8")
    return urllib.error.HTTPError("https://analyticsdata.googleapis.com", code, "err", {}, io.BytesIO(body))


def report_kind(body: dict) -> str:
    dims = [d["name"] for d in body.get("dimensions", [])]
    if not dims:
        return "totals"
    if "newVsReturning" in dims:
        return "segments"
    return "articles"


def install_urlopen(monkeypatch, responses):
    """responses: {report_kind: [結果 or 例外, ...]}。種類ごとに順に返す/投げる。受けたリクエストを返す。"""
    calls = []
    queues = {k: list(v) for k, v in responses.items()}

    def fake_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        calls.append({"url": req.full_url, "headers": dict(req.header_items()), "body": body, "method": req.get_method()})
        outcome = queues[report_kind(body)].pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)

    monkeypatch.setattr(ga4_api.urllib.request, "urlopen", fake_urlopen)
    return calls


def ok_responses():
    return {"totals": [TOTALS], "articles": [ARTICLE_EVENTS], "segments": [SEGMENTS]}


# --- CTR 計算 -------------------------------------------------------------

def test_compute_ctr_nonzero():
    assert compute_ctr({"a": 200}, {"a": 30}) == {"a": pytest.approx(0.15)}


def test_compute_ctr_zero_clicks_is_zero():
    assert compute_ctr({"a": 100}, {}) == {"a": 0.0}


def test_compute_ctr_zero_pageviews_is_not_fabricated(caplog):
    caplog.set_level(logging.WARNING, logger="ga4_api")
    assert compute_ctr({}, {"a": 5}) == {}
    assert "page_view=0" in caplog.text


def test_compute_ctr_keeps_values_above_one():
    assert compute_ctr({"a": 4}, {"a": 6}) == {"a": pytest.approx(1.5)}


# --- 取得の本流 -------------------------------------------------------------

def test_fetch_ga4_metrics_success(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="ga4_api")
    calls = install_urlopen(monkeypatch, ok_responses())

    m = fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider)

    assert isinstance(m, GA4Metrics)
    assert m.week == "2026-W40"
    assert m.sessions == 420
    assert m.pageviews == 1350
    assert m.ctr_by_article == {"n_a": pytest.approx(0.15), "n_b": 0.0}
    assert "n_c" not in m.ctr_by_article and "(not set)" not in m.ctr_by_article
    assert m.user_segment_counts == {"new": 310, "returning": 95}
    assert set(m.to_dict()) == {"week", "sessions", "pageviews", "ctr_by_article", "user_segment_counts"}

    assert len(calls) == 3
    for c in calls:
        assert c["method"] == "POST"
        assert c["url"] == f"https://analyticsdata.googleapis.com/v1beta/properties/{PROPERTY}:runReport"
        assert c["headers"]["Authorization"] == f"Bearer {TOKEN}"
        assert c["body"]["dateRanges"] == [{"startDate": "2026-09-28", "endDate": "2026-10-04"}]
    totals_body = calls[0]["body"]
    assert [x["name"] for x in totals_body["metrics"]] == ["sessions", "screenPageViews"]
    art_body = calls[1]["body"]
    assert art_body["dimensionFilter"]["filter"]["inListFilter"]["values"] == ["page_view", "article_click"]
    assert [d["name"] for d in art_body["dimensions"]] == ["eventName", "customEvent:article_id"]

    # 要求/応答のログは出る。トークンは出ない
    assert "runReport" in caplog.text and "status=200" in caplog.text and "rows=6" in caplog.text
    assert TOKEN not in caplog.text


def test_property_id_accepts_resource_name(monkeypatch):
    calls = install_urlopen(monkeypatch, ok_responses())
    fetch_ga4_metrics(f"properties/{PROPERTY}", "2026-W40", token_provider=token_provider)
    assert calls[0]["url"].endswith(f"/properties/{PROPERTY}:runReport")


def test_empty_week_returns_real_zeros(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="ga4_api")
    install_urlopen(monkeypatch, {"totals": [{"rowCount": 0}], "articles": [{"rowCount": 0}],
                                  "segments": [{"rowCount": 0}]})
    m = fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider)
    assert (m.sessions, m.pageviews, m.ctr_by_article, m.user_segment_counts) == (0, 0, {}, {})
    assert "データ行がありません" in caplog.text


def test_pagination_collects_all_rows(monkeypatch):
    monkeypatch.setattr(ga4_api, "PAGE_LIMIT", 2)
    page1 = {"rows": [mrow(10, dims=("page_view", "n_a")), mrow(1, dims=("article_click", "n_a"))], "rowCount": 3}
    page2 = {"rows": [mrow(4, dims=("page_view", "n_b"))], "rowCount": 3}
    calls = install_urlopen(monkeypatch, {"totals": [TOTALS], "articles": [page1, page2], "segments": [SEGMENTS]})
    m = fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider)
    assert m.ctr_by_article == {"n_a": pytest.approx(0.1), "n_b": 0.0}
    offsets = [c["body"]["offset"] for c in calls if report_kind(c["body"]) == "articles"]
    assert offsets == ["0", "2"]


# --- 失敗は黙らない ---------------------------------------------------------

def test_503_then_success_retries(monkeypatch):
    sleeps = []
    responses = ok_responses()
    responses["totals"] = [http_error(503), socket.timeout("timed out"), TOTALS]
    install_urlopen(monkeypatch, responses)
    m = fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider, sleep=sleeps.append)
    assert m.sessions == 420
    assert sleeps == [5, 10]


def test_timeouts_exhausted_raise(monkeypatch):
    sleeps = []
    install_urlopen(monkeypatch, {"totals": [urllib.error.URLError(socket.timeout("t"))] * 4})
    with pytest.raises(GA4APIError, match="3回リトライ"):
        fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider, sleep=sleeps.append)
    assert sleeps == [5, 10, 15]


def test_403_raises_without_retry(monkeypatch):
    sleeps = []
    calls = install_urlopen(monkeypatch, {"totals": [http_error(403, "User does not have sufficient permissions")]})
    with pytest.raises(GA4APIError, match="閲覧者"):
        fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider, sleep=sleeps.append)
    assert len(calls) == 1 and sleeps == []


def test_missing_custom_dimension_explains_fix(monkeypatch):
    responses = ok_responses()
    responses["articles"] = [http_error(400, "Field customEvent:article_id is not a valid dimension.")]
    install_urlopen(monkeypatch, responses)
    with pytest.raises(GA4APIError, match="カスタムディメンション"):
        fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider)


def test_non_integer_metric_raises_instead_of_zero(monkeypatch):
    responses = ok_responses()
    responses["totals"] = [{"rows": [{"metricValues": [{"value": "abc"}, {"value": "10"}]}], "rowCount": 1}]
    install_urlopen(monkeypatch, responses)
    with pytest.raises(GA4APIError, match="sessions"):
        fetch_ga4_metrics(PROPERTY, "2026-W40", token_provider=token_provider)


@pytest.mark.parametrize("pid", ["", "G-TW6M6WFB9T", "abc"])
def test_bad_property_id(pid):
    with pytest.raises(GA4APIError, match="property_id"):
        fetch_ga4_metrics(pid, "2026-W40", token_provider=token_provider)


def test_bad_week_format():
    with pytest.raises(GA4APIError, match="ISO週"):
        fetch_ga4_metrics(PROPERTY, "2026-09-28", token_provider=token_provider)


# --- 認証情報(GOOGLE_APPLICATION_CREDENTIALS)-----------------------------

def test_credentials_env_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    with pytest.raises(GA4APIError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        fetch_ga4_metrics(PROPERTY, "2026-W40")


def test_credentials_file_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "nope.json"))
    with pytest.raises(GA4APIError, match="ファイルがありません"):
        fetch_ga4_metrics(PROPERTY, "2026-W40")


def test_credentials_file_not_json(monkeypatch, tmp_path):
    p = tmp_path / "key.json"
    p.write_text("-----BEGIN PRIVATE KEY----- not json", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(p))
    with pytest.raises(GA4APIError) as ei:
        fetch_ga4_metrics(PROPERTY, "2026-W40")
    assert "JSON" in str(ei.value) and "PRIVATE KEY" not in str(ei.value)


def test_credentials_file_not_service_account(monkeypatch, tmp_path):
    p = tmp_path / "key.json"
    p.write_text(json.dumps({"type": "authorized_user"}), encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(p))
    with pytest.raises(GA4APIError, match="サービスアカウント鍵ではありません"):
        fetch_ga4_metrics(PROPERTY, "2026-W40")
