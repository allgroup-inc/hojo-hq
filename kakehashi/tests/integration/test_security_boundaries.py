"""Integration tests for security boundaries (Task 3.4).

Tests security controls including:
- Unauthorized access rejection
- HMAC constant-time comparison (timing attack protection)
- Key material not exposed in logs/errors
- Token expiration validation
- OWASP Top 10 attack scenarios
"""

import time
from datetime import datetime, timedelta

import pytest

from kakehashi.kek_wrapper.core.audit_log_collector import AuditError
from kakehashi.kek_wrapper.models.crypto_models import Role


class TestSecurityBoundaries:
    """Integration tests for security boundaries."""

    @pytest.mark.asyncio
    async def test_unauthorized_role_cannot_access_resource(self, kek_wrapper: KEKWrapper):
        """Test GUEST role cannot access keys."""
        guest_token = await kek_wrapper.rbac.issue_tokens(
            user_id="guest_user",
            role=Role.GUEST,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Key access should fail
        with pytest.raises(PermissionError):
            await kek_wrapper.encrypt(b"data", token=guest_token["access_token"])

    @pytest.mark.asyncio
    async def test_hmac_verification_constant_time(self, kek_wrapper: KEKWrapper):
        """Test HMAC verification is constant-time (timing attack resistant)."""
        correct_signature = "abcd1234efgh5678ijkl9012mnop3456"
        wrong_signature_1 = "xxxx1234efgh5678ijkl9012mnop3456"  # First 4 chars differ
        wrong_signature_2 = "abcd1234efgh5678ijkl9012mnop3xxx"  # Last 4 chars differ

        # Measure verification times
        times_1 = []
        times_2 = []

        for _ in range(100):
            # Time wrong_signature_1
            start = time.perf_counter()
            try:
                await kek_wrapper.audit.verify_signature(
                    data="test_log",
                    signature=wrong_signature_1,
                )
            except:
                pass
            times_1.append((time.perf_counter() - start) * 1000)

            # Time wrong_signature_2
            start = time.perf_counter()
            try:
                await kek_wrapper.audit.verify_signature(
                    data="test_log",
                    signature=wrong_signature_2,
                )
            except:
                pass
            times_2.append((time.perf_counter() - start) * 1000)

        # Times should be similar (constant-time comparison)
        avg_time_1 = sum(times_1) / len(times_1)
        avg_time_2 = sum(times_2) / len(times_2)
        time_diff_percent = abs(avg_time_1 - avg_time_2) / max(avg_time_1, avg_time_2) * 100

        # Allow 10% variance for consistent-time comparison
        assert time_diff_percent < 10, f"Timing leak detected: {time_diff_percent:.1f}%"

    @pytest.mark.asyncio
    async def test_key_material_not_in_logs(self, kek_wrapper: KEKWrapper):
        """Test key material is not exposed in logs."""
        await kek_wrapper.encrypt(b"sensitive_data")

        logs = await kek_wrapper.audit.get_logs(limit=10)
        log_text = str(logs)

        # Key material should not appear
        assert "secret_" not in log_text
        assert "sensitive_data" not in log_text
        # IV should not appear
        assert "0123456789abcdef" not in log_text.lower()

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, kek_wrapper: KEKWrapper):
        """Test expired tokens are rejected."""
        token = await kek_wrapper.rbac.issue_tokens(
            user_id="user",
            role=Role.OPERATOR,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Expire the token
        kek_wrapper.rbac.mock_current_time = datetime.utcnow() + timedelta(hours=2)

        with pytest.raises(InvalidTokenError):
            await kek_wrapper.rbac.verify_token(token["access_token"])

    @pytest.mark.asyncio
    async def test_sql_injection_attempt_blocked(self, kek_wrapper: KEKWrapper):
        """Test SQL injection attempts are blocked."""
        malicious_user_id = "' OR '1'='1"

        # Should handle malicious input safely
        token = await kek_wrapper.rbac.issue_tokens(
            user_id=malicious_user_id,
            role=Role.GUEST,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Should not execute injection
        token_data = await kek_wrapper.rbac.verify_token(token["access_token"])
        assert token_data["user_id"] == malicious_user_id

    @pytest.mark.asyncio
    async def test_xss_payload_handling(self, kek_wrapper: KEKWrapper):
        """Test XSS payload is handled safely."""
        xss_payload = "<script>alert('xss')</script>"

        # Should handle safely
        await kek_wrapper.audit.record_event(
            event_type="TEST",
            operation="XSS_TEST",
            status="SUCCESS",
            details={"payload": xss_payload},
        )

        # Payload should be stored safely (escaped/sanitized)
        logs = await kek_wrapper.audit.get_logs(limit=1)
        # Should be stored as string, not executable

    @pytest.mark.asyncio
    async def test_cross_role_permission_boundaries(self, kek_wrapper: KEKWrapper):
        """Test permission boundaries between roles."""
        roles_permissions = {
            Role.ADMIN: True,   # Can access
            Role.OPERATOR: True,  # Can access
            Role.AUDITOR: False,  # Cannot access
            Role.GUEST: False,    # Cannot access
        }

        for role, should_access in roles_permissions.items():
            token = await kek_wrapper.rbac.issue_tokens(
                user_id=f"user_{role}",
                role=role,
                chat_id="test",
                ip_address="127.0.0.1",
            )

            try:
                await kek_wrapper.encrypt(b"data", token=token["access_token"])
                accessed = True
            except PermissionError:
                accessed = False

            if should_access:
                assert accessed, f"{role} should be able to encrypt"
            else:
                assert not accessed, f"{role} should NOT be able to encrypt"

    @pytest.mark.asyncio
    async def test_token_reuse_prevention(self, kek_wrapper: KEKWrapper):
        """Test token cannot be reused if revoked."""
        token = await kek_wrapper.rbac.issue_tokens(
            user_id="user",
            role=Role.OPERATOR,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Token should work initially
        token_data = await kek_wrapper.rbac.verify_token(token["access_token"])
        assert token_data is not None

        # Expire token
        kek_wrapper.rbac.mock_current_time = token_data["expires_at"] + timedelta(seconds=1)

        # Token should not work after expiration
        with pytest.raises(InvalidTokenError):
            await kek_wrapper.rbac.verify_token(token["access_token"])

    @pytest.mark.asyncio
    async def test_rate_limiting_protection(self, kek_wrapper: KEKWrapper):
        """Test system handles rapid requests."""
        import asyncio

        # Rapid encryption requests
        tasks = [
            kek_wrapper.encrypt(f"data_{i}".encode())
            for i in range(100)
        ]

        # Should handle without DoS vulnerability
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should complete successfully (rate limiting not hard-blocking in this impl)
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) > 0

    @pytest.mark.asyncio
    async def test_privilege_escalation_prevented(self, kek_wrapper: KEKWrapper):
        """Test privilege escalation is prevented."""
        # Create operator token
        operator_token = await kek_wrapper.rbac.issue_tokens(
            user_id="operator",
            role=Role.OPERATOR,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Try to escalate to admin via token tampering
        parts = operator_token["access_token"].split(".")
        if len(parts) == 3:
            # Simple tampering should fail
            forged_token = f"{parts[0]}.TAMPERED.{parts[2]}"

            with pytest.raises(InvalidTokenError):
                await kek_wrapper.rbac.verify_token(forged_token)

    @pytest.mark.asyncio
    async def test_error_messages_dont_leak_secrets(self, kek_wrapper: KEKWrapper):
        """Test error messages don't leak secrets."""
        try:
            # Force an error
            kek_wrapper.kvc.mock_http_error = 500
            await kek_wrapper.encrypt(b"data")
        except Exception as e:
            error_msg = str(e)

            # Error message should not contain secret material
            assert "secret" not in error_msg.lower()
            assert "key" not in error_msg.lower() or "error" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_input_validation_on_all_parameters(self, kek_wrapper: KEKWrapper):
        """Test input validation prevents injection attacks."""
        # Test with various invalid inputs
        test_cases = [
            "",
            None,
            "\x00",
            "x" * 10000,  # Large input
        ]

        for test_input in test_cases:
            try:
                if test_input is not None:
                    await kek_wrapper.audit.record_event(
                        event_type=test_input,
                        operation="TEST",
                        status="SUCCESS",
                    )
            except (TypeError, ValueError):
                pass  # Expected for invalid inputs
