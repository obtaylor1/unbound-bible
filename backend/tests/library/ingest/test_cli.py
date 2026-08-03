import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from typer.testing import CliRunner


runner = CliRunner()


def _database_url(test_settings):
    return test_settings.database_url


def _manifest(
    path: Path, *, edition_code: str = 'CLI_TEST', source_content: bytes = b'test source'
) -> Path:
    payload = {
        'edition_code': edition_code,
        'name': 'CLI test edition',
        'reading_language': 'English',
        'source_language': 'Hebrew',
        'script': 'Latin',
        'translator': None,
        'publisher': None,
        'published_year': None,
        'license_spdx': 'LicenseRef-Public-Domain',
        'attribution': 'Public-domain test fixture.',
        'provenance_url': 'https://example.org/source',
        'source_tradition': 'Test tradition',
        'relationship': 'general_reading',
        'versification': 'Test',
        'expected_works': {'genesis': {'chapters': 1, 'verse_counts': {'1': 1}}},
        'source_files': [{
            'path': 'genesis.usfm',
            'sha256': sha256(source_content).hexdigest(),
            'source_url': 'https://example.org/genesis.usfm',
        }],
        'adapter': 'usfm',
        'adapter_options': {},
    }
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


@pytest.fixture
def cli_database(test_settings):
    from app.application import create_application

    application = create_application(test_settings)
    yield test_settings.database_url
    application.state.database_engine.dispose()


def _json(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


@pytest.mark.parametrize('command', ['seed-canon', 'stage', 'validate', 'publish', 'rollback'])
def test_mutating_commands_never_use_an_implicit_database(monkeypatch, command, tmp_path):
    from app.library.ingest.cli import app

    monkeypatch.delenv('DATABASE_URL', raising=False)
    args = [command]
    if command == 'stage':
        args += ['--manifest', str(_manifest(tmp_path / 'manifest.json'))]
    elif command in {'validate', 'publish'}:
        args += ['--run-id', '00000000-0000-0000-0000-000000000001']
        if command == 'publish':
            args.append('--confirm')
    elif command == 'rollback':
        args += ['--edition', 'CLI_TEST']

    result = runner.invoke(app, args)

    assert result.exit_code != 0
    assert 'DATABASE_URL' in result.output


def test_help_lists_all_safe_operator_commands():
    from app.library.ingest.cli import app

    result = runner.invoke(app, ['--help'])

    assert result.exit_code == 0
    for command in (
        'seed-canon', 'stage', 'validate', 'publish', 'rollback', 'coverage-report'
    ):
        assert command in result.output


@pytest.mark.parametrize(
    'command',
    ['seed-canon', 'stage', 'validate', 'publish', 'rollback', 'coverage-report'],
)
def test_each_command_has_help_text(command):
    from app.library.ingest.cli import app

    result = runner.invoke(app, [command, '--help'])

    assert result.exit_code == 0, result.output
    assert '--database-url' in result.output


def test_stage_has_an_injectable_adapter_boundary_and_structured_output(
    cli_database, tmp_path, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.types import NormalizedVerse
    from app.library.models import TextEdition

    manifest_path = _manifest(tmp_path / 'manifest.json')
    monkeypatch.setitem(
        cli.ADAPTERS,
        'usfm',
        lambda _manifest, _path: (
            NormalizedVerse('genesis', 'Genesis', 1, 1, 'In the beginning.', 'genesis.usfm:1:1'),
        ),
    )

    payload = _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(manifest_path), '--database-url', cli_database,
    ]))

    assert payload['edition_code'] == 'CLI_TEST'
    assert payload['run_id']
    assert len(payload['checksum']) == 64
    assert payload['staged_count'] == 1
    assert payload['errors'] == 0
    assert payload['warnings'] == 0
    assert payload['next_action'] == 'validate'
    engine, session_factory = cli._database(cli_database)
    try:
        with session_factory() as session:
            placeholder = session.get(TextEdition, 'CLI_TEST')
            assert (
                placeholder.name,
                placeholder.reading_language,
                placeholder.verification_status,
                placeholder.source_checksum,
            ) == (
                'Pending publication (CLI_TEST)',
                'Undetermined',
                'staged',
                None,
            )
    finally:
        engine.dispose()


def test_stage_fails_clearly_when_phase_three_adapter_is_not_installed(
    cli_database, tmp_path, monkeypatch
):
    from app.library.ingest import cli

    monkeypatch.setattr(cli, 'ADAPTERS', {})
    result = runner.invoke(cli.app, [
        'stage', '--manifest', str(_manifest(tmp_path / 'manifest.json')),
        '--database-url', cli_database,
    ])

    assert result.exit_code != 0
    assert 'adapter' in result.output.lower()
    assert 'not installed' in result.output.lower()


