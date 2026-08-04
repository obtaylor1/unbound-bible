from dataclasses import FrozenInstanceError
import sqlite3
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from app.library.ingest.models import (
    ScripturePublication,
    ScripturePublicationVerse,
    StagedScriptureVerse,
)
from app.library.models import EditionCoverage, TextEdition


def create_legacy_texts(session):
    """Create the standalone legacy table expected by the publisher."""
    with session.bind.begin() as connection:
        connection.execute(text('''
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation TEXT
            )
        '''))
        connection.execute(text('''
            CREATE UNIQUE INDEX uq_biblical_texts_translation_book_chapter_verse
            ON biblical_texts (coalesce(translation, ''), book, chapter, verse)
        '''))


def legacy_rows(session, translation):
    return session.execute(text('''
        SELECT book, chapter, verse, text, translation
        FROM biblical_texts
        WHERE translation = :translation
        ORDER BY book, chapter, verse
    '''), {'translation': translation}).all()


def active_publication(session, edition_code):
    return session.scalar(select(ScripturePublication).where(
        ScripturePublication.edition_code == edition_code,
        ScripturePublication.active.is_(True),
    ))


def set_run_manifest(run, **values):
    run.manifest_snapshot = {**run.manifest_snapshot, **values}


def test_publish_result_is_immutable(ingest_session):
    from app.library.ingest.publish import PublicationResult

    result = PublicationResult('edition', uuid4(), 1, True, 3)

    with pytest.raises(FrozenInstanceError):
        result.changed = False


def test_publish_blocks_positive_error_count_without_error_finding_rows(ingest_session):
    from app.library.ingest.publish import PublicationBlocked, publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Unsafe counter state')
    run.error_count = 1
    ingest_session.flush()

    with pytest.raises(PublicationBlocked, match='error count'):
        publish_run(ingest_session, run.id)

    assert active_publication(ingest_session, 'target') is None
    assert legacy_rows(ingest_session, 'target') == []


def test_publish_allows_warnings_when_error_count_is_zero(ingest_session):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Reviewed warning')
    run.warning_count = 1
    ingest_session.flush()

    result = publish_run(ingest_session, run.id)

    assert result.changed is True
    assert run.status == 'published'


def test_publish_promotes_manifest_metadata_and_failure_preserves_live_catalog(
    ingest_session, monkeypatch
):
    import app.library.ingest.publish as publisher
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Promoted text')
    run.manifest_snapshot = {
        **run.manifest_snapshot,
        'name': 'Reviewed Ethiopian Edition',
        'reading_language': "Ge'ez",
        'source_language': "Ge'ez",
        'script': "Ge'ez",
        'attribution': 'Reviewed attribution.',
        'relationship': 'exact_ethiopian',
    }
    live = ingest_session.get(TextEdition, 'target')
    live.name = 'Current Live Edition'
    live.reading_language = 'English'
    live.verification_status = 'verified'
    live.source_checksum = 'f' * 64
    ingest_session.flush()
    before = (
        live.name, live.reading_language, live.source_language, live.script,
        live.relationship, live.verification_status, live.source_checksum,
    )

    original_insert = publisher._insert_legacy_rows
    monkeypatch.setattr(
        publisher,
        '_insert_legacy_rows',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('injected failure')),
    )
    with pytest.raises(RuntimeError, match='injected failure'):
        publisher.publish_run(ingest_session, run.id)

    ingest_session.expire_all()
    current = ingest_session.get(TextEdition, 'target')
    assert (
        current.name, current.reading_language, current.source_language, current.script,
        current.relationship, current.verification_status, current.source_checksum,
    ) == before

    monkeypatch.setattr(publisher, '_insert_legacy_rows', original_insert)
    publisher.publish_run(ingest_session, run.id)

    ingest_session.expire_all()
    promoted = ingest_session.get(TextEdition, 'target')
    assert (
        promoted.name,
        promoted.reading_language,
        promoted.source_language,
        promoted.script,
        promoted.attribution,
        promoted.relationship,
        promoted.verification_status,
        promoted.source_checksum,
    ) == (
        'Reviewed Ethiopian Edition',
        "Ge'ez",
        "Ge'ez",
        "Ge'ez",
        'Reviewed attribution.',
        'exact_ethiopian',
        'verified',
        run.source_checksum,
    )


