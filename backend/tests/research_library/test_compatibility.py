import json
import os
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import psycopg2
import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from typer.testing import CliRunner

from app.auth.models import User
from app.commentary.models import CommentaryEdition, CommentaryEntry, CommentarySource
from app.database import Base, create_database_engine, create_session_factory
from app.library.models import (
    EditionCoverage,
    EditionWorkSource,
    LibraryWork,
    TextEdition,
)
from app.research_library.compatibility import (
    LegacyRegistrationError,
    register_legacy_sources,
)
from app.research_library.compatibility_cli import app
from app.research_library.eligibility import (
    evaluate_publication,
    public_eligibility_predicate,
)
from app.research_library.models import (
    CitationAnchor,
    ContentUnit,
    LegacyContentLink,
    LegacySourceLink,
    LicenseRecord,
    ResearchChunk,
    SourceAuditEvent,
    SourceEdition,
    SourceEditionWork,
    SourcePublication,
)


runner = CliRunner()


def _user(*, role='administrator', active=True):
    token = uuid4().hex
    return User(
        email=f'{token}@example.test',
        email_normalized=f'{token}@example.test',
        username=token,
        password_hash='unused',
        role=role,
        is_active=active,
    )


@pytest.fixture
def compatibility_database(test_settings):
    engine = create_database_engine(test_settings)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        yield test_settings.database_url, factory
    finally:
        engine.dispose()


def _seed(session):
    administrator = _user()
    genesis = LibraryWork(id='genesis', title='Genesis')
    enoch = LibraryWork(id='1-enoch', title='1 Enoch')
    edition = TextEdition(
        edition_code='legacy-eng',
        name='Legacy English Bible',
        reading_language='eng',
        source_language='gez',
        script='Latn',
        translator='A Translator',
        publisher='Archive Press',
        published_year=1910,
        license_spdx='PUBLIC-DOMAIN',
        attribution='Legacy attribution',
        provenance_url='https://archive.example/scripture',
        source_tradition='Ethiopian tradition',
        relationship='related_recension',
        versification='ethiopic-chapter-verse',
        expected_coverage={'works': ['genesis', '1-enoch']},
        verification_status='verified',
        source_checksum=None,
    )
    explicit = EditionWorkSource(
        edition_code='legacy-eng',
        work_id='genesis',
        source_key='gen',
        source_label='Genesis source folios',
        translator='A Translator',
        source_language='eng',
        source_tradition='Ethiopian tradition',
        published_year=1910,
        license_spdx='PUBLIC-DOMAIN',
        attribution='Genesis-specific attribution',
        provenance_url='https://archive.example/genesis',
        fallback=False,
        modified=False,
        verification_status='verified',
        canon_scope='ethio81',
    )
    coverage_duplicate = EditionCoverage(
        edition_code='legacy-eng', work_id='genesis', status='verified_english'
    )
    coverage_only = EditionCoverage(
        edition_code='legacy-eng', work_id='1-enoch', status='translation_needed'
    )
    commentary = CommentarySource(
        id='ancient-notes',
        title='Ancient Notes',
        abbreviation='AN',
        author='An Editor',
        publication_period='1890--1910',
        tradition='Historical commentary archive',
        language='eng',
        license_spdx='CC0-1.0',
        license_url='https://license.example/cc0',
        attribution='Commentary attribution',
        provenance_url='https://archive.example/commentary',
    )
    older = CommentaryEdition(
        source_id='ancient-notes', dataset_version='2024-01',
        source_checksum='1' * 64, status='published', record_count=0, coverage={},
    )
    newer = CommentaryEdition(
        source_id='ancient-notes', dataset_version='2025-02',
        source_checksum='2' * 64, status='staged', record_count=0, coverage={},
    )
    session.add_all([administrator, genesis, enoch, edition, commentary])
    session.flush()
    session.add_all([explicit, coverage_duplicate, coverage_only, older, newer])
    session.flush()
    session.add(CommentaryEntry(
        edition_id=newer.id,
        work_id='genesis',
        chapter=1,
        verse_start=1,
        verse_end=1,
        entry_type='verse',
        heading='Legacy heading',
        body='Legacy commentary body that must never be copied.',
        source_locator='legacy://ancient-notes/genesis/1/1',
        row_checksum='3' * 64,
        position=0,
    ))
    session.flush()
    return administrator


