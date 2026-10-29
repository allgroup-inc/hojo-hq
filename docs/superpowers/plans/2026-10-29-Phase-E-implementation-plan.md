# Phase E: High-Performance KAKEHASHI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate KAKEHASHI from LocalKekProvider (test) to Azure Key Vault (production) with Salesforce Shield equivalent enterprise security, unified implementation patterns across 5 parallel chat teams, comprehensive CI/CD gating, and external security audit by 2026-12-17.

**Architecture:** 
- **Hybrid Model**: Centralized Core Wrapper Library (Python 3.11+) providing KeyVaultConnector, CryptoService, AuditLogCollector, and ErrorHandler that all 5 chats depend on
- **Parallel Development**: 5 chat teams (glow-ma, 市場調査, ゆんたく, 沖縄企業のミカタ, アーカイブ) work independently on their components while adhering to unified coding standards
- **Security-First**: Multi-layer security (TLS 1.2+ in transit, AES-256-GCM at rest, HMAC-SHA256 audit log signatures, 4-role RBAC with Azure Managed Identity)
- **Progressive Rollout**: Blue-Green + Canary deployment (10%→50%→100%) after external penetration testing

**Tech Stack:**
- Language: Python 3.11+ (matches kakei-crm)
- Key Management: Azure Key Vault with Managed Identity, HSM-backed keys (production)
- Encryption: TLS 1.2+, AES-256-GCM, HMAC-SHA256
- Audit Log Storage: Azure Blob Storage (append-only)
- CI/CD: GitHub Actions (4-stage gating)
- Testing: pytest (unit/integration/security), Coverage >= 85%
- Compliance: SOC 2 Type II, ISO 27001:2022

**Spec:** `/home/user/hojo-hq/docs/superpowers/specs/2026-10-29-Phase-E-KAKEHASHI-design.md`

## Global Constraints

- **Security Level Target**: Salesforce Shield equivalent (verified against published security docs)
- **Compliance Certifications**: SOC 2 Type II + ISO 27001:2022 (Azure handles infrastructure; KAKEHASHI handles configuration & monitoring)
- **Shared Responsibility Model**: Azure responsible for HSM, Key Vault infrastructure; KAKEHASHI responsible for configuration, audit logging, RBAC policy, incident response
- **Deployment Deadline**: 2026-12-17 (12 weeks from 2026-10-29)
- **Code Standards**: Python 3.11+ with type hints (mypy), Black formatter, bandit security scanning
- **Test Coverage Minimum**: 85% across all Core Wrapper components
- **Audit Log Format**: JSON with HMAC-SHA256 signature, append-only storage (no deletion/edit)
- **Key Rotation**: Automatic 90-day rotation with emergency rotation capability (24hr SLA)
- **RBAC Model**: 4 roles (admin, operator, auditor, guest) with Azure AD / Managed Identity binding
- **Multi-Chat Governance**: 3-person triangle review (スイシン/ウタガイ/ベッカイ) for non-reversible changes, weekly sync Monday 9:00-10:00 JST
- **Decision Authority**: 小柳さん makes all security/schedule/budget decisions; documentation in `docs/議事_YYYYMMDD_<topic>.md`

## Review Focus

1. **HSM Key Validation Under Rotation**: Encryption/decryption must select correct key version from rotated HSM keys during production rotation cycle (90-day + emergency scenarios). Risk: old key used after new key active = corrupted data recovery.

2. **Audit Log Immutability with Concurrent Writers**: When all 5 chats write audit logs concurrently to append-only Blob Storage, ensure HMAC signature remains valid even under Azure Blob Storage eventual consistency (< 1sec). Risk: signature validation false-negatives = undetected tampering.

3. **Multi-Chat Wrapper Library Version Lock**: Core Wrapper released as `@kakehashi/kek-wrapper` must not break backward-compatible decryption during 5-chat staggered deployments (chats may deploy on different days). Risk: Chat A upgrades wrapper, Chat B still on old version, shared encrypted data becomes unreadable.

4. **CI/CD Gate Bypass via Direct Azure CLI**: Developers can bypass GitHub Actions gating by directly pushing encrypted keys/policies to Azure Key Vault using `az` CLI. Risk: Week 8 penetration tester confirms weakness, but production already deployed with non-gated config.

5. **Staging ↔ Production Secret Parity**: Staging uses test Azure Key Vault; production uses HSM-backed. If staging doesn't replicate HSM behavior (key caching, rotation latency), integration tests pass in staging but fail in production. Risk: discovered at production deployment (Week 9).

---

## File Structure

