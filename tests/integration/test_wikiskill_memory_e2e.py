"""WikiSkill Phase 1 Task 8: 自動 E2E。

Session A(決定を書いて commit → 経験を記録 → 終了)の記録だけを手がかりに、
まったく別の session_id の Session B が、Decision・「なぜ」・反対理由・失敗台帳・再発防止を
Memory Bootstrap(段1・段2)として復元できることを、hook ラッパ経由(subprocess・Claude Code と同じ stdin JSON)で固定する。

実セッション(Claude Code 本体)での手動 E2E は docs/wikiskill/Phase1受け入れ記録.md に別途記録する。
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT_NAMES = [
    "wikiskill_common.py",
    "experience_log.py",
    "memory_bootstrap.py",
    "decision_memory.py",
    "check_experience_privacy.py",
    "experience_archive.py",
    "check_repo_scope.py",
]
DECISION_PATH = "docs/議事_20261006_E2Eテスト決定.md"

FM_DECISION = """---
decision_id: D20261006-e2e-test
date: 2026-10-06
title: E2Eテスト決定
scope: hojo-hq/基盤
tags: [e2e, memory, 締切アラート]
status: adopted
supersedes:
decided_by: 小柳
---

# 議事 E2Eテスト決定

## なぜ(背景)

締切7日前では準備が間に合わない

## 前提

書類とgBizIDの準備に約1か月かかる

## 三名体制の議論

- **スイシン(推進)**: 約1か月前で統一して案内する
- **ウタガイ(反対理由・必須記録)**: 30日前は早すぎて忘れられる
- **ベッカイ(別解・前提を疑う)**: 前提を疑い、段階通知にする

## 裁定

約1か月前で統一する
"""

RULE_BULLETS = """## 再発防止メモ(同じミスが2度起きたら1行足す)
- **生成物を再生成する前に、必ず最新の origin/main をマージして取り込む**。古いブランチで再生成すると、新しいデータが消える。マージで競合したら一覧を確認してから解決する
- **コミット前にブランチ名を確認する**。並行セッションが同じ作業コピーでブランチを切り替えていることがある
"""

SKILL_MD = """---
name: writing-plans-hojo
description: 実装計画を書くときに使う。仕様から段階的な実装計画を作る。
---

# writing-plans-hojo

