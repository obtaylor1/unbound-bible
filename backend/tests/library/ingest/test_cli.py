import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from click import unstyle
from typer.testing import CliRunner


runner = CliRunner()


def test_installed_adapters_are_explicitly_registered():
    from app.library.ingest.cli import ADAPTERS

    assert set(ADAPTERS) == {'weahadu_bundle', 'composite_english_bundle'}


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
    assert '--database-url' in unstyle(result.output)


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

    restored_health = _json(runner.invoke(cli.app, [
        'coverage-report', '--run-id', run_ids[0], '--database-url', cli_database,
    ]))
    assert restored_health['active_run_id'] == run_ids[0]
    assert restored_health['is_active'] is True
    displaced_health = _json(runner.invoke(cli.app, [
        'coverage-report', '--run-id', run_ids[1], '--database-url', cli_database,
    ]))
    assert displaced_health['run_id'] == run_ids[1]
    assert displaced_health['active_run_id'] == run_ids[0]
    assert displaced_health['is_active'] is False


def test_stage_validate_publish_and_coverage_report(cli_database, tmp_path, monkeypatch):
    from app.library.ingest import cli
    from app.library.ingest.models import ScriptureIngestRun
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

    engine, session_factory = cli._database(cli_database)
    try:
        with session_factory() as session, session.begin():
            run = session.get(ScriptureIngestRun, UUID(staged['run_id']))
            run.error_count = 1
    finally:
        engine.dispose()
    rejected_retry = runner.invoke(cli.app, [
        'publish', '--run-id', staged['run_id'], '--confirm',
        '--database-url', cli_database,
    ])
    assert rejected_retry.exit_code != 0
    assert 'error count' in rejected_retry.output.lower()


def test_validate_passes_composite_declared_omissions_to_quality_gate(
    cli_database, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.types import NormalizedVerse
    from app.library.ingest.validate import ValidationResult

    manifest_path = (
        Path(__file__).resolve().parents[3]
        / 'data/scripture/eotc-composite-en/manifest.json'
    )
    monkeypatch.setitem(cli.ADAPTERS, 'composite_english_bundle', lambda *_: (
        NormalizedVerse(
            'genesis', 'Genesis', 1, 1, 'In the beginning.',
            'corrected-bundle.zip:GEN.json:1:1',
        ),
    ))
    captured = {}

    def fake_validate(rows, expected, warnings=(), known_missing_verses=None):
        captured['known_missing_verses'] = known_missing_verses
        return ValidationResult(())

    monkeypatch.setattr(cli, 'validate_edition', fake_validate)
    staged = _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(manifest_path), '--database-url', cli_database,
    ]))
    validated = _json(runner.invoke(cli.app, [
        'validate', '--run-id', staged['run_id'], '--database-url', cli_database,
    ]))

    assert validated['errors'] == 0
    assert captured['known_missing_verses']['2-meqabyan'] == {
        '16': [9], '21': [9],
    }
    assert sum(
        len(verses)
        for chapters in captured['known_missing_verses'].values()
        for verses in chapters.values()
    ) == 48


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


