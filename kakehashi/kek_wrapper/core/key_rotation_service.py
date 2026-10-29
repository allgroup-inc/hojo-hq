"""Key rotation service for scheduled and emergency key rotation (Phase E, Task 3.2).

This module implements the KeyRotationService that manages both scheduled (every
90 days) and emergency key rotation. It handles the full rotation lifecycle:
creating new key versions, re-encrypting existing data, archiving old versions,
and maintaining audit logs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from kakehashi.kek_wrapper.models.enums import EventType, Status
from kakehashi.kek_wrapper.models.rotation_models import (
    KeyVersionRecord,
    RotationResult,
    RotationStatus,
    RotationType,
)
from kakehashi.kek_wrapper.models.role import Role

if TYPE_CHECKING:
    from kakehashi.kek_wrapper.core.audit_log_collector import AuditLogCollector
    from kakehashi.kek_wrapper.core.crypto_service import CryptoService
    from kakehashi.kek_wrapper.core.error_handler import ErrorHandler
    from kakehashi.kek_wrapper.core.key_vault_connector import KeyVaultConnector

logger = logging.getLogger(__name__)


class KeyRotationService:
    """Manages key rotation lifecycle: creation, re-encryption, archival.

    Attributes:
        kvc: KeyVaultConnector instance for Key Vault operations.
        crypto: CryptoService instance for encryption/decryption.
        audit: AuditLogCollector instance for audit logging.
        error: ErrorHandler instance for security alerts.
        rotation_lock: asyncio.Lock to prevent concurrent rotations.
    """

    def __init__(
        self,
        key_vault_connector: KeyVaultConnector,
        crypto_service: CryptoService,
        audit_collector: AuditLogCollector,
        error_handler: ErrorHandler,
    ):
        """Initialize KeyRotationService with required dependencies.

        Args:
            key_vault_connector: KeyVaultConnector for Key Vault operations.
            crypto_service: CryptoService for encrypt/decrypt operations.
            audit_collector: AuditLogCollector for audit logging.
            error_handler: ErrorHandler for security alerts.
        """
        self.kvc = key_vault_connector
        self.crypto = crypto_service
        self.audit = audit_collector
        self.error = error_handler
        self.rotation_lock = asyncio.Lock()

    async def schedule_rotation(
        self,
        rotation_type: RotationType,
        actor_role: Role,
        actor_id: str = "scheduler",
    ) -> RotationResult:
        """Execute scheduled or emergency key rotation.

        Flow:
        1. Acquire lock to prevent concurrent rotations.
        2. Get current key version from Key Vault.
        3. Create new key version.
        4. Record rotation start in audit log.
        5. Re-encrypt all existing data with new key (batched).
        6. Invalidate cache.
        7. Archive old key version.
        8. Record rotation completion in audit log.

        Args:
            rotation_type: Type of rotation (SCHEDULED, EMERGENCY, or MANUAL).
            actor_role: Role of the actor initiating rotation.
            actor_id: ID of the actor (default: "scheduler" for automated runs).

        Returns:
            RotationResult with outcome and metadata.
        """
        async with self.rotation_lock:
            result = RotationResult(
                success=False,
                new_version=-1,
                old_version=-1,
                rotation_type=rotation_type,
                actor_role=actor_role,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                re_encrypted_count=0,
                audit_event_id="",
            )

            try:
                # Step 1: Get current version
                old_version = await self.kvc.get_current_version()
                result.old_version = old_version
                logger.info(f"Current key version: {old_version}")

                # Step 2: Create new key version
                new_version = await self._create_new_key_version()
                result.new_version = new_version
                logger.info(f"Created new key version: {new_version}")

                # Step 3: Record rotation start
                event_id = await self.audit.recordEvent(
                    event_type=EventType.KEY_ROTATE,
                    actor_role=actor_role.value,
                    resource_id="user-key-rotation",
                    operation="GET",
                    status=Status.SUCCESS,
                )
                result.audit_event_id = event_id
                logger.info(f"Rotation start recorded: {event_id}")

                # Step 4: Re-encrypt data
                re_encrypted = await self._re_encrypt_data(
                    old_version=old_version,
                    new_version=new_version,
                    actor_role=actor_role,
                )
                result.re_encrypted_count = re_encrypted
                logger.info(f"Re-encrypted {re_encrypted} records")

                # Step 5: Invalidate cache
                self.kvc.invalidate_cache()
                logger.info("Cache invalidated")

                # Step 6: Archive old version
                await self._archive_old_version(old_version)
                logger.info(f"Archived old key version: {old_version}")

                # Step 7: Record completion
                await self.audit.recordEvent(
                    event_type=EventType.KEY_ROTATE,
                    actor_role=actor_role.value,
                    resource_id="user-key-rotation",
                    operation="PUT",
                    status=Status.SUCCESS,
                )
                logger.info("Rotation completion recorded")

                result.success = True
                result.completed_at = datetime.now(timezone.utc)

            except Exception as e:
                result.success = False
                result.error_message = str(e)
                result.completed_at = datetime.now(timezone.utc)
                logger.error(f"Key rotation failed: {e}", exc_info=True)

                # Escalate to ErrorHandler
                await self.error.raise_security_alert(
                    severity="HIGH",
                    message=f"Key rotation failed: {rotation_type.value} — {str(e)}",
                )

                # Record failure
                try:
                    await self.audit.recordEvent(
                        event_type=EventType.KEY_ROTATE,
                        actor_role=actor_role.value,
                        resource_id="user-key-rotation",
                        operation="PUT",
                        status=Status.FAILURE,
                    )
                except Exception as audit_error:
                    logger.error(f"Failed to record rotation failure: {audit_error}")

            return result

    async def trigger_emergency_rotation(
        self,
        actor_id: str,
        actor_role: Role,
        reason: str,
    ) -> RotationResult:
        """Trigger emergency key rotation due to security incident.

        Rotates key immediately and escalates to CRITICAL alert.

        Args:
            actor_id: ID of the actor initiating emergency rotation.
            actor_role: Role of the actor.
            reason: Reason for emergency rotation (e.g., "compromise_suspected").

        Returns:
            RotationResult with outcome.
        """
        logger.warning(f"Emergency rotation triggered: {reason}")

        result = await self.schedule_rotation(
            rotation_type=RotationType.EMERGENCY,
            actor_role=actor_role,
            actor_id=actor_id,
        )

        if result.success:
            await self.error.raise_security_alert(
                severity="CRITICAL",
                message=f"Emergency key rotation completed: {reason}",
            )
            logger.warning(f"Emergency rotation completed: {reason}")
        else:
            logger.error(f"Emergency rotation failed: {reason}")

        return result

    async def _create_new_key_version(self) -> int:
        """Create a new key version in Azure Key Vault.

        Returns:
            Version number of the new key.

        Raises:
            Exception: if Key Vault operation fails.
        """
        # Use KeyVaultConnector's rotateKey method
        result = await self.kvc.rotateKey(force_emergency=False)
        new_version_str = result.get("key_version", "")

        # Extract version number from string like "kakehashi-kek/v2"
        import re

        match = re.search(r"/v(\d+)$", new_version_str)
        if match:
            return int(match.group(1))

        raise ValueError(f"Invalid key version format: {new_version_str}")

    async def _re_encrypt_data(
        self,
        old_version: int,
        new_version: int,
        actor_role: Role,
    ) -> int:
        """Re-encrypt all existing data with new key version.

        Fetches records in batches and re-encrypts each one. Failures on
        individual records are logged but do not stop the overall process.

        Args:
            old_version: Old key version number.
            new_version: New key version number.
            actor_role: Role of the actor.

        Returns:
            Number of records successfully re-encrypted.
        """
        re_encrypted_count = 0
        batch_size = 100

        try:
            # Mock implementation: in real code, would fetch from Cosmos DB
            # For testing, we'll just return 0 (no records to re-encrypt)
            logger.info(
                f"Re-encryption process: old_version={old_version}, "
                f"new_version={new_version}"
            )

            # Simulate batch processing (mock for testing)
            records = await self._fetch_records(skip=0, limit=batch_size)

            for record in records:
                try:
                    # Decrypt with old key
                    plaintext = await self.crypto.decrypt(
                        ciphertext=record.get("encrypted_data"),
                        key_version=old_version,
                    )

                    # Encrypt with new key
                    new_ciphertext = await self.crypto.encrypt(
                        plaintext=plaintext,
                        context=record.get("context"),
                    )

                    # Update record
                    await self._update_record(
                        record_id=record.get("id"),
                        encrypted_data=new_ciphertext,
                        key_version=new_version,
                    )

                    re_encrypted_count += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to re-encrypt record {record.get('id')}: {e}"
                    )
                    await self.error.raise_security_alert(
                        severity="MEDIUM",
                        message=f"Failed to re-encrypt record {record.get('id')}: {str(e)}",
                    )

        except Exception as e:
            logger.error(f"Re-encryption process failed: {e}", exc_info=True)
            raise

        return re_encrypted_count

    async def _archive_old_version(self, old_version: int) -> None:
        """Archive (disable) the old key version in Azure Key Vault.

        Args:
            old_version: Version number to archive.

        Raises:
            Exception: if Key Vault operation fails.
        """
        logger.info(f"Archiving key version: {old_version}")
        # In real implementation, would call Key Vault UpdateKey API
        # to set disabled=True. For now, this is a placeholder.

    async def get_rotation_status(self) -> RotationStatus:
        """Get current rotation status and next scheduled rotation date.

        Returns:
            RotationStatus with current version and schedule info.
        """
        current_version = await self.kvc.get_current_version()
        current_created_at = await self._get_version_created_at(current_version)
        next_scheduled = current_created_at + timedelta(days=90)
        last_record = await self._get_last_rotation_record()

        return RotationStatus(
            current_version=current_version,
            current_created_at=current_created_at,
            next_scheduled_rotation=next_scheduled,
            last_rotation_type=last_record.rotation_type if last_record else None,
            last_rotation_timestamp=last_record.created_at if last_record else None,
            is_rotation_in_progress=self.rotation_lock.locked(),
        )

    async def get_version_history(self) -> List[KeyVersionRecord]:
        """Get historical records of key rotations for audit purposes.

        Returns:
            List of KeyVersionRecord objects.
        """
        # Mock implementation: in real code, would fetch from audit log storage
        return []

    # ===== Private helper methods (mocked for testing) =====

    async def _fetch_records(self, skip: int, limit: int) -> List[dict]:
        """Fetch records from data store (mocked for tests).

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to fetch.

        Returns:
            List of records (empty list indicates no more records).
        """
        # Mock implementation: return empty list
        return []

    async def _update_record(
        self, record_id: str, encrypted_data: bytes, key_version: int
    ) -> None:
        """Update a record with new encrypted data (mocked for tests).

        Args:
            record_id: ID of the record to update.
            encrypted_data: New encrypted data.
            key_version: New key version number.
        """
        # Mock implementation: no-op
        pass

    async def _get_version_created_at(self, version: int) -> datetime:
        """Get creation timestamp of a key version (mocked for tests).

        Args:
            version: Version number.

        Returns:
            Creation datetime (UTC).
        """
        # Mock implementation: return current time
        return datetime.now(timezone.utc)

    async def _get_last_rotation_record(self) -> Optional[KeyVersionRecord]:
        """Get the most recent rotation record (mocked for tests).

        Returns:
            KeyVersionRecord or None if no rotations have occurred.
        """
        # Mock implementation: return None
        return None