def test_publish_replaces_only_target_edition_with_canonical_books_and_coverage(ingest_session):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    ingest_session.execute(text('''
        INSERT INTO biblical_texts (book, chapter, verse, text, translation)
        VALUES ('Genesis', 1, 1, 'KJV remains unchanged', 'KJV')
    '''))
    run = make_ingest_run(ingest_session, 'target', 'Published target text')
    staged = ingest_session.scalar(select(StagedScriptureVerse).where(
        StagedScriptureVerse.run_id == run.id
    ))
    staged.source_book = 'Arbitrary source label'
    from app.library.ingest.types import row_checksum
    staged.row_checksum = row_checksum(
        staged.work_id,
        staged.source_book,
        staged.chapter,
        staged.verse,
        staged.normalized_text,
        staged.source_locator,
    )
    ingest_session.flush()
    set_run_manifest(run, relationship='exact_ethiopian', reading_language='English')

    result = publish_run(ingest_session, run.id)

    assert result.changed is True
    assert result.publication_version == 1
    assert legacy_rows(ingest_session, 'KJV') == [
        ('Genesis', 1, 1, 'KJV remains unchanged', 'KJV')
    ]
    assert legacy_rows(ingest_session, 'target') == [
        ('Genesis', 1, 1, 'Published target text', 'target')
    ]
    coverage = ingest_session.scalar(select(EditionCoverage).where(
        EditionCoverage.edition_code == 'target', EditionCoverage.work_id == 'genesis'
    ))
    assert (coverage.status, coverage.chapter_count, coverage.verse_count) == (
        'verified_english', 1, 1
    )
    assert str(run.id) in coverage.note and run.source_checksum in coverage.note
    active = active_publication(ingest_session, 'target')
    assert (active.run_id, active.previous_run_id, active.publication_version) == (run.id, None, 1)
    assert run.status == 'published' and run.published_count == 1


def test_publish_is_full_fingerprint_idempotent_without_mutating_requested_run(ingest_session):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    first = make_ingest_run(ingest_session, 'target', 'First text')
    publish_run(ingest_session, first.id)
    requested = make_ingest_run(ingest_session, 'target', 'First text')
    requested.source_checksum = first.source_checksum
    ingest_session.flush()
    original_rows = legacy_rows(ingest_session, 'target')

    result = publish_run(ingest_session, requested.id)

    assert result.changed is False
    assert result.run_id == first.id
    assert result.publication_version == 1
    assert legacy_rows(ingest_session, 'target') == original_rows
    assert requested.status == 'verified'
    assert ingest_session.scalars(select(ScripturePublication).where(
        ScripturePublication.edition_code == 'target'
    )).all() == [active_publication(ingest_session, 'target')]


def test_same_source_checksum_with_changed_normalized_rows_publishes_new_version(
    ingest_session
):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    first = make_ingest_run(ingest_session, 'target', 'First text')
    publish_run(ingest_session, first.id)
    corrected = make_ingest_run(ingest_session, 'target', 'Corrected normalized text')
    corrected.source_checksum = first.source_checksum
    corrected.manifest_snapshot = first.manifest_snapshot
    ingest_session.flush()

    result = publish_run(ingest_session, corrected.id)

    assert result.changed is True
    assert result.publication_version == 2
    assert result.run_id == corrected.id
    assert legacy_rows(ingest_session, 'target')[0].text == 'Corrected normalized text'


