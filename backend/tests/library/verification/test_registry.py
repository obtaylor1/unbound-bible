import hashlib
import json
import os
from pathlib import Path
import stat
import threading
from types import SimpleNamespace

import pytest


DATA_DIR = (
    Path(__file__).parents[3]
    / 'data/scripture/eotc-composite-en/verification'
)


def _definition(**changes):
    from app.library.verification.registry import SourceDefinition

    values = {
        'family_id': 'world-messianic-bible',
        'landing_url': 'https://ebible.org/find/show.php?id=engwmb',
        'artifact_url': 'https://ebible.org/Scriptures/engwmb_vpl.zip',
        'artifact_filename': 'engwmb_vpl.zip',
        'adapter_id': 'wmb_vpl',
        'rights_jurisdiction': (
            'Public-domain dedication; World Messianic Bible naming condition applies'
        ),
        'allowed_source_hosts': ('ebible.org',),
        'max_artifact_bytes': 1024,
        'expected_work_ids': ('genesis',),
    }
    values.update(changes)
    return SourceDefinition(**values)


def _record(content=b'scripture', **changes):
    from app.library.verification.registry import ArtifactLockRecord

    values = {
        'family_id': 'world-messianic-bible',
        'artifact_path': 'engwmb_vpl.zip',
        'source_url': 'https://ebible.org/Scriptures/engwmb_vpl.zip',
        'landing_url': 'https://ebible.org/find/show.php?id=engwmb',
        'retrieved_at': '2026-08-17T12:00:00Z',
        'size_bytes': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
    }
    values.update(changes)
    return ArtifactLockRecord(**values)


def test_committed_registry_has_exact_reviewed_inventory_and_sources():
    from app.library.verification.registry import (
        APPROVED_SOURCE_DEFINITIONS,
        load_source_registry,
    )

    registry = load_source_registry(DATA_DIR / 'source-registry.json')

    assert set(registry.families) == {
        'world-messianic-bible', 'murdock-peshitta-1852',
        'kjv-1611-fallback', 'rh-charles-jubilees-1902',
    }
    assert {key: len(value.expected_work_ids) for key, value in registry.families.items()} == {
        'world-messianic-bible': 39,
        'murdock-peshitta-1852': 27,
        'kjv-1611-fallback': 6,
        'rh-charles-jubilees-1902': 1,
    }
    all_works = [work for family in registry.families.values() for work in family.expected_work_ids]
    assert len(all_works) == len(set(all_works)) == 73
    assert registry.families['murdock-peshitta-1852'].artifact_url == (
        'https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/Murdock.zip'
    )
    assert registry.families['kjv-1611-fallback'].artifact_url == (
        'https://www.gutenberg.org/cache/epub/124/pg124.txt'
    )
    assert registry.families['kjv-1611-fallback'].expected_work_ids == (
        'baruch', 'letter-of-jeremiah', 'prayer-of-azariah',
        'susanna', 'bel-and-the-dragon', 'prayer-of-manasseh',
    )
    assert set(registry.families['world-messianic-bible'].expected_work_ids) == {
        'genesis', 'exodus', 'leviticus', 'numbers', 'deuteronomy', 'joshua',
        'judges', 'ruth', '1-samuel', '2-samuel', '1-kings', '2-kings',
        '1-chronicles', '2-chronicles', 'ezra', 'nehemiah', 'esther', 'job',
        'psalms', 'proverbs', 'ecclesiastes', 'song-of-solomon', 'isaiah',
        'jeremiah', 'lamentations', 'ezekiel', 'daniel', 'hosea', 'joel',
        'amos', 'obadiah', 'jonah', 'micah', 'nahum', 'habakkuk', 'zephaniah',
        'haggai', 'zechariah', 'malachi',
    }
    assert set(registry.families['murdock-peshitta-1852'].expected_work_ids) == {
        'matthew', 'mark', 'luke', 'john', 'acts', 'romans', '1-corinthians',
        '2-corinthians', 'galatians', 'ephesians', 'philippians', 'colossians',
        '1-thessalonians', '2-thessalonians', '1-timothy', '2-timothy', 'titus',
        'philemon', 'hebrews', 'james', '1-peter', '2-peter', '1-john',
        '2-john', '3-john', 'jude', 'revelation',
    }
    assert registry.families['rh-charles-jubilees-1902'].expected_work_ids == (
        'jubilees',
    )
    assert registry.families == APPROVED_SOURCE_DEFINITIONS


