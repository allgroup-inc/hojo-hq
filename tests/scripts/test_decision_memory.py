"""WikiSkill Phase 1 Task 3: decision_memory.py の検査。

frontmatter 付きの新しい議事と、frontmatter 無しの過去の議事の両方を読めること、
ウタガイ(反対理由)が空の新規議事を --check が止めること、どの入力でも落ちないことを固定する。
"""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import decision_memory  # noqa: E402
from decision_memory import (  # noqa: E402
    check_decision,
    load_decisions,
    parse_decision,
    parse_frontmatter,
)

SCRIPT = os.path.abspath(os.path.join(SCRIPTS, "decision_memory.py"))
TODAY = dt.date(2026, 10, 6)

FM = (
    "---\ndecision_id: D20261006-x\ndate: 2026-10-06\ntitle: テスト決定\nstatus: adopted\n"
    "tags: [a, b]\n---\n## なぜ\n理由A\n## 三名体制の議論\n- **ウタガイ**: コストが高い\n## 裁定\n採用\n"
)


def write(root: Path, relpath: str, text: str) -> Path:
    p = Path(root) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def tmp_docs(tmp_path):
    (tmp_path / "docs" / "議事").mkdir(parents=True)
    return tmp_path


def run(args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args], capture_output=True, text=True
    )


# ---- brief の 9 テスト ------------------------------------------------------

def test_parse_frontmatter_tags_list():
    fm, body = parse_frontmatter(FM)
    assert fm["tags"] == ["a", "b"] and body.startswith("## なぜ")


def test_review_by_defaults_to_180_days(tmp_docs):
    d = parse_decision(write(tmp_docs, "docs/議事_20261006_x.md", FM), tmp_docs)
    assert d["review_by"] == "2027-04-04"


def test_legacy_file_date_from_filename(tmp_docs):
    d = parse_decision(
        write(
            tmp_docs,
            "docs/議事_20260810_北極星.md",
            "# 議事: 北極星\n見直し期限: **2026-09-07**\n- **ウタガイ(反対理由)**: n=11では検証不能\n## 裁定\nSEO先行\n",
        ),
        tmp_docs,
        today=TODAY,
    )
    assert d["legacy"] and d["date"] == "2026-08-10" and d["review_by"] == "2026-09-07"
    assert d["review_status"] == "expired" and "n=11" in d["utagai"] and "SEO" in d["outcome"]


def test_legacy_date_from_hyphenated_filename(tmp_docs):
    d = parse_decision(write(tmp_docs, "docs/議事_airecipeお題補充_2026-08-10.md", "# a\n"), tmp_docs)
    assert d["date"] == "2026-08-10"


def test_legacy_date_from_body(tmp_docs):
    d = parse_decision(
        write(tmp_docs, "docs/議事_総額.md", "# 議事: 総額\n- 日付: 2026-07-26 / 起案: x\n"), tmp_docs
    )
    assert d["date"] == "2026-07-26"


def test_load_scans_both_globs(tmp_docs):
    write(tmp_docs, "docs/議事_20260101_a.md", "# a\n")
    write(tmp_docs, "docs/議事/議事_20260102_b.md", "# b\n")
    write(tmp_docs, "docs/議事/sub/x.md", "# nested\n")  # 下位ディレクトリは対象外
    ds = load_decisions(tmp_docs)
    assert len(ds) == 2
    assert not any("sub" in d["path"] for d in ds)


def test_load_dedupes_file_reachable_twice(tmp_docs, monkeypatch):
    write(tmp_docs, "docs/議事_20260101_a.md", "# a\n")
    monkeypatch.setattr(
        decision_memory, "DECISION_GLOBS", ["docs/議事_*.md", "docs/議事_2026*.md"]
    )
    assert len(load_decisions(tmp_docs)) == 1


def test_load_dedupes_symlink_to_same_file(tmp_docs):
    real = write(tmp_docs, "docs/議事/議事_20260102_b.md", "# b\n")
    try:
        os.symlink(real, tmp_docs / "docs" / "議事_20260102_link.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlink 不可")
    assert len(load_decisions(tmp_docs)) == 1


def test_check_rejects_empty_utagai(tmp_docs):
    p = write(tmp_docs, "docs/議事_20261006_y.md", FM.replace("コストが高い", ""))
    errs = check_decision(p, tmp_docs)
    assert any("ウタガイ" in e for e in errs)


