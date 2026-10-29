#!/usr/bin/env python3
"""Validation tool for audit log entries against the canonical JSON Schema.

Task 2.3: Audit log schema validation.

Usage:
    python scripts/validate_audit_schema.py <entry.json>
    python scripts/validate_audit_schema.py - < entry.json

Exit status:
    0: valid
    1: invalid
    2: error (file not found, bad JSON, schema not found, etc.)
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema not installed. Install with: pip install jsonschema>=4.0", file=sys.stderr)
    sys.exit(2)


def load_schema(schema_path: Path) -> dict:
    """Load the audit log schema from the canonical location."""
    try:
        with open(schema_path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: schema file not found: {schema_path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in schema: {e}", file=sys.stderr)
        sys.exit(2)


def load_entry(path_or_stdin: str) -> dict:
    """Load audit log entry from file or stdin."""
    if path_or_stdin == "-":
        try:
            return json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON in entry: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        try:
            with open(path_or_stdin) as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: entry file not found: {path_or_stdin}", file=sys.stderr)
            sys.exit(2)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON in entry: {e}", file=sys.stderr)
            sys.exit(2)


def validate(entry: dict, schema: dict) -> bool:
    """Validate entry against schema. Print errors on failure."""
    try:
        jsonschema.validate(entry, schema)
        return True
    except jsonschema.ValidationError as e:
        print(f"Validation error: {e.message}", file=sys.stderr)
        if e.path:
            print(f"  at: {'.'.join(str(p) for p in e.path)}", file=sys.stderr)
        if e.schema_path:
            print(f"  schema: {'/'.join(str(p) for p in e.schema_path)}", file=sys.stderr)
        return False
    except jsonschema.SchemaError as e:
        print(f"Error: invalid schema: {e.message}", file=sys.stderr)
        sys.exit(2)


def main():
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <entry.json | ->",
            file=sys.stderr,
        )
        print("  Validates an audit log entry against the canonical JSON schema.", file=sys.stderr)
        print(
            f"  Read from file or stdin (- = read from stdin)",
            file=sys.stderr,
        )
        sys.exit(2)

    # Schema is at kakehashi/schemas/audit_log_schema.json, relative to repo root.
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    schema_path = repo_root / "kakehashi" / "schemas" / "audit_log_schema.json"

    schema = load_schema(schema_path)
    entry = load_entry(sys.argv[1])

    if validate(entry, schema):
        print("Valid", file=sys.stdout)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
