"""AuditLogCollector: signed, append-only audit trail (Phase E, Task 1.3).

Every security event is written as one JSON line (an ``AuditLogEntry``)
carrying an HMAC-SHA256 signature over all of its other fields.

Signing
    Signatures come from ``CryptoService.signLogEntry`` (Task 1.2) and are
    checked with ``CryptoService.validateSignature``; this module does not
    implement HMAC itself. The HMAC key is the Key Vault secret
    ``audit-hmac-key`` (32 bytes), loaded through ``KeyVaultConnector`` by
    ``AuditLogCollector.fromKeyVault``. It is never hard-coded.

    ``result`` and ``context`` are normalized through JSON before signing, so
    the signed entry is exactly the entry that is stored and later read back
    (tuples become lists, ``datetime`` values become ``...Z`` strings, and so
    on). A stored entry therefore validates after a storage round-trip.

Ordering under concurrency
    One ``asyncio.Lock`` covers timestamp assignment, signing and the append,
    so the append order equals the timestamp order. Timestamps are made
    strictly increasing per collector (a clock that repeats or goes back is
    bumped by one microsecond), which gives each writer's log a total order
    without adding a sequence field to the locked schema. Use one collector
    per process (per writer); the order guarantee is per writer.

Storage
    ``AzureAppendBlobAuditStore`` writes to Azure Blob Storage **AppendBlobs**
    only. Blobs are created with ``If-None-Match: *`` because the SDK's
    ``create_append_blob`` otherwise *overwrites* an existing blob: an
    existing log is reused, never truncated. Each append is sent with
    ``appendpos_condition`` so a retried request cannot land twice or
    interleave. When the SDK's own retry of a block that already landed gets
    the resulting 412 (``HttpResponseError``, ``AppendPositionConditionNotMet``),
    the append counts as done only if the bytes stored at the expected offset
    equal the entry; a length match is not enough. The cached append position
    is dropped before every append and restored only on confirmed success, so
    a cancelled or failed append can never leave a stale offset behind.
    Container-level immutability (WORM) is an infrastructure setting outside
    this module.

Errors
    Any failure to sign or store an entry raises ``AuditError`` (consumed by
    Task 1.4's ErrorHandler). A write failure is never swallowed: the
    audited operation must not proceed as if it had been recorded.
    Invalid arguments raise ``ValueError`` (programming error).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import socket
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
)
from urllib.parse import urlsplit, urlunsplit

from ..models.audit_event import FIELD_NAMES, AuditLogEntry, parse_utc_timestamp
from ..models.enums import EventType, Role, Status
from .crypto_service import DEFAULT_HMAC_SECRET_NAME, _json_default

try:  # azure-core ships with the Azure SDK; tests may run without it.
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
except ImportError:  # pragma: no cover - exercised only without the SDK installed
    from enum import Enum as _Enum

    class MatchConditions(_Enum):  # type: ignore[no-redef]
        IfMissing = 5

    class ResourceExistsError(Exception):  # type: ignore[no-redef]
        """Fallback so the module imports without azure-core."""

    class ResourceModifiedError(Exception):  # type: ignore[no-redef]
        """Fallback so the module imports without azure-core."""


logger = logging.getLogger(__name__)

#: Required length of the ``audit-hmac-key`` secret (256 bits for HMAC-SHA256).
HMAC_KEY_LENGTH = 32

#: ``actor`` recorded for events the wrapper emits on its own behalf.
DEFAULT_ACTOR = "kakehashi-kek-wrapper"

#: Role of system-level events. Task 1.1 Decision 2 abolished a "system"
#: role; internal operations are recorded as OPERATOR (see models/role.py).
DEFAULT_SYSTEM_ROLE = Role.OPERATOR

#: Largest block accepted by Append Block on every service version.
MAX_APPEND_BLOCK_BYTES = 4 * 1024 * 1024

#: Committed-block limit of one append blob; a new segment starts after it.
MAX_APPEND_BLOCKS = 50_000

#: Entries per SIEM POST.
DEFAULT_SIEM_BATCH_SIZE = 500

#: ``source`` of every SIEM event (spec section 6.3).
SIEM_SOURCE = "kakehashi-phase-e"

# Resource operations of the events the collector emits itself.
OPERATION_VALIDATE = "VALIDATE"
OPERATION_EXPORT = "EXPORT"

_WRITER_ID_RE = re.compile(r"[^0-9A-Za-z._-]")

#: Storage error code of a failed ``appendpos_condition`` (HTTP 412).
APPEND_POSITION_ERROR_CODE = "AppendPositionConditionNotMet"

#: Longest ``event_id`` copied from a rejected entry into a validation record.
MAX_REPORTED_EVENT_ID = 256


def _is_append_position_conflict(exc: BaseException) -> bool:
    """True for the 412 that a failed ``appendpos_condition`` produces.

    azure-storage-blob 12.31 raises ``HttpResponseError`` with
    ``error_code == AppendPositionConditionNotMet`` (a ``StorageErrorCode``
    str-enum), not ``ResourceModifiedError``; both shapes and a bare 412 are
    accepted. A misclassification is harmless: the caller then verifies the
    stored bytes before treating the append as done.
    """
    if isinstance(exc, ResourceModifiedError):
        return True
    code = getattr(exc, "error_code", None)
    code = getattr(code, "value", code)
    return code == APPEND_POSITION_ERROR_CODE or getattr(exc, "status_code", None) == 412


#: ``(url, body, headers) -> HTTP status``. Injected in tests; aiohttp by default.
SiemSender = Callable[[str, bytes, Mapping[str, str]], Awaitable[int]]


class AuditError(Exception):
    """An audit entry could not be signed, stored, validated or exported.

    Raised so the caller (Task 1.4 ErrorHandler) never treats an unaudited
    operation as audited.
    """


class _SiemHTTPError(AuditError):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


def serialize_entry(record: Mapping[str, Any]) -> bytes:
    """One stored JSON line (keys sorted, UTF-8, newline-terminated)."""
    return (
        json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=_json_default,
        ).encode("utf-8")
        + b"\n"
    )


def _normalize_json_object(value: Optional[Mapping[str, Any]], name: str) -> Dict[str, Any]:
    """Return ``value`` exactly as it will read back from storage."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a dict, got {type(value).__name__}")
    try:
        return json.loads(  # type: ignore[no-any-return]
            json.dumps(dict(value), allow_nan=False, ensure_ascii=False, default=_json_default)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not JSON serializable: {exc}") from None


# ===================================================================== stores


class AuditLogStore(Protocol):
    """Append-only sink for serialized audit entries."""

    async def append(self, record: bytes, timestamp: datetime) -> None:
        """Append one serialized entry. ``timestamp`` selects the day partition."""
        ...


class InMemoryAuditLogStore:
    """Append-only in-process store for tests and local development.

    There is no update or delete API; ``entries`` returns fresh copies.
    """

    def __init__(self) -> None:
        self._records: List[bytes] = []

    async def append(self, record: bytes, timestamp: datetime) -> None:
        if not isinstance(record, (bytes, bytearray)):
            raise TypeError("record must be bytes")
        self._records.append(bytes(record))

    def entries(self) -> List[Dict[str, Any]]:
        return [json.loads(r) for r in self._records]

    def __len__(self) -> int:
        return len(self._records)


@dataclass
class _BlobState:
    day: date
    segment: int
    name: str
    client: Any
    offset: int  # current blob length = the next append position
    blocks: int  # committed block count


class AzureAppendBlobAuditStore:
    """Audit store on Azure Blob Storage AppendBlobs (never BlockBlobs).

    Layout: ``<prefix>/YYYY/MM/DD/<writer_id>-<segment>.jsonl``, one JSON line
    per append block. ``writer_id`` defaults to ``<hostname>-<pid>`` so each
    process owns its blobs and appends never contend. A segment that reaches
    ``max_blocks`` (or is sealed) is left as is and the next one is opened.

    ``container_client`` is an ``azure.storage.blob.aio.ContainerClient``
    (or anything with the same ``get_blob_client`` / ``list_blobs`` API).
    """

    def __init__(
        self,
        container_client: Any,
        *,
        prefix: str = "audit",
        writer_id: Optional[str] = None,
        max_blocks: int = MAX_APPEND_BLOCKS,
    ) -> None:
        prefix = (prefix or "").strip("/")
        if not prefix:
            raise ValueError("prefix must be a non-empty blob path")
        if max_blocks < 1:
            raise ValueError("max_blocks must be positive")
        raw_writer = writer_id or f"{socket.gethostname()}-{os.getpid()}"
        self._container = container_client
        self.prefix = prefix
        self.writer_id = _WRITER_ID_RE.sub("-", raw_writer)
        self._max_blocks = max_blocks
        self._lock = asyncio.Lock()
        self._state: Optional[_BlobState] = None
        self._day: Optional[date] = None
        self._segment = 0

    @classmethod
    def withManagedIdentity(
        cls,
        account_url: str,
        container_name: str,
        *,
        client_id: Optional[str] = None,
        **kwargs: Any,
    ) -> "AzureAppendBlobAuditStore":
        """Build the store with a Managed Identity credential (no keys, no SAS)."""
        if not isinstance(account_url, str) or not account_url.startswith("https://"):
            raise ValueError("storage account URL must use https://")
        from azure.identity.aio import ManagedIdentityCredential
        from azure.storage.blob.aio import ContainerClient

        credential = (
            ManagedIdentityCredential(client_id=client_id)
            if client_id
            else ManagedIdentityCredential()
        )
        return cls(ContainerClient(account_url, container_name, credential=credential), **kwargs)

    def blob_name(self, day: date, segment: int) -> str:
        return f"{self.prefix}/{day:%Y/%m/%d}/{self.writer_id}-{segment:04d}.jsonl"

    async def _open(self, day: date) -> _BlobState:
        segment = self._segment if self._day == day else 0
        while True:
            name = self.blob_name(day, segment)
            client = self._container.get_blob_client(name)
            try:
                # If-None-Match: * -- without it the SDK overwrites an existing blob.
                await client.create_append_blob(match_condition=MatchConditions.IfMissing)
            except (ResourceExistsError, ResourceModifiedError):
                pass  # the blob exists: append to it, never recreate it
            props = await client.get_blob_properties()
            blob_type = getattr(props.blob_type, "value", props.blob_type)
            if blob_type != "AppendBlob":
                raise AuditError(f"{name} is a {blob_type}, not an AppendBlob; refusing to write")
            blocks = props.append_blob_committed_block_count or 0
            if getattr(props, "is_append_blob_sealed", False) or blocks >= self._max_blocks:
                segment += 1
                continue
            self._day, self._segment = day, segment
            return _BlobState(day, segment, name, client, int(props.size), blocks)

    async def append(self, record: bytes, timestamp: datetime) -> None:
        if len(record) > MAX_APPEND_BLOCK_BYTES:
            raise AuditError(
                f"audit entry is {len(record)} bytes; an append block holds at most "
                f"{MAX_APPEND_BLOCK_BYTES}"
            )
        day = timestamp.astimezone(timezone.utc).date()
        async with self._lock:
            try:
                if self._state is None or self._state.day != day:
                    self._state = await self._open(day)
            except AuditError:
                raise
            except Exception as exc:
                raise AuditError(
                    f"cannot open audit blob for {day.isoformat()}: {type(exc).__name__}"
                ) from exc
            state = self._state
            # Forget the cached append position until this append is
            # confirmed. If the call fails or is cancelled (CancelledError is
            # a BaseException), even after the block landed, the next append
            # re-reads the real end of the blob instead of a stale offset.
            self._state = None
            try:
                await state.client.append_block(record, appendpos_condition=state.offset)
            except Exception as exc:
                if not _is_append_position_conflict(exc):
                    raise AuditError(
                        f"append to {state.name} failed: {type(exc).__name__}"
                    ) from exc
                # 412: the blob no longer ends at our offset. The expected
                # cause is an SDK retry of a block that had already landed.
                state.offset, state.blocks = await self._confirm_landed(state, record, exc)
            else:
                state.offset += len(record)
                state.blocks += 1
            if state.blocks >= self._max_blocks:
                self._segment = state.segment + 1
            else:
                self._state = state

    @staticmethod
    async def _confirm_landed(
        state: _BlobState, record: bytes, cause: BaseException
    ) -> Tuple[int, int]:
        """After a 412, accept the append only if ``record`` is at ``state.offset``.

        Compares the stored bytes, not the blob length: audit entries of the
        same shape have the same length, so a length match proves nothing.
        Returns the blob's real (size, committed block count). Raises
        ``AuditError`` when the bytes differ or cannot be read.
        """
        end = state.offset + len(record)
        try:
            props = await state.client.get_blob_properties()
            landed = b""
            if int(props.size) >= end:
                downloader = await state.client.download_blob(
                    offset=state.offset, length=len(record)
                )
                landed = await downloader.readall()
        except Exception as inner:
            raise AuditError(
                f"append to {state.name} hit an append-position conflict and its "
                f"state is unknown: {type(inner).__name__}"
            ) from cause
        if landed != record:
            raise AuditError(
                f"append position of {state.name} moved and this entry is not at the "
                "expected offset (another writer?); entry not recorded"
            ) from cause
        return int(props.size), props.append_blob_committed_block_count or 0

    async def read_day(self, day: date, writer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Entries stored for ``day`` (UTC), blob by blob in append order.

        With ``writer_id`` only that writer's segments are read: the result is
        one writer's log and can be checked with
        ``AuditLogCollector.validateLogSequence``. Without it every writer's
        blobs are concatenated; order holds only per writer, so that combined
        list must not be fed to ``validateLogSequence`` (it would report
        ``OUT_OF_ORDER`` across writers, a false positive).
        """
        prefix = f"{self.prefix}/{day:%Y/%m/%d}/"
        names = sorted([b.name async for b in self._container.list_blobs(name_starts_with=prefix)])
        if writer_id is not None:
            wanted = _WRITER_ID_RE.sub("-", writer_id)
            names = [n for n in names if n[len(prefix) :].rsplit("-", 1)[0] == wanted]
        entries: List[Dict[str, Any]] = []
        for name in names:
            downloader = await self._container.get_blob_client(name).download_blob()
            data = await downloader.readall()
            entries.extend(json.loads(line) for line in data.splitlines() if line.strip())
        return entries

    async def close(self) -> None:
        if hasattr(self._container, "close"):
            await self._container.close()


# ================================================================== collector


async def _aiohttp_post(url: str, body: bytes, headers: Mapping[str, str]) -> int:
    """Default SIEM transport: one HTTPS POST, returns the HTTP status."""
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=body, headers=dict(headers)) as response:
            return response.status  # type: ignore[no-any-return]


class AuditLogCollector:
    """Records HMAC-signed audit events in append-only storage."""

    def __init__(
        self,
        crypto_service: Any,
        store: AuditLogStore,
        *,
        actor: str = DEFAULT_ACTOR,
        system_role: Role = DEFAULT_SYSTEM_ROLE,
        siem_sender: Optional[SiemSender] = None,
        siem_headers: Optional[Mapping[str, str]] = None,
        siem_batch_size: int = DEFAULT_SIEM_BATCH_SIZE,
        utc_now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        """
        Args:
            crypto_service: a ``CryptoService`` holding the audit HMAC key
                (use ``fromKeyVault`` to load it from Key Vault).
            store: append-only sink, e.g. ``AzureAppendBlobAuditStore``.
            actor: default ``actor`` of events (the service identity).
            system_role: role of events the collector emits itself.
            siem_sender: SIEM transport (default: aiohttp HTTPS POST).
            siem_headers: extra headers for SIEM requests (e.g. auth).
            siem_batch_size: entries per SIEM POST.
            utc_now: clock (tests inject a fake); must return aware datetimes.
        """
        if not isinstance(actor, str) or not actor:
            raise ValueError("actor must be a non-empty string")
        if not isinstance(system_role, Role):
            raise ValueError(
                f"system_role must be a Role enum member, got {type(system_role).__name__}"
            )
        if siem_batch_size < 1:
            raise ValueError("siem_batch_size must be positive")
        try:
            # fail at construction, not on the first security event
            crypto_service.signLogEntry({"probe": "audit-hmac-key"})
        except RuntimeError as exc:
            raise AuditError("audit collector requires a CryptoService with an HMAC key") from exc
        self._crypto = crypto_service
        self._store = store
        self.actor = actor
        self.system_role = system_role
        self._siem_sender: SiemSender = siem_sender or _aiohttp_post
        self._siem_headers = dict(siem_headers or {})
        self._siem_batch_size = siem_batch_size
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self._lock = asyncio.Lock()
        self._last_timestamp: Optional[datetime] = None

    @classmethod
    async def fromKeyVault(
        cls,
        connector: Any,
        store: AuditLogStore,
        *,
        hmac_secret_name: str = DEFAULT_HMAC_SECRET_NAME,
        hmac_key_version: Optional[str] = None,
        **kwargs: Any,
    ) -> "AuditLogCollector":
        """Build a collector whose HMAC key is ``audit-hmac-key`` from Key Vault.

        ``connector`` is a ``KeyVaultConnector`` (Task 1.1); only its
        ``getSecret(name, key_version)`` coroutine is used. The key must be
        exactly 32 bytes.
        """
        from .crypto_service import CryptoService

        try:
            key = await connector.getSecret(hmac_secret_name, hmac_key_version)
        except Exception as exc:
            raise AuditError(
                f"cannot load audit HMAC key {hmac_secret_name!r}: {type(exc).__name__}"
            ) from exc
        if not isinstance(key, (bytes, bytearray)) or len(key) != HMAC_KEY_LENGTH:
            size = len(key) if isinstance(key, (bytes, bytearray)) else type(key).__name__
            raise AuditError(
                f"audit HMAC key {hmac_secret_name!r} must be {HMAC_KEY_LENGTH} bytes, got {size}"
            )
        return cls(CryptoService(bytes(key)), store, **kwargs)

    # ------------------------------------------------------------- recording

    async def recordEvent(
        self,
        event_type: Union[EventType, str],
        actor_role: Union[Role, str],
        resource_id: str,
        operation: str,
        status: Union[Status, str],
        error_code: Optional[str] = None,
        *,
        actor: Optional[str] = None,
        result: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Record a security event with an HMAC signature. Returns its event_id.

        ``event_type``, ``actor_role`` and ``status`` are enum members. Their
        exact string values are also accepted (KeyVaultConnector passes
        ``Role.value``); any other value raises ``ValueError``.
        ``error_code`` is stored as ``result["error_code"]``.

        Raises ``AuditError`` if the entry cannot be signed or stored.
        """
        if error_code is not None and (not isinstance(error_code, str) or not error_code):
            raise ValueError("error_code must be a non-empty string or None")
        result_obj = _normalize_json_object(result, "result")
        if "error_code" in result_obj:
            raise ValueError("pass error_code as the argument, not inside result")
        result_obj["error_code"] = error_code
        context_obj = _normalize_json_object(context, "context")
        actor = self.actor if actor is None else actor

        # Validate everything that does not depend on the clock before
        # taking the lock (AuditLogEntry raises ValueError on bad values).
        AuditLogEntry(
            event_id="evt-validation",
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            actor=actor,
            actor_role=actor_role,  # type: ignore[arg-type]
            resource_id=resource_id,
            operation=operation,
            status=status,
        )

        async with self._lock:
            timestamp = self._next_timestamp()
            entry = AuditLogEntry(
                event_id=f"evt-{timestamp:%Y%m%d}-{uuid.uuid4().hex}",
                timestamp=timestamp,
                event_type=event_type,
                actor=actor,
                actor_role=actor_role,  # type: ignore[arg-type]
                resource_id=resource_id,
                operation=operation,
                status=status,
                result=result_obj,
                context=context_obj,
            )
            record = entry.to_dict()
            try:
                record["signature"] = self._crypto.signLogEntry(record)
                line = serialize_entry(record)
            except Exception as exc:
                raise AuditError(f"cannot sign audit entry: {type(exc).__name__}") from exc
            try:
                await self._store.append(line, timestamp)
            except AuditError:
                raise
            except Exception as exc:
                raise AuditError(
                    f"cannot write audit entry {entry.event_id}: {type(exc).__name__}"
                ) from exc
        return entry.event_id

    def _next_timestamp(self) -> datetime:
        now = self._utc_now()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise AuditError("audit clock returned a naive or non-datetime value")
        now = now.astimezone(timezone.utc)
        if self._last_timestamp is not None and now <= self._last_timestamp:
            now = self._last_timestamp + timedelta(microseconds=1)
        self._last_timestamp = now
        return now

    async def _record_system_event(
        self,
        event_type: EventType,
        resource_id: str,
        operation: str,
        status: Status,
        error_code: Optional[str] = None,
        result: Optional[Mapping[str, Any]] = None,
    ) -> str:
        return await self.recordEvent(
            event_type,
            self.system_role,
            resource_id,
            operation,
            status,
            error_code,
            result=result,
        )

    # ------------------------------------------------------------ validation

    def _check_entry(self, log_entry: Any) -> Optional[str]:
        """Reason code if ``log_entry`` is not a valid signed entry, else None."""
        if not isinstance(log_entry, Mapping):
            return "NOT_A_MAPPING"
        try:
            AuditLogEntry.from_dict(log_entry)
        except (TypeError, ValueError):
            return "SCHEMA_INVALID"
        try:
            valid = self._crypto.validateSignature(dict(log_entry), log_entry["signature"])
        except RuntimeError as exc:
            raise AuditError("cannot validate audit entries without an HMAC key") from exc
        return None if valid else "SIGNATURE_MISMATCH"

    async def _record_validation_failure(self, log_entry: Any, reason: str) -> None:
        event_id = log_entry.get("event_id") if isinstance(log_entry, Mapping) else None
        resource = event_id if isinstance(event_id, str) and event_id else "unidentified-entry"
        if len(resource) > MAX_REPORTED_EVENT_ID:
            # the entry is untrusted input; an oversized id must not make the
            # validation record itself unwritable
            resource = resource[:MAX_REPORTED_EVENT_ID] + "...(truncated)"
        await self._record_system_event(
            EventType.AUDIT_VALIDATE, resource, OPERATION_VALIDATE, Status.FAILURE, reason
        )

    async def validateLog(self, log_entry: dict[str, Any]) -> bool:
        """Validate one stored entry: exact schema, canonical values, HMAC signature.

        Returns False for a missing/extra field, an out-of-vocabulary value, a
        non-canonical timestamp, or a signature that does not match the
        content. Each failure is itself recorded as an ``AUDIT_VALIDATE`` /
        ``FAILURE`` event (tampering is a security event). Raises
        ``AuditError`` if that record cannot be written.
        """
        reason = self._check_entry(log_entry)
        if reason is None:
            return True
        logger.warning("audit entry failed validation: %s", reason)
        await self._record_validation_failure(log_entry, reason)
        return False

    async def validateLogSequence(self, log_entries: Sequence[Mapping[str, Any]]) -> bool:
        """Continuity check of one writer's log, in stored order.

        Every entry must pass ``validateLog``, event_ids must be unique and
        timestamps strictly increasing (the collector's per-writer order).
        A break is recorded as ``AUDIT_VALIDATE`` / ``FAILURE``.

        HMAC signatures cannot reveal a whole entry that was removed (the
        locked schema has no hash chain); append-only storage and WORM
        retention are what prevent deletion.
        """
        seen: set[str] = set()
        previous: Optional[datetime] = None
        for entry in log_entries:
            if not await self.validateLog(entry):  # type: ignore[arg-type]
                return False
            timestamp = parse_utc_timestamp(entry["timestamp"])
            reason = None
            if entry["event_id"] in seen:
                reason = "DUPLICATE_EVENT_ID"
            elif previous is not None and timestamp <= previous:
                reason = "OUT_OF_ORDER"
            if reason is not None:
                await self._record_validation_failure(entry, reason)
                return False
            seen.add(entry["event_id"])
            previous = timestamp
        return True

    # ---------------------------------------------------------------- export

    @staticmethod
    def _redacted_endpoint(siem_endpoint: str) -> str:
        """``https://host/path`` with credentials, query and fragment removed."""
        if not isinstance(siem_endpoint, str):
            raise ValueError("siem_endpoint must be a string")
        parts = urlsplit(siem_endpoint)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("siem_endpoint must be an https:// URL")
        netloc = parts.hostname + (f":{parts.port}" if parts.port else "")
        return urlunsplit(("https", netloc, parts.path, "", ""))

    @staticmethod
    def _siem_event(entry: Mapping[str, Any], reason: Optional[str]) -> Dict[str, Any]:
        status = entry.get("status")
        if reason is not None or entry.get("event_type") == EventType.SECURITY.value:
            severity = "HIGH"
        elif status in (Status.FAILURE.value, Status.DENIED.value):
            severity = "MEDIUM"
        else:
            severity = "LOW"
        message = (
            f"{entry.get('event_type')} {entry.get('operation')} {status}"
            f" on {entry.get('resource_id')}"
        )
        return {
            "source": SIEM_SOURCE,
            "timestamp": entry.get("timestamp"),
            "severity": severity,
            "message": message,
            "signature_valid": reason is None,
            "audit_log": dict(entry),  # unchanged content, signature included
        }

    async def exportToSIEM(
        self, siem_endpoint: str, log_entries: List[dict[str, Any]]
    ) -> dict[str, Any]:
        """Export a batch of audit entries to an external SIEM over HTTPS.

        Entries are sent unchanged (signature included), each wrapped in the
        spec section 6.3 event envelope, ``siem_batch_size`` per POST. Every
        entry's signature is checked first; an entry that fails is still sent
        (the SIEM must see tampering) with ``signature_valid: false`` and
        severity HIGH, and is counted in ``invalid_count``.

        Returns ``{"status": "success", "exported_count": N, "batch_id": ...,
        "invalid_count": K}``. The export itself is recorded as an
        ``AUDIT_EXPORT`` event. Raises ``AuditError`` if any POST fails
        (non-2xx or transport error); the FAILURE record carries the number
        of entries delivered before the failure.
        """
        resource = self._redacted_endpoint(siem_endpoint)
        if isinstance(log_entries, (str, bytes)) or not isinstance(log_entries, Sequence):
            raise ValueError("log_entries must be a list of audit entries")
        entries = list(log_entries)
        events = []
        invalid = 0
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("every log entry must be a dict")
            reason = self._check_entry(entry)
            invalid += reason is not None
            events.append(self._siem_event(entry, reason))

        batch_id = f"batch-{self._utc_now():%Y%m%d}-{uuid.uuid4().hex}"
        size = self._siem_batch_size
        chunks = [events[i : i + size] for i in range(0, len(events), size)]
        headers = {
            **self._siem_headers,
            "Content-Type": "application/json",
            "X-Audit-Batch-Id": batch_id,
        }
        exported = 0
        try:
            for index, chunk in enumerate(chunks):
                body = json.dumps(
                    {
                        "source": SIEM_SOURCE,
                        "batch_id": batch_id,
                        "chunk_index": index,
                        "chunk_count": len(chunks),
                        "events": chunk,
                    },
                    ensure_ascii=False,
                    default=_json_default,
                ).encode("utf-8")
                status = await self._siem_sender(siem_endpoint, body, headers)
                if not 200 <= status < 300:
                    raise _SiemHTTPError(
                        f"SIEM rejected batch {batch_id} chunk {index}: HTTP {status}", status
                    )
                exported += len(chunk)
        except Exception as exc:
            code = f"HTTP_{exc.status}" if isinstance(exc, _SiemHTTPError) else type(exc).__name__
            # logged first so the cause survives even if the record below fails
            logger.error(
                "SIEM export of batch %s failed: %s (%d of %d entries delivered)",
                batch_id,
                code,
                exported,
                len(entries),
            )
            await self._record_system_event(
                EventType.AUDIT_EXPORT,
                resource,
                OPERATION_EXPORT,
                Status.FAILURE,
                code,
                result={
                    "batch_id": batch_id,
                    "exported_count": exported,
                    "requested_count": len(entries),
                },
            )
            if isinstance(exc, AuditError):
                raise
            raise AuditError(f"SIEM export of batch {batch_id} failed: {code}") from exc

        await self._record_system_event(
            EventType.AUDIT_EXPORT,
            resource,
            OPERATION_EXPORT,
            Status.SUCCESS,
            result={"batch_id": batch_id, "exported_count": exported, "invalid_count": invalid},
        )
        return {
            "status": "success",
            "exported_count": exported,
            "batch_id": batch_id,
            "invalid_count": invalid,
        }


__all__ = [
    "AuditError",
    "AuditLogCollector",
    "AuditLogStore",
    "AzureAppendBlobAuditStore",
    "DEFAULT_ACTOR",
    "DEFAULT_SYSTEM_ROLE",
    "FIELD_NAMES",
    "HMAC_KEY_LENGTH",
    "InMemoryAuditLogStore",
    "serialize_entry",
]
