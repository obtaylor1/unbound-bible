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

from sqlalchemy import delete, inspect, select, text
from sqlalchemy.orm import Session

from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS
from app.library.ingest.models import (
    ScriptureIngestRun,
    ScripturePublication,
    ScriptureValidationFinding,
    StagedScriptureVerse,
)
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


def _locked_run(session: Session, run_id: UUID) -> ScriptureIngestRun:
    run = session.scalar(
        select(ScriptureIngestRun)
        .where(ScriptureIngestRun.id == run_id)
        .with_for_update()
    )
    if run is None:
        raise PublicationNotFound(f'Scripture ingest run {run_id} was not found.')
    return run


def _locked_edition(session: Session, edition_code: str) -> TextEdition:
    edition = session.scalar(
        select(TextEdition)
        .where(TextEdition.edition_code == edition_code)
        .with_for_update()
    )
    if edition is None:
        raise PublicationNotFound(f'Text edition {edition_code!r} was not found.')
    return edition


def _locked_history(
    session: Session, edition_code: str
) -> tuple[ScripturePublication, ...]:
    return tuple(session.scalars(
        select(ScripturePublication)
        .where(ScripturePublication.edition_code == edition_code)
        .order_by(ScripturePublication.publication_version, ScripturePublication.id)
        .with_for_update()
    ))


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
    return _staged_rows(session, run.id)


def _insert_legacy_rows(
    session: Session, edition_code: str, rows: Sequence[StagedScriptureVerse]
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
    session: Session, edition_code: str, rows: Sequence[StagedScriptureVerse]
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
    rows: Sequence[StagedScriptureVerse],
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


def _next_version(history: Sequence[ScripturePublication]) -> int:
    return max((publication.publication_version for publication in history), default=0) + 1


def publish_run(session: Session, run_id: UUID) -> PublicationResult:
    """Atomically make one verified run the active text for its edition.

    A verified, error-free run with a matching active checksum is a deliberate
    no-op.  The publication gate is never bypassed by checksum reuse.
    """
    with _atomic(session):
        run = _locked_run(session, run_id)
        edition = _locked_edition(session, run.edition_code)
        if run.edition_code != edition.edition_code:
            raise PublicationBlocked('Cannot publish a run for a different text edition.')
        history = _locked_history(session, edition.edition_code)
        active = _active_publication(history)
        _require_legacy_schema(session)
        rows = _ensure_publishable(session, run)
        if active is not None:
            active_run = _locked_run(session, active.run_id)
            if active_run.edition_code != edition.edition_code:
                raise PublicationBlocked('Active publication belongs to a different text edition.')
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
        run.status = 'published'
        run.published_count = len(rows)
        session.flush()
        return PublicationResult(
            edition.edition_code, run.id, publication.publication_version, True, len(rows)
        )


def _previous_run_for_restore(
    history: Sequence[ScripturePublication],
    active: ScripturePublication,
    restored_run_id: UUID,
) -> UUID | None:
    """Follow the restored run's prior lineage, never point back to displaced run.

    This gives rollback one-step semantics: repeated rollback can continue only
    toward an older distinct historical run and cannot toggle between two runs.
    """
    for publication in reversed(history):
        if publication.id != active.id and publication.run_id == restored_run_id:
            return publication.previous_run_id
    return None


def rollback_edition(session: Session, edition_code: str) -> RollbackResult:
    """Restore an edition's immediate distinct predecessor in one atomic unit."""
    with _atomic(session):
        edition = _locked_edition(session, edition_code)
        history = _locked_history(session, edition.edition_code)
        active = _active_publication(history)
        if active is None or active.previous_run_id is None or active.previous_run_id == active.run_id:
            raise RollbackUnavailable(
                f'No distinct prior run is available for edition {edition.edition_code!r}.'
            )
        _require_legacy_schema(session)
        displaced = _locked_run(session, active.run_id)
        restored = _locked_run(session, active.previous_run_id)
        if displaced.edition_code != edition.edition_code or restored.edition_code != edition.edition_code:
            raise PublicationBlocked('Publication history crosses text editions.')
        rows = _staged_rows(session, restored.id)
        predecessor = _previous_run_for_restore(history, active, restored.id)
        if predecessor == displaced.id:
            predecessor = None
        active.active = False
        session.flush()
        _replace_legacy_rows(session, edition.edition_code, rows)
        _rebuild_coverage(session, edition, restored, rows)
        publication = ScripturePublication(
            edition_code=edition.edition_code,
            run_id=restored.id,
            previous_run_id=predecessor,
            publication_version=_next_version(history),
            active=True,
        )
        session.add(publication)
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
