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
    memory_bootstrap._clear_caches()  # 1プロセス内の memo(Decision・同義語・audit 1回)を前のテストから持ち越さない
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
    out = retrieve(kb, ["北極星", "ボトルネック", "マージ", "競合"])
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
    for i in range(17):  # 区分の25%を超える語は使わない(DF)ので、6件が25%以下になるよう関係のない Skill を足す
        d = kb / f".claude/skills/filler-{i}"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: filler-{i}\ndescription: 関係のない手引き {i}\n---\n", encoding="utf-8")
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


# ---------------------------------------------------------------- 最終修正波(全体レビュー後)

def _fm_decision(kb, name, status="adopted", tags="[キャッシュ, 集計]", title="集計キャッシュの置き場所"):
    md = FM_DECISION_MD.replace("status: adopted", f"status: {status}").replace(
        "tags: [キャッシュ, 集計]", f"tags: {tags}").replace("title: 集計キャッシュの置き場所", f"title: {title}")
    (kb / "docs" / name).write_text(md, encoding="utf-8")


# --- B1: 採用以外の Decision の表示 / superseded・test タグは出さない

def test_deferred_and_rejected_decisions_are_labeled(kb):
    _fm_decision(kb, "議事_20261001_保留.md", status="deferred", title="集計キャッシュ保留案")
    _fm_decision(kb, "議事_20261002_却下.md", status="rejected", title="集計キャッシュ却下案")
    out = retrieve(kb, ["集計キャッシュ"])
    held = next(l for l in out.splitlines() if "集計キャッシュ保留案" in l)
    rejected = next(l for l in out.splitlines() if "集計キャッシュ却下案" in l)
    assert held.startswith("- [D:保留] 2026-10-01 集計キャッシュ保留案")
    assert rejected.startswith("- [D:却下] 2026-10-01 集計キャッシュ却下案")


def test_adopted_and_legacy_decisions_keep_plain_label(kb):
    _fm_decision(kb, "議事_20261001_採用.md")
    out = retrieve(kb, ["集計キャッシュ", "北極星", "ボトルネック"])
    assert "- [D] 2026-10-01 集計キャッシュの置き場所" in out
    assert "- [D] 2026-08-10" in out  # frontmatter の無い過去の議事


def test_superseded_and_test_tagged_decisions_are_skipped(kb):
    _fm_decision(kb, "議事_20261001_置換済み.md", status="superseded", title="集計キャッシュ旧案")
    _fm_decision(kb, "議事_20261002_試験.md", tags="[acceptance, test]", title="集計キャッシュ試験")
    _fm_decision(kb, "議事_20261003_採用.md", title="集計キャッシュ採用案")
    out = retrieve(kb, ["集計キャッシュ"])
    assert "集計キャッシュ採用案" in out
    assert "集計キャッシュ旧案" not in out and "集計キャッシュ試験" not in out


def test_real_acceptance_sample_is_not_a_decision():
    sample = "docs/wikiskill/受け入れ試験_議事サンプル.md"
    assert (REPO_ROOT / sample).exists()
    assert all(d["path"] != sample for d in load_decisions(REPO_ROOT))
    assert not (REPO_ROOT / "docs/議事/議事_20261006_受け入れ試験.md").exists()


# --- B3: 検索語の雑音

def test_build_query_skips_experience_basenames_and_random_units(kb):
    git(kb, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(kb, "checkout", "-q", "-b", "claude/superpowers-per-chat-3mbx56")
    d = kb / ".claude/experience/2026-10"
    d.mkdir(parents=True)
    (d / "session-88fbbce6-5a12-50ce-b8f3-4f86e601e77f.jsonl").write_text("{}\n", encoding="utf-8")
    (kb / "docs/phase1-notes.md").write_text("x", encoding="utf-8")
    git(kb, "add", "-A")
    git(kb, "commit", "-q", "-m", "chore: Experience 追記 7d9825cab")
    words = _unit_words(build_query(kb))
    assert "superpowers" in words and "phase1" in words
    for noise in ("3mbx56", "88fbbce6", "4f86e601e77f", "jsonl", "session", "7d9825cab"):
        assert noise not in words, noise


def test_query_units_drop_hex_and_random_suffix_but_keep_words():
    words = _unit_words(["3mbx56 88fbbce6 1d3cd976d937 phase1 lighthouse decade css 7d9825cab"])
    assert words == ["phase1", "lighthouse", "decade", "css"]


def test_title_bonus_orders_but_does_not_reach_min_score(kb):
    # 2語の検索で、題と本文に1語(キャッシュ)しか当たらない → 以前は 1 + 見出し加点 1 = 2 で通っていた
    _fm_decision(kb, "議事_20261001_採用.md")
    assert score(["キャッシュ", "zzzz"], "集計キャッシュの置き場所 本文", title="集計キャッシュの置き場所") == 2
    assert "集計キャッシュの置き場所" not in retrieve(kb, ["キャッシュ", "zzzz"])
    assert "集計キャッシュの置き場所" in retrieve(kb, ["キャッシュ", "再計算"])


def test_skill_name_match_still_counts_as_one_word(kb):
    # Skill の名前(識別子)に語がそのまま入っていれば、説明の一致と合わせて2語として数える
    d = kb / ".claude/skills/cache-tool"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: cache-tool\ndescription: cache の点検\n---\n", encoding="utf-8")
    assert "[Skill] cache-tool" in retrieve(kb, ["cache", "zzzz"])


def test_common_unit_is_ignored_per_section(kb):
    # Skill 区分の 5/6 に「確認」がある → この区分では「確認」を照合に使わない
    for i in range(4):
        d = kb / f".claude/skills/kakunin-{i}"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: kakunin-{i}\ndescription: 手順{i}の確認をする\n---\n",
                                    encoding="utf-8")
    d = kb / ".claude/skills/merge-check"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: merge-check\ndescription: マージの確認をする\n---\n", encoding="utf-8")
    # 「確認」を数えれば merge-check は 2語(マージ・確認)で通るが、ありふれた語を外すと1語
    out = retrieve(kb, ["確認", "マージ", "競合"])
    assert "[Skill] merge-check" not in out and "[Skill] kakunin-" not in out
    assert "[FK-002]" in out  # 失敗台帳の区分(1件)では「確認」も効く


