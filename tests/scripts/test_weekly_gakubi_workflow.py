"""weekly-gakubi.yml の構造検査(CI 赤 9 件 PR-A / 決裁キュー #22)。

生成の前に禁止語ガードのテスト(tests/scripts/test_weekly_gakubi.py)を毎回走らせ、失敗したら生成・commit に進まない
ことを YAML の並びで保証する。実行はしない(ネットワーク・API キー不要)。
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows" / "weekly-gakubi.yml"
TEST_FILE = "tests/scripts/test_weekly_gakubi.py"


def _steps():
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    return doc, doc["jobs"]["gakubi"]["steps"]


def _index_of(steps, pred):
    for i, s in enumerate(steps):
        if pred(s):
            return i
    return None


def _step(steps, pred, label):
    """条件に合う step を 1 つ返す。無ければ分かりやすい失敗メッセージで止める(StopIteration にしない)。"""
    found = [s for s in steps if pred(s)]
    assert len(found) == 1, f"{label}: 該当 step が {len(found)} 件(1 件のはず)"
    return found[0]


def _disabled(step):
    """step が `if: false`(YAML では bool の False になる)や `if: ${{ false }}` で無効化されているか。"""
    v = step.get("if", "")
    return str(v).strip().lower().replace(" ", "") in ("false", "${{false}}")


def _is_guard_step(s):
    return TEST_FILE in (s.get("run") or "") and "pytest" in (s.get("run") or "")


def test_pytest_step_runs_guard_tests_before_generation():
    _, steps = _steps()
    i_self = _index_of(steps, lambda s: "--self-test" in (s.get("run") or ""))
    i_pytest = _index_of(steps, _is_guard_step)
    i_gen = _index_of(steps, lambda s: s.get("name") == "Generate weekly digest")
    i_commit = _index_of(steps, lambda s: s.get("name") == "Commit digest")
    assert None not in (i_self, i_pytest, i_gen, i_commit), (i_self, i_pytest, i_gen, i_commit)
    assert i_self < i_pytest < i_gen < i_commit, (i_self, i_pytest, i_gen, i_commit)


def test_pytest_step_has_no_condition_so_failure_stops_the_job():
    doc, steps = _steps()
    step = _step(steps, _is_guard_step, "Guard tests")
    assert "if" not in step
    assert "continue-on-error" not in step
    gen = _step(steps, lambda s: s.get("name") == "Generate weekly digest", "Generate")
    assert "if" not in gen and "continue-on-error" not in gen  # ガードの失敗が生成へ波及する前提
    assert "continue-on-error" not in doc["jobs"]["gakubi"]  # job 単位でも失敗を握りつぶさない


def test_pytest_is_installed_before_use():
    _, steps = _steps()
    i_install = _index_of(steps, lambda s: re.search(r"pip install[^\n]*\bpytest\b", s.get("run") or "") is not None)
    i_pytest = _index_of(steps, lambda s: TEST_FILE in (s.get("run") or ""))
    assert i_install is not None and i_pytest is not None and i_install < i_pytest


def test_commit_step_still_only_runs_on_success_and_not_on_push():
    _, steps = _steps()
    commit = _step(steps, lambda s: s.get("name") == "Commit digest", "Commit digest")
    assert commit.get("if") == "github.event_name != 'push'"  # success() が暗黙に付く = 生成が失敗したら push しない


def test_push_trigger_covers_the_guard_and_its_inputs():
    doc, _ = _steps()
    paths = doc[True]["push"]["paths"] if True in doc else doc["on"]["push"]["paths"]
    for p in ("scripts/weekly_gakubi.py", TEST_FILE, "scripts/check_repo_scope.py", ".github/workflows/weekly-gakubi.yml"):
        assert p in paths, p


def test_guard_test_file_exists():
    assert (ROOT / TEST_FILE).exists()


def test_workflow_has_no_body_display_env():
    """dry-run の本文表示を有効にする env は workflow のどこにも無い(案 A: 本文は公開ログに出さない)。"""
    text = WF.read_text(encoding="utf-8")
    assert "SHOW_BODY" not in text
    _, steps = _steps()
    for s in steps:
        assert "SHOW_BODY" not in " ".join(str(k) for k in (s.get("env") or {}).keys())


# ---------------------------------------------------------------- PR 時の CI(wikiskill-tests)への登録

WIKISKILL_WF = ROOT / ".github" / "workflows" / "wikiskill-tests.yml"
THIS_FILE = "tests/scripts/test_weekly_gakubi_workflow.py"


def _wikiskill_steps():
    """wikiskill-tests.yml の最初の job の steps(コメントではなく実際の run: を見るために YAML として読む)。"""
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(WIKISKILL_WF.read_text(encoding="utf-8"))
    job = next(iter(doc["jobs"].values()))
    return job["steps"]


def test_both_test_files_run_in_wikiskill_tests_on_pull_requests():
    """新しい検査は PR 時に自動実行されなければ将来の変更を守れない(2026-10-12 小柳さん判断で PR-A に同梱)。

    ファイル全体の部分一致ではなく、pytest を走らせる step の run: のトークンで確かめる(コメントに名前があっても通らない)。
    """
    steps = _wikiskill_steps()
    step = _step(steps, lambda s: s.get("name") == "WikiSkill のテスト", "WikiSkill のテスト")
    tokens = (step.get("run") or "").split()
    assert tokens[:3] == ["python3", "-m", "pytest"], tokens[:3]
    assert TEST_FILE in tokens
    assert THIS_FILE in tokens
    assert not _disabled(step) and "continue-on-error" not in step


GUARD_PATHS = ("scripts/weekly_gakubi.py", ".github/workflows/weekly-gakubi.yml")


def test_guard_paths_are_in_wikiskill_scope_patterns():
    """ガード自体(スクリプト・workflow)だけを変える PR でも wikiskill-tests が省略されないこと(2026-10-12 PR-A のレビュー指摘)。

    対象判定は scripts/wikiskill_scope.py の PATTERNS で行い、push 側 paths は --check-workflow で同一を強制される。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import wikiskill_scope as ws

    for p in GUARD_PATHS:
        assert p in ws.PATTERNS, p
        assert ws.matches(p), p
    assert ws.workflow_push_paths(WIKISKILL_WF.read_text(encoding="utf-8")) == ws.PATTERNS


def test_guard_only_change_is_not_skipped_by_scope_step(tmp_path):
    """対象判定 step と同じ呼び方(--files-from)で、ガードのファイルだけの変更が exit 3(対象あり)になる。"""
    listing = tmp_path / "changed.txt"
    for p in GUARD_PATHS:
        listing.write_text(p + "\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "wikiskill_scope.py"), "--files-from", str(listing)],
            capture_output=True, text=True, cwd=ROOT,
        )
        assert proc.returncode == 3, (p, proc.returncode, proc.stdout, proc.stderr)


def test_wikiskill_tests_installs_pyyaml_for_the_workflow_test():
    """この構造テストは PyYAML を使う(無ければ skip して緑に見えてしまう)ので、runner に明示的に入れる。

    pyyaml を入れる step が、テスト step より前にあり、無効化(if: false)されていないことまで見る。
    """
    steps = _wikiskill_steps()
    i_install = _index_of(
        steps,
        lambda s: re.search(r"pip install[^\n]*\bpyyaml\b", s.get("run") or "", flags=re.IGNORECASE) is not None
        and not _disabled(s),
    )
    i_tests = _index_of(steps, lambda s: s.get("name") == "WikiSkill のテスト")
    assert i_install is not None, "pip install に pyyaml が無い(または無効化されている)"
    assert i_tests is not None and i_install < i_tests, (i_install, i_tests)
