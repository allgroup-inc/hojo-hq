"""WikiSkill Phase 2 Task 0b: wikiskill-tests.yml の paths が Bootstrap の入力を覆うこと。

YAML は文字列として読む(PyYAML に依存しない)。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_wikiskill_tests_paths_cover_inputs():
    text = read(".github/workflows/wikiskill-tests.yml")
    for p in ["CLAUDE.md", "docs/**", ".claude/skills/**", ".claude/settings.json",
              ".gitignore", "scripts/check_repo_scope.py"]:
        assert text.count(f"'{p}'") == 2, p  # pull_request と push の両方