def _counts(session):
    models = (
        SourceEdition, SourcePublication, SourceEditionWork, LegacySourceLink,
        SourceAuditEvent, LicenseRecord, ContentUnit, CitationAnchor,
        ResearchChunk, LegacyContentLink,
    )
    return {model: session.scalar(select(func.count()).select_from(model)) for model in models}


def _legacy_snapshot(session):
    models = (
        TextEdition,
        EditionWorkSource,
        EditionCoverage,
        CommentarySource,
        CommentaryEdition,
        CommentaryEntry,
    )
    snapshot = {}
    for model in models:
        primary_key = model.__mapper__.primary_key
        rows = session.scalars(select(model).order_by(*primary_key)).all()
        snapshot[model.__tablename__] = tuple(
            tuple(deepcopy(getattr(row, column.key)) for column in model.__table__.columns)
            for row in rows
        )
    return snapshot


def test_registers_scripture_commentary_and_work_union_without_rights_or_content(
    compatibility_database,
):
    _, factory = compatibility_database
    with factory.begin() as session:
        actor = _seed(session)
        legacy_before = _legacy_snapshot(session)
        result = register_legacy_sources(session, actor.id)

        assert result.created_sources == 2
        assert result.existing_sources == 0
        assert result.created_publication_shells == 2
        assert result.created_work_links == 2
        assert result.created_legacy_links == 3
        assert result.created_audit_events == 2

        scripture_link = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'text_edition'))
        scripture = session.get(SourceEdition, scripture_link.source_edition_id)
        assert (scripture.title, scripture.edition_label) == ('Legacy English Bible', 'legacy-eng')
        assert (scripture.language, scripture.script) == ('eng', 'Latn')
        assert (scripture.translator, scripture.publisher, scripture.publication_year) == (
            'A Translator', 'Archive Press', 1910)
        assert scripture.source_url == 'https://archive.example/scripture'
        assert scripture.acquisition_source == 'Ethiopian tradition'
        assert scripture.locator_scheme == 'ethiopic-chapter-verse'
        assert scripture.attribution == 'Legacy attribution'
        assert scripture.active_publication_id is None
        assert scripture.checksum.startswith('unverified-metadata-sha256:')
        assert len(scripture.checksum) == len('unverified-metadata-sha256:') + 64

        work_rows = session.scalars(select(SourceEditionWork).where(
            SourceEditionWork.source_edition_id == scripture.id
        ).order_by(SourceEditionWork.work_id)).all()
        assert [(row.work_id, row.source_label, row.locator_scheme, row.attribution_override)
                for row in work_rows] == [
            ('1-enoch', '1 Enoch', 'ethiopic-chapter-verse', 'Legacy attribution'),
            ('genesis', 'Genesis source folios', 'ethiopic-chapter-verse',
             'Genesis-specific attribution'),
        ]
        per_work_links = session.scalars(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'edition_work_source'
        ).order_by(LegacySourceLink.legacy_key)).all()
        assert [row.legacy_key for row in per_work_links] == ['legacy-eng:genesis']
        assert {row.source_edition_id for row in per_work_links} == {scripture.id}

        commentary_link = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'commentary_source'))
        commentary = session.get(SourceEdition, commentary_link.source_edition_id)
        assert commentary.title == 'Ancient Notes'
        assert commentary.edition_label == 'AN | dataset 2025-02'
        assert commentary.editor == 'An Editor'
        assert commentary.original_publication == '1890--1910'
        assert commentary.acquisition_source == (
            'Historical commentary archive | legacy dataset 2025-02'
        )
        assert commentary.language == 'eng'
        assert commentary.source_url == 'https://archive.example/commentary'
        assert commentary.attribution == 'Commentary attribution'
        assert commentary.locator_scheme == 'commentary-entry'
        assert commentary.checksum == '2' * 64

        publications = session.scalars(select(SourcePublication).order_by(
            SourcePublication.source_edition_id)).all()
        assert len(publications) == 2
        for publication in publications:
            source = session.get(SourceEdition, publication.source_edition_id)
            assert publication.version == 1
            assert publication.status == 'needs_rights_review'
            assert publication.validation_approved is False
            assert publication.public_visibility is False
            assert publication.license_record_id is None
            assert publication.ingest_run_id is None
            assert publication.published_at is None
            assert publication.content_checksum.startswith('legacy-metadata-sha256:')
            assert evaluate_publication(publication, source, None).eligible is False
        eligible = session.scalars(
            select(SourcePublication)
            .join(SourceEdition, SourcePublication.source_edition_id == SourceEdition.id)
            .outerjoin(
                LicenseRecord,
                SourcePublication.license_record_id == LicenseRecord.id,
            )
            .where(public_eligibility_predicate())
        ).all()
        assert eligible == []

        counts = _counts(session)
        assert counts[LicenseRecord] == counts[ContentUnit] == counts[CitationAnchor] == 0
        assert counts[ResearchChunk] == counts[LegacyContentLink] == 0
        assert legacy_before == _legacy_snapshot(session)
        audits = session.scalars(select(SourceAuditEvent).order_by(SourceAuditEvent.source_edition_id)).all()
        assert {event.action for event in audits} == {'legacy_source_registered'}
        for event in audits:
            assert event.actor_id == actor.id and event.prior_state is None
            assert set(event.resulting_state) == {
                'legacy_type', 'legacy_key', 'source_edition_id',
                'shell_publication_id', 'status', 'counts',
            }
            assert 'email' not in json.dumps(event.resulting_state).lower()


