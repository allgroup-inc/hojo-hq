"""WikiSkill Phase 2 Task 1: wiki_schema.py の検査。

候補・正式 Wiki の frontmatter(1行1キー・値はスカラーか1行 JSON)の読み書き、ID・dedup_key・normalize・
同義語表・タイトル類似度を固定する。
"""
import os
import sys
from datetime import date

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

from wiki_schema import (  # noqa: E402
    BODY_SECTIONS,
    CANDIDATE_ID_RE,
    WikiFormatError,
    dedup_key,
    make_candidate_id,
    normalize,
    parse_synonyms,
    parse_wiki_frontmatter,
    render_wiki,
    slugify,
    title_similarity,
)

GOOD = """---
candidate_id: K20261020-fk-006-ab12
title: マージ前に競合一覧を確認する
summary: 競合ファイル一覧を確認せずにマージすると事故になる
evidence: [{"ref": "FK-002", "quote": "競合ファイル一覧を確認せず"}]
confidence: 0.7
---

## 知識
マージ前に競合一覧を確認する。
"""

FM = {
    "candidate_id": "K20261020-fk-006-ab12",
    "title": "マージ前に競合一覧を確認する",
    "summary": "2026",  # 数字だけの文字列も文字列のまま戻ること
    "evidence": [{"ref": "FK-002", "quote": "競合ファイル一覧を確認せず"}],
    "confidence": 0.7,
    "confidence_basis": "rule=R3 / FK 1件",
    "visibility": "public",
    "repo": "allgroup-inc/hojo-hq",
    "created_at": "2026-10-20T00:00:00Z",
    "proposed_by": "knowledge_extract.py@1 rule-based",
    "contradictions": [],
    "related_wiki": [],
    "related_skills": ["writing-plans-hojo"],
    "review_status": "candidate",
    "dedup_key": "ab12" * 10,
    "extract_run": "run-1",
    "source_failure": ["FK-002"],
    "rejected_reason": "",
    "duplicate_of": "[先頭が括弧の文字列]",
}
SECTIONS = {h: f"{h[3:]}の本文" for h in BODY_SECTIONS}


def test_parse_wiki_frontmatter_scalar_and_json():
    fm, body = parse_wiki_frontmatter(GOOD)
    assert fm["evidence"][0]["ref"] and body.startswith("## 知識")
    assert fm["confidence"] == 0.7 and isinstance(fm["confidence"], float)
    assert fm["title"] == "マージ前に競合一覧を確認する"


def test_parse_wiki_frontmatter_rejects_bad_json():
    with pytest.raises(WikiFormatError):
        parse_wiki_frontmatter(GOOD.replace('"ref"', "ref"))


def test_candidate_id_format():
    assert CANDIDATE_ID_RE.match(make_candidate_id(date(2026, 10, 20), "fk-006", "ab12" * 10, set()))


def test_dedup_key_stable_under_whitespace_and_order():
    assert dedup_key("A  b", ["x", "y"]) == dedup_key("a b", ["y", "x"])


def test_normalize_nfkc_lower_strip():
    assert normalize("Ｍｅｒｇｅ！ ") == "merge"


def test_render_then_parse_roundtrip():
    fm, _ = parse_wiki_frontmatter(render_wiki(FM, SECTIONS))
    assert fm == FM


# ---- 追加の境界(負例を厚めに)

@pytest.mark.parametrize("text", [
    "title: x\n",                                   # 先頭が --- でない
    "---\ntitle: x\n",                              # 閉じ忘れ
    "---\ntitle x\n---\n",                          # コロンなし
    "---\ntitle: a\ntitle: b\n---\n",              # 同じキーが2回
    "---\n_place: official\n---\n",                 # _ 始まりのキーは内部用(偽装させない)
    "---\nevidence: [1, 2\n---\n",                  # JSON が閉じていない
    "---\n  title: x\n---\n",                       # 字下げ(入れ子)は対応外
])
def test_parse_wiki_frontmatter_rejects_malformed(text):
    with pytest.raises(WikiFormatError):
        parse_wiki_frontmatter(text)


def test_candidate_id_collision_extends_to_6hex():
    key = "abcdef" + "0" * 34
    taken = {"K20261020-x-abcd", "K20261020-x-abcde"}
    assert make_candidate_id(date(2026, 10, 20), "x", key, taken) == "K20261020-x-abcdef"
    with pytest.raises(ValueError):
        make_candidate_id(date(2026, 10, 20), "x", key, taken | {"K20261020-x-abcdef"})


def test_slugify_ascii_only_and_fallback():
    assert slugify("FK-006 マージ", "x") == "fk-006"
    assert slugify("マージ", "note-abc123") == "note-abc123"
    assert len(slugify("a" * 100, "x")) <= 40


def test_parse_synonyms_rejects_single_word_and_repeated_word():
    groups, reasons = parse_synonyms("マージ, merge\nmerge, 統合\n孤立\n# コメント\n締切, 期限 # 行末コメント\n")
    assert groups == [frozenset({"マージ", "merge"}), frozenset({"締切", "期限"})]
    assert len(reasons) == 2


