"""Machine-readable administrator CLI for controlled commentary imports."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
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

from .acquire import MAX_ARTIFACT_BYTES, acquire_source_bundle, read_acquired_artifact
from .adapter import load_helloao_bundle_bytes
from .publish import publish_run, rollback_publication, stage_bundle, validate_run
from .validate import SourceMetadata, load_source_registry


_REGISTRY_PATH = Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'sources.json'
_REVIEWED_ARTIFACTS_PATH = (
    Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'reviewed-artifacts.json'
)
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


def _reviewed_source_artifacts(
    source_id: str, metadata: SourceMetadata, path: Path,
) -> dict[str, dict[str, str]]:
    raw = _read_bounded_regular(path, maximum=256 * 1024, label='reviewed artifact manifest')
    try:
        manifest = json.loads(raw.decode('utf-8', errors='strict'))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Reviewed artifact manifest must contain valid JSON.') from exc
    if type(manifest) is not dict or set(manifest) != {'schema_version', 'sources'}:
        raise ValueError('Reviewed artifact manifest has an invalid schema.')
    sources = manifest['sources']
    if manifest['schema_version'] != 1 or type(sources) is not dict or source_id not in sources:
        raise ValueError('Reviewed artifact manifest has no approved source record.')
    source = sources[source_id]
    if (
        type(source) is not dict or set(source) != {'artifacts'}
        or type(source['artifacts']) is not dict
    ):
        raise ValueError('Reviewed artifact source record has an invalid schema.')
    artifacts = source['artifacts']
    expected = [f'{code}.json' for code in metadata.expected_source_books] + ['books.json']
    if set(artifacts) != set(expected):
        raise ValueError(
            'Reviewed artifact manifest is incomplete; production staging is blocked.'
        )
    approved: dict[str, dict[str, str]] = {}
    for filename in expected:
        record = artifacts[filename]
        expected_url = (
            metadata.upstream_url if filename == 'books.json'
            else f'https://bible.helloao.org/api/c/{source_id}/{filename}'
        )
        if (
            type(record) is not dict or set(record) != {'url', 'sha256'}
            or record.get('url') != expected_url
            or type(record.get('sha256')) is not str
            or re.fullmatch(r'[0-9a-f]{64}', record['sha256']) is None
        ):
            raise ValueError(
                'Reviewed artifact record does not match the approved URL and digest schema.'
            )
        if filename == 'books.json' and record['sha256'] != metadata.source_checksum:
            raise ValueError('Reviewed catalog digest does not match the pinned source registry.')
        approved[filename] = {'url': record['url'], 'sha256': record['sha256']}
    return approved


def _load_stage_input(
    source_id: str, input_path: Path, metadata: SourceMetadata, *,
    reviewed_manifest_path: Path = _REVIEWED_ARTIFACTS_PATH,
):
    _safe_input_directory(input_path)
    if input_path.name != source_id:
        raise ValueError('input directory name must exactly match --source.')
    reviewed = _reviewed_source_artifacts(source_id, metadata, reviewed_manifest_path)
    expected_codes = metadata.expected_source_books
    rows = []
    checksums = []
    for code in expected_codes:
        filename = f'{code}.json'
        raw, checksum, acquired_url = read_acquired_artifact(
            input_path, filename, source_id=source_id,
        )
        if (
            checksum != reviewed[filename]['sha256']
            or acquired_url != reviewed[filename]['url']
        ):
            raise ValueError(
                f'{filename} does not match its independently reviewed digest and URL.'
            )
        checksums.append((filename, checksum))
        loaded = tuple(load_helloao_bundle_bytes(raw, {code: _BOOK_MAP[code]}))
        if not loaded or any(not row.source_locator.startswith(f'helloao:{source_id}:{code}:') for row in loaded):
            raise ValueError(f'{filename} does not identify the reviewed commentary source.')
        rows.extend(loaded)
    _catalog_raw, catalog_checksum, catalog_url = read_acquired_artifact(
        input_path, 'books.json', source_id=source_id,
    )
    if (
        catalog_checksum != reviewed['books.json']['sha256']
        or catalog_url != reviewed['books.json']['url']
    ):
        raise ValueError('books.json does not match its independently reviewed digest and URL.')
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
            CommentaryValidationFinding.message,
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


def _open_report_parent(path: Path, hook=None) -> int:
    descriptor = os.open('/', os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        for component in path.expanduser().absolute().parts[1:]:
            if component in {'', '.', '..'}:
                raise ValueError('report output path contains an invalid component.')
            created = False
            try:
                os.mkdir(component, 0o700, dir_fd=descriptor)
                created = True
            except FileExistsError:
                pass
            try:
                child = os.open(
                    component,
                    os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
                    | getattr(os, 'O_NOFOLLOW', 0),
                    dir_fd=descriptor,
                )
            except OSError as exc:
                raise ValueError(
                    'report output path must not contain a symlink or special node.'
                ) from exc
            try:
                if created:
                    os.fsync(descriptor)
            except Exception:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            if hook is not None:
                hook(component)
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _atomic_json(
    path: Path, value: dict[str, object], *, _before_replace=None,
    _during_directory_open=None,
) -> None:
    path = path.expanduser().absolute()
    parent = path.parent
    directory = _open_report_parent(parent, _during_directory_open)
    opened_parent = os.fstat(directory)
    name = path.name
    temporary = name + '.part'
    data = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ) + '\n').encode('utf-8')
    try:
        for candidate, label in ((name, 'output'), (temporary, 'temporary')):
            try:
                info = os.stat(candidate, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f'report {label} path must be a regular file.')
            if candidate == temporary:
                os.unlink(candidate, dir_fd=directory)
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
            0o600,
            dir_fd=directory,
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
        if _before_replace is not None:
            _before_replace()
        try:
            current_parent = os.stat(parent, follow_symlinks=False)
        except FileNotFoundError:
            current_parent = None
        if current_parent is None or not stat.S_ISDIR(current_parent.st_mode) or (
            current_parent.st_dev, current_parent.st_ino
        ) != (opened_parent.st_dev, opened_parent.st_ino):
            raise ValueError('report output directory changed during report creation.')
        os.replace(
            temporary, name, src_dir_fd=directory, dst_dir_fd=directory,
        )
        os.fsync(directory)
    except Exception:
        try:
            info = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISREG(info.st_mode):
                os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        raise
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
            'artifact_digests': [
                {'path': str(item.path), 'sha256': item.checksum, 'url': item.url}
                for item in artifacts
            ],
            'command': 'acquire', 'output': str(output / source), 'source_id': source,
            'status': 'acquired',
        })
    except Exception:
        _error(
            'acquisition_failed', 'Acquisition was blocked by a safety check.',
            command='acquire',
        )


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
    except Exception:
        _error(
            'operation_blocked', 'Command was blocked by a safety or validation gate.',
            command='stage',
        )


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
    except Exception:
        _error(
            'operation_blocked', 'Command was blocked by a safety or validation gate.',
            command='validate',
        )


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
    except Exception:
        _error(
            'operation_blocked', 'Command was blocked by a safety or validation gate.',
            command='report',
        )


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
    except Exception:
        _error(
            'operation_blocked', 'Command was blocked by a safety or validation gate.',
            command='publish',
        )


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
    except Exception:
        _error(
            'operation_blocked', 'Command was blocked by a safety or validation gate.',
            command='rollback',
        )


if __name__ == '__main__':
    app()
