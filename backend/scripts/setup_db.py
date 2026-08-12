#!/usr/bin/env python3
"""Database setup script for fresh deployments.

This script is idempotent — safe to run multiple times. It will:
1. Apply all reviewed Alembic migrations
2. Create an admin user (if one doesn't exist)
3. Seed default categories (if none exist)

On a normal container startup both steps 2 and 3 happen automatically via the
application lifespan hook (initial_admin.py and initial_data.py). Use this
script when you need to run setup outside of a container restart — e.g. when
deploying to Railway or running CI against a fresh database.

Usage:
    # Inside the container:
    docker exec autostockmanager-backend python scripts/setup_db.py

    # Railway CLI (from backend/ directory):
    railway run python3 scripts/setup_db.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import text

sys.path.insert(0, "/app")
sys.path.insert(0, ".")

from app.database import async_session_factory, engine  # noqa: E402
from app.migration_runner import run_migrations  # noqa: E402
from app.initial_data import ensure_default_categories, DEFAULT_CATEGORIES  # noqa: E402


async def setup() -> None:
    """Run full database setup."""
    print("=" * 60)
    print("Auto Spare Parts ERP — Database Setup")
    print("=" * 60)

    # Step 1: Apply reviewed schema migrations
    print("\n[1/3] Applying Alembic migrations...")
    await run_migrations()
    print("  ✓ Database is at Alembic head")

    # Step 2: Create admin user
    print("\n[2/3] Creating admin user...")
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
                    INSERT INTO users
                        (id, username, email, password_hash, role,
                         is_active, failed_login_attempts, created_at, updated_at)
                    VALUES
                        (:id, :u, :e, :pw, :r, TRUE, 0, :now, :now)
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

    # Step 3: Seed categories — delegates to the same function the lifespan
    # calls so the category data is always consistent with initial_data.py.
    print("\n[3/3] Seeding categories...")
    await ensure_default_categories()
    total_parents = len(DEFAULT_CATEGORIES)
    total_subs = sum(len(v) for v in DEFAULT_CATEGORIES.values())
    print(f"  ✓ Categories ready ({total_parents} parent, {total_subs} subcategories)")

    await engine.dispose()

    print("\n" + "=" * 60)
    print("Setup complete! The application is ready to use.")
    print("  Login: admin / Admin123!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(setup())
