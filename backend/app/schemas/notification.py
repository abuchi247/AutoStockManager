"""Pydantic schemas for notification endpoints.

Defines request/response models for notification listing and read-status management.

Satisfies Requirements: 16.5, 16.6
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Response Schemas
# =============================================================================


class NotificationResponse(BaseModel):
    """Response body for a single notification."""

    id: UUID = Field(..., description="Notification UUID")
    user_id: UUID = Field(..., description="User who received this notification")
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., description="Short notification title")
    message: str = Field(..., description="Full notification message")
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Optional context-specific metadata"
    )
    is_read: bool = Field(..., description="Whether the notification has been read")
    read_at: Optional[datetime] = Field(
        default=None, description="Timestamp when marked as read"
    )
    created_at: Optional[datetime] = Field(
        default=None, description="When the notification was created"
    )

    model_config = {"from_attributes": True}

    @classmethod
    def from_notification(cls, notification) -> "NotificationResponse":
        """Create a response from a Notification model instance.

        Handles the extra_data -> metadata field mapping.
        """
        return cls(
            id=notification.id,
            user_id=notification.user_id,
            notification_type=notification.notification_type,
            title=notification.title,
            message=notification.message,
            metadata=notification.extra_data,
            is_read=notification.is_read,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )


class NotificationListResponse(BaseModel):
    """Response body for notification list with pagination metadata."""

    data: list[NotificationResponse] = Field(
        ..., description="List of notifications"
    )
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )


class MarkAllReadResponse(BaseModel):
    """Response body for mark-all-read operation."""

    marked_count: int = Field(
        ..., description="Number of notifications marked as read"
    )
