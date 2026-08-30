import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner


runner = CliRunner()
DATA_DIR = Path(__file__).parents[3] / 'data/scripture/eotc-composite-en/verification'


def _paths(tmp_path, content=b'scripture'):
    registry = json.loads((DATA_DIR / 'source-registry.json').read_text(encoding='utf-8'))
    registry['families'] = {
        'world-messianic-bible': registry['families']['world-messianic-bible']
    }
    # Registry loading deliberately requires the exact four families, so retain all
    # definitions while only materializing the selected artifact.
    registry_path = tmp_path / 'registry.json'
    registry_path.write_text(json.dumps(json.loads((DATA_DIR / 'source-registry.json').read_text())), encoding='utf-8')
    lock_path = tmp_path / 'lock.json'
    lock_path.write_text('{"artifacts":{},"version":1}\n', encoding='utf-8')
    root = tmp_path / 'artifacts'
    root.mkdir()
    artifact = root / 'engwmb_vpl.zip'
    artifact.write_bytes(content)
    return registry_path, lock_path, root, artifact


def _lock_args(registry, lock, root, artifact, *, source_url=None):
    return [
        'lock-artifact', 'world-messianic-bible',
        '--registry', str(registry), '--lock', str(lock),
        '--artifact-root', str(root), '--file', str(artifact),
        '--source-url', source_url or 'https://ebible.org/Scriptures/engwmb_vpl.zip',
        '--retrieved-at', '2026-08-17T12:00:00Z',
    ]


def _report_payload(work_id, source_sha256, *, classification=None):
    differences = []
    totals = {'exact': 1, 'formatting': 0, 'missing': 0, 'extra': 0, 'wording': 0}
    if classification is not None:
        totals['exact'] = 0
        totals[classification] = 1
        current_text = None if classification == 'missing' else 'Current text'
        source_text = None if classification == 'extra' else 'Source text'
        differences.append({
            'chapter': 1, 'verse': 1, 'classification': classification,
            'current_text': current_text, 'source_text': source_text,
        })
    return {
        'schema_version': 1,
        'work_id': work_id,
        'source_artifact_sha256': source_sha256,
        'current_publication_sha256': 'b' * 64,
        'parser_version': 'synthetic/1',
        'rules': {
            'unicode_form': 'NFC', 'normalize_line_endings': True,
            'collapse_whitespace': True,
        },
        'totals': totals,
        'declared_omissions': [],
        'differences': differences,
        'is_verified_candidate': classification not in {'missing', 'extra', 'wording'},
    }


def _write_family_reports(registry, report_dir, source_sha256, *, wording_work=None):
    work_ids = json.loads(registry.read_text(encoding='utf-8'))['families'][
        'world-messianic-bible'
    ]['expected_work_ids']
    for work_id in work_ids:
        payload = _report_payload(
            work_id,
            source_sha256,
            classification='wording' if work_id == wording_work else None,
        )
        (report_dir / f'{work_id}.json').write_text(
            json.dumps(payload), encoding='utf-8',
        )
    return work_ids


def test_help_lists_local_only_commands():
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        GutenbergKjvApocryphaAdapter,
    )
    from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter
    from app.library.verification.adapters.wmb_vpl import WmbVplAdapter
    from app.library.verification.adapters.charles_jubilees import CharlesJubileesAdapter
    from app.library.verification.cli import ADAPTERS, app

    assert set(ADAPTERS) == {
        'wmb_vpl', 'murdock_sword', 'gutenberg_kjv_apocrypha',
        'charles_jubilees',
    }
    assert type(ADAPTERS['wmb_vpl']) is WmbVplAdapter
    assert type(ADAPTERS['murdock_sword']) is MurdockSwordAdapter
    assert type(ADAPTERS['gutenberg_kjv_apocrypha']) is GutenbergKjvApocryphaAdapter
    assert type(ADAPTERS['charles_jubilees']) is CharlesJubileesAdapter
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert all(name in result.output for name in ('lock-artifact', 'compare-family', 'build-candidate'))


