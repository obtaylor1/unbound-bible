"""Caller-transaction-owned staging, validation, publication, and rollback."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
import re
from types import MappingProxyType
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commentary.models import (
    CommentaryEdition,
    CommentaryEntry,
    CommentaryImportRun,
    CommentaryPublication,
    CommentarySource,
    CommentaryValidationFinding,
    StagedCommentaryEntry,
)

from .types import NormalizedCommentaryEntry, _normalize_scalar
from .validate import ValidationFinding, has_exact_chapter_coverage, validate_commentary


_CHECKSUM = re.compile(r'^[0-9a-f]{64}$')
_EXCLUSION_ARTIFACT = re.compile(r'^[A-Z0-9]{3}-[1-9][0-9]*\.json$')
_EXCLUSION_FIELDS = frozenset({
    'source_id', 'artifact', 'artifact_sha256', 'content_index',
    'reason', 'reviewer', 'reviewed_on',
})
_ENTRY_TYPES = ('book_intro', 'chapter_intro', 'verse', 'verse_range')
_PROVIDER_AUDIT_FIELDS = frozenset({
    'provider_book_count', 'provider_chapter_count', 'provider_content_record_count',
    'acquired_normalized_entry_count', 'normalized_entry_type_counts',
    'reviewed_exclusion_count', 'covered_normalized_chapter_count',
    'empty_provider_chapters',
})
_PROVIDER_AUDIT_DERIVED_FIELDS = frozenset({
    'formula', 'expected_normalized_entry_count', 'variance',
})
_WARNING_REVIEW_POLICY = MappingProxyType({
    'missing_chapter_intro': MappingProxyType({
        'disposition': 'accepted',
        'rationale': (
            'The provider omits a chapter introduction; the application preserves that '
            'absence and does not fabricate commentary.'
        ),
    }),
    'multiple_notes_at_anchor': MappingProxyType({
        'disposition': 'accepted',
        'rationale': 'Distinct provider notes at the same anchor are preserved as distinct entries.',
    }),
    'reviewed_exclusion': MappingProxyType({
        'disposition': 'accepted',
        'rationale': 'The exclusion is accepted only through a checksum-bound reviewed decision.',
    }),
})
_AUDIT_FORMULA = (
    'normalized entries = provider content records - reviewed exclusions '
    '+ book introductions + chapter introductions'
)


def _audit_nonnegative_integer(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f'provider audit {name} must be a nonnegative integer.')
    return value


def reconcile_provider_audit(
    audit: object, rows: Iterable[NormalizedCommentaryEntry],
) -> dict[str, object]:
    """Recompute and seal the provider-to-normalized count reconciliation."""
    if not isinstance(audit, Mapping):
        raise ValueError('provider audit must be a JSON object.')
    fields = set(audit)
    if fields not in (
        _PROVIDER_AUDIT_FIELDS,
        _PROVIDER_AUDIT_FIELDS | _PROVIDER_AUDIT_DERIVED_FIELDS,
    ):
        raise ValueError('provider audit has an invalid schema.')
    materialized = tuple(rows)
    if not all(isinstance(row, NormalizedCommentaryEntry) for row in materialized):
        raise ValueError('provider audit rows must be normalized commentary entries.')
    counts = {
        field: _audit_nonnegative_integer(field, audit[field])
        for field in _PROVIDER_AUDIT_FIELDS
        if field not in {'normalized_entry_type_counts', 'empty_provider_chapters'}
    }
    raw_breakdown = audit['normalized_entry_type_counts']
    if not isinstance(raw_breakdown, Mapping) or set(raw_breakdown) != set(_ENTRY_TYPES):
        raise ValueError('provider audit normalized entry type counts have an invalid schema.')
    breakdown = {
        entry_type: _audit_nonnegative_integer(
            f'normalized_entry_type_counts.{entry_type}', raw_breakdown[entry_type],
        )
        for entry_type in _ENTRY_TYPES
    }
    actual_breakdown = Counter(row.entry_type for row in materialized)
    if breakdown != {entry_type: actual_breakdown[entry_type] for entry_type in _ENTRY_TYPES}:
        raise ValueError('provider audit normalized entry type counts do not match staged rows.')
    if counts['acquired_normalized_entry_count'] != len(materialized):
        raise ValueError('provider audit acquired normalized entry count does not match staged rows.')
    observed_books = {row.work_id for row in materialized}
    if counts['provider_book_count'] != len(observed_books):
        raise ValueError('provider audit book count does not match normalized books.')
    covered_chapters = {
        (row.work_id, row.chapter) for row in materialized if row.chapter is not None
    }
    if counts['covered_normalized_chapter_count'] != len(covered_chapters):
        raise ValueError('provider audit covered chapter count does not match staged rows.')
    empty_value = audit['empty_provider_chapters']
    if type(empty_value) is not list:
        raise ValueError('provider audit empty provider chapters must be a list.')
    empty_chapters: list[dict[str, object]] = []
    empty_identities: set[tuple[str, str, int]] = set()
    for value in empty_value:
        if not isinstance(value, Mapping) or set(value) != {
            'source_book_id', 'work_id', 'chapter',
        }:
            raise ValueError('provider audit empty provider chapter has an invalid schema.')
        source_book_id, work_id, chapter = (
            value['source_book_id'], value['work_id'], value['chapter'],
        )
        if (
            type(source_book_id) is not str
            or re.fullmatch(r'[A-Z0-9]{1,16}', source_book_id) is None
            or type(work_id) is not str or not work_id
            or type(chapter) is not int or chapter <= 0
            or (work_id, chapter) in covered_chapters
            or (source_book_id, work_id, chapter) in empty_identities
        ):
            raise ValueError('provider audit empty provider chapter is invalid or covered.')
        empty_identities.add((source_book_id, work_id, chapter))
        empty_chapters.append({
            'source_book_id': source_book_id, 'work_id': work_id, 'chapter': chapter,
        })
    empty_chapters.sort(key=lambda value: (
        value['source_book_id'], value['chapter'], value['work_id'],
    ))
    if empty_value != empty_chapters:
        raise ValueError('provider audit empty provider chapters must be canonical and ordered.')
    if (
        counts['provider_chapter_count']
        != counts['covered_normalized_chapter_count'] + len(empty_chapters)
    ):
        raise ValueError('provider audit chapter counts do not reconcile with empty chapters.')
    expected = (
        counts['provider_content_record_count'] - counts['reviewed_exclusion_count']
        + breakdown['book_intro'] + breakdown['chapter_intro']
    )
    variance = counts['acquired_normalized_entry_count'] - expected
    if expected < 0 or variance != 0:
        raise ValueError('provider audit normalized entry formula has a nonzero variance.')
    result = {
        **{field: counts[field] for field in _PROVIDER_AUDIT_FIELDS
           if field not in {'normalized_entry_type_counts', 'empty_provider_chapters'}},
        'normalized_entry_type_counts': breakdown,
        'empty_provider_chapters': empty_chapters,
        'formula': _AUDIT_FORMULA,
        'expected_normalized_entry_count': expected,
        'variance': variance,
    }
    if fields == _PROVIDER_AUDIT_FIELDS | _PROVIDER_AUDIT_DERIVED_FIELDS and dict(audit) != result:
        raise ValueError('provider audit derived reconciliation was tampered with.')
    return result


def warning_review_snapshot(counts_by_code: object) -> dict[str, object]:
    """Acknowledge only warnings covered by the bounded reviewed policy."""
    if not isinstance(counts_by_code, Mapping):
        raise ValueError('warning counts must be a mapping.')
    counts: dict[str, int] = {}
    for code in sorted(counts_by_code):
        count = counts_by_code[code]
        if type(code) is not str or type(count) is not int or count <= 0:
            raise ValueError('warning counts must use warning codes and positive integers.')
        if code not in _WARNING_REVIEW_POLICY:
            raise ValueError(f'warning code {code!r} has no reviewed disposition.')
        counts[code] = count
    dispositions = {
        code: dict(_WARNING_REVIEW_POLICY[code]) for code in counts
    }
    warning_count = sum(counts.values())
    return {
        'policy_version': 1,
        'counts_by_code': counts,
        'dispositions_by_code': dispositions,
        'warning_count': warning_count,
        'acknowledged_warning_count': warning_count,
        'all_warnings_reviewed': True,
    }


def _safe_exclusion_text(name: str, value: object, maximum: int) -> bool:
    try:
        return _normalize_scalar(name, value, maximum=maximum) == value
    except ValueError:
        return False


def _valid_review_date(value: object) -> bool:
    if type(value) is not str or not _safe_exclusion_text(
        'reviewed exclusion date', value, 10,
    ):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return value == parsed.isoformat() and parsed <= date.today()
_PUBLICATION_CONSTRAINTS = frozenset({
    'uq_commentary_editions_source_dataset_version',
    'uq_commentary_publications_source_version',
    'uq_commentary_publications_active_source',
})


class CommentaryPublicationConflict(ValueError):
    """A concurrent publication operation won a known uniqueness race."""


def is_commentary_publication_conflict(error: IntegrityError) -> bool:
    """Classify only known publication uniqueness failures across supported DBs."""
    original = error.orig
    diagnostic = getattr(original, 'diag', None)
    constraint = getattr(diagnostic, 'constraint_name', None)
    if constraint in _PUBLICATION_CONSTRAINTS:
        return True
    message = str(original).casefold()
    return any(fragment in message for fragment in (
        'unique constraint failed: commentary_publications.source_id',
        'unique constraint failed: commentary_publications.source_id, '
        'commentary_publications.version',
        'unique constraint failed: commentary_editions.source_id, '
        'commentary_editions.dataset_version',
    ))


@contextmanager
def _publication_conflict_boundary():
    try:
        yield
    except IntegrityError as exc:
        if is_commentary_publication_conflict(exc):
            raise CommentaryPublicationConflict(
                'Another commentary publication operation won the race.'
            ) from exc
        raise


def _ensure_caller_owned_outer_transaction(session: Session) -> None:
    """Materialize SQLite's deferred outer transaction before a SAVEPOINT.

    Python's SQLite driver otherwise lets a first SAVEPOINT become the physical
    top-level transaction; releasing it would commit despite the Session still
    appearing to own a transaction. ``BEGIN IMMEDIATE`` also serializes writers
    before they read publication state, matching the row lock used elsewhere.
    """
    connection = session.connection()
    if connection.dialect.name != 'sqlite':
        return
    driver_connection = connection.connection.driver_connection
    if not driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError('metadata_snapshot JSON object keys must be strings.')
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _json_snapshot(value: object) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError('metadata_snapshot must be a JSON object.')
    try:
        encoded = json.dumps(_plain_json(value), ensure_ascii=False, allow_nan=False)
        copied = json.loads(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError('metadata_snapshot must contain finite JSON values.') from exc
    return copied


def stage_bundle(
    session: Session,
    *,
    source_id: str,
    source_checksum: str,
    metadata_snapshot: Mapping[str, object],
    rows: Iterable[NormalizedCommentaryEntry],
) -> CommentaryImportRun:
    """Persist an immutable scalar snapshot of a normalized local bundle."""
    if type(source_id) is not str or not source_id:
        raise ValueError('source_id must identify an existing commentary source.')
    if session.get(CommentarySource, source_id) is None:
        raise ValueError('Commentary source was not found.')
    if type(source_checksum) is not str or _CHECKSUM.fullmatch(source_checksum) is None:
        raise ValueError('source_checksum must be 64 lowercase hexadecimal characters.')
    snapshot = _json_snapshot(metadata_snapshot)
    try:
        materialized = tuple(rows)
    except TypeError as exc:
        raise ValueError('rows must be an iterable of NormalizedCommentaryEntry values.') from exc
    if not all(isinstance(row, NormalizedCommentaryEntry) for row in materialized):
        raise ValueError('rows must contain only NormalizedCommentaryEntry values.')

    run = CommentaryImportRun(
        source_id=source_id,
        source_checksum=source_checksum,
        metadata_snapshot=snapshot,
        status='staged',
        staged_count=len(materialized),
    )
    session.add(run)
    session.flush()
    session.add_all([
        StagedCommentaryEntry(
            run_id=run.id,
            work_id=row.work_id,
            chapter=row.chapter,
            verse_start=row.verse_start,
            verse_end=row.verse_end,
            entry_type=row.entry_type,
            heading=row.heading,
            body=row.body,
            source_locator=row.source_locator,
            row_checksum=row.row_checksum,
            position=row.position,
        )
        for row in materialized
    ])
    session.flush()
    return run


def _staged_order_key(row: StagedCommentaryEntry) -> tuple[object, ...]:
    """Canonical semantic order shared by validation, manifests, and copying."""
    return (
        row.work_id,
        row.chapter if row.chapter is not None else -1,
        row.verse_start if row.verse_start is not None else -1,
        row.verse_end if row.verse_end is not None else -1,
        row.entry_type,
        row.position,
        row.id,
    )


def _staged_records(session: Session, run_id: UUID) -> list[StagedCommentaryEntry]:
    records = session.scalars(
        select(StagedCommentaryEntry)
        .where(StagedCommentaryEntry.run_id == run_id)
        .order_by(StagedCommentaryEntry.id)
    ).all()
    return sorted(records, key=_staged_order_key)


def _normalized_staged_rows(session: Session, run_id: UUID) -> list[NormalizedCommentaryEntry]:
    return [
        NormalizedCommentaryEntry(
            row.work_id,
            row.chapter,
            row.verse_start,
            row.verse_end,
            row.entry_type,
            row.heading,
            row.body,
            row.source_locator,
            row.position,
        )
        for row in _staged_records(session, run_id)
    ]


def _manifest(
    source_id: str,
    source_checksum: str,
    metadata: Mapping[str, object],
    rows: Iterable[NormalizedCommentaryEntry],
) -> str:
    relevant_metadata = dict(metadata)
    relevant_metadata.pop('validation_manifest', None)
    payload = [
        'commentary-verified-run-v2',
        source_id,
        source_checksum,
        relevant_metadata,
        [[
            row.work_id, row.chapter, row.verse_start, row.verse_end,
            row.entry_type, row.heading, row.body, row.source_locator,
            row.position, row.row_checksum,
        ] for row in rows],
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')
    return sha256(encoded).hexdigest()


def _previous_coverage(session: Session, source_id: str) -> Mapping[str, object] | None:
    edition = session.scalar(
        select(CommentaryEdition)
        .join(CommentaryPublication, CommentaryPublication.edition_id == CommentaryEdition.id)
        .where(
            CommentaryPublication.source_id == source_id,
            CommentaryPublication.active.is_(True),
            CommentaryEdition.source_id == source_id,
        )
    )
    if edition is None or not edition.coverage:
        return None
    return edition.coverage


def validate_run(session: Session, run_id: UUID) -> CommentaryImportRun:
    """Replace validation findings and persist the deterministic coverage snapshot."""
    run = session.scalar(
        select(CommentaryImportRun)
        .where(CommentaryImportRun.id == run_id)
        .with_for_update()
    )
    if run is None:
        raise ValueError('Commentary import run was not found.')
    if run.status not in {'staged', 'validated'}:
        raise ValueError('Only a staged or validated commentary run may be validated.')
    metadata = _json_snapshot(run.metadata_snapshot)
    expected = metadata.get('expected_books')
    if type(expected) is not list or not expected or any(type(item) is not str for item in expected):
        raise ValueError('metadata_snapshot expected_books must be a nonempty list of work IDs.')

    normalized_rows = _normalized_staged_rows(session, run.id)
    result = validate_commentary(
        normalized_rows,
        expected_books=set(expected),
        previous_coverage=_previous_coverage(session, run.source_id),
    )
    exclusions = metadata.get('reviewed_exclusions', [])
    exclusion_count = metadata.get('reviewed_exclusion_count', 0)
    if (
        type(exclusions) is not list or type(exclusion_count) is not int
        or exclusion_count != len(exclusions)
    ):
        raise ValueError('metadata_snapshot reviewed exclusions are inconsistent.')
    reviewed_findings: list[ValidationFinding] = []
    seen_exclusions: set[tuple[str, int]] = set()
    for exclusion in exclusions:
        if type(exclusion) is not dict or set(exclusion) != _EXCLUSION_FIELDS:
            raise ValueError('metadata_snapshot reviewed exclusion has an invalid schema.')
        artifact = exclusion['artifact']
        content_index = exclusion['content_index']
        identity = (artifact, content_index)
        if (
            exclusion['source_id'] != run.source_id
            or type(artifact) is not str or _EXCLUSION_ARTIFACT.fullmatch(artifact) is None
            or type(exclusion['artifact_sha256']) is not str
            or _CHECKSUM.fullmatch(exclusion['artifact_sha256']) is None
            or type(content_index) is not int or content_index < 0
            or identity in seen_exclusions
            or not _safe_exclusion_text('reviewed exclusion reason', exclusion['reason'], 1000)
            or not _safe_exclusion_text('reviewed exclusion reviewer', exclusion['reviewer'], 1000)
            or not _valid_review_date(exclusion['reviewed_on'])
        ):
            raise ValueError('metadata_snapshot reviewed exclusion is invalid.')
        seen_exclusions.add(identity)
        reviewed_findings.append(ValidationFinding(
            'warning', 'reviewed_exclusion',
            f'{artifact} content index {content_index} was excluded after checksum-bound review: '
            f'{exclusion["reason"]}',
        ))
    findings = (*result.findings, *reviewed_findings)
    if 'provider_audit' in metadata:
        metadata['provider_audit'] = reconcile_provider_audit(
            metadata['provider_audit'], normalized_rows,
        )
        warning_counts = Counter(
            finding.code for finding in findings if finding.severity == 'warning'
        )
        metadata['warning_review'] = warning_review_snapshot(warning_counts)
        if (
            metadata['provider_audit']['reviewed_exclusion_count']
            != len(reviewed_findings)
        ):
            raise ValueError(
                'provider audit reviewed exclusion count does not match reviewed decisions.'
            )
    session.execute(delete(CommentaryValidationFinding).where(
        CommentaryValidationFinding.run_id == run.id
    ))
    session.add_all([
        CommentaryValidationFinding(
            run_id=run.id,
            severity=finding.severity,
            code=finding.code,
            work_id=finding.work_id,
            chapter=finding.chapter,
            verse=finding.verse,
            message=finding.message,
        )
        for finding in findings
    ])
    metadata['coverage'] = {
        'books': result.coverage['books'],
        'chapters': result.coverage['chapters'],
        'entries': result.coverage['entries'],
        'by_work': {
            work_id: {
                'chapters': values['chapters'],
                'chapter_numbers': list(values['chapter_numbers']),
                'entries': values['entries'],
            }
            for work_id, values in result.coverage['by_work'].items()
        },
    }
    metadata['validation_manifest'] = _manifest(
        run.source_id, run.source_checksum, metadata, normalized_rows,
    )
    run.metadata_snapshot = metadata
    run.error_count = result.error_count
    run.warning_count = result.warning_count + len(reviewed_findings)
    run.status = 'verified' if result.publishable else 'validated'
    session.flush()
    return run


def _verified_staged_rows(
    session: Session, run: CommentaryImportRun, metadata: Mapping[str, object],
) -> list[NormalizedCommentaryEntry]:
    staged = _staged_records(session, run.id)
    if len(staged) != run.staged_count:
        raise ValueError('Staged commentary row count no longer matches the verified run.')
    normalized_rows: list[NormalizedCommentaryEntry] = []
    for row in staged:
        normalized = NormalizedCommentaryEntry(
            row.work_id, row.chapter, row.verse_start, row.verse_end, row.entry_type,
            row.heading, row.body, row.source_locator, row.position,
        )
        if normalized.row_checksum != row.row_checksum:
            raise ValueError('Staged commentary row changed after validation.')
        normalized_rows.append(normalized)
    expected_manifest = metadata.get('validation_manifest')
    if (
        type(expected_manifest) is not str
        or _CHECKSUM.fullmatch(expected_manifest) is None
        or _manifest(run.source_id, run.source_checksum, metadata, normalized_rows) != expected_manifest
    ):
        raise ValueError('Verified commentary run manifest no longer matches staged content.')
    return normalized_rows


def _copy_staged_entries(
    session: Session,
    edition: CommentaryEdition,
    normalized_rows: Iterable[NormalizedCommentaryEntry],
) -> None:
    session.add_all([
        CommentaryEntry(
            edition_id=edition.id,
            work_id=row.work_id,
            chapter=row.chapter,
            verse_start=row.verse_start,
            verse_end=row.verse_end,
            entry_type=row.entry_type,
            heading=row.heading,
            body=row.body,
            source_locator=row.source_locator,
            row_checksum=row.row_checksum,
            position=row.position,
        )
        for row in normalized_rows
    ])
    session.flush()


def publish_run(session: Session, run_id: UUID) -> CommentaryPublication:
    """Atomically publish one verified run inside a rollback-capable savepoint."""
    _ensure_caller_owned_outer_transaction(session)
    existing = session.get(CommentaryImportRun, run_id)
    if existing is None:
        raise ValueError('Commentary import run was not found.')
    if existing.status == 'published':
        raise ValueError('Commentary import run has already been published.')
    has_errors = session.scalar(select(func.count()).select_from(CommentaryValidationFinding).where(
        CommentaryValidationFinding.run_id == run_id,
        CommentaryValidationFinding.severity == 'error',
    ))
    if existing.status != 'verified' or existing.error_count or has_errors:
        raise ValueError('Only an error-free verified commentary run may be published.')

    with _publication_conflict_boundary(), session.begin_nested():
        # Every publication lifecycle operation locks the source first. This
        # gives publish and rollback one global order before any publication row.
        source = session.scalar(
            select(CommentarySource)
            .where(CommentarySource.id == existing.source_id)
            .with_for_update()
        )
        if source is None:
            raise ValueError('Commentary source was not found.')
        run = session.scalar(
            select(CommentaryImportRun)
            .where(CommentaryImportRun.id == run_id)
            .with_for_update()
        )
        if run is None:
            raise ValueError('Commentary import run was not found.')
        if run.status == 'published':
            raise ValueError('Commentary import run has already been published.')
        has_errors = session.scalar(select(func.count()).select_from(CommentaryValidationFinding).where(
            CommentaryValidationFinding.run_id == run_id,
            CommentaryValidationFinding.severity == 'error',
        ))
        if run.status != 'verified' or run.error_count or has_errors:
            raise ValueError('Only an error-free verified commentary run may be published.')

        if run.source_id != source.id:
            raise ValueError('Commentary run source changed during publication.')

        previous = session.scalar(
            select(CommentaryPublication)
            .where(
                CommentaryPublication.source_id == run.source_id,
                CommentaryPublication.active.is_(True),
            )
            .with_for_update()
        )
        version = session.scalar(
            select(func.coalesce(func.max(CommentaryPublication.version), 0)).where(
                CommentaryPublication.source_id == run.source_id
            )
        ) + 1
        metadata = _json_snapshot(run.metadata_snapshot)
        coverage = metadata.get('coverage')
        if type(coverage) is not dict:
            raise ValueError('Verified commentary run has no coverage snapshot.')
        if not has_exact_chapter_coverage(coverage):
            raise ValueError(
                'Legacy verified commentary coverage must be revalidated before publication.'
            )
        normalized_rows = _verified_staged_rows(session, run, metadata)
        edition = CommentaryEdition(
            source_id=run.source_id,
            dataset_version=str(run.id),
            source_checksum=run.source_checksum,
            status='published',
            record_count=run.staged_count,
            coverage=deepcopy(coverage),
        )
        session.add(edition)
        session.flush()
        _copy_staged_entries(session, edition, normalized_rows)
        if previous is not None:
            previous.active = False
            session.flush()
        publication = CommentaryPublication(
            source_id=run.source_id,
            edition_id=edition.id,
            version=version,
            active=True,
        )
        session.add(publication)
        run.status = 'published'
        session.flush()
    return publication


def rollback_publication(session: Session, publication_id: int) -> CommentaryPublication:
    """Roll back an active publication to its immediately preceding immutable edition."""
    _ensure_caller_owned_outer_transaction(session)
    requested = session.scalar(
        select(CommentaryPublication)
        .where(CommentaryPublication.id == publication_id)
    )
    if requested is None:
        raise ValueError('Commentary publication was not found.')
    if not requested.active:
        raise ValueError('Rollback requires the active publication.')

    with _publication_conflict_boundary(), session.begin_nested():
        source = session.scalar(
            select(CommentarySource)
            .where(CommentarySource.id == requested.source_id)
            .with_for_update()
        )
        if source is None:
            raise ValueError('Commentary source was not found.')
        current = session.scalar(
            select(CommentaryPublication)
            .where(
                CommentaryPublication.id == publication_id,
                CommentaryPublication.active.is_(True),
            )
            .with_for_update()
        )
        if current is None:
            raise ValueError('Rollback requires the active publication.')
        if current.source_id != source.id:
            raise ValueError('Commentary publication source changed during rollback.')
        target = session.scalar(
            select(CommentaryPublication)
            .where(
                CommentaryPublication.source_id == current.source_id,
                CommentaryPublication.version < current.version,
            )
            .order_by(CommentaryPublication.version.desc())
            .limit(1)
            .with_for_update()
        )
        if target is None:
            raise ValueError('No previous publication is available for rollback.')
        target_edition = session.scalar(select(CommentaryEdition).where(
            CommentaryEdition.id == target.edition_id,
            CommentaryEdition.source_id == current.source_id,
        ))
        if target_edition is None:
            raise ValueError('Rollback target does not belong to the publication source.')
        next_version = session.scalar(
            select(func.max(CommentaryPublication.version)).where(
                CommentaryPublication.source_id == current.source_id
            )
        ) + 1
        current.active = False
        session.flush()
        restored = CommentaryPublication(
            source_id=current.source_id,
            edition_id=target_edition.id,
            version=next_version,
            active=True,
        )
        session.add(restored)
        session.flush()
    return restored