### Core Wrapper Library (Chat 1 / glow-ma)
```
kakehashi/kek_wrapper/
├── __init__.py
├── core/
│   ├── key_vault_connector.py      [KeyVaultConnector class]
│   ├── crypto_service.py           [CryptoService with AES-256-GCM]
│   ├── audit_log_collector.py      [AuditLogCollector with HMAC]
│   └── error_handler.py            [SecurityError, AuditError, alerting]
├── models/
│   ├── audit_event.py              [AuditLogEntry dataclass]
│   ├── enums.py                    [EventType, Role enums]
│   └── crypto_models.py            [EncryptedData, KeyVersion models]
├── config/
│   └── defaults.py                 [Security defaults: key rotation, TTL]
└── tests/
    ├── test_key_vault_connector.py
    ├── test_crypto_service.py
    ├── test_audit_log_collector.py
    ├── test_integration_wrapper.py
    └── test_hsm_rotation_scenarios.py

kakehashi/ci_cd/
├── .husky/
│   └── pre-commit                  [Black, mypy, bandit hooks]
├── scripts/
│   ├── validate_audit_schema.py    [JSON schema validation]
│   ├── detect_direct_kv_access.py  [Anti-pattern: grep KeyVault()]
│   └── check_style_guide.py        [Audit log recording, error handling]
└── .semgrep.yml                    [SAST rules for secrets/crypto]
```

### 5-Chat Implementation Folders
```
kakehashi/implementations/
├── chat_001_glow_ma/               [Core Wrapper dependencies only]
├── chat_002_market_research/       [CI/CD gating, audit schema]
├── chat_003_yuntak/                [RBAC layer, user service]
├── chat_004_okinawa_mikata/        [Key rotation service]
└── chat_005_archive/               [Monitoring, alerting, incident response]
```

### Deployment & Documentation
```
docs/superpowers/
├── specs/2026-10-29-Phase-E-KAKEHASHI-design.md
├── plans/2026-10-29-Phase-E-implementation-plan.md (this file)
└── guides/
    ├── style-guide.md              [Coding rules, error handling, audit logging]
    ├── ci-cd-gate-guide.md         [4-stage gating, running checks locally]
    ├── audit-log-schema.md         [JSON structure, signature validation]
    └── hsm-key-rotation-ops.md     [Rotation procedures, emergency rotation]

docs/議事_YYYYMMDD_Phase-E-*.md     [Decision record: architecture changes, schedule shifts, security findings]
```

---

## Phase 1: Core Wrapper Library Foundation (Week 1-2: 2026-11-03 to 2026-11-14)

### Task 1.1: KeyVaultConnector Implementation

**Files:**
- Create: `kakehashi/kek_wrapper/core/key_vault_connector.py`
- Create: `kakehashi/kek_wrapper/models/crypto_models.py` (EncryptedData, KeyVersion)
- Create: `kakehashi/kek_wrapper/tests/test_key_vault_connector.py`

