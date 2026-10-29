"""Tests for CryptoService (Phase E, Task 1.2).

Keys are generated per test with ``secrets.token_bytes``; the only fixed keys
are the public NIST / McGrew-Viega GCM known-answer test vectors.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

import pytest

from kakehashi.kek_wrapper import CryptoService, EncryptedData
from kakehashi.kek_wrapper.core import crypto_service as cs
from kakehashi.kek_wrapper.models.role import Role

T0 = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def aes_key() -> bytes:
    return secrets.token_bytes(32)


@pytest.fixture
def hmac_key() -> bytes:
    return secrets.token_bytes(32)


@pytest.fixture
def service(hmac_key) -> CryptoService:
    return CryptoService(hmac_key, utc_now=lambda: T0)


def reference_hmac(key: bytes, entry: dict) -> str:
    """Independent signer (stdlib hmac) pinning the canonical form for Task 1.3."""
    body = {k: v for k, v in entry.items() if k != "signature"}
    message = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


# ------------------------------------------------------- brief: 5 named tests


def test_encrypt_generates_random_iv(service, aes_key):
    plaintext = b"same plaintext"
    first = run(service.encrypt(plaintext, aes_key))
    second = run(service.encrypt(plaintext, aes_key))

    assert isinstance(first, EncryptedData) and isinstance(second, EncryptedData)
    assert len(first.iv) == 16 and len(second.iv) == 16
    assert first.iv != second.iv
    assert first.ciphertext != second.ciphertext
    assert run(service.decrypt(first, aes_key)) == plaintext
    assert run(service.decrypt(second, aes_key)) == plaintext


def test_decrypt_recovers_plaintext(service, aes_key):
    encrypted = run(service.encrypt(b"secret data", aes_key))
    assert run(service.decrypt(encrypted, aes_key)) == b"secret data"


def test_signature_validation_passes_valid(service, hmac_key):
    log_entry = {"event_id": "evt-123", "status": "SUCCESS"}
    signature = reference_hmac(hmac_key, log_entry)
    assert service.validateSignature(log_entry, signature) is True


def test_signature_validation_fails_tampered(service, hmac_key):
    log_entry = {"event_id": "evt-123", "status": "SUCCESS"}
    original_signature = reference_hmac(hmac_key, log_entry)
    modified_log_entry = dict(log_entry, status="FAILURE")
    assert service.validateSignature(modified_log_entry, original_signature) is False


# AES-256 test cases 13-16 and 18 from McGrew & Viega, "The Galois/Counter Mode
# of Operation (GCM)" (the specification NIST SP 800-38D standardises). Public
# test constants, not secrets.
GCM_SPEC_KEY = "feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308"
GCM_SPEC_PT = (
    "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
    "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255"
)
GCM_SPEC_AAD = "feedfacedeadbeeffeedfacedeadbeefabaddad2"
GCM_SPEC_CT = (
    "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
    "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662898015ad"
)
NIST_GCM_VECTORS = [
    # (name, key, iv, plaintext, aad, ciphertext, tag)
    ("TC13", "00" * 32, "00" * 12, "", "", "", "530f8afbc74536b9a963b4f1c4cb738b"),
    (
        "TC14",
        "00" * 32,
        "00" * 12,
        "00" * 16,
        "",
        "cea7403d4d606b6e074ec5d3baf39d18",
        "d0d1c8a799996bf0265b98b5d48ab919",
    ),
    (
        "TC15",
        GCM_SPEC_KEY,
        "cafebabefacedbaddecaf888",
        GCM_SPEC_PT,
        "",
        GCM_SPEC_CT,
        "b094dac5d93471bdec1a502270e3cc6c",
    ),
    (
        "TC16",
        GCM_SPEC_KEY,
        "cafebabefacedbaddecaf888",
        GCM_SPEC_PT[:120],
        GCM_SPEC_AAD,
        GCM_SPEC_CT[:120],
        "76fc6ece0f4e1768cddf8853bb2d551b",
    ),
    # 60-byte IV: exercises the GHASH-derived counter path that CryptoService's
    # 16-byte (non-96-bit) IVs also take
    (
        "TC18",
        GCM_SPEC_KEY,
        "9313225df88406e555909c5aff5269aa6a7a9538534f7da1e4c303d2a318a728"
        "c3c0c95156809539fcf0e2429a6b525416aedbf5a0de6a57a637b39b",
        GCM_SPEC_PT[:120],
        GCM_SPEC_AAD,
        "5a8def2f0c9e53f1f75d7853659e2a20eeb2b22aafde6419a058ab4f6f746bf4"
        "0fc0c3b780f244452da3ebf1c5d82cdea2418997200ef82e44ae7e3f",
        "a44a8266ee1c8eb0c8b5d4cf5ae9f19a",
    ),
]


def test_aes_gcm_against_known_vectors():
    for name, key, iv, pt, aad, ct, tag in NIST_GCM_VECTORS:
        k, n, p = bytes.fromhex(key), bytes.fromhex(iv), bytes.fromhex(pt)
        a = bytes.fromhex(aad) or None
        sealed = cs._aes_gcm_seal(k, n, p, a)
        assert sealed[:-16].hex() == ct, name
        assert sealed[-16:].hex() == tag, name
        assert cs._aes_gcm_open(k, n, sealed, a) == p, name
        # a single flipped tag bit must be rejected
        forged = sealed[:-1] + bytes([sealed[-1] ^ 0x01])
        with pytest.raises(ValueError):
            cs._aes_gcm_open(k, n, forged, a)


# ------------------------------------------------------------- encryption


def test_encrypt_records_key_version_and_timestamp(service, aes_key):
    encrypted = run(service.encrypt(b"x", aes_key, key_version="v2"))
    assert encrypted.key_version == "v2"
    assert encrypted.timestamp == T0
    assert len(encrypted.ciphertext) == 1 + 16  # ciphertext || tag

    unversioned = run(service.encrypt(b"x", aes_key))
    assert unversioned.key_version is None


@pytest.mark.parametrize("bad_version", ["", 1, b"v1", object()])
def test_encrypt_rejects_invalid_key_version(service, aes_key, bad_version):
    with pytest.raises(ValueError, match="key_version"):
        run(service.encrypt(b"x", aes_key, key_version=bad_version))


def test_default_clock_is_utc_aware(aes_key):
    encrypted = run(CryptoService().encrypt(b"x", aes_key))
    assert encrypted.timestamp.tzinfo is not None
    assert encrypted.timestamp.utcoffset().total_seconds() == 0


def test_encrypt_accepts_bytes_like(service, aes_key):
    encrypted = run(service.encrypt(bytearray(b"abc"), memoryview(aes_key)))
    assert run(service.decrypt(encrypted, bytearray(aes_key))) == b"abc"


def test_encrypt_empty_plaintext(service, aes_key):
    encrypted = run(service.encrypt(b"", aes_key))
    assert run(service.decrypt(encrypted, aes_key)) == b""


@pytest.mark.parametrize("length", [0, 16, 24, 31, 33, 64])
def test_rejects_wrong_key_length(service, length):
    with pytest.raises(ValueError, match="32-byte key"):
        run(service.encrypt(b"x", b"\x00" * length))
    record = EncryptedData(b"\x00" * 16, b"\x00" * 16, None, T0)
    with pytest.raises(ValueError, match="32-byte key"):
        run(service.decrypt(record, b"\x00" * length))


def test_key_error_never_contains_key_material(service):
    key = secrets.token_bytes(31)
    with pytest.raises(ValueError) as excinfo:
        run(service.encrypt(b"x", key))
    assert key.hex() not in str(excinfo.value)
    assert repr(key) not in str(excinfo.value)


def test_rejects_non_bytes_inputs(service, aes_key):
    with pytest.raises(TypeError):
        run(service.encrypt("text", aes_key))
    with pytest.raises(TypeError):
        run(service.encrypt(b"x", "0" * 32))
    with pytest.raises(TypeError):
        run(service.decrypt({"ciphertext": b""}, aes_key))


# ------------------------------------------------------------- decryption


def test_decrypt_fails_on_tampered_ciphertext(service, aes_key):
    encrypted = run(service.encrypt(b"secret data", aes_key))
    flipped = bytes([encrypted.ciphertext[0] ^ 0x80]) + encrypted.ciphertext[1:]
    tampered = EncryptedData(flipped, encrypted.iv, encrypted.key_version, encrypted.timestamp)
    with pytest.raises(ValueError, match="authentication failed"):
        run(service.decrypt(tampered, aes_key))


def test_decrypt_fails_on_wrong_key_or_iv(service, aes_key):
    encrypted = run(service.encrypt(b"secret data", aes_key))
    with pytest.raises(ValueError, match="authentication failed"):
        run(service.decrypt(encrypted, secrets.token_bytes(32)))
    other_iv = EncryptedData(
        encrypted.ciphertext, secrets.token_bytes(16), encrypted.key_version, encrypted.timestamp
    )
    with pytest.raises(ValueError, match="authentication failed"):
        run(service.decrypt(other_iv, aes_key))


def test_decrypt_rejects_malformed_record(service, aes_key):
    encrypted = run(service.encrypt(b"secret data", aes_key))
    short_iv = EncryptedData(encrypted.ciphertext, encrypted.iv[:12], None, T0)
    with pytest.raises(ValueError, match="iv must be 16 bytes"):
        run(service.decrypt(short_iv, aes_key))
    truncated = EncryptedData(encrypted.ciphertext[:15], encrypted.iv, None, T0)
    with pytest.raises(ValueError, match="shorter than the GCM authentication tag"):
        run(service.decrypt(truncated, aes_key))


def test_explicit_iv_primitives_are_private():
    import kakehashi.kek_wrapper as pkg

    for name in ("aes_gcm_seal", "aes_gcm_open"):
        assert not hasattr(cs, name)
        assert not hasattr(pkg, name)


def test_primitives_reject_empty_iv(aes_key):
    with pytest.raises(ValueError, match="iv must not be empty"):
        cs._aes_gcm_seal(aes_key, b"", b"x")
    with pytest.raises(ValueError, match="iv must not be empty"):
        cs._aes_gcm_open(aes_key, b"", b"\x00" * 16)


# ------------------------------------------------------------- signatures


def test_sign_log_entry_matches_reference(service, hmac_key):
    entry = {"event_id": "evt-1", "status": "SUCCESS", "note": "沖縄"}
    signature = service.signLogEntry(entry)
    assert len(signature) == 64
    assert signature == reference_hmac(hmac_key, entry)
    assert service.validateSignature(entry, signature) is True


def test_signature_field_is_excluded(service):
    entry = {"event_id": "evt-1", "status": "SUCCESS"}
    signature = service.signLogEntry(entry)
    signed_entry = dict(entry, signature=signature)
    assert service.signLogEntry(signed_entry) == signature
    assert service.validateSignature(signed_entry, signed_entry["signature"]) is True


def test_signature_is_key_order_independent(service):
    a = {"event_id": "evt-1", "status": "SUCCESS"}
    b = {"status": "SUCCESS", "event_id": "evt-1"}
    assert service.signLogEntry(a) == service.signLogEntry(b)


def test_signature_handles_datetime_and_role(service, hmac_key):
    """Sign from a datetime object, validate the entry as Task 1.3 stores it (``...Z``)."""
    entry = {"event_id": "evt-1", "timestamp": T0, "actor_role": Role.ADMIN}
    signature = service.signLogEntry(entry)
    as_stored = {"event_id": "evt-1", "timestamp": "2026-11-06T09:00:00Z", "actor_role": "admin"}
    assert service.validateSignature(as_stored, signature) is True
    assert signature == reference_hmac(hmac_key, as_stored)


def test_signature_datetime_normalised_to_utc_z(service):
    jst = timezone(timedelta(hours=9))
    same_instant = datetime(2026, 11, 6, 18, 0, tzinfo=jst)
    signature = service.signLogEntry({"timestamp": same_instant})
    assert service.validateSignature({"timestamp": "2026-11-06T09:00:00Z"}, signature) is True
    # other textual forms of the same instant are different stored values
    assert service.validateSignature({"timestamp": "2026-11-06T09:00:00+00:00"}, signature) is False
    assert service.validateSignature({"timestamp": "2026-11-06T18:00:00+09:00"}, signature) is False

    with_micros = datetime(2026, 11, 6, 9, 0, 0, 123456, tzinfo=timezone.utc)
    signature = service.signLogEntry({"timestamp": with_micros})
    assert service.validateSignature({"timestamp": "2026-11-06T09:00:00.123456Z"}, signature) is True


def test_signature_rejects_naive_datetime(service):
    naive = {"timestamp": datetime(2026, 11, 6, 9, 0)}
    with pytest.raises(TypeError, match="naive datetime"):
        service.signLogEntry(naive)
    assert service.validateSignature(naive, "0" * 64) is False


def test_signature_uppercase_hex_accepted(service):
    entry = {"event_id": "evt-1"}
    assert service.validateSignature(entry, service.signLogEntry(entry).upper()) is True


@pytest.mark.parametrize(
    "bad_signature",
    ["", "abc", "z" * 64, "0" * 63, "0" * 65, None, 123, b"0" * 64],
)
def test_signature_rejects_malformed(service, bad_signature):
    assert service.validateSignature({"event_id": "evt-1"}, bad_signature) is False


def test_signature_with_other_key_fails(service):
    entry = {"event_id": "evt-1"}
    other = CryptoService(secrets.token_bytes(32))
    assert service.validateSignature(entry, other.signLogEntry(entry)) is False


def test_signature_rejects_unserializable_entry(service):
    valid = "0" * 64
    assert service.validateSignature({"blob": object()}, valid) is False
    assert service.validateSignature({"value": float("nan")}, valid) is False
    assert service.validateSignature(["not", "a", "dict"], valid) is False
    with pytest.raises(TypeError):
        service.signLogEntry({"blob": object()})


def test_signature_requires_hmac_key(aes_key):
    service = CryptoService()
    with pytest.raises(RuntimeError, match="no HMAC key"):
        service.validateSignature({"event_id": "evt-1"}, "0" * 64)
    with pytest.raises(RuntimeError, match="no HMAC key"):
        service.signLogEntry({"event_id": "evt-1"})


def test_constructor_rejects_short_hmac_key():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        CryptoService(secrets.token_bytes(16))
    with pytest.raises(TypeError):
        CryptoService("not-bytes")


# ------------------------------------------------------------- key vault


class FakeConnector:
    def __init__(self, secret: bytes) -> None:
        self.secret = secret
        self.calls = []

    async def getSecret(self, secret_name, key_version=None):
        self.calls.append((secret_name, key_version))
        return self.secret


def test_from_key_vault_loads_hmac_key(hmac_key):
    connector = FakeConnector(hmac_key)
    service = run(CryptoService.fromKeyVault(connector, utc_now=lambda: T0))
    assert connector.calls == [("audit-hmac-key", None)]
    entry = {"event_id": "evt-123", "status": "SUCCESS"}
    assert service.validateSignature(entry, reference_hmac(hmac_key, entry)) is True

    run(CryptoService.fromKeyVault(connector, "other-hmac", "v7"))
    assert connector.calls[-1] == ("other-hmac", "v7")
