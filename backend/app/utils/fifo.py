"""
FIFO (First-In, First-Out) cost layer consumption algorithm.

This module implements the core FIFO inventory valuation algorithm used
whenever stock is consumed — during sales, transfers out, or adjustments.
It selects cost layers in chronological order and deducts quantities until
the requested amount is fulfilled.

Satisfies:
- Requirement 1.5: Calculate COGS using FIFO by consuming oldest Cost_Layers first.
- Requirement 1.10: Consume from Cost_Layers in chronological order of receipt date.
- Requirement 18.10: Use partial index for efficient FIFO layer lookup.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_layer import CostLayer


class InsufficientCostLayerError(Exception):
    """Raised when cost layers cannot fulfill the requested consumption quantity.

    This occurs when the total remaining quantity across all available cost
    layers for a given spare part at a location is less than the amount
    requested for consumption.

    Attributes:
        spare_part_id: The spare part that has insufficient layers.
        location_id: The location where layers are insufficient.
        shortfall: The quantity that could not be fulfilled.
    """

    def __init__(
        self,
        spare_part_id: UUID,
        location_id: UUID,
        shortfall: Decimal,
    ) -> None:
        self.spare_part_id = spare_part_id
        self.location_id = location_id
        self.shortfall = shortfall
        super().__init__(
            f"Insufficient cost layers for spare_part_id={spare_part_id} "
            f"at location_id={location_id}. Shortfall: {shortfall}"
        )


async def consume_fifo_layers(
    db: AsyncSession,
    spare_part_id: UUID,
    location_id: UUID,
    quantity_to_consume: Decimal,
) -> tuple[Decimal, list[dict]]:
    """Consume cost layers in FIFO order for a given part at a location.

    This function implements the FIFO algorithm:
    1. Query cost layers WHERE remaining_quantity > 0, ordered by created_at ASC
    2. Acquire SELECT FOR UPDATE lock on the layers (pessimistic locking)
    3. For each layer, consume min(layer.remaining_quantity, remaining_needed)
    4. Accumulate cost as consumed_qty * layer.unit_cost
    5. Update layer remaining_quantity
    6. Return total cost and consumed details
    7. Raise InsufficientCostLayerError if all layers exhausted

    Args:
        db: The async database session (should be within an active transaction).
        spare_part_id: UUID of the spare part to consume layers for.
        location_id: UUID of the location to consume layers from.
        quantity_to_consume: The total quantity to consume across layers.

    Returns:
        A tuple of (total_cost, consumed_details) where:
        - total_cost: The total COGS calculated as sum of (qty * unit_cost)
          for each layer consumed. Uses Decimal for monetary precision.
        - consumed_details: A list of dicts recording what was consumed from
          each layer, useful for audit trails and transfer propagation.
          Each dict contains: layer_id, quantity_consumed, unit_cost, layer_cost.

    Raises:
        InsufficientCostLayerError: If the total remaining quantity across
            all available layers is less than quantity_to_consume.

    Example:
        async with db.begin():
            total_cogs, details = await consume_fifo_layers(
                db=db,
                spare_part_id=part.id,
                location_id=warehouse.id,
                quantity_to_consume=Decimal("10"),
            )
    """
    # Query layers with remaining stock, ordered chronologically (FIFO).
    # SELECT FOR UPDATE ensures no concurrent transaction can modify these
    # layers until our transaction commits.
    stmt = (
        select(CostLayer)
        .filter(
            CostLayer.spare_part_id == spare_part_id,
            CostLayer.location_id == location_id,
            CostLayer.remaining_quantity > 0,
        )
        .order_by(CostLayer.created_at.asc())
        .with_for_update()
    )
    result = await db.execute(stmt)
    layers = result.scalars().all()

    total_cost = Decimal("0")
    remaining_needed = quantity_to_consume
    consumed_details: list[dict] = []

    for layer in layers:
        if remaining_needed <= 0:
            break

        # Consume the minimum of what this layer has and what we still need
        consume_from_layer = min(layer.remaining_quantity, remaining_needed)
        layer_cost = consume_from_layer * layer.unit_cost

        # Update the layer's remaining quantity
        layer.remaining_quantity -= consume_from_layer

        # Accumulate totals
        total_cost += layer_cost
        remaining_needed -= consume_from_layer

        # Record consumption details for audit/reporting
        consumed_details.append({
            "layer_id": layer.id,
            "quantity_consumed": consume_from_layer,
            "unit_cost": layer.unit_cost,
            "layer_cost": layer_cost,
        })

    # If we couldn't fulfill the full quantity, raise an error
    if remaining_needed > 0:
        raise InsufficientCostLayerError(
            spare_part_id=spare_part_id,
            location_id=location_id,
            shortfall=remaining_needed,
        )

    return total_cost, consumed_details
