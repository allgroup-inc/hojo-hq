# -*- coding: utf-8 -*-
"""
scripts/collect_weekly_metrics.py のテスト(結果マガ売上自動化 Task 4)。
実行: python3 -m pytest tests/test_collect_weekly_metrics.py
"""
import datetime as dt
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import collect_weekly_metrics  # noqa: E402
from collect_weekly_metrics import (  # noqa: E402
    CollectError,
    collect_and_save_weekly_metrics,
    default_week,
    normalize_week,
)
from note_api import NoteMetrics, NoteAPIError  # noqa: E402
from ga4_api import GA4Metrics, GA4APIError  # noqa: E402
from line_api import LINEMetrics, LINEAPIError  # noqa: E402

UTC = dt.timezone.utc
BUYER_IDS = ["buyer_secret_u1", "buyer_secret_u2"]


@pytest.fixture
def temp_metrics_file(tmp_path):
    """テスト用の週次メトリクスファイル(W39 が1件)"""
    path = tmp_path / "kekka_weekly_metrics.json"
    path.write_text(json.dumps({
        "_readme": "test data",
        "_schema": {"week": "ISO週"},
        "weeks": [{
            "week": "2026-W39",
            "collected_at": "2026-09-29T17:30:00+09:00",
            "note": {"total_sales_jpy": 1000},
            "ga4": {"sessions": 100},
            "line": {"registered_count": 150},
        }],
    }), encoding="utf-8")
    return path


def _note(week="2026-W40", **over):
    kw = dict(
        week=week,
        views_by_article={"n_a": 1200, "n_b": 800},
        total_likes=50,
        total_sales_jpy=2000,
        buyer_ids=list(BUYER_IDS),
        buyer_profiles=[
            {"buyer_id": "buyer_secret_u1", "name": "Alice", "segment": "executive"},
            {"buyer_id": "buyer_secret_u2", "name": "Bob", "segment": "individual"},
        ],
    )
    kw.update(over)
    return NoteMetrics(**kw)


@pytest.fixture
def mock_metrics():
    """3つの API メトリクス"""
    ga4 = GA4Metrics(
        week="2026-W40",
        sessions=250,
        pageviews=1500,
        ctr_by_article={"n_a": 0.15, "n_b": 0.08},
        user_segment_counts={"new": 60, "returning": 40},
    )
    line = LINEMetrics(
        week="2026-W40",
        registered_count=200,
        open_rate_by_segment={"high_engagement": 0.45, "active_reader": 0.32},
        click_rate_by_segment={"high_engagement": 0.12, "active_reader": 0.08},
    )
    return _note(), ga4, line


@contextmanager
def _apis(path, note=None, ga4=None, line=None, line_source="line_messaging_api",
          note_exc=None, ga4_exc=None, line_exc=None):
    """ファイルと 3 API を差し替える。各モックを返す。"""
    m_note = MagicMock(return_value=note, side_effect=note_exc)
    m_ga4 = MagicMock(return_value=ga4, side_effect=ga4_exc)
    m_line = MagicMock(return_value=(line, line_source), side_effect=line_exc)
    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", path), \
            patch("collect_weekly_metrics.fetch_note_metrics", m_note), \
            patch("collect_weekly_metrics.fetch_ga4_metrics", m_ga4), \
            patch("collect_weekly_metrics.fetch_line_metrics_with_source", m_line):
        yield m_note, m_ga4, m_line


def _run(week="2026-W40", **kw):
    kw.setdefault("api_token", "test_token")
    kw.setdefault("property_id", "123456")
    kw.setdefault("channel_id", "2011004310")
    return collect_and_save_weekly_metrics(week, **kw)


def _saved(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- 追記・置き換え・順序 ---------------------------------------------------------

def test_collect_and_save_weekly_metrics_appends_to_json(temp_metrics_file, mock_metrics):
    """既存 JSON に新しい週のメトリクスを追記し、昇順を保つ"""
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line):
        result = _run()

    assert result["week"] == "2026-W40"
    assert "collected_at" in result
    assert result["note"]["total_sales_jpy"] == 2000
    assert result["ga4"]["sessions"] == 250
    assert result["line"]["registered_count"] == 200

    saved = _saved(temp_metrics_file)
    assert [e["week"] for e in saved["weeks"]] == ["2026-W39", "2026-W40"]
    assert saved["_readme"] == "test data"  # 既存のメタ情報は保持


def test_collect_and_save_weekly_metrics_replaces_existing_week(temp_metrics_file, mock_metrics):
    """同じ week が再度来たら置き換える(手動再実行)"""
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line):
        _run()
    note2 = _note(views_by_article={"n_x": 999}, total_likes=99, total_sales_jpy=9999,
                  buyer_ids=["u99"], buyer_profiles=[])
    with _apis(temp_metrics_file, note2, ga4, line):
        _run()

    saved = _saved(temp_metrics_file)
    assert [e["week"] for e in saved["weeks"]] == ["2026-W39", "2026-W40"]
    assert saved["weeks"][1]["note"]["total_sales_jpy"] == 9999


