"""Metadata-only registration of legacy sources in the research catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.commentary.models import CommentaryEdition, CommentarySource
from app.library.models import EditionCoverage, EditionWorkSource, LibraryWork, TextEdition
from app.research_library.audit import append_source_audit_event
from app.research_library.models import (
    LegacySourceLink,
    SourceEdition,
    SourceEditionWork,
    SourcePublication,
)


IDENTITY_NAMESPACE = UUID('46252634-4b6b-5b7f-a74f-c806ce5ebf8f')
UNVERIFIED_PREFIX = 'unverified-metadata-sha256:'
METADATA_PREFIX = 'legacy-metadata-sha256:'


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    created_sources: int = 0
    existing_sources: int = 0
    created_publication_shells: int = 0
    created_work_links: int = 0
    created_legacy_links: int = 0
    created_audit_events: int = 0


class LegacyRegistrationError(ValueError):
    """Fixed, safe domain failure for actor or catalog inconsistency."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


def locked_actor_query(actor_id: UUID):
    return select(User).where(User.id == actor_id).with_for_update()


def _identity(kind: str, legacy_type: str, legacy_key: str) -> UUID:
    return uuid5(IDENTITY_NAMESPACE, f'{kind}:{legacy_type}:{legacy_key}')


def _canonical_digest(metadata: dict[str, Any]) -> str:
    encoded = json.dumps(
        metadata,
        ensure_ascii=True,
        separators=(',', ':'),
        sort_keys=True,
    ).encode('utf-8')
    return sha256(encoded).hexdigest()


def _unverified_checksum(metadata: dict[str, Any]) -> str:
    return f'{UNVERIFIED_PREFIX}{_canonical_digest(metadata)}'


def _publication_metadata_checksum(metadata: dict[str, Any]) -> str:
    return f'{METADATA_PREFIX}{_canonical_digest(metadata)}'


def _conflict() -> LegacyRegistrationError:
    return LegacyRegistrationError(
        'legacy_registration_conflict',
        'Legacy source registration conflict',
    )


def _verify(record: object, expected: dict[str, Any]) -> None:
    if any(getattr(record, attribute) != value for attribute, value in expected.items()):
        raise _conflict()


def _add_or_verify_link(
    session: Session,
    *,
    legacy_type: str,
    legacy_key: str,
    source_edition_id: UUID,
) -> bool:
    expected_id = _identity('legacy-link', legacy_type, legacy_key)
    existing = session.scalar(select(LegacySourceLink).where(
        LegacySourceLink.legacy_type == legacy_type,
        LegacySourceLink.legacy_key == legacy_key,
    ))
    if existing is not None:
        _verify(existing, {
            'legacy_type': legacy_type,
            'legacy_key': legacy_key,
            'source_edition_id': source_edition_id,
        })
        return False
    by_id = session.get(LegacySourceLink, expected_id)
    if by_id is not None:
        raise _conflict()
    session.add(LegacySourceLink(
        id=expected_id,
        legacy_type=legacy_type,
        legacy_key=legacy_key,
        source_edition_id=source_edition_id,
    ))
    session.flush()
    return True


def _add_or_verify_source(
    session: Session,
    *,
    legacy_type: str,
    legacy_key: str,
    values: dict[str, Any],
) -> tuple[SourceEdition, bool]:
    source_id = _identity('source-edition', legacy_type, legacy_key)
    source = session.get(SourceEdition, source_id)
    if source is None:
        source = SourceEdition(id=source_id, active_publication_id=None, **values)
        session.add(source)
        session.flush()
        return source, True
    _verify(source, {'id': source_id, 'active_publication_id': None, **values})
    return source, False


def _add_or_verify_publication(
    session: Session,
    *,
    legacy_type: str,
    legacy_key: str,
    source: SourceEdition,
    content_checksum: str,
) -> tuple[SourcePublication, bool]:
    publication_id = _identity('source-publication-v1', legacy_type, legacy_key)
    values = {
        'source_edition_id': source.id,
        'license_record_id': None,
        'version': 1,
        'ingest_run_id': None,
        'status': 'needs_rights_review',
        'validation_approved': False,
        'public_visibility': False,
        'source_checksum': source.checksum,
        'content_checksum': content_checksum,
        'published_at': None,
        'published_by_user_id': None,
        'reviewed_by_user_id': None,
    }
    publication = session.get(SourcePublication, publication_id)
    if publication is None:
        publication = session.scalar(select(SourcePublication).where(
            SourcePublication.source_edition_id == source.id,
            SourcePublication.version == 1,
        ))
        if publication is not None:
            raise _conflict()
        publication = SourcePublication(id=publication_id, **values)
        session.add(publication)
        session.flush()
        return publication, True
    _verify(publication, {'id': publication_id, **values})
    return publication, False


