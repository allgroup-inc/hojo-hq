"""Tests for RBAC Enforcer (Task 3.1)."""

import asyncio

import pytest

from kakehashi.kek_wrapper.core.jwt_manager import JWTManager
from kakehashi.kek_wrapper.core.rbac_enforcer import RBACEnforcer
from kakehashi.kek_wrapper.models.role import Role


@pytest.fixture
def jwt_manager():
    """Create a JWT manager for testing."""
    return JWTManager(secret_key="test-secret-key")


@pytest.fixture
def rbac_enforcer(jwt_manager):
    """Create an RBAC enforcer for testing."""
    return RBACEnforcer(jwt_manager)


def test_admin_has_full_access(rbac_enforcer):
    """Admin role has access to all resources and operations."""
    # KEY_VAULT operations
    assert rbac_enforcer.has_permission(Role.ADMIN, "KEY_VAULT", "GET")
    assert rbac_enforcer.has_permission(Role.ADMIN, "KEY_VAULT", "PUT")
    assert rbac_enforcer.has_permission(Role.ADMIN, "KEY_VAULT", "DELETE")
    assert rbac_enforcer.has_permission(Role.ADMIN, "KEY_VAULT", "ROTATE")
    assert rbac_enforcer.has_permission(Role.ADMIN, "KEY_VAULT", "EXPORT")

    # USER_MANAGEMENT operations
    assert rbac_enforcer.has_permission(Role.ADMIN, "USER_MANAGEMENT", "CREATE")
    assert rbac_enforcer.has_permission(Role.ADMIN, "USER_MANAGEMENT", "UPDATE")
    assert rbac_enforcer.has_permission(Role.ADMIN, "USER_MANAGEMENT", "DELETE")
    assert rbac_enforcer.has_permission(Role.ADMIN, "USER_MANAGEMENT", "ASSIGN_ROLE")

    # AUDIT_LOG operations
    assert rbac_enforcer.has_permission(Role.ADMIN, "AUDIT_LOG", "EXPORT")
    assert rbac_enforcer.has_permission(Role.ADMIN, "AUDIT_LOG", "VIEW_FULL")


def test_operator_limited_access(rbac_enforcer):
    """Operator role has limited access: data R/W, own logs, workflow."""
    # DATABASE operations
    assert rbac_enforcer.has_permission(Role.OPERATOR, "DATABASE", "GET")
    assert rbac_enforcer.has_permission(Role.OPERATOR, "DATABASE", "PUT")

    # WORKFLOW operations
    assert rbac_enforcer.has_permission(Role.OPERATOR, "WORKFLOW", "EXECUTE")

    # AUDIT_LOG operations
    assert rbac_enforcer.has_permission(Role.OPERATOR, "AUDIT_LOG", "VIEW_OWN")

    # Operator cannot access KEY_VAULT or USER_MANAGEMENT
    assert not rbac_enforcer.has_permission(Role.OPERATOR, "KEY_VAULT", "ROTATE")
    assert not rbac_enforcer.has_permission(Role.OPERATOR, "KEY_VAULT", "GET")
    assert not rbac_enforcer.has_permission(Role.OPERATOR, "USER_MANAGEMENT", "DELETE")
    assert not rbac_enforcer.has_permission(Role.OPERATOR, "USER_MANAGEMENT", "CREATE")


def test_auditor_read_only(rbac_enforcer):
    """Auditor role is read-only: audit logs and compliance checks."""
    # AUDIT_LOG operations
    assert rbac_enforcer.has_permission(Role.AUDITOR, "AUDIT_LOG", "VIEW_FULL")
    assert rbac_enforcer.has_permission(Role.AUDITOR, "AUDIT_LOG", "VALIDATE")
    assert rbac_enforcer.has_permission(Role.AUDITOR, "AUDIT_LOG", "EXPORT_REPORT")

    # Auditor cannot write or access KEY_VAULT
    assert not rbac_enforcer.has_permission(Role.AUDITOR, "DATABASE", "PUT")
    assert not rbac_enforcer.has_permission(Role.AUDITOR, "DATABASE", "GET")
    assert not rbac_enforcer.has_permission(Role.AUDITOR, "KEY_VAULT", "GET")
    assert not rbac_enforcer.has_permission(Role.AUDITOR, "KEY_VAULT", "ROTATE")
    assert not rbac_enforcer.has_permission(Role.AUDITOR, "WORKFLOW", "EXECUTE")


