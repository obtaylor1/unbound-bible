import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
from pydantic import ValidationError

from app.config import Settings


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


def assert_legacy_database_fails_closed(text: str) -> None:
    """Assert that a retired database module cannot silently use a repo SQLite file."""
    normalized = text.lower()
    assert 'os.environ.get("database_url")' in normalized
    assert 'if not database_url:' in normalized
    assert 'database_url environment variable' in normalized
    assert 'not set' in normalized
    assert 'sqlite:///' not in normalized
    assert 'unbound_bible.db' not in normalized
    assert 'auth_forum.db' not in normalized


def test_legacy_database_guard_rejects_repo_sqlite_fallback(tmp_path):
    unsafe_module = tmp_path / 'database.py'
    unsafe_module.write_text(
        'DATABASE_URL = "sqlite:///unbound_bible.db"\n',
        encoding='utf-8',
    )

    with pytest.raises(AssertionError):
        assert_legacy_database_fails_closed(unsafe_module.read_text(encoding='utf-8'))


def test_retired_legacy_databases_do_not_fall_back_to_repo_sqlite_files():
    paths = [
        BACKEND_ROOT / 'database.py',
        REPOSITORY_ROOT / 'auth-forum-api' / 'database.py',
    ]

    for path in paths:
        assert_legacy_database_fails_closed(path.read_text(encoding='utf-8'))


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
    launchers = [
        (REPOSITORY_ROOT / '.replit').read_text(encoding='utf-8'),
        (BACKEND_ROOT / 'Dockerfile').read_text(encoding='utf-8'),
    ]
    application = (BACKEND_ROOT / 'app' / 'application.py').read_text(encoding='utf-8')

    for launcher in launchers:
        assert 'app.application:app' in launcher
        assert 'main:app' not in launcher

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
        assert 'SECRET_KEY = os.environ.get("JWT_SECRET_KEY")' in text
        assert 'SECRET_KEY = os.environ.get("JWT_SECRET_KEY",' not in text
        assert 'SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or' not in text
        assert 'guest_token' not in text
        assert 'default insecure development key' not in text
        assert 'JWT_SECRET_KEY environment variable is required' in text


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
