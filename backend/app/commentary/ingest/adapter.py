"""Adapter for the local HelloAO commentary bundle format."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
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
_CATALOG_BOOK_REQUIRED = frozenset({
    'id', 'commentaryId', 'name', 'commonName', 'order', 'numberOfChapters',
    'firstChapterNumber', 'firstChapterApiLink', 'lastChapterNumber',
    'lastChapterApiLink', 'totalNumberOfVerses', 'sha256',
    'firstChapterReference', 'lastChapterReference',
})
_CATALOG_BOOK_ALLOWED = _CATALOG_BOOK_REQUIRED | {'introduction'}
_COMMENTARY_REQUIRED = frozenset({
    'id', 'name', 'website', 'licenseUrl', 'englishName', 'language',
    'textDirection', 'availableFormats', 'listOfBooksApiLink', 'numberOfBooks',
    'totalNumberOfChapters', 'totalNumberOfVerses',
})
_COMMENTARY_ALLOWED = _COMMENTARY_REQUIRED | {
    'licenseNotes', 'licenseNotice', 'sha256', 'listOfProfilesApiLink',
    'totalNumberOfProfiles', 'languageName', 'languageEnglishName',
}
_CHAPTER_DOCUMENT_KEYS = frozenset({
    'commentary', 'book', 'thisChapterLink', 'nextChapterApiLink',
    'previousChapterApiLink', 'thisChapterReference', 'nextChapterReference',
    'previousChapterReference', 'numberOfVerses', 'chapter',
})
_RANGE = re.compile(r'([1-9][0-9]*)-([1-9][0-9]*)\Z')
_READ_CHUNK_BYTES = 64 * 1024
_DUPLICATE_JSON_KEY_ERROR = 'bundle contains a duplicate JSON key.'
_JSON_CONSTANT_ERROR = 'bundle must not contain nonstandard JSON constants.'
_JSON_ERROR = 'bundle must contain valid JSON.'


@dataclass(frozen=True, slots=True)
class HelloAOCommentaryBook:
    source_id: str
    source_book_id: str
    work_id: str
    name: str
    common_name: str
    order: int
    chapter_count: int
    first_chapter: int | None
    last_chapter: int | None
    introduction: str | None
    commentary_identity: str
    provider_dataset_checksum: str
    license_url: str
    language: str
    total_commentary_verses: int
    total_book_verses: int

    @property
    def chapter_urls(self) -> tuple[str, ...]:
        if self.chapter_count == 0:
            return ()
        base = f'https://bible.helloao.org/api/c/{self.source_id}/{self.source_book_id}'
        return tuple(f'{base}/{chapter}.json' for chapter in range(
            self.first_chapter, self.last_chapter + 1,  # type: ignore[arg-type,operator]
        ))

    @property
    def artifact_names(self) -> tuple[str, ...]:
        if self.chapter_count == 0:
            return ()
        return tuple(
            f'{self.source_book_id}-{chapter}.json'
            for chapter in range(  # type: ignore[arg-type,operator]
                self.first_chapter, self.last_chapter + 1,
            )
        )


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
    try:
        path_stat = os.lstat(path)
    except OSError as exc:
        raise ValueError('path must be a readable regular file.') from exc
    if not stat.S_ISREG(path_stat.st_mode):
        raise ValueError('path must be a regular file.')
    no_follow = getattr(os, 'O_NOFOLLOW', 0)
    non_block = getattr(os, 'O_NONBLOCK', 0)
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow | non_block)
    except OSError as exc:
        raise ValueError('path must be a readable regular file.') from exc

    try:
        descriptor_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(descriptor_stat.st_mode)
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


def _decode_bundle(raw: bytes) -> Mapping[str, Any]:
    parsed = _decode_json_object(raw)
    if set(parsed) != {'commentary', 'books'}:
        raise ValueError('bundle must have exactly the top-level keys commentary and books.')
    return parsed


def _decode_json_object(raw: bytes) -> Mapping[str, Any]:
    if type(raw) is not bytes:
        raise ValueError('bundle bytes must be bytes.')
    if len(raw) > _MAX_BUNDLE_BYTES:
        raise ValueError('bundle must be no larger than 5 MiB.')
    try:
        text = raw.decode('utf-8', errors='strict')
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
    return _require_mapping('bundle', parsed)


def _validate_commentary(value: object, source_id: str) -> Mapping[str, Any]:
    commentary = _require_mapping('commentary', value)
    if not _COMMENTARY_REQUIRED.issubset(commentary) or not set(commentary).issubset(
        _COMMENTARY_ALLOWED
    ):
        raise ValueError('commentary has unexpected or missing keys.')
    if _normalize_scalar('commentary id', commentary['id'], maximum=500) != source_id:
        raise ValueError('commentary id does not match the requested source.')
    if commentary['listOfBooksApiLink'] != f'/api/c/{source_id}/books.json':
        raise ValueError('commentary books link does not match the requested source.')
    for field in (
        'name', 'website', 'licenseUrl', 'englishName', 'language', 'textDirection',
        'listOfProfilesApiLink', 'languageName', 'languageEnglishName',
    ):
        _normalize_scalar(f'commentary {field}', commentary[field], maximum=2048)
    if commentary['availableFormats'] != ['json']:
        raise ValueError('commentary availableFormats must identify only JSON.')
    if (
        type(commentary.get('sha256')) is not str
        or re.fullmatch(r'[0-9a-f]{64}', commentary['sha256']) is None
    ):
        raise ValueError('commentary sha256 must be a lowercase SHA-256 digest.')
    for optional in ('licenseNotes', 'licenseNotice'):
        if optional in commentary and commentary[optional] is not None:
            _normalize_scalar(f'commentary {optional}', commentary[optional], maximum=10_000)
    for field in ('numberOfBooks', 'totalNumberOfChapters'):
        _require_positive_integer(f'commentary {field}', commentary[field])
    if type(commentary['totalNumberOfVerses']) is not int or commentary['totalNumberOfVerses'] < 0:
        raise ValueError('commentary totalNumberOfVerses must be nonnegative.')
    return commentary


def _commentary_identity(commentary: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        commentary, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')
    return sha256(serialized).hexdigest()


def _chapter_reference(
    name: str, value: object, source_id: str, book_id: str, chapter: int,
) -> None:
    reference = _require_mapping(name, value)
    _require_exact_keys(name, reference, frozenset({'commentaryId', 'book', 'chapter'}))
    if reference != {'commentaryId': source_id, 'book': book_id, 'chapter': chapter}:
        raise ValueError(f'{name} does not match its chapter coordinates.')


def _navigation_reference(
    name: str, link: object, reference: object, source_id: str,
) -> None:
    if link is None or reference is None:
        if link is not None or reference is not None:
            raise ValueError(f'{name} link and reference must both be null or present.')
        return
    value = _require_mapping(f'{name} reference', reference)
    _require_exact_keys(
        f'{name} reference', value, frozenset({'commentaryId', 'book', 'chapter'}),
    )
    book_id = value.get('book')
    chapter = value.get('chapter')
    if (
        value.get('commentaryId') != source_id
        or type(book_id) is not str or re.fullmatch(r'[A-Z0-9]{3}', book_id) is None
        or type(chapter) is not int or chapter <= 0
        or link != f'/api/c/{source_id}/{book_id}/{chapter}.json'
    ):
        raise ValueError(f'{name} navigation does not match its coordinates.')


def _catalog_book(
    raw_book: object, source_id: str, source_to_work: Mapping[str, str], index: int,
    commentary_identity: str, commentary: Mapping[str, Any],
) -> HelloAOCommentaryBook:
    book = _require_mapping(f'books[{index}]', raw_book)
    if not _CATALOG_BOOK_REQUIRED.issubset(book) or not set(book).issubset(_CATALOG_BOOK_ALLOWED):
        raise ValueError(f'books[{index}] has unexpected or missing keys.')
    book_id = _normalize_scalar(f'books[{index}].id', book['id'], maximum=500)
    if book_id not in source_to_work or book['commentaryId'] != source_id:
        raise ValueError('catalog book does not match the requested source and book map.')
    work_id = source_to_work[book_id]
    labels = []
    for field in ('name', 'commonName'):
        label = _normalize_scalar(f'books[{index}].{field}', book[field], maximum=500)
        if resolve_source_work_id(label) != work_id:
            raise ValueError('catalog book label does not match its canonical work.')
        labels.append(label)
    order = _require_positive_integer(f'books[{index}].order', book['order'])
    count_value = book['numberOfChapters']
    if type(count_value) is not int or count_value < 0:
        raise ValueError(f'books[{index}].numberOfChapters must be nonnegative.')
    count = count_value
    if count == 0:
        if any(book[field] is not None for field in (
            'firstChapterNumber', 'firstChapterApiLink', 'firstChapterReference',
            'lastChapterNumber', 'lastChapterApiLink', 'lastChapterReference',
        )):
            raise ValueError('zero-chapter catalog book must have null chapter bounds and links.')
        first = None
        last = None
    else:
        first = _require_positive_integer(
            f'books[{index}].firstChapterNumber', book['firstChapterNumber'],
        )
        last = _require_positive_integer(
            f'books[{index}].lastChapterNumber', book['lastChapterNumber'],
        )
        if first != 1 or last != count:
            if first != 1 or count > last:
                raise ValueError('catalog chapter bounds and count are inconsistent.')
        base = f'/api/c/{source_id}/{book_id}'
        if (
            book['firstChapterApiLink'] != f'{base}/{first}.json'
            or book['lastChapterApiLink'] != f'{base}/{last}.json'
        ):
            raise ValueError('catalog chapter links do not match chapter bounds.')
    if type(book['totalNumberOfVerses']) is not int or book['totalNumberOfVerses'] < 0:
        raise ValueError('catalog totalNumberOfVerses must be nonnegative.')
    if (
        type(book.get('sha256')) is not str
        or re.fullmatch(r'[0-9a-f]{64}', book['sha256']) is None
    ):
        raise ValueError('catalog book sha256 must be a lowercase SHA-256 digest.')
    if count:
        _chapter_reference(
            f'books[{index}].firstChapterReference', book['firstChapterReference'],
            source_id, book_id, first,  # type: ignore[arg-type]
        )
        _chapter_reference(
            f'books[{index}].lastChapterReference', book['lastChapterReference'],
            source_id, book_id, last,  # type: ignore[arg-type]
        )
    introduction = _optional_body(
        f'books[{index}].introduction', book.get('introduction', ''),
    )
    return HelloAOCommentaryBook(
        source_id, book_id, work_id, labels[0], labels[1], order, count, first, last,
        introduction, commentary_identity, commentary['sha256'], commentary['licenseUrl'],
        commentary['language'], commentary['totalNumberOfVerses'], book['totalNumberOfVerses'],
    )


def load_helloao_catalog_bytes(
    raw: bytes, source_id: str, book_map: Mapping[str, str],
) -> tuple[HelloAOCommentaryBook, ...]:
    """Validate a documented commentary books.json and return chapter descriptors."""
    document = _decode_json_object(raw)
    if set(document) != {'commentary', 'books'}:
        raise ValueError('catalog must have exactly commentary and books.')
    commentary = _validate_commentary(document['commentary'], source_id)
    identity = _commentary_identity(commentary)
    source_to_work = _normalize_book_map(book_map)
    books_value = document['books']
    if type(books_value) is not list or len(books_value) != commentary['numberOfBooks']:
        raise ValueError('catalog book count does not match commentary metadata.')
    books = tuple(
        _catalog_book(value, source_id, source_to_work, index, identity, commentary)
        for index, value in enumerate(books_value)
    )
    if (
        len({book.source_book_id for book in books}) != len(books)
        or len({book.order for book in books}) != len(books)
        or tuple(book.order for book in books) != tuple(sorted(book.order for book in books))
        or sum(book.chapter_count for book in books) != commentary['totalNumberOfChapters']
    ):
        raise ValueError('catalog contains duplicate, unordered, or inconsistent books.')
    return books


def load_helloao_chapter_bytes(
    raw: bytes, source_id: str, book: HelloAOCommentaryBook, expected_chapter: int,
    *, excluded_content_indices: frozenset[int] = frozenset(),
) -> tuple[NormalizedCommentaryEntry, ...]:
    """Normalize one exact documented commentary chapter response atomically."""
    if not isinstance(book, HelloAOCommentaryBook) or book.source_id != source_id:
        raise ValueError('chapter descriptor does not match the requested source.')
    if book.chapter_count == 0:
        raise ValueError('zero-chapter book cannot have a chapter artifact.')
    document = _decode_json_object(raw)
    _require_exact_keys('chapter document', document, _CHAPTER_DOCUMENT_KEYS)
    commentary = _validate_commentary(document['commentary'], source_id)
    if _commentary_identity(commentary) != book.commentary_identity:
        raise ValueError('chapter commentary metadata does not match the reviewed catalog.')
    raw_book = _catalog_book(document['book'], source_id, {
        book.source_book_id: book.work_id,
    }, 0, book.commentary_identity, commentary)
    if raw_book != book:
        raise ValueError('chapter book metadata does not match the reviewed catalog.')
    chapter = _require_mapping('chapter', document['chapter'])
    if set(chapter) not in ({'number', 'content'}, {'number', 'introduction', 'content'}):
        raise ValueError('chapter has unexpected or missing keys.')
    number = _require_positive_integer('chapter number', chapter['number'])
    if (
        type(expected_chapter) is not int
        or expected_chapter < book.first_chapter or expected_chapter > book.last_chapter
        or number != expected_chapter
    ):
        raise ValueError('chapter number does not match the expected artifact coordinates.')
    expected_link = f'/api/c/{source_id}/{book.source_book_id}/{number}.json'
    if document['thisChapterLink'] != expected_link:
        raise ValueError('chapter link does not match its reviewed coordinates.')
    _chapter_reference(
        'thisChapterReference', document['thisChapterReference'], source_id,
        book.source_book_id, number,
    )
    _navigation_reference(
        'nextChapter', document['nextChapterApiLink'], document['nextChapterReference'],
        source_id,
    )
    _navigation_reference(
        'previousChapter', document['previousChapterApiLink'],
        document['previousChapterReference'], source_id,
    )
    if type(document['numberOfVerses']) is not int or document['numberOfVerses'] < 0:
        raise ValueError('numberOfVerses must be nonnegative.')
    content = chapter['content']
    if type(content) is not list or len(content) != document['numberOfVerses']:
        raise ValueError('chapter content count must match numberOfVerses.')
    if (
        type(excluded_content_indices) is not frozenset
        or any(type(index) is not int or index < 0 for index in excluded_content_indices)
        or any(index >= len(content) for index in excluded_content_indices)
    ):
        raise ValueError('content exclusion indices must be a canonical in-range frozenset.')
    prefix = f'helloao:{source_id}:{book.source_book_id}:chapter:{number}'
    rows: list[NormalizedCommentaryEntry] = []
    position = 0
    introduction = _optional_body('chapter introduction', chapter.get('introduction', ''))
    if introduction is not None:
        rows.append(NormalizedCommentaryEntry(
            book.work_id, number, None, None, 'chapter_intro', None, introduction,
            f'{prefix}:intro', position,
        ))
        position += 1
    prepared: list[tuple[int, int, int, str, str]] = []
    for index, raw_content in enumerate(content):
        if index in excluded_content_indices:
            continue
        item = _require_mapping(f'content[{index}]', raw_content)
        _require_exact_keys(f'content[{index}]', item, _CONTENT_KEYS)
        if item['type'] != 'verse':
            raise ValueError('commentary chapter content type must be verse.')
        start, end, entry_type = _parse_verse_number(item['number'])
        prepared.append((index, start, end, entry_type, _content_body(item['content'])))
    anchor_counts: dict[tuple[int, int], int] = {}
    for _, start, end, _, _ in prepared:
        anchor_counts[(start, end)] = anchor_counts.get((start, end), 0) + 1
    occurrences: dict[tuple[int, int], int] = {}
    for _, start, end, entry_type, body in prepared:
        anchor = (start, end)
        occurrences[anchor] = occurrences.get(anchor, 0) + 1
        reference = str(start) if start == end else f'{start}-{end}'
        locator = f'{prefix}:verse:{reference}'
        if anchor_counts[anchor] > 1:
            locator = f'{locator}:occurrence:{occurrences[anchor]}'
        rows.append(NormalizedCommentaryEntry(
            book.work_id, number, start, end, entry_type, None,
            body, locator, position,
        ))
        position += 1
    return tuple(rows)


def _normalize_bundle(
    bundle: Mapping[str, Any], book_map: Mapping[str, str],
) -> Iterator[NormalizedCommentaryEntry]:
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
            content_anchor_occurrences: dict[tuple[int, int], int] = {}

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
                anchor = (verse_start, verse_end)
                occurrence = content_anchor_occurrences.get(anchor, 0) + 1
                content_anchor_occurrences[anchor] = occurrence
                locator = f'{chapter_prefix}:verse:{reference}'
                if occurrence > 1:
                    locator = f'{locator}:occurrence:{occurrence}'
                entries.append(emit(
                    work_id, chapter_number, verse_start, verse_end, entry_type, body,
                    locator,
                ))

    return iter(tuple(entries))


def load_helloao_bundle_bytes(
    raw: bytes, book_map: Mapping[str, str],
) -> Iterator[NormalizedCommentaryEntry]:
    """Normalize the exact bounded bytes already verified by a trusted caller."""
    return _normalize_bundle(_decode_bundle(raw), book_map)


def load_helloao_bundle(path: Path, book_map: Mapping[str, str]) -> Iterator[NormalizedCommentaryEntry]:
    """Return an iterator over one completely validated local HelloAO JSON bundle."""
    return load_helloao_bundle_bytes(_read_bundle_bytes(path), book_map)