@pytest.mark.parametrize(
    ('manifest_change', 'expected_field', 'expected_value'),
    [
        ({'name': 'Corrected Edition Name'}, 'name', 'Corrected Edition Name'),
        ({'attribution': 'Corrected attribution.'}, 'attribution', 'Corrected attribution.'),
        ({'license_spdx': 'CC-BY-4.0'}, 'license_spdx', 'CC-BY-4.0'),
        ({'adapter_options': {'strip_notes': True}}, None, None),
    ],
)
def test_same_source_checksum_with_changed_manifest_publishes_new_version(
    ingest_session, manifest_change, expected_field, expected_value
):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    first = make_ingest_run(ingest_session, 'target', 'Same rows')
    publish_run(ingest_session, first.id)
    corrected = make_ingest_run(ingest_session, 'target', 'Same rows')
    corrected.source_checksum = first.source_checksum
    set_run_manifest(corrected, **manifest_change)
    ingest_session.flush()

    result = publish_run(ingest_session, corrected.id)

    assert result.changed is True
    assert result.publication_version == 2
    assert result.run_id == corrected.id
    if expected_field is not None:
        assert getattr(ingest_session.get(TextEdition, 'target'), expected_field) == expected_value


def test_exact_active_run_retry_is_a_noop_after_run_is_published(ingest_session):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Published once')
    first = publish_run(ingest_session, run.id)

    retry = publish_run(ingest_session, run.id)

    assert retry == type(first)('target', run.id, 1, False, 1)
    assert len(ingest_session.scalars(select(ScripturePublication).where(
        ScripturePublication.edition_code == 'target'
    )).all()) == 1


@pytest.mark.parametrize('corruption', ['error_count', 'error_finding'])
def test_exact_active_run_retry_rechecks_error_gate(ingest_session, corruption):
    from app.library.ingest.models import ScriptureValidationFinding
    from app.library.ingest.publish import PublicationBlocked, publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Published once')
    publish_run(ingest_session, run.id)
    if corruption == 'error_count':
        run.error_count = 1
    else:
        ingest_session.add(ScriptureValidationFinding(
            run_id=run.id,
            severity='error',
            code='post_publish_audit_error',
            message='Post-publication audit found an error.',
        ))
    ingest_session.flush()

    with pytest.raises(PublicationBlocked, match='error'):
        publish_run(ingest_session, run.id)

    assert active_publication(ingest_session, 'target').run_id == run.id
    assert legacy_rows(ingest_session, 'target') == [
        ('Genesis', 1, 1, 'Published once', 'target')
    ]


def test_matching_checksum_noop_rechecks_active_run_error_gate(ingest_session):
    from app.library.ingest.publish import PublicationBlocked, publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    active = make_ingest_run(ingest_session, 'target', 'Published once')
    publish_run(ingest_session, active.id)
    active.error_count = 1
    requested = make_ingest_run(ingest_session, 'target', 'Published once')
    requested.source_checksum = active.source_checksum
    ingest_session.flush()

    with pytest.raises(PublicationBlocked, match='error count'):
        publish_run(ingest_session, requested.id)

    assert active_publication(ingest_session, 'target').run_id == active.id
    assert requested.status == 'verified'


