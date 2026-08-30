"""Safe, local-only operator commands for the verified scripture pipeline.

Source acquisition and parsing adapters are installed separately.  This module
coordinates already-reviewed adapters, validation, and atomic publication; it
never downloads source material and never guesses a database target.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Annotated, NoReturn
from uuid import UUID, uuid4

import typer
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.library.canon import WORKS
from app.library.ingest.manifest import SourceManifest
from app.library.ingest.models import (
    ScriptureIngestRun,
    ScripturePublication,
    ScriptureValidationFinding,
    StagedScriptureVerse,
)
from app.library.ingest.publish import publish_run, rollback_edition
from app.library.ingest.types import NormalizedVerse
from app.library.ingest.adapters.composite_english_bundle import (
    parse_composite_english_bundle,
)
from app.library.ingest.adapters.weahadu_bundle import parse_weahadu_bundle
from app.library.ingest.validate import validate_edition
from app.library.models import EditionCoverage, EditionWorkSource, TextEdition
from app.library.seed import seed_ethiopian_canon


StageAdapter = Callable[[SourceManifest, Path], Sequence[NormalizedVerse]]
ADAPTERS: dict[str, StageAdapter] = {
    'weahadu_bundle': parse_weahadu_bundle,
    'composite_english_bundle': parse_composite_english_bundle,
}

app = typer.Typer(
    no_args_is_help=True,
    help='Safely stage, validate, publish, and inspect verified scripture sources.',
)

DatabaseOption = Annotated[
    str | None,
    typer.Option(
        '--database-url',
        help='Explicit migrated database URL. Falls back only to an explicitly set DATABASE_URL.',
    ),
]


def _fail(message: str) -> NoReturn:
    typer.echo(f'Error: {message}', err=True)
    raise typer.Exit(code=1)


def _database_url(value: str | None) -> str:
    selected = value or os.environ.get('DATABASE_URL')
    if selected is None or not selected.strip():
        _fail(
            'Provide --database-url or explicitly set DATABASE_URL; '
            'the ingestion CLI has no implicit database default.'
        )
    return selected.strip()


def _database(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    # Engine construction needs only the selected URL.  Keep unrelated runtime
    # environment validation from changing an operator command's DB semantics.
    engine = create_database_engine(Settings(
        environment='development', database_url=database_url
    ))
    return engine, create_session_factory(engine)


@contextmanager
def _database_context(
    database_url: str | None,
) -> Iterator[sessionmaker[Session]]:
    """Translate setup/operation failures and always release a created engine."""
    engine: Engine | None = None
    try:
        engine, session_factory = _database(_database_url(database_url))
        yield session_factory
    except typer.Exit:
        raise
    except Exception as error:
        _fail(str(error))
    finally:
        if engine is not None:
            engine.dispose()


def _emit(
    *,
    run_id: UUID | str | None = None,
    edition_code: str | None = None,
    checksum: str | None = None,
    staged_count: int = 0,
    published_count: int = 0,
    errors: int = 0,
    warnings: int = 0,
    next_action: str,
    **extra: object,
) -> None:
    payload: dict[str, object] = {
        'run_id': str(run_id) if run_id is not None else None,
        'edition_code': edition_code,
        'checksum': checksum,
        'staged_count': staged_count,
        'published_count': published_count,
        'errors': errors,
        'warnings': warnings,
        'next_action': next_action,
    }
    payload.update(extra)
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _source_checksum(manifest: SourceManifest) -> str:
    artifacts = sorted(
        (source.path, source.sha256) for source in manifest.source_files
    )
    serialized = json.dumps(artifacts, ensure_ascii=False, separators=(',', ':'))
    return sha256(serialized.encode('utf-8')).hexdigest()


def _load_manifest(path: Path) -> SourceManifest:
    try:
        return SourceManifest.model_validate_json(path.read_text(encoding='utf-8'))
    except Exception as error:
        _fail(f'Unable to load manifest {path}: {error}')


def _ensure_edition_foreign_key(session: Session, manifest: SourceManifest) -> None:
    """Create only the non-authoritative shell required by the run foreign key."""
    edition = session.get(TextEdition, manifest.edition_code)
    if edition is not None:
        return
    session.add(TextEdition(
        edition_code=manifest.edition_code,
        name=f'Pending publication ({manifest.edition_code})',
        reading_language='Undetermined',
        source_language='Undetermined',
        script='Undetermined',
        relationship='general_reading',
        expected_coverage={},
        verification_status='staged',
        source_checksum=None,
    ))


def _get_run(session: Session, run_id: UUID) -> ScriptureIngestRun:
    run = session.get(ScriptureIngestRun, run_id)
    if run is None:
        raise LookupError(f'Scripture ingest run {run_id} was not found.')
    return run


@app.command('seed-canon')
def seed_canon(database_url: DatabaseOption = None) -> None:
    """Seed the immutable Ethiopian 81-book catalog into a migrated database."""
    with _database_context(database_url) as session_factory:
        with session_factory() as session:
            result = seed_ethiopian_canon(session)
        _emit(
            edition_code='ETHIO81',
            staged_count=0,
            next_action='stage',
            canon_entries=result.entry_count,
            navigation_works=result.navigation_work_count,
        )


@app.command()
def stage(
    manifest: Annotated[Path, typer.Option('--manifest', exists=True, dir_okay=False)],
    database_url: DatabaseOption = None,
) -> None:
    """Stage normalized rows from an installed, reviewed local adapter."""
    with _database_context(database_url) as session_factory:
        source_manifest = _load_manifest(manifest)
        adapter = ADAPTERS.get(source_manifest.adapter)
        if adapter is None:
            _fail(
                f'Adapter {source_manifest.adapter!r} is not installed. '
                'Install the reviewed Phase 3 adapter; remote acquisition is a separate step.'
            )
        try:
            rows = tuple(adapter(source_manifest, manifest.parent))
        except Exception as error:
            _fail(f'Adapter {source_manifest.adapter!r} failed: {error}')
        if not rows:
            _fail(f'Adapter {source_manifest.adapter!r} returned no scripture rows.')
        if not all(isinstance(row, NormalizedVerse) for row in rows):
            _fail(f'Adapter {source_manifest.adapter!r} returned a non-normalized row.')
        if any(row.source_locator is None for row in rows):
            _fail(f'Adapter {source_manifest.adapter!r} returned a row without a source locator.')

        checksum = _source_checksum(source_manifest)
        run_id = uuid4()
        with session_factory() as session, session.begin():
            _ensure_edition_foreign_key(session, source_manifest)
            session.flush()
            session.add(ScriptureIngestRun(
                id=run_id,
                edition_code=source_manifest.edition_code,
                source_checksum=checksum,
                manifest_snapshot=source_manifest.model_dump(mode='json'),
                status='staged',
                staged_count=len(rows),
            ))
            for row in rows:
                session.add(StagedScriptureVerse(
                    run_id=run_id,
                    work_id=row.work_id,
                    source_book=row.source_book,
                    chapter=row.chapter,
                    verse=row.verse,
                    normalized_text=row.text,
                    source_locator=row.source_locator,
                    row_checksum=row.row_checksum,
                ))
        _emit(
            run_id=run_id,
            edition_code=source_manifest.edition_code,
            checksum=checksum,
            staged_count=len(rows),
            next_action='validate',
        )


@app.command()
def validate(
    run_id: Annotated[UUID, typer.Option('--run-id')],
    database_url: DatabaseOption = None,
) -> None:
    """Validate one staged run and persist deterministic findings."""
    with _database_context(database_url) as session_factory:
        with session_factory() as session, session.begin():
            run = _get_run(session, run_id)
            if run.status in {'published', 'rolled_back'}:
                raise RuntimeError(f'Run {run.id} is already {run.status}.')
            manifest = SourceManifest.model_validate(run.manifest_snapshot)
            staged_rows = tuple(session.scalars(
                select(StagedScriptureVerse)
                .where(StagedScriptureVerse.run_id == run.id)
                .order_by(
                    StagedScriptureVerse.work_id,
                    StagedScriptureVerse.chapter,
                    StagedScriptureVerse.verse,
                )
            ))
            rows = tuple(NormalizedVerse(
                work_id=row.work_id,
                source_book=row.source_book,
                chapter=row.chapter,
                verse=row.verse,
                text=row.normalized_text,
                source_locator=row.source_locator,
            ) for row in staged_rows)
            relationship_warnings = (
                ('related_recension',) if manifest.relationship == 'related_recension' else ()
            )
            result = validate_edition(
                rows,
                manifest.expected_works,
                warnings=relationship_warnings,
                known_missing_verses=getattr(
                    manifest.adapter_options, 'known_missing_verses', {}
                ),
            )
            session.execute(delete(ScriptureValidationFinding).where(
                ScriptureValidationFinding.run_id == run.id
            ))
            for finding in result.findings:
                session.add(ScriptureValidationFinding(
                    run_id=run.id,
                    severity=finding.severity,
                    code=finding.code,
                    work_id=finding.work_id,
                    chapter=finding.chapter,
                    verse=finding.verse,
                    message=finding.message,
                ))
            run.error_count = result.error_count
            run.warning_count = result.warning_count
            run.staged_count = len(staged_rows)
            run.status = 'verified' if result.publishable else 'validated'
            output = {
                'run_id': run.id,
                'edition_code': run.edition_code,
                'checksum': run.source_checksum,
                'staged_count': len(staged_rows),
                'errors': result.error_count,
                'warnings': result.warning_count,
            }
        _emit(
            **output,
            next_action=(
                'publish --confirm'
                if output['errors'] == 0
                else 'fix source and stage a new run'
            ),
        )


@app.command()
def publish(
    run_id: Annotated[UUID, typer.Option('--run-id')],
    confirm: Annotated[bool, typer.Option('--confirm', help='Confirm atomic publication.')] = False,
    database_url: DatabaseOption = None,
) -> None:
    """Atomically publish one verified, error-free staged run."""
    if not confirm:
        _fail('Publication requires the explicit --confirm flag.')
    with _database_context(database_url) as session_factory:
        with session_factory() as session:
            result = publish_run(session, run_id)
            run = _get_run(session, result.run_id)
            output = {
                'run_id': result.run_id,
                'edition_code': result.edition_code,
                'checksum': run.source_checksum,
                'staged_count': run.staged_count,
                'published_count': result.published_count,
                'errors': run.error_count,
                'warnings': run.warning_count,
                'changed': result.changed,
                'publication_version': result.publication_version,
            }
        _emit(**output, next_action='coverage-report')


@app.command()
def rollback(
    edition: Annotated[str, typer.Option('--edition')],
    database_url: DatabaseOption = None,
) -> None:
    """Atomically restore an edition's immediate distinct predecessor."""
    with _database_context(database_url) as session_factory:
        with session_factory() as session:
            result = rollback_edition(session, edition)
            run = _get_run(session, result.restored_run_id)
            output = {
                'run_id': result.restored_run_id,
                'edition_code': result.edition_code,
                'checksum': run.source_checksum,
                'staged_count': run.staged_count,
                'published_count': result.published_count,
                'errors': run.error_count,
                'warnings': run.warning_count,
                'publication_version': result.publication_version,
                'displaced_run_id': str(result.displaced_run_id),
            }
        _emit(**output, next_action='coverage-report')


