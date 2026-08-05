"""Deterministic validation and provenance checks for commentary imports."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Any, Literal
from urllib.parse import urlsplit

from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS

from .types import NormalizedCommentaryEntry


_CANONICAL_WORKS = (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS)
_KNOWN_WORK_IDS = frozenset(work.id for work in _CANONICAL_WORKS)
_WORK_ORDER = {work.id: index for index, work in enumerate(_CANONICAL_WORKS)}
_CODE = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
_CHECKSUM = re.compile(r'^[0-9a-f]{64}$')
_SOURCE_BOOK = re.compile(r'^[A-Z0-9]{1,16}$')
_APPROVED_SOURCE_IDS = (
    'matthew-henry', 'john-gill', 'adam-clarke', 'jamieson-fausset-brown', 'keil-delitzsch',
)
_APPROVED_SOURCE_ID_SET = frozenset(_APPROVED_SOURCE_IDS)
_REGISTRY_FIELDS = frozenset({
    'title', 'abbreviation', 'author', 'publication_period', 'tradition', 'language',
    'attribution', 'upstream_url', 'license_spdx', 'license_url', 'license_basis',
    'license_reviewed_on', 'source_checksum', 'expected_book_count', 'expected_source_books',
})
_PUBLIC_DOMAIN_SPDX = 'LicenseRef-Public-Domain'
_PUBLIC_DOMAIN_URL = 'https://creativecommons.org/publicdomain/mark/1.0/'
_MAX_REGISTRY_BYTES = 256 * 1024
_READ_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """A stable, user-actionable validation finding."""

    severity: Literal['error', 'warning']
    code: str
    message: str
    work_id: str | None = None
    chapter: int | None = None
    verse: int | None = None

    def __post_init__(self) -> None:
        if self.severity not in {'error', 'warning'}:
            raise ValueError('severity must be error or warning.')
        if type(self.code) is not str or _CODE.fullmatch(self.code) is None:
            raise ValueError('code must be a conservative lowercase snake identifier.')
        if type(self.message) is not str or not self.message.strip():
            raise ValueError('message must be a nonblank string.')
        if self.work_id is not None and (type(self.work_id) is not str or not self.work_id.strip()):
            raise ValueError('work_id must be a nonblank string when provided.')
        if self.chapter is not None:
            if self.work_id is None or type(self.chapter) is not int or self.chapter <= 0:
                raise ValueError('chapter requires work_id and must be positive.')
        if self.verse is not None:
            if self.chapter is None or type(self.verse) is not int or self.verse <= 0:
                raise ValueError('verse requires chapter and must be positive.')


def _finding_key(finding: ValidationFinding) -> tuple[object, ...]:
    return (
        0 if finding.severity == 'error' else 1,
        _WORK_ORDER.get(finding.work_id, len(_WORK_ORDER)), finding.work_id or '',
        finding.chapter if finding.chapter is not None else -1,
        finding.verse if finding.verse is not None else -1,
        finding.code, finding.message,
    )


def _freeze_coverage(coverage: Mapping[str, Any]) -> Mapping[str, Any]:
    by_work = coverage.get('by_work')
    if not isinstance(by_work, Mapping):
        raise ValueError('coverage must contain by_work.')
    copied_by_work: dict[str, Mapping[str, int]] = {}
    for work_id, values in by_work.items():
        if type(work_id) is not str or not isinstance(values, Mapping):
            raise ValueError('coverage must contain valid by_work values.')
        chapters, entries = values.get('chapters'), values.get('entries')
        if type(chapters) is not int or type(entries) is not int or chapters < 0 or entries < 0:
            raise ValueError('coverage must contain nonnegative counts.')
        copied_by_work[work_id] = MappingProxyType({'chapters': chapters, 'entries': entries})
    books, chapters, entries = coverage.get('books'), coverage.get('chapters'), coverage.get('entries')
    if any(type(value) is not int or value < 0 for value in (books, chapters, entries)):
        raise ValueError('coverage must contain nonnegative counts.')
    return MappingProxyType({
        'books': books, 'chapters': chapters, 'entries': entries,
        'by_work': MappingProxyType(copied_by_work),
    })


@dataclass(frozen=True, slots=True)
class CommentaryValidationResult:
    """An immutable validation result suitable for publication gating."""

    findings: tuple[ValidationFinding, ...]
    coverage: Mapping[str, Any]

    def __post_init__(self) -> None:
        if type(self.findings) is not tuple or not all(isinstance(item, ValidationFinding) for item in self.findings):
            raise ValueError('findings must be a tuple of ValidationFinding values.')
        object.__setattr__(self, 'findings', tuple(sorted(set(self.findings), key=_finding_key)))
        object.__setattr__(self, 'coverage', _freeze_coverage(self.coverage))

    @property
    def error_count(self) -> int:
        return sum(finding.severity == 'error' for finding in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(finding.severity == 'warning' for finding in self.findings)

    @property
    def publishable(self) -> bool:
        return self.error_count == 0


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Strictly reviewed metadata for a provider-declared public-domain source."""

    title: str
    abbreviation: str
    author: str
    publication_period: str
    tradition: str
    language: str
    attribution: str
    upstream_url: str
    license_spdx: str
    license_url: str
    license_basis: str
    license_reviewed_on: str
    source_checksum: str
    expected_book_count: int
    expected_source_books: tuple[str, ...]


