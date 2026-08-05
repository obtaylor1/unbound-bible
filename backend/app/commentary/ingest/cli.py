"""Machine-readable administrator CLI for controlled commentary imports."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
from typing import Annotated, NoReturn
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
import typer
from typer import _click as click
from typer.core import TyperGroup

from app.commentary.models import (
    CommentaryImportRun,
    CommentarySource,
    CommentaryValidationFinding,
)
from app.config import Settings
from app.database import create_database_engine, create_session_factory

from .acquire import MAX_ARTIFACT_BYTES, acquire_source_bundle
from .adapter import load_helloao_bundle_bytes
from .publish import publish_run, rollback_publication, stage_bundle, validate_run
from .validate import SourceMetadata, load_source_registry


_REGISTRY_PATH = Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'sources.json'
_BOOK_NAMES = (
    'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth',
    '1 Samuel', '2 Samuel', '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles', 'Ezra',
    'Nehemiah', 'Esther', 'Job', 'Psalms', 'Proverbs', 'Ecclesiastes', 'Song of Solomon',
    'Isaiah', 'Jeremiah', 'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos',
    'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah',
    'Malachi', 'Matthew', 'Mark', 'Luke', 'John', 'Acts', 'Romans', '1 Corinthians',
    '2 Corinthians', 'Galatians', 'Ephesians', 'Philippians', 'Colossians',
    '1 Thessalonians', '2 Thessalonians', '1 Timothy', '2 Timothy', 'Titus', 'Philemon',
    'Hebrews', 'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John', 'Jude',
    'Revelation',
)
_BOOK_CODES = (
    'GEN', 'EXO', 'LEV', 'NUM', 'DEU', 'JOS', 'JDG', 'RUT', '1SA', '2SA', '1KI', '2KI',
    '1CH', '2CH', 'EZR', 'NEH', 'EST', 'JOB', 'PSA', 'PRO', 'ECC', 'SNG', 'ISA', 'JER',
    'LAM', 'EZK', 'DAN', 'HOS', 'JOL', 'AMO', 'OBA', 'JON', 'MIC', 'NAM', 'HAB', 'ZEP',
    'HAG', 'ZEC', 'MAL', 'MAT', 'MRK', 'LUK', 'JHN', 'ACT', 'ROM', '1CO', '2CO', 'GAL',
    'EPH', 'PHP', 'COL', '1TH', '2TH', '1TI', '2TI', 'TIT', 'PHM', 'HEB', 'JAS', '1PE',
    '2PE', '1JN', '2JN', '3JN', 'JUD', 'REV',
)
_BOOK_MAP = dict(zip(_BOOK_CODES, _BOOK_NAMES, strict=True))


class _JsonErrorGroup(TyperGroup):
    """Convert Click/Typer parsing failures into the CLI's JSON contract."""

    def main(self, *args, standalone_mode: bool = True, **kwargs):  # noqa: ANN002, ANN003
        command_args = kwargs.get('args')
        if command_args is None and args:
            command_args = args[0]
        if command_args is None:
            command_args = sys.argv[1:]
        command = command_args[0] if command_args else 'commentary'
        try:
            result = super().main(*args, standalone_mode=False, **kwargs)
        except click.ClickException as exc:
            _emit({
                'command': command,
                'error': {'code': 'invalid_command', 'message': exc.format_message()},
                'status': 'error',
            })
            if standalone_mode:
                raise SystemExit(exc.exit_code) from None
            return exc.exit_code
        if standalone_mode and type(result) is int and result != 0:
            raise SystemExit(result)
        return result


app = typer.Typer(
    cls=_JsonErrorGroup,
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
    help='Acquire, stage, validate, report, publish, and roll back reviewed commentary.',
)

DatabaseOption = Annotated[
    str | None,
    typer.Option('--database-url', help='Migrated database URL; otherwise uses DATABASE_URL.'),
]


