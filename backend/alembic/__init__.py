"""
Alembic migrations package for the Auto Spare Parts ERP system.

This package contains:
- env.py: Migration environment configuration (async SQLAlchemy setup)
- script.py.mako: Template for generating new migration files
- versions/: Directory containing all migration revision scripts

Migration scripts are applied in order to build or modify the PostgreSQL
database schema. Each migration is reversible (upgrade/downgrade).
"""
