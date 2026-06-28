"""Add business_settings table.

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_name", sa.String(255), nullable=False, server_default="My Business"),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("tax_id", sa.String(100), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("logo_base64", sa.Text(), nullable=True),
        sa.Column("invoice_footer", sa.Text(), nullable=True, server_default="Thank you for your patronage"),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("bank_account_number", sa.String(100), nullable=True),
        sa.Column("bank_account_name", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("business_settings")
