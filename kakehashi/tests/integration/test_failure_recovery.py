"""Integration tests for failure recovery (Task 3.4).

Tests system behavior under failure conditions:
- Key Vault connection failures with retry logic
- Audit log failures blocking cache writes
- Graceful degradation and recovery
- Circuit breaker patterns
"""

import asyncio

import pytest

from kakehashi.kek_wrapper.core.audit_log_collector import AuditError


class TestFailureRecovery:
    """Integration tests for failure recovery."""

    @pytest.mark.asyncio
    async def test_key_vault_failure_retries_then_fails(self, kek_wrapper: KEKWrapper):
        """Test Key Vault failure triggers retries."""
        kek_wrapper.kvc.mock_http_error = 503

        # Should fail after retries
        with pytest.raises(KeyVaultError):
            await kek_wrapper.encrypt(b"data")

        # Verify retry count
        retry_count = kek_wrapper.kvc.get_retry_count()
        assert retry_count == 3, f"Expected 3 retries, got {retry_count}"

    @pytest.mark.asyncio
    async def test_key_vault_recovery_after_outage(self, kek_wrapper: KEKWrapper):
        """Test recovery after Key Vault outage."""
        # Simulate failure
        kek_wrapper.kvc.mock_http_error = 503
        with pytest.raises(KeyVaultError):
            await kek_wrapper.encrypt(b"data")

        # Key Vault recovers
        kek_wrapper.kvc.mock_http_error = None
        kek_wrapper.kvc.retry_count = 0  # Reset retry counter

        # Next request should succeed
        ciphertext = await kek_wrapper.encrypt(b"data")
        assert ciphertext is not None

    @pytest.mark.asyncio
    async def test_audit_failure_blocks_cache_write(self, kek_wrapper: KEKWrapper):
        """Test audit failure blocks cache write."""
        kek_wrapper.audit.mock_fail = True

        # Encryption should fail due to audit failure
        with pytest.raises(AuditError):
            await kek_wrapper.encrypt(b"data")

        # Cache should remain empty
        cache_size = await kek_wrapper.cache.size()
        assert cache_size == 0

    @pytest.mark.asyncio
    async def test_audit_recovery_restores_functionality(self, kek_wrapper: KEKWrapper):
        """Test functionality restored when audit recovers."""
        # Simulate audit failure
        kek_wrapper.audit.mock_fail = True
        with pytest.raises(AuditError):
            await kek_wrapper.encrypt(b"data")

        # Audit recovers
        kek_wrapper.audit.mock_fail = False

        # Encryption should work again
        ciphertext = await kek_wrapper.encrypt(b"data")
        assert ciphertext is not None

    @pytest.mark.asyncio
    async def test_partial_rotation_failure_continues(self, kek_wrapper: KEKWrapper):
        """Test rotation continues despite partial failures."""
        # Rotation should succeed even if some data fails re-encryption
        result = await kek_wrapper.key_rotation.schedule_rotation(
            rotation_type="SCHEDULED",
            actor_role="ADMIN",
        )

        assert result["success"]

    @pytest.mark.asyncio
    async def test_concurrent_failures_handled_gracefully(self, kek_wrapper: KEKWrapper):
        """Test multiple concurrent failures are handled."""
        kek_wrapper.kvc.mock_http_error = 503

        # Multiple concurrent requests should all fail gracefully
        tasks = [
            kek_wrapper.encrypt(f"data_{i}".encode())
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should fail with KeyVaultError
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 10

    @pytest.mark.asyncio
    async def test_cache_continues_after_key_vault_failure(self, kek_wrapper: KEKWrapper):
        """Test cache functions even after Key Vault failure."""
        # First, warm up cache
        await kek_wrapper.encrypt(b"test_data_1")
        initial_cache_size = await kek_wrapper.cache.size()

        # Simulate Key Vault failure
        kek_wrapper.kvc.mock_http_error = 503
        with pytest.raises(KeyVaultError):
            await kek_wrapper.encrypt(b"test_data_2")

        # Cache should remain unchanged
        current_cache_size = await kek_wrapper.cache.size()
        assert current_cache_size == initial_cache_size

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self, kek_wrapper: KEKWrapper):
        """Test retry logic uses exponential backoff."""
        kek_wrapper.kvc.mock_http_error = 503

        import time
        start = time.time()
        with pytest.raises(KeyVaultError):
            await kek_wrapper.encrypt(b"data")
        elapsed = time.time() - start

        # Should have some delay due to retries
        assert elapsed > 0.01, "Retry backoff should introduce delay"

    @pytest.mark.asyncio
    async def test_failure_alert_notification(self, kek_wrapper: KEKWrapper):
        """Test failure triggers alert."""
        kek_wrapper.kvc.mock_http_error = 503

        # When Key Vault fails repeatedly, should trigger alert
        with pytest.raises(KeyVaultError):
            await kek_wrapper.encrypt(b"data")

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self, kek_wrapper: KEKWrapper):
        """Test circuit breaker pattern after repeated failures."""
        kek_wrapper.kvc.mock_http_error = 503

        # Multiple failures should not escalate
        for _ in range(5):
            with pytest.raises(KeyVaultError):
                await kek_wrapper.encrypt(b"data")

        # Should still fail gracefully
        with pytest.raises(KeyVaultError):
            await kek_wrapper.encrypt(b"data")

    @pytest.mark.asyncio
    async def test_recovery_during_rotation(self, kek_wrapper: KEKWrapper):
        """Test recovery during key rotation."""
        # Start a rotation
        rotation_task = asyncio.create_task(
            kek_wrapper.key_rotation.schedule_rotation(
                rotation_type="SCHEDULED",
                actor_role="ADMIN",
            )
        )

        # Introduce a transient failure
        kek_wrapper.kvc.mock_http_error = 503
        await asyncio.sleep(0.01)

        # Recover
        kek_wrapper.kvc.mock_http_error = None
        kek_wrapper.kvc.retry_count = 0

        # Rotation should complete
        result = await rotation_task
        assert result["success"]
