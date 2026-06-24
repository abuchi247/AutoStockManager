#!/usr/bin/env python3
"""Seed default categories for the Auto Spare Parts ERP system.

Usage (from inside the backend container):
    python scripts/seed_categories.py

Or with Docker:
    docker exec autostockmanager-backend python scripts/seed_categories.py

This script is idempotent — it checks if categories already exist before creating them.
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

sys.path.insert(0, "/app")
from app.database import async_session_factory


# Default categories with their subcategories
DEFAULT_CATEGORIES = {
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


async def seed_categories() -> None:
    """Create default categories and subcategories if they don't exist."""
    async with async_session_factory() as session:
        # Check if any categories already exist
        result = await session.execute(
            text("SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL")
        )
        existing_count = result.scalar() or 0

        if existing_count > 0:
            print(f"✓ Categories already exist ({existing_count} found). Skipping seed.")
            return

        now = datetime.now(timezone.utc)
        created_count = 0

        for parent_name, subcategories in DEFAULT_CATEGORIES.items():
            # Create parent category
            parent_id = uuid.uuid4()
            await session.execute(
                text("""
                    INSERT INTO categories (id, name, parent_id, description, is_active, created_at, updated_at)
                    VALUES (:id, :name, NULL, :description, TRUE, :created_at, :updated_at)
                """),
                {
                    "id": parent_id,
                    "name": parent_name,
                    "description": f"Auto spare parts - {parent_name}",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            created_count += 1

            # Create subcategories
            for sub_name in subcategories:
                sub_id = uuid.uuid4()
                await session.execute(
                    text("""
                        INSERT INTO categories (id, name, parent_id, description, is_active, created_at, updated_at)
                        VALUES (:id, :name, :parent_id, :description, TRUE, :created_at, :updated_at)
                    """),
                    {
                        "id": sub_id,
                        "name": sub_name,
                        "parent_id": parent_id,
                        "description": f"{parent_name} - {sub_name}",
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                created_count += 1

        await session.commit()
        print(f"✓ Successfully seeded {created_count} categories:")
        for parent_name, subcategories in DEFAULT_CATEGORIES.items():
            print(f"  • {parent_name} ({len(subcategories)} subcategories)")


def main():
    asyncio.run(seed_categories())


if __name__ == "__main__":
    main()
