"""
Alembic migration versions package.

This directory contains all database migration scripts, ordered chronologically.
Each script has an upgrade() and downgrade() function that applies or reverts
schema changes.

Naming convention: YYYYMMDD_HHMMSS_<revision_id>_<description>.py

To create a new migration:
    alembic revision --autogenerate -m "description of changes"

To apply all pending migrations:
    alembic upgrade head

To rollback the last migration:
    alembic downgrade -1
"""
