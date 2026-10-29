# Audit Log Schema

## Overview

The canonical JSON Schema for all audit log entries in KAKEHASHI Phase E. This schema defines the immutable contract that all audit log entries must satisfy before storage or transmission.

**Location:** `kakehashi/schemas/audit_log_schema.json`  
**Schema Version:** Phase E, Task 2.3 (Immutable)

## Required Fields (9 total)

- **event_id** (string): Unique event identifier
  - Format: `evt-YYYYMMDD-[a-f0-9]{8}`
  - Example: `evt-20261109-a1b2c3d4`

- **timestamp** (string): ISO 8601 UTC timestamp
  - Format: Must end with `Z` (no `+00:00` alternatives)
  - Example: `2026-11-09T09:00:00Z`
  - Example with microseconds: `2026-11-09T09:00:00.123456Z`

- **event_type** (enum): Type of event
  - Valid values: `KEY_ACCESS`, `KEY_ROTATE`, `SECURITY`, `CRYPTO`, `AUDIT`
  - Example: `KEY_ACCESS`

- **actor** (string): User or service ID making the request
  - Example: `user-abc123`, `service-key-vault`

- **actor_role** (enum): Role of the actor
  - Valid values: `SYSTEM`, `OPERATOR`, `AUDITOR`, `GUEST`
  - Example: `OPERATOR`

- **resource_id** (string): Resource being accessed (secret name, key ID, etc.)
  - Example: `https://vault.azure.net/secrets/kek/v1`

- **operation** (enum): Operation performed
  - Valid values: `GET`, `PUT`, `ROTATE`, `DELETE`, `VERIFY`
  - Example: `GET`

- **status** (enum): Outcome of the operation
  - Valid values: `SUCCESS`, `FAILURE`, `DENIED`
  - Example: `SUCCESS`

- **signature** (string): HMAC-SHA256 signature
  - Format: Hexadecimal string, exactly 64 characters
  - Calculated over all other fields (signature field excluded)
  - Example: `a1b2c3d4e5f6...` (64 hex chars)

## Optional Fields

- **result** (object): Operation result data
  - Type: Object with arbitrary properties
  - Used for: ciphertext length, key version, error codes, etc.
  - Example: `{"ciphertext_length": 48, "key_version": "v1"}`

- **context** (object): Extra metadata
  - Type: Object with arbitrary properties
  - Used for: IP address, user agent, error details, etc.
  - Example: `{"ip_address": "192.0.2.1", "user_agent": "curl/7.64.1"}`

## Validation Rules

- **additionalProperties: false** — No fields beyond those listed above are permitted
- **required fields** — All 9 required fields must be present in every entry
- **pattern matching** — event_id and signature must match their regex patterns
- **enum enforcement** — event_type, actor_role, operation, and status must be exact enum matches
- **immutability** — Schema changes require formal議事 with三名体制; this version is frozen

## Examples

### Valid Entry (Minimal)

```json
{
  "event_id": "evt-20261109-a1b2c3d4",
  "timestamp": "2026-11-09T09:00:00Z",
  "event_type": "KEY_ACCESS",
  "actor": "user-123",
  "actor_role": "OPERATOR",
  "resource_id": "https://vault.azure.net/secrets/kek/v1",
  "operation": "GET",
  "status": "SUCCESS",
  "result": {},
  "context": {},
  "signature": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

### Valid Entry (With Context)

```json
{
  "event_id": "evt-20261109-b5d6e7f8",
  "timestamp": "2026-11-09T09:15:30.123456Z",
  "event_type": "KEY_ROTATE",
  "actor": "service-admin",
  "actor_role": "SYSTEM",
  "resource_id": "https://vault.azure.net/keys/kek/v2",
  "operation": "ROTATE",
  "status": "SUCCESS",
  "result": {
    "new_version": "v2",
    "rotated_at": "2026-11-09T09:15:30Z"
  },
  "context": {
    "ip_address": "203.0.113.42",
    "user_agent": "KAKEHASHI/Phase-E",
    "request_id": "req-12345"
  },
  "signature": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

### Valid Entry (Failure)

```json
{
  "event_id": "evt-20261109-c7d8e9f0",
  "timestamp": "2026-11-09T09:30:00Z",
  "event_type": "KEY_ACCESS",
  "actor": "user-456",
  "actor_role": "GUEST",
  "resource_id": "https://vault.azure.net/secrets/sensitive/v1",
  "operation": "GET",
  "status": "DENIED",
  "result": {
    "error_code": "Forbidden"
  },
  "context": {
    "reason": "insufficient permissions"
  },
  "signature": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
}
```

## Validation

All audit entries MUST pass JSON Schema validation before being stored or transmitted.

### Using the Validation Tool

```bash
# Validate a single entry from file
python scripts/validate_audit_schema.py entry.json

# Validate from stdin
cat entry.json | python scripts/validate_audit_schema.py -

# Exit codes:
#   0: valid
#   1: invalid
#   2: error (file not found, bad JSON, schema not found, etc.)
```

### Using jsonschema in Python

```python
import json
import jsonschema
from pathlib import Path

# Load schema
schema_path = Path("kakehashi/schemas/audit_log_schema.json")
with open(schema_path) as f:
    schema = json.load(f)

# Load entry
with open("entry.json") as f:
    entry = json.load(f)

# Validate (raises jsonschema.ValidationError on failure)
jsonschema.validate(entry, schema)
```

## Related

- **AuditLogEntry dataclass:** `kakehashi/kek_wrapper/models/audit_event.py`
- **Enums:** `kakehashi/kek_wrapper/models/enums.py` (EventType, Status, Role)
- **CryptoService:** `kakehashi/kek_wrapper/core/crypto_service.py` (signature generation)
- **Task 2.2:** CI/CD schema validation checks
- **Task 2.4:** Audit log retrieval & query compliance
