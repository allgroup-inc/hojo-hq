"""WikiSkill Phase 1 Task 4: memory_bootstrap.py の検査。

新しいセッションに「今の作業に関係する」Decision・未解決・失敗・再発防止・Skill・Experience
だけを、信頼階層順・出典ラベル付き・文字数上限内で渡すことを固定する。
root の外は読まない / private の Experience は出さない / 段2 はセッションに1回だけ。
"""
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import memory_bootstrap  # noqa: E402
from decision_memory import load_decisions  # noqa: E402
from memory_bootstrap import bigrams, build_query, collect_sources, retrieve, score  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
BRANCH = "claude/lighthouse-css"
DECISION = "docs/議事_20260810_北極星ボトルネック裁定.md"
FM_DECISION = "docs/議事_20261001_集計キャッシュ.md"
FM_DECISION_MD = """---
decision_id: D-20261001-01
date: 2026-10-01
title: 集計キャッシュの置き場所
status: adopted
review_by: 2027-04-01
tags: [キャッシュ, 集計]
---
# 議事: 集計キャッシュの置き場所

## なぜ
集計の再計算に毎回3分かかり、週次レポの生成が締切に間に合わないため。

## 裁定
集計キャッシュは data/cache に置き、生成のたびに作り直す。

## 三名体制
- スイシン: 置く
- ウタガイ: キャッシュが古いまま公開される恐れ
- ベッカイ: 再計算そのものを速くする別解もある
"""
COPY_SCRIPTS = ("wikiskill_common.py", "experience_log.py", "decision_memory.py", "memory_bootstrap.py")

QUEUE = """# 決裁キュー(テスト用)

3. **Bing Webmaster Tools登録**(GSCからインポート・10分)
5. ~~独自ドメイン導入の採否~~ → **✅決裁(2026-08-28 小柳さん: moradou.jp採用・年額3,000円前後承認)**
"""

CLAUDE_MD = """# CLAUDE.md(テスト用)

## 再発防止メモ(同じミスが2度起きたら1行足す)
- **議事は `docs/議事_YYYYMMDD_<件名>.md` に置く**。他の文書の一節に埋め込まない
- **レイアウト系CSS(word-break等)は見出し限定**。広げるときは Lighthouse 実測とセット

## 次の節
- 関係のない箇条書き(再発防止メモではない)
"""

SKILL_MD = """---
name: writing-plans-hojo
description: "ミカタの実装計画と構成設計を、決める人の判断から逆算して作る。"
---

# 本文(ここは読まない)
"""


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _failure_ledger() -> str:
    real = (REPO_ROOT / "docs/失敗台帳.md").read_text(encoding="utf-8").splitlines()
    header = next(l for l in real if l.startswith("| ID |"))
    sep = real[real.index(header) + 1]
    row = next(l for l in real if l.startswith("| FK-002 "))
    return "# 失敗台帳(テスト用)\n\n## 台帳\n\n" + "\n".join([header, sep, row]) + "\n"


