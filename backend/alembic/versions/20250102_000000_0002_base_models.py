"""Create categories, locations, and spare_parts tables

This migration creates the foundational domain tables for the Auto Spare Parts
ERP system:
- categories: Hierarchical product categorization with self-referential parent_id
- locations: Multi-location inventory management (warehouses, retail branches)
- spare_parts: Master product catalog with all spare part attributes

It also creates partial unique indexes on spare_parts for soft-delete
compatibility, ensuring that uniqueness constraints only apply to active
(non-deleted) records.

Satisfies:
- Requirement 18.5: Use partial unique indexes to ensure soft-deleted records
  do not conflict with unique constraints on active records.
- Requirement 18.7: Performance indexing strategy.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers used by Alembic to maintain migration ordering.
revision: str = "0002"
down_revision: str = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create categories, locations, and spare_parts tables with indexes."""

    # =========================================================================
    # 1. Categories table (must be created first due to FK references)
    # =========================================================================
    op.create_table(
        "categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier for the record (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when this record was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
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
    # 2. Locations table
    # =========================================================================
    op.create_table(
        "locations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier for the record (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when this record was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
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
    # 3. Spare Parts table (depends on categories for FK)
    # =========================================================================
    op.create_table(
        "spare_parts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier for the record (UUID v4)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when this record was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
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
    # 4. Partial Unique Indexes for soft-delete compatibility (Req 18.5)
    # =========================================================================
    # These indexes ensure that part_number and barcode uniqueness is enforced
    # only among active (non-deleted) records. Soft-deleted records are excluded
    # from the constraint, allowing the same part_number or barcode to be reused
    # after a record is soft-deleted.

    op.create_index(
        "uix_spare_parts_part_number_active",
        "spare_parts",
        ["part_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_index(
        "uix_spare_parts_barcode_active",
        "spare_parts",
        ["barcode"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # =========================================================================
    # 5. Performance indexes (Req 18.7)
    # =========================================================================
    # Index on spare_parts.category_id for JOIN performance
    op.create_index(
        "ix_spare_parts_category_id",
        "spare_parts",
        ["category_id"],
    )

    # Index on spare_parts.subcategory_id for JOIN performance
    op.create_index(
        "ix_spare_parts_subcategory_id",
        "spare_parts",
        ["subcategory_id"],
    )

    # Index on spare_parts.brand for search/filter queries
    op.create_index(
        "ix_spare_parts_brand",
        "spare_parts",
        ["brand"],
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
    """Drop all tables and indexes created in this migration."""

    # Drop indexes first
    op.drop_index("ix_locations_is_active", table_name="locations")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_index("ix_spare_parts_brand", table_name="spare_parts")
    op.drop_index("ix_spare_parts_subcategory_id", table_name="spare_parts")
    op.drop_index("ix_spare_parts_category_id", table_name="spare_parts")
    op.drop_index("uix_spare_parts_barcode_active", table_name="spare_parts")
    op.drop_index("uix_spare_parts_part_number_active", table_name="spare_parts")

    # Drop tables in reverse dependency order
    op.drop_table("spare_parts")
    op.drop_table("locations")
    op.drop_table("categories")
