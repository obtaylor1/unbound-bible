"""Normalization boundary for untrusted scripture-import rows."""

from __future__ import annotations

from app.library.canon import SUPPLEMENTAL_LIBRARY_WORKS, WORKS, alias_target
from app.library.ingest.types import NormalizedVerse, normalize_string


_CANONICAL_WORK_IDS = frozenset(work.id for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS))


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
    return normalize_string('source_locator', source_locator)


def normalize_verse(
    source_book: object,
    chapter: object,
    verse: object,
    text: object,
    source_locator: object | None = None,
) -> NormalizedVerse:
    """Validate and normalize one source row without interpreting its scripture text."""
    cleaned_source_book = normalize_string('source_book', source_book)
    work_id = _resolve_work_id(cleaned_source_book)

    return NormalizedVerse(
        work_id=work_id,
        source_book=cleaned_source_book,
        chapter=chapter,
        verse=verse,
        text=normalize_string('text', text),
        source_locator=_normalize_locator(source_locator),
    )
