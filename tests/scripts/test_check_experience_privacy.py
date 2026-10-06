"""WikiSkill Phase 1 Task 5: check_experience_privacy.py の検査。

コミットされた Experience 記録(JSONL)が公開リポジトリに置けることを機械で証明する検査の、
正例(通る)と負例(止める)を固定する。禁止語の実文字列はここに書かず、実行時に
check_repo_scope.FORBIDDEN_CONTENT から取る(本ファイル自身も check_repo_scope の検査対象)。
"""
import json
import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import check_repo_scope  # noqa: E402
import check_experience_privacy  # noqa: E402
from check_experience_privacy import MAX_FIELD, MAX_NOTE, PUBLIC_REPO, check_record, scan  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
SCRIPT = os.path.join(SCRIPTS, "check_experience_privacy.py")

OK = {
    "ts": "2026-10-06T00:00:00Z",
    "session_id": "A",
    "event": "tool",
    "repo": "allgroup-inc/hojo-hq",
    "visibility": "public",
    "branch": "main",
    "tool": "Edit",
    "path": "docs/a.md",
}
END = {
    "ts": "2026-10-06T00:10:00Z",
    "session_id": "A",
    "event": "session_end",
    "repo": "allgroup-inc/hojo-hq",
    "visibility": "public",
    "branch": "main",
    "reason": "other",
    "duration_s": 600,
    "tools": {"Edit": 2, "Bash": 1},
    "skills": ["brainstorming"],
    "commits": [{"sha": "abc1234", "subject": "feat: add a thing"}],
    "files_changed": ["docs/a.md", "scripts/x.py"],
}


def run(args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args], capture_output=True, text=True
    )


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(root):
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "remote", "add", "origin", PUBLIC_URL)
    (root / "README.md").write_text("x")
    git(root, "add", "README.md")
    git(root, "commit", "-q", "-m", "init")


def _commit_jsonl(root, name, text, month="2026-10"):
    d = root / ".claude" / "experience" / month
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(text, encoding="utf-8")
    git(root, "add", "-f", str(f.relative_to(root)))
    git(root, "commit", "-q", "-m", f"add {name}")
    return f


@pytest.fixture
def repo_with_bad_jsonl(tmp_path):
    _init_repo(tmp_path)
    bad = {**OK, "visibility": "private"}
    _commit_jsonl(tmp_path, "session-bad.jsonl", json.dumps(bad) + "\n")
    return tmp_path


@pytest.fixture
def repo_with_good_jsonl(tmp_path):
    _init_repo(tmp_path)
    lines = [json.dumps(OK), json.dumps(END, ensure_ascii=False)]
    _commit_jsonl(tmp_path, "session-good.jsonl", "\n".join(lines) + "\n")
    return tmp_path


# ---- 定数 ----

def test_constants():
    assert PUBLIC_REPO == "allgroup-inc/hojo-hq"
    assert MAX_FIELD == 500
    assert MAX_NOTE == 1000


# ---- ブリーフの10テスト ----

def test_ok_record():
    assert check_record(OK, "x.jsonl") == []


def test_private_visibility_rejected():
    assert check_record({**OK, "visibility": "private"}, "x")


def test_other_repo_rejected():
    assert check_record({**OK, "repo": "allgroup-inc/glow-docs-private"}, "x")


def test_absolute_path_rejected():
    assert check_record({**OK, "path": "/home/user/x"}, "x")


def test_external_placeholder_ok():
    assert check_record({**OK, "path": "<external>"}, "x") == []


def test_long_field_rejected():
    assert check_record({**OK, "path": "a" * 501}, "x")


def test_note_up_to_1000_ok():
    assert check_record({**OK, "event": "note", "text": "あ" * 1000}, "x") == []


def test_forbidden_content_rejected():
    word = check_repo_scope.FORBIDDEN_CONTENT[0]
    assert check_record({**OK, "event": "note", "text": f"環境変数 {word} を"}, "x")


def test_selftest_passes():
    r = run(["--selftest"])
    assert r.returncode == 0, r.stderr
    assert "自己点検OK" in r.stdout


def test_scan_reports_file_and_reason(repo_with_bad_jsonl):
    hits = scan(repo_with_bad_jsonl)
    assert hits and hits[0][0].endswith(".jsonl")
    assert "visibility" in hits[0][1]


# ---- 追加: コントローラ決定 ----

def test_end_record_ok():
    assert check_record(END, "x.jsonl") == []


def test_unknown_placeholder_ok():
    assert check_record({**OK, "path": "<unknown>"}, "x") == []


def test_note_over_1000_rejected():
    assert check_record({**OK, "event": "note", "text": "あ" * 1001}, "x")


def test_non_note_string_over_500_rejected_even_for_other_keys():
    assert check_record({**OK, "branch": "b" * 501}, "x")


def test_nested_path_in_files_changed_rejected():
    rec = {**END, "files_changed": ["docs/a.md", "/etc/passwd"]}
    assert check_record(rec, "x")


