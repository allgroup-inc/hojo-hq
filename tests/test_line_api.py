# -*- coding: utf-8 -*-
"""scripts/line_api.py のテスト(結果マガ売上自動化 Task 3)。実行: python3 -m pytest tests/test_line_api.py"""
import io
import json
import logging
import os
import socket
import sys
import urllib.error
import urllib.parse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import line_api  # noqa: E402
from line_api import (  # noqa: E402
    SOURCE_API,
    SOURCE_CSV,
    LINEAPIError,
    LINEAPIUnavailable,
    LINEMetrics,
    aggregation_unit,
    compute_rates,
    fetch_line_metrics,
    fetch_line_metrics_with_source,
    load_line_metrics_csv,
)

TOKEN = "LINE-SECRET-TOKEN-DO-NOT-LOG"
CHANNEL = "2001234567"
WEEK = "2026-W40"  # 2026-09-28(月)〜2026-10-04(日)
DELIVERED = {"high_engagement": 40, "active_reader": 50, "line_only": 0}

FOLLOWERS = {"status": "ready", "followers": 152, "targetedReaches": 140, "blocks": 9}
UNITS = {
    "kekka_high_engagement": {"overview": {"uniqueImpression": 31, "uniqueClick": 12},
                              "messages": [{"seq": 1}], "clicks": []},
    "kekka_active_reader": {"overview": {"uniqueImpression": 20, "uniqueClick": None},
                            "messages": [{"seq": 1}, {"seq": 2}], "clicks": []},
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


def http_error(code, message=""):
    body = json.dumps({"message": message}).encode("utf-8")
    return urllib.error.HTTPError("https://api.line.me", code, "err", {}, io.BytesIO(body))


def kind_of(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.path == "/v2/oauth/verify":
        return "verify"
    if parsed.path == "/v2/bot/insight/followers":
        return "followers"
    if parsed.path == "/v2/bot/insight/message/event/aggregation":
        return urllib.parse.parse_qs(parsed.query)["customAggregationUnit"][0]
    raise AssertionError(f"想定外のURL {url}")


def install_urlopen(monkeypatch, responses):
    """responses: {kind: [結果 or 例外, ...]}。種類ごとに順に返す/投げる。受けたリクエストを返す。"""
    calls = []
    queues = {k: list(v) for k, v in responses.items()}

    def fake_urlopen(req, timeout=None):
        kind = kind_of(req.full_url)
        calls.append({"kind": kind, "url": req.full_url, "method": req.get_method(),
                      "headers": dict(req.header_items()), "data": req.data})
        outcome = queues[kind].pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)

    monkeypatch.setattr(line_api.urllib.request, "urlopen", fake_urlopen)
    return calls


def ok_responses():
    r = {"verify": [{"client_id": CHANNEL, "expires_in": 999, "scope": "P CM"}], "followers": [FOLLOWERS]}
    r.update({unit: [payload] for unit, payload in UNITS.items()})
    return r


def write_csv(tmp_path, week=WEEK, text=None):
    if text is None:
        text = (
            "week,registered_count,segment,delivered,unique_opens,unique_clicks\n"
            f"{week},150,high_engagement,40,30,10\n"
            f"{week},150,active_reader,50,25,5\n"
            f"{week},150,discovery_seeker,20,0,0\n"
            f"{week},150,line_only,80,,\n"
        )
    p = tmp_path / f"line_segment_stats_{week}.csv"
    p.write_text(text, encoding="utf-8")
    return p


# --- 率の計算 -----------------------------------------------------------------

def test_compute_rates_basic():
    o, c = compute_rates({"a": 40}, {"a": 30}, {"a": 10})
    assert o == {"a": pytest.approx(0.75)} and c == {"a": pytest.approx(0.25)}


def test_compute_rates_real_zero_is_kept():
    assert compute_rates({"a": 20}, {"a": 0}, {"a": 0}) == ({"a": 0.0}, {"a": 0.0})


def test_compute_rates_zero_delivered_not_fabricated(caplog):
    caplog.set_level(logging.WARNING, logger="line_api")
    assert compute_rates({"a": 0}, {"a": 0}, {"a": 0}) == ({}, {})
    assert "配信0人" in caplog.text


def test_compute_rates_unknown_count_not_filled_with_zero():
    o, c = compute_rates({"a": 40}, {"a": 30}, {"a": None})
    assert o == {"a": pytest.approx(0.75)} and c == {}


def test_compute_rates_count_above_delivered_raises():
    with pytest.raises(LINEAPIError, match="超えています"):
        compute_rates({"a": 10}, {"a": 11}, {"a": 0})


def test_aggregation_unit_name_fits_line_limits():
    for seg in line_api.SEGMENTS:
        unit = aggregation_unit(seg)
        assert len(unit) <= 30 and unit.replace("_", "").isalnum()


# --- API 経路 -----------------------------------------------------------------

def test_api_path_success(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="line_api")
    calls = install_urlopen(monkeypatch, ok_responses())

    m, source = fetch_line_metrics_with_source(
        CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN, data_dir=tmp_path)

    assert source == SOURCE_API
    assert isinstance(m, LINEMetrics)
    assert m.week == WEEK
    assert m.registered_count == 152
    assert m.open_rate_by_segment == {"high_engagement": pytest.approx(31 / 40), "active_reader": pytest.approx(20 / 50)}
    # LINE が null を返したクリック数は 0 にしない / 配信0人の line_only は率を作らない
    assert m.click_rate_by_segment == {"high_engagement": pytest.approx(12 / 40)}
    assert set(m.to_dict()) == {"week", "registered_count", "open_rate_by_segment", "click_rate_by_segment"}

    kinds = [c["kind"] for c in calls]
    assert kinds == ["verify", "followers", "kekka_active_reader", "kekka_high_engagement"]
    verify = calls[0]
    assert verify["method"] == "POST" and TOKEN not in verify["url"]
    assert urllib.parse.parse_qs(verify["data"].decode()) == {"access_token": [TOKEN]}
    assert calls[1]["url"] == "https://api.line.me/v2/bot/insight/followers?date=20261004"
    unit_q = urllib.parse.parse_qs(urllib.parse.urlparse(calls[2]["url"]).query)
    assert unit_q == {"customAggregationUnit": ["kekka_active_reader"], "from": ["20260928"], "to": ["20261004"]}
    for c in calls[1:]:
        assert c["method"] == "GET" and c["headers"]["Authorization"] == f"Bearer {TOKEN}"

    # 要求/応答のログは出る。トークンは出ない
    assert "insight/followers" in caplog.text and "status=200" in caplog.text and f"source={SOURCE_API}" in caplog.text
    assert TOKEN not in caplog.text


def test_api_token_read_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("KEKKA_LINE_CHANNEL_ACCESS_TOKEN", TOKEN)
    calls = install_urlopen(monkeypatch, ok_responses())
    m = fetch_line_metrics(CHANNEL, WEEK, delivered_by_segment=DELIVERED, data_dir=tmp_path)
    assert m.registered_count == 152
    assert calls[1]["headers"]["Authorization"] == f"Bearer {TOKEN}"


def test_token_env_is_kekka_not_mikata(monkeypatch, tmp_path):
    """ミカタの LINE_CHANNEL_ACCESS_TOKEN だけが設定されていても、それを使わず CSV へ回る。"""
    assert line_api.TOKEN_ENV == "KEKKA_LINE_CHANNEL_ACCESS_TOKEN"
    assert line_api.KEKKA_CHANNEL_ID == "2011004310"
    monkeypatch.delenv("KEKKA_LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "MIKATA-TOKEN")
    write_csv(tmp_path)

    def no_network(*a, **k):
        raise AssertionError("ミカタのトークンで API を叩いた")

    monkeypatch.setattr(line_api.urllib.request, "urlopen", no_network)
    _, source = fetch_line_metrics_with_source(CHANNEL, WEEK, delivered_by_segment=DELIVERED, data_dir=tmp_path)
    assert source == SOURCE_CSV


def test_api_connection_error_falls_back_to_csv(monkeypatch, tmp_path):
    write_csv(tmp_path)
    install_urlopen(monkeypatch, {"verify": [urllib.error.URLError(ConnectionRefusedError("refused"))]})
    _, source = fetch_line_metrics_with_source(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN,
                                               data_dir=tmp_path, sleep=lambda s: None)
    assert source == SOURCE_CSV


def test_api_code_bug_is_not_swallowed(monkeypatch, tmp_path):
    """TypeError 等のコードの誤りは「接続できない」扱いで CSV に逃がさず、そのまま落とす。"""
    write_csv(tmp_path)
    install_urlopen(monkeypatch, {"verify": [TypeError("bug")]})
    with pytest.raises(TypeError):
        fetch_line_metrics(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN,
                           data_dir=tmp_path, sleep=lambda s: None)


def test_api_retries_then_succeeds(monkeypatch, tmp_path):
    sleeps = []
    responses = ok_responses()
    responses["followers"] = [http_error(503), socket.timeout("timed out"), FOLLOWERS]
    install_urlopen(monkeypatch, responses)
    m, source = fetch_line_metrics_with_source(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN,
                                               data_dir=tmp_path, sleep=sleeps.append)
    assert source == SOURCE_API and m.registered_count == 152
    assert sleeps == [5, 10]


def test_api_401_raises_without_fallback(monkeypatch, tmp_path):
    write_csv(tmp_path)  # CSV があっても、トークン誤りは隠さない
    sleeps = []
    calls = install_urlopen(monkeypatch, {"verify": [http_error(401, "invalid token")]})
    with pytest.raises(LINEAPIError, match="HTTP 401") as ei:
        fetch_line_metrics(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN,
                           data_dir=tmp_path, sleep=sleeps.append)
    assert not isinstance(ei.value, LINEAPIUnavailable)
    assert len(calls) == 1 and sleeps == []
    assert TOKEN not in str(ei.value)


def test_api_channel_mismatch_raises(monkeypatch, tmp_path):
    write_csv(tmp_path)
    responses = ok_responses()
    responses["verify"] = [{"client_id": "1999999999", "expires_in": 1, "scope": "P"}]
    install_urlopen(monkeypatch, responses)
    with pytest.raises(LINEAPIError, match="トークンではありません"):
        fetch_line_metrics(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN, data_dir=tmp_path)


def test_api_untagged_unit_raises_instead_of_zero_percent(monkeypatch, tmp_path):
    responses = ok_responses()
    responses["kekka_high_engagement"] = [{"overview": {"uniqueImpression": 0, "uniqueClick": 0}, "messages": []}]
    install_urlopen(monkeypatch, responses)
    with pytest.raises(LINEAPIError, match="付け忘れ"):
        fetch_line_metrics(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN, data_dir=tmp_path)


def test_api_non_integer_followers_raises(monkeypatch, tmp_path):
    responses = ok_responses()
    responses["followers"] = [{"status": "ready", "followers": "152"}]
    install_urlopen(monkeypatch, responses)
    with pytest.raises(LINEAPIError, match="followers"):
        fetch_line_metrics(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN, data_dir=tmp_path)


def test_api_unknown_segment_in_delivered_raises(tmp_path):
    with pytest.raises(LINEAPIError, match="未知のセグメント"):
        fetch_line_metrics(CHANNEL, WEEK, delivered_by_segment={"vip": 3}, token=TOKEN, data_dir=tmp_path)


# --- CSV フォールバック -------------------------------------------------------

def test_csv_fallback_when_token_missing(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="line_api")
    monkeypatch.delenv("KEKKA_LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    write_csv(tmp_path)

    def no_network(*a, **k):
        raise AssertionError("トークン未設定なのに API を叩いた")

    monkeypatch.setattr(line_api.urllib.request, "urlopen", no_network)

    m, source = fetch_line_metrics_with_source(CHANNEL, WEEK, delivered_by_segment=DELIVERED, data_dir=tmp_path)

    assert source == SOURCE_CSV
    assert m.week == WEEK and m.registered_count == 150
    assert m.open_rate_by_segment == {
        "high_engagement": pytest.approx(0.75), "active_reader": pytest.approx(0.5), "discovery_seeker": 0.0}
    assert m.click_rate_by_segment == {
        "high_engagement": pytest.approx(0.25), "active_reader": pytest.approx(0.1), "discovery_seeker": 0.0}
    assert "line_only" not in m.open_rate_by_segment  # 空欄は 0 にしない
    assert "フォールバック" in caplog.text and "KEKKA_LINE_CHANNEL_ACCESS_TOKEN が未設定" in caplog.text


def test_csv_fallback_when_delivered_counts_not_given(monkeypatch, tmp_path):
    write_csv(tmp_path)
    calls = install_urlopen(monkeypatch, {})
    m, source = fetch_line_metrics_with_source(CHANNEL, WEEK, token=TOKEN, data_dir=tmp_path)
    assert source == SOURCE_CSV and m.registered_count == 150
    assert calls == []


def test_csv_fallback_after_api_outage(monkeypatch, tmp_path):
    write_csv(tmp_path)
    sleeps = []
    responses = ok_responses()
    responses["followers"] = [http_error(503)] * 4
    install_urlopen(monkeypatch, responses)
    m, source = fetch_line_metrics_with_source(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN,
                                               data_dir=tmp_path, sleep=sleeps.append)
    assert source == SOURCE_CSV and m.registered_count == 150
    assert sleeps == [5, 10, 15]


def test_csv_fallback_when_followers_not_ready(monkeypatch, tmp_path):
    write_csv(tmp_path)
    responses = ok_responses()
    responses["followers"] = [{"status": "unready"}]
    install_urlopen(monkeypatch, responses)
    _, source = fetch_line_metrics_with_source(CHANNEL, WEEK, delivered_by_segment=DELIVERED, token=TOKEN,
                                               data_dir=tmp_path)
    assert source == SOURCE_CSV


def test_both_unavailable_raises_with_both_reasons(monkeypatch, tmp_path):
    monkeypatch.delenv("KEKKA_LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    with pytest.raises(LINEAPIError) as ei:
        fetch_line_metrics(CHANNEL, WEEK, data_dir=tmp_path)
    msg = str(ei.value)
    assert "API:" in msg and "CSV:" in msg and f"line_segment_stats_{WEEK}.csv" in msg


def test_csv_accepts_excel_bom(tmp_path):
    p = write_csv(tmp_path)
    p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes())
    assert load_line_metrics_csv(WEEK, data_dir=tmp_path).registered_count == 150


@pytest.mark.parametrize("body, match", [
    ("week,registered_count,segment,delivered\n", "列がありません"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n", "データ行がありません"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n2026-W39,150,line_only,10,1,1\n", "週"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n2026-W40,150,vip,10,1,1\n", "未知"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n"
     "2026-W40,150,line_only,10,1,1\n2026-W40,150,line_only,10,1,1\n", "重複"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n"
     "2026-W40,150,line_only,10,1,1\n2026-W40,151,active_reader,10,1,1\n", "他の行"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n2026-W40,150,line_only,,1,1\n", "delivered"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n2026-W40,150,line_only,10,-1,1\n", "unique_opens"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n2026-W40,150,line_only,10,²,1\n", "unique_opens"),
    ("week,registered_count,segment,delivered,unique_opens,unique_clicks\n2026-W40,150,line_only,10,12,1\n", "超えています"),
])
def test_csv_invalid_content_raises(tmp_path, body, match):
    write_csv(tmp_path, text=body)
    with pytest.raises(LINEAPIError, match=match) as ei:
        load_line_metrics_csv(WEEK, data_dir=tmp_path)
    assert not isinstance(ei.value, LINEAPIUnavailable)  # 不正な CSV は「無い」とは扱わない


def test_invalid_csv_is_not_masked_by_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("KEKKA_LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    write_csv(tmp_path, text="week,registered_count,segment,delivered,unique_opens,unique_clicks\n"
                             "2026-W40,150,line_only,10,12,1\n")
    with pytest.raises(LINEAPIError, match="超えています"):
        fetch_line_metrics(CHANNEL, WEEK, data_dir=tmp_path)


# --- 入力チェック -------------------------------------------------------------

@pytest.mark.parametrize("cid", ["", "@mikata", "abc"])
def test_bad_channel_id(cid, tmp_path):
    with pytest.raises(LINEAPIError, match="channel_id"):
        fetch_line_metrics(cid, WEEK, data_dir=tmp_path)


def test_bad_week_format(tmp_path):
    with pytest.raises(LINEAPIError, match="ISO週"):
        fetch_line_metrics(CHANNEL, "2026-09-28", data_dir=tmp_path)
