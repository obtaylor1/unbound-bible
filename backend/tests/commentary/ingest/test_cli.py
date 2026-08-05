from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from typer.testing import CliRunner


runner = CliRunner()
BACKEND = Path(__file__).parents[3]


def payload(result):
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    return json.loads(lines[0])


def test_publish_requires_confirmation_and_emits_structured_error():
    from app.commentary.ingest.cli import app

    result = runner.invoke(app, ['publish', '--run-id', str(uuid4())])
    assert result.exit_code != 0
    assert payload(result)['error']['code'] == 'confirmation_required'


def test_rollback_requires_confirmation_and_emits_structured_error():
    from app.commentary.ingest.cli import app

    result = runner.invoke(app, ['rollback', '--publication-id', '1'])
    assert result.exit_code != 0
    assert payload(result)['error']['code'] == 'confirmation_required'


def test_acquire_command_emits_one_json_document(monkeypatch, tmp_path):
    from app.commentary.ingest import cli

    class Artifact:
        path = tmp_path / 'matthew-henry' / 'books.json'
        sidecar = tmp_path / 'matthew-henry' / 'books.json.sha256'
        checksum = 'a' * 64
        size = 2
        url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'

    monkeypatch.setattr(cli, 'acquire_source_bundle', lambda source, output: (Artifact(),))
    result = runner.invoke(cli.app, [
        'acquire', '--source', 'matthew-henry', '--output', str(tmp_path),
    ])
    assert result.exit_code == 0
    assert payload(result) == {
        'artifacts': 1, 'bytes': 2, 'command': 'acquire',
        'artifact_digests': [{
            'path': str(Artifact.path), 'sha256': 'a' * 64, 'url': Artifact.url,
        }],
        'output': str(tmp_path / 'matthew-henry'), 'source_id': 'matthew-henry',
        'status': 'acquired',
    }


def test_report_is_deterministic_and_atomically_written(monkeypatch, tmp_path):
    from app.commentary.ingest import cli

    run_id = uuid4()
    report_path = tmp_path / 'report.json'
    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(cli, '_build_report', lambda *_args: {
        'warnings': 0, 'run_id': str(run_id), 'coverage': {'entries': 1}, 'status': 'verified',
    })
    monkeypatch.setattr(cli, '_session_factory', lambda _url: lambda: Session())
    result = runner.invoke(cli.app, [
        'report', '--run-id', str(run_id), '--output', str(report_path),
        '--database-url', 'sqlite://',
    ])
    assert result.exit_code == 0
    expected = '{"coverage":{"entries":1},"run_id":"%s","status":"verified","warnings":0}\n' % run_id
    assert report_path.read_text(encoding='utf-8') == expected
    assert payload(result)['status'] == 'reported'


def test_cli_rolls_back_transaction_when_operation_fails(monkeypatch):
    from app.commentary.ingest import cli

    events = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def commit(self):
            events.append('commit')

        def rollback(self):
            events.append('rollback')

    monkeypatch.setattr(cli, '_session_factory', lambda _url: lambda: Session())
    monkeypatch.setattr(cli, 'publish_run', lambda *_args: (_ for _ in ()).throw(ValueError('blocked')))
    result = runner.invoke(cli.app, [
        'publish', '--run-id', str(uuid4()), '--confirm', '--database-url', 'sqlite://',
    ])
    assert result.exit_code != 0
    assert events == ['rollback']
    assert payload(result)['error']['code'] == 'operation_blocked'


