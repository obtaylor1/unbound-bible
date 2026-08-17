from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session, raiseload

from app.auth.models import User
from app.database import Base, create_database_engine, create_session_factory
from app.library.models import LibraryWork  # noqa: F401 - registers referenced table
from app.research_library.eligibility import (
    EligibilityDecision,
    evaluate_publication,
    public_eligibility_predicate,
)
from app.research_library.models import (
    PUBLICATION_STATUSES,
    LicenseRecord,
    SourceEdition,
    SourcePublication,
)


REASON_CASES = (
    ('publication_not_active', 'publication', 'status', 'verified'),
    ('publication_not_selected', 'edition', 'active_publication_id', uuid4()),
    ('edition_mismatch', 'publication', 'source_edition_id', uuid4()),
    ('validation_not_approved', 'publication', 'validation_approved', False),
    ('not_public', 'publication', 'public_visibility', False),
    ('license_missing', 'license', None, None),
    ('license_mismatch', 'license', 'id', uuid4()),
    ('license_mismatch', 'license', 'source_edition_id', uuid4()),
    ('rights_not_reviewed', 'license', 'reviewer_id', None),
    ('rights_not_reviewed', 'license', 'verification_date', None),
    ('commercial_use_not_allowed', 'license', 'commercial_use_allowed', False),
    ('commercial_use_not_allowed', 'license', 'commercial_use_allowed', None),
    ('display_not_allowed', 'license', 'display_allowed', False),
    ('display_not_allowed', 'license', 'display_allowed', None),
    ('redistribution_not_allowed', 'license', 'redistribution_allowed', False),
    ('redistribution_not_allowed', 'license', 'redistribution_allowed', None),
    ('attribution_requirement_unknown', 'license', 'attribution_required', None),
    ('attribution_missing', 'license', 'required_attribution_text', '   '),
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


def _eligible_transient_graph() -> tuple[SourcePublication, SourceEdition, LicenseRecord]:
    edition_id = uuid4()
    publication_id = uuid4()
    license_id = uuid4()
    publication = SourcePublication(
        id=publication_id,
        source_edition_id=edition_id,
        license_record_id=license_id,
        version=1,
        status='active',
        validation_approved=True,
        public_visibility=True,
        source_checksum='a' * 64,
        content_checksum='b' * 64,
    )
    edition = SourceEdition(
        id=edition_id,
        active_publication_id=publication_id,
        title='Eligible edition',
        edition_label='1',
        language='eng',
        checksum='a' * 64,
        locator_scheme='chapter_verse',
    )
    license_record = LicenseRecord(
        id=license_id,
        source_edition_id=edition_id,
        license_name='Explicit permissions',
        is_public_domain=None,
        commercial_use_allowed=True,
        display_allowed=True,
        redistribution_allowed=True,
        attribution_required=True,
        required_attribution_text='Use this attribution',
        reviewer_id=uuid4(),
        verification_date=datetime(2025, 1, 1, tzinfo=UTC),
    )
    return publication, edition, license_record


def _persist_graph(
    session: Session,
    suffix: str,
    *,
    status: str = 'active',
    selected: bool = True,
    has_license: bool = True,
    **changes,
) -> tuple[SourcePublication, SourceEdition, LicenseRecord | None]:
    reviewer = User(
        email=f'{suffix}@example.com',
        email_normalized=f'{suffix}@example.com',
        username=f'reviewer-{suffix}',
        password_hash='hash',
    )
    edition = SourceEdition(
        title=f'Edition {suffix}',
        edition_label='1',
        language='eng',
        checksum=(suffix[0] if suffix else 'a') * 64,
        locator_scheme='chapter_verse',
    )
    session.add_all([reviewer, edition])
    session.flush()
    license_record = None
    if has_license:
        license_record = LicenseRecord(
            source_edition_id=edition.id,
            license_name=f'License {suffix}',
            is_public_domain=None,
            commercial_use_allowed=True,
            display_allowed=True,
            redistribution_allowed=True,
            attribution_required=False,
            required_attribution_text=None,
            reviewer_id=reviewer.id,
            verification_date=datetime(2025, 1, 1, tzinfo=UTC),
        )
        for key, value in changes.items():
            if hasattr(license_record, key):
                setattr(license_record, key, value)
        session.add(license_record)
        session.flush()
    publication = SourcePublication(
        source_edition_id=edition.id,
        license_record_id=license_record.id if license_record else None,
        version=1,
        status=status,
        validation_approved=changes.get('validation_approved', True),
        public_visibility=changes.get('public_visibility', True),
        source_checksum='c' * 64,
        content_checksum='d' * 64,
    )
    session.add(publication)
    session.flush()
    if selected:
        edition.active_publication_id = publication.id
        session.flush()
    return publication, edition, license_record


def test_eligibility_decision_is_immutable_and_slotted() -> None:
    decision = EligibilityDecision(eligible=True, reasons=())

    with pytest.raises((AttributeError, TypeError)):
        decision.eligible = False  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        decision.extra = True  # type: ignore[attr-defined]


def test_fully_eligible_selected_publication_passes() -> None:
    publication, edition, license_record = _eligible_transient_graph()

    assert evaluate_publication(publication, edition, license_record) == EligibilityDecision(
        eligible=True, reasons=()
    )


@pytest.mark.parametrize(
    ('reason', 'target', 'attribute', 'value'),
    REASON_CASES,
)
def test_each_failed_gate_has_its_stable_reason(
    reason: str, target: str, attribute: str | None, value: object
) -> None:
    publication, edition, license_record = _eligible_transient_graph()
    if target == 'license' and attribute is None:
        license_record = None
    else:
        selected_record = {
            'publication': publication,
            'edition': edition,
            'license': license_record,
        }[target]
        setattr(selected_record, attribute, value)

    assert evaluate_publication(publication, edition, license_record) == EligibilityDecision(
        eligible=False, reasons=(reason,)
    )


def test_attribution_not_required_needs_no_text_and_public_domain_is_irrelevant() -> None:
    publication, edition, license_record = _eligible_transient_graph()
    license_record.attribution_required = False
    license_record.required_attribution_text = None
    license_record.is_public_domain = None

    assert evaluate_publication(publication, edition, license_record).eligible is True


@pytest.mark.parametrize('status', [s for s in PUBLICATION_STATUSES if s != 'active'])
def test_every_non_active_status_fails(status: str) -> None:
    publication, edition, license_record = _eligible_transient_graph()
    publication.status = status

    assert evaluate_publication(publication, edition, license_record).reasons == (
        'publication_not_active',
    )


def test_historical_active_publication_is_not_selected() -> None:
    publication, edition, license_record = _eligible_transient_graph()
    edition.active_publication_id = uuid4()

    assert evaluate_publication(publication, edition, license_record).reasons == (
        'publication_not_selected',
    )


def test_reasons_are_unique_and_in_documented_stable_order() -> None:
    publication, edition, license_record = _eligible_transient_graph()
    publication.status = 'disabled'
    edition.active_publication_id = uuid4()
    publication.source_edition_id = uuid4()
    publication.validation_approved = False
    publication.public_visibility = False
    license_record.id = uuid4()
    license_record.source_edition_id = uuid4()
    license_record.reviewer_id = None
    license_record.verification_date = None
    license_record.commercial_use_allowed = None
    license_record.display_allowed = False
    license_record.redistribution_allowed = None
    license_record.attribution_required = None
    license_record.required_attribution_text = '  '

    assert evaluate_publication(publication, edition, license_record).reasons == (
        'publication_not_active',
        'publication_not_selected',
        'edition_mismatch',
        'validation_not_approved',
        'not_public',
        'license_mismatch',
        'rights_not_reviewed',
        'commercial_use_not_allowed',
        'display_not_allowed',
        'redistribution_not_allowed',
        'attribution_requirement_unknown',
    )


def test_evaluator_does_not_issue_lazy_database_queries(
    research_library_session: Session,
) -> None:
    session = research_library_session
    publication, edition, license_record = _persist_graph(session, 'lazy')
    session.expire_all()
    publication = session.scalars(
        select(SourcePublication)
        .options(raiseload('*'))
        .where(SourcePublication.id == publication.id)
    ).one()
    edition = session.scalars(
        select(SourceEdition).options(raiseload('*')).where(SourceEdition.id == edition.id)
    ).one()
    license_record = session.scalars(
        select(LicenseRecord)
        .options(raiseload('*'))
        .where(LicenseRecord.id == license_record.id)
    ).one()
    statements: list[str] = []

    def record_statement(*_args) -> None:
        statements.append(_args[2])

    event.listen(session.bind, 'before_cursor_execute', record_statement)
    try:
        assert evaluate_publication(publication, edition, license_record).eligible is True
    finally:
        event.remove(session.bind, 'before_cursor_execute', record_statement)
    assert statements == []


def test_sql_predicate_matches_python_evaluator_and_outer_join_excludes_missing_license(
    research_library_session: Session,
) -> None:
    session = research_library_session
    graphs = [
        _persist_graph(session, 'eligible'),
        _persist_graph(session, 'historical', selected=False),
        _persist_graph(session, 'disabled', status='disabled'),
        _persist_graph(session, 'unvalidated', validation_approved=False),
        _persist_graph(session, 'private', public_visibility=False),
        _persist_graph(session, 'commercial-false', commercial_use_allowed=False),
        _persist_graph(session, 'commercial-none', commercial_use_allowed=None),
        _persist_graph(session, 'display-false', display_allowed=False),
        _persist_graph(session, 'display-none', display_allowed=None),
        _persist_graph(session, 'redistribution-false', redistribution_allowed=False),
        _persist_graph(session, 'redistribution-none', redistribution_allowed=None),
        _persist_graph(session, 'reviewer', reviewer_id=None),
        _persist_graph(session, 'verification', verification_date=None),
        _persist_graph(session, 'attribution-unknown', attribution_required=None),
        _persist_graph(session, 'missing', has_license=False),
        _persist_graph(
            session,
            'attribution-blank',
            attribution_required=True,
            required_attribution_text='   ',
        ),
    ]
    expected_ids = {
        publication.id
        for publication, edition, license_record in graphs
        if evaluate_publication(publication, edition, license_record).eligible
    }

    actual_ids = set(
        session.scalars(
            select(SourcePublication.id)
            .join(SourceEdition, SourceEdition.id == SourcePublication.source_edition_id)
            .outerjoin(
                LicenseRecord,
                LicenseRecord.id == SourcePublication.license_record_id,
            )
            .where(public_eligibility_predicate())
        )
    )

    assert actual_ids == expected_ids == {graphs[0][0].id}


def test_sql_predicate_contains_license_and_edition_identity_gates() -> None:
    compiled = str(
        public_eligibility_predicate().compile(
            compile_kwargs={'literal_binds': True}
        )
    )

    assert 'source_publications.source_edition_id = source_editions.id' in compiled
    assert 'source_publications.license_record_id = license_records.id' in compiled
    assert 'license_records.source_edition_id = source_editions.id' in compiled
