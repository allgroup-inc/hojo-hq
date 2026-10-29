# Staging SLA Baseline (Task 3.4)

Defines SLA targets, measurement methodology, and pass/fail criteria for KAKEHASHI integration testing in staging environment.

## Executive Summary

This document establishes the Service Level Agreement (SLA) baseline for KAKEHASHI production readiness. All metrics must be met before proceeding to Phase 4 (External Audit) and Phase 5 (Production Deployment).

## SLA Targets

### 1. Cryptographic Operations Latency

#### Encryption (AES-256-GCM)
| Percentile | Target | Unit | Measurement |
|---|---|---|---|
| p50 | < 10 | ms | 50th percentile latency |
| p95 | < 50 | ms | 95th percentile latency |
| p99 | < 100 | ms | 99th percentile latency |

**Measurement Method:**
- Run 1,000 encrypt operations sequentially
- Record latency of each operation using `datetime.utcnow()`
- Sort results and extract p50, p95, p99
- Test: `test_load_performance.py::TestLoadPerformance::test_encrypt_latency_meets_sla()`

#### Decryption (AES-256-GCM)
| Percentile | Target | Unit |
|---|---|---|
| p50 | < 10 | ms |
| p95 | < 50 | ms |
| p99 | < 100 | ms |

**Measurement Method:** Same as encryption, with decrypt operations
Test: `test_load_performance.py::TestLoadPerformance::test_decrypt_latency_meets_sla()`

### 2. Cache Performance

#### Cache Hit Latency
| Metric | Target | Unit |
|---|---|---|
| Average cache hit | < 1 | ms |
| Cache hit rate | >= 95 | % |

**Measurement Method:**
- Warm up cache with 10 warmup operations
- Measure latency of 100 subsequent operations
- Calculate average latency
- Test: `test_load_performance.py::TestLoadPerformance::test_cache_hit_latency_under_1ms()`
- Test: `test_e2e_encryption_flow.py::TestE2EEncryptionFlow::test_cache_hit_rate_within_ttl()`

### 3. Audit Logging Latency

#### Audit Event Recording
| Metric | Target | Unit |
|---|---|---|
| Average write latency | < 50 | ms |
| Maximum write latency | < 100 | ms |

**Measurement Method:**
- Record 100 audit events
- Measure latency of each event write operation
- Calculate average and maximum
- Test: `test_load_performance.py::TestLoadPerformance::test_audit_log_write_latency()`

### 4. Throughput

#### Encryption Operations Per Second
| Metric | Target | Unit |
|---|---|---|
| Minimum throughput | >= 1000 | ops/sec |

**Measurement Method:**
- Create 1,000 concurrent encryption tasks
- Measure total elapsed time
- Calculate throughput = 1000 / elapsed_seconds
- Test: `test_load_performance.py::TestLoadPerformance::test_throughput_meets_sla()`

### 5. Key Rotation

#### Emergency Key Rotation
| Metric | Target | Unit | Trigger |
|---|---|---|---|
| Completion time | < 60 | seconds | Key compromise suspected |

**Measurement Method:**
- Call `trigger_emergency_rotation()` with `reason=compromise_suspected`
- Measure elapsed time from call to completion
- Test: `test_key_rotation_workflow.py::TestKeyRotationWorkflow::test_emergency_rotation_completed_within_sla()`

#### Scheduled Key Rotation (Re-encryption)
| Metric | Target | Records |
|---|---|---|
| Completion time | < 300 seconds (5 min) | 1,000 |

**Measurement Method:**
- Insert 1,000 test records
- Call `schedule_rotation()` with `rotation_type=SCHEDULED`
- Measure elapsed time and re-encrypted count
- Test: `test_key_rotation_workflow.py::TestKeyRotationWorkflow::test_scheduled_rotation_re_encrypts_all_data()`

### 6. Concurrent Operations Scaling

#### Load Distribution
| Concurrency | Throughput Target | Unit |
|---|---|---|
| 10 | >= 100 | ops/sec |
| 50 | >= 100 | ops/sec |
| 100 | >= 1000 | ops/sec |
| 200 | >= 500 | ops/sec |

**Measurement Method:**
- Create N concurrent encrypt tasks
- Measure total elapsed time
- Calculate throughput
- Test: `test_load_performance.py::TestLoadPerformance::test_concurrent_operations_scaling()`

## Code Coverage Requirements

| Metric | Target |
|---|---|
| Branch coverage | >= 85% |
| Measured with | pytest-cov |

**Command:**
```bash
pytest kakehashi/tests/integration/ \
  --cov=kakehashi.kek_wrapper \
  --cov-fail-under=85
```

## RBAC Enforcement Verification

| Role | Permission | Resource | Action | Status Required |
|---|---|---|---|---|
| ADMIN | ALLOW | keys | read | PASS |
| ADMIN | ALLOW | keys | write | PASS |
| ADMIN | ALLOW | keys | rotate | PASS |
| ADMIN | ALLOW | users | manage | PASS |
| ADMIN | ALLOW | logs | export | PASS |
| OPERATOR | ALLOW | keys | read | PASS |
| OPERATOR | ALLOW | keys | write | PASS |
| OPERATOR | DENY | keys | rotate | PASS (rejection) |
| OPERATOR | DENY | users | manage | PASS (rejection) |
| AUDITOR | ALLOW | logs | read | PASS |
| AUDITOR | DENY | keys | read | PASS (rejection) |
| AUDITOR | DENY | keys | write | PASS (rejection) |
| GUEST | DENY | keys | read | PASS (rejection) |
| GUEST | DENY | logs | read | PASS (rejection) |

