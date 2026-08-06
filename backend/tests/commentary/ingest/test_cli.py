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


def _catalog_document():
    return {
        'commentary': {
            'id': 'matthew-henry', 'name': 'Matthew Henry Bible Commentary',
            'website': 'https://en.wikipedia.org/wiki/Matthew_Henry',
            'licenseUrl': 'https://creativecommons.org/publicdomain/mark/1.0/',
            'licenseNotes': None, 'licenseNotice': None,
            'englishName': 'Matthew Henry Bible Commentary', 'language': 'eng',
            'textDirection': 'ltr', 'sha256': 'a' * 64, 'availableFormats': ['json'],
            'listOfBooksApiLink': '/api/c/matthew-henry/books.json',
            'listOfProfilesApiLink': '/api/c/matthew-henry/profiles.json',
            'numberOfBooks': 1, 'totalNumberOfChapters': 1,
            'totalNumberOfVerses': 2, 'totalNumberOfProfiles': 0,
            'languageName': 'English', 'languageEnglishName': 'English',
        },
        'books': [{
            'id': 'GEN', 'commentaryId': 'matthew-henry', 'name': 'Genesis',
            'commonName': 'Genesis', 'introduction': 'Book introduction.', 'order': 1,
            'numberOfChapters': 1, 'firstChapterNumber': 1,
            'firstChapterApiLink': '/api/c/matthew-henry/GEN/1.json',
            'firstChapterReference': {
                'commentaryId': 'matthew-henry', 'book': 'GEN', 'chapter': 1,
            },
            'lastChapterNumber': 1,
            'lastChapterApiLink': '/api/c/matthew-henry/GEN/1.json',
            'lastChapterReference': {
                'commentaryId': 'matthew-henry', 'book': 'GEN', 'chapter': 1,
            },
            'sha256': 'b' * 64,
            'totalNumberOfVerses': 2,
        }],
    }


def _chapter_document():
    catalog = _catalog_document()
    return {
        'commentary': catalog['commentary'], 'book': catalog['books'][0],
        'thisChapterLink': '/api/c/matthew-henry/GEN/1.json',
        'thisChapterReference': {
            'commentaryId': 'matthew-henry', 'book': 'GEN', 'chapter': 1,
        },
        'nextChapterApiLink': None, 'previousChapterApiLink': None,
        'nextChapterReference': None, 'previousChapterReference': None,
        'numberOfVerses': 2,
        'chapter': {'number': 1, 'introduction': 'Chapter introduction.', 'content': [
            {'type': 'verse', 'number': 1, 'content': ['One.']},
            {'type': 'verse', 'number': '2-3', 'content': ['Two through three.']},
        ]},
    }


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _write_generation(source_dir, filename, raw, url):
    from hashlib import sha256

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
    return digest


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


