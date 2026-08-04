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


def test_edition_and_import_run_generate_uuid_ids(
    commentary_session, commentary_source, make_commentary_edition,
):
    from app.commentary.models import CommentaryImportRun

    edition = make_commentary_edition()
    run = CommentaryImportRun(
        source_id=commentary_source.id,
        source_checksum='a' * 64,
        metadata_snapshot={},
        status='staged',
    )
    commentary_session.add(run)
    commentary_session.flush()

    assert edition.id is not None
    assert run.id is not None


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


def _make_import_run(commentary_session, source_id, **overrides):
    from app.commentary.models import CommentaryImportRun

    values = {
        'source_id': source_id,
        'source_checksum': 'd' * 64,
        'metadata_snapshot': {},
        'status': 'staged',
    }
    values.update(overrides)
    run = CommentaryImportRun(**values)
    commentary_session.add(run)
    commentary_session.flush()
    return run


def test_invalid_import_run_status_is_rejected_with_a_valid_source(commentary_session, commentary_source):
    from app.commentary.models import CommentaryImportRun

    with commentary_session.begin_nested():
        commentary_session.add(CommentaryImportRun(
            source_id=commentary_source.id, source_checksum='a' * 64, metadata_snapshot={}, status='invalid',
        ))
        with pytest.raises(IntegrityError, match='ck_commentary_import_runs_status'):
            commentary_session.flush()


def test_invalid_edition_status_is_rejected_with_a_valid_source(commentary_session, commentary_source):
    from app.commentary.models import CommentaryEdition

    with commentary_session.begin_nested():
        commentary_session.add(CommentaryEdition(
            source_id=commentary_source.id, dataset_version='bad-status', source_checksum='a' * 64,
            status='invalid', coverage={},
        ))
        with pytest.raises(IntegrityError, match='ck_commentary_editions_status'):
            commentary_session.flush()


def test_invalid_finding_severity_is_rejected_with_a_valid_run(commentary_session, commentary_source, genesis):
    from app.commentary.models import CommentaryValidationFinding

    run = _make_import_run(commentary_session, commentary_source.id)
    with commentary_session.begin_nested():
        commentary_session.add(CommentaryValidationFinding(
            run_id=run.id, severity='info', code='bad-severity', work_id=genesis, message='not allowed',
        ))
        with pytest.raises(IntegrityError, match='ck_commentary_validation_findings_severity'):
            commentary_session.flush()


def test_invalid_entry_type_is_rejected_with_valid_references(
    commentary_session, genesis, make_commentary_edition,
):
    from app.commentary.models import CommentaryEntry

    edition = make_commentary_edition()
    with commentary_session.begin_nested():
        commentary_session.add(CommentaryEntry(**_entry_values(
            'edition_id', edition.id, genesis, entry_type='section',
        )))
        with pytest.raises(IntegrityError, match='ck_commentary_entries_entry_type'):
            commentary_session.flush()


@pytest.mark.parametrize(
    ('kind', 'constraint_name'),
    [
        ('edition', 'ck_commentary_editions_source_checksum_length'),
        ('run', 'ck_commentary_import_runs_source_checksum_length'),
        ('entry', 'ck_commentary_entries_row_checksum_length'),
        ('staged_entry', 'ck_staged_commentary_entries_row_checksum_length'),
    ],
)
def test_each_checksum_length_constraint_is_isolated(
    commentary_session, commentary_source, genesis, make_commentary_edition, kind, constraint_name,
):
    from app.commentary.models import CommentaryEdition, CommentaryEntry, CommentaryImportRun, StagedCommentaryEntry

    edition = make_commentary_edition()
    run = _make_import_run(commentary_session, commentary_source.id)
    if kind == 'edition':
        row = CommentaryEdition(
            source_id=commentary_source.id, dataset_version='bad-edition-checksum',
            source_checksum='a' * 63, status='staged', coverage={},
        )
    elif kind == 'run':
        row = CommentaryImportRun(
            source_id=commentary_source.id, source_checksum='a' * 63, metadata_snapshot={}, status='staged',
        )
    elif kind == 'entry':
        row = CommentaryEntry(**_entry_values('edition_id', edition.id, genesis, row_checksum='a' * 63))
    else:
        row = StagedCommentaryEntry(**_entry_values('run_id', run.id, genesis, row_checksum='a' * 63))
    with commentary_session.begin_nested():
        commentary_session.add(row)
        with pytest.raises(IntegrityError, match=constraint_name):
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
        row = CommentaryEdition(source_id=edition.source_id, dataset_version='negative-count',
                                source_checksum='c' * 64, status='staged', coverage={}, record_count=value)
    elif field == 'version':
        row = CommentaryPublication(source_id=edition.source_id, edition_id=edition.id, version=value)
    else:
        row = CommentaryEntry(**_entry_values('edition_id', edition.id, genesis, **{field: value}))
    with commentary_session.begin_nested():
        commentary_session.add(row)
        with pytest.raises(IntegrityError):
            commentary_session.flush()


