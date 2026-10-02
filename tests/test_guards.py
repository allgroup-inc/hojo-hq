# -*- coding: utf-8 -*-
"""tests/test_guards.py のテスト(売上自動化 Task 5-6)。実行: python3 -m pytest tests/test_guards.py"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from build_facts import FactsError, FactsDict  # noqa: E402
from guards import Guard, NumberVerifier  # noqa: E402

# Note: NumberVerifier, BannedPhrasesChecker, SegmentFitChecker will be added in Tasks 2-4


KPI = {"segment_thresholds": {"enterprise": {"min": 0, "max": 100, "threshold": 60}}}


def _metrics(**note_overrides):
    note = {"views_by_article": {"05": 13, "12": 5}, "total_sales_jpy": 5000, "buyer_count": 2}
    note.update(note_overrides)
    return {"week": "2026-W40", "note": note}


def _verify(facts, metrics=None):
    NumberVerifier().verify(facts, metrics if metrics is not None else _metrics(), KPI)


def test_number_verifier_is_a_guard():
    assert isinstance(NumberVerifier(), Guard)


def test_accepts_all_articles_present():
    _verify({"article_topics": [{"article_id": "05", "sales_jpy": 5000, "views": 13}]})


def test_rejects_nonexistent_article():
    with pytest.raises(FactsError, match="article.*not found"):
        _verify({"article_topics": [{"article_id": "ghost", "sales_jpy": 5000}]})


def test_accepts_matching_segment_sum():
    _verify({
        "sales_by_segment": {"enterprise": 3000, "sme": 2000},
        "article_topics": [{"article_id": "05", "sales_jpy": 2000}],
    })


def test_rejects_segment_sum_mismatch():
    with pytest.raises(FactsError, match="sales_by_segment.*sum.*mismatch"):
        _verify({"sales_by_segment": {"enterprise": 3000, "sme": 3000}})


def test_rejects_negative_segment_value():
    with pytest.raises(FactsError, match="negative"):
        _verify({"sales_by_segment": {"enterprise": 6000, "sme": -1000}})


def test_rejects_non_numeric_and_bool_segment_value():
    with pytest.raises(FactsError, match="not a number"):
        _verify({"sales_by_segment": {"enterprise": "5000"}})
    with pytest.raises(FactsError, match="not a number"):
        _verify({"sales_by_segment": {"enterprise": True}})


def test_rejects_views_mismatch():
    with pytest.raises(FactsError, match="views mismatch"):
        _verify({"article_topics": [{"article_id": "05", "views": 99}]})


def test_rejects_article_sales_over_total():
    with pytest.raises(FactsError, match="exceeds"):
        _verify({"article_topics": [
            {"article_id": "05", "sales_jpy": 4000},
            {"article_id": "12", "sales_jpy": 2000},
        ]})


def test_rejects_negative_article_sales():
    with pytest.raises(FactsError, match="non-negative"):
        _verify({"article_topics": [{"article_id": "05", "sales_jpy": -1}]})


def test_missing_note_raises():
    with pytest.raises(FactsError, match="note is missing"):
        _verify({"article_topics": []}, {"week": "2026-W40"})


def test_missing_views_by_article_raises_when_topics_given():
    with pytest.raises(FactsError, match="views_by_article is missing"):
        _verify({"article_topics": [{"article_id": "05"}]}, {"note": {"total_sales_jpy": 0}})


def test_missing_total_sales_raises_when_segments_given():
    with pytest.raises(FactsError, match="total_sales_jpy is missing"):
        _verify({"sales_by_segment": {"enterprise": 0}}, _metrics(total_sales_jpy=None))


def test_segments_must_be_dict():
    with pytest.raises(FactsError, match="must be a dict"):
        _verify({"sales_by_segment": [1, 2]})


def test_empty_facts_passes():
    _verify({}, {"note": {}})


def test_zero_sales_week_passes():
    _verify(
        {"sales_by_segment": {"enterprise": 0}, "article_topics": [{"article_id": "05", "sales_jpy": 0}]},
        _metrics(total_sales_jpy=0),
    )


def test_real_kpi_json_has_segment_thresholds():
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "kekka_kpi.json")
    kpi = json.load(open(path, encoding="utf-8"))
    for name, rule in kpi["segment_thresholds"].items():
        assert rule["min"] <= rule["threshold"] <= rule["max"], name
    assert {"targets", "articles", "weeks"} <= set(kpi)  # 既存の台帳キーを壊していない
