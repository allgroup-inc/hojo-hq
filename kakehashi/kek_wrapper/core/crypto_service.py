"""CryptoService: AES-256-GCM encryption and HMAC-SHA256 audit signatures.

Phase E, Task 1.2.

Encryption
    AES-256-GCM via ``cryptography`` (>= 41.0.0). Every call to ``encrypt``
    draws a fresh 16-byte IV from ``secrets.token_bytes`` (Task 1.2 brief); an
    IV is never reused or derived from input. The 16-byte GCM tag is appended
    to the ciphertext (``EncryptedData.ciphertext = ciphertext || tag``) and is
    checked by ``decrypt``. A failed check raises ``ValueError`` (spec section
    3.1): decryption never returns ``None`` or partial plaintext.

    ``encrypt`` requires ``key_version=`` (keyword-only) so every record says
    which KEK version encrypted it. Optional ``associated_data=`` is
    authenticated but not stored; ``decrypt`` must be given the same bytes.

    IV length: 16 bytes, kept per the 2026-10-29 Round 3 decision (Decision 3)
    and to be confirmed before production data is written. NIST SP 800-38D
    recommends 96-bit IVs; a 16-byte IV is valid GCM (the counter block is
    derived through GHASH) and is covered by 128-bit-IV known-answer tests.

    Keys are passed per call (fetched by the caller through
    ``KeyVaultConnector.getSecret``) and must be exactly 32 bytes. This module
    holds no key material of its own.

Audit signatures
    ``validateSignature`` checks an HMAC-SHA256 hex digest over the canonical
    JSON form of an audit log entry (see ``canonicalize_log_entry``). The HMAC
    key is given to the constructor (or loaded with ``fromKeyVault`` from the
    ``audit-hmac-key`` secret); it is never hard-coded. ``signLogEntry`` is the
    matching signer for the AuditLogCollector (Task 1.3).
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Optional

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac as crypto_hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..models.crypto_models import GCM_IV_LENGTH, GCM_TAG_LENGTH, EncryptedData

logger = logging.getLogger(__name__)

#: AES-256 key length in bytes.
AES_256_KEY_LENGTH = 32

#: Minimum HMAC-SHA256 key length in bytes (RFC 2104: at least the hash size).
MIN_HMAC_KEY_LENGTH = 32

#: Length of an HMAC-SHA256 hex digest.
HMAC_SHA256_HEX_LENGTH = 64

#: Key Vault secret holding the audit HMAC key (Task 1.3 brief).
DEFAULT_HMAC_SECRET_NAME = "audit-hmac-key"

#: Field of a log entry that carries its own signature; excluded when signing.
SIGNATURE_FIELD = "signature"


# ------------------------------------------------------------ sync utilities


def _require_bytes(value: Any, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{name} must be bytes, got {type(value).__name__}")
    return bytes(value)


def _require_aes_key(key: Any) -> bytes:
    key = _require_bytes(key, "key")
    if len(key) != AES_256_KEY_LENGTH:
        # never include the key itself in the message
        raise ValueError(
            f"AES-256-GCM requires a {AES_256_KEY_LENGTH}-byte key, got {len(key)} bytes"
        )
    return key


def _optional_associated_data(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    return _require_bytes(value, "associated_data")


def _aes_gcm_seal(
    key: bytes, iv: bytes, plaintext: bytes, associated_data: Optional[bytes] = None
) -> bytes:
    """AES-256-GCM encrypt with an explicit IV. Returns ``ciphertext || tag``.

    Private: only ``CryptoService.encrypt`` (which draws a fresh random IV)
    and the NIST known-answer tests may call this. Do not import it elsewhere:
    GCM loses confidentiality and integrity when an IV repeats under the same
    key, and an explicit-IV entry point invites exactly that.
    """
    key = _require_aes_key(key)
    iv = _require_bytes(iv, "iv")
    if not iv:
        raise ValueError("iv must not be empty")
    return AESGCM(key).encrypt(iv, _require_bytes(plaintext, "plaintext"), associated_data)


def _aes_gcm_open(
    key: bytes, iv: bytes, sealed: bytes, associated_data: Optional[bytes] = None
) -> bytes:
    """AES-256-GCM decrypt ``ciphertext || tag``. Raises ``ValueError`` on a bad tag."""
    key = _require_aes_key(key)
    iv = _require_bytes(iv, "iv")
    sealed = _require_bytes(sealed, "ciphertext")
    if not iv:
        raise ValueError("iv must not be empty")
    if len(sealed) < GCM_TAG_LENGTH:
        raise ValueError("ciphertext is shorter than the GCM authentication tag")
    try:
        return AESGCM(key).decrypt(iv, sealed, associated_data)
    except InvalidTag:
        raise ValueError(
            "AES-GCM authentication failed: wrong key, wrong IV or tampered ciphertext"
        ) from None


def _format_utc(value: datetime) -> str:
    """Aware datetime -> ISO 8601 in UTC with a ``Z`` suffix (Task 1.3 storage form)."""
    if value.tzinfo is None or value.utcoffset() is None:
        # a naive datetime has no defined instant; signing it would make the
        # signature depend on the signer's local time zone
        raise TypeError("naive datetime cannot be signed; use a timezone-aware UTC datetime")
    # astimezone(utc).isoformat() always ends in "+00:00"
    return value.astimezone(timezone.utc).isoformat().removesuffix("+00:00") + "Z"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _format_utc(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def canonicalize_log_entry(log_entry: Mapping[str, Any]) -> bytes:
    """Deterministic byte form of an audit log entry, as signed by HMAC-SHA256.

    * the ``signature`` field is excluded (an entry may carry its own signature)
    * keys sorted, compact separators, UTF-8, no ASCII escaping
    * aware ``datetime`` values as ISO 8601 UTC with a ``Z`` suffix
      (e.g. ``2026-11-06T09:00:00Z``); naive ``datetime`` rejected (``TypeError``)
    * ``Enum`` values (e.g. ``Role``) as ``.value``
    * NaN / Infinity rejected

    Sign exactly what you store: the signature covers this canonical form, so
    a stored entry validates only if every value serializes to the same JSON
    as at signing time. A ``datetime`` object signs the same as its stored
    ``...Z`` string, but any other textual form (``+00:00``, ``+09:00``, a
    different number of fractional digits) is a different value and fails.

    Raises ``TypeError`` / ``ValueError`` for entries that cannot be serialized.
    """
    if not isinstance(log_entry, Mapping):
        raise TypeError(f"log_entry must be a mapping, got {type(log_entry).__name__}")
    body = {k: v for k, v in log_entry.items() if k != SIGNATURE_FIELD}
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")


# ------------------------------------------------------------------- service


class CryptoService:
    """AES-256-GCM encryption plus HMAC-SHA256 audit-log signature checks."""

    def __init__(
        self,
        hmac_key: Optional[bytes] = None,
        *,
        utc_now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        """
        Args:
            hmac_key: audit HMAC key (>= 32 bytes), normally the
                ``audit-hmac-key`` secret from Key Vault. Required only for
                ``validateSignature`` / ``signLogEntry``.
            utc_now: clock for ``EncryptedData.timestamp`` (tests inject a fake).
        """
        if hmac_key is not None:
            hmac_key = _require_bytes(hmac_key, "hmac_key")
            if len(hmac_key) < MIN_HMAC_KEY_LENGTH:
                raise ValueError(
                    f"HMAC-SHA256 key must be at least {MIN_HMAC_KEY_LENGTH} bytes,"
                    f" got {len(hmac_key)} bytes"
                )
        self._hmac_key = hmac_key
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))

    @classmethod
    async def fromKeyVault(
        cls,
        connector: Any,
        hmac_secret_name: str = DEFAULT_HMAC_SECRET_NAME,
        hmac_key_version: Optional[str] = None,
        **kwargs: Any,
    ) -> "CryptoService":
        """Build a CryptoService whose HMAC key comes from Key Vault.

        ``connector`` is a ``KeyVaultConnector`` (Task 1.1); only its
        ``getSecret(name, key_version)`` coroutine is used.
        """
        hmac_key = await connector.getSecret(hmac_secret_name, hmac_key_version)
        return cls(hmac_key, **kwargs)

    # ---------------------------------------------------------- encryption

    async def encrypt(
        self,
        plaintext: bytes,
        key: bytes,
        *,
        key_version: str,
        associated_data: bytes | None = None,
    ) -> EncryptedData:
        """Encrypt plaintext with AES-256-GCM using a fresh random IV.

        Args:
            key_version: required, keyword-only. The KEK version ``key`` belongs
                to (as returned by ``KeyVaultConnector.getSecretWithVersion``).
                It is recorded on the result so the record can be decrypted
                with the same version after a rotation (spec section 1.6).
                Must be a non-empty string; ``None`` and ``""`` raise ``ValueError``.
            associated_data: optional, keyword-only. Bytes authenticated by
                the GCM tag but not encrypted and **not stored** in
                ``EncryptedData``. The caller must keep it (or be able to
                rebuild it, e.g. from the record id and ``key_version``) and
                pass the identical bytes to ``decrypt``. Use it to bind the
                ciphertext to its context so a record cannot be swapped.
        """
        if not isinstance(key_version, str) or not key_version:
            # a missing, empty or non-string version would be recorded and
            # later fail to select the KEK that encrypted the record
            raise ValueError("key_version must be a non-empty string")
        key = _require_aes_key(key)
        plaintext = _require_bytes(plaintext, "plaintext")
        aad = _optional_associated_data(associated_data)
        iv = secrets.token_bytes(GCM_IV_LENGTH)
        sealed = _aes_gcm_seal(key, iv, plaintext, aad)
        return EncryptedData(
            ciphertext=sealed,
            iv=iv,
            key_version=key_version,
            timestamp=self._utc_now(),
        )

    async def decrypt(
        self,
        encrypted_data: EncryptedData,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """Decrypt and validate the GCM tag. Raises ``ValueError`` if it is invalid.

        ``associated_data`` must be the exact bytes given to ``encrypt``
        (``None`` if none were given); any difference fails the tag check.
        """
        if not isinstance(encrypted_data, EncryptedData):
            raise TypeError(
                f"encrypted_data must be EncryptedData, got {type(encrypted_data).__name__}"
            )
        iv = _require_bytes(encrypted_data.iv, "iv")
        if len(iv) != GCM_IV_LENGTH:
            raise ValueError(f"iv must be {GCM_IV_LENGTH} bytes, got {len(iv)} bytes")
        aad = _optional_associated_data(associated_data)
        return _aes_gcm_open(key, iv, encrypted_data.ciphertext, aad)

    # ---------------------------------------------------------- signatures

    def _require_hmac_key(self) -> bytes:
        if self._hmac_key is None:
            # a missing key is a configuration error, not a failed signature:
            # reporting it as "invalid" would hide the misconfiguration
            raise RuntimeError(
                "CryptoService has no HMAC key; pass hmac_key or use fromKeyVault()"
            )
        return self._hmac_key

    def signLogEntry(self, log_entry: Mapping[str, Any]) -> str:
        """HMAC-SHA256 hex digest (64 lowercase chars) of ``log_entry``.

        The ``signature`` field, if present, is excluded (see
        ``canonicalize_log_entry``).
        """
        mac = crypto_hmac.HMAC(self._require_hmac_key(), hashes.SHA256())
        mac.update(canonicalize_log_entry(log_entry))
        return mac.finalize().hex()

    def validateSignature(self, log_entry: dict, signature: str) -> bool:
        """Validate the HMAC-SHA256 signature on an audit log entry.

        Returns True only when ``signature`` is the hex HMAC-SHA256 of the
        entry's canonical form. Returns False for a tampered entry, a wrong or
        malformed signature, or an entry that cannot be canonicalized. The
        comparison is constant-time. Raises ``RuntimeError`` when no HMAC key
        is configured.
        """
        key = self._require_hmac_key()
        if not isinstance(signature, str) or len(signature) != HMAC_SHA256_HEX_LENGTH:
            return False
        try:
            expected = bytes.fromhex(signature)
        except ValueError:
            return False
        try:
            message = canonicalize_log_entry(log_entry)
        except (TypeError, ValueError) as exc:
            logger.warning("audit log entry cannot be canonicalized: %s", type(exc).__name__)
            return False
        mac = crypto_hmac.HMAC(key, hashes.SHA256())
        mac.update(message)
        try:
            mac.verify(expected)
        except InvalidSignature:
            return False
        return True