def test_report_exposes_reviewed_exclusion_audit_metadata(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.cli import _build_report
    from app.commentary.models import CommentaryImportRun

    exclusion = _exclusion_record('EZK-40.json', 'a' * 64, 4)
    run = CommentaryImportRun(
        source_id=commentary_source.id, source_checksum='a' * 64,
        metadata_snapshot={
            'coverage': {'entries': 10}, 'reviewed_exclusion_count': 1,
            'reviewed_exclusions': [exclusion],
        },
        status='verified', staged_count=10,
    )
    commentary_session.add(run)
    commentary_session.flush()

    report = _build_report(commentary_session, run.id)

    assert report['reviewed_exclusion_count'] == 1
    assert report['reviewed_exclusions'] == [exclusion]


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


def test_report_ancestor_swap_during_nofollow_walk_cannot_redirect_output(tmp_path):
    from app.commentary.ingest.cli import _atomic_json

    safe = tmp_path / 'safe'
    (safe / 'reports').mkdir(parents=True)
    attacker = tmp_path / 'attacker'
    (attacker / 'reports').mkdir(parents=True)

    def swap(component):
        if component == 'safe':
            safe.rename(tmp_path / 'original-safe')
            safe.symlink_to(attacker, target_is_directory=True)

    with pytest.raises(ValueError, match='changed during report creation'):
        _atomic_json(
            safe / 'reports' / 'report.json', {'status': 'verified'},
            _during_directory_open=swap,
        )

    assert not (attacker / 'reports' / 'report.json').exists()
    assert not (tmp_path / 'original-safe' / 'reports' / 'report.json').exists()


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
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    trusted = _json_bytes(_chapter_document())
    catalog = _json_bytes(_catalog_document())
    chapter_url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    catalog_url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    chapter_checksum = _write_generation(source_dir, 'GEN-1.json', trusted, chapter_url)
    catalog_checksum = _write_generation(source_dir, 'books.json', catalog, catalog_url)
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1,
        'sources': {'matthew-henry': {'artifacts': {
            'GEN-1.json': {'url': chapter_url, 'sha256': chapter_checksum},
            'books.json': {'url': catalog_url, 'sha256': catalog_checksum},
        }}},
    }), encoding='utf-8')
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=1,
        expected_source_books=('GEN',), provider_dataset_checksum='a' * 64,
    )
    real_loader = cli.load_helloao_chapter_bytes
    loader_calls = 0

    def swapping_loader(
        raw, source_id, book, expected_chapter, *, excluded_content_indices=frozenset(),
    ):
        nonlocal loader_calls
        loader_calls += 1
        active = (
            source_dir / 'generations' / 'GEN-1.json' / chapter_checksum / 'GEN-1.json'
        )
        active.write_bytes(b'{"hostile":true}')
        return real_loader(
            raw, source_id, book, expected_chapter,
            excluded_content_indices=excluded_content_indices,
        )

    monkeypatch.setattr(cli, 'load_helloao_chapter_bytes', swapping_loader)
    audit_evidence = {}
    rows, _checksum = cli._load_stage_input(
        'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
        audit_evidence=audit_evidence,
    )
    assert loader_calls == 1
    assert rows[0].body == 'Book introduction.'
    assert [row.position for row in rows] == [0, 1, 2, 3]
    assert audit_evidence == {
        'provider_book_count': 1,
        'provider_chapter_count': 1,
        'provider_content_record_count': 2,
        'acquired_normalized_entry_count': 4,
        'normalized_entry_type_counts': {
            'book_intro': 1, 'chapter_intro': 1, 'verse': 1, 'verse_range': 1,
        },
        'reviewed_exclusion_count': 0,
        'covered_normalized_chapter_count': 1,
        'empty_provider_chapters': [],
    }


def test_stage_retains_zero_chapter_book_intro_without_requiring_chapter_artifact(tmp_path):
    from dataclasses import replace
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    catalog = _catalog_document()
    catalog['commentary']['numberOfBooks'] = 2
    catalog['books'].append({
        'id': 'SNG', 'commentaryId': 'matthew-henry',
        'name': 'Song of Songs', 'commonName': 'Song of Songs',
        'introduction': 'Song introduction.', 'order': 2,
        'numberOfChapters': 0, 'firstChapterNumber': None,
        'firstChapterApiLink': None, 'firstChapterReference': None,
        'lastChapterNumber': None, 'lastChapterApiLink': None,
        'lastChapterReference': None, 'sha256': 'c' * 64,
        'totalNumberOfVerses': 0,
    })
    catalog_raw = _json_bytes(catalog)
    chapter = _chapter_document()
    chapter['commentary'] = catalog['commentary']
    chapter['book'] = catalog['books'][0]
    chapter_raw = _json_bytes(chapter)
    catalog_url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    chapter_url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    catalog_checksum = _write_generation(source_dir, 'books.json', catalog_raw, catalog_url)
    chapter_checksum = _write_generation(source_dir, 'GEN-1.json', chapter_raw, chapter_url)
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1, 'sources': {'matthew-henry': {'artifacts': {
            'books.json': {'url': catalog_url, 'sha256': catalog_checksum},
            'GEN-1.json': {'url': chapter_url, 'sha256': chapter_checksum},
        }}},
    }), encoding='utf-8')
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=2,
        expected_source_books=('GEN', 'SNG'), provider_dataset_checksum='a' * 64,
    )

    rows, _checksum = cli._load_stage_input(
        'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
    )

    assert [row.work_id for row in rows if row.entry_type == 'book_intro'] == [
        'genesis', 'song-of-solomon',
    ]
    assert rows[-1].body == 'Song introduction.'


def test_stage_rejects_chapter_artifact_for_zero_chapter_book(tmp_path):
    from dataclasses import replace
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    catalog = _catalog_document()
    catalog['commentary']['numberOfBooks'] = 2
    catalog['books'].append({
        'id': 'SNG', 'commentaryId': 'matthew-henry',
        'name': 'Song of Songs', 'commonName': 'Song of Songs',
        'introduction': 'Song introduction.', 'order': 2,
        'numberOfChapters': 0, 'firstChapterNumber': None,
        'firstChapterApiLink': None, 'firstChapterReference': None,
        'lastChapterNumber': None, 'lastChapterApiLink': None,
        'lastChapterReference': None, 'sha256': 'c' * 64,
        'totalNumberOfVerses': 0,
    })
    catalog_url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    genesis_url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    song_url = 'https://bible.helloao.org/api/c/matthew-henry/SNG/1.json'
    checksums = {
        'books.json': _write_generation(
            source_dir, 'books.json', _json_bytes(catalog), catalog_url,
        ),
        'GEN-1.json': _write_generation(
            source_dir, 'GEN-1.json', _json_bytes({
                **_chapter_document(), 'commentary': catalog['commentary'],
                'book': catalog['books'][0],
            }), genesis_url,
        ),
        'SNG-1.json': _write_generation(
            source_dir, 'SNG-1.json', b'{}', song_url,
        ),
    }
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1, 'sources': {'matthew-henry': {'artifacts': {
            name: {'url': url, 'sha256': checksums[name]}
            for name, url in {
                'books.json': catalog_url, 'GEN-1.json': genesis_url,
                'SNG-1.json': song_url,
            }.items()
        }}},
    }), encoding='utf-8')
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=2,
        expected_source_books=('GEN', 'SNG'), provider_dataset_checksum='a' * 64,
    )

    with pytest.raises(ValueError, match='zero-chapter'):
        cli._load_stage_input(
            'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
        )


def test_stage_rejects_self_authored_sidecar_without_reviewed_digest(tmp_path):
    from dataclasses import replace
    from hashlib import sha256
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    raw = _json_bytes(_chapter_document())
    digest = sha256(raw).hexdigest()
    generation = source_dir / 'generations' / 'GEN-1.json' / digest
    generation.mkdir(parents=True)
    (generation / 'GEN-1.json').write_bytes(raw)
    (generation / 'GEN-1.json.sha256').write_text(
        f'{digest}  GEN-1.json\n', encoding='ascii',
    )
    chapter_url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    (source_dir / 'GEN-1.json.current.json').write_text(json.dumps({
        'schema_version': 1, 'source_id': 'matthew-henry', 'artifact': 'GEN-1.json',
        'url': chapter_url, 'sha256': digest,
        'generation': f'generations/GEN-1.json/{digest}',
    }), encoding='utf-8')
    catalog_url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    catalog = _json_bytes(_catalog_document())
    catalog_digest = _write_generation(source_dir, 'books.json', catalog, catalog_url)
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=1,
        expected_source_books=('GEN',), provider_dataset_checksum='a' * 64,
    )
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1, 'sources': {'matthew-henry': {'artifacts': {
            'GEN-1.json': {
                'url': chapter_url,
                'sha256': 'b' * 64,
            },
            'books.json': {
                'url': catalog_url, 'sha256': catalog_digest,
            },
        }}},
    }), encoding='utf-8')

    with pytest.raises(ValueError, match='reviewed digest'):
        cli._load_stage_input(
            'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
        )


def _reviewed_exclusions(path, records):
    path.write_text(json.dumps({
        'schema_version': 1, 'exclusions': records,
    }), encoding='utf-8')
    return path


def _exclusion_record(artifact, digest, index):
    return {
        'source_id': 'matthew-henry', 'artifact': artifact,
        'artifact_sha256': digest, 'content_index': index,
        'reason': 'Verified misfiled land-division note; not commentary on this chapter.',
        'reviewer': 'Test reviewer', 'reviewed_on': '2026-08-04',
    }


def test_stage_applies_exact_checksum_reviewed_exclusion_and_records_audit_metadata(tmp_path):
    from dataclasses import replace
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    catalog = _catalog_document()
    catalog['commentary']['totalNumberOfVerses'] = 3
    catalog['books'][0]['totalNumberOfVerses'] = 3
    chapter = _chapter_document()
    chapter['commentary'] = catalog['commentary']
    chapter['book'] = catalog['books'][0]
    chapter['numberOfVerses'] = 3
    chapter['chapter']['content'].append({
        'type': 'verse', 'number': 48, 'content': ['Misfiled land-division note.'],
    })
    catalog_url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    chapter_url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    catalog_digest = _write_generation(
        source_dir, 'books.json', _json_bytes(catalog), catalog_url,
    )
    chapter_digest = _write_generation(
        source_dir, 'GEN-1.json', _json_bytes(chapter), chapter_url,
    )
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1, 'sources': {'matthew-henry': {'artifacts': {
            'books.json': {'url': catalog_url, 'sha256': catalog_digest},
            'GEN-1.json': {'url': chapter_url, 'sha256': chapter_digest},
        }}},
    }), encoding='utf-8')
    exclusions = _reviewed_exclusions(
        tmp_path / 'exclusions.json',
        [_exclusion_record('GEN-1.json', chapter_digest, 2)],
    )
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=1,
        expected_source_books=('GEN',), provider_dataset_checksum='a' * 64,
    )
    applied = []

    rows, _ = cli._load_stage_input(
        'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
        reviewed_exclusions_path=exclusions, applied_exclusions=applied,
    )

    assert 'Misfiled land-division note.' not in {row.body for row in rows}
    assert [row.position for row in rows] == list(range(len(rows)))
    assert applied == [_exclusion_record('GEN-1.json', chapter_digest, 2)]


@pytest.mark.parametrize(('change', 'message'), [
    (lambda record: record.update(artifact_sha256='f' * 64), 'digest'),
    (lambda record: record.update(artifact='EXO-1.json'), 'artifact'),
    (lambda record: record.update(content_index=99), 'exclusion'),
    (lambda record: record.update(source_id='unknown-source'), 'source'),
])
def test_stage_rejects_stale_unknown_or_out_of_range_reviewed_exclusion(
    tmp_path, change, message,
):
    from dataclasses import replace
    from app.commentary.ingest import cli

    source_dir = tmp_path / 'matthew-henry'
    source_dir.mkdir()
    catalog_raw = _json_bytes(_catalog_document())
    chapter_raw = _json_bytes(_chapter_document())
    catalog_url = 'https://bible.helloao.org/api/c/matthew-henry/books.json'
    chapter_url = 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json'
    catalog_digest = _write_generation(source_dir, 'books.json', catalog_raw, catalog_url)
    chapter_digest = _write_generation(source_dir, 'GEN-1.json', chapter_raw, chapter_url)
    reviewed = tmp_path / 'reviewed.json'
    reviewed.write_text(json.dumps({
        'schema_version': 1, 'sources': {'matthew-henry': {'artifacts': {
            'books.json': {'url': catalog_url, 'sha256': catalog_digest},
            'GEN-1.json': {'url': chapter_url, 'sha256': chapter_digest},
        }}},
    }), encoding='utf-8')
    record = _exclusion_record('GEN-1.json', chapter_digest, 1)
    change(record)
    exclusions = _reviewed_exclusions(tmp_path / 'exclusions.json', [record])
    metadata = replace(
        cli._registry()['matthew-henry'], expected_book_count=1,
        expected_source_books=('GEN',), provider_dataset_checksum='a' * 64,
    )

    with pytest.raises(ValueError, match=message):
        cli._load_stage_input(
            'matthew-henry', source_dir, metadata, reviewed_manifest_path=reviewed,
            reviewed_exclusions_path=exclusions,
        )


def test_reviewed_exclusions_reject_duplicate_records_and_tampered_schema(tmp_path):
    from app.commentary.ingest import cli

    reviewed = {'GEN-1.json': {
        'url': 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json',
        'sha256': 'a' * 64,
    }}
    record = _exclusion_record('GEN-1.json', 'a' * 64, 1)
    duplicate = _reviewed_exclusions(tmp_path / 'duplicate.json', [record, record])
    with pytest.raises(ValueError, match='duplicate'):
        cli._reviewed_source_exclusions('matthew-henry', duplicate, reviewed)

    tampered = tmp_path / 'tampered.json'
    tampered.write_text(
        '{"schema_version":1,"schema_version":1,"exclusions":[]}', encoding='utf-8',
    )
    with pytest.raises(ValueError, match='valid JSON'):
        cli._reviewed_source_exclusions('matthew-henry', tampered, reviewed)