def test_check_rejects_missing_status(tmp_docs):
    p = write(tmp_docs, "docs/議事_20261006_z.md", FM.replace("status: adopted\n", ""))
    errs = check_decision(p, tmp_docs)
    assert any("status" in e for e in errs)


def test_check_ignores_legacy(tmp_docs):
    p = write(tmp_docs, "docs/議事_20260810_old.md", "# old\n")
    assert check_decision(p, tmp_docs) == []


def test_cli_check_exit_code(tmp_docs):
    bad = write(tmp_docs, "docs/議事_20261006_bad.md", FM.replace("コストが高い", ""))
    good = write(tmp_docs, "docs/議事_20261006_good.md", FM)
    rb = run(["--check", str(bad)])
    assert rb.returncode == 1 and "ウタガイ" in rb.stdout
    assert run(["--check", str(good)]).returncode == 0


# ---- 追加: parse_frontmatter の最小サブセット -------------------------------

def test_frontmatter_blank_value_and_comment_and_fullwidth_colon():
    text = (
        "---\ndecision_id: D1-x   # D + 日付 + slug\nsupersedes:\ndecided_by：小柳\n"
        "tags: a, b\n---\n本文\n"
    )
    fm, body = parse_frontmatter(text)
    assert fm["decision_id"] == "D1-x"
    assert fm["supersedes"] == ""
    assert fm["decided_by"] == "小柳"
    assert fm["tags"] == ["a", "b"]
    assert body == "本文\n"


@pytest.mark.parametrize(
    "text",
    [
        "# 議事\n本文\n",                                  # frontmatter 無し
        "---\nkey: value\n本文(閉じ忘れ)\n",                 # 閉じ忘れ
        "---\nitems:\n  - a\n  - b\n---\n本文\n",           # 入れ子/リスト
        "---\nkey: |\n  block\n---\n本文\n",                 # ブロック記法
        "---\ntags: [a, b\n---\n本文\n",                     # 壊れたリスト
        "---\n---\n本文\n",                                  # 空
        "",
    ],
)
def test_frontmatter_unsupported_is_legacy_never_crashes(text):
    fm, body = parse_frontmatter(text)
    assert fm == {} and body == text


def test_unsupported_yaml_file_is_read_as_legacy(tmp_docs):
    p = write(tmp_docs, "docs/議事_20260101_n.md", "---\nitems:\n  - a\n---\n# 議事: n\n")
    d = parse_decision(p, tmp_docs)
    assert d["legacy"] and d["date"] == "2026-01-01" and d["id"] == "legacy:議事_20260101_n"
    # 読み取りは legacy 扱いだが、--check の関門は素通りさせない(項目4)
    errs = check_decision(p, tmp_docs)
    assert len(errs) == 1 and "frontmatter を読めません" in errs[0]


# ---- 追加: parse_decision --------------------------------------------------

def test_frontmatter_decision_fields(tmp_docs):
    p = write(tmp_docs, "docs/議事_20261006_x.md", FM)
    d = parse_decision(p, tmp_docs, today=TODAY)
    assert d["id"] == "D20261006-x" and d["legacy"] is False
    assert d["title"] == "テスト決定" and d["status"] == "adopted" and d["tags"] == ["a", "b"]
    assert d["path"] == "docs/議事_20261006_x.md"
    assert d["why"] == "理由A" and d["utagai"] == "コストが高い" and d["outcome"] == "採用"
    assert d["review_status"] == "active"
    assert d["text_head"].startswith("テスト決定 a b ")


def test_legacy_id_status_and_unknown_values(tmp_docs):
    p = write(tmp_docs, "docs/議事_20260810_old.md", "# 議事録: 旧\n")
    d = parse_decision(p, tmp_docs)
    assert d["id"] == "legacy:議事_20260810_old"
    assert d["status"] == "unknown" and d["tags"] == [] and d["scope"] == ""
    assert d["title"] == "議事録: 旧"


def test_review_status_active_expired_unknown(tmp_docs):
    active = parse_decision(
        write(tmp_docs, "docs/議事_20261006_a.md", "# a\n見直し期限: 2026-10-06\n"), tmp_docs, today=TODAY
    )
    expired = parse_decision(
        write(tmp_docs, "docs/議事_20261006_b.md", "# b\n見直し期限: 2026-10-05\n"), tmp_docs, today=TODAY
    )
    unknown = parse_decision(write(tmp_docs, "docs/議事_nodate.md", "# c\n"), tmp_docs, today=TODAY)
    assert active["review_status"] == "active"
    assert expired["review_status"] == "expired"
    assert unknown["review_status"] == "unknown" and unknown["date"] is None and unknown["review_by"] is None


