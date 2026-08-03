"""Deterministic, publication-gating validation for normalized scripture rows."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
import re
import unicodedata

from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS
from app.library.ingest.manifest import ExpectedCoverage
from app.library.ingest.types import NormalizedVerse, contains_markup, normalize_string


_CANONICAL_WORKS = (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS)
_KNOWN_WORK_IDS = frozenset(work.id for work in _CANONICAL_WORKS)
_WORK_ORDER = {work.id: index for index, work in enumerate(_CANONICAL_WORKS)}
_CODE = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
_WARNING_CODE = re.compile(r'^[a-z][a-z0-9_ -]{0,63}$')
_PLACEHOLDER = re.compile(
    r'\b(?:awaiting|sample placeholder|text unavailable|no text available|not yet added|to be added|tbd|lorem ipsum)\b',
    re.IGNORECASE,
)
_BRACKETED_DESCRIPTION = re.compile(r'^\[[^\]]*\b(?:book|chapter)\b[^\]]*\]$', re.IGNORECASE)
_WARNING_MESSAGES = {
    'related_recension': 'The source is a related recension and requires reviewer context.',
}


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """One stable validation outcome attached to an optional scripture position."""

    severity: str
    code: str
    message: str
    work_id: str | None = None
    chapter: int | None = None
    verse: int | None = None

    def __post_init__(self) -> None:
        if self.severity not in {'error', 'warning'}:
            raise ValueError('severity must be error or warning.')
        if type(self.code) is not str or not _CODE.fullmatch(self.code):
            raise ValueError('code must be a conservative nonblank identifier.')
        if type(self.message) is not str or not self.message.strip():
            raise ValueError('message must be a nonblank string.')
        if self.work_id is not None and (type(self.work_id) is not str or not self.work_id.strip()):
            raise ValueError('work_id must be a nonblank string when provided.')
        if self.chapter is not None:
            if self.work_id is None:
                raise ValueError('chapter requires work_id.')
            if type(self.chapter) is not int or self.chapter <= 0:
                raise ValueError('chapter must be a positive integer.')
        if self.verse is not None:
            if self.chapter is None:
                raise ValueError('verse requires chapter and work_id.')
            if type(self.verse) is not int or self.verse <= 0:
                raise ValueError('verse must be a positive integer.')


def _finding_sort_key(finding: ValidationFinding) -> tuple[object, ...]:
    return (
        0 if finding.severity == 'error' else 1,
        _WORK_ORDER.get(finding.work_id, len(_WORK_ORDER)),
        finding.work_id or '',
        finding.chapter if finding.chapter is not None else -1,
        finding.verse if finding.verse is not None else -1,
        finding.code,
        finding.message,
    )


def _position_sort_key(position: tuple[str, int, int]) -> tuple[object, ...]:
    work_id, chapter, verse = position
    return (_WORK_ORDER.get(work_id, len(_WORK_ORDER)), work_id, chapter, verse)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """An immutable, deterministically ordered edition-validation result."""

    findings: tuple[ValidationFinding, ...]

    def __post_init__(self) -> None:
        if type(self.findings) is not tuple:
            raise ValueError('findings must be a tuple.')
        if not all(isinstance(finding, ValidationFinding) for finding in self.findings):
            raise ValueError('findings must contain ValidationFinding values.')
        object.__setattr__(self, 'findings', tuple(sorted(set(self.findings), key=_finding_sort_key)))

    @property
    def errors(self) -> tuple[ValidationFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == 'error')

    @property
    def warnings(self) -> tuple[ValidationFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == 'warning')

    @property
    def publishable(self) -> bool:
        return not self.errors

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


@dataclass(frozen=True, slots=True)
class _Coverage:
    chapters: int
    verse_counts: dict[int, int]


def _as_positive_int(name: str, value: object, maximum: int) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError(f'expected coverage {name} must be a positive integer.')
    return value


def _normalize_coverage(expected_works: object) -> dict[str, _Coverage]:
    if type(expected_works) is not dict or not expected_works:
        raise ValueError('expected coverage must be a nonempty dictionary keyed by canonical work ID.')

    normalized: dict[str, _Coverage] = {}
    for work_id, raw_coverage in expected_works.items():
        if type(work_id) is not str or work_id not in _KNOWN_WORK_IDS:
            raise ValueError(f'expected coverage has invalid work ID: {work_id!r}.')
        if work_id in normalized:
            raise ValueError(f'expected coverage repeats work ID: {work_id!r}.')

        if isinstance(raw_coverage, ExpectedCoverage):
            chapters = raw_coverage.chapters
            raw_counts = raw_coverage.verse_counts
        elif type(raw_coverage) is dict:
            if set(raw_coverage) - {'chapters', 'verse_counts'} or 'chapters' not in raw_coverage:
                raise ValueError(f'expected coverage for {work_id!r} has invalid fields.')
            chapters = raw_coverage['chapters']
            raw_counts = raw_coverage.get('verse_counts', {})
        else:
            raise ValueError(f'expected coverage for {work_id!r} must be an ExpectedCoverage or dictionary.')

        chapter_count = _as_positive_int('chapters', chapters, 200)
        if type(raw_counts) is not dict:
            raise ValueError(f'expected coverage verse_counts for {work_id!r} must be a dictionary.')
        counts: dict[int, int] = {}
        for chapter_key, verse_count in raw_counts.items():
            if type(chapter_key) is not str or not re.fullmatch(r'[1-9][0-9]*', chapter_key):
                raise ValueError(f'expected coverage verse_counts for {work_id!r} has invalid chapter key.')
            chapter = int(chapter_key)
            if chapter > chapter_count:
                raise ValueError(f'expected coverage verse_counts for {work_id!r} exceeds chapters.')
            counts[chapter] = _as_positive_int('verse_counts value', verse_count, 1000)
        normalized[work_id] = _Coverage(chapter_count, counts)
    return normalized


def _normalize_warning(warning: object) -> str:
    if type(warning) is not str:
        raise ValueError('warning must be a string identifier.')
    cleaned = warning.strip().casefold().replace('-', '_').replace(' ', '_')
    if not cleaned or not _WARNING_CODE.fullmatch(warning.strip().casefold()) or not _CODE.fullmatch(cleaned):
        raise ValueError('warning must be a conservative nonblank identifier.')
    return cleaned


def _is_unsafe_text(text: object) -> bool:
    if type(text) is not str:
        return True
    try:
        normalized = normalize_string('text', text)
    except ValueError:
        return True
    return (
        not normalized
        or normalized != text
        or contains_markup(text)
        or any(unicodedata.category(character) in {'Cc', 'Cs'} for character in text)
    )


def _is_placeholder(text: str) -> bool:
    return bool(_PLACEHOLDER.search(text) or _BRACKETED_DESCRIPTION.fullmatch(text.strip()))


def _safe_position(row: NormalizedVerse) -> tuple[str, int, int] | None:
    if type(row.work_id) is not str or row.work_id not in _KNOWN_WORK_IDS:
        return None
    if type(row.chapter) is not int or row.chapter <= 0:
        return None
    if type(row.verse) is not int or row.verse <= 0:
        return None
    return row.work_id, row.chapter, row.verse


def _finding_location(row: NormalizedVerse) -> tuple[str | None, int | None, int | None]:
    work_id = row.work_id if type(row.work_id) is str and row.work_id.strip() else None
    chapter = row.chapter if work_id is not None and type(row.chapter) is int and row.chapter > 0 else None
    verse = row.verse if chapter is not None and type(row.verse) is int and row.verse > 0 else None
    return work_id, chapter, verse


def _metadata_is_safe(row: NormalizedVerse) -> bool:
    """Re-run construction invariants without touching checksum properties."""
    try:
        NormalizedVerse(
            work_id=row.work_id,
            source_book=row.source_book,
            chapter=row.chapter,
            verse=row.verse,
            text=row.text,
            source_locator=row.source_locator,
        )
    except (TypeError, ValueError):
        return False
    return True


def validate_edition(
    verses: Iterable[NormalizedVerse],
    expected_works: object,
    warnings: Iterable[str] = (),
) -> ValidationResult:
    """Validate one normalized edition without mutating or re-iterating its rows."""
    expected = _normalize_coverage(expected_works)
    rows = tuple(verses)
    if not all(isinstance(row, NormalizedVerse) for row in rows):
        raise ValueError('verses must contain only NormalizedVerse values.')
    try:
        caller_warnings = tuple(warnings)
    except TypeError as error:
        raise ValueError('warnings must be an iterable of string identifiers.') from error

    findings: list[ValidationFinding] = []
    for code in sorted({_normalize_warning(warning) for warning in caller_warnings}):
        findings.append(ValidationFinding('warning', code, _WARNING_MESSAGES.get(code, f'Caller warning: {code}.')))

    checked_rows: list[tuple[NormalizedVerse, tuple[str, int, int] | None, bool]] = []
    for row in rows:
        position = _safe_position(row)
        if position is None:
            findings.append(ValidationFinding(
                'error', 'unsafe_row', 'Normalized verse identity or source scalars are unsafe.',
                *_finding_location(row),
            ))
            checked_rows.append((row, None, False))
            continue

        if _is_unsafe_text(row.text):
            findings.append(ValidationFinding(
                'error', 'unsafe_text', 'Verse text is empty, non-normalized, or unsafe.',
                *position,
            ))
            checked_rows.append((row, position, False))
            continue

        metadata_safe = _metadata_is_safe(row)
        if not metadata_safe:
            findings.append(ValidationFinding(
                'error', 'unsafe_row', 'Normalized verse identity or source scalars are unsafe.',
                *position,
            ))
        elif _is_placeholder(row.text):
            findings.append(ValidationFinding(
                'error', 'placeholder_text', 'Verse text is a source placeholder.', *position,
            ))
        checked_rows.append((row, position, metadata_safe))

    positions: dict[tuple[str, int, int], list[NormalizedVerse]] = defaultdict(list)
    observed: dict[str, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    text_positions: dict[str, set[tuple[str, int, int]]] = defaultdict(set)
    for row, position, checksum_safe in checked_rows:
        if position is None:
            continue
        positions[position].append(row)
        work_id, chapter, verse = position
        observed[work_id][chapter].add(verse)
        if checksum_safe:
            text_positions[row.text_checksum].add(position)

    for position, same_position_rows in positions.items():
        if len(same_position_rows) > 1:
            findings.append(ValidationFinding('error', 'duplicate_verse', 'More than one row has this verse identity.', *position))

    for checksum, checksum_positions in text_positions.items():
        if len(checksum_positions) > 1:
            work_id, chapter, verse = min(checksum_positions, key=_position_sort_key)
            findings.append(ValidationFinding(
                'warning', 'repeated_text_checksum',
                f'Identical normalized text checksum occurs at {len(checksum_positions)} positions: {checksum}.',
                work_id, chapter, verse,
            ))

    for work_id, coverage in expected.items():
        work_observed = observed.get(work_id, {})
        if not work_observed:
            findings.append(ValidationFinding('error', 'missing_work', 'Expected work has no observed verses.', work_id))
            continue
        for chapter in range(1, coverage.chapters + 1):
            verses_in_chapter = work_observed.get(chapter)
            if not verses_in_chapter:
                findings.append(ValidationFinding('error', 'missing_chapter', 'Expected chapter has no observed verses.', work_id, chapter))
                continue
            expected_verse_count = coverage.verse_counts.get(chapter)
            maximum = expected_verse_count if expected_verse_count is not None else max(verses_in_chapter)
            for verse in range(1, maximum + 1):
                if verse not in verses_in_chapter:
                    findings.append(ValidationFinding('error', 'missing_verse', 'Expected verse is not present.', work_id, chapter, verse))

    for work_id, chapters in observed.items():
        coverage = expected.get(work_id)
        for chapter, observed_verses in chapters.items():
            for verse in observed_verses:
                if coverage is None:
                    findings.append(ValidationFinding('error', 'observed_coverage_mismatch', 'Observed verse belongs to an unexpected work.', work_id, chapter, verse))
                elif chapter > coverage.chapters:
                    findings.append(ValidationFinding('error', 'observed_coverage_mismatch', 'Observed verse is beyond declared chapters.', work_id, chapter, verse))
                elif (expected_count := coverage.verse_counts.get(chapter)) is not None and verse > expected_count:
                    findings.append(ValidationFinding('error', 'observed_coverage_mismatch', 'Observed verse is beyond declared verse count.', work_id, chapter, verse))

    return ValidationResult(tuple(findings))
