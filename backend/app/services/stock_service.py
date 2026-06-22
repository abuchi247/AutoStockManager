"""Stock status cache service for performant stock queries.

Provides read operations against the Stock_Status_Cache table, enabling
fast stock quantity lookups for display and validation purposes.

Satisfies Requirements:
- 18.1: Maintain Stock_Status_Cache table tracking current_quantity per part per location
- 18.3: Read from Stock_Status_Cache for stock quantity queries
- 18.8: Composite unique index on (spare_part_id, location_id)
"""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from app.models.spare_part import SparePart
from app.models.stock_status_cache import StockStatusCache


class StockService:
    """Service for querying stock status cache entries.

    Provides methods to retrieve stock quantities from the cache table
    rather than computing them from the full movement ledger. This
    satisfies Requirement 18.3: read from Stock_Status_Cache for performance.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_at_location(
        self,
        location_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Get all stock entries at a specific location.

        Retrieves stock status cache entries for the given location with
        pagination support. Joins with spare_parts to include part name
        and part number for display.

        Args:
            location_id: UUID of the location to query stock for.
            page: Page number (1-based) for pagination.
            page_size: Number of items per page (default 50).

        Returns:
            Dictionary with location info, stock items, and pagination metadata.

        Raises:
            LocationNotFoundError: If the specified location does not exist.
        """
        # Verify location exists
        location_stmt = select(Location).filter_by(id=location_id)
        location_result = await self.db.execute(location_stmt)
        location = location_result.scalar_one_or_none()

        if location is None:
            raise LocationNotFoundError(location_id=location_id)

        # Count total items at this location
        count_stmt = (
            select(func.count())
            .select_from(StockStatusCache)
            .filter(StockStatusCache.location_id == location_id)
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Query stock cache entries joined with spare parts for names
        offset = (page - 1) * page_size
        stock_stmt = (
            select(
                StockStatusCache,
                SparePart.name.label("spare_part_name"),
                SparePart.part_number.label("spare_part_number"),
            )
            .outerjoin(SparePart, StockStatusCache.spare_part_id == SparePart.id)
            .filter(StockStatusCache.location_id == location_id)
            .order_by(StockStatusCache.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        stock_result = await self.db.execute(stock_stmt)
        rows = stock_result.all()

        # Build response items
        items = []
        for row in rows:
            cache_entry = row[0]
            spare_part_name = row[1]
            spare_part_number = row[2]
            items.append({
                "id": cache_entry.id,
                "spare_part_id": cache_entry.spare_part_id,
                "location_id": cache_entry.location_id,
                "current_quantity": float(cache_entry.current_quantity),
                "last_reconciled_at": cache_entry.last_reconciled_at,
                "created_at": None,  # Cache table doesn't have created_at
                "updated_at": cache_entry.updated_at,
                "spare_part_name": spare_part_name,
                "spare_part_number": spare_part_number,
            })

        return {
            "location_id": location_id,
            "location_name": location.name,
            "data": items,
            "meta": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }

    async def get_stock_for_part_at_location(
        self,
        spare_part_id: UUID,
        location_id: UUID,
    ) -> StockStatusCache | None:
        """Get the stock cache entry for a specific part at a specific location.

        Used for stock validation before sales or transfers.

        Args:
            spare_part_id: UUID of the spare part.
            location_id: UUID of the location.

        Returns:
            The StockStatusCache entry or None if no stock record exists.
        """
        stmt = select(StockStatusCache).filter_by(
            spare_part_id=spare_part_id,
            location_id=location_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


# =============================================================================
# Custom Exceptions
# =============================================================================


class LocationNotFoundError(Exception):
    """Raised when the requested location does not exist."""

    def __init__(self, location_id: UUID):
        self.location_id = location_id
        self.message = f"Location with id '{location_id}' not found"
        super().__init__(self.message)