def test_review_deadline_variants(tmp_docs):
    a = parse_decision(write(tmp_docs, "docs/議事_x1.md", "# a\n(見直し期限: 2026-12-01)\n"), tmp_docs)
    b = parse_decision(write(tmp_docs, "docs/議事_x2.md", "# b\n見直し期限：**2026-12-02**\n"), tmp_docs)
    assert a["review_by"] == "2026-12-01" and b["review_by"] == "2026-12-02"


def test_invalid_dates_do_not_crash(tmp_docs):
    p = write(tmp_docs, "docs/議事_20269999_bad.md", "# a\n- 日付: 2026-13-45\n見直し期限: 2026-99-99\n")
    d = parse_decision(p, tmp_docs)
    assert d["date"] is None and d["review_by"] is None and d["review_status"] == "unknown"


def test_legacy_sections_and_utagai_forms(tmp_docs):
    text = (
        "# 議事: x\n- 日付: 2026-07-01\n"
        "## 目的\n目的の文\n## 前提\n前提の文\n## 代替案\n- a案\n## 議論\n"
        "- **ベッカイ**: 別解の文\n"
        "- ウタガイ(担当: ◯◯さん)：全角コロンの反対理由\n"
        "## 結論\n採用する\n"
    )
    d = parse_decision(write(tmp_docs, "docs/議事_x3.md", text), tmp_docs)
    assert d["why"] == "目的の文" and d["premises"] == "前提の文" and d["alternatives"] == "- a案"
    assert "別解の文" in d["bekkai"]
    assert d["utagai"] == "全角コロンの反対理由"
    assert d["outcome"] == "採用する"


def test_legacy_utagai_empty_when_nothing_after_colon(tmp_docs):
    d = parse_decision(write(tmp_docs, "docs/議事_x4.md", "# a\n- ウタガイ:\n## 裁定\nx\n"), tmp_docs)
    assert d["utagai"] == ""


def test_section_is_capped_and_collapsed(tmp_docs):
    body = "## 背景\n" + ("あ  い\n" * 500)
    d = parse_decision(write(tmp_docs, "docs/議事_x5.md", "# a\n" + body), tmp_docs)
    assert len(d["why"]) == 600 and "  " not in d["why"]


def test_text_head_is_whitespace_collapsed_and_capped(tmp_docs):
    p = write(tmp_docs, "docs/議事_20261006_t.md", FM.replace("理由A", "理由A" + "字\n" * 1000))
    d = parse_decision(p, tmp_docs)
    assert "\n" not in d["text_head"] and len(d["text_head"]) <= len("テスト決定 a b ") + 600


def test_non_utf8_file_does_not_crash(tmp_docs):
    p = tmp_docs / "docs" / "議事_20260101_bin.md"
    p.write_bytes(b"# \xff\xfe broken\n\x80")
    assert parse_decision(p, tmp_docs)["legacy"] is True


# ---- 追加: check_decision --------------------------------------------------

def test_check_valid_file_passes(tmp_docs):
    assert check_decision(write(tmp_docs, "docs/議事_20261006_ok.md", FM), tmp_docs) == []


def test_check_invalid_status_and_review_by(tmp_docs):
    text = FM.replace("status: adopted", "status: maybe").replace("tags: [a, b]", "review_by: 2026-10-06")
    errs = check_decision(write(tmp_docs, "docs/議事_20261006_s.md", text), tmp_docs)
    assert any("status" in e and "maybe" in e for e in errs)
    assert any("review_by" in e for e in errs)  # date と同日は「より後」ではない


def test_check_requires_why_or_background_heading(tmp_docs):
    errs = check_decision(write(tmp_docs, "docs/議事_20261006_w.md", FM.replace("## なぜ", "## 経緯")), tmp_docs)
    assert any("なぜ" in e for e in errs)
    ok = check_decision(write(tmp_docs, "docs/議事_20261006_w2.md", FM.replace("## なぜ", "## 背景")), tmp_docs)
    assert ok == []


def test_check_rejects_missing_utagai_line(tmp_docs):
    errs = check_decision(
        write(tmp_docs, "docs/議事_20261006_m.md", FM.replace("- **ウタガイ**: コストが高い\n", "")), tmp_docs
    )
    assert any("ウタガイ" in e for e in errs)


