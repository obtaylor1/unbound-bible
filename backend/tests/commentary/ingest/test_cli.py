from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from typer.testing import CliRunner


runner = CliRunner()


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

    monkeypatch.setattr(cli, 'acquire_source_bundle', lambda source, output: (Artifact(),))
    result = runner.invoke(cli.app, [
        'acquire', '--source', 'matthew-henry', '--output', str(tmp_path),
    ])
    assert result.exit_code == 0
    assert payload(result) == {
        'artifacts': 1, 'bytes': 2, 'command': 'acquire',
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


def test_stage_artifact_verification_rejects_oversized_files_before_reading(tmp_path):
    from app.commentary.ingest.cli import _verify_artifact

    artifact = tmp_path / 'GEN.json'
    artifact.write_bytes(b'x' * (5 * 1024 * 1024 + 1))
    (tmp_path / 'GEN.json.sha256').write_text('untrusted\n', encoding='ascii')

    with pytest.raises(ValueError, match='5 MiB'):
        _verify_artifact(artifact)


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
    book = source_dir / 'GEN.json'
    book.write_bytes(trusted)
    book_checksum = sha256(trusted).hexdigest()
    (source_dir / 'GEN.json.sha256').write_text(
        f'{book_checksum}  GEN.json\n', encoding='ascii',
    )
    catalog = b'{}'
    catalog_checksum = sha256(catalog).hexdigest()
    (source_dir / 'books.json').write_bytes(catalog)
    (source_dir / 'books.json.sha256').write_text(
        f'{catalog_checksum}  books.json\n', encoding='ascii',
    )
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=1,
        expected_source_books=('GEN',), source_checksum=catalog_checksum,
    )
    real_loader = cli.load_helloao_bundle_bytes
    loader_calls = 0

    def swapping_loader(raw, book_map):
        nonlocal loader_calls
        loader_calls += 1
        book.write_bytes(b'{"hostile":true}')
        return real_loader(raw, book_map)

    monkeypatch.setattr(cli, 'load_helloao_bundle_bytes', swapping_loader)
    rows, _checksum = cli._load_stage_input('matthew-henry', source_dir, metadata)
    assert loader_calls == 1
    assert rows[0].body == 'An introduction to Genesis.'
