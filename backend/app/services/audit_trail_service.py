"""
Audit Trail service for the Auto Spare Parts ERP system.

Provides append-only event recording and query capabilities for the audit trail.
This service enforces the immutability constraint — it only exposes record_event
and query methods, with no update or delete operations.

Satisfies Requirements:
- 2.6: Record user identity, action type, timestamp, entity, old/new values on CRUD
- 15.1: Record: timestamp, user identity, action type, entity type, entity id,
        old values, new values
- 15.2: Critical events: login/logout, CRUD, approval, payment, stock adjustment
- 15.3: Retain all records for 7 years minimum (no delete capability)
- 15.4: Store old/new values as structured data for field-level comparison
- 15.5: Support querying by user, entity_type, entity_id, action_type, date_range
- 15.6: Append-only — no user including Admin can modify or delete audit trail records
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_trail import ActionType, AuditTrail


# =============================================================================
# Custom Exceptions
# =============================================================================


class AuditTrailImmutableError(Exception):
    """Raised when an attempt is made to modify or delete an audit trail record.

    Satisfies Requirement 15.6: Append-only — no user including Admin can
    modify or delete audit trail records.
    """

    def __init__(self, operation: str):
        self.message = (
            f"Operation '{operation}' is not permitted on audit trail records. "
            f"Audit trail is append-only."
        )
        super().__init__(self.message)


# =============================================================================
# Query Filters Dataclass
# =============================================================================


class AuditTrailFilters:
    """Filter parameters for querying audit trail events.

    Supports querying by user, entity_type, entity_id, action_type, and
    date_range as required by Requirement 15.5.
    """

    def __init__(
        self,
        user_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ):
        self.user_id = user_id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.action_type = action_type
        self.start_date = start_date
        self.end_date = end_date
        self.page = page
        self.page_size = page_size


# =============================================================================
# Audit Trail Service
# =============================================================================


class AuditTrailService:
    """Service handling audit trail recording and querying.

    This service intentionally does NOT provide update or delete methods.
    The audit trail is append-only (Requirement 15.6). Any attempt to call
    update or delete will raise AuditTrailImmutableError.

    Methods:
        record_event  - Record a new audit trail entry
        query_events  - Query audit trail with multiple filters
        get_event_by_id - Retrieve a single audit event by ID
    """

    def __init__(self, db: AsyncSession):
        """Initialize the audit trail service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Record Event (Append-Only Write)
    # -------------------------------------------------------------------------

    async def record_event(
        self,
        user_id: UUID,
        action_type: str,
        entity_type: str,
        entity_id: Optional[UUID] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditTrail:
        """Record a new audit trail event.

        Creates an append-only audit trail entry capturing the action performed,
        the user who performed it, the affected entity, and the before/after
        state as structured JSON.

        Satisfies Requirements 2.6, 15.1, 15.2, 15.4:
        - Records user identity, action type, timestamp
        - Records entity type and entity id
        - Stores old/new values as structured data for field-level comparison
        - Supports all critical events (login/logout, CRUD, approvals, payments,
          stock adjustments)

        Args:
            user_id: UUID of the user who performed the action.
            action_type: Type of action (use ActionType enum values).
            entity_type: Type of entity affected (e.g., 'spare_part', 'sale').
            entity_id: UUID of the affected entity (None for login/logout).
            old_values: JSON-serializable dict of entity state before action.
            new_values: JSON-serializable dict of entity state after action.
            ip_address: IP address from which the action was performed.

        Returns:
            The newly created AuditTrail instance.
        """
        audit_entry = AuditTrail(
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
        )
        self.db.add(audit_entry)
        await self.db.flush()
        await self.db.refresh(audit_entry)
        return audit_entry

    # -------------------------------------------------------------------------
    # Query Events (Read-Only)
    # -------------------------------------------------------------------------

    async def query_events(
        self,
        filters: AuditTrailFilters,
    ) -> tuple[list[AuditTrail], int]:
        """Query audit trail events with multiple filter options.

        Satisfies Requirement 15.5: Support querying by user, entity_type,
        entity_id, action_type, date_range.

        Args:
            filters: AuditTrailFilters instance containing query parameters.

        Returns:
            Tuple of (list of matching AuditTrail entries, total count).
        """
        conditions = self._build_filter_conditions(filters)

        # Count total matching records
        count_stmt = select(func.count(AuditTrail.id)).filter(*conditions)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results (newest first)
        offset = (filters.page - 1) * filters.page_size
        stmt = (
            select(AuditTrail)
            .filter(*conditions)
            .order_by(AuditTrail.created_at.desc())
            .offset(offset)
            .limit(filters.page_size)
        )
        result = await self.db.execute(stmt)
        events = list(result.scalars().all())

        return events, total

    async def get_event_by_id(self, event_id: UUID) -> Optional[AuditTrail]:
        """Retrieve a single audit trail event by its ID.

        Args:
            event_id: UUID of the audit trail entry.

        Returns:
            The AuditTrail instance if found, None otherwise.
        """
        stmt = select(AuditTrail).filter(AuditTrail.id == event_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Immutability Enforcement (Requirement 15.6)
    # -------------------------------------------------------------------------

    async def update_event(self, *args, **kwargs) -> None:
        """BLOCKED: Audit trail records cannot be updated.

        Raises:
            AuditTrailImmutableError: Always raised — updates are not permitted.
        """
        raise AuditTrailImmutableError("UPDATE")

    async def delete_event(self, *args, **kwargs) -> None:
        """BLOCKED: Audit trail records cannot be deleted.

        Raises:
            AuditTrailImmutableError: Always raised — deletes are not permitted.
        """
        raise AuditTrailImmutableError("DELETE")

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _build_filter_conditions(self, filters: AuditTrailFilters) -> list:
        """Build SQLAlchemy filter conditions from AuditTrailFilters.

        Args:
            filters: The filter parameters to convert to conditions.

        Returns:
            List of SQLAlchemy filter expressions.
        """
        conditions = []

        if filters.user_id is not None:
            conditions.append(AuditTrail.user_id == filters.user_id)

        if filters.entity_type is not None:
            conditions.append(AuditTrail.entity_type == filters.entity_type)

        if filters.entity_id is not None:
            conditions.append(AuditTrail.entity_id == filters.entity_id)

        if filters.action_type is not None:
            conditions.append(AuditTrail.action_type == filters.action_type)

        if filters.start_date is not None:
            conditions.append(AuditTrail.created_at >= filters.start_date)

        if filters.end_date is not None:
            conditions.append(AuditTrail.created_at <= filters.end_date)

        return conditions
