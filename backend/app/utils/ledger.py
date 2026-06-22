"""
Atomic ledger-write + cache-update helper.

This module provides a helper function that atomically writes to the
Inventory_Movement_Ledger and updates the Stock_Status_Cache within the
same database transaction. This ensures that the cache never drifts from
the ledger for operations that use this helper.

The caller is responsible for managing the transaction boundary (i.e., calling
commit/rollback). This function performs the writes but does not commit.

Satisfies Requirement 18.2: WHEN a new entry is appended to the
Inventory_Movement_Ledger, THE ERP_System SHALL atomically update the
Stock_Status_Cache within the same database transaction.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_movement_ledger import InventoryMovementLedger
from app.models.stock_status_cache import StockStatusCache


async def record_inventory_movement(
    db: AsyncSession,
    spare_part_id: uuid.UUID,
    location_id: uuid.UUID,
    quantity_change: Decimal,
    movement_type: str,
    reference_type: str,
    reference_id: uuid.UUID,
    unit_cost: Decimal,
    created_by: uuid.UUID,
) -> InventoryMovementLedger:
    """Write a ledger entry and atomically update the stock cache.

    This function performs two operations within the caller's transaction:
    1. Creates an InventoryMovementLedger entry recording the stock movement.
    2. Upserts the StockStatusCache row for the given (spare_part_id, location_id)
       pair using SELECT FOR UPDATE to prevent concurrent modification, then
       updates the current_quantity. If no cache row exists, one is created.

    Both operations occur in the same transaction — the caller controls when
    to commit. This guarantees that the cache is always consistent with the
    ledger after a successful commit.

    Args:
        db: The async database session (caller manages transaction boundary).
        spare_part_id: UUID of the spare part being moved.
        location_id: UUID of the location where the movement occurs.
        quantity_change: Signed decimal quantity change.
            Positive for inflows (purchase, transfer_in, return, adjustment_up).
            Negative for outflows (sale, transfer_out, adjustment_down).
        movement_type: Classification string (e.g., "SALE", "PURCHASE",
            "TRANSFER_OUT", "TRANSFER_IN", "ADJUSTMENT", "RETURN").
        reference_type: Type of the originating document (e.g., "sale", "grn",
            "transfer", "audit_adjustment").
        reference_id: UUID of the originating document.
        unit_cost: Cost per unit at the time of this movement.
        created_by: UUID of the user initiating this movement.

    Returns:
        The newly created InventoryMovementLedger entry.

    Raises:
        Any database-level exceptions (e.g., integrity errors) are propagated
        to the caller for handling within their transaction management.

    Example:
        async with db.begin():
            # Lock the cache row first if needed for validation
            ledger_entry = await record_inventory_movement(
                db=db,
                spare_part_id=part.id,
                location_id=location.id,
                quantity_change=Decimal("-5"),
                movement_type="SALE",
                reference_type="sale",
                reference_id=sale.id,
                unit_cost=Decimal("150.00"),
                created_by=current_user.id,
            )
            # Transaction commits at end of `async with db.begin()`
    """
    # -------------------------------------------------------------------------
    # Step 1: Create the immutable ledger entry
    # -------------------------------------------------------------------------
    ledger_entry = InventoryMovementLedger(
        spare_part_id=spare_part_id,
        location_id=location_id,
        quantity_change=quantity_change,
        movement_type=movement_type,
        reference_type=reference_type,
        reference_id=reference_id,
        unit_cost=unit_cost,
        created_by=created_by,
    )
    db.add(ledger_entry)

    # Flush to ensure the ledger entry is persisted before cache update,
    # maintaining write order within the transaction.
    await db.flush()

    # -------------------------------------------------------------------------
    # Step 2: Atomically update (or create) the Stock_Status_Cache row
    # -------------------------------------------------------------------------
    # Use SELECT FOR UPDATE to acquire a pessimistic lock on the cache row.
    # This prevents concurrent transactions from reading stale data or
    # creating duplicate rows for the same (spare_part_id, location_id) pair.
    stmt = (
        select(StockStatusCache)
        .filter_by(
            spare_part_id=spare_part_id,
            location_id=location_id,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    cache_row = result.scalar_one_or_none()

    if cache_row is not None:
        # Update existing cache row
        cache_row.current_quantity = cache_row.current_quantity + quantity_change
        cache_row.updated_at = datetime.now(timezone.utc)
    else:
        # Create new cache row for this (spare_part_id, location_id) pair
        cache_row = StockStatusCache(
            spare_part_id=spare_part_id,
            location_id=location_id,
            current_quantity=quantity_change,
        )
        db.add(cache_row)

    # Flush to ensure both the ledger write and cache update are in the
    # same transaction state before the caller decides to commit.
    await db.flush()

    return ledger_entry