def test_approved_source_contract_is_immutable():
    from app.library.verification.registry import APPROVED_SOURCE_DEFINITIONS

    with pytest.raises(TypeError):
        APPROVED_SOURCE_DEFINITIONS['world-messianic-bible'] = None


@pytest.mark.parametrize('family_id', [
    'world-messianic-bible', 'murdock-peshitta-1852',
    'kjv-1611-fallback', 'rh-charles-jubilees-1902',
])
@pytest.mark.parametrize('field', [
    'family_id', 'landing_url', 'artifact_url', 'artifact_filename', 'adapter_id',
    'rights_jurisdiction', 'allowed_source_hosts', 'max_artifact_bytes',
])
def test_registry_rejects_every_approved_family_field_mutation(
    tmp_path, family_id, field,
):
    from app.library.verification.registry import RegistryError, load_source_registry

    payload = json.loads((DATA_DIR / 'source-registry.json').read_text(encoding='utf-8'))
    family = payload['families'][family_id]
    replacements = {
        'family_id': 'kjv-1611-fallback' if family_id != 'kjv-1611-fallback' else 'world-messianic-bible',
        'landing_url': 'https://example.org/landing',
        'artifact_url': 'https://example.org/artifact',
        'artifact_filename': 'different-source.zip',
        'adapter_id': 'charles_jubilees' if family_id != 'rh-charles-jubilees-1902' else 'wmb_vpl',
        'rights_jurisdiction': 'Changed rights claim',
        'allowed_source_hosts': ['example.org'],
        'max_artifact_bytes': family['max_artifact_bytes'] + 1,
    }
    family[field] = replacements[field]
    path = tmp_path / 'registry.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(
        RegistryError,
        match='approved source contract|approved host|mapping key',
    ):
        load_source_registry(path)


@pytest.mark.parametrize(('family_id', 'operation'), [
    (family_id, operation)
    for family_id in (
        'world-messianic-bible', 'murdock-peshitta-1852',
        'kjv-1611-fallback', 'rh-charles-jubilees-1902',
    )
    for operation in ('reorder', 'add', 'remove', 'substitute')
    if not (family_id == 'rh-charles-jubilees-1902' and operation == 'reorder')
])
def test_registry_rejects_expected_work_inventory_mutation(
    tmp_path, family_id, operation,
):
    from app.library.verification.registry import RegistryError, load_source_registry

    payload = json.loads((DATA_DIR / 'source-registry.json').read_text(encoding='utf-8'))
    works = payload['families'][family_id]['expected_work_ids']
    if operation == 'reorder':
        works[0], works[1] = works[1], works[0]
    elif operation == 'add':
        works.append('made-up-work')
    elif operation == 'remove':
        works.pop()
    else:
        works[0] = 'made-up-work'
    path = tmp_path / 'registry.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(RegistryError, match='approved source contract|nonempty list'):
        load_source_registry(path)


def test_committed_lock_contains_all_reviewed_families_and_has_deterministic_bytes():
    from app.library.verification.registry import load_artifact_lock, lock_json_bytes

    path = DATA_DIR / 'source-artifacts.lock.json'
    lock = load_artifact_lock(path)
    assert set(lock.artifacts) == {
        'world-messianic-bible', 'murdock-peshitta-1852', 'kjv-1611-fallback',
        'rh-charles-jubilees-1902',
    }
    record = lock.artifacts['world-messianic-bible']
    assert record.artifact_path == 'engwmb_vpl.zip'
    assert record.source_url == 'https://ebible.org/Scriptures/engwmb_vpl.zip'
    assert record.retrieved_at.isoformat() == '2026-08-18T11:09:49+00:00'
    assert record.size_bytes == 4_283_520
    assert record.sha256 == (
        '02aef8d71addf7bf01438d1d132536f3d2cceb21820df6427015cddd608cfbf8'
    )
    murdock = lock.artifacts['murdock-peshitta-1852']
    assert murdock.artifact_path == 'murdock-source.zip'
    assert murdock.source_url == (
        'https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/Murdock.zip'
    )
    assert murdock.retrieved_at.isoformat() == '2026-08-29T05:53:51+00:00'
    assert murdock.size_bytes == 396_427
    assert murdock.sha256 == (
        '4f0adeba385acbfa37921f66677d4aaf99e23b4e65ca162f122832689036641f'
    )
    kjv = lock.artifacts['kjv-1611-fallback']
    assert kjv.artifact_path == 'project-gutenberg-124.txt'
    assert kjv.source_url == 'https://www.gutenberg.org/cache/epub/124/pg124.txt'
    assert kjv.retrieved_at.isoformat() == '2026-08-29T22:27:25+00:00'
    assert kjv.size_bytes == 835_071
    assert kjv.sha256 == (
        '83de0c18742ba22b3d442c3a5bc828fe9e91dff27ae3c298e9b5c9a6ecfbf4d4'
    )
    assert path.read_bytes() == lock_json_bytes(lock)