def test_guest_limited_read(rbac_enforcer):
    """Guest role has minimal access: read-only on non-sensitive data."""
    # DATABASE read only
    assert rbac_enforcer.has_permission(Role.GUEST, "DATABASE", "GET")

    # Guest cannot write, access KEY_VAULT, AUDIT_LOG, or USER_MANAGEMENT
    assert not rbac_enforcer.has_permission(Role.GUEST, "DATABASE", "PUT")
    assert not rbac_enforcer.has_permission(Role.GUEST, "KEY_VAULT", "GET")
    assert not rbac_enforcer.has_permission(Role.GUEST, "KEY_VAULT", "ROTATE")
    assert not rbac_enforcer.has_permission(Role.GUEST, "AUDIT_LOG", "VIEW_FULL")
    assert not rbac_enforcer.has_permission(Role.GUEST, "AUDIT_LOG", "VIEW_OWN")
    assert not rbac_enforcer.has_permission(Role.GUEST, "USER_MANAGEMENT", "DELETE")
    assert not rbac_enforcer.has_permission(Role.GUEST, "WORKFLOW", "EXECUTE")


def test_invalid_role(rbac_enforcer):
    """Invalid role returns False for any permission check."""
    # Create a fake role object that's not in ROLE_PERMISSIONS
    class FakeRole:
        value = "fake"

    fake_role = FakeRole()
    assert not rbac_enforcer.has_permission(fake_role, "DATABASE", "GET")


def test_unknown_resource_type(rbac_enforcer):
    """Unknown resource type returns False for admin role."""
    assert not rbac_enforcer.has_permission(Role.ADMIN, "UNKNOWN_RESOURCE", "GET")


def test_unknown_operation(rbac_enforcer):
    """Unknown operation returns False even for admin role."""
    assert not rbac_enforcer.has_permission(Role.ADMIN, "KEY_VAULT", "UNKNOWN_OP")


def test_require_role_allows_authorized_role(rbac_enforcer):
    """Decorator allows function execution for authorized roles."""
    @rbac_enforcer.require_role(Role.ADMIN, Role.AUDITOR)
    async def protected_endpoint(current_user):
        return "success"

    result = asyncio.run(protected_endpoint(current_user={"role": "admin"}))
    assert result == "success"


def test_require_role_denies_unauthorized_role(rbac_enforcer):
    """Decorator denies function execution for unauthorized roles."""
    @rbac_enforcer.require_role(Role.ADMIN)
    async def protected_endpoint(current_user):
        return "success"

    with pytest.raises(PermissionError, match="not allowed"):
        asyncio.run(protected_endpoint(current_user={"role": "guest"}))


def test_require_role_requires_context(rbac_enforcer):
    """Decorator requires user context."""
    @rbac_enforcer.require_role(Role.ADMIN)
    async def protected_endpoint(current_user):
        return "success"

    with pytest.raises(ValueError, match="User context required"):
        asyncio.run(protected_endpoint(current_user=None))


def test_require_permission_allows_authorized_operation(rbac_enforcer):
    """Decorator allows function execution for authorized operations."""
    @rbac_enforcer.require_permission("KEY_VAULT", "ROTATE")
    async def rotate_key(current_user):
        return "rotated"

    result = asyncio.run(rotate_key(current_user={"role": "admin"}))
    assert result == "rotated"


def test_require_permission_denies_unauthorized_operation(rbac_enforcer):
    """Decorator denies function execution for unauthorized operations."""
    @rbac_enforcer.require_permission("KEY_VAULT", "ROTATE")
    async def rotate_key(current_user):
        return "rotated"

    with pytest.raises(PermissionError, match="not allowed"):
        asyncio.run(rotate_key(current_user={"role": "guest"}))


def test_require_permission_requires_context(rbac_enforcer):
    """Decorator requires user context for permission check."""
    @rbac_enforcer.require_permission("KEY_VAULT", "GET")
    async def get_key(current_user):
        return "key_data"

    with pytest.raises(ValueError, match="User context required"):
        asyncio.run(get_key(current_user=None))
