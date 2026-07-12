import re
from dataclasses import dataclass


BOOK_ALIASES = {
    "gen": "Genesis", "genesis": "Genesis", "ex": "Exodus", "exod": "Exodus", "exodus": "Exodus",
    "ps": "Psalms", "psalm": "Psalms", "psalms": "Psalms", "matt": "Matthew", "matthew": "Matthew",
    "jn": "John", "john": "John", "rom": "Romans", "romans": "Romans", "tob": "Tobit", "tobit": "Tobit",
    "1 cor": "1 Corinthians", "1 corinthians": "1 Corinthians", "2 cor": "2 Corinthians", "2 corinthians": "2 Corinthians",
}


@dataclass(frozen=True)
class ScriptureReference:
    book: str
    chapter: int
    verse_start: int
    verse_end: int
    translation: str | None = None

    @property
    def label(self) -> str:
        verses = str(self.verse_start) if self.verse_start == self.verse_end else f"{self.verse_start}-{self.verse_end}"
        return f"{self.book} {self.chapter}:{verses}"


REFERENCE_PATTERN = re.compile(r"\b((?:[1-3]\s*)?[A-Za-z]+)\s+(\d{1,3}):(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?(?:\s+([A-Z]{2,12}))?\b", re.IGNORECASE)


def parse_reference(text: str) -> ScriptureReference | None:
    match = REFERENCE_PATTERN.search(text)
    if not match: return None
    raw_book = re.sub(r"\s+", " ", match.group(1).strip()).casefold()
    book = BOOK_ALIASES.get(raw_book, match.group(1).strip().title())
    start, end = int(match.group(3)), int(match.group(4) or match.group(3))
    if start < 1 or end < start or end - start > 100: return None
    candidate = match.group(5).upper() if match.group(5) else None
    translation = candidate if candidate in {"KJV", "NRSV", "NIV", "ESV", "NASB", "LXX", "MT", "WEB", "ASV"} else None
    return ScriptureReference(book, int(match.group(2)), start, end, translation)
