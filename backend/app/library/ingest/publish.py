"""Atomic publication and one-step rollback for verified scripture editions.

The legacy ``biblical_texts`` table is intentionally not mapped: deployments
predate the library schema and only the six common columns are part of this
contract.  A publication therefore replaces just one translation's legacy
rows inside the same transaction as its audit history and coverage.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS
from app.library.ingest.models import (
    ScriptureIngestRun,
    ScripturePublication,
    ScripturePublicationVerse,
    ScriptureValidationFinding,
    StagedScriptureVerse,
)
from app.library.ingest.types import row_checksum
from app.library.models import EditionCoverage, TextEdition


_LEGACY_TABLE = 'biblical_texts'
_LEGACY_COLUMNS = frozenset({'id', 'book', 'chapter', 'verse', 'text', 'translation'})
_DISPLAY_BOOK_NAMES = {
    work.id: work.name for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS)
}


class PublicationBlocked(RuntimeError):
    """Raised when a staged run does not meet the publication gate."""


class PublicationNotFound(LookupError):
    """Raised when a requested ingest run or edition cannot be found."""


class RollbackUnavailable(RuntimeError):
    """Raised when an edition has no distinct immediate predecessor to restore."""


class PublicationConflict(RuntimeError):
    """Raised when a concurrent writer wins an edition publication race."""


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Immutable outcome of publishing an edition run."""

    edition_code: str
    run_id: UUID
    publication_version: int
    changed: bool
    published_count: int


@dataclass(frozen=True, slots=True)
class RollbackResult:
    """Immutable outcome of restoring one previously published run."""

    edition_code: str
    restored_run_id: UUID
    displaced_run_id: UUID
    publication_version: int
    published_count: int


@contextmanager
def _atomic(session: Session) -> Iterator[None]:
    """Isolate this operation without committing a caller's transaction."""
    if session.in_transaction():
        connection = session.connection()
        driver_connection = connection.connection.driver_connection
        if (
            connection.dialect.name == 'sqlite'
            and not driver_connection.in_transaction
        ):
            # Python's sqlite driver otherwise lets SAVEPOINT become the outer
            # transaction, so releasing it would escape a caller rollback.
            connection.exec_driver_sql('BEGIN')
        with session.begin_nested():
            yield
    else:
        with session.begin():
            yield


def _require_legacy_schema(session: Session) -> None:
    inspector = inspect(session.get_bind())
    if not inspector.has_table(_LEGACY_TABLE):
        raise PublicationBlocked(
            'Cannot publish: required legacy biblical_texts table is missing.'
        )
    columns = {column['name'] for column in inspector.get_columns(_LEGACY_TABLE)}
    missing = sorted(_LEGACY_COLUMNS - columns)
    if missing:
        raise PublicationBlocked(
            'Cannot publish: legacy biblical_texts table is missing required columns: '
            + ', '.join(missing)
            + '.'
        )


def _read_run_edition_code(session: Session, run_id: UUID) -> str:
    edition_code = session.scalar(select(ScriptureIngestRun.edition_code).where(
        ScriptureIngestRun.id == run_id
    ))
    if edition_code is None:
        raise PublicationNotFound(f'Scripture ingest run {run_id} was not found.')
    return edition_code


def _lock_edition(session: Session, edition_code: str) -> TextEdition:
    edition = session.scalar(
        select(TextEdition)
        .where(TextEdition.edition_code == edition_code)
        .with_for_update()
    )
    if edition is None:
        raise PublicationNotFound(f'Text edition {edition_code!r} was not found.')
    if session.get_bind().dialect.name == 'sqlite':
        session.execute(
            update(TextEdition)
            .where(TextEdition.edition_code == edition_code)
            .values(edition_code=TextEdition.edition_code)
        )
    return edition


def _lock_publication_history(
    session: Session, edition_code: str
) -> tuple[ScripturePublication, ...]:
    return tuple(session.scalars(
        select(ScripturePublication)
        .where(ScripturePublication.edition_code == edition_code)
        .order_by(ScripturePublication.publication_version, ScripturePublication.id)
        .with_for_update()
    ))


