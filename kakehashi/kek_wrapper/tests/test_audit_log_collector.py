"""Tests for AuditLogCollector (Phase E, Task 1.3).

Storage, Key Vault and the SIEM are in-memory fakes; the default aiohttp SIEM
sender is exercised against a local HTTP server. The HMAC key is generated per
test with ``secrets.token_bytes`` (never hard-coded).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from kakehashi.kek_wrapper import (
    AuditError,
    AuditLogCollector,
    AuditLogEntry,
    AzureAppendBlobAuditStore,
    CryptoService,
    EventType,
    InMemoryAuditLogStore,
    KeyVaultConnector,
    Role,
    Status,
)
from kakehashi.kek_wrapper.core import audit_log_collector as alc
from kakehashi.kek_wrapper.core.audit_log_collector import (
    MatchConditions,
    ResourceExistsError,
    ResourceModifiedError,
)
from kakehashi.kek_wrapper.models.audit_event import FIELD_NAMES, parse_utc_timestamp

T0 = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)
SIEM_URL = "https://mock-siem.example.com"
SECRET_URL = "https://kakehashi-staging.vault.azure.net/secrets/kakehashi-kek/v1"
EVENT_ID_RE = re.compile(r"^evt-\d{8}-[0-9a-f]{32}$")

#: Field list of the Task 1.3 brief, in the brief's order.
BRIEF_FIELDS = (
    "event_id",
    "timestamp",
    "event_type",
    "actor",
    "actor_role",
    "resource_id",
    "operation",
    "status",
    "result",
    "context",
    "signature",
)


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------- fakes


class StepClock:
    """UTC clock advancing by ``step`` on each call."""

    def __init__(self, start: datetime = T0, step: timedelta = timedelta(milliseconds=1)):
        self.now = start
        self.step = step

    def __call__(self) -> datetime:
        value = self.now
        self.now = self.now + self.step
        return value


class YieldingStore(InMemoryAuditLogStore):
    """Yields to the event loop mid-append so concurrent writers could interleave."""

    async def append(self, record: bytes, timestamp: datetime) -> None:
        await asyncio.sleep(0)
        await super().append(record, timestamp)
        await asyncio.sleep(0)


class FailingStore:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def append(self, record: bytes, timestamp: datetime) -> None:
        raise self.exc


class RecordingSiem:
    def __init__(self, statuses: Optional[List[Any]] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.statuses = list(statuses or [])

    async def __call__(self, url: str, body: bytes, headers) -> int:
        self.calls.append({"url": url, "body": json.loads(body), "headers": dict(headers)})
        if self.statuses:
            status = self.statuses.pop(0)
            if isinstance(status, BaseException):
                raise status
            return status
        return 202


class FakeConnector:
    def __init__(self, value: Any = None, exc: Optional[BaseException] = None) -> None:
        self.value = value
        self.exc = exc
        self.calls: List[tuple] = []

    async def getSecret(self, name: str, key_version: Optional[str] = None):
        self.calls.append((name, key_version))
        if self.exc is not None:
            raise self.exc
        return self.value


@pytest.fixture
def hmac_key() -> bytes:
    return secrets.token_bytes(32)


@pytest.fixture
def crypto(hmac_key) -> CryptoService:
    return CryptoService(hmac_key)


@pytest.fixture
def store() -> InMemoryAuditLogStore:
    return InMemoryAuditLogStore()


@pytest.fixture
def siem() -> RecordingSiem:
    return RecordingSiem()


@pytest.fixture
def collector(crypto, store, siem) -> AuditLogCollector:
    return AuditLogCollector(crypto, store, siem_sender=siem, utc_now=StepClock())


def record(collector: AuditLogCollector, **overrides) -> str:
    kwargs = dict(
        event_type=EventType.KEY_VAULT_AUTH,
        actor_role=Role.OPERATOR,
        resource_id=SECRET_URL,
        operation="GET",
        status=Status.SUCCESS,
    )
    kwargs.update(overrides)
    return run(collector.recordEvent(**kwargs))


def reference_hmac(key: bytes, entry: dict) -> str:
    """Independent stdlib signer of the canonical form (pins Task 1.2's contract)."""
    body = {k: v for k, v in entry.items() if k != "signature"}
    message = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


# ------------------------------------------------------- brief: 5 named tests


def test_recordEvent_creates_valid_schema(collector, store):
    event_id = record(collector, error_code=None)

    assert isinstance(event_id, str) and event_id
    assert EVENT_ID_RE.match(event_id)
    assert event_id.startswith("evt-20261109-")

    entries = store.entries()
    assert len(entries) == 1
    entry = entries[0]
    # exactly the locked schema: no extra and no missing fields
    assert FIELD_NAMES == BRIEF_FIELDS
    assert set(entry) == set(BRIEF_FIELDS)
    parsed = AuditLogEntry.from_dict(entry)
    assert parsed.to_dict() == entry

    assert entry["event_id"] == event_id
    assert entry["timestamp"] == "2026-11-09T09:00:00Z"
    assert entry["event_type"] == "KEY_VAULT_AUTH"
    assert entry["actor"] == alc.DEFAULT_ACTOR
    assert entry["actor_role"] == "operator"  # Task 1.1 Role values are lowercase
    assert entry["resource_id"] == SECRET_URL
    assert entry["operation"] == "GET"
    assert entry["status"] == "SUCCESS"
    assert entry["result"] == {"error_code": None}
    assert entry["context"] == {}


def test_audit_entry_signed_with_hmac(collector, store, hmac_key):
    record(collector)
    entry = store.entries()[0]

    assert entry["signature"]
    assert len(entry["signature"]) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", entry["signature"])
    # the signature is HMAC-SHA256 over every other field (CryptoService contract)
    assert entry["signature"] == reference_hmac(hmac_key, entry)
    assert run(collector.validateLog(entry)) is True


def test_concurrent_audit_writes(crypto):
    store = YieldingStore()
    # a frozen clock: every writer reads the same instant
    collector = AuditLogCollector(crypto, store, utc_now=lambda: T0)

    async def main():
        return await asyncio.gather(
            *(
                collector.recordEvent(
                    EventType.CRYPTO_ENCRYPT,
                    Role.OPERATOR,
                    f"record-{i}",
                    "ENCRYPT",
                    Status.SUCCESS,
                )
                for i in range(100)
            )
        )

    event_ids = run(main())
    entries = store.entries()

    assert len(event_ids) == 100
    assert len(set(event_ids)) == 100
    assert len(entries) == 100
    assert {e["event_id"] for e in entries} == set(event_ids)
    assert all(crypto.validateSignature(e, e["signature"]) for e in entries)
    assert len({e["signature"] for e in entries}) == 100  # no signature conflicts

    # append order == timestamp order (strictly increasing despite the frozen clock)
    timestamps = [parse_utc_timestamp(e["timestamp"]) for e in entries]
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == 100
    # tasks start in submission order, so the append order is the write order
    assert [e["resource_id"] for e in entries] == [f"record-{i}" for i in range(100)]
    assert run(collector.validateLogSequence(entries)) is True


def test_export_to_siem_batch(collector, store, siem):
    for i in range(1000):
        record(collector, resource_id=f"secret-{i}")
    entries = store.entries()
    assert len(entries) == 1000

    result = run(collector.exportToSIEM(SIEM_URL, entries))

    assert result["status"] == "success"
    assert result["exported_count"] == 1000
    assert result["batch_id"].startswith("batch-")
    assert result["invalid_count"] == 0

    exported = [ev["audit_log"] for call in siem.calls for ev in call["body"]["events"]]
    assert len(exported) == 1000
    assert len(siem.calls) == 2  # 500 per POST
    for original, sent in zip(entries, exported):
        assert sent == original
        assert sent["signature"] == original["signature"]
    assert all(call["headers"]["X-Audit-Batch-Id"] == result["batch_id"] for call in siem.calls)
    assert all(ev["source"] == "kakehashi-phase-e" for c in siem.calls for ev in c["body"]["events"])

    # the export itself is audited
    last = store.entries()[-1]
    assert last["event_type"] == "AUDIT_EXPORT"
    assert last["status"] == "SUCCESS"
    assert last["result"]["exported_count"] == 1000
    assert last["resource_id"] == SIEM_URL


def test_audit_immutability(collector, store, crypto):
    record(collector, status=Status.SUCCESS)
    entry = store.entries()[0]
    assert run(collector.validateLog(entry)) is True

    modified = dict(entry)
    modified["status"] = "FAILURE"
    assert run(collector.validateLog(modified)) is False  # tampered, original signature

    modified["signature"] = crypto.signLogEntry(modified)
    assert run(collector.validateLog(modified)) is True  # corrected signature

    # the tampering was itself recorded as a security-relevant event
    failures = [e for e in store.entries() if e["event_type"] == "AUDIT_VALIDATE"]
    assert len(failures) == 1
    assert failures[0]["status"] == "FAILURE"
    assert failures[0]["resource_id"] == entry["event_id"]
    assert failures[0]["result"]["error_code"] == "SIGNATURE_MISMATCH"


# ------------------------------------------------------------- recordEvent


def test_recordEvent_accepts_exact_string_values(collector, store):
    """KeyVaultConnector passes Role.value / event type strings (Task 1.1 AuditSink)."""
    run(
        collector.recordEvent(
            event_type="KEY_ACCESS",
            actor_role="operator",
            resource_id=SECRET_URL,
            operation="GET",
            status="DENIED",
            error_code="Forbidden",
        )
    )
    entry = store.entries()[0]
    assert (entry["event_type"], entry["actor_role"], entry["status"]) == (
        "KEY_ACCESS",
        "operator",
        "DENIED",
    )
    assert entry["result"] == {"error_code": "Forbidden"}


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"actor_role": "OPERATOR"}, "actor_role"),  # brief's uppercase form is invalid
        ({"actor_role": "system"}, "actor_role"),  # abolished by Task 1.1 Decision 2
        ({"actor_role": Status.SUCCESS}, "actor_role"),
        ({"event_type": "DELETE_EVERYTHING"}, "event_type"),
        ({"event_type": Status.SUCCESS}, "event_type"),
        ({"status": "OK"}, "status"),
        ({"resource_id": ""}, "resource_id"),
        ({"operation": None}, "operation"),
        ({"actor": ""}, "actor"),
        ({"error_code": ""}, "error_code"),
        ({"error_code": 500}, "error_code"),
        ({"result": ["not", "a", "dict"]}, "result"),
        ({"result": {"error_code": "X"}}, "error_code"),
        ({"context": {"bad": object()}}, "context"),
        ({"context": {"nan": float("nan")}}, "context"),
    ],
)
def test_recordEvent_rejects_invalid_arguments(collector, store, overrides, match):
    with pytest.raises(ValueError, match=match):
        record(collector, **overrides)
    assert len(store) == 0


