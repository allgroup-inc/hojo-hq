"""決裁 #26 S2 PR-D2: main-direct-push-watch.yml の 2 step を、本物の git + 一時リポジトリ + 偽 gh で実行する回帰テスト。

対象 step(run: 本文を run_block() で抽出し、そのまま bash で実行する。workflow 自体は変えない):
  - 「検査する commit を決める(直近 SCAN_DEPTH 件 ∪ push の範囲)」 … id: range
  - 「直接 commit の判定」                                          … id: scan
「Issue 起票」step の回帰テストは test_direct_push_watch.py(PR #449)にある。

方針(2026-10-08 手順 3 の教訓: 書いてあるのに動かない、を文字列検査では捕まえられない):
  - git は本物。一時リポジトリは file:// で clone する(ローカルパスの clone は --depth が無視される)
  - 偽 gh は commits/<sha>/pulls と compare だけに答え、それ以外の呼び出しは exit 99 で run を失敗させる
  - 失敗ケースは returncode != 0 を、成功ケースは == 0 を必ず assert する(緑で黙らない)
  - CI runner に PyYAML は無いので、抽出は標準ライブラリの run_block() だけを使う
"""
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_direct_push_watch import run_block  # noqa: E402  PyYAML 不使用の run: 抽出

WF = ".github/workflows/main-direct-push-watch.yml"
RANGE_STEP = "検査する commit を決める"
SCAN_STEP = "直接 commit の判定"
ZERO_SHA = "0" * 40
REPO_NAME = "example/repo"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ---- 偽 gh: api の 2 種類だけに答える。それ以外は exit 99(想定外の呼び出しを黙認しない) ----

FAKE_GH_API = textwrap.dedent(r'''
    #!/usr/bin/env bash
    # テスト用の偽 gh(api 専用)。呼び出しを $FAKE_LOG に記録する。
    echo "$*" >> "$FAKE_LOG"
    if [ "$1" = "api" ]; then
      case "$2" in
        repos/*/commits/*/pulls)
          sha="${2#repos/*/commits/}"; sha="${sha%/pulls}"
          if [ -n "${FAKE_PR_SHAS:-}" ] && grep -qx "$sha" "$FAKE_PR_SHAS"; then echo 1; else echo 0; fi
          exit 0 ;;
        repos/*/compare/*)
          if [ -z "${FAKE_COMPARE_JSON:-}" ] || ! [ -f "$FAKE_COMPARE_JSON" ]; then
            echo "fake gh: compare was not expected: $*" >&2; exit 99
          fi
          cat "$FAKE_COMPARE_JSON"; exit 0 ;;
      esac
    fi
    echo "fake gh: unexpected args: $*" >&2; exit 99
''').lstrip()


# ---- 一時リポジトリ ----

def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=check, capture_output=True, text=True,
    )


def _rev(cwd, ref):
    return _git(cwd, "rev-parse", ref).stdout.strip()


def _put_tools(work: Path):
    """step が呼ぶ判定スクリプトと CODEOWNERS を、追跡せずに作業ツリーへ置く(commit の変更ファイルに混ぜない)。"""
    (work / "scripts").mkdir(exist_ok=True)
    (work / "scripts" / "direct_push_watch.py").write_text(read("scripts/direct_push_watch.py"), encoding="utf-8")
    (work / ".github").mkdir(exist_ok=True)
    (work / ".github" / "CODEOWNERS").write_text(read(".github/CODEOWNERS"), encoding="utf-8")


def _write_commit(work: Path, rel: str, text: str, subject: str):
    p = work / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    _git(work, "add", "--", rel)
    _git(work, "commit", "-q", "-m", subject)
    return _rev(work, "HEAD")


class World:
    """origin(bare)と、main の履歴 A → B(PR マージ)→ C(直接・守りの範囲)→ D(直接・範囲外)、別ブランチ E を持つ。"""

    def __init__(self, tmp_path: Path):
        self.origin = tmp_path / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True)
        self.url = f"file://{self.origin}"
        self.work = tmp_path / "work"
        subprocess.run(["git", "clone", "-q", self.url, str(self.work)], check=True, capture_output=True)
        w = self.work
        self.A = _write_commit(w, "site/index.html", "x", "A: site only (root)")
        _git(w, "branch", "-M", "main")
        _git(w, "checkout", "-q", "-b", "pr")
        _write_commit(w, "docs/wiki/W001.md", "w1", "wiki via PR")
        _git(w, "checkout", "-q", "main")
        _git(w, "merge", "-q", "--no-ff", "pr", "-m", "Merge pull request #1 from example/pr")
        self.B = _rev(w, "HEAD")
        self.C = _write_commit(w, "docs/wiki/W002.md", "w2", "direct wiki")
        self.D = _write_commit(w, "site/a.html", "a", "direct site")
        _git(w, "push", "-q", "origin", "main")
        _git(w, "checkout", "-q", "-b", "side")
        self.E = _write_commit(w, "docs/wiki/W003.md", "w3", "side wiki")
        _git(w, "push", "-q", "origin", "side")
        _git(w, "checkout", "-q", "main")
        _put_tools(w)
        self.tmp = tmp_path

    def shallow_clone(self) -> Path:
        """本番 checkout(fetch-depth 付き)の相当: E を持たない浅い clone。"""
        w2 = self.tmp / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "main", self.url, str(w2)],
                       check=True, capture_output=True)
        assert (w2 / ".git" / "shallow").exists()  # 本当に浅い(file:// でないと --depth が無視される)
        assert _git(w2, "cat-file", "-e", f"{self.E}^{{commit}}", check=False).returncode != 0  # E は無い
        _put_tools(w2)
        return w2


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


