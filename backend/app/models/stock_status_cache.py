"""
Stock Status Cache model.

This module defines the materialized cache table that maintains the current
aggregated stock quantity per spare part per location. It provides performant
reads for stock queries and is updated atomically alongside every ledger write.

The cache is the "fast read" layer — the ledger is the source of truth. Periodic
reconciliation ensures the cache stays in sync with ledger totals.

Satisfies Requirement 18.1: THE ERP_System SHALL maintain a Stock_Status_Cache
table tracking current_quantity per Spare_Part per location.

Satisfies Requirement 18.3: WHEN stock quantity is queried for display or
validation, THE ERP_System SHALL read from the Stock_Status_Cache for performance.

Satisfies Requirement 18.8: THE ERP_System SHALL maintain a composite unique
index on the Stock_Status_Cache table for spare_part_id and location_id columns.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockStatusCache(Base):
    """Cache table maintaining current stock quantity per part per location.

    This table is designed for fast reads during stock validation (e.g., before
    confirming a sale) and display. It is updated atomically within the same
    transaction that writes to the Inventory_Movement_Ledger.

    Columns:
        id                - UUID primary key
        spare_part_id     - The spare part being tracked
        location_id       - The location where the stock is held
        current_quantity  - Current aggregated stock quantity (Decimal)
        last_reconciled_at - Timestamp of the last successful reconciliation
        updated_at        - Timestamp of the last cache update

    Constraints:
        - Composite unique index on (spare_part_id, location_id) ensuring
          one cache row per part-location pair.

    Usage:
        # Query current stock for a part at a location
        stmt = (
            select(StockStatusCache)
            .filter_by(spare_part_id=part_id, location_id=loc_id)
            .with_for_update()
        )
    """

    __tablename__ = "stock_status_cache"

    __table_args__ = (
        Index(
            "uix_stock_status_cache_part_location",
            "spare_part_id",
            "location_id",
            unique=True,
        ),
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique identifier for this cache row",
    )

    # -------------------------------------------------------------------------
    # Composite Key Fields
    # -------------------------------------------------------------------------
    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="The spare part being tracked",
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="The location where the stock is held",
    )

    # -------------------------------------------------------------------------
    # Stock Data
    # -------------------------------------------------------------------------
    current_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
        default=Decimal("0"),
        comment="Current aggregated stock quantity at this location",
    )

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    last_reconciled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp of the last successful reconciliation against the ledger",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp of the last cache update",
    )