def test_recordEvent_stores_normalized_result_and_context(collector, store, hmac_key):
    when = datetime(2026, 11, 9, 18, 0, tzinfo=timezone(timedelta(hours=9)))
    record(
        collector,
        actor="user_abc123",
        result={"ciphertext_length": 48, "versions": ("v1", "v2")},
        context={"ip_address": "192.0.2.1", "requested_at": when, "chat": "chat_001"},
    )
    entry = store.entries()[0]
    assert entry["actor"] == "user_abc123"
    assert entry["result"] == {"ciphertext_length": 48, "versions": ["v1", "v2"], "error_code": None}
    assert entry["context"]["requested_at"] == "2026-11-09T09:00:00Z"
    # what was signed is what was stored
    assert entry["signature"] == reference_hmac(hmac_key, entry)
    assert run(collector.validateLog(entry)) is True


def test_timestamps_strictly_increase_when_clock_goes_back(crypto, store):
    times = iter([T0, T0 - timedelta(seconds=5), T0 + timedelta(seconds=1)])
    collector = AuditLogCollector(crypto, store, utc_now=lambda: next(times))
    for _ in range(3):
        record(collector)
    stamps = [e["timestamp"] for e in store.entries()]
    assert stamps == [
        "2026-11-09T09:00:00Z",
        "2026-11-09T09:00:00.000001Z",
        "2026-11-09T09:00:01Z",
    ]


