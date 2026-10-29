"""Tests for KeyVaultConnector (Phase E, Task 1.1).

The Azure SDK is replaced by in-memory fakes injected through the connector's
factories, so these tests need no network and no Azure subscription. The one
test that talks to a real (staging) vault runs only when
``KAKEHASHI_STAGING_VAULT_URL`` is set on a host with a Managed Identity.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Dict, List, Optional

import pytest

from kakehashi.kek_wrapper import (
    DEFAULT_CACHE_TTL_SECONDS,
    EncryptedData,
    KeyVaultAuthenticationError,
    KeyVaultConnector,
    KeyVaultError,
    KeyVersion,
)
from kakehashi.kek_wrapper.core import key_vault_connector as kvc
from kakehashi.kek_wrapper.core.key_vault_connector import (
    KEY_VAULT_SCOPE,
    ResourceNotFoundError,
)
from kakehashi.kek_wrapper.models.role import Role

VAULT_URL = "https://kakehashi-staging.vault.azure.net/"
T0 = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


# --------------------------------------------------------------------- fakes


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class FakeUtc:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class FakeCredential:
    def __init__(self, client_id: Optional[str] = None, fail: bool = False) -> None:
        self.client_id = client_id
        self.fail = fail
        self.scopes: List[str] = []
        self.closed = False

    async def get_token(self, *scopes: str):
        self.scopes.extend(scopes)
        if self.fail:
            raise RuntimeError("ManagedIdentityCredential authentication unavailable")
        return SimpleNamespace(token="fake-token", expires_on=0)  # nosec B106 - test mock

    async def close(self) -> None:
        self.closed = True


class FakeSecretClient:
    """Minimal async SecretClient: versioned secrets kept in memory."""

    def __init__(self, utc: FakeUtc) -> None:
        self.utc = utc
        self.store: Dict[str, List[SimpleNamespace]] = {}
        self.get_calls: List[tuple] = []
        self.set_calls: List[dict] = []
        self.fail_get: Optional[Exception] = None
        self.fail_set: Optional[Exception] = None
        self.closed = False
        self._counter = 0

    def put(self, name: str, value: str, created_on: Optional[datetime] = None) -> str:
        self._counter += 1
        version = f"v{self._counter}"
        props = SimpleNamespace(
            version=version, created_on=created_on or self.utc.now, enabled=True
        )
        self.store.setdefault(name, []).append(
            SimpleNamespace(name=name, value=value, properties=props)
        )
        return version

    async def get_secret(self, name: str, version: Optional[str] = None):
        self.get_calls.append((name, version))
        if self.fail_get is not None:
            raise self.fail_get
        versions = self.store.get(name)
        if not versions:
            raise ResourceNotFoundError("secret not found")
        if version is None:
            return versions[-1]
        for item in versions:
            if item.properties.version == version:
                return item
        raise ResourceNotFoundError("version not found")

    async def set_secret(self, name: str, value: str, **kwargs):
        self.set_calls.append({"name": name, **kwargs})
        if self.fail_set is not None:
            raise self.fail_set
        self.put(name, value)
        return self.store[name][-1]

    async def close(self) -> None:
        self.closed = True


class FakeAudit:
    """Audit sink with exactly the planned Task 1.3 ``recordEvent`` signature.

    No defaults and no ``**kwargs``: a call that omits or renames a parameter
    fails with TypeError, as it would against the real AuditLogCollector.
    """

    def __init__(self) -> None:
        self.events: List[dict] = []
        self.fail: Optional[Exception] = None

    async def recordEvent(self, event_type, actor_role, resource_id, operation, status, error_code):
        if self.fail is not None:
            raise self.fail
        self.events.append(
            {
                "event_type": event_type,
                "actor_role": actor_role,
                "resource_id": resource_id,
                "operation": operation,
                "status": status,
                "error_code": error_code,
            }
        )


class Harness:
    def __init__(self, *, fail_auth: bool = False, **kwargs) -> None:
        self.clock = FakeClock()
        self.utc = FakeUtc(T0)
        self.client = FakeSecretClient(self.utc)
        self.audit = FakeAudit()
        self.credentials: List[FakeCredential] = []
        self.client_factory_args: List[tuple] = []

        def credential_factory(client_id):
            cred = FakeCredential(client_id, fail=fail_auth)
            self.credentials.append(cred)
            return cred

        def client_factory(vault_url, credential):
            self.client_factory_args.append((vault_url, credential))
            return self.client

        self.connector = KeyVaultConnector(
            VAULT_URL,
            audit_collector=self.audit,
            credential_factory=credential_factory,
            client_factory=client_factory,
            clock=self.clock,
            utcnow=self.utc,
            **kwargs,
        )


# ---------------------------------------------------------- covering tests


def test_authenticate_with_managed_identity(monkeypatch):
    monkeypatch.setenv("AZURE_CLIENT_ID", "11111111-2222-3333-4444-555555555555")
    h = Harness()

    run(h.connector.authenticate())

    assert h.connector.is_authenticated
    assert len(h.credentials) == 1
    cred = h.credentials[0]
    # user-assigned identity selected from AZURE_CLIENT_ID
    assert cred.client_id == "11111111-2222-3333-4444-555555555555"
    # session proven usable by requesting a Key Vault token
    assert cred.scopes == [KEY_VAULT_SCOPE]
    assert h.client_factory_args == [(VAULT_URL, cred)]
    assert h.audit.events[-1]["event_type"] == "KEY_ACCESS"
    assert h.audit.events[-1]["operation"] == "GET"
    assert h.audit.events[-1]["status"] == "SUCCESS"

    # idempotent: a second call does not open another session
    run(h.connector.authenticate())
    assert len(h.credentials) == 1


def test_default_factories_use_managed_identity_sdk():
    """Without injected factories the connector builds the real async SDK objects."""
    ManagedIdentityCredential = pytest.importorskip("azure.identity.aio").ManagedIdentityCredential
    SecretClient = pytest.importorskip("azure.keyvault.secrets.aio").SecretClient

    async def build_defaults():
        cred_user = kvc._default_credential_factory("client-id")
        cred_system = kvc._default_credential_factory(None)
        client = kvc._default_client_factory(VAULT_URL, cred_user)
        try:
            assert isinstance(cred_user, ManagedIdentityCredential)
            assert isinstance(cred_system, ManagedIdentityCredential)
            assert isinstance(client, SecretClient)
        finally:
            await client.close()
            await cred_user.close()
            await cred_system.close()

    run(build_defaults())


def test_getSecret_returns_correct_key_version():
    h = Harness()
    k1, k2, k3 = os.urandom(32), os.urandom(32), os.urandom(32)
    v1 = h.client.put("kakehashi-kek", b64(k1))
    v2 = h.client.put("kakehashi-kek", b64(k2))
    v3 = h.client.put("kakehashi-kek", b64(k3))

    async def scenario():
        latest = await h.connector.getSecret("kakehashi-kek")
        pinned1 = await h.connector.getSecret("kakehashi-kek", v1)
        pinned2 = await h.connector.getSecret("kakehashi-kek", key_version=v2)
        pinned3 = await h.connector.getSecret("kakehashi-kek", v3)
        value, version = await h.connector.getSecretWithVersion("kakehashi-kek")
        return latest, pinned1, pinned2, pinned3, value, version

    latest, p1, p2, p3, value, version = run(scenario())

    assert latest == k3
    assert (p1, p2, p3) == (k1, k2, k3)
    assert value == k3 and version.version == v3
    assert isinstance(latest, bytes) and len(latest) == 32
    # getSecret authenticated lazily on first use
    assert h.connector.is_authenticated
    # the latest lookup also primed the cache for v3, so pinning v3 was a hit
    assert ("kakehashi-kek", v3) not in h.client.get_calls
    assert all(e["status"] == "SUCCESS" for e in h.audit.events)
    assert any(e["resource_id"].endswith(f"/secrets/kakehashi-kek/{v1}") for e in h.audit.events)


def test_getSecret_cache_ttl_expires():
    h = Harness()
    old, new = os.urandom(32), os.urandom(32)
    h.client.put("kakehashi-kek", b64(old))
    assert DEFAULT_CACHE_TTL_SECONDS == 300
    assert h.connector.cache_ttl_seconds == 300

    async def scenario():
        first = await h.connector.getSecret("kakehashi-kek")
        calls_after_first = len(h.client.get_calls)

        # Key Vault content changes, but the cache still serves the old value
        h.client.put("kakehashi-kek", b64(new))
        h.clock.advance(299.9)
        cached = await h.connector.getSecret("kakehashi-kek")
        assert len(h.client.get_calls) == calls_after_first

        # at exactly 5 minutes the entry is expired and re-fetched
        h.clock.advance(0.1)
        refreshed = await h.connector.getSecret("kakehashi-kek")
        assert len(h.client.get_calls) == calls_after_first + 1
        return first, cached, refreshed

    first, cached, refreshed = run(scenario())
    assert first == old
    assert cached == old
    assert refreshed == new

    # manual invalidation forces a fetch without waiting for the TTL
    h.connector.invalidate_cache("kakehashi-kek")
    before = len(h.client.get_calls)
    run(h.connector.getSecret("kakehashi-kek"))
    assert len(h.client.get_calls) == before + 1


def test_key_rotation_scenario():
    h = Harness()
    original = os.urandom(32)
    v1 = h.client.put("kakehashi-kek", b64(original), created_on=T0)

    async def scenario():
        # data encrypted under v1 records its key version
        record = EncryptedData(
            ciphertext=b"\x00" * 16, iv=b"\x00" * 16, key_version=v1, timestamp=T0
        )
        assert await h.connector.getSecret("kakehashi-kek") == original

        # day 30: scheduled rotation is not due yet
        h.utc.now = T0 + timedelta(days=30)
        skipped = await h.connector.rotateKey()
        assert skipped["rotated"] is False
        assert skipped["key_version"] == v1
        assert h.client.set_calls == []

        # day 90: scheduled rotation creates v2
        h.utc.now = T0 + timedelta(days=90)
        rotated = await h.connector.rotateKey()
        assert rotated["rotated"] is True and rotated["emergency"] is False
        assert rotated["previous_version"] == v1
        assert rotated["key_version"] != v1
        assert datetime.fromisoformat(rotated["created_at"]) == T0 + timedelta(days=90)
        assert h.client.set_calls[-1]["tags"]["kakehashi-rotation"] == "scheduled"
        assert h.client.set_calls[-1]["content_type"] == "application/octet-stream;base64"

        # new and old keys both work: latest is the new key, v1 still decrypts old data
        latest_value, latest_version = await h.connector.getSecretWithVersion("kakehashi-kek")
        assert latest_version.version == rotated["key_version"]
        assert latest_value != original and len(latest_value) == 32
        assert await h.connector.getSecret("kakehashi-kek", record.key_version) == original

        # emergency rotation ignores age and purges every cached version
        fetches_before = len(h.client.get_calls)
        emergency = await h.connector.rotateKey(force_emergency=True)
        assert emergency["rotated"] is True and emergency["emergency"] is True
        assert emergency["previous_version"] == rotated["key_version"]
        assert h.client.set_calls[-1]["tags"]["kakehashi-rotation"] == "emergency"
        assert await h.connector.getSecret("kakehashi-kek", v1) == original
        assert len(h.client.get_calls) > fetches_before + 1  # v1 had to be re-fetched
        return rotated, emergency

    run(scenario())
    rotations = [
        (e["operation"], e["status"]) for e in h.audit.events if e["event_type"] == "KEY_ROTATE"
    ]
    # day-30 check (GET, nothing written), day-90 rotation, emergency rotation
    assert rotations == [("GET", "SUCCESS"), ("PUT", "SUCCESS"), ("PUT", "SUCCESS")]


# ------------------------------------------------------- supporting tests


def test_authentication_failure_is_audited_and_raised():
    h = Harness(fail_auth=True)
    with pytest.raises(KeyVaultAuthenticationError):
        run(h.connector.authenticate())
    assert not h.connector.is_authenticated
    assert h.credentials[0].closed
    assert h.audit.events[-1]["status"] == "FAILURE"
    assert h.audit.events[-1]["error_code"] == "RuntimeError"


def test_constructor_validation(monkeypatch):
    monkeypatch.delenv("AZURE_KEY_VAULT_URL", raising=False)
    with pytest.raises(ValueError):
        KeyVaultConnector()
    with pytest.raises(ValueError):
        KeyVaultConnector("http://insecure.vault.azure.net/")
    with pytest.raises(ValueError):
        KeyVaultConnector(VAULT_URL, cache_ttl_seconds=0)
    with pytest.raises(ValueError):
        KeyVaultConnector(VAULT_URL, kek_secret_name="bad_name")  # nosec B106 - test data
    monkeypatch.setenv("AZURE_KEY_VAULT_URL", VAULT_URL)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    connector = KeyVaultConnector()
    assert connector.vault_url == VAULT_URL
    assert connector.client_id is None


def test_getSecret_errors_are_wrapped_and_audited():
    h = Harness()
    h.client.put("bad-value", "not base64 !!")

    with pytest.raises(ValueError):
        run(h.connector.getSecret("user_key_1"))  # underscores are illegal in Key Vault
    with pytest.raises(KeyVaultError, match="not valid base64"):
        run(h.connector.getSecret("bad-value"))
    with pytest.raises(KeyVaultError, match="ResourceNotFoundError"):
        run(h.connector.getSecret("missing-secret", "v99"))

    h.client.put("empty-value", "")
    with pytest.raises(KeyVaultError, match="no value"):
        run(h.connector.getSecret("empty-value"))

    failures = [e for e in h.audit.events if e["status"] == "FAILURE"]
    assert [e["error_code"] for e in failures] == [
        "KeyVaultError",
        "ResourceNotFoundError",
        "KeyVaultError",
    ]
    # secret values never appear in audit records
    assert all("not base64" not in str(e) for e in h.audit.events)


def test_rotation_failure_and_first_key_creation():
    h = Harness()
    # no KEK yet: a scheduled rotation creates the first version
    created = run(h.connector.rotateKey())
    assert created["rotated"] is True and created["previous_version"] is None
    assert h.client.set_calls[-1]["tags"]["kakehashi-previous-version"] == ""

    h.client.fail_set = RuntimeError("throttled")
    with pytest.raises(KeyVaultError, match="RuntimeError"):
        run(h.connector.rotateKey(force_emergency=True))
    assert h.audit.events[-1]["status"] == "FAILURE"


def test_rotation_fills_created_at_when_vault_omits_it():
    h = Harness()

    async def set_without_date(name, value, **kwargs):
        h.client.set_calls.append({"name": name, **kwargs})
        return SimpleNamespace(
            value=value, properties=SimpleNamespace(version="vx", created_on=None, enabled=True)
        )

    h.client.set_secret = set_without_date
    result = run(h.connector.rotateKey(force_emergency=True))
    assert result["created_at"] == T0.isoformat()


def test_close_and_context_manager():
    h = Harness()
    h.client.put("kakehashi-kek", b64(os.urandom(32)))

    async def scenario():
        async with h.connector as conn:
            await conn.getSecret("kakehashi-kek")
            assert conn._cache
        return conn

    conn = run(scenario())
    assert not conn.is_authenticated
    assert conn._cache == {}
    assert h.client.closed and h.credentials[0].closed


def test_logAccess_without_collector_uses_logger(caplog):
    connector = KeyVaultConnector(VAULT_URL)
    with caplog.at_level(logging.INFO, logger=kvc.__name__):
        run(
            connector.logAccess(
                "GET_SECRET", "SUCCESS", resource_id="test-vault", actor_role=Role.OPERATOR
            )
        )
    assert "event_type=KEY_ACCESS" in caplog.text
    assert "actor_role=operator" in caplog.text
    assert "operation=GET" in caplog.text
    assert "status=SUCCESS" in caplog.text


def test_models():
    kv = KeyVersion("kakehashi-kek", "v1", created_on=None)
    assert kv.age() is None
    assert kv.is_rotation_due() is True
    naive = KeyVersion("kakehashi-kek", "v1", created_on=datetime(2026, 1, 1))
    assert naive.age(datetime(2026, 1, 2, tzinfo=timezone.utc)) == timedelta(days=1)
    assert kv.to_dict()["created_at"] is None
    # Task 1.2 locked EncryptedData to exactly these four fields
    from dataclasses import fields

    assert [f.name for f in fields(EncryptedData)] == [
        "ciphertext",
        "iv",
        "key_version",
        "timestamp",
    ]
    record = EncryptedData(ciphertext=b"x", iv=b"\x00" * 16, key_version=None, timestamp=T0)
    assert record.key_version is None


def test_audit_sink_receives_task_1_3_signature():
    """logAccess calls recordEvent exactly as the Task 1.3 collector defines it."""
    import inspect

    expected = ["event_type", "actor_role", "resource_id", "operation", "status", "error_code"]
    assert list(inspect.signature(FakeAudit.recordEvent).parameters)[1:] == expected
    assert list(inspect.signature(kvc.AuditSink.recordEvent).parameters)[1:] == expected

    h = Harness(actor_role=Role.OPERATOR)
    h.client.put("kakehashi-kek", b64(os.urandom(32)))
    run(h.connector.getSecret("kakehashi-kek"))
    assert h.audit.events[-1] == {
        "event_type": "KEY_ACCESS",
        "actor_role": "operator",
        "resource_id": VAULT_URL.rstrip("/") + "/secrets/kakehashi-kek/v1",
        "operation": "GET",
        "status": "SUCCESS",
        "error_code": None,
    }
    # every record stays inside the spec section 1.4 vocabulary
    assert {e["event_type"] for e in h.audit.events} <= {"KEY_ACCESS", "KEY_ROTATE"}
    assert {e["status"] for e in h.audit.events} <= {"SUCCESS", "FAILURE", "DENIED"}


def test_logAccess_rejects_unknown_vocabulary():
    h = Harness()
    with pytest.raises(ValueError, match="operation"):
        run(
            h.connector.logAccess(
                "DELETE_EVERYTHING", "SUCCESS", resource_id="test-vault", actor_role=Role.OPERATOR
            )
        )
    with pytest.raises(ValueError, match="status"):
        run(
            h.connector.logAccess(
                "GET_SECRET", "SKIPPED", resource_id="test-vault", actor_role=Role.OPERATOR
            )
        )
    assert h.audit.events == []
    with pytest.raises(ValueError, match="actor_role"):
        KeyVaultConnector(VAULT_URL, actor_role=" ")


def test_logAccess_with_valid_role_enum():
    """Role enum型の値でlogAccessが正常に動作することを検証。"""
    h = Harness()
    for role in [Role.ADMIN, Role.OPERATOR, Role.AUDITOR, Role.GUEST]:
        h.audit.events.clear()
        run(h.connector.logAccess("GET_SECRET", "SUCCESS", resource_id="vault-1", actor_role=role))
        assert len(h.audit.events) == 1
        assert h.audit.events[0]["actor_role"] == role.value
        assert h.audit.events[0]["operation"] == "GET"


def test_logAccess_rejects_invalid_role_type():
    """文字列型のロール値を拒否することを検証。"""
    h = Harness()
    with pytest.raises(ValueError, match="Role enum member"):
        run(
            h.connector.logAccess(
                "GET_SECRET", "SUCCESS", resource_id="vault-1", actor_role="admin"
            )
        )


def test_no_stale_key_after_emergency_rotation():
    """A "latest" fetch in flight during an emergency rotation is not re-cached."""
    h = Harness()
    compromised = os.urandom(32)
    h.client.put("kakehashi-kek", b64(compromised))

    async def scenario():
        await h.connector.authenticate()
        real_get = h.client.get_secret
        fetched = asyncio.Event()
        release = asyncio.Event()
        held = []

        async def slow_get(name, version=None):
            result = await real_get(name, version)
            if not held:  # hold only the first fetch, with the pre-rotation value
                held.append(result)
                fetched.set()
                await release.wait()
            return result

        h.client.get_secret = slow_get
        in_flight = asyncio.create_task(h.connector.getSecret("kakehashi-kek"))
        await fetched.wait()

        rotated = await h.connector.rotateKey(force_emergency=True)
        release.set()

        # the in-flight call returns its (pre-rotation) value to its own caller ...
        assert await in_flight == compromised
        # ... but every call after the rotation gets the new key
        after = [await h.connector.getSecret("kakehashi-kek") for _ in range(3)]
        return rotated, after

    rotated, after = run(scenario())
    assert all(value != compromised for value in after)
    latest_version = run(h.connector.getSecretWithVersion("kakehashi-kek"))[1]
    assert latest_version.version == rotated["key_version"]


def test_invalidate_during_fetch_skips_cache_write():
    h = Harness()
    h.client.put("kakehashi-kek", b64(os.urandom(32)))

    async def scenario():
        await h.connector.authenticate()
        real_get = h.client.get_secret

        async def get_then_invalidate(name, version=None):
            result = await real_get(name, version)
            h.connector.invalidate_cache()  # global invalidation mid-fetch
            return result

        h.client.get_secret = get_then_invalidate
        await h.connector.getSecret("kakehashi-kek")
        h.client.get_secret = real_get

    run(scenario())
    assert h.connector._cache == {}


def test_failed_audit_prevents_cache_write():
    h = Harness()
    key = os.urandom(32)
    h.client.put("kakehashi-kek", b64(key))
    run(h.connector.authenticate())

    h.audit.fail = RuntimeError("audit collector down")
    with pytest.raises(RuntimeError, match="audit collector down"):
        run(h.connector.getSecret("kakehashi-kek"))
    # nothing cached: the next call goes to Key Vault again and is audited
    assert h.connector._cache == {}
    h.audit.fail = None
    fetches = len(h.client.get_calls)
    assert run(h.connector.getSecret("kakehashi-kek")) == key
    assert len(h.client.get_calls) == fetches + 1
    assert h.audit.events[-1]["status"] == "SUCCESS"


def test_credential_factory_failure_is_audited():
    audit = FakeAudit()

    def broken_factory(client_id):
        raise RuntimeError("no managed identity endpoint")

    connector = KeyVaultConnector(
        VAULT_URL, audit_collector=audit, credential_factory=broken_factory
    )
    with pytest.raises(KeyVaultAuthenticationError, match="RuntimeError"):
        run(connector.authenticate())
    assert audit.events[-1]["status"] == "FAILURE"
    assert audit.events[-1]["event_type"] == "KEY_ACCESS"


def test_failed_audit_prevents_authentication():
    h = Harness()
    h.audit.fail = RuntimeError("audit collector down")
    with pytest.raises(RuntimeError, match="audit collector down"):
        run(h.connector.authenticate())
    assert not h.connector.is_authenticated
    assert h.credentials[0].closed and h.client.closed

    h.audit.fail = None
    run(h.connector.authenticate())
    assert h.connector.is_authenticated
    assert len(h.credentials) == 2


@pytest.mark.skipif(
    not os.environ.get("KAKEHASHI_STAGING_VAULT_URL"),
    reason="staging Key Vault not configured (set KAKEHASHI_STAGING_VAULT_URL on a host with Managed Identity)",
)
def test_staging_vault_authentication():  # pragma: no cover - needs Azure
    async def scenario():
        async with KeyVaultConnector(os.environ["KAKEHASHI_STAGING_VAULT_URL"]) as conn:
            assert conn.is_authenticated

    run(scenario())
