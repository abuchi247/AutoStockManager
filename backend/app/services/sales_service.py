"""
Sales service implementing sales transaction logic.

Handles the sales lifecycle: create, confirm, return.
The service implements a state machine:
  DRAFT → CONFIRMED (on confirm)
  CONFIRMED → RETURNED (on return)
  DRAFT → CANCELLED (on cancel)

Satisfies:
- Requirement 5.1: Create a sale with customer, location, and line items
- Requirement 5.2: Reduce stock at selling location via ledger entries
- Requirement 5.6: Reject if quantity exceeds available stock
- Requirement 5.7: Calculate line_total = (quantity × unit_price) - discount_amount
- Requirement 5.8: Support sales returns reversing inventory and financial entries
- Requirement 5.9: Acquire pessimistic lock on stock records before validation
- Requirement 5.10: Stock validation and deduction in same transaction
- Requirement 5.11: Only one concurrent transaction succeeds for same stock
- Requirement 5.12: Return creates new Cost_Layer using original sale item's unit cost
- Requirement 5.13: Return Cost_Layer timestamp = return processing date (not original)
- Requirement 5.14: Never modify or re-open previously consumed/closed Cost_Layers
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_layer import CostLayer
from app.models.inventory_movement_ledger import MovementType
from app.models.sale import Sale, SaleItem, SaleStatus, PaymentType
from app.models.stock_status_cache import StockStatusCache
from app.utils.fifo import consume_fifo_layers
from app.utils.ledger import record_inventory_movement


# =============================================================================
# Custom Exceptions
# =============================================================================


class SaleNotFoundError(Exception):
    """Raised when the specified sale does not exist."""

    def __init__(self, sale_id: uuid.UUID):
        self.sale_id = sale_id
        super().__init__(f"Sale with id '{sale_id}' not found")


class InvalidSaleStatusError(Exception):
    """Raised when a sale operation is attempted on an invalid status."""

    def __init__(self, sale_id: uuid.UUID, current_status: str, expected_status: str):
        self.sale_id = sale_id
        self.current_status = current_status
        self.expected_status = expected_status
        super().__init__(
            f"Sale '{sale_id}' is in '{current_status}' status, "
            f"expected '{expected_status}'"
        )


class InsufficientStockError(Exception):
    """Raised when selling location doesn't have enough stock."""

    def __init__(
        self,
        spare_part_id: uuid.UUID,
        location_id: uuid.UUID,
        requested: Decimal,
        available: Decimal,
    ):
        self.spare_part_id = spare_part_id
        self.location_id = location_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for part '{spare_part_id}' at location '{location_id}'. "
            f"Requested: {requested}, Available: {available}"
        )


class SaleHasNoItemsError(Exception):
    """Raised when attempting to confirm a sale with no line items."""

    def __init__(self, sale_id: uuid.UUID):
        self.sale_id = sale_id
        super().__init__(f"Sale '{sale_id}' has no items and cannot be confirmed")


# =============================================================================
# Sales Service
# =============================================================================


