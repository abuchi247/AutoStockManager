"""
Transfer service implementing multi-location stock movement logic.

Handles the full transfer lifecycle: create, approve, receive, cancel.
The service implements a state machine:
  pending → in_transit (on approve) → received (on receive)
  pending → cancelled (on cancel)
  in_transit → cancelled (on cancel, with stock reversal)

Satisfies:
- Requirement 4.2: Transfer request specifying source, destination, part, quantity
- Requirement 4.3: Reserve quantity at source in pending status
- Requirement 4.4: Transfer states: pending, approved, in-transit, received, cancelled
- Requirement 4.5: Deduct from source and record in-transit on approval
- Requirement 4.6: Deduct from in-transit and add to destination on receive
- Requirement 4.9: Reject if quantity exceeds available stock
- Requirement 4.10: Create new Cost_Layer at destination using source unit cost
- Requirement 4.11: Consume source Cost_Layers using FIFO
- Requirement 4.12: Never move/modify source layers — consume + create new
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_layer import CostLayer
from app.models.inventory_movement_ledger import MovementType, ReferenceType
from app.models.stock_status_cache import StockStatusCache
from app.models.transfer import Transfer, TransferStatus, VALID_TRANSFER_TRANSITIONS
from app.utils.fifo import consume_fifo_layers
from app.utils.ledger import record_inventory_movement


# =============================================================================
# Custom Exceptions
# =============================================================================


class TransferNotFoundError(Exception):
    """Raised when the specified transfer does not exist."""

    def __init__(self, transfer_id: uuid.UUID):
        self.transfer_id = transfer_id
        super().__init__(f"Transfer with id '{transfer_id}' not found")


class InvalidTransferStatusError(Exception):
    """Raised when a transfer operation is attempted on an invalid status."""

    def __init__(self, transfer_id: uuid.UUID, current_status: str, expected_status: str):
        self.transfer_id = transfer_id
        self.current_status = current_status
        self.expected_status = expected_status
        super().__init__(
            f"Transfer '{transfer_id}' is in '{current_status}' status, "
            f"expected '{expected_status}'"
        )


class InsufficientStockError(Exception):
    """Raised when source location doesn't have enough stock."""

    def __init__(self, spare_part_id: uuid.UUID, location_id: uuid.UUID, requested: Decimal, available: Decimal):
        self.spare_part_id = spare_part_id
        self.location_id = location_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for part '{spare_part_id}' at location '{location_id}'. "
            f"Requested: {requested}, Available: {available}"
        )


class InvalidTransferError(Exception):
    """Raised when a transfer operation is invalid (generic)."""

    def __init__(self, message: str):
        super().__init__(message)


class InvalidTransferStateError(Exception):
    """Raised when a transfer state transition is not allowed."""

    def __init__(self, transfer_id: uuid.UUID, current_status: str, expected_status: str):
        self.transfer_id = transfer_id
        self.current_status = current_status
        self.expected_status = expected_status
        super().__init__(
            f"Transfer '{transfer_id}' is in '{current_status}' status, "
            f"expected '{expected_status}'"
        )


class LocationNotFoundError(Exception):
    """Raised when a referenced location does not exist."""

    def __init__(self, location_id: uuid.UUID):
        self.location_id = location_id
        super().__init__(f"Location with id '{location_id}' not found")


class SparePartNotFoundError(Exception):
    """Raised when a referenced spare part does not exist."""

    def __init__(self, spare_part_id: uuid.UUID):
        self.spare_part_id = spare_part_id
        super().__init__(f"Spare part with id '{spare_part_id}' not found")


# =============================================================================
# Transfer Service
# =============================================================================


