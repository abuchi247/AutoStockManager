#!/usr/bin/env python3
"""Database setup script for fresh deployments.

This script is idempotent — safe to run multiple times. It will:
1. Create all database tables (if they don't exist)
2. Create the invoice_number_seq sequence (if it doesn't exist)
3. Create an admin user (if one doesn't exist)
4. Seed default categories (if none exist)

Usage:
    # Inside the container or with railway run:
    python scripts/setup_db.py

    # Or with Docker:
    docker exec autostockmanager-backend python scripts/setup_db.py

    # Or with Railway CLI:
    cd backend && railway run python3 scripts/setup_db.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import text

sys.path.insert(0, "/app")
sys.path.insert(0, ".")

from app.database import Base, async_session_factory, engine  # noqa: E402


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


async def setup():
    """Run full database setup."""
    print("=" * 60)
    print("Auto Spare Parts ERP — Database Setup")
    print("=" * 60)

    # Step 1: Create tables
    print("\n[1/4] Creating database tables...")
    from app.models import *  # noqa: F401, F403

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ All tables created/verified")

    # Step 2: Create invoice sequence
    print("\n[2/4] Creating invoice_number_seq sequence...")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START 1"))
    print("  ✓ Sequence created/verified")

    # Step 3: Create admin user
    print("\n[3/4] Creating admin user...")
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": "admin"}
        )
        if result.scalar():
            print("  ✓ Admin user already exists, skipping")
        else:
            pw_hash = bcrypt.hashpw("Admin123!".encode(), bcrypt.gensalt(12)).decode()
            now = datetime.now(timezone.utc)
            await session.execute(
                text("""
                    INSERT INTO users (id, username, email, password_hash, role, is_active, failed_login_attempts, created_at, updated_at)
                    VALUES (:id, :u, :e, :pw, :r, TRUE, 0, :now, :now)
                """),
                {
                    "id": uuid.uuid4(),
                    "u": "admin",
                    "e": "admin@autostockmanager.com",
                    "pw": pw_hash,
                    "r": "Admin",
                    "now": now,
                },
            )
            await session.commit()
            print("  ✓ Admin user created (admin / Admin123!)")

    # Step 4: Seed categories
    print("\n[4/4] Seeding default categories...")
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM categories"))
        count = result.scalar() or 0
        if count > 0:
            print(f"  ✓ Categories already exist ({count} found), skipping")
        else:
            now = datetime.now(timezone.utc)
            created = 0
            for parent_name, subs in DEFAULT_CATEGORIES.items():
                parent_id = uuid.uuid4()
                await session.execute(
                    text("""
                        INSERT INTO categories (id, name, parent_id, description, is_active, created_at, updated_at)
                        VALUES (:id, :name, NULL, :desc, TRUE, :now, :now)
                    """),
                    {"id": parent_id, "name": parent_name, "desc": f"Auto spare parts - {parent_name}", "now": now},
                )
                created += 1
                for sub_name in subs:
                    await session.execute(
                        text("""
                            INSERT INTO categories (id, name, parent_id, description, is_active, created_at, updated_at)
                            VALUES (:id, :name, :pid, :desc, TRUE, :now, :now)
                        """),
                        {"id": uuid.uuid4(), "name": sub_name, "pid": parent_id, "desc": f"{parent_name} - {sub_name}", "now": now},
                    )
                    created += 1
            await session.commit()
            print(f"  ✓ Seeded {created} categories")

    await engine.dispose()

    print("\n" + "=" * 60)
    print("Setup complete! The application is ready to use.")
    print("  Login: admin / Admin123!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(setup())
