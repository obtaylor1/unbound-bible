"""Strict adapter for a frozen EOTCOpenSource/HaCohen research bundle."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import stat
from typing import Any
from zipfile import BadZipFile, ZipFile, ZipInfo

from app.library.ingest.manifest import SourceManifest, WeahaduBundleAdapterOptions
from app.library.ingest.normalize import normalize_verse
from app.library.ingest.types import NormalizedVerse


_INDEX_MEMBER = 'data/index.json'
_MAX_ARCHIVE_MEMBERS = 1_024
_MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024


def _file_checksum(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _is_safe_member(info: ZipInfo) -> bool:
    name = info.filename
    path = PurePosixPath(name)
    unix_mode = info.external_attr >> 16
    return (
        bool(name)
        and not name.startswith(('/', '\\'))
        and '\\' not in name
        and all(part not in {'', '.', '..'} for part in path.parts)
        and not stat.S_ISLNK(unix_mode)
        and not (info.flag_bits & 0x1)
    )


def _load_json(archive: ZipFile, member: str) -> dict[str, Any]:
    try:
        payload = json.loads(archive.read(member).decode('utf-8'))
    except KeyError as error:
        raise ValueError(f'missing required archive member: {member}') from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f'invalid UTF-8 JSON archive member: {member}') from error
    if not isinstance(payload, dict):
        raise ValueError(f'archive member must contain a JSON object: {member}')
    return payload


def _validated_archive(path: Path) -> ZipFile:
    try:
        archive = ZipFile(path)
    except (BadZipFile, OSError) as error:
        raise ValueError(f'invalid source archive: {path.name}') from error
    infos = archive.infolist()
    if len(infos) > _MAX_ARCHIVE_MEMBERS:
        archive.close()
        raise ValueError('source archive contains too many members.')
    if any(not _is_safe_member(info) for info in infos):
        archive.close()
        raise ValueError('source archive contains an unsafe archive member.')
    if sum(info.file_size for info in infos) > _MAX_UNCOMPRESSED_BYTES:
        archive.close()
        raise ValueError('source archive exceeds the uncompressed size limit.')
    return archive


def _book_member(index_book: dict[str, Any]) -> str:
    relative = index_book.get('file')
    if not isinstance(relative, str) or not relative:
        raise ValueError('indexed book is missing its source file.')
    candidate = PurePosixPath(relative)
    if relative.startswith(('/', '\\')) or '\\' in relative or any(
        part in {'', '.', '..'} for part in candidate.parts
    ):
        raise ValueError('indexed book contains an unsafe source file path.')
    return str(PurePosixPath('data') / candidate)


def _positive_number(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f'{label} must be a positive integer.')
    return value


def _rows_for_book(
    *,
    archive: ZipFile,
    archive_name: str,
    index_book: dict[str, Any],
    work_id: str,
    edition_code: str,
) -> list[NormalizedVerse]:
    member = _book_member(index_book)
    book = _load_json(archive, member)
    source_id = index_book.get('id')
    if book.get('id') != source_id:
        raise ValueError(f'book identity mismatch for {source_id!r}.')
    source_book = book.get('name')
    if not isinstance(source_book, str) or not source_book.strip():
        raise ValueError(f'book {source_id!r} has no source name.')
    editions = book.get('editions')
    if not isinstance(editions, dict) or edition_code not in editions:
        raise ValueError(f'book {source_id!r} is missing edition {edition_code!r}.')
    edition = editions[edition_code]
    if not isinstance(edition, dict) or edition.get('language') != 'gez':
        raise ValueError(f'edition {edition_code!r} must identify Ge\'ez text.')
    chapters = edition.get('chapters')
    if not isinstance(chapters, list) or not chapters:
        raise ValueError(f'book {source_id!r} has no chapters in {edition_code!r}.')

    rows: list[NormalizedVerse] = []
    chapter_numbers: set[int] = set()
    for chapter_record in chapters:
        if not isinstance(chapter_record, dict):
            raise ValueError(f'book {source_id!r} contains an invalid chapter record.')
        chapter = _positive_number(chapter_record.get('n'), 'chapter number')
        if chapter in chapter_numbers:
            raise ValueError(f'book {source_id!r} contains a duplicate chapter {chapter}.')
        chapter_numbers.add(chapter)
        verses = chapter_record.get('verses')
        if not isinstance(verses, list) or not verses:
            raise ValueError(f'book {source_id!r} chapter {chapter} has no verses.')
        verse_numbers: set[int] = set()
        for verse_record in verses:
            if not isinstance(verse_record, dict):
                raise ValueError('book contains an invalid verse record.')
            verse = _positive_number(verse_record.get('n'), 'verse number')
            if verse in verse_numbers:
                raise ValueError(
                    f'book {source_id!r} chapter {chapter} contains duplicate verse {verse}.'
                )
            verse_numbers.add(verse)
            text = verse_record.get('t')
            if not isinstance(text, str) or not text.strip():
                raise ValueError(
                    f'book {source_id!r} chapter {chapter} verse {verse} has empty text.'
                )
            row = normalize_verse(
                source_book,
                chapter,
                verse,
                text,
                f'{archive_name}!/{member}#{edition_code}:{chapter}:{verse}',
            )
            if row.work_id != work_id:
                raise ValueError(
                    f'book {source_id!r} resolved to {row.work_id!r}, expected {work_id!r}.'
                )
            rows.append(row)
    return rows


def parse_weahadu_bundle(
    manifest: SourceManifest, manifest_directory: Path
) -> tuple[NormalizedVerse, ...]:
    """Read only explicitly mapped Ge'ez books from one checksummed ZIP source."""
    options = manifest.adapter_options
    if manifest.adapter != 'weahadu_bundle' or not isinstance(
        options, WeahaduBundleAdapterOptions
    ):
        raise ValueError('manifest does not contain weahadu_bundle adapter options.')
    if len(manifest.source_files) != 1:
        raise ValueError('weahadu_bundle requires exactly one source archive.')
    if set(options.book_map.values()) != set(manifest.expected_works):
        raise ValueError('book_map must exactly match expected_works.')

    source = manifest.source_files[0]
    archive_path = manifest_directory / source.path
    manifest_root = manifest_directory.resolve()
    if (
        archive_path.is_symlink()
        or not archive_path.is_file()
        or not archive_path.resolve().is_relative_to(manifest_root)
    ):
        raise ValueError(
            f'source archive must be a regular file inside the manifest directory: {source.path}'
        )
    if _file_checksum(archive_path) != source.sha256:
        raise ValueError(f'source archive checksum does not match manifest: {source.path}')

    with _validated_archive(archive_path) as archive:
        index = _load_json(archive, _INDEX_MEMBER)
        index_books = index.get('books')
        if not isinstance(index_books, list):
            raise ValueError('bundle index must contain a books array.')
        by_id: dict[str, dict[str, Any]] = {}
        for record in index_books:
            if not isinstance(record, dict) or not isinstance(record.get('id'), str):
                raise ValueError('bundle index contains an invalid book record.')
            source_id = record['id'].casefold()
            if source_id in by_id:
                raise ValueError(f'bundle index contains duplicate book id {record["id"]!r}.')
            by_id[source_id] = record

        rows: list[NormalizedVerse] = []
        for source_id, work_id in options.book_map.items():
            index_book = by_id.get(source_id.casefold())
            if index_book is None:
                raise ValueError(f'bundle index is missing mapped book {source_id!r}.')
            rows.extend(_rows_for_book(
                archive=archive,
                archive_name=source.path,
                index_book=index_book,
                work_id=work_id,
                edition_code=options.edition,
            ))
    return tuple(rows)