def test_df_filter_needs_enough_entries(kb):
    # 1区分1件(kb の失敗台帳)では、当たった語が 100% でも「ありふれた語」と見なさない
    assert "[FK-002]" in retrieve(kb, ["マージ", "競合"])


def _stage2_without_stage1_exclusion(kb, monkeypatch, prompt):
    # 段1で表示した項目は段2で除かれる。検索語の組み立てだけを見るため、段1の表示を空にする
    monkeypatch.setattr(memory_bootstrap, "_stage1_render", lambda root, sources, terms: (None, set()))
    return memory_bootstrap._stage2(kb, prompt) or ""


def test_stage2_uses_prompt_and_branch_tokens_only(kb, monkeypatch):
    _commit(kb, "docs: 北極星ボトルネックの裁定")
    out = _stage2_without_stage1_exclusion(kb, monkeypatch, "マージで競合したときの手順を確認したい")
    assert "[FK-002]" in out
    assert DECISION not in out  # commit 件名だけに当たる議事は段2では出さない
    # 検索語の行(Phase 2 Task 3 で書式を変更): 指示から取った語とブランチ名の語を分けて出す。指示の本文は出さない
    assert out.splitlines()[1] == "検索語(指示から): マージ, 競合, 手順, 確認"
    assert out.splitlines()[2] == "検索語(ブランチから): lighthouse, css"


def test_stage2_falls_back_to_stage1_terms_for_short_prompt(kb, monkeypatch):
    _commit(kb, "docs: 北極星ボトルネックの裁定")
    out = _stage2_without_stage1_exclusion(kb, monkeypatch, "はい")  # 指示から語が2つ取れない
    assert DECISION in out
    assert "北極星" in out.splitlines()[2]  # 段1の検索語を使っている(Phase 2 Task 3: 検索語の行は2行目が指示から・3行目がそれ以外)


# --- B3: 本物の文書で固定(受け入れ試験の指示 / Lighthouse / Step 6)

ACCEPTANCE_PROMPT = "マージで競合したときの手順を確認したい"
NOISY_DECISIONS = (
    "docs/議事_20260912_経費精算の着工方針.md",
    "docs/議事_20260828_独自ドメインmoradou.md",
    "docs/議事_20260923_独自ドメイン配信範囲.md",
)


def test_real_acceptance_prompt_returns_merge_failure_without_noise(realcopy):
    out = memory_bootstrap._stage2(realcopy, ACCEPTANCE_PROMPT) or ""
    assert "- [FK-002]" in out
    for path in NOISY_DECISIONS:
        assert path not in out, path
    assert "経費精算" not in out and "moradou" not in out


def test_real_lighthouse_query_keeps_triage_skill_on_full_corpus(realcopy):
    out = retrieve(realcopy, ["Lighthouse", "パフォーマンス", "CSS", "見出し"])
    assert "[Skill] hojo-lighthouse-triage" in out


def test_real_step6_query_keeps_update_skills_line_on_full_corpus(realcopy):
    out = retrieve(realcopy, ["スキル改善", "13リポ", "配布"])
    assert "`scripts/update-skills.sh` は現状スキルのみ同期" in out


# --- B6 / B2: クラウド(detached HEAD)の [Exp] / part ファイル / 並び順