def _lock_runs(
    session: Session, run_ids: Sequence[UUID]
) -> dict[UUID, ScriptureIngestRun]:
    ordered_ids = tuple(sorted(set(run_ids), key=lambda value: value.hex))
    if not ordered_ids:
        return {}
    runs = tuple(session.scalars(
        select(ScriptureIngestRun)
        .where(ScriptureIngestRun.id.in_(ordered_ids))
        .order_by(ScriptureIngestRun.id)
        .with_for_update()
    ))
    by_id = {run.id: run for run in runs}
    missing = [run_id for run_id in ordered_ids if run_id not in by_id]
    if missing:
        raise PublicationNotFound(
            'Scripture ingest run(s) not found: '
            + ', '.join(str(run_id) for run_id in missing)
            + '.'
        )
    return by_id


def _active_publication(
    history: Sequence[ScripturePublication],
) -> ScripturePublication | None:
    active = [publication for publication in history if publication.active]
    if len(active) > 1:
        raise PublicationBlocked('Cannot publish: more than one active publication exists.')
    return active[0] if active else None


def _staged_rows(session: Session, run_id: UUID) -> tuple[StagedScriptureVerse, ...]:
    rows = tuple(session.scalars(
        select(StagedScriptureVerse)
        .where(StagedScriptureVerse.run_id == run_id)
        .order_by(
            StagedScriptureVerse.work_id,
            StagedScriptureVerse.chapter,
            StagedScriptureVerse.verse,
            StagedScriptureVerse.id,
        )
    ))
    if not rows:
        raise PublicationBlocked('Cannot publish: the run has no staged scripture rows.')
    positions = {(row.work_id, row.chapter, row.verse) for row in rows}
    if len(positions) != len(rows):
        raise PublicationBlocked('Cannot publish: staged scripture positions are not unique.')
    unknown = sorted({row.work_id for row in rows} - _DISPLAY_BOOK_NAMES.keys())
    if unknown:
        raise PublicationBlocked(
            'Cannot publish: staged rows have no canonical display book name: '
            + ', '.join(unknown)
            + '.'
        )
    return rows


def _validate_row_checksums(
    rows: Sequence[StagedScriptureVerse | ScripturePublicationVerse],
    *,
    label: str,
) -> None:
    for row in rows:
        expected = row_checksum(
            row.work_id,
            row.source_book,
            row.chapter,
            row.verse,
            row.normalized_text,
            row.source_locator,
        )
        if row.row_checksum != expected:
            raise PublicationBlocked(
                f'Cannot publish: {label} row checksum mismatch at '
                f'{row.work_id} {row.chapter}:{row.verse}.'
            )


def _snapshot_rows(
    session: Session, publication_id: int
) -> tuple[ScripturePublicationVerse, ...]:
    rows = tuple(session.scalars(
        select(ScripturePublicationVerse)
        .where(ScripturePublicationVerse.publication_id == publication_id)
        .order_by(
            ScripturePublicationVerse.work_id,
            ScripturePublicationVerse.chapter,
            ScripturePublicationVerse.verse,
            ScripturePublicationVerse.id,
        )
    ))
    if not rows:
        raise PublicationBlocked('Cannot rollback: publication snapshot has no rows.')
    _validate_row_checksums(rows, label='snapshot')
    return rows


def _ensure_publishable(session: Session, run: ScriptureIngestRun) -> tuple[StagedScriptureVerse, ...]:
    if run.status != 'verified':
        raise PublicationBlocked(
            f'Cannot publish run {run.id}: status must be verified, not {run.status!r}.'
        )
    error_finding = session.scalar(
        select(ScriptureValidationFinding.id)
        .where(
            ScriptureValidationFinding.run_id == run.id,
            ScriptureValidationFinding.severity == 'error',
        )
        .limit(1)
    )
    if error_finding is not None:
        raise PublicationBlocked(f'Cannot publish run {run.id}: it has error findings.')
    rows = _staged_rows(session, run.id)
    _validate_row_checksums(rows, label='staged')
    return rows


def _insert_legacy_rows(
    session: Session,
    edition_code: str,
    rows: Sequence[StagedScriptureVerse | ScripturePublicationVerse],
) -> None:
    """Insert canonical rows separately so failure injection can test rollback."""
    session.execute(
        text('''
            INSERT INTO biblical_texts (book, chapter, verse, text, translation)
            VALUES (:book, :chapter, :verse, :text, :translation)
        '''),
        [
            {
                'book': _DISPLAY_BOOK_NAMES[row.work_id],
                'chapter': row.chapter,
                'verse': row.verse,
                'text': row.normalized_text,
                'translation': edition_code,
            }
            for row in rows
        ],
    )


