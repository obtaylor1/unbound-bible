import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
from pydantic import ValidationError
import yaml

from app.config import Settings


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


def assert_legacy_database_fails_closed(text: str) -> None:
    """Assert that a retired database module cannot silently use a repo SQLite file."""
    tree = ast.parse(text)
    database_assignments = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == 'DATABASE_URL' for target in targets):
                database_assignments.append(node)

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip().lower()
            assert not value.startswith('sqlite:')
            assert not value.endswith(('.db', '.sqlite', '.sqlite3'))

    assert len(database_assignments) == 1
    database_lookup = database_assignments[0]
    assert isinstance(database_lookup, ast.Assign)
    assert isinstance(database_lookup.value, ast.Call)
    assert isinstance(database_lookup.value.func, ast.Attribute)
    assert database_lookup.value.func.attr == 'get'
    assert isinstance(database_lookup.value.func.value, ast.Attribute)
    assert isinstance(database_lookup.value.func.value.value, ast.Name)
    assert database_lookup.value.func.value.value.id == 'os'
    assert database_lookup.value.func.value.attr == 'environ'
    assert database_lookup.value.args
    assert isinstance(database_lookup.value.args[0], ast.Constant)
    assert database_lookup.value.args[0].value == 'DATABASE_URL'
    assert len(database_lookup.value.args) == 1

    missing_environment_guards = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Name)
        and node.test.operand.id == 'DATABASE_URL'
    ]
    assert len(missing_environment_guards) == 1
    guard = missing_environment_guards[0]
    assert any(isinstance(node, ast.Raise) for node in guard.body)
    messages = [
        node.value.lower()
        for statement in guard.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert any(
        'database_url environment variable' in message and 'not set' in message
        for message in messages
    )


def assert_legacy_auth_fails_closed(text: str) -> None:
    """Assert that a retired auth module has one environment-only signing secret."""
    tree = ast.parse(text)
    secret_assignments = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == 'SECRET_KEY' for target in targets):
                secret_assignments.append(node)

    assert len(secret_assignments) == 1
    secret_lookup = secret_assignments[0]
    assert isinstance(secret_lookup, ast.Assign)
    assert isinstance(secret_lookup.value, ast.Call)
    assert isinstance(secret_lookup.value.func, ast.Attribute)
    assert secret_lookup.value.func.attr == 'get'
    assert isinstance(secret_lookup.value.func.value, ast.Attribute)
    assert isinstance(secret_lookup.value.func.value.value, ast.Name)
    assert secret_lookup.value.func.value.value.id == 'os'
    assert secret_lookup.value.func.value.attr == 'environ'
    assert len(secret_lookup.value.args) == 1
    assert isinstance(secret_lookup.value.args[0], ast.Constant)
    assert secret_lookup.value.args[0].value == 'JWT_SECRET_KEY'

    missing_secret_guards = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Name)
        and node.test.operand.id == 'SECRET_KEY'
    ]
    assert len(missing_secret_guards) == 1
    guard = missing_secret_guards[0]
    messages = [
        node.value
        for statement in guard.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert any('JWT_SECRET_KEY environment variable is required' in message for message in messages)


def test_legacy_database_guard_rejects_repo_sqlite_fallback(tmp_path):
    unsafe_module = tmp_path / 'database.py'
    unsafe_module.write_text(
        'DATABASE_URL = "sqlite:///unbound_bible.db"\n',
        encoding='utf-8',
    )

    with pytest.raises(AssertionError):
        assert_legacy_database_fails_closed(unsafe_module.read_text(encoding='utf-8'))


@pytest.mark.parametrize(
    'unsafe_source',
    [
        '''
        import os
        DATABASE_URL = os.environ.get("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not set")
        FALLBACK_URL = "sqlite+pysqlite:///local-cache.sqlite"
        ''',
        '''
        import os
        DATABASE_URL = os.environ.get("DATABASE_URL")
        if not DATABASE_URL:
            DATABASE_URL = build_repo_local_url()
            raise ValueError("DATABASE_URL environment variable not set")
        ''',
    ],
)
def test_legacy_database_guard_rejects_broader_fallback_shapes(unsafe_source):
    with pytest.raises(AssertionError):
        assert_legacy_database_fails_closed(textwrap.dedent(unsafe_source))


def test_retired_legacy_databases_do_not_fall_back_to_repo_sqlite_files():
    paths = [
        BACKEND_ROOT / 'database.py',
        REPOSITORY_ROOT / 'auth-forum-api' / 'database.py',
    ]

    for path in paths:
        assert_legacy_database_fails_closed(path.read_text(encoding='utf-8'))


def _isolated_environment(*missing: str) -> dict[str, str]:
    environment = os.environ.copy()
    for name in missing:
        environment.pop(name, None)
    environment['PYTHONPATH'] = ''
    return environment


@pytest.mark.parametrize(
    'source',
    [
        BACKEND_ROOT / 'database.py',
        REPOSITORY_ROOT / 'auth-forum-api' / 'database.py',
    ],
)
def test_retired_database_imports_fail_before_engine_or_file_fallback(source, tmp_path):
    isolated_root = tmp_path / source.parent.name
    isolated_root.mkdir()
    isolated_module = isolated_root / 'database.py'
    isolated_module.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')

    result = subprocess.run(
        [
            sys.executable,
            '-c',
            textwrap.dedent(
                '''
                import atexit
                import pathlib
                import runpy
                import sys

                import dotenv
                import sqlalchemy

                dotenv.load_dotenv = lambda *_args, **_kwargs: False
                engine_calls = []
                sqlalchemy.create_engine = lambda *args, **kwargs: engine_calls.append((args, kwargs))

                def record_probe():
                    root = pathlib.Path(sys.argv[2])
                    database_files = [
                        path
                        for pattern in ('*.db', '*.sqlite', '*.sqlite3')
                        for path in root.rglob(pattern)
                    ]
                    outcome = 'no fallback' if not engine_calls and not database_files else repr(
                        {'engine_calls': engine_calls, 'database_files': database_files}
                    )
                    (root / 'database-probe.txt').write_text(outcome, encoding='utf-8')

                atexit.register(record_probe)
                runpy.run_path(sys.argv[1], run_name='__legacy_database_probe__')
                '''
            ),
            str(isolated_module),
            str(tmp_path),
        ],
        cwd=isolated_root,
        env=_isolated_environment('DATABASE_URL'),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode != 0
    assert 'DATABASE_URL environment variable' in result.stderr
    assert 'not set' in result.stderr
    assert (tmp_path / 'database-probe.txt').read_text(encoding='utf-8') == 'no fallback'


@pytest.mark.parametrize('environment', ['staging', 'production'])
def test_active_runtime_rejects_sqlite_outside_development_and_tests(environment):
    with pytest.raises(ValidationError, match='Production database must use PostgreSQL'):
        Settings(
            environment=environment,
            database_url='sqlite:///unbound_bible.db',
            jwt_secret_key='release-specific-secret-that-is-long-enough',
            public_base_url='https://staging.example.test',
            cors_origins=['https://staging.example.test'],
            ai_chat_provider='openai_compatible',
            ai_embedding_provider='openai_compatible',
            ai_transcription_provider='openai_compatible',
            ai_api_key='test-provider-key',
        )


def test_production_launchers_import_only_the_modular_application():
    replit_configuration = (REPOSITORY_ROOT / '.replit').read_text(encoding='utf-8')
    dockerfile = (BACKEND_ROOT / 'Dockerfile').read_text(encoding='utf-8')
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / 'compose.staging.yml').read_text(encoding='utf-8')
    )
    application = (BACKEND_ROOT / 'app' / 'application.py').read_text(encoding='utf-8')

    assert (
        'args = "cd backend && python -m uvicorn app.application:app '
        '--host 0.0.0.0 --port 8000"'
    ) in replit_configuration

    command_lines = [
        line.strip()[len('CMD '):]
        for line in dockerfile.splitlines()
        if line.strip().upper().startswith('CMD ')
    ]
    assert command_lines
    assert json.loads(command_lines[-1]) == [
        'sh',
        '-c',
        'alembic -c alembic.ini upgrade head && exec uvicorn '
        'app.application:app --host 0.0.0.0 --port 8000',
    ]

    api_service = compose['services']['api']
    assert 'command' not in api_service
    assert 'entrypoint' not in api_service

    assert 'from database import' not in application
    assert 'from auth import' not in application
    assert 'import main' not in application


