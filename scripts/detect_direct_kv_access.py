#!/usr/bin/env python3
"""Detect direct Key Vault access patterns (Task 2.2).

This script scans Python files to enforce the architectural constraint:
**All Key Vault access MUST go through KeyVaultConnector** (Task 1.1).

Forbidden patterns:
  - from azure.keyvault import *
  - SecretClient(...)
  - KeyVaultClient(...)
  - KeyVaultAuthenticationError, ...)

The only allowed way to access Key Vault is through:
  - kakehashi.kek_wrapper.KeyVaultConnector

Usage:
    python3 scripts/detect_direct_kv_access.py <directory>

Exit codes:
    0: No direct Key Vault access found
    1: Direct Key Vault access detected
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Forbidden patterns that indicate direct Key Vault usage
FORBIDDEN_PATTERNS: List[Tuple[str, str]] = [
    (r"from\s+azure\.keyvault", "Direct azure.keyvault import"),
    (r"import\s+.*azure\.keyvault", "Direct azure.keyvault import"),
    (r"SecretClient\s*\(", "Direct SecretClient instantiation"),
    (r"KeyVaultClient\s*\(", "Direct KeyVaultClient instantiation"),
    (r"CertificateClient\s*\(", "Direct CertificateClient instantiation"),
    (r"KeyClient\s*\(", "Direct KeyClient instantiation"),
]

# Files and paths that are allowed to use direct Key Vault access
ALLOWED_PATHS = [
    "kakehashi/kek_wrapper/core/key_vault_connector.py",  # The connector itself
    "kakehashi/kek_wrapper/tests/conftest.py",  # Test mocks
    "kakehashi/kek_wrapper/tests/test_key_vault_connector.py",  # Connector tests
]


def should_check_file(file_path: Path) -> bool:
    """Determine if a file should be checked.

    Files in ALLOWED_PATHS are exempt from the direct access check.
    """
    file_str = str(file_path.relative_to(Path.cwd()) if Path.cwd() in file_path.parents else file_path)
    for allowed in ALLOWED_PATHS:
        if file_str.endswith(allowed) or allowed in file_str:
            return False
    return True


def scan_files(directory: str) -> int:
    """Scan Python files for forbidden Key Vault access patterns.

    Returns 0 if no violations, 1 on first violation (fail fast).
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        print(f"❌ Directory not found: {directory}", file=sys.stderr)
        return 1

    violations = 0

    for py_file in sorted(dir_path.rglob("*.py")):
        if not should_check_file(py_file):
            continue

        try:
            content = py_file.read_text()
        except Exception as e:
            print(f"⚠️  Failed to read {py_file}: {e}", file=sys.stderr)
            continue

        for pattern, description in FORBIDDEN_PATTERNS:
            if re.search(pattern, content):
                print(
                    f"❌ {py_file}: {description} detected",
                    file=sys.stderr,
                )
                print(
                    f"   📋 Use KeyVaultConnector instead "
                    f"(from kakehashi.kek_wrapper import KeyVaultConnector)",
                    file=sys.stderr,
                )
                print(
                    f"   📍 Pattern: {pattern}",
                    file=sys.stderr,
                )
                violations += 1
                if violations > 0:
                    # Fail fast on first violation
                    return 1

    if violations == 0:
        print("✅ No direct Key Vault access detected")
        return 0
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 detect_direct_kv_access.py <directory>", file=sys.stderr)
        sys.exit(1)

    sys.exit(scan_files(sys.argv[1]))
