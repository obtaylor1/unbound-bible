from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.commentary.ingest.types import NormalizedCommentaryEntry
from app.commentary.models import (
    CommentaryEdition,
    CommentaryEntry,
    CommentaryImportRun,
    CommentaryPublication,
    CommentaryValidationFinding,
    StagedCommentaryEntry,
)


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
        'by_work': {'genesis': {'chapters': 1, 'entries': 1}},
    }
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
    assert [(entry.body, entry.position, entry.row_checksum) for entry in entries] == [
        (row.body, row.position, row.row_checksum) for row in rows
    ]


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