# ---- step の実行 ----

def _run_step(step_prefix, cwd: Path, tmp: Path, env_extra: dict, pr_shas=(), compare_json: str | None = None):
    """step の run: 本文を bash で実行し、(CompletedProcess, GITHUB_OUTPUT の dict, Summary 文字列, 偽 gh の呼び出しログ) を返す。"""
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(FAKE_GH_API, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    out = tmp / "output.txt"; summ = tmp / "summary.md"; log = tmp / "gh.log"
    for f in (out, summ, log):
        f.write_text("", encoding="utf-8")
    prs = tmp / "pr_shas.txt"
    prs.write_text("".join(s + "\n" for s in pr_shas), encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "PATH": f"{bindir}:{env['PATH']}",
        "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summ),
        "GITHUB_REPOSITORY": REPO_NAME, "GH_TOKEN": "x",
        "FAKE_LOG": str(log), "FAKE_PR_SHAS": str(prs),
        "SCAN_DEPTH": "20", "INPUT_SHA": "", "BEFORE": ZERO_SHA, "AFTER": "",
    })
    env.pop("FAKE_COMPARE_JSON", None)
    if compare_json is not None:
        cj = tmp / "compare.json"
        cj.write_text(compare_json, encoding="utf-8")
        env["FAKE_COMPARE_JSON"] = str(cj)
    env.update(env_extra)
    r = subprocess.run(["bash", "-c", run_block(read(WF), step_prefix)], cwd=cwd, env=env, capture_output=True, text=True)
    outputs = dict(l.split("=", 1) for l in out.read_text(encoding="utf-8").splitlines() if "=" in l)
    return r, outputs, summ.read_text(encoding="utf-8"), log.read_text(encoding="utf-8")


def _shas(cwd: Path):
    return set((cwd / "shas.txt").read_text(encoding="utf-8").split())


def _compare(total, shas):
    import json
    return json.dumps({"total_commits": total, "commits": [{"sha": s} for s in shas]})


def _run_scan(world_or_cwd, cwd: Path, tmp: Path, shas, pr_shas=()):
    (cwd / "shas.txt").write_text("".join(s + "\n" for s in shas), encoding="utf-8")
    return _run_step(SCAN_STEP, cwd, tmp, {}, pr_shas=pr_shas)


# ---- 1〜4: 「検査する commit を決める」 ----

