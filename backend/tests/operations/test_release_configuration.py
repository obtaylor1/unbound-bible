import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.application import create_application
from app.config import Settings


ROOT = Path(__file__).parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str) -> dict:
    return yaml.safe_load(_read(path))


def test_staging_settings_use_the_production_security_boundary():
    secure = {
        "environment": "staging",
        "database_url": "postgresql://app:password@db:5432/unbound_bible",
        "jwt_secret_key": "a-staging-secret-with-at-least-32-characters",
        "public_base_url": "https://staging.example.test",
        "cors_origins": ["https://staging.example.test"],
        "ai_chat_provider": "demo",
        "ai_embedding_provider": "demo",
        "ai_transcription_provider": "demo",
        "allow_production_demo": True,
    }

    settings = Settings(**secure)
    application = create_application(settings)

    assert settings.environment == "staging"
    assert application.docs_url is None
    assert application.openapi_url is None

    with pytest.raises(ValidationError, match="Production database must use PostgreSQL"):
        Settings(**{**secure, "database_url": "sqlite:///unsafe.db"})
    with pytest.raises(ValidationError, match="JWT secret"):
        Settings(**{**secure, "jwt_secret_key": "too-short"})
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(**{**secure, "public_base_url": "http://staging.example.test"})
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(**{**secure, "cors_origins": ["*"]})


def test_api_image_migrates_before_starting_the_modular_app_as_non_root():
    dockerfile = _read("backend/Dockerfile")

    assert "alembic -c alembic.ini upgrade head" in dockerfile
    assert "uvicorn app.application:app" in dockerfile
    assert dockerfile.index("alembic -c alembic.ini upgrade head") < dockerfile.index(
        "uvicorn app.application:app"
    )
    assert "USER app" in dockerfile
    assert "--frozen" in dockerfile


def test_frontend_image_builds_vite_and_serves_with_non_root_nginx():
    dockerfile = _read("frontend/Dockerfile")
    nginx = _read("frontend/nginx.conf")

    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "nginx-unprivileged" in dockerfile
    assert "COPY --from=build" in dockerfile
    assert "location = /healthz" in nginx
    assert "proxy_pass http://api:8000" in nginx
    assert "try_files $uri $uri/ /index.html" in nginx


def test_staging_compose_uses_postgres_healthchecks_env_file_and_no_embedded_secrets():
    compose = _yaml("compose.staging.yml")
    services = compose["services"]

    assert services["db"]["image"].startswith("postgres:")
    assert services["db"]["healthcheck"]
    assert services["api"]["healthcheck"]
    assert services["web"]["healthcheck"]
    assert services["api"]["environment"]["ENVIRONMENT"] == "staging"
    assert services["api"]["env_file"]
    assert services["db"]["env_file"]
    assert services["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert "postgres_data" in compose["volumes"]

    serialized = json.dumps(compose)
    for secret_name in ["JWT_SECRET_KEY", "AI_API_KEY", "POSTGRES_PASSWORD"]:
        assert secret_name not in services["api"]["environment"]
        assert secret_name not in services["db"].get("environment", {})
    assert "development-only-secret" not in serialized
    assert "password=" not in serialized.lower()


def test_quality_workflow_runs_every_release_gate_on_prs_and_main():
    workflow_text = _read(".github/workflows/quality.yml")
    workflow = yaml.safe_load(workflow_text)
    serialized = json.dumps(workflow)

    assert "pull_request:" in workflow_text
    assert "push:" in workflow_text
    assert "main" in workflow_text
    for command in ["pytest", "npm test", "npm run lint", "npm run build", "playwright test"]:
        assert command in serialized


def test_staging_workflow_publishes_sha_images_and_uses_protected_environment_without_eval():
    workflow_text = _read(".github/workflows/staging.yml")
    workflow = yaml.safe_load(workflow_text)
    serialized = json.dumps(workflow)

    assert "${{ github.sha }}" in workflow_text
    assert "environment: staging" in workflow_text
    assert "secrets.STAGING_DEPLOY_HOOK_URL" in workflow_text
    assert "docker/build-push-action" in serialized
    assert "push: true" in workflow_text
    assert "eval " not in workflow_text
    assert "sh -c" not in workflow_text
    assert "bash -c" not in workflow_text


def test_runbook_documents_configuration_health_deploy_and_rollback():
    runbook = _read("docs/operations/production-runbook.md")

    for phrase in [
        "`.env.staging`",
        "`/api/v1/health`",
        "`/api/v1/health/providers`",
        "`/healthz`",
        "commit SHA",
        "STAGING_DEPLOY_HOOK_URL",
        "Rollback",
    ]:
        assert phrase in runbook
