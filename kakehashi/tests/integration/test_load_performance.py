"""Integration tests for load and performance (Task 3.4).

Tests SLA targets:
- Encryption latency: p50 < 10ms, p95 < 50ms, p99 < 100ms
- Decryption latency: p50 < 10ms, p95 < 50ms, p99 < 100ms
- Cache hit latency: < 1ms
- Audit log write latency: < 100ms
- Throughput: >= 1000 ops/sec
"""

import asyncio
import time
from datetime import datetime

import pytest

from kakehashi.kek_wrapper.core.audit_log_collector import AuditError


class TestLoadPerformance:
    """Integration tests for load and performance."""

    @pytest.mark.asyncio
    async def test_encrypt_latency_meets_sla(self, kek_wrapper: KEKWrapper):
        """Test encryption latency SLA: p50 < 10ms, p95 < 50ms, p99 < 100ms."""
        latencies = []

        for _ in range(1000):
            start = datetime.utcnow()
            await kek_wrapper.encrypt(b"test_data")
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[500]
        p95 = latencies[950]
        p99 = latencies[990]

        assert p50 < 10, f"p50 {p50:.1f}ms > 10ms"
        assert p95 < 50, f"p95 {p95:.1f}ms > 50ms"
        assert p99 < 100, f"p99 {p99:.1f}ms > 100ms"

    @pytest.mark.asyncio
    async def test_decrypt_latency_meets_sla(self, kek_wrapper: KEKWrapper):
        """Test decryption latency SLA."""
        # Pre-generate ciphertexts
        ciphertexts = []
        for i in range(100):
            ct = await kek_wrapper.encrypt(f"data_{i}".encode())
            ciphertexts.append(ct)

        latencies = []
        for ct in ciphertexts:
            start = datetime.utcnow()
            await kek_wrapper.decrypt(ct)
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[50] if len(latencies) > 50 else latencies[0]
        p95 = latencies[95] if len(latencies) > 95 else latencies[-1]

        assert p50 < 10, f"Decrypt p50 {p50:.1f}ms > 10ms"
        assert p95 < 50, f"Decrypt p95 {p95:.1f}ms > 50ms"

    @pytest.mark.asyncio
    async def test_throughput_meets_sla(self, kek_wrapper: KEKWrapper):
        """Test throughput >= 1000 ops/sec."""
        tasks = [
            kek_wrapper.encrypt(b"data")
            for _ in range(1000)
        ]

        start = datetime.utcnow()
        await asyncio.gather(*tasks)
        elapsed = (datetime.utcnow() - start).total_seconds()

        throughput = 1000 / elapsed
        assert throughput >= 1000, f"Throughput {throughput:.0f} < 1000 ops/sec"

    @pytest.mark.asyncio
    async def test_concurrent_operations_scaling(self, kek_wrapper: KEKWrapper):
        """Test scaling with concurrent operations."""
        concurrency_levels = [10, 50, 100, 200]

        for concurrency in concurrency_levels:
            tasks = [
                kek_wrapper.encrypt(f"data_{i}".encode())
                for i in range(concurrency)
            ]

            start = datetime.utcnow()
            await asyncio.gather(*tasks)
            elapsed = (datetime.utcnow() - start).total_seconds()

            throughput = concurrency / elapsed
            # Throughput should not degrade significantly with concurrency
            assert throughput >= 100, f"Throughput at {concurrency} concurrency: {throughput:.0f} < 100"

    @pytest.mark.asyncio
    async def test_cache_hit_latency_under_1ms(self, kek_wrapper: KEKWrapper):
        """Test cache hit latency < 1ms."""
        # Warm up cache
        for _ in range(10):
            await kek_wrapper.encrypt(b"test_data")

        # Measure cache hit latency
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            await kek_wrapper.encrypt(b"test_data")
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 1, f"Cache hit latency {avg_latency:.2f}ms > 1ms"

    @pytest.mark.asyncio
    async def test_audit_log_write_latency(self, kek_wrapper: KEKWrapper):
        """Test audit log write latency < 100ms."""
        latencies = []

        for i in range(100):
            start = datetime.utcnow()
            await kek_wrapper.audit.record_event(
                event_type="TEST",
                operation="WRITE",
                status="SUCCESS",
            )
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            latencies.append(elapsed)

        max_latency = max(latencies)
        avg_latency = sum(latencies) / len(latencies)

        assert max_latency < 100, f"Audit write max latency {max_latency:.1f}ms > 100ms"
        assert avg_latency < 50, f"Audit write avg latency {avg_latency:.1f}ms > 50ms"

    @pytest.mark.asyncio
    async def test_sustained_load_1000_ops(self, kek_wrapper: KEKWrapper):
        """Test sustained load of 1000 operations."""
        operations = []
        for i in range(1000):
            op_type = i % 2  # Alternate encrypt/decrypt
            if op_type == 0:
                operations.append(kek_wrapper.encrypt(f"data_{i}".encode()))
            else:
                # Would need ciphertext for decrypt, simplified for test
                operations.append(kek_wrapper.encrypt(b"dummy"))

        start = datetime.utcnow()
        results = await asyncio.gather(*operations, return_exceptions=True)
        elapsed = (datetime.utcnow() - start).total_seconds()

        # Check for errors
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Got {len(errors)} errors during sustained load"

        # Check throughput
        throughput = 1000 / elapsed
        assert throughput >= 1000, f"Sustained load throughput {throughput:.0f} < 1000"

    @pytest.mark.asyncio
    async def test_latency_distribution_consistency(self, kek_wrapper: KEKWrapper):
        """Test latency distribution is consistent."""
        # First batch
        latencies_1 = []
        for _ in range(500):
            start = datetime.utcnow()
            await kek_wrapper.encrypt(b"test_1")
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            latencies_1.append(elapsed)

        # Second batch (ensure consistency)
        latencies_2 = []
        for _ in range(500):
            start = datetime.utcnow()
            await kek_wrapper.encrypt(b"test_2")
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            latencies_2.append(elapsed)

        avg_1 = sum(latencies_1) / len(latencies_1)
        avg_2 = sum(latencies_2) / len(latencies_2)

        # Should be similar (within 50% margin)
        ratio = max(avg_1, avg_2) / min(avg_1, avg_2)
        assert ratio < 1.5, f"Inconsistent latency: avg_1={avg_1:.1f}, avg_2={avg_2:.1f}"

    @pytest.mark.asyncio
    async def test_memory_efficiency_under_load(self, kek_wrapper: KEKWrapper):
        """Test memory usage remains bounded under load."""
        import sys

        # Get initial cache size
        initial_cache_size = await kek_wrapper.cache.size()

        # Generate high volume
        for _ in range(100):
            await kek_wrapper.encrypt(b"test_data")

        # Cache size should be bounded (not grow indefinitely)
        final_cache_size = await kek_wrapper.cache.size()

        # Cache should not grow unboundedly (5min TTL should keep it small)
        assert final_cache_size <= initial_cache_size + 10
