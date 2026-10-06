"""WikiSkill Phase 1 Task 0b: scripts/baseline_debt.py の検査。

実 pytest(tests/skill_validation)を再帰的に呼ばないよう、収集関数は差し替える。
禁止語の実文字列はこのファイルに書かない(check_repo_scope.FORBIDDEN_CONTENT を参照する)。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import baseline_debt as bd  # noqa: E402
import check_repo_scope as crs  # noqa: E402

TOP_KEYS = {"schema", "recorded_at", "commit", "base_ref", "phase1_origin", "note", "checks"}
ALL_CHECKS = {"check_repo_scope", "skill_validation", "scripts_tests_preexisting"}
CHECK_KEYS = {"command", "failure_count", "items", "cause", "introduced_by", "detected_at"}


def make_baseline():
    return {
        "checks": {
            "check_repo_scope": {"items": ["a::X", "b::X"]},
            "skill_validation": {"items": ["t::one", "t::two"]},
            "scripts_tests_preexisting": {"items": ["s::one"]},
        }
    }


def make_current(scope, skill, scripts=("s::one",)):
    return {
        "check_repo_scope": list(scope),
        "skill_validation": list(skill),
        "scripts_tests_preexisting": list(scripts),
    }


def test_compare_same():
    verdict, table = bd.compare(make_baseline(), make_current(["b::X", "a::X"], ["t::two", "t::one"]))
    assert verdict == "SAME"
    assert "check_repo_scope" in table and "skill_validation" in table
    assert "scripts_tests_preexisting" in table


def test_compare_regression_lists_new_items():
    verdict, table = bd.compare(
        make_baseline(), make_current(["a::X", "b::X", "c::X"], ["t::one", "t::two"])
    )
    assert verdict == "REGRESSION"
    assert "c::X" in table


def test_compare_improved_lists_removed_items():
    verdict, table = bd.compare(make_baseline(), make_current(["a::X"], ["t::one", "t::two"]))
    assert verdict == "IMPROVED"
    assert "b::X" in table


def test_compare_third_check_new_item_is_regression():
    verdict, table = bd.compare(
        make_baseline(), make_current(["a::X", "b::X"], ["t::one", "t::two"], ["s::one", "s::new"])
    )
    assert verdict == "REGRESSION"
    assert "s::new" in table


def test_compare_third_check_removed_item_is_improved():
    verdict, table = bd.compare(make_baseline(), make_current(["a::X", "b::X"], ["t::one", "t::two"], []))
    assert verdict == "IMPROVED"
    assert "s::one" in table


def test_compare_regression_wins_over_improvement():
    # 1件減って別の1件が増えたら、件数が同じでも REGRESSION
    verdict, _ = bd.compare(make_baseline(), make_current(["a::X", "z::X"], ["t::one", "t::two"]))
    assert verdict == "REGRESSION"


def test_collect_items_are_sorted(monkeypatch):
    monkeypatch.setattr(bd, "tracked_files", lambda: ["p2", "p1"])
    monkeypatch.setattr(crs, "find_violations", lambda paths: [("p2", crs.FORBIDDEN[1]), ("p1", crs.FORBIDDEN[0])])
    monkeypatch.setattr(crs, "read_text", lambda path: None)
    monkeypatch.setattr(bd, "collect_skill_validation", lambda: ["t::b", "t::a"])
    monkeypatch.setattr(bd, "collect_scripts_tests_preexisting", lambda: ["s::b", "s::a"])
    got = bd.collect()
    assert got["check_repo_scope"] == ["p1::FORBIDDEN[0]", "p2::FORBIDDEN[1]"]
    assert got["skill_validation"] == ["t::a", "t::b"]
    assert got["scripts_tests_preexisting"] == ["s::a", "s::b"]


def test_scan_reports_every_forbidden_word_per_file(tmp_path, monkeypatch):
    # 1ファイルに複数の禁止語があっても、語ごとに1項目(check_repo_scope.scan_contents は最初の1語だけ)
    w0, w1 = crs.FORBIDDEN_CONTENT[0], crs.FORBIDDEN_CONTENT[1]
    (tmp_path / "both.md").write_text(f"{w0}\n{w1}\n", encoding="utf-8")
    (tmp_path / "one.md").write_text(w0, encoding="utf-8")
    (tmp_path / "clean.md").write_text("問題なし", encoding="utf-8")
    monkeypatch.setattr(bd, "ROOT", tmp_path)
    got = bd.scan_scope_items(["both.md", "one.md", "clean.md"])
    assert got == {"both.md::FORBIDDEN_CONTENT[0]", "both.md::FORBIDDEN_CONTENT[1]", "one.md::FORBIDDEN_CONTENT[0]"}
    # 記録する項目に禁止語の実文字列を入れない(記録ファイル自体が検査に引っかからないように)
    assert not any(w0 in item or w1 in item for item in got)


def test_scan_records_path_items_by_index(tmp_path, monkeypatch):
    pat = crs.FORBIDDEN[2]
    path = f"dir/{pat}/x.txt"
    monkeypatch.setattr(bd, "ROOT", tmp_path)
    got = bd.scan_scope_items([path])
    assert f"{path}::FORBIDDEN[2]" in got
    assert all(not item.endswith("::" + pat) for item in got)


def test_scan_skips_allowed_paths_and_is_cwd_independent(tmp_path, monkeypatch):
    word = crs.FORBIDDEN_CONTENT[0]
    allowed = "scripts/check_repo_scope.py"
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / allowed).write_text(word, encoding="utf-8")
    monkeypatch.setattr(bd, "ROOT", tmp_path)
    elsewhere = tmp_path / "docs"
    monkeypatch.chdir(elsewhere)  # cwd が repo root でなくても読める
    assert bd.scan_scope_items([allowed]) == set()


def test_real_repo_scan_matches_baseline_count():
    # 実リポジトリ: 既知の9ファイルは語ごとに数えても9件のまま(各ファイル1語のみ)
    base = json.loads(bd.DEFAULT_PATH.read_text(encoding="utf-8"))
    assert sorted(bd.scan_scope_items(bd.tracked_files())) == base["checks"]["check_repo_scope"]["items"]


def test_parse_failed_lines_drops_reason_and_sorts():
    out = (
        "FAILED tests/x.py::T::b - AssertionError: boom\n"
        "some other line\n"
        "FAILED tests/x.py::T::a\n"
        "5 failed, 6 passed in 0.1s\n"
    )
    assert bd.parse_failed(out) == ["tests/x.py::T::a", "tests/x.py::T::b"]


def test_parse_failed_captures_error_lines_with_prefix():
    out = (
        "FAILED tests/x.py::T::a - AssertionError\n"
        "ERROR tests/x.py::T::b - fixture 'f' not found\n"
    )
    assert bd.parse_failed(out) == ["ERROR::tests/x.py::T::b", "tests/x.py::T::a"]


def test_summary_counts():
    assert bd.summary_counts("5 failed, 6 passed in 0.1s") == (5, 0)
    assert bd.summary_counts("1 failed, 2 passed, 1 error in 0.30s") == (1, 1)
    assert bd.summary_counts("2 errors in 0.1s") == (0, 2)
    assert bd.summary_counts("no summary here") is None


def fake_run(returncode, stdout="", stderr=""):
    def run(*args, **kwargs):
        assert kwargs.get("timeout") == bd.SKILL_VALIDATION_TIMEOUT
        return subprocess.CompletedProcess(args[0], returncode, stdout, stderr)
    return run


def test_scripts_tests_collector_uses_fixed_file_list_only(monkeypatch):
    seen = {}

    def run(argv, **kwargs):
        seen["argv"] = argv
        out = "FAILED tests/scripts/test_verify_mikata_seido.py::x - e\n1 failed, 3 passed in 0.1s\n"
        return subprocess.CompletedProcess(argv, 1, out, "")

    monkeypatch.setattr(bd.subprocess, "run", run)
    assert bd.collect_scripts_tests_preexisting() == ["tests/scripts/test_verify_mikata_seido.py::x"]
    targets = [a for a in seen["argv"] if a.startswith("tests/")]
    assert targets == [
        "tests/scripts/test_generate_ig_posts_mikata.py",
        "tests/scripts/test_verify_mikata_seido.py",
    ]
    assert targets == bd.SCRIPTS_TESTS_FILES
    assert "-rfE" in seen["argv"]
    # tests/scripts ディレクトリ全体や自分自身のテストは含めない
    assert "tests/scripts" not in seen["argv"]
    assert not any("test_baseline_debt" in a for a in seen["argv"])


def test_skill_validation_collector_still_targets_its_directory(monkeypatch):
    seen = {}

    def run(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "1 passed in 0.1s\n", "")

    monkeypatch.setattr(bd.subprocess, "run", run)
    assert bd.collect_skill_validation() == []
    assert [a for a in seen["argv"] if a.startswith("tests/")] == ["tests/skill_validation"]


def test_collect_skill_validation_ok(monkeypatch):
    out = "FAILED t.py::b - x\nFAILED t.py::a - y\n2 failed, 3 passed in 0.1s\n"
    monkeypatch.setattr(bd.subprocess, "run", fake_run(1, out))
    assert bd.collect_skill_validation() == ["t.py::a", "t.py::b"]
    monkeypatch.setattr(bd.subprocess, "run", fake_run(0, "5 passed in 0.1s\n"))
    assert bd.collect_skill_validation() == []


@pytest.mark.parametrize("code", [2, 5])
def test_collect_skill_validation_rejects_unexpected_exit(monkeypatch, code):
    monkeypatch.setattr(bd.subprocess, "run", fake_run(code, "", "boom"))
    with pytest.raises(bd.CollectionError, match=f"exit {code}"):
        bd.collect_skill_validation()


def test_collect_skill_validation_rejects_exit1_without_items(monkeypatch):
    monkeypatch.setattr(bd.subprocess, "run", fake_run(1, "1 failed in 0.1s\n"))
    with pytest.raises(bd.CollectionError, match="読み取れませんでした"):
        bd.collect_skill_validation()


def test_collect_skill_validation_includes_error_items(monkeypatch):
    out = (
        "FAILED t.py::a - x\nERROR t.py::b - setup\n"
        "1 failed, 1 error in 0.1s\n"
    )
    monkeypatch.setattr(bd.subprocess, "run", fake_run(1, out))
    assert bd.collect_skill_validation() == ["ERROR::t.py::b", "t.py::a"]


def test_collect_skill_validation_count_mismatch_is_collection_failure(monkeypatch):
    # サマリーは 1 failed + 1 error だが ERROR 行が出ていない(-rE を取りこぼした等)
    out = "FAILED t.py::a - x\n1 failed, 1 error in 0.1s\n"
    monkeypatch.setattr(bd.subprocess, "run", fake_run(1, out))
    with pytest.raises(bd.CollectionError, match="一致しません"):
        bd.collect_skill_validation()


def test_collect_skill_validation_timeout(monkeypatch):
    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(bd.subprocess, "run", run)
    with pytest.raises(bd.CollectionError, match="秒以内"):
        bd.collect_skill_validation()


def test_cli_compare_exits_1_on_collection_failure(tmp_path, monkeypatch, capsys):
    base = tmp_path / "b.json"
    write_baseline(base, ["a::X"], ["t::one"])
    def boom():
        raise bd.CollectionError("pytest が落ちた")
    monkeypatch.setattr(bd, "collect", boom)
    assert bd.main(["--compare", "--path", str(base)]) == 1
    assert "pytest が落ちた" in capsys.readouterr().err


def write_baseline(path: Path, scope, skill, scripts=("s::one",)):
    path.write_text(
        json.dumps({"schema": 1, "checks": {
            "check_repo_scope": {"items": scope},
            "skill_validation": {"items": skill},
            "scripts_tests_preexisting": {"items": list(scripts)},
        }}),
        encoding="utf-8",
    )


def test_cli_compare_exits_1_on_regression(tmp_path, monkeypatch, capsys):
    base = tmp_path / "b.json"
    write_baseline(base, ["a::X"], ["t::one"])
    monkeypatch.setattr(bd, "collect", lambda: make_current(["a::X", "new::X"], ["t::one"]))
    assert bd.main(["--compare", "--path", str(base)]) == 1
    assert "REGRESSION" in capsys.readouterr().out


def test_cli_compare_exits_0_on_same_and_improved(tmp_path, monkeypatch, capsys):
    base = tmp_path / "b.json"
    write_baseline(base, ["a::X"], ["t::one"])
    monkeypatch.setattr(bd, "collect", lambda: make_current(["a::X"], ["t::one"]))
    assert bd.main(["--compare", "--path", str(base)]) == 0
    monkeypatch.setattr(bd, "collect", lambda: make_current([], ["t::one"]))
    assert bd.main(["--compare", "--path", str(base)]) == 0
    assert "IMPROVED" in capsys.readouterr().out


def test_cli_compare_json_output(tmp_path, monkeypatch, capsys):
    base = tmp_path / "b.json"
    write_baseline(base, ["a::X"], ["t::one"])
    monkeypatch.setattr(bd, "collect", lambda: make_current(["a::X"], ["t::one"]))
    assert bd.main(["--compare", "--json", "--path", str(base)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "SAME"
    assert set(data["checks"]) == ALL_CHECKS


def test_record_refuses_overwrite_without_force(tmp_path, monkeypatch):
    target = tmp_path / "baseline.json"
    target.write_text("ORIGINAL", encoding="utf-8")
    monkeypatch.setattr(bd, "collect", lambda: make_current(["a::X"], ["t::one"]))
    assert bd.main(["--record", "--path", str(target)]) != 0
    assert target.read_text(encoding="utf-8") == "ORIGINAL"
    assert bd.main(["--record", "--force", "--path", str(target)]) == 0
    assert json.loads(target.read_text(encoding="utf-8"))["schema"] == 1


def test_record_json_has_required_schema_keys(tmp_path, monkeypatch):
    target = tmp_path / "baseline.json"
    monkeypatch.setattr(bd, "collect", lambda: make_current(["a::X"], ["t::one", "t::two"]))
    bd.record(target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert TOP_KEYS <= set(data)
    assert data["phase1_origin"] is False
    assert data["base_ref"] == "origin/main@04dbc28f4"
    assert set(data["checks"]) == ALL_CHECKS
    for check in data["checks"].values():
        assert CHECK_KEYS <= set(check)
        assert check["failure_count"] == len(check["items"])
    third = data["checks"]["scripts_tests_preexisting"]
    assert third["files"] == bd.SCRIPTS_TESTS_FILES
    assert third["command"] == (
        "python3 -m pytest tests/scripts/test_generate_ig_posts_mikata.py "
        "tests/scripts/test_verify_mikata_seido.py -q"
    )
    assert third["introduced_by"] == []
    assert "origin/main でも同一に失敗" in third["cause"]


def test_baseline_json_is_not_exempt_and_has_no_forbidden_literal():
    # 記録ファイルは ALLOWED に入れない(例外を広げない)。代わりに中身に禁止語を書かない。
    assert "docs/wikiskill/baseline-debt.json" not in crs.ALLOWED
    text = bd.DEFAULT_PATH.read_text(encoding="utf-8")
    assert crs.find_content_violations("docs/wikiskill/baseline-debt.json", text) is None
    for item in json.loads(text)["checks"]["check_repo_scope"]["items"]:
        assert "::FORBIDDEN_CONTENT[" in item or "::FORBIDDEN[" in item


def test_pytest_missing_is_a_clear_collection_error(monkeypatch):
    monkeypatch.setattr(
        bd.subprocess, "run",
        fake_run(1, "", "/usr/bin/python3: No module named pytest\n"),
    )
    with pytest.raises(bd.CollectionError, match=r"pytest が見つかりません\(pip install pytest\)"):
        bd.collect_skill_validation()
