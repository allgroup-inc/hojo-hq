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
    silently re-encoded, so corrupted or hand-provisioned plaintext never
    reaches the cipher. The decoded length is not checked here (secrets of
    different purposes have different lengths); CryptoService (Task 1.2)
    validates the key length for its algorithm.

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
    * Invalidation is race-safe: every invalidation (manual or by rotation)
      bumps a per-secret generation number. A fetch that was already in flight
      when the generation changed returns its value to its own caller but is
      not written to the cache, so a pre-rotation "latest" key cannot be
      re-cached after the purge.
    * Audit before cache: a fetched value is cached (and returned) only after
      its SUCCESS audit record was accepted. If the audit collector fails, the
      call raises and nothing is cached.
    * Audit granularity: one ``KEY_ACCESS`` record per Key Vault round-trip.
      Cache hits are served from process memory and are not audited
      individually; data-level access is audited by the caller
      (e.g. ``DATA_READ``, spec section 3.1).
    * Values are held only in process memory and never logged.

Audit vocabulary (spec section 1.4, consumed by AuditLogCollector, Task 1.3)
    ``logAccess`` operations map to the spec's event types and resource
    operations: ``AUTHENTICATE`` and ``GET_SECRET`` -> ``KEY_ACCESS`` / ``GET``;
    ``ROTATE_KEY`` -> ``KEY_ROTATE`` / ``PUT``; ``ROTATE_KEY_CHECK`` (scheduled
    rotation that was not yet due, nothing written) -> ``KEY_ROTATE`` / ``GET``.
    Status is one of ``SUCCESS``, ``FAILURE``, ``DENIED``.
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
from ..models.role import Role

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

#: Actor role recorded on audit events when none is configured (system internal operations).
DEFAULT_ACTOR_ROLE = Role.OPERATOR

# Audit status vocabulary (spec section 1.4).
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILURE = "FAILURE"
STATUS_DENIED = "DENIED"
AUDIT_STATUSES = frozenset({STATUS_SUCCESS, STATUS_FAILURE, STATUS_DENIED})

# Audit event types (spec section 1.4; values of Task 1.3's EventType enum).
EVENT_KEY_ACCESS = "KEY_ACCESS"
EVENT_KEY_ROTATE = "KEY_ROTATE"

# Resource operations (spec section 1.4).
RESOURCE_OP_GET = "GET"
RESOURCE_OP_PUT = "PUT"

# Operations accepted by ``logAccess``.
OP_AUTHENTICATE = "AUTHENTICATE"
OP_GET_SECRET = "GET_SECRET"
OP_ROTATE_KEY = "ROTATE_KEY"
OP_ROTATE_KEY_CHECK = "ROTATE_KEY_CHECK"  # scheduled rotation, key not yet due

#: ``logAccess`` operation -> (spec event_type, spec resource operation).
AUDIT_OPERATION_MAP: Dict[str, Tuple[str, str]] = {
    OP_AUTHENTICATE: (EVENT_KEY_ACCESS, RESOURCE_OP_GET),
    OP_GET_SECRET: (EVENT_KEY_ACCESS, RESOURCE_OP_GET),
    OP_ROTATE_KEY: (EVENT_KEY_ROTATE, RESOURCE_OP_PUT),
    OP_ROTATE_KEY_CHECK: (EVENT_KEY_ROTATE, RESOURCE_OP_GET),
}


class KeyVaultError(Exception):
    """Base error for Key Vault access through the wrapper."""


class KeyVaultAuthenticationError(KeyVaultError):
    """Managed Identity authentication failed."""