def test_check_accepts_utagai_items_on_following_indented_lines(tmp_docs):
    text = FM.replace("- **ウタガイ**: コストが高い\n", "- **ウタガイ(反対理由。必須)**:\n  1. コストが高い\n  2. 時間がない\n")
    assert check_decision(write(tmp_docs, "docs/議事_20261006_i.md", text), tmp_docs) == []


def test_check_accepts_fullwidth_colon_and_errors_name_path(tmp_docs):
    ok = FM.replace("**ウタガイ**: コストが高い", "**ウタガイ**：コストが高い")
    assert check_decision(write(tmp_docs, "docs/議事_20261006_f.md", ok), tmp_docs) == []
    errs = check_decision(write(tmp_docs, "docs/議事_20261006_g.md", FM.replace("title: テスト決定\n", "")), tmp_docs)
    assert errs and all("docs/議事_20261006_g.md" in e for e in errs)


# ---- 追加: CLI ------------------------------------------------------------

def test_cli_list_and_json(tmp_docs):
    write(tmp_docs, "docs/議事_20261006_x.md", FM)
    write(tmp_docs, "docs/議事_nodate.md", "# 日付なし\n")
    r = run(["--list", "--root", str(tmp_docs)])
    lines = r.stdout.strip().splitlines()
    assert r.returncode == 0 and len(lines) == 2
    assert any(l.startswith("2026-10-06  ") and "adopted" in l and "テスト決定" in l for l in lines)
    rj = run(["--list", "--json", "--root", str(tmp_docs)])
    data = json.loads(rj.stdout)
    assert len(data) == 2 and {d["date"] for d in data} == {"2026-10-06", None}
    assert all(isinstance(d["tags"], list) for d in data)


# ---- 追加(レビュー指摘): 値の型・壊れたファイル・コメント --------------------

def test_list_valued_scalars_do_not_crash(tmp_docs):
    text = FM.replace("date: 2026-10-06", "date: [2026-10-06]").replace(
        "title: テスト決定", "title: [a, b]"
    ).replace("tags: [a, b]", "tags: [a, b]\nreview_by: [2027-01-01]\nscope: [x, y]\nstatus: [adopted]")
    text = text.replace("status: adopted\n", "", 1)
    p = write(tmp_docs, "docs/議事_20261006_lst.md", text)
    d = parse_decision(p, tmp_docs, today=TODAY)
    assert d["title"] == "a b" and d["scope"] == "x y"
    assert d["date"] == "2026-10-06"  # ファイル名の日付にフォールバック
    errs = check_decision(p, tmp_docs)  # 例外を出さず、日付の違反として報告する
    assert any("date" in e for e in errs) and any("review_by" in e for e in errs)


def test_list_valued_decision_id_and_status(tmp_docs):
    text = FM.replace("decision_id: D20261006-x", "decision_id: [D1, D2]").replace(
        "status: adopted", "status: [adopted]"
    )
    p = write(tmp_docs, "docs/議事_20261006_ids.md", text)
    d = parse_decision(p, tmp_docs)
    assert d["id"] == "D1 D2" and d["status"] == "adopted"  # 1要素のリストは連結して読む
    two = write(tmp_docs, "docs/議事_20261006_two.md", FM.replace("status: adopted", "status: [adopted, rejected]"))
    assert parse_decision(two, tmp_docs)["status"] == "unknown"
    assert any("status" in e for e in check_decision(two, tmp_docs))
    assert isinstance(check_decision(p, tmp_docs), list)


def test_broken_file_does_not_stop_load(tmp_docs, monkeypatch, capsys):
    write(tmp_docs, "docs/議事_20260101_ok.md", "# ok\n")
    write(tmp_docs, "docs/議事_20260102_boom.md", "# boom\n")
    real = decision_memory.parse_decision

    def flaky(path, root, today=None):
        if "boom" in path.name:
            raise RuntimeError("壊れた")
        return real(path, root, today)

    monkeypatch.setattr(decision_memory, "parse_decision", flaky)
    ds = load_decisions(tmp_docs)
    assert [d["path"] for d in ds] == ["docs/議事_20260101_ok.md"]
    assert "boom" in capsys.readouterr().err
    # 監査ログにも残す(画面を見ていない hook 経由の読み込みでも silent にしない)
    log = (tmp_docs / ".claude/experience/_audit.log").read_text(encoding="utf-8")
    assert "\tdecision\t" in log and "docs/議事_20260102_boom.md" in log and "壊れた" in log


