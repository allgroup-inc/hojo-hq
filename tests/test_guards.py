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


# ======================================================================
# Task 6: エッジケース・エラーシナリオ(境界値 / 欠損 / ガード間の相互作用 /
#         JSONラウンドトリップ / エラーメッセージ品質 / 実データ)
# ======================================================================
#
# Review Focus(docs/superpowers/plans/2026-10-02-kekka-facts-builder.md)との対応:
#   RF1 数字の信頼性喪失   -> test_rf1_* / test_float_* / test_zero_week_* / test_nan_inf_*
#   RF2 AI感の混入(転記のみ)-> test_rf2_*
#   RF3 セグメント二重定義   -> test_rf3_* / test_segment_*_via_checker
#   RF4 禁止表現の監視漏れ   -> test_rf4_*
#   RF5 ソース追跡可能性     -> test_rf5_*(facts に source フィールドは持たせていない。
#                              代わりにエラーが由来ソースのパスを名指しすることを検査)

import guards as _guards_module  # noqa: E402
import build_facts as _build_facts_module  # noqa: E402

_WEEKLY_METRICS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "kekka_weekly_metrics.json")


def _fail(wm, kpi=None):
    """build_facts が FactsError を投げることを確認し、メッセージを返す。"""
    with pytest.raises(FactsError) as excinfo:
        build_facts(wm, kpi if kpi is not None else _real_kpi())
    return str(excinfo.value)


# ---- 境界値: 0 / 100 / 空コレクション -------------------------------------------------

@pytest.mark.parametrize("score", [0, 100])
def test_segment_score_boundary_0_and_100_via_checker(score):
    SegmentFitChecker().verify({"segment_scores": {"enterprise": score}}, {}, KPI)


@pytest.mark.parametrize("score", [-1, 101])
def test_segment_score_just_outside_boundary_rejected(score):
    with pytest.raises(FactsError, match="out of range"):
        SegmentFitChecker().verify({"segment_scores": {"enterprise": score}}, {}, KPI)


def test_build_facts_placeholder_score_on_exact_range_edge_passes():
    """プレースホルダ(60)が [60, 60] の境界ちょうどでも通る。"""
    kpi = _real_kpi()
    kpi["segment_thresholds"] = {"enterprise": {"min": 60, "max": 60, "threshold": 60}}
    assert build_facts(_week(), kpi)["segment_scores"] == {"enterprise": 60}


def test_build_facts_placeholder_just_outside_range_rejected():
    kpi = _real_kpi()
    kpi["segment_thresholds"] = {"enterprise": {"min": 0, "max": 59, "threshold": 59}}
    assert "out of range" in _fail(_week(), kpi)


def test_build_facts_with_empty_article_list():
    """views_by_article が空でも落ちない(0除算等なし)。article_topics は空。"""
    facts = build_facts(_week(views_by_article={}, total_sales_jpy=0, buyer_count=0), _real_kpi())
    assert facts["week"] == "2026-W40"
    assert facts["article_topics"] == []
    assert facts["sales_by_segment"] == {}


def test_zero_week_all_zero_values_passes():
    """全項目0の週(売上ゼロ・ビューゼロ)は正当なデータ。"""
    wm = _week(views_by_article={"05": 0, "12": 0}, total_sales_jpy=0, buyer_count=0,
               sales_by_article={"05": 0, "12": 0})
    wm["sales_by_segment"] = {"enterprise": 0, "sme": 0}
    facts = build_facts(wm, _real_kpi())
    assert [t["views"] for t in facts["article_topics"]] == [0, 0]
    assert [t["sales_jpy"] for t in facts["article_topics"]] == [0, 0]


def test_build_facts_empty_sales_by_article_dict_adds_no_sales():
    facts = build_facts(_week(sales_by_article={}), _real_kpi())
    assert all("sales_jpy" not in t for t in facts["article_topics"])


def test_build_facts_total_sales_none_is_fine_when_no_sales_numbers_used():
    """売上数字を facts に載せないなら total_sales_jpy が None でも通る(照合対象が無い)。"""
    assert build_facts(_week(total_sales_jpy=None), _real_kpi())["week"] == "2026-W40"


