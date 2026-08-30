from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path

import pytest

from app.library.verification import SourceVerse, VersePosition, compare_work
from app.library.verification.report import (
    report_json_bytes,
    report_markdown,
    report_sha256,
    write_report_pair,
)


def make_report():
    return compare_work(
        'genesis',
        current=[
            SourceVerse('genesis', 1, 1, 'Café'),
            SourceVerse('genesis', 1, 2, 'Current ```\n<script>alert(1)</script>'),
        ],
        source=[
            SourceVerse('genesis', 1, 1, 'Cafe\u0301'),
            SourceVerse('genesis', 1, 2, 'Sourcé | text'),
        ],
        declared_omissions=[(2, 4)],
        source_artifact_sha256='a' * 64,
        current_publication_sha256='b' * 64,
        parser_version='parser/1.0',
    )


def make_adversarial_report():
    work_id = 'genesis` ```\n<script>work()</script>\n# injected heading\n- injected list'
    evidence = 'Text ```\n<script>evidence()</script>\n# evidence heading\n- evidence list'
    return compare_work(
        work_id,
        current=[SourceVerse(work_id, 1, 1, evidence)],
        source=[SourceVerse(work_id, 1, 1, evidence + '!')],
        source_artifact_sha256='c' * 64,
        current_publication_sha256='d' * 64,
        parser_version='parser` ```\n<script>parser()</script>\n# parser heading\n- parser list',
    )


def test_json_is_canonical_deterministic_unicode_preserving_and_newline_terminated():
    report = make_report()

    first = report_json_bytes(report)
    second = report_json_bytes(report)
    decoded = first.decode('utf-8')
    payload = json.loads(first)

    assert first == second
    assert first.endswith(b'\n')
    assert 'Sourcé' in decoded
    assert '\\u00e9' not in decoded.lower()
    assert payload == {
        'schema_version': 1,
        'work_id': 'genesis',
        'source_artifact_sha256': 'a' * 64,
        'current_publication_sha256': 'b' * 64,
        'parser_version': 'parser/1.0',
        'rules': {
            'unicode_form': 'NFC',
            'normalize_line_endings': True,
            'collapse_whitespace': True,
        },
        'totals': {'exact': 1, 'formatting': 0, 'missing': 0, 'extra': 0, 'wording': 1},
        'declared_omissions': [{'chapter': 2, 'verse': 4}],
        'differences': [{
            'chapter': 1,
            'verse': 2,
            'classification': 'wording',
            'current_text': 'Current ```\n<script>alert(1)</script>',
            'source_text': 'Sourcé | text',
        }],
        'is_verified_candidate': False,
    }
    assert decoded == json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    ) + '\n'


def test_json_sha_hashes_exactly_the_serialized_bytes():
    report = make_report()

    assert report_sha256(report) == sha256(report_json_bytes(report)).hexdigest()


def test_markdown_is_deterministic_complete_and_escapes_arbitrary_evidence_text():
    report = make_report()

    first = report_markdown(report)
    second = report_markdown(report)

    assert first == second
    assert first.endswith('\n')
    for expected in (
        '# Scripture Source Verification Report',
        'genesis', 'a' * 64, 'b' * 64, 'parser/1.0',
        'NFC', 'Normalize line endings: `true`', 'Collapse whitespace: `true`',
        'Exact: 1', 'Formatting: 0', 'Missing: 0', 'Extra: 0', 'Wording: 1',
        '2:4', '1:2', 'wording', 'Sourcé | text',
    ):
        assert expected in first
    assert '<script>' not in first
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in first
    assert '\n    # ' not in first


def test_markdown_renders_all_free_form_metadata_and_evidence_as_inert_text():
    report = make_adversarial_report()

    first = report_markdown(report)
    second = report_markdown(report)

    assert first == second
    assert '<script>' not in first
    assert first.count('&lt;script&gt;') == 4
    assert '\n# injected heading\n' not in first
    assert '\n- injected list\n' not in first
    assert '\n# evidence heading\n' not in first
    assert '\n- evidence list' not in first
    assert '\n# parser heading\n' not in first
    assert '\n- parser list' not in first
    assert [line for line in first.splitlines() if line.startswith('#')] == [
        '# Scripture Source Verification Report',
        '## Identity',
        '## Rules',
        '## Totals',
        '## Declared omissions',
        '## Differences',
        '### 1:1 — wording',
    ]


