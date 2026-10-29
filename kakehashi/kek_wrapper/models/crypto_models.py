"""Data models shared by the KAKEHASHI core wrapper (Phase E).

These are plain dataclasses with no Azure SDK dependency so that every chat
implementation can import them without pulling in network clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

#: Scheduled rotation interval required by the Phase E spec (section 1.6).
DEFAULT_ROTATION_INTERVAL_DAYS = 90

#: Algorithm identifier recorded on every encrypted record.
DEFAULT_ALGORITHM = "AES-256-GCM"


@dataclass(frozen=True)
class KeyVersion:
    """Metadata of one version of a Key Vault secret (never the key material)."""

    secret_name: str
    version: str
    created_on: Optional[datetime] = None
    enabled: bool = True
    emergency: bool = False

    def age(self, now: Optional[datetime] = None) -> Optional[timedelta]:
        """Age of this version, or None when Key Vault did not report created_on."""
        if self.created_on is None:
            return None
        now = now or datetime.now(timezone.utc)
        created = self.created_on
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return now - created

    def is_rotation_due(
        self,
        now: Optional[datetime] = None,
        rotation_interval_days: int = DEFAULT_ROTATION_INTERVAL_DAYS,
    ) -> bool:
        """True when the version is at least ``rotation_interval_days`` old.

        An unknown creation date is treated as due: rotating unnecessarily is
        safe, keeping a key of unknown age is not.
        """
        age = self.age(now)
        if age is None:
            return True
        return age >= timedelta(days=rotation_interval_days)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "secret_name": self.secret_name,
            "key_version": self.version,
            "created_at": self.created_on.isoformat() if self.created_on else None,
            "enabled": self.enabled,
            "emergency": self.emergency,
        }


#: IV length used by CryptoService for AES-256-GCM (Task 1.2 brief: 16 bytes).
GCM_IV_LENGTH = 16

#: Length of the GCM authentication tag appended to ``EncryptedData.ciphertext``.
GCM_TAG_LENGTH = 16


@dataclass(frozen=True)
class EncryptedData:
    """An AES-256-GCM encrypted record (Phase E, Task 1.2).

    The four fields are locked for Task 1.3 (no additions).

    ``ciphertext`` holds the GCM ciphertext followed by the 16-byte
    authentication tag (the layout produced by ``cryptography``'s ``AESGCM``),
    so the tag travels with the record without a separate field.

    ``key_version`` records which KEK version encrypted the record. The field
    type stays ``Optional[str]`` (locked layout), but ``CryptoService.encrypt``
    requires a non-empty ``key_version=`` (Round 3, Decision 1), so every
    record it produces carries one: decryption must select the exact key
    version that encrypted the record, otherwise data written before a
    rotation becomes unreadable (Phase E plan, critical risk 1).

    Associated data passed to ``encrypt`` is authenticated but deliberately
    not stored here; the caller keeps or rebuilds it for ``decrypt``.
    """

    ciphertext: bytes
    iv: bytes  # 16 bytes (128 bits) for GCM
    key_version: Optional[str]  # which KEK version was used
    timestamp: datetime  # when encrypted (for audit)
