from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from types import MappingProxyType

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.commentary.ingest.types import NormalizedCommentaryEntry
from app.commentary.models import (
    CommentaryEdition,
    CommentaryEntry,
    CommentaryImportRun,
    CommentaryPublication,
    CommentaryValidationFinding,
    StagedCommentaryEntry,
)
from app.database import Base, ensure_sqlite_foreign_keys
from app.library.seed import seed_ethiopian_canon


def _row(*, body='Commentary text.', position=0, start=1):
    return NormalizedCommentaryEntry(
        'genesis', 1, start, start, 'verse', None, body,
        f'provider:GEN.1.{start}', position,
    )


def _metadata(**overrides):
    value = {'dataset_version': '2026-08-04', 'expected_books': ['genesis']}
    value.update(overrides)
    return value


def _stage(session, source, rows=None, **metadata):
    from app.commentary.ingest.publish import stage_bundle

    return stage_bundle(
        session,
        source_id=source.id,
        source_checksum='b' * 64,
        metadata_snapshot=_metadata(**metadata),
        rows=rows or [_row()],
    )


def _verified(session, source, rows=None, **metadata):
    from app.commentary.ingest.publish import validate_run

    run = _stage(session, source, rows, **metadata)
    return validate_run(session, run.id)


def test_stage_bundle_snapshots_all_normalized_scalars_without_committing(
    commentary_session, commentary_source,
):
    metadata = _metadata(nested={'reviewed': True})
    row = NormalizedCommentaryEntry(
        'genesis', 1, 2, 4, 'verse_range', 'A heading', 'Body\n\nSecond paragraph.',
        'provider:GEN.1.2-4', 7,
    )

    from app.commentary.ingest.publish import stage_bundle

    run = stage_bundle(
        commentary_session, source_id=commentary_source.id,
        source_checksum='c' * 64, metadata_snapshot=metadata, rows=[row],
    )
    staged = commentary_session.scalar(
        select(StagedCommentaryEntry).where(StagedCommentaryEntry.run_id == run.id)
    )

    assert run.status == 'staged'
    assert run.staged_count == 1
    assert run.source_checksum == 'c' * 64
    assert run.metadata_snapshot == metadata
    assert (
        staged.work_id, staged.chapter, staged.verse_start, staged.verse_end,
        staged.entry_type, staged.heading, staged.body, staged.source_locator,
        staged.position, staged.row_checksum,
    ) == (
        row.work_id, row.chapter, row.verse_start, row.verse_end,
        row.entry_type, row.heading, row.body, row.source_locator,
        row.position, row.row_checksum,
    )
    assert commentary_session.in_transaction()
    metadata['nested']['reviewed'] = False
    assert run.metadata_snapshot['nested']['reviewed'] is True


def test_stage_bundle_accepts_any_mapping_snapshot(commentary_session, commentary_source):
    from app.commentary.ingest.publish import stage_bundle

    metadata = MappingProxyType(_metadata(nested=MappingProxyType({'reviewed': True})))
    run = stage_bundle(
        commentary_session, source_id=commentary_source.id, source_checksum='f' * 64,
        metadata_snapshot=metadata, rows=[_row()],
    )

    assert run.metadata_snapshot == {
        'dataset_version': '2026-08-04', 'expected_books': ['genesis'],
        'nested': {'reviewed': True},
    }


@pytest.mark.parametrize('checksum', ['x' * 64, 'a' * 63, True])
def test_stage_bundle_rejects_invalid_checksum(commentary_session, commentary_source, checksum):
    from app.commentary.ingest.publish import stage_bundle

    with pytest.raises(ValueError, match='checksum'):
        stage_bundle(
            commentary_session, source_id=commentary_source.id,
            source_checksum=checksum, metadata_snapshot=_metadata(), rows=[_row()],
        )