def test_naive_clock_raises_audit_error(crypto, store):
    collector = AuditLogCollector(crypto, store, utc_now=lambda: datetime(2026, 11, 9))
    with pytest.raises(AuditError, match="naive"):
        record(collector)


def test_store_failure_raises_audit_error(crypto):
    collector = AuditLogCollector(crypto, FailingStore(ConnectionError("network down")))
    with pytest.raises(AuditError, match="cannot write") as info:
        record(collector)
    assert isinstance(info.value.__cause__, ConnectionError)


def test_store_audit_error_propagates_unchanged(crypto):
    original = AuditError("blob is a BlockBlob")
    collector = AuditLogCollector(crypto, FailingStore(original))
    with pytest.raises(AuditError) as info:
        record(collector)
    assert info.value is original


def test_signing_failure_raises_audit_error(crypto, store):
    collector = AuditLogCollector(crypto, store)

    def broken(entry):
        raise ValueError("cannot canonicalize")

    collector._crypto = SimpleNamespace(signLogEntry=broken)
    with pytest.raises(AuditError, match="cannot sign"):
        record(collector)
    assert len(store) == 0


def test_collector_requires_hmac_key(store):
    with pytest.raises(AuditError, match="HMAC key"):
        AuditLogCollector(CryptoService(), store)


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"actor": ""}, "actor"),
        ({"system_role": "operator"}, "system_role"),
        ({"siem_batch_size": 0}, "siem_batch_size"),
    ],
)
def test_collector_rejects_bad_configuration(crypto, store, kwargs, match):
    with pytest.raises(ValueError, match=match):
        AuditLogCollector(crypto, store, **kwargs)


