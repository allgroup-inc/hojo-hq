"""RBAC Enforcer for Task 3.1.

Provides decorators (@require_role, @require_permission) to enforce
role-based and resource-based access control on API endpoints.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from kakehashi.kek_wrapper.core.jwt_manager import JWTManager
from kakehashi.kek_wrapper.models.rbac_models import ROLE_PERMISSIONS
from kakehashi.kek_wrapper.models.role import Role


class RBACEnforcer:
    """Enforces role-based access control on API endpoints."""

    def __init__(self, jwt_manager: JWTManager):
        """Initialize RBAC enforcer.

        Args:
            jwt_manager: JWTManager instance for token verification
        """
        self.jwt_manager = jwt_manager

    def has_permission(
        self,
        role: Role,
        resource_type: str,
        operation: str,
    ) -> bool:
        """Check if a role has permission for a resource operation.

        Args:
            role: User role
            resource_type: Resource type (KEY_VAULT, DATABASE, AUDIT_LOG, etc.)
            operation: Operation (GET, PUT, ROTATE, etc.)

        Returns:
            True if role has permission, False otherwise
        """
        if role not in ROLE_PERMISSIONS:
            return False

        permissions = ROLE_PERMISSIONS[role]
        for perm in permissions:
            if perm.resource_type == resource_type and operation in perm.operations:
                return True

        return False

    def require_role(
        self,
        *allowed_roles: Role
    ) -> Callable:
        """Decorator to require specific roles for endpoint access.

        Usage:
            @rbac.require_role(Role.ADMIN, Role.AUDITOR)
            async def get_audit_logs(self, current_user: dict):
                ...

        Args:
            *allowed_roles: Allowed Role enum values

        Returns:
            Decorator function

        Raises:
            ValueError: If current_user context is not provided
            PermissionError: If user's role is not in allowed_roles
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract current_user from kwargs
                current_user = kwargs.get("current_user")
                if not current_user:
                    raise ValueError("User context required")

                user_role = current_user.get("role")
                allowed_role_values = [r.value for r in allowed_roles]

                if user_role not in allowed_role_values:
                    raise PermissionError(
                        f"Role {user_role} not allowed. "
                        f"Requires one of: {allowed_role_values}"
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def require_permission(
        self,
        resource_type: str,
        operation: str,
    ) -> Callable:
        """Decorator to require specific resource/operation permissions.

        Usage:
            @rbac.require_permission("KEY_VAULT", "ROTATE")
            async def rotate_key(self, current_user: dict):
                ...

        Args:
            resource_type: Resource type to check
            operation: Operation to check

        Returns:
            Decorator function

        Raises:
            ValueError: If current_user context is not provided
            PermissionError: If role lacks permission for resource/operation
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract current_user from kwargs
                current_user = kwargs.get("current_user")
                if not current_user:
                    raise ValueError("User context required")

                role_str = current_user.get("role")
                try:
                    role = Role(role_str)
                except ValueError:
                    raise PermissionError(f"Invalid role: {role_str}")

                if not self.has_permission(role, resource_type, operation):
                    raise PermissionError(
                        f"Role {role_str} not allowed for "
                        f"{operation} on {resource_type}"
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator
