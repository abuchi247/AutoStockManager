"""Create locations, categories, and spare_parts tables

This migration creates the foundational domain tables for the ERP system:
- locations: Physical storage locations (warehouses, retail branches)
- categories: Hierarchical product categories with self-referential parent
- spare_parts: Core product catalog with all attributes

It also applies partial unique indexes for soft-delete compatibility:
- uix_spare_parts_part_number_active: Ensures unique part_number among active records
- uix_spare_parts_barcode_active: Ensures unique barcode among active records

These partial indexes allow soft-deleted records to retain their original
part_number/barcode values without conflicting with new active records that
may reuse those identifiers.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:00:01.000000+00:00

Requirements:
- 18.5: Use partial unique indexes to ensure soft-deleted records don't conflict
         with unique constraints on active records
- 18.7: Proper indexing strategy
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers used by Alembic to maintain migration ordering.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create locations, categories, and spare_parts tables with indexes."""

    # =========================================================================
    # 1. Create 'locations' table
    # =========================================================================
    op.create_table(
        "locations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("uuid_generate_v4()"),
            comment="Unique identifier for the record (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp when this record was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp of the last update to this record",
        ),
        sa.Column(
            "created_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who created this record",
        ),
        sa.Column(
            "updated_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who last updated this record",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when this record was soft-deleted (NULL means active)",
        ),
        sa.Column(
            "deleted_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who soft-deleted this record",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable name of the location",
        ),
        sa.Column(
            "type",
            sa.String(50),
            nullable=False,
            comment="Location type classification (e.g., 'warehouse', 'retail_branch')",
        ),
        sa.Column(
            "address",
            sa.String(500),
            nullable=False,
            comment="Physical address of the location",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether this location is currently operational",
        ),
    )

    # =========================================================================
    # 2. Create 'categories' table
    # =========================================================================
    op.create_table(
        "categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("uuid_generate_v4()"),
            comment="Unique identifier for the record (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp when this record was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp of the last update to this record",
        ),
        sa.Column(
            "created_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who created this record",
        ),
        sa.Column(
            "updated_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who last updated this record",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when this record was soft-deleted (NULL means active)",
        ),
        sa.Column(
            "deleted_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who soft-deleted this record",
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Category display name",
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
            comment="Parent category ID for subcategory hierarchy (NULL for top-level)",
        ),
        sa.Column(
            "description",
            sa.String(1000),
            nullable=True,
            comment="Optional description of this category",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether this category is currently active",
        ),
    )

    # =========================================================================
    # 3. Create 'spare_parts' table
    # =========================================================================
    op.create_table(
        "spare_parts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("uuid_generate_v4()"),
            comment="Unique identifier for the record (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp when this record was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp of the last update to this record",
        ),
        sa.Column(
            "created_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who created this record",
        ),
        sa.Column(
            "updated_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who last updated this record",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when this record was soft-deleted (NULL means active)",
        ),
        sa.Column(
            "deleted_by",
            sa.String(255),
            nullable=True,
            comment="User identifier of who soft-deleted this record",
        ),
        sa.Column(
            "part_number",
            sa.String(100),
            nullable=False,
            comment="Unique part identification number",
        ),
        sa.Column(
            "barcode",
            sa.String(255),
            nullable=True,
            comment="Scannable barcode value (unique when present)",
        ),
        sa.Column(
            "name",
            sa.String(500),
            nullable=False,
            comment="Product display name",
        ),
        sa.Column(
            "description",
            sa.String(2000),
            nullable=True,
            comment="Detailed product description",
        ),
        sa.Column(
            "brand",
            sa.String(255),
            nullable=True,
            comment="Manufacturer or brand name",
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=False,
            comment="Primary category for this spare part",
        ),
        sa.Column(
            "subcategory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
            comment="Subcategory for this spare part (optional)",
        ),
        sa.Column(
            "vehicle_compatibility",
            postgresql.JSON(),
            nullable=True,
            comment="JSON list of compatible vehicles",
        ),
        sa.Column(
            "unit_of_measure",
            sa.String(50),
            nullable=False,
            server_default="PCS",
            comment="Unit of measure (e.g., PCS, BOX, LTR, KG)",
        ),
        sa.Column(
            "cost_price",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
            comment="Purchase/cost price",
        ),
        sa.Column(
            "selling_price",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
            comment="Retail selling price",
        ),
        sa.Column(
            "min_stock_level",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
            comment="Minimum stock threshold triggering reorder alerts",
        ),
        sa.Column(
            "max_stock_level",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
            comment="Maximum stock capacity for this part",
        ),
        sa.Column(
            "reorder_quantity",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
            comment="Default quantity to reorder when stock is low",
        ),
    )

    # =========================================================================
    # 4. Create indexes
    # =========================================================================

    # --- Partial unique indexes for soft-delete compatibility (Req 18.5) ---
    # These indexes enforce uniqueness ONLY among active (non-deleted) records.
    # Soft-deleted records (deleted_at IS NOT NULL) are excluded from the index,
    # allowing the same part_number/barcode to be reused by a new active record
    # after the original is soft-deleted.

    op.execute(
        """
        CREATE UNIQUE INDEX uix_spare_parts_part_number_active
        ON spare_parts (part_number)
        WHERE deleted_at IS NULL
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uix_spare_parts_barcode_active
        ON spare_parts (barcode)
        WHERE deleted_at IS NULL
        """
    )

    # --- General performance indexes (Req 18.7) ---
    # Index on spare_parts.name for text search/filtering
    op.create_index(
        "ix_spare_parts_name",
        "spare_parts",
        ["name"],
    )

    # Index on spare_parts.brand for filter queries
    op.create_index(
        "ix_spare_parts_brand",
        "spare_parts",
        ["brand"],
    )

    # Index on spare_parts.category_id for category filtering and joins
    op.create_index(
        "ix_spare_parts_category_id",
        "spare_parts",
        ["category_id"],
    )

    # Index on categories.parent_id for hierarchical queries
    op.create_index(
        "ix_categories_parent_id",
        "categories",
        ["parent_id"],
    )

    # Index on locations.is_active for filtering active locations
    op.create_index(
        "ix_locations_is_active",
        "locations",
        ["is_active"],
    )


def downgrade() -> None:
    """Drop tables and indexes in reverse order."""

    # Drop indexes first
    op.drop_index("ix_locations_is_active", table_name="locations")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_index("ix_spare_parts_category_id", table_name="spare_parts")
    op.drop_index("ix_spare_parts_brand", table_name="spare_parts")
    op.drop_index("ix_spare_parts_name", table_name="spare_parts")
    op.execute("DROP INDEX IF EXISTS uix_spare_parts_barcode_active")
    op.execute("DROP INDEX IF EXISTS uix_spare_parts_part_number_active")

    # Drop tables in reverse dependency order
    op.drop_table("spare_parts")
    op.drop_table("categories")
    op.drop_table("locations")