# ------------------------------------------------------- HMAC key from Key Vault


def test_fromKeyVault_loads_audit_hmac_key(store, hmac_key):
    connector = FakeConnector(value=hmac_key)
    collector = run(AuditLogCollector.fromKeyVault(connector, store, utc_now=StepClock()))
    assert connector.calls == [("audit-hmac-key", None)]
    record(collector)
    entry = store.entries()[0]
    assert entry["signature"] == reference_hmac(hmac_key, entry)


def test_fromKeyVault_pinned_version_and_name(store, hmac_key):
    connector = FakeConnector(value=hmac_key)
    run(
        AuditLogCollector.fromKeyVault(
            connector, store, hmac_secret_name="audit-hmac-key-2", hmac_key_version="v7"
        )
    )
    assert connector.calls == [("audit-hmac-key-2", "v7")]


@pytest.mark.parametrize("value", [secrets.token_bytes(16), secrets.token_bytes(64), "text"])
def test_fromKeyVault_rejects_wrong_key_length(store, value):
    with pytest.raises(AuditError, match="32 bytes"):
        run(AuditLogCollector.fromKeyVault(FakeConnector(value=value), store))


def test_fromKeyVault_wraps_key_vault_failure(store):
    connector = FakeConnector(exc=RuntimeError("vault unavailable"))
    with pytest.raises(AuditError, match="cannot load audit HMAC key") as info:
        run(AuditLogCollector.fromKeyVault(connector, store))
    assert isinstance(info.value.__cause__, RuntimeError)


def test_key_vault_connector_writes_through_collector(collector, store):
    """Task 1.1 KeyVaultConnector -> Task 1.3 collector, end to end (fake SDK)."""
    key = secrets.token_bytes(32)

    class Credential:
        async def get_token(self, *scopes):
            return SimpleNamespace(token="t", expires_on=0)

        async def close(self):
            pass

    class SecretClient:
        async def get_secret(self, name, version=None):
            props = SimpleNamespace(version="v1", created_on=T0, enabled=True)
            return SimpleNamespace(value=base64.b64encode(key).decode(), properties=props)

        async def close(self):
            pass

    connector = KeyVaultConnector(
        "https://kakehashi-staging.vault.azure.net/",
        audit_collector=collector,
        credential_factory=lambda client_id: Credential(),
        client_factory=lambda url, cred: SecretClient(),
    )
    assert run(connector.getSecret("kakehashi-kek")) == key

    entries = store.entries()
    assert [(e["event_type"], e["operation"], e["status"]) for e in entries] == [
        ("KEY_ACCESS", "GET", "SUCCESS"),  # authenticate
        ("KEY_ACCESS", "GET", "SUCCESS"),  # get_secret
    ]
    assert entries[1]["resource_id"] == SECRET_URL
    assert all(e["actor_role"] == "operator" for e in entries)
    assert run(collector.validateLogSequence(entries)) is True


# --------------------------------------------------------------- validation


def _stored(collector, store) -> dict:
    record(collector)
    return store.entries()[-1]


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda e: e.pop("context"), "SCHEMA_INVALID"),
        (lambda e: e.update(extra="field"), "SCHEMA_INVALID"),
        (lambda e: e.update(actor_role="OPERATOR"), "SCHEMA_INVALID"),
        (lambda e: e.update(timestamp="2026-11-09T09:00:00+00:00"), "SCHEMA_INVALID"),
        (lambda e: e.update(timestamp="2026-11-09T09:00:00.000Z"), "SCHEMA_INVALID"),
        (lambda e: e.update(timestamp=12345), "SCHEMA_INVALID"),
        (lambda e: e.update(signature=""), "SIGNATURE_MISMATCH"),
        (lambda e: e.update(signature="zz" * 32), "SIGNATURE_MISMATCH"),
        (lambda e: e["result"].update(error_code="X"), "SIGNATURE_MISMATCH"),
    ],
)
def test_validateLog_rejects_invalid_entries(collector, store, mutate, reason):
    entry = _stored(collector, store)
    entry = json.loads(json.dumps(entry))
    mutate(entry)
    assert run(collector.validateLog(entry)) is False
    failure = store.entries()[-1]
    assert failure["event_type"] == "AUDIT_VALIDATE"
    assert failure["result"]["error_code"] == reason


