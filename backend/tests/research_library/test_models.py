from collections.abc import Generator

import pytest
from sqlalchemy import ForeignKeyConstraint, delete, event, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.database import (
    Base,
    create_database_engine,
    create_session_factory,
)
from app.library.models import LibraryWork
from app.research_library.models import (
    PUBLICATION_STATUSES,
    STORED_SOURCE_CLASSIFICATIONS,
    CitationAnchor,
    ContentUnit,
    ImmutableResearchLibraryRecordError,
    LegacyContentLink,
    LegacySourceLink,
    LicenseRecord,
    ResearchChunk,
    ResearchWorkProfile,
    SourceAuditEvent,
    SourceEdition,
    SourceEditionWork,
    SourcePublication,
    WorkDivision,
)


APPROVED_STORED_CLASSIFICATIONS = (
    'canonical_scripture',
    'ethiopian_canon',
    'deuterocanonical_scripture',
    'ancient_biblical_translation',
    'ancient_jewish_literature',
    'dead_sea_scroll_manuscript',
    'ancient_historical_source',
    'early_christian_writing',
    'jewish_tradition',
    'church_tradition',
    'archaeology',
    'modern_scholarship',
)


@pytest.fixture
def research_library_session(test_settings) -> Generator[Session, None, None]:
    engine = create_database_engine(test_settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _make_scope_graph(
    session: Session,
    suffix: str,
    *,
    publication_status: str = 'verified',
    public_visibility: bool = False,
) -> dict:
    work = LibraryWork(id=f'scope-work-{suffix}', title=f'Scope Work {suffix}')
    edition = SourceEdition(
        title=f'Scope Edition {suffix}',
        edition_label='1',
        language='eng',
        checksum=suffix[0] * 64,
        locator_scheme='chapter_verse',
    )
    session.add_all([work, edition])
    session.flush()
    division = WorkDivision(
        work_id=work.id,
        division_type='chapter',
        label='Chapter 1',
        normalized_locator='1',
        canonical_key=f'{work.id}.1',
        ordinal=1,
    )
    edition_work = SourceEditionWork(
        source_edition_id=edition.id,
        work_id=work.id,
        source_label=work.title,
        locator_scheme='chapter_verse',
    )
    license_record = LicenseRecord(
        source_edition_id=edition.id,
        license_name=f'License {suffix}',
    )
    session.add_all([division, edition_work, license_record])
    session.flush()
    publication = SourcePublication(
        source_edition_id=edition.id,
        license_record_id=license_record.id,
        version=1,
        status=publication_status,
        validation_approved=True,
        public_visibility=public_visibility,
        source_checksum=suffix[0] * 64,
        content_checksum=suffix[-1] * 64,
    )
    session.add(publication)
    session.flush()
    unit = ContentUnit(
        source_publication_id=publication.id,
        source_edition_id=edition.id,
        work_id=work.id,
        work_division_id=division.id,
        language='eng',
        script='Latn',
        direction='ltr',
        ordinal=1,
        normalized_text=f'Text {suffix}',
        source_locator='1:1',
        textual_certainty='visible_text',
        checksum=suffix[-1] * 64,
    )
    session.add(unit)
    session.flush()
    citation = CitationAnchor(
        source_publication_id=publication.id,
        content_unit_id=unit.id,
        work_division_id=division.id,
        anchor_key=f'{work.id}.1.1',
        human_locator=f'{work.title} 1:1',
        inspector_route=f'/source-inspector/{work.id}/1/1',
        open_target={'division': f'{work.id}.1'},
    )
    session.add(citation)
    session.flush()
    return {
        'work': work,
        'edition': edition,
        'division': division,
        'edition_work': edition_work,
        'license': license_record,
        'publication': publication,
        'unit': unit,
        'citation': citation,
    }


def test_research_library_models_persist_the_approved_domain_vocabulary(
    research_library_session: Session,
) -> None:
    session = research_library_session
    assert PUBLICATION_STATUSES == (
        'needs_rights_review',
        'importing',
        'verified',
        'active',
        'disabled',
        'restricted',
        'internal_research_only',
    )
    assert {
        ResearchWorkProfile.__tablename__,
        WorkDivision.__tablename__,
        SourceEdition.__tablename__,
        SourceEditionWork.__tablename__,
        LicenseRecord.__tablename__,
        SourcePublication.__tablename__,
        ContentUnit.__tablename__,
        CitationAnchor.__tablename__,
        ResearchChunk.__tablename__,
        LegacySourceLink.__tablename__,
        LegacyContentLink.__tablename__,
        SourceAuditEvent.__tablename__,
    } == {
        'research_work_profiles',
        'work_divisions',
        'source_editions',
        'source_edition_works',
        'license_records',
        'source_publications',
        'content_units',
        'citation_anchors',
        'research_chunks',
        'legacy_source_links',
        'legacy_content_links',
        'source_audit_events',
    }

    work = LibraryWork(id='1-enoch', title='1 Enoch')
    actor = User(
        email='reviewer@example.test',
        email_normalized='reviewer@example.test',
        username='reviewer',
        password_hash='test-hash',
    )
    session.add_all([work, actor])
    session.flush()

    profile = ResearchWorkProfile(
        work_id=work.id,
        short_title='1 En.',
        short_description='Ancient Jewish apocalyptic work.',
        source_classification='ancient_jewish_literature',
        hierarchy_level='work',
        traditions=['Ethiopian Orthodox', 'Second Temple Jewish'],
        canonical_statuses=['canonical', 'noncanonical_in_other_traditions'],
        original_languages=['Geʽez', 'Aramaic', 'Greek'],
        attributed_authorship='Enochic tradition',
        date_era='Second Temple period',
        historical_classification='ancient_jewish',
        literary_classification='apocalyptic',
    )
    book = WorkDivision(
        work_id=work.id,
        division_type='book',
        label='Book of the Watchers',
        normalized_locator='book-watchers',
        canonical_key='1-enoch.watchers',
        ordinal=1,
        display_metadata={'range': '1–36'},
    )
    chapter = WorkDivision(
        work_id=work.id,
        parent=book,
        division_type='chapter',
        label='Chapter 1',
        normalized_locator='1',
        canonical_key='1-enoch.1',
        ordinal=1,
    )
    edition = SourceEdition(
        title='The Book of Enoch',
        edition_label='Public domain English translation',
        translator='R. H. Charles',
        editor='R. H. Charles',
        publisher='Clarendon Press',
        publication_year=1912,
        original_publication='1912 first edition',
        language='eng',
        script='Latn',
        source_url='https://example.test/enoch',
        acquisition_source='public archive',
        checksum='a' * 64,
        locator_scheme='chapter_verse',
        attribution='Translated by R. H. Charles.',
    )
    session.add_all([profile, book, chapter, edition])
    session.flush()

    edition_work = SourceEditionWork(
        source_edition_id=edition.id,
        work_id=work.id,
        source_label='1 Enoch',
        locator_scheme='chapter_verse',
        attribution_override='R. H. Charles translation of 1 Enoch.',
    )
    license_record = LicenseRecord(
        source_edition_id=edition.id,
        license_name='Public domain determination',
        license_url='https://example.test/rights',
        is_public_domain=True,
        commercial_use_allowed=True,
        display_allowed=True,
        redistribution_allowed=True,
        modification_allowed=True,
        attribution_required=False,
        required_attribution_text=None,
        source_text_rights='public_domain',
        translation_rights='public_domain',
        image_rights='not_applicable',
        reviewed_source_urls=['https://example.test/rights'],
        reviewer_id=actor.id,
        explanatory_notes='Translator died in 1931; source reviewed independently.',
    )
    session.add_all([edition_work, license_record])
    session.flush()

    publication = SourcePublication(
        source_edition_id=edition.id,
        license_record_id=license_record.id,
        version=1,
        ingest_run_id=None,
        status='active',
        validation_approved=True,
        public_visibility=True,
        source_checksum='a' * 64,
        content_checksum='b' * 64,
        published_by_user_id=actor.id,
        reviewed_by_user_id=actor.id,
    )
    session.add(publication)
    session.flush()

    unit = ContentUnit(
        source_publication_id=publication.id,
        source_edition_id=edition.id,
        work_id=work.id,
        work_division_id=chapter.id,
        language='eng',
        script='Latn',
        direction='ltr',
        ordinal=1,
        normalized_text='The words of the blessing of Enoch.',
        source_locator='1:1',
        textual_certainty='translation',
        checksum='c' * 64,
    )
    session.add(unit)
    session.flush()

    citation = CitationAnchor(
        source_publication_id=publication.id,
        content_unit_id=unit.id,
        work_division_id=chapter.id,
        anchor_key='1-enoch.1.1',
        human_locator='1 Enoch 1:1',
        inspector_route='/source-inspector/1-enoch/1/1',
        open_target={'division': '1-enoch.1', 'unit_ordinal': 1},
    )
    session.add(citation)
    session.flush()

    chunk = ResearchChunk(
        source_edition_id=edition.id,
        source_publication_id=publication.id,
        work_id=work.id,
        work_division_id=chapter.id,
        citation_anchor_id=citation.id,
        ordinal=1,
        boundary_type='verse',
        classification='ancient_jewish_literature',
        hierarchy_level='verse',
        language='eng',
        content_digest='d' * 64,
        text_content=unit.normalized_text,
        search_document=None,
    )
    legacy_source = LegacySourceLink(
        legacy_type='text_editions',
        legacy_key='charles-1912',
        source_edition_id=edition.id,
    )
    legacy_content = LegacyContentLink(
        legacy_type='biblical_texts',
        legacy_key='1-enoch:1:1',
        content_unit_id=unit.id,
    )
    audit = SourceAuditEvent(
        actor_id=actor.id,
        source_edition_id=edition.id,
        source_publication_id=publication.id,
        action='publication_activated',
        prior_state={'status': 'verified'},
        resulting_state={'status': 'active'},
        reason='Rights and validation review completed.',
        validation_run_id='validation-2026-001',
        checksum_metadata={'source': 'a' * 64, 'content': 'b' * 64},
    )
    session.add_all([chunk, legacy_source, legacy_content, audit])
    session.flush()

    assert session.get(ResearchWorkProfile, profile.id).traditions[0] == 'Ethiopian Orthodox'
    assert session.get(WorkDivision, chapter.id).parent_id == book.id
    assert session.get(SourcePublication, publication.id).license_record_id == license_record.id
    assert session.get(CitationAnchor, citation.id).open_target['division'] == '1-enoch.1'
    assert session.get(SourceAuditEvent, audit.id).resulting_state == {'status': 'active'}


@pytest.mark.parametrize(
    ('case', 'constraint_name'),
    [
        ('division_type', 'ck_work_divisions_division_type'),
        ('division_ordinal', 'ck_work_divisions_ordinal_positive'),
        ('publication_status', 'ck_source_publications_status'),
        ('publication_version', 'ck_source_publications_version_positive'),
        ('content_direction', 'ck_content_units_direction'),
        ('textual_certainty', 'ck_content_units_textual_certainty'),
        ('chunk_classification', 'ck_research_chunks_classification'),
        ('chunk_ordinal', 'ck_research_chunks_ordinal_positive'),
    ],
)
def test_research_library_models_reject_invalid_controlled_values(
    research_library_session: Session,
    case: str,
    constraint_name: str,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, f'controlled-{case}')

    if case.startswith('division_'):
        record = WorkDivision(
            work_id=graph['work'].id,
            parent_id=graph['division'].id,
            division_type='page' if case == 'division_type' else 'verse',
            label='Invalid division',
            normalized_locator=f'invalid-{case}',
            canonical_key=f"{graph['work'].id}.invalid-{case}",
            ordinal=0 if case == 'division_ordinal' else 1,
        )
    elif case.startswith('publication_'):
        record = SourcePublication(
            source_edition_id=graph['edition'].id,
            license_record_id=graph['license'].id,
            version=0 if case == 'publication_version' else 2,
            status='draft' if case == 'publication_status' else 'verified',
            validation_approved=True,
            public_visibility=False,
            source_checksum='1' * 64,
            content_checksum='2' * 64,
        )
    elif case.startswith('content_') or case == 'textual_certainty':
        record = ContentUnit(
            source_publication_id=graph['publication'].id,
            source_edition_id=graph['edition'].id,
            work_id=graph['work'].id,
            work_division_id=graph['division'].id,
            language='eng',
            script='Latn',
            direction='sideways' if case == 'content_direction' else 'ltr',
            ordinal=2,
            normalized_text='Otherwise valid text',
            source_locator='1:2',
            textual_certainty='ai_guess' if case == 'textual_certainty' else 'visible_text',
            checksum='3' * 64,
        )
    else:
        record = _chunk_for_graph(
            graph,
            classification=(
                'ai_synthesis'
                if case == 'chunk_classification'
                else 'ancient_jewish_literature'
            ),
            ordinal=0 if case == 'chunk_ordinal' else 1,
        )
    session.add(record)

    with pytest.raises(IntegrityError, match=constraint_name):
        session.flush()


def test_work_profile_rejects_ai_synthesis_as_a_stored_classification(
    research_library_session: Session,
) -> None:
    session = research_library_session
    session.add(LibraryWork(id='classification-work', title='Classification Work'))
    session.flush()
    session.add(ResearchWorkProfile(
        work_id='classification-work',
        source_classification='ai_synthesis',
        hierarchy_level='work',
        traditions=[],
        canonical_statuses=[],
        original_languages=[],
    ))

    with pytest.raises(IntegrityError, match='ck_research_work_profiles_source_classification'):
        session.flush()


@pytest.mark.parametrize('classification', APPROVED_STORED_CLASSIFICATIONS)
def test_work_profile_accepts_each_approved_stored_classification(
    research_library_session: Session,
    classification: str,
) -> None:
    session = research_library_session
    work = LibraryWork(id=f'profile-{classification}', title=classification)
    session.add(work)
    session.flush()
    profile = ResearchWorkProfile(
        work_id=work.id,
        source_classification=classification,
        hierarchy_level='work',
        traditions=[],
        canonical_statuses=[],
        original_languages=[],
    )
    session.add(profile)
    session.flush()

    assert profile.source_classification == classification


@pytest.mark.parametrize('classification', APPROVED_STORED_CLASSIFICATIONS)
def test_chunk_accepts_each_approved_stored_classification(
    research_library_session: Session,
    classification: str,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, f'chunk-{classification}')
    chunk = _chunk_for_graph(graph, classification=classification)
    session.add(chunk)
    session.flush()

    assert chunk.classification == classification


def test_chunk_rejects_ai_synthesis_as_a_stored_classification(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'chunk-ai-synthesis')
    session.add(_chunk_for_graph(graph, classification='ai_synthesis'))

    with pytest.raises(IntegrityError, match='ck_research_chunks_classification'):
        session.flush()


def test_stored_classification_vocabulary_matches_the_approved_design() -> None:
    assert STORED_SOURCE_CLASSIFICATIONS == APPROVED_STORED_CLASSIFICATIONS


def test_division_parent_must_belong_to_the_same_work(
    research_library_session: Session,
) -> None:
    session = research_library_session
    first = _make_scope_graph(session, 'aa')
    second = _make_scope_graph(session, 'bb')
    session.add(WorkDivision(
        work_id=second['work'].id,
        parent_id=first['division'].id,
        division_type='verse',
        label='Cross-work child',
        normalized_locator='1:2',
        canonical_key=f"{second['work'].id}.1.2",
        ordinal=2,
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_publication_license_must_belong_to_the_same_edition(
    research_library_session: Session,
) -> None:
    session = research_library_session
    first = _make_scope_graph(session, 'cc')
    second = _make_scope_graph(session, 'dd')
    session.add(SourcePublication(
        source_edition_id=first['edition'].id,
        license_record_id=second['license'].id,
        version=2,
        status='verified',
        validation_approved=True,
        public_visibility=False,
        source_checksum='c' * 64,
        content_checksum='d' * 64,
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_content_unit_division_work_must_be_covered_by_the_publication_edition(
    research_library_session: Session,
) -> None:
    session = research_library_session
    first = _make_scope_graph(session, 'ee')
    second = _make_scope_graph(session, 'ff')
    session.add(ContentUnit(
        source_publication_id=first['publication'].id,
        source_edition_id=first['edition'].id,
        work_id=second['work'].id,
        work_division_id=second['division'].id,
        language='eng',
        script='Latn',
        direction='ltr',
        ordinal=2,
        normalized_text='Cross-scope text',
        source_locator='1:2',
        textual_certainty='visible_text',
        checksum='3' * 64,
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_citation_publication_must_match_its_content_unit_publication(
    research_library_session: Session,
) -> None:
    session = research_library_session
    first = _make_scope_graph(session, 'gg')
    second = _make_scope_graph(session, 'hh')
    session.add(CitationAnchor(
        source_publication_id=first['publication'].id,
        content_unit_id=second['unit'].id,
        work_division_id=second['division'].id,
        anchor_key='cross-publication-anchor',
        human_locator='Cross publication',
        inspector_route='/source-inspector/cross',
        open_target={'division': 'cross'},
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_chunk_links_must_describe_one_consistent_source_chain(
    research_library_session: Session,
) -> None:
    session = research_library_session
    first = _make_scope_graph(session, 'ii')
    second = _make_scope_graph(session, 'jj')
    session.add(ResearchChunk(
        source_edition_id=first['edition'].id,
        source_publication_id=first['publication'].id,
        work_id=second['work'].id,
        work_division_id=second['division'].id,
        citation_anchor_id=second['citation'].id,
        ordinal=1,
        boundary_type='verse',
        classification='ancient_jewish_literature',
        hierarchy_level='verse',
        language='eng',
        content_digest='4' * 64,
        text_content='Cross-scope chunk',
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_audit_publication_must_match_its_source_edition(
    research_library_session: Session,
) -> None:
    session = research_library_session
    first = _make_scope_graph(session, 'audit-first')
    second = _make_scope_graph(session, 'audit-second')
    actor = User(
        email='audit-mismatch@example.test',
        email_normalized='audit-mismatch@example.test',
        username='audit-mismatch',
        password_hash='test-hash',
    )
    session.add(actor)
    session.flush()
    session.add(SourceAuditEvent(
        actor_id=actor.id,
        source_edition_id=first['edition'].id,
        source_publication_id=second['publication'].id,
        action='invalid_cross_edition_event',
        resulting_state={},
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_audit_allows_edition_only_and_matching_publication_provenance(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'audit-valid')
    actor = User(
        email='audit-valid@example.test',
        email_normalized='audit-valid@example.test',
        username='audit-valid',
        password_hash='test-hash',
    )
    session.add(actor)
    session.flush()
    edition_event = SourceAuditEvent(
        actor_id=actor.id,
        source_edition_id=graph['edition'].id,
        action='edition_reviewed',
        resulting_state={'reviewed': True},
    )
    publication_event = SourceAuditEvent(
        actor_id=actor.id,
        source_edition_id=graph['edition'].id,
        source_publication_id=graph['publication'].id,
        action='publication_reviewed',
        resulting_state={'reviewed': True},
    )
    session.add_all([edition_event, publication_event])
    session.flush()

    assert edition_event.source_publication_id is None
    assert publication_event.source_publication_id == graph['publication'].id


def _make_immutable_record(session: Session, record_kind: str):
    graph = _make_scope_graph(session, f'immutable-{record_kind}')
    if record_kind == 'publication':
        return graph['publication'], 'status', 'disabled'
    if record_kind == 'content_unit':
        return graph['unit'], 'normalized_text', 'Changed text'
    if record_kind == 'citation_anchor':
        return graph['citation'], 'human_locator', 'Changed locator'
    if record_kind == 'research_chunk':
        chunk = ResearchChunk(
            source_edition_id=graph['edition'].id,
            source_publication_id=graph['publication'].id,
            work_id=graph['work'].id,
            work_division_id=graph['division'].id,
            citation_anchor_id=graph['citation'].id,
            ordinal=1,
            boundary_type='verse',
            classification='ancient_jewish_literature',
            hierarchy_level='verse',
            language='eng',
            content_digest='6' * 64,
            text_content='Immutable chunk',
        )
        session.add(chunk)
        session.flush()
        return chunk, 'text_content', 'Changed chunk'
    actor = User(
        email=f'{record_kind}@example.test',
        email_normalized=f'{record_kind}@example.test',
        username=f'actor-{record_kind}',
        password_hash='test-hash',
    )
    session.add(actor)
    session.flush()
    audit = SourceAuditEvent(
        actor_id=actor.id,
        source_edition_id=graph['edition'].id,
        source_publication_id=graph['publication'].id,
        action='snapshot_created',
        prior_state=None,
        resulting_state={'status': 'verified'},
        reason='Initial audit reason',
    )
    session.add(audit)
    session.flush()
    return audit, 'reason', 'Changed reason'


@pytest.mark.parametrize(
    'record_kind',
    ['publication', 'content_unit', 'citation_anchor', 'research_chunk', 'audit_event'],
)
def test_publication_snapshot_and_audit_records_reject_updates(
    research_library_session: Session,
    record_kind: str,
) -> None:
    session = research_library_session
    record, attribute, changed_value = _make_immutable_record(session, record_kind)
    setattr(record, attribute, changed_value)

    with pytest.raises(ImmutableResearchLibraryRecordError, match='immutable|append-only'):
        session.flush()


@pytest.mark.parametrize(
    'record_kind',
    ['publication', 'content_unit', 'citation_anchor', 'research_chunk', 'audit_event'],
)
def test_publication_snapshot_and_audit_records_reject_deletes(
    research_library_session: Session,
    record_kind: str,
) -> None:
    session = research_library_session
    record, _, _ = _make_immutable_record(session, record_kind)
    session.delete(record)

    with pytest.raises(ImmutableResearchLibraryRecordError, match='immutable|append-only'):
        session.flush()


@pytest.mark.parametrize(
    'record_kind',
    ['publication', 'content_unit', 'citation_anchor', 'research_chunk', 'audit_event'],
)
@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_bulk_dml_rejects_immutable_snapshot_and_audit_mutations(
    research_library_session: Session,
    record_kind: str,
    operation: str,
) -> None:
    session = research_library_session
    record, attribute, changed_value = _make_immutable_record(session, record_kind)
    model = type(record)
    statement = (
        update(model).where(model.id == record.id).values({attribute: changed_value})
        if operation == 'update'
        else delete(model).where(model.id == record.id)
    )

    with pytest.raises(ImmutableResearchLibraryRecordError, match='immutable|append-only'):
        session.execute(statement)


def test_bulk_dml_allows_unrelated_model_updates(
    research_library_session: Session,
) -> None:
    session = research_library_session
    work = LibraryWork(id='bulk-update-work', title='Before')
    session.add(work)
    session.flush()

    session.execute(
        update(LibraryWork).where(LibraryWork.id == work.id).values(title='After')
    )
    session.expire(work)

    assert work.title == 'After'


def test_bulk_update_mappings_rejects_immutable_publication_before_sql(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'bulk-mappings-publication')
    publication = graph['publication']
    original_status = publication.status

    with pytest.raises(ImmutableResearchLibraryRecordError, match='immutable'):
        session.bulk_update_mappings(
            SourcePublication,
            [{'id': publication.id, 'status': 'disabled'}],
        )

    session.expire(publication)
    assert publication.status == original_status


def test_bulk_save_objects_rejects_updates_to_persistent_immutable_records(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'bulk-save-publication')
    publication = graph['publication']
    original_status = publication.status
    publication.status = 'disabled'

    with pytest.raises(ImmutableResearchLibraryRecordError, match='immutable'):
        session.bulk_save_objects([publication])

    session.expire(publication)
    assert publication.status == original_status


def test_legacy_bulk_operations_remain_available_for_mutable_models(
    research_library_session: Session,
) -> None:
    session = research_library_session
    first = LibraryWork(id='bulk-mutable-first', title='Before')
    session.add(first)
    session.flush()

    session.bulk_update_mappings(
        LibraryWork,
        [{'id': first.id, 'title': 'After'}],
    )
    second = LibraryWork(id='bulk-mutable-second', title='Bulk insert')
    session.bulk_save_objects([second])
    session.expire(first)

    assert first.title == 'After'
    assert session.get(LibraryWork, second.id).title == 'Bulk insert'


def test_legacy_links_use_typed_compatibility_identity() -> None:
    for model in (LegacySourceLink, LegacyContentLink):
        assert 'legacy_type' in model.__table__.c
        assert 'legacy_table' not in model.__table__.c


def _chunk_for_graph(graph: dict, **overrides) -> ResearchChunk:
    values = {
        'source_edition_id': graph['edition'].id,
        'source_publication_id': graph['publication'].id,
        'work_id': graph['work'].id,
        'work_division_id': graph['division'].id,
        'citation_anchor_id': graph['citation'].id,
        'ordinal': 1,
        'boundary_type': 'verse',
        'classification': 'ancient_jewish_literature',
        'hierarchy_level': 'verse',
        'language': 'eng',
        'content_digest': '7' * 64,
        'text_content': 'Chunk text',
    }
    values.update(overrides)
    return ResearchChunk(**values)


def test_work_profile_is_one_to_one_with_library_work(
    research_library_session: Session,
) -> None:
    session = research_library_session
    session.add(LibraryWork(id='one-profile', title='One Profile'))
    session.flush()
    session.add_all([
        ResearchWorkProfile(
            work_id='one-profile',
            source_classification='canonical_scripture',
            hierarchy_level='work',
            traditions=[],
            canonical_statuses=[],
            original_languages=[],
        ),
        ResearchWorkProfile(
            work_id='one-profile',
            source_classification='ethiopian_canon',
            hierarchy_level='work',
            traditions=[],
            canonical_statuses=[],
            original_languages=[],
        ),
    ])

    with pytest.raises(IntegrityError):
        session.flush()


def test_edition_work_link_is_unique_per_edition_and_work(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'edition-work-unique')
    session.add(SourceEditionWork(
        source_edition_id=graph['edition'].id,
        work_id=graph['work'].id,
        source_label='Duplicate coverage',
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_publication_version_is_unique_per_edition(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'publication-version')
    session.add(SourcePublication(
        source_edition_id=graph['edition'].id,
        license_record_id=graph['license'].id,
        version=1,
        status='verified',
        validation_approved=True,
        public_visibility=False,
        source_checksum='8' * 64,
        content_checksum='9' * 64,
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_edition_active_pointer_declares_same_edition_foreign_key() -> None:
    constraint = next(
        item
        for item in SourceEdition.__table__.constraints
        if isinstance(item, ForeignKeyConstraint)
        and item.name == 'fk_source_editions_active_publication_same_edition'
    )

    assert tuple(constraint.column_keys) == ('active_publication_id', 'id')
    assert tuple(element.target_fullname for element in constraint.elements) == (
        'source_publications.id',
        'source_publications.source_edition_id',
    )
    assert constraint.ondelete == 'RESTRICT'


def test_edition_active_pointer_supports_replacement_and_rollback(
    research_library_session: Session,
) -> None:
    assert 'active_publication_id' in SourceEdition.__table__.c
    session = research_library_session
    graph = _make_scope_graph(
        session,
        'active-lifecycle',
        publication_status='active',
        public_visibility=True,
    )
    replacement = SourcePublication(
        source_edition_id=graph['edition'].id,
        license_record_id=graph['license'].id,
        version=2,
        status='active',
        validation_approved=True,
        public_visibility=True,
        source_checksum='a' * 64,
        content_checksum='b' * 64,
    )
    session.add(replacement)
    session.flush()

    graph['edition'].active_publication_id = graph['publication'].id
    session.flush()
    graph['edition'].active_publication_id = replacement.id
    session.flush()
    graph['edition'].active_publication_id = graph['publication'].id
    session.flush()
    session.expire(graph['edition'])

    assert graph['edition'].active_publication_id == graph['publication'].id
    assert graph['publication'].version == 1
    assert replacement.version == 2
    assert graph['publication'].status == replacement.status == 'active'
    assert graph['publication'].validation_approved is replacement.validation_approved is True
    assert graph['publication'].public_visibility is replacement.public_visibility is True


def test_model_documents_the_active_pointer_as_current_activation_authority() -> None:
    assert 'sole current-activation authority' in (SourceEdition.__doc__ or '')
    assert "status='active'" in (SourcePublication.__doc__ or '')


def test_content_unit_position_is_unique_within_publication_division(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'content-position')
    session.add(ContentUnit(
        source_publication_id=graph['publication'].id,
        source_edition_id=graph['edition'].id,
        work_id=graph['work'].id,
        work_division_id=graph['division'].id,
        language='eng',
        direction='ltr',
        ordinal=1,
        normalized_text='Duplicate position',
        source_locator='1:2',
        textual_certainty='visible_text',
        checksum='a' * 64,
    ))

    with pytest.raises(IntegrityError):
        session.flush()


def test_bulk_content_inserts_with_explicit_scope_require_no_lookup_queries(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'explicit-bulk-scope')
    publication_id = graph['publication'].id
    edition_id = graph['edition'].id
    work_id = graph['work'].id
    division_id = graph['division'].id
    session.expire_all()
    statements: list[str] = []

    def record_statement(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(session.bind, 'before_cursor_execute', record_statement)
    try:
        session.add_all([
            ContentUnit(
                source_publication_id=publication_id,
                source_edition_id=edition_id,
                work_id=work_id,
                work_division_id=division_id,
                language='eng',
                direction='ltr',
                ordinal=2,
                normalized_text='Bulk text 2',
                source_locator='1:2',
                textual_certainty='visible_text',
                checksum='4' * 64,
            ),
            ContentUnit(
                source_publication_id=publication_id,
                source_edition_id=edition_id,
                work_id=work_id,
                work_division_id=division_id,
                language='eng',
                direction='ltr',
                ordinal=3,
                normalized_text='Bulk text 3',
                source_locator='1:3',
                textual_certainty='visible_text',
                checksum='5' * 64,
            ),
        ])
        session.flush()
    finally:
        event.remove(session.bind, 'before_cursor_execute', record_statement)

    assert statements
    assert not [statement for statement in statements if statement.lstrip().upper().startswith('SELECT')]


def test_citation_anchor_key_is_stable_within_publication(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'anchor-key')
    session.add(CitationAnchor(
        source_publication_id=graph['publication'].id,
        content_unit_id=graph['unit'].id,
        work_division_id=graph['division'].id,
        anchor_key=graph['citation'].anchor_key,
        human_locator='Duplicate anchor key',
        inspector_route='/source-inspector/duplicate',
        open_target={'division': 'duplicate'},
    ))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize('missing_link', ['work_division_id', 'citation_anchor_id'])
def test_chunk_requires_division_and_citation_links(
    research_library_session: Session,
    missing_link: str,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, f'missing-{missing_link}')
    session.add(_chunk_for_graph(graph, **{missing_link: None}))

    with pytest.raises(IntegrityError):
        session.flush()


def test_chunk_deduplication_is_stable_and_not_nullable(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'chunk-dedup')
    session.add(_chunk_for_graph(graph))
    session.flush()
    session.add(_chunk_for_graph(graph, ordinal=2))

    with pytest.raises(IntegrityError):
        session.flush()


def test_chunk_ordinal_is_unique_within_publication(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'chunk-ordinal')
    session.add(_chunk_for_graph(graph))
    session.flush()
    session.add(_chunk_for_graph(graph, content_digest='8' * 64))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize('model', [LegacySourceLink, LegacyContentLink])
def test_legacy_identity_is_unique(
    research_library_session: Session,
    model: type,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, f'legacy-{model.__tablename__}')
    target = (
        {'source_edition_id': graph['edition'].id}
        if model is LegacySourceLink
        else {'content_unit_id': graph['unit'].id}
    )
    session.add_all([
        model(legacy_type='legacy_table', legacy_key='legacy-key', **target),
        model(legacy_type='legacy_table', legacy_key='legacy-key', **target),
    ])

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize('model', [LegacySourceLink, LegacyContentLink])
@pytest.mark.parametrize(
    'identity',
    [
        {'legacy_type': '', 'legacy_key': 'key'},
        {'legacy_type': 'type', 'legacy_key': ''},
    ],
)
def test_legacy_identity_parts_are_nonblank(
    research_library_session: Session,
    model: type,
    identity: dict,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, f'legacy-nonblank-{model.__tablename__}')
    target = (
        {'source_edition_id': graph['edition'].id}
        if model is LegacySourceLink
        else {'content_unit_id': graph['unit'].id}
    )
    session.add(model(**identity, **target))

    with pytest.raises(IntegrityError):
        session.flush()


def test_research_library_models_enforce_stable_uniqueness(
    research_library_session: Session,
) -> None:
    session = research_library_session
    work = LibraryWork(id='unique-work', title='Unique Work')
    session.add(work)
    session.flush()
    session.add_all([
        WorkDivision(
            work_id=work.id,
            division_type='chapter',
            label='First',
            normalized_locator='1',
            canonical_key='unique-work.1',
            ordinal=1,
        ),
        WorkDivision(
            work_id=work.id,
            division_type='chapter',
            label='Duplicate position',
            normalized_locator='01',
            canonical_key='unique-work.01',
            ordinal=1,
        ),
    ])
    with pytest.raises(IntegrityError):
        session.flush()


def test_division_position_uses_null_safe_root_and_child_partial_indexes() -> None:
    indexes = {index.name: index for index in WorkDivision.__table__.indexes}
    root = indexes['uq_work_divisions_root_ordinal']
    child = indexes['uq_work_divisions_child_ordinal']

    assert root.dialect_options['sqlite']['where'] is not None
    assert root.dialect_options['postgresql']['where'] is not None
    assert child.dialect_options['sqlite']['where'] is not None
    assert child.dialect_options['postgresql']['where'] is not None


def test_child_division_ordinal_is_unique_within_parent(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'child-ordinal-unique')
    session.add_all([
        WorkDivision(
            work_id=graph['work'].id,
            parent_id=graph['division'].id,
            division_type='verse',
            label='Verse 1',
            normalized_locator='1:1',
            canonical_key=f"{graph['work'].id}.1.1",
            ordinal=1,
        ),
        WorkDivision(
            work_id=graph['work'].id,
            parent_id=graph['division'].id,
            division_type='verse',
            label='Duplicate child ordinal',
            normalized_locator='1:01',
            canonical_key=f"{graph['work'].id}.1.01",
            ordinal=1,
        ),
    ])

    with pytest.raises(IntegrityError):
        session.flush()


def test_same_child_ordinal_is_allowed_under_different_parents(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graph = _make_scope_graph(session, 'child-ordinal-scope')
    other_parent = WorkDivision(
        work_id=graph['work'].id,
        division_type='chapter',
        label='Chapter 2',
        normalized_locator='2',
        canonical_key=f"{graph['work'].id}.2",
        ordinal=2,
    )
    session.add(other_parent)
    session.flush()
    session.add_all([
        WorkDivision(
            work_id=graph['work'].id,
            parent_id=graph['division'].id,
            division_type='verse',
            label='Chapter 1 Verse 1',
            normalized_locator='1:1',
            canonical_key=f"{graph['work'].id}.1.1",
            ordinal=1,
        ),
        WorkDivision(
            work_id=graph['work'].id,
            parent_id=other_parent.id,
            division_type='verse',
            label='Chapter 2 Verse 1',
            normalized_locator='2:1',
            canonical_key=f"{graph['work'].id}.2.1",
            ordinal=1,
        ),
    ])
    session.flush()
