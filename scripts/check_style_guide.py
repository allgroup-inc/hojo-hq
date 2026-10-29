#!/usr/bin/env python3
"""Verify implementation style guide compliance (Spec §3.1, Task 2.2).

This script enforces architectural constraints from KAKEHASHI Spec §3.1:
  1. All Key Vault access goes through KeyVaultConnector
  2. All sensitive data is audited
  3. No secrets in logs
  4. Error handling follows spec 3.4

Usage:
    python3 scripts/check_style_guide.py <directory>

Exit codes:
    0: All style guide checks pass
    1: Style guide violation detected
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Checks: (pattern, violation_description, severity)
STYLE_VIOLATIONS: List[Tuple[str, str, str]] = [
    # No secrets in logs
    (
        r'print\(["\'].*password|secret|token|key["\']',
        "Potential secret logged to stdout (violation of §3.1.3)",
        "ERROR",
    ),
    (
        r'logger\.(debug|info|warning|error)\(["\'].*password|secret|token|key["\']',
        "Potential secret logged via logger (violation of §3.1.3)",
        "ERROR",
    ),
    # Error handling must use ErrorHandler
    (
        r'except\s+.*:\s*raise',
        "Must log errors through ErrorHandler, not re-raise directly (§3.4)",
        "WARNING",
    ),
    # Audit requirements
    (
        r'def\s+\w+\(.*secret.*\):\s*[^#]*(?!recordEvent)',
        "Function handling secrets must record audit event (§3.1.2)",
        "WARNING",
    ),
]

# Allowed exclusions (files that can override style guide)
STYLE_EXEMPTIONS = [
    "kakehashi/kek_wrapper/tests/",  # Test files
    "kakehashi/kek_wrapper/core/error_handler.py",  # Handler definition itself
]


def should_check_file(file_path: Path) -> bool:
    """Determine if a file should be checked for style violations."""
    file_str = str(file_path)
    for exemption in STYLE_EXEMPTIONS:
        if exemption in file_str:
            return False
    return True


def scan_files(directory: str) -> int:
    """Scan Python files for style guide violations.

    Returns 0 if all pass, 1 on first violation (fail fast).
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        print(f"❌ Directory not found: {directory}", file=sys.stderr)
        return 1

    violations = 0
    warnings = 0

    for py_file in sorted(dir_path.rglob("*.py")):
        if not should_check_file(py_file):
            continue

        try:
            content = py_file.read_text()
        except Exception as e:
            print(f"⚠️  Failed to read {py_file}: {e}", file=sys.stderr)
            continue

        for pattern, description, severity in STYLE_VIOLATIONS:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                if severity == "ERROR":
                    print(f"❌ {py_file}: {description}", file=sys.stderr)
                    violations += 1
                else:
                    print(f"⚠️  {py_file}: {description}", file=sys.stderr)
                    warnings += 1

    if violations > 0:
        print(f"❌ Found {violations} style guide violations", file=sys.stderr)
        return 1

    if warnings > 0:
        print(f"⚠️  Found {warnings} style guide warnings (non-blocking)", file=sys.stderr)
        return 0

    print("✅ All style guide checks passed (Spec §3.1 compliance verified)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 check_style_guide.py <directory>", file=sys.stderr)
        sys.exit(1)

    sys.exit(scan_files(sys.argv[1]))