# ---- 追加(レビュー指摘): ウタガイ継続行・見出し ------------------------------

def test_check_rejects_sibling_indented_utagai(tmp_docs):
    text = FM.replace(
        "- **ウタガイ**: コストが高い\n", "  - **ウタガイ**:\n  - **ベッカイ**: b\n"
    )
    errs = check_decision(write(tmp_docs, "docs/議事_20261006_sib.md", text), tmp_docs)
    assert any("ウタガイ" in e for e in errs)


def test_check_accepts_deeper_indented_utagai(tmp_docs):
    text = FM.replace(
        "- **ウタガイ**: コストが高い\n", "  - **ウタガイ**:\n    - コストが高い\n  - **ベッカイ**: b\n"
    )
    assert check_decision(write(tmp_docs, "docs/議事_20261006_deep.md", text), tmp_docs) == []


def test_empty_utagai_bullet_under_heading_mentioning_utagai_fails(tmp_docs):
    text = FM.replace(
        "## 三名体制の議論\n- **ウタガイ**: コストが高い\n",
        "## 三名体制の議論(ウタガイ反対必須)\n- **ウタガイ**:\n- **ベッカイ**: b\n",
    )
    errs = check_decision(write(tmp_docs, "docs/議事_20261006_hd.md", text), tmp_docs)
    assert any("ウタガイ" in e for e in errs)


def test_utagai_heading_with_body_passes(tmp_docs):
    for head in ("### ウタガイ(懐疑)", "### **ウタガイ**"):
        text = FM.replace(
            "- **ウタガイ**: コストが高い\n", f"{head}\n- コストが高い\n"
        )
        assert check_decision(write(tmp_docs, "docs/議事_20261006_hp.md", text), tmp_docs) == []


# ---- 追加(レビュー指摘): frontmatter を読めない時の関門 ----------------------

def test_check_flags_unreadable_frontmatter(tmp_docs):
    nested = "---\ndecision_id: D1-x\nsupersedes:\n  - D0\n---\n## なぜ\nx\n- ウタガイ: y\n"
    unclosed = "---\ndecision_id: D1-x\ndate: 2026-10-06\n## なぜ\nx\n- ウタガイ: y\n"
    for i, text in enumerate((nested, unclosed)):
        p = write(tmp_docs, f"docs/議事_2026100{i}_u.md", text)
        errs = check_decision(p, tmp_docs)
        assert len(errs) == 1 and "frontmatter を読めません" in errs[0]
        assert parse_decision(p, tmp_docs)["legacy"] is True  # 読み取りは従来どおり legacy


def test_check_still_ignores_files_not_starting_with_frontmatter(tmp_docs):
    p = write(tmp_docs, "docs/議事_20260810_hr.md", "# 旧\n---\nkey: x\n---\n")
    assert check_decision(p, tmp_docs) == []


# ---- 追加(レビュー指摘): コメント処理とテンプレートの往復 --------------------

def test_comment_stripping_rules():
    fm, _ = parse_frontmatter(
        "---\n"
        'title: "a # b"\n'
        "scope: Issue #10 対応\n"
        "supersedes:   # コメントだけ\n"
        "decided_by: 小柳 # 末尾コメント\n"
        "decision_id: D1-x #\n"
        "---\n"
    )
    assert fm["title"] == "a # b"
    assert fm["scope"] == "Issue #10 対応"
    assert fm["supersedes"] == ""
    assert fm["decided_by"] == "小柳"
    assert fm["decision_id"] == "D1-x"


def test_template_frontmatter_round_trips():
    template = Path(SCRIPT).parent.parent / "docs" / "wikiskill" / "議事frontmatterテンプレート.md"
    block = template.read_text(encoding="utf-8").split("```yaml\n", 1)[1].split("```", 1)[0]
    fm, _ = parse_frontmatter(block)
    assert fm["supersedes"] == ""
    assert fm["decision_id"] == "D20260101-example"
    assert fm["status"] == "adopted" and fm["review_by"] == "2027-04-04"
    assert fm["tags"] == ["memory", "hooks", "skills"]
    assert fm["scope"] == "hojo-hq/基盤" and fm["decided_by"] == "小柳"


# ---- 追加(レビュー指摘): CLI と ### 見出し ----------------------------------