@app.command('coverage-report')
def coverage_report(
    run_id: Annotated[UUID | None, typer.Option('--run-id')] = None,
    edition: Annotated[str | None, typer.Option('--edition')] = None,
    database_url: DatabaseOption = None,
) -> None:
    """Report persisted run counts and edition coverage without mutating data."""
    with _database_context(database_url) as session_factory:
        with session_factory() as session:
            run: ScriptureIngestRun | None = None
            if run_id is not None:
                run = _get_run(session, run_id)
                if edition is not None and edition != run.edition_code:
                    raise RuntimeError('--run-id and --edition refer to different editions.')
                edition = run.edition_code
            coverage = []
            inventory = None
            active_publication = None
            if edition is not None:
                active_publication = session.scalar(
                    select(ScripturePublication).where(
                        ScripturePublication.edition_code == edition,
                        ScripturePublication.active.is_(True),
                    )
                )
                coverage_rows = tuple(session.scalars(
                    select(EditionCoverage)
                    .where(EditionCoverage.edition_code == edition)
                    .order_by(EditionCoverage.work_id)
                ))
                coverage = [
                    {
                        'work_id': row.work_id,
                        'status': row.status,
                        'chapter_count': row.chapter_count,
                        'verse_count': row.verse_count,
                    }
                    for row in coverage_rows
                ]
                source_rows = tuple(session.scalars(
                    select(EditionWorkSource)
                    .where(EditionWorkSource.edition_code == edition)
                    .order_by(EditionWorkSource.work_id)
                ))
                status_totals = Counter(
                    row.verification_status for row in source_rows
                )
                populated_work_ids = {row.work_id for row in coverage_rows}
                unavailable_work_ids = sorted(
                    {work.id for work in WORKS} - populated_work_ids
                )
                inventory = {
                    'populated_work_count': len(populated_work_ids),
                    'chapter_count': sum(
                        row.chapter_count or 0 for row in coverage_rows
                    ),
                    'verse_count': sum(row.verse_count or 0 for row in coverage_rows),
                    'verified_work_count': sum(
                        count for status, count in status_totals.items()
                        if status.startswith('verified_')
                    ),
                    'in_progress_work_count': status_totals['in_progress'],
                    'fallback_work_count': sum(row.fallback for row in source_rows),
                    'catalog_unavailable_work_count': len(unavailable_work_ids),
                    'catalog_unavailable_work_ids': unavailable_work_ids,
                    'verification_status_totals': dict(sorted(status_totals.items())),
                }
            if run is None and edition is not None:
                run = (
                    _get_run(session, active_publication.run_id)
                    if active_publication is not None else None
                )
            if run is None and edition is None:
                run_count = session.scalar(select(func.count()).select_from(ScriptureIngestRun))
                _emit(next_action='stage', runs=run_count, coverage=[])
                return
            if run is None:
                _emit(
                    edition_code=edition,
                    next_action='validate or publish a candidate',
                    status='unpublished',
                    active_run_id=None,
                    is_active=False,
                    coverage=coverage,
                    inventory=inventory,
                )
                return
            _emit(
                run_id=run.id if run else None,
                edition_code=edition,
                checksum=run.source_checksum if run else None,
                staged_count=run.staged_count if run else 0,
                published_count=run.published_count if run else 0,
                errors=run.error_count if run else 0,
                warnings=run.warning_count if run else 0,
                next_action='review coverage',
                status=run.status if run else None,
                active_run_id=(
                    str(active_publication.run_id)
                    if active_publication is not None else None
                ),
                is_active=(
                    active_publication is not None
                    and active_publication.run_id == run.id
                ),
                coverage=coverage,
                inventory=inventory,
            )


if __name__ == '__main__':
    app()