def test_build_facts_total_sales_none_fails_when_sales_numbers_present():
    msg = _fail(_week(total_sales_jpy=None, sales_by_article={"05": 100}))
    assert "total_sales_jpy" in msg


def test_build_facts_sales_by_segment_none_treated_as_absent():
    wm = _week()
    wm["sales_by_segment"] = None
    assert build_facts(wm, _real_kpi())["sales_by_segment"] == {}


def test_build_facts_sales_by_segment_read_from_note_when_top_level_absent():
    facts = build_facts(_week(sales_by_segment={"enterprise": 5000}), _real_kpi())
    assert facts["sales_by_segment"] == {"enterprise": 5000}


def test_build_facts_sales_by_article_must_be_dict():
    assert "sales_by_article must be a dict" in _fail(_week(sales_by_article=[1, 2]))


def test_build_facts_sales_by_segment_must_be_dict():
    wm = _week()
    wm["sales_by_segment"] = [3000, 2000]
    assert "sales_by_segment must be a dict" in _fail(wm)


def test_build_facts_note_not_a_dict():
    wm = {"week": "2026-W40", "note": "oops"}
    assert "note" in _fail(wm)


def test_build_facts_views_by_article_not_a_dict():
    assert "views_by_article" in _fail(_week(views_by_article=[13, 5]))


def test_build_facts_missing_note_section():
    assert "note" in _fail({"week": "2026-W40", "ga4": {}})


# ---- None / 型違いの欠損フィールド(NumberVerifier 単体) --------------------------------

def test_number_verifier_topic_not_a_dict_is_rejected_as_unknown_article():
    with pytest.raises(FactsError, match="not found"):
        _verify({"article_topics": ["05"]})


def test_number_verifier_topic_missing_article_id():
    with pytest.raises(FactsError, match="article_id 'None' not found"):
        _verify({"article_topics": [{"sales_jpy": 100}]})


def test_number_verifier_article_topics_none_treated_as_empty():
    _verify({"article_topics": None})


def test_number_verifier_non_dict_weekly_metrics():
    for bad in (None, [], "x"):
        with pytest.raises(FactsError, match="note is missing"):
            NumberVerifier().verify({}, bad, KPI)


def test_number_verifier_sales_jpy_non_numeric_types():
    for bad in ("100", None, True, [1]):
        with pytest.raises(FactsError, match="non-negative number"):
            _verify({"article_topics": [{"article_id": "05", "sales_jpy": bad}]})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_inf_sales_rejected(bad):
    with pytest.raises(FactsError, match="non-negative number"):
        _verify({"article_topics": [{"article_id": "05", "sales_jpy": bad}]})
    with pytest.raises(FactsError, match="not a number"):
        _verify({"sales_by_segment": {"enterprise": bad}})


def test_number_verifier_non_finite_total_is_treated_as_missing():
    with pytest.raises(FactsError, match="total_sales_jpy is missing"):
        _verify({"sales_by_segment": {"enterprise": 0}}, _metrics(total_sales_jpy=float("nan")))


# ---- float の扱い(仕様: 丸めず原文のまま比較。int() 変換はしない) -------------------------

def test_float_article_sales_not_truncated_and_exceeding_total_rejected():
    """5000.7 を int() で 5000 に丸めて通してしまわない(丸めると total 超過を見逃す)。"""
    with pytest.raises(FactsError, match="exceeds"):
        _verify({"article_topics": [{"article_id": "05", "sales_jpy": 5000.7}]})


def test_float_article_sales_within_total_passes():
    _verify({"article_topics": [{"article_id": "05", "sales_jpy": 2500.5}]})


def test_float_segment_sum_equal_to_int_total_passes():
    _verify({"sales_by_segment": {"enterprise": 2500.0, "sme": 2500.0}})


def test_float_value_survives_build_facts_unchanged():
    facts = build_facts(_week(sales_by_article={"05": 2500.5}), _real_kpi())
    assert facts["article_topics"][0]["sales_jpy"] == 2500.5


# ---- 複数違反の混在: 最初の違反だけを報告(収集しない) ------------------------------------

