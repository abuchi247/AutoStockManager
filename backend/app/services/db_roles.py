"""Database role separation and least-privilege enforcement.

This module defines the expected database role structure for production
deployments and provides validation utilities to ensure the application
connects with appropriately scoped credentials.

Production deployments MUST use separate database identities:

- **app_role**: Used by the running application (Uvicorn workers). Has only
  DML privileges (SELECT, INSERT, UPDATE, DELETE) on application tables.
  Cannot execute DDL, create/drop schemas, or access pg_catalog admin functions.

- **migration_role**: Used exclusively by the Alembic migration step during
  deployment. Has DDL privileges (CREATE, ALTER, DROP) plus DML. This role
  is used by the pre-deploy migration command, NOT by the running application.

- **backup_role**: Used by the backup operator. Has SELECT-only access for
  pg_dump and cannot modify data.

Validates: Requirements 18.5, 18.6
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import unquote, urlsplit

logger = logging.getLogger(__name__)


class DatabaseRole(str, Enum):
    """Expected database role types for production."""

    APPLICATION = "application"
    MIGRATION = "migration"
    BACKUP = "backup"


@dataclass(frozen=True)
class RoleDefinition:
    """Definition of a database role and its expected privileges."""

    name: str
    role_type: DatabaseRole
    description: str
    grants: tuple[str, ...]
    revocations: tuple[str, ...]


# Role definitions for documentation and provisioning scripts
APPLICATION_ROLE = RoleDefinition(
    name="autostockmanager_app",
    role_type=DatabaseRole.APPLICATION,
    description="Application runtime role with DML-only access",
    grants=(
        "SELECT", "INSERT", "UPDATE", "DELETE",
        "USAGE ON ALL SEQUENCES",
    ),
    revocations=(
        "CREATE", "DROP", "ALTER", "TRUNCATE",
        "REFERENCES", "TRIGGER",
    ),
)

MIGRATION_ROLE = RoleDefinition(
    name="autostockmanager_migrate",
    role_type=DatabaseRole.MIGRATION,
    description="Migration role with DDL+DML for schema changes",
    grants=(
        "SELECT", "INSERT", "UPDATE", "DELETE",
        "CREATE", "ALTER", "DROP", "TRUNCATE",
        "USAGE ON ALL SEQUENCES",
        "REFERENCES",
    ),
    revocations=(),
)

BACKUP_ROLE = RoleDefinition(
    name="autostockmanager_backup",
    role_type=DatabaseRole.BACKUP,
    description="Backup role with read-only access for pg_dump",
    grants=(
        "SELECT",
        "USAGE ON SCHEMA public",
    ),
    revocations=(
        "INSERT", "UPDATE", "DELETE",
        "CREATE", "DROP", "ALTER", "TRUNCATE",
    ),
)

ALL_ROLES = (APPLICATION_ROLE, MIGRATION_ROLE, BACKUP_ROLE)


def generate_role_sql(
    database_name: str = "autostockmanager",
    schema_name: str = "public",
) -> str:
    """Generate SQL statements to create and configure production database roles.

    This SQL should be executed by a database administrator (superuser) during
    initial production setup. It creates the three roles with appropriate
    privilege separation.

    Returns:
        SQL string for role creation and privilege grants.
    """
    return f"""\
-- =============================================================================
-- AutoStockManager Production Database Role Setup
-- =============================================================================
-- Execute as a database superuser (e.g., postgres) during initial provisioning.
-- Passwords must be set separately via ALTER ROLE ... PASSWORD or pg_hba.conf.
-- Never store passwords in this script.
-- =============================================================================

-- 1. Create roles (NOLOGIN base roles)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APPLICATION_ROLE.name}') THEN
        CREATE ROLE {APPLICATION_ROLE.name} NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{MIGRATION_ROLE.name}') THEN
        CREATE ROLE {MIGRATION_ROLE.name} NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{BACKUP_ROLE.name}') THEN
        CREATE ROLE {BACKUP_ROLE.name} NOLOGIN;
    END IF;
END
$$;

-- 2. Revoke default public permissions
REVOKE ALL ON DATABASE {database_name} FROM PUBLIC;
REVOKE ALL ON SCHEMA {schema_name} FROM PUBLIC;

-- 3. Grant schema usage to all roles
GRANT CONNECT ON DATABASE {database_name} TO {APPLICATION_ROLE.name};
GRANT CONNECT ON DATABASE {database_name} TO {MIGRATION_ROLE.name};
GRANT CONNECT ON DATABASE {database_name} TO {BACKUP_ROLE.name};
GRANT USAGE ON SCHEMA {schema_name} TO {APPLICATION_ROLE.name};
GRANT USAGE ON SCHEMA {schema_name} TO {MIGRATION_ROLE.name};
GRANT USAGE ON SCHEMA {schema_name} TO {BACKUP_ROLE.name};

