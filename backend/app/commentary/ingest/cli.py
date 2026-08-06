"""Machine-readable administrator CLI for controlled commentary imports."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import date
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

# The standalone CLI does not run the web application's model bootstrap. Import the
# referenced library ORM module intentionally so commentary foreign keys can resolve.
from app.library import models as _library_models  # noqa: F401
from app.commentary.models import (
    CommentaryImportRun,
    CommentarySource,
    CommentaryValidationFinding,
)
from app.config import Settings
from app.database import create_database_engine, create_session_factory

from .acquire import (
    MAX_ARTIFACT_BYTES, MAX_REVIEWED_MANIFEST_BYTES, acquire_source_bundle,
    read_acquired_artifact,
)
from .adapter import load_helloao_catalog_bytes, load_helloao_chapter_bytes
from .publish import (
    publish_run, rollback_publication, stage_bundle, validate_run,
    warning_review_snapshot,
)
from .types import NormalizedCommentaryEntry, _normalize_scalar
from .validate import SourceMetadata, load_source_registry


_REGISTRY_PATH = Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'sources.json'
_REVIEWED_ARTIFACTS_PATH = (
    Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'reviewed-artifacts.json'
)
_REVIEWED_EXCLUSIONS_PATH = (
    Path(__file__).resolve().parents[3] / 'data' / 'commentaries' / 'reviewed-exclusions.json'
)
_APPROVED_SOURCE_IDS = frozenset({
    'matthew-henry', 'john-gill', 'adam-clarke',
    'jamieson-fausset-brown', 'keil-delitzsch',
})
_EXCLUSION_FIELDS = frozenset({
    'source_id', 'artifact', 'artifact_sha256', 'content_index',
    'reason', 'reviewer', 'reviewed_on',
})
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
_CHAPTER_ARTIFACT = re.compile(r'([A-Z0-9]{3})-([1-9][0-9]*)\.json\Z')


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
    raw = _read_bounded_regular(
        path, maximum=MAX_REVIEWED_MANIFEST_BYTES, label='reviewed artifact manifest',
    )
    try:
        manifest = json.loads(
            raw.decode('utf-8', errors='strict'),
            object_pairs_hook=_reject_duplicate_manifest_members,
            parse_constant=_reject_manifest_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
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
    if 'books.json' not in artifacts:
        raise ValueError('Reviewed artifact manifest is incomplete; production staging is blocked.')
    approved: dict[str, dict[str, str]] = {}
    covered_books: set[str] = set()
    for filename in sorted(artifacts):
        record = artifacts[filename]
        if filename == 'books.json':
            expected_url = metadata.upstream_url
        else:
            match = _CHAPTER_ARTIFACT.fullmatch(filename)
            if match is None or match.group(1) not in metadata.expected_source_books:
                raise ValueError('Reviewed artifact manifest contains an unapproved artifact name.')
            book_id, raw_chapter = match.groups()
            covered_books.add(book_id)
            expected_url = (
                f'https://bible.helloao.org/api/c/{source_id}/{book_id}/{raw_chapter}.json'
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
        approved[filename] = {'url': record['url'], 'sha256': record['sha256']}
    if not covered_books:
        raise ValueError('Reviewed artifact manifest is incomplete; production staging is blocked.')
    return approved


def _reviewed_source_exclusions(
    source_id: str, path: Path, reviewed: dict[str, dict[str, str]],
) -> tuple[dict[str, object], ...]:
    """Load checksum-bound human review decisions for one approved source."""
    raw = _read_bounded_regular(
        path, maximum=256 * 1024, label='reviewed exclusion manifest',
    )
    try:
        document = json.loads(
            raw.decode('utf-8', errors='strict'),
            object_pairs_hook=_reject_duplicate_manifest_members,
            parse_constant=_reject_manifest_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ValueError('Reviewed exclusion manifest must contain valid JSON.') from exc
    if (
        type(document) is not dict
        or set(document) != {'schema_version', 'exclusions'}
        or document['schema_version'] != 1
        or type(document['exclusions']) is not list
    ):
        raise ValueError('Reviewed exclusion manifest has an invalid schema.')
    selected: list[dict[str, object]] = []
    identities: set[tuple[str, str, int]] = set()
    for index, value in enumerate(document['exclusions']):
        if type(value) is not dict or set(value) != _EXCLUSION_FIELDS:
            raise ValueError(f'Reviewed exclusion {index} has an invalid schema.')
        record_source = value['source_id']
        artifact = value['artifact']
        digest = value['artifact_sha256']
        content_index = value['content_index']
        reason = value['reason']
        reviewer = value['reviewer']
        reviewed_on = value['reviewed_on']
        if type(record_source) is not str or record_source not in _APPROVED_SOURCE_IDS:
            raise ValueError('Reviewed exclusion has an unknown source ID.')
        if type(artifact) is not str or _CHAPTER_ARTIFACT.fullmatch(artifact) is None:
            raise ValueError('Reviewed exclusion has an unknown artifact name.')
        if type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
            raise ValueError('Reviewed exclusion artifact digest is invalid.')
        if type(content_index) is not int or content_index < 0:
            raise ValueError('Reviewed exclusion content index must be nonnegative.')
        for label, text in (('reason', reason), ('reviewer', reviewer)):
            try:
                normalized_text = _normalize_scalar(
                    f'reviewed exclusion {label}', text, maximum=1000,
                )
            except ValueError as exc:
                raise ValueError(f'Reviewed exclusion {label} is invalid.') from exc
            if normalized_text != text:
                raise ValueError(f'Reviewed exclusion {label} is invalid.')
        try:
            review_date = date.fromisoformat(reviewed_on) if type(reviewed_on) is str else None
        except ValueError as exc:
            raise ValueError('Reviewed exclusion review date is invalid.') from exc
        if review_date is None or review_date > date.today() or reviewed_on != review_date.isoformat():
            raise ValueError('Reviewed exclusion review date is invalid.')
        identity = (record_source, artifact, content_index)
        if identity in identities:
            raise ValueError('Reviewed exclusion manifest contains a duplicate exclusion.')
        identities.add(identity)
        if record_source != source_id:
            continue
        reviewed_artifact = reviewed.get(artifact)
        if reviewed_artifact is None:
            raise ValueError('Reviewed exclusion references an unknown artifact.')
        if reviewed_artifact['sha256'] != digest:
            raise ValueError('Reviewed exclusion artifact digest is stale or unapproved.')
        selected.append(dict(value))
    return tuple(selected)


def _reject_duplicate_manifest_members(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Reviewed artifact manifest contains duplicate members.')
        value[key] = item
    return value


def _reject_manifest_constant(_value: str) -> None:
    raise ValueError('Reviewed artifact manifest contains a nonstandard JSON constant.')


def _verified_stage_artifact(
    input_path: Path, source_id: str, filename: str,
    reviewed: dict[str, dict[str, str]],
) -> tuple[bytes, str]:
    raw, checksum, acquired_url = read_acquired_artifact(
        input_path, filename, source_id=source_id,
    )
    record = reviewed.get(filename)
    if record is None or checksum != record['sha256'] or acquired_url != record['url']:
        raise ValueError(
            f'{filename} does not match its independently reviewed digest and URL.'
        )
    return raw, checksum


def _load_stage_input(
    source_id: str, input_path: Path, metadata: SourceMetadata, *,
    reviewed_manifest_path: Path = _REVIEWED_ARTIFACTS_PATH,
    reviewed_exclusions_path: Path | None = None,
    applied_exclusions: list[dict[str, object]] | None = None,
    audit_evidence: dict[str, object] | None = None,
):
    _safe_input_directory(input_path)
    if input_path.name != source_id:
        raise ValueError('input directory name must exactly match --source.')
    reviewed = _reviewed_source_artifacts(source_id, metadata, reviewed_manifest_path)
    if reviewed_exclusions_path is None and reviewed_manifest_path == _REVIEWED_ARTIFACTS_PATH:
        reviewed_exclusions_path = _REVIEWED_EXCLUSIONS_PATH
    exclusions = (
        _reviewed_source_exclusions(source_id, reviewed_exclusions_path, reviewed)
        if reviewed_exclusions_path is not None else ()
    )
    excluded_by_artifact: dict[str, frozenset[int]] = {}
    for record in exclusions:
        artifact = record['artifact']
        excluded_by_artifact[artifact] = frozenset({
            *excluded_by_artifact.get(artifact, frozenset()),
            record['content_index'],
        })
    catalog_raw, catalog_checksum = _verified_stage_artifact(
        input_path, source_id, 'books.json', reviewed,
    )
    expected_codes = metadata.expected_source_books
    books = load_helloao_catalog_bytes(
        catalog_raw, source_id, {code: _BOOK_MAP[code] for code in expected_codes},
    )
    if tuple(book.source_book_id for book in books) != expected_codes:
        raise ValueError('books.json does not contain the exact reviewed book set and order.')
    if not books or any(
        book.provider_dataset_checksum != metadata.provider_dataset_checksum
        or book.license_url != metadata.license_url
        or book.language != metadata.language
        for book in books
    ):
        raise ValueError('books.json provenance does not match the reviewed source registry.')
    expected_urls = {'books.json': metadata.upstream_url}
    selected_artifacts: dict[str, tuple[tuple[str, int], ...]] = {}
    for book in books:
        selected = []
        for filename in reviewed:
            match = _CHAPTER_ARTIFACT.fullmatch(filename)
            if match is not None and match.group(1) == book.source_book_id:
                chapter = int(match.group(2))
                if book.chapter_count == 0:
                    raise ValueError('Reviewed manifest contains a chapter artifact for a zero-chapter book.')
                if chapter < book.first_chapter or chapter > book.last_chapter:
                    raise ValueError('Reviewed artifact chapter is outside catalog bounds.')
                selected.append((filename, chapter))
        selected.sort(key=lambda item: item[1])
        if book.chapter_count == 0:
            selected_artifacts[book.source_book_id] = ()
            continue
        if (
            len(selected) != book.chapter_count
            or not selected
            or selected[0][1] != book.first_chapter
            or selected[-1][1] != book.last_chapter
        ):
            raise ValueError('Reviewed artifact manifest does not match catalog chapter coverage.')
        selected_artifacts[book.source_book_id] = tuple(selected)
        for filename, chapter in selected:
            expected_urls[filename] = (
                f'https://bible.helloao.org/api/c/{source_id}/'
                f'{book.source_book_id}/{chapter}.json'
            )
    if set(reviewed) != set(expected_urls) or any(
        reviewed[name]['url'] != url for name, url in expected_urls.items()
    ):
        raise ValueError('Reviewed artifact manifest is incomplete; production staging is blocked.')

    rows: list[NormalizedCommentaryEntry] = []
    checksums = [('books.json', catalog_checksum)]
    position = 0
    total_verse_records = 0
    total_excluded_records = 0
    covered_normalized_chapters: set[tuple[str, int]] = set()
    empty_provider_chapters: list[dict[str, object]] = []
    for book in books:
        book_verse_records = 0
        book_excluded_records = 0
        if book.introduction is not None:
            rows.append(NormalizedCommentaryEntry(
                book.work_id, None, None, None, 'book_intro', None, book.introduction,
                f'helloao:{source_id}:{book.source_book_id}:book-intro', position,
            ))
            position += 1
        for filename, chapter in selected_artifacts[book.source_book_id]:
            raw, checksum = _verified_stage_artifact(
                input_path, source_id, filename, reviewed,
            )
            checksums.append((filename, checksum))
            excluded_indices = excluded_by_artifact.get(filename, frozenset())
            chapter_rows = load_helloao_chapter_bytes(
                raw, source_id, book, chapter,
                excluded_content_indices=excluded_indices,
            )
            if chapter_rows:
                covered_normalized_chapters.add((book.work_id, chapter))
            else:
                empty_provider_chapters.append({
                    'source_book_id': book.source_book_id,
                    'work_id': book.work_id,
                    'chapter': chapter,
                })
            for row in chapter_rows:
                rows.append(replace(row, position=position))
                position += 1
                if row.entry_type in {'verse', 'verse_range'}:
                    book_verse_records += 1
                    total_verse_records += 1
            book_excluded_records += len(excluded_indices)
            total_excluded_records += len(excluded_indices)
        if book_verse_records + book_excluded_records != book.total_book_verses:
            raise ValueError('Staged chapter entries do not match catalog book totals.')
    if total_verse_records + total_excluded_records != books[0].total_commentary_verses:
        raise ValueError('Staged chapter entries do not match catalog commentary totals.')
    if applied_exclusions is not None:
        applied_exclusions.extend(dict(record) for record in exclusions)
    if audit_evidence is not None:
        entry_type_counts = Counter(row.entry_type for row in rows)
        audit_evidence.clear()
        audit_evidence.update({
            'provider_book_count': len(books),
            'provider_chapter_count': sum(book.chapter_count for book in books),
            'provider_content_record_count': books[0].total_commentary_verses,
            'acquired_normalized_entry_count': len(rows),
            'normalized_entry_type_counts': {
                entry_type: entry_type_counts[entry_type]
                for entry_type in ('book_intro', 'chapter_intro', 'verse', 'verse_range')
            },
            'reviewed_exclusion_count': len(exclusions),
            'covered_normalized_chapter_count': len(covered_normalized_chapters),
            'empty_provider_chapters': empty_provider_chapters,
        })
    serialized = json.dumps(
        [sorted(checksums), list(exclusions)], sort_keys=True, separators=(',', ':'),
    ).encode('utf-8')
    return tuple(rows), sha256(serialized).hexdigest()


def _metadata_snapshot(
    metadata: SourceMetadata, *,
    reviewed_exclusions: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
    provider_audit: dict[str, object] | None = None,
) -> dict[str, object]:
    # Resolve aliases through the same constructor path the adapter uses.
    from app.library.ingest.types import resolve_source_work_id
    expected_books = [resolve_source_work_id(_BOOK_MAP[code]) for code in metadata.expected_source_books]
    snapshot = {
        'title': metadata.title,
        'author': metadata.author,
        'license_spdx': metadata.license_spdx,
        'license_url': metadata.license_url,
        'attribution': metadata.attribution,
        'provenance_url': metadata.upstream_url,
        'license_basis': metadata.license_basis,
        'license_reviewer': metadata.license_reviewer,
        'license_reviewed_on': metadata.license_reviewed_on,
        'reviewed_urls': list(metadata.reviewed_urls),
        'provider_dataset_checksum': metadata.provider_dataset_checksum,
        'expected_books': expected_books,
        'expected_source_books': list(metadata.expected_source_books),
    }
    snapshot['reviewed_exclusions'] = [dict(record) for record in reviewed_exclusions]
    snapshot['reviewed_exclusion_count'] = len(reviewed_exclusions)
    if provider_audit is not None:
        snapshot['provider_audit'] = json.loads(json.dumps(
            provider_audit, ensure_ascii=False, allow_nan=False,
        ))
    return snapshot


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
    metadata = run.metadata_snapshot if type(run.metadata_snapshot) is dict else {}
    warning_counts: dict[str, int] = {}
    for item in findings:
        if item.severity == 'warning':
            warning_counts[item.code] = warning_counts.get(item.code, 0) + 1
    provider_audit = metadata.get('provider_audit')
    warning_review = metadata.get('warning_review')
    if provider_audit is not None or warning_review is not None:
        if type(provider_audit) is not dict:
            raise ValueError('provider audit report metadata is missing or invalid.')
        required = {
            'provider_book_count', 'provider_chapter_count',
            'provider_content_record_count', 'acquired_normalized_entry_count',
            'normalized_entry_type_counts', 'reviewed_exclusion_count',
            'covered_normalized_chapter_count', 'empty_provider_chapters',
            'formula', 'expected_normalized_entry_count', 'variance',
        }
        breakdown = provider_audit.get('normalized_entry_type_counts')
        empty_chapters = provider_audit.get('empty_provider_chapters')
        if (
            set(provider_audit) != required
            or type(breakdown) is not dict
            or set(breakdown) != {'book_intro', 'chapter_intro', 'verse', 'verse_range'}
            or any(type(value) is not int or value < 0 for value in breakdown.values())
            or type(empty_chapters) is not list
        ):
            raise ValueError('provider audit report metadata has an invalid schema.')
        integer_fields = required - {
            'normalized_entry_type_counts', 'empty_provider_chapters', 'formula',
        }
        if any(
            type(provider_audit[field]) is not int or provider_audit[field] < 0
            for field in integer_fields
        ):
            raise ValueError('provider audit report counts are invalid.')
        expected = (
            provider_audit['provider_content_record_count']
            - provider_audit['reviewed_exclusion_count']
            + breakdown['book_intro'] + breakdown['chapter_intro']
        )
        coverage = metadata.get('coverage')
        if (
            provider_audit['formula'] != (
                'normalized entries = provider content records - reviewed exclusions '
                '+ book introductions + chapter introductions'
            )
            or provider_audit['expected_normalized_entry_count'] != expected
            or provider_audit['variance'] != 0
            or provider_audit['acquired_normalized_entry_count'] != expected
            or sum(breakdown.values()) != expected
            or provider_audit['provider_chapter_count'] != (
                provider_audit['covered_normalized_chapter_count'] + len(empty_chapters)
            )
            or run.staged_count != expected
            or type(coverage) is not dict or coverage.get('entries') != expected
            or provider_audit['reviewed_exclusion_count']
            != metadata.get('reviewed_exclusion_count', 0)
            or provider_audit['reviewed_exclusion_count']
            != warning_counts.get('reviewed_exclusion', 0)
        ):
            raise ValueError('provider audit report totals do not reconcile.')
        expected_warning_review = warning_review_snapshot(warning_counts)
        if (
            warning_review != expected_warning_review
            or run.warning_count != expected_warning_review['warning_count']
            or run.error_count != sum(item.severity == 'error' for item in findings)
        ):
            raise ValueError('report warning counts do not reconcile with validation findings.')
    return {
        'run_id': str(run.id),
        'source_id': run.source_id,
        'source_checksum': run.source_checksum,
        'status': run.status,
        'staged_count': run.staged_count,
        'errors': run.error_count,
        'warnings': run.warning_count,
        'coverage': metadata.get('coverage'),
        'reviewed_exclusion_count': metadata.get('reviewed_exclusion_count', 0),
        'reviewed_exclusions': metadata.get('reviewed_exclusions', []),
        'provider_audit': provider_audit,
        'warning_review': warning_review,
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
        reviewed_exclusions: list[dict[str, object]] = []
        provider_audit: dict[str, object] = {}
        rows, checksum = _load_stage_input(
            source, input_path, registry[source], applied_exclusions=reviewed_exclusions,
            audit_evidence=provider_audit,
        )
        factory = _session_factory(database_url)
        with factory() as session:
            try:
                _ensure_source(session, source, registry[source])
                run = stage_bundle(
                    session, source_id=source, source_checksum=checksum,
                    metadata_snapshot=_metadata_snapshot(
                        registry[source], reviewed_exclusions=reviewed_exclusions,
                        provider_audit=provider_audit,
                    ), rows=rows,
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
