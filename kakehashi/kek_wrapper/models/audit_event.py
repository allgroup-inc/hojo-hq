"""AuditLogEntry: one signed, immutable audit record (Phase E, Task 1.3).

The field set is locked for Task 1.4 and later (no additions). Field names
and order follow the Task 1.3 brief.

Stored form (``to_dict``) and signing
    * ``timestamp`` is stored as ISO 8601 UTC with a ``Z`` suffix,
      ``YYYY-MM-DDTHH:MM:SS[.ffffff]Z``, produced by the same helper that
      ``CryptoService`` uses to canonicalize datetimes (Task 1.2). The stored
      string therefore signs exactly like the ``datetime`` it came from.
    * ``event_type``, ``actor_role`` and ``status`` are stored as their enum
      ``.value`` strings (``actor_role`` is lowercase, e.g. ``"operator"``).
    * ``signature`` is the HMAC-SHA256 hex digest over every other field
      (``CryptoService.signLogEntry``; keys sorted, ``signature`` excluded).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Tuple, Type, TypeVar, Union

# Single source of truth for the signed timestamp form (Task 1.2, Finding 1).
from ..core.crypto_service import _format_utc
from .enums import EventType, Role, Status

_E = TypeVar("_E", EventType, Role, Status)


def _enum_value(enum_cls: Type[_E], value: Union[_E, str], name: str) -> str:
    """Return the string value of ``value`` as a member of ``enum_cls``.

    Accepts an enum member or its exact string value; anything else raises
    ``ValueError`` (``"OPERATOR"`` is not a valid ``Role``: values are lowercase).
    """
    if isinstance(value, enum_cls):
        return value.value
    if isinstance(value, Enum) and not isinstance(value, enum_cls):
        raise ValueError(f"{name} must be a {enum_cls.__name__}, got {type(value).__name__}")
    try:
        return enum_cls(value).value
    except ValueError:
        allowed = ", ".join(repr(m.value) for m in enum_cls)
        raise ValueError(f"invalid {name} {value!r}; allowed: {allowed}") from None


def parse_utc_timestamp(value: str) -> datetime:
    """Parse a stored ``...Z`` timestamp; reject any other textual form.

    Raises ``ValueError`` unless ``value`` is exactly what ``_format_utc``
    produces for the parsed instant (so ``+00:00`` or ``+09:00`` forms, which
    would sign differently, are rejected).
    """
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be an ISO 8601 UTC string ending in 'Z'")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if _format_utc(parsed) != value:
        raise ValueError("timestamp is not in canonical YYYY-MM-DDTHH:MM:SS[.ffffff]Z form")
    return parsed


@dataclass(frozen=True)
class AuditLogEntry:
    """One audit record. Construct through ``AuditLogCollector.recordEvent``."""

    event_id: str  # "evt-YYYYMMDD-<uuid4 hex>"
    timestamp: datetime  # timezone-aware; stored as ...Z (UTC)
    event_type: str  # EventType value
    actor: str  # user / service making the request
    actor_role: str  # Role value (lowercase)
    resource_id: str  # resource accessed (e.g. Key Vault secret URL)
    operation: str  # action (GET, PUT, ROTATE, EXPORT, ...)
    status: str  # Status value
    result: Dict[str, Any] = field(default_factory=dict)  # operation output (incl. error_code)
    context: Dict[str, Any] = field(default_factory=dict)  # extra context (ip, user agent, ...)
    signature: str = ""  # HMAC-SHA256 hex digest (64 chars)

    def __post_init__(self) -> None:
        for name in ("event_id", "actor", "resource_id", "operation"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.timestamp, datetime) or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be a timezone-aware datetime")
        object.__setattr__(
            self, "event_type", _enum_value(EventType, self.event_type, "event_type")
        )
        object.__setattr__(self, "actor_role", _enum_value(Role, self.actor_role, "actor_role"))
        object.__setattr__(self, "status", _enum_value(Status, self.status, "status"))
        for name in ("result", "context"):
            if not isinstance(getattr(self, name), dict):
                raise ValueError(f"{name} must be a dict")
        if not isinstance(self.signature, str):
            raise ValueError("signature must be a string")

    def to_dict(self) -> Dict[str, Any]:
        """Stored JSON form (all fields; timestamp as a ``...Z`` string)."""
        return {
            "event_id": self.event_id,
            "timestamp": _format_utc(self.timestamp),
            "event_type": self.event_type,
            "actor": self.actor,
            "actor_role": self.actor_role,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "status": self.status,
            "result": dict(self.result),
            "context": dict(self.context),
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuditLogEntry":
        """Parse a stored entry. Raises ``ValueError`` on missing/extra fields or bad values."""
        if not isinstance(data, Mapping):
            raise ValueError(f"audit entry must be a mapping, got {type(data).__name__}")
        keys = set(data)
        if keys != set(FIELD_NAMES):
            missing = sorted(set(FIELD_NAMES) - keys)
            extra = sorted(keys - set(FIELD_NAMES))
            raise ValueError(f"audit entry schema mismatch: missing={missing} extra={extra}")
        values = dict(data)
        values["timestamp"] = parse_utc_timestamp(values["timestamp"])
        return cls(**values)


#: Field names of an AuditLogEntry in declaration order (the locked schema).
FIELD_NAMES: Tuple[str, ...] = tuple(f.name for f in fields(AuditLogEntry))
