from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError


def _entry_values(owner_name, owner_id, work_id, **overrides):
    values = {
        owner_name: owner_id,
        'work_id': work_id,
        'chapter': 1,
        'verse_start': 1,
        'verse_end': 1,
        'entry_type': 'verse',
        'heading': None,
        'body': 'In the beginning',
        'source_locator': 'https://example.test/entry/1',
        'row_checksum': 'b' * 64,
        'position': 0,
    }
    values.update(overrides)
    return values


def test_reversed_verse_range_is_rejected(commentary_session, genesis, make_commentary_edition):
    from app.commentary.models import CommentaryEntry

    edition = make_commentary_edition()
    commentary_session.add(CommentaryEntry(**_entry_values(
        'edition_id', edition.id, genesis, verse_start=4, verse_end=3, entry_type='verse_range',
    )))
    with pytest.raises(IntegrityError):
        commentary_session.flush()


@pytest.mark.parametrize('entry_type, chapter, verse_start, verse_end', [
    ('book_intro', 1, None, None),
    ('chapter_intro', None, None, None),
    ('verse', 1, None, None),
    ('verse', 1, 1, 2),
])
def test_coordinate_type_mismatches_are_rejected(
    commentary_session, genesis, make_commentary_edition, entry_type, chapter, verse_start, verse_end,
):
    from app.commentary.models import CommentaryEntry

    edition = make_commentary_edition()
    with commentary_session.begin_nested():
        commentary_session.add(CommentaryEntry(**_entry_values(
            'edition_id', edition.id, genesis, entry_type=entry_type, chapter=chapter,
            verse_start=verse_start, verse_end=verse_end,
        )))
        with pytest.raises(IntegrityError):
            commentary_session.flush()


def test_invalid_status_severity_and_checksum_lengths_are_rejected(
    commentary_session, commentary_source, genesis, make_commentary_edition,
):
    from app.commentary.models import CommentaryEdition, CommentaryImportRun, CommentaryValidationFinding

    edition = make_commentary_edition()
    invalid_rows = [
        CommentaryEdition(id=uuid4(), source_id=commentary_source.id, dataset_version='bad-status',
                          source_checksum='a' * 64, status='bad', coverage={}),
        CommentaryEdition(id=uuid4(), source_id=commentary_source.id, dataset_version='bad-checksum',
                          source_checksum='a' * 63, status='staged', coverage={}),
        CommentaryImportRun(id=uuid4(), source_id=commentary_source.id, source_checksum='a' * 63,
                            metadata_snapshot={}, status='staged'),
        CommentaryValidationFinding(run_id=uuid4(), severity='info', code='bad', work_id=genesis,
                                    message='not allowed'),
    ]
    for row in invalid_rows:
        with commentary_session.begin_nested():
            commentary_session.add(row)
            with pytest.raises(IntegrityError):
                commentary_session.flush()


@pytest.mark.parametrize('field, value', [
    ('record_count', -1),
    ('position', -1),
    ('chapter', 0),
    ('verse_start', 0),
    ('verse_end', 0),
    ('version', 0),
])
def test_negative_counts_positions_and_nonpositive_coordinates_are_rejected(
    commentary_session, genesis, make_commentary_edition, field, value,
):
    from app.commentary.models import CommentaryEdition, CommentaryEntry, CommentaryPublication

    edition = make_commentary_edition()
    if field == 'record_count':
        row = CommentaryEdition(id=uuid4(), source_id=edition.source_id, dataset_version='negative-count',
                                source_checksum='c' * 64, status='staged', coverage={}, record_count=value)
    elif field == 'version':
        row = CommentaryPublication(source_id=edition.source_id, edition_id=edition.id, version=value)
    else:
        row = CommentaryEntry(**_entry_values('edition_id', edition.id, genesis, **{field: value}))
    with commentary_session.begin_nested():
        commentary_session.add(row)
        with pytest.raises(IntegrityError):
            commentary_session.flush()


@pytest.mark.parametrize('model_name, owner_name', [
    ('CommentaryEntry', 'edition_id'),
    ('StagedCommentaryEntry', 'run_id'),
])
def test_duplicate_entry_identities_include_nullable_coordinates(
    commentary_session, genesis, make_commentary_edition, commentary_source, model_name, owner_name,
):
    from app.commentary.models import CommentaryImportRun, CommentaryEntry, StagedCommentaryEntry

    edition = make_commentary_edition()
    run = CommentaryImportRun(id=uuid4(), source_id=commentary_source.id, source_checksum='d' * 64,
                              metadata_snapshot={}, status='staged')
    commentary_session.add(run)
    commentary_session.flush()
    model = {'CommentaryEntry': CommentaryEntry, 'StagedCommentaryEntry': StagedCommentaryEntry}[model_name]
    owner_id = edition.id if owner_name == 'edition_id' else run.id
    values = _entry_values(owner_name, owner_id, genesis, entry_type='book_intro', chapter=None,
                           verse_start=None, verse_end=None)
    commentary_session.add(model(**values))
    commentary_session.flush()
    with commentary_session.begin_nested():
        commentary_session.add(model(**values))
        with pytest.raises(IntegrityError):
            commentary_session.flush()


