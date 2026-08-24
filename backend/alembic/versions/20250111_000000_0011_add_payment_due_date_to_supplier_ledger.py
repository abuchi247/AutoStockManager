"""Add payment_due_date column to supplier_ledger.

Stores the calculated payment due date for PURCHASE entries based on
the supplier's payment_terms. Used for aging analysis and overdue alerts.

Revision ID: 0011
Revises: 0010
Create Date: 2025-01-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_ledger",
        sa.Column(
            "payment_due_date",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Payment due date calculated from supplier payment terms",
        ),
    )
    # Index for querying upcoming/overdue payments efficiently
    op.create_index(
        "ix_supplier_ledger_due_date",
        "supplier_ledger",
        ["payment_due_date"],
        postgresql_where=sa.text("payment_due_date IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_ledger_due_date", table_name="supplier_ledger")
    op.drop_column("supplier_ledger", "payment_due_date")
