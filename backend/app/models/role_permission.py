"""
Role Permission model.

Stores configurable permissions per role as a JSONB object. Each role has
exactly one row. The permissions field is a dict of permission keys mapped
to boolean values indicating whether that role has the permission.

Example:
    {
        "create_sales": true,
        "process_returns": false,
        "view_reports": true,
        ...
    }

The Admin role always has all permissions — the UI shows them as checked
and disabled. The backend enforces this by always granting Admin access
regardless of what's stored.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RolePermission(Base):
    """Configurable permissions per role."""

    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="Role name: Admin, Manager, Salesperson, Storekeeper",
    )

    permissions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Permission keys mapped to boolean values",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role='{self.role}')>"