def _write_lines(kb, name, rows, month="2026-10"):
    d = kb / ".claude/experience" / month
    d.mkdir(parents=True, exist_ok=True)
    with open(d / name, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return d / name


def _ev(sid, ts, event, branch=BRANCH, **kw):
    return {"ts": ts, "session_id": sid, "event": event, "repo": "allgroup-inc/hojo-hq",
            "visibility": "public", "branch": branch, **kw}


def test_experience_without_session_end_uses_latest_line(kb):
    _write_lines(kb, "session-A.jsonl", [
        _ev("A", "2026-10-06T20:40:13Z", "session_start"),
        _ev("A", "2026-10-06T20:41:05Z", "note", text="受け入れ試験 A 完了: 締切アラート案内時期の決定を記録した" + "。" * 40),
        _ev("A", "2026-10-06T20:43:17Z", "tool", tool="Bash", program="git"),
    ])
    (line,) = [s["line"] for s in memory_bootstrap._experience(kb)]
    note60 = ("受け入れ試験 A 完了: 締切アラート案内時期の決定を記録した" + "。" * 40)[:60]
    assert line == f"- [Exp] 2026-10-06 session-A: events 3 / note: {note60}"


def test_experience_without_note_omits_note_part(kb):
    _write_lines(kb, "session-B.jsonl", [_ev("B", "2026-10-06T01:00:00Z", "session_start")])
    (line,) = [s["line"] for s in memory_bootstrap._experience(kb)]
    assert line == "- [Exp] 2026-10-06 session-B: events 1"


def test_experience_reads_base_and_parts_as_one_session(kb):
    _write_lines(kb, "session-P.jsonl", [_ev("P", "2026-10-06T01:00:00Z", "session_start"),
                                        _ev("P", "2026-10-06T01:01:00Z", "note", text="古いメモ")])
    _write_lines(kb, "session-P.part1.jsonl", [_ev("P", "2026-10-06T02:00:00Z", "note", text="新しいメモ"),
                                              _ev("P", "2026-10-06T02:01:00Z", "tool", tool="Bash", program="ls")])
    (line,) = [s["line"] for s in memory_bootstrap._experience(kb)]
    assert line == "- [Exp] 2026-10-06 session-P: events 4 / note: 新しいメモ"


def test_experience_session_end_in_part_file_is_used(kb):
    _write_lines(kb, "session-Q.jsonl", [_ev("Q", "2026-10-06T01:00:00Z", "session_start")])
    write_session_end(kb, "Q", "2026-10-06T03:00:00Z")  # 本体に追記されるので、part へ移す
    base = kb / ".claude/experience/2026-10/session-Q.jsonl"
    start, end = base.read_text(encoding="utf-8").splitlines()
    base.write_text(start + "\n", encoding="utf-8")
    (base.parent / "session-Q.part1.jsonl").write_text(end + "\n", encoding="utf-8")
    (line,) = [s["line"] for s in memory_bootstrap._experience(kb)]
    assert line == "- [Exp] 2026-10-06 session-Q: commits 1 / skills: writing-plans"


def test_experience_orders_by_first_line_ts_not_mtime(kb):
    old = _write_lines(kb, "session-old.jsonl", [_ev("old", "2026-10-01T00:00:00Z", "session_start")])
    new = _write_lines(kb, "session-new.jsonl", [_ev("new", "2026-10-05T00:00:00Z", "session_start")])
    os.utime(new, (1_000_000, 1_000_000))   # 新しいセッションのファイルの方が更新時刻は古い
    os.utime(old, (2_000_000, 2_000_000))
    assert [s["title"] for s in memory_bootstrap._experience(kb)] == ["session-new", "session-old"]


def _detach_with_origin_refs(kb, *names):
    for n in names:
        git(kb, "update-ref", f"refs/remotes/origin/{n}", "HEAD")
    git(kb, "checkout", "-q", "--detach", "HEAD")


def test_experience_on_detached_head_uses_the_single_origin_branch(kb):
    _detach_with_origin_refs(kb, BRANCH)
    write_session_end(kb, "mine", "2026-10-05T01:00:00Z")
    write_session_end(kb, "theirs", "2026-10-05T02:00:00Z", branch="claude/other")
    titles = [s["title"] for s in memory_bootstrap._experience(kb)]
    assert titles == ["session-mine"]
    assert "lighthouse" in _unit_words(build_query(kb))  # ブランチ名の語も detached で取れる


def test_experience_on_ambiguous_detached_head_does_not_filter_by_branch(kb):
    _detach_with_origin_refs(kb, BRANCH, "claude/other")
    write_session_end(kb, "mine", "2026-10-05T01:00:00Z")
    write_session_end(kb, "theirs", "2026-10-05T02:00:00Z", branch="claude/other")
    titles = [s["title"] for s in memory_bootstrap._experience(kb)]
    assert titles == ["session-theirs", "session-mine"]


def test_experience_hides_the_current_session(kb):
    write_session_end(kb, "other", "2026-10-05T01:00:00Z")
    _write_lines(kb, "session-me.jsonl", [_ev("me", "2026-10-06T01:00:00Z", "session_start")])
    (kb / ".claude/experience/_local").mkdir(parents=True)
    (kb / ".claude/experience/_local/current_session").write_text("me\n", encoding="utf-8")
    assert [s["title"] for s in memory_bootstrap._experience(kb)] == ["session-other"]


# --- C4: ウタガイは重複判定で隠さない / ベッカイの見出しだけのラベルを重ねない

def test_utagai_is_never_hidden_by_dedupe():
    d = _decision(outcome="ウタガイの指摘どおり、キャッシュが古いまま公開される恐れがあるので毎回作り直す",
                  utagai="キャッシュが古いまま公開される恐れ", bekkai="")
    line = memory_bootstrap._decision_line(d, "議事")
    assert "ウタガイ: キャッシュが古いまま公開される恐れ" in line


def test_bekkai_heading_only_labels_are_stripped():
    for raw, want in (
        ("ベッカイ(別解) ベッカイ(別解) - 理由: 速い", "ベッカイ: - 理由: 速い"),
        ("ベッカイ(別解・前提を疑う) 5. 段階通知にする", "ベッカイ: 5. 段階通知にする"),
        ("ベッカイの案を採る", "ベッカイ: ベッカイの案を採る"),
    ):
        line = memory_bootstrap._decision_line(_decision(bekkai=raw), "議事")
        assert want in line, (raw, line)
        assert "ベッカイ: ベッカイ(" not in line
    # 見出しのラベルしか無いときは欄ごと出さない
    line = memory_bootstrap._decision_line(_decision(bekkai="ベッカイ(別解) ベッカイ(別解)"), "議事")
    assert "ベッカイ:" not in line


# ---------------------------------------------------------------- Phase 2 Task 3: [Wiki] 区分・wiki.off・同義語・Skill名一致・検索語行

import wiki_schema  # noqa: E402
from wiki_schema import load_synonyms  # noqa: E402

PHASE1_REV = "39f9d71c2"  # Phase 2 Task 3 より前の memory_bootstrap.py(回帰比較の基準)
WORDS = ["北極星", "ボトルネック", "マージ", "競合", "議事", "docs", "実装計画", "構成設計", "Bing", "Webmaster"]
APPROVED_TITLE = "マージ競合の解き方"
CANDIDATE_TITLE = "マージ競合の候補ページ"
ARCHIVED_TITLE = "マージ競合の旧版ページ"
APPROVED_ID = "W20261020-merge-conflict"
PAYLOAD = {"session_id": "W1", "source": "startup"}


def _wiki_fm(title, summary, status="approved", visibility="public", wiki_id=APPROVED_ID):
    fm = {
        "candidate_id": "K20261019-merge-conflict-abcd", "title": title, "summary": summary,
        "evidence": [{"source": DECISION, "quote": "マージで競合したら一覧を先に確認する"}],
        "confidence": 0.8, "confidence_basis": "Decision 1件と Experience 1件が一致", "visibility": visibility,
        "repo": "allgroup-inc/hojo-hq", "created_at": "2026-10-19", "proposed_by": "knowledge_extract",
        "contradictions": [], "related_wiki": [], "related_skills": [], "review_status": status,
        "dedup_key": "0" * 40, "extract_run": "run-test",
        "source_experience": ["session-abc@2026-10-18T00:00:00Z"], "source_decision": [DECISION],
        "source_failure": [],
    }
    if status in ("approved", "superseded"):
        fm.update({"wiki_id": wiki_id, "approved_by": "小柳(テスト)", "approved_at": "2026-10-20",
                   "review_by": "2027-04-18", "review": {"スイシン": "a", "ウタガイ": "b", "ベッカイ": "c"}})
    return fm


def _write_wiki(root, rel, title, summary, knowledge="競合ファイルの一覧を先に確認し、1件ずつ解く。", **kw):
    sections = {"## 知識": f"{title}。{knowledge}",
                "## 根拠(Provenance)": "- 議事", "## 反証(ウタガイ)": "- なし", "## 適用範囲と例外": "- 全般",
                "## 関連": "- なし"}
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(wiki_schema.render_wiki(_wiki_fm(title, summary, **kw), sections), encoding="utf-8")
    return p


APPROVED_SUMMARY = "マージで競合したら、競合ファイルの一覧を先に確認してから個別に解く。"


@pytest.fixture
def kbw(kb):
    """kb + 正式 Wiki 1件(approved)+ 候補 1件 + _archive 1件。hook 経路用に wiki_schema.py も写す。"""
    shutil.copy(SCRIPTS / "wiki_schema.py", kb / "scripts" / "wiki_schema.py")
    _write_wiki(kb, f"docs/wiki/{APPROVED_ID}.md", APPROVED_TITLE, APPROVED_SUMMARY)
    _write_wiki(kb, "docs/wiki/_candidates/K20261021-merge-candidate-beef.md", CANDIDATE_TITLE, APPROVED_SUMMARY,
                status="candidate")
    _write_wiki(kb, "docs/wiki/_archive/W20261001-merge-old.md", ARCHIVED_TITLE, APPROVED_SUMMARY,
                status="superseded", wiki_id="W20261001-merge-old")
    git(kb, "add", "-A")
    git(kb, "commit", "-q", "-m", "chore: wiki fixture")
    memory_bootstrap._clear_caches()
    return kb


def add_approved(root, n, filler=0):
    for i in range(n):
        _write_wiki(root, f"docs/wiki/W20261020-merge-{i}.md", f"マージ競合の手順その{i}",
                    f"マージで競合したときの手順その{i}。", wiki_id=f"W20261020-merge-{i}")
    for i in range(filler):
        _write_wiki(root, f"docs/wiki/W20261020-filler-{i}.md", f"関係のない知識その{i}",
                    f"関係のない要約その{i}。", knowledge="別の話題の本文。", wiki_id=f"W20261020-filler-{i}")


def set_summary(root, summary):
    _write_wiki(root, f"docs/wiki/{APPROVED_ID}.md", APPROVED_TITLE, summary)


def write_syn(root, *lines):
    p = Path(root) / "docs/wiki/_synonyms.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# テスト用の同義語表\n" + "\n".join(lines) + "\n", encoding="utf-8")