def test_duplicate_source_dataset_version_is_rejected(commentary_session, make_commentary_edition):
    from app.commentary.models import CommentaryEdition

    edition = make_commentary_edition()
    with commentary_session.begin_nested():
        commentary_session.add(CommentaryEdition(
            id=uuid4(), source_id=edition.source_id, dataset_version=edition.dataset_version,
            source_checksum='e' * 64, status='staged', coverage={},
        ))
        with pytest.raises(IntegrityError):
            commentary_session.flush()


def test_only_one_active_publication_per_source_allows_inactive_history(
    commentary_session, commentary_source, published_edition, commentary_editions,
):
    from app.commentary.models import CommentaryPublication

    commentary_session.add(CommentaryPublication(
        source_id=commentary_source.id, edition_id=published_edition.id, version=1, active=True,
    ))
    commentary_session.flush()
    with commentary_session.begin_nested():
        commentary_session.add(CommentaryPublication(
            source_id=commentary_source.id, edition_id=commentary_editions[0].id, version=2, active=True,
        ))
        with pytest.raises(IntegrityError):
            commentary_session.flush()
    commentary_session.add(CommentaryPublication(
        source_id=commentary_source.id, edition_id=commentary_editions[0].id, version=2, active=False,
    ))
    commentary_session.flush()


def test_foreign_key_cascade_and_restrict_behavior(commentary_session, commentary_source, genesis, published_edition):
    from app.commentary.models import (
        CommentaryImportRun, CommentaryPublication, CommentaryValidationFinding, StagedCommentaryEntry,
    )

    run = CommentaryImportRun(id=uuid4(), source_id=commentary_source.id, source_checksum='f' * 64,
                              metadata_snapshot={}, status='staged')
    commentary_session.add(run)
    commentary_session.flush()
    commentary_session.add_all([
        StagedCommentaryEntry(**_entry_values('run_id', run.id, genesis)),
        CommentaryValidationFinding(run_id=run.id, severity='warning', code='style', message='Review'),
        CommentaryPublication(source_id=commentary_source.id, edition_id=published_edition.id, version=1),
    ])
    commentary_session.flush()
    commentary_session.execute(delete(CommentaryImportRun).where(CommentaryImportRun.id == run.id))
    commentary_session.flush()
    assert commentary_session.scalar(select(StagedCommentaryEntry.id).where(StagedCommentaryEntry.run_id == run.id)) is None
    assert commentary_session.scalar(select(CommentaryValidationFinding.id).where(CommentaryValidationFinding.run_id == run.id)) is None
    with commentary_session.begin_nested():
        with pytest.raises(IntegrityError):
            commentary_session.execute(
                delete(type(published_edition)).where(type(published_edition).id == published_edition.id)
            )


def test_valid_commentary_rows_flush(commentary_session, commentary_source, genesis, make_commentary_edition):
    from app.commentary.models import (
        CommentaryEntry, CommentaryImportRun, CommentaryPublication, CommentaryValidationFinding,
    )

    edition = make_commentary_edition()
    run = CommentaryImportRun(id=uuid4(), source_id=commentary_source.id, source_checksum='f' * 64,
                              metadata_snapshot={'format': 'test'}, status='validated')
    commentary_session.add_all([
        run,
        CommentaryEntry(**_entry_values('edition_id', edition.id, genesis, entry_type='book_intro',
                                        chapter=None, verse_start=None, verse_end=None, position=0)),
        CommentaryEntry(**_entry_values('edition_id', edition.id, genesis, entry_type='chapter_intro',
                                        chapter=1, verse_start=None, verse_end=None, position=1)),
        CommentaryEntry(**_entry_values('edition_id', edition.id, genesis, entry_type='verse', position=2)),
        CommentaryEntry(**_entry_values('edition_id', edition.id, genesis, entry_type='verse_range',
                                        verse_start=1, verse_end=3, position=3)),
        CommentaryValidationFinding(run_id=run.id, severity='error', code='missing', message='Missing source'),
        CommentaryPublication(source_id=commentary_source.id, edition_id=edition.id, version=1),
    ])
    commentary_session.flush()