class AuditSink(Protocol):
    """What ``logAccess`` delegates to. AuditLogCollector (Task 1.3) implements it.

    Mirrors the planned Task 1.3 signature
    ``recordEvent(event_type, actor_role, resource_id, operation, status,
    error_code)``. ``event_type`` is passed as its string value, so Task 1.3's
    ``EventType`` should be a ``str``-valued enum (``class EventType(str, Enum)``).
    The connector always calls it with keyword arguments.
    """

    async def recordEvent(
        self,
        event_type: str,
        actor_role: str,
        resource_id: str,
        operation: str,
        status: str,
        error_code: Optional[str],
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
        actor_role: Role = DEFAULT_ACTOR_ROLE,
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
        if not isinstance(actor_role, Role):
            raise ValueError(
                f"actor_role must be a Role enum member, got {type(actor_role).__name__}"
            )
        self._validate_name(kek_secret_name)

        self.vault_url = resolved_url
        self.client_id = client_id or os.environ.get(ENV_CLIENT_ID) or None
        self.kek_secret_name = kek_secret_name
        self.cache_ttl_seconds = cache_ttl_seconds
        self.rotation_interval_days = rotation_interval_days
        self._audit = audit_collector
        self.actor_role = actor_role
        self._credential_factory = credential_factory or _default_credential_factory
        self._client_factory = client_factory or _default_client_factory
        self._clock = clock
        self._utcnow = utcnow

        self._credential: Any = None
        self._client: Any = None
        self._auth_lock = asyncio.Lock()
        self._cache: Dict[Tuple[str, Optional[str]], _CacheEntry] = {}
        # Bumped on every invalidation; see "Caching strategy" in the module doc.
        self._generations: Dict[str, int] = {}
        self._global_generation = 0

    # ------------------------------------------------------------------ auth

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None

    async def authenticate(self) -> None:
        """Establish the Managed Identity session and the Key Vault client.

        Requests a token for the Key Vault scope up front so that a missing or
        misconfigured identity fails here, not on the first decryption.

        The session is kept only after its SUCCESS audit record was accepted.
        If the audit collector fails, the SDK objects are closed, the connector
        stays unauthenticated and the collector's error propagates.
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
                await self._close_quietly(credential)
                await self.logAccess(
                    OP_AUTHENTICATE,
                    STATUS_FAILURE,
                    resource_id=self.vault_url,
                    actor_role=self.actor_role,
                    error_code=type(exc).__name__,
                )
                raise KeyVaultAuthenticationError(
                    f"Managed Identity authentication to {self.vault_url} failed: "
                    f"{type(exc).__name__}"
                ) from exc
            try:
                await self.logAccess(
                    OP_AUTHENTICATE,
                    STATUS_SUCCESS,
                    resource_id=self.vault_url,
                    actor_role=self.actor_role,
                )
            except BaseException:
                await self._close_quietly(client)
                await self._close_quietly(credential)
                raise
            self._credential = credential
            self._client = client

    @staticmethod
    async def _close_quietly(obj: Any) -> None:
        """Best-effort close of an SDK object during error cleanup."""
        if obj is None or not hasattr(obj, "close"):
            return
        try:
            await obj.close()
        except Exception:  # pragma: no cover - best effort cleanup
            logger.warning("failed to close %s during error cleanup", type(obj).__name__)

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

        generation = self._generation_of(secret_name)
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

        # Audit first: a value whose access could not be audited is neither
        # returned nor cached (a failing collector raises here).
        await self.logAccess(
            OP_GET_SECRET,
            STATUS_SUCCESS,
            resource_id=self._resource(secret_name, version.version or key_version),
        )

        # Skip the cache write if the secret was invalidated (e.g. by an
        # emergency rotation) while this fetch was in flight.
        if self._generation_of(secret_name) == generation:
            expires_at = self._clock() + self.cache_ttl_seconds
            entry = _CacheEntry(value=value, key_version=version, expires_at=expires_at)
            self._cache[cache_key] = entry
            if version.version:
                self._cache[(secret_name, version.version)] = entry
        return value, version

    def invalidate_cache(self, secret_name: Optional[str] = None) -> None:
        """Drop cached entries for one secret, or all of them.

        Also bumps the generation, so fetches already in flight are not
        written back to the cache.
        """
        if secret_name is None:
            self._global_generation += 1
            self._cache.clear()
            return
        self._bump_generation(secret_name)
        for key in [k for k in self._cache if k[0] == secret_name]:
            del self._cache[key]

    def _generation_of(self, secret_name: str) -> Tuple[int, int]:
        return self._global_generation, self._generations.get(secret_name, 0)

    def _bump_generation(self, secret_name: str) -> None:
        self._generations[secret_name] = self._generations.get(secret_name, 0) + 1

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
            # The spec has no "skipped" status: the check is recorded as a
            # successful KEY_ROTATE with operation GET (nothing was written).
            age = current.age(self._utcnow())
            logger.info(
                "scheduled rotation of %s skipped: version %s is %s days old (interval %s)",
                name,
                current.version,
                age.days if age is not None else "unknown",
                self.rotation_interval_days,
            )
            await self.logAccess(
                OP_ROTATE_KEY_CHECK,
                STATUS_SUCCESS,
                resource_id=self._resource(name, current.version),
            )
            result = current.to_dict()
            result.update(previous_version=None, rotated=False, emergency=False)
            return result

        if force_emergency:
            self.invalidate_cache(name)
        else:
            self._bump_generation(name)
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
        resource_id: str,
        actor_role: Role,
        error_code: Optional[str] = None,
    ) -> None:
        """Record a Key Vault access in the central audit log.

        ``operation`` is one of ``AUTHENTICATE``, ``GET_SECRET``, ``ROTATE_KEY``
        or ``ROTATE_KEY_CHECK`` and is mapped to the spec's event type and
        resource operation (see "Audit vocabulary" in the module doc).
        ``status`` is ``SUCCESS``, ``FAILURE`` or ``DENIED``; anything else is
        rejected with ``ValueError``.
        ``actor_role`` is a Role enum value indicating the privilege level of the actor.
        ``resource_id`` is the Key Vault resource identifier being accessed.

        Delegates to the AuditLogCollector when one is attached (Task 1.3);
        until then it writes a structured line to the standard logger. Key
        material is never passed here. Errors from the collector propagate:
        an access that cannot be audited must not be silently accepted.
        """
        if not isinstance(actor_role, Role):
            raise ValueError(
                f"actor_role must be a Role enum member, got {type(actor_role).__name__}"
            )
        mapped = AUDIT_OPERATION_MAP.get(operation)
        if mapped is None:
            raise ValueError(
                f"unknown audit operation {operation!r}; expected one of "
                f"{sorted(AUDIT_OPERATION_MAP)}"
            )
        if status not in AUDIT_STATUSES:
            raise ValueError(
                f"unknown audit status {status!r}; expected one of {sorted(AUDIT_STATUSES)}"
            )
        event_type, resource_operation = mapped
        if self._audit is not None:
            await self._audit.recordEvent(
                event_type=event_type,
                actor_role=actor_role.value,
                resource_id=resource_id,
                operation=resource_operation,
                status=status,
                error_code=error_code,
            )
            return
        logger.info(
            "audit event_type=%s actor_role=%s resource_id=%s operation=%s status=%s "
            "error_code=%s",
            event_type,
            actor_role.value,
            resource_id,
            resource_operation,
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
