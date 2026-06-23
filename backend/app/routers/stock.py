"""Stock query router for reading stock levels from the cache.

Provides the following endpoint:
- GET /api/v1/stock/locations/{id} - Get stock at a specific location

Reads from Stock_Status_Cache for performant stock queries rather than
computing quantities from the full movement ledger.

Satisfies Requirements: 18.1, 18.3, 18.8
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DbSession
from app.schemas.stock import StockItemResponse, StockLocationResponse
from app.services.stock_service import LocationNotFoundError, StockService

router = APIRouter(prefix="/api/v1/stock", tags=["Stock"])


@router.get(
    "/locations/{location_id}",
    response_model=StockLocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stock at a location",
    description="Retrieves current stock quantities for all spare parts at a given location. "
    "Reads from the Stock_Status_Cache for fast performance.",
    responses={
        404: {"description": "Location not found"},
    },
)
async def get_stock_at_location(
    location_id: UUID,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
) -> StockLocationResponse:
    """Get stock quantities at a specific location.

    Returns paginated stock cache entries for the specified location,
    including spare part names and part numbers for display convenience.

    Requirements:
    - 18.1: Stock_Status_Cache tracks current_quantity per part per location
    - 18.3: Read from Stock_Status_Cache for stock quantity queries
    """
    stock_service = StockService(db=db)

    try:
        result = await stock_service.get_stock_at_location(
            location_id=location_id,
            page=page,
            page_size=page_size,
        )
    except LocationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with id '{location_id}' not found",
        )

    # Convert items to response models
    stock_items = [StockItemResponse(**item) for item in result["data"]]

    return StockLocationResponse(
        location_id=result["location_id"],
        location_name=result["location_name"],
        data=stock_items,
        meta=result["meta"],
    )