def test_cli_check_missing_file(tmp_docs):
    r = run(["--check", str(tmp_docs / "docs" / "nope.md")])
    assert r.returncode == 1 and "見つかりません" in r.stdout and "Traceback" not in r.stderr


def test_sections_accept_h2_and_h3_headings(tmp_docs):
    text = (
        "# a\n###なぜ\n理由\n"
        "### 前提\n前提の文\n#### 小見出し\n続き\n### 代替案\n案\n"
        "### 結論(部門長の裁定)\n採用\n## 見直し\nx\n"
    )
    d = parse_decision(write(tmp_docs, "docs/議事_x6.md", text), tmp_docs)
    assert d["why"] == "理由"
    assert d["premises"] == "前提の文 #### 小見出し 続き"
    assert d["alternatives"] == "案"
    assert d["outcome"] == "採用"


def test_check_why_heading_accepts_h3_and_no_space(tmp_docs):
    for head in ("### なぜ", "##なぜ", "### 背景"):
        p = write(tmp_docs, "docs/議事_20261006_h3.md", FM.replace("## なぜ", head))
        assert check_decision(p, tmp_docs) == []
    p = write(tmp_docs, "docs/議事_20261006_h4.md", FM.replace("## なぜ", "#### なぜ"))
    assert any("なぜ" in e for e in check_decision(p, tmp_docs))


# ---- WikiSkill Phase 2 Task 6: ベッカイ抽出(g)と任意キー visibility ---------------

def _parse_text(root, text):
    return parse_decision(write(root, "docs/議事/議事_20261007_t6.md", text), root)


def _check_text(root, text):
    return check_decision(write(root, "docs/議事/議事_20261007_t6.md", text), root)


def test_bekkai_from_heading_section(tmp_docs):
    d = _parse_text(tmp_docs, "## ベッカイ\n前提を疑う案\n## 裁定\n採用\n")
    assert d["bekkai"] == "前提を疑う案"


def test_bekkai_from_bullet_line_and_continuation(tmp_docs):
    d = _parse_text(tmp_docs, "- **ベッカイ**: 別案\n  - 補足A\n- **裁定**: x\n")
    assert "別案" in d["bekkai"] and "補足A" in d["bekkai"] and "裁定" not in d["bekkai"]


def test_bekkai_ignores_incidental_mentions(tmp_docs):
    d = _parse_text(tmp_docs, "本文でベッカイ案に触れた。\n## 裁定\n採用\n")
    assert d["bekkai"] == ""


def test_bekkai_heading_wins_over_bullet_and_never_takes_other_rows(tmp_docs):
    # 見出しがあれば箇条書きは見ない。ウタガイ・裁定の行や、ベッカイに触れただけの行は混ざらない
    text = ("- **ウタガイ**: 反対理由(ベッカイ案も検討した)\n- ベッカイ: 箇条書きの別案\n"
            "### ベッカイ(別解)\n見出しの別案\n- **裁定**: 採用\n### 裁定\n採用\n")
    d = _parse_text(tmp_docs, text)
    assert d["bekkai"] == "見出しの別案 - **裁定**: 採用"  # 同レベルの次の見出し(### 裁定)まで = 節の本文
    assert "ウタガイ" not in d["bekkai"] and "反対理由" not in d["bekkai"] and "箇条書き" not in d["bekkai"]


def test_bekkai_bullet_stops_at_sibling_and_is_capped(tmp_docs):
    text = "- ベッカイ: " + "あ" * 700 + "\n- **ウタガイ**: 反対\n- 裁定: x\n"
    d = _parse_text(tmp_docs, text)
    assert d["bekkai"].startswith("あ")
    assert len(d["bekkai"]) <= decision_memory.SECTION_MAX + 1 and "反対" not in d["bekkai"]


def test_visibility_key_parsed(tmp_docs):
    d = _parse_text(tmp_docs, FM.replace("status: adopted", "status: adopted\nvisibility: private"))
    assert d["visibility"] == "private"
    assert _parse_text(tmp_docs, FM)["visibility"] == ""


def test_check_rejects_bad_visibility(tmp_docs):
    errs = _check_text(tmp_docs, FM.replace("status: adopted", "status: adopted\nvisibility: secret"))
    assert any("visibility" in e for e in errs)
    for ok in ("public", "private"):
        assert _check_text(tmp_docs, FM.replace("status: adopted", f"status: adopted\nvisibility: {ok}")) == []