def _emit(payload: dict[str, object]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def _error(code: str, message: str, *, command: str) -> NoReturn:
    _emit({'command': command, 'error': {'code': code, 'message': message}, 'status': 'error'})
    raise typer.Exit(code=1)


def _selected_database_url(value: str | None) -> str:
    selected = value or os.environ.get('DATABASE_URL')
    if type(selected) is not str or not selected.strip():
        raise ValueError('Provide --database-url or set DATABASE_URL explicitly.')
    return selected.strip()


def _session_factory(database_url: str | None) -> sessionmaker[Session]:
    url = _selected_database_url(database_url)
    engine = create_database_engine(Settings(environment='development', database_url=url))
    return create_session_factory(engine)


def _registry() -> dict[str, SourceMetadata]:
    return load_source_registry(_REGISTRY_PATH)


def _source_values(source_id: str, metadata: SourceMetadata) -> dict[str, object]:
    return {
        'id': source_id,
        'title': metadata.title,
        'abbreviation': metadata.abbreviation,
        'author': metadata.author,
        'publication_period': metadata.publication_period,
        'tradition': metadata.tradition,
        'language': metadata.language,
        'license_spdx': metadata.license_spdx,
        'license_url': metadata.license_url,
        'attribution': metadata.attribution,
        'provenance_url': metadata.upstream_url,
    }


def _ensure_source(session: Session, source_id: str, metadata: SourceMetadata) -> None:
    expected = _source_values(source_id, metadata)
    existing = session.get(CommentarySource, source_id)
    if existing is None:
        session.add(CommentarySource(**expected))
        session.flush()
        return
    actual = {name: getattr(existing, name) for name in expected}
    if actual != expected:
        raise ValueError('Existing commentary source does not match the reviewed registry.')


def _safe_input_directory(path: Path) -> None:
    absolute = path.expanduser().absolute()
    descriptor = os.open('/', os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        for component in absolute.parts[1:]:
            try:
                child = os.open(
                    component,
                    os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
                    | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0),
                    dir_fd=descriptor,
                )
            except OSError as exc:
                raise ValueError('input path must not contain a symlink or special node.') from exc
            os.close(descriptor)
            descriptor = child
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError('input must be a real acquired source directory.')
    finally:
        os.close(descriptor)


def _read_bounded_regular(path: Path, *, maximum: int, label: str) -> bytes:
    """Read one file through no-follow directory descriptors exactly once."""
    absolute = path.expanduser().absolute()
    parent = os.open('/', os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    descriptor: int | None = None
    try:
        for component in absolute.parts[1:-1]:
            try:
                child = os.open(
                    component,
                    os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
                    | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0),
                    dir_fd=parent,
                )
            except OSError as exc:
                raise ValueError(f'{label} path must not contain a symlink.') from exc
            os.close(parent)
            parent = child
        try:
            descriptor = os.open(
                absolute.name,
                os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0),
                dir_fd=parent,
            )
        except OSError as exc:
            raise ValueError(f'{label} must be a regular file.') from exc
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f'{label} must be a regular file.')
        if info.st_size > maximum:
            size_label = '5 MiB' if maximum == MAX_ARTIFACT_BYTES else f'{maximum} bytes'
            raise ValueError(f'{label} must be no larger than {size_label}.')
        chunks = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                raise ValueError(f'{label} ended during verification.')
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        if after.st_size != info.st_size:
            raise ValueError(f'{label} changed during verification.')
        return b''.join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def _verify_artifact(path: Path) -> tuple[bytes, str]:
    sidecar_path = path.with_name(path.name + '.sha256')
    raw = _read_bounded_regular(path, maximum=MAX_ARTIFACT_BYTES, label='input artifact')
    checksum = sha256(raw).hexdigest()
    try:
        sidecar = _read_bounded_regular(
            sidecar_path, maximum=256, label='checksum sidecar',
        ).decode('ascii', errors='strict')
    except UnicodeDecodeError as exc:
        raise ValueError('checksum sidecar must contain ASCII text.') from exc
    if sidecar != f'{checksum}  {path.name}\n':
        raise ValueError(f'Checksum sidecar does not match {path.name}.')
    return raw, checksum