def test_idempotent_rerun_and_deterministic_ids_across_fresh_databases(test_settings, tmp_path):
    snapshots = []
    for index in range(2):
        settings = test_settings.model_copy(update={
            'database_url': f'sqlite:///{tmp_path / f"fresh-{index}.db"}'
        })
        engine = create_database_engine(settings)
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        with factory.begin() as session:
            actor = _seed(session)
            first = register_legacy_sources(session, actor.id)
            second = register_legacy_sources(session, actor.id)
            assert first.created_sources == 2
            assert second.created_sources == 0
            assert second.existing_sources == 2
            assert second.created_publication_shells == 0
            assert second.created_work_links == 0
            assert second.created_legacy_links == 0
            assert second.created_audit_events == 0
            snapshots.append((
                session.scalars(select(SourceEdition.id).order_by(SourceEdition.id)).all(),
                session.scalars(select(SourcePublication.id).order_by(SourcePublication.id)).all(),
                session.scalars(select(SourceEditionWork.id).order_by(SourceEditionWork.id)).all(),
                session.scalars(select(LegacySourceLink.id).order_by(LegacySourceLink.id)).all(),
            ))
            assert session.scalar(select(func.count()).select_from(SourceAuditEvent)) == 2
        engine.dispose()
    assert snapshots[0] == snapshots[1]


def test_resumes_deterministic_rows_missing_links(compatibility_database):
    _, factory = compatibility_database
    with factory.begin() as session:
        actor = _seed(session)
        first = register_legacy_sources(session, actor.id)
        scripture_link = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'text_edition'))
        per_work = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'edition_work_source'))
        session.delete(scripture_link)
        session.delete(per_work)
        session.flush()
        result = register_legacy_sources(session, actor.id)
        assert first.created_sources == 2
        assert result.created_sources == 0
        assert result.existing_sources == 2
        assert result.created_legacy_links == 2
        assert result.created_audit_events == 1
        restored_primary = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'text_edition'))
        source_id = restored_primary.source_edition_id
        session.delete(restored_primary)
        session.flush()
        session.add(LegacySourceLink(
            legacy_type='text_edition', legacy_key='legacy-eng',
            source_edition_id=source_id,
        ))
        session.flush()
        compatible_existing_link = register_legacy_sources(session, actor.id)
        assert compatible_existing_link.created_legacy_links == 0
        assert compatible_existing_link.created_audit_events == 0
        assert session.scalar(select(func.count()).select_from(SourceAuditEvent)) == 3
        recovery_events = session.scalars(select(SourceAuditEvent).where(
            SourceAuditEvent.source_edition_id == source_id,
            SourceAuditEvent.action == 'legacy_source_registered',
        )).all()
        recovery = next(
            event for event in recovery_events
            if event.resulting_state['counts']['publication_shells'] == 0
        )
        assert recovery.prior_state is None
        assert recovery.source_edition_id == source_id
        assert recovery.resulting_state['counts'] == {
            'publication_shells': 0,
            'work_links': 0,
            'legacy_links': 2,
        }


