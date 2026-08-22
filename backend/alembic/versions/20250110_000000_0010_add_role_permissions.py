"""Add role_permissions table for configurable RBAC.

Stores per-role permission flags as JSONB. Seeded with default
permissions matching the original hardcoded behaviour.

Revision ID: 0010
Revises: 0009
Create Date: 2025-01-10 00:00:00.000000
"""

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


# Default permissions per role — consolidated into logical business workflows
ALL_PERMISSIONS = [
    "sales",
    "sales_returns",
    "customers",
    "credit_management",
    "inventory",
    "purchasing",
    "receiving",
    "transfers",
    "transfer_approval",
    "locations",
    "categories",
    "audits",
    "audit_approval",
    "reports",
    "invoices",
    "user_management",
    "system_settings",
]

DEFAULT_PERMISSIONS = {
    "Admin": {p: True for p in ALL_PERMISSIONS},
    "Manager": {
        "sales": True, "sales_returns": True, "customers": True,
        "credit_management": True, "inventory": True, "purchasing": True,
        "receiving": True, "transfers": True, "transfer_approval": True,
        "locations": True, "categories": True, "audits": True,
        "audit_approval": True, "reports": True, "invoices": True,
        "user_management": False, "system_settings": False,
    },
    "Salesperson": {
        "sales": True, "sales_returns": False, "customers": True,
        "credit_management": False, "inventory": False, "purchasing": False,
        "receiving": False, "transfers": False, "transfer_approval": False,
        "locations": False, "categories": False, "audits": False,
        "audit_approval": False, "reports": False, "invoices": True,
        "user_management": False, "system_settings": False,
    },
    "Storekeeper": {
        "sales": False, "sales_returns": False, "customers": False,
        "credit_management": False, "inventory": True, "purchasing": False,
        "receiving": True, "transfers": True, "transfer_approval": False,
        "locations": True, "categories": False, "audits": True,
        "audit_approval": False, "reports": False, "invoices": False,
        "user_management": False, "system_settings": False,
    },
}


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("role", sa.String(50), unique=True, nullable=False),
        sa.Column("permissions", JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # Seed default permissions
    now = datetime.now(timezone.utc)
    for role, perms in DEFAULT_PERMISSIONS.items():
        import json
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (id, role, permissions, updated_at) "
                "VALUES (CAST(:id AS uuid), :role, CAST(:permissions AS jsonb), :updated_at)"
            ).bindparams(
                id=str(uuid.uuid4()),
                role=role,
                permissions=json.dumps(perms),
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_table("role_permissions")
