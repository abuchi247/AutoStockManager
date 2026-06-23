"""
Audit service implementing snapshot-based inventory audit logic.

This service implements the full audit lifecycle:
1. initiate_audit - Captures Stock_Status_Cache snapshot at initiation time
2. submit_count - Calculates variance against snapshot (not live quantity)
3. complete_audit - Creates adjustment ledger entries to align system with counted
4. get_reconciliation_view - Shows post-snapshot movements for auditor review
5. check_recount_required - Flags spare parts with movements during active audit

The snapshot-based approach ensures that stock movements occurring after audit
initiation do not corrupt variance calculations. A reconciliation view shows
post-snapshot movements separately for auditor review.

Satisfies:
- Requirement 11.3: Calculate variance as counted_quantity - system_quantity (snapshot)
- Requirement 11.4: Complete audit creates adjustment entries in ledger
- Requirement 11.5: Maintain history of all audit sessions
- Requirement 11.6: Flag stock movements during active audit as requiring re-count
- Requirement 11.7: Capture snapshot of system quantities at initiation timestamp
- Requirement 11.8: Compare physical count against snapshot (not current live quantity)
- Requirement 11.9: Exclude post-snapshot ledger entries from initial variance
- Requirement 11.10: Provide reconciliation view showing post-snapshot movements
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_session import (
    AuditSession,
    AuditSnapshotItem,
    AuditCount,
    AuditType,
    AuditStatus,
)
from app.models.inventory_movement_ledger import (
    InventoryMovementLedger,
    MovementType,
    ReferenceType,
)
from app.models.stock_status_cache import StockStatusCache
from app.utils.ledger import record_inventory_movement


# =============================================================================
# Custom Exceptions
# =============================================================================


class AuditSessionNotFoundError(Exception):
    """Raised when the specified audit session does not exist."""

    def __init__(self, session_id: uuid.UUID):
        self.session_id = session_id
        super().__init__(f"Audit session with id '{session_id}' not found")


class InvalidAuditStatusError(Exception):
    """Raised when an audit operation is attempted on an invalid status."""

    def __init__(self, session_id: uuid.UUID, current_status: str, expected_status: str):
        self.session_id = session_id
        self.current_status = current_status
        self.expected_status = expected_status
        super().__init__(
            f"Audit session '{session_id}' is in '{current_status}' status, "
            f"expected '{expected_status}'"
        )


class SnapshotItemNotFoundError(Exception):
    """Raised when no snapshot item exists for the given part in the session."""

    def __init__(self, session_id: uuid.UUID, spare_part_id: uuid.UUID):
        self.session_id = session_id
        self.spare_part_id = spare_part_id
        super().__init__(
            f"No snapshot item for spare part '{spare_part_id}' "
            f"in audit session '{session_id}'"
        )


class DuplicateCountError(Exception):
    """Raised when a count has already been submitted for this part in the session."""

    def __init__(self, session_id: uuid.UUID, spare_part_id: uuid.UUID):
        self.session_id = session_id
        self.spare_part_id = spare_part_id
        super().__init__(
            f"A count has already been submitted for spare part '{spare_part_id}' "
            f"in audit session '{session_id}'"
        )


# =============================================================================
# Data Transfer Objects
# =============================================================================


class ReconciliationMovement:
    """Represents a post-snapshot movement shown in the reconciliation view."""

    def __init__(
        self,
        ledger_entry_id: uuid.UUID,
        spare_part_id: uuid.UUID,
        quantity_change: Decimal,
        movement_type: str,
        reference_type: str,
        reference_id: uuid.UUID,
        created_at: datetime,
        created_by: uuid.UUID,
    ):
        self.ledger_entry_id = ledger_entry_id
        self.spare_part_id = spare_part_id
        self.quantity_change = quantity_change
        self.movement_type = movement_type
        self.reference_type = reference_type
        self.reference_id = reference_id
        self.created_at = created_at
        self.created_by = created_by


class RecountFlag:
    """Represents a spare part flagged as requiring re-count."""

    def __init__(
        self,
        spare_part_id: uuid.UUID,
        movement_count: int,
        net_quantity_change: Decimal,
    ):
        self.spare_part_id = spare_part_id
        self.movement_count = movement_count
        self.net_quantity_change = net_quantity_change


# =============================================================================
# Audit Service
# =============================================================================


class AuditService:
    """Service managing snapshot-based inventory audits.

    All mutating methods expect the caller to manage the transaction
    boundary (i.e., call commit or use `async with db.begin()`).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # Initiate Audit
    # -------------------------------------------------------------------------

    async def initiate_audit(
        self,
        location_id: uuid.UUID,
        audit_type: AuditType,
        initiated_by: uuid.UUID,
        spare_part_ids: Optional[list[uuid.UUID]] = None,
    ) -> AuditSession:
        """Initiate an audit session by capturing a snapshot of current stock.

        Creates an AuditSession with snapshot_timestamp=NOW() and captures
        the current Stock_Status_Cache quantities into AuditSnapshotItem records.

        For FULL_STOCK_COUNT: captures all parts at the specified location.
        For CYCLE_COUNT: captures only the specified spare_part_ids.

        Satisfies:
        - Requirement 11.7: Capture snapshot of system quantities at initiation timestamp
        - Requirement 11.5: Maintain history of all audit sessions

        Args:
            location_id: UUID of the location being audited.
            audit_type: Type of audit (CYCLE_COUNT or FULL_STOCK_COUNT).
            initiated_by: UUID of the user initiating the audit.
            spare_part_ids: List of part IDs for CYCLE_COUNT (ignored for FULL).

        Returns:
            The newly created AuditSession with snapshot items populated.
        """
        now = datetime.now(timezone.utc)

        # Create the audit session
        session = AuditSession(
            location_id=location_id,
            audit_type=audit_type,
            status=AuditStatus.INITIATED,
            snapshot_timestamp=now,
            initiated_by=initiated_by,
        )
        self.db.add(session)
        await self.db.flush()

        # Query Stock_Status_Cache for the location
        stmt = select(StockStatusCache).filter_by(location_id=location_id)

        if audit_type == AuditType.CYCLE_COUNT and spare_part_ids:
            # For cycle count, only capture specified parts
            stmt = stmt.filter(StockStatusCache.spare_part_id.in_(spare_part_ids))

        result = await self.db.execute(stmt)
        cache_rows = result.scalars().all()

        # Create snapshot items for each cache row
        for cache_row in cache_rows:
            snapshot_item = AuditSnapshotItem(
                session_id=session.id,
                spare_part_id=cache_row.spare_part_id,
                snapshot_quantity=cache_row.current_quantity,
            )
            self.db.add(snapshot_item)

        await self.db.flush()
        await self.db.refresh(session)
        return session

    # -------------------------------------------------------------------------
    # Submit Count
    # -------------------------------------------------------------------------

    async def submit_count(
        self,
        session_id: uuid.UUID,
        spare_part_id: uuid.UUID,
        counted_quantity: Decimal,
        counted_by: uuid.UUID,
    ) -> AuditCount:
        """Submit a physical count for a spare part in an active audit session.

        Looks up the snapshot_quantity for this part and calculates:
            variance = counted_quantity - snapshot_quantity

        The variance is calculated against the snapshot, NOT the current live
        quantity in Stock_Status_Cache. This ensures post-snapshot movements
        don't affect the variance calculation.

        Satisfies:
        - Requirement 11.3: Calculate variance as counted_quantity - system_quantity (snapshot)
        - Requirement 11.8: Compare physical count against snapshot (not current live quantity)
        - Requirement 11.9: Exclude post-snapshot ledger entries from initial variance

        Args:
            session_id: UUID of the audit session.
            spare_part_id: UUID of the spare part being counted.
            counted_quantity: The actual physical count quantity.
            counted_by: UUID of the user performing the count.

        Returns:
            The newly created AuditCount record with calculated variance.

        Raises:
            AuditSessionNotFoundError: If session doesn't exist.
            InvalidAuditStatusError: If session is not INITIATED or IN_PROGRESS.
            SnapshotItemNotFoundError: If no snapshot exists for this part.
        """
        session = await self._get_session(session_id)

        # Validate session is in a countable state
        if session.status not in (AuditStatus.INITIATED, AuditStatus.IN_PROGRESS):
            raise InvalidAuditStatusError(
                session_id=session_id,
                current_status=session.status.value if isinstance(session.status, AuditStatus) else session.status,
                expected_status="INITIATED or IN_PROGRESS",
            )

        # Look up the snapshot quantity for this part
        stmt = select(AuditSnapshotItem).filter_by(
            session_id=session_id,
            spare_part_id=spare_part_id,
        )
        result = await self.db.execute(stmt)
        snapshot_item = result.scalar_one_or_none()

        if snapshot_item is None:
            raise SnapshotItemNotFoundError(
                session_id=session_id,
                spare_part_id=spare_part_id,
            )

        # Calculate variance = counted_quantity - snapshot_quantity
        variance = counted_quantity - snapshot_item.snapshot_quantity

        # Create the audit count record
        audit_count = AuditCount(
            session_id=session_id,
            spare_part_id=spare_part_id,
            counted_quantity=counted_quantity,
            variance=variance,
            counted_by=counted_by,
            counted_at=datetime.now(timezone.utc),
        )
        self.db.add(audit_count)

        # Transition session to IN_PROGRESS if still INITIATED
        if session.status == AuditStatus.INITIATED:
            session.status = AuditStatus.IN_PROGRESS

        await self.db.flush()
        await self.db.refresh(audit_count)
        return audit_count

    # -------------------------------------------------------------------------
    # Complete Audit
    # -------------------------------------------------------------------------

    async def complete_audit(
        self,
        session_id: uuid.UUID,
        approved_by: uuid.UUID,
    ) -> AuditSession:
        """Complete an audit session by creating adjustment ledger entries.

        For each non-zero variance in the audit counts:
        - Creates an ADJUSTMENT entry in the InventoryMovementLedger
        - Updates the StockStatusCache atomically (via record_inventory_movement)

        The adjustment quantity equals the variance (counted - snapshot), which
        aligns the system quantity with the physical count.

        Satisfies:
        - Requirement 11.4: Complete audit creates adjustment entries in ledger

        Args:
            session_id: UUID of the audit session to complete.
            approved_by: UUID of the user approving the audit.

        Returns:
            The updated AuditSession with COMPLETED status.

        Raises:
            AuditSessionNotFoundError: If session doesn't exist.
            InvalidAuditStatusError: If session is not IN_PROGRESS.
        """
        session = await self._get_session(session_id)

        if session.status not in (AuditStatus.INITIATED, AuditStatus.IN_PROGRESS):
            raise InvalidAuditStatusError(
                session_id=session_id,
                current_status=session.status.value if isinstance(session.status, AuditStatus) else session.status,
                expected_status="INITIATED or IN_PROGRESS",
            )

        # Get all audit counts for this session
        stmt = select(AuditCount).filter_by(session_id=session_id)
        result = await self.db.execute(stmt)
        counts = result.scalars().all()

        # For each non-zero variance, create an adjustment ledger entry
        for count in counts:
            if count.variance != Decimal("0"):
                await record_inventory_movement(
                    db=self.db,
                    spare_part_id=count.spare_part_id,
                    location_id=session.location_id,
                    quantity_change=count.variance,
                    movement_type=MovementType.ADJUSTMENT.value,
                    reference_type=ReferenceType.AUDIT.value,
                    reference_id=session.id,
                    unit_cost=Decimal("0"),
                    created_by=approved_by,
                )

        # Update session status
        session.status = AuditStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)
        session.approved_by = approved_by

        await self.db.flush()
        return session

    # -------------------------------------------------------------------------
    # Reconciliation View
    # -------------------------------------------------------------------------

    async def get_reconciliation_view(
        self,
        session_id: uuid.UUID,
    ) -> list[ReconciliationMovement]:
        """Get post-snapshot movements for auditor review.

        Queries the InventoryMovementLedger for all movements at the audit
        location that occurred after the snapshot_timestamp. These movements
        are excluded from variance calculations but shown to auditors for
        context and decision-making.

        Satisfies:
        - Requirement 11.10: Provide reconciliation view showing post-snapshot movements

        Args:
            session_id: UUID of the audit session.

        Returns:
            List of ReconciliationMovement objects representing post-snapshot
            movements at the audited location.

        Raises:
            AuditSessionNotFoundError: If session doesn't exist.
        """
        session = await self._get_session(session_id)

        # Query ledger entries after the snapshot timestamp at the same location
        stmt = (
            select(InventoryMovementLedger)
            .filter(
                InventoryMovementLedger.location_id == session.location_id,
                InventoryMovementLedger.created_at > session.snapshot_timestamp,
            )
            .order_by(InventoryMovementLedger.created_at.asc())
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        movements = []
        for entry in entries:
            movements.append(
                ReconciliationMovement(
                    ledger_entry_id=entry.id,
                    spare_part_id=entry.spare_part_id,
                    quantity_change=entry.quantity_change,
                    movement_type=entry.movement_type,
                    reference_type=entry.reference_type,
                    reference_id=entry.reference_id,
                    created_at=entry.created_at,
                    created_by=entry.created_by,
                )
            )

        return movements

    # -------------------------------------------------------------------------
    # Re-count Flagging
    # -------------------------------------------------------------------------

    async def check_recount_required(
        self,
        session_id: uuid.UUID,
    ) -> list[RecountFlag]:
        """Check which spare parts require re-count due to movements during audit.

        Identifies spare parts at the audit location that have had stock
        movements since the snapshot_timestamp. These parts may have
        inaccurate counts because the physical stock has changed since
        the snapshot was taken.

        Satisfies:
        - Requirement 11.6: Flag stock movements during active audit as requiring re-count

        Args:
            session_id: UUID of the audit session.

        Returns:
            List of RecountFlag objects for parts with post-snapshot movements.

        Raises:
            AuditSessionNotFoundError: If session doesn't exist.
        """
        session = await self._get_session(session_id)

        # Get the spare_part_ids that are in this audit's snapshot
        snapshot_stmt = select(AuditSnapshotItem.spare_part_id).filter_by(
            session_id=session_id
        )
        snapshot_result = await self.db.execute(snapshot_stmt)
        audited_part_ids = [row[0] for row in snapshot_result.all()]

        if not audited_part_ids:
            return []

        # Query ledger for movements affecting audited parts after snapshot
        stmt = (
            select(
                InventoryMovementLedger.spare_part_id,
                func.count(InventoryMovementLedger.id).label("movement_count"),
                func.sum(InventoryMovementLedger.quantity_change).label("net_change"),
            )
            .filter(
                InventoryMovementLedger.location_id == session.location_id,
                InventoryMovementLedger.created_at > session.snapshot_timestamp,
                InventoryMovementLedger.spare_part_id.in_(audited_part_ids),
            )
            .group_by(InventoryMovementLedger.spare_part_id)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        flags = []
        for row in rows:
            flags.append(
                RecountFlag(
                    spare_part_id=row[0],
                    movement_count=row[1],
                    net_quantity_change=row[2] or Decimal("0"),
                )
            )

        return flags

    # -------------------------------------------------------------------------
    # List Sessions
    # -------------------------------------------------------------------------

    async def list_sessions(
        self,
        location_id: Optional[uuid.UUID] = None,
        status_filter: Optional[AuditStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditSession], int]:
        """List audit sessions with optional filtering and pagination.

        Satisfies:
        - Requirement 11.5: Maintain history of all audit sessions

        Args:
            location_id: Optional filter by location.
            status_filter: Optional filter by session status.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of sessions, total count).
        """
        stmt = select(AuditSession)

        if location_id:
            stmt = stmt.filter(AuditSession.location_id == location_id)
        if status_filter:
            stmt = stmt.filter(AuditSession.status == status_filter)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        stmt = stmt.order_by(AuditSession.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        sessions = list(result.scalars().all())

        return sessions, total

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    async def _get_session(self, session_id: uuid.UUID) -> AuditSession:
        """Retrieve an audit session by ID or raise AuditSessionNotFoundError."""
        stmt = select(AuditSession).filter_by(id=session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            raise AuditSessionNotFoundError(session_id)

        return session