def _add_or_verify_work(
    session: Session,
    *,
    edition_code: str,
    source_edition_id: UUID,
    work_id: str,
    source_label: str,
    locator_scheme: str | None,
    attribution_override: str | None,
) -> bool:
    work_id_value = _identity(
        'source-edition-work', 'edition_work_source', f'{edition_code}:{work_id}'
    )
    values = {
        'source_edition_id': source_edition_id,
        'work_id': work_id,
        'source_label': source_label,
        'locator_scheme': locator_scheme,
        'attribution_override': attribution_override,
    }
    row = session.get(SourceEditionWork, work_id_value)
    if row is None:
        row = session.scalar(select(SourceEditionWork).where(
            SourceEditionWork.source_edition_id == source_edition_id,
            SourceEditionWork.work_id == work_id,
        ))
        if row is not None:
            raise _conflict()
        session.add(SourceEditionWork(id=work_id_value, **values))
        session.flush()
        return True
    _verify(row, {'id': work_id_value, **values})
    return False


def _scripture_metadata(edition: TextEdition) -> dict[str, Any]:
    return {
        'legacy_type': 'text_edition',
        'legacy_key': edition.edition_code,
        'name': edition.name,
        'reading_language': edition.reading_language,
        'source_language': edition.source_language,
        'script': edition.script,
        'translator': edition.translator,
        'publisher': edition.publisher,
        'published_year': edition.published_year,
        'attribution': edition.attribution,
        'provenance_url': edition.provenance_url,
        'source_tradition': edition.source_tradition,
        'relationship': edition.relationship,
        'versification': edition.versification,
        'verification_status': edition.verification_status,
    }


def _register_scripture(
    session: Session,
    edition: TextEdition,
    actor_id: UUID,
) -> RegistrationResult:
    legacy_type = 'text_edition'
    legacy_key = edition.edition_code
    metadata = _scripture_metadata(edition)
    checksum = edition.source_checksum or _unverified_checksum(metadata)
    source_values = {
        'title': edition.name,
        'edition_label': edition.edition_code,
        'translator': edition.translator,
        'editor': None,
        'publisher': edition.publisher,
        'publication_year': edition.published_year,
        'original_publication': (
            f'Source language: {edition.source_language}; '
            f'legacy relationship: {edition.relationship}'
        ),
        'language': edition.reading_language,
        'script': edition.script,
        'source_url': edition.provenance_url,
        'acquisition_source': edition.source_tradition,
        'checksum': checksum,
        'locator_scheme': edition.versification or 'chapter-verse',
        'attribution': edition.attribution,
        'verification_date': None,
    }
    source, source_created = _add_or_verify_source(
        session,
        legacy_type=legacy_type,
        legacy_key=legacy_key,
        values=source_values,
    )
    publication, publication_created = _add_or_verify_publication(
        session,
        legacy_type=legacy_type,
        legacy_key=legacy_key,
        source=source,
        content_checksum=_publication_metadata_checksum(metadata),
    )
    legacy_links = int(_add_or_verify_link(
        session,
        legacy_type=legacy_type,
        legacy_key=legacy_key,
        source_edition_id=source.id,
    ))

    explicit_rows = session.scalars(select(EditionWorkSource).where(
        EditionWorkSource.edition_code == edition.edition_code
    ).order_by(EditionWorkSource.work_id)).all()
    explicit = {row.work_id: row for row in explicit_rows}
    coverage_ids = session.scalars(select(EditionCoverage.work_id).where(
        EditionCoverage.edition_code == edition.edition_code
    ).order_by(EditionCoverage.work_id)).all()
    covered_work_ids = sorted(set(explicit) | set(coverage_ids))
    works = {
        row.id: row for row in session.scalars(select(LibraryWork).where(
            LibraryWork.id.in_(covered_work_ids)
        ).order_by(LibraryWork.id)).all()
    } if covered_work_ids else {}
    if set(works) != set(covered_work_ids):
        raise _conflict()
    created_work_links = 0
    for work_id in covered_work_ids:
        legacy_work = explicit.get(work_id)
        work = works[work_id]
        created_work_links += int(_add_or_verify_work(
            session,
            edition_code=edition.edition_code,
            source_edition_id=source.id,
            work_id=work_id,
            source_label=legacy_work.source_label if legacy_work else work.title,
            locator_scheme=edition.versification or 'chapter-verse',
            attribution_override=(
                legacy_work.attribution if legacy_work else edition.attribution
            ),
        ))
        if legacy_work is not None:
            legacy_links += int(_add_or_verify_link(
                session,
                legacy_type='edition_work_source',
                legacy_key=f'{edition.edition_code}:{work_id}',
                source_edition_id=source.id,
            ))

    audit_created = 0
    if source_created:
        counts = {
            'publication_shells': int(publication_created),
            'work_links': created_work_links,
            'legacy_links': legacy_links,
        }
        append_source_audit_event(
            session,
            actor_id=actor_id,
            action='legacy_source_registered',
            prior_state=None,
            resulting_state={
                'legacy_type': legacy_type,
                'legacy_key': legacy_key,
                'source_edition_id': str(source.id),
                'shell_publication_id': str(publication.id),
                'status': 'needs_rights_review',
                'counts': counts,
            },
            source_edition_id=source.id,
            source_publication_id=publication.id,
        )
        audit_created = 1
    return RegistrationResult(
        created_sources=int(source_created),
        existing_sources=int(not source_created),
        created_publication_shells=int(publication_created),
        created_work_links=created_work_links,
        created_legacy_links=legacy_links,
        created_audit_events=audit_created,
    )


