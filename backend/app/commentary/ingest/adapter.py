"""Adapter for the local HelloAO commentary bundle format."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
from collections.abc import Iterator, Mapping
from typing import Any

from app.library.ingest.types import resolve_source_work_id

from .types import NormalizedCommentaryEntry, _normalize_scalar, normalize_body


_MAX_BUNDLE_BYTES = 5 * 1024 * 1024
_BOOK_KEYS = frozenset({
    'id', 'name', 'commonName', 'introduction', 'order', 'numberOfChapters', 'chapters',
})
_CHAPTER_KEYS = frozenset({'number', 'introduction', 'content'})
_CONTENT_KEYS = frozenset({'type', 'number', 'content'})
_RANGE = re.compile(r'([1-9][0-9]*)-([1-9][0-9]*)\Z')
_READ_CHUNK_BYTES = 64 * 1024
_DUPLICATE_JSON_KEY_ERROR = 'bundle contains a duplicate JSON key.'
_JSON_CONSTANT_ERROR = 'bundle must not contain nonstandard JSON constants.'
_JSON_ERROR = 'bundle must contain valid JSON.'


def _require_mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f'{name} must be an object.')
    return value


def _require_exact_keys(name: str, value: Mapping[str, Any], expected: frozenset[str]) -> None:
    if set(value) != expected:
        raise ValueError(f'{name} has unexpected or missing keys.')


def _require_positive_integer(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f'{name} must be a positive integer.')
    return value


def _normalize_book_map(book_map: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(book_map, Mapping) or not book_map:
        raise ValueError('book_map must be a nonempty mapping.')
    normalized: dict[str, str] = {}
    source_id_by_work: dict[str, str] = {}
    for source_id, work_id in book_map.items():
        source_key = _normalize_scalar('book_map source id', source_id, maximum=500)
        if source_key in normalized:
            raise ValueError('book_map has ambiguous duplicate source IDs after normalization.')
        work_label = _normalize_scalar('book_map work id', work_id, maximum=255)
        try:
            canonical_work_id = resolve_source_work_id(work_label)
        except ValueError as exc:
            raise ValueError(f'book_map contains an unknown work: {work_label!r}.') from exc
        if canonical_work_id in source_id_by_work:
            raise ValueError(
                'book_map source IDs must map to unique canonical work IDs.',
            )
        source_id_by_work[canonical_work_id] = source_key
        normalized[source_key] = canonical_work_id
    return normalized


def _parse_verse_number(value: object) -> tuple[int, int, str]:
    if type(value) is int:
        if value <= 0:
            raise ValueError('content number must be a positive integer or an ASCII N-M range.')
        return value, value, 'verse'
    if type(value) is not str:
        raise ValueError('content number must be a positive integer or an ASCII N-M range.')
    match = _RANGE.fullmatch(value)
    if match is None:
        raise ValueError('content number must be a positive integer or an ASCII N-M range.')
    try:
        start, end = int(match.group(1)), int(match.group(2))
    except ValueError as exc:
        raise ValueError('content number must be a positive integer or an ASCII N-M range.') from exc
    if end < start:
        raise ValueError('content number range must end at or after its start.')
    return start, end, 'verse' if start == end else 'verse_range'


def _content_body(value: object) -> str:
    if type(value) is not list or not value:
        raise ValueError('content must be a nonempty list of strings.')
    paragraphs: list[str] = []
    for index, fragment in enumerate(value):
        if type(fragment) is not str:
            raise ValueError(f'content fragment {index} must be a string.')
        paragraphs.append(normalize_body(fragment))
    return normalize_body('\n\n'.join(paragraphs))


def _optional_body(name: str, value: object) -> str | None:
    if type(value) is not str:
        raise ValueError(f'{name} must be a string.')
    if value.strip():
        return normalize_body(value)
    # Validate even whitespace-only optional fields, which otherwise emit no row.
    normalize_body(f'{value}x')
    return None


def _reject_json_constant(value: str) -> None:
    raise ValueError(_JSON_CONSTANT_ERROR)


def _reject_duplicate_json_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(_DUPLICATE_JSON_KEY_ERROR)
        result[key] = value
    return result


def _read_bundle_bytes(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise ValueError('path must be a Path to a regular file.')
    no_follow = getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow)
    except OSError as exc:
        raise ValueError('path must be a readable regular file.') from exc

    try:
        descriptor_stat = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_stat.st_mode):
            raise ValueError('path must be a regular file.')
        if not no_follow:
            path_stat = os.lstat(path)
            if (
                not stat.S_ISREG(path_stat.st_mode)
                or path_stat.st_dev != descriptor_stat.st_dev
                or path_stat.st_ino != descriptor_stat.st_ino
            ):
                raise ValueError('path must be a regular file.')

        chunks: list[bytes] = []
        size = 0
        while size <= _MAX_BUNDLE_BYTES:
            chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, _MAX_BUNDLE_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > _MAX_BUNDLE_BYTES:
            raise ValueError('bundle must be no larger than 5 MiB.')
        return b''.join(chunks)
    except OSError as exc:
        raise ValueError('bundle could not be read.') from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass


def _read_bundle(path: Path) -> Mapping[str, Any]:
    try:
        text = _read_bundle_bytes(path).decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise ValueError('bundle must be valid UTF-8.') from exc
    try:
        parsed = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_members,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(_JSON_ERROR) from exc
    except ValueError as exc:
        if str(exc) in {_DUPLICATE_JSON_KEY_ERROR, _JSON_CONSTANT_ERROR}:
            raise ValueError(str(exc)) from exc
        raise ValueError(_JSON_ERROR) from exc
    bundle = _require_mapping('bundle', parsed)
    if set(bundle) != {'commentary', 'books'}:
        raise ValueError('bundle must have exactly the top-level keys commentary and books.')
    return bundle


def load_helloao_bundle(path: Path, book_map: Mapping[str, str]) -> Iterator[NormalizedCommentaryEntry]:
    """Return an iterator over one completely validated local HelloAO JSON bundle."""
    bundle = _read_bundle(path)
    source_to_work = _normalize_book_map(book_map)

    commentary = _require_mapping('commentary', bundle['commentary'])
    if 'id' not in commentary:
        raise ValueError('commentary must contain a nonblank id.')
    commentary_id = _normalize_scalar('commentary id', commentary['id'], maximum=500)
    books = bundle['books']
    if type(books) is not list:
        raise ValueError('books must be a list.')

    position = 0
    entries: list[NormalizedCommentaryEntry] = []
    seen_book_ids: set[str] = set()
    seen_verse_identities: set[tuple[str, int, int, int, str]] = set()

    def emit(
        work_id: str,
        chapter: int | None,
        verse_start: int | None,
        verse_end: int | None,
        entry_type: str,
        body: str,
        locator: str,
    ) -> NormalizedCommentaryEntry:
        nonlocal position
        if entry_type in {'verse', 'verse_range'}:
            verse_identity = (work_id, chapter, verse_start, verse_end, entry_type)  # type: ignore[arg-type]
            if verse_identity in seen_verse_identities:
                raise ValueError('duplicate verse or verse-range identity.')
            seen_verse_identities.add(verse_identity)
        entry = NormalizedCommentaryEntry(
            work_id=work_id, chapter=chapter, verse_start=verse_start, verse_end=verse_end,
            entry_type=entry_type, heading=None, body=body, source_locator=locator, position=position,
        )
        position += 1
        return entry

    for book_index, raw_book in enumerate(books):
        book = _require_mapping(f'books[{book_index}]', raw_book)
        _require_exact_keys(f'books[{book_index}]', book, _BOOK_KEYS)
        book_id = _normalize_scalar(f'books[{book_index}].id', book['id'], maximum=500)
        if book_id in seen_book_ids:
            raise ValueError('duplicate book id.')
        seen_book_ids.add(book_id)
        if book_id not in source_to_work:
            raise ValueError(f'book id {book_id!r} is not present in book_map.')
        work_id = source_to_work[book_id]
        for label_name in ('name', 'commonName'):
            label = _normalize_scalar(f'books[{book_index}].{label_name}', book[label_name], maximum=500)
            try:
                label_work_id = resolve_source_work_id(label)
            except ValueError as exc:
                raise ValueError(f'books[{book_index}].{label_name} is not a known work label.') from exc
            if label_work_id != work_id:
                raise ValueError(f'books[{book_index}].{label_name} does not match its mapped work.')
        _require_positive_integer(f'books[{book_index}].order', book['order'])
        number_of_chapters = _require_positive_integer(
            f'books[{book_index}].numberOfChapters', book['numberOfChapters'],
        )
        book_introduction = _optional_body(f'books[{book_index}].introduction', book['introduction'])
        chapters = book['chapters']
        if type(chapters) is not list or len(chapters) != number_of_chapters:
            raise ValueError('book chapter count must match numberOfChapters.')

        prefix = f'helloao:{commentary_id}:{book_id}'
        if book_introduction is not None:
            entries.append(
                emit(work_id, None, None, None, 'book_intro', book_introduction, f'{prefix}:book-intro'),
            )

        seen_chapter_numbers: set[int] = set()
        for chapter_index, raw_chapter in enumerate(chapters):
            chapter_data = _require_mapping(f'chapters[{chapter_index}]', raw_chapter)
            _require_exact_keys(f'chapters[{chapter_index}]', chapter_data, _CHAPTER_KEYS)
            chapter_number = _require_positive_integer(
                f'chapters[{chapter_index}].number', chapter_data['number'],
            )
            if chapter_number in seen_chapter_numbers:
                raise ValueError('duplicate chapter number.')
            seen_chapter_numbers.add(chapter_number)
            if chapter_number != chapter_index + 1:
                raise ValueError('chapter numbers must be sequential from 1.')
            chapter_introduction = _optional_body(
                f'chapters[{chapter_index}].introduction', chapter_data['introduction'],
            )
            content = chapter_data['content']
            if type(content) is not list:
                raise ValueError(f'chapters[{chapter_index}].content must be a list.')

            chapter_prefix = f'{prefix}:chapter:{chapter_number}'
            if chapter_introduction is not None:
                entries.append(emit(
                    work_id, chapter_number, None, None, 'chapter_intro', chapter_introduction,
                    f'{chapter_prefix}:intro',
                ))
            for content_index, raw_content in enumerate(content):
                content_item = _require_mapping(f'content[{content_index}]', raw_content)
                _require_exact_keys(f'content[{content_index}]', content_item, _CONTENT_KEYS)
                if content_item['type'] != 'verse':
                    raise ValueError('content type must be verse.')
                verse_start, verse_end, entry_type = _parse_verse_number(content_item['number'])
                body = _content_body(content_item['content'])
                reference = str(verse_start) if verse_start == verse_end else f'{verse_start}-{verse_end}'
                entries.append(emit(
                    work_id, chapter_number, verse_start, verse_end, entry_type, body,
                    f'{chapter_prefix}:verse:{reference}',
                ))

    return iter(tuple(entries))