-- 4. Application role: DML only
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema_name}
    TO {APPLICATION_ROLE.name};
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema_name}
    TO {APPLICATION_ROLE.name};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_name}
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APPLICATION_ROLE.name};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_name}
    GRANT USAGE, SELECT ON SEQUENCES TO {APPLICATION_ROLE.name};

-- 5. Migration role: DDL + DML (used only during deployment)
GRANT ALL PRIVILEGES ON SCHEMA {schema_name} TO {MIGRATION_ROLE.name};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema_name}
    TO {MIGRATION_ROLE.name};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema_name}
    TO {MIGRATION_ROLE.name};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_name}
    GRANT ALL PRIVILEGES ON TABLES TO {MIGRATION_ROLE.name};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_name}
    GRANT ALL PRIVILEGES ON SEQUENCES TO {MIGRATION_ROLE.name};

-- 6. Backup role: read-only
GRANT SELECT ON ALL TABLES IN SCHEMA {schema_name} TO {BACKUP_ROLE.name};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_name}
    GRANT SELECT ON TABLES TO {BACKUP_ROLE.name};

-- 7. Create login users inheriting from base roles
-- (Passwords set via secret manager, not in this script)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APPLICATION_ROLE.name}_user') THEN
        CREATE ROLE {APPLICATION_ROLE.name}_user LOGIN IN ROLE {APPLICATION_ROLE.name};
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{MIGRATION_ROLE.name}_user') THEN
        CREATE ROLE {MIGRATION_ROLE.name}_user LOGIN IN ROLE {MIGRATION_ROLE.name};
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{BACKUP_ROLE.name}_user') THEN
        CREATE ROLE {BACKUP_ROLE.name}_user LOGIN IN ROLE {BACKUP_ROLE.name};
    END IF;
END
$$;

-- NOTE: Set passwords for login users via:
--   ALTER ROLE autostockmanager_app_user PASSWORD '<from-secret-manager>';
--   ALTER ROLE autostockmanager_migrate_user PASSWORD '<from-secret-manager>';
--   ALTER ROLE autostockmanager_backup_user PASSWORD '<from-secret-manager>';
"""


def extract_username_from_url(database_url: str) -> Optional[str]:
    """Extract the username from a database connection URL.

    Returns None if the URL cannot be parsed or has no username.
    """
    try:
        parts = urlsplit(database_url)
        return unquote(parts.username) if parts.username else None
    except (ValueError, AttributeError):
        return None


def validate_role_separation(
    app_database_url: str,
    migration_database_url: Optional[str] = None,
) -> list[str]:
    """Validate that application and migration use different database identities.

    Returns a list of warnings. An empty list indicates proper separation.
    In development (single user), warnings are informational only.
    """
    warnings: list[str] = []

    app_user = extract_username_from_url(app_database_url)
    if app_user is None:
        warnings.append(
            "Could not extract application database username from DATABASE_URL"
        )
        return warnings

    # Check if application is using a superuser-like name
    superuser_names = {"postgres", "root", "admin", "rds_superuser"}
    if app_user.lower() in superuser_names:
        warnings.append(
            f"Application is using a privileged database user '{app_user}'. "
            "Production should use a least-privilege application role."
        )

    # Check role separation if migration URL is provided
    if migration_database_url:
        migration_user = extract_username_from_url(migration_database_url)
        if migration_user and migration_user == app_user:
            warnings.append(
                "Application and migration use the same database identity. "
                "Production should separate these for least-privilege enforcement."
            )
    else:
        # No separate migration URL — acceptable in dev, warning in production
        warnings.append(
            "No separate MIGRATION_DATABASE_URL configured. "
            "Production deployments should use a dedicated migration identity."
        )

    return warnings


def log_role_configuration(
    app_database_url: str,
    migration_database_url: Optional[str] = None,
    environment: str = "development",
) -> None:
    """Log the current role configuration without exposing credentials.

    Emits informational log messages about which database user is configured
    for the application and migration, and any warnings about privilege separation.
    """
    app_user = extract_username_from_url(app_database_url)
    logger.info(
        "database_role_configuration",
        extra={
            "app_user": app_user or "<unknown>",
            "has_migration_identity": migration_database_url is not None,
            "environment": environment,
        },
    )

    if environment == "production":
        warnings = validate_role_separation(app_database_url, migration_database_url)
        for warning in warnings:
            logger.warning(
                "database_role_warning",
                extra={"warning": warning, "environment": environment},
            )
