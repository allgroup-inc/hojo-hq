"""WikiSkill M3 / Component G: Skill Validator の検査(合成データ・外部接続なし)。

一時的な git リポジトリに、コミット済みの Skill と修正案・Evaluation Set・測定結果を作って検査する。
- 互換性(名前・frontmatter・機密・大きさ)、回帰、測定の不足、改善の測定
- 修正案がないとき、同一のとき、測定できないときは「判定不能」(改善効果を推測しない)
- 読むだけ(Skill 本体と入力は変わらない)・外部コマンドは許可リストだけ・外部通信なし
"""
import ast
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import skill_validator as sv  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
TODAY = dt.date(2026, 10, 15)
LIVE = ("---\nname: writing-plans\ndescription: 実装計画を書くときに使う\nlicense: MIT\n---\n"
        "# 実装計画\n\n## 手順\n1. 目的を書く。\n2. タスクに分ける。\n")


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "hojo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "remote", "add", "origin", PUBLIC_URL)
    _write(root / ".claude/skills/writing-plans/SKILL.md", LIVE)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _candidate(tmp_path, text, name="candidate.md"):
    p = tmp_path / "cand" / name
    _write(p, text)
    return p


def _evals(tmp_path, n):
    p = tmp_path / "evals.jsonl"
    p.write_text("".join(json.dumps({"case_id": f"c{i:02d}"}) + "\n" for i in range(n)), encoding="utf-8")
    return p


def _results(tmp_path, rows, name="results.jsonl"):
    p = tmp_path / name
    lines = [row if isinstance(row, str) else json.dumps(row, ensure_ascii=False) for row in rows]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _pair(n, old_pass, new_pass):
    """n ケースの結果。old は先頭 old_pass 件が pass、new は先頭 new_pass 件が pass。"""
    rows = []
    for i in range(n):
        rows.append({"case_id": f"c{i:02d}", "variant": "old", "outcome": "pass" if i < old_pass else "fail"})
        rows.append({"case_id": f"c{i:02d}", "variant": "new", "outcome": "pass" if i < new_pass else "fail"})
    return rows