@pytest.fixture
def kb(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    git(root, "init", "-q", "-b", BRANCH)
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "remote", "add", "origin", PUBLIC_URL)
    (root / "docs").mkdir()
    shutil.copy(REPO_ROOT / DECISION, root / DECISION)
    (root / "docs/失敗台帳.md").write_text(_failure_ledger(), encoding="utf-8")
    (root / "docs/決裁キュー.md").write_text(QUEUE, encoding="utf-8")
    (root / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    (root / ".claude/skills/writing-plans-hojo").mkdir(parents=True)
    (root / ".claude/skills/writing-plans-hojo/SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (root / "scripts").mkdir()
    for name in COPY_SCRIPTS:
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    (root / ".claude/hooks").mkdir(parents=True)
    shutil.copy(REPO_ROOT / ".claude/hooks/wikiskill-hook.sh", root / ".claude/hooks/wikiskill-hook.sh")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fix: word-break を見出し限定に")
    return root


def run_hook(kb, event, payload, env=None):
    e = {**os.environ, "CLAUDE_PROJECT_DIR": str(kb)}
    e.pop("HOJO_MEMORY_OFF", None)
    e.update(env or {})
    return subprocess.run(
        ["bash", ".claude/hooks/wikiskill-hook.sh", event],
        input=json.dumps(payload, ensure_ascii=False), cwd=kb, env=e, capture_output=True, text=True,
    )


def run_bootstrap(kb, *args, payload=None, env=None):
    e = {**os.environ, "CLAUDE_PROJECT_DIR": str(kb)}
    e.pop("HOJO_MEMORY_OFF", None)
    e.update(env or {})
    return subprocess.run(
        [sys.executable, str(kb / "scripts/memory_bootstrap.py"), *args],
        input=json.dumps(payload or {}, ensure_ascii=False), cwd=kb, env=e, capture_output=True, text=True,
    )


def write_session_end(kb, sid, ts, branch=BRANCH, visibility="public", skills=("writing-plans",), commits=1,
                      subject="c"):
    month = ts[:7]
    d = kb / ".claude/experience" / month
    d.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": ts, "session_id": sid, "event": "session_end", "repo": "allgroup-inc/hojo-hq",
        "visibility": visibility, "branch": branch,
        "commits": [{"sha": f"abc{i}", "subject": f"{subject}{i}"} for i in range(commits)],
        "tools": {"Bash": 1}, "skills": list(skills), "duration_s": 10,
    }
    with open(d / f"session-{sid}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def context_of(stdout: str) -> str:
    return json.loads(stdout).get("hookSpecificOutput", {}).get("additionalContext", "")


# ---------------------------------------------------------------- brief の17本

def test_build_query_from_branch_and_commits(kb):
    t = build_query(kb)
    assert "lighthouse" in t and any("word-break" in x for x in t) and "claude" not in t


def test_bigrams_drop_particle_only():
    assert "のは" not in bigrams("のは") and "北極" in bigrams("北極星")


def test_decision_retrieved_with_why_and_utagai(kb):
    out = retrieve(kb, ["北極星", "ボトルネック", "SEO"])
    decision = next(d for d in load_decisions(kb) if d["path"] == DECISION)
    assert "[D] 2026-08-10" in out and "裁定:" in out and "ウタガイ:" in out
    # なぜ: は本物の「なぜ」節があるときだけ(ベッカイ等を読み替えない)
    assert ("なぜ:" in out) == bool(decision["why"])
    assert "ベッカイ: 律速段階は流入" in out


def test_frontmatter_decision_shows_real_why(kb):
    (kb / FM_DECISION).write_text(FM_DECISION_MD, encoding="utf-8")
    out = retrieve(kb, ["集計キャッシュ"])
    assert "[D] 2026-10-01 集計キャッシュの置き場所" in out
    assert "なぜ: 集計の再計算に毎回3分かかり" in out
    assert "ウタガイ: キャッシュが古いまま公開される恐れ" in out


def test_expired_decision_is_labeled_not_hidden(kb):
    out = retrieve(kb, ["北極星"])
    assert "期限切れ・再議論対象" in out


def test_failure_ledger_row_retrieved(kb):
    out = retrieve(kb, ["マージ", "競合"])
    assert "[FK-002]" in out and "対策:" in out


def test_prevention_memo_retrieved(kb):
    out = retrieve(kb, ["議事", "docs"])
    assert "[再発防止]" in out


def test_skill_retrieved_by_description(kb):
    out = retrieve(kb, ["実装計画"])
    assert "writing-plans-hojo" in out


def test_queue_only_open_items(kb):
    out = retrieve(kb, ["Bing"])
    assert "Bing Webmaster" in out and "moradou.jp採用" not in out


def test_empty_kind_says_none(kb):
    out = retrieve(kb, ["zzzz"])
    assert out.count("該当なし") >= 4


def test_budget_respected(kb):
    assert len(retrieve(kb, ["北極星", "マージ", "議事", "実装計画"], budget_chars=1500)) <= 1500


def test_experience_private_rows_not_shown(kb):
    write_session_end(kb, "private-session", "2026-10-05T01:00:00Z", visibility="private")
    out = retrieve(kb, [])
    assert "private-session" not in out
    assert "private" in (kb / ".claude/experience/_audit.log").read_text(encoding="utf-8")


def test_prompt_stage_runs_once_per_session(kb):
    o1 = run_hook(kb, "UserPromptSubmit", {"session_id": "B", "prompt": "失敗台帳のマージ競合を直したい"})
    assert o1.returncode == 0 and "[FK-002]" in o1.stdout
    o2 = run_hook(kb, "UserPromptSubmit", {"session_id": "B", "prompt": "次は別の話"})
    assert o2.returncode == 0 and o2.stdout.strip() == "{}"


def test_stage2_does_not_repeat_stage1_items(kb):
    # 段1(ブランチ・commit)で北極星の議事が出る状態を作る
    (kb / "notes.txt").write_text("x", encoding="utf-8")
    git(kb, "add", "notes.txt")
    git(kb, "commit", "-q", "-m", "docs: 北極星ボトルネックの裁定を反映")
    s1 = run_hook(kb, "SessionStart", {"session_id": "C", "source": "startup"})
    assert DECISION in context_of(s1.stdout)
    s2 = run_hook(kb, "UserPromptSubmit", {"session_id": "C", "prompt": "北極星のボトルネックとマージ競合の話"})
    assert s2.returncode == 0
    ctx2 = context_of(s2.stdout)
    assert DECISION not in ctx2  # 段1で出した [D] は再掲しない
    assert ctx2.startswith("# 🧠 Memory Bootstrap(段2: 最初の指示から)") and "[FK-002]" in ctx2


def test_session_start_hook_merges_logger_and_bootstrap(kb):
    r = run_hook(kb, "SessionStart", {"session_id": "B", "source": "startup"})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["additionalContext"].startswith("# 🧠 Memory Bootstrap")
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert list((kb / ".claude/experience").glob("*/session-B.jsonl"))


def test_bootstrap_never_reads_outside_root(kb):
    sib = kb.parent / "glow-docs-private"
    (sib / "docs").mkdir(parents=True)
    (sib / "docs/議事_20261001_極秘決定.md").write_text("# 議事: 極秘決定\n極秘キーワード\n", encoding="utf-8")
    assert "極秘" not in retrieve(kb, ["極秘", "決定"])


def test_decision_loader_ignores_experience_dir(kb):
    (kb / ".claude/experience/2026-10").mkdir(parents=True)
    (kb / ".claude/experience/2026-10/議事_20261001_偽.md").write_text("# 偽\n", encoding="utf-8")
    assert all(".claude/experience" not in d["path"] for d in load_decisions(kb))


@pytest.mark.skipif(os.environ.get("WIKISKILL_SKIP_TIMING") == "1", reason="timing is environment-dependent; measured locally")
def test_bootstrap_runtime_under_500ms_on_real_repo():
    t = time.perf_counter()
    subprocess.run([sys.executable, str(SCRIPTS / "memory_bootstrap.py"), "query", "スキル改善"],
                   cwd=REPO_ROOT, check=True, stdout=subprocess.DEVNULL)
    elapsed = time.perf_counter() - t
    assert elapsed < 0.5, f"query took {elapsed:.3f}s"


# ---------------------------------------------------------------- 制御側の決定事項

def test_output_order_and_labels(kb):
    write_session_end(kb, "pub1", "2026-10-05T01:00:00Z")
    out = retrieve(kb, ["北極星", "ボトルネック", "マージ", "競合", "議事", "docs", "実装計画", "Bing Webmaster Tools"])
    heads = ["## 関連する決定 [D]", "## 未解決", "## 過去の失敗 [FK]", "## 再発防止メモ [再発防止]",
             "## 現在有効な関連Skill [Skill]", "## 直近のExperience [Exp]"]
    pos = [out.index(h) for h in heads]
    assert pos == sorted(pos)
    for label in ("[D]", "[未解決]", "[FK-002]", "[再発防止]", "[Skill]", "[Exp]"):
        assert label in out
    assert f"→ {DECISION}" in out


def test_experience_shows_three_newest_same_branch_public(kb):
    for i, day in enumerate(["01", "02", "03", "04"]):
        write_session_end(kb, f"s{i}", f"2026-10-{day}T01:00:00Z", commits=i)
    write_session_end(kb, "other", "2026-10-05T01:00:00Z", branch="claude/other")
    out = retrieve(kb, [])
    assert "session-s3: commits 3 / skills: writing-plans" in out
    assert "session-s1" in out and "session-s0" not in out and "session-other" not in out


def test_broken_source_is_audited_and_others_still_shown(kb):
    (kb / "docs/失敗台帳.md").unlink()
    (kb / "docs/失敗台帳.md").mkdir()  # 読めない(ディレクトリ)
    out = retrieve(kb, ["北極星", "マージ", "競合"])
    assert "[D] 2026-08-10" in out
    fk = out.split("## 過去の失敗 [FK]")[1].split("\n## ")[0]
    assert "該当なし" in fk
    assert "failure:" in (kb / ".claude/experience/_audit.log").read_text(encoding="utf-8")


def test_collect_sources_kinds(kb):
    kinds = {s["kind"] for s in collect_sources(kb)}
    assert {"decision", "queue", "failure", "prevention", "skill"} <= kinds
    assert all(s["kind"] != "queue" or "moradou.jp採用" not in s["body"] for s in collect_sources(kb))


def test_score_counts_matched_terms():
    assert score(["実装計画"], "実装計画を作る") == 1
    assert score(["実装計画", "lighthouse"], "Lighthouse の実装計画") == 2
    assert score(["lighthouse"], "Lighthouse の実測", title="hojo-lighthouse-triage") == 2  # 名前で一致 +1
    assert score(["zzzz"], "北極星") == 0
    assert score(["AI", "LP"], "AIでLPを作る") == 2  # 2文字の英字語も照合する


def test_hook_honors_stop_switch_but_query_does_not(kb):
    (kb / ".claude/memory.off").touch()
    r = run_bootstrap(kb, "hook", "UserPromptSubmit", payload={"session_id": "D", "prompt": "マージ競合"})
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert not (kb / ".claude/experience/_local/D.bootstrapped").exists()
    q = run_bootstrap(kb, "query", "マージ 競合")
    assert q.returncode == 0 and "[FK-002]" in q.stdout


def test_stage2_marker_created_even_when_nothing_new(kb):
    r = run_bootstrap(kb, "hook", "UserPromptSubmit", payload={"session_id": "E", "prompt": "zzzz"})
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert (kb / ".claude/experience/_local/E.bootstrapped").exists()


def test_hook_unexpected_error_becomes_system_message(kb, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(kb))
    monkeypatch.delenv("HOJO_MEMORY_OFF", raising=False)

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(memory_bootstrap, "build_query", boom)
    monkeypatch.setattr(memory_bootstrap, "read_hook_input", lambda: {"session_id": "F"})
    assert memory_bootstrap.main(["memory_bootstrap.py", "hook", "SessionStart"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["systemMessage"].startswith("⚠ Memory Bootstrap 失敗:")


def test_session_start_reports_bootstrap_failure_and_keeps_logger(kb):
    (kb / "scripts/memory_bootstrap.py").write_text("raise SystemExit(4)", encoding="utf-8")
    r = run_hook(kb, "SessionStart", {"session_id": "G", "source": "startup"})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "exit=4" in out["systemMessage"] and "hookSpecificOutput" not in out
    assert list((kb / ".claude/experience").glob("*/session-G.jsonl"))


def test_session_start_merges_both_warnings(kb):
    (kb / "scripts/experience_log.py").write_text("raise SystemExit(3)", encoding="utf-8")
    r = run_hook(kb, "SessionStart", {"session_id": "H", "source": "startup"})
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "exit=3" in out["systemMessage"]
    assert out["hookSpecificOutput"]["additionalContext"].startswith("# 🧠 Memory Bootstrap")


def test_queue_steps_under_completed_item_are_hidden(kb):
    (kb / "docs/決裁キュー.md").write_text(
        QUEUE + "   1. **ドメイン取得の手順**(完了済み項目の下の手順)\n"
        "6. **早期警報閾値の採否**\n   1. **閾値の手順**(未完了項目の下の手順)\n", encoding="utf-8")
    bodies = [s["body"] for s in collect_sources(kb) if s["kind"] == "queue"]
    assert any("Bing" in b for b in bodies) and any("閾値の手順" in b for b in bodies)
    assert not any("ドメイン取得" in b for b in bodies)


def test_japanese_term_needs_most_of_its_bigrams():
    # bigram 2個以下の語は全部、3個以上は6割以上(最低2個)
    assert score(["北極星"], "北極星4本の現在地") == 1
    assert score(["北極星"], "北極の話") == 0
    # パフォーマンス(6個→4個必要)は フォーマット の3片(フォ・ォー・ーマ)では一致しない
    assert score(["パフォーマンス"], "フォーマットを直す") == 0
    assert score(["パフォーマンス"], "パフォーマンスの改善") == 1


def test_english_common_words_and_numbers_do_not_match():
    assert score(["the 2026 use"], "Use when the user wants ... 2026") == 0


def test_stage2_skipped_without_session_id(kb):
    e = {"CLAUDE_SESSION_ID": ""}
    r = run_bootstrap(kb, "hook", "UserPromptSubmit", payload={"prompt": "マージ競合"}, env=e)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "session_id" in out["systemMessage"] and "hookSpecificOutput" not in out
    assert "session_id missing" in (kb / ".claude/experience/_audit.log").read_text(encoding="utf-8")


# ---------------------------------------------------------------- レビュー指摘の固定(2026-10-06)

def _init_git(root, branch=BRANCH, message="init"):
    git(root, "init", "-q", "-b", branch)
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "remote", "add", "origin", PUBLIC_URL)
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", message)


@pytest.fixture
def realish(tmp_path):
    """本物の CLAUDE.md・hojo-lighthouse-triage・FK-006 行で、実際の検索語の結果を固定する。"""
    root = tmp_path / "realish"
    (root / "docs").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "CLAUDE.md", root / "CLAUDE.md")
    real = (REPO_ROOT / "docs/失敗台帳.md").read_text(encoding="utf-8").splitlines()
    header = next(l for l in real if l.startswith("| ID |"))
    rows = [header, real[real.index(header) + 1], next(l for l in real if l.startswith("| FK-006 "))]
    (root / "docs/失敗台帳.md").write_text("# 失敗台帳\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    (root / "docs/決裁キュー.md").write_text("# 決裁キュー\n", encoding="utf-8")
    skill = root / ".claude/skills/hojo-lighthouse-triage"
    skill.mkdir(parents=True)
    shutil.copy(REPO_ROOT / ".claude/skills/hojo-lighthouse-triage/SKILL.md", skill / "SKILL.md")
    _init_git(root)
    return root


def test_real_lighthouse_query_finds_triage_skill_not_fk006(realish):
    out = retrieve(realish, ["Lighthouse", "パフォーマンス", "CSS", "見出し"])
    assert "[Skill] hojo-lighthouse-triage" in out
    assert "[FK-006]" not in out


def test_real_step6_query_shows_update_skills_prevention_line(realish):
    out = retrieve(realish, ["スキル改善", "13リポ", "配布"])
    assert "[再発防止] `.claude/commands/`" in out and "`scripts/update-skills.sh` は現状スキルのみ同期" in out


def test_stage2_excludes_stage1_ids_before_ranking(kb):
    for i in range(1, 7):  # 段1の検索語(lighthouse・css)に当たる Skill が6件
        d = kb / f".claude/skills/lighthouse-check-{i}"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: lighthouse-check-{i}\ndescription: Lighthouse と CSS の点検手順 {i}\n---\n",
                                    encoding="utf-8")
    d = kb / ".claude/skills/domain-guide"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: domain-guide\ndescription: ドメイン移行の手順を案内する\n---\n", encoding="utf-8")
    s1 = context_of(run_bootstrap(kb, "hook", "SessionStart", payload={"session_id": "J"}).stdout)
    assert s1.count("[Skill] lighthouse-check-") == 5  # 1区分5件まで(6件目は段1で出ていない)
    s2 = context_of(run_bootstrap(kb, "hook", "UserPromptSubmit",
                                  payload={"session_id": "J", "prompt": "ドメイン移行"}).stdout)
    assert "[Skill] domain-guide" in s2  # 段1の5件に押し出されない
    shown1 = {l for l in s1.splitlines() if l.startswith("- [Skill]")}
    assert not any(l in s2 for l in shown1)
    assert "lighthouse-check-6" in s2  # 段1で表示されなかった6件目は新規として出る


def _many_sessions(kb, month, n, prefix, branch=BRANCH):
    for i in range(n):
        write_session_end(kb, f"{prefix}{i:03d}", f"{month}-01T00:{i % 60:02d}:00Z", branch=branch)


def _spy_open(monkeypatch, opened):
    """builtins.open と io.open(Path.read_text 等が使う)の両方で開いたパスを記録する。"""
    import builtins
    import io
    real_open = builtins.open

    def spy(path, *a, **k):
        opened.append(str(path))
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)


def test_experience_scan_stops_after_three_and_skips_older_months(kb, monkeypatch):
    _many_sessions(kb, "2026-09", 60, "old")
    _many_sessions(kb, "2026-10", 2, "other", branch="claude/other")
    for i, ts in enumerate(["2026-10-02T01:00:00Z", "2026-10-03T01:00:00Z", "2026-10-04T01:00:00Z"]):
        write_session_end(kb, f"new{i}", ts)
    opened = []
    _spy_open(monkeypatch, opened)
    srcs = memory_bootstrap._experience(kb)
    monkeypatch.undo()
    assert [s["title"] for s in srcs] == ["session-new2", "session-new1", "session-new0"]
    assert not any("/2026-09/" in p for p in opened)


def test_experience_scan_caps_files(kb, monkeypatch):
    _many_sessions(kb, "2026-10", 60, "other", branch="claude/other")
    opened = []
    _spy_open(monkeypatch, opened)
    srcs = memory_bootstrap._experience(kb)
    monkeypatch.undo()
    assert srcs == []
    assert len([p for p in opened if "/session-" in p]) == 50


def test_experience_reads_only_file_tail(kb):
    d = kb / ".claude/experience/2026-10"
    d.mkdir(parents=True)
    # 先頭に壊れた session_end 行 + 約40KBの詰め物。末尾だけ読むなら壊れた行は見えない
    head = '{"event": "session_end", broken\n'
    filler = "\n".join(json.dumps({"event": "tool", "tool": "Bash", "pad": "x" * 200}) for _ in range(200))
    (d / "session-big.jsonl").write_text(head + filler + "\n", encoding="utf-8")
    write_session_end(kb, "big", "2026-10-02T00:00:00Z")
    assert [s["title"] for s in memory_bootstrap._experience(kb)] == ["session-big"]
    audit_log = kb / ".claude/experience/_audit.log"
    assert not audit_log.exists() or "malformed" not in audit_log.read_text(encoding="utf-8")


def test_experience_long_session_end_line_is_read(kb):
    # commit 50件の session_end は 4KB を超える → 読み直して拾う
    write_session_end(kb, "long", "2026-10-02T00:00:00Z", commits=50, subject="件" * 200)
    f = next((kb / ".claude/experience").glob("*/session-long.jsonl"))
    assert f.stat().st_size > memory_bootstrap.TAIL_BYTES
    srcs = memory_bootstrap._experience(kb)
    assert [s["title"] for s in srcs] == ["session-long"] and "commits 50" in srcs[0]["line"]


def test_experience_malformed_rows_audited_once(kb):
    d = kb / ".claude/experience/2026-10"
    d.mkdir(parents=True)
    for i in range(3):
        (d / f"session-bad{i}.jsonl").write_text('{"event": "session_end", broken\n', encoding="utf-8")
    memory_bootstrap._experience(kb)
    lines = [l for l in (kb / ".claude/experience/_audit.log").read_text(encoding="utf-8").splitlines()
             if "malformed" in l]
    assert len(lines) == 1 and "skipped 3 malformed" in lines[0]


def test_non_repo_root_inside_another_repo_reads_no_git(kb):
    sub = kb / "notarepo"
    sub.mkdir()
    assert build_query(sub) == []  # 外側(kb)のブランチ・commit を読まない
    assert "git: root is not the top" in (sub / ".claude/experience/_audit.log").read_text(encoding="utf-8")


def test_decision_line_capped_and_deduped(kb):
    long = "とても長い裁定の本文。" * 60
    (kb / "docs/議事_20261002_長文.md").write_text(
        "---\ndecision_id: D-20261002-01\ndate: 2026-10-02\ntitle: 長文の議事\nstatus: adopted\n"
        "review_by: 2026-10-03\n---\n# 議事: 長文の議事\n\n## なぜ\n" + long + "\n\n## 裁定\n" + long +
        "\n\n- ウタガイ: 長すぎる\n", encoding="utf-8")
    out = retrieve(kb, ["長文の議事"])
    line = next(l for l in out.splitlines() if "長文の議事" in l)
    assert len(line) <= 600
    assert "裁定:" in line and "なぜ:" not in line  # 裁定と同じ本文の なぜ は出さない
    assert "期限切れ・再議論対象" in line  # 長さを削っても見直し欄(期限切れ表示)は残す
    assert line.endswith("→ docs/議事_20261002_長文.md")


def test_merge_failure_reports_merge_exit_code(kb, tmp_path_factory):
    bindir = tmp_path_factory.mktemp("bin")
    for tool in ("cat", "date", "mkdir", "tr", "git"):
        (bindir / tool).symlink_to(shutil.which(tool))
    r = subprocess.run([shutil.which("bash"), ".claude/hooks/wikiskill-hook.sh", "SessionStart"],
                       input=json.dumps({"session_id": "K"}), cwd=kb, capture_output=True, text=True,
                       env={"PATH": str(bindir), "CLAUDE_PROJECT_DIR": str(kb)})
    assert r.returncode == 0
    assert "SessionStart/merge exit=127" in json.loads(r.stdout)["systemMessage"]


# ---------------------------------------------------------------- hook 経路の実時間(本物の docs・Skill・scripts の写し)

@pytest.fixture(scope="module")
def realcopy(tmp_path_factory):
    root = tmp_path_factory.mktemp("realcopy")
    shutil.copytree(REPO_ROOT / "docs", root / "docs")
    shutil.copy(REPO_ROOT / "CLAUDE.md", root / "CLAUDE.md")
    for p in (REPO_ROOT / ".claude/skills").glob("*/SKILL.md"):
        (root / ".claude/skills" / p.parent.name).mkdir(parents=True)
        shutil.copy(p, root / ".claude/skills" / p.parent.name / "SKILL.md")
    (root / "scripts").mkdir()
    for p in SCRIPTS.glob("*.py"):
        shutil.copy(p, root / "scripts" / p.name)
    (root / ".claude/hooks").mkdir(parents=True)
    shutil.copy(REPO_ROOT / ".claude/hooks/wikiskill-hook.sh", root / ".claude/hooks/wikiskill-hook.sh")
    assert not (root / ".claude/memory.off").exists()
    _init_git(root, branch="claude/skill-kaizen", message="feat: スキル改善の配布手順を13リポへ広げる")
    return root


def _timed_hook(root, event, payload):
    t = time.perf_counter()
    r = run_hook(root, event, payload)
    return time.perf_counter() - t, r


@pytest.mark.skipif(os.environ.get("WIKISKILL_SKIP_TIMING") == "1", reason="timing is environment-dependent; measured locally")
def test_hook_session_start_under_500ms_on_real_copy(realcopy):
    elapsed, r = _timed_hook(realcopy, "SessionStart", {"session_id": "T1", "source": "startup"})
    assert r.returncode == 0 and context_of(r.stdout).startswith("# 🧠 Memory Bootstrap")
    print(f"SessionStart hook: {elapsed * 1000:.0f} ms")
    assert elapsed < 0.5, f"SessionStart hook took {elapsed:.3f}s"


@pytest.mark.skipif(os.environ.get("WIKISKILL_SKIP_TIMING") == "1", reason="timing is environment-dependent; measured locally")
def test_hook_user_prompt_submit_under_500ms_on_real_copy(realcopy):
    elapsed, r = _timed_hook(realcopy, "UserPromptSubmit",
                             {"session_id": "T2", "prompt": "Lighthouse のパフォーマンスを見出し限定のCSSで直したい"})
    assert r.returncode == 0 and json.loads(r.stdout) is not None
    print(f"UserPromptSubmit hook (first prompt): {elapsed * 1000:.0f} ms")
    assert elapsed < 0.5, f"UserPromptSubmit hook took {elapsed:.3f}s"


# ---------------------------------------------------------------- 最終修正波(Task 7b): slow 監査 / [D] 行 / 検索語

def _audit_text(root):
    p = Path(root) / ".claude/experience/_audit.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _hook_env(kb, monkeypatch, payload):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(kb))
    monkeypatch.delenv("HOJO_MEMORY_OFF", raising=False)
    monkeypatch.setattr(memory_bootstrap, "read_hook_input", lambda: payload)


def test_slow_hook_audits_without_system_message(kb, monkeypatch, capsys):
    _hook_env(kb, monkeypatch, {"session_id": "S1"})
    monkeypatch.setattr(memory_bootstrap, "SLOW_MS", -1)  # どんな実行も「遅い」扱いにする
    assert memory_bootstrap.main(["memory_bootstrap.py", "hook", "SessionStart"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "systemMessage" not in out and out["hookSpecificOutput"]["additionalContext"]
    lines = [l for l in _audit_text(kb).splitlines() if "\tslow " in l]
    assert len(lines) == 1
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\tbootstrap\tslow SessionStart \d+ms", lines[0])


def test_slow_audit_format_with_forced_clock(kb, monkeypatch, capsys):
    _hook_env(kb, monkeypatch, {"session_id": "S1"})
    ticks = itertools.count()

    def fake_clock():  # 呼び出し回数に依らない: 最初だけ 0、以降は 0.612 秒から単調増加(1回ごとに +1µs)
        n = next(ticks)
        return 0.0 if n == 0 else 0.612 + n * 1e-6

    monkeypatch.setattr(time, "perf_counter", fake_clock)
    memory_bootstrap.main(["memory_bootstrap.py", "hook", "SessionStart"])
    capsys.readouterr()
    assert _audit_text(kb).strip().endswith("\tbootstrap\tslow SessionStart 612ms")


def test_slow_audit_for_user_prompt_submit(kb, monkeypatch, capsys):
    _hook_env(kb, monkeypatch, {"session_id": "S2", "prompt": "北極星 ボトルネック の話"})
    monkeypatch.setattr(memory_bootstrap, "SLOW_MS", -1)
    memory_bootstrap.main(["memory_bootstrap.py", "hook", "UserPromptSubmit"])
    assert "systemMessage" not in json.loads(capsys.readouterr().out)
    assert "\tbootstrap\tslow UserPromptSubmit " in _audit_text(kb)


def test_fast_hook_writes_no_slow_line(kb, monkeypatch, capsys):
    _hook_env(kb, monkeypatch, {"session_id": "S1"})
    memory_bootstrap.main(["memory_bootstrap.py", "hook", "SessionStart"])
    capsys.readouterr()
    assert "slow" not in _audit_text(kb)


def test_slow_not_measured_when_stopped(kb, monkeypatch, capsys):
    _hook_env(kb, monkeypatch, {"session_id": "S1"})
    monkeypatch.setattr(memory_bootstrap, "SLOW_MS", -1)
    monkeypatch.setenv("HOJO_MEMORY_OFF", "1")
    memory_bootstrap.main(["memory_bootstrap.py", "hook", "SessionStart"])
    assert json.loads(capsys.readouterr().out) == {}
    assert _audit_text(kb) == ""


def _decision(**kw):
    d = {"outcome": "裁定の本文", "why": "なぜの本文", "premises": "前提の本文", "utagai": "ウタガイの本文",
         "bekkai": "ベッカイの本文", "review_by": "2027-04-01", "review_status": "active",
         "date": "2026-10-01", "path": "docs/議事_20261001_x.md"}
    d.update(kw)
    return d


def test_decision_line_short_decision_unchanged():
    line = memory_bootstrap._decision_line(_decision(), "短い議事")
    assert line == ("- [D] 2026-10-01 短い議事 — 裁定: 裁定の本文 / なぜ: なぜの本文 / 前提: 前提の本文 / "
                    "ウタガイ: ウタガイの本文 / ベッカイ: ベッカイの本文 / 見直し: 2027-04-01 → docs/議事_20261001_x.md")


_ALL = {"裁定", "なぜ", "前提", "ウタガイ", "ベッカイ", "見直し"}


def _long_decision(path_len):
    """各欄が120字を超える議事。path の長さで、どの段階まで縮める/落とすかを決定的に変える。"""
    assert path_len >= 12
    return _decision(outcome="裁" * 200, why="理" * 200, premises="前" * 200, utagai="疑" * 200,
                     bekkai="別" * 200, path="docs/" + "p" * (path_len - 8) + ".md")


def _labels(line):
    return {m for m in re.findall(r"(裁定|なぜ|前提|ウタガイ|ベッカイ|見直し): ", line)}


def _field(line, label):
    return line.split(f"{label}: ", 1)[1].split(" / ", 1)[0]


# 長さの内訳(題「議事」): 先頭22 + 欄(「ラベル: 」込み 裁定/なぜ/前提=124, ウタガイ/ベッカイ=126, 見直し=15) + 区切り" / "×欄数-1
#   + 末尾 " → " 3字 + path。全欄120字だと 679 + path。欄を60字へ縮めると1欄ごとに 60 減る。
#   前提を落とすと 67、なぜを落とすと 67、ベッカイを落とすと 129 減る。

def test_decision_line_stage0_nothing_trimmed_when_it_fits():
    line = memory_bootstrap._decision_line(_long_decision(20), "議事")  # 679 + 20 = 699 <= 700
    assert len(line) == 699
    assert _labels(line) == _ALL
    for label in ("裁定", "なぜ", "前提"):
        assert len(_field(line, label)) == 120 and _field(line, label).endswith("…")


def test_decision_line_stage1_shrinks_premises_why_outcome_to_60():
    d = _long_decision(170)  # 849 → 前提60で789 → なぜ60で729 → 裁定60で669: 3欄とも縮めて初めて収まる
    line = memory_bootstrap._decision_line(d, "議事")
    assert len(line) == 669 and len(line) <= 700
    assert _labels(line) == _ALL  # 欄はまだ1つも落ちない
    for label in ("裁定", "なぜ", "前提"):
        text = _field(line, label)
        assert len(text) == 60 and text.endswith("…"), label
    assert len(_field(line, "ウタガイ")) == 120 and len(_field(line, "ベッカイ")) == 120
    assert line.endswith(" → " + d["path"])


def test_decision_line_stage2_drops_premises_first():
    d = _long_decision(230)  # 縮めても 729 > 700 → 前提を落として 662
    line = memory_bootstrap._decision_line(d, "議事")
    assert len(line) == 662
    assert _labels(line) == _ALL - {"前提"}
    assert len(_field(line, "裁定")) == 60 and len(_field(line, "なぜ")) == 60
    assert line.endswith(" → " + d["path"])


def test_decision_line_stage3_then_drops_why():
    d = _long_decision(300)  # 前提を落としても 732 → なぜも落として 665
    line = memory_bootstrap._decision_line(d, "議事")
    assert len(line) == 665
    assert _labels(line) == _ALL - {"前提", "なぜ"}
    assert line.endswith(" → " + d["path"])


def test_decision_line_stage4_then_drops_bekkai():
    d = _long_decision(400)  # なぜを落としても 765 → ベッカイも落として 636
    line = memory_bootstrap._decision_line(d, "議事")
    assert len(line) == 636
    assert _labels(line) == {"裁定", "ウタガイ", "見直し"}
    assert len(_field(line, "ウタガイ")) == 120  # ウタガイはまだ削らない
    assert line.endswith(" → " + d["path"])


def test_decision_line_stage5_cuts_utagai_only_as_much_as_needed():
    d = _long_decision(480)  # 欄を落としきっても 716 → ウタガイを16字だけ削って 700
    line = memory_bootstrap._decision_line(d, "議事")
    assert len(line) == 700
    assert _labels(line) == {"裁定", "ウタガイ", "見直し"}
    assert len(_field(line, "ウタガイ")) == 104 and _field(line, "ウタガイ").endswith("…")
    assert len(_field(line, "裁定")) == 60
    assert line.endswith(" → " + d["path"])


def test_decision_line_floor_utagai_is_exactly_80_then_outcome_gives_way():
    d = _long_decision(530)  # ウタガイを床の80字まで削っても 726 → 裁定をさらに26字削って 700
    line = memory_bootstrap._decision_line(d, "議事")
    assert len(line) == 700
    assert _labels(line) == {"裁定", "ウタガイ", "見直し"}
    utagai = _field(line, "ウタガイ")
    assert len(utagai) == 80 and utagai.endswith("…")
    assert len(_field(line, "裁定")) == 34
    assert "見直し: 2027-04-01" in line and line.endswith(" → " + d["path"])


def test_decision_line_never_drops_utagai_review_or_path_even_when_oversized():
    d = _long_decision(900)  # どうやっても 700 に収まらない病的な path
    line = memory_bootstrap._decision_line(d, "議事")
    assert {"ウタガイ", "見直し"} <= _labels(line)
    assert len(_field(line, "ウタガイ")) == 80
    assert line.endswith(" → " + d["path"])


def test_decision_line_expired_label_survives_trimming():
    d = _long_decision(400)
    d["review_status"] = "expired"
    line = memory_bootstrap._decision_line(d, "議事")
    assert "見直し: 2027-04-01 **(期限切れ・再議論対象)**" in line and len(line) <= 700


# --- 段1の検索語(branch-local commit)

def _commit(root, subject):
    git(root, "commit", "-q", "--allow-empty", "-m", subject)


def _unit_words(terms):
    return [w for _k, w, _g in memory_bootstrap.query_units(terms)]


def test_build_query_uses_only_branch_local_commits(kb):
    for w in ("olderone", "oldertwo", "olderthree", "olderfour", "olderfive"):
        _commit(kb, f"feat: {w}")
    git(kb, "update-ref", "refs/remotes/origin/main", "HEAD")
    for w in ("localone", "localtwo", "localthree"):
        _commit(kb, f"feat: {w}")
    words = _unit_words(build_query(kb))
    assert {"localone", "localtwo", "localthree"} <= set(words)
    assert not any(w.startswith("older") for w in words)
    assert "lighthouse" in words  # ブランチ名の語は残る
    # commit 件名の語は新しい順
    assert words.index("localthree") < words.index("localtwo") < words.index("localone")


def test_build_query_falls_back_to_last_five_without_local_commits(kb):
    for i, w in enumerate(("fbone", "fbtwo", "fbthree", "fbfour", "fbfive", "fbsix", "fbseven")):
        _commit(kb, f"feat: {w}")
    git(kb, "update-ref", "refs/remotes/origin/main", "HEAD")  # origin/main..HEAD が空
    words = _unit_words(build_query(kb))
    assert {"fbseven", "fbsix", "fbfive", "fbfour", "fbthree"} <= set(words)
    assert "fbtwo" not in words and "fbone" not in words


def test_build_query_falls_back_when_origin_main_unknown(kb):
    for w in ("ghone", "ghtwo", "ghthree", "ghfour", "ghfive", "ghsix"):
        _commit(kb, f"feat: {w}")
    words = _unit_words(build_query(kb))  # kb に origin/main の参照は無い
    assert {"ghsix", "ghfive", "ghfour", "ghthree", "ghtwo"} <= set(words)
    assert "ghone" not in words


def test_build_query_truncates_subject_to_60_chars(kb):
    git(kb, "update-ref", "refs/remotes/origin/main", "HEAD")
    subject = "headword " + "x" * 50 + " " + "tailword " * 15  # 先頭59字が headword + x*50、tailword は60字より後
    assert len(subject) > 190
    _commit(kb, subject)
    words = _unit_words(build_query(kb))
    assert "headword" in words and "x" * 50 in words
    assert "tailword" not in words


def test_build_query_caps_units_at_40_keeping_branch_tokens(kb):
    git(kb, "update-ref", "refs/remotes/origin/main", "HEAD")
    for i in range(10):
        _commit(kb, "feat: " + " ".join(f"w{c}{i}z" for c in "abcdefgh"))  # 1件に8語 × 10件 = 80語
    terms = build_query(kb)
    words = _unit_words(terms)
    assert len(words) == 40
    assert "lighthouse" in words and "css" in words  # ブランチ名の語は先頭なので必ず残る
    assert len(memory_bootstrap.query_units(terms)) == 40
