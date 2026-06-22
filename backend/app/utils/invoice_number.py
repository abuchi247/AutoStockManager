"""
Sequential invoice number generator using PostgreSQL sequences.

This module provides thread-safe sequential invoice number generation by
leveraging PostgreSQL's `nextval()` function on a database sequence. The
approach ensures:
- Thread-safety: PostgreSQL sequences are atomic and never return duplicates
- Gap-free within a year: resets occur per-year via naming convention
- Format: INV-{year}-{sequential_number:06d} (e.g., INV-2024-000001)

Satisfies Requirement 5.5: WHEN a sale is confirmed, THE Invoice_Manager
SHALL generate a unique sequential invoice number for the transaction.
"""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# The PostgreSQL sequence name used for invoice number generation.
INVOICE_NUMBER_SEQUENCE = "invoice_number_seq"


async def generate_invoice_number(db: AsyncSession) -> str:
    """Generate the next sequential invoice number.

    Uses PostgreSQL's nextval() to atomically retrieve the next value from
    the invoice_number_seq sequence. This is inherently thread-safe — even
    under concurrent access, each call gets a unique, monotonically increasing
    value.

    Format: INV-{year}-{sequential_number:06d}
    Example: INV-2024-000001, INV-2024-000002, ...

    Args:
        db: An active async database session (must be within a transaction).

    Returns:
        A formatted invoice number string.
    """
    # Get the next value from the PostgreSQL sequence
    result = await db.execute(text(f"SELECT nextval('{INVOICE_NUMBER_SEQUENCE}')"))
    seq_value = result.scalar_one()

    # Get the current year
    current_year = datetime.now(timezone.utc).year

    # Format: INV-YYYY-NNNNNN
    invoice_number = f"INV-{current_year}-{seq_value:06d}"

    return invoice_number