def test_all_report_values_are_immutable_slots_values():
    report = make_report()

    with pytest.raises(FrozenInstanceError):
        report.parser_version = 'changed'
    with pytest.raises(FrozenInstanceError):
        report.totals.wording = 0
    with pytest.raises(FrozenInstanceError):
        report.source_artifact.sha256 = 'c' * 64
    with pytest.raises(FrozenInstanceError):
        report.current_publication.sha256 = 'c' * 64


@pytest.mark.parametrize('stem', [
    '', '.', '..', '../report', 'folder/report', '/absolute', '\\absolute',
    'report.json', 'bad\x00name', 'bad\nname', ' report', 'report ',
])
def test_write_report_pair_rejects_unsafe_stems_without_creating_output(stem, tmp_path):
    output = tmp_path / 'reports'

    with pytest.raises(ValueError, match='stem'):
        write_report_pair(make_report(), output, stem)

    assert not output.exists()


def test_write_report_pair_is_atomic_repeatable_and_identical_across_directories(tmp_path):
    report = make_report()
    first_dir = tmp_path / 'one'
    second_dir = tmp_path / 'two'

    first = write_report_pair(report, first_dir, 'genesis-verification')
    again = write_report_pair(report, first_dir, 'genesis-verification')
    second = write_report_pair(report, second_dir, 'genesis-verification')

    assert first == again
    assert first.json_path == first_dir / 'genesis-verification.json'
    assert first.markdown_path == first_dir / 'genesis-verification.md'
    assert first.json_sha256 == report_sha256(report)
    assert first.json_path.read_bytes() == second.json_path.read_bytes() == report_json_bytes(report)
    assert first.markdown_path.read_bytes() == second.markdown_path.read_bytes()
    assert tuple(first_dir.glob('.*.tmp')) == ()


def test_write_failure_leaves_no_final_or_temporary_files(tmp_path, monkeypatch):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'

    def fail_before_replace(path: Path, data: bytes):
        raise OSError('injected write failure')

    monkeypatch.setattr(report_module, '_write_temp_file', fail_before_replace)

    with pytest.raises(OSError, match='injected write failure'):
        write_report_pair(make_report(), output, 'genesis')

    assert list(output.iterdir()) == []


def _pair_paths(output):
    return output / 'genesis.json', output / 'genesis.md'


def _assert_prior_pair(output, prior_bytes):
    json_path, markdown_path = _pair_paths(output)
    assert (json_path.read_bytes(), markdown_path.read_bytes()) == prior_bytes
    assert sorted(path.name for path in output.iterdir()) == ['genesis.json', 'genesis.md']


def _inject_move_failures(monkeypatch, report_module, failures):
    real_move = report_module._move_file
    operation_counts = {}

    def injected_move(source, destination, operation):
        operation_counts[operation] = operation_counts.get(operation, 0) + 1
        key = (operation, operation_counts[operation])
        if key in failures:
            raise OSError(f'injected {operation} failure {key[1]}')
        return real_move(source, destination, operation)

    monkeypatch.setattr(report_module, '_move_file', injected_move)
    return operation_counts