def test_staging_and_failed_validation_preserve_published_edition_metadata(
    cli_database, tmp_path, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.types import NormalizedVerse
    from app.library.models import TextEdition
    from sqlalchemy import text

    engine, session_factory = cli._database(cli_database)
    try:
        with engine.begin() as connection:
            connection.execute(text('''
                CREATE TABLE biblical_texts (
                    id INTEGER PRIMARY KEY, book TEXT NOT NULL, chapter INTEGER NOT NULL,
                    verse INTEGER NOT NULL, text TEXT NOT NULL, translation TEXT
                )
            '''))
    finally:
        engine.dispose()

    current_text = {'value': 'Published text.'}
    monkeypatch.setitem(cli.ADAPTERS, 'usfm', lambda *_: (
        NormalizedVerse(
            'genesis', 'Genesis', 1, 1, current_text['value'], 'genesis.usfm:1:1'
        ),
    ))
    first_manifest = _manifest(tmp_path / 'first.json', source_content=b'first')
    first = _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(first_manifest), '--database-url', cli_database,
    ]))
    _json(runner.invoke(cli.app, [
        'validate', '--run-id', first['run_id'], '--database-url', cli_database,
    ]))
    _json(runner.invoke(cli.app, [
        'publish', '--run-id', first['run_id'], '--confirm', '--database-url', cli_database,
    ]))

    replacement_manifest = _manifest(tmp_path / 'replacement.json', source_content=b'second')
    replacement_payload = json.loads(replacement_manifest.read_text(encoding='utf-8'))
    replacement_payload.update({
        'name': 'Unpublished Replacement',
        'reading_language': "Ge'ez",
        'source_language': "Ge'ez",
        'script': "Ge'ez",
    })
    replacement_manifest.write_text(json.dumps(replacement_payload), encoding='utf-8')
    current_text['value'] = 'Text unavailable.'
    replacement = _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(replacement_manifest), '--database-url', cli_database,
    ]))

    engine, session_factory = cli._database(cli_database)
    try:
        with session_factory() as session:
            edition = session.get(TextEdition, 'CLI_TEST')
            assert (
                edition.name, edition.reading_language, edition.verification_status,
                edition.source_checksum,
            ) == (
                'CLI test edition', 'English', 'verified', first['checksum'],
            )
    finally:
        engine.dispose()

    validation = _json(runner.invoke(cli.app, [
        'validate', '--run-id', replacement['run_id'], '--database-url', cli_database,
    ]))
    assert validation['errors'] == 1

    engine, session_factory = cli._database(cli_database)
    try:
        with session_factory() as session:
            edition = session.get(TextEdition, 'CLI_TEST')
            assert (
                edition.name, edition.reading_language, edition.verification_status,
                edition.source_checksum,
            ) == (
                'CLI test edition', 'English', 'verified', first['checksum'],
            )
    finally:
        engine.dispose()


def test_publish_cli_refuses_verified_run_with_positive_error_count(
    cli_database, tmp_path, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.models import ScriptureIngestRun
    from app.library.ingest.types import NormalizedVerse

    monkeypatch.setitem(cli.ADAPTERS, 'usfm', lambda *_: (
        NormalizedVerse('genesis', 'Genesis', 1, 1, 'Unsafe counter.', 'genesis.usfm:1:1'),
    ))
    manifest_path = _manifest(tmp_path / 'manifest.json')
    staged = _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(manifest_path), '--database-url', cli_database,
    ]))

    engine, session_factory = cli._database(cli_database)
    try:
        with session_factory() as session, session.begin():
            run = session.get(ScriptureIngestRun, UUID(staged['run_id']))
            run.status = 'verified'
            run.error_count = 1
    finally:
        engine.dispose()

    result = runner.invoke(cli.app, [
        'publish', '--run-id', staged['run_id'], '--confirm',
        '--database-url', cli_database,
    ])

    assert result.exit_code != 0
    assert 'error count' in result.output.lower()