@pytest.mark.parametrize('unsafe_reason', [
    '<em>reviewed</em>', 'reviewed\ud800', ' reviewed ', 'line\nbreak',
])
def test_reviewed_exclusions_reject_unsafe_or_noncanonical_review_text(
    tmp_path, unsafe_reason,
):
    from app.commentary.ingest import cli

    reviewed = {'GEN-1.json': {
        'url': 'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json',
        'sha256': 'a' * 64,
    }}
    record = _exclusion_record('GEN-1.json', 'a' * 64, 1)
    record['reason'] = unsafe_reason
    path = _reviewed_exclusions(tmp_path / 'unsafe.json', [record])

    with pytest.raises(ValueError, match='reason'):
        cli._reviewed_source_exclusions('matthew-henry', path, reviewed)


def test_metadata_snapshot_records_reviewed_exclusions_and_count():
    from app.commentary.ingest import cli

    exclusion = _exclusion_record('EZK-40.json', 'a' * 64, 4)
    snapshot = cli._metadata_snapshot(
        cli._registry()['matthew-henry'], reviewed_exclusions=[exclusion],
    )

    assert snapshot['reviewed_exclusion_count'] == 1
    assert snapshot['reviewed_exclusions'] == [exclusion]


def test_production_review_manifest_has_complete_reviewed_chapter_set():
    from app.commentary.ingest import cli

    artifacts = cli._reviewed_source_artifacts(
        'matthew-henry', cli._registry()['matthew-henry'],
        cli._REVIEWED_ARTIFACTS_PATH,
    )

    assert 'books.json' in artifacts
    assert 'EZK-40.json' in artifacts
    assert len(artifacts) > 1_000


def test_production_exclusion_is_exactly_checksum_bound_to_misfiled_ezekiel_record():
    from app.commentary.ingest import cli

    artifacts = cli._reviewed_source_artifacts(
        'matthew-henry', cli._registry()['matthew-henry'],
        cli._REVIEWED_ARTIFACTS_PATH,
    )
    exclusions = cli._reviewed_source_exclusions(
        'matthew-henry', cli._REVIEWED_EXCLUSIONS_PATH, artifacts,
    )

    assert exclusions == ({
        'source_id': 'matthew-henry', 'artifact': 'EZK-40.json',
        'artifact_sha256': '1906ea01374f9db6edb02fc15f22ebe5a313a11c989165cd84933c270493616f',
        'content_index': 4,
        'reason': 'Verified misfiled land-division commentary belonging to Ezekiel 48; not commentary on Ezekiel 40.',
        'reviewer': 'Codex-assisted review', 'reviewed_on': '2026-08-05',
    },)


def _run_cli(*arguments: str):
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(BACKEND)
    return subprocess.run(
        [sys.executable, '-m', 'app.commentary.ingest.cli', *arguments],
        cwd=BACKEND, env=environment, text=True, capture_output=True, check=False,
    )


def test_standalone_stage_registers_library_metadata_before_flushing(tmp_path):
    from app.commentary import models as commentary_models  # noqa: F401
    from app.config import Settings
    from app.database import Base, create_database_engine, create_session_factory
    from app.library.seed import seed_ethiopian_canon

    database = tmp_path / 'standalone-stage.sqlite'
    database_url = f'sqlite:///{database}'
    engine = create_database_engine(Settings(environment='test', database_url=database_url))
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        seed_ethiopian_canon(session)
        session.commit()
    engine.dispose()

    # Run stage in a fresh interpreter, as the administrator command is run in production.
    # Only the bundle loader is replaced so this small regression does not need the full
    # reviewed multi-gigabyte source bundle; database/session/staging behavior stays real.
    script = """
import os

from app.commentary.ingest import cli
from app.commentary.ingest.types import NormalizedCommentaryEntry

cli._load_stage_input = lambda *_args, **_kwargs: ([
    NormalizedCommentaryEntry(
        'genesis', 1, 1, 1, 'verse', None, 'In the beginning.',
        'https://bible.helloao.org/api/c/matthew-henry/GEN/1.json', 0,
    )
], 'a' * 64)
cli.app(args=[
    'stage', '--source', 'matthew-henry', '--input', '.',
    '--database-url', os.environ['DATABASE_URL_FOR_TEST'],
])
"""
    environment = os.environ.copy()
    environment['PYTHONPATH'] = str(BACKEND)
    environment['DATABASE_URL_FOR_TEST'] = database_url
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=BACKEND, env=environment,
        text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ''
    document = json.loads(result.stdout)
    assert document['status'] == 'staged'
    assert document['staged_count'] == 1


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