@pytest.mark.parametrize('fail_on_backup', [1, 2])
def test_backup_failure_restores_prior_pair_and_cleans_all_debris(
    tmp_path, monkeypatch, fail_on_backup,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    write_report_pair(make_report(), output, 'genesis')
    prior_bytes = tuple(path.read_bytes() for path in _pair_paths(output))
    _inject_move_failures(monkeypatch, report_module, {('backup', fail_on_backup)})

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    assert isinstance(raised.value, report_module.ReportPairWriteError)
    assert f'injected backup failure {fail_on_backup}' in str(raised.value.primary_error)
    _assert_prior_pair(output, prior_bytes)


@pytest.mark.parametrize('fail_on_reservation', [1, 2])
def test_backup_path_reservation_failure_restores_prior_pair(
    tmp_path, monkeypatch, fail_on_reservation,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    write_report_pair(make_report(), output, 'genesis')
    prior_bytes = tuple(path.read_bytes() for path in _pair_paths(output))
    real_reserve = report_module._reserve_backup_path
    reservations = 0

    def fail_reservation(path):
        nonlocal reservations
        reservations += 1
        if reservations == fail_on_reservation:
            raise OSError(f'injected backup reservation failure {fail_on_reservation}')
        return real_reserve(path)

    monkeypatch.setattr(report_module, '_reserve_backup_path', fail_reservation)

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    assert isinstance(raised.value, report_module.ReportPairWriteError)
    assert f'backup reservation failure {fail_on_reservation}' in str(
        raised.value.primary_error
    )
    _assert_prior_pair(output, prior_bytes)


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_backup_descriptor_close_failure_cleans_or_reports_reserved_path(
    tmp_path, monkeypatch, cleanup_fails,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    write_report_pair(make_report(), output, 'genesis')
    prior_bytes = tuple(path.read_bytes() for path in _pair_paths(output))
    real_close = report_module.os.close
    real_move = report_module._move_file
    real_remove = report_module._remove_file
    close_calls = []
    move_calls = []
    reservation_cleanup_paths = []

    def close_then_fail(descriptor):
        close_calls.append(descriptor)
        real_close(descriptor)
        raise OSError('injected descriptor close failure')

    def track_moves(source, destination, operation):
        move_calls.append((source, destination, operation))
        return real_move(source, destination, operation)

    def injected_cleanup(path, operation):
        if operation == 'cleanup-backup-reservation':
            reservation_cleanup_paths.append(path)
            if cleanup_fails:
                raise OSError('injected reservation cleanup failure')
        return real_remove(path, operation)

    monkeypatch.setattr(report_module.os, 'close', close_then_fail)
    monkeypatch.setattr(report_module, '_move_file', track_moves)
    monkeypatch.setattr(report_module, '_remove_file', injected_cleanup)

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    error = raised.value
    assert isinstance(error, report_module.ReportPairWriteError)
    assert 'descriptor close failure' in str(error.primary_error)
    assert len(close_calls) == 1
    assert len(reservation_cleanup_paths) == 1
    assert move_calls == []
    assert tuple(path.read_bytes() for path in _pair_paths(output)) == prior_bytes

    extras = set(output.iterdir()) - set(_pair_paths(output))
    if cleanup_fails:
        assert any(
            'reservation cleanup failure' in str(item)
            for item in error.cleanup_errors
        )
        assert error.recovery_paths == tuple(extras) == tuple(reservation_cleanup_paths)
        assert reservation_cleanup_paths[0].exists()
        assert str(reservation_cleanup_paths[0]) in str(error)
    else:
        assert error.cleanup_errors == ()
        assert error.recovery_paths == ()
        assert extras == set()
        _assert_prior_pair(output, prior_bytes)


@pytest.mark.parametrize('fail_on_install', [1, 2])
@pytest.mark.parametrize('with_prior_pair', [False, True])
def test_install_failure_restores_the_complete_prior_state(
    tmp_path, monkeypatch, fail_on_install, with_prior_pair,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    prior_bytes = None
    if with_prior_pair:
        write_report_pair(make_report(), output, 'genesis')
        prior_bytes = tuple(path.read_bytes() for path in _pair_paths(output))
    _inject_move_failures(monkeypatch, report_module, {('install', fail_on_install)})

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    assert isinstance(raised.value, report_module.ReportPairWriteError)
    assert f'injected install failure {fail_on_install}' in str(raised.value.primary_error)
    if with_prior_pair:
        _assert_prior_pair(output, prior_bytes)
    else:
        json_path, markdown_path = _pair_paths(output)
        assert not json_path.exists()
        assert not markdown_path.exists()
        assert list(output.iterdir()) == []


def test_rollback_restores_original_file_objects_and_metadata(tmp_path, monkeypatch):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    write_report_pair(make_report(), output, 'genesis')
    json_path, markdown_path = _pair_paths(output)
    json_path.chmod(0o640)
    markdown_path.chmod(0o600)
    prior_stats = tuple(path.stat() for path in (json_path, markdown_path))
    _inject_move_failures(monkeypatch, report_module, {('install', 2)})

    with pytest.raises(report_module.ReportPairWriteError):
        write_report_pair(make_adversarial_report(), output, 'genesis')

    restored_stats = tuple(path.stat() for path in (json_path, markdown_path))
    assert [item.st_ino for item in restored_stats] == [
        item.st_ino for item in prior_stats
    ]
    assert [item.st_mode for item in restored_stats] == [
        item.st_mode for item in prior_stats
    ]
    assert [item.st_mtime_ns for item in restored_stats] == [
        item.st_mtime_ns for item in prior_stats
    ]


@pytest.mark.parametrize('fail_on_restore', [1, 2])
def test_failed_restoration_retains_backup_and_attempts_every_restore(
    tmp_path, monkeypatch, fail_on_restore,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    write_report_pair(make_report(), output, 'genesis')
    prior_bytes = tuple(path.read_bytes() for path in _pair_paths(output))
    operation_counts = _inject_move_failures(
        monkeypatch,
        report_module,
        {('install', 2), ('restore', fail_on_restore)},
    )

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    error = raised.value
    assert isinstance(error, report_module.ReportPairWriteError)
    assert 'injected install failure 2' in str(error.primary_error)
    assert operation_counts['restore'] == 2
    assert len(error.rollback_errors) == 1
    assert f'injected restore failure {fail_on_restore}' in str(error.rollback_errors[0])
    assert len(error.recovery_paths) == 1
    recovery_path = error.recovery_paths[0]
    assert recovery_path.exists()
    assert 'restore' in str(error).lower()
    assert str(recovery_path) in str(error)
    failed_index = fail_on_restore - 1
    assert recovery_path.read_bytes() == prior_bytes[failed_index]
    successful_index = 1 - failed_index
    assert _pair_paths(output)[successful_index].read_bytes() == prior_bytes[successful_index]
    assert not _pair_paths(output)[failed_index].exists()
    assert not tuple(output.glob('.*.tmp'))


def test_cleanup_failures_do_not_mask_primary_and_all_cleanup_is_attempted(
    tmp_path, monkeypatch,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    write_report_pair(make_report(), output, 'genesis')
    real_remove = report_module._remove_file
    cleanup_calls = []

    def fail_first_cleanup(path, operation):
        if operation.startswith('cleanup'):
            cleanup_calls.append(path)
            if len(cleanup_calls) == 1:
                raise OSError('injected cleanup failure')
        return real_remove(path, operation)

    _inject_move_failures(monkeypatch, report_module, {('backup', 1)})
    monkeypatch.setattr(report_module, '_remove_file', fail_first_cleanup)

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    error = raised.value
    assert isinstance(error, report_module.ReportPairWriteError)
    assert 'injected backup failure 1' in str(error.primary_error)
    assert len(error.cleanup_errors) == 1
    assert 'injected cleanup failure' in str(error.cleanup_errors[0])
    assert len(cleanup_calls) >= 3
    assert cleanup_calls[0] in error.recovery_paths
    assert cleanup_calls[0].exists()


def test_successful_install_surfaces_backup_cleanup_failure_and_attempts_both(
    tmp_path, monkeypatch,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    write_report_pair(make_report(), output, 'genesis')
    real_remove = report_module._remove_file
    backup_cleanup_calls = []

    def fail_first_backup_cleanup(path, operation):
        if operation == 'cleanup-backup':
            backup_cleanup_calls.append(path)
            if len(backup_cleanup_calls) == 1:
                raise OSError('injected backup cleanup failure')
        return real_remove(path, operation)

    monkeypatch.setattr(report_module, '_remove_file', fail_first_backup_cleanup)

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    error = raised.value
    assert isinstance(error, report_module.ReportPairWriteError)
    assert len(backup_cleanup_calls) == 2
    assert len(error.cleanup_errors) == 1
    assert backup_cleanup_calls[0] in error.recovery_paths
    assert backup_cleanup_calls[0].exists()
    assert _pair_paths(output)[0].read_bytes() == report_json_bytes(make_adversarial_report())


def test_second_staging_failure_cleans_first_staged_file(tmp_path, monkeypatch):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    real_write = report_module._write_temp_file
    writes = 0

    def fail_second_write(path, data):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError('injected second staging failure')
        return real_write(path, data)

    monkeypatch.setattr(report_module, '_write_temp_file', fail_second_write)

    with pytest.raises(OSError) as raised:
        write_report_pair(make_report(), output, 'genesis')

    assert isinstance(raised.value, report_module.ReportPairWriteError)
    assert list(output.iterdir()) == []


def test_temp_cleanup_failure_preserves_write_error_and_recovery_path(
    tmp_path, monkeypatch,
):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    real_remove = report_module._remove_file

    def fail_fsync(_descriptor):
        raise OSError('injected fsync failure')

    def fail_temp_cleanup(path, operation):
        if operation == 'cleanup-temp-write':
            raise OSError('injected temp cleanup failure')
        return real_remove(path, operation)

    monkeypatch.setattr(report_module.os, 'fsync', fail_fsync)
    monkeypatch.setattr(report_module, '_remove_file', fail_temp_cleanup)

    with pytest.raises(OSError) as raised:
        write_report_pair(make_report(), output, 'genesis')

    error = raised.value
    assert isinstance(error, report_module.ReportPairWriteError)
    assert 'injected fsync failure' in str(error.primary_error)
    assert any('injected temp cleanup failure' in str(item) for item in error.cleanup_errors)
    assert len(error.recovery_paths) == 1
    assert error.recovery_paths[0].exists()
    assert str(error.recovery_paths[0]) in str(error)


def test_new_pair_removal_failure_is_actionable_and_not_silent(tmp_path, monkeypatch):
    from app.library.verification import report as report_module

    output = tmp_path / 'reports'
    json_path, markdown_path = _pair_paths(output)
    real_remove = report_module._remove_file

    def fail_new_removal(path, operation):
        if operation == 'rollback-new':
            raise OSError('injected new-file removal failure')
        return real_remove(path, operation)

    _inject_move_failures(monkeypatch, report_module, {('install', 2)})
    monkeypatch.setattr(report_module, '_remove_file', fail_new_removal)

    with pytest.raises(OSError) as raised:
        write_report_pair(make_adversarial_report(), output, 'genesis')

    error = raised.value
    assert isinstance(error, report_module.ReportPairWriteError)
    assert 'injected install failure 2' in str(error.primary_error)
    assert any('new-file removal failure' in str(item) for item in error.rollback_errors)
    assert error.recovery_paths == (json_path,)
    assert json_path.exists()
    assert not markdown_path.exists()
    assert str(json_path) in str(error)


def test_rejects_preexisting_partial_pair_before_touching_it(tmp_path):
    output = tmp_path / 'reports'
    output.mkdir()
    json_path, markdown_path = _pair_paths(output)
    json_path.write_bytes(b'prior-json')

    with pytest.raises(ValueError, match='complete pair'):
        write_report_pair(make_report(), output, 'genesis')

    assert json_path.read_bytes() == b'prior-json'
    assert not markdown_path.exists()
    assert sorted(output.iterdir()) == [json_path]


@pytest.mark.parametrize('kind', ['symlink', 'directory'])
@pytest.mark.parametrize('final_index', [0, 1])
def test_rejects_symlink_and_nonregular_preexisting_outputs(
    tmp_path, kind, final_index,
):
    output = tmp_path / 'reports'
    output.mkdir()
    final_path = _pair_paths(output)[final_index]
    if kind == 'symlink':
        target = tmp_path / 'target'
        target.write_bytes(b'target')
        final_path.symlink_to(target)
    else:
        final_path.mkdir()

    with pytest.raises(ValueError, match='regular file'):
        write_report_pair(make_report(), output, 'genesis')

    assert final_path.is_symlink() if kind == 'symlink' else final_path.is_dir()
