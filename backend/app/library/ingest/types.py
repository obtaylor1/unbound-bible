"""Immutable normalized scripture rows and their deterministic checksums."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import unicodedata

from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS


_KNOWN_WORK_IDS = frozenset(work.id for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS))
_XML_NAME_START_RANGES = (
    (0x00C0, 0x00D6), (0x00D8, 0x00F6), (0x00F8, 0x02FF),
    (0x0370, 0x037D), (0x037F, 0x1FFF), (0x200C, 0x200D),
    (0x2070, 0x218F), (0x2C00, 0x2FEF), (0x3001, 0xD7FF),
    (0xF900, 0xFDCF), (0xFDF0, 0xFFFD), (0x10000, 0xEFFFF),
)


def _require_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f'{name} must be a string.')
    return value


def _reject_surrogates(name: str, value: str) -> None:
    if any(unicodedata.category(character) == 'Cs' for character in value):
        raise ValueError(f'{name} must not contain lone Unicode surrogate code points.')


def normalize_string(name: str, value: object) -> str:
    """Strictly normalize one import scalar without rewriting semantic content."""
    source = _require_string(name, value)
    _reject_surrogates(name, source)
    return ' '.join(unicodedata.normalize('NFC', source).split())


def _is_xml_name_start(character: str) -> bool:
    """Return whether one character is an XML 1.0 ``NameStartChar``."""
    if character in ':_' or 'A' <= character <= 'Z' or 'a' <= character <= 'z':
        return True
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in _XML_NAME_START_RANGES)


def contains_markup(value: str) -> bool:
    """Detect tag/declaration starts in one bounded reverse scan.

    A tag-like start only counts when its ``<`` is immediately followed by an
    XML name start (or ``/`` plus one) and some ``>`` occurs later.  XML
    declarations and processing instructions are unsafe from their opener,
    even when truncated.
    """
    closing_angle_to_right = False
    for index in range(len(value) - 1, -1, -1):
        character = value[index]
        if character == '>':
            closing_angle_to_right = True
            continue
        if character != '<' or index + 1 >= len(value):
            continue

        name_index = index + 1
        next_character = value[name_index]
        if next_character in '!?':
            return True
        if next_character == '/':
            name_index += 1
            if name_index >= len(value):
                continue

        if _is_xml_name_start(value[name_index]) and closing_angle_to_right:
            return True
    return False


def _validate_normalized_string(name: str, value: object) -> str:
    source = _require_string(name, value)
    normalized = normalize_string(name, source)
    if source != normalized:
        raise ValueError(f'{name} must already be NFC-normalized with collapsed whitespace.')
    if not source:
        raise ValueError(f'{name} must not be empty after normalization.')

    for character in source:
        if unicodedata.category(character) == 'Cc':
            raise ValueError(f'{name} must not contain control characters.')
    if contains_markup(source):
        raise ValueError(f'{name} must not contain HTML or XML markup.')
    return source


def _checksum(values: list[object]) -> str:
    """Hash a typed, position-preserving JSON sequence without ambiguity."""
    payload = json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return sha256(payload.encode('utf-8')).hexdigest()


def text_checksum(text: str) -> str:
    """Return the stable checksum used to find repeated normalized verse text."""
    return _checksum(['normalized-verse-text-v1', text])


def row_checksum(
    work_id: str,
    source_book: str,
    chapter: int,
    verse: int,
    text: str,
    source_locator: str | None,
) -> str:
    """Return a stable checksum for the canonical row identity and source data."""
    return _checksum([
        'normalized-verse-row-v2', work_id, source_book, chapter, verse, text, source_locator,
    ])


@dataclass(frozen=True, slots=True)
class NormalizedVerse:
    """A fully normalized source verse ready for later staging."""

    work_id: str
    source_book: str
    chapter: int
    verse: int
    text: str
    source_locator: str | None = None

    def __post_init__(self) -> None:
        if type(self.work_id) is not str or self.work_id not in _KNOWN_WORK_IDS:
            raise ValueError('work_id must identify a known canonical work.')
        if (
            type(self.chapter) is not int
            or type(self.verse) is not int
            or self.chapter <= 0
            or self.verse <= 0
        ):
            raise ValueError('chapter and verse must be positive integers.')

        _validate_normalized_string('source_book', self.source_book)
        _validate_normalized_string('text', self.text)
        if self.source_locator is not None:
            _validate_normalized_string('source_locator', self.source_locator)

    @property
    def text_checksum(self) -> str:
        return text_checksum(self.text)

    @property
    def row_checksum(self) -> str:
        return row_checksum(
            self.work_id,
            self.source_book,
            self.chapter,
            self.verse,
            self.text,
            self.source_locator,
        )