def _safe_environment(database_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({
        'DATABASE_URL': f'sqlite:///{database_path}',
        'ENVIRONMENT': 'test',
        'JWT_SECRET_KEY': 'test-secret-key-that-is-at-least-32-characters',
        'PUBLIC_BASE_URL': 'http://localhost:5001',
        'CORS_ORIGINS': '["http://localhost:5001"]',
        'AI_CHAT_PROVIDER': 'demo',
        'AI_EMBEDDING_PROVIDER': 'demo',
        'AI_TRANSCRIPTION_PROVIDER': 'demo',
        'OPENAI_API_KEY': 'test-key',
    })
    return environment


def _run_legacy_python(code: str, database_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, '-c', textwrap.dedent(code)],
        cwd=BACKEND_ROOT,
        env=_safe_environment(database_path),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def test_retired_legacy_auth_runtimes_keep_fail_closed_configuration():
    backend_auth = (BACKEND_ROOT / 'auth.py').read_text(encoding='utf-8')
    forum_auth = (REPOSITORY_ROOT / 'auth-forum-api' / 'auth.py').read_text(
        encoding='utf-8'
    )

    for text in [backend_auth, forum_auth]:
        assert_legacy_auth_fails_closed(text)
        assert 'guest_token' not in text
        assert 'default insecure development key' not in text


def test_legacy_auth_guard_rejects_alternate_secret_assignment():
    unsafe_source = '''
    import os
    SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    if not SECRET_KEY:
        SECRET_KEY = load_guest_key()
        raise RuntimeError("JWT_SECRET_KEY environment variable is required")
    '''

    with pytest.raises(AssertionError):
        assert_legacy_auth_fails_closed(textwrap.dedent(unsafe_source))


@pytest.mark.parametrize(
    'source',
    [
        BACKEND_ROOT / 'auth.py',
        REPOSITORY_ROOT / 'auth-forum-api' / 'auth.py',
    ],
)
def test_retired_auth_imports_fail_closed_without_jwt_secret(source, tmp_path):
    isolated_root = tmp_path / source.parent.name
    isolated_root.mkdir()
    isolated_module = isolated_root / 'auth.py'
    isolated_module.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')

    result = subprocess.run(
        [
            sys.executable,
            '-c',
            textwrap.dedent(
                '''
                import atexit
                import pathlib
                import runpy
                import sys
                import types

                import dotenv

                dotenv.load_dotenv = lambda *_args, **_kwargs: False
                dependency_calls = []

                database = types.ModuleType('database')
                database.get_db = lambda: dependency_calls.append('database.get_db')
                sys.modules['database'] = database

                models = types.ModuleType('models')
                models.User = type('User', (), {})
                models.UserRole = type('UserRole', (), {})
                sys.modules['models'] = models

                schemas = types.ModuleType('schemas')
                schemas.TokenData = type('TokenData', (), {})
                sys.modules['schemas'] = schemas

                def record_probe():
                    outcome = 'no fallback' if not dependency_calls else repr(dependency_calls)
                    pathlib.Path(sys.argv[2]).joinpath('auth-probe.txt').write_text(
                        outcome,
                        encoding='utf-8',
                    )

                atexit.register(record_probe)
                runpy.run_path(sys.argv[1], run_name='__legacy_auth_probe__')
                '''
            ),
            str(isolated_module),
            str(tmp_path),
        ],
        cwd=isolated_root,
        env=_isolated_environment('JWT_SECRET_KEY'),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode != 0
    assert 'JWT_SECRET_KEY environment variable is required' in result.stderr
    assert (tmp_path / 'auth-probe.txt').read_text(encoding='utf-8') == 'no fallback'


def test_replit_backend_launcher_module_imports_with_safe_settings(tmp_path):
    replit_configuration = (REPOSITORY_ROOT / '.replit').read_text(encoding='utf-8')
    assert (
        'args = "cd backend && python -m uvicorn app.application:app '
        '--host 0.0.0.0 --port 8000"'
    ) in replit_configuration

    result = _run_legacy_python(
        '''
        import sys
        from app.application import app
        assert {'main', 'auth', 'database'}.isdisjoint(sys.modules)
        schema = app.openapi()
        assert '/api/v1/books' in schema['paths']
        print(app.title)
        ''',
        tmp_path / 'launcher.db',
    )

    assert result.returncode == 0, result.stderr
    assert 'Unbound Bible API' in result.stdout


def test_legacy_launcher_exposes_only_migrated_private_study_routes(tmp_path):
    result = _run_legacy_python(
        '''
        import main

        route_methods = [
            (route.path, method)
            for route in main.app.routes
            for method in getattr(route, 'methods', set())
            if route.path in {'/api/v1/notes', '/api/v1/studies', '/api/v1/study-sessions'}
        ]
        assert sorted(route_methods) == [
            ('/api/v1/notes', 'GET'),
            ('/api/v1/notes', 'POST'),
            ('/api/v1/studies', 'GET'),
            ('/api/v1/studies', 'POST'),
        ]

        schema = main.app.openapi()
        assert '/api/v1/admin/embeddings/populate' not in schema['paths']
        ''',
        tmp_path / 'routes.db',
    )

    assert result.returncode == 0, result.stderr


def test_legacy_launcher_does_not_register_incompatible_study_tables(tmp_path):
    result = _run_legacy_python(
        '''
        import main

        assert 'user_notes' not in main.Base.metadata.tables
        assert 'study_sessions' not in main.Base.metadata.tables
        ''',
        tmp_path / 'metadata.db',
    )

    assert result.returncode == 0, result.stderr


def test_reconciled_legacy_routes_serialize_empty_database_responses(tmp_path):
    result = _run_legacy_python(
        '''
        from fastapi.testclient import TestClient
        import main

        client = TestClient(main.app)
        expectations = {
            '/api/v1/race-misuse': [],
            '/api/v1/factbook': [],
            '/api/v1/canons/compare': {'books': []},
        }
        for path, expected in expectations.items():
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
            assert response.json() == expected, path
        ''',
        tmp_path / 'serialization.db',
    )

    assert result.returncode == 0, result.stderr


def test_missing_ethiopian_text_is_explicitly_unavailable_and_never_scripture(tmp_path):
    result = _run_legacy_python(
        '''
        from fastapi.testclient import TestClient
        import main

        client = TestClient(main.app)
        comparison = client.get('/api/v1/texts/Genesis/1/1/compare')
        assert comparison.status_code == 200, comparison.text
        payload = comparison.json()
        assert payload['ethiopian_baseline'] is None
        assert payload['ethiopian_availability'] == {
            'available': False,
            'status': 'unavailable',
            'translation': None,
        }

        reference = client.get('/api/v1/ethiopian-reference/Genesis/1/1')
        assert reference.status_code == 404, reference.text
        detail = reference.json()['detail']
        assert detail == {
            'status': 'unavailable',
            'book': 'Genesis',
            'chapter': 1,
            'verse': 1,
            'translation': None,
        }
        assert 'text' not in detail
        ''',
        tmp_path / 'missing.db',
    )

    assert result.returncode == 0, result.stderr


def test_ethiopian_endpoints_return_verified_database_text_unchanged(tmp_path):
    verified_text = 'Verified database text — በመጀመሪያ'
    result = _run_legacy_python(
        f'''
        from fastapi.testclient import TestClient
        import main
        from database import SessionLocal

        with SessionLocal() as session:
            session.add(main.BiblicalText(
                book='Genesis', chapter=1, verse=1,
                text={verified_text!r}, translation='ETH81',
            ))
            session.commit()

        client = TestClient(main.app)
        comparison = client.get('/api/v1/texts/Genesis/1/1/compare')
        assert comparison.status_code == 200, comparison.text
        payload = comparison.json()
        assert payload['ethiopian_baseline'] == {verified_text!r}
        assert payload['ethiopian_availability'] == {{
            'available': True,
            'status': 'available',
            'translation': 'ETH81',
        }}

        reference = client.get('/api/v1/ethiopian-reference/Genesis/1/1')
        assert reference.status_code == 200, reference.text
        assert reference.json() == {{
            'book': 'Genesis', 'chapter': 1, 'verse': 1,
            'text': {verified_text!r}, 'translation': 'ETH81',
            'is_sample_placeholder': False,
        }}
        ''',
        tmp_path / 'verified.db',
    )

    assert result.returncode == 0, result.stderr


def test_chapter_content_exposes_verified_edition_metadata(tmp_path):
    result = _run_legacy_python(
        '''
        from fastapi.testclient import TestClient
        import main
        from app.database import Base as AppBase
        from app.library.models import TextEdition
        from database import SessionLocal

        AppBase.metadata.create_all(main.engine)

        with main.app.state.session_factory() as session:
            session.add(TextEdition(
                edition_code='GEEZ-TEST',
                name="Ge'ez Test Edition",
                reading_language="Ge'ez",
                source_language="Ge'ez",
                script='Ethiopic',
                publisher='Test Publisher',
                license_spdx='CC-BY-NC-ND-4.0',
                attribution='Test attribution',
                provenance_url='https://example.org/geez',
                source_tradition='Ethiopian Orthodox Tewahedo',
                relationship='exact_ethiopian',
                versification='Test versification',
                expected_coverage={'genesis': {'chapters': 1}},
                verification_status='verified',
            ))
            session.commit()

        with SessionLocal() as session:
            session.add(main.BiblicalText(
                book='Genesis', chapter=1, verse=1,
                text='በቀዳሚ', translation='GEEZ-TEST',
            ))
            session.commit()

        response = TestClient(main.app).get(
            '/api/biblical-texts/chapter-content?book=Genesis&chapter=1'
        )
        assert response.status_code == 200, response.text
        assert response.json()['content'][0]['edition'] == {
            'code': 'GEEZ-TEST',
            'name': "Ge'ez Test Edition",
            'language': "Ge'ez",
            'source_language': "Ge'ez",
            'script': 'Ethiopic',
            'publisher': 'Test Publisher',
            'license': 'CC-BY-NC-ND-4.0',
            'attribution': 'Test attribution',
            'provenance_url': 'https://example.org/geez',
            'source_tradition': 'Ethiopian Orthodox Tewahedo',
            'relationship': 'exact_ethiopian',
            'versification': 'Test versification',
            'verification_status': 'verified',
        }
        ''',
        tmp_path / 'edition-metadata.db',
    )

    assert result.returncode == 0, result.stderr
