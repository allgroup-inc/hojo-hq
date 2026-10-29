# KAKEHASHI Phase E アーキテクチャ

## 全体図

```
┌─────────────────────────────────────────────────────┐
│ Application Layer (Phase 3)                          │
│ ┌─────────┐  ┌──────────┐  ┌──────────┐            │
│ │  RBAC   │  │ Key Mgmt │  │Monitoring│            │
│ │ (3.1)   │  │  (3.2)   │  │  (3.3)   │            │
│ └────┬────┘  └────┬─────┘  └────┬─────┘            │
└─────┼─────────────┼─────────────┼─────────────────┘
      │             │             │
┌─────┼─────────────┼─────────────┼─────────────────┐
│ Core Wrapper (Phase 1)                              │
│ ┌──────────────┐  ┌─────────┐  ┌──────────────┐   │
│ │   Crypto     │  │ Audit   │  │Error Handler │   │
│ │ AES-256-GCM  │  │Collector│  │& Security    │   │
│ │   (1.2)      │  │ (1.3)   │  │Alert (1.4)   │   │
│ └──────┬───────┘  └────┬────┘  └──────┬───────┘   │
│        │               │               │            │
│ ┌──────┴───────┬───────┴─────┬────────┴────────┐  │
│ │ KeyVaultConnector (1.1)                      │  │
│ │ - Managed Identity Auth                      │  │
│ │ - 5-min cache + generation counter           │  │
│ │ - 90-day auto rotation                       │  │
│ └──────┬────────────────────────────────────────┘  │
└─────────┼─────────────────────────────────────────┘
          │
┌─────────┼─────────────────────────────────────────┐
│ CI/CD (Phase 2)                                     │
│ ┌────────────────┐  ┌────────────────────────┐    │
│ │ Pre-commit     │  │ GitHub Actions (5 gate)│    │
│ │ Hooks (2.1)    │  │ Schema / SAST / Cov 2.2│    │
│ └────────────────┘  └────────────────────────┘    │
└─────────────────────────────────────────────────────┘
          │
┌─────────┼─────────────────────────────────────────┐
│ Infrastructure (Azure)                              │
│ ┌───────────────────┐  ┌──────────────────────┐   │
│ │  Key Vault        │  │ Blob Storage (Audit) │   │
│ │ (ManagedIdentity) │  │ (Append-only)        │   │
│ └───────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Phase 1: Core Wrapper Library

### Task 1.1: KeyVaultConnector
- **責務:** Azure Key Vault との統一インターフェース
- **手法:**
  - Managed Identity 認証 (fail-fast on init)
  - Key Vault REST API 経由 secret retrieve
  - 5 分 TTL キャッシュ + generation カウンタ(emergency rotation 対応)
  - 90 日定期ローテーション + emergency rotate サポート
  - getSecret() → logAccess() → cache (順序保証)
- **外部依存:** Azure SDK (`azure-identity`, `azure-keyvault-secrets`)

### Task 1.2: CryptoService (AES-256-GCM)
- **責務:** 対称鍵暗号化・署名検証
- **手法:**
  - AES-256-GCM 暗号化(NIST recommended)
  - 16 bytes random IV per message
  - HMAC-SHA256 署名検証 (constant-time compare)
  - Invalid GCM tag on decrypt → ValueError (no silent failure)
- **依存:** Task 1.1 (key source)

### Task 1.3: AuditLogCollector
- **責務:** 監査ログの記録・署名・export
- **手法:**
  - Azure Blob AppendBlob (immutable, append-only)
  - Event ID: evt-YYYYMMDD-{uuid4}
  - 10 required fields (event_type, actor_role, resource_id, operation, status, signature, ...)
  - HMAC-SHA256 signature over all fields
  - Deterministic sort(keys alphabetical) for hash consistency
  - Export to SIEM endpoint (Task 3.3 extended)
- **依存:** Task 1.2 (HMAC)

### Task 1.4: ErrorHandler & SecurityAlert
- **責務:** セキュリティエラー・アラート管理
- **手法:**
  - SecurityError / AuditError 例外定義
  - logSecurityEvent() → audit log record
  - alertOnFailure(severity) → Slack/email/local file
  - Severity: CRITICAL(immediate) / HIGH(1min batch) / MEDIUM(file)
  - Fallback: local logging if external down
- **依存:** Task 1.3 (audit sink)

### Task 1.5: Tests & Coverage
- **責務:** Phase 1 テスト集約・カバレッジ確保
- **手法:**
  - 13 tests per task (52 total)
  - conftest.py fixtures: mock_key_vault_client, mock_audit_collector, ...
  - Coverage >= 85% (expected 100%)

## Phase 2: CI/CD Gates

### Task 2.1: Pre-commit Hooks
- Black, mypy, isort, bandit local checks

### Task 2.2: GitHub Actions Security Gate
- 5 automated checks: schema, anti-pattern, style, SAST, coverage

### Task 2.3: Audit Log Schema
- JSON Schema definition + validation script

### Task 2.4: SAST & Style Compliance
- Semgrep rules + check_style_guide.py

### Task 2.5: Documentation
- style-guide.md, key-rotation-ops.md, architecture-guide.md (this file)

## Phase 3: Advanced Features (Parallel)

### Task 3.1: RBAC Layer
- Role-based access control (SYSTEM/OPERATOR/AUDITOR/GUEST)
- Depends on: Phase 1, Phase 2

### Task 3.2: Key Rotation Service
- Scheduled 90-day rotation + emergency rotate API
- Depends on: Task 3.1 + Phase 2

### Task 3.3: Monitoring & Alerting
- Audit log anomaly detection, export to SIEM
- Depends on: Tasks 3.1-3.2

### Task 3.4: Staging Integration
- E2E test with all Phase 3 components
- Depends on: Tasks 3.1-3.3

## Security Model: Shared Responsibility

| Layer | Responsibility | Implementer |
|---|---|---|
| **Infrastructure** | Azure network, storage encryption at rest, firewall | Azure |
| **Key Management** | ManagedIdentity setup, RBAC roles, audit logging | KAKEHASHI (Phase 1-3) |
| **Application** | Encryption/decryption logic, error handling | KAKEHASHI (Phase 1) |
| **Operations** | Key rotation schedule, incident response | Operations team (Phase 3.3 tooling) |

## Data Flow: Example (Key Retrieval)

```
Application Request
    │
    ├─> KeyVaultConnector.getSecret("db-password")
    │       │
    │       ├─> Check cache (generation valid?)
    │       │   ├─> HIT: return cached key + logAccess(SUCCESS)
    │       │   └─> MISS: continue
    │       │
    │       ├─> Azure Key Vault /secrets/{name}/versions/latest
    │       │   └─> ManagedIdentity auth (fail-fast)
    │       │
    │       ├─> Decode base64 → bytes
    │       │
    │       ├─> logAccess("GET", actor_role, resource_id, operation="GET", status=SUCCESS)
    │       │   │
    │       │   ├─> AuditLogCollector.recordEvent()
    │       │   │
    │       │   └─> Check audit success before cache write (Fix 4)
    │       │
    │       └─> Cache[secret_name, version] = {key: bytes, generation: N, ttl_expires: now+5min}
    │
    └─> Application uses key
        │
        └─> CryptoService.decrypt(ciphertext, key)
            │
            ├─> Extract IV from EncryptedData
            │
            ├─> AES-256-GCM decrypt (GCM tag validates integrity)
            │
            └─> Return plaintext

[Audit Trail]
AuditLogCollector writes:
{
  "event_id": "evt-20261029-abc12345",
  "timestamp": "2026-10-29T14:33:00Z",
  "event_type": "KEY_ACCESS",
  "actor": "app-service",
  "actor_role": "SYSTEM",
  "resource_id": "db-password",
  "operation": "GET",
  "status": "SUCCESS",
  "signature": "hmac_sha256_hex_64_chars",
  "result": {"key_version": "v123", "cached": false}
}
```

## Next Steps: Phase 4-6

- **Phase 4:** External security audit (whitebox penetration test)
- **Phase 5:** Blue-Green production deployment + Canary rollout
- **Phase 6:** Operations handbook + Salesforce Shield compliance certification
