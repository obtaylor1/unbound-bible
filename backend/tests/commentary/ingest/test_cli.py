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
