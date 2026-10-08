"""決裁 #26 S2 PR-A2: wikiskill-tests を全 PR で起動し、対象外 PR はテストを省略して緑にする。

- scripts/wikiskill_scope.py の判定が GitHub Actions の paths パターンと同じ意味であること
- workflow の push: paths と PATTERNS が一致すること(二重管理のずれを止める)
- 「対象判定」step の run: 本文を一時 git リポジトリ + 本物の git で実行し、skip の判断と安全側の挙動を確かめる
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wikiskill_scope as ws  # noqa: E402
from test_direct_push_watch import run_block  # noqa: E402  PyYAML 不使用の run: 抽出

WF = ".github/workflows/wikiskill-tests.yml"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ---- パターンの意味(GitHub Actions の paths と同じ) ----

def test_star_does_not_cross_slash_and_double_star_does():
    assert ws.matches("tests/scripts/test_wiki_schema.py")
    assert not ws.matches("tests/scripts/sub/test_x.py")       # `*` は `/` に一致しない
    assert ws.matches("docs/a/b/c.md") and ws.matches("docs/x.md")  # `**` は `/` を含む
    assert not ws.matches("docs2/x.md") and not ws.matches("mydocs/x.md")


def test_literal_paths_match_exactly():
    assert ws.matches("CLAUDE.md") and not ws.matches("README.md")
    assert ws.matches(".gitignore") and not ws.matches(".gitattributes")
    assert ws.matches("scripts/wiki_schema.py") and not ws.matches("scripts/wiki_schema.pyc")
    assert ws.matches(".claude/skills/humanizer/SKILL.md") and not ws.matches(".claude/commands/brief.md")


def test_out_of_scope_examples():
    for p in ("site/index.html", "data/subsidies.json", "posts/note/x.md", "scripts/fg_seo.py", "glow-ma/src/a.gs"):
        assert not ws.matches(p), p


def test_in_scope_handles_added_deleted_modified_and_renamed_paths():
    # 削除されたパス・リネーム前のパスも「パス」として判定される(--no-renames で両方が一覧に出る前提)
    changed = ["site/a.html", "docs/old.md", "docs/new.md", "scripts/wiki_schema.py", ""]
    assert ws.in_scope(changed) == ["docs/new.md", "docs/old.md", "scripts/wiki_schema.py"]
    assert ws.in_scope(["site/a.html", "data/x.json"]) == []


def test_selftest_and_cli_exit_codes(tmp_path):
    r = subprocess.run([sys.executable, "scripts/wikiskill_scope.py", "--selftest"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    f = tmp_path / "c.txt"
    f.write_text("site/a.html\ndocs/x.md\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "scripts/wikiskill_scope.py", "--files-from", str(f)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == ws.EXIT_MATCHED and r.stdout.strip() == "docs/x.md"
    f.write_text("site/a.html\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "scripts/wikiskill_scope.py", "--files-from", str(f)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == ""


# ---- workflow との一致 ----

def test_workflow_push_paths_equal_patterns_and_pull_request_has_no_paths():
    t = read(WF)
    assert ws.workflow_push_paths(t) == ws.PATTERNS
    assert len(ws.PATTERNS) == 26  # 2026-10-08 時点の push 側 paths の実数(計画書の「28」は誤記)
    assert not ws.workflow_pull_request_has_paths(t)
    assert "\non:\n  pull_request:\n  push:\n" in t
    r = subprocess.run([sys.executable, "scripts/wikiskill_scope.py", "--check-workflow", WF], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_workflow_job_name_and_conditional_steps():
    t = read(WF)
    assert "name: wikiskill-tests-all" in t
    assert "fetch-depth: 0" in t  # 対象判定の `origin/<base>...HEAD` 差分はマージベースが要る(浅い checkout では取れない)
    assert t.count("if: steps.scope.outputs.skip != 'true'") == 4  # setup-python / pytest / git config / テスト
    assert "scripts/wikiskill_scope.py --selftest" in t and "--check-workflow" in t
    assert "--no-renames" in t  # リネームは削除+追加として両方のパスを見る
    assert "安全側" in t  # 差分取得・判定の失敗は全テスト実行
    assert "tests/scripts/test_wikiskill_scope.py" in t  # このテスト自体も CI で走る


# ---- 「対象判定」step を本物の git で実行する ----

def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args], cwd=cwd, check=True, capture_output=True)


def _repo_with_pr(tmp_path, touched_files):
    """origin(bare)に main を持ち、作業リポが head ブランチで touched_files を変えた状態を作る。"""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    (work / "scripts").mkdir()
    for f in ("wikiskill_scope.py",):
        (work / "scripts" / f).write_text((ROOT / "scripts" / f).read_text(encoding="utf-8"), encoding="utf-8")
    (work / ".github" / "workflows").mkdir(parents=True)
    (work / WF).write_text(read(WF), encoding="utf-8")
    (work / "site").mkdir(); (work / "site" / "index.html").write_text("x", encoding="utf-8")
    _git(work, "add", "-A"); _git(work, "commit", "-q", "-m", "base"); _git(work, "branch", "-M", "main"); _git(work, "push", "-q", "origin", "main")
    _git(work, "checkout", "-q", "-b", "feature")
    for rel in touched_files:
        p = work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("changed", encoding="utf-8")
    _git(work, "add", "-A"); _git(work, "commit", "-q", "-m", "change")
    return work


def _run_scope_step(work, event="pull_request", base_ref="main"):
    out = work / "out.txt"; summ = work / "summary.md"; out.touch(); summ.touch()
    env = dict(os.environ, EVENT=event, BASE_REF=base_ref, GITHUB_OUTPUT=str(out), GITHUB_STEP_SUMMARY=str(summ))
    r = subprocess.run(["bash", "-c", run_block(read(WF), "対象判定(PR")], cwd=work, env=env, capture_output=True, text=True)
    outputs = dict(l.split("=", 1) for l in out.read_text(encoding="utf-8").splitlines() if "=" in l)
    return r, outputs, summ.read_text(encoding="utf-8")


def test_scope_step_skips_when_only_out_of_scope_files_changed(tmp_path):
    work = _repo_with_pr(tmp_path, ["site/index.html", "data/x.json"])
    r, outputs, summary = _run_scope_step(work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["skip"] == "true" and "テスト省略" in summary


def test_scope_step_runs_when_a_watched_file_changed(tmp_path):
    work = _repo_with_pr(tmp_path, ["site/index.html", "docs/wiki/W001.md"])
    r, outputs, summary = _run_scope_step(work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["skip"] == "false" and "docs/wiki/W001.md" in summary


def test_scope_step_runs_when_a_watched_file_is_deleted(tmp_path):
    work = _repo_with_pr(tmp_path, ["site/index.html"])
    # ベース側にある対象ファイルを削除する PR
    (work / "docs").mkdir(exist_ok=True)
    _git(work, "checkout", "-q", "main"); (work / "docs" / "x.md").write_text("d", encoding="utf-8")
    _git(work, "add", "-A"); _git(work, "commit", "-q", "-m", "add doc"); _git(work, "push", "-q", "origin", "main")
    _git(work, "checkout", "-q", "feature"); _git(work, "merge", "-q", "main")
    _git(work, "rm", "-q", "docs/x.md"); _git(work, "commit", "-q", "-m", "delete doc")
    r, outputs, _ = _run_scope_step(work)
    assert r.returncode == 0 and outputs["skip"] == "false"


def test_scope_step_falls_back_to_full_run_when_base_is_missing(tmp_path):
    work = _repo_with_pr(tmp_path, ["site/index.html"])
    r, outputs, summary = _run_scope_step(work, base_ref="no-such-branch")
    assert r.returncode == 0 and outputs["skip"] == "false"
    assert "安全側" in summary and "::warning::" in r.stdout


def test_scope_step_never_skips_on_push_or_dispatch(tmp_path):
    work = _repo_with_pr(tmp_path, ["site/index.html"])
    for ev in ("push", "workflow_dispatch"):
        r, outputs, _ = _run_scope_step(work, event=ev)
        assert r.returncode == 0 and outputs["skip"] == "false", ev
