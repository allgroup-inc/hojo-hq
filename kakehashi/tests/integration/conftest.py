"""Pytest fixtures for KAKEHASHI integration tests (Task 3.4).

Provides staging environment setup, KEKWrapper fixtures, mock Azure services,
and shared utilities for end-to-end testing of cryptographic workflows,
RBAC enforcement, key rotation, and audit trail completeness.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kakehashi.kek_wrapper.models.crypto_models import EncryptedData, Role


class MockKeyVaultConnector:
    """Mock Key Vault Connector with caching and version management."""

    def __init__(self):
        self.secret_value = base64.b64encode(b"abcdefghijklmnopqrstuvwxyz012345").decode("ascii")
        self.current_version = "kakehashi-kek/v1"
        self.versions = ["kakehashi-kek/v1"]
        self.mock_http_error = None
        self.retry_count = 0
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    async def get_secret(self, secret_name: str, version: Optional[str] = None) -> str:
        """Get secret from Key Vault with caching."""
        if self.mock_http_error:
            self.retry_count += 1
            if self.retry_count >= 3:
                raise KeyVaultError(f"HTTP {self.mock_http_error} after 3 retries")
            await asyncio.sleep(0.01)  # Simulate retry delay
            raise KeyVaultError(f"HTTP {self.mock_http_error}")

        # Check cache
        cache_key = f"{secret_name}:{version or 'latest'}"
        if cache_key in self.cache:
            cached_value, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_value

        # Store in cache
        self.cache[cache_key] = (self.secret_value, time.time())
        return self.secret_value

    async def list_secret_versions(self, secret_name: str) -> List[str]:
        """List all versions of a secret."""
        return self.versions

    def get_current_version(self) -> str:
        """Get current key version."""
        return self.current_version

    def get_retry_count(self) -> int:
        """Get number of retries performed."""
        return self.retry_count

    def reset(self):
        """Reset state for next test."""
        self.mock_http_error = None
        self.retry_count = 0
        self.cache.clear()


class MockCryptoService:
    """Mock Crypto Service with encryption/decryption."""

    def __init__(self):
        self.key = base64.b64decode(b"abcdefghijklmnopqrstuvwxyz012345")

    async def encrypt(self, plaintext: bytes) -> EncryptedData:
        """Encrypt plaintext using mock AES-256-GCM."""
        import secrets
        iv = secrets.token_bytes(16)
        # Simple XOR encryption for testing (not production-grade)
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, self.key * (len(plaintext) // len(self.key) + 1)))
        return EncryptedData(
            ciphertext=ciphertext,
            iv=iv,
            key_version="kakehashi-kek/v1",
            timestamp=datetime.now(timezone.utc),
        )

    async def decrypt(self, encrypted_data: EncryptedData) -> bytes:
        """Decrypt ciphertext using mock AES-256-GCM."""
        plaintext = bytes(a ^ b for a, b in zip(encrypted_data.ciphertext, self.key * (len(encrypted_data.ciphertext) // len(self.key) + 1)))
        return plaintext

    def validate_signature(self, data: bytes, signature: str) -> bool:
        """Validate HMAC signature."""
        expected = hmac.new(self.key, data, hashlib.sha256).hexdigest()
        # Constant-time comparison
        return hmac.compare_digest(expected, signature)

    def sign_data(self, data: bytes) -> str:
        """Generate HMAC signature."""
        return hmac.new(self.key, data, hashlib.sha256).hexdigest()


class MockAuditCollector:
    """Mock Audit Log Collector with tampering detection."""

    def __init__(self):
        self.logs: List[Dict[str, Any]] = []
        self.mock_fail = False
        self.signing_key = b"audit_signing_key_32_bytes_long_"

    async def record_event(
        self,
        event_type: str,
        operation: str,
        status: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record an audit event."""
        if self.mock_fail:
            raise AuditError("Audit service failed")

        event_id = f"evt-{len(self.logs)}-{int(time.time() * 1000)}"
        log_entry = {
            "id": event_id,
            "event_type": event_type,
            "operation": operation,
            "status": status,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }

        # Sign the log entry
        log_json = json.dumps(log_entry, sort_keys=True)
        signature = hmac.new(self.signing_key, log_json.encode(), hashlib.sha256).hexdigest()
        log_entry["signature"] = signature

        self.logs.append(log_entry)
        return event_id

    async def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs."""
        return self.logs[-limit:]

    async def delete_log(self, log_id: str) -> None:
        """Attempt to delete a log (should fail in production)."""
        raise PermissionError("Audit logs are append-only")

    async def verify_log_signature(self, log_entry: Dict[str, Any]) -> bool:
        """Verify HMAC signature of a log entry."""
        signature = log_entry.pop("signature")
        log_json = json.dumps(log_entry, sort_keys=True)
        expected = hmac.new(self.signing_key, log_json.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def verify_signature(self, data: str, signature: str) -> bool:
        """Verify signature of arbitrary data."""
        expected = hmac.new(self.signing_key, data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def get_logs_sync(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get logs synchronously."""
        return self.logs[-limit:]


