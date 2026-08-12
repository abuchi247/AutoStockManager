#!/usr/bin/env python3
"""Manual CLI fallback for seeding default categories.

On a normal startup the application seeds categories automatically via the
lifespan hook (app/initial_data.py). Use this script only when you need to
trigger seeding outside of a container restart — e.g. after wiping the
categories table manually or when debugging.

This script is idempotent — safe to run multiple times.

Usage (from inside the backend container):
    python scripts/seed_categories.py

Or with Docker:
    docker exec autostockmanager-backend python scripts/seed_categories.py

Or with Railway CLI (from the backend/ directory):
    railway run python3 scripts/seed_categories.py
"""

import asyncio
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, ".")

from app.initial_data import ensure_default_categories, DEFAULT_CATEGORIES  # noqa: E402


async def main() -> None:
    print("Seeding default categories...")
    await ensure_default_categories()
    total_parents = len(DEFAULT_CATEGORIES)
    total_subs = sum(len(v) for v in DEFAULT_CATEGORIES.values())
    print(f"Done. ({total_parents} parent categories, {total_subs} subcategories)")


if __name__ == "__main__":
    asyncio.run(main())