def test_range_window_mode_takes_first_parent_depth(world):
    r, outputs, summary, log = _run_step(RANGE_STEP, world.work, world.tmp, {"SCAN_DEPTH": "2"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["mode"] == "window"
    assert _shas(world.work) == {world.D, world.C}       # first-parent 直近 2 件。pr 側の commit は入らない
    assert "compare" not in log                           # BEFORE が 0×40 なら compare API は呼ばない
    assert "検査対象: 2 commit" in r.stdout


def test_range_window_unions_push_compare_range(world):
    cj = _compare(3, [world.B, world.C, world.D])
    r, outputs, summary, log = _run_step(
        RANGE_STEP, world.work, world.tmp, {"SCAN_DEPTH": "1", "BEFORE": world.A, "AFTER": world.D}, compare_json=cj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["mode"] == "window"
    assert _shas(world.work) == {world.B, world.C, world.D}
    lines = (world.work / "shas.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(set(lines)) == 3            # sort -u で重複なし
    assert f"compare/{world.A}...{world.D}" in log


def test_range_fails_when_compare_is_truncated(world):
    cj = _compare(3, [world.D])                           # total 3 なのに 1 件しか列挙されない
    r, outputs, summary, log = _run_step(
        RANGE_STEP, world.work, world.tmp, {"BEFORE": world.A, "AFTER": world.D}, compare_json=cj)
    assert r.returncode != 0
    assert "::error::" in r.stdout and "検知漏れ" in r.stdout
    assert "検知漏れの可能性" in summary


def test_range_dispatch_mode_uses_only_the_given_sha(world):
    r, outputs, summary, log = _run_step(RANGE_STEP, world.work, world.tmp, {"INPUT_SHA": world.C, "BEFORE": world.A, "AFTER": world.D})
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["mode"] == "dispatch"
    assert _shas(world.work) == {world.C}
    assert log == ""                                      # dispatch では gh を一切呼ばない


# ---- 5〜9: 「直接 commit の判定」 ----

def test_scan_flags_only_direct_commits_in_scope(world):
    r, outputs, summary, log = _run_scan(world, world.work, world.tmp, [world.B, world.C, world.D], pr_shas=[world.B])
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["found"] == "true"
    hits = (world.work / "hits.md").read_text(encoding="utf-8")
    assert hits == f"- `{world.C[:9]}` direct wiki\n    - docs/wiki/W002.md\n"
    assert world.B[:9] not in hits and world.D[:9] not in hits
    assert f"::warning::直接 commit {world.C[:9]}" in r.stdout
    assert log.count("/pulls") == 3                       # 3 commit とも PR の有無を問い合わせる


def test_scan_reports_none_when_nothing_matches(world):
    r, outputs, summary, log = _run_scan(world, world.work, world.tmp, [world.B, world.D], pr_shas=[world.B])
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["found"] == "false"
    assert (world.work / "hits.md").read_text(encoding="utf-8") == ""
    assert "該当なし(2 commit を検査)" in summary


def test_scan_fails_loudly_on_unknown_sha(world):
    bogus = "f" * 40
    r, outputs, summary, log = _run_scan(world, world.work, world.tmp, [bogus])
    assert r.returncode != 0
    assert "::error::" in r.stdout and "見つかりません" in r.stdout
    assert "が見つかりません" in summary
    assert "found" not in outputs                         # 後続 step の条件は書かれない(run が失敗で止まる)
    assert "/pulls" not in log                            # 取れない SHA で API を叩かない


def test_scan_fetches_missing_sha_by_hash(world):
    w2 = world.shallow_clone()
    r, outputs, summary, log = _run_scan(world, w2, world.tmp, [world.E])
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["found"] == "true"
    assert _git(w2, "cat-file", "-e", f"{world.E}^{{commit}}", check=False).returncode == 0  # SHA 指定で取れた
    hits = (w2 / "hits.md").read_text(encoding="utf-8")
    assert hits == f"- `{world.E[:9]}` side wiki\n    - docs/wiki/W003.md\n"


def test_scan_handles_root_commit_without_parent(world):
    r, outputs, summary, log = _run_scan(world, world.work, world.tmp, [world.A])
    assert r.returncode == 0, r.stdout + r.stderr
    assert outputs["found"] == "false"                    # root commit は site のみ = 範囲外。エラーにしない
    assert (world.work / "changed.txt").read_text(encoding="utf-8").split() == ["site/index.html"]
    assert "::error::" not in r.stdout


# ---- 10: run_block の抽出が 2 step の実体と一致する ----

def test_run_block_extracts_range_and_scan_steps_exactly():
    t = read(WF)
    rng = run_block(t, RANGE_STEP)
    assert rng.startswith("set -e\n")
    assert 'git log --first-parent -n "$SCAN_DEPTH" --format=%H > shas.txt' in [l.strip() for l in rng.splitlines()]  # 字下げ幅に依らない
    assert rng.rstrip("\n").endswith('echo "検査対象: $(wc -l < shas.txt) commit"')
    scan = run_block(t, SCAN_STEP)
    assert scan.startswith("set -e\n: > hits.md\n")
    assert 'git diff --name-only "${sha}^1" "$sha" > changed.txt' in scan
    assert scan.rstrip("\n").endswith("fi")
    for body in (rng, scan):
        assert "gh issue create" not in body and "line-notify" not in body  # 隣の step を含まない
        assert not any(l.startswith(" ") for l in body.splitlines()[:1])    # 字下げが剥がれている
    assert "run_block" not in rng
    try:
        import yaml  # 手元に PyYAML があれば YAML パーサの結果と完全一致も確かめる(CI では無いので飛ばす)
    except ImportError:
        return
    steps = yaml.safe_load(t)["jobs"]["watch"]["steps"]
    assert rng == next(s["run"] for s in steps if s.get("name", "").startswith(RANGE_STEP))
    assert scan == next(s["run"] for s in steps if s.get("name", "").startswith(SCAN_STEP))


def test_wikiskill_tests_runs_this_file():
    assert "tests/scripts/test_direct_push_watch_steps.py" in read(".github/workflows/wikiskill-tests.yml")
