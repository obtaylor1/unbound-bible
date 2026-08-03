"""Normalization boundary for untrusted scripture-import rows."""

from __future__ import annotations

from app.library.ingest.types import NormalizedVerse, normalize_string, resolve_source_work_id


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
    work_id = resolve_source_work_id(cleaned_source_book)

    return NormalizedVerse(
        work_id=work_id,
        source_book=cleaned_source_book,
        chapter=chapter,
        verse=verse,
        text=normalize_string('text', text),
        source_locator=_normalize_locator(source_locator),
    )
