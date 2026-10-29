"""KAKEHASHI core wrapper: the single entry point to Key Vault for every chat."""

from .core.audit_log_collector import (
    AuditError,
    AuditLogCollector,
    AzureAppendBlobAuditStore,
    InMemoryAuditLogStore,
)
from .core.crypto_service import CryptoService
from .core.key_vault_connector import (
    DEFAULT_CACHE_TTL_SECONDS,
    KeyVaultAuthenticationError,
    KeyVaultConnector,
    KeyVaultError,
)
from .models.audit_event import AuditLogEntry
from .models.crypto_models import EncryptedData, KeyVersion
from .models.enums import EventType, Role, Status

__all__ = [
    "AuditError",
    "AuditLogCollector",
    "AuditLogEntry",
    "AzureAppendBlobAuditStore",
    "CryptoService",
    "DEFAULT_CACHE_TTL_SECONDS",
    "EncryptedData",
    "EventType",
    "InMemoryAuditLogStore",
    "KeyVaultAuthenticationError",
    "KeyVaultConnector",
    "KeyVaultError",
    "KeyVersion",
    "Role",
    "Status",
]