def test_rerun_preserves_valid_active_publication_pointer(compatibility_database):
    _, factory = compatibility_database
    with factory.begin() as session:
        actor = _seed(session)
        register_legacy_sources(session, actor.id)
        scripture_link = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'text_edition'
        ))
        source = session.get(SourceEdition, scripture_link.source_edition_id)
        license_record = LicenseRecord(
            source_edition_id=source.id,
            license_name='Explicitly reviewed rights',
            commercial_use_allowed=True,
            display_allowed=True,
            redistribution_allowed=True,
            attribution_required=False,
            reviewer_id=actor.id,
            verification_date=datetime.now(UTC),
        )
        session.add(license_record)
        session.flush()
        active_publication = SourcePublication(
            source_edition_id=source.id,
            license_record_id=license_record.id,
            version=2,
            status='active',
            validation_approved=True,
            public_visibility=True,
            source_checksum=source.checksum,
            content_checksum='reviewed-content-sha256:' + '4' * 64,
            published_at=datetime.now(UTC),
            published_by_user_id=actor.id,
            reviewed_by_user_id=actor.id,
        )
        session.add(active_publication)
        session.flush()
        source.active_publication_id = active_publication.id
        session.flush()

        result = register_legacy_sources(session, actor.id)

        assert result.created_sources == 0
        assert result.created_audit_events == 0
        assert source.active_publication_id == active_publication.id


@pytest.mark.parametrize('role,active,code', [
    ('reader', True, 'actor_not_administrator'),
    ('administrator', False, 'actor_inactive'),
])
def test_rejects_ineligible_actor_without_writes(compatibility_database, role, active, code):
    _, factory = compatibility_database
    with factory.begin() as session:
        actor = _user(role=role, active=active)
        session.add(actor); session.flush()
        with pytest.raises(LegacyRegistrationError) as error:
            register_legacy_sources(session, actor.id)
        assert error.value.code == code
        assert _counts(session)[SourceEdition] == 0
    with factory() as session:
        with pytest.raises(LegacyRegistrationError) as error:
            register_legacy_sources(session, uuid4())
        assert error.value.code == 'actor_not_found'


def test_conflict_and_audit_failure_are_rolled_back_by_caller(compatibility_database, monkeypatch):
    _, factory = compatibility_database
    actor_id = None
    with factory.begin() as session:
        actor = _seed(session); actor_id = actor.id
        conflicting_source = SourceEdition(
            title='Conflicting source', edition_label='conflict', language='eng',
            checksum='f' * 64, locator_scheme='chapter-verse',
        )
        session.add(conflicting_source)
        session.flush()
        session.add(LegacySourceLink(
            legacy_type='text_edition', legacy_key='legacy-eng',
            source_edition_id=conflicting_source.id,
        ))
    with pytest.raises(LegacyRegistrationError, match='Legacy source registration conflict'):
        with factory.begin() as session:
            register_legacy_sources(session, actor_id)
    with factory() as session:
        assert _counts(session)[SourceEdition] == 1

    with factory.begin() as session:
        session.execute(__import__('sqlalchemy').delete(LegacySourceLink))
    def fail(*args, **kwargs):
        raise RuntimeError('secret raw audit failure')
    monkeypatch.setattr('app.research_library.compatibility.append_source_audit_event', fail)
    with pytest.raises(RuntimeError):
        with factory.begin() as session:
            register_legacy_sources(session, actor_id)
    with factory() as session:
        assert _counts(session)[SourceEdition] == 1


def test_unverified_commentary_metadata_digest_is_canonical(compatibility_database):
    _, factory = compatibility_database
    with factory.begin() as session:
        actor = _user(); session.add(actor)
        session.add(CommentarySource(
            id='no-editions', title='No Editions', abbreviation='NE', author='Editor',
            publication_period='1900', tradition='Archive', language='eng',
            license_spdx='UNKNOWN', license_url='https://license.example/unknown',
            attribution='Attribute', provenance_url='https://archive.example/no-editions',
        ))
        session.flush()
        register_legacy_sources(session, actor.id)
        source = session.scalar(select(SourceEdition))
        assert source.checksum.startswith('unverified-metadata-sha256:')
        assert source.active_publication_id is None


