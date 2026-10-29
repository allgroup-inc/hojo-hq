"""Data models shared by the KAKEHASHI core wrapper (Phase E).

These are plain dataclasses with no Azure SDK dependency so that every chat
implementation can import them without pulling in network clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class EncryptedData:
    """An encrypted record together with what is needed to decrypt it.

    ``key_version`` is mandatory: decryption must select the exact key version
    that encrypted the record, otherwise data written before a rotation becomes
    unreadable (Phase E plan, critical risk 1).
    """

    ciphertext: bytes
    key_version: str
    key_name: str
    nonce: bytes = b""
    algorithm: str = DEFAULT_ALGORITHM
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.key_version:
            raise ValueError("EncryptedData.key_version is required")
        if not self.key_name:
            raise ValueError("EncryptedData.key_name is required")
