import ast
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.exc import IntegrityError

import app.application as application_module
from app.api.router import api_router
from app.application import create_application
from app.database import Base
from app.library.models import LibraryWork, LibraryWorkAlias
from app.library.seed import seed_ethiopian_canon


def test_application_exposes_versioned_health_endpoint(test_settings):
    client = TestClient(create_application(test_settings))
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'healthy', 'service': 'unbound-bible'}


def test_shared_state_wiring_supports_a_legacy_shaped_application(test_settings):
    wire_application_state = getattr(application_module, 'wire_application_state', None)
    assert callable(wire_application_state)

    legacy_application = FastAPI()
    legacy_limiter = object()
    legacy_application.state.limiter = legacy_limiter
    legacy_engine = create_engine(
        test_settings.database_url,
        connect_args={'check_same_thread': False},
    )
    with legacy_engine.connect() as connection:
        assert connection.scalar(text('PRAGMA foreign_keys')) == 0
    Base.metadata.create_all(legacy_engine)

    wire_application_state(legacy_application, test_settings, legacy_engine)
    legacy_application.include_router(api_router, prefix='/api/v1')

    assert legacy_application.state.settings is test_settings
    assert legacy_application.state.database_engine is legacy_engine
    assert legacy_application.state.limiter is legacy_limiter
    with legacy_engine.connect() as connection:
        assert connection.scalar(text('PRAGMA foreign_keys')) == 1
    with legacy_application.state.session_factory() as session:
        assert session.get_bind() is legacy_engine
        seed_ethiopian_canon(session)

    with pytest.raises(IntegrityError):
        with legacy_engine.begin() as connection:
            connection.execute(
                LibraryWorkAlias.__table__.insert(),
                {'alias': 'Orphaned legacy alias', 'work_id': 'missing-work'},
            )

    with legacy_engine.begin() as connection:
        connection.execute(
            LibraryWork.__table__.insert(),
            {'id': 'legacy-cascade-work', 'title': 'Legacy cascade work'},
        )
        connection.execute(
            LibraryWorkAlias.__table__.insert(),
            {'alias': 'Legacy cascade alias', 'work_id': 'legacy-cascade-work'},
        )
        connection.execute(
            delete(LibraryWork).where(LibraryWork.id == 'legacy-cascade-work')
        )
        assert connection.execute(
            select(LibraryWorkAlias).where(
                LibraryWorkAlias.work_id == 'legacy-cascade-work'
            )
        ).all() == []

    response = TestClient(legacy_application).get('/api/v1/books?canon=ETHIO81')
    assert response.status_code == 200
    assert response.json()['navigation_count'] == 95


def test_legacy_main_invokes_shared_application_state_wiring():
    backend_root = Path(__file__).resolve().parents[1]
    module = ast.parse((backend_root / 'main.py').read_text())

    calls = [
        node for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == 'wire_application_state'
    ]

    assert len(calls) == 1
    assert [argument.id for argument in calls[0].args] == ['app', 'settings', 'engine']


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
