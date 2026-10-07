"""WikiSkill Phase 2 Task 1: wiki_validate.py の検査。

検証器は「誤った知識・公開できない知識・根拠の無い知識」を正式知識にしない最後の歯止め。
見逃し(false negative)が最大のリスクなので、負例を厚めに置く。
fixture `wk` = 一時 git リポジトリ(origin = hojo-hq)+ commit 済み Experience 1セッション(note 行)
+ 議事1件(frontmatter)+ 失敗台帳(FK-002)+ 有効な候補1件。
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
REPO_ROOT = SCRIPTS.parent
SCRIPT = SCRIPTS / "wiki_validate.py"
sys.path.insert(0, str(SCRIPTS))

import wiki_schema  # noqa: E402
import wiki_validate  # noqa: E402
from check_repo_scope import FORBIDDEN_CONTENT  # noqa: E402
from wiki_schema import (  # noqa: E402
    BODY_SECTIONS,
    CANDIDATES_DIR,
    WIKI_DIR,
    all_source_ids,
    dedup_key,
    make_candidate_id,
    parse_wiki_frontmatter,
    render_wiki,
)
from wiki_validate import build_context, resolve_source, validate_tree  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
PRIVATE_URL = "https://github.com/allgroup-inc/glow-docs-private.git"
TS = "2026-10-01T00:00:00Z"
REF = f"session-s1@{TS}"
NOTE_TEXT = "学び: マージ前に競合ファイル一覧を確認すると事故が減る"
QUOTE = "競合ファイル一覧を確認すると事故が減る"
DID = "D20261001-merge-rule"
DECISION_REL = "docs/議事/議事_20261001_マージ手順.md"
DECISION_TEXT = f"""---
decision_id: {DID}
date: 2026-10-01
title: マージ手順の固定
status: adopted
tags: [merge]
---
# マージ手順の固定

## なぜ
競合の見落としを防ぐ。

## 三名体制の議論
- **ウタガイ**: 手順が増えると速度が落ちる