def test_rollback_command_restores_the_previous_published_run(
    cli_database, tmp_path, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.types import NormalizedVerse
    from sqlalchemy import text

    engine, _ = cli._database(cli_database)
    try:
        with engine.begin() as connection:
            connection.execute(text('''
                CREATE TABLE biblical_texts (
                    id INTEGER PRIMARY KEY, book TEXT NOT NULL, chapter INTEGER NOT NULL,
                    verse INTEGER NOT NULL, text TEXT NOT NULL, translation TEXT
                )
            '''))
    finally:
        engine.dispose()

    current_text = {'value': 'First text.'}
    monkeypatch.setitem(cli.ADAPTERS, 'usfm', lambda *_: (
        NormalizedVerse(
            'genesis', 'Genesis', 1, 1, current_text['value'], 'genesis.usfm:1:1'
        ),
    ))

    run_ids = []
    for number, text_value in enumerate(('First text.', 'Second text.'), start=1):
        current_text['value'] = text_value
        manifest_path = _manifest(
            tmp_path / f'manifest-{number}.json', source_content=f'source-{number}'.encode()
        )
        staged = _json(runner.invoke(cli.app, [
            'stage', '--manifest', str(manifest_path), '--database-url', cli_database,
        ]))
        run_ids.append(staged['run_id'])
        _json(runner.invoke(cli.app, [
            'validate', '--run-id', staged['run_id'], '--database-url', cli_database,
        ]))
        _json(runner.invoke(cli.app, [
            'publish', '--run-id', staged['run_id'], '--confirm',
            '--database-url', cli_database,
        ]))

    rolled_back = _json(runner.invoke(cli.app, [
        'rollback', '--edition', 'CLI_TEST', '--database-url', cli_database,
    ]))

    assert rolled_back['run_id'] == run_ids[0]
    assert rolled_back['displaced_run_id'] == run_ids[1]
    assert rolled_back['published_count'] == 1


def test_stage_validate_publish_and_coverage_report(cli_database, tmp_path, monkeypatch):
    from app.library.ingest import cli
    from app.library.ingest.types import NormalizedVerse
    from sqlalchemy import text

    manifest_path = _manifest(tmp_path / 'manifest.json')
    monkeypatch.setitem(cli.ADAPTERS, 'usfm', lambda *_: (
        NormalizedVerse('genesis', 'Genesis', 1, 1, 'In the beginning.', 'genesis.usfm:1:1'),
    ))
    staged = _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(manifest_path), '--database-url', cli_database,
    ]))
    validated = _json(runner.invoke(cli.app, [
        'validate', '--run-id', staged['run_id'], '--database-url', cli_database,
    ]))
    assert validated['errors'] == 0
    assert validated['next_action'] == 'publish --confirm'

    engine, _ = cli._database(cli_database)
    try:
        with engine.begin() as connection:
            connection.execute(text('''
                CREATE TABLE biblical_texts (
                    id INTEGER PRIMARY KEY, book TEXT NOT NULL, chapter INTEGER NOT NULL,
                    verse INTEGER NOT NULL, text TEXT NOT NULL, translation TEXT
                )
            '''))
    finally:
        engine.dispose()

    without_confirmation = runner.invoke(cli.app, [
        'publish', '--run-id', staged['run_id'], '--database-url', cli_database,
    ])
    assert without_confirmation.exit_code != 0
    assert '--confirm' in without_confirmation.output

    published = _json(runner.invoke(cli.app, [
        'publish', '--run-id', staged['run_id'], '--confirm',
        '--database-url', cli_database,
    ]))
    assert published['published_count'] == 1
    assert published['next_action'] == 'coverage-report'

    coverage = _json(runner.invoke(cli.app, [
        'coverage-report', '--run-id', staged['run_id'], '--database-url', cli_database,
    ]))
    assert coverage['run_id'] == staged['run_id']
    assert coverage['edition_code'] == 'CLI_TEST'
    assert coverage['published_count'] == 1


def test_validate_records_errors_and_publish_refuses_the_run(
    cli_database, tmp_path, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.types import NormalizedVerse

    manifest_path = _manifest(tmp_path / 'manifest.json')
    monkeypatch.setitem(cli.ADAPTERS, 'usfm', lambda *_: (
        NormalizedVerse('genesis', 'Genesis', 1, 1, 'Text unavailable.', 'genesis.usfm:1:1'),
    ))
    staged = _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(manifest_path), '--database-url', cli_database,
    ]))
    validated = _json(runner.invoke(cli.app, [
        'validate', '--run-id', staged['run_id'], '--database-url', cli_database,
    ]))
    assert validated['errors'] == 1
    assert validated['next_action'] == 'fix source and stage a new run'

    result = runner.invoke(cli.app, [
        'publish', '--run-id', staged['run_id'], '--confirm',
        '--database-url', cli_database,
    ])
    assert result.exit_code != 0
    assert 'verified' in result.output.lower() or 'error' in result.output.lower()


def test_seed_canon_accepts_database_url_from_environment(cli_database, monkeypatch):
    from app.library.ingest.cli import app

    monkeypatch.setenv('DATABASE_URL', cli_database)
    payload = _json(runner.invoke(app, ['seed-canon']))

    assert payload['edition_code'] == 'ETHIO81'
    assert payload['staged_count'] == 0
    assert payload['next_action'] == 'stage'


def test_rollback_reports_when_no_predecessor_exists(cli_database):
    from app.library.ingest.cli import app

    result = runner.invoke(app, [
        'rollback', '--edition', 'MISSING', '--database-url', cli_database,
    ])

    assert result.exit_code != 0
    assert 'not found' in result.output.lower()
