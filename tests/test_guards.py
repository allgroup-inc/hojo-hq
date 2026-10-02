# -*- coding: utf-8 -*-
"""tests/test_guards.py のテスト(売上自動化 Task 5-6)。実行: python3 -m pytest tests/test_guards.py"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from build_facts import FactsError, FactsDict  # noqa: E402
from guards import BannedPhrasesChecker, Guard, NumberVerifier  # noqa: E402

# Note: SegmentFitChecker will be added in a later task


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


# ---- BannedPhrasesChecker ----

BANNED_KPI = {"banned_phrases": ["無料で", "申請代行", "ChatGPT", "100%"]}


def _banned(facts, kpi=None):
    BannedPhrasesChecker().verify(facts, {}, kpi if kpi is not None else BANNED_KPI)


def test_banned_checker_is_a_guard():
    assert isinstance(BannedPhrasesChecker(), Guard)


def test_banned_clean_text_passes():
    _banned({
        "article_topics": [{"article_id": "05", "title": "助成金の上手な活用法", "description": "実数だけを書く"}],
        "sales_by_segment": {"enterprise": 3000},
    })


def test_banned_empty_facts_passes():
    _banned({})


def test_banned_phrase_in_title_names_phrase_and_field():
    with pytest.raises(FactsError, match=r"banned phrase '無料で'.*article_topics\[0\]\.title"):
        _banned({"article_topics": [{"article_id": "05", "title": "無料で助成金をゲット"}]})


def test_banned_phrase_in_description_and_later_article():
    with pytest.raises(FactsError, match=r"'申請代行'.*article_topics\[1\]\.description"):
        _banned({"article_topics": [
            {"article_id": "05", "title": "ok", "description": "ok"},
            {"article_id": "12", "title": "ok", "description": "申請代行します"},
        ]})


def test_banned_phrase_in_nested_field():
    with pytest.raises(FactsError, match=r"article_topics\[0\]\.tags\[1\]"):
        _banned({"article_topics": [{"article_id": "05", "tags": ["助成金", "ChatGPTで作成"]}]})


def test_banned_phrase_in_segment_name_and_score_key():
    with pytest.raises(FactsError, match="sales_by_segment key"):
        _banned({"sales_by_segment": {"申請代行層": 0}})
    with pytest.raises(FactsError, match="segment_scores key"):
        _banned({"segment_scores": {"無料で使う層": 50}})


def test_banned_article_id_is_not_scanned():
    _banned({"article_topics": [{"article_id": "ChatGPT", "title": "ok"}]})


def test_banned_case_insensitive_and_fullwidth():
    with pytest.raises(FactsError, match="ChatGPT"):
        _banned({"article_topics": [{"article_id": "05", "title": "chatgptの使い方"}]})
    with pytest.raises(FactsError, match="ChatGPT"):
        _banned({"article_topics": [{"article_id": "05", "title": "ＣｈａｔＧＰＴの使い方"}]})


def test_banned_phrase_is_literal_not_regex():
    kpi = {"banned_phrases": ["a.c", "100%"]}
    _banned({"article_topics": [{"article_id": "05", "title": "abc"}]}, kpi)  # '.' は任意1文字ではない
    with pytest.raises(FactsError, match="100%"):
        _banned({"article_topics": [{"article_id": "05", "title": "成功率100%"}]}, kpi)


def test_banned_missing_or_empty_list_fails_closed():
    for kpi in ({}, {"banned_phrases": []}, {"banned_phrases": "無料で"}, {"banned_phrases": None}):
        with pytest.raises(FactsError, match="banned_phrases"):
            _banned({"article_topics": []}, kpi)


def test_banned_invalid_entry_rejected():
    for bad in ("", "  ", 5):
        with pytest.raises(FactsError, match="invalid entry"):
            _banned({}, {"banned_phrases": ["ok", bad]})


def test_real_kpi_json_banned_phrases_valid_and_flag_known_bad_text():
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "kekka_kpi.json")
    kpi = json.load(open(path, encoding="utf-8"))
    assert all(isinstance(p, str) and p.strip() for p in kpi["banned_phrases"])
    _banned({"article_topics": [{"article_id": "05", "title": "フォロワーが買うのではなかった"}]}, kpi)
    for a in kpi["articles"].values():  # 既存の実タイトルが誤検知されないこと(正例)
        _banned({"article_topics": [{"article_id": "05", "title": a["title"]}]}, kpi)
    with pytest.raises(FactsError):
        _banned({"article_topics": [{"article_id": "05", "title": "必ず稼げる"}]}, kpi)
