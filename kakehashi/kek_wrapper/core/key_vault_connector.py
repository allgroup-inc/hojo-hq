"""KeyVaultConnector: the only sanctioned path from KAKEHASHI code to Azure Key Vault.

Phase E, Task 1.1. Every chat implementation fetches key material through this
class instead of calling the Azure SDK directly (CI rejects direct calls).

Authentication
    Azure Managed Identity only (``ManagedIdentityCredential``). No secret,
    connection string or client secret is ever read by this module. A
    user-assigned identity is selected with ``AZURE_CLIENT_ID``; without it the
    system-assigned identity is used. The vault is taken from
    ``AZURE_KEY_VAULT_URL`` unless passed explicitly.

Secret format
    Key material is stored in Key Vault as a base64 string
    (content type ``application/octet-stream;base64``). ``getSecret`` returns
    the decoded bytes. A value that is not valid base64 is rejected rather than
    silently re-encoded, because a wrong-length key must never reach the cipher.

Caching strategy (handoff point for Task 1.2+)
    * TTL: 300 seconds (5 minutes) per entry, measured on a monotonic clock.
    * Cache key: ``(secret_name, key_version)``. ``key_version=None`` means
      "latest" and is cached separately from the concrete version it resolved
      to, so a later pinned lookup of that version is also a cache hit.
    * Refresh: lazy. An expired entry is dropped and re-fetched on the next
      call; there is no background refresh task.
    * Rotation: a scheduled rotation drops only the "latest" entry (older
      versions are immutable and must keep decrypting old records). An
      emergency rotation drops every cached version of the secret so that a
      version disabled in Key Vault after a compromise is not served from
      memory.
    * Values are held only in process memory and never logged.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
import re
import secrets as _secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Protocol, Tuple

from ..models.crypto_models import DEFAULT_ROTATION_INTERVAL_DAYS, KeyVersion

try:  # azure-core ships with the Azure SDK; tests may run without it.
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:  # pragma: no cover - exercised only without the SDK installed

    class ResourceNotFoundError(Exception):  # type: ignore[no-redef]
        """Fallback so the module imports without azure-core."""


logger = logging.getLogger(__name__)

#: Cache lifetime required by the Phase E plan (Task 1.1 output).
DEFAULT_CACHE_TTL_SECONDS = 300

#: OAuth scope used to prove the Managed Identity session is usable.
KEY_VAULT_SCOPE = "https://vault.azure.net/.default"

#: Default name of the key-encryption-key secret rotated by ``rotateKey``.
DEFAULT_KEK_SECRET_NAME = "kakehashi-kek"

#: AES-256 key length in bytes.
KEY_LENGTH_BYTES = 32

KEY_CONTENT_TYPE = "application/octet-stream;base64"

ENV_VAULT_URL = "AZURE_KEY_VAULT_URL"
ENV_CLIENT_ID = "AZURE_CLIENT_ID"

# Key Vault object names: 1-127 characters, alphanumerics and dashes only.
_SECRET_NAME_RE = re.compile(r"^[0-9A-Za-z-]{1,127}$")

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILURE = "FAILURE"
STATUS_SKIPPED = "SKIPPED"  # scheduled rotation called before the key was due

OP_AUTHENTICATE = "AUTHENTICATE"
OP_GET_SECRET = "GET_SECRET"
OP_ROTATE_KEY = "ROTATE_KEY"


class KeyVaultError(Exception):
    """Base error for Key Vault access through the wrapper."""


class KeyVaultAuthenticationError(KeyVaultError):
    """Managed Identity authentication failed."""


class AuditSink(Protocol):
    """What ``logAccess`` delegates to. AuditLogCollector (Task 1.3) implements it."""

    async def recordEvent(
        self,
        event_type: str,
        resource_id: str,
        status: str,
        error_code: Optional[str] = None,
    ) -> Any: ...


CredentialFactory = Callable[[Optional[str]], Any]
ClientFactory = Callable[[str, Any], Any]


def _default_credential_factory(client_id: Optional[str]) -> Any:
    from azure.identity.aio import ManagedIdentityCredential

    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    return ManagedIdentityCredential()


def _default_client_factory(vault_url: str, credential: Any) -> Any:
    from azure.keyvault.secrets.aio import SecretClient

    return SecretClient(vault_url=vault_url, credential=credential)


@dataclass
class _CacheEntry:
    value: bytes
    key_version: KeyVersion
    expires_at: float


class KeyVaultConnector:
    """Managed-Identity Key Vault client with a 5-minute in-memory key cache."""

    def __init__(
        self,
        vault_url: Optional[str] = None,
        *,
        client_id: Optional[str] = None,
        kek_secret_name: str = DEFAULT_KEK_SECRET_NAME,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        rotation_interval_days: int = DEFAULT_ROTATION_INTERVAL_DAYS,
        audit_collector: Optional[AuditSink] = None,
        credential_factory: Optional[CredentialFactory] = None,
        client_factory: Optional[ClientFactory] = None,
        clock: Callable[[], float] = time.monotonic,
        utcnow: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        resolved_url = vault_url or os.environ.get(ENV_VAULT_URL)
        if not resolved_url:
            raise ValueError(
                f"Key Vault URL is required (argument or {ENV_VAULT_URL} environment variable)"
            )
        if not resolved_url.startswith("https://"):
            raise ValueError("Key Vault URL must use https://")
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        self._validate_name(kek_secret_name)

        self.vault_url = resolved_url
        self.client_id = client_id or os.environ.get(ENV_CLIENT_ID) or None
        self.kek_secret_name = kek_secret_name
        self.cache_ttl_seconds = cache_ttl_seconds
        self.rotation_interval_days = rotation_interval_days
        self._audit = audit_collector
        self._credential_factory = credential_factory or _default_credential_factory
        self._client_factory = client_factory or _default_client_factory
        self._clock = clock
        self._utcnow = utcnow

        self._credential: Any = None
        self._client: Any = None
        self._auth_lock = asyncio.Lock()
        self._cache: Dict[Tuple[str, Optional[str]], _CacheEntry] = {}

    # ------------------------------------------------------------------ auth

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None

    async def authenticate(self) -> None:
        """Establish the Managed Identity session and the Key Vault client.

        Requests a token for the Key Vault scope up front so that a missing or
        misconfigured identity fails here, not on the first decryption.
        """
        async with self._auth_lock:
            if self._client is not None:
                return
            credential = None
            try:
                credential = self._credential_factory(self.client_id)
                await credential.get_token(KEY_VAULT_SCOPE)
                client = self._client_factory(self.vault_url, credential)
            except Exception as exc:
                if credential is not None and hasattr(credential, "close"):
                    try:
                        await credential.close()
                    except Exception:  # pragma: no cover - best effort cleanup
                        logger.warning("failed to close credential after auth error")
                await self.logAccess(
                    OP_AUTHENTICATE,
                    STATUS_FAILURE,
                    resource_id=self.vault_url,
                    error_code=type(exc).__name__,
                )
                raise KeyVaultAuthenticationError(
                    f"Managed Identity authentication to {self.vault_url} failed: "
                    f"{type(exc).__name__}"
                ) from exc
            self._credential = credential
            self._client = client
        await self.logAccess(OP_AUTHENTICATE, STATUS_SUCCESS, resource_id=self.vault_url)

    async def close(self) -> None:
        """Release SDK sessions and drop cached key material."""
        self.invalidate_cache()
        client, credential = self._client, self._credential
        self._client = None
        self._credential = None
        if client is not None and hasattr(client, "close"):
            await client.close()
        if credential is not None and hasattr(credential, "close"):
            await credential.close()

    async def __aenter__(self) -> "KeyVaultConnector":
        await self.authenticate()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    # --------------------------------------------------------------- secrets

    async def getSecret(self, secret_name: str, key_version: Optional[str] = None) -> bytes:
        """Return the key bytes for ``secret_name`` (latest, or a pinned version)."""
        value, _ = await self.getSecretWithVersion(secret_name, key_version)
        return value

    async def getSecretWithVersion(
        self, secret_name: str, key_version: Optional[str] = None
    ) -> Tuple[bytes, KeyVersion]:
        """Like ``getSecret`` but also returns which version was served.

        Encryption needs this to record ``key_version`` on each record.
        """
        self._validate_name(secret_name)
        cache_key = (secret_name, key_version)
        entry = self._cache.get(cache_key)
        now = self._clock()
        if entry is not None:
            if now < entry.expires_at:
                return entry.value, entry.key_version
            del self._cache[cache_key]

        if not self.is_authenticated:
            await self.authenticate()

        try:
            secret = await self._client.get_secret(secret_name, key_version)
            value = self._decode(secret.value)
        except Exception as exc:
            await self.logAccess(
                OP_GET_SECRET,
                STATUS_FAILURE,
                resource_id=self._resource(secret_name, key_version),
                error_code=type(exc).__name__,
            )
            if isinstance(exc, KeyVaultError):
                raise
            raise KeyVaultError(
                f"failed to fetch secret {secret_name!r}"
                f"{' version ' + key_version if key_version else ''}: {type(exc).__name__}"
            ) from exc

        version = self._key_version_from(secret_name, secret)
        expires_at = self._clock() + self.cache_ttl_seconds
        entry = _CacheEntry(value=value, key_version=version, expires_at=expires_at)
        self._cache[cache_key] = entry
        if version.version:
            self._cache[(secret_name, version.version)] = entry

        await self.logAccess(
            OP_GET_SECRET,
            STATUS_SUCCESS,
            resource_id=self._resource(secret_name, version.version or key_version),
        )
        return value, version

    def invalidate_cache(self, secret_name: Optional[str] = None) -> None:
        """Drop cached entries for one secret, or all of them."""
        if secret_name is None:
            self._cache.clear()
            return
        for key in [k for k in self._cache if k[0] == secret_name]:
            del self._cache[key]

    # -------------------------------------------------------------- rotation

    async def rotateKey(self, force_emergency: bool = False) -> dict:
        """Create a new version of the KEK secret.

        Scheduled call (``force_emergency=False``): rotates only when the current
        version is at least ``rotation_interval_days`` (90) old; otherwise returns
        the current version's metadata with ``rotated: False``.

        Emergency call (``force_emergency=True``): rotates immediately regardless
        of age and purges every cached version of the KEK.

        Old versions are never disabled here: records encrypted before the
        rotation must stay decryptable until they are re-encrypted. Disabling
        a compromised version is an operator action in Key Vault.

        Returns a dict with at least ``key_version`` and ``created_at``
        (ISO 8601), plus ``secret_name``, ``previous_version``, ``rotated`` and
        ``emergency``.
        """
        if not self.is_authenticated:
            await self.authenticate()
        name = self.kek_secret_name
        resource = self._resource(name, None)

        try:
            current: Optional[KeyVersion]
            try:
                current_secret = await self._client.get_secret(name)
                current = self._key_version_from(name, current_secret)
            except ResourceNotFoundError:
                current = None

            not_due = (
                not force_emergency
                and current is not None
                and not current.is_rotation_due(self._utcnow(), self.rotation_interval_days)
            )
            new_secret = None
            if not not_due:
                new_key = base64.b64encode(_secrets.token_bytes(KEY_LENGTH_BYTES)).decode("ascii")
                new_secret = await self._client.set_secret(
                    name,
                    new_key,
                    content_type=KEY_CONTENT_TYPE,
                    tags={
                        "kakehashi-rotation": "emergency" if force_emergency else "scheduled",
                        "kakehashi-previous-version": current.version if current else "",
                    },
                )
        except Exception as exc:
            await self.logAccess(
                OP_ROTATE_KEY, STATUS_FAILURE, resource_id=resource, error_code=type(exc).__name__
            )
            raise KeyVaultError(f"key rotation for {name!r} failed: {type(exc).__name__}") from exc

        if not_due and current is not None:
            await self.logAccess(
                OP_ROTATE_KEY, STATUS_SKIPPED, resource_id=self._resource(name, current.version)
            )
            result = current.to_dict()
            result.update(previous_version=None, rotated=False, emergency=False)
            return result

        if force_emergency:
            self.invalidate_cache(name)
        else:
            self._cache.pop((name, None), None)

        new_version = self._key_version_from(name, new_secret, emergency=force_emergency)
        await self.logAccess(
            OP_ROTATE_KEY, STATUS_SUCCESS, resource_id=self._resource(name, new_version.version)
        )
        result = new_version.to_dict()
        if result["created_at"] is None:
            result["created_at"] = self._utcnow().isoformat()
        result.update(
            previous_version=current.version if current else None,
            rotated=True,
            emergency=force_emergency,
        )
        return result

    # ----------------------------------------------------------------- audit

    async def logAccess(
        self,
        operation: str,
        status: str,
        *,
        resource_id: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """Record a Key Vault access in the central audit log.

        Delegates to the AuditLogCollector when one is attached (Task 1.3);
        until then it writes a structured line to the standard logger. Key
        material is never passed here. Errors from the collector propagate:
        an access that cannot be audited must not be silently accepted.
        """
        event_type = f"KEY_VAULT_{operation}"
        resource = resource_id or self.vault_url
        if self._audit is not None:
            await self._audit.recordEvent(
                event_type=event_type,
                resource_id=resource,
                status=status,
                error_code=error_code,
            )
            return
        logger.info(
            "audit event_type=%s resource_id=%s status=%s error_code=%s",
            event_type,
            resource,
            status,
            error_code,
        )

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _validate_name(secret_name: str) -> None:
        if not isinstance(secret_name, str) or not _SECRET_NAME_RE.match(secret_name):
            raise ValueError(
                "secret name must be 1-127 characters of letters, digits and '-' "
                "(Azure Key Vault naming rule)"
            )

    @staticmethod
    def _decode(value: Optional[str]) -> bytes:
        if not value:
            raise KeyVaultError("secret has no value")
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            # Never include the value itself in the message.
            raise KeyVaultError("secret value is not valid base64 key material") from exc

    @staticmethod
    def _key_version_from(name: str, secret: Any, emergency: bool = False) -> KeyVersion:
        props = getattr(secret, "properties", None)
        return KeyVersion(
            secret_name=name,
            version=getattr(props, "version", None) or "",
            created_on=getattr(props, "created_on", None),
            enabled=bool(getattr(props, "enabled", True)),
            emergency=emergency,
        )

    def _resource(self, name: str, version: Optional[str]) -> str:
        base = f"{self.vault_url.rstrip('/')}/secrets/{name}"
        return f"{base}/{version}" if version else base