def test_validateLog_rejects_non_mapping(collector, store):
    assert run(collector.validateLog(["not", "an", "entry"])) is False
    failure = store.entries()[-1]
    assert failure["resource_id"] == "unidentified-entry"
    assert failure["result"]["error_code"] == "NOT_A_MAPPING"


def test_validateLog_raises_when_failure_cannot_be_recorded(crypto, store):
    collector = AuditLogCollector(crypto, store)
    record(collector)
    entry = dict(store.entries()[0], status="FAILURE")
    collector._store = FailingStore(OSError("disk full"))
    with pytest.raises(AuditError):
        run(collector.validateLog(entry))


def test_validateLog_without_key_raises(collector, store):
    entry = _stored(collector, store)
    collector._crypto = CryptoService()  # misconfigured after construction
    with pytest.raises(AuditError, match="HMAC key"):
        run(collector.validateLog(entry))


def test_validateLogSequence_detects_breaks(collector, store):
    for i in range(3):
        record(collector, resource_id=f"r{i}")
    a, b, c = store.entries()

    assert run(collector.validateLogSequence([a, b, c])) is True
    assert run(collector.validateLogSequence([])) is True

    assert run(collector.validateLogSequence([a, c, b])) is False
    assert store.entries()[-1]["result"]["error_code"] == "OUT_OF_ORDER"

    assert run(collector.validateLogSequence([a, b, b])) is False
    assert store.entries()[-1]["result"]["error_code"] == "DUPLICATE_EVENT_ID"

    tampered = dict(b, operation="PUT")
    assert run(collector.validateLogSequence([a, tampered, c])) is False
    assert store.entries()[-1]["result"]["error_code"] == "SIGNATURE_MISMATCH"


def test_audit_log_entry_model_validation():
    base = dict(
        event_id="evt-1",
        timestamp=T0,
        event_type=EventType.SECURITY,
        actor="svc",
        actor_role=Role.ADMIN,
        resource_id="r",
        operation="GET",
        status=Status.SKIPPED,
    )
    entry = AuditLogEntry(**base)
    assert (entry.event_type, entry.actor_role, entry.status) == ("SECURITY", "admin", "SKIPPED")
    with pytest.raises(ValueError, match="timezone-aware"):
        AuditLogEntry(**dict(base, timestamp=datetime(2026, 11, 9)))
    with pytest.raises(ValueError, match="result"):
        AuditLogEntry(**dict(base, result=[]))
    with pytest.raises(ValueError, match="signature"):
        AuditLogEntry(**dict(base, signature=None))
    with pytest.raises(ValueError, match="mapping"):
        AuditLogEntry.from_dict([])
    with pytest.raises(ValueError, match="ending in 'Z'"):
        parse_utc_timestamp("2026-11-09T09:00:00")


# ------------------------------------------------------------------ export


def test_export_flags_tampered_entries_but_still_sends_them(collector, store, siem):
    record(collector)
    record(collector)
    good, bad = store.entries()
    bad = dict(bad, status="FAILURE")

    result = run(collector.exportToSIEM(SIEM_URL, [good, bad]))

    assert result["exported_count"] == 2
    assert result["invalid_count"] == 1
    events = siem.calls[0]["body"]["events"]
    assert [ev["signature_valid"] for ev in events] == [True, False]
    assert [ev["severity"] for ev in events] == ["LOW", "HIGH"]
    assert events[1]["audit_log"] == bad


def test_export_severity_mapping(collector, store, siem):
    record(collector, status=Status.FAILURE, error_code="Timeout")
    record(collector, event_type=EventType.SECURITY, status=Status.FAILURE, error_code="X")
    run(collector.exportToSIEM(SIEM_URL, store.entries()))
    assert [ev["severity"] for ev in siem.calls[0]["body"]["events"]] == ["MEDIUM", "HIGH"]


def test_export_empty_batch(collector, siem):
    result = run(collector.exportToSIEM(SIEM_URL, []))
    assert result["status"] == "success" and result["exported_count"] == 0
    assert siem.calls == []


