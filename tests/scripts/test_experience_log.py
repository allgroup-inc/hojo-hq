"""WikiSkill Phase 1 Task 1: experience_log.py の検査。

プロンプト本文・Bash コマンド全文・プロジェクト外パスが JSONL に残らないこと、
hojo-hq 以外の remote では必ず private になること、書込失敗が silent にならないことを固定する。
"""
import io
import itertools
import json
import os
import re
import subprocess
import sys
import time

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


def test_note_with_line_separator_chars_round_trips(repo):
    """raw の U+2028/U+2029/\\x85 を含む note が、読み戻しで行として割れない(記録件数が変わらない)。"""
    append_event(repo, start_event(repo, "s1"))
    path = append_event(repo, note_event("s1", "a\u2028b\u2029c\x85d", repo))
    append_event(repo, build_tool_event(
        {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(repo / "README.md")}}, repo))
    assert "\u2028" in path.read_text(encoding="utf-8")  # raw で書かれている
    events = experience_log._read_events(path)
    assert len(events) == 3
    assert events[1]["text"] == "a\u2028b\u2029c\x85d"
    s = summarize_session(repo, "s1")
    assert s["tools"] == {"Edit": 1}


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


# ---- _program_of / パスの堅牢性 ----

@pytest.mark.parametrize("command, program, leaked", [
    ('API_KEY="abc def" curl https://x.example', "curl", ["abc", "def"]),
    ('GIT_AUTHOR_NAME="Foo Bar" git commit -m x', "git", ["Foo", "Bar"]),
    ("echo 'unbalanced", "<unknown>", ["unbalanced"]),
    (None, "<unknown>", []),
    (123, "<unknown>", []),
    ("", "<unknown>", []),
])
def test_bash_program_parsing_never_leaks_values(repo, command, program, leaked):
    ev = build_tool_event({"tool_name": "Bash", "tool_input": {"command": command}}, repo)
    assert ev["program"] == program
    for word in leaked:
        assert word not in json.dumps(ev)


@pytest.mark.parametrize("tin", [{}, {"file_path": ""}, {"file_path": None}, {"file_path": 5}])
def test_file_tool_without_usable_path_is_unknown(repo, tin):
    ev = build_tool_event({"tool_name": "Edit", "tool_input": tin}, repo)
    assert ev["path"] == "<unknown>"


# ---- _git の文字コード耐性 ----

def test_git_replaces_undecodable_output_and_survives_decode_error(repo, monkeypatch):
    seen = {}

    class Done:
        returncode = 0
        stdout = " ok \n"

    def fake_run(*a, **kw):
        seen.update(kw)
        return Done()

    monkeypatch.setattr(experience_log.subprocess, "run", fake_run)
    assert experience_log._git(repo, "status") == "ok"
    assert seen["errors"] == "replace"

    def boom(*a, **kw):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(experience_log.subprocess, "run", boom)
    assert experience_log._git(repo, "status") == ""


# ---- hook モード / CLI(main を直接駆動) ----

@pytest.fixture
def cli(repo, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("HOJO_MEMORY_OFF", raising=False)

    def run(*argv, stdin=None):
        if stdin is not None:
            monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(stdin)))
        capsys.readouterr()
        rc = experience_log.main(["experience_log.py", *argv])
        cap = capsys.readouterr()
        return rc, cap.out, cap.err

    run.repo = repo
    return run


def _events(repo, sid):
    (path,) = (repo / ".claude/experience").glob(f"*/session-{sid}.jsonl")
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_hook_session_start_writes_record_and_current_session(cli):
    rc, out, _ = cli("hook", "SessionStart", stdin={"session_id": "s9", "source": "resume"})
    assert rc == 0 and json.loads(out) == {}
    (ev,) = _events(cli.repo, "s9")
    assert ev["event"] == "session_start" and ev["source"] == "resume"
    assert (cli.repo / ".claude/experience/_local/current_session").read_text().strip() == "s9"


def test_hook_session_end_writes_summary_and_ended_marker(cli):
    cli("hook", "SessionStart", stdin={"session_id": "s9"})
    rc, out, _ = cli("hook", "SessionEnd", stdin={"session_id": "s9", "reason": "clear"})
    assert rc == 0 and json.loads(out) == {}
    evs = _events(cli.repo, "s9")
    assert [e["event"] for e in evs] == ["session_start", "session_end"]
    assert evs[-1]["reason"] == "clear"
    assert (cli.repo / ".claude/experience/_local/s9.ended").exists()