def section(out, label):
    lines = out.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("## ") and label in l)
    body = []
    for l in lines[start + 1:]:
        if l.startswith("## "):
            break
        body.append(l)
    return "\n".join(body)


def wiki_line(out):
    return next(l for l in out.splitlines() if l.startswith("- [Wiki]"))


def record_opens(monkeypatch):
    """builtins.open / io.open / Path.open / Path.read_text / Path.read_bytes で開いたパスを記録する。"""
    import builtins
    import io
    opened = []
    real_open = builtins.open

    def spy(path, *a, **k):
        opened.append(os.path.abspath(str(path)) if not isinstance(path, int) else str(path))
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    for name in ("open", "read_text", "read_bytes"):
        real = getattr(Path, name)

        def wrap(self, *a, _real=real, **k):
            opened.append(str(Path(self).absolute()))
            return _real(self, *a, **k)

        monkeypatch.setattr(Path, name, wrap)
    return opened


def stage1_with_branch(root, branch):
    git(root, "checkout", "-q", "-b", branch)
    return memory_bootstrap._stage1(root) or ""


def stage2(root, prompt):
    return memory_bootstrap._stage2(root, prompt) or ""


def strip_wiki_section(out):
    keep, skipping = [], False
    for l in out.splitlines(keepends=True):
        if l.startswith("## "):
            skipping = "[Wiki]" in l
            if skipping:
                continue
        if skipping or l.startswith("検索語"):
            continue
        keep.append(l)
    return "".join(keep)