def test_collect_and_save_weekly_metrics_preserves_chronological_order(temp_metrics_file, mock_metrics):
    """W41 → W38 の順に足しても(fixture の W39 と合わせて)昇順になる"""
    _, ga4, line = mock_metrics
    for week in ["2026-W41", "2026-W38"]:
        note_w = _note(week=week, views_by_article={}, total_likes=0, total_sales_jpy=0,
                       buyer_ids=[], buyer_profiles=[])
        with _apis(temp_metrics_file, note_w, ga4, line):
            _run(week)

    assert [e["week"] for e in _saved(temp_metrics_file)["weeks"]] == ["2026-W38", "2026-W39", "2026-W41"]


def test_missing_file_is_initialized(tmp_path, mock_metrics):
    """ファイルが無ければ weeks=[] から始める"""
    path = tmp_path / "sub" / "kekka_weekly_metrics.json"
    note, ga4, line = mock_metrics
    with _apis(path, note, ga4, line):
        _run()
    assert [e["week"] for e in _saved(path)["weeks"]] == ["2026-W40"]


# --- API エラー --------------------------------------------------------------------

def test_collect_and_save_weekly_metrics_error_on_note_api_failure(temp_metrics_file):
    before = temp_metrics_file.read_text(encoding="utf-8")
    with _apis(temp_metrics_file, note_exc=NoteAPIError("API error")):
        with pytest.raises(CollectError, match="note API 失敗"):
            _run()
    assert temp_metrics_file.read_text(encoding="utf-8") == before  # 失敗した週は書かない


def test_collect_and_save_weekly_metrics_error_on_ga4_api_failure(temp_metrics_file, mock_metrics):
    note, _, _ = mock_metrics
    with _apis(temp_metrics_file, note, ga4_exc=GA4APIError("GA4 error")):
        with pytest.raises(CollectError, match="GA4 API 失敗"):
            _run()


def test_collect_and_save_weekly_metrics_error_on_line_api_failure(temp_metrics_file, mock_metrics):
    note, ga4, _ = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line_exc=LINEAPIError("LINE error")):
        with pytest.raises(CollectError, match="LINE API 失敗"):
            _run()


def test_missing_ga4_property_id_fails_before_api(temp_metrics_file, mock_metrics, monkeypatch):
    """GA4_PROPERTY_ID が無ければ、どの API も叩く前に止まる"""
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line) as (m_note, m_ga4, m_line):
        with pytest.raises(CollectError, match="GA4 プロパティID"):
            _run(property_id=None)
    assert not m_note.called and not m_ga4.called and not m_line.called


# --- C1: 既定の週は前週 --------------------------------------------------------------

def test_default_week_is_previous_week():
    """定期実行(月曜 00:00 UTC = 月曜 09:00 JST)では、直前に終わった前週を選ぶ"""
    # 2026-10-05(月)00:00 UTC。今週は 2026-W41(10/05〜10/11)、前週は 2026-W40(9/28〜10/04)
    monday_run = dt.datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
    assert default_week(monday_run) == "2026-W40"
    # cron が遅れて月曜の昼に動いても前週
    assert default_week(dt.datetime(2026, 10, 5, 3, 0, tzinfo=UTC)) == "2026-W40"
    # 日曜 23:59 JST(= 日曜 14:59 UTC)に手動実行すると、その週の前週
    assert default_week(dt.datetime(2026, 10, 4, 14, 59, tzinfo=UTC)) == "2026-W39"
    # 年またぎ: 2027-01-04(月)の前週は 2026-W53(2026 は 53 週ある年)
    assert default_week(dt.datetime(2027, 1, 4, 0, 0, tzinfo=UTC)) == "2026-W53"


def test_collect_without_week_uses_previous_week(temp_metrics_file, mock_metrics):
    """week を省略すると前週を集め、3 API にも前週が渡る"""
    note, ga4, line = mock_metrics
    monday_run = dt.datetime(2026, 10, 5, 9, 0, tzinfo=collect_weekly_metrics.JST)
    with patch.object(collect_weekly_metrics, "_now_jst", return_value=monday_run), \
            _apis(temp_metrics_file, note, ga4, line) as (m_note, m_ga4, m_line):
        result = _run(week=None)
    assert result["week"] == "2026-W40"
    assert m_note.call_args.args[1] == "2026-W40"
    assert m_ga4.call_args.args[1] == "2026-W40"
    assert m_line.call_args.args[1] == "2026-W40"


# --- C3: 購入者IDを公開しない -----------------------------------------------------------