@pytest.mark.parametrize('status,finding,remove_staged_rows', [
    ('staged', None, False),
    ('verified', {'severity': 'error', 'code': 'missing_verse', 'message': 'Missing verse'}, False),
    ('verified', None, True),
])
def test_same_checksum_does_not_bypass_publication_gate(
    ingest_session, status, finding, remove_staged_rows
):
    from app.library.ingest.publish import PublicationBlocked, publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    first = make_ingest_run(ingest_session, 'target', 'Published text')
    publish_run(ingest_session, first.id)
    requested = make_ingest_run(
        ingest_session,
        'target',
        'Unsafe replacement rows',
        status=status,
        finding=finding,
    )
    requested.source_checksum = first.source_checksum
    if remove_staged_rows:
        ingest_session.execute(delete(StagedScriptureVerse).where(
            StagedScriptureVerse.run_id == requested.id
        ))
    ingest_session.flush()
    original_rows = legacy_rows(ingest_session, 'target')
    original_publication = active_publication(ingest_session, 'target')
    original_coverage = ingest_session.scalar(select(EditionCoverage).where(
        EditionCoverage.edition_code == 'target'
    ))
    coverage_snapshot = (
        original_coverage.id,
        original_coverage.status,
        original_coverage.chapter_count,
        original_coverage.verse_count,
        original_coverage.note,
    )

    with pytest.raises(PublicationBlocked):
        publish_run(ingest_session, requested.id)

    assert legacy_rows(ingest_session, 'target') == original_rows
    assert active_publication(ingest_session, 'target') is original_publication
    assert len(ingest_session.scalars(select(ScripturePublication).where(
        ScripturePublication.edition_code == 'target'
    )).all()) == 1
    coverage = ingest_session.scalar(select(EditionCoverage).where(
        EditionCoverage.edition_code == 'target'
    ))
    assert (
        coverage.id,
        coverage.status,
        coverage.chapter_count,
        coverage.verse_count,
        coverage.note,
    ) == coverage_snapshot
    assert first.status == 'published'
    assert requested.status == status
    assert requested.published_count == 0


@pytest.mark.parametrize('status,finding', [
    ('staged', None),
    ('validated', None),
    ('verified', {'severity': 'error', 'code': 'missing_verse', 'message': 'Missing verse'}),
])
def test_publish_blocks_unverified_or_error_runs(ingest_session, status, finding):
    from app.library.ingest.publish import PublicationBlocked, publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Unsafe to publish', status=status, finding=finding)

    with pytest.raises(PublicationBlocked):
        publish_run(ingest_session, run.id)

    assert legacy_rows(ingest_session, 'target') == []
    assert active_publication(ingest_session, 'target') is None
    assert run.status == status


def test_publish_does_not_change_other_edition_coverage(ingest_session):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    other = make_ingest_run(ingest_session, 'other', 'Other text')
    target = make_ingest_run(ingest_session, 'target', 'Target text')
    publish_run(ingest_session, other.id)
    other_coverage = ingest_session.scalar(select(EditionCoverage).where(
        EditionCoverage.edition_code == 'other'
    ))
    before = (other_coverage.id, other_coverage.status, other_coverage.note)

    publish_run(ingest_session, target.id)

    ingest_session.expire_all()
    current = ingest_session.scalar(select(EditionCoverage).where(
        EditionCoverage.edition_code == 'other'
    ))
    assert (current.id, current.status, current.note) == before


@pytest.mark.parametrize(
    ('relationship', 'language', 'expected_status'),
    [
        ('exact_ethiopian', 'Ge\'ez', 'verified_original'),
        ('related_recension', 'Amharic', 'related_recension'),
        ('general_reading', 'English', 'verified_english'),
    ],
)
def test_coverage_status_truthfully_reflects_edition_relationship(
    ingest_session, relationship, language, expected_status
):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Target text')
    set_run_manifest(
        run,
        relationship=relationship,
        reading_language=language,
    )

    publish_run(ingest_session, run.id)

    coverage = ingest_session.scalar(select(EditionCoverage).where(
        EditionCoverage.edition_code == 'target'
    ))
    assert coverage.status == expected_status
    assert ingest_session.get(TextEdition, 'target').relationship == relationship


