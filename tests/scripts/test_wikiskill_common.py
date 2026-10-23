"""WikiSkill Phase 1 Task 1: wikiskill_common.py の検査。"""
import io
import json
import os
import sys

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

from wikiskill_common import audit, disabled, emit, read_hook_input, session_id_of  # noqa: E402


def test_disabled_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOJO_MEMORY_OFF", "1")
    assert disabled(tmp_path)


def test_disabled_by_file(tmp_path, monkeypatch):
    monkeypatch.delenv("HOJO_MEMORY_OFF", raising=False)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/memory.off").touch()
    assert disabled(tmp_path)


def test_read_hook_input_tolerates_garbage(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert read_hook_input() == {}


def test_session_id_fallback_order(monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-id")
    assert session_id_of({}) == "env-id"
    assert session_id_of({"session_id": "payload-id"}) == "payload-id"
    monkeypatch.delenv("CLAUDE_SESSION_ID")
    assert session_id_of({}).startswith("unknown-")


def test_audit_appends_tab_separated_line(tmp_path):
    audit(tmp_path, "logger", "disk full")
    line = (tmp_path / ".claude/experience/_audit.log").read_text().splitlines()[-1]
    assert line.split("\t")[1:] == ["logger", "disk full"]


def test_emit_shape(capsys):
    emit("SessionStart", additional_context="X", system_message="W")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"] == {"hookEventName": "SessionStart", "additionalContext": "X"}
    assert out["systemMessage"] == "W"


# ---- Phase 2 最終修正: commit 済みの判定(committed_files)と失敗台帳の行の分け方(split_ledger_row) ----
import subprocess  # noqa: E402

import pytest  # noqa: E402

from wikiskill_common import GitError, committed_files, split_ledger_row  # noqa: E402


def _g(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def cf_repo(tmp_path):
    root = tmp_path / "cf"
    (root / "d").mkdir(parents=True)
    _g(root, "init", "-q")
    _g(root, "config", "user.email", "t@example.com")
    _g(root, "config", "user.name", "t")
    _g(root, "config", "commit.gpgsign", "false")
    for name in ("clean", "edited", "staged", "assumed", "skipped", "日本語"):
        (root / "d" / f"{name}.md").write_text(name, encoding="utf-8")
    _g(root, "add", "-A")
    _g(root, "commit", "-q", "-m", "init")
    return root


def test_committed_files_only_unchanged_tracked_regular_files(cf_repo):
    d = cf_repo / "d"
    (d / "untracked.md").write_text("u", encoding="utf-8")
    (d / "edited.md").write_text("changed", encoding="utf-8")
    (d / "staged.md").write_text("changed", encoding="utf-8")
    _g(cf_repo, "add", "d/staged.md")
    _g(cf_repo, "update-index", "--assume-unchanged", "d/assumed.md")
    (d / "assumed.md").write_text("changed", encoding="utf-8")  # diff には出ない書き換え
    _g(cf_repo, "update-index", "--skip-worktree", "d/skipped.md")
    (d / "skipped.md").write_text("changed", encoding="utf-8")
    os.symlink("clean.md", d / "link.md")
    _g(cf_repo, "add", "d/link.md")
    _g(cf_repo, "commit", "-q", "-m", "link", "--", "d/link.md")  # staged.md は index に載せたまま
    assert committed_files(cf_repo, "d") == {"d/clean.md", "d/日本語.md"}


def test_committed_files_raises_outside_top_or_without_git(cf_repo, tmp_path):
    with pytest.raises(GitError):
        committed_files(cf_repo / "d", ".")  # root が最上位でない(外側のリポのパスを混ぜない)
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitError):
        committed_files(plain, ".")


def test_split_ledger_row_honours_escaped_pipe():
    row = r"| FK-009 | 2026-10-01 | 事故 | `a \| b` を誤って分けた | 影響 |"
    assert split_ledger_row(row) == ["FK-009", "2026-10-01", "事故", r"`a \| b` を誤って分けた", "影響"]
    assert split_ledger_row("|a|b|") == ["a", "b"]