def test_stage_bundle_rejects_missing_source_and_non_normalized_rows(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import stage_bundle

    with pytest.raises(ValueError, match='source'):
        stage_bundle(
            commentary_session, source_id='missing', source_checksum='a' * 64,
            metadata_snapshot=_metadata(), rows=[_row()],
        )
    with pytest.raises(ValueError, match='NormalizedCommentaryEntry'):
        stage_bundle(
            commentary_session, source_id=commentary_source.id, source_checksum='a' * 64,
            metadata_snapshot=_metadata(), rows=[object()],
        )


def test_validate_run_replaces_findings_and_saves_coverage(commentary_session, commentary_source):
    from app.commentary.ingest.publish import validate_run

    run = _stage(commentary_session, commentary_source)
    commentary_session.add(CommentaryValidationFinding(
        run_id=run.id, severity='error', code='old', message='Old finding.',
    ))
    commentary_session.flush()

    result = validate_run(commentary_session, run.id)
    findings = commentary_session.scalars(select(CommentaryValidationFinding).where(
        CommentaryValidationFinding.run_id == run.id
    )).all()

    assert result is run
    assert run.status == 'verified'
    assert run.error_count == 0
    assert run.warning_count == 2
    assert run.metadata_snapshot['coverage'] == {
        'books': 1, 'chapters': 1, 'entries': 1,
        'by_work': {
            'genesis': {'chapters': 1, 'chapter_numbers': [1], 'entries': 1},
        },
    }
    assert len(run.metadata_snapshot['validation_manifest']) == 64
    assert {finding.code for finding in findings} == {'missing_book_intro', 'missing_chapter_intro'}


def test_validate_run_with_errors_is_validated_not_verified(commentary_session, commentary_source):
    from app.commentary.ingest.publish import validate_run

    run = _stage(commentary_session, commentary_source, expected_books=['genesis', 'exodus'])
    validate_run(commentary_session, run.id)

    assert run.status == 'validated'
    assert run.error_count == 1
    assert 'missing_expected_book' in {
        item.code for item in commentary_session.scalars(select(CommentaryValidationFinding).where(
            CommentaryValidationFinding.run_id == run.id
        ))
    }


def test_validate_run_uses_previous_published_coverage(commentary_session, commentary_source):
    from app.commentary.ingest.publish import publish_run, validate_run

    old_rows = [_row(start=index, position=index) for index in range(1, 101)]
    old = _verified(commentary_session, commentary_source, old_rows)
    publish_run(commentary_session, old.id)
    new = _stage(commentary_session, commentary_source, [_row(start=index, position=index) for index in range(1, 95)])

    validate_run(commentary_session, new.id)

    assert new.status == 'validated'
    assert 'record_count_regression' in {
        item.code for item in commentary_session.scalars(select(CommentaryValidationFinding).where(
            CommentaryValidationFinding.run_id == new.id
        ))
    }


def test_validate_run_accepts_legacy_active_edition_coverage(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import validate_run

    edition = CommentaryEdition(
        source_id=commentary_source.id, dataset_version='legacy', source_checksum='a' * 64,
        status='published', record_count=1,
        coverage={
            'books': 1, 'chapters': 1, 'entries': 1,
            'by_work': {'genesis': {'chapters': 1, 'entries': 1}},
        },
    )
    commentary_session.add(edition)
    commentary_session.flush()
    commentary_session.add(CommentaryPublication(
        source_id=commentary_source.id, edition_id=edition.id, version=1, active=True,
    ))
    commentary_session.flush()
    run = _stage(commentary_session, commentary_source)

    validate_run(commentary_session, run.id)

    assert run.status == 'verified'
    assert run.metadata_snapshot['coverage']['by_work']['genesis'] == {
        'chapters': 1, 'chapter_numbers': [1], 'entries': 1,
    }


def test_publish_rejects_legacy_verified_coverage_until_revalidated(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    snapshot = dict(run.metadata_snapshot)
    snapshot['coverage'] = {
        'books': 1, 'chapters': 1, 'entries': 1,
        'by_work': {'genesis': {'chapters': 1, 'entries': 1}},
    }
    run.metadata_snapshot = snapshot
    commentary_session.flush()

    with pytest.raises(ValueError, match='revalidated'):
        publish_run(commentary_session, run.id)


def test_validate_run_rejects_missing_run_invalid_status_and_bad_metadata(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import validate_run

    with pytest.raises(ValueError, match='not found'):
        validate_run(commentary_session, uuid4())
    run = _stage(commentary_session, commentary_source)
    run.status = 'published'
    commentary_session.flush()
    with pytest.raises(ValueError, match='staged or validated'):
        validate_run(commentary_session, run.id)
    run.status = 'staged'
    run.metadata_snapshot = {'dataset_version': '1'}
    commentary_session.flush()
    with pytest.raises(ValueError, match='expected_books'):
        validate_run(commentary_session, run.id)


def test_staged_and_validated_runs_are_not_public(commentary_session, commentary_source):
    from app.commentary.ingest.publish import validate_run

    run = _stage(commentary_session, commentary_source, expected_books=['genesis', 'exodus'])
    assert commentary_session.scalar(select(CommentaryPublication)) is None
    validate_run(commentary_session, run.id)
    assert run.status == 'validated'
    assert commentary_session.scalar(select(CommentaryPublication)) is None
    assert commentary_session.scalar(select(CommentaryEdition)) is None
    assert commentary_session.scalar(select(CommentaryEntry)) is None


def test_publish_copies_exact_rows_coverage_and_checksum(commentary_session, commentary_source):
    from app.commentary.ingest.publish import publish_run

    rows = [_row(body='First.', position=4, start=1), _row(body='Second.', position=9, start=2)]
    run = _verified(commentary_session, commentary_source, rows)
    publication = publish_run(commentary_session, run.id)
    edition = commentary_session.get(CommentaryEdition, publication.edition_id)
    entries = commentary_session.scalars(select(CommentaryEntry).where(
        CommentaryEntry.edition_id == edition.id
    ).order_by(CommentaryEntry.position)).all()

    assert publication.active is True
    assert publication.source_id == commentary_source.id
    assert publication.version == 1
    assert run.status == 'published'
    assert edition.status == 'published'
    assert edition.dataset_version == str(run.id)
    assert edition.source_checksum == run.source_checksum
    assert edition.record_count == 2
    assert edition.coverage == run.metadata_snapshot['coverage']
    assert [(
        entry.work_id, entry.chapter, entry.verse_start, entry.verse_end,
        entry.entry_type, entry.heading, entry.body, entry.source_locator,
        entry.position, entry.row_checksum,
    ) for entry in entries] == [(
        row.work_id, row.chapter, row.verse_start, row.verse_end,
        row.entry_type, row.heading, row.body, row.source_locator,
        row.position, row.row_checksum,
    ) for row in rows
    ]


def test_publish_accepts_legitimate_rows_staged_out_of_position_order(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    rows = [_row(body='Position nine.', position=9, start=2), _row(body='Position four.', position=4)]
    run = _verified(commentary_session, commentary_source, rows)

    publication = publish_run(commentary_session, run.id)

    entries = commentary_session.scalars(select(CommentaryEntry).where(
        CommentaryEntry.edition_id == publication.edition_id
    ).order_by(CommentaryEntry.position)).all()
    assert [(entry.position, entry.body) for entry in entries] == [
        (4, 'Position four.'), (9, 'Position nine.'),
    ]


@pytest.mark.parametrize('finish', ['close', 'rollback'])
def test_publish_is_rolled_back_when_fresh_caller_does_not_commit(
    commentary_session, commentary_source, finish,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    commentary_session.commit()
    factory = sessionmaker(bind=commentary_session.bind, autoflush=False, expire_on_commit=False)

    caller = factory()
    try:
        publish_run(caller, run.id)
        if finish == 'rollback':
            caller.rollback()
    finally:
        caller.close()

    with factory() as observer:
        assert observer.scalar(select(CommentaryPublication)) is None
        assert observer.scalar(select(CommentaryEdition)) is None
        assert observer.get(CommentaryImportRun, run.id).status == 'verified'


def test_publish_switches_active_publication_and_versions_monotonically(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    first = publish_run(commentary_session, _verified(commentary_session, commentary_source).id)
    second = publish_run(
        commentary_session,
        _verified(commentary_session, commentary_source, [_row(body='New text.')], dataset_version='v2').id,
    )

    assert first.active is False
    assert second.active is True
    assert (first.version, second.version) == (1, 2)
    assert commentary_session.scalar(select(func.count()).select_from(CommentaryEdition)) == 2


def test_publish_rejects_missing_nonverified_error_and_duplicate_runs(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    with pytest.raises(ValueError, match='not found'):
        publish_run(commentary_session, uuid4())
    staged = _stage(commentary_session, commentary_source)
    with pytest.raises(ValueError, match='error-free verified'):
        publish_run(commentary_session, staged.id)
    verified = _verified(commentary_session, commentary_source)
    verified.error_count = 1
    commentary_session.flush()
    with pytest.raises(ValueError, match='error-free verified'):
        publish_run(commentary_session, verified.id)
    verified.error_count = 0
    publication = publish_run(commentary_session, verified.id)
    with pytest.raises(ValueError, match='already been published'):
        publish_run(commentary_session, verified.id)
    assert publication.active is True


def test_publish_checks_persisted_error_findings_even_if_counter_is_corrupt(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    commentary_session.add(CommentaryValidationFinding(
        run_id=run.id, severity='error', code='late_error', message='Late blocker.',
    ))
    commentary_session.flush()

    with pytest.raises(ValueError, match='error-free verified'):
        publish_run(commentary_session, run.id)
    assert commentary_session.scalar(select(CommentaryPublication)) is None


def test_publish_rejects_staged_row_changed_after_verification(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    staged = commentary_session.scalar(select(StagedCommentaryEntry).where(
        StagedCommentaryEntry.run_id == run.id
    ))
    staged.body = 'Changed after validation.'
    commentary_session.flush()

    with pytest.raises(ValueError, match='changed after validation'):
        publish_run(commentary_session, run.id)
    assert commentary_session.scalar(select(CommentaryPublication)) is None


def test_publish_rejects_scalar_and_checksum_changed_together_after_verification(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    staged = commentary_session.scalar(select(StagedCommentaryEntry).where(
        StagedCommentaryEntry.run_id == run.id
    ))
    changed = _row(body='Coordinated replacement.')
    staged.body = changed.body
    staged.row_checksum = changed.row_checksum
    commentary_session.flush()

    with pytest.raises(ValueError, match='manifest'):
        publish_run(commentary_session, run.id)
    assert commentary_session.scalar(select(CommentaryPublication)) is None


def test_publish_manifest_rejects_position_reordering_with_matching_checksum(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    staged = commentary_session.scalar(select(StagedCommentaryEntry).where(
        StagedCommentaryEntry.run_id == run.id
    ))
    reordered = _row(position=8)
    staged.position = reordered.position
    staged.row_checksum = reordered.row_checksum
    commentary_session.flush()

    with pytest.raises(ValueError, match='manifest'):
        publish_run(commentary_session, run.id)
    assert commentary_session.scalar(select(CommentaryPublication)) is None


@pytest.mark.parametrize('mutation', ['source_checksum', 'coverage', 'expected_books'])
def test_publish_rejects_verified_run_metadata_mutation(
    commentary_session, commentary_source, mutation,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    snapshot = dict(run.metadata_snapshot)
    if mutation == 'source_checksum':
        run.source_checksum = '0' * 64
    elif mutation == 'coverage':
        snapshot['coverage'] = {
            'books': 1, 'chapters': 1, 'entries': 99,
            'by_work': {
                'genesis': {
                    'chapters': 1, 'chapter_numbers': [1], 'entries': 99,
                },
            },
        }
        run.metadata_snapshot = snapshot
    else:
        snapshot['expected_books'] = ['genesis', 'exodus']
        run.metadata_snapshot = snapshot
    commentary_session.flush()

    with pytest.raises(ValueError, match='manifest'):
        publish_run(commentary_session, run.id)


def test_publish_rejects_verified_run_reassigned_to_another_existing_source(
    commentary_session, commentary_source, make_commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    other = make_commentary_source('other-existing-source')
    run.source_id = other.id
    commentary_session.flush()

    with pytest.raises(ValueError, match='manifest'):
        publish_run(commentary_session, run.id)
    assert commentary_session.scalar(select(CommentaryPublication)) is None
    assert commentary_session.scalar(select(CommentaryEdition)) is None


def test_publish_copies_reconstructed_normalized_values_not_raw_staging_scalars(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    run = _verified(commentary_session, commentary_source)
    staged = commentary_session.scalar(select(StagedCommentaryEntry).where(
        StagedCommentaryEntry.run_id == run.id
    ))
    # This raw DB value normalizes to the originally verified body and therefore
    # retains the same semantic manifest and checksum.
    staged.body = '  Commentary   text.  '
    commentary_session.flush()

    publication = publish_run(commentary_session, run.id)
    entry = commentary_session.scalar(select(CommentaryEntry).where(
        CommentaryEntry.edition_id == publication.edition_id
    ))
    assert entry.body == 'Commentary text.'


def test_publish_failure_rolls_back_its_savepoint_and_preserves_previous_active(
    commentary_session, commentary_source, monkeypatch,
):
    import app.commentary.ingest.publish as publisher

    previous = publisher.publish_run(
        commentary_session, _verified(commentary_session, commentary_source).id
    )
    run = _verified(commentary_session, commentary_source, [_row(body='Replacement.')], dataset_version='v2')
    original_copy = publisher._copy_staged_entries

    def fail_after_copy(*args, **kwargs):
        original_copy(*args, **kwargs)
        raise RuntimeError('injected publication failure')

    monkeypatch.setattr(publisher, '_copy_staged_entries', fail_after_copy)
    with pytest.raises(RuntimeError, match='injected'):
        publisher.publish_run(commentary_session, run.id)

    commentary_session.expire_all()
    active = commentary_session.scalar(select(CommentaryPublication).where(
        CommentaryPublication.source_id == commentary_source.id,
        CommentaryPublication.active.is_(True),
    ))
    assert active.id == previous.id
    assert commentary_session.get(CommentaryImportRun, run.id).status == 'verified'
    assert commentary_session.scalar(select(func.count()).select_from(CommentaryEdition)) == 1


def test_failure_after_deactivation_restores_every_publication_write(
    commentary_session, commentary_source, monkeypatch,
):
    import app.commentary.ingest.publish as publisher

    previous = publisher.publish_run(
        commentary_session, _verified(commentary_session, commentary_source).id
    )
    run = _verified(
        commentary_session, commentary_source, [_row(body='Replacement.')], dataset_version='v2'
    )
    original_flush = commentary_session.flush

    def fail_final_flush(objects=None):
        pending_publication = any(
            isinstance(item, CommentaryPublication) and item.id is None
            for item in commentary_session.new
        )
        if previous.active is False and pending_publication:
            raise RuntimeError('injected final publication failure')
        return original_flush(objects)

    monkeypatch.setattr(commentary_session, 'flush', fail_final_flush)
    with pytest.raises(RuntimeError, match='final publication'):
        publisher.publish_run(commentary_session, run.id)

    commentary_session.expire_all()
    assert commentary_session.get(CommentaryPublication, previous.id).active is True
    assert commentary_session.get(CommentaryImportRun, run.id).status == 'verified'
    assert commentary_session.scalar(select(func.count()).select_from(CommentaryEdition)) == 1
    assert commentary_session.scalar(select(func.count()).select_from(CommentaryEntry)) == 1


def test_database_constraints_protect_against_duplicate_active_or_version(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run

    active = publish_run(commentary_session, _verified(commentary_session, commentary_source).id)
    commentary_session.add(CommentaryPublication(
        source_id=commentary_source.id, edition_id=active.edition_id,
        version=active.version, active=True,
    ))
    with pytest.raises(IntegrityError):
        commentary_session.flush()
    commentary_session.rollback()


def test_rollback_creates_new_active_version_for_selected_prior_edition(
    commentary_session, commentary_source,
):
    from app.commentary.ingest.publish import publish_run, rollback_publication

    previous = publish_run(commentary_session, _verified(commentary_session, commentary_source).id)
    previous_entry = commentary_session.scalar(select(CommentaryEntry).where(
        CommentaryEntry.edition_id == previous.edition_id
    ))
    current = publish_run(
        commentary_session,
        _verified(commentary_session, commentary_source, [_row(body='Replacement.')], dataset_version='v2').id,
    )
    restored = rollback_publication(commentary_session, current.id)

    assert previous.active is False
    assert current.active is False
    assert restored.active is True
    assert restored.edition_id == previous.edition_id
    assert restored.source_id == previous.source_id
    assert restored.version == 3
    assert commentary_session.get(CommentaryEntry, previous_entry.id).body == 'Commentary text.'
    assert commentary_session.scalar(select(func.count()).select_from(CommentaryEdition)) == 2
    assert commentary_session.get(CommentaryEdition, previous.edition_id).status == 'published'
    assert commentary_session.get(CommentaryEdition, current.edition_id).status == 'published'


@pytest.mark.parametrize('finish', ['close', 'rollback'])
def test_rollback_is_rolled_back_when_fresh_caller_does_not_commit(
    commentary_session, commentary_source, finish,
):
    from app.commentary.ingest.publish import publish_run, rollback_publication

    publish_run(commentary_session, _verified(commentary_session, commentary_source).id)
    current = publish_run(
        commentary_session,
        _verified(commentary_session, commentary_source, [_row(body='Current.')]).id,
    )
    commentary_session.commit()
    factory = sessionmaker(bind=commentary_session.bind, autoflush=False, expire_on_commit=False)

    caller = factory()
    try:
        rollback_publication(caller, current.id)
        if finish == 'rollback':
            caller.rollback()
    finally:
        caller.close()

    with factory() as observer:
        active = observer.scalar(select(CommentaryPublication).where(
            CommentaryPublication.active.is_(True)
        ))
        assert active.id == current.id
        assert observer.scalar(select(func.count()).select_from(CommentaryPublication)) == 2


def _race_database(tmp_path):
    path = tmp_path / 'commentary-race.db'
    engine = create_engine(
        f'sqlite:///{path}',
        connect_args={'check_same_thread': False, 'timeout': 15},
    )
    ensure_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        seed_ethiopian_canon(session)
        from app.commentary.models import CommentarySource
        session.add(CommentarySource(
            id='race-source', title='Race Source', abbreviation='RS', author='Author',
            publication_period='1900', tradition='Test', language='eng',
            license_spdx='LicenseRef-Public-Domain',
            license_url='https://creativecommons.org/publicdomain/mark/1.0/',
            attribution='Public domain.', provenance_url='https://example.test/source',
        ))
        session.commit()
        source = session.get(CommentarySource, 'race-source')
        first = _verified(session, source, [_row(body='First.')])
        second = _verified(session, source, [_row(body='Second.')])
        session.commit()
        ids = first.id, second.id
    return engine, factory, ids


def test_independent_sessions_publish_two_runs_with_one_monotonic_active_result(tmp_path):
    from app.commentary.ingest.publish import publish_run

    engine, factory, run_ids = _race_database(tmp_path)
    barrier = Barrier(2)

    def publish(run_id):
        with factory() as session:
            barrier.wait()
            publication = publish_run(session, run_id)
            session.commit()
            return publication.id

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            publication_ids = list(executor.map(publish, run_ids))
        with factory() as observer:
            publications = observer.scalars(select(CommentaryPublication).order_by(
                CommentaryPublication.version
            )).all()
            assert [item.version for item in publications] == [1, 2]
            assert sum(item.active for item in publications) == 1
            assert {item.id for item in publications} == set(publication_ids)
            assert observer.scalar(select(func.count()).select_from(CommentaryEdition)) == 2
            assert observer.scalar(select(func.count()).select_from(CommentaryEntry)) == 2
            assert set(observer.scalars(select(CommentaryImportRun.status))) == {'published'}
    finally:
        engine.dispose()


def test_independent_sessions_duplicate_publish_has_one_winner_and_no_orphans(tmp_path):
    from app.commentary.ingest.publish import publish_run

    engine, factory, run_ids = _race_database(tmp_path)
    run_id = run_ids[0]
    barrier = Barrier(2)

    def publish():
        with factory() as session:
            barrier.wait()
            try:
                publication = publish_run(session, run_id)
                session.commit()
                return ('published', publication.id)
            except ValueError as exc:
                session.rollback()
                return ('rejected', type(exc).__name__)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: publish(), range(2)))
        assert sorted(item[0] for item in outcomes) == ['published', 'rejected']
        with factory() as observer:
            active = observer.scalars(select(CommentaryPublication)).all()
            assert len(active) == 1 and active[0].active and active[0].version == 1
            assert observer.scalar(select(func.count()).select_from(CommentaryEdition)) == 1
            assert observer.scalar(select(func.count()).select_from(CommentaryEntry)) == 1
            assert observer.get(CommentaryImportRun, run_id).status == 'published'
            assert observer.get(CommentaryImportRun, run_ids[1]).status == 'verified'
    finally:
        engine.dispose()


def _prepare_publish_rollback_race(factory):
    with factory() as session:
        from app.commentary.models import CommentarySource
        source = session.get(CommentarySource, 'race-source')
        first = _verified(session, source, [_row(body='First.')])
        from app.commentary.ingest.publish import publish_run
        publish_run(session, first.id)
        second = _verified(session, source, [_row(body='Second.')])
        current = publish_run(session, second.id)
        requested = _verified(session, source, [_row(body='Third.')])
        session.commit()
        return current.id, requested.id


def _run_publish_rollback_race(factory, current_id, requested_id):
    from app.commentary.ingest.publish import publish_run, rollback_publication

    barrier = Barrier(2)

    def operation(kind):
        with factory() as session:
            barrier.wait()
            try:
                value = (
                    publish_run(session, requested_id)
                    if kind == 'publish'
                    else rollback_publication(session, current_id)
                )
                session.commit()
                return ('completed', value.id)
            except ValueError as exc:
                session.rollback()
                return ('rejected', str(exc))
            except OperationalError as exc:
                session.rollback()
                return ('database-error', str(exc))

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(operation, ('publish', 'rollback')))
    return outcomes


def _assert_publish_rollback_race_consistent(factory, requested_id, outcomes):
    assert 'database-error' not in {item[0] for item in outcomes}
    assert outcomes[0][0] == 'completed'  # Publishing the distinct verified run always wins eventually.
    with factory() as observer:
        publications = observer.scalars(select(CommentaryPublication).order_by(
            CommentaryPublication.version
        )).all()
        assert [item.version for item in publications] == list(range(1, len(publications) + 1))
        assert sum(item.active for item in publications) == 1
        assert observer.scalar(select(func.count()).select_from(CommentaryEdition)) == 3
        assert observer.scalar(select(func.count()).select_from(CommentaryEntry)) == 3
        requested = observer.get(CommentaryImportRun, requested_id)
        assert requested.status == 'published'
        assert observer.scalar(select(CommentaryEdition).where(
            CommentaryEdition.dataset_version == str(requested.id)
        )) is not None


def test_independent_publish_and_rollback_use_consistent_lock_order(tmp_path):
    engine, factory, _ = _race_database(tmp_path)
    try:
        current_id, requested_id = _prepare_publish_rollback_race(factory)
        outcomes = _run_publish_rollback_race(factory, current_id, requested_id)
        _assert_publish_rollback_race_consistent(factory, requested_id, outcomes)
    finally:
        engine.dispose()


@pytest.mark.skipif(
    not os.environ.get('COMMENTARY_TEST_POSTGRES_DSN'),
    reason='COMMENTARY_TEST_POSTGRES_DSN is not configured for real PostgreSQL integration tests.',
)
def test_postgresql_publish_and_rollback_are_deadlock_free():
    dsn = os.environ['COMMENTARY_TEST_POSTGRES_DSN']
    schema = f'commentary_test_{uuid4().hex}'
    admin_engine = create_engine(dsn)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(dsn, connect_args={'options': f'-csearch_path={schema}'})
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        Base.metadata.create_all(engine)
        with factory() as session:
            seed_ethiopian_canon(session)
            from app.commentary.models import CommentarySource
            session.add(CommentarySource(
                id='race-source', title='Race Source', abbreviation='RS', author='Author',
                publication_period='1900', tradition='Test', language='eng',
                license_spdx='LicenseRef-Public-Domain',
                license_url='https://creativecommons.org/publicdomain/mark/1.0/',
                attribution='Public domain.', provenance_url='https://example.test/source',
            ))
            session.commit()
        current_id, requested_id = _prepare_publish_rollback_race(factory)
        outcomes = _run_publish_rollback_race(factory, current_id, requested_id)
        _assert_publish_rollback_race_consistent(factory, requested_id, outcomes)
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def test_rollback_rejects_missing_current_or_cross_source_target(
    commentary_session, commentary_source, make_commentary_source,
):
    from app.commentary.ingest.publish import publish_run, rollback_publication

    with pytest.raises(ValueError, match='not found'):
        rollback_publication(commentary_session, 999999)
    unpublished_edition = CommentaryEdition(
        source_id=commentary_source.id, dataset_version='orphan', source_checksum='a' * 64,
        status='published', record_count=0, coverage={},
    )
    commentary_session.add(unpublished_edition)
    commentary_session.flush()
    orphan = CommentaryPublication(
        source_id=commentary_source.id, edition_id=unpublished_edition.id, version=1, active=False,
    )
    commentary_session.add(orphan)
    commentary_session.flush()
    with pytest.raises(ValueError, match='active publication'):
        rollback_publication(commentary_session, orphan.id)

    other = make_commentary_source('other-commentary')
    active = publish_run(commentary_session, _verified(commentary_session, other).id)
    # Corrupting source ownership is also blocked by the deferred composite FK.
    active.source_id = commentary_source.id
    with pytest.raises(IntegrityError):
        commentary_session.commit()
    commentary_session.rollback()


def test_services_never_commit_caller_transaction(commentary_session, commentary_source):
    from app.commentary.ingest.publish import publish_run, rollback_publication, stage_bundle, validate_run

    calls = []
    original_commit = commentary_session.commit

    def forbidden_commit():
        calls.append(True)
        raise AssertionError('service committed caller transaction')

    commentary_session.commit = forbidden_commit
    try:
        run = stage_bundle(
            commentary_session, source_id=commentary_source.id, source_checksum='d' * 64,
            metadata_snapshot=_metadata(), rows=[_row()],
        )
        validate_run(commentary_session, run.id)
        first = publish_run(commentary_session, run.id)
        second_run = stage_bundle(
            commentary_session, source_id=commentary_source.id, source_checksum='e' * 64,
            metadata_snapshot=_metadata(dataset_version='v2'), rows=[_row(body='Second.')],
        )
        validate_run(commentary_session, second_run.id)
        second = publish_run(commentary_session, second_run.id)
        rollback_publication(commentary_session, second.id)
    finally:
        commentary_session.commit = original_commit
    assert calls == []
