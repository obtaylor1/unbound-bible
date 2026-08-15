import ast
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.exc import IntegrityError

import app.application as application_module
import app.application_state as application_state_module
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


def test_shared_http_client_is_reused_by_research_queries_and_closed_once(
    test_settings, monkeypatch,
):
    test_settings.ai_chat_provider = 'openai_compatible'
    constructed = []
    provider_clients = []

    class SharedClient:
        def __init__(self):
            self.close_calls = 0

        async def aclose(self):
            self.close_calls += 1

    def create_client():
        client = SharedClient()
        constructed.append(client)
        return client

    class UnusedProvider:
        name = 'unused'

    def create_provider(_name, _settings, http_client=None):
        provider_clients.append(http_client)
        return UnusedProvider()

    monkeypatch.setattr(
        application_state_module, '_create_http_client', create_client,
        raising=False,
    )
    monkeypatch.setattr('app.research.router.create_chat_provider', create_provider)
    app = create_application(test_settings)

    with TestClient(app) as client:
        assert client.post(
            '/api/v1/research/query', json={'question': 'First question'}
        ).status_code == 200
        assert client.post(
            '/api/v1/research/query', json={'question': 'Second question'}
        ).status_code == 200
        assert len(constructed) == 1
        assert provider_clients == [constructed[0], constructed[0]]

    assert constructed[0].close_calls == 1


def test_demo_only_application_does_not_construct_http_client(
    test_settings, monkeypatch,
):
    constructed = []
    monkeypatch.setattr(
        application_state_module,
        '_create_http_client',
        lambda: constructed.append(object()),
        raising=False,
    )

    with TestClient(create_application(test_settings)) as client:
        assert client.get('/api/v1/health').status_code == 200

    assert constructed == []


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


def test_legacy_main_has_no_direct_scripture_acquisition_or_cache_writer():
    backend_root = Path(__file__).resolve().parents[1]
    source = (backend_root / 'main.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    retired_helpers = {
        'download_chapter_data',
        'get_or_create_translation',
        'ensure_translations_cached',
        'ensure_chapter_cached',
        'bg_ensure_translations_cached',
        'bg_ensure_chapter_cached',
    }

    assert retired_helpers.isdisjoint({
        node.name for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    })
    for forbidden in (
        '_create_unverified_context',
        'verify=False',
        'CERT_NONE',
        'check_hostname',
        'urllib.request',
        'urlopen(',
        'bulk_save_objects',
        'INSERT INTO biblical_texts',
        'bible-api.com',
        'api.nlt.to',
    ):
        assert forbidden not in source
    for function in (
        node for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
        constructs_scripture = any(
            isinstance(call.func, ast.Name) and call.func.id == 'BiblicalText'
            for call in calls
        )
        writes_session = any(
            isinstance(call.func, ast.Attribute)
            and call.func.attr in {'add', 'bulk_save_objects', 'commit', 'execute'}
            for call in calls
        )
        assert not (constructs_scripture and writes_session), function.name


def test_legacy_scripture_read_routes_never_enqueue_acquisition_tasks():
    backend_root = Path(__file__).resolve().parents[1]
    module = ast.parse((backend_root / 'main.py').read_text(encoding='utf-8'))
    route_paths = {
        'get_book_content': '/api/biblical-texts/book-content',
        'get_chapter_content': '/api/biblical-texts/chapter-content',
        'get_verse_comparison': '/api/v1/texts/{book}/{chapter}/{verse}',
    }
    routes = {
        node.name: node for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in route_paths
    }

    assert set(routes) == set(route_paths)
    assert not any(
        alias.name == 'BackgroundTasks'
        for node in module.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    )
    for name, route in routes.items():
        assert any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == 'app'
            and decorator.func.attr == 'get'
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and decorator.args[0].value == route_paths[name]
            for decorator in route.decorator_list
        )
        assert 'background_tasks' not in {
            argument.arg for argument in (*route.args.posonlyargs, *route.args.args)
        }
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'add_task'
            for node in ast.walk(route)
        )


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