def test_lock_serialization_sorts_family_keys_and_is_byte_stable():
    from app.library.verification.registry import ArtifactLock, ArtifactLockRecord, lock_json_bytes

    common = {
        'artifact_path': 'source.zip',
        'source_url': 'https://archive.org/source.zip',
        'landing_url': 'https://archive.org/details/source',
        'retrieved_at': '2026-08-17T12:00:00Z',
        'size_bytes': 1,
        'sha256': '0' * 64,
    }
    late = ArtifactLockRecord(family_id='world-messianic-bible', **common)
    early = ArtifactLockRecord(family_id='kjv-1611-fallback', **common)
    first = lock_json_bytes(ArtifactLock(1, {
        late.family_id: late, early.family_id: early,
    }))
    second = lock_json_bytes(ArtifactLock(1, {
        early.family_id: early, late.family_id: late,
    }))
    assert first == second
    assert first.index(b'kjv-1611-fallback') < first.index(b'world-messianic-bible')


def test_lock_writer_rejects_invalid_existing_bytes_without_overwrite(tmp_path):
    from app.library.verification.registry import ArtifactLock, RegistryError, write_artifact_lock

    path = tmp_path / 'lock.json'
    path.write_bytes(b'{"invalid":true}\n')
    before = path.read_bytes()

    with pytest.raises(RegistryError):
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert path.read_bytes() == before


@pytest.mark.parametrize('target_kind', ['symlink', 'directory'])
def test_lock_writer_rejects_symlink_and_nonregular_target(tmp_path, target_kind):
    from app.library.verification.registry import ArtifactLock, RegistryError, write_artifact_lock

    path = tmp_path / 'lock.json'
    if target_kind == 'symlink':
        target = tmp_path / 'target.json'
        target.write_text('{"artifacts":{},"version":1}\n', encoding='utf-8')
        path.symlink_to(target)
    else:
        path.mkdir()

    with pytest.raises(RegistryError, match='regular|symlink'):
        write_artifact_lock(path, ArtifactLock(1, {}))