def test_lock_artifact_is_deterministic_and_idempotent(tmp_path):
    from app.library.verification.cli import app

    registry, lock, root, artifact = _paths(tmp_path)
    first = runner.invoke(app, _lock_args(registry, lock, root, artifact))
    assert first.exit_code == 0, first.output
    first_bytes = lock.read_bytes()
    second = runner.invoke(app, _lock_args(registry, lock, root, artifact))
    assert second.exit_code == 0, second.output
    assert lock.read_bytes() == first_bytes
    payload = json.loads(first.stdout)
    assert payload['family_id'] == 'world-messianic-bible'
    assert payload['sha256'] == hashlib.sha256(b'scripture').hexdigest()
    assert str(tmp_path) not in first.stdout


def test_lock_artifact_never_downloads_and_rejects_bad_file_location(tmp_path, monkeypatch):
    from app.library.verification import cli

    registry, lock, root, artifact = _paths(tmp_path)
    outside = tmp_path / 'engwmb_vpl.zip'
    outside.write_bytes(b'scripture')
    result = runner.invoke(cli.app, _lock_args(registry, lock, root, outside))
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload['status'] == 'error'
    assert str(tmp_path) not in result.stdout


def test_lock_artifact_requires_replace_and_exact_confirmation(tmp_path):
    from app.library.verification.cli import app

    registry, lock, root, artifact = _paths(tmp_path)
    assert runner.invoke(app, _lock_args(registry, lock, root, artifact)).exit_code == 0
    artifact.write_bytes(b'changed')
    base = _lock_args(registry, lock, root, artifact)
    assert runner.invoke(app, base).exit_code != 0
    assert runner.invoke(app, base + ['--replace', '--confirm-family', 'wrong']).exit_code != 0
    replaced = runner.invoke(app, base + [
        '--replace', '--confirm-family', 'world-messianic-bible'
    ])
    assert replaced.exit_code == 0, replaced.output


def test_lock_artifact_cli_rejects_non_utc_retrieval_time(tmp_path):
    from app.library.verification.cli import app

    registry, lock, root, artifact = _paths(tmp_path)
    args = _lock_args(registry, lock, root, artifact)
    args[args.index('--retrieved-at') + 1] = '2026-08-17T12:00:00-04:00'
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert json.loads(result.stdout)['status'] == 'error'
    assert lock.read_text(encoding='utf-8') == '{"artifacts":{},"version":1}\n'


def test_atomic_update_failure_preserves_previous_lock(tmp_path, monkeypatch):
    from app.library.verification import registry as module
    from app.library.verification.cli import lock_artifact_service

    registry, lock, root, artifact = _paths(tmp_path)
    before = lock.read_bytes()
    monkeypatch.setattr(module.os, 'replace', lambda *_: (_ for _ in ()).throw(OSError('fail')))
    with pytest.raises(OSError):
        lock_artifact_service(
            family_id='world-messianic-bible', registry_path=registry,
            lock_path=lock, artifact_root=root, file=artifact,
            source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
            retrieved_at='2026-08-17T12:00:00Z',
        )
    assert lock.read_bytes() == before


def test_compare_refuses_missing_lock_and_missing_adapter(tmp_path):
    from app.library.verification.cli import compare_family_service

    registry, lock, root, artifact = _paths(tmp_path)
    current = tmp_path / 'current.zip'
    current.write_bytes(b'current')
    with pytest.raises(ValueError, match='not locked'):
        compare_family_service(
            family_id='world-messianic-bible', registry_path=registry,
            lock_path=lock, artifact_root=root, current_bundle=current,
            output=tmp_path / 'reports', adapters={},
        )

    from app.library.verification.cli import lock_artifact_service
    lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    with pytest.raises(ValueError, match='adapter wmb_vpl is not installed'):
        compare_family_service(
            family_id='world-messianic-bible', registry_path=registry,
            lock_path=lock, artifact_root=root, current_bundle=current,
            output=tmp_path / 'reports', adapters={},
        )


