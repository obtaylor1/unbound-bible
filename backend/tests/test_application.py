from fastapi.testclient import TestClient

from app.application import create_application


def test_application_exposes_versioned_health_endpoint(test_settings):
    client = TestClient(create_application(test_settings))
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'healthy', 'service': 'unbound-bible'}


def test_production_rejects_insecure_configuration():
    from pydantic import ValidationError
    from app.config import Settings

    try:
        Settings(
            environment='production',
            database_url='sqlite:///production.db',
            jwt_secret_key='short',
            cors_origins=['*'],
        )
    except ValidationError as error:
        message = str(error)
        assert 'JWT secret' in message or 'Wildcard CORS' in message
    else:
        raise AssertionError('Insecure production settings were accepted')