class SalesService:
    """Service managing sales transactions.

    All mutating methods expect the caller to manage the transaction
    boundary (i.e., call commit or use `async with db.begin()`).
    """

    def __init__(self, db: AsyncSession, user_id: Optional[uuid.UUID] = None):
        self.db = db
        self.user_id = user_id

    # -------------------------------------------------------------------------
    # Create Sale
    # -------------------------------------------------------------------------

    async def create_sale(
        self,
        customer_id: Optional[uuid.UUID],
        location_id: uuid.UUID,
        payment_type: PaymentType = PaymentType.CASH,
        items: Optional[list[dict]] = None,
    ) -> Sale:
        """Create a new sale in DRAFT status.

        Args:
            customer_id: Optional customer UUID (None for walk-in).
            location_id: UUID of the selling location.
            payment_type: CASH or CREDIT.
            items: Optional list of item dicts with spare_part_id, quantity,
                   unit_price, and optional discount_amount.

        Returns:
            The newly created Sale record in DRAFT status.
        """
        sale = Sale(
            customer_id=customer_id,
            location_id=location_id,
            status=SaleStatus.DRAFT,
            payment_type=payment_type,
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            discount_total=Decimal("0.00"),
        )
        self.db.add(sale)
        await self.db.flush()

        if items:
            for item_data in items:
                quantity = Decimal(str(item_data["quantity"]))
                unit_price = Decimal(str(item_data["unit_price"]))
                discount_amount = Decimal(str(item_data.get("discount_amount", "0.00")))
                line_total = (quantity * unit_price) - discount_amount

                sale_item = SaleItem(
                    sale_id=sale.id,
                    spare_part_id=item_data["spare_part_id"],
                    quantity=quantity,
                    unit_price=unit_price,
                    discount_amount=discount_amount,
                    line_total=line_total,
                )
                self.db.add(sale_item)

            await self.db.flush()

        return sale

    # -------------------------------------------------------------------------
    # Confirm Sale
    # -------------------------------------------------------------------------

    async def confirm_sale(self, sale_id: uuid.UUID) -> Sale:
        """Confirm a DRAFT sale: validate stock, consume FIFO, record ledger.

        Steps:
        1. Validate sale is in DRAFT status with at least one item
        2. For each item: acquire pessimistic lock on cache, validate stock,
           consume FIFO layers, record ledger entry
        3. Generate invoice number
        4. Update sale totals and status

        Args:
            sale_id: UUID of the sale to confirm.

        Returns:
            The confirmed Sale with CONFIRMED status.

        Raises:
            SaleNotFoundError: If sale doesn't exist.
            InvalidSaleStatusError: If sale is not DRAFT.
            SaleHasNoItemsError: If sale has no line items.
            InsufficientStockError: If stock is insufficient.
        """
        import secrets
        import time

        sale = await self._get_sale_with_items(sale_id)

        if sale.status != SaleStatus.DRAFT:
            raise InvalidSaleStatusError(
                sale_id=sale_id,
                current_status=sale.status.value if isinstance(sale.status, SaleStatus) else str(sale.status),
                expected_status=SaleStatus.DRAFT.value,
            )

        if not sale.items:
            raise SaleHasNoItemsError(sale_id)

        total_discount = Decimal("0.00")
        subtotal = Decimal("0.00")

        for item in sale.items:
            # Acquire pessimistic lock on the cache row
            stmt = (
                select(StockStatusCache)
                .filter_by(
                    spare_part_id=item.spare_part_id,
                    location_id=sale.location_id,
                )
                .with_for_update()
            )
            result = await self.db.execute(stmt)
            cache = result.scalar_one_or_none()

            available = cache.current_quantity if cache else Decimal("0")
            if available < item.quantity:
                raise InsufficientStockError(
                    spare_part_id=item.spare_part_id,
                    location_id=sale.location_id,
                    requested=item.quantity,
                    available=available,
                )

            # Consume FIFO layers
            total_cogs, _ = await consume_fifo_layers(
                db=self.db,
                spare_part_id=item.spare_part_id,
                location_id=sale.location_id,
                quantity_to_consume=item.quantity,
            )

            # Set COGS on the item
            item.cost_of_goods_sold = total_cogs

            # Recalculate line total
            item.line_total = (item.quantity * item.unit_price) - item.discount_amount

            # Record SALE movement in ledger
            avg_unit_cost = total_cogs / item.quantity if item.quantity else Decimal("0")
            await record_inventory_movement(
                db=self.db,
                spare_part_id=item.spare_part_id,
                location_id=sale.location_id,
                quantity_change=-item.quantity,
                movement_type=MovementType.SALE.value,
                reference_type="sale",
                reference_id=sale.id,
                unit_cost=avg_unit_cost,
                created_by=self.user_id,
            )

            subtotal += item.line_total
            total_discount += item.discount_amount

        # Generate invoice number
        timestamp = str(int(time.time()))
        random_hex = secrets.token_hex(3)
        sale.invoice_number = f"INV-{timestamp}-{random_hex}"

        # Update totals
        sale.subtotal = subtotal
        sale.discount_total = total_discount
        sale.total_amount = subtotal + sale.tax_amount
        sale.status = SaleStatus.CONFIRMED

        await self.db.flush()
        return sale

    # -------------------------------------------------------------------------
    # Return Sale
    # -------------------------------------------------------------------------

    async def return_sale(
        self,
        sale_id: uuid.UUID,
        returned_by: uuid.UUID,
        return_items: Optional[list[dict]] = None,
    ) -> Sale:
        """Process a sales return, creating new cost layers and ledger entries.

        This method implements the return flow:
        1. Validate the sale is in CONFIRMED status
        2. For each sale item being returned:
           a. Create a NEW CostLayer at the sale's location with:
              - unit_cost = original sale item's unit_price (cost basis)
              - original_quantity = return quantity
              - remaining_quantity = return quantity
              - source_type = "return"
              - source_reference_id = sale.id
              - created_at = NOW() (return processing date, NOT original receipt date)
           b. Record RETURN movement via record_inventory_movement (positive qty)
        3. Update sale status to RETURNED

        Key rules:
        - NEVER modify or re-open previously consumed/closed cost layers (Req 5.14)
        - New cost layer timestamp = return processing date (Req 5.13)
        - Cost layer unit_cost comes from the original sale item's cost basis (Req 5.12)

        Args:
            sale_id: UUID of the sale to return.
            returned_by: UUID of the user processing the return.
            return_items: Optional list of dicts specifying which items to return
                and quantities. Each dict should have:
                - sale_item_id: UUID of the sale item
                - quantity: Decimal quantity to return
                If None, all items in the sale are returned in full.

        Returns:
            The updated Sale record with RETURNED status.

        Raises:
            SaleNotFoundError: If sale doesn't exist.
            InvalidSaleStatusError: If sale is not CONFIRMED.
        """
        sale = await self._get_sale_with_items(sale_id)

        if sale.status != SaleStatus.CONFIRMED:
            raise InvalidSaleStatusError(
                sale_id=sale_id,
                current_status=sale.status.value if isinstance(sale.status, SaleStatus) else str(sale.status),
                expected_status=SaleStatus.CONFIRMED.value,
            )

        # Determine which items and quantities to return
        items_to_return = self._resolve_return_items(sale, return_items)

        # Process each return item
        for sale_item, return_quantity in items_to_return:
            # Determine the unit cost for the new cost layer.
            # Use the COGS-derived unit cost if available (COGS / quantity gives
            # the actual average cost consumed during the sale). If not available,
            # fall back to the sale item's unit_price.
            if sale_item.cost_of_goods_sold is not None and sale_item.quantity > 0:
                unit_cost = sale_item.cost_of_goods_sold / sale_item.quantity
            else:
                unit_cost = sale_item.unit_price

            # Create a NEW CostLayer at the return location
            # created_at will be set by BaseModel default to NOW() (Req 5.13)
            new_layer = CostLayer(
                spare_part_id=sale_item.spare_part_id,
                location_id=sale.location_id,
                unit_cost=unit_cost,
                original_quantity=return_quantity,
                remaining_quantity=return_quantity,
                source_type="return",
                source_reference_id=sale.id,
            )
            self.db.add(new_layer)
            await self.db.flush()

            # Record RETURN movement in the ledger (positive quantity = inflow)
            await record_inventory_movement(
                db=self.db,
                spare_part_id=sale_item.spare_part_id,
                location_id=sale.location_id,
                quantity_change=return_quantity,
                movement_type=MovementType.RETURN.value,
                reference_type="sale",
                reference_id=sale.id,
                unit_cost=unit_cost,
                created_by=returned_by,
            )

        # Update sale status to RETURNED
        sale.status = SaleStatus.RETURNED

        await self.db.flush()
        return sale

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    async def _get_sale_with_items(self, sale_id: uuid.UUID) -> Sale:
        """Retrieve a sale with its items loaded, or raise SaleNotFoundError."""
        stmt = select(Sale).filter_by(id=sale_id)
        result = await self.db.execute(stmt)
        sale = result.scalar_one_or_none()

        if sale is None:
            raise SaleNotFoundError(sale_id)

        return sale

    def _resolve_return_items(
        self,
        sale: Sale,
        return_items: Optional[list[dict]],
    ) -> list[tuple[SaleItem, Decimal]]:
        """Resolve which sale items and quantities are being returned.

        Args:
            sale: The sale with items loaded.
            return_items: Optional explicit return specification. If None,
                all items are returned in full.

        Returns:
            List of (SaleItem, return_quantity) tuples.
        """
        if return_items is None:
            # Return all items in full
            return [(item, item.quantity) for item in sale.items]

        # Build lookup by sale_item_id
        items_by_id = {item.id: item for item in sale.items}
        resolved = []

        for return_spec in return_items:
            sale_item_id = return_spec["sale_item_id"]
            quantity = Decimal(str(return_spec["quantity"]))

            if sale_item_id in items_by_id:
                sale_item = items_by_id[sale_item_id]
                # Cap return quantity at original sale quantity
                actual_return_qty = min(quantity, sale_item.quantity)
                resolved.append((sale_item, actual_return_qty))

        return resolved
