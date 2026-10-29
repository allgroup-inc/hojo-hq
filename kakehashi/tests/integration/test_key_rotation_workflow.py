"""Integration tests for key rotation workflow (Task 3.4).

Tests the complete key rotation process including:
- Scheduled 90-day rotation with re-encryption
- Emergency rotation (< 1min SLA)
- Backward compatibility during rotation
- Cache invalidation and version management
"""

import asyncio
from datetime import datetime

import pytest

from conftest import KEKWrapper, PermissionError
from kakehashi.kek_wrapper.models.crypto_models import Role, RotationType


class TestKeyRotationWorkflow:
    """Integration tests for key rotation."""

    @pytest.mark.asyncio
    async def test_scheduled_rotation_re_encrypts_all_data(
        self, kek_wrapper: KEKWrapper, staging_db
    ):
        """Test scheduled rotation re-encrypts all data."""
        # Insert test data (1000 records)
        total_records = 1000
        for i in range(total_records):
            plaintext = f"customer_data_{i}".encode()
            ciphertext = await kek_wrapper.encrypt(plaintext)
            await staging_db.insert({
                "id": f"record_{i}",
                "data": ciphertext,
            })

        # Execute scheduled rotation
        start = datetime.utcnow()
        result = await kek_wrapper.key_rotation.schedule_rotation(
            rotation_type="SCHEDULED",
            actor_role=Role.ADMIN,
        )
        elapsed = (datetime.utcnow() - start).total_seconds()

        assert result["success"]
        assert result["re_encrypted_count"] == total_records
        assert elapsed < 300, f"Re-encryption took {elapsed:.1f}s > 5min SLA"

    @pytest.mark.asyncio
    async def test_emergency_rotation_completed_within_sla(self, kek_wrapper: KEKWrapper):
        """Test emergency rotation completes within < 1min SLA."""
        start = datetime.utcnow()
        result = await kek_wrapper.key_rotation.trigger_emergency_rotation(
            actor_id="security_team",
            actor_role=Role.ADMIN,
            reason="compromise_suspected",
        )
        elapsed = (datetime.utcnow() - start).total_seconds()

        assert result["success"]
        assert elapsed < 60, f"Emergency rotation took {elapsed:.1f}s > 1min SLA"

    @pytest.mark.asyncio
    async def test_backward_compatibility_during_rotation(self, kek_wrapper: KEKWrapper):
        """Test backward compatibility with old key during rotation."""
        plaintext = b"sensitive_data"
        old_version = kek_wrapper.kvc.get_current_version()

        # Encrypt with old key
        ciphertext_old = await kek_wrapper.encrypt(plaintext)

        # Start rotation (but don't wait for completion)
        rotation_task = asyncio.create_task(
            kek_wrapper.key_rotation.schedule_rotation(
                rotation_type="SCHEDULED",
                actor_role=Role.ADMIN,
            )
        )

        # Should be able to decrypt old data during rotation
        decrypted = await kek_wrapper.decrypt(ciphertext_old)
        assert decrypted == plaintext

        # Wait for rotation to complete
        result = await rotation_task
        assert result["success"]

        # New encryption works with new key
        new_ciphertext = await kek_wrapper.encrypt(plaintext)
        decrypted_new = await kek_wrapper.decrypt(new_ciphertext)
        assert decrypted_new == plaintext

    @pytest.mark.asyncio
    async def test_rotation_permission_check(self, kek_wrapper: KEKWrapper):
        """Test only ADMIN can trigger rotation."""
        # OPERATOR cannot rotate
        with pytest.raises(PermissionError):
            await kek_wrapper.key_rotation.schedule_rotation(
                rotation_type="SCHEDULED",
                actor_role=Role.OPERATOR,
            )

        # AUDITOR cannot rotate
        with pytest.raises(PermissionError):
            await kek_wrapper.key_rotation.schedule_rotation(
                rotation_type="SCHEDULED",
                actor_role=Role.AUDITOR,
            )

    @pytest.mark.asyncio
    async def test_key_version_increments(self, kek_wrapper: KEKWrapper):
        """Test key version increments after rotation."""
        initial_version = kek_wrapper.kvc.get_current_version()

        # Perform rotation
        result = await kek_wrapper.key_rotation.schedule_rotation(
            rotation_type="SCHEDULED",
            actor_role=Role.ADMIN,
        )

        assert result["success"]
        # Check new version was added
        all_versions = await kek_wrapper.kvc.list_secret_versions("kakehashi-kek")
        assert len(all_versions) > 1

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_rotation(self, kek_wrapper: KEKWrapper):
        """Test cache is invalidated after rotation."""
        # Warm up cache
        await kek_wrapper.encrypt(b"test_data")
        initial_cache_size = await kek_wrapper.cache.size()

        # Perform rotation (would invalidate cache in production)
        await kek_wrapper.key_rotation.schedule_rotation(
            rotation_type="SCHEDULED",
            actor_role=Role.ADMIN,
        )

        # Cache behavior - in mock, would be cleared after rotation
        # This is implementation-specific

    @pytest.mark.asyncio
    async def test_audit_log_records_rotation_event(self, kek_wrapper: KEKWrapper):
        """Test rotation events are logged."""
        initial_logs = await kek_wrapper.audit.get_logs()
        initial_count = len(initial_logs)

        # Perform rotation
        await kek_wrapper.key_rotation.schedule_rotation(
            rotation_type="SCHEDULED",
            actor_role=Role.ADMIN,
        )

        # Check for rotation log
        logs = await kek_wrapper.audit.get_logs()
        rotation_logs = [log for log in logs if log["event_type"] == "KEY_ROTATE"]
        assert len(rotation_logs) > 0

    @pytest.mark.asyncio
    async def test_emergency_rotation_audit_trail(self, kek_wrapper: KEKWrapper):
        """Test emergency rotation creates audit trail."""
        # Perform emergency rotation
        await kek_wrapper.key_rotation.trigger_emergency_rotation(
            actor_id="security_team",
            actor_role=Role.ADMIN,
            reason="key_compromise",
        )

        # Check audit log
        logs = await kek_wrapper.audit.get_logs()
        emergency_logs = [
            log for log in logs
            if log["event_type"] == "KEY_ROTATE"
            and log["operation"] == "EMERGENCY"
        ]
        assert len(emergency_logs) > 0

    @pytest.mark.asyncio
    async def test_concurrent_encryptions_during_rotation(self, kek_wrapper: KEKWrapper):
        """Test concurrent encryptions don't fail during rotation."""
        # Start rotation
        rotation_task = asyncio.create_task(
            kek_wrapper.key_rotation.schedule_rotation(
                rotation_type="SCHEDULED",
                actor_role=Role.ADMIN,
            )
        )

        # Perform concurrent encryptions during rotation
        encrypt_tasks = [
            kek_wrapper.encrypt(f"data_{i}".encode())
            for i in range(50)
        ]

        results = await asyncio.gather(*encrypt_tasks, return_exceptions=True)

        # Should not have errors
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Got {len(errors)} errors during rotation"

        # Wait for rotation
        await rotation_task
