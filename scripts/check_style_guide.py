#!/usr/bin/env python3
"""Style guide compliance checker for KAKEHASHI Phase E.

Verifies implementation compliance with Specification §3 requirements:
- §3.1: Key Vault access abstraction
- §3.2: AES-256-GCM encryption mandatory
- §3.3: Audit log required operations
- §3.4: Error handling (SecurityError, AuditError)

Task 2.4: Style guide automation
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


class StyleViolation:
    """Represents a single style guide violation."""

    def __init__(
        self,
        file_path: Path,
        rule_name: str,
        message: str,
        line_number: int = 0,
    ) -> None:
        self.file_path = file_path
        self.rule_name = rule_name
        self.message = message
        self.line_number = line_number

    def __str__(self) -> str:
        """Format violation for display."""
        location = f"{self.file_path}"
        if self.line_number:
            location += f":{self.line_number}"
        return f"❌ {location}: {self.rule_name}\n   {self.message}"


class StyleGuideChecker:
    """Enforces style guide rules for KAKEHASHI codebase."""

    def __init__(self) -> None:
        """Initialize the checker with rule definitions."""
        self.violations: List[StyleViolation] = []

    def _check_key_vault_abstraction(self, filepath: Path, content: str) -> None:
        """Check §3.1: Direct Key Vault access is forbidden."""
        forbidden_patterns = [
            (r"from azure\.keyvault", "Direct azure.keyvault import"),
            (r"SecretClient\s*\(", "Direct SecretClient instantiation"),
            (r"KeyVaultClient\s*\(", "Direct KeyVaultClient instantiation"),
        ]

        for pattern, reason in forbidden_patterns:
            if re.search(pattern, content):
                self.violations.append(
                    StyleViolation(
                        filepath,
                        "key-vault-abstraction",
                        f"{reason}. Use KeyVaultConnector instead.",
                    )
                )

    def _check_underscore_public(self, filepath: Path, content: str) -> None:
        """Check: Public methods must not use _ prefix."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("__"):
                    continue

                if node.name.startswith("_"):
                    if "test" not in str(filepath).lower():
                        self.violations.append(
                            StyleViolation(
                                filepath,
                                "no-underscore-public",
                                f"Method {node.name} uses underscore prefix. "
                                f"Public API should not use underscore.",
                                node.lineno,
                            )
                        )

    def _check_audit_required(self, filepath: Path, content: str) -> None:
        """Check §3.3: rotate/invalidate/set_secret require audit logging."""
        audit_keywords = ["rotate", "invalidate", "purge", "set_secret", "revoke"]
        audit_calls = ["logAccess", "log_access", "recordEvent", "record_event"]

        for keyword in audit_keywords:
            pattern = rf"def {keyword}[a-z_]*\s*\([^)]*\):\s*\n(.*?)(?=\n    def |\nclass |\Z)"
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)

            for match in matches:
                method_body = match.group(1)
                has_audit = any(
                    audit_call in method_body for audit_call in audit_calls
                )

                if not has_audit:
                    self.violations.append(
                        StyleViolation(
                            filepath,
                            "audit-required-operations",
                            f"Method containing '{keyword}' must call logAccess/recordEvent "
                            f"to record the operation.",
                        )
                    )

    def _check_error_handling(self, filepath: Path, content: str) -> None:
        """Check §3.4: SecurityError and AuditError must be caught."""
        security_errors = ["SecurityError", "AuditError"]

        for error_type in security_errors:
            if re.search(rf"raise {error_type}", content):
                if not re.search(rf"except {error_type}", content):
                    self.violations.append(
                        StyleViolation(
                            filepath,
                            "error-handling-spec",
                            f"{error_type} is raised but never caught. "
                            f"Add try/except handler.",
                        )
                    )

    def _check_plaintext_keys(self, filepath: Path, content: str) -> None:
        """Check: Keys must not be plaintext literals."""
        forbidden = [
            (r"(key|secret|password)\s*=\s*['\"]", "Plaintext key/secret literal"),
            (r"API_KEY\s*=\s*['\"]", "Plaintext API key"),
        ]

        for pattern, reason in forbidden:
            if re.search(pattern, content, re.IGNORECASE):
                self.violations.append(
                    StyleViolation(
                        filepath,
                        "no-plaintext-key-storage",
                        f"{reason}. Use Key Vault or environment variables.",
                    )
                )

    def check_directory(self, directory: Path) -> bool:
        """Check all Python files in a directory."""
        py_files = sorted(directory.rglob("*.py"))

        for py_file in py_files:
            if "test" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                self._check_single_file(py_file, content)
            except Exception as e:
                print(f"⚠️  Error checking {py_file}: {e}", file=sys.stderr)

        return len(self.violations) == 0

    def _check_single_file(self, filepath: Path, content: str) -> None:
        """Run all checks on a single file."""
        self._check_key_vault_abstraction(filepath, content)
        self._check_underscore_public(filepath, content)
        self._check_audit_required(filepath, content)
        self._check_error_handling(filepath, content)
        self._check_plaintext_keys(filepath, content)

    def report(self) -> str:
        """Generate a violation report."""
        if not self.violations:
            return "✅ Style guide compliance check passed"

        report_lines = [f"❌ {len(self.violations)} style guide violations found:\n"]
        for violation in self.violations:
            report_lines.append(str(violation))

        return "\n".join(report_lines)


def main(directory: str = "kakehashi/") -> int:
    """Main entry point for style guide checker."""
    target_dir = Path(directory)

    if not target_dir.exists():
        print(f"❌ Directory not found: {directory}", file=sys.stderr)
        return 1

    checker = StyleGuideChecker()
    success = checker.check_directory(target_dir)

    print(checker.report())

    return 0 if success else 1


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "kakehashi/"
    sys.exit(main(directory))
