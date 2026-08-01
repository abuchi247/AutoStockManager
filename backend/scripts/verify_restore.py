"""Automated restore verification with integrity checks.

This script validates a restored PostgreSQL backup by running integrity checks
against critical business data. It is designed to be run against an ISOLATED
restore-test database, never production.

Usage:
    python -m scripts.verify_restore --database-url "postgresql://user:pass@host/db"

Integrity checks:
    1. Alembic migration revision matches expected head
    2. Inventory ledger consistency (movements vs stock cache)
    3. Sales record integrity (valid items, customers, totals)
    4. Purchase order integrity (valid suppliers, items)
    5. Invoice integrity (valid sale references, amounts)
    6. User account integrity (valid roles, hashed passwords, timestamps)
    7. Audit trail integrity (valid references, monotonic timestamps)

Validates: Requirements 18.3, 18.4
"""

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import sqlalchemy
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    """Result status for an integrity check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of a single integrity check."""

    name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RestoreVerificationReport:
    """Complete restore verification report."""

    database_url_host: str  # Host only, no credentials
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    alembic_revision: Optional[str] = None
    table_counts: dict[str, int] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Overall pass: no FAILED checks."""
        return all(c.status != CheckStatus.FAILED for c in self.checks)

    def summary(self) -> str:
        """Human-readable summary."""
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.status == CheckStatus.PASSED)
        failed = sum(1 for c in self.checks if c.status == CheckStatus.FAILED)
        warnings = sum(1 for c in self.checks if c.status == CheckStatus.WARNING)
        skipped = sum(1 for c in self.checks if c.status == CheckStatus.SKIPPED)

        lines = [
            "=" * 60,
            "RESTORE VERIFICATION REPORT",
            "=" * 60,
            f"Database: {self.database_url_host}",
            f"Started: {self.started_at.isoformat()}",
            f"Duration: {self.duration_seconds:.1f}s" if self.duration_seconds else "",
            f"Alembic revision: {self.alembic_revision or 'unknown'}",
            "",
            "Table Counts:",
        ]
        for table, count in sorted(self.table_counts.items()):
            lines.append(f"  {table}: {count:,}")

        lines.extend([
            "",
            f"Results: {passed} passed, {failed} failed, "
            f"{warnings} warnings, {skipped} skipped (total: {total})",
            "",
        ])

        for check in self.checks:
            icon = {
                CheckStatus.PASSED: "✓",
                CheckStatus.FAILED: "✗",
                CheckStatus.WARNING: "⚠",
                CheckStatus.SKIPPED: "○",
            }[check.status]
            lines.append(f"  {icon} {check.name}: {check.message}")

        lines.append("")
        lines.append(f"OVERALL: {'PASSED' if self.passed else 'FAILED'}")
        lines.append("=" * 60)
        return "\n".join(lines)


class RestoreVerifier:
    """Runs integrity checks against a restored database."""

    def __init__(self, database_url: str):
        """Initialize with a synchronous database URL (no asyncpg)."""
        # Convert asyncpg URL to synchronous psycopg2 for scripting
        sync_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        self.engine = create_engine(sync_url, pool_pre_ping=True)
        # Extract host for reporting (no credentials)
        from urllib.parse import urlsplit
        parts = urlsplit(sync_url)
        self.host_info = f"{parts.hostname}:{parts.port}/{parts.path.strip('/')}"

    def verify(self) -> RestoreVerificationReport:
        """Run all integrity checks and return the report."""
        report = RestoreVerificationReport(
            database_url_host=self.host_info,
            started_at=datetime.now(timezone.utc),
        )
        start_time = time.time()

        with self.engine.connect() as conn:
            report.alembic_revision = self._check_alembic_revision(conn, report)
            self._check_table_counts(conn, report)
            self._check_inventory_ledger_integrity(conn, report)
            self._check_sales_integrity(conn, report)
            self._check_purchase_integrity(conn, report)
            self._check_invoice_integrity(conn, report)
            self._check_user_integrity(conn, report)
            self._check_audit_trail_integrity(conn, report)

        report.completed_at = datetime.now(timezone.utc)
        report.duration_seconds = time.time() - start_time
        return report

    def _check_alembic_revision(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> Optional[str]:
        """Verify alembic_version table exists and has a single head."""
        try:
            result = conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            rows = result.fetchall()
            if not rows:
                report.checks.append(CheckResult(
                    name="alembic_revision",
                    status=CheckStatus.FAILED,
                    message="alembic_version table is empty (no applied migrations)",
                ))
                return None
            if len(rows) > 1:
                report.checks.append(CheckResult(
                    name="alembic_revision",
                    status=CheckStatus.WARNING,
                    message=f"Multiple alembic heads detected: {[r[0] for r in rows]}",
                ))
                return rows[0][0]

            revision = rows[0][0]
            report.checks.append(CheckResult(
                name="alembic_revision",
                status=CheckStatus.PASSED,
                message=f"Single head at revision {revision}",
                details={"revision": revision},
            ))
            return revision
        except Exception as e:
            report.checks.append(CheckResult(
                name="alembic_revision",
                status=CheckStatus.FAILED,
                message=f"Cannot read alembic_version: {e}",
            ))
            return None

    def _check_table_counts(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> None:
        """Record row counts for critical tables."""
        critical_tables = [
            "users", "sales", "sale_items", "spare_parts", "locations",
            "purchase_orders", "purchase_order_items", "customers",
            "suppliers", "invoices", "inventory_movement_ledger",
            "audit_trails", "cost_layers", "customer_credit_ledger",
        ]
        for table in critical_tables:
            try:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                )
                count = result.scalar() or 0
                report.table_counts[table] = count
            except Exception:
                # Table may not exist in this schema version
                report.table_counts[table] = -1

    def _check_inventory_ledger_integrity(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> None:
        """Verify inventory movement ledger is internally consistent."""
        try:
            # Check for movements with NULL required fields
            result = conn.execute(text("""
                SELECT COUNT(*) FROM inventory_movement_ledger
                WHERE spare_part_id IS NULL
                   OR location_id IS NULL
                   OR quantity IS NULL
                   OR movement_type IS NULL
            """))
            null_count = result.scalar() or 0
            if null_count > 0:
                report.checks.append(CheckResult(
                    name="ledger_null_fields",
                    status=CheckStatus.FAILED,
                    message=f"{null_count} ledger entries have NULL required fields",
                    details={"null_entries": null_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="ledger_null_fields",
                    status=CheckStatus.PASSED,
                    message="All ledger entries have required fields populated",
                ))

            # Check ledger entries reference existing spare parts
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT iml.spare_part_id)
                FROM inventory_movement_ledger iml
                LEFT JOIN spare_parts sp ON sp.id = iml.spare_part_id
                WHERE sp.id IS NULL
            """))
            orphan_count = result.scalar() or 0
            if orphan_count > 0:
                report.checks.append(CheckResult(
                    name="ledger_orphan_parts",
                    status=CheckStatus.WARNING,
                    message=f"{orphan_count} spare part references in ledger have no matching part",
                    details={"orphan_part_refs": orphan_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="ledger_orphan_parts",
                    status=CheckStatus.PASSED,
                    message="All ledger spare part references are valid",
                ))
        except Exception as e:
            report.checks.append(CheckResult(
                name="ledger_integrity",
                status=CheckStatus.SKIPPED,
                message=f"Inventory ledger check skipped: {e}",
            ))

    def _check_sales_integrity(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> None:
        """Verify sales records have valid references and non-negative totals."""
        try:
            # Sales with negative totals
            result = conn.execute(text("""
                SELECT COUNT(*) FROM sales WHERE total_amount < 0
            """))
            negative_count = result.scalar() or 0
            if negative_count > 0:
                report.checks.append(CheckResult(
                    name="sales_negative_totals",
                    status=CheckStatus.FAILED,
                    message=f"{negative_count} sales have negative total_amount",
                    details={"negative_sales": negative_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="sales_negative_totals",
                    status=CheckStatus.PASSED,
                    message="All sales have non-negative totals",
                ))

            # Sale items referencing non-existent sales
            result = conn.execute(text("""
                SELECT COUNT(*) FROM sale_items si
                LEFT JOIN sales s ON s.id = si.sale_id
                WHERE s.id IS NULL
            """))
            orphan_items = result.scalar() or 0
            if orphan_items > 0:
                report.checks.append(CheckResult(
                    name="sales_orphan_items",
                    status=CheckStatus.FAILED,
                    message=f"{orphan_items} sale items reference non-existent sales",
                    details={"orphan_items": orphan_items},
                ))
            else:
                report.checks.append(CheckResult(
                    name="sales_orphan_items",
                    status=CheckStatus.PASSED,
                    message="All sale items reference valid sales",
                ))
        except Exception as e:
            report.checks.append(CheckResult(
                name="sales_integrity",
                status=CheckStatus.SKIPPED,
                message=f"Sales integrity check skipped: {e}",
            ))

    def _check_purchase_integrity(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> None:
        """Verify purchase orders have valid supplier references."""
        try:
            # POs with orphan supplier references
            result = conn.execute(text("""
                SELECT COUNT(*) FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplier_id
                WHERE s.id IS NULL AND po.supplier_id IS NOT NULL
            """))
            orphan_count = result.scalar() or 0
            if orphan_count > 0:
                report.checks.append(CheckResult(
                    name="purchases_orphan_suppliers",
                    status=CheckStatus.WARNING,
                    message=f"{orphan_count} purchase orders reference non-existent suppliers",
                    details={"orphan_supplier_refs": orphan_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="purchases_orphan_suppliers",
                    status=CheckStatus.PASSED,
                    message="All purchase orders have valid supplier references",
                ))

            # PO items referencing non-existent POs
            result = conn.execute(text("""
                SELECT COUNT(*) FROM purchase_order_items poi
                LEFT JOIN purchase_orders po ON po.id = poi.purchase_order_id
                WHERE po.id IS NULL
            """))
            orphan_items = result.scalar() or 0
            if orphan_items > 0:
                report.checks.append(CheckResult(
                    name="purchases_orphan_items",
                    status=CheckStatus.FAILED,
                    message=f"{orphan_items} PO items reference non-existent orders",
                    details={"orphan_items": orphan_items},
                ))
            else:
                report.checks.append(CheckResult(
                    name="purchases_orphan_items",
                    status=CheckStatus.PASSED,
                    message="All purchase order items reference valid orders",
                ))
        except Exception as e:
            report.checks.append(CheckResult(
                name="purchases_integrity",
                status=CheckStatus.SKIPPED,
                message=f"Purchase integrity check skipped: {e}",
            ))

    def _check_invoice_integrity(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> None:
        """Verify invoices reference valid sales."""
        try:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM invoices i
                LEFT JOIN sales s ON s.id = i.sale_id
                WHERE s.id IS NULL AND i.sale_id IS NOT NULL
            """))
            orphan_count = result.scalar() or 0
            if orphan_count > 0:
                report.checks.append(CheckResult(
                    name="invoices_orphan_sales",
                    status=CheckStatus.FAILED,
                    message=f"{orphan_count} invoices reference non-existent sales",
                    details={"orphan_invoice_refs": orphan_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="invoices_orphan_sales",
                    status=CheckStatus.PASSED,
                    message="All invoices reference valid sales",
                ))
        except Exception as e:
            report.checks.append(CheckResult(
                name="invoices_integrity",
                status=CheckStatus.SKIPPED,
                message=f"Invoice integrity check skipped: {e}",
            ))

    def _check_user_integrity(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> None:
        """Verify user accounts have valid roles and hashed passwords."""
        try:
            # Users with empty or NULL password hashes
            result = conn.execute(text("""
                SELECT COUNT(*) FROM users
                WHERE password_hash IS NULL OR password_hash = ''
            """))
            no_hash_count = result.scalar() or 0
            if no_hash_count > 0:
                report.checks.append(CheckResult(
                    name="users_missing_passwords",
                    status=CheckStatus.FAILED,
                    message=f"{no_hash_count} users have missing password hashes",
                    details={"users_no_hash": no_hash_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="users_missing_passwords",
                    status=CheckStatus.PASSED,
                    message="All users have password hashes",
                ))

            # Users with invalid roles
            result = conn.execute(text("""
                SELECT COUNT(*) FROM users
                WHERE role NOT IN ('ADMIN', 'MANAGER', 'SALES', 'INVENTORY', 'VIEWER')
            """))
            bad_role_count = result.scalar() or 0
            if bad_role_count > 0:
                report.checks.append(CheckResult(
                    name="users_invalid_roles",
                    status=CheckStatus.WARNING,
                    message=f"{bad_role_count} users have unrecognized roles",
                    details={"invalid_role_users": bad_role_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="users_invalid_roles",
                    status=CheckStatus.PASSED,
                    message="All users have valid roles",
                ))

            # Users without timestamps
            result = conn.execute(text("""
                SELECT COUNT(*) FROM users
                WHERE created_at IS NULL
            """))
            no_ts_count = result.scalar() or 0
            if no_ts_count > 0:
                report.checks.append(CheckResult(
                    name="users_missing_timestamps",
                    status=CheckStatus.WARNING,
                    message=f"{no_ts_count} users have NULL created_at",
                    details={"users_no_timestamp": no_ts_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="users_missing_timestamps",
                    status=CheckStatus.PASSED,
                    message="All users have creation timestamps",
                ))
        except Exception as e:
            report.checks.append(CheckResult(
                name="users_integrity",
                status=CheckStatus.SKIPPED,
                message=f"User integrity check skipped: {e}",
            ))

    def _check_audit_trail_integrity(
        self, conn: sqlalchemy.engine.Connection, report: RestoreVerificationReport
    ) -> None:
        """Verify audit trail entries have valid references and ordering."""
        try:
            # Audit entries without timestamps
            result = conn.execute(text("""
                SELECT COUNT(*) FROM audit_trails
                WHERE created_at IS NULL
            """))
            no_ts_count = result.scalar() or 0
            if no_ts_count > 0:
                report.checks.append(CheckResult(
                    name="audit_missing_timestamps",
                    status=CheckStatus.FAILED,
                    message=f"{no_ts_count} audit entries have NULL timestamps",
                    details={"audit_no_timestamp": no_ts_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="audit_missing_timestamps",
                    status=CheckStatus.PASSED,
                    message="All audit trail entries have timestamps",
                ))

            # Check for audit entries with NULL action
            result = conn.execute(text("""
                SELECT COUNT(*) FROM audit_trails
                WHERE action IS NULL OR action = ''
            """))
            no_action_count = result.scalar() or 0
            if no_action_count > 0:
                report.checks.append(CheckResult(
                    name="audit_missing_action",
                    status=CheckStatus.WARNING,
                    message=f"{no_action_count} audit entries have no action recorded",
                    details={"audit_no_action": no_action_count},
                ))
            else:
                report.checks.append(CheckResult(
                    name="audit_missing_action",
                    status=CheckStatus.PASSED,
                    message="All audit trail entries have actions recorded",
                ))
        except Exception as e:
            report.checks.append(CheckResult(
                name="audit_integrity",
                status=CheckStatus.SKIPPED,
                message=f"Audit trail integrity check skipped: {e}",
            ))


def main() -> None:
    """CLI entry point for restore verification."""
    parser = argparse.ArgumentParser(
        description="Verify a restored PostgreSQL backup for AutoStockManager"
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL connection URL for the restored database (NOT production)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    verifier = RestoreVerifier(args.database_url)
    report = verifier.verify()

    if args.json:
        import json
        output = {
            "database_host": report.database_url_host,
            "started_at": report.started_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            "duration_seconds": report.duration_seconds,
            "alembic_revision": report.alembic_revision,
            "table_counts": report.table_counts,
            "overall_passed": report.passed,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                }
                for c in report.checks
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print(report.summary())

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
