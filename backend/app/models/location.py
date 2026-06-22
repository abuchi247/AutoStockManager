"""
Location model for multi-location inventory management.

This module defines the Location model representing warehouses and retail branches
where spare parts are stored and sold. Locations are a core entity in the ERP system
enabling multi-site inventory tracking, transfers, and sales.

Satisfies Requirement 4.1: THE Location_Manager SHALL support defining multiple
storage locations including warehouses and retail branches.
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin


class Location(BaseModel, SoftDeleteMixin):
    """Model representing a physical storage location (warehouse or retail branch).

    Locations are used throughout the system to track where inventory is stored,
    where sales originate from, and as source/destination for stock transfers.

    Columns (in addition to BaseModel and SoftDeleteMixin columns):
        name      - Human-readable name of the location (e.g., "Main Warehouse")
        type      - Location classification (e.g., "warehouse", "retail_branch")
        address   - Physical address of the location
        is_active - Whether this location is currently operational

    Relationships (defined in related models):
        - stock_status_cache entries (one per spare part stored here)
        - inventory_movement_ledger entries (all stock movements at this location)
        - sales (sales transactions originating from this location)
        - transfers (as source or destination)
        - cost_layers (inventory valuation layers at this location)

    Usage:
        location = Location(
            name="Main Warehouse",
            type="warehouse",
            address="123 Industrial Ave, Lagos",
            is_active=True,
            created_by="admin-user-id",
        )
    """

    __tablename__ = "locations"

    # -------------------------------------------------------------------------
    # Location-specific columns
    # -------------------------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable name of the location",
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Location type classification (e.g., 'warehouse', 'retail_branch')",
    )

    address: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Physical address of the location",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this location is currently operational",
    )
