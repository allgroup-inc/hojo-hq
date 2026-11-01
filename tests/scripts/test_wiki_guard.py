"""決裁 #26 S2 PR-B: wiki-guard(scripts/wiki_guard.py + repo-scope.yml の 1 step)。

- 純粋関数 violations(): 正式 Wiki(docs/wiki/*.md 直下)× PR 作者 = Claude 用アカウント のときだけ違反
- 休眠: claude_login が空なら常に違反なし / workflow の step は vars.HOJO_CLAUDE_LOGIN が空なら skipped(if:)かつ本文先頭で exit 0
- step の run: 本文を偽 gh と一緒に bash で実行し、違反・通過・API 失敗・取得不完全(fail-closed)を固定する
- 既存の guard 7 step・check 名・トリガーが PR-B で変わっていないことを固定する(休眠時の無害性)
"""
import os
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wiki_guard as wg  # noqa: E402
from test_direct_push_watch import run_block  # noqa: E402  PyYAML 不使用の run: 抽出

RS = ".github/workflows/repo-scope.yml"
STEP = "wiki-guard"
CLAUDE, HUMAN = "claude-hojo", "takeshikoyanagi9-lab"
W1 = "docs/wiki/W001.md"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def run(*args):
    return subprocess.run([sys.executable, "scripts/wiki_guard.py", *args], cwd=ROOT, capture_output=True, text=True)


# ---- 純粋関数 ----

def test_official_wiki_changed_by_claude_is_flagged():
    assert wg.violations([W1, "docs/a.md"], CLAUDE, CLAUDE) == [W1]


def test_candidates_archive_and_synonyms_are_not_official():
    files = ["docs/wiki/_candidates/c.md", "docs/wiki/_archive/old.md", "docs/wiki/_synonyms.txt", "docs/wiki/README.txt"]
    assert wg.violations(files, CLAUDE, CLAUDE) == []
    assert not any(wg.is_official_wiki(f) for f in files)


def test_other_author_passes():
    assert wg.violations([W1], HUMAN, CLAUDE) == []


def test_dormant_when_claude_login_is_empty():
    assert wg.violations([W1], CLAUDE, "") == []
    assert wg.violations([W1], CLAUDE, "   ") == []
    assert wg.violations([W1], CLAUDE, None) == []


def test_app_bot_author_passes():
    assert wg.violations([W1], "hojo-app[bot]", CLAUDE) == []
    assert wg.violations([W1], "github-actions[bot]", CLAUDE) == []


def test_only_direct_children_of_docs_wiki_count():
    files = [W1, "docs/x.md", "docs/wiki/sub/W002.md", "docs/wikis/W003.md", "docs/wiki/", "docs/wiki/W004.markdown"]
    assert wg.violations(files, CLAUDE, CLAUDE) == [W1]


def test_login_comparison_is_case_insensitive_and_trimmed():
    assert wg.violations([W1], "Claude-Hojo", CLAUDE) == [W1]
    assert wg.violations([W1], " claude-hojo ", CLAUDE) == [W1]
    assert wg.violations([W1], "claude-hojo2", CLAUDE) == []


def test_empty_author_passes():
    # push・dispatch など PR 以外では作者が無い → 比較できないので違反にしない
    assert wg.violations([W1], "", CLAUDE) == []
    assert wg.violations([W1], None, CLAUDE) == []


# ---- CLI ----

def test_selftest_passes():
    r = run("--selftest")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "自己点検OK" in r.stdout


