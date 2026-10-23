"""
SKILL.md format validation tests.

This module validates that all skills in .claude/skills/ directory
conform to the required format specifications:
1. All skills must have ## Step n sections
2. All skills must have ## 検証失敗時 section
3. All skills must have ## 本番前テスト section
"""

import re
from pathlib import Path


def test_all_skills_have_step_sections():
    """全スキルが ## Step n セクションを持つか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            steps = re.findall(r'^## Step \d+:', content, re.MULTILINE)
            assert len(steps) > 0, f"{skill_dir.name} に Step セクションがありません"


def test_all_skills_have_failure_section():
    """全スキルが ## 検証失敗時 セクションを持つか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            assert "## 検証失敗時" in content, \
                f"{skill_dir.name} に「検証失敗時」セクションがありません"


def test_all_skills_have_local_test_section():
    """全スキルが ## 本番前テスト セクションを持つか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            assert "## 本番前テスト" in content, \
                f"{skill_dir.name} に「本番前テスト」セクションがありません"


def test_skill_md_files_exist():
    """全スキルディレクトリが SKILL.md を持つか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    for skill_dir in skills_dir.iterdir():
        # Skip special files/directories
        if skill_dir.name.startswith('.') or skill_dir.name.endswith('-LICENSE') or skill_dir.name.endswith('.md'):
            continue

        if skill_dir.is_dir():
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.exists(), f"{skill_dir.name}/SKILL.md が見つかりません"


def test_step_sections_are_numbered():
    """Step セクションが正しく番号付けされているか検査"""
    skills_dir = Path('.claude/skills')
    assert skills_dir.exists(), f"{skills_dir} ディレクトリが見つかりません"

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            # Check that if steps exist, they are sequentially numbered starting from 1
            steps = re.findall(r'^## Step (\d+):', content, re.MULTILINE)
            if len(steps) > 0:
                # Convert to integers for comparison
                step_nums = [int(s) for s in steps]
                # Steps should be sequential starting from 1
                expected = list(range(1, len(step_nums) + 1))
                assert step_nums == expected, \
                    f"{skill_dir.name}: Step番号がシーケンシャルではありません (期待: {expected}, 実際: {step_nums})"
