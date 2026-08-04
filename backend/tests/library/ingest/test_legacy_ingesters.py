import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LEGACY_INGESTERS = (
    REPOSITORY_ROOT / 'server/data/ingest_ertale_canon.py',
    REPOSITORY_ROOT / 'server/data/ingest_report_data.py',
    REPOSITORY_ROOT / 'server/data/ingest_ethiopian_canon.py',
)
FORBIDDEN_SOURCE = (
    '_create_unverified_context',
    'verify=False',
    'requests.',
    'urllib.',
    'sqlalchemy',
    'sqlite3',
    'delete from',
    'insert into',
    '.delete(',
    '.add(',
    '.commit(',
    '.connect(',
)


@pytest.mark.parametrize('script', LEGACY_INGESTERS)
def test_legacy_ingesters_are_inert_migration_notices(script):
    source = script.read_text(encoding='utf-8').casefold()

    assert 'python -m app.library.ingest.cli' in source
    assert 'stage' in source
    assert 'validate' in source
    assert 'publish --confirm' in source
    for forbidden in FORBIDDEN_SOURCE:
        assert forbidden not in source


@pytest.mark.parametrize('script', LEGACY_INGESTERS)
def test_legacy_ingester_import_is_side_effect_free(script, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('HOME', str(tmp_path))
    before = set(tmp_path.rglob('*'))

    runpy.run_path(str(script), run_name='legacy_ingester_import')

    assert capsys.readouterr().out == ''
    assert set(tmp_path.rglob('*')) == before


@pytest.mark.parametrize('script', LEGACY_INGESTERS)
def test_legacy_ingester_execution_cannot_create_a_database_or_contact_a_service(script, tmp_path):
    environment = {
        'HOME': str(tmp_path),
        'NO_PROXY': '*',
        'PATH': os.environ['PATH'],
    }

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    message = result.stdout + result.stderr
    assert result.returncode != 0
    assert 'python -m app.library.ingest.cli' in message
    assert 'stage' in message
    assert 'validate' in message
    assert 'publish --confirm' in message
    assert not list(tmp_path.rglob('*.db'))