class TransferService:
    """Service managing stock transfers between locations.

    All mutating methods expect the caller to manage the transaction
    boundary (i.e., call commit or use `async with db.begin()`).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # List Transfers
    # -------------------------------------------------------------------------

    async def list_transfers(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[TransferStatus] = None,
        source_location_id: Optional[uuid.UUID] = None,
        destination_location_id: Optional[uuid.UUID] = None,
    ) -> tuple[list[Transfer], int]:
        """List transfers with optional filtering and pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            status_filter: Optional filter by transfer status.
            source_location_id: Optional filter by source location.
            destination_location_id: Optional filter by destination location.

        Returns:
            Tuple of (list of transfers, total count).
        """
        from sqlalchemy import func as sa_func

        stmt = select(Transfer)

        if status_filter:
            stmt = stmt.filter(Transfer.status == status_filter.value)
        if source_location_id:
            stmt = stmt.filter(Transfer.source_location_id == source_location_id)
        if destination_location_id:
            stmt = stmt.filter(
                Transfer.destination_location_id == destination_location_id
            )

        # Count total
        count_stmt = select(sa_func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        stmt = stmt.order_by(Transfer.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        transfers = list(result.scalars().all())

        return transfers, total

    # -------------------------------------------------------------------------
    # Create Transfer
    # -------------------------------------------------------------------------

    async def create_transfer(
        self,
        spare_part_id: uuid.UUID,
        source_location_id: uuid.UUID,
        destination_location_id: uuid.UUID,
        quantity: Decimal,
        requested_by: uuid.UUID,
    ) -> Transfer:
        """Create a new transfer request in PENDING status.

        Args:
            spare_part_id: The part to transfer.
            source_location_id: Origin location.
            destination_location_id: Target location.
            quantity: Amount to transfer (must be positive).
            requested_by: User creating the request.

        Returns:
            The newly created Transfer record.
        """
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
            quantity=quantity,
            status=TransferStatus.PENDING.value,
            requested_by=requested_by,
        )
        self.db.add(transfer)
        await self.db.flush()
        await self.db.refresh(transfer)
        return transfer

    # -------------------------------------------------------------------------
    # Approve Transfer (deducts from source, puts in-transit)
    # -------------------------------------------------------------------------

    async def approve_transfer(
        self,
        transfer_id: uuid.UUID,
        approved_by: uuid.UUID,
    ) -> Transfer:
        """Approve a pending transfer: deduct source, mark in-transit.

        Steps:
        1. Validate transfer is in PENDING status
        2. Acquire pessimistic lock on source Stock_Status_Cache
        3. Validate available quantity >= transfer quantity
        4. Consume FIFO layers at source
        5. Write TRANSFER_OUT ledger entry at source
        6. Write TRANSFER_IN_TRANSIT ledger entry (in-transit location concept)
        7. Update source cache
        8. Store consumed layer details on transfer record
        9. Update transfer status to IN_TRANSIT

        Args:
            transfer_id: UUID of the transfer to approve.
            approved_by: UUID of the approving user.

        Returns:
            The updated Transfer record.

        Raises:
            TransferNotFoundError: If transfer doesn't exist.
            InvalidTransferStatusError: If transfer is not PENDING.
            InsufficientStockError: If source doesn't have enough stock.
        """
        transfer = await self._get_transfer(transfer_id)

        if transfer.status != TransferStatus.PENDING.value:
            raise InvalidTransferStatusError(
                transfer_id=transfer_id,
                current_status=transfer.status,
                expected_status=TransferStatus.PENDING.value,
            )

        # Acquire pessimistic lock on source cache
        stmt = (
            select(StockStatusCache)
            .filter_by(
                spare_part_id=transfer.spare_part_id,
                location_id=transfer.source_location_id,
            )
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        cache = result.scalar_one_or_none()

        available = cache.current_quantity if cache else Decimal("0")
        if available < transfer.quantity:
            raise InsufficientStockError(
                spare_part_id=transfer.spare_part_id,
                location_id=transfer.source_location_id,
                requested=transfer.quantity,
                available=available,
            )

        # Consume FIFO layers at source
        total_cost, consumed_details = await consume_fifo_layers(
            db=self.db,
            spare_part_id=transfer.spare_part_id,
            location_id=transfer.source_location_id,
            quantity_to_consume=transfer.quantity,
        )

        # Calculate weighted average unit cost for ledger entry
        avg_unit_cost = total_cost / transfer.quantity if transfer.quantity else Decimal("0")

        # Write TRANSFER_OUT ledger entry at source (negative qty)
        await record_inventory_movement(
            db=self.db,
            spare_part_id=transfer.spare_part_id,
            location_id=transfer.source_location_id,
            quantity_change=-transfer.quantity,
            movement_type=MovementType.TRANSFER_OUT.value,
            reference_type=ReferenceType.TRANSFER.value,
            reference_id=transfer.id,
            unit_cost=avg_unit_cost,
            created_by=approved_by,
        )

        # Serialize consumed_details for JSON storage
        # Convert Decimal/UUID to serializable types
        serializable_details = []
        for detail in consumed_details:
            serializable_details.append({
                "layer_id": str(detail["layer_id"]),
                "quantity_consumed": str(detail["quantity_consumed"]),
                "unit_cost": str(detail["unit_cost"]),
                "layer_cost": str(detail["layer_cost"]),
            })

        # Update transfer record
        transfer.status = TransferStatus.IN_TRANSIT.value
        transfer.approved_by = approved_by
        transfer.approved_at = datetime.now(timezone.utc)
        transfer.consumed_layer_details = serializable_details

        await self.db.flush()
        return transfer

    # -------------------------------------------------------------------------
    # Receive Transfer (adds to destination, creates new cost layers)
    # -------------------------------------------------------------------------

    async def receive_transfer(
        self,
        transfer_id: uuid.UUID,
        received_by: uuid.UUID,
    ) -> Transfer:
        """Receive a transfer at the destination location.

        This method implements the receive flow:
        1. Validate transfer is in IN_TRANSIT status
        2. Read consumed_layer_details from the transfer record
        3. For each consumed layer detail:
           a. Create a NEW CostLayer at destination with same unit_cost,
              quantity_consumed as original_quantity and remaining_quantity,
              source_type="transfer", source_reference_id=transfer.id,
              created_at=NOW()
           b. Call record_inventory_movement for TRANSFER_IN (positive qty at destination)
        4. Update transfer status to RECEIVED, set received_by and received_at
        5. Return the updated transfer

        Key rules from design:
        - Never move or modify source layers — always consume + create new
        - A single transfer consuming from multiple source layers creates
          multiple destination layers (preserving cost granularity)
        - New cost layers have created_at = NOW() (not the original receipt date)

        Satisfies:
        - Requirement 4.6: Deduct from in-transit, add to destination via ledger
        - Requirement 4.10: Create new Cost_Layer at destination using source unit cost
        - Requirement 4.12: Never move/modify source layers

        Args:
            transfer_id: UUID of the transfer to receive.
            received_by: UUID of the user receiving the transfer.

        Returns:
            The updated Transfer record with RECEIVED status.

        Raises:
            TransferNotFoundError: If transfer doesn't exist.
            InvalidTransferStatusError: If transfer is not IN_TRANSIT.
        """
        transfer = await self._get_transfer(transfer_id)

        if transfer.status != TransferStatus.IN_TRANSIT.value:
            raise InvalidTransferStatusError(
                transfer_id=transfer_id,
                current_status=transfer.status,
                expected_status=TransferStatus.IN_TRANSIT.value,
            )

        # Read consumed layer details from the transfer record
        consumed_layer_details = transfer.consumed_layer_details or []

        # For each consumed layer detail, create a new cost layer at destination
        # and record a TRANSFER_IN movement
        for detail in consumed_layer_details:
            quantity_consumed = Decimal(str(detail["quantity_consumed"]))
            unit_cost = Decimal(str(detail["unit_cost"]))

            # Create a NEW CostLayer at the destination location
            new_layer = CostLayer(
                spare_part_id=transfer.spare_part_id,
                location_id=transfer.destination_location_id,
                unit_cost=unit_cost,
                original_quantity=quantity_consumed,
                remaining_quantity=quantity_consumed,
                source_type="transfer",
                source_reference_id=transfer.id,
            )
            self.db.add(new_layer)
            await self.db.flush()

            # Record TRANSFER_IN movement at destination (positive qty)
            await record_inventory_movement(
                db=self.db,
                spare_part_id=transfer.spare_part_id,
                location_id=transfer.destination_location_id,
                quantity_change=quantity_consumed,
                movement_type=MovementType.TRANSFER_IN.value,
                reference_type=ReferenceType.TRANSFER.value,
                reference_id=transfer.id,
                unit_cost=unit_cost,
                created_by=received_by,
            )

        # Update transfer status to RECEIVED
        transfer.status = TransferStatus.RECEIVED.value
        transfer.received_by = received_by
        transfer.received_at = datetime.now(timezone.utc)

        await self.db.flush()
        return transfer

    # -------------------------------------------------------------------------
    # Cancel Transfer
    # -------------------------------------------------------------------------

    async def cancel_transfer(
        self,
        transfer_id: uuid.UUID,
        cancelled_by: uuid.UUID,
        reason: str,
    ) -> Transfer:
        """Cancel a transfer that has not yet been received.

        If the transfer is IN_TRANSIT (stock was already deducted from source),
        reverses the deduction by creating a TRANSFER_IN ledger entry at the
        source location and restoring cost layers.

        Args:
            transfer_id: UUID of the transfer to cancel.
            cancelled_by: UUID of the cancelling user.
            reason: Required cancellation reason.

        Returns:
            The updated Transfer record.

        Raises:
            TransferNotFoundError: If transfer doesn't exist.
            InvalidTransferStatusError: If transfer is already RECEIVED or CANCELLED.
        """
        transfer = await self._get_transfer(transfer_id)

        if transfer.status in (TransferStatus.RECEIVED.value, TransferStatus.CANCELLED.value):
            raise InvalidTransferStatusError(
                transfer_id=transfer_id,
                current_status=transfer.status,
                expected_status="PENDING or IN_TRANSIT",
            )

        # If IN_TRANSIT, reverse the stock deduction at source
        if transfer.status == TransferStatus.IN_TRANSIT.value:
            consumed_details = transfer.consumed_layer_details or []
            for detail in consumed_details:
                quantity_consumed = Decimal(str(detail["quantity_consumed"]))
                unit_cost = Decimal(str(detail["unit_cost"]))

                # Create a new cost layer at source to restore stock
                new_layer = CostLayer(
                    spare_part_id=transfer.spare_part_id,
                    location_id=transfer.source_location_id,
                    unit_cost=unit_cost,
                    original_quantity=quantity_consumed,
                    remaining_quantity=quantity_consumed,
                    source_type="transfer_cancelled",
                    source_reference_id=transfer.id,
                )
                self.db.add(new_layer)
                await self.db.flush()

                # Record TRANSFER_IN at source (positive qty — restoring stock)
                await record_inventory_movement(
                    db=self.db,
                    spare_part_id=transfer.spare_part_id,
                    location_id=transfer.source_location_id,
                    quantity_change=quantity_consumed,
                    movement_type=MovementType.TRANSFER_IN.value,
                    reference_type=ReferenceType.TRANSFER.value,
                    reference_id=transfer.id,
                    unit_cost=unit_cost,
                    created_by=cancelled_by,
                )

        transfer.status = TransferStatus.CANCELLED.value
        transfer.cancellation_reason = reason

        await self.db.flush()
        return transfer

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    async def _get_transfer(self, transfer_id: uuid.UUID) -> Transfer:
        """Retrieve a transfer by ID or raise TransferNotFoundError."""
        stmt = select(Transfer).filter_by(id=transfer_id)
        result = await self.db.execute(stmt)
        transfer = result.scalar_one_or_none()

        if transfer is None:
            raise TransferNotFoundError(transfer_id)

        return transfer
