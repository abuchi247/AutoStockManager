"""Initial migration - baseline schema setup

This is the foundational migration for the Auto Spare Parts ERP system.
It establishes the PostgreSQL extensions required by the application before
any domain tables are created.

Extensions enabled:
- uuid-ossp: Provides UUID generation functions (uuid_generate_v4()) used
  as default primary key values across all tables in the system.

Revision ID: 0001
Revises: None (this is the first migration)
Create Date: 2025-01-01 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic to maintain migration ordering.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply forward schema changes.

    Enables the uuid-ossp PostgreSQL extension which provides UUID generation
    functions. This is required because all models in the ERP system use UUID
    primary keys (via uuid_generate_v4()) for globally unique, non-sequential
    identifiers that are safe for distributed systems and prevent enumeration
    attacks on API endpoints.

    The 'IF NOT EXISTS' clause makes this idempotent — safe to run multiple
    times without error.
    """
    # Enable UUID generation support in PostgreSQL.
    # All ERP tables use UUID primary keys for security and scalability.
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


def downgrade() -> None:
    """Revert schema changes.

    Removes the uuid-ossp extension. Only safe if no tables depend on it.
    In practice, this should only be run when tearing down a fresh database.
    """
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
