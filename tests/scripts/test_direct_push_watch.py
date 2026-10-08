"""決裁 #26 S1: main への直接 commit の検知(scripts/direct_push_watch.py + workflow)。"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import direct_push_watch as d  # noqa: E402

WF = ".github/workflows/main-direct-push-watch.yml"
PATS = ["docs/wiki/", "scripts/memory_bootstrap.py", ".github/workflows/repo-scope.yml"]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def run(*args, cwd=ROOT):
    return subprocess.run([sys.executable, "scripts/direct_push_watch.py", *args], cwd=cwd, capture_output=True, text=True)


# ---- classify(純粋関数) ----

def test_trust_boundary_file_is_flagged():
    assert d.classify(["scripts/memory_bootstrap.py", "data/x.json"], False, PATS) == ["scripts/memory_bootstrap.py"]


def test_official_wiki_direct_child_is_flagged_even_without_prefix_pattern():
    assert d.classify(["docs/wiki/W001.md"], False, ["scripts/memory_bootstrap.py"]) == ["docs/wiki/W001.md"]


def test_wiki_candidates_and_archive_are_not_official():
    pats = ["scripts/memory_bootstrap.py"]
    assert d.classify(["docs/wiki/_candidates/c.md", "docs/wiki/_archive/old.md", "docs/wiki/_synonyms.txt"], False, pats) == []


def test_pull_request_commit_is_never_flagged():
    assert d.classify(["scripts/memory_bootstrap.py", "docs/wiki/W001.md"], True, PATS) == []


def test_unrelated_bot_update_is_not_flagged():
    assert d.classify(["data/subsidies.json", "site/themes/a.html", "reports/w.md"], False, PATS) == []


def test_directory_prefix_pattern_matches_nested_paths():
    assert d.classify(["docs/wiki/_candidates/c.md"], False, ["docs/wiki/"]) == ["docs/wiki/_candidates/c.md"]


def test_default_patterns_come_from_codeowners():
    real = d.codeowners_paths()
    assert "docs/wiki/" in real
    assert "scripts/memory_bootstrap.py" in real
    assert ".github/CODEOWNERS" in real
    assert len(real) >= 20


def test_selftest_passes():
    r = run("--selftest")
    assert r.returncode == 0, r.stdout + r.stderr


def test_cli_exit_codes(tmp_path):
    f = tmp_path / "changed.txt"
    f.write_text("scripts/memory_bootstrap.py\nREADME.md\n", encoding="utf-8")
    r = run("--files-from", str(f))
    assert r.returncode == d.EXIT_MATCHED and r.stdout.strip() == "scripts/memory_bootstrap.py"
    r = run("--files-from", str(f), "--has-pr")
    assert r.returncode == 0 and r.stdout.strip() == ""


# ---- plan / duplicates(重複防止・競合の自己修復) ----

def test_plan_distinguishes_reuse_and_new():
    existing = ["⚠️ main への直接 commit が守りの範囲を変更: 123456789", "無関係な Issue"]
    assert d.plan(existing, ["123456789aaaa", "abcdef012bbbb"]) == [("reuse", "123456789"), ("new", "abcdef012")]


def test_plan_same_sha_twice_in_one_run_is_created_once():
    assert d.plan([], ["abcdef012", "abcdef012"]) == [("new", "abcdef012"), ("reuse", "abcdef012")]


def test_duplicates_keep_oldest_and_close_newer():
    issues = [{"number": 12, "title": "x 123456789"}, {"number": 10, "title": "y 123456789"},
              {"number": 11, "title": "z abcdef012"}, {"number": 13, "title": "w 123456789"}]
    assert d.duplicates(issues) == [(12, "123456789", 10), (13, "123456789", 10)]


def test_duplicates_none_when_unique():
    assert d.duplicates([{"number": 1, "title": "a 123456789"}, {"number": 2, "title": "b abcdef012"}]) == []


def test_race_two_runs_same_snapshot_both_create_then_self_heal():
    """競合試験: 2 つの run が同じ「既存一覧」を見て両方 new と判断しても、起票後の掃除で 1 件に戻る。"""
    snapshot = []  # 両 run が見た既存 Issue(空)
    run_a = d.plan(snapshot, ["deadbeef0"])
    run_b = d.plan(snapshot, ["deadbeef0"])
    assert run_a == run_b == [("new", "deadbeef0")]  # ここまでは両方起票してしまう
    after = [{"number": 101, "title": "⚠️ …: deadbeef0"}, {"number": 102, "title": "⚠️ …: deadbeef0"}]
    assert d.duplicates(after) == [(102, "deadbeef0", 101)]  # 新しい方だけ閉じる
    # 掃除後の一覧で再計画すると reuse になる(3 回目の run は起票しない)
    assert d.plan([after[0]["title"]], ["deadbeef0"]) == [("reuse", "deadbeef0")]


def test_cli_plan_and_dups(tmp_path):
    ex = tmp_path / "existing.txt"; ex.write_text("t: 123456789\n", encoding="utf-8")
    sh = tmp_path / "shas.txt"; sh.write_text("123456789\nabcdef012\n", encoding="utf-8")
    r = run("--plan", "--existing", str(ex), "--shas", str(sh))
    assert r.returncode == 0 and r.stdout.split() == ["reuse", "123456789", "new", "abcdef012"]
    js = tmp_path / "issues.json"
    js.write_text(json.dumps([{"number": 5, "title": "a 123456789"}, {"number": 7, "title": "b 123456789"}]), encoding="utf-8")
    r = run("--dups", "--issues", str(js))
    assert r.returncode == 0 and r.stdout.strip() == "close 7 123456789 keep=5"


# ---- workflow(文字列として検査。本番設定は変えない) ----

def test_workflow_triggers_only_main_push_and_dispatch():
    t = read(WF)
    assert "pull_request_target" not in t
    assert "branches: [main]" in t
    assert "workflow_dispatch:" in t and "sha:" in t


def test_workflow_declares_minimal_permissions():
    t = read(WF)
    assert "permissions:" in t
    assert "contents: read" in t and "issues: write" in t
    assert "contents: write" not in t


def test_workflow_never_pushes_and_uses_default_token_only():
    t = read(WF)
    assert "git push" not in t
    assert "create-github-app-token" not in t
    assert "github.token" in t


def test_workflow_serializes_runs_without_cancelling():
    t = read(WF)
    assert "concurrency:" in t and "cancel-in-progress: false" in t


def test_workflow_scans_window_plus_push_range_and_fails_on_truncation():
    t = read(WF)
    assert "git log --first-parent -n" in t
    assert "compare/$BEFORE...$AFTER" in t
    assert "total_commits" in t and "検知漏れ" in t


def test_workflow_dedupes_via_issue_list_not_search():
    t = read(WF)
    assert "scripts/direct_push_watch.py --plan" in t
    assert "--limit 500 --json title" in t
    assert "--search" not in t
    assert "scripts/direct_push_watch.py --dups" in t  # 二重起票の自己修復


def test_workflow_distinguishes_reused_created_failed_and_fails_job_on_failure():
    t = read(WF)
    for k in ("reused=", "created=", "failed="):
        assert k in t
    assert '[ "$failed" -eq 0 ]' in t  # 起票失敗で step(= run)を失敗にする
    assert "GITHUB_STEP_SUMMARY" in t  # LINE が無くても GitHub 上で追える


def test_workflow_line_runs_even_if_issue_step_failed_and_only_on_new_or_failed():
    t = read(WF)
    assert "if: always() && steps.scan.outputs.found == 'true' && (steps.issue.outputs.created != '0' || steps.issue.outputs.failed != '0')" in t


def test_workflow_fails_explicitly_when_file_list_is_truncated_or_sha_missing():
    t = read(WF)
    assert '-ge 300' in t and "truncated=true" in t
    assert "if: always() && steps.scan.outputs.truncated == 'true'" in t  # Issue・LINE の後で run を失敗にする
    assert "が見つかりません" in t  # 存在しない SHA は明示的に失敗


def test_workflow_dedupe_covers_closed_issues_too():
    # 試験 Issue をクローズした後に同じ SHA を再検査しても増殖しない(--state all)
    assert "--state all --label direct-push-watch --limit 500 --json title" in read(WF)


def test_wikiskill_tests_runs_this_file():
    assert "tests/scripts/test_direct_push_watch.py" in read(".github/workflows/wikiskill-tests.yml")