def _normalize_expected_books(expected_books: object) -> frozenset[str]:
    if type(expected_books) not in {set, frozenset} or not expected_books:
        raise ValueError('expected_books must be a nonempty set or frozenset of canonical work IDs.')
    for work_id in expected_books:
        if type(work_id) is not str or work_id not in _KNOWN_WORK_IDS:
            raise ValueError('expected_books must contain exact known canonical work IDs.')
    return frozenset(expected_books)


def _location(row: object) -> tuple[str | None, int | None, int | None]:
    work_id = getattr(row, 'work_id', None)
    if type(work_id) is not str or not work_id.strip():
        return None, None, None
    chapter = getattr(row, 'chapter', None)
    if type(chapter) is not int or chapter <= 0:
        return work_id, None, None
    verse = getattr(row, 'verse_start', None)
    if type(verse) is not int or verse <= 0:
        return work_id, chapter, None
    return work_id, chapter, verse


def _is_safe_normalized_row(row: NormalizedCommentaryEntry) -> bool:
    try:
        reconstructed = NormalizedCommentaryEntry(
            row.work_id, row.chapter, row.verse_start, row.verse_end, row.entry_type,
            row.heading, row.body, row.source_locator, row.position,
        )
    except (TypeError, ValueError):
        return False
    return (
        type(row.work_id) is str
        and type(row.entry_type) is str
        and (row.heading is None or type(row.heading) is str)
        and type(row.body) is str
        and type(row.source_locator) is str
        and type(row.position) is int
        and row == reconstructed
    )


def _coverage(rows: list[NormalizedCommentaryEntry]) -> Mapping[str, Any]:
    works = sorted({row.work_id for row in rows}, key=lambda item: (_WORK_ORDER[item], item))
    by_work: dict[str, dict[str, int]] = {}
    chapter_pairs: set[tuple[str, int]] = set()
    for work_id in works:
        work_rows = [row for row in rows if row.work_id == work_id]
        chapters = {row.chapter for row in work_rows if type(row.chapter) is int and row.chapter > 0}
        chapter_pairs.update((work_id, chapter) for chapter in chapters)
        by_work[work_id] = {'chapters': len(chapters), 'entries': len(work_rows)}
    return {'books': len(works), 'chapters': len(chapter_pairs), 'entries': len(rows), 'by_work': by_work}


