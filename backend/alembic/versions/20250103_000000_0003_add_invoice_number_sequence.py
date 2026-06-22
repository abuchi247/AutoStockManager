"""Add invoice_number_seq PostgreSQL sequence

Creates a PostgreSQL sequence for generating sequential invoice numbers.
This sequence is used by the invoice number generator utility to produce
thread-safe, unique, monotonically increasing invoice numbers.

Format: INV-{year}-{sequential_number:06d}

Satisfies Requirement 5.5: WHEN a sale is confirmed, THE Invoice_Manager
SHALL generate a unique sequential invoice number for the transaction.

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-03 00:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op


# Revision identifiers used by Alembic to maintain migration ordering.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the invoice_number_seq sequence.

    The sequence starts at 1 and increments by 1. PostgreSQL sequences
    are atomic and thread-safe — concurrent calls to nextval() are
    guaranteed to return unique values without requiring advisory locks.
    """
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS invoice_number_seq "
        "START WITH 1 INCREMENT BY 1 NO MAXVALUE CACHE 1"
    )


def downgrade() -> None:
    """Drop the invoice_number_seq sequence."""
    op.execute("DROP SEQUENCE IF EXISTS invoice_number_seq")
