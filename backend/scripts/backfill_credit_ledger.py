#!/usr/bin/env python3
"""Backfill credit ledger entries for confirmed credit sales that are missing them.

This script finds all confirmed credit sales that don't have a corresponding
credit ledger entry and creates them. Safe to run multiple times (idempotent).

Usage:
    # Local Docker:
    docker exec autostockmanager-backend python scripts/backfill_credit_ledger.py

    # Railway:
    cd backend && railway run python3 scripts/backfill_credit_ledger.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text

sys.path.insert(0, "/app")
sys.path.insert(0, ".")

from app.database import async_session_factory, engine


async def backfill():
    """Find confirmed credit sales without ledger entries and create them."""
    print("=" * 60)
    print("Backfill Credit Ledger Entries")
    print("=" * 60)

    async with async_session_factory() as session:
        # Find all confirmed credit sales
        result = await session.execute(
            text("""
                SELECT s.id, s.customer_id, s.total_amount, s.invoice_number, s.created_at
                FROM sales s
                WHERE s.status = 'CONFIRMED'
                  AND s.payment_type = 'CREDIT'
                  AND s.customer_id IS NOT NULL
                  AND s.deleted_at IS NULL
            """)
        )
        credit_sales = result.fetchall()
        print(f"\nFound {len(credit_sales)} confirmed credit sales")

        # Find which ones already have ledger entries
        result = await session.execute(
            text("""
                SELECT DISTINCT reference_id
                FROM customer_credit_ledger
                WHERE reference_type = 'sale'
                  AND transaction_type = 'SALE'
            """)
        )
        existing_refs = {row.reference_id for row in result.fetchall()}
        print(f"Already have ledger entries: {len(existing_refs)}")

        # Create missing entries
        created = 0
        for sale in credit_sales:
            if sale.id in existing_refs:
                continue

            entry_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            await session.execute(
                text("""
                    INSERT INTO customer_credit_ledger 
                    (id, customer_id, transaction_type, amount, reference_type, reference_id, notes, created_by, created_at)
                    VALUES (:id, :customer_id, 'SALE', :amount, 'sale', :reference_id, :notes, :created_by, :created_at)
                """),
                {
                    "id": entry_id,
                    "customer_id": sale.customer_id,
                    "amount": sale.total_amount,
                    "reference_id": sale.id,
                    "notes": f"Credit sale {sale.invoice_number or 'N/A'} (backfilled)",
                    "created_by": sale.customer_id,  # Use customer_id as placeholder for created_by
                    "created_at": sale.created_at or now,
                },
            )
            created += 1
            print(f"  ✓ {sale.invoice_number}: {sale.total_amount} → customer {str(sale.customer_id)[:8]}")

        await session.commit()

    await engine.dispose()

    print(f"\n{'=' * 60}")
    print(f"Done! Created {created} new ledger entries.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(backfill())