def test_publish_failure_after_delete_rolls_back_all_target_state(ingest_session, monkeypatch):
    import app.library.ingest.publish as publisher
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    old = make_ingest_run(ingest_session, 'target', 'Old text')
    publisher.publish_run(ingest_session, old.id)
    new = make_ingest_run(ingest_session, 'target', 'New text')
    before_coverage = ingest_session.scalar(select(EditionCoverage).where(
        EditionCoverage.edition_code == 'target'
    )).note

    def fail_after_delete(*_args, **_kwargs):
        raise RuntimeError('injected insert failure')

    monkeypatch.setattr(publisher, '_insert_legacy_rows', fail_after_delete)
    with pytest.raises(RuntimeError, match='injected insert failure'):
        publisher.publish_run(ingest_session, new.id)

    ingest_session.expire_all()
    assert legacy_rows(ingest_session, 'target') == [
        ('Genesis', 1, 1, 'Old text', 'target')
    ]
    assert active_publication(ingest_session, 'target').run_id == old.id
    assert ingest_session.get(type(new), new.id).status == 'verified'
    assert ingest_session.scalar(select(EditionCoverage.note).where(
        EditionCoverage.edition_code == 'target'
    )) == before_coverage


def test_publish_copies_a_checksum_verified_immutable_snapshot(ingest_session):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Snapshot text')

    publish_run(ingest_session, run.id)

    publication = active_publication(ingest_session, 'target')
    snapshot = ingest_session.scalar(select(ScripturePublicationVerse).where(
        ScripturePublicationVerse.publication_id == publication.id
    ))
    staged = ingest_session.scalar(select(StagedScriptureVerse).where(
        StagedScriptureVerse.run_id == run.id
    ))
    assert (
        snapshot.work_id,
        snapshot.source_book,
        snapshot.chapter,
        snapshot.verse,
        snapshot.normalized_text,
        snapshot.source_locator,
        snapshot.row_checksum,
    ) == (
        staged.work_id,
        staged.source_book,
        staged.chapter,
        staged.verse,
        staged.normalized_text,
        staged.source_locator,
        staged.row_checksum,
    )


def test_publish_blocks_staged_checksum_mismatch_before_mutation(ingest_session):
    from app.library.ingest.publish import PublicationBlocked, publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Corrupt staging')
    staged = ingest_session.scalar(select(StagedScriptureVerse).where(
        StagedScriptureVerse.run_id == run.id
    ))
    staged.row_checksum = '0' * 64
    ingest_session.flush()

    with pytest.raises(PublicationBlocked, match='checksum'):
        publish_run(ingest_session, run.id)

    assert legacy_rows(ingest_session, 'target') == []
    assert active_publication(ingest_session, 'target') is None
    assert run.status == 'verified'


def test_publish_refuses_missing_legacy_schema_before_state_changes(ingest_session):
    from app.library.ingest.publish import PublicationBlocked, publish_run
    from .conftest import make_ingest_run

    run = make_ingest_run(ingest_session, 'target', 'Text')

    with pytest.raises(PublicationBlocked, match='biblical_texts'):
        publish_run(ingest_session, run.id)

    assert run.status == 'verified'
    assert active_publication(ingest_session, 'target') is None


def test_rollback_restores_immediately_previous_rows_and_refuses_to_oscillate(ingest_session):
    from app.library.ingest.publish import RollbackUnavailable, publish_run, rollback_edition
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    old = make_ingest_run(ingest_session, 'target', 'Old exact text')
    set_run_manifest(old, name='Old reviewed edition', reading_language='English')
    publish_run(ingest_session, old.id)
    new = make_ingest_run(ingest_session, 'target', 'New exact text')
    set_run_manifest(new, name='New reviewed edition', reading_language="Ge'ez")
    publish_run(ingest_session, new.id)
    assert ingest_session.get(TextEdition, 'target').name == 'New reviewed edition'

    result = rollback_edition(ingest_session, 'target')

    assert result.restored_run_id == old.id
    assert result.displaced_run_id == new.id
    assert result.publication_version == 3
    assert legacy_rows(ingest_session, 'target') == [
        ('Genesis', 1, 1, 'Old exact text', 'target')
    ]
    active = active_publication(ingest_session, 'target')
    assert (active.run_id, active.previous_run_id) == (old.id, None)
    assert old.status == 'published' and new.status == 'rolled_back'
    restored_edition = ingest_session.get(TextEdition, 'target')
    assert (restored_edition.name, restored_edition.reading_language) == (
        'Old reviewed edition', 'English'
    )
    assert old.source_checksum in ingest_session.scalar(select(EditionCoverage.note).where(
        EditionCoverage.edition_code == 'target'
    ))
    assert len(ingest_session.scalars(select(ScripturePublication).where(
        ScripturePublication.edition_code == 'target', ScripturePublication.active.is_(True)
    )).all()) == 1
    with pytest.raises(RollbackUnavailable, match='distinct prior'):
        rollback_edition(ingest_session, 'target')
    assert active_publication(ingest_session, 'target').run_id == old.id