def test_compare_delegates_only_after_artifact_verification(tmp_path):
    from app.library.verification.cli import (
        CompareFamilyResult,
        compare_family_service,
        lock_artifact_service,
    )

    registry, lock, root, artifact = _paths(tmp_path)
    lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    calls = []

    class Adapter:
        def compare_family(self, **kwargs):
            calls.append(kwargs)
            return CompareFamilyResult(report_count=39, output_id='wmb-reports')

        def build_candidate(self, **kwargs):
            raise AssertionError('not called')

    result = compare_family_service(
        family_id='world-messianic-bible', registry_path=registry,
        lock_path=lock, artifact_root=root, current_bundle=tmp_path / 'current.zip',
        output=tmp_path / 'reports', adapters={'wmb_vpl': Adapter()},
    )
    assert result == CompareFamilyResult(report_count=39, output_id='wmb-reports')
    assert calls[0]['artifact_path'] == artifact


def test_candidate_refuses_unresolved_differences_without_explicit_replacement(tmp_path):
    from app.library.verification.cli import (
        CandidateBuildResult,
        build_candidate_service,
        lock_artifact_service,
    )

    registry, lock, root, artifact = _paths(tmp_path)
    lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    reports = tmp_path / 'reports'
    reports.mkdir()
    source_sha256 = hashlib.sha256(b'scripture').hexdigest()
    _write_family_reports(registry, reports, source_sha256, wording_work='genesis')
    calls = []

    class Adapter:
        def compare_family(self, **kwargs):
            raise AssertionError('not called')

        def build_candidate(self, **kwargs):
            calls.append(kwargs)
            return CandidateBuildResult(work_count=39, output_id='wmb-candidate')

    args = dict(
        family_id='world-messianic-bible', registry_path=registry,
        lock_path=lock, artifact_root=root, report_dir=reports,
        output=tmp_path / 'candidate.zip', adapters={'wmb_vpl': Adapter()},
    )
    with pytest.raises(ValueError, match='--replace-from-source'):
        build_candidate_service(**args)
    assert not calls
    assert build_candidate_service(**args, replace_from_source=True) == CandidateBuildResult(
        work_count=39, output_id='wmb-candidate',
    )
    assert calls[0]['replace_from_source'] is True


def test_candidate_rejects_incomplete_or_stale_report_set(tmp_path):
    from app.library.verification.cli import build_candidate_service, lock_artifact_service

    registry, lock, root, artifact = _paths(tmp_path)
    lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    reports = tmp_path / 'reports'
    reports.mkdir()
    report = reports / 'genesis.json'
    report.write_text(json.dumps(_report_payload(
        'genesis', hashlib.sha256(b'scripture').hexdigest(),
    )), encoding='utf-8')

    class Adapter:
        def build_candidate(self, **kwargs):
            raise AssertionError('incomplete evidence must not delegate')

    args = dict(
        family_id='world-messianic-bible', registry_path=registry,
        lock_path=lock, artifact_root=root, report_dir=reports,
        output=tmp_path / 'candidate.zip', adapters={'wmb_vpl': Adapter()},
        replace_from_source=True,
    )
    with pytest.raises(ValueError, match='complete'):
        build_candidate_service(**args)

    # Complete filenames alone cannot make stale reports valid.
    work_ids = json.loads(registry.read_text())['families'][
        'world-messianic-bible'
    ]['expected_work_ids']
    stale = json.loads(report.read_text())
    stale['source_artifact_sha256'] = '0' * 64
    for work_id in work_ids:
        stale['work_id'] = work_id
        (reports / f'{work_id}.json').write_text(json.dumps(stale), encoding='utf-8')
    with pytest.raises(ValueError, match='locked artifact'):
        build_candidate_service(**args)

    stale['source_artifact_sha256'] = hashlib.sha256(b'scripture').hexdigest()
    stale['schema_version'] = True
    for work_id in work_ids:
        stale['work_id'] = work_id
        (reports / f'{work_id}.json').write_text(json.dumps(stale), encoding='utf-8')
    with pytest.raises(ValueError, match='schema version'):
        build_candidate_service(**args)