@pytest.mark.parametrize(
    ('field', 'constraint_name'),
    [
        ('staged_count', 'ck_commentary_import_runs_staged_count_nonnegative'),
        ('error_count', 'ck_commentary_import_runs_error_count_nonnegative'),
        ('warning_count', 'ck_commentary_import_runs_warning_count_nonnegative'),
    ],
)
def test_negative_import_run_counts_are_rejected_independently(
    commentary_session, commentary_source, field, constraint_name,
):
    from app.commentary.models import CommentaryImportRun

    values = {
        'source_id': commentary_source.id,
        'source_checksum': 'c' * 64,
        'metadata_snapshot': {},
        'status': 'staged',
        field: -1,
    }
    with commentary_session.begin_nested():
        commentary_session.add(CommentaryImportRun(**values))
        with pytest.raises(IntegrityError, match=constraint_name):
            commentary_session.flush()


def test_negative_staged_entry_position_is_rejected_with_valid_references(
    commentary_session, commentary_source, genesis,
):
    from app.commentary.models import StagedCommentaryEntry

    run = _make_import_run(commentary_session, commentary_source.id)
    with commentary_session.begin_nested():
        commentary_session.add(StagedCommentaryEntry(**_entry_values(
            'run_id', run.id, genesis, position=-1,
        )))
        with pytest.raises(IntegrityError, match='ck_staged_commentary_entries_position_nonnegative'):
            commentary_session.flush()


@pytest.mark.parametrize(
    ('field', 'value', 'constraint_name'),
    [
        ('chapter', 0, 'ck_commentary_validation_findings_chapter_positive'),
        ('chapter', -1, 'ck_commentary_validation_findings_chapter_positive'),
        ('verse', 0, 'ck_commentary_validation_findings_verse_positive'),
        ('verse', -1, 'ck_commentary_validation_findings_verse_positive'),
    ],
)
def test_nonpositive_finding_coordinates_are_rejected_with_valid_references(
    commentary_session, commentary_source, genesis, field, value, constraint_name,
):
    from app.commentary.models import CommentaryValidationFinding

    run = _make_import_run(commentary_session, commentary_source.id)
    with commentary_session.begin_nested():
        commentary_session.add(CommentaryValidationFinding(
            run_id=run.id,
            severity='warning',
            code='bad-coordinate',
            work_id=genesis,
            message='not allowed',
            **{field: value},
        ))
        with pytest.raises(IntegrityError, match=constraint_name):
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
    run = CommentaryImportRun(source_id=commentary_source.id, source_checksum='d' * 64,
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
            source_id=edition.source_id, dataset_version=edition.dataset_version,
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

    run = CommentaryImportRun(source_id=commentary_source.id, source_checksum='f' * 64,
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
    run = CommentaryImportRun(source_id=commentary_source.id, source_checksum='f' * 64,
                              metadata_snapshot={'format': 'test'}, status='validated')
    commentary_session.add(run)
    commentary_session.flush()
    commentary_session.add_all([
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
