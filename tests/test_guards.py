# -*- coding: utf-8 -*-
"""tests/test_guards.py のテスト(売上自動化 Task 5-6)。実行: python3 -m pytest tests/test_guards.py"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from build_facts import FactsError, FactsDict  # noqa: E402
from guards import BannedPhrasesChecker, Guard, NumberVerifier, SegmentFitChecker  # noqa: E402


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


# ---- SegmentFitChecker ----

SEG_KPI = {
    "segment_thresholds": {
        "enterprise": {"min": 0, "max": 100, "threshold": 60},
        "sme": {"min": 0, "max": 100, "threshold": 60},
        "startup": {"min": 0, "max": 100, "threshold": 60},
    }
}


def _seg(scores, kpi=None):
    SegmentFitChecker().verify({"segment_scores": scores}, {}, SEG_KPI if kpi is None else kpi)


def test_segment_checker_is_a_guard():
    assert isinstance(SegmentFitChecker(), Guard)


def test_segment_valid_scores_pass():
    _seg({"enterprise": 75, "sme": 60, "startup": 100})


def test_segment_boundaries_inclusive():
    _seg({"enterprise": 100, "sme": 0})  # min / max ちょうどは通る


def test_segment_below_threshold_is_not_enforced():
    """threshold は下流向けメタデータ。低スコアは正当なデータとして通す(統括裁定)。"""
    _seg({"startup": 45, "sme": 0})


def test_segment_rejects_negative_score():
    with pytest.raises(FactsError, match="segment.*score.*out of range"):
        _seg({"enterprise": -5})


def test_segment_rejects_over_100():
    with pytest.raises(FactsError, match="segment.*score.*out of range"):
        _seg({"sme": 105})





def test_segment_rejects_undefined_segment():
    with pytest.raises(FactsError, match="segment.*not defined in kpi"):
        _seg({"ghost_segment": 75})


@pytest.mark.parametrize("bad", [75.5, "75", None, True])
def test_segment_rejects_non_integer_score(bad):
    with pytest.raises(FactsError, match="must be an integer"):
        _seg({"enterprise": bad})


@pytest.mark.parametrize("kpi", [{}, {"segment_thresholds": {}}, {"segment_thresholds": None}, {"segment_thresholds": []}])
def test_segment_missing_or_empty_thresholds_fails_closed(kpi):
    with pytest.raises(FactsError, match="segment_thresholds.*missing or empty"):
        _seg({"enterprise": 75}, kpi)


@pytest.mark.parametrize(
    "rule",
    [
        {"min": 0, "max": 100, "threshold": "60"},
        {"min": 0, "max": 100, "threshold": None},
        {"min": 0, "max": 100, "threshold": float("nan")},
        {"min": 0, "max": 100, "threshold": True},
        {"min": 0, "max": 100, "threshold": 120},
        {"min": 0, "max": 100, "threshold": -1},
        {"min": 70, "max": 100, "threshold": 60},
        {"min": 0, "max": 150, "threshold": 60},
        "60",
    ],
)
def test_segment_invalid_threshold_definition_rejected(rule):
    with pytest.raises(FactsError, match="kpi.segment_thresholds"):
        _seg({"enterprise": 75}, {"segment_thresholds": {"enterprise": rule}})


def test_segment_rule_defaults_to_0_100():
    kpi = {"segment_thresholds": {"enterprise": {}}}
    _seg({"enterprise": 0}, kpi)
    _seg({"enterprise": 100}, kpi)
    with pytest.raises(FactsError, match="out of range"):
        _seg({"enterprise": 101}, kpi)





def test_segment_no_scores_passes():
    SegmentFitChecker().verify({}, {}, {})
    _seg({}, {})
    SegmentFitChecker().verify({"segment_scores": None}, {}, SEG_KPI)


def test_segment_scores_must_be_a_dict():
    with pytest.raises(FactsError, match="segment_scores must be a dict"):
        SegmentFitChecker().verify({"segment_scores": [75]}, {}, SEG_KPI)


def test_segment_first_violation_names_segment():
    with pytest.raises(FactsError, match="'sme'"):
        _seg({"enterprise": 80, "sme": 101})


def test_real_kpi_json_accepts_scores_and_rejects_out_of_range():
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "kekka_kpi.json")
    kpi = json.load(open(path, encoding="utf-8"))
    names = kpi["segment_thresholds"]
    assert {"enterprise", "sme", "startup", "other"} <= set(names)
    _seg({n: names[n]["threshold"] for n in names}, kpi)
    _seg({"other": 0}, kpi)
    with pytest.raises(FactsError, match="out of range"):
        _seg({"other": names["other"]["max"] + 1}, kpi)


# ---- build_facts()(Guard チェーンの統合) ----

import copy  # noqa: E402
import json  # noqa: E402

from build_facts import build_facts  # noqa: E402

_REAL_KPI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "kekka_kpi.json")


def _real_kpi():
    return json.load(open(_REAL_KPI_PATH, encoding="utf-8"))


def _week(**note_overrides):
    """weeks[] の1件(単一週)。"""
    note = {
        "week": "2026-W40",
        "views_by_article": {"05": 13, "12": 5},
        "total_likes": 3,
        "total_sales_jpy": 5000,
        "buyer_count": 2,
    }
    note.update(note_overrides)
    return {"week": "2026-W40", "note": note}


def test_build_facts_full_flow_returns_json_dict():
    facts = build_facts(_week(), _real_kpi())
    assert facts["week"] == "2026-W40"
    assert [t["article_id"] for t in facts["article_topics"]] == ["05", "12"]
    assert facts["article_topics"][0]["views"] == 13
    assert set(facts) == {"week", "article_topics", "sales_by_segment", "segment_scores"}
    json.dumps(facts, ensure_ascii=False)  # JSON シリアライズ可能


def test_build_facts_segment_scores_are_placeholder_60_for_four_segments():
    facts = build_facts(_week(), _real_kpi())
    assert facts["segment_scores"] == {"enterprise": 60, "sme": 60, "startup": 60, "other": 60}


def test_build_facts_sales_by_segment_empty_when_absent():
    assert build_facts(_week(), _real_kpi())["sales_by_segment"] == {}


def test_build_facts_includes_sales_by_article_when_present():
    facts = build_facts(_week(sales_by_article={"05": 3000}), _real_kpi())
    by_id = {t["article_id"]: t for t in facts["article_topics"]}
    assert by_id["05"]["sales_jpy"] == 3000
    assert "sales_jpy" not in by_id["12"]  # 無い記事は創作しない


def test_build_facts_sales_by_segment_passes_through_and_keeps_order():
    wm = _week()
    wm["sales_by_segment"] = {"sme": 2000, "enterprise": 3000}
    facts = build_facts(wm, _real_kpi())
    assert list(facts["sales_by_segment"]) == ["sme", "enterprise"]
    assert facts["sales_by_segment"] is not wm["sales_by_segment"]  # 入力と共有しない


def test_build_facts_does_not_mutate_inputs():
    wm, kpi = _week(sales_by_article={"05": 3000}), _real_kpi()
    wm_before, kpi_before = copy.deepcopy(wm), copy.deepcopy(kpi)
    build_facts(wm, kpi)
    assert wm == wm_before and kpi == kpi_before


def test_build_facts_week_falls_back_to_note_week():
    wm = _week()
    del wm["week"]
    assert build_facts(wm, _real_kpi())["week"] == "2026-W40"


@pytest.mark.parametrize("wm,kpi", [(None, KPI), (_week(), None), ({}, KPI), (_week(), {})])
def test_build_facts_rejects_none_and_empty_inputs(wm, kpi):
    with pytest.raises(FactsError):
        build_facts(wm, kpi)


def test_build_facts_rejects_non_dict_inputs():
    with pytest.raises(FactsError, match="must be a dict"):
        build_facts([_week()], _real_kpi())
    with pytest.raises(FactsError, match="must be a dict"):
        build_facts(_week(), "kpi")


def test_build_facts_rejects_whole_file_instead_of_single_week():
    with pytest.raises(FactsError, match="note"):
        build_facts({"weeks": [_week()]}, _real_kpi())


def test_build_facts_missing_views_by_article():
    wm = _week()
    del wm["note"]["views_by_article"]
    with pytest.raises(FactsError, match="views_by_article"):
        build_facts(wm, _real_kpi())


@pytest.mark.parametrize("week", ["2026-40", "2026-W5", "2026-W54", "2026-W00", "26-W40", 202640])
def test_build_facts_rejects_bad_week_format(week):
    wm = _week()
    wm["week"] = week
    wm["note"]["week"] = week
    with pytest.raises(FactsError, match="ISO 8601"):
        build_facts(wm, _real_kpi())


def test_build_facts_rejects_missing_or_conflicting_week():
    wm = _week()
    del wm["week"]
    del wm["note"]["week"]
    with pytest.raises(FactsError, match="no 'week'"):
        build_facts(wm, _real_kpi())
    wm = _week()
    wm["note"]["week"] = "2026-W39"
    with pytest.raises(FactsError, match="mismatch"):
        build_facts(wm, _real_kpi())


def test_build_facts_number_guard_failure_propagates():
    wm = _week(sales_by_article={"05": 9999})  # total_sales_jpy 5000 を超過
    with pytest.raises(FactsError, match="exceeds"):
        build_facts(wm, _real_kpi())
    wm = _week()
    wm["sales_by_segment"] = {"enterprise": 1}  # 合計が total と不一致
    with pytest.raises(FactsError, match="sum.*mismatch"):
        build_facts(wm, _real_kpi())


def test_build_facts_negative_article_sales_rejected():
    with pytest.raises(FactsError, match="non-negative"):
        build_facts(_week(sales_by_article={"05": -1}), _real_kpi())


def test_build_facts_banned_phrase_in_segment_name_rejected():
    wm = _week()
    wm["sales_by_segment"] = {"無料で使える層": 5000}
    with pytest.raises(FactsError, match="banned phrase"):
        build_facts(wm, _real_kpi())


def test_build_facts_banned_list_missing_fails_closed():
    kpi = _real_kpi()
    del kpi["banned_phrases"]
    with pytest.raises(FactsError, match="banned_phrases"):
        build_facts(_week(), kpi)


def test_build_facts_segment_thresholds_missing_fails_closed():
    kpi = _real_kpi()
    del kpi["segment_thresholds"]
    with pytest.raises(FactsError, match="segment_thresholds"):
        build_facts(_week(), kpi)


def test_build_facts_segment_guard_failure_propagates():
    kpi = _real_kpi()
    kpi["segment_thresholds"] = {"enterprise": {"min": 70, "max": 100, "threshold": 80}}  # 60 は範囲外
    with pytest.raises(FactsError, match="out of range"):
        build_facts(_week(), kpi)


def test_build_facts_guard_order_number_before_banned(monkeypatch):
    """数字ガード→禁止表現→セグメントの順に呼ばれる。"""
    import guards
    calls = []
    for cls in (NumberVerifier, BannedPhrasesChecker, SegmentFitChecker):
        monkeypatch.setattr(cls, "verify", lambda self, f, w, k, _n=cls.__name__: calls.append(_n))
    build_facts(_week(), _real_kpi())
    assert calls == ["NumberVerifier", "BannedPhrasesChecker", "SegmentFitChecker"]
    assert guards  # 遅延importでも同じモジュールを使う


def test_number_verifier_treats_empty_segments_as_no_segment_data():
    _verify({"sales_by_segment": {}, "article_topics": [{"article_id": "05", "views": 13}]})