@pytest.mark.parametrize('corruption', ['error_count', 'error_finding'])
def test_rollback_rechecks_restored_run_error_gate_before_mutation(
    ingest_session, corruption
):
    from app.library.ingest.models import ScriptureValidationFinding
    from app.library.ingest.publish import PublicationBlocked, publish_run, rollback_edition
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    old = make_ingest_run(ingest_session, 'target', 'Old text')
    set_run_manifest(old, name='Old edition')
    publish_run(ingest_session, old.id)
    new = make_ingest_run(ingest_session, 'target', 'New text')
    set_run_manifest(new, name='New edition')
    publish_run(ingest_session, new.id)
    if corruption == 'error_count':
        old.error_count = 1
    else:
        ingest_session.add(ScriptureValidationFinding(
            run_id=old.id,
            severity='error',
            code='rollback_audit_error',
            message='Restored run failed a later audit.',
        ))
    ingest_session.flush()
    before_publication = active_publication(ingest_session, 'target')
    before_coverage = ingest_session.scalar(select(EditionCoverage.note).where(
        EditionCoverage.edition_code == 'target'
    ))

    with pytest.raises(PublicationBlocked, match='error'):
        rollback_edition(ingest_session, 'target')

    assert active_publication(ingest_session, 'target').id == before_publication.id
    assert legacy_rows(ingest_session, 'target')[0].text == 'New text'
    assert ingest_session.get(TextEdition, 'target').name == 'New edition'
    assert ingest_session.scalar(select(EditionCoverage.note).where(
        EditionCoverage.edition_code == 'target'
    )) == before_coverage


def test_rollback_uses_snapshot_after_old_staging_is_mutated_and_deleted(ingest_session):
    from app.library.ingest.publish import publish_run, rollback_edition
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    old = make_ingest_run(ingest_session, 'target', 'Immutable old text')
    publish_run(ingest_session, old.id)
    old_staged = ingest_session.scalar(select(StagedScriptureVerse).where(
        StagedScriptureVerse.run_id == old.id
    ))
    old_staged.normalized_text = 'Tampered staging text'
    ingest_session.flush()
    ingest_session.execute(delete(StagedScriptureVerse).where(
        StagedScriptureVerse.run_id == old.id
    ))
    new = make_ingest_run(ingest_session, 'target', 'New text')
    publish_run(ingest_session, new.id)

    rollback_edition(ingest_session, 'target')

    assert legacy_rows(ingest_session, 'target') == [
        ('Genesis', 1, 1, 'Immutable old text', 'target')
    ]


def test_corrupt_snapshot_blocks_rollback_without_changes(ingest_session):
    from app.library.ingest.publish import PublicationBlocked, publish_run, rollback_edition
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    old = make_ingest_run(ingest_session, 'target', 'Old text')
    publish_run(ingest_session, old.id)
    old_publication = active_publication(ingest_session, 'target')
    snapshot = ingest_session.scalar(select(ScripturePublicationVerse).where(
        ScripturePublicationVerse.publication_id == old_publication.id
    ))
    snapshot.row_checksum = '0' * 64
    ingest_session.flush()
    new = make_ingest_run(ingest_session, 'target', 'Current text')
    publish_run(ingest_session, new.id)
    current = active_publication(ingest_session, 'target')
    rows_before = legacy_rows(ingest_session, 'target')

    with pytest.raises(PublicationBlocked, match='snapshot.*checksum'):
        rollback_edition(ingest_session, 'target')

    assert legacy_rows(ingest_session, 'target') == rows_before
    assert active_publication(ingest_session, 'target').id == current.id
    assert new.status == 'published'


