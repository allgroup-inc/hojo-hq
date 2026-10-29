"""Role enum: System role definitions for audit logging.

Phase E, Task 1.1 (Decision B+C: Role Enum prior to Task 1.3).

Roles represent the actor's privilege level in audit log records. The system
defines 4 roles; system-internal operations use ADMIN or OPERATOR (no separate
"system" role in audit output).

Audit records always use one of these roles:
  * ADMIN: administrative operations (key rotation, user management, policy)
  * OPERATOR: operational access (secret retrieval, scheduled tasks)
  * AUDITOR: read-only access for compliance review
  * GUEST: minimal access (e.g., health checks)

Internal operations (e.g., KeyVaultConnector initialization) that have no
end-user actor are recorded as OPERATOR.
"""

from enum import Enum
from typing import Optional


class Role(Enum):
    """System role enumeration for audit logging.

    Each role has a string value matching the spec (section 1.3, Table 2).
    """

    ADMIN = "admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    GUEST = "guest"

    @classmethod
    def from_string(cls, value: Optional[str]) -> "Role":
        """Convert a string to a Role enum, or raise ValueError if invalid.

        Args:
            value: the role name as a string (e.g. "admin")

        Returns:
            Role enum member (e.g. Role.ADMIN)

        Raises:
            ValueError: if value is not a valid role name.
        """
        if not value:
            raise ValueError("role value cannot be empty")
        try:
            return cls(value)
        except ValueError:
            allowed = ", ".join(f'"{r.value}"' for r in cls)
            raise ValueError(
                f"invalid role {value!r}. allowed roles: {allowed}"
            ) from None