def test_title_similarity():
    assert title_similarity("マージ前に競合一覧を確認する", "マージ前に競合一覧を確認する") == 1.0
    assert title_similarity("git push の手順", "締切アラートの配信") < 0.6
    assert title_similarity("", "x") == 0.0


# ---------------------------------------------------------------- 矛盾判定の照合範囲(議事 D20261007-wikiskill-conflict-scope)

import wiki_schema  # noqa: E402
from wiki_schema import decision_conflicts, negation_sentences  # noqa: E402

# 実データ(D20261006-skill-dist-privacy-gate・D20261006-wikiskill-phase1 の裁定)を要約した合成例の長い裁定文。
# 組織全体の語(phase・議事・小柳・実装・skill)は否定語の無い文にあり、否定文は update-skills.sh の1文だけ。
RULING_PROSE = ("採用。今後の Skill 配布は原則 Skill変更 → Privacy / Scope → 三名体制レビュー → 小柳 Decision Gate → 配布 "
                "の順とする。ただし Phase 1 では `scripts/update-skills.sh` そのものを変更しない。"
                "実装は別タスクとして起票。議事は Phase 2 の実装で参照する。")
FK003_LESSON = ("事故+プロセス: Lighthouse CI が performance スコア基準未達で連続失敗し、Issue が開いたまま"
                "自動 bot コメントが積まれ続けた。レイアウト系 CSS の適用範囲を広げる変更は議事と三名体制で決め、"
                "実装を本番で実測する。")
PHASE1_RULING = ("WikiSkill Phase 1(記憶基盤)の導入 裁定: 2026-10-06 小柳さん承認。Task 9(PR・マージ・タグ)は別承認。"
                 " - ウタガイの3点は受け入れ条件として実装に取り込む。 - 実装は Subagent-driven で進め、skill と議事を参照する。")


def _adopted(outcome, title="配布の手順", did="D20261006-x"):
    return {"id": did, "status": "adopted", "date": "2026-10-06", "title": title, "outcome": outcome, "tags": []}


@pytest.fixture(autouse=True)
def _fresh_conflict_cache():
    wiki_schema._clear_conflict_cache()
    yield
    wiki_schema._clear_conflict_cache()


def test_negation_sentences_split_on_period_newline_and_bullets():
    text = "A はする。B はしない\nC は禁止 - D は進める - E は却下 ・F はやめる ① G は不可 1. H は進める 2) I はしない"
    assert negation_sentences(text) == ["B はしない", "C は禁止", "E は却下", "F はやめる", "G は不可", "I はしない"]


def test_negation_sentences_midword_marks_do_not_split():
    """空白の直後でない ・ や丸数字(規則①・scripts・sh)は文の区切りにしない。丸数字の範囲はかなを含まない。"""
    assert negation_sentences("規則①と scripts・sh の変更はしない") == ["規則1と scripts・sh の変更はしない"]
    assert negation_sentences("ひらがなとカタカナだけの文はしない") == ["ひらがなとカタカナだけの文はしない"]


def test_negation_sentences_title_only_negation():
    assert negation_sentences("直接 push は禁止\n本文は手順の説明だけ。例外もある") == ["直接 push は禁止"]


def test_negation_sentences_removes_code_spans():
    assert negation_sentences("Phase 1 では `scripts/update-skills.sh` を変更しない") == ["Phase 1 では   を変更しない"]


def test_negation_inside_code_span_is_not_a_negation_sentence():
    """コード断片の中の否定語は数えない(パス・コマンドは Decision の文ではない)。"""
    assert negation_sentences("手順は `--no-verify しない` を参照する") == []


def test_negation_sentences_demonstrative_pulls_one_previous_sentence():
    assert negation_sentences("生成物を作り直すときに新しいデータを取り込む手順は使わない。この手順は採用しない") == [
        "生成物を作り直すときに新しいデータを取り込む手順は使わない", "この手順は採用しない"]
    # 箇条書きの印・空白の後でも指示語として見る。遡るのは1文だけ
    assert negation_sentences("A を使う。B を作る。 - その案は却下") == ["B を作る", "その案は却下"]


def test_negation_sentences_demonstrative_without_negation_pulls_nothing():
    assert negation_sentences("A を使う。この方法は速い。B は禁止") == ["B は禁止"]


def test_negation_sentences_negation_without_demonstrative_stays_alone():
    assert negation_sentences("A を使う。B は禁止") == ["B は禁止"]


def test_decision_feats_cache_key_and_negation_only_features():
    import memory_bootstrap as mb
    d = _adopted(RULING_PROSE)
    negs, feats = wiki_schema._decision_feats(d, mb)
    assert negs == ("しない",)
    assert (d["title"], d["outcome"]) in wiki_schema._DECISION_FEATS
    assert "小柳" not in feats and "scripts" not in feats and "phase" in feats


