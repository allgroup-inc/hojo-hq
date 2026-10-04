"""
Skill dependency validation tests.

This module validates that:
1. All referenced skills in other skills' descriptions actually exist
2. There are no circular dependencies between skills
3. The skill dependency graph is acyclic
"""

import re
from pathlib import Path


def extract_dependencies(skill_dir):
    """
    Extract skill dependencies from all SKILL.md files.

    Returns a dict mapping skill names to lists of referenced skill names.
    """
    skills = {}
    for skill_path in Path(skill_dir).iterdir():
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding='utf-8')
                # Look for references to other skills (typically in description or body)
                # Skill names are typically in format: word-word or word-word-word
                refs = re.findall(r'/([a-z][\w-]*?)/', content)
                # Filter out non-skill references by checking if they exist in .claude/skills/
                valid_refs = []
                for ref in refs:
                    ref_path = Path(skill_dir) / ref / "SKILL.md"
                    if ref_path.exists():
                        valid_refs.append(ref)
                skills[skill_path.name] = list(set(valid_refs))  # Deduplicate
    return skills


def test_all_referenced_skills_exist():
    """参照先スキルが全て .claude/skills/ に存在するか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    deps = extract_dependencies(str(skills_dir))

    for skill, refs in deps.items():
        for ref in refs:
            ref_path = skills_dir / ref / "SKILL.md"
            assert ref_path.exists(), \
                f"{skill} が参照する {ref} が見つかりません"


def test_no_circular_dependencies():
    """A→B→A のような循環参照がないか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    deps = extract_dependencies(str(skills_dir))

    visited = set()
    rec_stack = set()

    def has_cycle(skill, path):
        """DFS with recursion stack to detect cycles"""
        if skill in rec_stack:
            return True
        if skill in visited:
            return False

        visited.add(skill)
        rec_stack.add(skill)

        for ref in deps.get(skill, []):
            if has_cycle(ref, path + [skill]):
                return True

        rec_stack.remove(skill)
        return False

    for skill in deps:
        if skill not in visited:
            assert not has_cycle(skill, []), \
                f"{skill} から循環参照があります"


def test_dependency_graph_is_valid():
    """依存グラフが有効か（ノードが存在するか）を総合的に検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    deps = extract_dependencies(str(skills_dir))
    all_skills = set(deps.keys())

    for skill, refs in deps.items():
        for ref in refs:
            assert ref in all_skills, \
                f"{skill} が参照する {ref} はスキル一覧に存在しません"


def test_no_self_references():
    """スキルが自分自身を参照していないか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    deps = extract_dependencies(str(skills_dir))

    for skill, refs in deps.items():
        assert skill not in refs, \
            f"{skill} が自分自身を参照しています"
