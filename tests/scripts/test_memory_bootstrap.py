"""WikiSkill Phase 1 Task 4: memory_bootstrap.py の検査。

新しいセッションに「今の作業に関係する」Decision・未解決・失敗・再発防止・Skill・Experience
だけを、信頼階層順・出典ラベル付き・文字数上限内で渡すことを固定する。
root の外は読まない / private の Experience は出さない / 段2 はセッションに1回だけ。
"""
import json
import os
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


def write_session_end(kb, sid, ts, branch=BRANCH, visibility="public", skills=("writing-plans",), commits=1):
    month = ts[:7]
    d = kb / ".claude/experience" / month
    d.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": ts, "session_id": sid, "event": "session_end", "repo": "allgroup-inc/hojo-hq",
        "visibility": visibility, "branch": branch,
        "commits": [{"sha": f"abc{i}", "subject": f"c{i}"} for i in range(commits)],
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
    assert "[D] 2026-08-10" in out and "なぜ:" in out and "ウタガイ:" in out


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


def test_score_counts_shared_features():
    assert score(["実装計画"], "実装計画を作る") == 3
    assert score(["lighthouse"], "Lighthouse の実測") >= 1
    assert score(["zzzz"], "北極星") == 0


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


def test_short_query_needs_every_feature():
    # 北極星 は特徴量2つ(北極・極星)。min_score 3 に届かない短い語は「全部一致」で拾う
    assert score(["北極星"], "北極星4本の現在地") == 2
    assert score(["北極星"], "北極の話") == 1


def test_english_common_words_and_numbers_do_not_match():
    assert score(["the 2026 use"], "Use when the user wants ... 2026") == 0


def test_stage2_skipped_without_session_id(kb):
    e = {"CLAUDE_SESSION_ID": ""}
    r = run_bootstrap(kb, "hook", "UserPromptSubmit", payload={"prompt": "マージ競合"}, env=e)
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert "session_id missing" in (kb / ".claude/experience/_audit.log").read_text(encoding="utf-8")
