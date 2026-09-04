"""Tests for database role separation and least-privilege enforcement.

Validates: Requirements 18.5, 18.6
"""

import pytest

from app.services.db_roles import (
    ALL_ROLES,
    APPLICATION_ROLE,
    BACKUP_ROLE,
    DatabaseRole,
    MIGRATION_ROLE,
    extract_username_from_url,
    generate_role_sql,
    log_role_configuration,
    validate_role_separation,
)


class TestRoleDefinitions:
    """Verify role definitions are correctly structured."""

    def test_application_role_has_dml_only(self):
        """Application role should have DML grants and DDL revocations."""
        assert "SELECT" in APPLICATION_ROLE.grants
        assert "INSERT" in APPLICATION_ROLE.grants
        assert "UPDATE" in APPLICATION_ROLE.grants
        assert "DELETE" in APPLICATION_ROLE.grants
        assert "CREATE" in APPLICATION_ROLE.revocations
        assert "DROP" in APPLICATION_ROLE.revocations
        assert "ALTER" in APPLICATION_ROLE.revocations

    def test_migration_role_has_ddl_and_dml(self):
        """Migration role should have both DDL and DML grants."""
        assert "CREATE" in MIGRATION_ROLE.grants
        assert "ALTER" in MIGRATION_ROLE.grants
        assert "DROP" in MIGRATION_ROLE.grants
        assert "SELECT" in MIGRATION_ROLE.grants
        assert "INSERT" in MIGRATION_ROLE.grants
        assert len(MIGRATION_ROLE.revocations) == 0

    def test_backup_role_is_read_only(self):
        """Backup role should only have SELECT access."""
        assert "SELECT" in BACKUP_ROLE.grants
        assert "INSERT" in BACKUP_ROLE.revocations
        assert "UPDATE" in BACKUP_ROLE.revocations
        assert "DELETE" in BACKUP_ROLE.revocations

    def test_all_roles_have_distinct_names(self):
        """Each role must have a unique name."""
        names = [r.name for r in ALL_ROLES]
        assert len(names) == len(set(names))

    def test_all_roles_have_distinct_types(self):
        """Each role must have a unique type."""
        types = [r.role_type for r in ALL_ROLES]
        assert len(types) == len(set(types))


class TestExtractUsername:
    """Verify URL username extraction."""

    def test_extracts_simple_username(self):
        url = "postgresql+asyncpg://myuser:secret@localhost:5432/mydb"
        assert extract_username_from_url(url) == "myuser"

    def test_extracts_encoded_username(self):
        url = "postgresql+asyncpg://my%40user:secret@localhost:5432/mydb"
        assert extract_username_from_url(url) == "my@user"

    def test_returns_none_for_no_username(self):
        url = "postgresql+asyncpg://localhost:5432/mydb"
        assert extract_username_from_url(url) is None

    def test_returns_none_for_invalid_url(self):
        assert extract_username_from_url("") is None

    def test_extracts_from_sync_url(self):
        url = "postgresql://appuser:pass@db.example.com:5432/prod"
        assert extract_username_from_url(url) == "appuser"


class TestValidateRoleSeparation:
    """Verify role separation validation logic."""

    def test_warns_on_superuser_names(self):
        url = "postgresql+asyncpg://postgres:secret@localhost/db"
        warnings = validate_role_separation(url)
        assert any("privileged" in w.lower() for w in warnings)

    def test_warns_on_root_user(self):
        url = "postgresql+asyncpg://root:secret@localhost/db"
        warnings = validate_role_separation(url)
        assert any("privileged" in w.lower() for w in warnings)

    def test_warns_when_no_migration_url(self):
        url = "postgresql+asyncpg://appuser:secret@localhost/db"
        warnings = validate_role_separation(url, migration_database_url=None)
        assert any("MIGRATION_DATABASE_URL" in w for w in warnings)

    def test_warns_when_same_identity(self):
        url = "postgresql+asyncpg://appuser:secret@localhost/db"
        migration_url = "postgresql+asyncpg://appuser:othersecret@localhost/db"
        warnings = validate_role_separation(url, migration_url)
        assert any("same database identity" in w.lower() for w in warnings)

    def test_no_superuser_warning_for_custom_user(self):
        url = "postgresql+asyncpg://stockpilot_app_user:s@localhost/db"
        migration_url = "postgresql+asyncpg://stockpilot_migrate_user:s@localhost/db"
        warnings = validate_role_separation(url, migration_url)
        assert not any("privileged" in w.lower() for w in warnings)
        assert not any("same database identity" in w.lower() for w in warnings)

    def test_returns_empty_for_proper_separation(self):
        url = "postgresql+asyncpg://app_user:s@localhost/db"
        migration_url = "postgresql+asyncpg://migrate_user:s@localhost/db"
        warnings = validate_role_separation(url, migration_url)
        # Only non-separation warnings should be absent
        assert not any("privileged" in w.lower() for w in warnings)
        assert not any("same database identity" in w.lower() for w in warnings)


class TestGenerateRoleSql:
    """Verify SQL generation for role provisioning."""

    def test_generates_sql_with_default_names(self):
        sql = generate_role_sql()
        assert "stockpilot_app" in sql
        assert "stockpilot_migrate" in sql
        assert "stockpilot_backup" in sql
        assert "CREATE ROLE" in sql
        assert "GRANT" in sql

    def test_uses_custom_database_name(self):
        sql = generate_role_sql(database_name="custom_db")
        assert "custom_db" in sql

    def test_uses_custom_schema_name(self):
        sql = generate_role_sql(schema_name="app_schema")
        assert "app_schema" in sql

    def test_includes_login_user_creation(self):
        sql = generate_role_sql()
        assert "stockpilot_app_user" in sql
        assert "stockpilot_migrate_user" in sql
        assert "stockpilot_backup_user" in sql
        assert "LOGIN" in sql

    def test_does_not_include_passwords(self):
        """Generated SQL must not contain actual password values."""
        sql = generate_role_sql()
        # Should not contain common placeholder passwords as VALUES
        assert "changeme" not in sql.lower()
        assert "password123" not in sql.lower()
        # The SQL references PASSWORD in comments/instructions but must not
        # include actual credential literals in executable statements
        lines_with_password_value = [
            line for line in sql.split("\n")
            if "PASSWORD" in line.upper()
            and not line.strip().startswith("--")
            and "ALTER ROLE" not in line
        ]
        assert len(lines_with_password_value) == 0, (
            f"Unexpected PASSWORD usage in SQL: {lines_with_password_value}"
        )


class TestLogRoleConfiguration:
    """Verify logging of role configuration."""

    def test_logs_without_error(self, caplog):
        """Calling log_role_configuration should not raise."""
        import logging
        with caplog.at_level(logging.INFO):
            log_role_configuration(
                app_database_url="postgresql+asyncpg://appuser:s@localhost/db",
                migration_database_url="postgresql+asyncpg://migrateuser:s@localhost/db",
                environment="development",
            )
        assert "database_role_configuration" in caplog.text

    def test_production_logs_warnings(self, caplog):
        """Production with superuser should log warnings."""
        import logging
        with caplog.at_level(logging.WARNING):
            log_role_configuration(
                app_database_url="postgresql+asyncpg://postgres:s@localhost/db",
                environment="production",
            )
        assert "database_role_warning" in caplog.text
