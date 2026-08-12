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
