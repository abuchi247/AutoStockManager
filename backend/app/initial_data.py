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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.category import Category

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
    "create_sales",
    "confirm_sales",
    "cancel_sales",
    "process_returns",
    "manage_customers",
    "record_payments",
    "credit_adjustments",
    "view_reports",
    "view_profit",
    "generate_invoices",
    "manage_inventory",
    "adjust_stock",
    "manage_transfers",
    "approve_transfers",
    "manage_purchases",
    "approve_purchases",
    "receive_goods",
    "manage_suppliers",
    "manage_locations",
    "manage_categories",
    "manage_users",
    "manage_settings",
    "start_audits",
    "approve_audits",
    "view_dashboard",
    "view_notifications",
]

DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "Admin": {p: True for p in ALL_PERMISSIONS},
    "Manager": {
        "create_sales": True, "confirm_sales": True, "cancel_sales": True,
        "process_returns": True, "manage_customers": True, "record_payments": True,
        "credit_adjustments": True, "view_reports": True, "view_profit": True,
        "generate_invoices": True, "manage_inventory": True, "adjust_stock": True,
        "manage_transfers": True, "approve_transfers": True, "manage_purchases": True,
        "approve_purchases": True, "receive_goods": True, "manage_suppliers": True,
        "manage_locations": True, "manage_categories": True, "manage_users": False,
        "manage_settings": False, "start_audits": True, "approve_audits": True,
        "view_dashboard": True, "view_notifications": True,
    },
    "Salesperson": {
        "create_sales": True, "confirm_sales": True, "cancel_sales": True,
        "process_returns": False, "manage_customers": True, "record_payments": True,
        "credit_adjustments": False, "view_reports": False, "view_profit": False,
        "generate_invoices": True, "manage_inventory": False, "adjust_stock": False,
        "manage_transfers": False, "approve_transfers": False, "manage_purchases": False,
        "approve_purchases": False, "receive_goods": False, "manage_suppliers": False,
        "manage_locations": False, "manage_categories": False, "manage_users": False,
        "manage_settings": False, "start_audits": False, "approve_audits": False,
        "view_dashboard": True, "view_notifications": True,
    },
    "Storekeeper": {
        "create_sales": False, "confirm_sales": False, "cancel_sales": False,
        "process_returns": False, "manage_customers": False, "record_payments": False,
        "credit_adjustments": False, "view_reports": False, "view_profit": False,
        "generate_invoices": False, "manage_inventory": True, "adjust_stock": True,
        "manage_transfers": True, "approve_transfers": False, "manage_purchases": False,
        "approve_purchases": False, "receive_goods": True, "manage_suppliers": False,
        "manage_locations": True, "manage_categories": False, "manage_users": False,
        "manage_settings": False, "start_audits": True, "approve_audits": False,
        "view_dashboard": True, "view_notifications": True,
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

        await session.commit()
        logger.warning(
            "default_role_permissions_seeded",
            extra={"roles": list(DEFAULT_ROLE_PERMISSIONS.keys())},
        )
        print(f"\n  ✓ Seeded role permissions for {len(DEFAULT_ROLE_PERMISSIONS)} roles\n")