def _prov(tmp_path, evals, results, dataset="syn-eval-01", independent=True, corrupt=False):
    """出どころの申告。ハッシュは評価データと結果ファイルの今の内容から作る。"""
    import hashlib as _h
    m = {"dataset_id": dataset, "independent_of_candidate": independent,
         "evals_sha256": _h.sha256(evals.read_bytes()).hexdigest(),
         "results_sha256": _h.sha256(results.read_bytes()).hexdigest()}
    p = tmp_path / "provenance.json"
    p.write_text("{ 壊れた" if corrupt else json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return p


def _run(root, *args):
    return sv.main(["--root", str(root), "--date", TODAY.isoformat(), "--skill", "writing-plans", *args])


def _digest(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root)
        if ".git" in rel.parts or "__pycache__" in rel.parts or "evaluations" in rel.parts or not p.is_file():
            continue
        h.update(str(rel).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def test_no_candidate_is_undecidable_and_writes_nothing(repo, capsys):
    assert _run(repo) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "修正案がない" in out
    assert not (repo / "docs" / "evaluations").exists()


def test_identical_candidate_is_undecidable(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE)
    assert _run(repo, "--candidate", str(cand)) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "同一" in out


def test_renamed_skill_fails(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("name: writing-plans", "name: plans-renamed"))
    assert _run(repo, "--candidate", str(cand)) == 0
    out = capsys.readouterr().out
    assert "判定: **不合格**" in out and "name" in out


def test_removed_frontmatter_key_fails(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("license: MIT\n", ""))
    assert _run(repo, "--candidate", str(cand)) == 0
    out = capsys.readouterr().out
    assert "判定: **不合格**" in out and "license" in out


def test_empty_description_fails(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("description: 実装計画を書くときに使う", "description: "))
    assert _run(repo, "--candidate", str(cand)) == 0
    assert "判定: **不合格**" in capsys.readouterr().out


def test_missing_frontmatter_fails(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, "# 本文だけ\n")
    assert _run(repo, "--candidate", str(cand)) == 0
    assert "判定: **不合格**" in capsys.readouterr().out


def test_secret_in_candidate_fails_and_is_never_echoed(repo, tmp_path, capsys):
    marker = "本文の秘密マーカーXYZ"
    cand = _candidate(tmp_path, LIVE + f"\n連絡先 someone@example.com {marker}\n")
    assert _run(repo, "--candidate", str(cand)) == 0
    out = capsys.readouterr().out
    assert "判定: **不合格**" in out and "email" in out
    assert "someone@example.com" not in out and marker not in out


def test_forbidden_term_in_candidate_fails_without_echo(repo, tmp_path, capsys):
    term = sv.sp.check_repo_scope.FORBIDDEN_CONTENT[0]
    cand = _candidate(tmp_path, LIVE + f"\n{term}\n")
    assert _run(repo, "--candidate", str(cand)) == 0
    out = capsys.readouterr().out
    assert "判定: **不合格**" in out and term not in out


def test_oversized_candidate_fails(repo, tmp_path, capsys):
    big = LIVE + ("追加の行\n" * 60000)
    cand = _candidate(tmp_path, big)
    assert _run(repo, "--candidate", str(cand)) == 0
    out = capsys.readouterr().out
    assert "判定: **不合格**" in out and "上限" in out


def test_compatible_without_results_is_undecidable(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("1. 目的を書く。", "1. 目的を明確に書く。"))
    assert _run(repo, "--candidate", str(cand), "--evals", str(_evals(tmp_path, 12))) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "測定結果がない" in out and "互換性の検査は通過" in out


def test_too_few_common_cases_is_undecidable(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    res = _results(tmp_path, _pair(5, 2, 5))
    assert _run(repo, "--candidate", str(cand), "--evals", str(_evals(tmp_path, 5)), "--results", str(res)) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and f"必要: {sv.MIN_CASES} 件以上" in out


def test_measured_improvement_passes_only_on_the_given_data(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    ev, res = _evals(tmp_path, 12), _results(tmp_path, _pair(12, 6, 9))
    prov = _prov(tmp_path, ev, res)
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res),
                "--provenance", str(prov)) == 0
    out = capsys.readouterr().out
    assert "判定: **合格**(指定された評価データ上のみ。実運用の改善ではない)" in out
    assert "0.5 → 0.75" in out and "syn-eval-01" in out
    assert "承認ではない" in out and "自動採用・自動反映はしていません" in out
    assert "実際のタスクの自動実行・測定はしていない" in out and "実運用での改善は確認していない" in out


def test_regression_fails_and_names_the_count(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    rows = _pair(12, 6, 9)
    rows = [{**r, "outcome": "fail"} if (r["case_id"] == "c00" and r["variant"] == "new") else r for r in rows]
    res = _results(tmp_path, rows)
    assert _run(repo, "--candidate", str(cand), "--evals", str(_evals(tmp_path, 12)), "--results", str(res)) == 0
    out = capsys.readouterr().out
    assert "判定: **不合格**" in out and "回帰" in out


def test_equal_rates_are_not_an_improvement(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    res = _results(tmp_path, _pair(12, 7, 7))
    assert _run(repo, "--candidate", str(cand), "--evals", str(_evals(tmp_path, 12)), "--results", str(res)) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "改善が測定されなかった" in out


def test_error_and_conflicting_results_are_not_counted(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    rows = _pair(12, 6, 9)
    rows += [{"case_id": "c01", "variant": "new", "outcome": "error"},
             {"case_id": "c02", "variant": "old", "outcome": "fail"}]  # c02 の old は食い違う(採らない)
    ev, res = _evals(tmp_path, 12), _results(tmp_path, rows)
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res),
                "--provenance", str(_prov(tmp_path, ev, res))) == 0
    out = capsys.readouterr().out
    # c01(error)と c02(結果が食い違う)は外れ、共通ケースは10件になる。10件は必要件数を満たす
    assert "判定: **合格**" in out and "共通ケース 10 件" in out


def test_bad_result_lines_do_not_crash(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    rows = ["これはJSONではない", json.dumps(["配列"]), json.dumps({"case_id": "c00", "variant": "x", "outcome": "pass"})]
    rows += _pair(12, 6, 9)
    ev, res = _evals(tmp_path, 12), _results(tmp_path, rows)
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res),
                "--provenance", str(_prov(tmp_path, ev, res))) == 0
    assert "判定: **合格**" in capsys.readouterr().out


def test_proposal_reference_must_be_in_proposals_and_match_skill(repo, tmp_path, capsys):
    outside = tmp_path / "outside.md"
    _write(outside, "# Skill改善提案(未検証): writing-plans\n")
    assert _run(repo, "--proposal", str(outside)) == sv.sp.EXIT_USAGE
    inside = repo / "docs" / "proposals" / "proposal-20261015-writing-plans.md"
    _write(inside, "# Skill改善提案(未検証): other-skill\n")
    assert _run(repo, "--proposal", str(inside)) == sv.sp.EXIT_USAGE
    _write(inside, "# Skill改善提案(未検証): writing-plans\n")
    cand = _candidate(tmp_path, LIVE)
    assert _run(repo, "--candidate", str(cand), "--proposal", str(inside)) == 0
    assert "proposal-20261015-writing-plans.md" in capsys.readouterr().out


def test_candidate_must_be_a_file(repo, tmp_path):
    assert _run(repo, "--candidate", str(tmp_path / "missing.md")) == sv.sp.EXIT_USAGE


def test_skill_and_inputs_are_unchanged_by_a_run(repo, tmp_path):
    before = _digest(repo)
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    res = _results(tmp_path, _pair(12, 6, 9))
    _run(repo, "--candidate", str(cand), "--evals", str(_evals(tmp_path, 12)), "--results", str(res))
    assert _digest(repo) == before
    assert (repo / ".claude/skills/writing-plans/SKILL.md").read_text(encoding="utf-8") == LIVE


def test_save_writes_exactly_one_report_without_candidate_text(repo, tmp_path, capsys):
    marker = "保存されてはいけない本文マーカー"
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。") + marker)
    res = _results(tmp_path, _pair(12, 6, 9))
    before = _digest(repo)
    assert _run(repo, "--candidate", str(cand), "--evals", str(_evals(tmp_path, 12)), "--results", str(res), "--save") == 0
    reports = sorted(p.name for p in (repo / "docs" / "evaluations").iterdir())
    assert reports == ["skill-writing-plans-eval-20261015.md"]
    text = (repo / "docs" / "evaluations" / reports[0]).read_text(encoding="utf-8")
    assert marker not in text
    assert _digest(repo) == before


def test_save_refuses_overwrite(repo, tmp_path, capsys):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    res = _results(tmp_path, _pair(12, 6, 9))
    args = ("--candidate", str(cand), "--evals", str(_evals(tmp_path, 12)), "--results", str(res), "--save")
    assert _run(repo, *args) == 0
    assert _run(repo, *args) == sv.sp.EXIT_SAVE_REFUSED


def test_allowlist_refuses_anything_but_committed_skill_reads(repo):
    for bad in (["push", "origin"], ["sh", "-c", "id"], ["show", "HEAD:../../etc/passwd"],
                ["show", "HEAD:.claude/skills/x/../../secret"], ["-c", "core.pager=x", "show"]):
        with pytest.raises(sv.CommandNotAllowed):
            sv.run_allowed(repo, bad)
    out = sv.run_allowed(repo, ["show", "HEAD:.claude/skills/writing-plans/SKILL.md"])
    assert out.returncode == 0 and b"name: writing-plans" in out.stdout


def test_module_has_no_network_or_process_imports():
    tree = ast.parse((ROOT / "scripts" / "skill_validator.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    forbidden = {"urllib", "http", "socket", "requests", "ssl", "ftplib", "smtplib", "xmlrpc", "aiohttp", "os"}
    assert not (names & forbidden), names & forbidden


def test_diff_summary_counts_without_content():
    d = sv.diff_summary("# A\nx\n", "# A\n# B\ny\nz\n")
    assert d["lines_old"] == 2 and d["lines_new"] == 4
    assert d["headings_added"] == 1 and d["headings_removed"] == 0


def test_frontmatter_keys_parser():
    ok, keys = sv.frontmatter_keys(LIVE)
    assert ok and keys["name"] == "writing-plans" and "license" in keys
    assert sv.frontmatter_keys("本文だけ") == (False, {})
    assert sv.frontmatter_keys("---\nname: x\n") == (False, {})  # 閉じが無い


def test_default_root_is_the_script_repository_not_the_environment_project():
    """既定の基準は、このスクリプトのリポジトリ(別の作業ツリーを指す CLAUDE_PROJECT_DIR は使わない)。"""
    assert sv.default_root() == ROOT
    assert "project_dir" not in (ROOT / "scripts" / "skill_validator.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- 評価結果の厳密さ(出どころの申告)

def _improved_inputs(tmp_path):
    cand = _candidate(tmp_path, LIVE.replace("2. タスクに分ける。", "2. タスクを細かく分ける。"))
    ev, res = _evals(tmp_path, 12), _results(tmp_path, _pair(12, 6, 9))
    return cand, ev, res


def test_improvement_without_provenance_is_undecidable(repo, tmp_path, capsys):
    cand, ev, res = _improved_inputs(tmp_path)
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res)) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "出どころの申告(--provenance)がない" in out
    assert "判定: **合格**" not in out


def test_provenance_hash_mismatch_is_undecidable(repo, tmp_path, capsys):
    cand, ev, res = _improved_inputs(tmp_path)
    prov = _prov(tmp_path, ev, res)
    res.write_text(res.read_text(encoding="utf-8") + "\n", encoding="utf-8")  # 申告の後に結果を書き換えた
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res),
                "--provenance", str(prov)) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "一致しない" in out


def test_not_independent_is_undecidable(repo, tmp_path, capsys):
    cand, ev, res = _improved_inputs(tmp_path)
    prov = _prov(tmp_path, ev, res, independent=False)
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res),
                "--provenance", str(prov)) == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "独立していると申告されていない" in out


