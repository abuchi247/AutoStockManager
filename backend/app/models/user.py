"""
User model for authentication and role-based access control.

Defines the User table storing credentials, roles, and account lockout state.
Satisfies Requirements 2.1, 2.7, 2.8:
- Four roles: Admin, Manager, Salesperson, Storekeeper
- bcrypt password hashing with cost factor 12
- Account lockout after 5 failed attempts in 15 minutes
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin


class UserRole(str, enum.Enum):
    """Enumeration of supported user roles (Requirement 2.1)."""

    ADMIN = "Admin"
    MANAGER = "Manager"
    SALESPERSON = "Salesperson"
    STOREKEEPER = "Storekeeper"


class User(BaseModel, SoftDeleteMixin):
    """User model for authentication and authorization.

    Stores user credentials, role assignment, and account lockout state.
    Inherits UUID primary key and audit columns from BaseModel, and
    soft-delete capability from SoftDeleteMixin.

    Attributes:
        username: Unique login identifier
        email: Unique email address for password reset
        password_hash: bcrypt-hashed password (cost factor 12)
        role: One of Admin, Manager, Salesperson, Storekeeper
        is_active: Whether the account is enabled
        locked_until: Timestamp until which the account is locked (nullable)
        failed_login_attempts: Counter for consecutive failed login attempts
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique login username",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique email address for password resets",
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt-hashed password",
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="User role: Admin, Manager, Salesperson, or Storekeeper",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the user account is active",
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Account locked until this timestamp (NULL means not locked)",
    )

    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of consecutive failed login attempts",
    )

    @property
    def is_locked(self) -> bool:
        """Check if the account is currently locked."""
        if self.locked_until is None:
            return False
        from datetime import timezone

        return datetime.now(timezone.utc) < self.locked_until

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username!r}, role={self.role!r})>"
