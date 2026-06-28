"""Add performance indexes on sales table.

These indexes support dashboard KPIs, report date-range queries,
and customer purchase history lookups.

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-06 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for dashboard KPIs and date-range report queries
    # Covers: status + created_at range scans (most common report pattern)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_status_created_at "
        "ON sales (status, created_at)"
    )

    # Index on customer_id for customer purchase history and report joins
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_customer_id "
        "ON sales (customer_id) WHERE customer_id IS NOT NULL"
    )

    # Index on location_id for location-filtered reports
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_location_id "
        "ON sales (location_id)"
    )

    # Index on supplier_ledger for supplier report queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_supplier_ledger_supplier_created "
        "ON supplier_ledger (supplier_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_supplier_ledger_supplier_created")
    op.execute("DROP INDEX IF EXISTS ix_sales_location_id")
    op.execute("DROP INDEX IF EXISTS ix_sales_customer_id")
    op.execute("DROP INDEX IF EXISTS ix_sales_status_created_at")