def _previous_entries(previous_coverage: Mapping[str, object] | None) -> int | None:
    if previous_coverage is None:
        return None
    if not isinstance(previous_coverage, Mapping):
        raise ValueError('previous_coverage must be a mapping.')
    if set(previous_coverage) == {'entries'}:
        entries = previous_coverage['entries']
        if type(entries) is not int or entries <= 0:
            raise ValueError('previous_coverage entries must be a positive integer.')
        return entries
    if set(previous_coverage) != {'books', 'chapters', 'entries', 'by_work'}:
        raise ValueError('previous_coverage must be an entries count or a complete coverage mapping.')
    books = previous_coverage['books']
    chapters = previous_coverage['chapters']
    entries = previous_coverage['entries']
    by_work = previous_coverage['by_work']
    if (
        type(books) is not int or type(chapters) is not int or type(entries) is not int
        or books < 0 or chapters < 0 or entries < 0 or not isinstance(by_work, Mapping)
    ):
        raise ValueError('previous_coverage must contain nonnegative exact integer counts.')
    work_chapters = 0
    work_entries = 0
    for work_id, work_coverage in by_work.items():
        if type(work_id) is not str or work_id not in _KNOWN_WORK_IDS:
            raise ValueError('previous_coverage by_work must use known canonical work IDs.')
        if not isinstance(work_coverage, Mapping) or set(work_coverage) != {'chapters', 'entries'}:
            raise ValueError('previous_coverage by_work values must contain chapters and entries only.')
        work_chapter_count = work_coverage['chapters']
        work_entry_count = work_coverage['entries']
        if (
            type(work_chapter_count) is not int or type(work_entry_count) is not int
            or work_chapter_count < 0 or work_entry_count < 0
            or work_chapter_count > work_entry_count
            or (work_entry_count == 0 and work_chapter_count != 0)
        ):
            raise ValueError('previous_coverage by_work counts are inconsistent.')
        work_chapters += work_chapter_count
        work_entries += work_entry_count
    if (
        books != len(by_work)
        or chapters != work_chapters
        or entries != work_entries
        or chapters > entries
        or (entries > 0 and books > entries)
        or (entries == 0 and (books != 0 or chapters != 0 or by_work))
    ):
        raise ValueError('previous_coverage counts must match by_work totals.')
    return entries


