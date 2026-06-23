"""
Login history model for recording authentication attempts.

Tracks all login attempts (successful and failed) with contextual information
including timestamp, IP address, user agent, and outcome.

Satisfies Requirement 17.5:
THE Security_Manager SHALL record login history including timestamp, IP address,
user agent, and login success or failure status.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LoginHistory(Base):
    """Model recording every login attempt for security auditing.

    This is an append-only table — records are never updated or deleted.
    Each row represents a single authentication attempt with its outcome.

    Attributes:
        id: Unique identifier for the login attempt record.
        user_id: The user who attempted login (nullable for failed lookups).
        username: The username used in the login attempt.
        ip_address: Client IP address from the request.
        user_agent: Browser/client user agent string.
        success: Whether the login attempt was successful.
        failure_reason: Reason for failure (if applicable).
        created_at: Timestamp of the login attempt.
    """

    __tablename__ = "login_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique identifier for the login history record",
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="User who attempted login (null if user not found)",
    )

    username: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Username used in the login attempt",
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Client IP address (supports IPv4 and IPv6)",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Client user agent string",
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Whether the login attempt was successful",
    )

    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for login failure (null if successful)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="Timestamp of the login attempt",
    )

    def __repr__(self) -> str:
        status = "success" if self.success else "failed"
        return (
            f"<LoginHistory(id={self.id}, username={self.username!r}, "
            f"status={status}, created_at={self.created_at})>"
        )
