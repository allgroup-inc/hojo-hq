"""Tests for JWT Manager (Task 3.1)."""

import pytest

from kakehashi.kek_wrapper.core.jwt_manager import JWTManager
from kakehashi.kek_wrapper.models.role import Role


@pytest.fixture
def jwt_manager():
    """Create a JWT manager for testing."""
    return JWTManager(secret_key="test-secret-key")


def test_issue_tokens_returns_access_and_refresh(jwt_manager):
    """JWT manager issues both access and refresh tokens."""
    tokens = jwt_manager.issue_tokens(
        user_id="user123",
        role=Role.ADMIN,
        chat_id="chat001",
        ip_address="192.0.2.1"
    )

    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] == 3600  # 1 hour in seconds
    assert isinstance(tokens["access_token"], str)
    assert isinstance(tokens["refresh_token"], str)


def test_verify_token_decodes_valid_token(jwt_manager):
    """Valid access token can be decoded and verified."""
    tokens = jwt_manager.issue_tokens(
        user_id="user123",
        role=Role.OPERATOR,
        chat_id="chat001",
        ip_address="192.0.2.1"
    )

    payload = jwt_manager.verify_token(tokens["access_token"])
    assert payload["user_id"] == "user123"
    assert payload["role"] == "operator"
    assert payload["chat_id"] == "chat001"
    assert payload["token_type"] == "access"
    assert payload["ip_address"] == "192.0.2.1"


def test_verify_token_rejects_invalid_signature(jwt_manager):
    """Token with tampered signature is rejected."""
    tokens = jwt_manager.issue_tokens(
        user_id="user123",
        role=Role.ADMIN,
        chat_id="chat001",
        ip_address="192.0.2.1"
    )

    # Tamper with token
    tampered_token = tokens["access_token"] + "tampered"

    with pytest.raises(ValueError, match="Invalid token signature"):
        jwt_manager.verify_token(tampered_token)


def test_issue_tokens_rejects_invalid_role(jwt_manager):
    """Issuing tokens with invalid role raises ValueError."""
    with pytest.raises(ValueError, match="Invalid role"):
        jwt_manager.issue_tokens(
            user_id="user123",
            role="invalid_role",  # String instead of Role enum
            chat_id="chat001",
            ip_address="192.0.2.1"
        )


def test_refresh_token_type_validation(jwt_manager):
    """Using access token as refresh token raises ValueError."""
    tokens = jwt_manager.issue_tokens(
        user_id="user123",
        role=Role.ADMIN,
        chat_id="chat001",
        ip_address="192.0.2.1"
    )

    # Try to use access token as refresh token
    with pytest.raises(ValueError, match="not a refresh token"):
        jwt_manager.refresh_access_token(tokens["access_token"])


def test_verify_token_with_different_roles(jwt_manager):
    """Tokens are issued correctly for all role types."""
    for role in [Role.ADMIN, Role.OPERATOR, Role.AUDITOR, Role.GUEST]:
        tokens = jwt_manager.issue_tokens(
            user_id=f"user_{role.value}",
            role=role,
            chat_id="chat001",
            ip_address="192.0.2.1"
        )

        payload = jwt_manager.verify_token(tokens["access_token"])
        assert payload["role"] == role.value


def test_verify_invalid_token_format(jwt_manager):
    """Invalid token format raises ValueError."""
    with pytest.raises(ValueError, match="Failed to decode token"):
        jwt_manager.verify_token("not.a.valid.token")
