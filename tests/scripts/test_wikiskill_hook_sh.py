"""WikiSkill Phase 1 Task 2: .claude/hooks/wikiskill-hook.sh の検査(実 subprocess)。

停止スイッチが Python より前に効くこと、Python が壊れても exit 0 + systemMessage になること、
常に妥当な JSON を出すこと、500ms 以内で終わることを固定する。
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REAL_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    git(tmp_path, "config", "commit.gpgsign", "false")
    git(tmp_path, "remote", "add", "origin", PUBLIC_URL)
    (tmp_path / "README.md").write_text("x")
    git(tmp_path, "add", "README.md")
    git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".claude/hooks").mkdir(parents=True)
    for rel in ("scripts/wikiskill_common.py", "scripts/experience_log.py",
                "scripts/decision_memory.py", "scripts/memory_bootstrap.py",  # Task 4: SessionStart/UserPromptSubmit で使う
                ".claude/hooks/wikiskill-hook.sh"):
        shutil.copy(REAL_ROOT / rel, tmp_path / rel)
    return tmp_path


def run_hook(repo, event, payload, env=None):
    e = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    e.pop("HOJO_MEMORY_OFF", None)
    e.update(env or {})
    return subprocess.run(
        ["bash", ".claude/hooks/wikiskill-hook.sh", event],
        input=json.dumps(payload), cwd=repo, env=e, capture_output=True, text=True,
    )


def read_session(repo, sid):
    files = list((repo / ".claude/experience").glob(f"*/session-{sid}.jsonl"))
    assert files, f"session-{sid}.jsonl not found"
    return files[0].read_text(encoding="utf-8")


def start_payload(repo, sid="A"):
    return {"session_id": sid, "hook_event_name": "SessionStart", "source": "startup", "cwd": str(repo)}


def test_session_start_writes_record(repo):
    r = run_hook(repo, "SessionStart", start_payload(repo))
    assert r.returncode == 0
    assert list((repo / ".claude/experience").glob("*/session-A.jsonl"))
    assert r.stdout.strip() == "{}"  # 成功時は偽の失敗警告を出さない


def test_hook_tolerates_missing_session_id(repo):
    r = run_hook(repo, "SessionStart", {"hook_event_name": "SessionStart"})
    assert r.returncode == 0
    assert "unknown-" in next((repo / ".claude/experience").glob("*/session-unknown-*.jsonl")).name
    assert "session_id" in (repo / ".claude/experience/_audit.log").read_text()


def test_disabled_by_memory_off_file(repo):
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude/memory.off").touch()
    r = run_hook(repo, "SessionStart", start_payload(repo))
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert not (repo / ".claude/experience").exists()


def test_post_tool_use_bash(repo):
    r = run_hook(repo, "PostToolUse", {"session_id": "A", "tool_name": "Bash",
                                       "tool_input": {"command": "python3 x.py --secret"}})
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    text = read_session(repo, "A")
    assert '"program": "python3"' in text and "--secret" not in text


def test_session_end_without_commits(repo):
    run_hook(repo, "SessionStart", start_payload(repo))
    r = run_hook(repo, "SessionEnd", {"session_id": "A", "reason": "exit"})
    assert r.returncode == 0
    last = json.loads(read_session(repo, "A").splitlines()[-1])
    assert last["event"] == "session_end" and last["commits"] == []
    assert (repo / ".claude/experience/_local/A.ended").exists()


def test_python_failure_is_reported_not_silent(repo):
    (repo / "scripts/experience_log.py").write_text("raise SystemExit(3)")
    r = run_hook(repo, "SessionStart", start_payload(repo))
    assert r.returncode == 0
    assert "systemMessage" in r.stdout
    assert "exit=3" in json.loads(r.stdout)["systemMessage"]


@pytest.mark.skipif(os.environ.get("WIKISKILL_SKIP_TIMING") == "1", reason="timing is environment-dependent; measured locally")
def test_hook_runtime_under_500ms(repo):
    payload = {"session_id": "A", "tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    t = time.perf_counter()
    r = run_hook(repo, "PostToolUse", payload)
    elapsed = time.perf_counter() - t
    assert r.returncode == 0
    assert elapsed < 0.5, f"hook took {elapsed:.3f}s"


# ---- 停止スイッチ・失敗系(ラッパ自身の不変条件) ----

def test_stop_switch_wins_even_when_python_is_broken(repo):
    (repo / ".claude/memory.off").touch()
    (repo / "scripts/experience_log.py").write_text("raise SystemExit(3)")
    r = run_hook(repo, "SessionStart", start_payload(repo))
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert not (repo / ".claude/experience").exists()


@pytest.mark.parametrize("value", ["1", "true", "YES", " On "])
def test_stop_switch_by_env_var(repo, value):
    r = run_hook(repo, "SessionStart", start_payload(repo), env={"HOJO_MEMORY_OFF": value})
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert not (repo / ".claude/experience").exists()


def test_falsy_env_var_does_not_stop_recording(repo):
    r = run_hook(repo, "SessionStart", start_payload(repo), env={"HOJO_MEMORY_OFF": "0"})
    assert r.returncode == 0 and r.stdout.strip() == "{}"
    assert list((repo / ".claude/experience").glob("*/session-A.jsonl"))


def test_python_missing_is_reported_and_exits_0(repo, tmp_path_factory):
    bindir = tmp_path_factory.mktemp("bin")
    for tool in ("cat", "date", "mkdir", "tr", "git"):
        found = shutil.which(tool)
        assert found, tool
        (bindir / tool).symlink_to(found)
    bash = shutil.which("bash")
    r = subprocess.run(
        [bash, ".claude/hooks/wikiskill-hook.sh", "SessionStart"],
        input=json.dumps(start_payload(repo)), cwd=repo, capture_output=True, text=True,
        env={"PATH": str(bindir), "CLAUDE_PROJECT_DIR": str(repo)},
    )
    assert r.returncode == 0
    assert "systemMessage" in json.loads(r.stdout)
    audit = (repo / ".claude/experience/_audit.log").read_text()
    assert "\thook-wrapper\t" in audit and "SessionStart" in audit


def test_python_exit0_with_empty_stdout_is_reported(repo):
    (repo / "scripts/experience_log.py").write_text("")
    r = run_hook(repo, "SessionStart", start_payload(repo))
    assert r.returncode == 0
    assert "systemMessage" in json.loads(r.stdout)
    assert "empty stdout" in (repo / ".claude/experience/_audit.log").read_text()


def test_python_exit0_with_non_json_stdout_is_reported(repo):
    (repo / "scripts/experience_log.py").write_text("print('hello not json')")
    r = run_hook(repo, "SessionStart", start_payload(repo))
    assert r.returncode == 0
    assert "systemMessage" in json.loads(r.stdout)
    assert "non-JSON stdout" in (repo / ".claude/experience/_audit.log").read_text()


def test_python_nonzero_exit_is_audited(repo):
    (repo / "scripts/experience_log.py").write_text("raise SystemExit(3)")
    run_hook(repo, "SessionStart", start_payload(repo))
    line = (repo / ".claude/experience/_audit.log").read_text().strip().splitlines()[-1]
    assert "\thook-wrapper\tSessionStart exit=3 " in line


def test_unwritable_audit_never_breaks_wrapper(repo):
    (repo / ".claude/experience").mkdir(parents=True)
    (repo / ".claude/experience/_audit.log").mkdir()  # ファイルの場所がディレクトリ → 追記不可
    (repo / "scripts/experience_log.py").write_text("raise SystemExit(3)")
    r = run_hook(repo, "SessionStart", start_payload(repo))
    assert r.returncode == 0 and "systemMessage" in json.loads(r.stdout)


def test_user_prompt_submit_prints_empty_json(repo):
    r = run_hook(repo, "UserPromptSubmit", {"session_id": "A", "prompt": "x"})
    assert r.returncode == 0 and r.stdout.strip() == "{}"


def test_non_ascii_payload_returns_valid_json(repo):
    cwd = str(repo / "沖縄企業のミカタ")
    payload = {"session_id": "A", "hook_event_name": "SessionStart", "source": "startup", "cwd": cwd}
    e = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    e.pop("HOJO_MEMORY_OFF", None)
    r = subprocess.run(
        ["bash", ".claude/hooks/wikiskill-hook.sh", "SessionStart"],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), cwd=repo, env=e,
        capture_output=True,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout.decode("utf-8")) == {}
    assert list((repo / ".claude/experience").glob("*/session-A.jsonl"))