def test_no_buyer_ids_in_public_file(temp_metrics_file, mock_metrics):
    """公開ファイルに buyer_ids / buyer_profiles / 購入者ID・属性が残らず、buyer_count だけが残る"""
    note, ga4, line = mock_metrics
    note.buyer_ids.append("buyer_secret_u1")  # 重複はユニーク人数に数えない
    with _apis(temp_metrics_file, note, ga4, line):
        result = _run()

    raw = temp_metrics_file.read_text(encoding="utf-8")
    assert "buyer_ids" not in raw
    assert "buyer_profiles" not in raw
    for secret in ["buyer_secret_u1", "buyer_secret_u2", "Alice", "Bob", "executive"]:
        assert secret not in raw
    entry = json.loads(raw)["weeks"][-1]["note"]
    assert entry["buyer_count"] == 2
    assert set(entry) == {"week", "views_by_article", "total_likes", "total_sales_jpy", "buyer_count"}
    assert "buyer_ids" not in result["note"] and "buyer_profiles" not in result["note"]


def test_stdout_has_no_buyer_ids(temp_metrics_file, mock_metrics, capsys):
    """main() の標準出力(公開の Actions ログ)は集計値だけで、購入者ID・記事別の内訳を出さない"""
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line):
        rc = collect_weekly_metrics.main(["-w", "2026-W40", "--api-token", "t", "--property-id", "123456"])
    assert rc == 0
    out = capsys.readouterr().out
    for secret in ["buyer_secret_u1", "buyer_secret_u2", "Alice", "buyer_ids", "buyer_profiles"]:
        assert secret not in out
    summary = json.loads(out)
    assert summary["note"]["buyer_count"] == 2
    assert summary["note"]["total_sales_jpy"] == 2000
    assert summary["note"]["total_views"] == 2000
    assert summary["line"]["source"] == "line_messaging_api"


def test_main_returns_1_on_failure(temp_metrics_file):
    with _apis(temp_metrics_file, note_exc=NoteAPIError("x")):
        assert collect_weekly_metrics.main(["-w", "2026-W40", "--property-id", "1"]) == 1


# --- I3: ファイル検証が先・書き込みはアトミック ---------------------------------------------

@pytest.mark.parametrize("broken", [
    "{not json",
    "[]",
    '{"weeks": {}}',
    '{"weeks": ["2026-W39"]}',
    '{"weeks": [{"note": {}}]}',
])
def test_broken_file_fails_before_api(tmp_path, mock_metrics, broken):
    """壊れた/形式違いのファイルは CollectError。API は叩かず、ファイルも変えない"""
    path = tmp_path / "kekka_weekly_metrics.json"
    path.write_text(broken, encoding="utf-8")
    note, ga4, line = mock_metrics
    with _apis(path, note, ga4, line) as (m_note, m_ga4, m_line):
        with pytest.raises(CollectError, match="メトリクスファイル"):
            _run()
    assert not m_note.called and not m_ga4.called and not m_line.called
    assert path.read_text(encoding="utf-8") == broken


def test_write_is_atomic_and_leaves_no_temp_file(temp_metrics_file, mock_metrics):
    """書き込みに失敗しても元ファイルは無傷で、一時ファイルも残らない"""
    before = temp_metrics_file.read_text(encoding="utf-8")
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line), \
            patch("collect_weekly_metrics.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(CollectError, match="書き込み失敗"):
            _run()
    assert temp_metrics_file.read_text(encoding="utf-8") == before
    assert sorted(p.name for p in temp_metrics_file.parent.iterdir()) == [temp_metrics_file.name]


# --- I4: 週表記の検証・正規化 ----------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("2026-W40", "2026-W40"),
    ("2026-W1", "2026-W01"),
    (" 2026-w05 ", "2026-W05"),
    ("2026-W53", "2026-W53"),
])
def test_normalize_week_ok(raw, expected):
    assert normalize_week(raw) == expected


@pytest.mark.parametrize("raw", ["2026-40", "26-W40", "2026-W400", "2026-W00", "2025-W53", "2026-W40; rm -rf /", ""])
def test_normalize_week_rejects(raw):
    with pytest.raises(CollectError):
        normalize_week(raw)


def test_single_digit_week_is_stored_zero_padded(temp_metrics_file, mock_metrics):
    """'2026-W1' と '2026-W01' は同じエントリになる"""
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line) as (m_note, _, _):
        _run("2026-W1")
        _run("2026-W01")
    assert m_note.call_args.args[1] == "2026-W01"
    assert [e["week"] for e in _saved(temp_metrics_file)["weeks"]] == ["2026-W01", "2026-W39"]


# --- I5: LINE の取得元・チャネルID ------------------------------------------------------

@pytest.mark.parametrize("source", ["line_messaging_api", "csv"])
def test_line_source_is_recorded(temp_metrics_file, mock_metrics, source):
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line, line_source=source):
        _run()
    assert _saved(temp_metrics_file)["weeks"][-1]["line_source"] == source


def test_channel_id_falls_back_to_kekka_constant(temp_metrics_file, mock_metrics, monkeypatch):
    """引数も環境変数も無ければ、結果マガの定数チャネルID(2011004310)を使う"""
    monkeypatch.delenv("KEKKA_CHANNEL_ID", raising=False)
    note, ga4, line = mock_metrics
    with _apis(temp_metrics_file, note, ga4, line) as (_, _, m_line):
        _run(channel_id=None)
    assert m_line.call_args.args[0] == "2011004310"
