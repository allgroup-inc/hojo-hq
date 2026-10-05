"""
Test suite for skill dependencies.

Validates that:
1. All referenced skills exist in .claude/skills/
2. There are no circular dependencies
3. All skills can be loaded
"""

import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from extract_skill_dependencies import extract_dependencies


class TestSkillDependencies:
    """Test suite for skill dependency validation"""
    
    @classmethod
    def setup_class(cls):
        """Setup: Extract all dependencies once"""
        cls.skills_dir = Path(__file__).parent.parent.parent / ".claude" / "skills"
        cls.dependencies = extract_dependencies(str(cls.skills_dir))
    
    def test_all_referenced_skills_exist(self):
        """
        All referenced skills must exist in .claude/skills/
        
        This test ensures that when a skill references another skill,
        that referenced skill's SKILL.md file actually exists.
        """
        missing_skills = []
        
        for skill, refs in self.dependencies.items():
            for ref in refs:
                ref_skill_path = self.skills_dir / ref / "SKILL.md"
                if not ref_skill_path.exists():
                    missing_skills.append({
                        'skill': skill,
                        'missing_ref': ref,
                        'expected_path': str(ref_skill_path)
                    })
        
        assert len(missing_skills) == 0, (
            f"Found {len(missing_skills)} missing skill references:\n" +
            "\n".join([
                f"  - {item['skill']} references {item['missing_ref']} "
                f"(expected at {item['expected_path']})"
                for item in missing_skills
            ])
        )
    
    def test_no_circular_dependencies(self):
        """
        Detect circular dependencies (A→B→A)
        
        Circular dependencies can cause infinite loops when processing
        skills in dependency order. This test uses depth-first search
        to detect cycles.
        """
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node, path):
            """Depth-first search to detect cycles"""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.dependencies.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path[:])
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            
            rec_stack.remove(node)
        
        # Start DFS from each skill
        for skill in self.dependencies:
            if skill not in visited:
                dfs(skill, [])
        
        assert len(cycles) == 0, (
            f"Found {len(cycles)} circular dependency cycles:\n" +
            "\n".join([f"  - {' → '.join(cycle)}" for cycle in cycles])
        )
    
    def test_all_skills_have_skill_md(self):
        """
        All skill directories must have a SKILL.md file.
        
        This is a basic sanity check to ensure skill structure is valid.
        """
        missing_skill_md = []
        
        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue
            
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                missing_skill_md.append(skill_path.name)
        
        assert len(missing_skill_md) == 0, (
            f"Found {len(missing_skill_md)} skill directories without SKILL.md:\n" +
            "\n".join([f"  - {skill}" for skill in missing_skill_md])
        )
    
    def test_dependencies_dict_structure(self):
        """
        Validate the structure of the dependencies dictionary.
        
        Each skill should map to a list of referenced skills (strings).
        """
        assert isinstance(self.dependencies, dict), "Dependencies must be a dict"
        
        for skill, refs in self.dependencies.items():
            assert isinstance(skill, str), f"Skill name must be string: {skill}"
            assert isinstance(refs, list), f"References for {skill} must be list"
            
            for ref in refs:
                assert isinstance(ref, str), (
                    f"Reference in {skill} must be string, got {type(ref)}: {ref}"
                )
    
    def test_no_self_references(self):
        """
        Skills should not reference themselves.
        
        A skill referencing itself (e.g., /humanizer/ in humanizer/SKILL.md)
        is likely an error.
        """
        self_refs = []
        
        for skill, refs in self.dependencies.items():
            if skill in refs:
                self_refs.append(skill)
        
        assert len(self_refs) == 0, (
            f"Found {len(self_refs)} skills that reference themselves:\n" +
            "\n".join([f"  - {skill}" for skill in self_refs])
        )
    
    def test_dependency_statistics(self):
        """
        Log dependency statistics for monitoring.
        
        This test generates statistics about the dependency graph
        and fails only if something looks wrong structurally.
        """
        total_skills = len(self.dependencies)
        skills_with_refs = sum(1 for refs in self.dependencies.values() if refs)
        total_refs = sum(len(refs) for refs in self.dependencies.values())
        
        # Calculate in-degree (how many times each skill is referenced)
        in_degree = {}
        for refs in self.dependencies.values():
            for ref in refs:
                in_degree[ref] = in_degree.get(ref, 0) + 1
        
        most_referenced = sorted(
            in_degree.items(), key=lambda x: -x[1]
        )[:5]
        
        print(f"\n\nDependency Statistics:")
        print(f"  Total skills: {total_skills}")
        print(f"  Skills with references: {skills_with_refs}")
        print(f"  Total references: {total_refs}")
        print(f"  Average refs per skill: {total_refs / max(1, skills_with_refs):.1f}")
        
        if most_referenced:
            print(f"  Most referenced skills:")
            for skill, count in most_referenced:
                print(f"    - {skill}: {count}x")
        
        # Basic sanity check: we should have some skills
        assert total_skills > 0, "No skills found in .claude/skills/"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
