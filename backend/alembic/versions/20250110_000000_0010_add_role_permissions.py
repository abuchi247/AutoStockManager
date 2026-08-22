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


# Default permissions per role — matches the original hardcoded behaviour
ALL_PERMISSIONS = [
    "create_sales",
    "confirm_sales",
    "cancel_sales",
    "process_returns",
    "manage_customers",
    "record_payments",
    "credit_adjustments",
    "view_reports",
    "view_profit",
    "generate_invoices",
    "manage_inventory",
    "adjust_stock",
    "manage_transfers",
    "approve_transfers",
    "manage_purchases",
    "approve_purchases",
    "receive_goods",
    "manage_suppliers",
    "manage_locations",
    "manage_categories",
    "manage_users",
    "manage_settings",
    "start_audits",
    "approve_audits",
    "view_dashboard",
    "view_notifications",
]

DEFAULT_PERMISSIONS = {
    "Admin": {p: True for p in ALL_PERMISSIONS},
    "Manager": {
        "create_sales": True,
        "confirm_sales": True,
        "cancel_sales": True,
        "process_returns": True,
        "manage_customers": True,
        "record_payments": True,
        "credit_adjustments": True,
        "view_reports": True,
        "view_profit": True,
        "generate_invoices": True,
        "manage_inventory": True,
        "adjust_stock": True,
        "manage_transfers": True,
        "approve_transfers": True,
        "manage_purchases": True,
        "approve_purchases": True,
        "receive_goods": True,
        "manage_suppliers": True,
        "manage_locations": True,
        "manage_categories": True,
        "manage_users": False,
        "manage_settings": False,
        "start_audits": True,
        "approve_audits": True,
        "view_dashboard": True,
        "view_notifications": True,
    },
    "Salesperson": {
        "create_sales": True,
        "confirm_sales": True,
        "cancel_sales": True,
        "process_returns": False,
        "manage_customers": True,
        "record_payments": True,
        "credit_adjustments": False,
        "view_reports": False,
        "view_profit": False,
        "generate_invoices": True,
        "manage_inventory": False,
        "adjust_stock": False,
        "manage_transfers": False,
        "approve_transfers": False,
        "manage_purchases": False,
        "approve_purchases": False,
        "receive_goods": False,
        "manage_suppliers": False,
        "manage_locations": False,
        "manage_categories": False,
        "manage_users": False,
        "manage_settings": False,
        "start_audits": False,
        "approve_audits": False,
        "view_dashboard": True,
        "view_notifications": True,
    },
    "Storekeeper": {
        "create_sales": False,
        "confirm_sales": False,
        "cancel_sales": False,
        "process_returns": False,
        "manage_customers": False,
        "record_payments": False,
        "credit_adjustments": False,
        "view_reports": False,
        "view_profit": False,
        "generate_invoices": False,
        "manage_inventory": True,
        "adjust_stock": True,
        "manage_transfers": True,
        "approve_transfers": False,
        "manage_purchases": False,
        "approve_purchases": False,
        "receive_goods": True,
        "manage_suppliers": False,
        "manage_locations": True,
        "manage_categories": False,
        "manage_users": False,
        "manage_settings": False,
        "start_audits": True,
        "approve_audits": False,
        "view_dashboard": True,
        "view_notifications": True,
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
                "VALUES (:id::uuid, :role, :permissions::jsonb, :updated_at)"
            ).bindparams(
                id=str(uuid.uuid4()),
                role=role,
                permissions=json.dumps(perms),
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_table("role_permissions")