def test_cli_does_not_expose_internal_exception_details(monkeypatch, tmp_path):
    from app.commentary.ingest import cli

    secret = 'database-password=do-not-disclose'
    monkeypatch.setattr(
        cli, 'acquire_source_bundle',
        lambda *_args: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    result = runner.invoke(cli.app, [
        'acquire', '--source', 'matthew-henry', '--output', str(tmp_path),
    ])

    assert result.exit_code != 0
    assert secret not in result.stdout
    assert payload(result)['error']['code'] == 'acquisition_failed'


def test_report_findings_are_ordered_by_every_emitted_field(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.cli import _build_report
    from app.commentary.models import CommentaryImportRun, CommentaryValidationFinding

    run = CommentaryImportRun(
        source_id=commentary_source.id, source_checksum='a' * 64,
        metadata_snapshot={}, status='verified', staged_count=0,
    )
    commentary_session.add(run)
    commentary_session.flush()
    for message in ('Zulu', 'Alpha'):
        commentary_session.add(CommentaryValidationFinding(
            run_id=run.id, severity='warning', code='style', message=message,
            work_id='genesis', chapter=1, verse=1,
        ))
    commentary_session.flush()

    report = _build_report(commentary_session, run.id)
    assert [item['message'] for item in report['findings']] == ['Alpha', 'Zulu']


def test_cli_commits_at_boundary_after_success(monkeypatch):
    from app.commentary.ingest import cli

    events = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def commit(self):
            events.append('commit')

        def rollback(self):
            events.append('rollback')

    class Publication:
        id = 9
        source_id = 'matthew-henry'
        edition_id = uuid4()
        version = 1

    monkeypatch.setattr(cli, '_session_factory', lambda _url: lambda: Session())
    monkeypatch.setattr(cli, 'publish_run', lambda *_args: Publication())
    result = runner.invoke(cli.app, [
        'publish', '--run-id', str(uuid4()), '--confirm', '--database-url', 'sqlite://',
    ])
    assert result.exit_code == 0
    assert events == ['commit']
    assert payload(result)['status'] == 'published'


def test_report_rejects_symlinked_output_ancestor(tmp_path):
    from app.commentary.ingest.cli import _atomic_json

    real = tmp_path / 'real'
    real.mkdir()
    linked = tmp_path / 'linked'
    linked.symlink_to(real, target_is_directory=True)

    try:
        _atomic_json(linked / 'report.json', {'status': 'verified'})
    except ValueError as error:
        assert 'symlink' in str(error)
    else:
        raise AssertionError('symlinked report parent was accepted')
    assert not (real / 'report.json').exists()


def test_report_parent_swap_cannot_redirect_final_report(tmp_path):
    from app.commentary.ingest.cli import _atomic_json

    parent = tmp_path / 'reports'
    parent.mkdir()
    attacker = tmp_path / 'attacker'
    attacker.mkdir()

    def swap():
        parent.rename(tmp_path / 'original-reports')
        parent.symlink_to(attacker, target_is_directory=True)

    with pytest.raises(ValueError, match='changed during report creation'):
        _atomic_json(parent / 'report.json', {'status': 'verified'}, _before_replace=swap)

    assert list(attacker.iterdir()) == []
    assert not (tmp_path / 'original-reports' / 'report.json').exists()


def test_stage_artifact_verification_rejects_oversized_files_before_reading(tmp_path):
    from app.commentary.ingest.cli import MAX_ARTIFACT_BYTES, _read_bounded_regular

    artifact = tmp_path / 'GEN.json'
    artifact.write_bytes(b'x' * (5 * 1024 * 1024 + 1))

    with pytest.raises(ValueError, match='5 MiB'):
        _read_bounded_regular(
            artifact, maximum=MAX_ARTIFACT_BYTES, label='input artifact',
        )


def test_parser_errors_are_single_structured_json_documents():
    from app.commentary.ingest.cli import app

    cases = [
        ['publish', '--run-id', 'not-a-uuid', '--confirm'],
        ['rollback', '--publication-id', 'not-an-integer', '--confirm'],
        ['acquire', '--source', 'matthew-henry'],
    ]
    for arguments in cases:
        result = runner.invoke(app, arguments)
        assert result.exit_code != 0
        assert result.stderr == ''
        parsed = payload(result)
        assert parsed['status'] == 'error'
        assert parsed['error']['code'] == 'invalid_command'


def test_stage_rejects_symlinked_input_ancestor(tmp_path):
    from app.commentary.ingest.cli import _safe_input_directory

    real = tmp_path / 'real'
    source = real / 'matthew-henry'
    source.mkdir(parents=True)
    linked = tmp_path / 'linked'
    linked.symlink_to(real, target_is_directory=True)

    with pytest.raises(ValueError, match='symlink'):
        _safe_input_directory(linked / 'matthew-henry')


def test_stage_parses_the_same_verified_bytes_when_path_is_swapped(monkeypatch, tmp_path):
    from dataclasses import replace
    from hashlib import sha256
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    fixture = Path(__file__).parents[1] / 'fixtures' / 'helloao-genesis-1.json'
    trusted = fixture.read_bytes()
    book_checksum = sha256(trusted).hexdigest()
    catalog = b'{}'
    catalog_checksum = sha256(catalog).hexdigest()
    book_url = 'https://bible.helloao.org/api/c/matthew-henry/GEN.json'
    catalog_url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'

    def generation(filename, raw, url):
        digest = sha256(raw).hexdigest()
        directory = source_dir / 'generations' / filename / digest
        directory.mkdir(parents=True)
        (directory / filename).write_bytes(raw)
        marker = {
            'schema_version': 1, 'source_id': 'matthew-henry',
            'artifact': filename, 'url': url, 'sha256': digest,
            'generation': f'generations/{filename}/{digest}',
        }
        (source_dir / f'{filename}.current.json').write_text(
            json.dumps(marker), encoding='utf-8',
        )

    generation('GEN.json', trusted, book_url)
    generation('books.json', catalog, catalog_url)
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1,
        'sources': {'matthew-henry': {'artifacts': {
            'GEN.json': {'url': book_url, 'sha256': book_checksum},
            'books.json': {'url': catalog_url, 'sha256': catalog_checksum},
        }}},
    }), encoding='utf-8')
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=1,
        expected_source_books=('GEN',), source_checksum=catalog_checksum,
    )
    real_loader = cli.load_helloao_bundle_bytes
    loader_calls = 0

    def swapping_loader(raw, book_map):
        nonlocal loader_calls
        loader_calls += 1
        active = source_dir / 'generations' / 'GEN.json' / book_checksum / 'GEN.json'
        active.write_bytes(b'{"hostile":true}')
        return real_loader(raw, book_map)

    monkeypatch.setattr(cli, 'load_helloao_bundle_bytes', swapping_loader)
    rows, _checksum = cli._load_stage_input(
        'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
    )
    assert loader_calls == 1
    assert rows[0].body == 'An introduction to Genesis.'