def _phase1_query(root, words, workdir):
    """Phase 1 の memory_bootstrap.py(PHASE1_REV)を root で動かした query の出力。"""
    d = workdir / "phase1-scripts"
    d.mkdir()
    for name in ("memory_bootstrap.py", "wikiskill_common.py", "experience_log.py", "decision_memory.py"):
        src = subprocess.run(["git", "show", f"{PHASE1_REV}:scripts/{name}"], cwd=REPO_ROOT, check=True,
                             capture_output=True, text=True).stdout
        (d / name).write_text(src, encoding="utf-8")
    e = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    e.pop("HOJO_MEMORY_OFF", None)
    r = subprocess.run([sys.executable, str(d / "memory_bootstrap.py"), "query", *words], cwd=root, env=e,
                       check=True, capture_output=True, text=True)
    return r.stdout


def test_wiki_kind_order_between_prevention_and_skill(kbw):
    out = retrieve(kbw, WORDS)
    assert out.index("[再発防止]") < out.index("[Wiki]") < out.index("[Skill]")


def test_wiki_only_approved_shown(kbw):
    _write_wiki(kbw, "docs/wiki/W20261022-merge-private.md", "マージ競合の非公開ページ", APPROVED_SUMMARY,
                visibility="private", wiki_id="W20261022-merge-private")
    out = retrieve(kbw, WORDS)
    assert APPROVED_TITLE in out and CANDIDATE_TITLE not in out and ARCHIVED_TITLE not in out
    assert "マージ競合の非公開ページ" not in out  # リポの公開性(public)と違う visibility は出さない


def test_candidates_dir_never_opened(kbw, monkeypatch):
    opened = record_opens(monkeypatch)
    out = retrieve(kbw, WORDS)
    monkeypatch.undo()
    assert APPROVED_TITLE in out
    assert any(f"/docs/wiki/{APPROVED_ID}.md" in p for p in opened)  # 記録が効いている
    assert not any("/docs/wiki/_candidates/" in p for p in opened)


def test_archive_dir_never_opened(kbw, monkeypatch):
    opened = record_opens(monkeypatch)
    retrieve(kbw, WORDS)
    memory_bootstrap._stage1(kbw)
    memory_bootstrap._stage2(kbw, "マージ競合の手順を確認したい")
    monkeypatch.undo()
    assert opened
    assert not any("/docs/wiki/_archive/" in p for p in opened)
    assert not any("/docs/wiki/_candidates/" in p for p in opened)