def test_unreadable_provenance_is_undecidable_not_a_crash(repo, tmp_path, capsys):
    cand, ev, res = _improved_inputs(tmp_path)
    prov = _prov(tmp_path, ev, res, corrupt=True)
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res),
                "--provenance", str(prov)) == 0
    assert "判定: **判定不能**" in capsys.readouterr().out


def test_every_report_states_the_scope_and_never_claims_production_improvement(repo, tmp_path, capsys):
    cand, ev, res = _improved_inputs(tmp_path)
    cases = [
        [],                                                            # 修正案なし
        ["--candidate", str(cand)],                                    # 測定なし
        ["--candidate", str(cand), "--evals", str(ev), "--results", str(res)],  # 申告なし
        ["--candidate", str(cand), "--evals", str(ev), "--results", str(res),
         "--provenance", str(_prov(tmp_path, ev, res))],               # 合格
    ]
    for args in cases:
        capsys.readouterr()
        assert _run(repo, *args) == 0
        out = capsys.readouterr().out
        assert "実際のタスクの自動実行・測定はしていない" in out
        assert "実運用での改善は確認していない" in out
        assert "実運用で改善した" not in out and "改善が確認された" not in out


def test_provenance_hash_is_not_claimed_as_authenticity(repo, tmp_path, capsys):
    cand, ev, res = _improved_inputs(tmp_path)
    assert _run(repo, "--candidate", str(cand), "--evals", str(ev), "--results", str(res),
                "--provenance", str(_prov(tmp_path, ev, res))) == 0
    out = capsys.readouterr().out
    assert "(真正性)は確認していない" in out          # 報告は、真正性を確認したとは書かない
    assert "真正性を確認" not in out