def test_stage_rejects_self_authored_sidecar_without_reviewed_digest(tmp_path):
    from dataclasses import replace
    from hashlib import sha256
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    fixture = Path(__file__).parents[1] / 'fixtures' / 'helloao-genesis-1.json'
    raw = fixture.read_bytes()
    digest = sha256(raw).hexdigest()
    generation = source_dir / 'generations' / 'GEN.json' / digest
    generation.mkdir(parents=True)
    (generation / 'GEN.json').write_bytes(raw)
    (generation / 'GEN.json.sha256').write_text(f'{digest}  GEN.json\n', encoding='ascii')
    (source_dir / 'GEN.json.current.json').write_text(json.dumps({
        'schema_version': 1, 'source_id': 'matthew-henry', 'artifact': 'GEN.json',
        'url': 'https://bible.helloao.org/api/c/matthew-henry/GEN.json',
        'sha256': digest, 'generation': f'generations/GEN.json/{digest}',
    }), encoding='utf-8')
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=1,
        expected_source_books=('GEN',), source_checksum='a' * 64,
    )
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1, 'sources': {'matthew-henry': {'artifacts': {
            'GEN.json': {
                'url': 'https://bible.helloao.org/api/c/matthew-henry/GEN.json',
                'sha256': 'b' * 64,
            },
            'books.json': {
                'url': 'https://bible.helloao.org/api/c/matthew-henry/books.json',
                'sha256': 'a' * 64,
            },
        }}},
    }), encoding='utf-8')

    with pytest.raises(ValueError, match='reviewed digest'):
        cli._load_stage_input(
            'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
        )


def test_production_review_manifest_blocks_unreviewed_book_staging():
    from app.commentary.ingest import cli

    with pytest.raises(ValueError, match='incomplete'):
        cli._reviewed_source_artifacts(
            'matthew-henry', cli._registry()['matthew-henry'],
            cli._REVIEWED_ARTIFACTS_PATH,
        )


def _run_cli(*arguments: str):
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(BACKEND)
    return subprocess.run(
        [sys.executable, '-m', 'app.commentary.ingest.cli', *arguments],
        cwd=BACKEND, env=environment, text=True, capture_output=True, check=False,
    )


@pytest.mark.parametrize(('arguments', 'command', 'code', 'exit_code'), [
    (('publish', '--run-id', 'not-a-uuid', '--confirm'), 'publish', 'invalid_command', 2),
    (('acquire', '--source', 'matthew-henry'), 'acquire', 'invalid_command', 2),
    (('acquire', '--unknown-option'), 'acquire', 'invalid_command', 2),
    (('not-a-command',), 'not-a-command', 'invalid_command', 2),
    ((), 'commentary', 'invalid_command', 2),
    (
        ('publish', '--run-id', '00000000-0000-0000-0000-000000000000'),
        'publish', 'confirmation_required', 1,
    ),
])
def test_real_module_failures_emit_one_json_without_traceback(
    arguments, command, code, exit_code,
):
    result = _run_cli(*arguments)

    assert result.returncode == exit_code
    assert result.stderr == ''
    assert result.stdout.endswith('\n')
    assert result.stdout.count('\n') == 1
    document = json.loads(result.stdout)
    assert document['command'] == command
    assert document['status'] == 'error'
    assert document['error']['code'] == code


def test_real_module_success_emits_one_json_without_stderr(tmp_path):
    from app.commentary.models import CommentaryImportRun, CommentarySource
    from app.config import Settings
    from app.database import Base, create_database_engine, create_session_factory
    from app.library.seed import seed_ethiopian_canon

    database = tmp_path / 'commentary-cli.sqlite'
    database_url = f'sqlite:///{database}'
    engine = create_database_engine(Settings(environment='test', database_url=database_url))
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        seed_ethiopian_canon(session)
        source = CommentarySource(
            id='test-source', title='Test', abbreviation='T', author='Test',
            publication_period='2026', tradition='Test', language='eng',
            license_spdx='CC0-1.0', license_url='https://example.test/license',
            attribution='Test', provenance_url='https://example.test/source',
        )
        session.add(source)
        session.flush()
        run = CommentaryImportRun(
            source_id=source.id, source_checksum='a' * 64,
            metadata_snapshot={}, status='staged', staged_count=0,
        )
        session.add(run)
        session.commit()
        run_id = run.id
    engine.dispose()

    output = tmp_path / 'report.json'
    result = _run_cli(
        'report', '--run-id', str(run_id), '--output', str(output),
        '--database-url', database_url,
    )

    assert result.returncode == 0
    assert result.stderr == ''
    assert result.stdout.count('\n') == 1
    assert json.loads(result.stdout)['status'] == 'reported'
    assert json.loads(output.read_text(encoding='utf-8'))['run_id'] == str(run_id)