def test_wiki_line_shows_provenance_and_approver(kbw):
    out = retrieve(kbw, WORDS)
    assert "根拠: Exp 1・Decision 1・FK 0 / 承認: 小柳(テスト) 2026-10-20 → docs/wiki/" in out
    assert wiki_line(out) == (f"- [Wiki] {APPROVED_TITLE} — {APPROVED_SUMMARY} / 根拠: Exp 1・Decision 1・FK 0 / "
                              f"承認: 小柳(テスト) 2026-10-20 → docs/wiki/{APPROVED_ID}.md")


def test_wiki_summary_truncated_160(kbw):
    set_summary(kbw, "あ" * 200)
    line = wiki_line(retrieve(kbw, WORDS))
    assert "あ" * 160 in line and "あ" * 161 not in line


def test_wiki_off_disables_only_wiki(kbw):
    (kbw / ".claude/wiki.off").touch()
    out = retrieve(kbw, WORDS)
    retrieve(kbw, WORDS)
    assert section(out, "[Wiki]") == "- 該当なし" and "[D]" in out and "[FK-002]" in out
    lines = [l for l in _audit_text(kbw).splitlines() if "wiki: disabled by wiki.off" in l]
    assert len(lines) == 1  # 1プロセスに1回だけ


def test_memory_off_disables_wiki_too(kbw):
    (kbw / ".claude/memory.off").touch()
    r = run_hook(kbw, "SessionStart", PAYLOAD)
    assert r.returncode == 0 and r.stdout.strip() == "{}"


def test_wiki_per_kind_cap_and_budget(kbw):
    add_approved(kbw, 8, filler=30)  # 一致 9件 / 39件 ≒ 23%(ありふれた語の判定 25% に掛からない)
    full = retrieve(kbw, WORDS)
    assert full.count("- [Wiki]") == 5  # 1区分5件まで
    out = retrieve(kbw, WORDS, budget_chars=3000)
    assert out.count("- [Wiki]") <= 5 and len(out) <= 3000


def test_synonym_group_matches_either_word(kbw):
    assert "[FK-002]" not in retrieve(kbw, ["merge", "競合"])  # 失敗台帳の行に merge は無い
    write_syn(kbw, "マージ, merge")
    assert "[FK-002]" in retrieve(kbw, ["merge", "競合"])


def test_synonym_group_counts_once(kbw):
    write_syn(kbw, "マージ, merge")
    s = memory_bootstrap._select(collect_sources(kbw), ["マージ merge"], synonyms=load_synonyms(kbw))
    assert s["failure"] and s["wiki"]
    assert all(x["score"] <= 2 for x in s["failure"] + s["wiki"])  # 同じグループの語は1語(+見出し加点1)


def test_skill_name_counts_only_for_prompt_terms(kbw):
    # 段1(name_terms=[])では名前一致だけの Skill は出ない、段2(指示に名前)では出る
    s1 = stage1_with_branch(kbw, "claude/writing-plans-x")
    legacy = memory_bootstrap._select(collect_sources(kbw), build_query(kbw))  # 手動 query 相当(従来どおり)
    assert any(s["title"] == "writing-plans-hojo" for s in legacy["skill"])
    assert s1 and "writing-plans-hojo" not in s1
    assert "writing-plans-hojo" in stage2(kbw, "writing-plans の手順")


def test_terms_line_shows_normalized_units(kbw):
    write_syn(kbw, "マージ, merge")
    o = stage2(kbw, "マージ競合の手順を確認したい")
    assert "検索語(指示から):" in o and "マージ" in o and "確認したい" not in o
    lines = o.splitlines()
    assert lines[1] == "検索語(指示から): マージ(=merge), 競合, 手順, 確認"
    assert lines[2] == "検索語(ブランチから): lighthouse, css"


PHASE1_FIXTURE = Path(__file__).resolve().parent / "fixtures/bootstrap_phase1_expected.txt"  # Task 6 で再凍結する


def _has_rev(rev):
    r = subprocess.run(["git", "cat-file", "-e", f"{rev}^{{commit}}"], cwd=REPO_ROOT, capture_output=True)
    return r.returncode == 0


def test_existing_kinds_match_frozen_phase1_output(kb):
    """凍結した Phase 1 の出力(kb・WORDS)と、[Wiki] 節と検索語行を除いて同一。浅い clone でも走る。"""
    expected = PHASE1_FIXTURE.read_text(encoding="utf-8")
    for label in ("[D]", "[FK-002]", "[再発防止]", "[Skill]", "[未解決]"):
        assert label in expected, label
    out = retrieve(kb, WORDS)
    assert section(out, "[Wiki]") == "- 該当なし"
    assert strip_wiki_section(out) == expected


def test_existing_kinds_unchanged_without_wiki(kb, tmp_path):
    if not _has_rev(PHASE1_REV):
        pytest.skip(f"{PHASE1_REV} が無い(浅い clone 等)。凍結した出力との比較は別のテストで行う")
    PHASE1_EXPECTED = _phase1_query(kb, WORDS, tmp_path)
    for label in ("[D]", "[FK-002]", "[再発防止]", "[Skill]", "[未解決]"):
        assert label in PHASE1_EXPECTED, label  # 既存6区分(Exp 以外)が実際に出ている状態で比べる
    out = retrieve(kb, WORDS)
    assert "[Wiki]" in out and section(out, "[Wiki]") == "- 該当なし"
    assert strip_wiki_section(out) == PHASE1_EXPECTED  # 既存6区分の行は Phase 1 と同一


