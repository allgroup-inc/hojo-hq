"""KAKEHASHI core wrapper: the single entry point to Key Vault for every chat."""

from .core.audit_log_collector import (
    AuditError,
    AuditLogCollector,
    AzureAppendBlobAuditStore,
    InMemoryAuditLogStore,
)
from .core.crypto_service import CryptoService
from .core.jwt_manager import JWTManager
from .core.key_vault_connector import (
    DEFAULT_CACHE_TTL_SECONDS,
    KeyVaultAuthenticationError,
    KeyVaultConnector,
    KeyVaultError,
)
from .core.rbac_enforcer import RBACEnforcer
from .models.audit_event import AuditLogEntry
from .models.crypto_models import EncryptedData, KeyVersion
from .models.enums import EventType, Role, Status
from .models.rbac_models import Permission, ROLE_PERMISSIONS

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
    "JWTManager",
    "KeyVaultAuthenticationError",
    "KeyVaultConnector",
    "KeyVaultError",
    "KeyVersion",
    "Permission",
    "RBACEnforcer",
    "Role",
    "ROLE_PERMISSIONS",
    "Status",
]
