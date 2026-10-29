"""RBAC (Role-Based Access Control) models for Task 3.1.

Defines the Permission dataclass and ROLE_PERMISSIONS matrix that maps
each role to a set of permissions for specific resources and operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

from .role import Role


@dataclass
class Permission:
    """Permission to perform operations on a resource type.

    Attributes:
        name: Unique permission identifier (e.g., "full_access")
        description: Human-readable description of the permission
        resource_type: Type of resource (KEY_VAULT, DATABASE, AUDIT_LOG, USER_MANAGEMENT, WORKFLOW)
        operations: Set of allowed operations on this resource (GET, PUT, DELETE, ROTATE, etc.)
    """

    name: str
    description: str
    resource_type: str
    operations: Set[str]


# Role-to-Permissions mapping matrix
# ADMIN: 4 permissions (full_access, user_management, audit_export, key_rotation)
# OPERATOR: 3 permissions (data_rw, own_logs, workflow)
# AUDITOR: 2 permissions (audit_read, compliance_check)
# GUEST: 1 permission (limited_read)
# Total: 10 permissions, 30+ operations across resource types

ROLE_PERMISSIONS: dict[Role, List[Permission]] = {
    Role.ADMIN: [
        Permission(
            name="full_access",
            description="キー・ユーザー・監査ログの全操作",
            resource_type="KEY_VAULT",
            operations={"GET", "PUT", "DELETE", "ROTATE", "EXPORT"}
        ),
        Permission(
            name="user_management",
            description="ユーザー作成・削除・ロール変更",
            resource_type="USER_MANAGEMENT",
            operations={"CREATE", "UPDATE", "DELETE", "ASSIGN_ROLE"}
        ),
        Permission(
            name="audit_export",
            description="監査ログの外部 SIEM へのエクスポート",
            resource_type="AUDIT_LOG",
            operations={"EXPORT", "VIEW_FULL"}
        ),
        Permission(
            name="key_rotation",
            description="定期・緊急キーローテーション",
            resource_type="KEY_VAULT",
            operations={"ROTATE", "EMERGENCY_ROTATE"}
        ),
    ],
    Role.OPERATOR: [
        Permission(
            name="data_rw",
            description="データの読み書き",
            resource_type="DATABASE",
            operations={"GET", "PUT"}
        ),
        Permission(
            name="own_logs",
            description="自分のログエントリのみ閲覧",
            resource_type="AUDIT_LOG",
            operations={"VIEW_OWN"}
        ),
        Permission(
            name="workflow",
            description="ワークフロー実行",
            resource_type="WORKFLOW",
            operations={"EXECUTE"}
        ),
    ],
    Role.AUDITOR: [
        Permission(
            name="audit_read",
            description="監査ログ読み取り(全件)",
            resource_type="AUDIT_LOG",
            operations={"VIEW_FULL"}
        ),
        Permission(
            name="compliance_check",
            description="コンプライアンスチェック実行",
            resource_type="AUDIT_LOG",
            operations={"VALIDATE", "EXPORT_REPORT"}
        ),
    ],
    Role.GUEST: [
        Permission(
            name="limited_read",
            description="非機密データの読み取りのみ",
            resource_type="DATABASE",
            operations={"GET"}
        ),
    ],
}