def test_cli_exit_codes(tmp_path):
    f = tmp_path / "changed.txt"
    f.write_text(f"{W1}\ndocs/wiki/_candidates/c.md\nsite/index.html\n", encoding="utf-8")
    r = run("--files-from", str(f), "--author", CLAUDE, "--claude-login", CLAUDE)
    assert r.returncode == wg.EXIT_MATCHED and r.stdout.split() == [W1]
    r = run("--files-from", str(f), "--author", HUMAN, "--claude-login", CLAUDE)
    assert r.returncode == 0 and r.stdout.strip() == ""
    r = run("--files-from", str(f), "--author", CLAUDE, "--claude-login", "")   # 休眠
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_cli_rejects_missing_arguments(tmp_path):
    f = tmp_path / "changed.txt"
    f.write_text(f"{W1}\n", encoding="utf-8")
    assert run().returncode == 2
    assert run("--files-from", str(f), "--author", CLAUDE).returncode == 2       # --claude-login 無し
    assert run("--files-from", str(f), "--claude-login", CLAUDE).returncode == 2  # --author 無し


# ---- workflow(文字列。休眠の条件と、既存 step の不変) ----

def _guard_block():
    t = read(RS)
    m = re.search(r"^  guard:\n(.*?)(?=^  [A-Za-z_-]+:\n|\Z)", t, re.S | re.M)
    assert m
    return m.group(1)


def test_step_is_dormant_until_variable_is_set_and_only_on_pull_request():
    g = _guard_block()
    assert "- name: wiki-guard" in g
    assert "if: ${{ !cancelled() && github.event_name == 'pull_request' && vars.HOJO_CLAUDE_LOGIN != '' }}" in g
    assert "CLAUDE_LOGIN: ${{ vars.HOJO_CLAUDE_LOGIN }}" in g
    assert "PR_AUTHOR: ${{ github.event.pull_request.user.login }}" in g
    assert "pull_request_target" not in read(RS)
    body = run_block(read(RS), STEP)
    assert 'if [ -z "$CLAUDE_LOGIN" ]; then' in body and "exit 0" in body        # 本文側の早期終了(二重の休眠)
    assert "gh api --paginate" in body and "検査不完全" in body                       # 全件取得と fail-closed
    assert "git push" not in body and "gh pr merge" not in body                    # 書き込みはしない


def test_existing_guard_steps_check_names_and_triggers_are_unchanged():
    # 休眠時の無害性: 既存 7 step(名前・順序)の後ろに wiki-guard が 1 つ増えただけ。check-run 名・トリガーは不変
    names = re.findall(r"^      - name: (.+)$", _guard_block(), re.M)
    assert names == [
        "pytest を入れる",
        "Experience記録の公開可否 自己点検",
        "Experience記録の公開可否",
        "Wiki(候補・正式)の自己点検",
        "Wiki(候補・正式)の検査",
        "議事(Decision)の必須項目検査",
        "Baseline 比較(新しい赤を増やさない)",
        "wiki-guard(正式 Wiki を変える PR の作者が Claude 用アカウントなら赤。S7b まで休眠)",
    ]
    t = read(RS)
    assert "name: repo-scope-check" in t and "name: repo-scope-guard" in t
    assert "on:\n  push:\n  pull_request:\n  workflow_dispatch: {}" in t
    assert t.count("- name: wiki-guard") == 1
    assert re.search(r"^  wiki-guard:", t, re.M) is None  # 新しい job(= 新しい check-run)ではなく guard の中の step


def test_wikiskill_tests_runs_this_file_and_watches_the_script():
    t = read(".github/workflows/wikiskill-tests.yml")
    assert "tests/scripts/test_wiki_guard.py" in t
    assert "- 'scripts/wiki_guard.py'" in t  # wiki_guard.py だけを変える push/PR でもテストが走る


# ---- step の run: 本文を偽 gh と一緒に bash で実行する ----

FAKE_GH = textwrap.dedent(r'''
    #!/usr/bin/env bash
    echo "$*" >> "$FAKE_LOG"
    if [ "$1" = "api" ]; then
      [ "${FAKE_API_FAIL:-0}" = "1" ] && exit 1
      case "$*" in *"/pulls/"*"/files"*) cat "$FAKE_FILES"; exit 0 ;; esac
    fi
    echo "fake gh: unexpected args: $*" >&2; exit 99
''').lstrip()


