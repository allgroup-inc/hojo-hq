"""WikiSkill Phase 1 Task 0b: scripts/baseline_debt.py の検査。

実 pytest(tests/skill_validation)を再帰的に呼ばないよう、収集関数は差し替える。
禁止語の実文字列はこのファイルに書かない(check_repo_scope.FORBIDDEN_CONTENT を参照する)。
"""
import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import baseline_debt as bd  # noqa: E402
import check_repo_scope as crs  # noqa: E402

TOP_KEYS = {"schema", "recorded_at", "commit", "base_ref", "phase1_origin", "note", "checks"}
CHECK_KEYS = {"command", "failure_count", "items", "cause", "introduced_by", "detected_at"}


def make_baseline():
    return {
        "checks": {
            "check_repo_scope": {"items": ["a::X", "b::X"]},
            "skill_validation": {"items": ["t::one", "t::two"]},
        }
    }


def make_current(scope, skill):
    return {"check_repo_scope": list(scope), "skill_validation": list(skill)}


def test_compare_same():
    verdict, table = bd.compare(make_baseline(), make_current(["b::X", "a::X"], ["t::two", "t::one"]))
    assert verdict == "SAME"
    assert "check_repo_scope" in table and "skill_validation" in table


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


def test_compare_regression_wins_over_improvement():
    # 1件減って別の1件が増えたら、件数が同じでも REGRESSION
    verdict, _ = bd.compare(make_baseline(), make_current(["a::X", "z::X"], ["t::one", "t::two"]))
    assert verdict == "REGRESSION"


def test_collect_items_are_sorted(monkeypatch):
    monkeypatch.setattr(crs, "tracked_files", lambda: ["p2", "p1"])
    monkeypatch.setattr(crs, "find_violations", lambda paths: [("p2", "ZZ"), ("p1", "AA")])
    monkeypatch.setattr(crs, "scan_contents", lambda paths: [("p9", "MM")])
    monkeypatch.setattr(bd, "collect_skill_validation", lambda: ["t::b", "t::a"])
    got = bd.collect()
    assert got["check_repo_scope"] == sorted(got["check_repo_scope"])
    assert got["check_repo_scope"] == ["p1::AA", "p2::ZZ", "p9::MM"]
    assert got["skill_validation"] == ["t::a", "t::b"]


def test_parse_failed_lines_drops_reason_and_sorts():
    out = (
        "FAILED tests/x.py::T::b - AssertionError: boom\n"
        "some other line\n"
        "FAILED tests/x.py::T::a\n"
        "5 failed, 6 passed in 0.1s\n"
    )
    assert bd.parse_failed(out) == ["tests/x.py::T::a", "tests/x.py::T::b"]


def write_baseline(path: Path, scope, skill):
    path.write_text(
        json.dumps({"schema": 1, "checks": {
            "check_repo_scope": {"items": scope},
            "skill_validation": {"items": skill},
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
    assert set(data["checks"]) == {"check_repo_scope", "skill_validation"}


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
    assert set(data["checks"]) == {"check_repo_scope", "skill_validation"}
    for check in data["checks"].values():
        assert CHECK_KEYS <= set(check)
        assert check["failure_count"] == len(check["items"])


def test_baseline_json_path_is_allowed_by_scope_check():
    assert "docs/wikiskill/baseline-debt.json" in crs.ALLOWED
    word = crs.FORBIDDEN_CONTENT[0]
    assert crs.find_content_violations("docs/wikiskill/baseline-debt.json", word) is None
    assert crs.find_content_violations("docs/other.md", word) == word
