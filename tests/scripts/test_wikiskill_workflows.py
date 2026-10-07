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


# ---- Task 5: Gate(CODEOWNERS・昇格手順書・knowledge-extract.yml) ----
import re

WF = ".github/workflows/knowledge-extract.yml"


def guard_step(t):
    """「ステージ対象のガード」ステップ(name 行から次の `- name:` 直前まで)の本文を返す。"""
    m = re.search(r"- name:[^\n]*[Gg]uard[^\n]*\n(.*?)(?=\n      - name:|\Z)", t, re.S)
    assert m, "guard step not found"
    return m.group(0)


def unresolved_doc_paths(rel):
    """文書中の `docs/…md` 参照のうち実在しないものを返す(CLAUDE.md 再発防止メモの `\\S+?` 方式)。

    Task 7 などからも再利用する。grep の `[^[:space:]]*` 方式は日本語文中で
    複数パスを1つにつなぐので使わない。
    """
    text = (ROOT / rel).read_text(encoding="utf-8")
    paths = sorted(set(re.findall(r"docs/\S+?\.md", text)))
    return [p for p in paths if not (ROOT / p).exists()]


def test_knowledge_extract_is_dispatch_only():
    t = read(WF)
    assert "workflow_dispatch" in t and "schedule:" not in t and "\n  push:" not in t


def test_knowledge_extract_concurrency_group():
    assert "group: knowledge-extract" in read(WF) and "cancel-in-progress: false" in read(WF)


def test_knowledge_extract_never_pushes_main():
    t = read(WF)
    assert "push origin main" not in t and "refs/heads/main" not in t and "wiki-candidates/" in t


def test_knowledge_extract_stages_only_candidates():
    t = read(WF)
    assert "git add docs/wiki/_candidates" in t and "git add -A" not in t
    assert "docs/wiki/_candidates/" in guard_step(t)


def test_knowledge_extract_runs_validator_before_pr():
    t = read(WF)
    # 先頭の wiki_validate.py は selftest なので、本番の検証ステップ(出力を validate.txt へ)を指す
    assert "scripts/wiki_validate.py 2>&1" in t
    assert t.index("scripts/wiki_validate.py 2>&1") < t.index("git push") < t.index("gh pr create")


def test_codeowners_covers_docs_wiki():
    assert "docs/wiki/ @takeshikoyanagi9-lab" in read(".github/CODEOWNERS")


def test_promotion_doc_paths_resolve():
    assert unresolved_doc_paths("docs/wikiskill/Wiki昇格手順.md") == []
