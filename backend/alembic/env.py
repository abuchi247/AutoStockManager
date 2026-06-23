"""
Alembic environment configuration for async SQLAlchemy migrations.

This module configures Alembic to work with SQLAlchemy 2.0's async engine
(asyncpg driver for PostgreSQL). It supports both offline (SQL script generation)
and online (direct database connection) migration modes.

Key design decisions:
- Uses async_engine_from_config to create an async-compatible engine for migrations
- Imports all models so Base.metadata contains the full schema for autogenerate
- Reads the database URL from pydantic-settings (app.config) rather than alembic.ini
  to maintain a single source of truth for configuration
- Uses NullPool for migration connections to avoid pool-related issues during
  schema changes

Usage:
    # Generate a new migration (from backend/ directory):
    alembic revision --autogenerate -m "description of changes"

    # Apply all pending migrations:
    alembic upgrade head

    # Rollback the last migration:
    alembic downgrade -1

    # Show current revision:
    alembic current

    # Show migration history:
    alembic history
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.database import Base

# ---------------------------------------------------------------------------
# Model Imports for Autogenerate Support
# ---------------------------------------------------------------------------
# All SQLAlchemy models MUST be imported here so that Base.metadata contains
# their table definitions. Without these imports, `alembic revision --autogenerate`
# will not detect model changes.
#
# As new models are added to the project, uncomment their imports below:
from app.models.base import BaseModel  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.spare_part import SparePart  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.category import Category  # noqa: F401
# from app.models.inventory_movement_ledger import InventoryMovementLedger  # noqa: F401
# from app.models.stock_status_cache import StockStatusCache  # noqa: F401
# from app.models.cost_layer import CostLayer  # noqa: F401
# from app.models.sale import Sale, SaleItem  # noqa: F401
# from app.models.customer import Customer  # noqa: F401
# from app.models.customer_credit_ledger import CustomerCreditLedger  # noqa: F401
# from app.models.supplier import Supplier  # noqa: F401
# from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem  # noqa: F401
# from app.models.goods_receipt_note import GoodsReceiptNote, GRNItem  # noqa: F401
# from app.models.transfer import Transfer  # noqa: F401
# from app.models.audit_session import AuditSession, AuditSnapshotItem, AuditCount  # noqa: F401
# from app.models.notification import Notification  # noqa: F401
# from app.models.audit_trail import AuditTrail  # noqa: F401
# from app.models.invoice import Invoice  # noqa: F401
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Alembic Configuration Setup
# ---------------------------------------------------------------------------

# Access the Alembic Config object, which provides values from alembic.ini
config = context.config

# Set up Python logging using the configuration from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Load application settings and inject the database URL into Alembic's config.
# This ensures alembic uses the same connection string as the application,
# avoiding configuration drift between app and migrations.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.async_database_url)

# The target metadata object is used by autogenerate to compare the current
# database schema against the models defined in code and generate migration diffs.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration Execution Functions
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without connecting).

    In offline mode, Alembic generates SQL statements that can be applied
    manually to the database. This is useful for:
    - Generating migration SQL for DBA review before applying
    - Environments where direct database access is not available
    - Creating migration scripts for deployment pipelines

    The generated SQL is emitted to stdout or a configured output file.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migration operations using the provided synchronous connection.

    This function is called within run_sync() to bridge the async/sync gap.
    It configures the Alembic context with the active connection and runs
    all pending migrations within a transaction.

    Args:
        connection: A synchronous SQLAlchemy Connection object provided
                    by the async engine's run_sync() method.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async PostgreSQL engine.

    Creates an async engine using asyncpg, establishes a connection, and
    delegates to do_run_migrations() via run_sync() to execute the actual
    migration steps.

    Uses NullPool to avoid connection pooling during migrations, since
    migration operations are short-lived and shouldn't hold pool connections.
    """
    # Create an async engine from the [alembic] section of alembic.ini.
    # NullPool is used because migrations are transient operations that
    # don't benefit from connection pooling.
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Connect and run migrations synchronously within the async context.
    # run_sync() bridges async engine connections to Alembic's sync API.
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    # Cleanly dispose of the engine after migrations complete.
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode.

    Alembic's CLI calls this function synchronously, so we use asyncio.run()
    to bridge into the async migration runner. This allows the async engine
    (asyncpg) to be used for database operations during migrations.
    """
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
# Determine which mode to run based on Alembic's context.
# Offline mode is triggered by: alembic upgrade head --sql
# Online mode is the default for: alembic upgrade head

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