def validate_commentary(
    rows: Iterable[NormalizedCommentaryEntry], expected_books: set[str] | frozenset[str],
    previous_coverage: Mapping[str, object] | None = None,
) -> CommentaryValidationResult:
    """Validate normalized commentary rows without re-iterating or mutating them."""
    expected = _normalize_expected_books(expected_books)
    previous_entries = _previous_entries(previous_coverage)
    try:
        materialized = tuple(rows)
    except TypeError:
        materialized = ()
        iterable_error = True
    else:
        iterable_error = False

    findings: list[ValidationFinding] = []
    if iterable_error:
        findings.append(ValidationFinding('error', 'invalid_rows_input', 'Rows must be an iterable.'))
    if not materialized:
        findings.append(ValidationFinding('error', 'no_rows', 'No commentary rows were provided.'))

    valid_rows: list[NormalizedCommentaryEntry] = []
    for item in materialized:
        if not isinstance(item, NormalizedCommentaryEntry):
            findings.append(ValidationFinding('error', 'invalid_row_type', 'Row is not a NormalizedCommentaryEntry.'))
            continue
        if not _is_safe_normalized_row(item):
            findings.append(ValidationFinding(
                'error', 'unsafe_normalized_row', 'Normalized commentary row has unsafe or invalid scalars.',
                *_location(item),
            ))
            continue
        valid_rows.append(item)

    observed_books = {row.work_id for row in valid_rows}
    for work_id in sorted(expected - observed_books, key=lambda item: (_WORK_ORDER[item], item)):
        findings.append(ValidationFinding('error', 'missing_expected_book', 'Expected book has no commentary entries.', work_id))
    for work_id in sorted(observed_books - expected, key=lambda item: (_WORK_ORDER[item], item)):
        findings.append(ValidationFinding('error', 'unexpected_book', 'Commentary entries include an unexpected book.', work_id))

    identities: dict[tuple[str, int | None, int | None, int | None, str], list[NormalizedCommentaryEntry]] = defaultdict(list)
    ranges: dict[tuple[str, int], list[NormalizedCommentaryEntry]] = defaultdict(list)
    chapters_by_work: dict[str, set[int]] = defaultdict(set)
    has_book_intro: set[str] = set()
    has_chapter_intro: set[tuple[str, int]] = set()
    for row in valid_rows:
        identity = (row.work_id, row.chapter, row.verse_start, row.verse_end, row.entry_type)
        identities[identity].append(row)
        if row.entry_type == 'book_intro':
            has_book_intro.add(row.work_id)
        if row.chapter is not None:
            chapters_by_work[row.work_id].add(row.chapter)
        if row.entry_type == 'chapter_intro' and row.chapter is not None:
            has_chapter_intro.add((row.work_id, row.chapter))
        if row.entry_type in {'verse', 'verse_range'} and row.chapter is not None:
            ranges[(row.work_id, row.chapter)].append(row)

    for identity, same_identity in identities.items():
        if len(same_identity) > 1:
            work_id, chapter, verse_start, _, _ = identity
            findings.append(ValidationFinding(
                'error', 'duplicate_identity', 'More than one row has the same normalized identity.',
                work_id, chapter, verse_start,
            ))
    for (work_id, chapter), entries in ranges.items():
        ordered = sorted(entries, key=lambda row: (row.verse_start or 0, row.verse_end or 0, row.entry_type))
        furthest_end = 0
        for row in ordered:
            if row.verse_start is not None and row.verse_start <= furthest_end:
                findings.append(ValidationFinding(
                    'error', 'overlapping_coverage', 'Verse or range coverage overlaps another entry.',
                    work_id, chapter, row.verse_start,
                ))
            if row.verse_end is not None:
                furthest_end = max(furthest_end, row.verse_end)

    for work_id in sorted(observed_books, key=lambda item: (_WORK_ORDER[item], item)):
        if work_id not in has_book_intro:
            findings.append(ValidationFinding('warning', 'missing_book_intro', 'Book has no introduction.', work_id))
        for chapter in sorted(chapters_by_work[work_id]):
            if (work_id, chapter) not in has_chapter_intro:
                findings.append(ValidationFinding(
                    'warning', 'missing_chapter_intro', 'Chapter has no introduction.', work_id, chapter,
                ))

    coverage = _coverage(valid_rows)
    if previous_entries is not None and coverage['entries'] * 20 < previous_entries * 19:
        findings.append(ValidationFinding(
            'error', 'record_count_regression', 'Commentary record count regressed by more than five percent.',
        ))
    return CommentaryValidationResult(tuple(findings), coverage)


def _read_registry_bytes(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise ValueError('path must be a Path to a regular file.')
    try:
        path_stat = os.lstat(path)
    except OSError as exc:
        raise ValueError('path must be a readable regular file.') from exc
    if not stat.S_ISREG(path_stat.st_mode):
        raise ValueError('path must be a regular file.')
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    except OSError as exc:
        raise ValueError('path must be a readable regular file.') from exc
    try:
        descriptor_stat = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_stat.st_mode) or (path_stat.st_dev, path_stat.st_ino) != (descriptor_stat.st_dev, descriptor_stat.st_ino):
            raise ValueError('path must be a regular file.')
        chunks: list[bytes] = []
        size = 0
        while size <= _MAX_REGISTRY_BYTES:
            chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, _MAX_REGISTRY_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > _MAX_REGISTRY_BYTES:
            raise ValueError('registry must be no larger than 256 KiB.')
        return b''.join(chunks)
    except OSError as exc:
        raise ValueError('registry could not be read.') from exc
    finally:
        os.close(descriptor)


def _reject_json_constant(_: str) -> None:
    raise ValueError('registry must not contain nonstandard JSON constants.')


def _reject_duplicate_json_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('registry contains a duplicate JSON key.')
        result[key] = value
    return result


