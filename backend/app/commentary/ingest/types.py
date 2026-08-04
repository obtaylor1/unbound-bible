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
_MAX_RAW_BODY_CHARS = 200_000
_STANDARD_HTML_TAGS = frozenset({
    'a', 'address', 'area', 'article', 'aside', 'audio', 'b', 'base', 'blockquote', 'body', 'br',
    'button', 'canvas', 'caption', 'cite', 'code', 'col', 'colgroup', 'data', 'datalist', 'dd',
    'del', 'details', 'dialog', 'div', 'dl', 'dt', 'em', 'embed', 'fieldset', 'figcaption', 'figure',
    'footer', 'form', 'frame', 'frameset', 'head', 'header', 'hgroup', 'hr', 'html', 'i', 'iframe',
    'img', 'input', 'ins', 'label', 'legend', 'li', 'link', 'main', 'map', 'mark', 'media', 'menu',
    'meta', 'meter', 'nav', 'noscript', 'object', 'ol', 'optgroup', 'option', 'output', 'p', 'picture',
    'pre', 'progress', 'q', 'script', 'section', 'select', 'slot', 'small', 'source', 'span', 'strong',
    'style', 'sub', 'summary', 'sup', 'svg', 'table', 'tbody', 'td', 'template', 'textarea', 'tfoot',
    'th', 'thead', 'time', 'title', 'tr', 'track', 'u', 'ul', 'video', 'wbr',
}) | frozenset(f'h{level}' for level in range(1, 7))


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


def _is_name_start(character: str) -> bool:
    return character.isalpha() or character in '_:'


def _is_name_character(character: str) -> bool:
    return character.isalnum() or character in '_.:-'


def _contains_commentary_markup(value: str) -> bool:
    """Scan angle tokens once, retaining comparison prose but rejecting markup forms."""
    index = 0
    length = len(value)
    while index < length:
        start = value.find('<', index)
        if start < 0:
            return False
        if start + 1 >= length:
            return False
        next_character = value[start + 1]
        if next_character in '!?':
            return True

        end = value.find('>', start + 1)
        if end < 0:
            tail = value[start + 1:].lstrip()
            name_end = 0
            while name_end < len(tail) and _is_name_character(tail[name_end]):
                name_end += 1
            return bool(name_end and tail[:name_end].lower() in _STANDARD_HTML_TAGS)

        token = value[start + 1:end].strip()
        before = value[start - 1] if start else ''
        after = value[end + 1] if end + 1 < length else ''
        if token.startswith('/') or token.endswith('/'):
            return True
        if token and _is_name_start(token[0]):
            name_end = 1
            while name_end < len(token) and _is_name_character(token[name_end]):
                name_end += 1
            name = token[:name_end].lower()
            remainder = token[name_end:]
            if name in _STANDARD_HTML_TAGS:
                return True
            if '=' in remainder or '"' in remainder or "'" in remainder:
                return True
            if not (before.isalnum() and after.isalnum()):
                return True
        index = end + 1
    return False


def normalize_body(value: object) -> str:
    """Normalize commentary prose while retaining intentional paragraphs."""
    source = _require_string('body', value)
    if len(source) > _MAX_RAW_BODY_CHARS:
        raise ValueError('body exceeds the raw input safety limit.')
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
