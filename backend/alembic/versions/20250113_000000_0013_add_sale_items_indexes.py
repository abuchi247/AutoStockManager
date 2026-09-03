"""Add performance indexes on sale_items foreign keys.

Postgres does not auto-create indexes on FK columns. sale_items.sale_id is
used by selectin loads and by dashboard/report joins; sale_items.spare_part_id
is used by top-selling-product aggregation. Without these, those queries do
sequential scans that degrade as sales grow.

Revision ID: 0013
Revises: 0012
Create Date: 2025-01-13 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_sale_items_sale_id",
        "sale_items",
        ["sale_id"],
    )
    op.create_index(
        "ix_sale_items_spare_part_id",
        "sale_items",
        ["spare_part_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sale_items_spare_part_id", table_name="sale_items")
    op.drop_index("ix_sale_items_sale_id", table_name="sale_items")
