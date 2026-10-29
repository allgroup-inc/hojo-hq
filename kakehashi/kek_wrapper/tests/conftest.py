"""Pytest fixtures for KAKEHASHI core wrapper tests (Phase E, Tasks 1.1-1.4).

These fixtures provide shared mocks for Azure SDK clients, crypto services,
audit collectors, and alert services, enabling tests across all modules to
use consistent mock objects without duplicating setup code.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from kakehashi.kek_wrapper.models.crypto_models import EncryptedData


@pytest.fixture
async def mock_key_vault_client():
    """Mock azure.keyvault.secrets.aio.SecretClient.

    Returns an AsyncMock configured to return a mock secret with
    a base64-encoded 32-byte key (matching the fixture used in Task 1.1).
    """
    client = AsyncMock()
    # Return value for get_secret: mock with 32-byte base64-encoded key
    secret_value = base64.b64encode(b"abcdefghijklmnopqrstuvwxyz012345").decode("ascii")
    client.get_secret = AsyncMock(
        return_value=MagicMock(value=secret_value)
    )
    # Mock list_properties_of_secrets for key version enumeration
    client.list_properties_of_secrets = AsyncMock(return_value=[])
    return client


@pytest.fixture
async def mock_blob_storage_client():
    """Mock azure.storage.blob.aio.ContainerClient (append blob).

    Returns an AsyncMock configured for append blob operations used by
    AuditLogCollector (Task 1.3).
    """
    client = AsyncMock()
    # Mock get_append_blob_client to return an async blob client
    append_blob = AsyncMock()
    append_blob.exists = AsyncMock(return_value=False)
    append_blob.create_append_blob = AsyncMock()
    append_blob.append_block = AsyncMock()
    client.get_append_blob_client = MagicMock(return_value=append_blob)
    return client


@pytest.fixture
async def mock_audit_collector():
    """Mock AuditLogCollector for KeyVaultConnector & ErrorHandler tests.

    Returns an AsyncMock configured to record events and validate logs,
    matching the interface used in Tasks 1.1 and 1.4.
    """
    collector = AsyncMock()
    # recordEvent returns an event ID string
    collector.recordEvent = AsyncMock(return_value="evt-12345")
    # validateLog returns boolean (True = valid)
    collector.validateLog = AsyncMock(return_value=True)
    # Additional methods that may be called by error handling
    collector.close = AsyncMock()
    return collector


@pytest.fixture
async def mock_crypto_service():
    """Mock CryptoService for AuditLogCollector tests.

    Returns an AsyncMock configured to encrypt/decrypt data and validate
    signatures, matching the interface used in Task 1.3.
    """
    service = AsyncMock()

    # encrypt: returns EncryptedData with random IV
    encrypted_data = EncryptedData(
        ciphertext=b"encrypted_ciphertext_bytes_with_tag",
        iv=b"0123456789abcdef",  # 16 bytes
        key_version="kakehashi-kek/v1",
        timestamp=datetime.now(timezone.utc),
    )
    service.encrypt = AsyncMock(return_value=encrypted_data)

    # decrypt: returns plaintext bytes
    service.decrypt = AsyncMock(return_value=b"decrypted_plaintext")

    # validateSignature: returns boolean
    service.validateSignature = MagicMock(return_value=True)

    # signLogEntry: returns hex-encoded HMAC
    service.signLogEntry = MagicMock(return_value="abcd" * 16)  # 64-char hex

    return service


@pytest.fixture
def mock_alert_service():
    """Mock alert service (Slack/email) for ErrorHandler tests.

    Returns a MagicMock configured for alert sending operations used
    in Task 1.4 error handling and security event notification.
    """
    alerter = MagicMock()
    # send method for alert notifications
    alerter.send = MagicMock(return_value=None)
    # Additional methods for batch or template-based alerts
    alerter.send_batch = MagicMock(return_value=None)
    return alerter
