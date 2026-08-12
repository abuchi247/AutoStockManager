"""Unit tests for production configuration validation."""

import pytest

from app.config import Settings


class TestProductionConfigurationValidation:
    """Production credentials are rejected without exposing their values."""

    def test_development_settings_allow_placeholders(self):
        """Development remains usable with the documented local defaults."""
        settings = Settings(
            environment="development",
            jwt_secret_key="change-me-in-production",
            postgres_password="changeme",
        )

        assert settings.environment == "development"

    def test_production_rejects_short_jwt_secret(self):
        """Production JWT secrets must contain at least 32 characters."""
        secret = "too-short-secret"

        with pytest.raises(ValueError) as error:
            Settings(
                environment="production",
                jwt_secret_key=secret,
                postgres_password="a-real-database-password",
            )

        message = str(error.value)
        assert "jwt_secret_key" in message
        assert secret not in message

    def test_production_rejects_placeholder_jwt_secret(self):
        """Known JWT placeholders are rejected even when long enough."""
        secret = "your-secret-key-change-in-production"

        with pytest.raises(ValueError) as error:
            Settings(
                environment="production",
                jwt_secret_key=secret,
                postgres_password="a-real-database-password",
            )

        message = str(error.value)
        assert "jwt_secret_key" in message
        assert secret not in message

    def test_production_rejects_placeholder_database_password(self):
        """Known database placeholders are rejected from direct settings."""
        password = "changeme"

        with pytest.raises(ValueError) as error:
            Settings(
                environment="production",
                jwt_secret_key="a" * 32,
                postgres_password=password,
            )

        message = str(error.value)
        assert "POSTGRES_PASSWORD" in message
        assert password not in message

    def test_production_rejects_placeholder_database_url_password(self):
        """Docker-style credentials embedded in DATABASE_URL are validated."""
        database_url = "postgresql+asyncpg://postgres:changeme@db:5432/erp"

        with pytest.raises(ValueError) as error:
            Settings(
                environment="production",
                jwt_secret_key="a" * 32,
                database_url=database_url,
            )

        message = str(error.value)
        assert "DATABASE_URL" in message
        assert database_url not in message
        assert "changeme" not in message

    def test_production_accepts_secure_credentials(self):
        """A sufficiently long non-placeholder configuration is accepted."""
        settings = Settings(
            environment="production",
            jwt_secret_key="a" * 32,
            postgres_password="a-real-database-password",
            database_url="postgresql+asyncpg://postgres:unused@db:5432/erp",
            smtp_host="smtp.example.com",
            smtp_from_email="no-reply@example.com",
            cors_origins=["https://app.example.com"],
        )

        assert settings.environment == "production"
