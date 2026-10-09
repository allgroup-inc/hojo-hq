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
    _commit_jsonl(tmp_path, "session-good.jsonl", json.dumps(OK) + "\n")
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

A_REL = ".claude/experience/2026-10/session-a.jsonl"
PART_REL = ".claude/experience/2026-10/session-a.part1.jsonl"


def _repo_with_two_records(tmp_path, gitignore):
    _init_repo(tmp_path, gitignore=gitignore)
    _commit_jsonl(tmp_path, "session-a.jsonl", json.dumps(OK) + "\n")          # _commit_jsonl は add -f(除外されていても追跡させる)
    _commit_jsonl(tmp_path, "session-a.part1.jsonl", json.dumps(OK) + "\n")
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
    # 日本語・空白を含むパスが壊れずに違反として出る(-z の固定)
    _init_repo(tmp_path, gitignore=STANDARD_GITIGNORE + ".claude/experience/2026-11/\n")
    _commit_jsonl(tmp_path, "session-日本語 空白.jsonl", json.dumps(OK) + "\n", month="2026-11")
    rel = ".claude/experience/2026-11/session-日本語 空白.jsonl"
    hits = check_tracking(tmp_path)
    assert _paths(hits) == [rel]
    r = _cli(tmp_path)
    assert r.returncode == 1 and rel in r.stderr


def test_tracked_records_reincluded_by_negation_are_not_flagged(tmp_path):
    # 否定パターンで正しく再包含されたファイルは違反にしない(`-v` は再包含されただけのパスも出し、終了コードも 0 になる。実測)
    gi = STANDARD_GITIGNORE + ".claude/experience/2026-10/*.jsonl\n!.claude/experience/2026-10/session-a.jsonl\n"
    _init_repo(tmp_path, gitignore=gi)
    _commit_jsonl(tmp_path, "session-a.jsonl", json.dumps(OK) + "\n")   # 再包含 → 追跡されてよい
    _commit_jsonl(tmp_path, "session-b.jsonl", json.dumps(OK) + "\n")   # 除外されたまま(add -f で追跡)
    b_rel = ".claude/experience/2026-10/session-b.jsonl"
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
    _commit_jsonl(tmp_path, "session-sep.jsonl", line + "\n" + json.dumps(OK) + "\n")
    assert scan(tmp_path) == []


def test_crlf_lines_scan_clean(tmp_path):
    _init_repo(tmp_path)
    _commit_jsonl(tmp_path, "session-crlf.jsonl", json.dumps(OK) + "\r\n" + json.dumps(OK) + "\r\n")
    assert scan(tmp_path) == []


def test_leading_backslash_path_rejected():
    assert check_record({**OK, "path": "\\x"}, "x")
    assert check_record({**OK, "path": "\\\\srv\\share\\x"}, "x")
    assert check_record({**END, "files_changed": ["\\x"]}, "x")


def test_scan_deeply_nested_json_reported_not_crash(tmp_path):
    _init_repo(tmp_path)
    deep = "[" * 2000 + "]" * 2000
    _commit_jsonl(tmp_path, "session-deep.jsonl", deep + "\n")
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
    _commit_jsonl(root, "session-A.jsonl", json.dumps(OK) + "\n")
    bad = {**OK, "path": "/home/user/secret.md"}
    _commit_jsonl(root, "session-A.part1.jsonl", json.dumps(bad) + "\n")
    hits = scan(root)
    assert [h[0] for h in hits] == [".claude/experience/2026-10/session-A.part1.jsonl"]