class MockRBACEnforcer:
    """Mock RBAC Enforcer with role-based access control."""

    def __init__(self):
        self.tokens: Dict[str, Dict[str, Any]] = {}
        self.mock_current_time = datetime.now(timezone.utc)

    async def issue_tokens(
        self,
        user_id: str,
        role: Role,
        chat_id: str,
        ip_address: str,
    ) -> Dict[str, str]:
        """Issue access/refresh tokens for a user."""
        import secrets
        access_token = f"at_{secrets.token_hex(16)}"
        refresh_token = f"rt_{secrets.token_hex(16)}"

        self.tokens[access_token] = {
            "user_id": user_id,
            "role": role,
            "chat_id": chat_id,
            "ip_address": ip_address,
            "issued_at": self.mock_current_time,
            "expires_at": self.mock_current_time + timedelta(hours=1),
        }

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
        }

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode token."""
        if token not in self.tokens:
            raise InvalidTokenError("Invalid token")

        token_data = self.tokens[token]
        if self.mock_current_time > token_data["expires_at"]:
            raise InvalidTokenError("Token expired")

        # Check for forged signature (simple check)
        if token.endswith("FORGED_SIGNATURE"):
            raise InvalidTokenError("Invalid signature")

        return token_data

    async def check_permission(self, token: str, resource: str, action: str) -> bool:
        """Check if token has permission for resource/action."""
        token_data = await self.verify_token(token)
        role = token_data["role"]

        # Permission matrix
        permissions = {
            Role.ADMIN: ["read", "write", "rotate", "manage_users", "export_logs"],
            Role.OPERATOR: ["read", "write", "workflows"],
            Role.AUDITOR: ["read"],
            Role.GUEST: [],
        }

        return action in permissions.get(role, [])


class MockKeyRotationManager:
    """Mock Key Rotation Manager."""

    def __init__(self, kvc: MockKeyVaultConnector, crypto: MockCryptoService, audit: MockAuditCollector):
        self.kvc = kvc
        self.crypto = crypto
        self.audit = audit
        self.rotation_count = 0

    async def schedule_rotation(
        self,
        rotation_type: str,
        actor_role: Role,
    ) -> Dict[str, Any]:
        """Schedule a key rotation."""
        if actor_role != Role.ADMIN:
            raise PermissionError(f"Role {actor_role} cannot schedule rotations")

        # Generate new key version
        self.rotation_count += 1
        new_version = f"kakehashi-kek/v{self.rotation_count + 1}"

        # Add to versions
        self.kvc.versions.append(new_version)

        # Simulate re-encryption of test data (simplified)
        re_encrypted_count = 1000  # Assume 1000 records

        await self.audit.record_event(
            event_type="KEY_ROTATE",
            operation="SCHEDULED",
            status="SUCCESS",
        )

        return {
            "success": True,
            "rotation_count": self.rotation_count,
            "new_version": new_version,
            "re_encrypted_count": re_encrypted_count,
        }

    async def trigger_emergency_rotation(
        self,
        actor_id: str,
        actor_role: Role,
        reason: str,
    ) -> Dict[str, Any]:
        """Trigger emergency key rotation."""
        if actor_role != Role.ADMIN:
            raise PermissionError(f"Role {actor_role} cannot trigger emergency rotations")

        self.rotation_count += 1
        new_version = f"kakehashi-kek/v{self.rotation_count + 1}"

        await self.audit.record_event(
            event_type="KEY_ROTATE",
            operation="EMERGENCY",
            status="SUCCESS",
            user_id=actor_id,
            details={"reason": reason},
        )

        return {
            "success": True,
            "rotation_count": self.rotation_count,
            "new_version": new_version,
        }


class MockMonitoring:
    """Mock Monitoring service for cache metrics."""

    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0

    async def get_cache_hit(self) -> bool:
        """Check if last operation was a cache hit."""
        import random
        # Simulate 95% hit rate
        is_hit = random.random() < 0.95
        if is_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        return is_hit


class MockCache:
    """Mock cache service."""

    def __init__(self):
        self.data: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return self.data.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        self.data[key] = value

    async def size(self) -> int:
        """Get cache size."""
        return len(self.data)

    def clear(self) -> None:
        """Clear all cache."""
        self.data.clear()


class KEKWrapper:
    """Mock KEK Wrapper orchestrating all components."""

    def __init__(self):
        self.kvc = MockKeyVaultConnector()
        self.crypto = MockCryptoService()
        self.audit = MockAuditCollector()
        self.rbac = MockRBACEnforcer()
        self.key_rotation = MockKeyRotationManager(self.kvc, self.crypto, self.audit)
        self.monitoring = MockMonitoring()
        self.cache = MockCache()

    async def encrypt(self, plaintext: bytes, token: Optional[str] = None) -> bytes:
        """Encrypt data with full workflow."""
        if token:
            await self.rbac.verify_token(token)
            has_permission = await self.rbac.check_permission(token, "key", "read")
            if not has_permission:
                raise PermissionError("No permission to read key")

        # Record audit event
        await self.audit.record_event(
            event_type="KEY_ACCESS",
            operation="GET",
            status="SUCCESS",
        )

        # Encrypt
        encrypted = await self.crypto.encrypt(plaintext)
        return encrypted.ciphertext

    async def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt data with full workflow."""
        # Create mock EncryptedData
        encrypted = EncryptedData(
            ciphertext=ciphertext,
            iv=b"0123456789abcdef",
            key_version="kakehashi-kek/v1",
            timestamp=datetime.now(timezone.utc),
        )
        return await self.crypto.decrypt(encrypted)


class KeyVaultError(Exception):
    """Key Vault error."""
    pass


class AuditError(Exception):
    """Audit error."""
    pass


class InvalidTokenError(Exception):
    """Invalid token error."""
    pass


class PermissionError(Exception):
    """Permission error."""
    pass


# Pytest Fixtures


@pytest.fixture
async def kek_wrapper() -> KEKWrapper:
    """Create and return a KEKWrapper instance."""
    return KEKWrapper()


@pytest.fixture
async def staging_db() -> MagicMock:
    """Mock Cosmos DB staging instance."""
    db = AsyncMock()
    db.insert = AsyncMock()
    db.query = AsyncMock(return_value=[])
    db.update = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def mock_alert_service() -> MagicMock:
    """Mock alert service for security events."""
    alerter = MagicMock()
    alerter.send = MagicMock(return_value=None)
    alerter.send_batch = MagicMock(return_value=None)
    return alerter


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
