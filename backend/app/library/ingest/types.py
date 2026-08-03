"""Immutable normalized scripture rows and their deterministic checksums."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


def _checksum(values: list[object]) -> str:
    """Hash a typed, position-preserving JSON sequence without ambiguity."""
    payload = json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return sha256(payload.encode('utf-8')).hexdigest()


def text_checksum(text: str) -> str:
    """Return the stable checksum used to find repeated normalized verse text."""
    return _checksum(['normalized-verse-text-v1', text])


def row_checksum(
    work_id: str,
    chapter: int,
    verse: int,
    text: str,
    source_locator: str | None,
) -> str:
    """Return a stable checksum for the canonical row identity and source data."""
    return _checksum([
        'normalized-verse-row-v1', work_id, chapter, verse, text, source_locator,
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

    @property
    def text_checksum(self) -> str:
        return text_checksum(self.text)

    @property
    def row_checksum(self) -> str:
        return row_checksum(
            self.work_id,
            self.chapter,
            self.verse,
            self.text,
            self.source_locator,
        )