@pytest.mark.parametrize('mutation', [
    'extra-field', 'missing-field', 'bad-checksum', 'bad-type',
    'contradictory-totals', 'forged-verified-flag',
])
def test_candidate_strictly_deserializes_reports(tmp_path, mutation):
    from app.library.verification.cli import build_candidate_service, lock_artifact_service

    registry, lock, root, artifact = _paths(tmp_path)
    lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    reports = tmp_path / 'reports'
    reports.mkdir()
    checksum = hashlib.sha256(b'scripture').hexdigest()
    _write_family_reports(registry, reports, checksum)
    path = reports / 'genesis.json'
    payload = json.loads(path.read_text())
    if mutation == 'extra-field':
        payload['surprise'] = 'ignored before hardening'
    elif mutation == 'missing-field':
        del payload['parser_version']
    elif mutation == 'bad-checksum':
        payload['current_publication_sha256'] = 'not-a-checksum'
    elif mutation == 'bad-type':
        payload['rules']['collapse_whitespace'] = 1
    elif mutation == 'contradictory-totals':
        payload['totals']['wording'] = 0
        payload['differences'] = [{
            'chapter': 1, 'verse': 1, 'classification': 'wording',
            'current_text': 'Current', 'source_text': 'Source',
        }]
    else:
        payload['is_verified_candidate'] = False
    path.write_text(json.dumps(payload), encoding='utf-8')

    class Adapter:
        def build_candidate(self, **kwargs):
            raise AssertionError('malformed report must not delegate')

    with pytest.raises(ValueError):
        build_candidate_service(
            family_id='world-messianic-bible', registry_path=registry,
            lock_path=lock, artifact_root=root, report_dir=reports,
            output=tmp_path / 'candidate.zip', adapters={'wmb_vpl': Adapter()},
            replace_from_source=True,
        )


def test_candidate_cannot_hide_wording_difference_with_zeroed_total(tmp_path):
    from app.library.verification.cli import build_candidate_service, lock_artifact_service

    registry, lock, root, artifact = _paths(tmp_path)
    lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    reports = tmp_path / 'reports'
    reports.mkdir()
    _write_family_reports(registry, reports, hashlib.sha256(b'scripture').hexdigest())
    path = reports / 'genesis.json'
    payload = json.loads(path.read_text())
    payload['differences'] = [{
        'chapter': 1, 'verse': 1, 'classification': 'wording',
        'current_text': 'Current', 'source_text': 'Source',
    }]
    payload['is_verified_candidate'] = False
    path.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(ValueError, match='totals|differences'):
        build_candidate_service(
            family_id='world-messianic-bible', registry_path=registry,
            lock_path=lock, artifact_root=root, report_dir=reports,
            output=tmp_path / 'candidate.zip', adapters={'wmb_vpl': object()},
        )


@pytest.mark.parametrize('mutation', ['duplicate-work', 'wrong-work'])
def test_candidate_rejects_duplicate_and_wrong_family_reports(tmp_path, mutation):
    from app.library.verification.cli import build_candidate_service, lock_artifact_service

    registry, lock, root, artifact = _paths(tmp_path)
    lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    reports = tmp_path / 'reports'
    reports.mkdir()
    _write_family_reports(registry, reports, hashlib.sha256(b'scripture').hexdigest())
    genesis = json.loads((reports / 'genesis.json').read_text())
    if mutation == 'duplicate-work':
        (reports / 'duplicate.json').write_text(json.dumps(genesis), encoding='utf-8')
    else:
        genesis['work_id'] = 'made-up-work'
        (reports / 'genesis.json').write_text(json.dumps(genesis), encoding='utf-8')

    with pytest.raises(ValueError, match='duplicate|expected family work'):
        build_candidate_service(
            family_id='world-messianic-bible', registry_path=registry,
            lock_path=lock, artifact_root=root, report_dir=reports,
            output=tmp_path / 'candidate.zip', adapters={'wmb_vpl': object()},
            replace_from_source=True,
        )


def test_candidate_cli_never_serializes_arbitrary_adapter_result(tmp_path, monkeypatch):
    from app.library.verification import cli

    registry, lock, root, artifact = _paths(tmp_path)
    cli.lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )
    reports = tmp_path / 'reports'
    reports.mkdir()
    _write_family_reports(registry, reports, hashlib.sha256(b'scripture').hexdigest())

    class Adapter:
        def build_candidate(self, **kwargs):
            return {'path': str(tmp_path / 'PRIVATE_CANDIDATE'), 'token': 'CANDIDATE_SECRET'}

    monkeypatch.setattr(cli, 'ADAPTERS', {'wmb_vpl': Adapter()})
    result = runner.invoke(cli.app, [
        'build-candidate', 'world-messianic-bible', '--registry', str(registry),
        '--lock', str(lock), '--artifact-root', str(root),
        '--report-dir', str(reports), '--output', str(tmp_path / 'candidate.zip'),
    ])

    assert result.exit_code != 0
    rendered = result.stdout + result.stderr
    assert str(tmp_path) not in rendered
    assert 'PRIVATE_CANDIDATE' not in rendered
    assert 'CANDIDATE_SECRET' not in rendered