def _replace_legacy_rows(
    session: Session,
    edition_code: str,
    rows: Sequence[StagedScriptureVerse | ScripturePublicationVerse],
) -> None:
    session.execute(
        text('DELETE FROM biblical_texts WHERE translation = :edition_code'),
        {'edition_code': edition_code},
    )
    _insert_legacy_rows(session, edition_code, rows)


def _coverage_status(edition: TextEdition) -> str:
    language_is_english = edition.reading_language.strip().casefold() == 'english'
    if edition.relationship == 'exact_ethiopian':
        return 'verified_english' if language_is_english else 'verified_original'
    if edition.relationship == 'related_recension':
        return 'related_recension'
    return 'verified_english' if language_is_english else 'translation_needed'


def _rebuild_coverage(
    session: Session,
    edition: TextEdition,
    run: ScriptureIngestRun,
    rows: Sequence[StagedScriptureVerse | ScripturePublicationVerse],
) -> None:
    session.execute(delete(EditionCoverage).where(EditionCoverage.edition_code == edition.edition_code))
    by_work: dict[str, list[StagedScriptureVerse]] = {}
    for row in rows:
        by_work.setdefault(row.work_id, []).append(row)
    status = _coverage_status(edition)
    note = f'Published run {run.id}; source checksum {run.source_checksum}.'
    for work_id in sorted(by_work):
        work_rows = by_work[work_id]
        session.add(EditionCoverage(
            edition_code=edition.edition_code,
            work_id=work_id,
            status=status,
            chapter_count=len({row.chapter for row in work_rows}),
            verse_count=len(work_rows),
            note=note,
        ))


def _copy_snapshot(
    session: Session,
    publication: ScripturePublication,
    rows: Sequence[StagedScriptureVerse | ScripturePublicationVerse],
) -> None:
    if publication.id is None:
        session.flush()
    for row in rows:
        session.add(ScripturePublicationVerse(
            publication_id=publication.id,
            work_id=row.work_id,
            source_book=row.source_book,
            chapter=row.chapter,
            verse=row.verse,
            normalized_text=row.normalized_text,
            source_locator=row.source_locator,
            row_checksum=row.row_checksum,
        ))


def _next_version(history: Sequence[ScripturePublication]) -> int:
    return max((publication.publication_version for publication in history), default=0) + 1


def _is_publication_race(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, 'diag', None)
    constraint_name = getattr(diagnostic, 'constraint_name', None)
    if constraint_name in {
        'uq_scripture_publications_active_edition',
        'uq_scripture_publications_edition_version',
    }:
        return True
    message = str(error.orig).lower()
    return (
        'unique constraint failed: scripture_publications.edition_code' in message
        or 'uq_scripture_publications_active_edition' in message
        or 'uq_scripture_publications_edition_version' in message
    )


def _is_sqlite_lock_race(error: OperationalError) -> bool:
    return 'database is locked' in str(error.orig).lower()


def _publication_conflict(operation: str, edition_code: str) -> PublicationConflict:
    return PublicationConflict(
        f'Concurrent {operation} conflict for edition {edition_code!r}; retry the operation.'
    )