def test_coverage_report_by_edition_uses_active_run_not_newer_candidates(cli_database):
    from app.library.ingest import cli
    from app.library.ingest.publish import publish_run
    from sqlalchemy import text
    from .conftest import make_ingest_run

    engine, session_factory = cli._database(cli_database)
    try:
        with engine.begin() as connection:
            connection.execute(text('''
                CREATE TABLE biblical_texts (
                    id INTEGER PRIMARY KEY, book TEXT NOT NULL, chapter INTEGER NOT NULL,
                    verse INTEGER NOT NULL, text TEXT NOT NULL, translation TEXT
                )
            '''))
        with session_factory() as session:
            active = make_ingest_run(session, 'REPORT', 'Active text')
            publish_run(session, active.id)
            candidate = make_ingest_run(session, 'REPORT', 'Candidate text', status='staged')
            session.commit()
            active_id = str(active.id)
            candidate_id = candidate.id
    finally:
        engine.dispose()

    staged_report = _json(runner.invoke(cli.app, [
        'coverage-report', '--edition', 'REPORT', '--database-url', cli_database,
    ]))
    assert staged_report['run_id'] == active_id
    assert staged_report['status'] == 'published'

    engine, session_factory = cli._database(cli_database)
    try:
        with session_factory() as session, session.begin():
            session.get(type(candidate), candidate_id).status = 'verified'
    finally:
        engine.dispose()
    verified_report = _json(runner.invoke(cli.app, [
        'coverage-report', '--edition', 'REPORT', '--database-url', cli_database,
    ]))
    assert verified_report['run_id'] == active_id
    assert verified_report['status'] == 'published'

    engine, session_factory = cli._database(cli_database)
    try:
        with session_factory() as session:
            unchanged = make_ingest_run(session, 'REPORT', 'Active text')
            unchanged.source_checksum = session.get(type(active), UUID(active_id)).source_checksum
            no_op = publish_run(session, unchanged.id)
            assert no_op.changed is False
            session.commit()
    finally:
        engine.dispose()
    no_op_report = _json(runner.invoke(cli.app, [
        'coverage-report', '--edition', 'REPORT', '--database-url', cli_database,
    ]))
    assert no_op_report['run_id'] == active_id
    assert no_op_report['status'] == 'published'


def test_coverage_report_clearly_reports_edition_without_active_publication(
    cli_database, tmp_path, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.types import NormalizedVerse

    monkeypatch.setitem(cli.ADAPTERS, 'usfm', lambda *_: (
        NormalizedVerse('genesis', 'Genesis', 1, 1, 'Staged only.', 'genesis.usfm:1:1'),
    ))
    _json(runner.invoke(cli.app, [
        'stage', '--manifest', str(_manifest(tmp_path / 'manifest.json')),
        '--database-url', cli_database,
    ]))

    report = _json(runner.invoke(cli.app, [
        'coverage-report', '--edition', 'CLI_TEST', '--database-url', cli_database,
    ]))

    assert report['run_id'] is None
    assert report['status'] == 'unpublished'
    assert report['next_action'] == 'validate or publish a candidate'


@pytest.mark.parametrize(
    'command,args',
    [
        ('seed-canon', []),
        ('stage', ['--manifest', '{manifest}']),
        ('validate', ['--run-id', '00000000-0000-0000-0000-000000000001']),
        ('publish', [
            '--run-id', '00000000-0000-0000-0000-000000000001', '--confirm',
        ]),
        ('rollback', ['--edition', 'CLI_TEST']),
        ('coverage-report', ['--edition', 'CLI_TEST']),
    ],
)
def test_all_commands_translate_invalid_database_urls_without_tracebacks(
    command, args, tmp_path
):
    from app.library.ingest.cli import app

    manifest = _manifest(tmp_path / 'manifest.json')
    resolved_args = [str(manifest) if value == '{manifest}' else value for value in args]
    result = runner.invoke(app, [
        command, *resolved_args, '--database-url', 'unsupported+driver://example/db',
    ])

    assert result.exit_code == 1
    assert result.output.startswith('Error:')
    assert 'Traceback' not in result.output


def test_database_context_disposes_created_engine_when_command_fails(monkeypatch):
    from app.library.ingest import cli

    class EngineProbe:
        disposed = False

        def dispose(self):
            self.disposed = True

    engine = EngineProbe()

    def failing_factory():
        raise RuntimeError('session factory failed')

    monkeypatch.setattr(cli, '_database', lambda _url: (engine, failing_factory))

    result = runner.invoke(cli.app, [
        'coverage-report', '--database-url', 'sqlite:///explicit.db',
    ])

    assert result.exit_code == 1
    assert result.output == 'Error: session factory failed\n'
    assert engine.disposed is True