def run_step(tmp_path, *, login, author, files, changed_files=None, api_fail=False):
    tmp_path = Path(tempfile.mkdtemp(dir=tmp_path))  # 1 テストで複数回呼べるよう、呼び出しごとに別ディレクトリ
    work = tmp_path / "work"; work.mkdir()
    (work / "scripts").mkdir()
    (work / "scripts" / "wiki_guard.py").write_text(read("scripts/wiki_guard.py"), encoding="utf-8")
    bindir = tmp_path / "bin"; bindir.mkdir()
    gh = bindir / "gh"; gh.write_text(FAKE_GH, encoding="utf-8"); gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    summ = tmp_path / "summary.md"; log = tmp_path / "gh.log"; ff = tmp_path / "files.txt"
    summ.touch(); log.touch()
    ff.write_text("".join(f + "\n" for f in files), encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "PATH": f"{bindir}:{env['PATH']}",
        "CLAUDE_LOGIN": login, "PR_AUTHOR": author, "PR_NUMBER": "42",
        "PR_CHANGED_FILES": str(len(files)) if changed_files is None else changed_files,
        "GH_TOKEN": "x", "GITHUB_REPOSITORY": "example/repo", "GITHUB_STEP_SUMMARY": str(summ),
        "FAKE_LOG": str(log), "FAKE_FILES": str(ff), "FAKE_API_FAIL": "1" if api_fail else "0",
    })
    r = subprocess.run(["bash", "-c", run_block(read(RS), STEP)], cwd=work, env=env, capture_output=True, text=True)
    return r, summ.read_text(encoding="utf-8"), log.read_text(encoding="utf-8")


def test_step_dormant_when_login_empty_does_not_call_gh(tmp_path):
    r, summary, log = run_step(tmp_path, login="", author=CLAUDE, files=[W1])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "休眠" in r.stdout and log == "" and summary == ""


def test_step_fails_when_claude_changes_official_wiki(tmp_path):
    r, summary, log = run_step(tmp_path, login=CLAUDE, author=CLAUDE, files=[W1, "docs/wiki/_candidates/c.md", "site/a.html"])
    assert r.returncode != 0
    assert "::error::wiki-guard" in r.stdout and W1 in r.stdout
    assert "❌ wiki-guard" in summary and f"- {W1}" in summary and "_candidates" not in summary
    assert "api --paginate repos/example/repo/pulls/42/files" in log


def test_step_passes_when_author_is_human_or_only_candidates_changed(tmp_path):
    r, summary, _ = run_step(tmp_path, login=CLAUDE, author=HUMAN, files=[W1])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "違反なし" in r.stdout and summary == ""
    r, summary, _ = run_step(tmp_path, login=CLAUDE, author=CLAUDE, files=["docs/wiki/_candidates/c.md"])
    assert r.returncode == 0 and "違反なし" in r.stdout


def test_step_fails_closed_when_api_fails(tmp_path):
    r, _, _ = run_step(tmp_path, login=CLAUDE, author=HUMAN, files=[W1], api_fail=True)
    assert r.returncode != 0
    assert "取得できません" in r.stdout


def test_step_fails_closed_when_file_listing_is_incomplete(tmp_path):
    # ページネーションや 3,000 件上限で一部しか取れなかった = PR の changed_files と件数が合わない → 「違反なし」にしない
    r, _, _ = run_step(tmp_path, login=CLAUDE, author=HUMAN, files=["site/a.html"], changed_files="3")
    assert r.returncode != 0
    assert "1 件しか取得できません" in r.stdout and "検査不完全" in r.stdout
    r, _, _ = run_step(tmp_path, login=CLAUDE, author=HUMAN, files=["site/a.html"], changed_files="")
    assert r.returncode != 0 and "changed_files が取れません" in r.stdout


def test_step_passes_with_zero_changed_files(tmp_path):
    r, _, _ = run_step(tmp_path, login=CLAUDE, author=CLAUDE, files=[])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "違反なし(0 ファイル" in r.stdout
