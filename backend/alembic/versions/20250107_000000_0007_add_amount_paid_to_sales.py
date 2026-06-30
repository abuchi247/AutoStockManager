"""Add amount_paid column to sales table.

Supports partial payments at checkout for credit sales.

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales",
        sa.Column(
            "amount_paid",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
            comment="Amount paid at checkout (for credit sales, this may be partial)",
        ),
    )


def downgrade() -> None:
    op.drop_column("sales", "amount_paid")
