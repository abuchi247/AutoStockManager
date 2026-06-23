"""
Purchase service implementing PO lifecycle and GRN processing.

Handles the purchase order lifecycle: create, approve, receive goods (GRN), cancel.
The service implements the state machine:
  DRAFT → APPROVED (on approve)
  APPROVED → ORDERED (when sent to supplier, optional)
  APPROVED/ORDERED → PARTIALLY_RECEIVED (partial goods receipt)
  APPROVED/ORDERED/PARTIALLY_RECEIVED → RECEIVED (all items fully received)
  DRAFT/APPROVED/ORDERED/PARTIALLY_RECEIVED → CANCELLED (with reason)

GRN Processing (Critical Logic):
  When a GRN is confirmed:
  1. For each GRN line item: create an InventoryMovementLedger entry
     (type=PURCHASE, quantity_change=+received_qty)
  2. Create a new CostLayer at the receiving location with the unit_cost
     from the GRN line item
  3. Update the StockStatusCache atomically via the ledger helper
  4. Update PO item received quantities
  5. Update PO status based on whether all items are fully received
  6. Record a purchase debit in the SupplierLedger for the total GRN amount

Satisfies:
- Requirement 9.1: PO states: draft, approved, ordered, partially_received,
  received, cancelled
- Requirement 9.2: PO initial state is draft
- Requirement 9.3: Manager/Admin approves PO (draft → approved)
- Requirement 9.4: Goods received creates GRN recording received quantities
  per line item
- Requirement 9.5: GRN confirmation adds received quantities to location via
  inventory movement ledger
- Requirement 9.6: GRN confirmation updates PO state to partially_received
  or received
- Requirement 9.7: Cancelling an ordered/partially_received PO requires reason
  and Manager/Admin
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cost_layer import CostLayer
from app.models.goods_receipt_note import GoodsReceiptNote
from app.models.grn_items import GRNItem
from app.models.inventory_movement_ledger import MovementType
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)
from app.models.supplier_ledger import SupplierLedger, SupplierTransactionType
from app.utils.ledger import record_inventory_movement


# =============================================================================
# Custom Exceptions
# =============================================================================


class PurchaseOrderNotFoundError(Exception):
    """Raised when the specified purchase order does not exist."""

    def __init__(self, po_id: uuid.UUID):
        self.po_id = po_id
        super().__init__(f"Purchase order with id '{po_id}' not found")


class InvalidPOStatusError(Exception):
    """Raised when a PO operation is attempted on an invalid status."""

    def __init__(
        self, po_id: uuid.UUID, current_status: str, allowed_statuses: list[str]
    ):
        self.po_id = po_id
        self.current_status = current_status
        self.allowed_statuses = allowed_statuses
        super().__init__(
            f"Purchase order '{po_id}' is in '{current_status}' status, "
            f"allowed: {allowed_statuses}"
        )


class POHasNoItemsError(Exception):
    """Raised when attempting to approve a PO with no line items."""

    def __init__(self, po_id: uuid.UUID):
        self.po_id = po_id
        super().__init__(f"Purchase order '{po_id}' has no items")


class CancellationReasonRequiredError(Exception):
    """Raised when cancelling a PO without providing a reason."""

    def __init__(self, po_id: uuid.UUID):
        self.po_id = po_id
        super().__init__(
            f"Cancellation reason is required for purchase order '{po_id}'"
        )


class InvalidGRNQuantityError(Exception):
    """Raised when GRN quantity exceeds remaining ordered quantity."""

    def __init__(
        self,
        po_item_id: uuid.UUID,
        received: Decimal,
        remaining: Decimal,
    ):
        self.po_item_id = po_item_id
        self.received = received
        self.remaining = remaining
        super().__init__(
            f"GRN quantity {received} exceeds remaining ordered quantity "
            f"{remaining} for PO item '{po_item_id}'"
        )


# =============================================================================
# Purchase Service
# =============================================================================


class PurchaseService:
    """Service managing purchase order lifecycle and goods receipt processing.

    All mutating methods expect the caller to manage the transaction
    boundary (i.e., call commit or use `async with db.begin()`).
    """

    def __init__(self, db: AsyncSession, user_id: Optional[uuid.UUID] = None):
        self.db = db
        self.user_id = user_id

    # -------------------------------------------------------------------------
    # Create PO
    # -------------------------------------------------------------------------

    async def create_po(
        self,
        supplier_id: uuid.UUID,
        items: list[dict],
        notes: Optional[str] = None,
    ) -> PurchaseOrder:
        """Create a new purchase order in DRAFT status.

        Satisfies Requirement 9.2: WHEN a Purchase_Order is created,
        THE Purchase_Manager SHALL set the initial state to draft.

        Args:
            supplier_id: UUID of the supplier to order from.
            items: List of item dicts with keys:
                - spare_part_id: UUID of the spare part
                - quantity_ordered: Decimal quantity to order
                - unit_cost: Decimal cost per unit
            notes: Optional notes for the PO.

        Returns:
            The newly created PurchaseOrder in DRAFT status.
        """
        po = PurchaseOrder(
            supplier_id=supplier_id,
            status=PurchaseOrderStatus.DRAFT,
            total_amount=Decimal("0.00"),
            notes=notes,
            created_by=str(self.user_id) if self.user_id else None,
        )
        self.db.add(po)
        await self.db.flush()

        total_amount = Decimal("0.00")

        for item_data in items:
            quantity_ordered = Decimal(str(item_data["quantity_ordered"]))
            unit_cost = Decimal(str(item_data["unit_cost"]))

            po_item = PurchaseOrderItem(
                purchase_order_id=po.id,
                spare_part_id=item_data["spare_part_id"],
                quantity_ordered=quantity_ordered,
                quantity_received=Decimal("0.00"),
                unit_cost=unit_cost,
            )
            self.db.add(po_item)
            total_amount += quantity_ordered * unit_cost

        po.total_amount = total_amount
        await self.db.flush()
        await self.db.refresh(po)

        return po

    # -------------------------------------------------------------------------
    # Approve PO
    # -------------------------------------------------------------------------

    async def approve_po(
        self,
        po_id: uuid.UUID,
        approved_by: uuid.UUID,
    ) -> PurchaseOrder:
        """Approve a purchase order (DRAFT → APPROVED).

        Satisfies Requirement 9.3: WHEN a Purchase_Order is in draft state,
        THE Purchase_Manager SHALL allow a Manager or Admin user to approve
        the Purchase_Order, changing its state to approved.

        Args:
            po_id: UUID of the purchase order to approve.
            approved_by: UUID of the approving user (Manager/Admin).

        Returns:
            The approved PurchaseOrder.

        Raises:
            PurchaseOrderNotFoundError: If PO doesn't exist.
            InvalidPOStatusError: If PO is not in DRAFT status.
            POHasNoItemsError: If PO has no line items.
        """
        po = await self._get_po_with_items(po_id)

        if po.status != PurchaseOrderStatus.DRAFT:
            raise InvalidPOStatusError(
                po_id=po_id,
                current_status=po.status.value,
                allowed_statuses=[PurchaseOrderStatus.DRAFT.value],
            )

        if not po.items:
            raise POHasNoItemsError(po_id)

        po.status = PurchaseOrderStatus.APPROVED
        po.approved_by = approved_by
        po.approved_at = datetime.now(timezone.utc)

        # Recalculate total to ensure accuracy
        po.total_amount = po.calculate_total()

        await self.db.flush()
        return po

    # -------------------------------------------------------------------------
    # Receive Goods (GRN Processing)
    # -------------------------------------------------------------------------

    async def receive_goods(
        self,
        po_id: uuid.UUID,
        location_id: uuid.UUID,
        received_by: uuid.UUID,
        items: list[dict],
        notes: Optional[str] = None,
    ) -> GoodsReceiptNote:
        """Receive goods against a purchase order, creating a GRN.

        This is the critical GRN confirmation flow:
        1. Validate PO is in a receivable state
        2. Create GoodsReceiptNote and GRNItem records
        3. For each GRN line item:
           a. Update PO item's quantity_received
           b. Create a new CostLayer at the receiving location
           c. Record PURCHASE movement via record_inventory_movement
              (which atomically updates StockStatusCache)
        4. Update PO status based on whether all items are fully received
        5. Record a purchase debit in the SupplierLedger

        Satisfies Requirements 9.4, 9.5, 9.6.

        Args:
            po_id: UUID of the purchase order to receive against.
            location_id: UUID of the location where goods are being received.
            received_by: UUID of the user receiving the goods.
            items: List of dicts with keys:
                - po_item_id: UUID of the PurchaseOrderItem
                - quantity_received: Decimal quantity received
                - unit_cost: Optional Decimal override (defaults to PO item's unit_cost)
            notes: Optional notes for the GRN.

        Returns:
            The created GoodsReceiptNote with items.

        Raises:
            PurchaseOrderNotFoundError: If PO doesn't exist.
            InvalidPOStatusError: If PO is not in a receivable state.
            InvalidGRNQuantityError: If received qty exceeds remaining.
        """
        po = await self._get_po_with_items(po_id)

        # PO must be in a state that allows receiving
        receivable_statuses = [
            PurchaseOrderStatus.APPROVED,
            PurchaseOrderStatus.ORDERED,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
        ]
        if po.status not in receivable_statuses:
            raise InvalidPOStatusError(
                po_id=po_id,
                current_status=po.status.value,
                allowed_statuses=[s.value for s in receivable_statuses],
            )

        # Build a lookup of PO items by ID
        po_items_by_id = {item.id: item for item in po.items}

        # Create the GRN record
        grn = GoodsReceiptNote(
            purchase_order_id=po.id,
            location_id=location_id,
            received_by=received_by,
            received_at=datetime.now(timezone.utc),
            notes=notes,
            created_by=str(self.user_id) if self.user_id else None,
        )
        self.db.add(grn)
        await self.db.flush()

        total_grn_amount = Decimal("0.00")

        for item_data in items:
            po_item_id = item_data["po_item_id"]
            quantity_received = Decimal(str(item_data["quantity_received"]))

            # Validate PO item exists
            if po_item_id not in po_items_by_id:
                raise PurchaseOrderNotFoundError(po_id)

            po_item = po_items_by_id[po_item_id]

            # Use override unit_cost if provided, otherwise PO item's unit_cost
            unit_cost = Decimal(str(item_data.get("unit_cost", po_item.unit_cost)))

            # Validate quantity doesn't exceed remaining
            remaining = po_item.quantity_ordered - po_item.quantity_received
            if quantity_received > remaining:
                raise InvalidGRNQuantityError(
                    po_item_id=po_item_id,
                    received=quantity_received,
                    remaining=remaining,
                )

            # Create GRN line item
            grn_item = GRNItem(
                grn_id=grn.id,
                po_item_id=po_item_id,
                spare_part_id=po_item.spare_part_id,
                quantity_received=quantity_received,
                unit_cost=unit_cost,
                created_by=str(self.user_id) if self.user_id else None,
            )
            self.db.add(grn_item)

            # Update PO item's quantity_received
            po_item.quantity_received += quantity_received

            # Create a new CostLayer at the receiving location
            cost_layer = CostLayer(
                spare_part_id=po_item.spare_part_id,
                location_id=location_id,
                unit_cost=unit_cost,
                original_quantity=quantity_received,
                remaining_quantity=quantity_received,
                source_type="purchase",
                source_reference_id=grn.id,
                created_by=str(self.user_id) if self.user_id else None,
            )
            self.db.add(cost_layer)

            # Record PURCHASE movement in the ledger (positive quantity = inflow)
            # This also atomically updates StockStatusCache
            await record_inventory_movement(
                db=self.db,
                spare_part_id=po_item.spare_part_id,
                location_id=location_id,
                quantity_change=quantity_received,
                movement_type=MovementType.PURCHASE.value,
                reference_type="grn",
                reference_id=grn.id,
                unit_cost=unit_cost,
                created_by=received_by,
            )

            total_grn_amount += quantity_received * unit_cost

        # Update PO status based on whether all items are fully received
        await self._update_po_status_after_receipt(po)

        # Record purchase debit in SupplierLedger for the total GRN amount
        if total_grn_amount > Decimal("0"):
            supplier_entry = SupplierLedger(
                supplier_id=po.supplier_id,
                transaction_type=SupplierTransactionType.PURCHASE.value,
                amount=total_grn_amount,
                reference_type="grn",
                reference_id=grn.id,
                notes=f"GRN for PO {po.id}",
                created_by=received_by,
            )
            self.db.add(supplier_entry)

        await self.db.flush()
        await self.db.refresh(grn)

        return grn

    # -------------------------------------------------------------------------
    # Cancel PO
    # -------------------------------------------------------------------------

    async def cancel_po(
        self,
        po_id: uuid.UUID,
        cancelled_by: uuid.UUID,
        reason: Optional[str] = None,
    ) -> PurchaseOrder:
        """Cancel a purchase order.

        Satisfies Requirement 9.7: WHEN a Purchase_Order in ordered or
        partially_received state is cancelled, THE Purchase_Manager SHALL
        require a cancellation reason and Manager/Admin authorization.

        For DRAFT status, no reason is required.
        For APPROVED/ORDERED/PARTIALLY_RECEIVED, a reason is required.

        Args:
            po_id: UUID of the purchase order to cancel.
            cancelled_by: UUID of the user cancelling (Manager/Admin).
            reason: Cancellation reason (required for non-draft POs).

        Returns:
            The cancelled PurchaseOrder.

        Raises:
            PurchaseOrderNotFoundError: If PO doesn't exist.
            InvalidPOStatusError: If PO is already received or cancelled.
            CancellationReasonRequiredError: If reason is missing for
                ordered/partially_received POs.
        """
        po = await self._get_po_with_items(po_id)

        # Cannot cancel already received or cancelled POs
        non_cancellable = [
            PurchaseOrderStatus.RECEIVED,
            PurchaseOrderStatus.CANCELLED,
        ]
        if po.status in non_cancellable:
            raise InvalidPOStatusError(
                po_id=po_id,
                current_status=po.status.value,
                allowed_statuses=[
                    s.value
                    for s in PurchaseOrderStatus
                    if s not in non_cancellable
                ],
            )

        # Require reason for non-draft POs (Requirement 9.7)
        requires_reason = [
            PurchaseOrderStatus.APPROVED,
            PurchaseOrderStatus.ORDERED,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
        ]
        if po.status in requires_reason and not reason:
            raise CancellationReasonRequiredError(po_id)

        po.status = PurchaseOrderStatus.CANCELLED

        # Store reason in notes (append if existing notes)
        if reason:
            cancel_note = f"[CANCELLED by {cancelled_by}]: {reason}"
            if po.notes:
                po.notes = f"{po.notes}\n{cancel_note}"
            else:
                po.notes = cancel_note

        await self.db.flush()
        return po

    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------

    async def get_po(self, po_id: uuid.UUID) -> PurchaseOrder:
        """Retrieve a purchase order by ID with items loaded.

        Args:
            po_id: UUID of the purchase order.

        Returns:
            The PurchaseOrder with items.

        Raises:
            PurchaseOrderNotFoundError: If PO doesn't exist.
        """
        return await self._get_po_with_items(po_id)

    async def list_pos(
        self,
        supplier_id: Optional[uuid.UUID] = None,
        status: Optional[PurchaseOrderStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PurchaseOrder], int]:
        """List purchase orders with optional filters.

        Args:
            supplier_id: Optional filter by supplier.
            status: Optional filter by status.
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Tuple of (list of POs, total count).
        """
        from sqlalchemy import func

        filters = []
        if supplier_id:
            filters.append(PurchaseOrder.supplier_id == supplier_id)
        if status:
            filters.append(PurchaseOrder.status == status)

        # Count total
        count_stmt = select(func.count(PurchaseOrder.id)).filter(*filters)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(PurchaseOrder)
            .filter(*filters)
            .order_by(PurchaseOrder.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        pos = list(result.scalars().all())

        return pos, total

    async def get_grns_for_po(self, po_id: uuid.UUID) -> list[GoodsReceiptNote]:
        """Retrieve all GRNs for a purchase order.

        Args:
            po_id: UUID of the purchase order.

        Returns:
            List of GoodsReceiptNote records.
        """
        stmt = (
            select(GoodsReceiptNote)
            .filter(GoodsReceiptNote.purchase_order_id == po_id)
            .order_by(GoodsReceiptNote.received_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    async def _get_po_with_items(self, po_id: uuid.UUID) -> PurchaseOrder:
        """Retrieve a PO with items loaded, or raise PurchaseOrderNotFoundError."""
        stmt = select(PurchaseOrder).filter_by(id=po_id)
        result = await self.db.execute(stmt)
        po = result.scalar_one_or_none()

        if po is None:
            raise PurchaseOrderNotFoundError(po_id)

        return po

    async def _update_po_status_after_receipt(self, po: PurchaseOrder) -> None:
        """Update PO status based on line item received quantities.

        Satisfies Requirement 9.6: WHEN a Goods_Receipt_Note is confirmed,
        THE Purchase_Manager SHALL update the Purchase_Order state to
        partially_received if some items remain, or received if all items
        are fully received.

        Args:
            po: The PurchaseOrder with items loaded and updated quantities.
        """
        all_received = all(
            item.quantity_received >= item.quantity_ordered for item in po.items
        )

        if all_received:
            po.status = PurchaseOrderStatus.RECEIVED
        else:
            po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
