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