@pytest.mark.skipif(os.environ.get("WIKISKILL_SKIP_TIMING") == "1", reason="timing is environment-dependent; measured locally")
def test_bootstrap_runtime_under_500ms_with_wiki(realcopy):
    wiki_dir = realcopy / "docs/wiki"
    before = set(wiki_dir.glob("*.md")) if wiki_dir.is_dir() else set()
    add_approved(realcopy, 5, filler=15)  # 承認済み20件(一致5件 = 25% で、ありふれた語の判定に掛からない)
    try:
        # 3回測って最速を見る(1回だけだと、この環境では Phase 1 の同じ hook も負荷で 500ms を跨ぐことがある)
        t1s, t2s = [], []
        for n in range(3):
            t1, r1 = _timed_hook(realcopy, "SessionStart", {"session_id": f"TW1-{n}", "source": "startup"})
            assert r1.returncode == 0 and context_of(r1.stdout).startswith("# 🧠 Memory Bootstrap")
            t2, r2 = _timed_hook(realcopy, "UserPromptSubmit",
                                 {"session_id": f"TW2-{n}", "prompt": "マージで競合したときの手順を確認したい"})
            assert r2.returncode == 0 and "[Wiki] マージ競合の手順その" in context_of(r2.stdout)
            t1s.append(t1)
            t2s.append(t2)
        print("with 20 Wikis: SessionStart " + "/".join(f"{t * 1000:.0f}" for t in t1s) + " ms, UserPromptSubmit "
              + "/".join(f"{t * 1000:.0f}" for t in t2s) + " ms")
        assert min(t1s) < 0.5 and min(t2s) < 0.5, (t1s, t2s)
    finally:
        for p in set(wiki_dir.glob("*.md")) - before:  # module 共有の realcopy を元に戻す
            p.unlink()