def _commentary_metadata(source: CommentarySource) -> dict[str, Any]:
    return {
        'legacy_type': 'commentary_source',
        'legacy_key': source.id,
        'title': source.title,
        'abbreviation': source.abbreviation,
        'author': source.author,
        'publication_period': source.publication_period,
        'tradition': source.tradition,
        'language': source.language,
        'attribution': source.attribution,
        'provenance_url': source.provenance_url,
    }


def _register_commentary(
    session: Session,
    legacy: CommentarySource,
    actor_id: UUID,
) -> RegistrationResult:
    legacy_type = 'commentary_source'
    legacy_key = legacy.id
    metadata = _commentary_metadata(legacy)
    newest = session.scalar(select(CommentaryEdition).where(
        CommentaryEdition.source_id == legacy.id
    ).order_by(
        CommentaryEdition.created_at.desc(),
        CommentaryEdition.dataset_version.desc(),
        CommentaryEdition.id.desc(),
    ).limit(1))
    if newest is None:
        checksum = _unverified_checksum(metadata)
        edition_label = legacy.abbreviation
        acquisition_source = legacy.tradition
    else:
        checksum = newest.source_checksum
        metadata = {
            **metadata,
            'selected_dataset_version': newest.dataset_version,
            'selected_source_checksum': newest.source_checksum,
        }
        edition_label = f'{legacy.abbreviation} | dataset {newest.dataset_version}'
        acquisition_source = (
            f'{legacy.tradition} | legacy dataset {newest.dataset_version}'
        )
    source_values = {
        'title': legacy.title,
        'edition_label': edition_label,
        'translator': None,
        'editor': legacy.author,
        'publisher': None,
        'publication_year': None,
        'original_publication': legacy.publication_period,
        'language': legacy.language,
        'script': None,
        'source_url': legacy.provenance_url,
        'acquisition_source': acquisition_source,
        'checksum': checksum,
        'locator_scheme': 'commentary-entry',
        'attribution': legacy.attribution,
        'verification_date': None,
    }
    source, source_created = _add_or_verify_source(
        session, legacy_type=legacy_type, legacy_key=legacy_key, values=source_values
    )
    publication, publication_created = _add_or_verify_publication(
        session,
        legacy_type=legacy_type,
        legacy_key=legacy_key,
        source=source,
        content_checksum=_publication_metadata_checksum(metadata),
    )
    legacy_link_created = _add_or_verify_link(
        session,
        legacy_type=legacy_type,
        legacy_key=legacy_key,
        source_edition_id=source.id,
    )
    audit_created = 0
    if source_created:
        append_source_audit_event(
            session,
            actor_id=actor_id,
            action='legacy_source_registered',
            prior_state=None,
            resulting_state={
                'legacy_type': legacy_type,
                'legacy_key': legacy_key,
                'source_edition_id': str(source.id),
                'shell_publication_id': str(publication.id),
                'status': 'needs_rights_review',
                'counts': {
                    'publication_shells': int(publication_created),
                    'work_links': 0,
                    'legacy_links': int(legacy_link_created),
                },
            },
            source_edition_id=source.id,
            source_publication_id=publication.id,
        )
        audit_created = 1
    return RegistrationResult(
        created_sources=int(source_created),
        existing_sources=int(not source_created),
        created_publication_shells=int(publication_created),
        created_legacy_links=int(legacy_link_created),
        created_audit_events=audit_created,
    )


def _sum_results(results: list[RegistrationResult]) -> RegistrationResult:
    totals = {field: 0 for field in RegistrationResult.__dataclass_fields__}
    for result in results:
        for field, value in asdict(result).items():
            totals[field] += value
    return RegistrationResult(**totals)


def register_legacy_sources(session: Session, actor_id: UUID) -> RegistrationResult:
    """Register legacy source metadata without committing or copying content."""
    actor = session.scalar(locked_actor_query(actor_id))
    if actor is None:
        raise LegacyRegistrationError('actor_not_found', 'Actor user was not found')
    if not actor.is_active:
        raise LegacyRegistrationError('actor_inactive', 'Actor user is inactive')
    if actor.role != 'administrator':
        raise LegacyRegistrationError(
            'actor_not_administrator', 'Actor must be an active administrator'
        )

    results: list[RegistrationResult] = []
    editions = session.scalars(select(TextEdition).order_by(TextEdition.edition_code)).all()
    for edition in editions:
        results.append(_register_scripture(session, edition, actor_id))
    commentary_sources = session.scalars(select(CommentarySource).order_by(
        CommentarySource.id
    )).all()
    for source in commentary_sources:
        results.append(_register_commentary(session, source, actor_id))
    return _sum_results(results)