@pytest.mark.parametrize('malicious', [
    {'report_count': 1, 'output_id': '/Users/private/source'},
    {'url': 'https://user:password@example.org/source'},
    {'url': 'https://example.org/source?access_token=SECRET_VALUE'},
    {'nested': {'password': 'NESTED_SECRET_VALUE'}},
    {'message': 'safe\u202eHIDDEN_VALUE'},
])
def test_cli_never_serializes_arbitrary_adapter_results(tmp_path, monkeypatch, malicious):
    from app.library.verification import cli

    registry, lock, root, artifact = _paths(tmp_path)
    cli.lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )

    class Adapter:
        def compare_family(self, **kwargs):
            return malicious

    monkeypatch.setattr(cli, 'ADAPTERS', {'wmb_vpl': Adapter()})
    result = runner.invoke(cli.app, [
        'compare-family', 'world-messianic-bible', '--registry', str(registry),
        '--lock', str(lock), '--artifact-root', str(root),
        '--current-bundle', str(tmp_path / 'current.zip'),
        '--output', str(tmp_path / 'reports'),
    ])

    assert result.exit_code != 0
    rendered = result.stdout + result.stderr
    for secret in (
        str(tmp_path), 'password', 'SECRET_VALUE', 'NESTED_SECRET_VALUE',
        'HIDDEN_VALUE', 'access_token',
    ):
        assert secret not in rendered


def test_compare_cli_emits_only_typed_safe_success_fields(tmp_path, monkeypatch):
    from app.library.verification import cli

    registry, lock, root, artifact = _paths(tmp_path)
    cli.lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )

    class Adapter:
        def compare_family(self, **kwargs):
            return cli.CompareFamilyResult(39, 'wmb-reports')

    monkeypatch.setattr(cli, 'ADAPTERS', {'wmb_vpl': Adapter()})
    result = runner.invoke(cli.app, [
        'compare-family', 'world-messianic-bible', '--registry', str(registry),
        '--lock', str(lock), '--artifact-root', str(root),
        '--current-bundle', str(tmp_path / 'current.zip'),
        '--output', str(tmp_path / 'reports'),
    ])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        'status': 'ok', 'family_id': 'world-messianic-bible',
        'report_count': 39, 'output_id': 'wmb-reports',
    }
    assert str(tmp_path) not in result.stdout


def test_cli_error_never_echoes_adapter_exception_content(tmp_path, monkeypatch):
    from app.library.verification import cli

    registry, lock, root, artifact = _paths(tmp_path)
    cli.lock_artifact_service(
        family_id='world-messianic-bible', registry_path=registry, lock_path=lock,
        artifact_root=root, file=artifact,
        source_url='https://ebible.org/Scriptures/engwmb_vpl.zip',
        retrieved_at='2026-08-17T12:00:00Z',
    )

    class Adapter:
        def compare_family(self, **kwargs):
            raise RuntimeError(
                f'{tmp_path}/PRIVATE https://user:password@example.org/?token=ERROR_SECRET'
            )

    monkeypatch.setattr(cli, 'ADAPTERS', {'wmb_vpl': Adapter()})
    result = runner.invoke(cli.app, [
        'compare-family', 'world-messianic-bible', '--registry', str(registry),
        '--lock', str(lock), '--artifact-root', str(root),
        '--current-bundle', str(tmp_path / 'current.zip'),
        '--output', str(tmp_path / 'reports'),
    ])

    assert result.exit_code != 0
    rendered = result.stdout + result.stderr
    for secret in (str(tmp_path), 'PRIVATE', 'password', 'token', 'ERROR_SECRET'):
        assert secret not in rendered
