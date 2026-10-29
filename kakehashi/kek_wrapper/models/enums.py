"""Audit vocabulary enums (Phase E, Task 1.3).

``Role`` is not redefined here: it lives in ``models/role.py`` (Task 1.1,
Decision 2) with lowercase values and no ``SYSTEM`` member. It is re-exported
from this module so audit code can import the whole vocabulary from one place.

Both enums are ``str``-valued (``class X(str, Enum)``) as required by
``KeyVaultConnector.AuditSink`` (Task 1.1): the connector passes event types
and statuses as their string values, and those strings must equal the enum
values exactly.
"""

from __future__ import annotations

from enum import Enum

from .role import Role

__all__ = ["EventType", "Role", "Status"]


class EventType(str, Enum):
    """Type of an audit event (the ``event_type`` field of an AuditLogEntry)."""

    # Spec section 1.4 vocabulary. KeyVaultConnector.logAccess emits these two
    # (AUTHENTICATE / GET_SECRET -> KEY_ACCESS, ROTATE_KEY(_CHECK) -> KEY_ROTATE).
    KEY_ACCESS = "KEY_ACCESS"
    KEY_ROTATE = "KEY_ROTATE"
    SECRET_DECRYPT = "SECRET_DECRYPT"  # nosec B105 - enum member, not a secret
    USER_LOGIN = "USER_LOGIN"
    DATA_EXPORT = "DATA_EXPORT"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    # Spec section 3.1 example: data-level access audited by the caller.
    DATA_READ = "DATA_READ"

    # Finer-grained Key Vault events (Task 1.3 brief).
    KEY_VAULT_AUTH = "KEY_VAULT_AUTH"
    KEY_VAULT_GET_SECRET = "KEY_VAULT_GET_SECRET"  # nosec B105 - enum member, not a secret
    KEY_VAULT_ROTATE = "KEY_VAULT_ROTATE"

    # CryptoService operations (Task 1.2).
    CRYPTO_ENCRYPT = "CRYPTO_ENCRYPT"
    CRYPTO_DECRYPT = "CRYPTO_DECRYPT"

    # Emitted by AuditLogCollector itself.
    AUDIT_EXPORT = "AUDIT_EXPORT"
    AUDIT_VALIDATE = "AUDIT_VALIDATE"

    # Security failures recorded by ErrorHandler.logSecurityEvent (Task 1.4).
    SECURITY = "SECURITY"


class Status(str, Enum):
    """Outcome of an audited operation (the ``status`` field)."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    # Access refused by policy (spec section 1.4; KeyVaultConnector vocabulary).
    DENIED = "DENIED"
    # Operation intentionally not performed (Task 1.3 brief).
    SKIPPED = "SKIPPED"
