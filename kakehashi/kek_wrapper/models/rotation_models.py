"""Key rotation models and enums (Phase E, Task 3.2).

Defines the data models for scheduled and emergency key rotation, including
rotation types, key version records, rotation status, and rotation results.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from .enums import Status
from .role import Role


class RotationType(str, Enum):
    """Type of key rotation operation."""

    SCHEDULED = "SCHEDULED"  # Periodic rotation (every 90 days)
    EMERGENCY = "EMERGENCY"  # Triggered by security incident
    MANUAL = "MANUAL"  # Manual rotation by administrator


class KeyVersionRecord(BaseModel):
    """Record of a key version in rotation history."""

    version: int = Field(..., description="Key Vault version number")
    created_at: datetime = Field(..., description="When this key version was created")
    rotation_type: RotationType = Field(
        ..., description="Type of rotation that created this version"
    )
    actor_id: str = Field(..., description="ID of the actor who initiated rotation")
    actor_role: Role = Field(..., description="Role of the actor")
    status: Status = Field(..., description="Rotation outcome (SUCCESS/FAILURE/PARTIAL)")
    re_encrypted_count: int = Field(
        default=0, description="Number of records re-encrypted with new key"
    )
    re_encryption_status: Optional[str] = Field(
        default=None,
        description="Re-encryption state: 'in_progress', 'completed', or 'rolled_back'",
    )


class RotationStatus(BaseModel):
    """Current key rotation status and schedule."""

    current_version: int = Field(..., description="Current active key version")
    current_created_at: datetime = Field(..., description="When current key was created")
    next_scheduled_rotation: datetime = Field(
        ..., description="Planned date for next scheduled rotation (90 days later)"
    )
    last_rotation_type: Optional[RotationType] = Field(
        default=None, description="Type of last completed rotation"
    )
    last_rotation_timestamp: Optional[datetime] = Field(
        default=None, description="Timestamp of last completed rotation"
    )
    is_rotation_in_progress: bool = Field(
        default=False, description="Whether a rotation is currently in progress"
    )


class RotationResult(BaseModel):
    """Outcome of a key rotation operation."""

    success: bool = Field(..., description="Whether rotation succeeded")
    new_version: int = Field(..., description="Version number of new key")
    old_version: int = Field(..., description="Version number of old key")
    rotation_type: RotationType = Field(..., description="Type of rotation")
    actor_role: Role = Field(..., description="Role of the initiating actor")
    started_at: datetime = Field(..., description="When rotation started (UTC)")
    completed_at: datetime = Field(..., description="When rotation completed (UTC)")
    re_encrypted_count: int = Field(
        default=0, description="Number of records successfully re-encrypted"
    )
    audit_event_id: str = Field(
        ..., description="Audit log event ID from AuditLogCollector.recordEvent()"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if rotation failed"
    )