def test_export_http_error_raises_and_records_partial_count(crypto, store):
    siem = RecordingSiem(statuses=[202, 503])
    collector = AuditLogCollector(crypto, store, siem_sender=siem, siem_batch_size=2)
    for _ in range(3):
        record(collector)
    entries = store.entries()

    with pytest.raises(AuditError, match="HTTP 503"):
        run(collector.exportToSIEM(SIEM_URL, entries))

    failure = store.entries()[-1]
    assert failure["event_type"] == "AUDIT_EXPORT"
    assert failure["status"] == "FAILURE"
    assert failure["result"]["error_code"] == "HTTP_503"
    assert failure["result"]["exported_count"] == 2
    assert failure["result"]["requested_count"] == 3


def test_export_transport_error_wrapped(crypto, store):
    siem = RecordingSiem(statuses=[ConnectionResetError("reset")])
    collector = AuditLogCollector(crypto, store, siem_sender=siem)
    record(collector)
    with pytest.raises(AuditError, match="ConnectionResetError") as info:
        run(collector.exportToSIEM(SIEM_URL, store.entries()))
    assert isinstance(info.value.__cause__, ConnectionResetError)
    assert store.entries()[-1]["result"]["error_code"] == "ConnectionResetError"


def test_export_redacts_endpoint_credentials_in_audit(collector, store, siem):
    url = "https://user:pass@mock-siem.example.com:8443/ingest?token=secret#x"
    run(collector.exportToSIEM(url, []))
    assert siem.calls == []
    assert store.entries()[-1]["resource_id"] == "https://mock-siem.example.com:8443/ingest"


def test_export_sends_custom_headers(crypto, store):
    siem = RecordingSiem()
    collector = AuditLogCollector(
        crypto, store, siem_sender=siem, siem_headers={"Authorization": "Bearer t"}
    )
    record(collector)
    run(collector.exportToSIEM(SIEM_URL, store.entries()))
    assert siem.calls[0]["headers"]["Authorization"] == "Bearer t"
    assert siem.calls[0]["headers"]["Content-Type"] == "application/json"


@pytest.mark.parametrize(
    "endpoint, entries, match",
    [
        ("http://mock-siem.example.com", [], "https"),
        ("https://", [], "https"),
        (None, [], "string"),
        (SIEM_URL, "not a list", "list"),
        (SIEM_URL, [1, 2], "dict"),
    ],
)
def test_export_rejects_bad_arguments(collector, siem, endpoint, entries, match):
    with pytest.raises(ValueError, match=match):
        run(collector.exportToSIEM(endpoint, entries))
    assert siem.calls == []


