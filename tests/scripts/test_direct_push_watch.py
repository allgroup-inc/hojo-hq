"""決裁 #26 S1: main への直接 commit の検知(scripts/direct_push_watch.py + workflow)。"""
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
    r = subprocess.run([sys.executable, "scripts/direct_push_watch.py", "--selftest"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cli_exit_codes(tmp_path):
    f = tmp_path / "changed.txt"
    f.write_text("scripts/memory_bootstrap.py\nREADME.md\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "scripts/direct_push_watch.py", "--files-from", str(f)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == d.EXIT_MATCHED and r.stdout.strip() == "scripts/memory_bootstrap.py"
    r = subprocess.run([sys.executable, "scripts/direct_push_watch.py", "--files-from", str(f), "--has-pr"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == ""


# ---- workflow(文字列として検査。本番設定は変えない) ----

def test_workflow_triggers_only_main_push_and_dispatch():
    t = read(WF)
    assert "pull_request_target" not in t
    assert "branches: [main]" in t or "branches:\n      - main" in t
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


def test_workflow_calls_classifier_and_dedupes_issues():
    t = read(WF)
    assert "scripts/direct_push_watch.py --files-from" in t
    assert "direct-push-watch" in t  # ラベル
    assert "--search" in t  # 同じ commit の重複起票なし


def test_wikiskill_tests_runs_this_file():
    assert "tests/scripts/test_direct_push_watch.py" in read(".github/workflows/wikiskill-tests.yml")
