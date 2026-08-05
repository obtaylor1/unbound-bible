"""Caller-transaction-owned staging, validation, publication, and rollback."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from hashlib import sha256
import json
import re
from uuid import UUID

from sqlalchemy import delete, func, select
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

from .types import NormalizedCommentaryEntry
from .validate import validate_commentary


_CHECKSUM = re.compile(r'^[0-9a-f]{64}$')


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
        'commentary-verified-run-v1',
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
        for finding in result.findings
    ])
    metadata['coverage'] = {
        'books': result.coverage['books'],
        'chapters': result.coverage['chapters'],
        'entries': result.coverage['entries'],
        'by_work': {
            work_id: dict(values) for work_id, values in result.coverage['by_work'].items()
        },
    }
    metadata['validation_manifest'] = _manifest(
        run.source_id, run.source_checksum, metadata, normalized_rows,
    )
    run.metadata_snapshot = metadata
    run.error_count = result.error_count
    run.warning_count = result.warning_count
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

    with session.begin_nested():
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

    with session.begin_nested():
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
