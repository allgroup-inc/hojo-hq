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
