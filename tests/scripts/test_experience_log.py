"""WikiSkill Phase 1 Task 1: experience_log.py の検査。

プロンプト本文・Bash コマンド全文・プロジェクト外パスが JSONL に残らないこと、
hojo-hq 以外の remote では必ず private になること、書込失敗が silent にならないことを固定する。
"""
import json
import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import experience_log  # noqa: E402
from experience_log import (  # noqa: E402
    ExperienceWriteError,
    append_event,
    build_tool_event,
    note_event,
    repo_slug,
    sanitize_path,
    start_event,
    summarize_session,
)

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
PRIVATE_URL = "https://github.com/allgroup-inc/glow-docs-private.git"


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(root, origin):
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "remote", "add", "origin", origin)
    (root / "README.md").write_text("x")
    git(root, "add", "README.md")
    git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path, PUBLIC_URL)


@pytest.fixture
def repo_private(tmp_path):
    return _init_repo(tmp_path, PRIVATE_URL)


def test_sanitize_path_inside_project(repo):
    assert sanitize_path(str(repo / "docs/a.md"), repo) == "docs/a.md"


def test_sanitize_path_outside_project(repo):
    assert sanitize_path("/home/user/glow-docs-private/x.md", repo) == "<external>"


def test_visibility_public_for_hojo_hq(repo):
    assert repo_slug(repo) == "allgroup-inc/hojo-hq"
    assert start_event(repo, "s1")["visibility"] == "public"


def test_visibility_private_for_other_remote(repo_private):
    ev = start_event(repo_private, "s1")
    assert ev["repo"] == "allgroup-inc/glow-docs-private"
    assert ev["visibility"] == "private"


def test_append_event_writes_one_line_per_call(repo):
    p = append_event(repo, start_event(repo, "s1"))
    append_event(repo, {"ts": "2026-10-06T00:00:00Z", "session_id": "s1", "event": "note", "text": "ok"})
    assert len(p.read_text().splitlines()) == 2
    assert p.name == "session-s1.jsonl"
    assert p.parent.parent == repo / ".claude/experience"


def test_bash_tool_event_keeps_only_program(repo):
    ev = build_tool_event(
        {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'secret words'"}}, repo
    )
    assert ev["program"] == "git"
    assert "secret" not in json.dumps(ev)
    assert "commit" not in json.dumps(ev)
    # 先頭の環境変数代入(値が秘密になり得る)も残さない
    ev = build_tool_event(
        {"tool_name": "Bash", "tool_input": {"command": "TOKEN=hunter2 curl https://x.example/?k=1"}}, repo
    )
    assert ev["program"] == "curl"
    assert "hunter2" not in json.dumps(ev) and "x.example" not in json.dumps(ev)


def test_skill_tool_event(repo):
    ev = build_tool_event({"tool_name": "Skill", "tool_input": {"skill": "writing-plans"}}, repo)
    assert ev["skill"] == "writing-plans"
    assert ev["event"] == "skill"


def test_other_tools_ignored(repo):
    assert build_tool_event({"tool_name": "Read", "tool_input": {}}, repo) is None


def test_note_truncated_to_1000(repo):
    assert len(note_event("s1", "x" * 2000)["text"]) == 1000


def test_summarize_session_collects_commits(repo):
    append_event(repo, start_event(repo, "s1"))  # head を記録
    append_event(repo, build_tool_event(
        {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(repo / "README.md")}}, repo))
    append_event(repo, build_tool_event(
        {"session_id": "s1", "tool_name": "Skill", "tool_input": {"skill": "writing-plans"}}, repo))
    (repo / "f.txt").write_text("1")
    git(repo, "add", "f.txt")
    git(repo, "commit", "-q", "-m", "feat: f")
    s = summarize_session(repo, "s1")
    assert s["event"] == "session_end"
    assert s["commits"][0]["subject"] == "feat: f"
    assert s["tools"] == {"Edit": 1}
    assert s["skills"] == ["writing-plans"]
    assert isinstance(s["duration_s"], int) and s["duration_s"] >= 0


def test_append_event_failure_is_audited(repo, monkeypatch, capsys):
    def failing_open(path):
        raise OSError("disk full")

    monkeypatch.setattr(experience_log, "_open_append", failing_open)
    with pytest.raises(ExperienceWriteError):
        append_event(repo, start_event(repo, "s1"))
    # 監査ログに失敗が残る(silent fail 禁止)
    lines = (repo / ".claude/experience/_audit.log").read_text().splitlines()
    assert lines and lines[-1].split("\t")[1] == "experience_log"
    assert "disk full" in lines[-1]
    # 失敗したイベントはセッション JSONL に残っていない
    assert not list((repo / ".claude/experience").glob("*/session-s1.jsonl"))
    # 監査ログ自体が書けない場合は stderr に出る(どこにも出ない失敗を作らない)
    (repo / ".claude/experience/_audit.log").unlink()
    (repo / ".claude/experience/_audit.log").mkdir()
    capsys.readouterr()
    with pytest.raises(ExperienceWriteError):
        append_event(repo, start_event(repo, "s1"))
    assert "disk full" in capsys.readouterr().err
