# KAKEHASHI Integration Tests (Task 3.4)

End-to-end integration tests for cryptographic key management workflow, RBAC enforcement, key rotation, audit trail completeness, and security boundaries.

## Overview

This test suite validates the complete KAKEHASHI system in a staging environment, covering:

1. **E2E Encryption Flow** (`test_e2e_encryption_flow.py`)
   - Encryption/decryption roundtrip
   - Cache hit rate validation (>= 95%)
   - Audit log recording
   - Concurrent operations

2. **RBAC Access Control** (`test_rbac_access_control.py`)
   - ADMIN: Full access
   - OPERATOR: Limited access (keys, workflows)
   - AUDITOR: Read-only
   - GUEST: No access

3. **Key Rotation Workflow** (`test_key_rotation_workflow.py`)
   - Scheduled 90-day rotation
   - Emergency rotation (< 1min SLA)
   - Backward compatibility
   - Cache invalidation

4. **Audit Trail Completeness** (`test_audit_trail_completeness.py`)
   - All operations logged
   - HMAC signature validation
   - Tamper detection
   - Append-only enforcement

5. **Failure Recovery** (`test_failure_recovery.py`)
   - Key Vault retry logic
   - Graceful degradation
   - Recovery after outage
   - Audit failure handling

6. **Load & Performance** (`test_load_performance.py`)
   - Encryption latency: p95 < 50ms
   - Decryption latency: p95 < 50ms
   - Throughput: >= 1000 ops/sec
   - Concurrent operations scaling

7. **Security Boundaries** (`test_security_boundaries.py`)
   - Unauthorized access rejection
   - Constant-time HMAC comparison
   - Key material not exposed
   - Token expiration validation

## Prerequisites

- Python 3.11+
- Azure CLI (for staging environment setup)
- Environment variables configured:
  - `AZURE_TENANT_ID`
  - `AZURE_CLIENT_ID`
  - `AZURE_CLIENT_SECRET`
  - `AZURE_KEY_VAULT_URL_STAGING`
  - `COSMOS_DB_ENDPOINT_STAGING`

## Installation

```bash
# Install dependencies
pip install -r ../../requirements.txt
pip install pytest-asyncio pytest-cov

# Or use the project's setup
cd /home/user/hojo-hq
pip install -e kakehashi/
```

## Running Tests

### Run all integration tests

```bash
pytest kakehashi/tests/integration/ -v
```

### Run specific test file

```bash
pytest kakehashi/tests/integration/test_e2e_encryption_flow.py -v
```

### Run with coverage

```bash
pytest kakehashi/tests/integration/ \
  --cov=kakehashi.kek_wrapper \
  --cov-report=html \
  --cov-report=term-missing
```

### Run with markers

```bash
# Mark async tests
pytest kakehashi/tests/integration/ -v -m asyncio
```

## Test Configuration

### Environment Setup

```bash
# Setup staging environment
python kakehashi/tests/integration/staging_setup.py
```

### Fixtures

All tests use the following fixtures from `conftest.py`:

- `kek_wrapper`: Main KEKWrapper instance with all components
- `staging_db`: Mock Cosmos DB instance
- `mock_alert_service`: Mock alert service
- `event_loop`: Async event loop for async tests

## SLA Targets

### Latency
- Encryption: p50 < 10ms, p95 < 50ms, p99 < 100ms
- Decryption: p50 < 10ms, p95 < 50ms, p99 < 100ms
- Cache hit: < 1ms
- Audit log write: < 100ms

### Throughput
- Minimum: 1000 ops/sec

### Key Rotation
- Emergency: < 60 seconds (1 minute)

## Generating SLA Report

```bash
python kakehashi/tests/integration/generate_sla_report.py \
  --output /tmp/sla_report.md
```

The report includes:
- Test execution summary
- SLA target verification
- RBAC validation results
- Security boundary testing
- GO/NO-GO decision

## Test Results Interpretation

### PASS Criteria
- All 22+ test functions pass
- Code coverage >= 85%
- SLA targets met
- RBAC permissions enforced
- Audit trail complete and tamper-proof
- Security boundaries validated
- Failure recovery functional

### FAIL Criteria
- Any test fails
- Coverage < 85%
- SLA targets missed
- Permission enforcement fails
- Audit trail gaps or tampering detected
- Security boundaries bypassed
- Failure recovery broken

## GitHub Actions Workflow

Tests are automatically triggered by:

1. **Manual trigger**: `workflow_dispatch` in GitHub Actions
2. **Weekly schedule**: Sundays at 00:00 UTC
3. **Pre-production checks**: Before production deployment

See `.github/workflows/staging-integration.yml` for workflow details.

## Troubleshooting

### Test failures

1. Check environment variables are set
2. Verify staging Azure resources exist
3. Check network connectivity to Azure services
4. Review test output for specific error messages

### Performance test failures

- May be due to system load
- Run performance tests in isolation:
  ```bash
  pytest kakehashi/tests/integration/test_load_performance.py -v
  ```

### Async test issues

- Ensure pytest-asyncio is installed
- Check event loop configuration in conftest.py

## Contributing

When adding new integration tests:

1. Follow the naming convention: `test_<description>()`
2. Use `@pytest.mark.asyncio` for async tests
3. Include docstring explaining what's tested
4. Use fixtures from conftest.py
5. Ensure test is independent (can run in any order)
6. Add to appropriate test class
7. Update test count in README

## References

- [Task 3.4 Brief](../../../.superpowers/sdd/2026-10-29-Phase-E-implementation-plan/task-3.4-brief.md)
- [SLA Baseline](../../../docs/guides/staging-sla-baseline.md)
- [KAKEHASHI Documentation](../../README.md)

---

**Phase 3.4 Integration Tests** | Last Updated: 2026-10-29
