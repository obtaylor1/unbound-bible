from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.library.ingest.models import ScripturePublication, StagedScriptureVerse
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


def set_edition(session, edition_code, **values):
    edition = session.get(TextEdition, edition_code)
    for name, value in values.items():
        setattr(edition, name, value)
    session.flush()


def test_publish_result_is_immutable(ingest_session):
    from app.library.ingest.publish import PublicationResult

    result = PublicationResult('edition', uuid4(), 1, True, 3)

    with pytest.raises(FrozenInstanceError):
        result.changed = False


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
    ingest_session.flush()
    set_edition(ingest_session, 'target', relationship='exact_ethiopian', reading_language='English')

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


def test_publish_is_checksum_idempotent_without_mutating_requested_run(ingest_session):
    from app.library.ingest.publish import publish_run
    from .conftest import make_ingest_run

    create_legacy_texts(ingest_session)
    first = make_ingest_run(ingest_session, 'target', 'First text')
    publish_run(ingest_session, first.id)
    requested = make_ingest_run(ingest_session, 'target', 'Different staged rows', status='staged')
    requested.source_checksum = first.source_checksum
    ingest_session.flush()
    original_rows = legacy_rows(ingest_session, 'target')

    result = publish_run(ingest_session, requested.id)

    assert result.changed is False
    assert result.run_id == first.id
    assert result.publication_version == 1
    assert legacy_rows(ingest_session, 'target') == original_rows
    assert requested.status == 'staged'
    assert ingest_session.scalars(select(ScripturePublication).where(
        ScripturePublication.edition_code == 'target'
    )).all() == [active_publication(ingest_session, 'target')]


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
    set_edition(
        ingest_session,
        'target',
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
    publish_run(ingest_session, old.id)
    new = make_ingest_run(ingest_session, 'target', 'New exact text')
    publish_run(ingest_session, new.id)

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
    assert old.source_checksum in ingest_session.scalar(select(EditionCoverage.note).where(
        EditionCoverage.edition_code == 'target'
    ))
    assert len(ingest_session.scalars(select(ScripturePublication).where(
        ScripturePublication.edition_code == 'target', ScripturePublication.active.is_(True)
    )).all()) == 1
    with pytest.raises(RollbackUnavailable, match='distinct prior'):
        rollback_edition(ingest_session, 'target')
    assert active_publication(ingest_session, 'target').run_id == old.id


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