def test_cli_success_explicit_inputs_and_safe_failures(compatibility_database, monkeypatch):
    url, factory = compatibility_database
    with factory.begin() as session:
        actor = _seed(session); actor_id = actor.id
    success = runner.invoke(app, [
        'register', '--database-url', url, '--actor-id', str(actor_id),
    ])
    assert success.exit_code == 0, success.output
    payload = json.loads(success.stdout)
    assert payload['created_sources'] == 2
    assert payload['next_action'] == 'review_source_rights'
    assert url not in success.output and str(actor_id) not in success.output

    missing = runner.invoke(app, ['register', '--database-url', ' ', '--actor-id', str(actor_id)])
    invalid = runner.invoke(app, ['register', '--database-url', url, '--actor-id', 'secret@example.test'])
    assert json.loads(missing.stderr)['error_code'] == 'missing_database_url'
    assert json.loads(invalid.stderr)['error_code'] == 'invalid_actor_id'
    assert 'secret@example.test' not in invalid.output

    engine_called = False
    def fail_if_called(*args, **kwargs):
        nonlocal engine_called
        engine_called = True
        raise AssertionError('unsupported dialect must be rejected before engine creation')
    monkeypatch.setattr(
        'app.research_library.compatibility_cli.create_database_engine', fail_if_called
    )
    unsupported = runner.invoke(app, [
        'register', '--database-url', 'mysql://secret:password@host/db',
        '--actor-id', str(actor_id),
    ])
    assert json.loads(unsupported.stderr)['error_code'] == 'unsupported_database'
    assert 'password' not in unsupported.output
    assert not engine_called


def test_cli_dispose_failure_preserves_committed_success(compatibility_database, monkeypatch):
    url, factory = compatibility_database
    engine = factory.kw['bind']
    with factory.begin() as session:
        actor = _seed(session); actor_id = actor.id
    monkeypatch.setattr('app.research_library.compatibility_cli.create_database_engine', lambda settings: engine)
    monkeypatch.setattr(engine, 'dispose', lambda: (_ for _ in ()).throw(RuntimeError('secret')))
    result = runner.invoke(app, [
        'register', '--database-url', 'sqlite:///not-used.db', '--actor-id', str(actor_id),
    ])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload['created_sources'] == 2
    assert payload['warning_code'] == 'engine_cleanup_failed'
    assert 'secret' not in result.output


def test_cli_rolls_back_everything_when_audit_creation_fails(
    compatibility_database, monkeypatch
):
    url, factory = compatibility_database
    with factory.begin() as session:
        actor = _seed(session); actor_id = actor.id

    def fail(*args, **kwargs):
        raise RuntimeError('audit secret@example.test token=hunter2')

    monkeypatch.setattr(
        'app.research_library.compatibility.append_source_audit_event', fail
    )
    result = runner.invoke(app, [
        'register', '--database-url', url, '--actor-id', str(actor_id),
    ])
    assert result.exit_code != 0
    assert json.loads(result.stderr) == {
        'changed': False,
        'error_code': 'registration_failure',
        'message': 'Legacy source registration failed safely',
    }
    assert 'hunter2' not in result.output
    assert 'secret@example.test' not in result.output
    with factory() as session:
        counts = _counts(session)
        assert counts[SourceEdition] == 0
        assert counts[SourcePublication] == 0
        assert counts[LegacySourceLink] == 0
        assert counts[SourceAuditEvent] == 0


@pytest.mark.parametrize('missing_artifact', ['publication_shell', 'work_link'])
def test_cli_changed_reports_every_recovery_write(
    compatibility_database, missing_artifact
):
    url, factory = compatibility_database
    with factory.begin() as session:
        actor = _seed(session); actor_id = actor.id
        register_legacy_sources(session, actor_id)
        scripture_link = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == 'text_edition'
        ))
        source_id = scripture_link.source_edition_id
        if missing_artifact == 'publication_shell':
            publication = session.scalar(select(SourcePublication).where(
                SourcePublication.source_edition_id == source_id
            ))
            session.connection().execute(delete(SourceAuditEvent).where(
                SourceAuditEvent.source_publication_id == publication.id
            ))
            session.connection().execute(delete(SourcePublication).where(
                SourcePublication.id == publication.id
            ))
        else:
            work_link = session.scalar(select(SourceEditionWork).where(
                SourceEditionWork.source_edition_id == source_id
            ).order_by(SourceEditionWork.work_id))
            session.delete(work_link)

    recovered = runner.invoke(app, [
        'register', '--database-url', url, '--actor-id', str(actor_id),
    ])
    assert recovered.exit_code == 0, recovered.output
    payload = json.loads(recovered.stdout)
    assert payload['changed'] is True
    assert payload['created_audit_events'] == 1
    expected_count = (
        payload['created_publication_shells']
        if missing_artifact == 'publication_shell'
        else payload['created_work_links']
    )
    assert expected_count == 1
    with factory() as session:
        audit_count_after_recovery = session.scalar(
            select(func.count()).select_from(SourceAuditEvent)
        )

    unchanged = runner.invoke(app, [
        'register', '--database-url', url, '--actor-id', str(actor_id),
    ])
    assert unchanged.exit_code == 0, unchanged.output
    unchanged_payload = json.loads(unchanged.stdout)
    assert unchanged_payload['changed'] is False
    assert all(
        unchanged_payload[key] == 0 for key in (
            'created_sources',
            'created_publication_shells',
            'created_work_links',
            'created_legacy_links',
            'created_audit_events',
        )
    )
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SourceAuditEvent)) == (
            audit_count_after_recovery
        )