def test_default_aiohttp_sender_posts_body():
    pytest.importorskip("aiohttp")
    from aiohttp import web

    received: Dict[str, Any] = {}

    async def handler(request):
        received["body"] = await request.read()
        received["batch"] = request.headers.get("X-Audit-Batch-Id")
        return web.Response(status=202)

    async def main():
        app = web.Application()
        app.router.add_post("/ingest", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            return await alc._aiohttp_post(
                f"http://127.0.0.1:{port}/ingest", b'{"events":[]}', {"X-Audit-Batch-Id": "b1"}
            )
        finally:
            await runner.cleanup()

    assert run(main()) == 202
    assert received == {"body": b'{"events":[]}', "batch": "b1"}


def test_collector_defaults_to_aiohttp_sender(crypto, store):
    assert AuditLogCollector(crypto, store)._siem_sender is alc._aiohttp_post


# ------------------------------------------------------ Azure AppendBlob store


class FakeBlob:
    def __init__(self, blob_type: str = "AppendBlob") -> None:
        self.data = bytearray()
        self.blocks = 0
        self.blob_type = blob_type
        self.sealed = False


class FakeBlobClient:
    def __init__(self, container: "FakeContainer", name: str) -> None:
        self.container = container
        self.name = name

    async def create_append_blob(self, match_condition=None, **kwargs):
        self.container.create_calls.append((self.name, match_condition))
        if self.name in self.container.blobs:
            if match_condition == MatchConditions.IfMissing:
                raise ResourceExistsError("BlobAlreadyExists")
        # like the real SDK: without a condition an existing blob is overwritten
        self.container.blobs[self.name] = FakeBlob()

    async def get_blob_properties(self):
        if self.container.fail_properties:
            raise self.container.fail_properties
        blob = self.container.blobs[self.name]
        return SimpleNamespace(
            blob_type=SimpleNamespace(value=blob.blob_type),
            size=len(blob.data),
            append_blob_committed_block_count=blob.blocks,
            is_append_blob_sealed=blob.sealed,
        )

    async def append_block(self, data, appendpos_condition=None, **kwargs):
        blob = self.container.blobs[self.name]
        if self.container.fail_next is not None:
            exc, self.container.fail_next = self.container.fail_next, None
            raise exc
        if self.container.lost_response:
            # the first attempt lands, its response is lost, the SDK retry gets 412
            self.container.lost_response = False
            blob.data += data
            blob.blocks += 1
            raise ResourceModifiedError("AppendPositionConditionNotMet")
        if appendpos_condition is not None and appendpos_condition != len(blob.data):
            raise ResourceModifiedError("AppendPositionConditionNotMet")
        blob.data += data
        blob.blocks += 1

    async def download_blob(self):
        data = bytes(self.container.blobs[self.name].data)

        async def readall():
            return data

        return SimpleNamespace(readall=readall)


class FakeContainer:
    def __init__(self) -> None:
        self.blobs: Dict[str, FakeBlob] = {}
        self.create_calls: List[tuple] = []
        self.fail_next: Optional[BaseException] = None
        self.fail_properties: Optional[BaseException] = None
        self.lost_response = False
        self.closed = False

    def get_blob_client(self, name: str) -> FakeBlobClient:
        return FakeBlobClient(self, name)

    async def list_blobs(self, name_starts_with: str = ""):
        for name in list(self.blobs):
            if name.startswith(name_starts_with):
                yield SimpleNamespace(name=name)

    async def close(self) -> None:
        self.closed = True


def _blob_lines(container: FakeContainer, name: str) -> List[dict]:
    return [json.loads(line) for line in bytes(container.blobs[name].data).splitlines()]


def append(store: AzureAppendBlobAuditStore, payload: dict, when: datetime = T0) -> None:
    run(store.append(json.dumps(payload).encode() + b"\n", when))


def test_azure_store_writes_append_blob_and_never_overwrites():
    container = FakeContainer()
    name = "audit/2026/11/09/writer-a-0000.jsonl"
    existing = FakeBlob()
    existing.data += b'{"n":0}\n'
    existing.blocks = 1
    container.blobs[name] = existing  # written by an earlier process run

    store = AzureAppendBlobAuditStore(container, writer_id="writer-a")
    append(store, {"n": 1})
    append(store, {"n": 2})

    assert container.create_calls == [(name, MatchConditions.IfMissing)]
    assert _blob_lines(container, name) == [{"n": 0}, {"n": 1}, {"n": 2}]
    assert container.blobs[name].blocks == 3


def test_azure_store_refuses_non_append_blob():
    container = FakeContainer()
    name = "audit/2026/11/09/w-0000.jsonl"
    container.blobs[name] = FakeBlob(blob_type="BlockBlob")
    store = AzureAppendBlobAuditStore(container, writer_id="w")
    with pytest.raises(AuditError, match="not an AppendBlob"):
        append(store, {"n": 1})


def test_azure_store_rolls_over_full_and_sealed_segments():
    container = FakeContainer()
    sealed = FakeBlob()
    sealed.sealed = True
    container.blobs["audit/2026/11/09/w-0000.jsonl"] = sealed
    store = AzureAppendBlobAuditStore(container, writer_id="w", max_blocks=2)

    for n in range(5):
        append(store, {"n": n})

    assert _blob_lines(container, "audit/2026/11/09/w-0001.jsonl") == [{"n": 0}, {"n": 1}]
    assert _blob_lines(container, "audit/2026/11/09/w-0002.jsonl") == [{"n": 2}, {"n": 3}]
    assert _blob_lines(container, "audit/2026/11/09/w-0003.jsonl") == [{"n": 4}]
    assert sealed.data == bytearray()


def test_azure_store_partitions_by_utc_day():
    container = FakeContainer()
    store = AzureAppendBlobAuditStore(container, writer_id="w")
    append(store, {"n": 1}, T0)
    # 2026-11-10 08:00 JST is still 2026-11-09 UTC
    append(store, {"n": 2}, datetime(2026, 11, 10, 8, 0, tzinfo=timezone(timedelta(hours=9))))
    append(store, {"n": 3}, T0 + timedelta(days=1))
    assert sorted(container.blobs) == [
        "audit/2026/11/09/w-0000.jsonl",
        "audit/2026/11/10/w-0000.jsonl",
    ]
    assert run(store.read_day(date(2026, 11, 9))) == [{"n": 1}, {"n": 2}]
    assert run(store.read_day(date(2026, 11, 10))) == [{"n": 3}]


def test_azure_store_retry_that_already_landed_is_not_duplicated():
    container = FakeContainer()
    store = AzureAppendBlobAuditStore(container, writer_id="w")
    append(store, {"n": 1})
    container.lost_response = True
    append(store, {"n": 2})  # succeeds: the block is already in the blob
    append(store, {"n": 3})
    assert _blob_lines(container, "audit/2026/11/09/w-0000.jsonl") == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_azure_store_detects_foreign_writer_then_recovers():
    container = FakeContainer()
    store = AzureAppendBlobAuditStore(container, writer_id="w")
    append(store, {"n": 1})
    name = "audit/2026/11/09/w-0000.jsonl"
    container.blobs[name].data += b'{"foreign":true}\n'
    container.blobs[name].blocks += 1

    with pytest.raises(AuditError, match="moved unexpectedly"):
        append(store, {"n": 2})
    append(store, {"n": 3})  # reopened at the real end of the blob
    assert _blob_lines(container, name) == [{"n": 1}, {"foreign": True}, {"n": 3}]


def test_azure_store_unknown_state_after_412():
    container = FakeContainer()
    store = AzureAppendBlobAuditStore(container, writer_id="w")
    append(store, {"n": 1})
    container.fail_next = ResourceModifiedError("412")
    container.fail_properties = ConnectionError("down")
    with pytest.raises(AuditError, match="state is unknown"):
        append(store, {"n": 2})


def test_azure_store_wraps_append_and_open_failures():
    container = FakeContainer()
    store = AzureAppendBlobAuditStore(container, writer_id="w")
    append(store, {"n": 1})
    container.fail_next = TimeoutError("slow")
    with pytest.raises(AuditError, match="append to .* failed: TimeoutError"):
        append(store, {"n": 2})
    append(store, {"n": 3})
    assert _blob_lines(container, "audit/2026/11/09/w-0000.jsonl") == [{"n": 1}, {"n": 3}]

    other = FakeContainer()
    other.fail_properties = PermissionError("AuthorizationFailure")
    store2 = AzureAppendBlobAuditStore(other, writer_id="w")
    with pytest.raises(AuditError, match="cannot open audit blob"):
        append(store2, {"n": 1})


def test_azure_store_rejects_oversized_entry():
    store = AzureAppendBlobAuditStore(FakeContainer(), writer_id="w")
    with pytest.raises(AuditError, match="append block"):
        run(store.append(b"x" * (alc.MAX_APPEND_BLOCK_BYTES + 1), T0))


def test_azure_store_configuration():
    with pytest.raises(ValueError, match="prefix"):
        AzureAppendBlobAuditStore(FakeContainer(), prefix="/")
    with pytest.raises(ValueError, match="max_blocks"):
        AzureAppendBlobAuditStore(FakeContainer(), max_blocks=0)
    store = AzureAppendBlobAuditStore(FakeContainer(), prefix="/kakehashi/audit/", writer_id="host 1/pid:2")
    assert store.blob_name(date(2026, 11, 9), 3) == "kakehashi/audit/2026/11/09/host-1-pid-2-0003.jsonl"
    default = AzureAppendBlobAuditStore(FakeContainer())
    assert re.fullmatch(r"[0-9A-Za-z._-]+-\d+", default.writer_id)
    container = FakeContainer()
    run(AzureAppendBlobAuditStore(container).close())
    assert container.closed


def test_azure_store_with_managed_identity():
    pytest.importorskip("azure.storage.blob")
    with pytest.raises(ValueError, match="https"):
        AzureAppendBlobAuditStore.withManagedIdentity("http://acct.blob.core.windows.net", "audit")
    for client_id in (None, "00000000-0000-0000-0000-000000000000"):
        store = AzureAppendBlobAuditStore.withManagedIdentity(
            "https://acct.blob.core.windows.net", "audit", client_id=client_id, writer_id="w"
        )
        assert store._container.container_name == "audit"
        assert store.writer_id == "w"


def test_collector_end_to_end_on_append_blob(crypto):
    container = FakeContainer()
    blob_store = AzureAppendBlobAuditStore(container, writer_id="w")
    collector = AuditLogCollector(crypto, blob_store, utc_now=StepClock())

    async def main():
        await asyncio.gather(
            *(
                collector.recordEvent(EventType.DATA_READ, Role.AUDITOR, f"r{i}", "GET", Status.SUCCESS)
                for i in range(20)
            )
        )
        return await blob_store.read_day(date(2026, 11, 9))

    entries = run(main())
    assert len(entries) == 20
    assert run(collector.validateLogSequence(entries)) is True


def test_in_memory_store_rejects_non_bytes():
    with pytest.raises(TypeError):
        run(InMemoryAuditLogStore().append("text", T0))