def test_rollback_walks_five_version_lineage_without_oscillation(ingest_session):
    from app.library.ingest.publish import RollbackUnavailable, publish_run, rollback_edition
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    runs = [make_ingest_run(ingest_session, 'target', text_value) for text_value in ('A', 'B', 'C')]
    for run in runs:
        publish_run(ingest_session, run.id)

    rollback_edition(ingest_session, 'target')
    rollback_edition(ingest_session, 'target')

    history = ingest_session.scalars(select(ScripturePublication).where(
        ScripturePublication.edition_code == 'target'
    ).order_by(ScripturePublication.publication_version)).all()
    assert [publication.run_id for publication in history] == [
        runs[0].id, runs[1].id, runs[2].id, runs[1].id, runs[0].id
    ]
    assert [publication.previous_run_id for publication in history] == [
        None, runs[0].id, runs[1].id, runs[0].id, None
    ]
    assert [publication.active for publication in history] == [False, False, False, False, True]
    assert [run.status for run in runs] == ['published', 'rolled_back', 'rolled_back']
    assert all(ingest_session.scalar(select(ScripturePublicationVerse.id).where(
        ScripturePublicationVerse.publication_id == publication.id
    )) is not None for publication in history)
    with pytest.raises(RollbackUnavailable):
        rollback_edition(ingest_session, 'target')


def test_service_owned_transaction_persists_after_reopen(test_settings):
    from app.application import create_application
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    application = create_application(test_settings)
    factory = application.state.session_factory
    with factory() as setup:
        create_legacy_texts(setup)
        run = make_ingest_run(setup, 'target', 'Durable text')
        setup.commit()
        run_id = run.id
    with factory() as service_session:
        assert not service_session.in_transaction()
        publish_run(service_session, run_id)
        assert not service_session.in_transaction()
    with factory() as reopened:
        assert legacy_rows(reopened, 'target') == [
            ('Genesis', 1, 1, 'Durable text', 'target')
        ]
        assert active_publication(reopened, 'target').run_id == run_id
        assert reopened.scalar(select(EditionCoverage.id).where(
            EditionCoverage.edition_code == 'target'
        )) is not None


def test_caller_rollback_removes_successful_savepoint_publication(test_settings):
    from app.application import create_application
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    application = create_application(test_settings)
    factory = application.state.session_factory
    with factory() as setup:
        create_legacy_texts(setup)
        run = make_ingest_run(setup, 'target', 'Caller-owned text')
        setup.commit()
        run_id = run.id
    with factory() as caller:
        transaction = caller.begin()
        publish_run(caller, run_id)
        assert legacy_rows(caller, 'target') == [
            ('Genesis', 1, 1, 'Caller-owned text', 'target')
        ]
        transaction.rollback()
    with factory() as reopened:
        assert legacy_rows(reopened, 'target') == []
        assert active_publication(reopened, 'target') is None
        assert reopened.scalar(select(EditionCoverage.id).where(
            EditionCoverage.edition_code == 'target'
        )) is None


def test_publish_run_not_found_and_rollback_is_scoped_to_its_edition(ingest_session):
    from app.library.ingest.publish import PublicationNotFound, publish_run, rollback_edition
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    other = make_ingest_run(ingest_session, 'other', 'Other edition')
    publish_run(ingest_session, other.id)

    with pytest.raises(PublicationNotFound):
        publish_run(ingest_session, uuid4())
    with pytest.raises(PublicationNotFound):
        rollback_edition(ingest_session, 'target')
    assert active_publication(ingest_session, 'other').run_id == other.id


