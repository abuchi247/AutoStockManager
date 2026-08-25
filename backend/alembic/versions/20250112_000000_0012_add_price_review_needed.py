"""Add price_review_needed column to spare_parts.

Flags items where a cost increase has eroded the margin below the
acceptable threshold, prompting the owner to review selling prices.

Revision ID: 0012
Revises: 0011
Create Date: 2025-01-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spare_parts",
        sa.Column(
            "price_review_needed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Flag indicating selling price needs review due to cost increase",
        ),
    )


def downgrade() -> None:
    op.drop_column("spare_parts", "price_review_needed")