def test_dotdot_component_rejected():
    assert check_record({**OK, "path": "docs/../../etc/x"}, "x")
    assert check_record({**OK, "path": ".."}, "x")


def test_dotdot_inside_name_is_ok():
    assert check_record({**OK, "path": "docs/a..b.md"}, "x") == []


def test_tilde_path_rejected():
    assert check_record({**OK, "path": "~/secret"}, "x")


def test_windows_drive_rejected():
    assert check_record({**OK, "path": "C:\\Users\\x"}, "x")
    assert check_record({**OK, "path": "d:/work/x"}, "x")


def test_files_changed_dotdot_and_drive_rejected():
    assert check_record({**END, "files_changed": ["../x"]}, "x")
    assert check_record({**END, "files_changed": ["C:/x"]}, "x")


def test_invalid_event_name_rejected():
    assert check_record({**OK, "event": "weird"}, "x")
    bad = dict(OK)
    del bad["event"]
    assert check_record(bad, "x")


@pytest.mark.parametrize(
    "ev", ["session_start", "session_resume", "tool", "skill", "note", "session_end"]
)
def test_all_valid_event_names_ok(ev):
    assert check_record({**OK, "event": ev}, "x") == []


def test_nested_long_string_in_commits_rejected():
    rec = {**END, "commits": [{"sha": "abc1234", "subject": "s" * 501}]}
    assert check_record(rec, "x")


def test_nested_long_skill_name_rejected():
    assert check_record({**END, "skills": ["k" * 501]}, "x")


def test_nested_forbidden_content_rejected():
    word = check_repo_scope.FORBIDDEN_CONTENT[0]
    rec = {**END, "commits": [{"sha": "abc1234", "subject": f"fix {word}"}]}
    assert check_record(rec, "x")


def test_non_dict_record_rejected():
    assert check_record(["a"], "x")
    assert check_record("a", "x")
    assert check_record(None, "x")


def test_scan_ok_repo(repo_with_good_jsonl):
    assert scan(repo_with_good_jsonl) == []


def test_scan_no_experience_dir(tmp_path):
    _init_repo(tmp_path)
    assert scan(tmp_path) == []


def test_scan_non_json_line_reports_line_number(tmp_path):
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, "session-x.jsonl", json.dumps(OK) + "\nnot json\n")
    hits = scan(tmp_path)
    assert len(hits) == 1
    assert "2" in hits[0][1] and "JSON" in hits[0][1]


def test_scan_non_object_line_rejected(tmp_path):
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, "session-x.jsonl", "[1,2]\n")
    assert scan(tmp_path)


def test_scan_multiple_violations_one_tuple_each(tmp_path):
    _init_repo(tmp_path)
    bad = {**OK, "visibility": "private", "repo": "x/y"}
    _commit_jsonl(tmp_path, "session-x.jsonl", json.dumps(bad) + "\n")
    hits = scan(tmp_path)
    assert len(hits) >= 2
    assert all(h[0].endswith("session-x.jsonl") for h in hits)


def test_scan_skips_non_jsonl_and_audit_and_local(tmp_path):
    _init_repo(tmp_path)
    exp = tmp_path / ".claude" / "experience"
    (exp / "_local").mkdir(parents=True)
    (exp / "_local" / "a.jsonl").write_text("not json\n")
    (exp / "_audit.log").write_text("not json\n")
    (exp / "README.md").write_text("not json\n")
    git(tmp_path, "add", "-f", ".claude/experience")
    git(tmp_path, "commit", "-q", "-m", "x")
    assert scan(tmp_path) == []


def test_scan_ignores_untracked_jsonl(tmp_path):
    _init_repo(tmp_path)
    d = tmp_path / ".claude" / "experience" / "2026-10"
    d.mkdir(parents=True)
    (d / "session-u.jsonl").write_text("not json\n")  # 追跡されていない
    assert scan(tmp_path) == []


def test_scan_blank_lines_ignored(tmp_path):
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, "session-x.jsonl", json.dumps(OK) + "\n\n")
    assert scan(tmp_path) == []


def test_cli_exit_codes(tmp_path):
    bad_root = tmp_path / "bad"
    good_root = tmp_path / "good"
    for r in (bad_root, good_root):
        r.mkdir()
        _init_repo(r)
    _commit_jsonl(bad_root, "session-bad.jsonl", json.dumps({**OK, "visibility": "private"}) + "\n")
    _commit_jsonl(good_root, "session-good.jsonl", json.dumps(OK) + "\n" + json.dumps(END) + "\n")

    def cli(root):
        return subprocess.run(
            [sys.executable, SCRIPT], cwd=root, capture_output=True, text=True
        )

    bad = cli(bad_root)
    assert bad.returncode == 1
    assert "session-bad.jsonl" in bad.stderr and "→" in bad.stderr
    assert "docs/wikiskill/README.md" in bad.stderr
    good = cli(good_root)
    assert good.returncode == 0
    assert "OK: Experience記録 1件・違反なし" in good.stdout


def test_real_repo_runs_clean():
    r = run([])
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("OK: Experience記録")
