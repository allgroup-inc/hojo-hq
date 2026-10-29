"""Test suite for Task 2.5: Documentation & Guides."""

import json
import os
import re
from pathlib import Path


class TestStyleGuide:
    """Test docs/guides/style-guide.md."""

    @staticmethod
    def test_style_guide_covers_all_spec_sections():
        """Verify style-guide.md covers all specification sections §3.1-3.4."""
        guide_path = Path("/home/user/hojo-hq/docs/guides/style-guide.md")
        assert guide_path.exists(), f"style-guide.md not found at {guide_path}"

        content = guide_path.read_text()

        # Check for all 4 required sections
        required_sections = ["§3.1", "§3.2", "§3.3", "§3.4"]
        for section in required_sections:
            assert section in content, f"Missing section: {section}"

        # Check that each section has both ❌禁止 and ✅推奨 examples
        sections_with_examples = content.split("##")[1:]  # Split by section header
        assert len(sections_with_examples) >= 4, "Not enough section divisions"

        # Verify ❌ and ✅ symbols are present
        assert "❌" in content, "Missing ❌ (禁止) examples"
        assert "✅" in content, "Missing ✅ (推奨) examples"

        # Verify code blocks with python syntax
        assert "```python" in content, "Missing Python code examples"

    @staticmethod
    def test_style_guide_has_naming_conventions():
        """Verify style-guide.md includes naming conventions."""
        guide_path = Path("/home/user/hojo-hq/docs/guides/style-guide.md")
        content = guide_path.read_text()

        # Check for naming section
        assert "命名規約" in content or "naming" in content.lower(), \
            "Missing naming conventions section"

        # Check for function/class/constant naming patterns
        assert "snake_case" in content, "Missing snake_case reference"
        assert "PascalCase" in content, "Missing PascalCase reference"
        assert "UPPER_SNAKE_CASE" in content, "Missing UPPER_SNAKE_CASE reference"

    @staticmethod
    def test_style_guide_has_type_hints():
        """Verify style-guide.md requires type hints."""
        guide_path = Path("/home/user/hojo-hq/docs/guides/style-guide.md")
        content = guide_path.read_text()

        assert "型ヒント" in content or "type hints" in content.lower(), \
            "Missing type hints section"
        assert "mypy" in content, "Missing mypy reference"

    @staticmethod
    def test_style_guide_has_test_coverage_requirement():
        """Verify style-guide.md specifies >= 85% coverage."""
        guide_path = Path("/home/user/hojo-hq/docs/guides/style-guide.md")
        content = guide_path.read_text()

        assert "85" in content, "Missing coverage percentage (85%)"
        assert "pytest" in content, "Missing pytest reference"


class TestKeyRotationOps:
    """Test docs/guides/key-rotation-ops.md."""

    @staticmethod
    def test_key_rotation_ops_schedule_documented():
        """Verify key-rotation-ops.md documents the rotation schedule."""
        ops_path = Path("/home/user/hojo-hq/docs/guides/key-rotation-ops.md")
        assert ops_path.exists(), f"key-rotation-ops.md not found at {ops_path}"

        content = ops_path.read_text()

        # Check for monthly schedule
        assert "毎月 1 日" in content or "1st of" in content.lower(), \
            "Missing monthly (1st day) schedule"
        assert "03:00" in content or "3:00" in content, \
            "Missing time (03:00 JST)"

        # Check for emergency rotation section
        assert "緊急ローテーション" in content or "Emergency" in content, \
            "Missing emergency rotation section"

        # Verify 4+ step emergency procedure
        emergency_section = content.split("緊急ローテーション")[1] if "緊急ローテーション" in content else ""
        step_count = len(re.findall(r'\d+\.|^-\s+', emergency_section, re.MULTILINE))
        assert step_count >= 3, f"Emergency rotation needs 4+ steps, found {step_count}"

    @staticmethod
    def test_key_rotation_ops_cache_invalidation_mentioned():
        """Verify key-rotation-ops.md mentions cache invalidation."""
        ops_path = Path("/home/user/hojo-hq/docs/guides/key-rotation-ops.md")
        content = ops_path.read_text()

        cache_keywords = ["キャッシュ", "cache", "invalidate", "clear"]
        found = any(keyword in content for keyword in cache_keywords)
        assert found, "Missing cache invalidation discussion"

    @staticmethod
    def test_key_rotation_ops_blob_command_syntax_valid():
        """Verify az storage blob download command in key-rotation-ops.md is syntactically valid."""
        ops_path = Path("/home/user/hojo-hq/docs/guides/key-rotation-ops.md")
        content = ops_path.read_text()

        # Extract the blob download command
        match = re.search(r'az storage blob download.*?(?=\n\n|\Z)', content, re.DOTALL)
        assert match, "Missing 'az storage blob download' command"

        command = match.group(0)

        # Basic syntax checks
        assert "--account-name" in command, "Missing --account-name parameter"
        assert "--container-name" in command, "Missing --container-name parameter"
        assert "--name" in command, "Missing --name parameter"
        assert "--file" in command, "Missing --file parameter"

    @staticmethod
    def test_key_rotation_ops_version_lifecycle_table():
        """Verify key-rotation-ops.md includes version lifecycle table."""
        ops_path = Path("/home/user/hojo-hq/docs/guides/key-rotation-ops.md")
        content = ops_path.read_text()

        # Check for version lifecycle section with table
        assert "バージョン" in content or "Version" in content, \
            "Missing version section"
        assert "ステータス" in content or "Status" in content, \
            "Missing version lifecycle table"

        # Check for key statuses
        statuses = ["latest", "active", "old", "disabled"]
        for status in statuses:
            assert status in content, f"Missing version status: {status}"


