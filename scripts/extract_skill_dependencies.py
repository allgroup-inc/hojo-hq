#!/usr/bin/env python3
"""
Extract skill dependencies from .claude/skills/ directory.

Looks for skill references in SKILL.md files' description fields.
References are skill names surrounded by forward slashes: /skill-name/

Usage:
    python scripts/extract_skill_dependencies.py [skills_dir]

Example:
    python scripts/extract_skill_dependencies.py .claude/skills/
"""

import os
import re
import json
import sys
from pathlib import Path


def extract_dependencies(skill_dir):
    """
    Extract dependencies from all SKILL.md files.

    Args:
        skill_dir: Path to the .claude/skills directory

    Returns:
        Dictionary mapping skill names to lists of referenced skills.
        {skill_name: [referenced_skill_1, referenced_skill_2, ...]}
    """
    skills = {}
    skill_dir = Path(skill_dir)

    for skill_path in sorted(skill_dir.iterdir()):
        if not skill_path.is_dir():
            continue

        skill_name = skill_path.name
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not read {skill_md}: {e}", file=sys.stderr)
            continue

        # Extract description field from YAML frontmatter
        # Format: description: "..." or description: ...
        match = re.search(
            r'^description:\s*["\']?(.+?)(?:["\']?\n|$)',
            content,
            re.MULTILINE
        )

        if match:
            desc = match.group(1).strip('"\'')
            # Find all skill references in format /skill-name/
            # Skill names can contain letters, digits, and hyphens
            refs = re.findall(r'/([a-z0-9\-]+)/', desc)
            # Remove duplicates and sort
            refs = sorted(set(refs))
            skills[skill_name] = refs
        else:
            skills[skill_name] = []

    return skills


def generate_markdown(dependencies):
    """
    Generate Markdown representation of skill dependencies.

    Args:
        dependencies: Dictionary mapping skills to their references

    Returns:
        Markdown string
    """
    md = "# スキル依存マップ (2026-10-04)\n\n"
    md += "スキルの相互参照関係を示します。\n"
    md += "参照形式: SKILL.md の description フィールド内で `/スキル名/` で囲まれた参照を抽出\n\n"

    md += "| スキル | 参照先スキル | 参照数 |\n"
    md += "|---|---|---|\n"

    for skill in sorted(dependencies.keys()):
        refs = dependencies[skill]
        if refs:
            ref_str = ", ".join([f"`{ref}`" for ref in refs])
            md += f"| `{skill}` | {ref_str} | {len(refs)} |\n"
        else:
            md += f"| `{skill}` | (参照なし) | 0 |\n"

    md += "\n## 依存グラフ統計\n\n"

    # Count total references
    total_refs = sum(len(refs) for refs in dependencies.values())
    skills_with_refs = sum(1 for refs in dependencies.values() if refs)

    md += f"- 総スキル数: {len(dependencies)}\n"
    md += f"- 参照を持つスキル数: {skills_with_refs}\n"
    md += f"- 総参照数: {total_refs}\n"

    # Find most referenced skills
    ref_counts = {}
    for refs in dependencies.values():
        for ref in refs:
            ref_counts[ref] = ref_counts.get(ref, 0) + 1

    if ref_counts:
        md += "\n### 参照されるスキル (被参照数降順)\n\n"
        for skill, count in sorted(ref_counts.items(), key=lambda x: -x[1]):
            md += f"- `{skill}`: {count}回\n"

    # Find circular dependencies
    def find_cycles(deps):
        """Find circular dependencies"""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in deps.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path[:])
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.remove(node)

        for skill in deps:
            if skill not in visited:
                dfs(skill, [])

        return cycles

    cycles = find_cycles(dependencies)
    if cycles:
        md += f"\n### 循環参照 (警告)\n\n"
        for cycle in cycles:
            md += f"- {' → '.join(cycle)}\n"
    else:
        md += f"\n### 循環参照\nなし ✓\n"

    return md


def main():
    skill_dir = sys.argv[1] if len(sys.argv) > 1 else ".claude/skills"

    # Extract dependencies
    dependencies = extract_dependencies(skill_dir)

    # Generate and print Markdown
    markdown = generate_markdown(dependencies)
    print(markdown)

    # Also return JSON for testing
    return dependencies


if __name__ == "__main__":
    main()
