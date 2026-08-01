"""Contract tests for the production deployment configuration.

The production stack is a standalone Compose file rather than an override of the
development file: Compose merges list-valued keys such as ``volumes`` and
``ports``, so an override cannot remove the development source mounts or the
published database ports. These tests lock in the properties the operations
runbook promises, because a regression there is only visible in production.

Validates: Requirements 3.1, 9.1, 18.1, 20.5
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


REPO_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_COMPOSE = REPO_ROOT / "docker-compose.production.yml"
DEVELOPMENT_COMPOSE = REPO_ROOT / "docker-compose.yml"
APPLICATION_SERVICES = ("backend", "worker", "frontend")


@pytest.fixture(scope="module")
def production_stack() -> dict:
    return yaml.safe_load(PRODUCTION_COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def production_services(production_stack) -> dict:
    return production_stack["services"]


def _environment(service: dict) -> dict[str, str]:
    """Resolve a service's environment, following YAML merge keys."""
    environment = service.get("environment") or {}
    if isinstance(environment, list):
        resolved: dict[str, str] = {}
        for item in environment:
            name, _, value = str(item).partition("=")
            resolved[name] = value
        return resolved
    return {str(key): str(value) for key, value in environment.items()}


class TestProductionStackIsSelfContained:
    def test_production_compose_defines_the_whole_stack(self, production_services):
        """It must not depend on the development file to be complete."""
        for name in ("backend", "worker", "frontend", "postgres", "redis"):
            assert name in production_services, f"missing production service: {name}"

    def test_no_host_source_mounts(self, production_services):
        """Requirement 20.5: the image is the artifact, not the host checkout."""
        for name in APPLICATION_SERVICES:
            for mount in production_services[name].get("volumes") or []:
                assert not str(mount).startswith(
                    ("./", "/", "..")
                ), f"{name} bind-mounts host source in production: {mount}"

    def test_datastores_are_not_published_to_the_host(self, production_services):
        """PostgreSQL and Redis stay on the internal network."""
        for name in ("postgres", "redis"):
            assert not production_services[name].get(
                "ports"
            ), f"{name} publishes ports in production"

    def test_application_ports_are_not_bound_to_all_interfaces(
        self, production_services
    ):
        """Only the reverse proxy should reach the app containers directly."""
        for name in ("backend", "frontend"):
            for mapping in production_services[name].get("ports") or []:
                assert (
                    str(mapping).count(":") >= 2
                ), f"{name} port mapping has no bind address: {mapping}"


class TestProductionRuntimeHardening:
    @pytest.mark.parametrize("name", APPLICATION_SERVICES)
    def test_containers_are_restricted(self, production_services, name):
        service = production_services[name]
        assert service.get("read_only") is True, f"{name} filesystem is writable"
        assert "no-new-privileges:true" in (service.get("security_opt") or [])
        assert service.get("restart") == "unless-stopped"


class TestProductionApplicationConfiguration:
    @pytest.mark.parametrize("name", ("backend", "worker"))
    def test_environment_is_production(self, production_services, name):
        assert _environment(production_services[name])["ENVIRONMENT"] == "production"

    @pytest.mark.parametrize("name", ("backend", "worker"))
    def test_redis_url_carries_the_required_password(self, production_services, name):
        """The bundled Redis requires auth, so the URL must supply it."""
        redis_url = _environment(production_services[name])["REDIS_URL"]
        assert "${REDIS_PASSWORD}" in redis_url

    def test_redis_requires_a_password(self, production_services):
        command = production_services["redis"].get("command") or []
        assert "--requirepass" in command

    @pytest.mark.parametrize("name", ("backend", "worker"))
    def test_browser_origins_are_deployment_supplied(self, production_services, name):
        """Requirement 3.1: the cookie origin check needs real production origins."""
        environment = _environment(production_services[name])
        for variable in ("CORS_ORIGINS", "FRONTEND_BASE_URL"):
            value = environment[variable]
            assert "${" in value, f"{variable} is hard-coded in production"
            assert "localhost" not in value, f"{variable} defaults to localhost"

    def test_worker_runs_the_arq_worker_not_the_api(self, production_services):
        """Requirement 9.1: the worker overrides the image CMD (no migrations)."""
        command = production_services["worker"].get("command") or []
        assert command[0] == "arq"
        assert "app.services.background_jobs.WorkerSettings" in command

    @pytest.mark.parametrize("name", ("backend", "worker"))
    def test_worker_and_api_share_queue_and_broker(self, production_services, name):
        environment = _environment(production_services[name])
        assert "JOB_QUEUE_NAME" in environment
        assert "REDIS_URL" in environment

    def test_worker_has_smtp_delivery_configuration(self, production_services):
        environment = _environment(production_services["worker"])
        assert "SMTP_HOST" in environment
        assert "SMTP_FROM_EMAIL" in environment

    @pytest.mark.parametrize("name", ("backend", "worker"))
    def test_observability_is_configured(self, production_services, name):
        environment = _environment(production_services[name])
        assert environment["TELEMETRY_ENABLED"].endswith("true}")
        assert "ERROR_TRACKER_DSN" in environment
        assert "LOG_LEVEL" in environment


class TestDevelopmentComposeStaysDevelopmentOnly:
    def test_development_file_is_not_used_for_production(self):
        """Guards against reintroducing the unsafe override usage."""
        text = DEVELOPMENT_COMPOSE.read_text(encoding="utf-8")
        assert "docker-compose.production.yml up" in text
        assert "-f docker-compose.yml -f docker-compose.production.yml" not in text