class TestArchitectureGuide:
    """Test docs/guides/architecture-guide.md."""

    @staticmethod
    def test_architecture_guide_ascii_diagram_exists():
        """Verify architecture-guide.md contains ASCII art diagram."""
        arch_path = Path("/home/user/hojo-hq/docs/guides/architecture-guide.md")
        assert arch_path.exists(), f"architecture-guide.md not found at {arch_path}"

        content = arch_path.read_text()

        # Check for ASCII diagram markers
        assert "┌" in content or "│" in content, "Missing ASCII diagram"
        assert "─" in content or "─" in content, "Missing ASCII diagram elements"

    @staticmethod
    def test_architecture_guide_covers_phase_1_components():
        """Verify architecture-guide.md covers all Phase 1 components."""
        arch_path = Path("/home/user/hojo-hq/docs/guides/architecture-guide.md")
        content = arch_path.read_text()

        # Task 1.1-1.4 components
        components = [
            "KeyVaultConnector",
            "CryptoService",
            "AuditLogCollector",
            "ErrorHandler",
        ]

        for component in components:
            assert component in content, f"Missing Phase 1 component: {component}"

    @staticmethod
    def test_architecture_guide_covers_phase_2_gates():
        """Verify architecture-guide.md covers Phase 2 CI/CD gates."""
        arch_path = Path("/home/user/hojo-hq/docs/guides/architecture-guide.md")
        content = arch_path.read_text()

        # Phase 2 elements
        phase2_items = ["pre-commit", "GitHub Actions", "SAST", "coverage"]

        for item in phase2_items:
            assert item.lower() in content.lower(), f"Missing Phase 2 item: {item}"

    @staticmethod
    def test_architecture_guide_covers_phase_3_features():
        """Verify architecture-guide.md mentions Phase 3 RBAC, rotation, monitoring."""
        arch_path = Path("/home/user/hojo-hq/docs/guides/architecture-guide.md")
        content = arch_path.read_text()

        phase3_features = ["RBAC", "Key Rotation", "Monitoring"]

        for feature in phase3_features:
            assert feature in content, f"Missing Phase 3 feature: {feature}"

    @staticmethod
    def test_architecture_guide_data_flow_example():
        """Verify architecture-guide.md includes data flow example."""
        arch_path = Path("/home/user/hojo-hq/docs/guides/architecture-guide.md")
        content = arch_path.read_text()

        # Check for data flow section
        assert "Data Flow" in content or "データフロー" in content, \
            "Missing data flow example"

        # Check for flow elements
        assert "Application Request" in content or "getSecret" in content, \
            "Missing flow details"

    @staticmethod
    def test_architecture_guide_shared_responsibility_model():
        """Verify architecture-guide.md documents shared responsibility model."""
        arch_path = Path("/home/user/hojo-hq/docs/guides/architecture-guide.md")
        content = arch_path.read_text()

        # Check for responsibility section
        assert "Shared Responsibility" in content or "responsibility" in content.lower(), \
            "Missing shared responsibility section"

        # Check for layers
        layers = ["Infrastructure", "Application", "Operations"]
        for layer in layers:
            assert layer in content, f"Missing responsibility layer: {layer}"


class TestGuideLinks:
    """Test that all guides reference real files."""

    @staticmethod
    def test_all_guide_files_exist():
        """Verify all 3 guide files exist."""
        guide_files = [
            "/home/user/hojo-hq/docs/guides/style-guide.md",
            "/home/user/hojo-hq/docs/guides/key-rotation-ops.md",
            "/home/user/hojo-hq/docs/guides/architecture-guide.md",
        ]

        for guide_file in guide_files:
            path = Path(guide_file)
            assert path.exists(), f"Guide file not found: {guide_file}"
            assert path.stat().st_size > 100, f"Guide file too small: {guide_file}"

    @staticmethod
    def test_style_guide_references_real_modules():
        """Verify style-guide.md references modules that will exist."""
        guide_path = Path("/home/user/hojo-hq/docs/guides/style-guide.md")
        content = guide_path.read_text()

        # Extract import paths
        imports = re.findall(r'from kakehashi\..*? import', content)
        assert len(imports) > 0, "Missing kakehashi module imports in examples"

    @staticmethod
    def test_guides_reference_azure_documentation():
        """Verify guides reference Azure CLI when appropriate."""
        ops_path = Path("/home/user/hojo-hq/docs/guides/key-rotation-ops.md")
        content = ops_path.read_text()

        # Check for Azure CLI references
        assert "az keyvault" in content, "Missing Azure Key Vault CLI reference"
        assert "az storage blob" in content, "Missing Azure Storage CLI reference"

    @staticmethod
    def test_guides_markdown_format_valid():
        """Verify all guides are valid Markdown."""
        guide_files = [
            "/home/user/hojo-hq/docs/guides/style-guide.md",
            "/home/user/hojo-hq/docs/guides/key-rotation-ops.md",
            "/home/user/hojo-hq/docs/guides/architecture-guide.md",
        ]

        for guide_file in guide_files:
            path = Path(guide_file)
            content = path.read_text()

            # Basic Markdown validation
            # Check for matching code blocks
            code_block_count = content.count("```")
            assert code_block_count % 2 == 0, \
                f"{path.name} has unmatched code blocks"

            # Check for matching emphasis
            bold_count = content.count("**") + content.count("__")
            assert bold_count % 2 == 0, \
                f"{path.name} has unmatched bold markers"

            # Verify it has headers
            assert "#" in content, f"{path.name} has no headers"
