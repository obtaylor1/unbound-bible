import os
from pathlib import Path
import subprocess
import sys
import textwrap


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


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


def test_replit_backend_launcher_module_imports_with_safe_settings(tmp_path):
    replit_configuration = (REPOSITORY_ROOT / '.replit').read_text(encoding='utf-8')
    assert 'args = "cd backend && python main.py"' in replit_configuration

    result = _run_legacy_python(
        '''
        import main
        schema = main.app.openapi()
        assert '/api/v1/texts/{book}/{chapter}/{verse}/compare' in schema['paths']
        print(main.app.title)
        ''',
        tmp_path / 'launcher.db',
    )

    assert result.returncode == 0, result.stderr
    assert 'Liberation Bible Project API' in result.stdout


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
