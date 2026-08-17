from collections.abc import Generator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.database import Base, create_database_engine, create_session_factory
from app.library.models import LibraryWork
from app.research_library.models import (
    PUBLICATION_STATUSES,
    CitationAnchor,
    ContentUnit,
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


@pytest.fixture
def research_library_session(test_settings) -> Generator[Session, None, None]:
    engine = create_database_engine(test_settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


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
        source_classification='primary_text',
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
        classification='primary_text',
        hierarchy_level='verse',
        language='eng',
        content_digest='d' * 64,
        text_content=unit.normalized_text,
        search_document=None,
    )
    legacy_source = LegacySourceLink(
        legacy_table='text_editions',
        legacy_key='charles-1912',
        source_edition_id=edition.id,
    )
    legacy_content = LegacyContentLink(
        legacy_table='biblical_texts',
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
    ('model', 'values'),
    [
        (WorkDivision, {'division_type': 'page'}),
        (WorkDivision, {'ordinal': 0}),
        (SourcePublication, {'status': 'draft'}),
        (SourcePublication, {'version': 0}),
        (ContentUnit, {'direction': 'sideways'}),
        (ContentUnit, {'textual_certainty': 'ai_guess'}),
        (ResearchChunk, {'ordinal': 0}),
    ],
)
def test_research_library_models_reject_invalid_controlled_values(
    research_library_session: Session,
    model: type,
    values: dict,
) -> None:
    session = research_library_session
    work = LibraryWork(id='constraint-work', title='Constraint Work')
    edition = SourceEdition(
        title='Constraint Edition',
        edition_label='1',
        language='eng',
        checksum='e' * 64,
        locator_scheme='chapter_verse',
    )
    session.add_all([work, edition])
    session.flush()
    division = WorkDivision(
        work_id=work.id,
        division_type='chapter',
        label='Chapter 1',
        normalized_locator='1',
        canonical_key='constraint-work.1',
        ordinal=1,
    )
    session.add(division)
    session.flush()
    publication = SourcePublication(
        source_edition_id=edition.id,
        version=1,
        status='verified',
        validation_approved=True,
        public_visibility=False,
        source_checksum='e' * 64,
        content_checksum='f' * 64,
    )
    session.add(publication)
    session.flush()

    defaults = {
        WorkDivision: {
            'work_id': work.id,
            'division_type': 'verse',
            'label': 'Verse 1',
            'normalized_locator': '1:1',
            'canonical_key': 'constraint-work.1.1',
            'ordinal': 1,
        },
        SourcePublication: {
            'source_edition_id': edition.id,
            'version': 2,
            'status': 'verified',
            'validation_approved': True,
            'public_visibility': False,
            'source_checksum': 'e' * 64,
            'content_checksum': 'f' * 64,
        },
        ContentUnit: {
            'source_publication_id': publication.id,
            'work_division_id': division.id,
            'language': 'eng',
            'script': 'Latn',
            'direction': 'ltr',
            'ordinal': 1,
            'normalized_text': 'Text',
            'source_locator': '1:1',
            'textual_certainty': 'visible_text',
            'checksum': '1' * 64,
        },
        ResearchChunk: {
            'source_edition_id': edition.id,
            'source_publication_id': publication.id,
            'work_id': work.id,
            'work_division_id': division.id,
            'ordinal': 1,
            'boundary_type': 'verse',
            'classification': 'primary_text',
            'hierarchy_level': 'verse',
            'language': 'eng',
            'content_digest': '2' * 64,
            'text_content': 'Text',
        },
    }
    invalid = {**defaults[model], **values}
    session.add(model(**invalid))
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
