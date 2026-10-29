"""JWT Token Manager for Task 3.1.

Handles JWT token issuance, verification, and refresh for RBAC.
Tokens include role, user_id, chat_id, and IP address for audit purposes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt

from kakehashi.kek_wrapper.models.role import Role


class JWTManager:
    """JWT token manager for access and refresh tokens."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """Initialize JWT manager.

        Args:
            secret_key: Secret key for signing tokens (from Key Vault)
            algorithm: JWT signature algorithm (default: HS256)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expiry = timedelta(hours=1)  # 1 hour
        self.refresh_token_expiry = timedelta(days=1)   # 24 hours

    def issue_tokens(
        self,
        user_id: str,
        role: Role,
        chat_id: str,
        ip_address: str,
    ) -> Dict[str, str]:
        """Issue JWT token pair (access + refresh).

        Args:
            user_id: User identifier
            role: Role enum (ADMIN, OPERATOR, AUDITOR, GUEST)
            chat_id: Chat/session identifier
            ip_address: Client IP address for audit

        Returns:
            Dictionary with:
                - access_token: JWT access token
                - refresh_token: JWT refresh token
                - expires_in: Access token expiry in seconds
                - token_type: Bearer

        Raises:
            ValueError: If role is not a valid Role enum
        """
        if not isinstance(role, Role):
            raise ValueError(f"Invalid role: {role}")

        now = datetime.utcnow()

        # Create access token payload
        access_payload = {
            "user_id": user_id,
            "role": role.value,
            "chat_id": chat_id,
            "token_type": "access",
            "iat": now,
            "exp": now + self.access_token_expiry,
            "ip_address": ip_address,
        }
        access_token = jwt.encode(
            access_payload,
            self.secret_key,
            algorithm=self.algorithm
        )

        # Create refresh token payload
        refresh_payload = {
            "user_id": user_id,
            "token_type": "refresh",
            "iat": now,
            "exp": now + self.refresh_token_expiry,
        }
        refresh_token = jwt.encode(
            refresh_payload,
            self.secret_key,
            algorithm=self.algorithm
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": int(self.access_token_expiry.total_seconds()),
            "token_type": "Bearer",
        }

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload as dictionary

        Raises:
            ValueError: If token is expired, has invalid signature, or fails to decode
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidSignatureError:
            raise ValueError("Invalid token signature")
        except jwt.DecodeError:
            raise ValueError("Failed to decode token")

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Issue new access token from a valid refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access token string

        Raises:
            ValueError: If refresh token is invalid or not a refresh token

        Note:
            This is a stub that returns None. Full implementation requires
            fetching user role from database (Task 3.2+).
        """
        payload = self.verify_token(refresh_token)

        if payload.get("token_type") != "refresh":
            raise ValueError("Token is not a refresh token")

        # Stub: returning None until Task 3.2 implements user DB lookup
        return None
