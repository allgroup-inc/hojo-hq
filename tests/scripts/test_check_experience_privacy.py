"""WikiSkill Phase 1 Task 5: check_experience_privacy.py の検査。

コミットされた Experience 記録(JSONL)が公開リポジトリに置けることを機械で証明する検査の、
正例(通る)と負例(止める)を固定する。禁止語の実文字列はここに書かず、実行時に
check_repo_scope.FORBIDDEN_CONTENT から取る(本ファイル自身も check_repo_scope の検査対象)。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import check_repo_scope  # noqa: E402
import check_experience_privacy  # noqa: E402
from check_experience_privacy import MAX_FIELD, MAX_NOTE, PUBLIC_REPO, check_record, scan  # noqa: E402
from check_experience_privacy import _label, _local_label, record_name_problem  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
# 記録ファイル名に使う識別子(session_id と同じ形の UUID。実在のセッションではない架空の値)
SID_X = "5f0c2e7a-1b3d-4e8f-9a6b-2c4d6e8f0a1b"
SID_A = "6a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
SID_B = "7b2c3d4e-5f60-4b7c-9d8e-0f1a2b3c4d5e"
SID_BAD = "8c3d4e5f-6071-4c8d-8e9f-1a2b3c4d5e6f"
SID_GOOD = "9d4e5f60-7182-4d9e-9f0a-2b3c4d5e6f70"
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


# 本物の .gitignore と同じ約束(記録はコミットする / _local と _audit.log はローカル限定)
STANDARD_GITIGNORE = ".claude/experience/_local/\n.claude/experience/_audit.log\n"


def _init_repo(root, gitignore=STANDARD_GITIGNORE):
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "remote", "add", "origin", PUBLIC_URL)
    (root / "README.md").write_text("x")
    (root / ".gitignore").write_text(gitignore, encoding="utf-8")
    git(root, "add", "README.md", ".gitignore")
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
    _commit_jsonl(tmp_path, f"session-{SID_BAD}.jsonl", json.dumps(bad) + "\n")
    return tmp_path


@pytest.fixture
def repo_with_good_jsonl(tmp_path):
    _init_repo(tmp_path)
    lines = [json.dumps(OK), json.dumps(END, ensure_ascii=False)]
    _commit_jsonl(tmp_path, f"session-{SID_GOOD}.jsonl", "\n".join(lines) + "\n")
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
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", json.dumps(OK) + "\nnot json\n")
    hits = scan(tmp_path)
    assert len(hits) == 1
    assert "2" in hits[0][1] and "JSON" in hits[0][1]


def test_scan_non_object_line_rejected(tmp_path):
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", "[1,2]\n")
    assert scan(tmp_path)


def test_scan_multiple_violations_one_tuple_each(tmp_path):
    _init_repo(tmp_path)
    bad = {**OK, "visibility": "private", "repo": "x/y"}
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", json.dumps(bad) + "\n")
    hits = scan(tmp_path)
    assert len(hits) >= 2
    assert all(h[0].endswith(f"session-{SID_X}.jsonl") for h in hits)


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
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", json.dumps(OK) + "\n\n")
    assert scan(tmp_path) == []


def test_cli_exit_codes(tmp_path):
    bad_root = tmp_path / "bad"
    good_root = tmp_path / "good"
    for r in (bad_root, good_root):
        r.mkdir()
        _init_repo(r)
    _commit_jsonl(bad_root, f"session-{SID_BAD}.jsonl", json.dumps({**OK, "visibility": "private"}) + "\n")
    _commit_jsonl(good_root, f"session-{SID_GOOD}.jsonl", json.dumps(OK) + "\n" + json.dumps(END) + "\n")

    def cli(root):
        return subprocess.run(
            [sys.executable, SCRIPT], cwd=root, capture_output=True, text=True
        )

    bad = cli(bad_root)
    assert bad.returncode == 1
    assert f"session-{SID_BAD}.jsonl" in bad.stderr and "→" in bad.stderr
    assert "docs/wikiskill/README.md" in bad.stderr
    good = cli(good_root)
    assert good.returncode == 0
    assert "OK: Experience記録 1件・違反なし" in good.stdout


def test_real_repo_runs_clean():
    r = run([])
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("OK: Experience記録")


# ---- 決裁 #26 S2 PR-D: ignore と追跡状態(2026-10-08 802a00cbf の再発を機械で止める) ----

from check_experience_privacy import EXPERIENCE_DIR, MUST_IGNORE, RECORD_PROBE, check_tracking  # noqa: E402


def _cli(root):
    return subprocess.run([sys.executable, SCRIPT], cwd=root, capture_output=True, text=True)


def test_tracking_probe_paths_are_fixed():
    # 検査対象の具体的なパスを固定する(変えるときはこのテストと .gitignore の約束を一緒に見直す)
    assert EXPERIENCE_DIR == ".claude/experience"
    assert RECORD_PROBE == ".claude/experience/2026-01/session-probe.jsonl"
    assert MUST_IGNORE == (".claude/experience/_local/probe", ".claude/experience/_audit.log")


def test_tracking_ok_with_standard_gitignore(tmp_path):
    # 正常系: 本物と同じ約束の .gitignore なら違反 0。記録ファイルが追跡されていても通る
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, f"session-{SID_GOOD}.jsonl", json.dumps(OK) + "\n")
    assert check_tracking(tmp_path) == []
    r = _cli(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ignore・追跡状態 OK" in r.stdout


def test_tracking_fails_when_record_dir_is_ignored(tmp_path):
    # 異常系 1(802a00cbf 型): .claude/experience/ 丸ごと ignore → 記録パスの違反 1 件で exit 1
    _init_repo(tmp_path, gitignore=STANDARD_GITIGNORE + ".claude/experience/\n")
    hits = check_tracking(tmp_path)
    assert [p for p, _ in hits] == [RECORD_PROBE]
    assert "記録パスを除外" in hits[0][1]
    r = _cli(tmp_path)
    assert r.returncode == 1
    assert RECORD_PROBE in r.stderr and ".claude/memory.off" in r.stderr


@pytest.mark.parametrize("pattern", [".claude/*", "**/experience/**", "*.jsonl"])
def test_tracking_catches_other_spellings_of_the_same_exclusion(tmp_path, pattern):
    # .gitignore の文字列検査ではすり抜ける書き方も、git 自身の判定なら止まる
    _init_repo(tmp_path, gitignore=STANDARD_GITIGNORE + pattern + "\n")
    assert [p for p, _ in check_tracking(tmp_path)] == [RECORD_PROBE]


def test_tracking_fails_when_local_only_paths_are_not_ignored(tmp_path):
    # 異常系 2: .gitignore が空 → _local/ と _audit.log の「ignore されていない」違反 2 件(正例・負例の両方で検査が効く)
    _init_repo(tmp_path, gitignore="")
    hits = check_tracking(tmp_path)
    assert [p for p, _ in hits] == list(MUST_IGNORE)
    assert all("ignore されていません" in why for _, why in hits)
    assert _cli(tmp_path).returncode == 1


def test_tracking_fails_when_local_only_file_is_already_tracked(tmp_path):
    # 異常系 3: ignore はされているが、_audit.log と _local/ のファイルが既に追跡されている(-f で add された)
    _init_repo(tmp_path)
    exp = tmp_path / ".claude" / "experience"
    (exp / "_local").mkdir(parents=True)
    (exp / "_audit.log").write_text("x\n", encoding="utf-8")
    (exp / "_local" / "current-session").write_text("S\n", encoding="utf-8")
    git(tmp_path, "add", "-f", ".claude/experience/_audit.log", ".claude/experience/_local/current-session")
    git(tmp_path, "commit", "-q", "-m", "oops")
    hits = check_tracking(tmp_path)
    assert sorted(p for p, _ in hits) == [".claude/experience/_audit.log", ".claude/experience/_local/current-session"]
    assert all("追跡されています" in why for _, why in hits)
    r = _cli(tmp_path)
    assert r.returncode == 1 and "git rm --cached" in r.stderr


def test_tracking_fails_closed_when_git_cannot_answer(tmp_path):
    # git リポジトリでない場所: check-ignore は「判定できない」(None)、CLI 全体は exit 1(検査できなかったことを違反なしにしない)
    from check_experience_privacy import _is_ignored
    assert _is_ignored(tmp_path, RECORD_PROBE) is None
    r = _cli(tmp_path)
    assert r.returncode == 1 and "検査できませんでした" in r.stderr


def test_tracking_ignores_user_global_excludes(tmp_path):
    # 利用者の global excludes(例: *.jsonl)で記録パスが除外されていても、コミットされた .gitignore だけを見る
    _init_repo(tmp_path)
    (tmp_path / "global_ignore").write_text("*.jsonl\n", encoding="utf-8")
    git(tmp_path, "config", "core.excludesFile", str(tmp_path / "global_ignore"))
    assert check_tracking(tmp_path) == []


# ---- 決裁 #26 S2 PR-D3: 追跡済み Experience 記録全件の ignore 判定(月・part を狙った除外を見逃さない) ----

from check_experience_privacy import _ignored_among  # noqa: E402

A_REL = f".claude/experience/2026-10/session-{SID_A}.jsonl"
PART_REL = f".claude/experience/2026-10/session-{SID_A}.part1.jsonl"


def _repo_with_two_records(tmp_path, gitignore):
    _init_repo(tmp_path, gitignore=gitignore)
    _commit_jsonl(tmp_path, f"session-{SID_A}.jsonl", json.dumps(OK) + "\n")          # _commit_jsonl は add -f(除外されていても追跡させる)
    _commit_jsonl(tmp_path, f"session-{SID_A}.part1.jsonl", json.dumps(OK) + "\n")
    return tmp_path


def _paths(hits):
    return [p for p, _ in hits]


def test_tracked_records_ok_with_standard_gitignore(tmp_path):
    # 正常系: 本物と同じ約束なら追跡済み 2 件とも違反なし。_ignored_among は空 dict(None ではない)
    _repo_with_two_records(tmp_path, STANDARD_GITIGNORE)
    assert _ignored_among(tmp_path, [A_REL, PART_REL]) == {}
    assert _ignored_among(tmp_path, []) == {}
    assert check_tracking(tmp_path) == []
    r = _cli(tmp_path)
    assert r.returncode == 0 and "ignore・追跡状態 OK" in r.stdout


def test_tracked_records_month_targeted_exclusion_is_caught(tmp_path):
    # 異常系 1: 月を狙った除外。探り用パス(2026-01)は当たらない = PR-D だけでは見逃していた壊し方
    _repo_with_two_records(tmp_path, STANDARD_GITIGNORE + ".claude/experience/2026-10/\n")
    hits = check_tracking(tmp_path)
    assert _paths(hits) == [A_REL, PART_REL]
    assert RECORD_PROBE not in _paths(hits)
    for _, why in hits:
        assert "追跡済みの記録が .gitignore で除外" in why and ".gitignore:3" in why and "2026-10/" in why
    r = _cli(tmp_path)
    assert r.returncode == 1 and A_REL in r.stderr and PART_REL in r.stderr


def test_tracked_records_part_targeted_exclusion_is_caught(tmp_path):
    # 異常系 2: part だけを狙った除外 → part の 1 件だけが違反
    _repo_with_two_records(tmp_path, STANDARD_GITIGNORE + "*.part1.jsonl\n")
    hits = check_tracking(tmp_path)
    assert _paths(hits) == [PART_REL]
    assert "`*.part1.jsonl`" in hits[0][1]
    assert _cli(tmp_path).returncode == 1


def test_tracked_records_whole_dir_exclusion_with_negation_still_caught(tmp_path):
    # 異常系 3: 丸ごと除外 + `!` で再包含したつもり。git は親ディレクトリの除外を `!` で覆せないので全件 ignore 扱い
    _repo_with_two_records(tmp_path, STANDARD_GITIGNORE + ".claude/experience/\n!.claude/experience/2026-10/\n")
    hits = check_tracking(tmp_path)
    assert _paths(hits) == [RECORD_PROBE, A_REL, PART_REL]
    assert _cli(tmp_path).returncode == 1


def test_tracked_records_japanese_and_space_path_is_handled(tmp_path):
    # 日本語・空白を含むパスでも git の判定(-z)は壊れない。名前が命名規則に合わないので、表示は伏せる
    _init_repo(tmp_path, gitignore=STANDARD_GITIGNORE + ".claude/experience/2026-11/\n")
    name = "session-日本語 空白.jsonl"
    _commit_jsonl(tmp_path, name, json.dumps(OK) + "\n", month="2026-11")
    rel = ".claude/experience/2026-11/" + name
    ignored = _ignored_among(tmp_path, [rel])
    assert list(ignored) == [rel]                       # git の判定は実際のパスで行われる
    hits = check_tracking(tmp_path)
    assert _paths(hits) == [f"<不正な記録パス: 長さ {len(rel)}>"]
    r = _cli(tmp_path)
    assert r.returncode == 1 and rel not in r.stderr and "日本語 空白" not in r.stderr


def test_tracked_records_reincluded_by_negation_are_not_flagged(tmp_path):
    # 否定パターンで正しく再包含されたファイルは違反にしない(`-v` は再包含されただけのパスも出し、終了コードも 0 になる。実測)
    gi = STANDARD_GITIGNORE + f".claude/experience/2026-10/*.jsonl\n!.claude/experience/2026-10/session-{SID_A}.jsonl\n"
    _init_repo(tmp_path, gitignore=gi)
    _commit_jsonl(tmp_path, f"session-{SID_A}.jsonl", json.dumps(OK) + "\n")   # 再包含 → 追跡されてよい
    _commit_jsonl(tmp_path, f"session-{SID_B}.jsonl", json.dumps(OK) + "\n")   # 除外されたまま(add -f で追跡)
    b_rel = f".claude/experience/2026-10/session-{SID_B}.jsonl"
    assert _ignored_among(tmp_path, [A_REL]) == {}                       # 再包含だけのパスは「ignore なし」
    ignored = _ignored_among(tmp_path, [A_REL, b_rel])
    assert list(ignored) == [b_rel] and "!" not in ignored[b_rel]
    hits = check_tracking(tmp_path)
    assert _paths(hits) == [b_rel]
    assert _cli(tmp_path).returncode == 1


def test_tracked_records_fail_closed_outside_git(tmp_path):
    # git リポジトリでなければ判定不能(None)。CLI は既存の fail-closed 経路で exit 1
    assert _ignored_among(tmp_path, [A_REL]) is None


# ---- レビュー指摘の修正 ----

def test_line_separator_chars_in_note_scan_clean(tmp_path):
    # experience_log.py は ensure_ascii=False で U+2028/U+2029/\x85 を raw のまま出力する
    _init_repo(tmp_path)
    rec = {**OK, "event": "note", "text": "a\u2028b\u2029c\x85d"}
    line = json.dumps(rec, ensure_ascii=False)
    assert "\u2028" in line and "\x85" in line  # raw で入っていること
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", line + "\n" + json.dumps(OK) + "\n")
    assert scan(tmp_path) == []


def test_crlf_lines_scan_clean(tmp_path):
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", json.dumps(OK) + "\r\n" + json.dumps(OK) + "\r\n")
    assert scan(tmp_path) == []


def test_leading_backslash_path_rejected():
    assert check_record({**OK, "path": "\\x"}, "x")
    assert check_record({**OK, "path": "\\\\srv\\share\\x"}, "x")
    assert check_record({**END, "files_changed": ["\\x"]}, "x")


def test_scan_deeply_nested_json_reported_not_crash(tmp_path):
    _init_repo(tmp_path)
    deep = "[" * 2000 + "]" * 2000
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", deep + "\n")
    hits = scan(tmp_path)
    assert len(hits) == 1 and "入れ子が深すぎます" in hits[0][1]


def test_cli_unknown_argument_exits_2():
    r = run(["--selftst"])
    assert r.returncode == 2
    assert "使い方" in r.stderr


# ---- 最終修正波: プログラム名の形 / part ファイル ----

BASH = {**OK, "tool": "Bash", "program": "python3"}
BASH.pop("path")


@pytest.mark.parametrize("program", ["python3", "git", "run_all.sh", "<unknown>", "<external>"])
def test_program_name_ok(program):
    assert check_record({**BASH, "program": program}, "x.jsonl") == []


@pytest.mark.parametrize("program", [
    "x)", "顧客A社_抽出.sh", "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx", "a" * 33, "", "with space", 5,
])
def test_program_name_rejected(program):
    problems = check_record({**BASH, "program": program}, "x.jsonl")
    assert any("program" in p for p in problems)


def test_scan_covers_part_files(tmp_path):
    _init_repo(tmp_path)
    root = tmp_path
    _commit_jsonl(root, f"session-{SID_A}.jsonl", json.dumps(OK) + "\n")
    bad = {**OK, "path": "/home/user/secret.md"}
    _commit_jsonl(root, f"session-{SID_A}.part1.jsonl", json.dumps(bad) + "\n")
    hits = scan(root)
    assert [h[0] for h in hits] == [f".claude/experience/2026-10/session-{SID_A}.part1.jsonl"]


# ---- skill_failure(P1-a・D1): 記録側が書く失敗記録を、公開可否の検査が正しく扱うこと ----

# 記録側(experience_log.build_failure_event)が書く形そのもの(架空の値)
SKILL_FAILURE_OK = {
    "ts": "2026-10-16T00:00:00Z",
    "session_id": "S",
    "event": "skill_failure",
    "repo": "allgroup-inc/hojo-hq",
    "visibility": "public",
    "branch": "main",
    "skill": "demo-skill",
    "skill_key": "0123456789ab",
    "skill_version": "1.0.0",
    "duration_ms": 40,
    "interrupted": False,
}


def test_skill_failure_is_a_valid_event():
    assert "skill_failure" in check_experience_privacy.VALID_EVENTS


def test_skill_failure_normal_record_passes():
    # 必須テスト1: 正常な skill_failure は合格する
    assert check_record(SKILL_FAILURE_OK, "x.jsonl") == []


def test_skill_failure_without_optional_fields_passes():
    rec = {k: v for k, v in SKILL_FAILURE_OK.items() if k not in ("duration_ms", "interrupted")}
    assert check_record(rec, "x.jsonl") == []


def test_skill_failure_unknown_name_next_to_it_still_rejected():
    # 必須テスト2: 未知イベントは引き続き不合格(似た名前も通さない)
    assert check_record({**SKILL_FAILURE_OK, "event": "skill_failures"}, "x")
    assert check_record({**SKILL_FAILURE_OK, "event": "skill_failed"}, "x")
    assert check_record({**SKILL_FAILURE_OK, "event": "weird"}, "x")


def test_skill_failure_absolute_path_rejected():
    # 必須テスト3: skill_failure に絶対パスが含まれると不合格
    problems = check_record({**SKILL_FAILURE_OK, "path": "/home/someone/private.txt"}, "x")
    assert problems and any("絶対パス" in p for p in problems)


@pytest.mark.parametrize("field, value", [
    ("branch", "ghp_" + "a" * 20),                          # 鍵の接頭辞
    ("branch", "sk-" + "b" * 24),                           # 鍵の接頭辞
    ("session_id", "password=hunter2hunter2"),              # 資格情報の代入
    ("session_id", "api_key: abcdef123456"),                # 資格情報の代入
    ("branch", "Bearer " + "C" * 20),                       # bearer トークン
    ("branch", "user@example.com"),                         # メールアドレス
    ("branch", "https://user:secretpw@example.com/x"),      # URL 内の資格情報
    ("branch", "A" * 40),                                   # 40 文字以上の連続トークン
])
def test_skill_failure_secret_rejected(field, value):
    # 必須テスト4: skill_failure に秘密情報が含まれると不合格
    problems = check_record({**SKILL_FAILURE_OK, field: value}, "x")
    assert problems, f"{field}={value!r} が通ってしまった"
    assert any("秘密情報らしい値" in p for p in problems)


def test_skill_failure_secret_value_not_echoed_in_reason():
    # 違反の理由(CI のログに出る)に、一致した秘密の値そのものを出さない
    secret = "ghp_" + "Z" * 20
    problems = check_record({**SKILL_FAILURE_OK, "branch": secret}, "x")
    assert problems and all(secret not in p for p in problems)


def test_skill_failure_extra_field_rejected():
    # 記録側が書かない項目(error 本文など)は、値が無害でも不合格
    problems = check_record({**SKILL_FAILURE_OK, "error": "ふつうの文章"}, "x")
    assert problems and any("許可されていない項目" in p for p in problems)


def test_skill_failure_forbidden_content_rejected():
    word = check_repo_scope.FORBIDDEN_CONTENT[0]  # 禁止語の実文字列はソースに書かない
    assert check_record({**SKILL_FAILURE_OK, "branch": f"x-{word}"}, "x")


def test_skill_failure_long_field_rejected():
    assert check_record({**SKILL_FAILURE_OK, "branch": "b" * (MAX_FIELD + 1)}, "x")


def test_existing_event_checks_unchanged_after_skill_failure_added():
    # 必須テスト5: 既存イベントの扱いは変わらない(skill・tool・note・session_end)
    assert check_record({**OK, "event": "skill", "skill": "demo-skill", "skill_key": "0123456789ab",
                         "skill_version": "1.0.0", "duration_ms": 1}, "x") == []
    assert check_record({**OK, "path": "/home/x"}, "x")  # 既存の絶対パス検査は残る
    assert check_record({**OK, "event": "note", "text": "あ" * (MAX_NOTE + 1)}, "x")  # 既存の長さ検査は残る
    assert check_record(END, "x") == []


def test_skill_failure_committed_record_scan_passes(tmp_path):
    # 必須テスト6(D1 の再現): 失敗記録を含むコミットが、未知の event として止まらないこと
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, f"session-{SID_X}.jsonl", json.dumps(SKILL_FAILURE_OK) + "\n")
    assert scan(tmp_path) == []


def test_skill_failure_committed_with_secret_scan_fails(tmp_path):
    _init_repo(tmp_path)
    bad = {**SKILL_FAILURE_OK, "branch": "ghp_" + "a" * 20}
    _commit_jsonl(tmp_path, f"session-{SID_BAD}.jsonl", json.dumps(bad) + "\n")
    hits = scan(tmp_path)
    assert hits and any("秘密情報らしい値" in reason for _, reason in hits)


def test_skill_failure_selftest_cases_are_part_of_selftest():
    # 自己点検にも skill_failure の正例・負例が入っている
    r = run(["--selftest"])
    assert r.returncode == 0, r.stderr
    assert "自己点検OK" in r.stdout


# ---- 記録ファイル名の検査(P1-b・案C): 命名規則・境界値・表示の伏せ方・内容検査の非緩和 ----

SECRET_NAME_TOKEN = "ghp_" + "a" * 20   # 架空の鍵らしい値(実在の認証情報ではない)

NAME_OK = [
    f".claude/experience/2026-10/session-{SID_A}.jsonl",
    f".claude/experience/2026-10/session-{SID_A}.part1.jsonl",
    f".claude/experience/2026-10/session-{SID_A}.part12.jsonl",
    ".claude/experience/2026-10/session-unknown-20261016T101112Z.jsonl",
    ".claude/experience/2026-01/session-unknown-20261016T101112Z.part3.jsonl",
    f".claude/experience/2026-12/session-{SID_A}.jsonl",             # 境界: 12 月
    f".claude/experience/2026-01/session-{SID_A}.jsonl",             # 境界: 1 月
]

NAME_BAD = [
    f".claude/experience/2026-10/session-{SID_A.upper()}.jsonl",     # 大文字の UUID
    ".claude/experience/2026-10/session-" + SID_A.replace("-", "") + ".jsonl",   # ハイフンなし
    ".claude/experience/2026-10/session-6a1b2c3d-4e5f.jsonl",        # 短い UUID
    f".claude/experience/2026-10/session-{SID_A}x.jsonl",            # 余計な文字
    ".claude/experience/2026-10/session-unknown-2026.jsonl",         # unknown の時刻が無い
    ".claude/experience/2026-10/session-unknown-20261016T1011Z.jsonl",  # 時刻の形が違う
    ".claude/experience/2026-10/session-a.jsonl",                    # 短い名前(旧テストの形)
    ".claude/experience/2026-10/notes.jsonl",                        # session- で始まらない
    f".claude/experience/2026-10/session-{SID_A}.part0.jsonl",       # part は 1 から
    f".claude/experience/2026-10/session-{SID_A}.part.jsonl",        # part の番号が無い
    f".claude/experience/2026-10/session-{SID_A}.part01.jsonl",      # 先頭に 0
    f".claude/experience/2026-10/session-{SID_A}.partX.jsonl",       # 番号でない
    f".claude/experience/2026-10/session-{SID_A}.part1.part2.jsonl", # part が二重
    f".claude/experience/2026-10/session-{SID_A}.json",              # 拡張子違い
    f".claude/experience/2026-00/session-{SID_A}.jsonl",             # 境界: 0 月
    f".claude/experience/2026-13/session-{SID_A}.jsonl",             # 境界: 13 月
    f".claude/experience/2026-1/session-{SID_A}.jsonl",              # 月の桁が足りない
    f".claude/experience/2026-10/extra/session-{SID_A}.jsonl",       # 余計なフォルダ
    f"docs/session-{SID_A}.jsonl",                                   # 記録の置き場所ではない
    f".claude/experience/2026-10/session-{SID_A}..jsonl",            # .. を含む
    f".claude/experience/../2026-10/session-{SID_A}.jsonl",          # .. のフォルダ
    ".claude/experience/2026-10/session-a\\b.jsonl",                 # バックスラッシュ
    f".claude/experience/2026-10/session-{SID_A} .jsonl",            # 空白
    f".claude/experience/2026-10/session-{SECRET_NAME_TOKEN}.jsonl", # 鍵らしい識別子
    ".claude/experience/2026-10/session-AKIA" + "B" * 16 + ".jsonl",  # 鍵らしい識別子(AWS 形式)
]


@pytest.mark.parametrize("rel", NAME_OK)
def test_record_name_ok(rel):
    # 必須テスト(互換): 既存の正当な命名(UUID・unknown-<時刻>・.partN)と、月・part の境界値は通る
    assert record_name_problem(rel) is None


@pytest.mark.parametrize("rel", NAME_BAD)
def test_record_name_bad_is_rejected(rel):
    # 異常系: パストラバーサル・不正なファイル名・秘密らしい識別子は拒否する
    assert record_name_problem(rel) is not None


def test_secret_name_reason_does_not_echo_the_value():
    rel = f".claude/experience/2026-10/session-{SECRET_NAME_TOKEN}.jsonl"
    why = record_name_problem(rel)
    assert "秘密情報" in why
    assert SECRET_NAME_TOKEN not in why and "ghp_" not in why


def test_label_hides_invalid_record_names_and_keeps_valid_ones():
    bad = f".claude/experience/2026-10/session-{SECRET_NAME_TOKEN}.jsonl"
    assert _label(bad) == f"<不正な記録パス: 長さ {len(bad)}>"
    assert SECRET_NAME_TOKEN not in _label(bad)
    good = f".claude/experience/2026-10/session-{SID_A}.jsonl"
    assert _label(good) == good


def test_local_label_keeps_plain_names_and_hides_secret_like_ones():
    # _local/ や _audit.log の名前には session_id が入りうる。安全な名前だけ表示する
    assert _local_label("_local/current-session") == "_local/current-session"
    assert _local_label(".claude/experience/_audit.log") == ".claude/experience/_audit.log"
    secret_local = ".claude/experience/_local/" + SECRET_NAME_TOKEN + ".ended"
    assert SECRET_NAME_TOKEN not in _local_label(secret_local)
    assert _local_label("_local/with space") == f"<ローカル限定の記録パス: 長さ {len('_local/with space')}>"


def test_scan_reports_invalid_name_redacted_and_cli_hides_it(tmp_path):
    # 異常系: 鍵らしい識別子のファイル名は、違反として止まり、名前そのものは表示されない
    _init_repo(tmp_path)
    name = f"session-{SECRET_NAME_TOKEN}.jsonl"
    _commit_jsonl(tmp_path, name, json.dumps(OK) + "\n")
    hits = scan(tmp_path)
    assert len(hits) == 1
    label, reason = hits[0]
    assert label == f"<不正な記録パス: 長さ {len('.claude/experience/2026-10/' + name)}>"
    assert "ファイル名の形式" in reason and SECRET_NAME_TOKEN not in reason
    r = _cli(tmp_path)
    assert r.returncode == 1 and "不正な記録パス" in r.stderr
    assert SECRET_NAME_TOKEN not in r.stderr and "ghp_" not in r.stderr


def test_scan_invalid_name_still_checks_content(tmp_path):
    # 名前が合わなくても、内容の検査は止まらない(検査の緩和をしない)
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, "session-notauuid.jsonl", json.dumps({**OK, "path": "/home/x/y"}) + "\n")
    hits = scan(tmp_path)
    reasons = [r for _, r in hits]
    assert any("ファイル名の形式" in r for r in reasons)
    assert any("絶対パス" in r for r in reasons)
    assert all(label.startswith("<不正な記録パス") for label, _ in hits)


def test_scan_valid_name_still_checks_content(tmp_path):
    # 名前が正しくても、内容の違反は従来どおり止まる(境界: 正しい名前で緩めない)
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, f"session-{SID_A}.jsonl", json.dumps({**OK, "visibility": "private"}) + "\n")
    hits = scan(tmp_path)
    assert len(hits) == 1 and hits[0][0] == f".claude/experience/2026-10/session-{SID_A}.jsonl"
    assert "visibility" in hits[0][1]


def test_scan_valid_names_including_part_pass(tmp_path):
    # 正常系: UUID・unknown-<時刻>・.partN の全部が、違反なしで通る
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, f"session-{SID_A}.jsonl", json.dumps(OK) + "\n")
    _commit_jsonl(tmp_path, f"session-{SID_A}.part1.jsonl", json.dumps(OK) + "\n")
    _commit_jsonl(tmp_path, "session-unknown-20261016T101112Z.jsonl", json.dumps(OK) + "\n")
    assert scan(tmp_path) == []


def test_real_repo_record_names_all_match():
    # 必須テスト(互換): 本物のリポジトリの追跡済みの記録(既存 60 件)の名前がすべて通る
    root = Path(__file__).resolve().parents[2]
    targets = [n for n in check_experience_privacy._tracked_experience(root) if check_experience_privacy._is_target(n)]
    assert targets, "追跡済みの記録が 1 件も見つからない(検査できていない)"
    assert [n for n in targets if record_name_problem(n)] == []