def test_real_data_ruling_prose_is_not_conflict():
    """実データの偽陽性の再現: 裁定文の否定語の無い文の語(phase・議事・小柳・実装・skill)では当てない。"""
    import memory_bootstrap as mb
    whole = mb.features(_adopted(RULING_PROSE)["title"] + " " + RULING_PROSE)
    for text in (FK003_LESSON, PHASE1_RULING):
        old_units = [g[0][1] for g in wiki_schema._conflict_groups(text, None, mb) if mb._group_matches(g, whole)]
        assert len(old_units) >= wiki_schema.CONFLICT_MIN_UNITS  # 全文で照合していた頃は矛盾になっていた
        assert decision_conflicts(text, [_adopted(RULING_PROSE)]) == []


def test_backtick_path_only_overlap_is_not_conflict():
    d = _adopted("Phase 1 では `scripts/update-skills.sh` を変更しない")
    assert decision_conflicts("Phase 1 の scripts と update-skills.sh の手順", [d]) == []


def test_abc_forbidden_still_conflicts():
    got = decision_conflicts("学び: 自動生成物を main へ直接 push したら当日中に反映できた",
                             [_adopted("自動生成物は main へ直接 push しない")])
    assert [g["decision"] for g in got] == ["D20261006-x"] and {"自動生成物", "直接", "push"} <= set(got[0]["units"])


def test_genuinely_incompatible_alert_candidate_conflicts():
    got = decision_conflicts("締切7日前にアラートを送ると登録率が上がる",
                             [_adopted("締切7日前のアラートは配信しない。利用者向けは約1か月前から")])
    assert got and {"締切", "アラート"} <= set(got[0]["units"])


@pytest.mark.xfail(strict=True, reason="既知の偽陰性: 「送らない」は NEGATION_WORDS に無い。否定語リストの拡張は別議事")
def test_known_false_negative_verb_not_in_negation_words():
    assert decision_conflicts("締切7日前にアラートを送ると登録率が上がる",
                              [_adopted("締切7日前のアラートは送らない。利用者向けは約1か月前から")])


def test_anaphoric_negation_conflicts_via_previous_sentence():
    """R5 の fixture と同じ形: 禁止の中身は前の文、否定語は「この手順は採用しない」にある。"""
    d = _adopted("生成物を作り直すときに新しいデータを取り込む手順は使わない。この手順は採用しない",
                 title="生成物の取り込み手順")
    got = decision_conflicts("学び: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む", [d])
    assert got and {"生成物", "データ"} <= set(got[0]["units"])


def test_negation_sentences_demonstrative_after_opening_bracket():
    """開き括弧・かぎの後の指示語も文頭として見る(「(この運用は禁止)」「「この運用は禁止」」)。"""
    assert negation_sentences("A を使う。(この運用は禁止)") == ["A を使う", "(この運用は禁止)"]
    assert negation_sentences("A を使う。（この運用は禁止）") == ["A を使う", "(この運用は禁止)"]
    assert negation_sentences("A を使う。「「この運用は禁止」」") == ["A を使う", "「「この運用は禁止」」"]
    assert negation_sentences("A を使う。【その案は却下】") == ["A を使う", "【その案は却下】"]


def test_negation_sentences_mid_sentence_demonstrative_is_not_supported():
    """文の途中の指示語(「…ため、この案は却下」)は直前の文を引かない(議事のウタガイ①に明記した未対応の形)。"""
    assert negation_sentences("A を導入する。準備が間に合わないため、この案は却下") == ["準備が間に合わないため、この案は却下"]


@pytest.mark.xfail(strict=True, reason="検出できない形: 件名が主題で裁定は「却下。…」だけ(件名は照合に含めない)。"
                                       "件名を常に比較する案は小柳判断(議事 D20261007-wikiskill-conflict-scope)")
def test_known_false_negative_title_subject_rejected_outcome():
    d = _adopted("却下。準備が間に合わないため", title="締切7日前アラートの導入")
    assert decision_conflicts("締切7日前にアラートを送ると登録率が上がる", [d])


@pytest.mark.xfail(strict=True, reason="照合範囲の変更で落ちた形(ウタガイ③): 禁止の文は否定語の一覧に無い動詞で、"
                                       "別の文の「しない」だけが否定語。全文照合では検出していた")
def test_known_regression_negation_word_only_in_unrelated_sentence():
    d = _adopted("締切7日前のアラートは送らない。Phase 1 では設定を変更しない")
    assert decision_conflicts("締切7日前にアラートを送ると登録率が上がる", [d])


def test_regression_shape_was_caught_by_whole_text_matching():
    """上の xfail の形は、全文照合なら2語以上当たっていた(新しい照合範囲で落ちた回帰であることの確認)。"""
    import memory_bootstrap as mb
    text = "締切7日前にアラートを送ると登録率が上がる"
    for title, outcome in (("配布の手順", "締切7日前のアラートは送らない。Phase 1 では設定を変更しない"),
                           ("締切7日前アラートの導入", "却下。準備が間に合わないため")):
        whole = mb.features(title + " " + outcome)
        hit = [g[0][1] for g in wiki_schema._conflict_groups(text, None, mb) if mb._group_matches(g, whole)]
        assert {"締切", "アラート"} <= set(hit)