def _registry_string(name: str, value: object, maximum: int) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name} must be a nonblank string no longer than {maximum} characters.')
    return value


def _https_url(name: str, value: object) -> str:
    url = _registry_string(name, value, 2048)
    if any(character.isspace() for character in url):
        raise ValueError(f'{name} must be an HTTPS URL without credentials, query, or fragment.')
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f'{name} must be a valid HTTPS URL.') from exc
    if (
        parsed.scheme != 'https' or not parsed.netloc or not hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or port is not None and not 0 < port <= 65535
    ):
        raise ValueError(f'{name} must be an HTTPS URL without credentials, query, or fragment.')
    return url


def _metadata(source_id: str, value: object) -> SourceMetadata:
    if type(value) is not dict or set(value) != _REGISTRY_FIELDS:
        raise ValueError(f'{source_id} must have exactly the required metadata fields.')
    title = _registry_string('title', value['title'], 200)
    abbreviation = _registry_string('abbreviation', value['abbreviation'], 16)
    author = _registry_string('author', value['author'], 200)
    publication_period = _registry_string('publication_period', value['publication_period'], 100)
    tradition = _registry_string('tradition', value['tradition'], 120)
    language = _registry_string('language', value['language'], 16)
    attribution = _registry_string('attribution', value['attribution'], 4096)
    upstream_url = _https_url('upstream_url', value['upstream_url'])
    license_spdx = _registry_string('license_spdx', value['license_spdx'], 64)
    license_url = _https_url('license_url', value['license_url'])
    license_basis = _registry_string('license_basis', value['license_basis'], 2048)
    reviewed = _registry_string('license_reviewed_on', value['license_reviewed_on'], 10)
    if license_spdx != _PUBLIC_DOMAIN_SPDX or license_url != _PUBLIC_DOMAIN_URL:
        raise ValueError('registry must use the approved public-domain license metadata.')
    try:
        reviewed_date = date.fromisoformat(reviewed)
    except ValueError as exc:
        raise ValueError('license_reviewed_on must be an ISO date.') from exc
    if reviewed_date.isoformat() != reviewed or reviewed_date > date.today():
        raise ValueError('license_reviewed_on must be an ISO date that is not in the future.')
    checksum = _registry_string('source_checksum', value['source_checksum'], 64)
    if _CHECKSUM.fullmatch(checksum) is None:
        raise ValueError('source_checksum must be 64 lowercase hexadecimal characters.')
    count = value['expected_book_count']
    codes = value['expected_source_books']
    if type(count) is not int or count <= 0 or type(codes) is not list:
        raise ValueError('expected source book count and list are invalid.')
    if any(type(code) is not str or _SOURCE_BOOK.fullmatch(code) is None for code in codes):
        raise ValueError('expected source books must be nonempty uppercase source IDs.')
    if len(codes) != len(set(codes)) or count != len(codes):
        raise ValueError('expected source book count must equal unique listed source IDs.')
    return SourceMetadata(
        title, abbreviation, author, publication_period, tradition, language, attribution, upstream_url,
        license_spdx, license_url, license_basis, reviewed, checksum, count, tuple(codes),
    )


def load_source_registry(path: Path) -> dict[str, SourceMetadata]:
    """Load exactly the reviewed, provider-declared public-domain source catalog."""
    try:
        text = _read_registry_bytes(path).decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise ValueError('registry must be valid UTF-8.') from exc
    try:
        parsed = json.loads(text, parse_constant=_reject_json_constant, object_pairs_hook=_reject_duplicate_json_members)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('registry must contain valid JSON.') from exc
    except ValueError as exc:
        if str(exc) == 'registry contains a duplicate JSON key.':
            raise
        raise ValueError('registry must contain valid JSON.') from exc
    if type(parsed) is not dict or set(parsed) != _APPROVED_SOURCE_ID_SET:
        raise ValueError('registry must contain exactly the approved source IDs.')
    return {source_id: _metadata(source_id, parsed[source_id]) for source_id in _APPROVED_SOURCE_IDS}