## 裁定
マージ前に競合一覧を必ず確認する
"""
FK_ROW = ("| FK-002 | 2026-07-23 | ヒヤリハット+プロセス | mainへのマージで競合ファイル一覧を確認せずコミットした"
          " | 実害なし | 自己申告 | 手順が仕組み化されていない | ルール化 | 横展開 | 監視中 | 2027-01-23 |")
LEDGER = ("# 失敗台帳\n\n| ID | 発生日 | 分類 | 事実経過 | 影響 | 発見経路 | 真因 | 対策(形態) | 横展開 | ステータス | 見直し/クローズ予定 |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|\n" + FK_ROW + "\n")
TITLE = "マージ前に競合ファイル一覧を確認する"
APPROVED = {
    "wiki_id": "W20261020-merge-conflict",
    "approved_by": "小柳(テスト)",
    "approved_at": "2026-10-20",
    "review_by": "2027-04-18",
    "review": {"スイシン": "事故が減る", "ウタガイ": "急ぎの修正で手順が重い", "ベッカイ": "スクリプト化"},
}


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _event(sid, text, ts=TS, visibility="public", repo="allgroup-inc/hojo-hq"):
    return {"ts": ts, "session_id": sid, "event": "note", "repo": repo, "visibility": visibility,
            "branch": "main", "text": text}


def _write_session(root, sid, events):
    p = root / ".claude/experience/2026-10" / f"session-{sid}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    return p


def sections_for(fm, knowledge="マージ前に競合ファイル一覧を確認する。"):
    """抽出器が書く本文の形(Provenance に全 source id を1行ずつ)。"""
    prov = "\n".join(f"- {s}: 根拠" for s in all_source_ids(fm)) or "- なし"
    return {
        "## 知識": knowledge,
        "## 根拠(Provenance)": prov,
        "## 反証(ウタガイ)": "急ぎの修正では手順が重い。",
        "## 適用範囲と例外": "main へのマージ全般。",
        "## 関連": "なし",
    }


def base_fm(**over):
    fm = {
        "candidate_id": "",
        "title": TITLE,
        "summary": "マージ前に競合一覧を確認すると、マーカー入りのまま公開する事故を防げる。",
        "evidence": [{"ref": REF, "quote": QUOTE}],
        "confidence": 0.4,
        "confidence_basis": "rule=R2 / Exp のみ",
        "visibility": "public",
        "repo": "allgroup-inc/hojo-hq",
        "created_at": "2026-10-07T00:00:00Z",
        "proposed_by": "knowledge_extract.py@1 rule-based",
        "contradictions": [],
        "related_wiki": [],
        "related_skills": [],
        "review_status": "candidate",
        "dedup_key": "",
        "extract_run": "run-test",
        "source_experience": [REF],
    }
    fm.update(over)
    key = dedup_key(fm["title"], all_source_ids(fm))
    fm["dedup_key"] = fm["dedup_key"] or key
    fm["candidate_id"] = fm["candidate_id"] or make_candidate_id(date(2026, 10, 7), "merge-conflict", fm["dedup_key"], set())
    return fm


def write_candidate(root, fm, sections=None, name=None):
    p = root / CANDIDATES_DIR / (name or f"{fm['candidate_id']}.md")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_wiki(fm, sections or sections_for(fm)), encoding="utf-8")
    return p


@pytest.fixture
def wk(tmp_path):
    root = tmp_path / "wk"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "remote", "add", "origin", PUBLIC_URL)
    _write_session(root, "s1", [_event("s1", NOTE_TEXT)])
    (root / DECISION_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / DECISION_REL).write_text(DECISION_TEXT, encoding="utf-8")
    (root / "docs/失敗台帳.md").write_text(LEDGER, encoding="utf-8")
    write_candidate(root, base_fm())
    (root / CANDIDATES_DIR / ".gitkeep").write_text("")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


# ---------------------------------------------------------------- helpers

def codes(root):
    return {c for _p, c, _r in validate_tree(root)[0]}


def cand_path(root):
    paths = sorted((root / CANDIDATES_DIR).glob("*.md"))
    assert len(paths) == 1, paths
    return paths[0]


def read_fm(path):
    return parse_wiki_frontmatter(path.read_text(encoding="utf-8"))[0]


def edit(root, drop=None, **over):
    """唯一の候補の frontmatter を書き換える(本文の Provenance は source に合わせて作り直す)。"""
    p = cand_path(root)
    fm = read_fm(p)
    fm.update(over)
    if drop:
        fm.pop(drop, None)
    p.write_text(render_wiki(fm, sections_for(fm)), encoding="utf-8")
    return root


def edit_body(root, drop):
    p = cand_path(root)
    fm = read_fm(p)
    secs = {k: v for k, v in sections_for(fm).items() if k != drop}
    p.write_text(render_wiki(fm, secs), encoding="utf-8")
    return root


def rename(root, name):
    p = cand_path(root)
    p.rename(p.with_name(name))
    return root


def copy_candidate(root):
    p = cand_path(root)
    shutil.copy(p, p.with_name("K20261007-copy-0000.md"))


def move_to_root(root):
    p = cand_path(root)
    shutil.move(str(p), str(root / WIKI_DIR / p.name))


def promote(root, **over):
    p = cand_path(root)
    fm = read_fm(p)
    fm.update({"review_status": "approved", **APPROVED})
    fm.update(over)
    (root / WIKI_DIR / f"{fm['wiki_id']}.md").write_text(render_wiki(fm, sections_for(fm)), encoding="utf-8")
    p.unlink()
    return root


def add_candidate_same_words(root, **over):
    fm = base_fm(source_failure=["FK-002"], **over)
    return write_candidate(root, fm)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return root


def add_untracked_session(root, sid):
    _write_session(root, sid, [_event(sid, NOTE_TEXT)])


def commit_private_row(root, sid):
    _write_session(root, sid, [_event(sid, NOTE_TEXT, visibility="private")])
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", f"private {sid}")


def fk_quote():
    return {"ref": "FK-002", "quote": "競合ファイル一覧を確認せず"}


def run(args, cwd=None):
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(cwd or REPO_ROOT),
                          capture_output=True, text=True, env=env, timeout=120)


# ---------------------------------------------------------------- brief のテスト

def test_valid_candidate_passes(wk):
    assert validate_tree(wk) == ([], [])


def test_missing_required_key_fails(wk):
    assert codes(edit(wk, drop="summary")) == {"V01"}


def test_missing_body_section_fails(wk):
    assert "V01" in codes(edit_body(wk, drop="## 反証(ウタガイ)"))


def test_candidate_id_must_match_filename(wk):
    assert "V02" in codes(rename(wk, "K20261020-other-0000.md"))


def test_duplicate_candidate_id_fails(wk):
    copy_candidate(wk)
    assert "V02" in codes(wk)


def test_no_source_fails(wk):
    assert "V03" in codes(edit(wk, source_experience=[], source_decision=[], source_failure=[]))


def test_unresolved_experience_fails(wk):
    assert "V03" in codes(edit(wk, source_experience=["session-zzz@2026-10-01T00:00:00Z"]))


def test_untracked_experience_not_resolvable(wk):
    add_untracked_session(wk, "U")
    assert "V03" in codes(edit(wk, source_experience=[f"session-U@{TS}"],
                               evidence=[{"ref": f"session-U@{TS}", "quote": QUOTE}]))


def test_unknown_decision_fails(wk):
    assert "V03" in codes(edit(wk, source_decision=["D20990101-none"]))


def test_fk_resolves(wk):
    assert codes(edit(wk, source_failure=["FK-002"], evidence=[fk_quote()])) == set()


def test_quote_must_be_verbatim(wk):
    assert "V04" in codes(edit(wk, evidence=[{"ref": REF, "quote": "要約した別の文"}]))


def test_private_experience_source_fails(wk):
    commit_private_row(wk, "P")
    ref = f"session-P@{TS}"
    c = codes(edit(wk, source_experience=[ref], evidence=[{"ref": ref, "quote": QUOTE}]))
    assert "V05" in c and "V03" not in c  # 解決はできる(=読めた)うえで公開不可として止まる


def test_visibility_must_match_repo(wk):
    assert "V05" in codes(edit(wk, visibility="private"))


def test_forbidden_content_fails(wk):
    assert "V06" in codes(edit(wk, summary=f"x {FORBIDDEN_CONTENT[0]} y"))


def test_summary_over_200_fails(wk):
    assert "V07" in codes(edit(wk, summary="あ" * 201))


def test_approved_in_candidates_fails(wk):
    assert "V08" in codes(edit(wk, review_status="approved", **APPROVED))


def test_candidate_in_wiki_root_fails(wk):
    move_to_root(wk)
    assert "V08" in codes(wk)


def test_approved_requires_approver_utagai_review_by(wk):
    promote(wk, review={"スイシン": "a", "ウタガイ": "なし", "ベッカイ": "c"})
    assert "V09" in codes(wk)


def test_bot_approver_rejected(wk):
    promote(wk, approved_by="github-actions[bot]")
    assert "V09" in codes(wk)


def test_duplicate_requires_duplicate_of(wk):
    promote(wk)
    add_candidate_same_words(wk)
    assert "V10" in codes(wk)


def test_synonyms_format(wk):
    write(wk, "docs/wiki/_synonyms.txt", "マージ, merge\nmerge, 統合\n")
    assert "V14" in codes(wk)


def test_dangling_wiki_ref_fails(wk):
    assert "V15" in codes(edit(wk, related_wiki=["W20990101-none"]))


def test_selftest_passes():
    r = run(["--selftest"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "自己点検OK(" in r.stdout


def test_cli_exit_codes(wk):
    r = run([], cwd=wk)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "OK: Wiki 0件・候補 1件・違反なし"
    edit(wk, drop="title")
    assert run([], cwd=wk).returncode == 1


# ---------------------------------------------------------------- 追加の正例

def test_promoted_wiki_passes(wk):
    promote(wk)
    assert validate_tree(wk) == ([], [])


def test_decision_source_with_verbatim_quote_passes(wk):
    assert codes(edit(wk, source_decision=[DID],
                      evidence=[{"ref": DID, "quote": "マージ前に競合一覧を必ず確認する"}])) == set()


def test_duplicate_of_declared_passes(wk):
    promote(wk)
    add_candidate_same_words(wk, duplicate_of=APPROVED["wiki_id"])
    assert validate_tree(wk) == ([], [])


def test_valid_synonyms_pass(wk):
    write(wk, "docs/wiki/_synonyms.txt", "# 同義語\nマージ, merge\n締切, 期限, deadline\n")
    assert validate_tree(wk) == ([], [])


def test_related_wiki_existing_passes(wk):
    promote(wk)
    add_candidate_same_words(wk, title="締切アラートの配信時期", related_wiki=[APPROVED["wiki_id"]])
    assert validate_tree(wk) == ([], [])


def test_summary_exactly_200_passes(wk):
    assert codes(edit(wk, summary="あ" * 200)) == set()


def test_json_output(wk):
    edit(wk, drop="title")
    r = run(["--json"], cwd=wk)
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["warnings"] == []
    assert any(v[1] == "V01" for v in out["violations"])


def test_github_actions_annotation(wk):
    edit(wk, drop="title")
    env = {**os.environ, "GITHUB_ACTIONS": "true"}
    r = subprocess.run([sys.executable, str(SCRIPT)], cwd=str(wk), capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "::error file=docs/wiki/_candidates/" in r.stdout


# ---------------------------------------------------------------- 追加の負例(見逃しを潰す)

def test_unreadable_frontmatter_is_v01(wk):
    p = cand_path(wk)
    p.write_text(p.read_text(encoding="utf-8").replace('"ref"', "ref"), encoding="utf-8")
    assert "V01" in codes(wk)


def test_internal_key_spoof_is_v01(wk):
    p = cand_path(wk)
    p.write_text(p.read_text(encoding="utf-8").replace("---\n", "---\n_place: official\n", 1), encoding="utf-8")
    assert "V01" in codes(wk)


@pytest.mark.parametrize("over", [
    {"confidence": 1.5},
    {"confidence": "高い"},
    {"evidence": []},
    {"evidence": [{"ref": REF}]},
    {"visibility": "internal"},
    {"review_status": "needs_review"},
    {"created_at": "昨日"},
    {"dedup_key": "xyz"},
    {"related_wiki": "W20261020-x"},
    {"source_experience": REF},
    {"needs_review": ["D1"]},
    {"title": ""},
    {"review_status": "rejected"},  # rejected_reason なし
])
def test_schema_type_and_enum_violations(wk, over):
    assert "V01" in codes(edit(wk, **over))


def test_extra_or_reordered_section_is_v01(wk):
    p = cand_path(wk)
    fm = read_fm(p)
    secs = sections_for(fm)
    order = list(BODY_SECTIONS)
    order[0], order[1] = order[1], order[0]
    text = render_wiki(fm, {}).rstrip("\n") + "\n\n" + "\n\n".join(f"{h}\n{secs[h]}" for h in order) + "\n"
    p.write_text(text, encoding="utf-8")
    assert "V01" in codes(wk)


def test_empty_section_is_v01(wk):
    p = cand_path(wk)
    fm = read_fm(p)
    p.write_text(render_wiki(fm, {**sections_for(fm), "## 関連": ""}), encoding="utf-8")
    assert "V01" in codes(wk)


def test_candidate_id_bad_format_is_v02(wk):
    assert "V02" in codes(edit(wk, candidate_id="K2026-bad"))


def test_candidate_id_suffix_must_match_dedup_key(wk):
    assert "V02" in codes(edit(wk, dedup_key="f" * 40))


def test_unknown_fk_fails(wk):
    assert "V03" in codes(edit(wk, source_failure=["FK-999"]))


def test_bad_source_format_fails(wk):
    assert "V03" in codes(edit(wk, source_experience=["s1@2026-10-01"]))


def test_provenance_section_must_list_every_source(wk):
    p = cand_path(wk)
    fm = read_fm(p)
    fm["source_failure"] = ["FK-002"]
    secs = {**sections_for(fm), "## 根拠(Provenance)": f"- {REF}: 根拠"}
    p.write_text(render_wiki(fm, secs), encoding="utf-8")
    assert "V03" in codes(wk)


def test_modified_tracked_experience_not_resolvable(wk):
    _write_session(wk, "s1", [_event("s1", "書き換えた別の文")])
    assert "V03" in codes(wk)


def test_staged_but_uncommitted_experience_not_resolvable(wk):
    add_untracked_session(wk, "S")
    git(wk, "add", "-A")
    ref = f"session-S@{TS}"
    assert "V03" in codes(edit(wk, source_experience=[ref], evidence=[{"ref": ref, "quote": QUOTE}]))


def test_evidence_ref_must_be_a_source(wk):
    assert "V04" in codes(edit(wk, evidence=[fk_quote()]))


def test_quote_from_other_source_is_not_verbatim(wk):
    assert "V04" in codes(edit(wk, evidence=[{"ref": REF, "quote": "競合ファイル一覧を確認せずコミットした"}]))


def test_quote_over_200_fails(wk):
    assert "V07" in codes(edit(wk, evidence=[{"ref": REF, "quote": "あ" * 201}]))


def test_other_repo_experience_row_fails(wk):
    _write_session(wk, "O", [_event("O", NOTE_TEXT, repo="allgroup-inc/glow-docs-private")])
    git(wk, "add", "-A")
    git(wk, "commit", "-q", "-m", "o")
    ref = f"session-O@{TS}"
    assert "V05" in codes(edit(wk, source_experience=[ref], evidence=[{"ref": ref, "quote": QUOTE}]))


def test_repo_field_must_match(wk):
    assert "V05" in codes(edit(wk, repo="allgroup-inc/glow-docs-private"))


def test_private_repo_candidate_fails(wk):
    git(wk, "remote", "set-url", "origin", PRIVATE_URL)
    assert "V05" in codes(wk)


def test_forbidden_content_in_body_fails(wk):
    p = cand_path(wk)
    fm = read_fm(p)
    p.write_text(render_wiki(fm, {**sections_for(fm), "## 関連": FORBIDDEN_CONTENT[-1]}), encoding="utf-8")
    assert "V06" in codes(wk)


def test_forbidden_content_json_escaped_fails(wk):
    word = FORBIDDEN_CONTENT[0]
    escaped = "".join(f"\\u{ord(ch):04x}" for ch in word)
    p = cand_path(wk)
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace("related_skills: []", f'related_skills: ["{escaped}"]'), encoding="utf-8")
    assert "V06" in codes(wk)


def test_forbidden_content_fullwidth_fails(wk):
    word = FORBIDDEN_CONTENT[0]
    wide = "".join(chr(ord(ch) + 0xFEE0) if "!" <= ch <= "~" else ch for ch in word)
    assert "V06" in codes(edit(wk, summary=f"x {wide} y"))


@pytest.mark.parametrize("over", [
    {"title": "あ" * 81},
    {"evidence": [{"ref": REF, "quote": QUOTE}] * 11},
])
def test_length_limits(wk, over):
    assert "V07" in codes(edit(wk, **over))


def test_knowledge_over_1500_fails(wk):
    p = cand_path(wk)
    fm = read_fm(p)
    p.write_text(render_wiki(fm, sections_for(fm, knowledge="あ" * 1501)), encoding="utf-8")
    assert "V07" in codes(wk)


def test_approved_missing_key_fails(wk):
    promote(wk)
    p = next((wk / WIKI_DIR).glob("W*.md"))
    fm = read_fm(p)
    fm.pop("review_by")
    p.write_text(render_wiki(fm, sections_for(fm)), encoding="utf-8")
    assert "V08" in codes(wk)


def test_stray_file_in_wiki_dir_fails(wk):
    write(wk, "docs/wiki/sub/x.md", "x")
    write(wk, "docs/wiki/_draft.md", "x")
    vs = validate_tree(wk)[0]
    assert {(p, c) for p, c, _ in vs} >= {("docs/wiki/sub/x.md", "V08"), ("docs/wiki/_draft.md", "V08")}


@pytest.mark.parametrize("over", [
    {"approved_by": "Claude"},
    {"approved_by": "  "},
    {"approved_by": "renovate[bot]"},
    {"review": {"スイシン": "a", "ウタガイ": "  TBD ", "ベッカイ": "c"}},
    {"review": {"スイシン": "a", "ベッカイ": "c"}},
    {"review": "全員賛成"},
    {"review_by": "2026-10-20"},
    {"review_by": "来年"},
    {"approved_at": "2026/10/20"},
])
def test_approved_content_violations(wk, over):
    promote(wk, **over)
    assert "V09" in codes(wk)


def test_wiki_id_must_match_filename(wk):
    promote(wk)
    p = next((wk / WIKI_DIR).glob("W*.md"))
    p.rename(p.with_name("W20261020-other.md"))
    assert "V09" in codes(wk)


def test_approved_with_duplicate_of_fails(wk):
    promote(wk, duplicate_of="W20261020-merge-conflict")
    assert "V10" in codes(wk)


def test_similar_candidates_need_duplicate_of(wk):
    add_candidate_same_words(wk)
    assert "V10" in codes(wk)


def test_candidate_duplicate_of_other_candidate_passes(wk):
    first = read_fm(cand_path(wk))["candidate_id"]
    add_candidate_same_words(wk, duplicate_of=first)
    assert validate_tree(wk) == ([], [])


@pytest.mark.parametrize("text", [
    "孤立\n",                                     # 1語だけ
    "マージ, マージ\n",                           # 同じ語だけ(実質1語)
    "a, merge\n",                                 # 1字の語
    ", ".join(f"語{i}" for i in range(9)) + "\n",  # 9語
    "".join(f"語{i}a, 語{i}b\n" for i in range(201)),  # 201行
])
def test_synonyms_violations(wk, text):
    write(wk, "docs/wiki/_synonyms.txt", text)
    assert "V14" in codes(wk)


def test_synonyms_forbidden_word_fails(wk):
    write(wk, "docs/wiki/_synonyms.txt", f"{FORBIDDEN_CONTENT[0]}, 統合名\n")
    assert "V14" in codes(wk)


def test_dangling_superseded_by_fails(wk):
    promote(wk)
    p = next((wk / WIKI_DIR).glob("W*.md"))
    fm = read_fm(p)
    fm.update({"review_status": "superseded", "superseded_by": "W20990101-none"})
    (wk / "docs/wiki/_archive").mkdir(parents=True)
    (wk / "docs/wiki/_archive" / p.name).write_text(render_wiki(fm, sections_for(fm)), encoding="utf-8")
    p.unlink()
    assert "V15" in codes(wk)


def test_dangling_duplicate_of_fails(wk):
    assert "V15" in codes(edit(wk, duplicate_of="W20990101-none"))


def test_rule_exception_fails_closed(wk, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")
    promote(wk)
    add_candidate_same_words(wk, title="締切アラートの配信時期")  # 比べる相手があるので類似度を必ず計算する
    monkeypatch.setattr(wiki_schema, "title_similarity", boom)
    assert "V10" in codes(wk)


def test_context_failure_fails_closed(wk, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("git がない")
    monkeypatch.setattr(wiki_validate, "build_context", boom)
    vs, _ = validate_tree(wk)
    assert vs and vs[0][1] == "V03"


def test_resolve_source_unknown_is_empty(wk):
    ctx = build_context(wk)
    assert resolve_source("session-zzz@2026-10-01T00:00:00Z", "experience", ctx) == ("", None)
    assert resolve_source("FK-999", "failure", ctx) == ("", None)
    assert resolve_source(REF, "nonsense", ctx) == ("", None)
    text, row = resolve_source(REF, "experience", ctx)
    assert text == NOTE_TEXT and row["session_id"] == "s1"


def test_cli_outside_git_fails_closed(tmp_path):
    assert run([], cwd=tmp_path).returncode == 1


def test_cli_bad_args_exit_2():
    assert run(["--nope"]).returncode == 2


# ---------------------------------------------------------------- 修正ラウンド1(レビュー指摘)

LONG_TAIL = "のは、急ぎの修正でも夜間の自動生成でも休日のリリース作業でも、どの担当でも同じ"


def test_superset_title_of_approved_is_duplicate(wk):
    """承認済みタイトル全体 + 長い語尾の候補は、片方向の類似度だと 0.6 未満で素通りしていた。"""
    long_title = TITLE + LONG_TAIL
    assert wiki_schema.title_similarity(long_title, TITLE) < wiki_schema.DUPLICATE_RATIO  # 片方向では見逃す形
    promote(wk)
    add_candidate_same_words(wk, title=long_title)
    assert "V10" in codes(wk)


def test_superset_title_of_other_candidate_is_duplicate(wk):
    add_candidate_same_words(wk, title=TITLE + LONG_TAIL)
    assert "V10" in codes(wk)


@pytest.mark.parametrize("n", [1, 7])
def test_quote_shorter_than_min_fails(wk, n):
    assert "V04" in codes(edit(wk, evidence=[{"ref": REF, "quote": QUOTE[:n]}]))


def test_quote_exactly_min_passes(wk):
    assert wiki_schema.MIN_QUOTE == 8
    assert codes(edit(wk, evidence=[{"ref": REF, "quote": QUOTE[:8]}])) == set()


def test_undecodable_committed_experience_is_v03(wk):
    bad = wk / ".claude/experience/2026-10/session-X.jsonl"
    bad.write_bytes(b'{"ts": "2026-10-01T00:00:00Z", "text": "\xff\xfe"}\n')
    git(wk, "add", "-A")
    git(wk, "commit", "-q", "-m", "bad")
    vs = validate_tree(wk)[0]
    assert (".claude/experience/2026-10/session-X.jsonl", "V03") in {(p, c) for p, c, _ in vs}


def test_committed_symlink_experience_not_resolvable(wk):
    link = wk / ".claude/experience/2026-10/session-L.jsonl"
    link.symlink_to("session-s1.jsonl")  # 中身は s1 と同じ(解決できてしまえば素通り)
    git(wk, "add", "-A")
    git(wk, "commit", "-q", "-m", "link")
    ref = f"session-L@{TS}"
    assert "V03" in codes(edit(wk, source_experience=[ref], evidence=[{"ref": ref, "quote": QUOTE}]))


@pytest.mark.parametrize("sep", ["​", "­", " "])
def test_forbidden_content_with_inserted_chars_fails(wk, sep):
    word = FORBIDDEN_CONTENT[0]
    assert "V06" in codes(edit(wk, summary=f"x {word[:2]}{sep}{word[2:]} y"))


def test_review_by_beyond_6_months_fails(wk):
    promote(wk, review_by="2099-12-31")
    assert "V09" in codes(wk)


def test_review_by_at_183_days_passes(wk):
    promote(wk, review_by="2027-04-21")  # 2026-10-20 + 183日
    assert validate_tree(wk) == ([], [])
    p = next((wk / WIKI_DIR).glob("W*.md"))
    p.write_text(p.read_text(encoding="utf-8").replace("2027-04-21", "2027-04-22"), encoding="utf-8")
    assert "V09" in codes(wk)


# ---------------------------------------------------------------- 修正ラウンド2(V06 の不可視文字照合を Cf/Z に限定)

def _allowed_private_repo_name():
    """FK-006 行に出てくる非公開リポ名(禁止語ではなく言及は許される)。実文字列はテストに書かない。"""
    ledger = (REPO_ROOT / "docs/失敗台帳.md").read_text(encoding="utf-8")
    row = next(l for l in ledger.splitlines() if l.startswith("| FK-006 "))
    target = wiki_schema.normalize(FORBIDDEN_CONTENT[6])
    names = {t for t in re.findall(r"[A-Za-z0-9-]+", row)
             if wiki_schema.normalize(t) == target and FORBIDDEN_CONTENT[6] not in t}
    assert names, "FK-006 行に非公開リポ名が見つからない"
    return sorted(names)[0]


def test_strip_invisible_keeps_symbols():
    assert wiki_schema.strip_invisible("A​B­ C　D") == "abcd"
    assert wiki_schema.strip_invisible("a-b_c/d") == "a-b_c/d"


def test_allowed_private_repo_name_passes_v06(wk):
    name = _allowed_private_repo_name()
    assert codes(edit(wk, summary=f"移設先は {name} です")) == set()


def test_forbidden_content_6_itself_fails(wk):
    assert "V06" in codes(edit(wk, summary=f"環境変数 {FORBIDDEN_CONTENT[6]}X を使う"))


# ---------------------------------------------------------------- Phase 2 Task 4: 矛盾検知(V11〜V13)・needs_review

FORBID = "自動生成物は main へ直接 push しない"
CONFLICT_TITLE = "自動生成物の直接 push は速い"
OPPOSITE = "マージ前の競合一覧の確認はしない"  # 承認済み(基本の候補)と「マージ・競合・一覧・確認」が重なる
DECISION_TITLE = "生成物の取り扱い"           # 基本の候補の語(マージ・競合・公開…)と重ならない題
NEG_DID = "D20261005-push-rule"


def add_decision(root, did=NEG_DID, date_="2026-10-05", status="adopted", tags=None, outcome=FORBID,
                 title=DECISION_TITLE, commit=True):
    """否定語を含みうる議事を1件足して commit する(検証器は commit 済みの議事だけを読む)。"""
    tag_line = f"tags: [{', '.join(tags)}]\n" if tags else ""
    text = (f"---\ndecision_id: {did}\ndate: {date_}\ntitle: {title}\nstatus: {status}\n{tag_line}---\n"
            f"# {title}\n\n## なぜ\n事故を防ぐ。\n\n## 三名体制の議論\n- **ウタガイ**: 遅くなる\n\n## 裁定\n{outcome}\n")
    rel = f"docs/議事/議事_{date_.replace('-', '')}_{did}.md"
    write(root, rel, text)
    if commit:
        git(root, "add", "-A", "docs/議事")
        git(root, "commit", "-q", "-m", f"decision {did}")
    return rel


def make_conflicting(root):
    add_decision(root)
    return edit(root, title=CONFLICT_TITLE, review_status="conflict",
                contradictions=[{"source": NEG_DID, "note": "Decision が否定(しない)"}])


def promote_clean(root):
    return promote(root)


def boom(*a, **k):
    raise RuntimeError("conflict boom")


def test_contradictions_require_conflict_status(wk):
    assert "V11" in codes(edit(wk, contradictions=[{"source": "x", "note": "y"}]))


def test_negation_decision_two_unit_overlap_is_conflict(wk):
    add_decision(wk, outcome="自動生成物は main へ直接 push しない")
    assert "V12" in codes(edit(wk, title="自動生成物の直接 push は速い"))


def test_one_unit_overlap_is_not_conflict(wk):
    add_decision(wk, outcome="直接 push しない")
    assert "V12" not in codes(edit(wk, title="push の速さ"))


def test_non_adopted_or_test_tag_decisions_ignored(wk):
    add_decision(wk, did="D20261005-deferred", status="deferred")
    add_decision(wk, did="D20261006-test", date_="2026-10-06", tags=["test"])
    assert "V12" not in codes(edit(wk, title=CONFLICT_TITLE))


def test_conflict_candidate_cannot_be_approved(wk):
    make_conflicting(wk)
    promote(wk)
    assert "V12" in codes(wk)


def test_acknowledged_decision_allows_approval(wk):
    make_conflicting(wk)
    promote(wk, acknowledged_decisions=[{"decision": NEG_DID, "reason": "Decision と同じ向き"}])
    assert "V12" not in codes(wk)


def test_new_decision_marks_wiki_needs_review_exit0_warning(wk):
    promote_clean(wk)
    add_decision(wk, did="D20261101-opposite", date_="2026-11-01", outcome=OPPOSITE)
    r = run([], cwd=wk)
    assert r.returncode == 0 and "needs_review" in r.stdout, r.stdout + r.stderr


def test_conflict_check_exception_fails_closed(wk, monkeypatch):
    monkeypatch.setattr(wiki_schema, "decision_conflicts", boom)
    assert "V12" in codes(wk)


# ---------------------------------------------------------------- Task 4: 追加の境界(brief 外)

def test_conflict_candidate_with_contradictions_passes(wk):
    make_conflicting(wk)
    assert validate_tree(wk) == ([], [])


def test_decision_conflicts_returns_ids_and_units(wk):
    add_decision(wk)
    ds = [d for d in build_context(wk)["decisions"]]
    got = wiki_schema.decision_conflicts(CONFLICT_TITLE, ds)
    assert [g["decision"] for g in got] == [NEG_DID]
    assert {"自動生成物", "直接", "push"} <= set(got[0]["units"])
    assert wiki_schema.decision_conflicts(CONFLICT_TITLE, ds, after="2026-10-05") == []  # date > after だけ


def test_decision_without_negation_is_not_conflict(wk):
    add_decision(wk, outcome="自動生成物は main へ直接 push する")
    assert "V12" not in codes(edit(wk, title=CONFLICT_TITLE))


def test_synonym_counts_once_in_conflict(wk):
    """同義語表の同じ行の語は1語。「push」と「プッシュ」だけの重なりは2語にならない。"""
    add_decision(wk, outcome="プッシュ と push はしない")
    assert "V12" in codes(edit(wk, title="push とプッシュの速さ"))  # 同義語表が無ければ2語
    write(wk, "docs/wiki/_synonyms.txt", "push, プッシュ\n")
    assert "V12" not in codes(wk)


def test_acknowledged_other_decision_does_not_cover(wk):
    make_conflicting(wk)
    promote(wk, acknowledged_decisions=[{"decision": "D20990101-other", "reason": "別の議事"}])
    assert "V12" in codes(wk)


def test_approved_older_decision_is_v12_not_warning(wk):
    """approved_at 以前の Decision と矛盾 = 承認の時点で分かっていた矛盾 → V12(warning ではない)。"""
    make_conflicting(wk)
    promote(wk)
    vs, warns = validate_tree(wk)
    assert "V12" in {c for _p, c, _r in vs} and warns == []


def test_newer_decision_is_warning_not_violation(wk):
    promote_clean(wk)
    add_decision(wk, did="D20261101-opposite", date_="2026-11-01", outcome=OPPOSITE)
    vs, warns = validate_tree(wk)
    assert vs == [] and [d for _p, d, _r in warns] == ["D20261101-opposite"]


def test_newer_decision_acknowledged_clears_warning(wk):
    promote(wk, acknowledged_decisions=[{"decision": "D20261101-opposite", "reason": "同じ向き(確認済み)"}])
    add_decision(wk, did="D20261101-opposite", date_="2026-11-01", outcome=OPPOSITE)
    assert validate_tree(wk) == ([], [])


def test_needs_review_exception_is_warning(wk, monkeypatch):
    promote_clean(wk)
    monkeypatch.setattr(wiki_schema, "needs_review", boom)
    vs, warns = validate_tree(wk)
    assert warns and warns[0][0].startswith("docs/wiki/W")


def test_github_actions_needs_review_annotation(wk):
    promote_clean(wk)
    add_decision(wk, did="D20261101-opposite", date_="2026-11-01", outcome=OPPOSITE)
    env = {**os.environ, "GITHUB_ACTIONS": "true"}
    r = subprocess.run([sys.executable, str(SCRIPT)], cwd=str(wk), capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0
    assert "::warning file=docs/wiki/W20261020-merge-conflict.md::needs_review D20261101-opposite" in r.stdout


def test_needs_review_map(wk):
    promote_clean(wk)
    assert wiki_validate.needs_review_map(wk) == {}
    add_decision(wk, did="D20261101-opposite", date_="2026-11-01", outcome=OPPOSITE)
    assert wiki_validate.needs_review_map(wk) == {"docs/wiki/W20261020-merge-conflict.md": ["D20261101-opposite"]}


def test_uncommitted_decision_not_used_for_conflict(wk):
    add_decision(wk, commit=False)
    assert "V12" not in codes(edit(wk, title=CONFLICT_TITLE))


# ---------------------------------------------------------------- Task 4: 検証器も commit 済みの議事・台帳だけを読む

def test_untracked_decision_not_resolvable(wk):
    rel = add_decision(wk, did="D20261005-untracked", outcome="マージ前に競合ファイル一覧を必ず見る", commit=False)
    ev_ = [{"ref": "D20261005-untracked", "quote": "マージ前に競合ファイル一覧を必ず見る"}]
    assert (wk / rel).is_file()
    assert "V03" in codes(edit(wk, source_decision=["D20261005-untracked"], evidence=ev_))
    git(wk, "add", "-A", "docs/議事")
    git(wk, "commit", "-q", "-m", "commit it")
    assert "V03" not in codes(wk)


def test_modified_decision_not_resolvable(wk):
    ev_ = [{"ref": DID, "quote": "マージ前に競合一覧を必ず確認する"}]
    edit(wk, source_decision=[DID], evidence=ev_)
    assert "V03" not in codes(wk)
    p = wk / DECISION_REL
    p.write_text(p.read_text(encoding="utf-8") + "\n追記(未 commit)\n", encoding="utf-8")
    assert "V03" in codes(wk)


def test_uncommitted_ledger_edit_makes_fk_unresolvable(wk):
    edit(wk, source_failure=["FK-002"], evidence=[fk_quote()], source_experience=[])
    assert "V03" not in codes(wk)
    ledger = wk / "docs/失敗台帳.md"
    ledger.write_text(ledger.read_text(encoding="utf-8") + FK_ROW.replace("FK-002", "FK-003") + "\n", encoding="utf-8")
    assert "V03" in codes(wk)
    assert build_context(wk)["fk_rows"] == {}


def test_extractor_and_validator_share_committed_reader():
    import knowledge_extract
    assert knowledge_extract._committed_files is wiki_validate.committed_files