def test_wiki_failure_is_audited_and_others_still_shown(kbw, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("wiki boom")

    monkeypatch.setattr(memory_bootstrap._ws, "iter_wiki", boom)
    out = retrieve(kbw, WORDS)
    assert section(out, "[Wiki]") == "- 該当なし" and "[FK-002]" in out
    assert "wiki: RuntimeError: wiki boom" in _audit_text(kbw)


def test_synonyms_failure_means_no_synonyms(kbw, monkeypatch):
    write_syn(kbw, "マージ, merge")

    def boom(*_a, **_k):
        raise RuntimeError("syn boom")

    monkeypatch.setattr(memory_bootstrap._ws, "load_synonyms", boom)
    assert "[FK-002]" not in retrieve(kbw, ["merge", "競合"])  # 同義語なしで動く
    assert "synonyms: RuntimeError: syn boom" in _audit_text(kbw)


# ---------------------------------------------------------------- Phase 2 Task 4: needs_review の Wiki は注入しない

OPPOSITE_TO_APPROVED = "マージ競合の一覧確認は先にしない"  # 承認済み Wiki と「マージ・競合・一覧・確認」が重なる
NEW_DID = "D20261101-merge-order"


def add_decision(root, date="2026-11-01", outcome=OPPOSITE_TO_APPROVED, did=NEW_DID, title="作業順の見直し"):
    text = (f"---\ndecision_id: {did}\ndate: {date}\ntitle: {title}\nstatus: adopted\ntags: [順序]\n---\n"
            f"# 議事: {title}\n\n## なぜ\n手戻りを減らす。\n\n## 裁定\n{outcome}\n\n## 三名体制\n"
            f"- スイシン: 変える\n- ウタガイ: 事故が増える恐れ\n- ベッカイ: 手順書で足りる\n")
    (Path(root) / f"docs/議事_{date.replace('-', '')}_{did}.md").write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", f"decision {did}")
    memory_bootstrap._clear_caches()


def audit_text(root):
    return _audit_text(root)


def test_needs_review_wiki_not_injected(kbw):
    assert APPROVED_TITLE in retrieve(kbw, WORDS)
    add_decision(kbw, date="2026-11-01", outcome=OPPOSITE_TO_APPROVED)
    assert APPROVED_TITLE not in retrieve(kbw, WORDS) and "needs_review" in audit_text(kbw)
    assert f"wiki: needs_review {APPROVED_ID} {NEW_DID}" in audit_text(kbw)


def test_needs_review_wiki_not_in_stage1_or_stage2(kbw):
    assert APPROVED_TITLE in stage2(kbw, "マージ競合の手順を確認したい")  # 対照
    add_decision(kbw)
    s1 = stage1_with_branch(kbw, "claude/merge-conflict")
    s2 = stage2(kbw, "マージ競合の手順を確認したい")
    assert APPROVED_TITLE not in s1 and APPROVED_TITLE not in s2
    assert "[D]" in s2  # 新しい Decision の方は出る(Decision が勝つ)


def test_older_decision_also_blocks_injection(kbw):
    """多重の守り(fix round 1): approved_at 以前の Decision と矛盾するページ(本来 V12 で止まる)も注入しない。"""
    add_decision(kbw, date="2026-10-19")
    assert APPROVED_TITLE not in retrieve(kbw, WORDS)
    assert f"wiki: needs_review {APPROVED_ID} {NEW_DID}" in audit_text(kbw)
    assert wiki_schema.needs_review(wiki_schema.load_wiki_file(kbw / f"docs/wiki/{APPROVED_ID}.md", kbw),
                                    memory_bootstrap._decisions_cached(kbw)) == []  # V13 の警告の対象ではない


def test_bootstrap_self_source_restating_negation_is_injected(kbw):
    """出典の Decision の否定をそのまま引き継ぐ Wiki は、その Decision と矛盾扱いしない(自己矛盾の除外)。"""
    p = kbw / f"docs/wiki/{APPROVED_ID}.md"
    fm, body = wiki_schema.parse_wiki_frontmatter(p.read_text(encoding="utf-8"))
    _pre, secs, _order = wiki_schema.split_sections(body)
    fm["source_decision"] = [NEW_DID]
    fm["summary"] = OPPOSITE_TO_APPROVED + "。"
    p.write_text(wiki_schema.render_wiki(fm, secs), encoding="utf-8")
    add_decision(kbw, date="2026-10-19")
    assert APPROVED_TITLE in retrieve(kbw, WORDS)


def test_acknowledged_decision_keeps_wiki(kbw):
    p = kbw / f"docs/wiki/{APPROVED_ID}.md"
    fm, body = wiki_schema.parse_wiki_frontmatter(p.read_text(encoding="utf-8"))
    _pre, secs, _order = wiki_schema.split_sections(body)
    fm["acknowledged_decisions"] = [{"decision": NEW_DID, "reason": "同じ向き(先に一覧を見るのは任意)"}]
    p.write_text(wiki_schema.render_wiki(fm, secs), encoding="utf-8")
    add_decision(kbw)
    assert APPROVED_TITLE in retrieve(kbw, WORDS)


def test_needs_review_audited_once_per_page(kbw):
    add_decision(kbw)
    retrieve(kbw, WORDS)
    retrieve(kbw, WORDS)
    lines = [l for l in audit_text(kbw).splitlines() if f"wiki: needs_review {APPROVED_ID}" in l]
    assert len(lines) == 1


def test_needs_review_exception_drops_wiki_fail_closed(kbw, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("needs_review boom")

    monkeypatch.setattr(memory_bootstrap._ws, "decision_conflicts", boom)
    out = retrieve(kbw, WORDS)
    assert APPROVED_TITLE not in out and "[FK-002]" in out  # Wiki だけ落とし、他の区分は出す
    assert f"wiki: needs_review {APPROVED_ID} error" in audit_text(kbw)


def test_wiki_second_guard_drops_candidate_path(kbw, monkeypatch):
    """iter_wiki が誤って _candidates/ のページを official として返しても、_wiki が二重に捨てる。"""
    page = wiki_schema.load_wiki_file(kbw / f"docs/wiki/{APPROVED_ID}.md", kbw)
    fake = {**page, "title": "候補なのに正式を名乗るページ", "_path": "docs/wiki/_candidates/x.md", "_place": "official"}
    monkeypatch.setattr(memory_bootstrap._ws, "iter_wiki", lambda root, place: [fake] if place == "official" else [])
    assert memory_bootstrap._wiki(kbw) == []
    assert "候補なのに正式を名乗るページ" not in retrieve(kbw, WORDS)


def test_clear_caches_resets_decision_and_synonym_memo(kbw):
    memory_bootstrap._decisions_cached(kbw)
    write_syn(kbw, "マージ, merge")
    memory_bootstrap._synonyms(kbw)
    assert memory_bootstrap._DECISIONS_CACHE and memory_bootstrap._SYN_CACHE
    memory_bootstrap._clear_caches()
    assert not memory_bootstrap._DECISIONS_CACHE and not memory_bootstrap._SYN_CACHE


def test_needs_review_hook_path_runs_as_script(kbw):
    """hook(スクリプトとして実行)でも needs_review の Wiki は出ない(wiki_schema が memory_bootstrap を読む経路)。"""
    r0 = run_hook(kbw, "UserPromptSubmit", {"session_id": "NR0", "prompt": "マージ競合の手順を確認したい"})
    assert APPROVED_TITLE in context_of(r0.stdout)  # Decision を足す前は出る(対照)
    add_decision(kbw)
    r = run_hook(kbw, "UserPromptSubmit", {"session_id": "NR1", "prompt": "マージ競合の手順を確認したい"})
    assert r.returncode == 0
    ctx = context_of(r.stdout)
    assert ctx and APPROVED_TITLE not in ctx and "[D]" in ctx