def _load_stage_input(source_id: str, input_path: Path, metadata: SourceMetadata):
    _safe_input_directory(input_path)
    if input_path.name != source_id:
        raise ValueError('input directory name must exactly match --source.')
    expected_codes = metadata.expected_source_books
    rows = []
    checksums = []
    for code in expected_codes:
        artifact = input_path / f'{code}.json'
        raw, checksum = _verify_artifact(artifact)
        checksums.append((artifact.name, checksum))
        loaded = tuple(load_helloao_bundle_bytes(raw, {code: _BOOK_MAP[code]}))
        if not loaded or any(not row.source_locator.startswith(f'helloao:{source_id}:{code}:') for row in loaded):
            raise ValueError(f'{artifact.name} does not identify the reviewed commentary source.')
        rows.extend(loaded)
    catalog = input_path / 'books.json'
    _catalog_raw, catalog_checksum = _verify_artifact(catalog)
    if catalog_checksum != metadata.source_checksum:
        raise ValueError('books.json checksum no longer matches the reviewed registry.')
    checksums.append(('books.json', catalog_checksum))
    serialized = json.dumps(sorted(checksums), separators=(',', ':')).encode('utf-8')
    return tuple(rows), sha256(serialized).hexdigest()


def _metadata_snapshot(metadata: SourceMetadata) -> dict[str, object]:
    # Resolve aliases through the same constructor path the adapter uses.
    from app.library.ingest.types import resolve_source_work_id
    expected_books = [resolve_source_work_id(_BOOK_MAP[code]) for code in metadata.expected_source_books]
    return {
        'title': metadata.title,
        'author': metadata.author,
        'license_spdx': metadata.license_spdx,
        'license_url': metadata.license_url,
        'attribution': metadata.attribution,
        'provenance_url': metadata.upstream_url,
        'license_reviewed_on': metadata.license_reviewed_on,
        'expected_books': expected_books,
        'expected_source_books': list(metadata.expected_source_books),
    }


def _build_report(session: Session, run_id: UUID) -> dict[str, object]:
    run = session.get(CommentaryImportRun, run_id)
    if run is None:
        raise ValueError('Commentary import run was not found.')
    findings = session.scalars(
        select(CommentaryValidationFinding)
        .where(CommentaryValidationFinding.run_id == run.id)
        .order_by(
            CommentaryValidationFinding.severity,
            CommentaryValidationFinding.work_id,
            CommentaryValidationFinding.chapter,
            CommentaryValidationFinding.verse,
            CommentaryValidationFinding.code,
            CommentaryValidationFinding.id,
        )
    ).all()
    return {
        'run_id': str(run.id),
        'source_id': run.source_id,
        'source_checksum': run.source_checksum,
        'status': run.status,
        'staged_count': run.staged_count,
        'errors': run.error_count,
        'warnings': run.warning_count,
        'coverage': run.metadata_snapshot.get('coverage'),
        'findings': [
            {
                'severity': item.severity, 'code': item.code, 'message': item.message,
                'work_id': item.work_id, 'chapter': item.chapter, 'verse': item.verse,
            }
            for item in findings
        ],
    }


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path = path.expanduser()
    parent = path.parent
    absolute = path.absolute()
    for component in reversed((absolute, *absolute.parents)):
        try:
            info = os.lstat(component)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('report output path must not contain a symlink.')
    parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise ValueError('report output must be a regular file path.')
    temporary = path.with_name(path.name + '.part')
    if temporary.exists():
        if temporary.is_symlink() or not temporary.is_file():
            raise ValueError('report temporary path must be a regular file.')
        temporary.unlink()
    data = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ) + '\n').encode('utf-8')
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
        0o600,
    )
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError('report write made no progress.')
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    directory = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@app.command()
def acquire(
    source: Annotated[str, typer.Option('--source')],
    output: Annotated[Path, typer.Option('--output')],
) -> None:
    try:
        artifacts = acquire_source_bundle(source, output)
        _emit({
            'artifacts': len(artifacts), 'bytes': sum(item.size for item in artifacts),
            'command': 'acquire', 'output': str(output / source), 'source_id': source,
            'status': 'acquired',
        })
    except Exception as exc:
        _error('acquisition_failed', str(exc), command='acquire')


