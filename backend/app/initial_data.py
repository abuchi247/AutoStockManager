"""Auto-seed reference data on first startup.

Called from the application lifespan in main.py immediately after
ensure_initial_admin(). All functions here are idempotent — they check
whether data already exists and exit early if so, making them safe to call
on every container restart.

Seeded data:
  - Default categories (10 parent categories, 37 subcategories)
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.category import Category

# Arbitrary, stable key for the Postgres advisory lock that serializes the
# category seed across concurrent worker startups (categories have no unique
# constraint, so a race would insert duplicate trees rather than raise).
_CATEGORY_SEED_LOCK_KEY = 872_314_501

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default category tree
# This is the single source of truth used by:
#   - The startup seeder (this file, called from main.py lifespan)
#   - backend/scripts/seed_categories.py  (manual CLI fallback)
#   - backend/scripts/setup_db.py          (all-in-one deploy script)
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Brakes": ["Brake Pads", "Brake Discs", "Brake Fluid"],
    "Filters": ["Oil Filters", "Air Filters", "Fuel Filters", "Cabin Filters"],
    "Engine Parts": ["Pistons", "Gaskets", "Timing Belts", "Spark Plugs"],
    "Electrical": ["Batteries", "Alternators", "Starters", "Sensors"],
    "Suspension": ["Shock Absorbers", "Springs", "Control Arms"],
    "Body Parts": ["Bumpers", "Fenders", "Mirrors", "Lights"],
    "Transmission": ["Clutch", "Gearbox", "CV Joints"],
    "Cooling": ["Radiators", "Water Pumps", "Thermostats", "Hoses"],
    "Exhaust": ["Mufflers", "Catalytic Converters", "Exhaust Pipes"],
    "Fuel System": ["Fuel Pumps", "Injectors", "Fuel Lines"],
}


async def ensure_default_categories() -> None:
    """Create the default category tree if the categories table is empty.

    This is safe to call on every startup — it only inserts rows when the
    table has no active (non-deleted) categories at all (i.e. a completely
    fresh database). Existing data is never touched.
    """
    async with async_session_factory() as session:
        # Serialize the check-and-insert across concurrent uvicorn workers.
        # The categories table has no unique constraint on name, so without a
        # lock two workers could both see an empty table and each insert the
        # full tree, producing duplicates. A transaction-scoped Postgres
        # advisory lock makes exactly one worker do the seed; the lock releases
        # when this transaction ends.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"),
            {"k": _CATEGORY_SEED_LOCK_KEY},
        )

        result = await session.execute(
            select(func.count(Category.id)).where(Category.deleted_at.is_(None))
        )
        existing = result.scalar_one()

        if existing > 0:
            logger.debug(
                "default_categories_skipped",
                extra={"reason": "categories_exist", "count": existing},
            )
            return

        now = datetime.now(timezone.utc)
        created = 0

        for parent_name, subcategory_names in DEFAULT_CATEGORIES.items():
            parent_id = uuid.uuid4()
            parent = Category(
                id=parent_id,
                name=parent_name,
                parent_id=None,
                description=f"Auto spare parts — {parent_name}",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(parent)
            created += 1

            for sub_name in subcategory_names:
                sub = Category(
                    id=uuid.uuid4(),
                    name=sub_name,
                    parent_id=parent_id,
                    description=f"{parent_name} — {sub_name}",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(sub)
                created += 1

        await session.commit()

        logger.warning(
            "default_categories_seeded",
            extra={
                "parent_count": len(DEFAULT_CATEGORIES),
                "total_count": created,
            },
        )
        print(f"\n  ✓ Seeded {created} default categories "
              f"({len(DEFAULT_CATEGORIES)} parent, "
              f"{created - len(DEFAULT_CATEGORIES)} subcategories)\n")


# ---------------------------------------------------------------------------
# Default role permissions
# ---------------------------------------------------------------------------

ALL_PERMISSIONS = [
    "sales",
    "sales_returns",
    "customers",
    "credit_management",
    "inventory",
    "purchasing",
    "receiving",
    "transfers",
    "transfer_approval",
    "locations",
    "categories",
    "audits",
    "audit_approval",
    "reports",
    "invoices",
    "user_management",
    "system_settings",
]

DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "Admin": {p: True for p in ALL_PERMISSIONS},
    "Manager": {
        "sales": True, "sales_returns": True, "customers": True,
        "credit_management": True, "inventory": True, "purchasing": True,
        "receiving": True, "transfers": True, "transfer_approval": True,
        "locations": True, "categories": True, "audits": True,
        "audit_approval": True, "reports": True, "invoices": True,
        "user_management": False, "system_settings": False,
    },
    "Salesperson": {
        "sales": True, "sales_returns": False, "customers": True,
        "credit_management": False, "inventory": False, "purchasing": False,
        "receiving": False, "transfers": False, "transfer_approval": False,
        "locations": False, "categories": False, "audits": False,
        "audit_approval": False, "reports": False, "invoices": True,
        "user_management": False, "system_settings": False,
    },
    "Storekeeper": {
        "sales": False, "sales_returns": False, "customers": False,
        "credit_management": False, "inventory": True, "purchasing": False,
        "receiving": True, "transfers": True, "transfer_approval": False,
        "locations": True, "categories": False, "audits": True,
        "audit_approval": False, "reports": False, "invoices": False,
        "user_management": False, "system_settings": False,
    },
}


async def ensure_default_role_permissions() -> None:
    """Seed default role permissions if the table is empty."""
    from app.models.role_permission import RolePermission

    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count(RolePermission.id))
        )
        existing = result.scalar_one()

        if existing > 0:
            logger.debug(
                "default_role_permissions_skipped",
                extra={"reason": "permissions_exist", "count": existing},
            )
            return

        now = datetime.now(timezone.utc)
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            rp = RolePermission(
                id=uuid.uuid4(),
                role=role,
                permissions=perms,
                updated_at=now,
            )
            session.add(rp)

        try:
            await session.commit()
        except IntegrityError:
            # Concurrency guard: multiple uvicorn workers run this startup hook.
            # role_permissions.role is unique, so if another worker seeded first
            # this commit collides. That is a benign outcome — the rows exist —
            # so roll back quietly instead of crashing the worker.
            await session.rollback()
            logger.info("default_role_permissions_already_seeded_by_another_worker")
            return
        logger.warning(
            "default_role_permissions_seeded",
            extra={"roles": list(DEFAULT_ROLE_PERMISSIONS.keys())},
        )
        print(f"\n  ✓ Seeded role permissions for {len(DEFAULT_ROLE_PERMISSIONS)} roles\n")
