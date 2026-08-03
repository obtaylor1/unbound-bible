"""Normalization boundary for untrusted scripture-import rows."""

from __future__ import annotations

import re
import unicodedata

from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS, alias_target
from app.library.ingest.types import NormalizedVerse


_MARKUP_RE = re.compile(
    r'''(?isx)
    <!-- .*? -->
    | <!doctype\b [^>]* >
    | <\? .*? \?>
    | <!\[cdata\[ .*? \]\]>
    | </? \s* [a-z] [a-z0-9:._-]* (?: \s+ [^<>]*? )? \s* /? >
    ''',
)
_CANONICAL_WORK_IDS = frozenset(work.id for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS))


def _require_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f'{name} must be a string.')
    return value


def _normalize_spaces(value: str) -> str:
    """Apply NFC and turn all Unicode whitespace runs into one ordinary space."""
    return ' '.join(unicodedata.normalize('NFC', value).split())


def _contains_markup(value: str) -> bool:
    return _MARKUP_RE.search(value) is not None


def _has_control_characters(value: str) -> bool:
    return any(unicodedata.category(character) == 'Cc' for character in value)


def _resolve_work_id(source_book: str) -> str:
    if source_book in _CANONICAL_WORK_IDS:
        return source_book
    resolved = alias_target(source_book)
    if resolved in _CANONICAL_WORK_IDS:
        return resolved
    raise ValueError(f'Unknown source book: {source_book!r}.')


def _normalize_locator(source_locator: object | None) -> str | None:
    if source_locator is None:
        return None
    locator = _normalize_spaces(_require_string('source_locator', source_locator))
    if not locator:
        raise ValueError('source_locator must not be blank.')
    if _has_control_characters(locator):
        raise ValueError('source_locator must not contain control characters.')
    if _contains_markup(locator):
        raise ValueError('source_locator must not contain markup.')
    return locator


def normalize_verse(
    source_book: object,
    chapter: object,
    verse: object,
    text: object,
    source_locator: object | None = None,
) -> NormalizedVerse:
    """Validate and normalize one source row without interpreting its scripture text."""
    if type(chapter) is not int or type(verse) is not int or chapter <= 0 or verse <= 0:
        raise ValueError('chapter and verse must be positive integers.')

    cleaned_source_book = _normalize_spaces(_require_string('source_book', source_book))
    work_id = _resolve_work_id(cleaned_source_book)

    normalized_text = _normalize_spaces(_require_string('text', text))
    if not normalized_text:
        raise ValueError('text must not be empty after normalization.')
    if _contains_markup(normalized_text):
        raise ValueError('text must not contain HTML or XML markup.')

    return NormalizedVerse(
        work_id=work_id,
        source_book=cleaned_source_book,
        chapter=chapter,
        verse=verse,
        text=normalized_text,
        source_locator=_normalize_locator(source_locator),
    )