def publish_run(session: Session, run_id: UUID) -> PublicationResult:
    """Atomically make one verified run the active text for its edition.

    A verified, error-free run with a matching active checksum is a deliberate
    no-op.  The publication gate is never bypassed by checksum reuse.
    """
    edition_code = '<unknown>'
    try:
        with _atomic(session):
            edition_code = _read_run_edition_code(session, run_id)
            edition = _lock_edition(session, edition_code)
            history = _lock_publication_history(session, edition.edition_code)
            active = _active_publication(history)
            involved_ids = [run_id]
            if active is not None:
                involved_ids.append(active.run_id)
            runs = _lock_runs(session, involved_ids)
            run = runs[run_id]
            if run.edition_code != edition.edition_code:
                raise PublicationBlocked('Cannot publish a run for a different text edition.')
            _require_legacy_schema(session)
            if active is not None and active.run_id == run.id:
                return PublicationResult(
                    edition.edition_code,
                    run.id,
                    active.publication_version,
                    False,
                    run.published_count,
                )
            rows = _ensure_publishable(session, run)
            if active is not None:
                active_run = runs[active.run_id]
                if active_run.edition_code != edition.edition_code:
                    raise PublicationBlocked(
                        'Active publication belongs to a different text edition.'
                    )
                if active_run.source_checksum == run.source_checksum:
                    return PublicationResult(
                        edition.edition_code,
                        active_run.id,
                        active.publication_version,
                        False,
                        active_run.published_count,
                    )

            if active is not None:
                active.active = False
                # Make the partial-active uniqueness invariant explicit before the
                # new active row is inserted on every supported dialect.
                session.flush()
            _replace_legacy_rows(session, edition.edition_code, rows)
            _rebuild_coverage(session, edition, run, rows)
            publication = ScripturePublication(
                edition_code=edition.edition_code,
                run_id=run.id,
                previous_run_id=active.run_id if active is not None else None,
                publication_version=_next_version(history),
                active=True,
            )
            session.add(publication)
            _copy_snapshot(session, publication, rows)
            run.status = 'published'
            run.published_count = len(rows)
            session.flush()
            return PublicationResult(
                edition.edition_code,
                run.id,
                publication.publication_version,
                True,
                len(rows),
            )
    except IntegrityError as error:
        if _is_publication_race(error):
            raise _publication_conflict('publication', edition_code) from error
        raise
    except OperationalError as error:
        if _is_sqlite_lock_race(error):
            raise _publication_conflict('publication', edition_code) from error
        raise


def _previous_publication_for_restore(
    history: Sequence[ScripturePublication],
    active: ScripturePublication,
    restored_run_id: UUID,
) -> ScripturePublication | None:
    for publication in reversed(history):
        if (
            publication.publication_version < active.publication_version
            and publication.run_id == restored_run_id
        ):
            return publication
    return None


def rollback_edition(session: Session, edition_code: str) -> RollbackResult:
    """Restore an edition's immediate distinct predecessor in one atomic unit."""
    try:
        with _atomic(session):
            edition = _lock_edition(session, edition_code)
            history = _lock_publication_history(session, edition.edition_code)
            active = _active_publication(history)
            if (
                active is None
                or active.previous_run_id is None
                or active.previous_run_id == active.run_id
            ):
                raise RollbackUnavailable(
                    f'No distinct prior run is available for edition {edition.edition_code!r}.'
                )
            target_publication = _previous_publication_for_restore(
                history, active, active.previous_run_id
            )
            if target_publication is None:
                raise RollbackUnavailable(
                    'No prior publication snapshot is available for edition '
                    f'{edition.edition_code!r}.'
                )
            involved_ids = [active.run_id, target_publication.run_id]
            if target_publication.previous_run_id is not None:
                involved_ids.append(target_publication.previous_run_id)
            runs = _lock_runs(session, involved_ids)
            _require_legacy_schema(session)
            displaced = runs[active.run_id]
            restored = runs[target_publication.run_id]
            if (
                displaced.edition_code != edition.edition_code
                or restored.edition_code != edition.edition_code
                or any(
                    run.edition_code != edition.edition_code
                    for run in runs.values()
                )
            ):
                raise PublicationBlocked('Publication history crosses text editions.')
            rows = _snapshot_rows(session, target_publication.id)
            active.active = False
            session.flush()
            _replace_legacy_rows(session, edition.edition_code, rows)
            _rebuild_coverage(session, edition, restored, rows)
            publication = ScripturePublication(
                edition_code=edition.edition_code,
                run_id=restored.id,
                previous_run_id=target_publication.previous_run_id,
                publication_version=_next_version(history),
                active=True,
            )
            session.add(publication)
            _copy_snapshot(session, publication, rows)
            displaced.status = 'rolled_back'
            restored.status = 'published'
            restored.published_count = len(rows)
            session.flush()
            return RollbackResult(
                edition.edition_code,
                restored.id,
                displaced.id,
                publication.publication_version,
                len(rows),
            )
    except IntegrityError as error:
        if _is_publication_race(error):
            raise _publication_conflict('rollback', edition_code) from error
        raise
    except OperationalError as error:
        if _is_sqlite_lock_race(error):
            raise _publication_conflict('rollback', edition_code) from error
        raise