実装計画を書く手順。
"""


def _real_ledger_lines():
    """実際の失敗台帳から、ヘッダ行・区切り行・FK-002 行をそのまま取る。"""
    lines = (REPO / "docs" / "失敗台帳.md").read_text(encoding="utf-8").splitlines()
    header = next(i for i, ln in enumerate(lines) if ln.startswith("| ID | 発生日"))
    fk002 = next(ln for ln in lines if ln.startswith("| FK-002 |"))
    return lines[header], lines[header + 1], fk002


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def write(world, rel, text):
    p = Path(world) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def hook(world, event, sid, **payload):
    """wikiskill-hook.sh を Claude Code と同じ stdin JSON で呼ぶ。"""
    env = {k: v for k, v in os.environ.items() if k != "HOJO_MEMORY_OFF"}
    env["CLAUDE_PROJECT_DIR"] = str(world)
    data = {"session_id": sid, "cwd": str(world), "hook_event_name": event, **payload}
    return subprocess.run(
        ["bash", str(Path(world) / ".claude/hooks/wikiskill-hook.sh"), event],
        input=json.dumps(data, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=world,
        env=env,
        timeout=30,
    )


def read_session(world, sid):
    files = sorted((Path(world) / ".claude" / "experience").glob(f"*/session-{sid}.jsonl"))
    assert files, f"session-{sid}.jsonl が無い"
    return files[0].read_text(encoding="utf-8")


def _build_world(root, origin_url):
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "e2e")
    git(root, "config", "user.email", "e2e@example.com")
    git(root, "remote", "add", "origin", origin_url)

    header, sep, fk002 = _real_ledger_lines()
    write(root, "CLAUDE.md", "# CLAUDE.md\n\n" + RULE_BULLETS)
    write(root, "docs/失敗台帳.md", "# 失敗台帳\n\n## 台帳\n\n" + "\n".join([header, sep, fk002]) + "\n")
    write(root, "docs/決裁キュー.md", "# 決裁キュー\n\n- 該当なし\n")
    write(root, ".claude/skills/writing-plans-hojo/SKILL.md", SKILL_MD)
    for rel in (".claude/settings.json", ".gitignore"):
        write(root, rel, (REPO / rel).read_text(encoding="utf-8"))
    for name in SCRIPT_NAMES:
        write(root, f"scripts/{name}", (REPO / "scripts" / name).read_text(encoding="utf-8"))
    hook_dst = root / ".claude/hooks/wikiskill-hook.sh"
    hook_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / ".claude/hooks/wikiskill-hook.sh", hook_dst)
    hook_dst.chmod(0o755)

    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "chore: initial")
    # bootstrap は origin/main との差分を見る。clone ではないので参照を手で作る
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "checkout", "-q", "-b", "claude/e2e-memory")
    return root


@pytest.fixture
def world(tmp_path):
    return _build_world(tmp_path / "world", "https://github.com/allgroup-inc/hojo-hq.git")


@pytest.fixture
def world_private(tmp_path):
    return _build_world(tmp_path / "world_private", "https://github.com/allgroup-inc/glow-docs-private.git")


def _context(proc):
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    return out["hookSpecificOutput"]["additionalContext"]


def _run_session_a(world):
    hook(world, "SessionStart", sid="A", source="startup")
    write(world, DECISION_PATH, FM_DECISION)
    hook(world, "PostToolUse", sid="A", tool_name="Write",
         tool_input={"file_path": str(world / DECISION_PATH)})
    git(world, "add", "-A")
    git(world, "commit", "-q", "-m", "docs: 締切アラート時期の決定")
    hook(world, "PostToolUse", sid="A", tool_name="Bash",
         tool_input={"command": "git commit -m x"})
    hook(world, "PostToolUse", sid="A", tool_name="Skill",
         tool_input={"skill": "writing-plans-hojo"})
    hook(world, "SessionEnd", sid="A", reason="exit")
    # クラウドでは push まで必要。ここでは commit までで原本を Git に載せる
    git(world, "add", ".claude/experience")
    git(world, "commit", "-q", "-m", "chore: experience")


def test_session_a_then_fresh_session_b_restores_decision_and_why(world):
    # ---- Session A ----
    _run_session_a(world)
    a = read_session(world, "A")
    assert '"event": "session_end"' in a and "締切アラート時期の決定" in a

    # ---- Session B(完全に別の session_id・マーカー無し)----
    r1 = hook(world, "SessionStart", sid="B", source="startup")
    ctx = _context(r1)
    assert "[D] 2026-10-06 E2Eテスト決定" in ctx                       # Decision が復元される
    assert "なぜ: 締切7日前では準備が間に合わない" in ctx               # 「なぜ」が復元される
    assert "ウタガイ: 30日前は早すぎて忘れられる" in ctx               # 反対理由が復元される
    assert "見直し: 2027-04-04" in ctx                                  # 180日既定
    assert "[Exp]" in ctx and "session-A" in ctx and "writing-plans-hojo" in ctx  # Experience(低信頼)

    r2 = hook(world, "UserPromptSubmit", sid="B", prompt="マージで競合したときの手順を確認したい")
    ctx2 = _context(r2)
    assert "[FK-002]" in ctx2 and "[再発防止]" in ctx2                  # 失敗・再発防止が必要に応じて復元される
    # 段1の項目を再掲しない。見出しの検索語には議事ファイル名が載るので、項目行(出典ラベル付き)で判定する
    assert "[D] 2026-10-06 E2Eテスト決定" not in ctx2
    assert "なぜ: 締切7日前" not in ctx2 and "- [Exp]" not in ctx2

    r3 = hook(world, "UserPromptSubmit", sid="B", prompt="次")
    assert r3.stdout.strip() == "{}"                                    # 段2は1セッション1回

    # 受け入れ記録用に、実出力を残す(pytest -s で確認できる)
    print("\n=== STAGE1 additionalContext ===\n" + ctx)
    print("\n=== STAGE2 additionalContext ===\n" + ctx2)


def test_memory_off_disables_everything_without_breaking_session(world):
    (world / ".claude/memory.off").touch()
    r = hook(world, "SessionStart", sid="C", source="startup")
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert not list((world / ".claude/experience").glob("*/session-C.jsonl"))


def test_private_repo_session_never_marks_public(world_private):   # origin=glow-docs-private
    hook(world_private, "SessionStart", sid="P", source="startup")
    text = read_session(world_private, "P")
    assert '"visibility": "private"' in text
    assert '"visibility": "public"' not in text


def test_privacy_check_passes_on_e2e_output(world):   # Session A の記録が CI 検査を通る
    _run_session_a(world)
    tracked = git(world, "ls-files", "--", ".claude/experience")
    assert "session-A.jsonl" in tracked                                 # 検査対象が実在する(空振りでない)
    r = subprocess.run(["python3", "scripts/check_experience_privacy.py"],
                       cwd=world, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
