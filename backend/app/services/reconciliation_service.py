"""
Reconciliation service for the Auto Spare Parts ERP system.

Provides periodic reconciliation between the Stock_Status_Cache and the
Inventory_Movement_Ledger to detect and correct drift. When mismatches are
found, the cache is corrected and admin notifications are generated.

Satisfies Requirements:
- 18.4: Perform periodic reconciliation between cache and ledger to detect/correct drift
- 18.6: If reconciliation detects mismatch, log discrepancy, correct cache, generate admin notification
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_movement_ledger import InventoryMovementLedger
from app.models.notification import NotificationType
from app.models.stock_status_cache import StockStatusCache
from app.models.user import User, UserRole
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ReconciliationMismatch:
    """Represents a single detected mismatch between cache and ledger."""

    spare_part_id: UUID
    location_id: UUID
    cached_quantity: Decimal
    expected_quantity: Decimal
    drift: Decimal


@dataclass
class ReconciliationResult:
    """Summary of a reconciliation run."""

    total_cache_entries: int = 0
    mismatches_found: int = 0
    mismatches_corrected: int = 0
    details: list[ReconciliationMismatch] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def has_mismatches(self) -> bool:
        """Return True if any mismatches were detected."""
        return self.mismatches_found > 0


# =============================================================================
# Reconciliation Service
# =============================================================================


class ReconciliationService:
    """Service for periodic reconciliation of Stock_Status_Cache against ledger.

    Compares each entry in the Stock_Status_Cache against the sum of
    quantity_change values in the Inventory_Movement_Ledger for the same
    (spare_part_id, location_id) pair. If a mismatch is detected, the cache
    is corrected, the discrepancy is logged, and admin notifications are created.

    Satisfies Requirement 18.4: THE ERP_System SHALL perform periodic
    reconciliation between the Stock_Status_Cache and the
    Inventory_Movement_Ledger to detect and correct any drift.

    Satisfies Requirement 18.6: IF reconciliation detects a mismatch between
    the Stock_Status_Cache and the Inventory_Movement_Ledger sum, THEN THE
    ERP_System SHALL log the discrepancy, correct the cache, and generate an
    admin notification.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the reconciliation service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db
        self.notification_service = NotificationService(db)

    async def reconcile_stock(self) -> ReconciliationResult:
        """Perform full reconciliation of Stock_Status_Cache vs ledger.

        Algorithm:
        1. Query all entries in Stock_Status_Cache
        2. For each entry, compute the expected quantity from SUM(quantity_change)
           in Inventory_Movement_Ledger for the same (spare_part_id, location_id)
        3. Compare expected vs cached quantity
        4. If mismatch: log discrepancy, correct cache, notify admins

        Returns:
            ReconciliationResult with summary of mismatches found and corrected.
        """
        result = ReconciliationResult(
            started_at=datetime.now(timezone.utc),
        )

        # Step 1: Get all cache entries
        cache_entries = await self._get_all_cache_entries()
        result.total_cache_entries = len(cache_entries)

        if not cache_entries:
            result.completed_at = datetime.now(timezone.utc)
            return result

        # Step 2-3: Compare each cache entry against ledger sum
        mismatches = await self._detect_mismatches(cache_entries)
        result.mismatches_found = len(mismatches)
        result.details = mismatches

        # Step 4: Correct mismatches and notify
        if mismatches:
            await self._correct_mismatches(mismatches)
            result.mismatches_corrected = len(mismatches)

            # Generate admin notifications for drift
            await self._notify_admins_of_drift(mismatches)

            logger.warning(
                "Reconciliation found %d mismatches out of %d cache entries. "
                "All corrected.",
                len(mismatches),
                len(cache_entries),
            )
        else:
            logger.info(
                "Reconciliation complete. No mismatches found across %d cache entries.",
                len(cache_entries),
            )

        result.completed_at = datetime.now(timezone.utc)
        return result

    async def _get_all_cache_entries(self) -> list[StockStatusCache]:
        """Retrieve all entries from the Stock_Status_Cache.

        Returns:
            List of all StockStatusCache rows.
        """
        stmt = select(StockStatusCache)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _compute_ledger_sum(
        self, spare_part_id: UUID, location_id: UUID
    ) -> Decimal:
        """Compute expected quantity from ledger for a (part, location) pair.

        Args:
            spare_part_id: The spare part to sum movements for.
            location_id: The location to sum movements for.

        Returns:
            The sum of all quantity_change values, or Decimal("0") if none exist.
        """
        stmt = select(
            func.coalesce(
                func.sum(InventoryMovementLedger.quantity_change),
                Decimal("0"),
            )
        ).filter(
            InventoryMovementLedger.spare_part_id == spare_part_id,
            InventoryMovementLedger.location_id == location_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or Decimal("0")

    async def _detect_mismatches(
        self, cache_entries: list[StockStatusCache]
    ) -> list[ReconciliationMismatch]:
        """Compare cache entries against ledger sums and detect drift.

        Args:
            cache_entries: List of cache rows to validate.

        Returns:
            List of mismatches where cached quantity differs from ledger sum.
        """
        mismatches: list[ReconciliationMismatch] = []

        for entry in cache_entries:
            expected_qty = await self._compute_ledger_sum(
                entry.spare_part_id, entry.location_id
            )

            if entry.current_quantity != expected_qty:
                drift = entry.current_quantity - expected_qty
                mismatch = ReconciliationMismatch(
                    spare_part_id=entry.spare_part_id,
                    location_id=entry.location_id,
                    cached_quantity=entry.current_quantity,
                    expected_quantity=expected_qty,
                    drift=drift,
                )
                mismatches.append(mismatch)

                logger.warning(
                    "Stock drift detected: part=%s, location=%s, "
                    "cached=%s, expected=%s, drift=%s",
                    entry.spare_part_id,
                    entry.location_id,
                    entry.current_quantity,
                    expected_qty,
                    drift,
                )

        return mismatches

    async def _correct_mismatches(
        self, mismatches: list[ReconciliationMismatch]
    ) -> None:
        """Correct cache entries to match ledger sums.

        Updates each mismatched cache row's current_quantity to the expected
        value computed from the ledger, and sets last_reconciled_at.

        Args:
            mismatches: List of detected mismatches to correct.
        """
        now = datetime.now(timezone.utc)

        for mismatch in mismatches:
            stmt = (
                select(StockStatusCache)
                .filter(
                    StockStatusCache.spare_part_id == mismatch.spare_part_id,
                    StockStatusCache.location_id == mismatch.location_id,
                )
            )
            result = await self.db.execute(stmt)
            cache_entry = result.scalar_one()

            cache_entry.current_quantity = mismatch.expected_quantity
            cache_entry.last_reconciled_at = now

            logger.info(
                "Corrected cache: part=%s, location=%s, "
                "old=%s, new=%s",
                mismatch.spare_part_id,
                mismatch.location_id,
                mismatch.cached_quantity,
                mismatch.expected_quantity,
            )

        await self.db.flush()

    async def _notify_admins_of_drift(
        self, mismatches: list[ReconciliationMismatch]
    ) -> None:
        """Generate admin notifications for detected stock drift.

        Creates a single notification per admin user summarizing all
        mismatches found during reconciliation.

        Satisfies Requirement 18.6: Generate admin notification when
        reconciliation detects mismatch.

        Args:
            mismatches: List of detected and corrected mismatches.
        """
        # Get admin users
        target_roles = [UserRole.ADMIN.value, UserRole.MANAGER.value]
        stmt = select(User).filter(
            User.role.in_(target_roles),
            User.is_active == True,  # noqa: E712
            User.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        admin_users = list(result.scalars().all())

        if not admin_users:
            return

        # Build summary message
        total_drift_entries = len(mismatches)
        message = (
            f"Periodic stock reconciliation detected {total_drift_entries} "
            f"mismatch(es) between Stock_Status_Cache and "
            f"Inventory_Movement_Ledger. All entries have been corrected."
        )

        # Build metadata with drift details (limited to first 10 for brevity)
        drift_details = [
            {
                "spare_part_id": str(m.spare_part_id),
                "location_id": str(m.location_id),
                "cached_quantity": str(m.cached_quantity),
                "expected_quantity": str(m.expected_quantity),
                "drift": str(m.drift),
            }
            for m in mismatches[:10]
        ]

        metadata = {
            "total_mismatches": total_drift_entries,
            "drift_details": drift_details,
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
        }

        # Create notification for each admin/manager
        for user in admin_users:
            await self.notification_service.create_notification(
                user_id=user.id,
                notification_type=NotificationType.SYSTEM.value,
                title="Stock Reconciliation: Drift Detected",
                message=message,
                metadata=metadata,
            )


# =============================================================================
# Standalone Callable (for scheduler integration)
# =============================================================================


async def run_reconciliation(db: AsyncSession) -> ReconciliationResult:
    """Standalone function to run reconciliation.

    Designed to be called from a scheduler (e.g., APScheduler, Celery beat)
    or a FastAPI background task.

    Args:
        db: Async SQLAlchemy session.

    Returns:
        ReconciliationResult with summary of the run.
    """
    service = ReconciliationService(db)
    return await service.reconcile_stock()
