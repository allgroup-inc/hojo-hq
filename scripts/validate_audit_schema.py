#!/usr/bin/env python3
"""Validate audit log JSON schema against Task 1.3 spec (Task 2.2).

This script scans all Python files in the target directory and validates
any audit entries found against the required 10-field schema:
  event_id, timestamp, event_type, actor, actor_role, resource_id,
  operation, status, result, context, signature

Fails fast on first schema violation.

Usage:
    python3 scripts/validate_audit_schema.py <directory>

Exit codes:
    0: All audit entries valid
    1: Schema violation detected
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Set

# The locked 10-field schema from Task 1.3 AuditLogEntry.to_dict()
REQUIRED_FIELDS: Set[str] = {
    "event_id",
    "timestamp",
    "event_type",
    "actor",
    "actor_role",
    "resource_id",
    "operation",
    "status",
    "result",
    "context",
    "signature",
}

# Valid enum values from kakehashi/kek_wrapper/models/enums.py
VALID_EVENT_TYPES = {
    "KEY_ACCESS",
    "KEY_ROTATE",
    "SECRET_DECRYPT",
    "USER_LOGIN",
    "DATA_EXPORT",
    "COMPLIANCE_CHECK",
    "DATA_READ",
    "KEY_VAULT_AUTH",
    "KEY_VAULT_GET_SECRET",
    "KEY_VAULT_ROTATE",
    "CRYPTO_ENCRYPT",
    "CRYPTO_DECRYPT",
    "AUDIT_EXPORT",
    "AUDIT_VALIDATE",
    "SECURITY",
}

VALID_STATUSES = {"SUCCESS", "FAILURE", "DENIED", "SKIPPED"}

VALID_ROLES = {"operator", "admin", "service"}


def validate_audit_entry(entry: Dict[str, Any], file_path: str, line_num: int) -> None:
    """Validate a single audit entry against the schema.

    Raises ValueError on schema violation.
    """
    # Check required fields
    missing = REQUIRED_FIELDS - set(entry.keys())
    extra = set(entry.keys()) - REQUIRED_FIELDS
    if missing or extra:
        msg = ""
        if missing:
            msg += f"missing={sorted(missing)} "
        if extra:
            msg += f"extra={sorted(extra)}"
        raise ValueError(
            f"{file_path}:{line_num} - audit entry schema mismatch: {msg.strip()}"
        )

    # Validate field types and values
    if not isinstance(entry["event_id"], str) or not entry["event_id"]:
        raise ValueError(
            f"{file_path}:{line_num} - event_id must be a non-empty string"
        )

    if not isinstance(entry["timestamp"], str):
        raise ValueError(f"{file_path}:{line_num} - timestamp must be a string")
    if not entry["timestamp"].endswith("Z"):
        raise ValueError(
            f"{file_path}:{line_num} - timestamp must end with 'Z' (UTC ISO 8601)"
        )

    if entry["event_type"] not in VALID_EVENT_TYPES:
        raise ValueError(
            f"{file_path}:{line_num} - invalid event_type '{entry['event_type']}'. "
            f"Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )

    if not isinstance(entry["actor"], str) or not entry["actor"]:
        raise ValueError(f"{file_path}:{line_num} - actor must be a non-empty string")

    if entry["actor_role"] not in VALID_ROLES:
        raise ValueError(
            f"{file_path}:{line_num} - invalid actor_role '{entry['actor_role']}'. "
            f"Must be one of: {', '.join(sorted(VALID_ROLES))}"
        )

    if not isinstance(entry["resource_id"], str) or not entry["resource_id"]:
        raise ValueError(
            f"{file_path}:{line_num} - resource_id must be a non-empty string"
        )

    if not isinstance(entry["operation"], str) or not entry["operation"]:
        raise ValueError(f"{file_path}:{line_num} - operation must be a non-empty string")

    if entry["status"] not in VALID_STATUSES:
        raise ValueError(
            f"{file_path}:{line_num} - invalid status '{entry['status']}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    if not isinstance(entry["result"], dict):
        raise ValueError(f"{file_path}:{line_num} - result must be a dict")

    if not isinstance(entry["context"], dict):
        raise ValueError(f"{file_path}:{line_num} - context must be a dict")

    if not isinstance(entry["signature"], str) or len(entry["signature"]) < 64:
        raise ValueError(
            f"{file_path}:{line_num} - signature must be a string with >= 64 characters "
            "(HMAC-SHA256 hex digest)"
        )


def scan_files(directory: str) -> int:
    """Scan all Python files in directory for audit entries.

    Returns 0 if all valid, 1 on first violation.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        print(f"❌ Directory not found: {directory}", file=sys.stderr)
        return 1

    violations = 0
    # JSON pattern to extract audit entries (simple heuristic)
    json_pattern = re.compile(r'(\{[^{}]*"event_id"[^{}]*\})')

    for py_file in sorted(dir_path.rglob("*.py")):
        try:
            content = py_file.read_text()
        except Exception as e:
            print(f"⚠️  Failed to read {py_file}: {e}", file=sys.stderr)
            continue

        # Look for hardcoded audit entry dicts or to_dict() returns
        # This is a heuristic; real audit entries come from AuditLogEntry.to_dict()
        for i, line in enumerate(content.split("\n"), 1):
            # Skip comments and docstrings
            if line.strip().startswith("#"):
                continue

            # Look for dict/JSON patterns that might be audit entries
            if '"event_id"' in line and "signature" in line:
                # Try to extract and validate
                try:
                    # Simple extraction for lines that look like audit dicts
                    match = json_pattern.search(content)
                    if match:
                        json_str = match.group(1)
                        try:
                            entry = json.loads(json_str)
                            if "event_id" in entry and "signature" in entry:
                                validate_audit_entry(entry, str(py_file), i)
                        except json.JSONDecodeError:
                            # Not valid JSON, skip
                            pass
                except (ValueError, KeyError) as e:
                    print(f"❌ {e}", file=sys.stderr)
                    violations += 1
                    if violations > 0:
                        # Fail fast on first violation
                        return 1

    if violations == 0:
        print("✅ All audit entries passed schema validation")
        return 0
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 validate_audit_schema.py <directory>", file=sys.stderr)
        sys.exit(1)

    sys.exit(scan_files(sys.argv[1]))
