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
        assert text.count(f"'{p}'") == 1, p  # push 側だけ(pull_request は全 PR 起動・判定は scripts/wikiskill_scope.py)
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


# 決裁 #26 S2 PR-C: S1 の検知一式と、守りの仕組みが依存する .gitignore(2026-10-08 直接 push で壊された)
S2_PROTECTED_EXISTING = [
    ".github/workflows/main-direct-push-watch.yml",
    "scripts/direct_push_watch.py",
    "tests/scripts/test_direct_push_watch.py",
    "scripts/wiki_guard.py",  # PR-B(2026-10-09)で作成。CODEOWNERS 行は PR-C で先に登録済み
]
S2_PROTECTED_PLANNED: list[str] = []  # PR-B で wiki_guard.py が実在するようになり、予定だけの行は無くなった


def codeowners_rules():
    """コメント・空行を除いた (pattern, owners) の並び(先頭から順。後の行が優先)。"""
    out = []
    for line in read(".github/CODEOWNERS").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        out.append((parts[0], parts[1:]))
    return out


def _codeowners_match(pattern, path):
    """CODEOWNERS(gitignore 流)の最小限の一致: / を含むパターンはルート基準、`dir/` は配下すべて、
    先頭 / はルート固定。ワイルドカードは本リポの CODEOWNERS に無いので扱わない。"""
    pat = pattern.lstrip("/")
    if pattern.endswith("/"):
        return path.startswith(pat)
    if "/" in pattern:
        return path == pat
    return path.split("/")[-1] == pat  # スラッシュ無しはどの階層のその名前にも一致


def owners_of(path):
    """後の行が優先(GitHub の規則)。一致する行が無ければ空。"""
    owners = []
    for pattern, who in codeowners_rules():
        if _codeowners_match(pattern, path):
            owners = who
    return owners


def test_codeowners_covers_s1_detection_files_and_root_gitignore():
    lines = set(read(".github/CODEOWNERS").splitlines())
    for p in S2_PROTECTED_EXISTING:
        assert f"{p} @takeshikoyanagi9-lab" in lines, p
        assert (ROOT / p).exists(), p
        assert owners_of(p) == ["@takeshikoyanagi9-lab"], p
    assert "/.gitignore @takeshikoyanagi9-lab" in lines  # ルートの .gitignore だけ(先頭 / で固定)
    assert owners_of(".gitignore") == ["@takeshikoyanagi9-lab"]
    assert owners_of("site/.gitignore") == []  # 配下の同名ファイルには当てない


def test_codeowners_planned_file_is_listed_but_may_not_exist_yet():
    lines = set(read(".github/CODEOWNERS").splitlines())
    for p in S2_PROTECTED_PLANNED:
        assert f"{p} @takeshikoyanagi9-lab" in lines, p
        assert owners_of(p) == ["@takeshikoyanagi9-lab"], p
        # 存在してもしなくてもよい(PR-B で作る)。存在しない間は GitHub 側で何にも一致しないだけ


def test_codeowners_rules_do_not_contradict():
    """すべての行の持ち主が同一(小柳さん 1 人)で、後勝ちの規則でも持ち主が変わる組み合わせが無い。"""
    rules = codeowners_rules()
    assert rules, "CODEOWNERS が空"
    assert {tuple(who) for _, who in rules} == {("@takeshikoyanagi9-lab",)}
    patterns = [p for p, _ in rules]
    assert len(patterns) == len(set(patterns)), "同じパターンの重複行"
    for p in TRUST_BOUNDARY + S2_PROTECTED_EXISTING + S2_PROTECTED_PLANNED + ["docs/wiki/W001.md", ".gitignore"]:
        assert owners_of(p) == ["@takeshikoyanagi9-lab"], p
    for p in ["scripts/fg_seo.py", "site/index.html", "docs/決裁キュー.md", "docs/wiki/_candidates/c.md"]:
        assert owners_of(p) == ([] if p != "docs/wiki/_candidates/c.md" else ["@takeshikoyanagi9-lab"]), p


def test_promotion_doc_paths_resolve():
    assert unresolved_doc_paths("docs/wikiskill/Wiki昇格手順.md") == []


# ---- 決裁 #26 S2 PR-A1: repo-scope.yml の 2 ジョブ分割 ----
RS = ".github/workflows/repo-scope.yml"


def _job_block(text, job_id):
    """`  <job_id>:` から次のジョブ(同じ字下げの `  xxx:`)直前までを返す。PyYAML に依存しない。"""
    m = re.search(rf"^  {job_id}:\n(.*?)(?=^  [A-Za-z_-]+:\n|\Z)", text, re.S | re.M)
    assert m, f"job not found: {job_id}"
    return m.group(1)


def test_repo_scope_has_two_jobs_with_unique_check_names():
    t = read(RS)
    check, guard = _job_block(t, "check"), _job_block(t, "guard")
    assert "name: repo-scope-check" in check and "name: repo-scope-guard" in guard
    # 他 workflow と重複する素の `check` / `test` を check-run 名にしない
    assert re.search(r"^    name: check$", t, re.M) is None


def test_repo_scope_check_job_keeps_placement_check_only():
    check = _job_block(read(RS), "check")
    assert "scripts/check_repo_scope.py --selftest" in check
    assert "run: python3 scripts/check_repo_scope.py\n" in check
    for s in ("check_experience_privacy", "wiki_validate", "decision_memory", "baseline_debt"):
        assert s not in check, s  # 守りの検査は guard 側へ移した


def test_repo_scope_guard_job_keeps_all_guard_checks_and_baseline_compare():
    guard = _job_block(read(RS), "guard")
    for s in ("scripts/check_experience_privacy.py --selftest", "run: python3 scripts/check_experience_privacy.py\n",
              "scripts/wiki_validate.py --selftest", "run: python3 scripts/wiki_validate.py\n",
              "scripts/decision_memory.py --check", "scripts/baseline_debt.py --compare"):
        assert s in guard, s
    assert "check_repo_scope.py\n" not in guard  # 置き場所の検査(Baseline 赤)は guard に入れない
    assert "pip install pytest" in guard  # baseline_debt --compare は pytest を使う
    # 先行の赤で後続が止まらない(検査の素通り防止)
    assert guard.count("if: ${{ !cancelled() }}") >= 6


def test_repo_scope_triggers_unchanged():
    t = read(RS)
    assert "on:\n  push:\n  pull_request:\n  workflow_dispatch: {}" in t
    assert "concurrency:\n  group: repo-scope-${{ github.ref }}" in t
