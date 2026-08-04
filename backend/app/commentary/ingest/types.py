"""Normalized, immutable commentary records."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Literal
import unicodedata

from app.library.ingest.types import contains_markup, normalize_string, resolve_source_work_id


EntryType = Literal['book_intro', 'chapter_intro', 'verse', 'verse_range']
_ENTRY_TYPES = frozenset({'book_intro', 'chapter_intro', 'verse', 'verse_range'})
_HORIZONTAL_WHITESPACE = re.compile(r'[^\S\n]+')
_EXCESS_LINE_BREAKS = re.compile(r'\n{3,}')
_KNOWN_MARKUP_TAG = re.compile(
    r'<\s*/?\s*(?:p|br|div|span|em|strong|i|b|a|ul|ol|li|blockquote|script|style)\b[^>]*>',
    re.IGNORECASE,
)
_BALANCED_TAG = re.compile(
    r'<\s*([A-Za-z_][A-Za-z0-9_.:-]*)(?:\s+[^<>]*)?\s*>.*?</\s*\1\s*>',
    re.IGNORECASE | re.DOTALL,
)


def _require_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f'{name} must be a string.')
    return value


def _reject_controls(name: str, value: str, *, allow_line_feed: bool = False) -> None:
    for character in value:
        if unicodedata.category(character) == 'Cc' and not (allow_line_feed and character == '\n'):
            raise ValueError(f'{name} must not contain control characters.')


def _normalize_scalar(name: str, value: object, *, maximum: int, allow_empty: bool = False) -> str:
    source = _require_string(name, value)
    normalized = normalize_string(name, source)
    _reject_controls(name, source)
    if contains_markup(normalized):
        raise ValueError(f'{name} must not contain HTML or XML markup.')
    if not normalized and not allow_empty:
        raise ValueError(f'{name} must not be blank.')
    if len(normalized) > maximum:
        raise ValueError(f'{name} must be at most {maximum} characters.')
    return normalized


def _contains_commentary_markup(value: str) -> bool:
    """Detect executable/renderable markup without treating mathematical prose as tags."""
    return '<!' in value or '<?' in value or bool(
        _KNOWN_MARKUP_TAG.search(value) or _BALANCED_TAG.search(value),
    )


def normalize_body(value: object) -> str:
    """Normalize commentary prose while retaining intentional paragraphs."""
    source = _require_string('body', value)
    # ``normalize_string`` rejects lone surrogates before we reshape whitespace.
    normalized = unicodedata.normalize('NFC', source)
    normalized = normalized.replace('\u2028', '\n').replace('\u2029', '\n\n')
    if any(unicodedata.category(character) == 'Cs' for character in normalized):
        raise ValueError('body must not contain lone Unicode surrogate code points.')
    _reject_controls('body', normalized, allow_line_feed=True)
    if _contains_commentary_markup(normalized):
        raise ValueError('body must not contain HTML or XML markup.')

    lines = [_HORIZONTAL_WHITESPACE.sub(' ', line).strip() for line in normalized.split('\n')]
    body = _EXCESS_LINE_BREAKS.sub('\n\n', '\n'.join(lines)).strip()
    if not body:
        raise ValueError('body must not be blank.')
    if len(body) > 100_000:
        raise ValueError('body must be at most 100000 characters.')
    return body


def _checksum(values: list[object]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return sha256(payload.encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class NormalizedCommentaryEntry:
    """One validated commentary entry with a deterministic source checksum."""

    work_id: str
    chapter: int | None
    verse_start: int | None
    verse_end: int | None
    entry_type: EntryType
    heading: str | None
    body: str
    source_locator: str
    position: int

    def __post_init__(self) -> None:
        work_id = _normalize_scalar('work_id', self.work_id, maximum=255)
        if resolve_source_work_id(work_id) != work_id:
            raise ValueError('work_id must identify a known canonical work.')
        object.__setattr__(self, 'work_id', work_id)

        if type(self.entry_type) is not str or self.entry_type not in _ENTRY_TYPES:
            raise ValueError('entry_type must be book_intro, chapter_intro, verse, or verse_range.')
        if type(self.position) is not int or self.position < 0:
            raise ValueError('position must be a nonnegative integer.')
        self._validate_coordinates()

        if self.heading is not None:
            object.__setattr__(
                self, 'heading', _normalize_scalar('heading', self.heading, maximum=500),
            )
        object.__setattr__(self, 'body', normalize_body(self.body))
        object.__setattr__(
            self, 'source_locator', _normalize_scalar('source_locator', self.source_locator, maximum=2048),
        )

    def _validate_coordinates(self) -> None:
        chapter, verse_start, verse_end = self.chapter, self.verse_start, self.verse_end
        for name, value in (
            ('chapter', chapter), ('verse_start', verse_start), ('verse_end', verse_end),
        ):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f'{name} must be a positive integer when present.')

        if self.entry_type == 'book_intro':
            valid = chapter is None and verse_start is None and verse_end is None
        elif self.entry_type == 'chapter_intro':
            valid = chapter is not None and verse_start is None and verse_end is None
        else:
            valid = chapter is not None and verse_start is not None and verse_end is not None
            if valid and verse_end < verse_start:
                valid = False
            if valid and self.entry_type == 'verse' and verse_start != verse_end:
                valid = False
            if valid and self.entry_type == 'verse_range' and verse_start == verse_end:
                valid = False
        if not valid:
            raise ValueError(f'Coordinates are invalid for entry_type {self.entry_type!r}.')

    @property
    def row_checksum(self) -> str:
        return _checksum([
            'commentary-row-v1', self.work_id, self.chapter, self.verse_start, self.verse_end,
            self.entry_type, self.heading, self.body, self.source_locator, self.position,
        ])
