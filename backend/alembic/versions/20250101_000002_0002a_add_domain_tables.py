"""Add all domain tables missing from migration history.

Previously the application relied on SQLAlchemy create_all() at startup.
That path was removed in favour of Alembic-only schema management, but
the corresponding revisions were never generated for 22 of 26 tables.
This migration fills that gap.

Revision ID: 0002a
Revises: 0002
Create Date: 2025-01-01 00:00:02.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON, BYTEA, ENUM as PG_ENUM

revision: str = "0002a"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Use dialect-level PG_ENUM with create_type=False so that Alembic does not
# attempt a second CREATE TYPE when creating tables referencing these enums.
SALE_STATUS = PG_ENUM("DRAFT", "CONFIRMED", "RETURNED", "CANCELLED", name="sale_status", create_type=False)
PAYMENT_TYPE = PG_ENUM("CASH", "CREDIT", name="payment_type", create_type=False)
PURCHASE_ORDER_STATUS = PG_ENUM(
    "DRAFT", "APPROVED", "ORDERED", "PARTIALLY_RECEIVED", "RECEIVED", "CANCELLED",
    name="purchase_order_status", create_type=False,
)
INVOICE_FORMAT = PG_ENUM("A4", "THERMAL", name="invoice_format", create_type=False)
AUDIT_TYPE = PG_ENUM("CYCLE_COUNT", "FULL_STOCK_COUNT", name="audit_type", create_type=False)
AUDIT_STATUS = PG_ENUM("INITIATED", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="audit_status", create_type=False)


def upgrade() -> None:
    # --- Create enum types via raw SQL (IF NOT EXISTS for idempotency) ---
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sale_status') THEN CREATE TYPE sale_status AS ENUM ('DRAFT','CONFIRMED','RETURNED','CANCELLED'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_type') THEN CREATE TYPE payment_type AS ENUM ('CASH','CREDIT'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'purchase_order_status') THEN CREATE TYPE purchase_order_status AS ENUM ('DRAFT','APPROVED','ORDERED','PARTIALLY_RECEIVED','RECEIVED','CANCELLED'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invoice_format') THEN CREATE TYPE invoice_format AS ENUM ('A4','THERMAL'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_type') THEN CREATE TYPE audit_type AS ENUM ('CYCLE_COUNT','FULL_STOCK_COUNT'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_status') THEN CREATE TYPE audit_status AS ENUM ('INITIATED','IN_PROGRESS','COMPLETED','CANCELLED'); END IF; END $$;")

    # --- 1. users (no FK to other new tables) ---
    op.create_table(
        "users",
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- 2. customers ---
    op.create_table(
        "customers",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("tax_id", sa.String(100), nullable=True),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("account_status", sa.String(20), nullable=False, server_default="'ACTIVE'"),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    # --- 3. suppliers ---
    op.create_table(
        "suppliers",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_person", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("tax_id", sa.String(100), nullable=True),
        sa.Column("payment_terms", sa.String(100), nullable=True),
        sa.Column("account_status", sa.String(20), nullable=False, server_default="'ACTIVE'"),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    # --- 4. sales ---
    op.create_table(
        "sales",
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=True, unique=True),
        sa.Column("status", SALE_STATUS, nullable=False),
        sa.Column("payment_type", PAYMENT_TYPE, nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=True, server_default="0.00"),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    # --- 5. sale_items ---
    op.create_table(
        "sale_items",
        sa.Column("sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id"), nullable=False),
        sa.Column("spare_part_id", UUID(as_uuid=True), sa.ForeignKey("spare_parts.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("cost_of_goods_sold", sa.Numeric(14, 2), nullable=True),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 6. purchase_orders ---
    op.create_table(
        "purchase_orders",
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("status", PURCHASE_ORDER_STATUS, nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 7. purchase_order_items ---
    op.create_table(
        "purchase_order_items",
        sa.Column("purchase_order_id", UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("spare_part_id", UUID(as_uuid=True), sa.ForeignKey("spare_parts.id"), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity_received", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 8. goods_receipt_notes ---
    op.create_table(
        "goods_receipt_notes",
        sa.Column("purchase_order_id", UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("received_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 9. grn_items ---
    op.create_table(
        "grn_items",
        sa.Column("grn_id", UUID(as_uuid=True), sa.ForeignKey("goods_receipt_notes.id"), nullable=False),
        sa.Column("po_item_id", UUID(as_uuid=True), sa.ForeignKey("purchase_order_items.id"), nullable=False),
        sa.Column("spare_part_id", UUID(as_uuid=True), sa.ForeignKey("spare_parts.id"), nullable=False),
        sa.Column("quantity_received", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 4), nullable=False),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 10. transfers ---
    op.create_table(
        "transfers",
        sa.Column("spare_part_id", UUID(as_uuid=True), sa.ForeignKey("spare_parts.id"), nullable=False),
        sa.Column("source_location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("destination_location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("consumed_layer_details", JSON, nullable=True),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 11. cost_layers ---
    op.create_table(
        "cost_layers",
        sa.Column("spare_part_id", UUID(as_uuid=True), sa.ForeignKey("spare_parts.id"), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 4), nullable=False),
        sa.Column("original_quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_reference_id", UUID(as_uuid=True), nullable=False),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 12. stock_status_cache ---
    op.create_table(
        "stock_status_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("spare_part_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("current_quantity", sa.Numeric(15, 4), nullable=False, server_default="0.0000"),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- 13. inventory_movement_ledger ---
    op.create_table(
        "inventory_movement_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("spare_part_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_change", sa.Numeric(15, 4), nullable=False),
        sa.Column("movement_type", sa.String(50), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=False),
        sa.Column("unit_cost", sa.Numeric(15, 4), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- 14. customer_credit_ledger ---
    op.create_table(
        "customer_credit_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- 15. supplier_ledger ---
    op.create_table(
        "supplier_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("supplier_id", UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- 16. invoices ---
    op.create_table(
        "invoices",
        sa.Column("sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id"), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("pdf_data", BYTEA, nullable=False),
        sa.Column("format", INVOICE_FORMAT, nullable=False),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 17. login_history ---
    op.create_table(
        "login_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- 18. notifications ---
    op.create_table(
        "notifications",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 19. audit_trail ---
    op.create_table(
        "audit_trail",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("old_values", JSON, nullable=True),
        sa.Column("new_values", JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- 20. audit_sessions ---
    op.create_table(
        "audit_sessions",
        sa.Column("location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("audit_type", AUDIT_TYPE, nullable=False),
        sa.Column("status", AUDIT_STATUS, nullable=False),
        sa.Column("snapshot_timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 21. audit_snapshot_items ---
    op.create_table(
        "audit_snapshot_items",
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("audit_sessions.id"), nullable=False),
        sa.Column("spare_part_id", UUID(as_uuid=True), sa.ForeignKey("spare_parts.id"), nullable=False),
        sa.Column("snapshot_quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # --- 22. audit_counts ---
    op.create_table(
        "audit_counts",
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("audit_sessions.id"), nullable=False),
        sa.Column("spare_part_id", UUID(as_uuid=True), sa.ForeignKey("spare_parts.id"), nullable=False),
        sa.Column("counted_quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("variance", sa.Numeric(15, 4), nullable=False),
        sa.Column("counted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("audit_counts")
    op.drop_table("audit_snapshot_items")
    op.drop_table("audit_sessions")
    op.drop_table("audit_trail")
    op.drop_table("notifications")
    op.drop_table("login_history")
    op.drop_table("invoices")
    op.drop_table("supplier_ledger")
    op.drop_table("customer_credit_ledger")
    op.drop_table("inventory_movement_ledger")
    op.drop_table("stock_status_cache")
    op.drop_table("cost_layers")
    op.drop_table("transfers")
    op.drop_table("grn_items")
    op.drop_table("goods_receipt_notes")
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
    op.drop_table("sale_items")
    op.drop_table("sales")
    op.drop_table("suppliers")
    op.drop_table("customers")
    op.drop_table("users")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS audit_status")
    op.execute("DROP TYPE IF EXISTS audit_type")
    op.execute("DROP TYPE IF EXISTS invoice_format")
    op.execute("DROP TYPE IF EXISTS purchase_order_status")
    op.execute("DROP TYPE IF EXISTS payment_type")
    op.execute("DROP TYPE IF EXISTS sale_status")