def test_publish_and_rollback_lock_edition_history_then_runs_in_uuid_order(
    ingest_session, monkeypatch
):
    import app.library.ingest.publish as publisher
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    first = make_ingest_run(ingest_session, 'target', 'First')
    publisher.publish_run(ingest_session, first.id)
    second = make_ingest_run(ingest_session, 'target', 'Second')

    original_edition = publisher._lock_edition
    original_history = publisher._lock_publication_history
    original_runs = publisher._lock_runs
    calls = []

    def lock_edition(session, edition_code):
        calls.append('edition')
        return original_edition(session, edition_code)

    def lock_history(session, edition_code):
        calls.append('history')
        return original_history(session, edition_code)

    def lock_runs(session, run_ids):
        locked = original_runs(session, run_ids)
        calls.append(('runs', tuple(locked)))
        return locked

    monkeypatch.setattr(publisher, '_lock_edition', lock_edition)
    monkeypatch.setattr(publisher, '_lock_publication_history', lock_history)
    monkeypatch.setattr(publisher, '_lock_runs', lock_runs)

    publisher.publish_run(ingest_session, second.id)
    assert calls == [
        'edition',
        'history',
        ('runs', tuple(sorted((first.id, second.id), key=lambda value: value.hex))),
    ]

    third = make_ingest_run(ingest_session, 'target', 'Third')
    calls.clear()
    publisher.publish_run(ingest_session, third.id)
    calls.clear()
    publisher.rollback_edition(ingest_session, 'target')
    assert calls == [
        'edition',
        'history',
        ('runs', tuple(sorted((first.id, second.id, third.id), key=lambda value: value.hex))),
    ]


def test_sqlite_edition_write_lock_serializes_competing_publishers(test_settings):
    import app.library.ingest.publish as publisher
    from app.application import create_application
    from .conftest import make_ingest_run

    application = create_application(test_settings)
    factory = application.state.session_factory
    with factory() as setup:
        create_legacy_texts(setup)
        run = make_ingest_run(setup, 'target', 'Competing text')
        setup.commit()
        run_id = run.id

    with factory() as first, factory() as competing:
        competing.connection().exec_driver_sql('PRAGMA busy_timeout=50')
        outer = first.begin()
        publisher._lock_edition(first, 'target')

        with pytest.raises(publisher.PublicationConflict, match='Concurrent publication'):
            publisher.publish_run(competing, run_id)

        outer.rollback()
    with factory() as reopened:
        assert active_publication(reopened, 'target') is None
        assert legacy_rows(reopened, 'target') == []


def test_only_recognized_publication_integrity_races_are_translated(
    ingest_session, monkeypatch
):
    import app.library.ingest.publish as publisher
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    run = make_ingest_run(ingest_session, 'target', 'Conflict text')

    def recognized_race(*_args, **_kwargs):
        raise IntegrityError(
            'insert',
            {},
            sqlite3.IntegrityError(
                'UNIQUE constraint failed: scripture_publications.edition_code, '
                'scripture_publications.publication_version'
            ),
        )

    monkeypatch.setattr(publisher, '_copy_snapshot', recognized_race)
    with pytest.raises(publisher.PublicationConflict, match='Concurrent publication'):
        publisher.publish_run(ingest_session, run.id)

    def unrelated_integrity_error(*_args, **_kwargs):
        raise IntegrityError(
            'insert', {}, sqlite3.IntegrityError('FOREIGN KEY constraint failed')
        )

    monkeypatch.setattr(publisher, '_copy_snapshot', unrelated_integrity_error)
    with pytest.raises(IntegrityError, match='FOREIGN KEY'):
        publisher.publish_run(ingest_session, run.id)