def test_number_verifier_reports_first_violation_only():
    facts = {"article_topics": [
        {"article_id": "ghost1", "sales_jpy": 100},
        {"article_id": "ghost2", "sales_jpy": -5},
    ]}
    with pytest.raises(FactsError) as excinfo:
        _verify(facts)
    assert "ghost1" in str(excinfo.value)
    assert "ghost2" not in str(excinfo.value)


def test_mixed_valid_and_invalid_topics_fail_on_the_invalid_one():
    with pytest.raises(FactsError, match="'ghost'"):
        _verify({"article_topics": [
            {"article_id": "05", "views": 13, "sales_jpy": 100},
            {"article_id": "ghost", "views": 1},
            {"article_id": "12", "views": 5},
        ]})


def test_banned_checker_reports_first_violation_only():
    with pytest.raises(FactsError) as excinfo:
        _banned({"article_topics": [
            {"article_id": "05", "title": "無料でどうぞ"},
            {"article_id": "12", "title": "申請代行します"},
        ]})
    assert "無料で" in str(excinfo.value)
    assert "申請代行" not in str(excinfo.value)


def test_segment_checker_reports_first_violation_only():
    with pytest.raises(FactsError) as excinfo:
        _seg({"enterprise": 101, "sme": -1})
    assert "'enterprise'" in str(excinfo.value)
    assert "'sme'" not in str(excinfo.value)


def test_build_facts_guard_sequence_stops_at_first_failure_number_before_banned():
    """数字違反と禁止表現違反が同時にあっても、最初に当たる NumberVerifier の理由だけが出る。"""
    wm = _week()
    wm["sales_by_segment"] = {"無料で使う層": 1}  # 合計不一致(数字)かつ禁止表現(文字)
    msg = _fail(wm)
    assert "sum mismatch" in msg
    assert "banned phrase" not in msg


def test_build_facts_guard_sequence_banned_before_segment():
    """禁止表現リスト欠落とセグメント範囲外が同時なら、禁止表現側(先)で止まる。"""
    kpi = _real_kpi()
    del kpi["banned_phrases"]
    kpi["segment_thresholds"] = {"enterprise": {"min": 70, "max": 100, "threshold": 80}}
    msg = _fail(_week(), kpi)
    assert "banned_phrases" in msg
    assert "out of range" not in msg


def test_build_facts_mixed_valid_data_with_one_bad_segment_name_fails():
    wm = _week(sales_by_article={"05": 1000})
    wm["sales_by_segment"] = {"enterprise": 3000, "sme": 1000, "確実に稼げる層": 1000}
    assert "banned phrase '確実に稼'" in _fail(wm)


# ---- 禁止表現の追加エッジ ---------------------------------------------------------------

def test_banned_nested_dict_value_is_scanned():
    with pytest.raises(FactsError, match=r"article_topics\[0\]\.meta\.note"):
        _banned({"article_topics": [{"article_id": "05", "meta": {"note": "申請代行OK"}}]})


def test_banned_tuple_value_is_scanned():
    with pytest.raises(FactsError, match=r"article_topics\[0\]\.tags\[0\]"):
        _banned({"article_topics": [{"article_id": "05", "tags": ("ChatGPT",)}]})


def test_banned_non_string_values_and_non_dict_topics_ignored():
    _banned({"article_topics": [{"article_id": "05", "views": 13, "ok": None}, "文字列トピック", 5]})


def test_banned_non_dict_segment_sections_ignored():
    _banned({"sales_by_segment": ["申請代行"], "segment_scores": None})


def test_banned_non_dict_kpi_fails_closed():
    with pytest.raises(FactsError, match="banned_phrases"):
        BannedPhrasesChecker().verify({}, {}, None)


def test_rf4_banned_list_present_but_phrase_not_matching_passes_clean_text():
    """RF4: リストが有効なら実在の禁止語を検出し、無関係な文は誤検知しない(正例・負例の両方)。"""
    kpi = _real_kpi()
    clean = {"article_topics": [{"article_id": "05", "title": "助成金の締切を実数で確認する"}]}
    BannedPhrasesChecker().verify(clean, {}, kpi)
    for phrase in kpi["banned_phrases"]:
        with pytest.raises(FactsError, match="banned phrase"):
            BannedPhrasesChecker().verify(
                {"article_topics": [{"article_id": "05", "title": f"前置き{phrase}後置き"}]}, {}, kpi)


def test_rf4_every_real_banned_phrase_blocks_build_facts_via_segment_name():
    kpi = _real_kpi()
    for phrase in kpi["banned_phrases"]:
        wm = _week()
        wm["sales_by_segment"] = {phrase: 5000}
        assert "banned phrase" in _fail(wm, kpi), phrase


# ---- Guard 基底クラス --------------------------------------------------------------------

def test_guard_is_abstract_and_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Guard()


def test_guard_subclass_without_verify_cannot_be_instantiated():
    class Incomplete(Guard):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_guard_subclass_may_delegate_to_abstract_verify():
    class Delegating(Guard):
        def verify(self, facts, weekly_metrics, kpi):
            return super().verify(facts, weekly_metrics, kpi)

    assert Delegating().verify({}, {}, {}) is None


def test_all_three_guards_share_the_same_facts_error_class():
    assert _guards_module.FactsError is _build_facts_module.FactsError is FactsError
    assert issubclass(FactsError, Exception)


# ---- JSON シリアライズ / ラウンドトリップ ---------------------------------------------------

def test_facts_dict_to_dict_json_round_trip_equal():
    wm = _week(sales_by_article={"05": 3000})
    wm["sales_by_segment"] = {"enterprise": 3000, "sme": 2000}
    facts = build_facts(wm, _real_kpi())
    restored = json.loads(json.dumps(facts, ensure_ascii=False))
    assert restored == facts


def test_facts_dict_json_has_no_circular_refs_and_keeps_japanese():
    wm = _week()
    wm["sales_by_segment"] = {"沖縄の中小企業": 5000}
    text = json.dumps(build_facts(wm, _real_kpi()), ensure_ascii=False, allow_nan=False)
    assert "沖縄の中小企業" in text


def test_facts_dict_to_dict_is_a_deep_copy():
    topics = [{"article_id": "05", "views": 13}]
    fd = FactsDict(week="2026-W40", article_topics=topics, sales_by_segment={"a": 1}, segment_scores={"a": 60})
    out = fd.to_dict()
    out["article_topics"][0]["views"] = 999
    out["sales_by_segment"]["a"] = 999
    assert topics[0]["views"] == 13
    assert fd.sales_by_segment == {"a": 1}


def test_facts_dict_to_dict_keys_and_types():
    fd = FactsDict(week="2026-W40", article_topics=[], sales_by_segment={}, segment_scores={})
    assert fd.to_dict() == {"week": "2026-W40", "article_topics": [], "sales_by_segment": {}, "segment_scores": {}}


def test_build_facts_result_is_independent_of_input_after_return():
    wm = _week()
    facts = build_facts(wm, _real_kpi())
    facts["article_topics"].append({"article_id": "zzz"})
    assert [t["article_id"] for t in build_facts(wm, _real_kpi())["article_topics"]] == ["05", "12"]


# ---- エラーメッセージの品質(何が・どこで・どうすべきか) --------------------------------------

def test_error_message_for_unknown_article_lists_valid_choices():
    with pytest.raises(FactsError) as excinfo:
        _verify({"article_topics": [{"article_id": "ghost"}]})
    msg = str(excinfo.value)
    assert "'ghost'" in msg and "weekly_metrics.note.views_by_article" in msg
    assert "['05', '12']" in msg  # 有効な候補を提示


def test_error_message_for_views_mismatch_shows_both_values():
    with pytest.raises(FactsError) as excinfo:
        _verify({"article_topics": [{"article_id": "05", "views": 99}]})
    msg = str(excinfo.value)
    assert "99" in msg and "13" in msg and "'05'" in msg


def test_error_message_for_sum_mismatch_shows_both_totals():
    with pytest.raises(FactsError) as excinfo:
        _verify({"sales_by_segment": {"enterprise": 1}})
    msg = str(excinfo.value)
    assert "1" in msg and "5000" in msg


def test_error_message_for_undefined_segment_lists_valid_segments():
    with pytest.raises(FactsError) as excinfo:
        _seg({"ghost": 50})
    msg = str(excinfo.value)
    assert "'ghost'" in msg and "['enterprise', 'sme', 'startup']" in msg