**Tests:**
- `test_rbac_access_control.py::TestRBACAccessControl::test_admin_full_access()`
- `test_rbac_access_control.py::TestRBACAccessControl::test_operator_limited_access()`
- `test_rbac_access_control.py::TestRBACAccessControl::test_auditor_read_only()`
- `test_rbac_access_control.py::TestRBACAccessControl::test_guest_no_access()`

## Audit Trail Completeness Verification

| Event Type | Must Log | Tamper Detection | Append-Only |
|---|---|---|---|
| KEY_ACCESS (encrypt) | PASS | PASS | PASS |
| KEY_ACCESS (decrypt) | PASS | PASS | PASS |
| KEY_ROTATE | PASS | PASS | PASS |
| USER_LOGIN | PASS | PASS | PASS |

**Tests:**
- `test_audit_trail_completeness.py::TestAuditTrailCompleteness::test_all_operations_logged()`
- `test_audit_trail_completeness.py::TestAuditTrailCompleteness::test_hmac_signature_validates_tamper_detection()`
- `test_audit_trail_completeness.py::TestAuditTrailCompleteness::test_audit_log_deletion_blocked()`

## Security Boundaries Verification

| Boundary | Attack Vector | Expected Result |
|---|---|---|
| Unauthorized Access | GUEST role → encrypt | Rejection (PermissionError) |
| Token Tampering | Modify token signature | Rejection (InvalidTokenError) |
| Timing Attack | HMAC comparison | Constant-time (< 10% variance) |
| Key Exposure | Log analysis | No key material in logs |
| Token Expiration | Use expired token | Rejection (InvalidTokenError) |

**Tests:**
- `test_security_boundaries.py::TestSecurityBoundaries::test_unauthorized_role_cannot_access_resource()`
- `test_security_boundaries.py::TestSecurityBoundaries::test_hmac_verification_constant_time()`
- `test_security_boundaries.py::TestSecurityBoundaries::test_key_material_not_in_logs()`
- `test_security_boundaries.py::TestSecurityBoundaries::test_expired_token_rejected()`

## Failure Recovery Verification

| Failure Scenario | Recovery Mechanism | SLA |
|---|---|---|
| Key Vault 503 | Retry with exponential backoff | Fail after 3 retries |
| Key Vault recovery | Auto-detection and resume | < 1 request latency |
| Audit failure | Block cache write | Skip cache write |
| Partial rotation | Continue with next record | Graceful degradation |

**Tests:**
- `test_failure_recovery.py::TestFailureRecovery::test_key_vault_failure_retries_then_fails()`
- `test_failure_recovery.py::TestFailureRecovery::test_key_vault_recovery_after_outage()`
- `test_failure_recovery.py::TestFailureRecovery::test_audit_failure_blocks_cache_write()`

## Test Execution Environment

### Staging Azure Resources
- **Region:** East US (default)
- **Key Vault:** `staging-kakehashi-kv`
- **Cosmos DB:** `staging-kakehashi` (isolated database)
- **Application Insights:** `staging-kakehashi`
- **Log Analytics:** `staging-kakehashi`

### Network Configuration
- **Isolation:** Separate resource group from production
- **Network policy:** Default Azure security groups
- **Data cleanup:** Automated after each test run

### Concurrency Limits
- **Key Vault:** 100 concurrent connections
- **Cosmos DB:** 400 RUs (test database)
- **Application Insights:** Unlimited metrics/events

## Measurement Methodology

### Latency Measurement
```python
from datetime import datetime

start = datetime.utcnow()
result = await operation()
elapsed = (datetime.utcnow() - start).total_seconds() * 1000  # ms
```

### Percentile Calculation
```python
latencies.sort()
p50 = latencies[500]      # 50th percentile (1000 samples)
p95 = latencies[950]      # 95th percentile
p99 = latencies[990]      # 99th percentile
```

### Throughput Calculation
```python
throughput = operation_count / elapsed_seconds
```

## Pass/Fail Criteria

### PASS (GO for production)
- ✅ All 22+ integration tests PASSED
- ✅ Code coverage >= 85%
- ✅ Encryption latency: p95 < 50ms
- ✅ Decryption latency: p95 < 50ms
- ✅ Throughput: >= 1000 ops/sec
- ✅ Emergency rotation: < 60 seconds
- ✅ RBAC: All 4 roles verified
- ✅ Audit trail: Complete and tamper-proof
- ✅ Security boundaries: All tests passed
- ✅ Failure recovery: Functional

### FAIL (NO-GO, fix required)
- ❌ Any test failure
- ❌ Coverage < 85%
- ❌ Latency SLA miss
- ❌ Throughput < 1000 ops/sec
- ❌ RBAC permission enforcement fail
- ❌ Audit trail gaps
- ❌ Security boundary bypass
- ❌ Failure recovery broken

## Report Generation

Automated SLA report is generated by:
```bash
python kakehashi/tests/integration/generate_sla_report.py --output /tmp/sla_report.md
```

Report includes:
- Test execution summary
- SLA target achievement
- GO/NO-GO decision
- Recommendations

## References

- **Brief:** `.superpowers/sdd/2026-10-29-Phase-E-implementation-plan/task-3.4-brief.md`
- **Tests:** `kakehashi/tests/integration/`
- **Workflows:** `.github/workflows/staging-integration.yml`

---

**SLA Baseline v1.0** | Task 3.4 | 2026-10-29