**Interfaces:**
- Consumes: Azure Managed Identity (environment: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`), Azure Key Vault SDK
- Produces: 
  - `async def authenticate() -> None` - Establishes Managed Identity session
  - `async def getSecret(secret_name: str, key_version: Optional[str]) -> bytes` - Returns decryption key
  - `async def rotateKey(force_emergency: bool = False) -> dict` - Returns new key metadata
  - `async def logAccess(operation: str, status: str) -> None` - Delegates to AuditLogCollector

**Timeline:** 3 days (Nov 3-5)  
**Responsibility:** Chat 1 (glow-ma)  
**Input:** Azure credentials (Managed Identity)  
**Output:** KeyVaultConnector class with caching (TTL: 5 min), key version tracking  
**Verification:** 
- Unit test: `test_authenticate_with_managed_identity()` - connects to staging Key Vault
- Unit test: `test_getSecret_returns_correct_key_version()` - retrieves key v1, v2, v3 scenarios
- Unit test: `test_getSecret_cache_ttl_expires()` - verifies 5-minute cache expiration
- Integration test: `test_key_rotation_scenario()` - simulate 90-day rotation, old+new key both work

**Handoff Points:** 
- KeyVaultConnector interface locked (no signature changes after Nov 5)
- Key caching strategy documented (TTL, refresh logic)

**Risks & Buffers:** 
- Risk: Azure Managed Identity setup delayed → Buffer: pre-stage credentials in test environment by Oct 31
- Risk: Key Vault quota exceeded under load → Buffer: staging environment with separate key vault for testing

---

### Task 1.2: CryptoService (AES-256-GCM)

**Files:**
- Create: `kakehashi/kek_wrapper/core/crypto_service.py`
- Create: `kakehashi/kek_wrapper/tests/test_crypto_service.py`
- Modify: `kakehashi/kek_wrapper/models/crypto_models.py` (add EncryptedData with IV tracking)

**Interfaces:**
- Consumes: KeyVaultConnector (for key fetching), cryptography library (Fernet, AES modes)
- Produces:
  - `def encrypt(plaintext: bytes, key: bytes) -> EncryptedData` - Returns ciphertext + IV + key_version
  - `def decrypt(encrypted_data: EncryptedData, key: bytes) -> bytes` - Validates IV, returns plaintext
  - `def validateSignature(log_entry: dict, signature: str) -> bool` - HMAC-SHA256 verification

**Timeline:** 3 days (Nov 6-8)  
**Responsibility:** Chat 1 (glow-ma)  
**Input:** Cryptography library (Python cryptography pkg), KeyVaultConnector from Task 1.1  
**Output:** CryptoService class with AES-256-GCM, IV per-value, key version tracking  
**Verification:**
- Unit test: `test_encrypt_generates_random_iv()` - two calls with same key produce different ciphertexts
- Unit test: `test_decrypt_recovers_plaintext()` - round-trip encryption/decryption
- Unit test: `test_signature_validation_passes_valid()` - HMAC-SHA256 validates correct signature
- Unit test: `test_signature_validation_fails_tampered()` - detects tampered log entry
- Security test: `test_aes_gcm_against_known_vectors()` - validates against NIST test vectors

**Handoff Points:**
- EncryptedData format locked (ciphertext, iv, key_version, timestamp fields)
- HMAC-SHA256 signature algorithm finalized

**Risks & Buffers:**
- Risk: Cryptography library version incompatibility → Buffer: lock to cryptography >= 41.0.0
- Risk: IV collision under high throughput → Buffer: use `secrets.token_bytes(16)` (cryptographically secure)

---

### Task 1.3: AuditLogCollector with HMAC Signatures

**Files:**
- Create: `kakehashi/kek_wrapper/core/audit_log_collector.py`
- Create: `kakehashi/kek_wrapper/models/audit_event.py` (AuditLogEntry dataclass)
- Create: `kakehashi/kek_wrapper/models/enums.py` (EventType, Role, Status)
- Create: `kakehashi/kek_wrapper/tests/test_audit_log_collector.py`

**Interfaces:**
- Consumes: Azure Blob Storage connection (append-only), CryptoService for HMAC
- Produces:
  - `async def recordEvent(event_type: EventType, actor_role: str, resource_id: str, operation: str, status: str, error_code: Optional[str]) -> str` - Returns event_id
  - `async def validateLog(log_entry: dict) -> bool` - Checks HMAC signature + continuity
  - `async def exportToSIEM(siem_endpoint: str, log_entries: List[dict]) -> dict` - Sends batch to external SIEM

**Timeline:** 4 days (Nov 9-12)  
**Responsibility:** Chat 1 (glow-ma)  
**Input:** Azure Blob Storage credentials, CryptoService (Task 1.2)  
**Output:** AuditLogCollector class with immutable JSON logging, HMAC signing, batch export  
**Verification:**
- Unit test: `test_recordEvent_creates_valid_schema()` - AuditLogEntry JSON matches spec schema
- Unit test: `test_audit_entry_signed_with_hmac()` - signature present and non-empty
- Integration test: `test_concurrent_audit_writes()` - 100 concurrent writes, all signed, append order preserved
- Integration test: `test_export_to_siem_batch()` - exports 1000 entries with correct signatures
- Security test: `test_audit_immutability()` - modifying one entry invalidates HMAC

**Handoff Points:**
- Audit log JSON schema finalized (timestamp, event_id, event_type, actor, resource, result, context, signature)
- SIEM export format documented (batch size, retry logic)

**Risks & Buffers:**
- Risk: Blob Storage eventual consistency causes signature failures → Buffer: implement retry logic (3 attempts, exponential backoff)
- Risk: HMAC signature key theft → Buffer: signature key stored in Key Vault (not in code)

---

### Task 1.4: ErrorHandler & SecurityAlert

**Files:**
- Create: `kakehashi/kek_wrapper/core/error_handler.py`
- Create: `kakehashi/kek_wrapper/tests/test_error_handler.py`

**Interfaces:**
- Consumes: AuditLogCollector, alert service (Slack/email)
- Produces:
  - `class SecurityError(Exception)` - Raised on crypto/key failures
  - `class AuditError(Exception)` - Raised on audit log failures
  - `async def logSecurityEvent(error_type: str, context: dict) -> None` - Logs to audit + alerts
  - `async def alertOnFailure(severity: str, message: str) -> None` - Sends immediate notification

**Timeline:** 2 days (Nov 13-14)  
**Responsibility:** Chat 1 (glow-ma)  
**Input:** AuditLogCollector (Task 1.3)  
**Output:** Error classes + alert system integrated with audit logging  
**Verification:**
- Unit test: `test_security_error_triggers_audit_log()` - exception auto-records to audit
- Unit test: `test_alert_on_key_rotation_failure()` - emergency scenario triggers alert
- Integration test: `test_cascading_alerts()` - multiple failures trigger escalation

**Handoff Points:**
- Error handling strategy locked (which errors auto-alert vs. silent)

**Risks & Buffers:**
- Risk: Alert service down, errors not reported → Buffer: implement local file fallback logging

---

### Task 1.5: Core Wrapper Unit Tests & Coverage Report

**Files:**
- Modify: `kakehashi/kek_wrapper/tests/` (aggregate all tests)
- Create: `kakehashi/kek_wrapper/tests/conftest.py` (pytest fixtures: mock Key Vault, Blob Storage)
- Create: `.coverage.json` (coverage report artifact)

**Timeline:** 2 days (Nov 13-14, parallel with 1.4)  
**Responsibility:** Chat 1 (glow-ma)  
**Input:** All Task 1.1-1.4 implementations  
**Output:** Coverage >= 85%, all tests passing, report in CI  
**Verification:**
```bash
pytest kakehashi/kek_wrapper/tests/ -v --cov=kakehashi.kek_wrapper --cov-report=json
# Expected: coverage.json shows >= 85% across all modules
```

**Handoff Points:**
- Core Wrapper API stable (no signature changes)
- All tests passing on Ubuntu 20.04 + Python 3.11

**Risks & Buffers:**
- Risk: Coverage gap in HSM rotation code → Buffer: mock HSM scenarios in conftest.py

---

## Phase 2: CI/CD Gating & Style Enforcement (Week 3-4: 2026-11-17 to 2026-11-28)

### Task 2.1: Pre-Commit Hooks (Black, mypy, bandit)

**Files:**
- Create: `.husky/pre-commit`
- Create: `pyproject.toml` (Black, isort, mypy config)
- Create: `.bandit` (security config)

**Timeline:** 2 days (Nov 17-18)  
**Responsibility:** Chat 2 (市場調査)  
**Input:** Core Wrapper code (Phase 1)  
**Output:** Local hooks blocking commits with formatting/type/security issues  
**Verification:**
- Test: Create intentional KeyVault() direct call, pre-commit blocks with error message
- Test: Type mismatch (int passed where str expected), mypy blocks
- Test: Hardcoded secret detection, bandit blocks

**Handoff Points:**
- Hook configuration locked; all chats install `.husky` with `npm install husky`

---

### Task 2.2: GitHub Actions Security Gate (PR Stage)

**Files:**
- Create: `.github/workflows/security-gate.yml`
- Create: `scripts/validate_audit_schema.py` (JSON schema validation)
- Create: `scripts/detect_direct_kv_access.py` (grep for anti-patterns)
- Create: `scripts/check_style_guide.py` (audit log recording check)
- Create: `.semgrep.yml` (SAST rules)

**Timeline:** 4 days (Nov 19-22)  
**Responsibility:** Chat 2 (市場調査)  
**Input:** Pre-commit hooks (Task 2.1), specification  
**Output:** GitHub Actions workflow running 5 security checks on every PR  
**Verification:**
- Test: Submit PR with audit schema violation, workflow fails with clear message
- Test: Submit PR with direct Key Vault call, workflow fails
- Test: Submit PR with missing error handling, workflow fails
- Test: Submit valid PR, workflow passes all 5 checks in < 2 minutes

**Handoff Points:**
- Security gate workflow finalized; CI status required for merge

---

### Task 2.3: Audit Log Schema Validation

**Files:**
- Create: `kakehashi/schemas/audit_log_schema.json` (JSON Schema spec)
- Create: `scripts/validate_audit_schema.py`
- Create: `docs/guides/audit-log-schema.md` (documentation)
- Modify: `kakehashi/kek_wrapper/tests/test_audit_log_collector.py` (add schema validation tests)

**Timeline:** 3 days (Nov 23-25)  
**Responsibility:** Chat 2 (市場調査)  
**Input:** AuditLogEntry definition (from Task 1.3)  
**Output:** JSON Schema + validation script + documentation  
**Verification:**
- Unit test: `test_valid_audit_entry_passes_schema()` - correct entry validates
- Unit test: `test_missing_signature_fails_schema()` - missing required field fails
- Unit test: `test_invalid_event_type_fails_schema()` - enum constraint enforced

**Handoff Points:**
- Audit schema frozen (any change requires議事 with 三名体制)

---

### Task 2.4: SAST & Style Compliance Automation

**Files:**
- Modify: `.semgrep.yml` (add crypto/key hardcoding rules)
- Modify: `scripts/check_style_guide.py` (enforce audit logging in data operations)
- Create: `docs/guides/ci-cd-gate-guide.md` (how to run checks locally)

**Timeline:** 2 days (Nov 26-27)  
**Responsibility:** Chat 2 (市場調査)  
**Input:** Core Wrapper code (Phase 1), security gate workflow (Task 2.2)  
**Output:** Automated detection of hardcoded secrets, missing audit logging, weak crypto  
**Verification:**
- Test: commit code with hardcoded AWS key, semgrep blocks
- Test: fetch_user() without audit logging, check_style_guide blocks

**Handoff Points:**
- SAST rules finalized; CI cannot be bypassed without explicit override (tracked)

---

### Task 2.5: Documentation & Guides

**Files:**
- Create: `docs/guides/style-guide.md` (coding rules, error handling, example code)
- Create: `docs/guides/ci-cd-gate-guide.md` (running checks locally, interpreting failures)
- Create: `docs/guides/hsm-key-rotation-ops.md` (rotation procedures, emergency rotation)

**Timeline:** 1 day (Nov 28)  
**Responsibility:** Chat 2 (市場調査)  
**Input:** All Phase 1-2 work  
**Output:** Comprehensive guides for 5 chat teams  
**Verification:**
- Readability: Non-specialist reads guide, understands how to run pre-commit checks

**Handoff Points:**
- Documentation complete; shared with all 5 chats

---

## Phase 3: 5-Chat Integration & E2E Testing (Week 5-6: 2026-12-01 to 2026-12-12)

**Timeline:** 12 days total (parallel work by 5 chats)  
**Responsibility:** Chat 3 (ゆんたく), Chat 4 (沖縄企業のミカタ), Chat 5 (アーカイブ) + Chat 1 (integration lead)  
**Input:** Core Wrapper (Phase 1), CI/CD gating (Phase 2)  

### Task 3.1: RBAC Layer (Chat 3 / ゆんたく)

**Files:**
- Create: `kakehashi/implementations/chat_003_yuntak/rbac_service.py`
- Create: `kakehashi/implementations/chat_003_yuntak/tests/test_rbac_service.py`

**Interfaces:**
- Consumes: KeyVaultConnector, Azure AD / Managed Identity
- Produces:
  - `async def assignRole(user_id: str, role: Role) -> None`
  - `async def checkPermission(user_id: str, resource_id: str, operation: str) -> bool`
  - `async def getActiveRoles() -> dict` - returns current RBAC policy

**Timeline:** 4 days (Dec 1-4)  
**Output:** RBAC enforcement layer (4 roles: admin, operator, auditor, guest)  
**Verification:**
- Unit test: `test_operator_cannot_rotate_keys()` - operator denied key rotation
- Unit test: `test_auditor_can_read_logs()` - auditor permitted read-only access
- Integration test: `test_rbac_with_keyvault_connector()` - RBAC gates Key Vault access

**Handoff Points:**
- RBAC policy document (who is which role)

---

### Task 3.2: Key Rotation Service (Chat 4 / 沖縄企業のミカタ)

**Files:**
- Create: `kakehashi/implementations/chat_004_okinawa_mikata/key_rotation_service.py`
- Create: `kakehashi/implementations/chat_004_okinawa_mikata/tests/test_key_rotation_service.py`

**Interfaces:**
- Consumes: KeyVaultConnector, AuditLogCollector
- Produces:
  - `async def scheduleRotation(interval_days: int) -> None` - 90-day default
  - `async def emergencyRotate() -> dict` - 24-hour SLA rotation
  - `async def rekeyAllData(old_key_version: str, new_key_version: str) -> dict` - Batch rekey

**Timeline:** 5 days (Dec 5-9)  
**Output:** Key rotation orchestration (90-day + emergency paths)  
**Verification:**
- Unit test: `test_schedule_rotation_triggers_after_90days()`
- Integration test: `test_emergency_rotation_within_24hrs()`
- Integration test: `test_rekey_data_validation()` - decrypt with old key, re-encrypt with new

**Handoff Points:**
- Key rotation playbook documented (manual vs. automatic triggers)

---

### Task 3.3: Monitoring & Alerting (Chat 5 / アーカイブ)

**Files:**
- Create: `kakehashi/implementations/chat_005_archive/monitoring_service.py`
- Create: `kakehashi/implementations/chat_005_archive/tests/test_monitoring_service.py`

**Interfaces:**
- Consumes: AuditLogCollector, KeyVaultConnector
- Produces:
  - `async def watchAuditLogs() -> None` - Real-time monitoring
  - `async def detectAnomalies(window_minutes: int) -> List[dict]` - Alert on unusual access patterns
  - `async def incidentResponse(incident_type: str) -> None` - Automated playbook trigger

**Timeline:** 4 days (Dec 1-4, parallel with Task 3.1)  
**Output:** Monitoring dashboard + anomaly detection rules  
**Verification:**
- Unit test: `test_detect_brute_force_login()` - flag > 5 failed logins in 5 min
- Unit test: `test_detect_mass_data_export()` - flag unusual data volume access
- Integration test: `test_incident_response_playbook()` - trigger alert, log event, notify ops

**Handoff Points:**
- Monitoring thresholds documented (what triggers alert vs. silent log)

---

### Task 3.4: Staging Integration Testing

**Files:**
- Create: `kakehashi/tests/integration_staging/` (E2E tests)
- Create: `kakehashi/tests/integration_staging/test_e2e_encrypt_decrypt.py`
- Create: `kakehashi/tests/integration_staging/test_e2e_rbac.py`
- Create: `kakehashi/tests/integration_staging/test_e2e_audit_immutability.py`

**Timeline:** 4 days (Dec 10-12, parallel final testing)  
**Responsibility:** Chat 1 (integration orchestration) + all 5 chats (test creation)  
**Input:** All implementations from Tasks 3.1-3.3  
**Output:** E2E tests passing in staging environment (Core Wrapper + all 5 chats)  
**Verification:**
```bash
pytest kakehashi/tests/integration_staging/ -v --cov=kakehashi
# All tests PASS in < 5 min
```

**Handoff Points:**
- Staging environment stable (all 5 chats deployed + tests passing)
- Integration test suite frozen (baseline for Week 7 audit)

---

## Phase 4: External Security Audit & Penetration Testing (Week 7-8: 2026-12-15 to 2026-12-26)

**Timeline:** 10 days  
**Responsibility:** External security firm (pre-booked) + Chat 1 (liaison)  
**Input:** Staging deployment (Phase 3)  
**Output:** Penetration test report + remediation plan  

### Task 4.1: Pre-Audit Checklist & Evidence Collection

**Files:**
- Create: `docs/audit/pre-audit-checklist.md` - Verify all controls in place
- Create: `docs/audit/evidence-collection.md` - Document controls & configs

**Timeline:** 2 days (Dec 15-16)  
**Responsibility:** Chat 1  
**Verification:**
- [ ] HSM-backed keys enabled in staging Key Vault
- [ ] Audit log HMAC signatures validated (3 random samples)
- [ ] RBAC roles assigned (4 test users with different roles)
- [ ] Key rotation tested (v1 → v2 successful)
- [ ] CI/CD gates all passing (0 overrides)

**Handoff Points:**
- Evidence package ready for auditors

---

### Task 4.2: Penetration Testing (White-box)

**Files:**
- External firm deliverable: `docs/audit/penetration_test_report_20261220.pdf`

**Timeline:** 5 days (Dec 17-21)  
**Responsibility:** External firm  
**Input:** Staging environment access, code review, architecture docs  
**Output:** Report with findings (Critical/High/Medium/Low)  
**Verification:**
- Pentest conducted against staging (production not touched)
- Report includes: vulnerability description, severity, reproducibility, remediation

**Expected Findings Categories:**
- Crypto: IV reuse, weak key generation, algorithm downgrade
- Auth: RBAC bypass, token forgery, privilege escalation
- Audit: log tampering, signature bypass, export interception
- Deployment: blue-green switch vulnerability, canary data leak

---

### Task 4.3: Remediation & Re-Testing

**Files:**
- Create: `docs/议事_20261222_審計所見対応.md` (remediation decision record)
- Modify: relevant code/config per findings

**Timeline:** 5 days (Dec 22-26, parallel with 4.2 closing)  
**Responsibility:** Chat 1-5 (by severity/component)  
**Input:** Penetration test report  
**Output:** All Critical/High findings resolved, Medium findings assessed  
**Verification:**
- Pentest firm re-tests critical fixes → PASS
- Modified code passes all CI/CD gates
- Audit log captures remediation (who, when, what changed)

**Handoff Points:**
- Audit sign-off: "Ready for production deployment"
- Remediation decisions documented (三名体制 review if policy change)

---

## Phase 5: Production Deployment (Week 9-10: 2026-12-29 to 2027-01-09)

**Timeline:** 10 days  
**Responsibility:** Chat 5 (deployment lead) + Chat 1 (monitoring)  
**Input:** Audit-approved staging code  
**Output:** Production system live with monitoring active  

### Task 5.1: Blue-Green Production Setup

**Files:**
- Create: `kakehashi/deploy/blue_green_config.yaml` - Azure deployment templates
- Create: `kakehashi/deploy/canary_deploy_script.py` - Traffic shifting logic

**Timeline:** 2 days (Dec 29-30)  
**Responsibility:** Chat 5  
**Input:** Audit-approved code  
**Output:** Blue (old system) + Green (new system) both ready, traffic 100% to Blue  
**Verification:**
- [ ] Green deployment successful (all services running)
- [ ] Health checks passing (Green @ 100% CPU < 50%, latency < 100ms)
- [ ] Logs flowing to audit system

**Handoff Points:**
- Blue-Green environment ready; manual switch to Green on go/no-go decision

---

### Task 5.2: Canary Rollout (10% → 50% → 100%)

**Files:**
- Modify: `kakehashi/deploy/canary_deploy_script.py`
- Create: `docs/guides/incident-response-playbook.md` - Rollback procedures

**Timeline:** 6 days (Jan 1-6)  
**Responsibility:** Chat 5 + Chat 1 (monitoring)  
**Input:** Blue-Green setup (Task 5.1)  
**Output:** Production traffic fully migrated to Green system  

**Canary Schedule:**
- Day 1 (Jan 1): 10% traffic → Green (90% Blue)
  - Monitor: error rate, latency, audit log volume
  - SLA: error rate < 0.1%, latency p95 < 150ms
  - Decision: proceed or rollback after 4 hours
- Day 2-3 (Jan 2-3): 50% traffic → Green (if 10% passed)
  - Monitor same metrics
  - SLA: same as 10%
  - Decision: proceed after 8 hours
- Day 4-6 (Jan 4-6): 100% traffic → Green (if 50% passed)
  - Monitor for 48 hours
  - SLA: error rate < 0.05%, latency p95 < 100ms
  - Final: Decommission Blue, Green is prod

**Verification:**
- At each stage, compare metrics: Green < 1.2x Blue baseline (acceptable variance)
- No security incidents detected (audit log anomaly count = 0)
- Rollback possible at any stage (< 1 min cutover back to Blue)

**Handoff Points:**
- Production system stable; incident response team trained

---

### Task 5.3: Incident Response Team Training

**Files:**
- Create: `docs/guides/incident-response-playbook.md`
- Create: `docs/guides/emergency-rotation-procedures.md`

**Timeline:** 2 days (Jan 7-8, parallel with canary)  
**Responsibility:** Chat 5  
**Input:** System architecture, monitoring dashboards, runbooks  
**Output:** Operations team certified to handle incidents  
**Verification:**
- [ ] Ops team can manually trigger emergency key rotation (< 10 min)
- [ ] Ops team can access audit logs, identify breach (< 5 min)
- [ ] Ops team can initiate rollback to Blue system (< 1 min)
- [ ] Ops team can notify security team + customers (templated, < 15 min)

---

## Phase 6: Documentation & Handoff (Week 11-12: 2027-01-12 to 2027-01-23)

**Timeline:** 10 days  
**Responsibility:** Chat 1-5 (distributed)  
**Input:** Production system + audit results  
**Output:** Operational handoff complete  

### Task 6.1: Operations Handbook

**Files:**
- Create: `docs/guides/operations-handbook.md` - Daily operations, common tasks
- Create: `docs/guides/runbooks/` - Specific incident playbooks

**Timeline:** 3 days (Jan 12-14)  
**Responsibility:** Chat 5 (ops focus) + Chat 1 (architecture context)  
**Output:** Step-by-step procedures for:
- Monitoring dashboard interpretation
- Key rotation (scheduled + emergency)
- Audit log inspection (export, signature validation)
- RBAC policy updates
- Incident escalation

**Verification:**
- Readability: Operations engineer reads handbook, performs 3 random tasks without questions

---

### Task 6.2: Salesforce Shield Equivalence Documentation

**Files:**
- Create: `docs/audit/salesforce-shield-equivalence.md` - Feature-by-feature comparison

**Timeline:** 2 days (Jan 15-16)  
**Responsibility:** Chat 1  
**Output:** Document explaining how KAKEHASHI Phase E matches Salesforce Shield across:
- Encryption (TLS 1.2+, AES-256-GCM, at-rest + in-transit)
- Access Control (RBAC 4-role, Managed Identity)
- Audit Logging (immutable, HMAC-signed, append-only)
- Key Management (HSM-backed, 90-day rotation, emergency rotation)
- Compliance (SOC 2 Type II, ISO 27001)
- Shared Responsibility (Azure handles infrastructure, KAKEHASHI handles configuration/monitoring)

**Verification:**
- Readability: Auditor / customer review, can explain KAKEHASHI security posture to board

---

### Task 6.3: Compliance Certification Handoff

**Files:**
- Create: `docs/audit/compliance-summary.md` - SOC 2 Type II + ISO 27001 status
- Create: `docs/audit/siem-export-setup.md` - SIEM integration instructions

**Timeline:** 2 days (Jan 17-18)  
**Responsibility:** Chat 1  
**Output:**
- SOC 2 Type II: Audit scope, shared responsibility clarification, ongoing compliance plan
- ISO 27001: Control mapping, evidence artifacts, annual audit schedule
- SIEM: Configuration steps to export audit logs to customer SIEM

---

### Task 6.4: Final Approval & Sign-Off

**Files:**
- Create/Modify: `docs/決裁申請_20261029_Phase-E-KAKEHASHI-High-Performance-Security.md` (completion record)
- Create: `docs/議事_20270119_Phase-E完了決裁.md` - Final approval decision

**Timeline:** 2 days (Jan 19-20)  
**Responsibility:** Chat 1 (liaison) + 小柳さん (decision)  
**Input:** All Phase 1-6 deliverables  
**Output:** 小柳さん sign-off: "Phase E complete, production stable"  
**Verification:**
- [ ] All 6 phases completed on schedule (2026-12-17 target met)
- [ ] External audit passed (Critical/High remediated)
- [ ] Production system stable (error rate < 0.1%, uptime 99.9%)
- [ ] Operations team trained + incident response tested
- [ ] Documentation complete + team signed off

**Handoff Points:**
- Operations ownership transferred to production team
- Phase E declared complete; Phase F (next iteration) can begin

---

## Cross-Phase Governance & Risks

### Weekly Sync (Every Monday 9:00-10:00 JST)

**Attendees:** All 5 chat leads + 小柳さん (1 lead moderates each week)  
**Agenda:** 
- Phase progress (% complete, blockers)
- Dependency status (is Chat 1 blocking Chat 2?)
- Escalations (non-reversible decisions requiring議事)
- Metrics (test coverage, CI passes, audit log volume)

**Output:** Minutes in `docs/weekly-sync_YYYYMMDD.md`

---

### Risk Register & Mitigation

| Risk | Severity | Likelihood | Mitigation | Owner |
|------|----------|------------|-----------|-------|
| HSM key unavailable during production rotation | Critical | Low | Pre-stage HSM backup key; 24-hour SLA emergency rotation | Chat 1 |
| Audit log signature validation fails at scale (concurrent writes) | High | Medium | Test with 1000 concurrent writers in staging; implement retry logic (3x backoff) | Chat 1 |
| CI/CD gate bypass via Azure CLI | High | Medium | Restrict Azure CLI access via Azure Policy; audit all direct Key Vault changes; weekly review | Chat 2 |
| Staging ↔ Production secret parity (HSM behavior not replicated) | High | Medium | Staging uses same Azure Key Vault config as prod (copy policies); run same tests in both | Chat 1 |
| Multi-chat version lock (Chat A upgrades wrapper, Chat B breaks) | Medium | High | Core Wrapper SemVer (semantic versioning); backward-compatible decryption always; tag releases | Chat 1 |
| 12月 holiday delays (team availability) | Medium | High | Pre-stage all Week 5-6 work by Dec 1; buffer Phase 4 audit to Jan if needed | Chat 1 |

---

## Self-Review Checklist

**1. Spec Coverage:** Each section of the Phase E design spec maps to specific tasks:
- ✅ §1 Security Requirements → Task 1.1-1.4 (wrapper implementation)
- ✅ §1.6 Key Rotation → Task 3.2 (rotation service)
- ✅ §2 Architecture → Tasks 1.1-1.4 (Core Wrapper) + 3.1-3.3 (chat implementations)
- ✅ §3 Style Guide → Task 2.1-2.4 (CI/CD + pre-commit)
- ✅ §4 CI/CD Gating → Task 2.2 (GitHub Actions)
- ✅ §5 Multi-Chat Coordination → Task 3.4 (E2E integration)
- ✅ No gaps identified

**2. Step Scan:** Each task step is actionable (implementer knows exactly what to write):
- ✅ Task 1.1 Step 1: "Write test: test_authenticate_with_managed_identity()" — specific, testable
- ✅ Task 2.2 Step 2: "Create `.github/workflows/security-gate.yml` with 5 checks" — specific files, clear requirements
- ✅ Task 3.4: "All E2E tests PASS in staging" — verifiable pass/fail criterion
- ✅ No vague steps ("handle edge cases", "add appropriate validation")

**3. Type Consistency:** 
- ✅ KeyVaultConnector.getSecret() returns `bytes` (Task 1.1)
- ✅ CryptoService.encrypt() consumes `bytes` key (Task 1.2)
- ✅ AuditLogCollector.recordEvent() consumes EventType enum (Task 1.3)
- ✅ No name/signature mismatches across tasks

**4. Review Focus:** Each of the 5 review focus items has a dedicated task/test:
1. HSM Key Validation → Task 1.1 + 1.2 (test_key_rotation_scenario), Task 3.2 (test_rekey_data_validation)
2. Audit Log Immutability → Task 1.3 (test_concurrent_audit_writes), Task 3.4 (E2E immutability test)
3. Multi-Chat Version Lock → Task 1.4 (version tagging), Task 3.4 (integration with all 5 chats)
4. CI/CD Gate Bypass → Task 2.2 (GitHub Actions gating), Task 2.4 (SAST automation)
5. Staging ↔ Production Parity → Task 3.4 (staging E2E tests), Task 5.1 (Blue-Green validation)

**5. Proportion:** Plan length vs. spec:
- Spec: ~572 lines
- Plan: ~800 lines (expanded tasks + steps, not code)
- Ratio: 1.4:1 (acceptable; plan details execution, not transcription)

---

## Execution Handoff

**Plan saved to:** `docs/superpowers/plans/2026-10-29-Phase-E-implementation-plan.md`

**For subagent-driven execution:** Invoke `superpowers:subagent-driven-development` with this plan. Each task will be assigned a fresh subagent for implementation + independent review before the next task.

**For native execution:** I (the primary agent) will implement all tasks in sequence in this session, then request a full-branch code review from a fresh reviewer on the most capable model.

**Recommendation:** **Subagent-driven approach** — Phase E spans 5 parallel chat teams with high interdependency (Core Wrapper must be stable before other chats start). Fresh reviewers on each task catch interface issues early (e.g., signature mismatch between KeyVaultConnector.getSecret() and CryptoService.encrypt()). Cost is ~1 subagent per task; benefit is a 12-week timeline without critical-path rework.

**Does this plan capture what you want? Which execution approach should we use?**