def test_hook_session_end_marker_survives_summary_failure(cli, monkeypatch):
    def boom(root, sid):
        raise RuntimeError("summary broke")

    monkeypatch.setattr(experience_log, "summarize_session", boom)
    rc, out, _ = cli("hook", "SessionEnd", stdin={"session_id": "s9"})
    assert rc == 0
    assert "systemMessage" in json.loads(out)
    assert (cli.repo / ".claude/experience/_local/s9.ended").exists()
    assert "summary broke" in (cli.repo / ".claude/experience/_audit.log").read_text()


def test_hook_write_failure_warns_via_system_message_and_exits_0(cli, monkeypatch):
    def failing_open(path):
        raise OSError("disk full")

    monkeypatch.setattr(experience_log, "_open_append", failing_open)
    rc, out, _ = cli("hook", "PostToolUse",
                     stdin={"session_id": "s9", "tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert rc == 0
    msg = json.loads(out)["systemMessage"]
    assert "Experience記録に失敗" in msg and "disk full" in msg and "_audit.log" in msg
    assert "disk full" in (cli.repo / ".claude/experience/_audit.log").read_text()


def test_hook_disabled_prints_empty_json_and_writes_nothing(cli, monkeypatch):
    monkeypatch.setenv("HOJO_MEMORY_OFF", "1")
    rc, out, _ = cli("hook", "SessionStart", stdin={"session_id": "s9"})
    assert rc == 0 and json.loads(out) == {}
    assert not (cli.repo / ".claude/experience").exists()


def test_hook_success_prints_empty_json_for_every_event(cli):
    for ev, payload in (
        ("SessionStart", {"session_id": "s9"}),
        ("PostToolUse", {"session_id": "s9", "tool_name": "Bash", "tool_input": {"command": "ls"}}),
        ("SessionEnd", {"session_id": "s9"}),
    ):
        rc, out, _ = cli("hook", ev, stdin=payload)
        assert rc == 0 and out.strip() == "{}", ev


def test_hook_audits_missing_session_id(cli):
    rc, out, _ = cli("hook", "SessionStart", stdin={"hook_event_name": "SessionStart"})
    assert rc == 0 and json.loads(out) == {}
    log = (cli.repo / ".claude/experience/_audit.log").read_text()
    assert "session_id missing in hook payload; using unknown-" in log


def test_hook_does_not_audit_when_session_id_present(cli):
    cli("hook", "SessionStart", stdin={"session_id": "s9"})
    assert not (cli.repo / ".claude/experience/_audit.log").exists()


def test_hook_missing_session_id_not_audited_when_env_provides_it(cli, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_ID", "envsid")
    cli("hook", "SessionStart", stdin={"hook_event_name": "SessionStart"})
    assert not (cli.repo / ".claude/experience/_audit.log").exists()
    assert _events(cli.repo, "envsid")


def test_note_cli_appends_note_event_using_env_session(cli, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_ID", "envsid")
    rc, out, _ = cli("note", "decided X")
    assert rc == 0 and "recorded:" in out
    (ev,) = _events(cli.repo, "envsid")
    assert ev["event"] == "note" and ev["text"] == "decided X"


def test_note_cli_falls_back_to_current_session_file(cli):
    cli("hook", "SessionStart", stdin={"session_id": "s9"})
    rc, _, _ = cli("note", "via file")
    assert rc == 0
    assert [e["event"] for e in _events(cli.repo, "s9")] == ["session_start", "note"]
    assert not list((cli.repo / ".claude/experience").glob("*/session-unknown-*.jsonl"))


def test_note_survives_git_decode_failure(cli, monkeypatch):
    def boom(*a, **kw):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(experience_log.subprocess, "run", boom)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "s7")
    rc, _, _ = cli("note", "still written")
    assert rc == 0
    # git が全滅(例外)なら tracked か分からないので part へ書く(Phase 2 Task 0b)。本体 or part のどちらかに残っていればよい
    (path,) = (cli.repo / ".claude/experience").glob("*/session-s7*.jsonl")
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["text"] == "still written"


def test_note_unexpected_error_is_audited_not_a_traceback(cli, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(experience_log, "note_event", boom)
    rc, _, err = cli("note", "x")
    assert rc == 1 and "kaboom" in err and "Traceback" not in err
    assert "kaboom" in (cli.repo / ".claude/experience/_audit.log").read_text()


def test_summarize_ignores_invalid_head_and_audits(repo):
    ev = start_event(repo, "s1")
    ev["head"] = "--output=/tmp/x"
    append_event(repo, ev)
    s = summarize_session(repo, "s1")
    assert s["commits"] == []
    assert "invalid head" in (repo / ".claude/experience/_audit.log").read_text()


# ---- slow 監査(hook 1回が SLOW_MS を超えたら _audit.log にだけ残す) ----

def _audit_lines(repo):
    p = repo / ".claude/experience/_audit.log"
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def test_slow_hook_is_audited_without_system_message(cli, monkeypatch):
    monkeypatch.setattr(experience_log, "SLOW_MS", -1)  # どんな実行も「遅い」扱いにする
    rc, out, _ = cli("hook", "SessionStart", stdin={"session_id": "s9"})
    assert rc == 0 and json.loads(out) == {}  # 画面警告(systemMessage)は足さない
    lines = [l for l in _audit_lines(cli.repo) if "\tslow " in l]
    assert len(lines) == 1
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\texperience_log\tslow SessionStart \d+ms", lines[0])


def test_slow_audit_format_with_forced_clock(cli, monkeypatch):
    ticks = itertools.count()

    def fake_clock():  # 呼び出し回数に依らない: 最初だけ 0、以降は 0.612 秒から単調増加(1回ごとに +1µs)
        n = next(ticks)
        return 0.0 if n == 0 else 0.612 + n * 1e-6

    monkeypatch.setattr(time, "perf_counter", fake_clock)
    rc, out, _ = cli("hook", "PostToolUse",
                     stdin={"session_id": "s9", "tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert rc == 0 and json.loads(out) == {}
    assert _audit_lines(cli.repo)[-1].endswith("\texperience_log\tslow PostToolUse 612ms")


def test_slow_line_coexists_with_write_failure_warning(cli, monkeypatch):
    def failing_open(path):
        raise OSError("disk full")

    monkeypatch.setattr(experience_log, "_open_append", failing_open)
    monkeypatch.setattr(experience_log, "SLOW_MS", -1)
    rc, out, _ = cli("hook", "PostToolUse",
                     stdin={"session_id": "s9", "tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert rc == 0 and "Experience記録に失敗" in json.loads(out)["systemMessage"]
    assert "slow" not in json.loads(out)["systemMessage"]
    assert any("\tslow PostToolUse " in l for l in _audit_lines(cli.repo))


def test_fast_hook_writes_no_slow_line(cli):
    cli("hook", "SessionStart", stdin={"session_id": "s9"})
    assert not any("slow" in l for l in _audit_lines(cli.repo))


def test_slow_not_measured_when_stopped(cli, monkeypatch):
    monkeypatch.setattr(experience_log, "SLOW_MS", -1)
    monkeypatch.setenv("HOJO_MEMORY_OFF", "1")
    rc, out, _ = cli("hook", "SessionStart", stdin={"session_id": "s9"})
    assert rc == 0 and json.loads(out) == {}
    assert _audit_lines(cli.repo) == []


# ---- 最終修正波: part ファイル / プログラム名の検査 / detached HEAD のブランチ / first-parent ----

def _commit_experience(repo):
    git(repo, "add", ".claude/experience")
    git(repo, "commit", "-q", "-m", "chore: experience")


def test_append_goes_to_part_file_once_base_is_tracked(repo):
    base = append_event(repo, start_event(repo, "s1"))
    assert base.name == "session-s1.jsonl"
    _commit_experience(repo)
    p1 = append_event(repo, note_event("s1", "after commit", repo))
    assert p1.name == "session-s1.part1.jsonl" and p1.parent == base.parent
    assert len(base.read_text().splitlines()) == 1  # commit 済みの本体は汚さない
    assert git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    # part1 も commit されたら part2 へ
    _commit_experience(repo)
    p2 = append_event(repo, note_event("s1", "after second commit", repo))
    assert p2.name == "session-s1.part2.jsonl"
    assert git(repo, "status", "--porcelain", "--untracked-files=no") == ""


def test_summarize_reads_base_and_parts_as_one_session(repo):
    append_event(repo, start_event(repo, "s1"))
    append_event(repo, build_tool_event(
        {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(repo / "README.md")}}, repo))
    _commit_experience(repo)
    append_event(repo, build_tool_event(
        {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(repo / "README.md")}}, repo))
    append_event(repo, build_tool_event(
        {"session_id": "s1", "tool_name": "Skill", "tool_input": {"skill": "writing-plans"}}, repo))
    s = summarize_session(repo, "s1")
    assert s["tools"] == {"Edit": 2} and s["skills"] == ["writing-plans"]
    assert [c["subject"] for c in s["commits"]] == ["chore: experience"]  # head は本体の session_start から


def test_summarize_lists_first_parent_commits_only(repo):
    append_event(repo, start_event(repo, "s1"))
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("s")
    git(repo, "add", "side.txt")
    git(repo, "commit", "-q", "-m", "feat: side work")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "side", "-m", "merge: side")
    subjects = [c["subject"] for c in summarize_session(repo, "s1")["commits"]]
    assert subjects == ["merge: side"]


@pytest.mark.parametrize("command, program", [
    ("TOKEN=$(cat ~/.config/x) gh", "<unknown>"),
    ("/home/user/other-repo/scripts/顧客A社_抽出.sh --all", "<external>"),
    ("sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx", "<unknown>"),
    ("python3 -m pytest", "python3"),
    ("./scripts/run_all.sh", "run_all.sh"),
    ("顧客A社.sh", "<unknown>"),
])
def test_bash_program_name_is_validated(repo, command, program):
    ev = build_tool_event({"tool_name": "Bash", "tool_input": {"command": command}}, repo)
    assert ev["program"] == program
    assert "顧客" not in json.dumps(ev, ensure_ascii=False)


def test_bash_absolute_program_inside_repo_keeps_basename(repo):
    ev = build_tool_event({"tool_name": "Bash", "tool_input": {"command": f"{repo}/scripts/x.sh"}}, repo)
    assert ev["program"] == "x.sh"


def test_branch_on_detached_head_uses_the_single_origin_ref(repo):
    git(repo, "update-ref", "refs/remotes/origin/claude/feature-x", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD~0")
    (repo / "b.txt").write_text("b")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "feat: b")
    git(repo, "update-ref", "refs/remotes/origin/claude/feature-x", "HEAD")
    git(repo, "checkout", "-q", "--detach", "HEAD")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/claude/feature-x")
    assert start_event(repo, "s1")["branch"] == "claude/feature-x"


def test_branch_on_detached_head_ambiguous_is_unknown(repo):
    git(repo, "update-ref", "refs/remotes/origin/a", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/b", "HEAD")
    git(repo, "checkout", "-q", "--detach", "HEAD")
    assert start_event(repo, "s1")["branch"] == "unknown"
    git(repo, "update-ref", "-d", "refs/remotes/origin/a")
    git(repo, "update-ref", "-d", "refs/remotes/origin/b")
    assert start_event(repo, "s1")["branch"] == "unknown"  # 0件も unknown("HEAD" にしない)


def test_branch_on_normal_checkout(repo):
    assert start_event(repo, "s1")["branch"] == "main"


# ---- Phase 2 Task 0b: 持ち越しA群 (d) git エラー (e) ~ パス ----

from datetime import datetime, timezone  # noqa: E402

_NOW_0B = datetime(2026, 10, 7, 0, 0, 0, tzinfo=timezone.utc)


def _audit_text_0b(root):
    p = root / ".claude/experience/_audit.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _git_fails(monkeypatch, code=128):
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        if isinstance(cmd, list) and cmd[:2] == ["git", "ls-files"]:
            return subprocess.CompletedProcess(cmd, code, "", "fatal: boom")
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(experience_log.subprocess, "run", fake_run)
    experience_log._TRACKED.clear()


def test_is_tracked_untracked_exit1_writes_base(repo):
    p = experience_log.session_file(repo, "s1", _NOW_0B)
    assert p.name == "session-s1.jsonl"


def test_tracked_state_values(repo, monkeypatch):
    f = repo / "README.md"
    assert experience_log._tracked_state(repo, f) == "tracked"
    assert experience_log._is_tracked(repo, f) is True
    assert experience_log._tracked_state(repo, repo / "nope.txt") == "untracked"
    _git_fails(monkeypatch)
    assert experience_log._tracked_state(repo, repo / "nope.txt") == "error"
    assert experience_log._is_tracked(repo, repo / "nope.txt") is False


def test_tracked_state_exception_is_error(repo, monkeypatch):
    def boom(*a, **kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(experience_log.subprocess, "run", boom)
    assert experience_log._tracked_state(repo, repo / "x.txt") == "error"


def test_is_tracked_git_error_writes_part_file(repo, monkeypatch):
    _git_fails(monkeypatch)
    p = experience_log.session_file(repo, "s1", _NOW_0B)
    assert ".part1." in p.name
    # ディスク上に既にある part は飛ばす
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}\n", encoding="utf-8")
    assert ".part2." in experience_log.session_file(repo, "s1", _NOW_0B).name


def test_git_error_is_audited_once(repo, monkeypatch):
    _git_fails(monkeypatch)
    for _ in range(3):
        experience_log.session_file(repo, "s1", _NOW_0B)
    assert _audit_text_0b(repo).count("git ls-files failed") == 1


def test_sanitize_path_tilde_is_external(repo):
    assert sanitize_path("~/glow/x.md", repo) == "<external>"


def test_program_tilde_is_external(repo):
    assert experience_log._program_of("~/bin/tool --x", repo) == "<external>"
