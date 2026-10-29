"""Integration tests for RBAC enforcement (Task 3.4).

Tests role-based access control for all 4 roles:
- ADMIN: Full access to all resources
- OPERATOR: Limited access (key read/write, workflows)
- AUDITOR: Read-only audit logs
- GUEST: No access to keys
"""

import pytest

from conftest import InvalidTokenError, KEKWrapper, PermissionError
from kakehashi.kek_wrapper.models.crypto_models import Role, RotationType


class TestRBACAccessControl:
    """Integration tests for RBAC enforcement."""

    @pytest.mark.asyncio
    async def test_admin_full_access(self, kek_wrapper: KEKWrapper):
        """Test ADMIN role has full access."""
        admin_token = await kek_wrapper.rbac.issue_tokens(
            user_id="admin_user",
            role=Role.ADMIN,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Key rotation (admin only)
        result = await kek_wrapper.key_rotation.schedule_rotation(
            rotation_type="SCHEDULED",
            actor_role=Role.ADMIN,
        )
        assert result["success"]

        # User management (admin only) - check token issuance
        token_data = await kek_wrapper.rbac.verify_token(admin_token["access_token"])
        assert token_data["role"] == Role.ADMIN

        # Audit logs access (admin can export)
        logs = await kek_wrapper.audit.get_logs()
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_operator_limited_access(self, kek_wrapper: KEKWrapper):
        """Test OPERATOR role has limited access."""
        operator_token = await kek_wrapper.rbac.issue_tokens(
            user_id="operator_user",
            role=Role.OPERATOR,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Key read/write (OK)
        ciphertext = await kek_wrapper.encrypt(b"data")
        assert ciphertext is not None

        # Key rotation (NG)
        with pytest.raises(PermissionError):
            await kek_wrapper.key_rotation.schedule_rotation(
                rotation_type="SCHEDULED",
                actor_role=Role.OPERATOR,
            )

        # Verify token
        token_data = await kek_wrapper.rbac.verify_token(operator_token["access_token"])
        assert token_data["role"] == Role.OPERATOR

    @pytest.mark.asyncio
    async def test_auditor_read_only(self, kek_wrapper: KEKWrapper):
        """Test AUDITOR role is read-only."""
        auditor_token = await kek_wrapper.rbac.issue_tokens(
            user_id="auditor_user",
            role=Role.AUDITOR,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Audit logs read (OK)
        logs = await kek_wrapper.audit.get_logs()
        assert isinstance(logs, list)

        # Key access (NG)
        with pytest.raises(PermissionError):
            await kek_wrapper.encrypt(b"data", token=auditor_token["access_token"])

    @pytest.mark.asyncio
    async def test_guest_no_access(self, kek_wrapper: KEKWrapper):
        """Test GUEST role has no access to keys."""
        guest_token = await kek_wrapper.rbac.issue_tokens(
            user_id="guest_user",
            role=Role.GUEST,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Key access (NG)
        with pytest.raises(PermissionError):
            await kek_wrapper.encrypt(b"data", token=guest_token["access_token"])

    @pytest.mark.asyncio
    async def test_token_signature_tampering_rejected(self, kek_wrapper: KEKWrapper):
        """Test token signature tampering is rejected."""
        token = await kek_wrapper.rbac.issue_tokens(
            user_id="user",
            role=Role.OPERATOR,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Tamper with token signature
        parts = token["access_token"].split(".")
        if len(parts) == 3:
            forged_token = f"{parts[0]}.{parts[1]}.FORGED_SIGNATURE"

            with pytest.raises(InvalidTokenError):
                await kek_wrapper.rbac.verify_token(forged_token)

    @pytest.mark.asyncio
    async def test_permission_check_for_resource_action(self, kek_wrapper: KEKWrapper):
        """Test permission checking for specific resource/action."""
        admin_token = await kek_wrapper.rbac.issue_tokens(
            user_id="admin_user",
            role=Role.ADMIN,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Admin can manage users
        has_perm = await kek_wrapper.rbac.check_permission(
            admin_token["access_token"],
            "users",
            "manage_users",
        )
        assert has_perm

    @pytest.mark.asyncio
    async def test_token_expiration_check(self, kek_wrapper: KEKWrapper):
        """Test token expiration validation."""
        token = await kek_wrapper.rbac.issue_tokens(
            user_id="user",
            role=Role.OPERATOR,
            chat_id="test",
            ip_address="127.0.0.1",
        )

        # Valid token
        token_data = await kek_wrapper.rbac.verify_token(token["access_token"])
        assert token_data["role"] == Role.OPERATOR

        # Expire token
        from datetime import timedelta
        kek_wrapper.rbac.mock_current_time = token_data["expires_at"] + timedelta(seconds=1)

        with pytest.raises(InvalidTokenError):
            await kek_wrapper.rbac.verify_token(token["access_token"])

    @pytest.mark.asyncio
    async def test_multiple_roles_permissions_matrix(self, kek_wrapper: KEKWrapper):
        """Test permission matrix for all roles."""
        roles_to_test = [
            (Role.ADMIN, ["read", "write", "rotate", "manage_users", "export_logs"]),
            (Role.OPERATOR, ["read", "write", "workflows"]),
            (Role.AUDITOR, ["read"]),
            (Role.GUEST, []),
        ]

        for role, expected_actions in roles_to_test:
            token = await kek_wrapper.rbac.issue_tokens(
                user_id=f"user_{role}",
                role=role,
                chat_id="test",
                ip_address="127.0.0.1",
            )

            for action in expected_actions:
                has_perm = await kek_wrapper.rbac.check_permission(
                    token["access_token"],
                    "resource",
                    action,
                )
                assert has_perm, f"{role} should have {action} permission"

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self, kek_wrapper: KEKWrapper):
        """Test invalid token is rejected."""
        with pytest.raises(InvalidTokenError):
            await kek_wrapper.rbac.verify_token("invalid_token")