def test_error_message_for_out_of_range_shows_score_and_range():
    with pytest.raises(FactsError) as excinfo:
        _seg({"sme": 150})
    msg = str(excinfo.value)
    assert "150" in msg and "[0, 100]" in msg and "'sme'" in msg


def test_error_message_for_banned_phrase_shows_phrase_field_and_text():
    with pytest.raises(FactsError) as excinfo:
        _banned({"article_topics": [{"article_id": "05", "title": "ChatGPTで書いた"}]})
    msg = str(excinfo.value)
    assert "'ChatGPT'" in msg and "article_topics[0].title" in msg and "ChatGPTで書いた" in msg


def test_error_message_fail_closed_names_file_to_fix():
    """リスト欠落時のエラーは直すべきファイルを案内する(救済策つき)。"""
    with pytest.raises(FactsError, match=r"data/kekka_kpi\.json"):
        BannedPhrasesChecker().verify({}, {}, {})
    with pytest.raises(FactsError, match=r"data/kekka_kpi\.json"):
        _seg({"enterprise": 1}, {})


def test_error_message_for_bad_week_shows_expected_format_and_value():
    wm = _week()
    wm["week"] = wm["note"]["week"] = "2026-40"
    msg = _fail(wm)
    assert "YYYY-Www" in msg and "'2026-40'" in msg


def test_all_error_messages_are_nonempty_strings_for_a_batch_of_bad_inputs():
    bad_inputs = [
        (None, _real_kpi()), (_week(), None), ({}, _real_kpi()), ({"weeks": []}, _real_kpi()),
        (_week(views_by_article=None), _real_kpi()), (_week(sales_by_article=3), _real_kpi()),
    ]
    for wm, kpi in bad_inputs:
        with pytest.raises(FactsError) as excinfo:
            build_facts(wm, kpi)
        assert isinstance(str(excinfo.value), str) and len(str(excinfo.value)) > 10


# ---- Review Focus 個別 ---------------------------------------------------------------------

def test_rf1_every_number_in_facts_traces_to_source():
    """RF1: facts の views / sales_jpy はすべて weekly_metrics 原文と一致する。"""
    wm = _week(sales_by_article={"05": 3000, "12": 2000})
    facts = build_facts(wm, _real_kpi())
    for topic in facts["article_topics"]:
        assert topic["views"] == wm["note"]["views_by_article"][topic["article_id"]]
        assert topic["sales_jpy"] == wm["note"]["sales_by_article"][topic["article_id"]]


def test_rf1_tampered_number_after_build_is_caught_by_guard():
    """RF1: facts が原文と食い違えば NumberVerifier が即 FactsError にする。"""
    wm = _week(sales_by_article={"05": 3000})
    facts = build_facts(wm, _real_kpi())
    facts["article_topics"][0]["views"] += 1
    with pytest.raises(FactsError, match="views mismatch"):
        NumberVerifier().verify(facts, wm, _real_kpi())
    facts["article_topics"][0]["views"] -= 1
    facts["article_topics"][0]["sales_jpy"] = 99999
    with pytest.raises(FactsError, match="exceeds"):
        NumberVerifier().verify(facts, wm, _real_kpi())


def test_rf2_facts_contain_only_transcribed_fields():
    """RF2: 解釈・推計・文章を足さない。article_topics のキーは転記元の3つだけ。"""
    wm = _week(sales_by_article={"05": 3000})
    wm["ga4"] = {"pageviews": 999, "summary": "好調です"}
    wm["line"] = {"friends": 42}
    wm["collected_at"] = "2026-10-02T09:00:00+09:00"
    facts = build_facts(wm, _real_kpi())
    assert set(facts) == {"week", "article_topics", "sales_by_segment", "segment_scores"}
    for topic in facts["article_topics"]:
        assert set(topic) <= {"article_id", "views", "sales_jpy"}
    assert "好調です" not in json.dumps(facts, ensure_ascii=False)  # GA4等の他ソースの文を持ち込まない


def test_rf2_no_free_text_strings_other_than_ids_week_and_segment_names():
    facts = build_facts(_week(sales_by_article={"05": 3000}), _real_kpi())
    texts = [s for _, s in _guards_module._iter_strings(facts, "facts")]
    allowed = {"2026-W40", "05", "12", "enterprise", "sme", "startup", "other"}
    assert set(texts) <= allowed


