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
              ".gitignore", "scripts/check_repo_scope.py", ".github/workflows/knowledge-extract.yml",
              ".github/workflows/repo-scope.yml", ".github/CODEOWNERS"]:
        assert text.count(f"'{p}'") == 2, p  # pull_request と push の両方
    assert "tests/scripts/test_wikiskill_workflows.py" in text  # このテスト自体も CI で走らせる


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
    assert "push origin main" not in t and "wiki-candidates/" in t
    # refs/heads/main は「main からだけ走る」ガード(if: と GITHUB_REF の確認)にだけ出てよい。push の行には出さない
    for line in t.splitlines():
        assert not ("push" in line and "refs/heads/main" in line), line
        assert "HEAD:refs/heads/main" not in line, line


def test_knowledge_extract_runs_only_from_main():
    t = read(WF)
    assert "    if: github.ref == 'refs/heads/main'" in t  # job の条件
    first = re.search(r"    steps:\n      - name:[^\n]*\n(.*?)(?=\n      - )", t, re.S)
    assert first and '"$GITHUB_REF" != "refs/heads/main"' in first.group(0) and "::error::" in first.group(0)
    assert "exit 1" in first.group(0)


def test_knowledge_extract_rejects_max_over_ten():
    t = read(WF)
    assert '[ "$INPUT_MAX" -gt 10 ]' in t and "::error::max は 10 以下" in t
    assert t.index('[ "$INPUT_MAX" -gt 10 ]') < t.index("scripts/knowledge_extract.py --no-llm")


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


TRUST_BOUNDARY = [
    "scripts/memory_bootstrap.py", "scripts/experience_log.py", "scripts/decision_memory.py",
    "scripts/wikiskill_common.py", "scripts/wiki_schema.py", "scripts/wiki_validate.py", "scripts/knowledge_extract.py",
    "scripts/wikiskill_lock.py", "scripts/experience_archive.py", "scripts/check_experience_privacy.py",
    "scripts/check_repo_scope.py", "scripts/baseline_debt.py", "docs/wikiskill/baseline-debt.json",
    ".github/workflows/knowledge-extract.yml", ".github/workflows/wikiskill-tests.yml", ".github/workflows/repo-scope.yml",
    ".github/CODEOWNERS", ".claude/hooks/wikiskill-hook.sh", ".claude/settings.json",
]


def test_codeowners_covers_trust_boundary():
    """WikiSkill の Trust Boundary のファイルはすべて小柳さんが持ち主(G1)。指定先のファイルは実在する。"""
    lines = set(read(".github/CODEOWNERS").splitlines())
    for p in TRUST_BOUNDARY:
        assert f"{p} @takeshikoyanagi9-lab" in lines, p
        assert (ROOT / p).exists(), p
    assert "branch protection はまだ有効ではない" in read(".github/CODEOWNERS")


def test_promotion_doc_paths_resolve():
    assert unresolved_doc_paths("docs/wikiskill/Wiki昇格手順.md") == []
