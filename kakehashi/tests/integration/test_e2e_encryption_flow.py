"""Integration tests for end-to-end encryption flow (Task 3.4).

Tests the complete encryption/decryption workflow including:
- Key retrieval from Key Vault with caching
- AES-256-GCM encryption
- Audit log recording
- Cache hit rate validation
- Error cascade effects
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from kakehashi.kek_wrapper.core.audit_log_collector import AuditError


class TestE2EEncryptionFlow:
    """Integration tests for full encryption flow."""

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_roundtrip(self, kek_wrapper: KEKWrapper):
        """Test encryption/decryption roundtrip."""
        plaintext = b"sensitive_customer_data_12345"

        # Encrypt
        ciphertext = await kek_wrapper.encrypt(plaintext)
        assert ciphertext != plaintext
        assert len(ciphertext) > len(plaintext)  # IV + tag added

        # Decrypt
        decrypted = await kek_wrapper.decrypt(ciphertext)
        assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_cache_hit_rate_within_ttl(self, kek_wrapper: KEKWrapper):
        """Test cache hit rate >= 95% within 5-minute TTL."""
        cache_hits = 0
        total_requests = 100

        for i in range(total_requests):
            ciphertext = await kek_wrapper.encrypt(f"data_{i}".encode())
            # Cache hit check via monitoring
            if await kek_wrapper.monitoring.get_cache_hit():
                cache_hits += 1

        hit_rate = cache_hits / total_requests
        assert hit_rate >= 0.95, f"Cache hit rate {hit_rate:.1%} < 95%"

    @pytest.mark.asyncio
    async def test_audit_log_recorded_before_cache_write(self, kek_wrapper: KEKWrapper):
        """Test audit log recording before cache write."""
        plaintext = b"test_data"

        # Normal flow
        ciphertext = await kek_wrapper.encrypt(plaintext)
        audit_logs = await kek_wrapper.audit.get_logs(limit=1)
        assert len(audit_logs) > 0
        assert audit_logs[0]["event_type"] == "KEY_ACCESS"
        assert audit_logs[0]["operation"] == "GET"

        # Audit failure simulation
        initial_cache_size = await kek_wrapper.cache.size()
        kek_wrapper.audit.mock_fail = True
        with pytest.raises(AuditError):
            await kek_wrapper.encrypt(plaintext)

        # Cache should not have new entry
        final_cache_size = await kek_wrapper.cache.size()
        assert final_cache_size == initial_cache_size

    @pytest.mark.asyncio
    async def test_concurrent_encrypt_requests(self, kek_wrapper: KEKWrapper):
        """Test concurrent encryption requests."""
        tasks = [
            kek_wrapper.encrypt(f"data_{i}".encode())
            for i in range(100)
        ]

        start = datetime.utcnow()
        results = await asyncio.gather(*tasks)
        elapsed = (datetime.utcnow() - start).total_seconds()

        avg_latency_ms = (elapsed * 1000) / 100
        assert avg_latency_ms < 50, f"Avg latency {avg_latency_ms:.1f}ms > 50ms"
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_multiple_encrypt_calls_use_cache(self, kek_wrapper: KEKWrapper):
        """Test that multiple encrypt calls use cached key."""
        # First call
        await kek_wrapper.encrypt(b"data_1")
        logs_1 = await kek_wrapper.audit.get_logs()
        initial_log_count = len(logs_1)

        # Second call should use cache
        for _ in range(10):
            await kek_wrapper.encrypt(b"data_2")

        logs_2 = await kek_wrapper.audit.get_logs()
        # Should have added logs for each call
        assert len(logs_2) > initial_log_count

    @pytest.mark.asyncio
    async def test_encryption_with_various_data_sizes(self, kek_wrapper: KEKWrapper):
        """Test encryption works with various data sizes."""
        test_sizes = [1, 16, 256, 1024, 10240]  # Various sizes

        for size in test_sizes:
            plaintext = b"x" * size
            ciphertext = await kek_wrapper.encrypt(plaintext)
            decrypted = await kek_wrapper.decrypt(ciphertext)
            assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_error_cascade_on_key_vault_failure(self, kek_wrapper: KEKWrapper):
        """Test error cascade when Key Vault fails."""
        # Simulate Key Vault failure
        kek_wrapper.kvc.mock_http_error = 503

        with pytest.raises(Exception):
            await kek_wrapper.encrypt(b"test_data")

    @pytest.mark.asyncio
    async def test_iv_uniqueness_per_encryption(self, kek_wrapper: KEKWrapper):
        """Test that each encryption uses a unique IV."""
        plaintext = b"same_data"
        ciphertexts = set()

        # Encrypt same plaintext multiple times
        for _ in range(10):
            ciphertext = await kek_wrapper.encrypt(plaintext)
            ciphertexts.add(ciphertext)

        # Should have different ciphertexts due to random IV
        assert len(ciphertexts) == 10