def test_rf3_segment_defaults_match_task8_rule_0_100_60():
    """RF3: SegmentFitChecker の既定値と kpi.json の定義が 0-100 / 閾値60 で一致(二重定義しない)。"""
    assert (_guards_module._SEGMENT_DEFAULT_MIN, _guards_module._SEGMENT_DEFAULT_MAX,
            _guards_module._SEGMENT_DEFAULT_THRESHOLD) == (0, 100, 60)
    for name, rule in _real_kpi()["segment_thresholds"].items():
        assert (rule["min"], rule["max"], rule["threshold"]) == (0, 100, 60), name


def test_rf3_build_facts_placeholder_equals_kpi_threshold():
    """RF3: build_facts のプレースホルダ値は kpi の推奨閾値と同値(閾値の二重定義を避ける)。"""
    kpi = _real_kpi()
    facts = build_facts(_week(), kpi)
    assert facts["segment_scores"] == {n: r["threshold"] for n, r in kpi["segment_thresholds"].items()}
    assert _build_facts_module._DEFAULT_SEGMENT_SCORE == _guards_module._SEGMENT_DEFAULT_THRESHOLD


def test_rf5_errors_name_the_source_field_they_were_checked_against():
    """RF5: 食い違いのエラーは由来ソース(weekly_metrics.note.*)のパスと原文の値を名指しする。"""
    with pytest.raises(FactsError, match=r"weekly_metrics\.note\.total_sales_jpy is 5000"):
        _verify({"sales_by_segment": {"enterprise": 1}})
    with pytest.raises(FactsError, match=r"weekly_metrics\.note\.views_by_article has 13"):
        _verify({"article_topics": [{"article_id": "05", "views": 99}]})
    with pytest.raises(FactsError, match=r"weekly_metrics\.note\.total_sales_jpy \(5000\)"):
        _verify({"article_topics": [{"article_id": "05", "sales_jpy": 6000}]})


def test_rf5_top_level_and_note_week_conflict_is_not_silently_resolved():
    """RF5: 2つのソース(top-level / note)の週が食い違うとき、どちらかを黙って採用しない。"""
    wm = _week()
    wm["note"]["week"] = "2026-W41"
    assert "mismatch" in _fail(wm)


# ---- 実データ(data/kekka_kpi.json / data/kekka_weekly_metrics.json) ------------------------

def test_real_kpi_article_ids_and_titles_work_end_to_end():
    """台帳の実記事ID・実タイトルで構築でき、実タイトルが禁止表現に誤検知されない。"""
    kpi = _real_kpi()
    views = {aid: 1 for aid in kpi["articles"]}
    facts = build_facts(_week(views_by_article=views), kpi)
    assert [t["article_id"] for t in facts["article_topics"]] == list(kpi["articles"])
    for aid, article in kpi["articles"].items():
        BannedPhrasesChecker().verify({"article_topics": [{"article_id": aid, "title": article["title"]}]}, {}, kpi)


def test_real_kpi_default_build_facts_with_schema_shaped_week():
    """_schema どおりの週(ga4 / line / collected_at を含む)でも余分なキーは無視して構築できる。"""
    wm = {
        "week": "2026-W40",
        "collected_at": "2026-10-05T09:00:00+09:00",
        "note": {"week": "2026-W40", "views_by_article": {"05": 13, "12": 5},
                 "total_likes": 3, "total_sales_jpy": 2560, "buyer_count": 2},
        "ga4": {"sessions": 100},
        "line": {"friends": 10},
        "line_source": "csv",
    }
    facts = build_facts(wm, _real_kpi())
    assert facts["week"] == "2026-W40" and len(facts["article_topics"]) == 2


def test_real_weekly_metrics_file_every_recorded_week_builds():
    """実ファイルに週が記録されていれば、全週が検証を通る(空なら対象なし)。"""
    data = json.load(open(_WEEKLY_METRICS_PATH, encoding="utf-8"))
    assert isinstance(data["weeks"], list)
    kpi = _real_kpi()
    for week in data["weeks"]:
        facts = build_facts(week, kpi)
        json.dumps(facts, ensure_ascii=False)