def test_lock_commit_keeps_canonical_readable_until_single_atomic_replace(
    tmp_path, monkeypatch,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{ "artifacts": {}, "version": 1 }\n'
    path.write_bytes(old)
    real_open = module.os.open
    real_fsync = module.os.fsync
    real_replace = module.os.replace
    committed = False
    replacements = []

    def assert_old_before_open(value, flags, *args):
        if not committed:
            assert path.read_bytes() == old
        return real_open(value, flags, *args)

    def assert_old_before_fsync(descriptor):
        if not committed:
            assert path.read_bytes() == old
        return real_fsync(descriptor)

    def observe_replace(source, destination):
        nonlocal committed
        assert destination == path
        assert path.read_bytes() == old
        replacements.append((Path(source), Path(destination)))
        result = real_replace(source, destination)
        committed = True
        return result

    monkeypatch.setattr(module.os, 'open', assert_old_before_open)
    monkeypatch.setattr(module.os, 'fsync', assert_old_before_fsync)
    monkeypatch.setattr(module.os, 'replace', observe_replace)

    write_artifact_lock(path, ArtifactLock(1, {}))

    assert len(replacements) == 1
    assert replacements[0][1] == path
    assert path.read_bytes() == b'{"artifacts":{},"version":1}\n'


def test_concurrent_reader_sees_old_lock_until_atomic_commit(tmp_path, monkeypatch):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{ "artifacts": {}, "version": 1 }\n'
    path.write_bytes(old)
    real_replace = module.os.replace
    commit_ready = threading.Event()
    allow_commit = threading.Event()
    errors = []

    def pause_commit(source, destination):
        if Path(destination) == path:
            commit_ready.set()
            assert allow_commit.wait(timeout=5)
        return real_replace(source, destination)

    def write_lock():
        try:
            write_artifact_lock(path, ArtifactLock(1, {}))
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(module.os, 'replace', pause_commit)
    writer = threading.Thread(target=write_lock)
    writer.start()
    try:
        assert commit_ready.wait(timeout=5)
        assert path.read_bytes() == old
    finally:
        allow_commit.set()
        writer.join(timeout=5)

    assert not writer.is_alive()
    assert errors == []
    assert path.read_bytes() == b'{"artifacts":{},"version":1}\n'


def test_lock_transaction_cleans_partial_recovery_copy_after_fsync_failure(
    tmp_path, monkeypatch,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{"artifacts":{},"version":1}\n'
    path.write_bytes(old)
    real_fsync = module.os.fsync
    file_syncs = 0

    def fail_recovery_copy_fsync(descriptor):
        nonlocal file_syncs
        if stat.S_ISREG(module.os.fstat(descriptor).st_mode):
            file_syncs += 1
            if file_syncs == 2:
                raise OSError('recovery copy fsync failed')
        return real_fsync(descriptor)

    monkeypatch.setattr(module.os, 'fsync', fail_recovery_copy_fsync)
    with pytest.raises(LockWriteError):
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert path.read_bytes() == old
    assert list(tmp_path.glob('.lock.json.*')) == []


def test_lock_transaction_does_not_delete_unowned_stage_collision(tmp_path, monkeypatch):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    transaction_id = f'{os.getpid()}-collision'
    collision = tmp_path / f'.lock.json.tmp-{transaction_id}'
    collision.write_bytes(b'unowned')
    monkeypatch.setattr(module, 'uuid4', lambda: SimpleNamespace(hex='collision'))

    with pytest.raises(LockWriteError):
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert collision.read_bytes() == b'unowned'
    assert not path.exists()


@pytest.mark.parametrize('failed_directory_sync', [1, 2, 3])
def test_old_lock_is_restored_for_every_directory_sync_failure(
    tmp_path, monkeypatch, failed_directory_sync,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{"artifacts":{},"version":1}\n'
    path.write_bytes(old)
    real_fsync = module.os.fsync
    directory_syncs = 0

    def fail_selected_directory_sync(descriptor):
        nonlocal directory_syncs
        if stat.S_ISDIR(module.os.fstat(descriptor).st_mode):
            directory_syncs += 1
            if directory_syncs == failed_directory_sync:
                raise OSError('selected directory sync failure')
        return real_fsync(descriptor)

    monkeypatch.setattr(module.os, 'fsync', fail_selected_directory_sync)
    with pytest.raises(LockWriteError):
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert path.read_bytes() == old


@pytest.mark.parametrize('had_old_lock', [False, True])
@pytest.mark.parametrize('failure', ['stage-fsync', 'directory-open', 'directory-fsync'])
def test_lock_transaction_failure_restores_prior_state(
    tmp_path, monkeypatch, had_old_lock, failure,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{"artifacts":{},"version":1}\n'
    if had_old_lock:
        path.write_bytes(old)
    real_open = module.os.open
    real_fsync = module.os.fsync

    if failure == 'stage-fsync':
        calls = 0

        def fail_stage_fsync(descriptor):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('stage fsync failed')
            return real_fsync(descriptor)

        monkeypatch.setattr(module.os, 'fsync', fail_stage_fsync)
    elif failure == 'directory-open':
        def fail_directory_open(value, flags, *args):
            if Path(value) == tmp_path:
                raise OSError('directory open failed')
            return real_open(value, flags, *args)

        monkeypatch.setattr(module.os, 'open', fail_directory_open)
    else:
        def fail_directory_fsync(descriptor):
            if stat.S_ISDIR(module.os.fstat(descriptor).st_mode):
                raise OSError('directory fsync failed')
            return real_fsync(descriptor)

        monkeypatch.setattr(module.os, 'fsync', fail_directory_fsync)

    with pytest.raises(LockWriteError):
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert path.read_bytes() == old if had_old_lock else not path.exists()


def test_lock_transaction_commit_replace_failure_leaves_old_lock(
    tmp_path, monkeypatch,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{"artifacts":{},"version":1}\n'
    path.write_bytes(old)
    real_replace = module.os.replace

    def fail_commit_replace(source, destination):
        if Path(destination) == path:
            raise OSError('replace failed')
        return real_replace(source, destination)

    monkeypatch.setattr(module.os, 'replace', fail_commit_replace)
    with pytest.raises(LockWriteError):
        write_artifact_lock(path, ArtifactLock(1, {}))
    assert path.read_bytes() == old


def test_lock_transaction_restore_failure_reports_new_and_recovery_backup(
    tmp_path, monkeypatch,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{ "artifacts": {}, "version": 1 }\n'
    path.write_bytes(old)
    real_replace = module.os.replace
    real_fsync = module.os.fsync
    replaces = 0

    def fail_restore(source, destination):
        nonlocal replaces
        replaces += 1
        if replaces == 2:
            raise OSError('restore failed')
        return real_replace(source, destination)

    directory_syncs = 0

    def fail_directory_fsync(descriptor):
        nonlocal directory_syncs
        if stat.S_ISDIR(module.os.fstat(descriptor).st_mode):
            directory_syncs += 1
            if directory_syncs == 2:
                raise OSError('commit fsync failed')
        return real_fsync(descriptor)

    monkeypatch.setattr(module.os, 'replace', fail_restore)
    monkeypatch.setattr(module.os, 'fsync', fail_directory_fsync)
    with pytest.raises(LockWriteError) as captured:
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert path.exists()
    assert path.read_bytes() != old
    assert captured.value.recovery_path == path
    assert captured.value.recovery_backup is not None
    assert captured.value.recovery_backup.read_bytes() == old


def test_lock_transaction_backup_cleanup_failure_rolls_back(tmp_path, monkeypatch):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{"artifacts":{},"version":1}\n'
    path.write_bytes(old)
    real_unlink = Path.unlink
    failed = False

    def fail_backup_cleanup(value, *args, **kwargs):
        nonlocal failed
        if '.bak-' in value.name and not failed:
            failed = True
            raise OSError('backup cleanup failed')
        return real_unlink(value, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', fail_backup_cleanup)
    with pytest.raises(LockWriteError):
        write_artifact_lock(path, ArtifactLock(1, {}))
    assert path.read_bytes() == old


@pytest.mark.parametrize('had_old_lock', [False, True])
def test_lock_transaction_cleanup_failure_does_not_mask_primary(
    tmp_path, monkeypatch, had_old_lock,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    old = b'{"artifacts":{},"version":1}\n'
    if had_old_lock:
        path.write_bytes(old)
    real_fsync = module.os.fsync
    real_unlink = Path.unlink

    def fail_stage_fsync(_descriptor):
        raise OSError('primary stage failure')

    def fail_temp_cleanup(value, *args, **kwargs):
        if '.tmp-' in value.name:
            raise OSError('secondary cleanup failure')
        return real_unlink(value, *args, **kwargs)

    monkeypatch.setattr(module.os, 'fsync', fail_stage_fsync)
    monkeypatch.setattr(Path, 'unlink', fail_temp_cleanup)
    with pytest.raises(LockWriteError) as captured:
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert 'primary stage failure' in str(captured.value.primary_error)
    assert any('secondary cleanup failure' in str(error) for error in captured.value.cleanup_errors)
    assert path.read_bytes() == old if had_old_lock else not path.exists()


def test_lock_transaction_reports_retained_final_path_if_no_old_cleanup_fails(
    tmp_path, monkeypatch,
):
    from app.library.verification import registry as module
    from app.library.verification.registry import ArtifactLock, LockWriteError, write_artifact_lock

    path = tmp_path / 'lock.json'
    real_fsync = module.os.fsync
    real_unlink = Path.unlink

    def fail_directory_fsync(descriptor):
        if stat.S_ISDIR(module.os.fstat(descriptor).st_mode):
            raise OSError('commit fsync failed')
        return real_fsync(descriptor)

    def fail_final_cleanup(value, *args, **kwargs):
        if value == path:
            raise OSError('final cleanup failed')
        return real_unlink(value, *args, **kwargs)

    monkeypatch.setattr(module.os, 'fsync', fail_directory_fsync)
    monkeypatch.setattr(Path, 'unlink', fail_final_cleanup)
    with pytest.raises(LockWriteError) as captured:
        write_artifact_lock(path, ArtifactLock(1, {}))

    assert path.exists()
    assert captured.value.recovery_path == path
    assert any('final cleanup failed' in str(error) for error in captured.value.cleanup_errors)


@pytest.mark.parametrize('bad_url', [
    'http://ebible.org/source.zip',
    'https://user:pass@ebible.org/source.zip',
    'https://ebible.org/source.zip#fragment',
    'https://ebible.org/source.zip?access_token=secret',
    'https://ebible.org/source.zip?sig=secret',
    'https://ebible.org/%2e%2e/private.zip',
    'https://ebible.org/%252525252e%252525252e/private.zip',
    'https://ebible.org/source%0a.zip',
    'https://evil.example/source.zip',
])
def test_definition_rejects_unsafe_or_unapproved_artifact_urls(bad_url):
    with pytest.raises(ValueError):
        _definition(artifact_url=bad_url)


@pytest.mark.parametrize('bad_url', [
    'https://ebible.org/source\u0085.zip',
    'https://ebible.org/source\u202e.zip',
    'https://ebible.org/source\u200b.zip',
    'https://ebible.org/source%C2%85.zip',
    'https://ebible.org/source%E2%80%AE.zip',
    'https://ebible.org/source%25E2%2580%25AE.zip',
])
def test_definition_rejects_raw_and_encoded_unicode_controls(bad_url):
    with pytest.raises(ValueError, match='control|format|unsafe'):
        _definition(artifact_url=bad_url)


def test_definition_rejects_unicode_format_in_relevant_text_but_allows_letters():
    with pytest.raises(ValueError, match='control|format|unsafe'):
        _definition(rights_jurisdiction='Public domain\u202e')
    assert _definition(rights_jurisdiction='Domaine public — Éthiopie').rights_jurisdiction


@pytest.mark.parametrize('filename', [
    '../source.zip', '/tmp/source.zip', 'folder/source.zip', 'source\n.zip',
    '..', '.hidden', 'source%2fescape.zip',
])
def test_definition_rejects_unsafe_artifact_filenames(filename):
    with pytest.raises(ValueError):
        _definition(artifact_filename=filename)


def test_json_loading_rejects_duplicate_members_and_extra_fields(tmp_path):
    from app.library.verification.registry import RegistryError, load_source_registry

    duplicate = tmp_path / 'duplicate.json'
    duplicate.write_text('{"version":1,"version":1,"families":{}}', encoding='utf-8')
    with pytest.raises(RegistryError, match='duplicate JSON member'):
        load_source_registry(duplicate)

    payload = json.loads((DATA_DIR / 'source-registry.json').read_text(encoding='utf-8'))
    payload['unexpected'] = True
    extra = tmp_path / 'extra.json'
    extra.write_text(json.dumps(payload), encoding='utf-8')
    with pytest.raises(RegistryError, match='extra field'):
        load_source_registry(extra)


def test_registry_rejects_omitted_approved_murdock_artifact_url(tmp_path):
    from app.library.verification.registry import RegistryError, load_source_registry

    payload = json.loads((DATA_DIR / 'source-registry.json').read_text(encoding='utf-8'))
    del payload['families']['murdock-peshitta-1852']['artifact_url']
    path = tmp_path / 'registry.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(RegistryError, match='approved source contract'):
        load_source_registry(path)


def test_definition_rejects_normalized_duplicates_and_unsupported_adapter():
    with pytest.raises(ValueError, match='work IDs'):
        _definition(expected_work_ids=('genesis', 'genesis'))
    with pytest.raises(ValueError, match='hosts'):
        _definition(allowed_source_hosts=('ebible.org', 'EBIBLE.ORG'))
    with pytest.raises(ValueError, match='adapter'):
        _definition(adapter_id='generic_parser')


def test_lock_rejects_non_utc_or_naive_retrieval_dates():
    with pytest.raises(ValueError, match='UTC'):
        _record(retrieved_at='2026-08-17T12:00:00')
    with pytest.raises(ValueError, match='UTC'):
        _record(retrieved_at='2026-08-17T12:00:00-04:00')


def test_verify_artifact_streams_and_checks_checksum_size_and_host(tmp_path, monkeypatch):
    from app.library.verification import registry as module
    from app.library.verification.registry import SourceArtifactError, verify_artifact

    content = b'scripture'
    (tmp_path / 'engwmb_vpl.zip').write_bytes(content)
    monkeypatch.setattr(Path, 'read_bytes', lambda _self: pytest.fail('must stream'))
    assert verify_artifact(_record(content), _definition(), tmp_path).sha256 == hashlib.sha256(content).hexdigest()
    with pytest.raises(SourceArtifactError, match='checksum mismatch'):
        verify_artifact(_record(content, sha256='0' * 64), _definition(), tmp_path)
    with pytest.raises(SourceArtifactError, match='size mismatch'):
        verify_artifact(_record(content, size_bytes=len(content) + 1), _definition(), tmp_path)
    with pytest.raises(SourceArtifactError, match='approved host'):
        verify_artifact(_record(content, source_url='https://example.org/source.zip'), _definition(), tmp_path)


def test_verify_artifact_rejects_oversize_wrong_filename_and_landing(tmp_path):
    from app.library.verification.registry import SourceArtifactError, verify_artifact

    content = b'scripture'
    (tmp_path / 'engwmb_vpl.zip').write_bytes(content)
    with pytest.raises(SourceArtifactError, match='maximum'):
        verify_artifact(_record(content), _definition(max_artifact_bytes=3), tmp_path)
    with pytest.raises(SourceArtifactError, match='filename'):
        verify_artifact(_record(content, artifact_path='other.zip'), _definition(), tmp_path)
    with pytest.raises(SourceArtifactError, match='landing URL'):
        verify_artifact(_record(content, landing_url='https://ebible.org/other'), _definition(), tmp_path)


def test_verify_artifact_rejects_symlink_and_nonregular(tmp_path):
    from app.library.verification.registry import SourceArtifactError, verify_artifact

    target = tmp_path / 'target.zip'
    target.write_bytes(b'scripture')
    (tmp_path / 'engwmb_vpl.zip').symlink_to(target)
    with pytest.raises(SourceArtifactError, match='symlink|regular'):
        verify_artifact(_record(), _definition(), tmp_path)

    (tmp_path / 'engwmb_vpl.zip').unlink()
    (tmp_path / 'engwmb_vpl.zip').mkdir()
    with pytest.raises(SourceArtifactError, match='regular'):
        verify_artifact(_record(), _definition(), tmp_path)


def test_verify_artifact_detects_file_change_during_hash(tmp_path, monkeypatch):
    from app.library.verification import registry as module
    from app.library.verification.registry import SourceArtifactError, verify_artifact

    content = b'scripture'
    path = tmp_path / 'engwmb_vpl.zip'
    path.write_bytes(content)
    original = module._stream_identity

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000))
        return result

    monkeypatch.setattr(module, '_stream_identity', changed)
    with pytest.raises(SourceArtifactError, match='changed while'):
        verify_artifact(_record(content), _definition(), tmp_path)


def test_verify_artifact_detects_descriptor_change_after_stream(tmp_path, monkeypatch):
    from app.library.verification import registry as module
    from app.library.verification.registry import SourceArtifactError, verify_artifact

    content = b'scripture'
    (tmp_path / 'engwmb_vpl.zip').write_bytes(content)
    real_fstat = module.os.fstat
    calls = 0

    def changed_fstat(descriptor):
        nonlocal calls
        calls += 1
        value = real_fstat(descriptor)
        if calls == 2:
            fields = {
                name: getattr(value, name)
                for name in (
                    'st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns',
                    'st_ctime_ns',
                )
            }
            fields['st_mtime_ns'] += 1
            return SimpleNamespace(**fields)
        return value

    monkeypatch.setattr(module.os, 'fstat', changed_fstat)
    with pytest.raises(SourceArtifactError, match='changed while'):
        verify_artifact(_record(content), _definition(), tmp_path)
    assert calls >= 2


def test_file_identity_detects_same_size_rewrite_with_restored_mtime(tmp_path):
    from app.library.verification.registry import _same_file

    path = tmp_path / 'source.zip'
    path.write_bytes(b'original')
    before = path.stat()
    path.write_bytes(b'replaced')
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    assert not _same_file(before, path.stat())
