# -*- coding: utf-8 -*-
"""
scripts/collect_weekly_metrics.py のテスト(結果マガ売上自動化 Task 4)。
実行: python3 -m pytest tests/test_collect_weekly_metrics.py
"""
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import collect_weekly_metrics  # noqa: E402
from collect_weekly_metrics import collect_and_save_weekly_metrics, CollectError  # noqa: E402
from note_api import NoteMetrics  # noqa: E402
from ga4_api import GA4Metrics  # noqa: E402
from line_api import LINEMetrics  # noqa: E402


@pytest.fixture
def temp_metrics_file():
    """テスト用の週次メトリクスファイルを一時的に作成"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        initial_data = {
            "_readme": "test data",
            "_schema": {"week": "ISO週"},
            "weeks": [
                {
                    "week": "2026-W39",
                    "collected_at": "2026-09-29T17:30:00+09:00",
                    "note": {"total_sales_jpy": 1000},
                    "ga4": {"sessions": 100},
                    "line": {"registered_count": 150},
                }
            ],
        }
        json.dump(initial_data, f)
        temp_path = f.name

    yield Path(temp_path)

    # クリーンアップ
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def mock_metrics():
    """3つの API メトリクスをモック"""
    note = NoteMetrics(
        week="2026-W40",
        views_by_article={"n_a": 1200, "n_b": 800},
        total_likes=50,
        total_sales_jpy=2000,
        buyer_ids=["u1", "u2"],
        buyer_profiles=[
            {"buyer_id": "u1", "name": "Alice", "segment": "executive"},
            {"buyer_id": "u2", "name": "Bob", "segment": "individual"},
        ],
    )

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

    return note, ga4, line


def test_collect_and_save_weekly_metrics_appends_to_json(temp_metrics_file, mock_metrics):
    """
    テスト: 既存 JSON に新しい週のメトリクスを追記する
    - 1週分のデータから開始
    - collect_and_save_weekly_metrics を実行
    - 2週分に増えることを確認
    - 時系列順序が保持されることを確認
    """
    note, ga4, line = mock_metrics

    # パッチ: 一時ファイルを使用
    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", temp_metrics_file):
        with patch("collect_weekly_metrics.fetch_note_metrics", return_value=note):
            with patch("collect_weekly_metrics.fetch_ga4_metrics", return_value=ga4):
                with patch("collect_weekly_metrics.fetch_line_metrics", return_value=line):
                    # 実行
                    result = collect_and_save_weekly_metrics(
                        "2026-W40",
                        api_token="test_token",
                        property_id="123456",
                        channel_id="2011004310",
                    )

    # 検証: 結果が返された
    assert result["week"] == "2026-W40"
    assert "collected_at" in result
    assert result["note"]["total_sales_jpy"] == 2000
    assert result["ga4"]["sessions"] == 250
    assert result["line"]["registered_count"] == 200

    # 検証: PII が削除されている(buyer_profiles の個人情報が削除)
    assert len(result["note"]["buyer_profiles"]) == 2
    for profile in result["note"]["buyer_profiles"]:
        assert "buyer_id" in profile
        assert "name" not in profile  # name が削除されている
        assert "segment" not in profile  # segment が削除されている

    # 検証: ファイルに 2 週分が記録された
    with open(temp_metrics_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert len(saved_data["weeks"]) == 2
    assert saved_data["weeks"][0]["week"] == "2026-W39"
    assert saved_data["weeks"][1]["week"] == "2026-W40"

    # 検証: 時系列順序が保持されている
    weeks = [entry["week"] for entry in saved_data["weeks"]]
    assert weeks == sorted(weeks)


def test_collect_and_save_weekly_metrics_replaces_existing_week(temp_metrics_file, mock_metrics):
    """
    テスト: 既存の week が再度来た場合は置き換える
    - 2026-W40 のデータで上書きを試みる(既に 2026-W39 が在)
    - 元のデータが置き換わることを確認
    """
    note, ga4, line = mock_metrics

    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", temp_metrics_file):
        with patch("collect_weekly_metrics.fetch_note_metrics", return_value=note):
            with patch("collect_weekly_metrics.fetch_ga4_metrics", return_value=ga4):
                with patch("collect_weekly_metrics.fetch_line_metrics", return_value=line):
                    result = collect_and_save_weekly_metrics(
                        "2026-W40",
                        api_token="test_token",
                        property_id="123456",
                        channel_id="2011004310",
                    )

    # 同じ week でもう一度実行(異なるデータ)
    note2 = NoteMetrics(
        week="2026-W40",
        views_by_article={"n_x": 999},
        total_likes=99,
        total_sales_jpy=9999,
        buyer_ids=["u99"],
        buyer_profiles=[],
    )

    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", temp_metrics_file):
        with patch("collect_weekly_metrics.fetch_note_metrics", return_value=note2):
            with patch("collect_weekly_metrics.fetch_ga4_metrics", return_value=ga4):
                with patch("collect_weekly_metrics.fetch_line_metrics", return_value=line):
                    result2 = collect_and_save_weekly_metrics(
                        "2026-W40",
                        api_token="test_token",
                        property_id="123456",
                        channel_id="2011004310",
                    )

    # 検証: ファイルにはまだ 2 週分(2026-W39, 2026-W40)
    with open(temp_metrics_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert len(saved_data["weeks"]) == 2
    # W40 が置き換わっている
    w40_entry = saved_data["weeks"][1]
    assert w40_entry["week"] == "2026-W40"
    assert w40_entry["note"]["total_sales_jpy"] == 9999  # 新しい値


def test_collect_and_save_weekly_metrics_preserves_chronological_order(temp_metrics_file, mock_metrics):
    """
    テスト: 複数の週をランダム順で追加しても、時系列順序が保持される
    """
    note, ga4, line = mock_metrics

    # W39, W40, W38 の順で追加
    weeks_to_add = ["2026-W38", "2026-W41"]

    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", temp_metrics_file):
        for week in weeks_to_add:
            note_w = NoteMetrics(
                week=week,
                views_by_article={},
                total_likes=0,
                total_sales_jpy=0,
                buyer_ids=[],
                buyer_profiles=[],
            )
            with patch("collect_weekly_metrics.fetch_note_metrics", return_value=note_w):
                with patch("collect_weekly_metrics.fetch_ga4_metrics", return_value=ga4):
                    with patch("collect_weekly_metrics.fetch_line_metrics", return_value=line):
                        collect_and_save_weekly_metrics(
                            week,
                            api_token="test_token",
                            property_id="123456",
                            channel_id="2011004310",
                        )

    # 検証: ファイルに 3 週分(W38, W39, W41 — fixture に既に W39 が在)
    with open(temp_metrics_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert len(saved_data["weeks"]) == 3

    # 検証: week が昇順
    weeks = [entry["week"] for entry in saved_data["weeks"]]
    assert weeks == ["2026-W38", "2026-W39", "2026-W41"]


def test_collect_and_save_weekly_metrics_error_on_note_api_failure(temp_metrics_file):
    """
    テスト: note API が失敗したら CollectError を上げる
    """
    from note_api import NoteAPIError

    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", temp_metrics_file):
        with patch(
            "collect_weekly_metrics.fetch_note_metrics",
            side_effect=NoteAPIError("API error"),
        ):
            with pytest.raises(CollectError, match="note API 失敗"):
                collect_and_save_weekly_metrics(
                    "2026-W40",
                    api_token="test_token",
                    property_id="123456",
                    channel_id="2011004310",
                )


def test_collect_and_save_weekly_metrics_error_on_ga4_api_failure(temp_metrics_file, mock_metrics):
    """
    テスト: GA4 API が失敗したら CollectError を上げる
    """
    from ga4_api import GA4APIError
    note, _, _ = mock_metrics

    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", temp_metrics_file):
        with patch("collect_weekly_metrics.fetch_note_metrics", return_value=note):
            with patch(
                "collect_weekly_metrics.fetch_ga4_metrics",
                side_effect=GA4APIError("GA4 error"),
            ):
                with pytest.raises(CollectError, match="GA4 API 失敗"):
                    collect_and_save_weekly_metrics(
                        "2026-W40",
                        api_token="test_token",
                        property_id="123456",
                        channel_id="2011004310",
                    )


def test_collect_and_save_weekly_metrics_error_on_line_api_failure(temp_metrics_file, mock_metrics):
    """
    テスト: LINE API が失敗したら CollectError を上げる
    """
    from line_api import LINEAPIError
    note, ga4, _ = mock_metrics

    with patch.object(collect_weekly_metrics, "WEEKLY_METRICS_FILE", temp_metrics_file):
        with patch("collect_weekly_metrics.fetch_note_metrics", return_value=note):
            with patch("collect_weekly_metrics.fetch_ga4_metrics", return_value=ga4):
                with patch(
                    "collect_weekly_metrics.fetch_line_metrics",
                    side_effect=LINEAPIError("LINE error"),
                ):
                    with pytest.raises(CollectError, match="LINE API 失敗"):
                        collect_and_save_weekly_metrics(
                            "2026-W40",
                            api_token="test_token",
                            property_id="123456",
                            channel_id="2011004310",
                        )


def test_sanitize_buyer_profiles():
    """
    テスト: buyer_profiles のサニタイズが正しく機能する
    (PII を削除して buyer_id のみを保持)
    """
    profiles = [
        {"buyer_id": "u1", "name": "Alice", "email": "alice@example.com", "segment": "executive"},
        {"buyer_id": "u2", "name": "Bob"},
        {"some_key": "value"},  # buyer_id が無い(フィルタ対象外)
    ]

    result = collect_weekly_metrics._sanitize_buyer_profiles(profiles)

    assert len(result) == 2  # buyer_id が無いものは除外
    assert result[0] == {"buyer_id": "u1"}
    assert result[1] == {"buyer_id": "u2"}