def test_postgresql_registration_lock_is_command_wide_and_actor_independent():
    from app.research_library.compatibility import (
        POSTGRES_REGISTRATION_ADVISORY_LOCK_ID,
        lock_postgresql_registration_scope,
    )

    class RecordingSession:
        def __init__(self):
            self.calls = []

        def execute(self, statement, parameters=None):
            self.calls.append((str(statement), parameters))

    session = RecordingSession()
    lock_postgresql_registration_scope(session)

    assert session.calls == [
        ('SET TRANSACTION ISOLATION LEVEL READ COMMITTED', None),
        (
            'SELECT pg_advisory_xact_lock(:lock_id)',
            {'lock_id': POSTGRES_REGISTRATION_ADVISORY_LOCK_ID},
        ),
        (
            'LOCK TABLE library_works, text_editions, edition_work_sources, '
            'edition_coverage, commentary_sources, commentary_editions IN SHARE MODE',
            None,
        ),
        (
            'LOCK TABLE source_editions, source_publications, source_edition_works, '
            'legacy_source_links, source_audit_events IN SHARE ROW EXCLUSIVE MODE',
            None,
        ),
    ]


def _postgres_connect(url, database=None):
    parsed = make_url(url)
    return psycopg2.connect(
        host=parsed.host,
        port=parsed.port,
        user=parsed.username,
        password=parsed.password,
        dbname=database or parsed.database,
    )


@pytest.mark.skipif(
    not os.environ.get('TEST_POSTGRES_DATABASE_URL'),
    reason='TEST_POSTGRES_DATABASE_URL is not configured for live PostgreSQL tests.',
)
def test_live_postgresql_two_administrators_serialize_registration():
    from app.research_library.compatibility_cli import _register_in_transaction

    service_url = os.environ['TEST_POSTGRES_DATABASE_URL']
    parsed = make_url(service_url)
    database_name = f'unbound_compatibility_{uuid4().hex}'
    admin = _postgres_connect(service_url)
    admin.autocommit = True
    engine = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{database_name}"')
        isolated_url = parsed.set(database=database_name).render_as_string(
            hide_password=False
        )
        engine = create_engine(isolated_url)
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        with factory.begin() as session:
            first = _seed(session)
            second = _user()
            session.add(second)
            session.flush()
            actor_ids = (first.id, second.id)

        barrier = Barrier(2)

        def attempt(actor_id):
            barrier.wait()
            with factory() as session:
                return _register_in_transaction(session, 'postgresql', actor_id)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, actor_ids))

        assert sorted(result.created_sources for result in results) == [0, 2]
        assert sorted(result.existing_sources for result in results) == [0, 2]
        with factory() as session:
            counts = _counts(session)
            assert counts[SourceEdition] == 2
            assert counts[SourcePublication] == 2
            assert counts[SourceEditionWork] == 2
            assert counts[LegacySourceLink] == 3
            assert counts[SourceAuditEvent] == 2
    finally:
        if engine is not None:
            engine.dispose()
        with admin.cursor() as cursor:
            cursor.execute(
                'SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                'WHERE datname = %s',
                (database_name,),
            )
            cursor.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        admin.close()


def test_actor_lock_query_compiles_for_postgresql():
    from sqlalchemy.dialects import postgresql

    from app.research_library.compatibility import locked_actor_query

    sql = str(locked_actor_query(uuid4()).compile(dialect=postgresql.dialect()))
    assert 'FOR UPDATE' in sql