@app.command()
def stage(
    source: Annotated[str, typer.Option('--source')],
    input_path: Annotated[Path, typer.Option('--input')],
    database_url: DatabaseOption = None,
) -> None:
    try:
        registry = _registry()
        if source not in registry:
            raise ValueError('source must be one of the five approved source IDs.')
        rows, checksum = _load_stage_input(source, input_path, registry[source])
        factory = _session_factory(database_url)
        with factory() as session:
            try:
                _ensure_source(session, source, registry[source])
                run = stage_bundle(
                    session, source_id=source, source_checksum=checksum,
                    metadata_snapshot=_metadata_snapshot(registry[source]), rows=rows,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
        _emit({
            'command': 'stage', 'run_id': str(run.id), 'source_id': source,
            'staged_count': run.staged_count, 'status': run.status,
        })
    except Exception as exc:
        _error('operation_blocked', str(exc), command='stage')


@app.command()
def validate(
    run_id: Annotated[UUID, typer.Option('--run-id')],
    database_url: DatabaseOption = None,
) -> None:
    try:
        factory = _session_factory(database_url)
        with factory() as session:
            try:
                run = validate_run(session, run_id)
                session.commit()
            except Exception:
                session.rollback()
                raise
        _emit({
            'command': 'validate', 'run_id': str(run.id), 'source_id': run.source_id,
            'status': run.status, 'errors': run.error_count, 'warnings': run.warning_count,
        })
    except Exception as exc:
        _error('operation_blocked', str(exc), command='validate')


@app.command()
def report(
    run_id: Annotated[UUID, typer.Option('--run-id')],
    output: Annotated[Path, typer.Option('--output')],
    database_url: DatabaseOption = None,
) -> None:
    try:
        factory = _session_factory(database_url)
        with factory() as session:
            data = _build_report(session, run_id)
        _atomic_json(output, data)
        _emit({
            'command': 'report', 'output': str(output), 'run_id': str(run_id),
            'status': 'reported',
        })
    except Exception as exc:
        _error('operation_blocked', str(exc), command='report')


@app.command()
def publish(
    run_id: Annotated[UUID, typer.Option('--run-id')],
    confirm: Annotated[bool, typer.Option('--confirm')] = False,
    database_url: DatabaseOption = None,
) -> None:
    if not confirm:
        _error('confirmation_required', 'Publish requires --confirm.', command='publish')
    try:
        factory = _session_factory(database_url)
        with factory() as session:
            try:
                publication = publish_run(session, run_id)
                session.commit()
            except Exception:
                session.rollback()
                raise
        _emit({
            'command': 'publish', 'publication_id': publication.id,
            'edition_id': str(publication.edition_id), 'source_id': publication.source_id,
            'status': 'published', 'version': publication.version,
        })
    except Exception as exc:
        _error('operation_blocked', str(exc), command='publish')


@app.command()
def rollback(
    publication_id: Annotated[int, typer.Option('--publication-id')],
    confirm: Annotated[bool, typer.Option('--confirm')] = False,
    database_url: DatabaseOption = None,
) -> None:
    if not confirm:
        _error('confirmation_required', 'Rollback requires --confirm.', command='rollback')
    try:
        factory = _session_factory(database_url)
        with factory() as session:
            try:
                restored = rollback_publication(session, publication_id)
                session.commit()
            except Exception:
                session.rollback()
                raise
        _emit({
            'command': 'rollback', 'publication_id': restored.id,
            'edition_id': str(restored.edition_id), 'source_id': restored.source_id,
            'status': 'rolled_back', 'version': restored.version,
        })
    except Exception as exc:
        _error('operation_blocked', str(exc), command='rollback')


if __name__ == '__main__':
    app()
