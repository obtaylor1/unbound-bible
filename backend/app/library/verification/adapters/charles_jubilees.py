"""Verified R. H. Charles Jubilees transcription and historical evidence adapter."""

from __future__ import annotations

from collections import defaultdict
import difflib
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.library.verification.compare import compare_work
from app.library.verification.report import report_json_bytes, report_sha256, write_report_pair
from app.library.verification.registry import SourceDefinition
from app.library.verification.types import ComparisonRules, SourceVerse


PARSER_VERSION = "charles-jubilees/1"
SOURCE_ARTIFACT_SHA256 = (
    "e48d840d060a64cfdee1c7cec640770fdf1c3f2daf76c84383163ce9126dd54a"
)
SOURCE_ARTIFACT_SIZE = 606_449
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
CURRENT_MEMBER = "data/jub.json"
REVIEWED_FINAL_PUBLICATION_SHA256 = (
    "238bc987c8033f73fee8ffd0dd7401edb076b596c5e35afab3a7a4f3e8eb4693"
)
HISTORICAL_LOCK_FILENAME = "rh-charles-jubilees-1902-historical-artifacts.lock.json"
HISTORICAL_EVIDENCE_FILENAME = "rh-charles-jubilees-1902-historical-evidence.json"
VISUAL_REVIEW_FILENAME = "rh-charles-jubilees-1902-visual-review.json"
VISUAL_REVIEW_SHA256 = (
    "87b4e81fdb6793b97dccedff60c319c5dff5cd796205b2af81d246a215979597"
)
EXPECTED_COUNTS = (
    29, 33, 35, 33, 32, 38, 39, 30, 15, 36,
    24, 31, 29, 24, 34, 31, 18, 19, 31, 13,
    26, 30, 32, 33, 23, 35, 27, 30, 20, 26,
    32, 34, 23, 21, 27, 24, 25, 24, 18, 13,
    28, 25, 24, 34, 16, 16, 12, 19, 23, 13,
)
MARKER_REPAIRS = (
    (4, 2, "(99-105 A.M.) 2.", "2. (99-105 A.M.)"),
    (4, 13, "(309-315 A.M.) 13.", "13. (309-315 A.M.)"),
    (6, 15, "15 And He gave", "15. And He gave"),
    (9, 9, "9 And for Madai", "9. And for Madai"),
    (13, 13, "13 And it came", "13. And it came"),
    (22, 21, "21, For, owing", "21. For, owing"),
    (22, 26, "26: And the two", "26. And the two"),
)

_START_ANCHOR = "_Toc233264794"
_AM_NOTE = re.compile(r"\([^()]{0,80}\bA\.?\s*M\.?[^()]{0,80}\)")
_CHAPTER = re.compile(r"^(V1|[IVXLCDM]+)\.\s*")
_POSITION = re.compile(r"(?<!\S)(\d{1,2})\s*\.\s+")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _secure_read(path: Path, *, maximum: int, context: str) -> bytes:
    path = Path(path)
    try:
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise ValueError(f"{context} is missing or unsafe.") from error
    try:
        opened = os.fstat(descriptor)
        identity = (before.st_dev, before.st_ino, before.st_size)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or identity != (opened.st_dev, opened.st_ino, opened.st_size)
            or not 0 < opened.st_size <= maximum
        ):
            raise ValueError(f"{context} changed before its secure snapshot.")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"{context} changed during its secure snapshot.")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ValueError(f"{context} exceeded its secure snapshot size.")
        after_fd, after_path = os.fstat(descriptor), path.lstat()
        if (
            identity != (after_fd.st_dev, after_fd.st_ino, after_fd.st_size)
            or identity != (after_path.st_dev, after_path.st_ino, after_path.st_size)
            or before.st_mtime_ns != after_fd.st_mtime_ns
            or before.st_mtime_ns != after_path.st_mtime_ns
        ):
            raise ValueError(f"{context} changed during its secure snapshot.")
        return b"".join(chunks)
    except OSError as error:
        raise ValueError(f"{context} changed during its secure snapshot.") from error
    finally:
        os.close(descriptor)


def _validate_definition(definition: SourceDefinition) -> None:
    if type(definition) is not SourceDefinition:
        raise ValueError("definition must be a SourceDefinition.")
    if definition.adapter_id != "charles_jubilees":
        raise ValueError("definition must select the Charles Jubilees adapter.")
    if definition.expected_work_ids != ("jubilees",):
        raise ValueError("definition must contain exactly Jubilees.")


class _PublicationHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.started = False
        self.finished = False
        self.in_paragraph = False
        self.suppressed = 0
        self.parts: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("name") == _START_ANCHOR:
            self.started = True
        if tag == "footer" and "footnotes" in values.get("class", "").split():
            self.finished = True
            self.in_paragraph = False
        if not self.started or self.finished:
            return
        if tag == "p":
            if self.in_paragraph:
                raise ValueError("authorized reprint contains nested paragraphs.")
            self.in_paragraph = True
            self.parts = []
        if tag in {"sup", "script", "style"} or (
            tag == "a"
            and (
                values.get("name", "").startswith("_ftnref")
                or values.get("href", "").startswith("#_ftn")
            )
        ):
            self.suppressed += 1
        if tag == "br" and self.in_paragraph and not self.suppressed:
            self.parts.append("\0")

    def handle_endtag(self, tag: str) -> None:
        if self.suppressed and tag in {"a", "sup", "script", "style"}:
            self.suppressed -= 1
        if tag == "p" and self.in_paragraph:
            paragraph = "".join(self.parts)
            paragraph = re.sub(r"(?<=\w)-\0(?=[a-z])", "", paragraph)
            paragraph = paragraph.replace("\0", " ")
            self.paragraphs.append(
                unicodedata.normalize("NFC", " ".join(paragraph.split()))
            )
            self.parts = []
            self.in_paragraph = False

    def handle_data(self, data: str) -> None:
        if self.started and not self.finished and self.in_paragraph and not self.suppressed:
            self.parts.append(data)


def _roman_number(value: str) -> int:
    value = value.replace("1", "I")  # reviewed V1 OCR shape on the chapter VI heading
    result = previous = 0
    for character in reversed(value):
        number = _ROMAN_VALUES[character]
        result += -number if number < previous else number
        previous = max(previous, number)
    return result


def _clean_paragraphs(snapshot: bytes) -> list[str]:
    try:
        text = snapshot.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("authorized reprint must be strict UTF-8 encoding.") from error
    if text.startswith("\ufeff"):
        raise ValueError("authorized reprint must be BOM-free UTF-8.")
    if text.count("\r\n") != text.count("\n") or "\r" in text.replace("\r\n", ""):
        raise ValueError("authorized reprint newline identity changed.")
    identity = (
        "<title>The Book of Jubilees by R. H. Charles - Read Online for free at Global Grey ebooks</title>",
        '<h1 class="book-title">The Book of Jubilees</h1>',
        '<p class="book-byline">by <a href="https://www.globalgreyebooks.com/r-h-charles-books.html"><u>R. H. Charles</u></a></p>',
        "permission to reprint here the translation of",
        "published in 1902",
        "Charles’s&#xa0;<em>Jubilees</em>&#xa0;=&#xa0;<em>The Book of Jubilees translated from the Ethiopic Text</em>, by R. H. Charles, D.D. (London, 1902).",
    )
    if any(text.count(marker) != 1 for marker in identity):
        raise ValueError("authorized reprint edition identity is invalid.")
    parser = _PublicationHtml()
    try:
        parser.feed(text)
        parser.close()
    except (AssertionError, TypeError) as error:
        raise ValueError("authorized reprint HTML structure is invalid.") from error
    if not parser.started or not parser.finished or parser.in_paragraph:
        raise ValueError("authorized reprint story/footer boundaries are invalid.")
    paragraphs = [value for value in parser.paragraphs if value]
    repaired: set[tuple[int, int]] = set()
    for index, paragraph in enumerate(paragraphs):
        for chapter, verse, old, new in MARKER_REPAIRS:
            if old in paragraph:
                if paragraph.count(old) != 1 or (chapter, verse) in repaired:
                    raise ValueError("authorized reprint marker repair identity is ambiguous.")
                paragraphs[index] = paragraph.replace(old, new)
                repaired.add((chapter, verse))
                paragraph = paragraphs[index]
    if repaired != {(chapter, verse) for chapter, verse, *_ in MARKER_REPAIRS}:
        raise ValueError("authorized reprint marker repair inventory changed.")
    return paragraphs


def _parse_snapshot(snapshot: bytes, definition: SourceDefinition) -> tuple[SourceVerse, ...]:
    _validate_definition(definition)
    paragraphs = _clean_paragraphs(snapshot)
    values: dict[tuple[int, int], str] = {}
    current: tuple[int, int] | None = None
    chapter = 1
    seen_chapters: list[int] = []
    started = False
    for original in paragraphs:
        if original.startswith("2450 A.M."):
            continue
        if original in {
            "Herewith is completed the account of the division of the days.",
            "THE END", "↑ Back to top",
        }:
            continue
        text = _AM_NOTE.sub("", original)
        text = " ".join(text.split()).strip()
        chapter_match = _CHAPTER.match(text)
        if chapter_match is not None:
            chapter = _roman_number(chapter_match.group(1))
            if chapter != len(seen_chapters) + 2:
                raise ValueError("authorized reprint chapter sequence is invalid.")
            seen_chapters.append(chapter)
            text = text[chapter_match.end():].strip()
            current = (chapter, 1)
            values[current] = ""
            started = True
        elif not started:
            marker = _POSITION.match(text)
            if marker is None or int(marker.group(1)) != 1:
                continue
            started = True
            current = (1, 1)
        matches = list(_POSITION.finditer(text))
        if current is not None and current in values and chapter_match is not None:
            first_end = matches[0].start() if matches else len(text)
            values[current] = text[:first_end].strip()
        elif matches and matches[0].start() == 0:
            pass
        elif current is not None and not matches:
            values[current] = " ".join((values[current], text)).strip()
            continue
        elif matches and matches[0].start() != 0:
            raise ValueError("authorized reprint contains an unexpected embedded position.")
        for index, match in enumerate(matches):
            verse = int(match.group(1))
            if chapter_match is not None and verse == 1:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            position = (chapter, verse)
            if position in values:
                raise ValueError("authorized reprint contains a duplicate position.")
            values[position] = text[match.end():end].strip()
            current = position
    if seen_chapters != list(range(2, 51)):
        raise ValueError("authorized reprint must contain exactly 50 ordered chapters.")
    expected = {
        (chapter_number, verse)
        for chapter_number, count in enumerate(EXPECTED_COUNTS, 1)
        for verse in range(1, count + 1)
    }
    if set(values) != expected or len(values) != 1307:
        missing = sorted(expected - set(values))
        extra = sorted(set(values) - expected)
        raise ValueError(
            "authorized reprint numbered position inventory is invalid "
            f"({len(values)} parsed; missing={missing[:12]!r}; extra={extra[:12]!r})."
        )
    if any(not value for value in values.values()):
        raise ValueError("authorized reprint contains a blank scripture position.")
    forbidden = ("Editors’ Preface", "Footnotes", "THE BOOK OF JUBILEES", "Herewith is completed")
    if any(marker in value for value in values.values() for marker in forbidden):
        raise ValueError("authorized reprint editorial material leaked into scripture.")
    return tuple(
        SourceVerse("jubilees", chapter_number, verse, values[(chapter_number, verse)])
        for chapter_number, count in enumerate(EXPECTED_COUNTS, 1)
        for verse in range(1, count + 1)
    )


def parse_charles_jubilees(
    path: Path, definition: SourceDefinition, *, expected_sha256: str | None = None,
) -> tuple[SourceVerse, ...]:
    """Parse the exact 1,307 Charles-numbered positions from the locked reprint."""
    _validate_definition(definition)
    snapshot = _secure_read(
        path, maximum=min(definition.max_artifact_bytes, MAX_ARTIFACT_BYTES),
        context="Charles Jubilees authorized-reprint artifact",
    )
    if expected_sha256 is not None and sha256(snapshot).hexdigest() != expected_sha256:
        raise ValueError("Charles Jubilees artifact snapshot does not match its lock checksum.")
    return _parse_snapshot(snapshot, definition)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


_HISTORICAL_SAMPLES = (
    ("beginning", 1, 1, 100),
    ("beginning", 8, 15, 169),
    ("beginning", 16, 31, 216),
    ("middle", 17, 1, 217),
    ("middle", 25, 12, 256),
    ("middle", 33, 23, 298),
    ("end", 34, 1, 298),
    ("end", 42, 13, 331),
    ("end", 50, 13, 359),
)

_REPAIR_REVIEW_PAGES = (
    (4, 2, 128), (4, 13, 131), (6, 15, 149), (9, 9, 174),
    (13, 13, 197), (22, 21, 239), (22, 26, 240),
)
_CROP_FIELDS = {
    "anchor_size", "crop_rgb_sha256", "djvu_object_index", "ocr_bbox",
    "ocr_canvas", "ocr_token_end", "ocr_token_start", "pdf_page",
    "pixel_margin", "render_bbox", "render_canvas", "scan_leaf",
    "source_text_sha256", "token_margin",
}


def _review_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z]+", value.lower()))


def _visual_ocr_pages(snapshot: bytes) -> tuple[tuple[int, int, tuple[tuple[str, tuple[int, ...]], ...]], ...]:
    try:
        root = ET.fromstring(snapshot)
    except ET.ParseError as error:
        raise ValueError("Charles Jubilees visual review OCR XML is invalid.") from error
    objects = root.findall(".//OBJECT")
    if len(objects) != 380:
        raise ValueError("Charles Jubilees visual review OCR page inventory changed.")
    pages = []
    word_count = 0
    for page_number, item in enumerate(objects, 1):
        parameter = item.find("PARAM")
        expected_name = f"bookofjubileesor00char_{page_number:04d}.djvu"
        if (
            parameter is None or parameter.get("name") != "PAGE"
            or parameter.get("value") != expected_name
        ):
            raise ValueError("Charles Jubilees visual review OCR page mapping changed.")
        try:
            width, height = int(item.get("width", "")), int(item.get("height", ""))
        except ValueError as error:
            raise ValueError("Charles Jubilees visual review OCR canvas is invalid.") from error
        if not 1000 <= width <= 5000 or not 1000 <= height <= 6000:
            raise ValueError("Charles Jubilees visual review OCR canvas is out of bounds.")
        records = []
        for word in item.findall(".//WORD"):
            tokens = _review_tokens(word.text or "")
            if len(tokens) != 1:
                continue
            try:
                coordinates = tuple(int(value) for value in word.get("coords", "").split(","))
            except ValueError as error:
                raise ValueError("Charles Jubilees visual review OCR coordinates are invalid.") from error
            if (
                len(coordinates) != 4
                or any(value < 0 for value in coordinates)
                or coordinates[0] >= coordinates[2]
                or min(coordinates[1], coordinates[3]) >= max(coordinates[1], coordinates[3])
            ):
                raise ValueError("Charles Jubilees visual review OCR coordinates are invalid.")
            records.append((tokens[0], coordinates))
            word_count += 1
            if word_count > 200_000:
                raise ValueError("Charles Jubilees visual review OCR word bound exceeded.")
        pages.append((width, height, tuple(records)))
    return tuple(pages)


def _visual_scan_mapping(snapshot: bytes) -> tuple[int, ...]:
    try:
        root = ET.fromstring(snapshot)
    except ET.ParseError as error:
        raise ValueError("Charles Jubilees visual review scandata is invalid.") from error
    pages = root.findall(".//pageData/page")
    if len(pages) != 386 or root.findtext(".//leafCount") != "386":
        raise ValueError("Charles Jubilees visual review scandata inventory changed.")
    accessible = []
    for expected_leaf, page in enumerate(pages):
        if page.get("leafNum") != str(expected_leaf):
            raise ValueError("Charles Jubilees visual review scandata leaf order changed.")
        if page.findtext("addToAccessFormats", "true") != "false":
            accessible.append(expected_leaf)
    if len(accessible) != 380 or tuple(accessible) != tuple(range(1, 381)):
        raise ValueError("Charles Jubilees visual review PDF/scan page mapping changed.")
    return tuple(accessible)


def _derive_visual_crop(
    source_text: str,
    page: tuple[int, int, tuple[tuple[str, tuple[int, ...]], ...]],
) -> dict[str, object]:
    width, height, records = page
    source_tokens = _review_tokens(source_text)
    page_tokens = tuple(record[0] for record in records)
    blocks = difflib.SequenceMatcher(
        None, source_tokens, page_tokens, autojunk=False,
    ).get_matching_blocks()
    longest = max(blocks, key=lambda block: block.size)
    if longest.size < 8:
        raise ValueError("Charles Jubilees visual review has no stable OCR anchor.")
    token_margin = len(source_tokens) + 8
    first = max(0, longest.b - token_margin)
    last = min(len(records), longest.b + longest.size + token_margin)
    coordinates = [record[1] for record in records[first:last]]
    ocr_bbox = [
        min(item[0] for item in coordinates),
        min(min(item[1], item[3]) for item in coordinates),
        max(item[2] for item in coordinates),
        max(max(item[1], item[3]) for item in coordinates),
    ]
    render_width, render_height = 1275, 1650
    render_bbox = [
        max(0, math.floor(ocr_bbox[0] * render_width / width) - 24),
        max(0, math.floor(ocr_bbox[1] * render_height / height) - 24),
        min(render_width, math.ceil(ocr_bbox[2] * render_width / width) + 24),
        min(render_height, math.ceil(ocr_bbox[3] * render_height / height) + 24),
    ]
    return {
        "anchor_size": longest.size,
        "ocr_bbox": ocr_bbox,
        "ocr_canvas": [width, height],
        "ocr_token_end": last,
        "ocr_token_start": first,
        "pixel_margin": 24,
        "render_bbox": render_bbox,
        "render_canvas": [render_width, render_height],
        "source_text_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
        "token_margin": token_margin,
    }


def _validate_visual_crop(
    crop: object, *, chapter: int, verse: int, expected_page: int,
    rows: dict[tuple[int, int], str], pages, scan_mapping, full_page: bool = False,
) -> dict[str, object]:
    if type(crop) is not dict or set(crop) != _CROP_FIELDS:
        raise ValueError("Charles Jubilees visual review crop fields are invalid.")
    if (
        crop.get("pdf_page") != expected_page
        or crop.get("scan_leaf") != scan_mapping[expected_page - 1]
        or crop.get("djvu_object_index") != expected_page
        or crop.get("render_canvas") != [1275, 1650]
        or crop.get("pixel_margin") != 24
        or type(crop.get("crop_rgb_sha256")) is not str
        or re.fullmatch(r"[0-9a-f]{64}", crop["crop_rgb_sha256"]) is None
    ):
        raise ValueError("Charles Jubilees visual review crop identity is invalid.")
    source_text = rows.get((chapter, verse))
    if source_text is None:
        raise ValueError("Charles Jubilees visual review position is invalid.")
    derived = _derive_visual_crop(source_text, pages[expected_page - 1])
    compared = {
        field: value for field, value in derived.items()
        if not (full_page and field == "render_bbox")
    }
    if any(crop.get(field) != value for field, value in compared.items()):
        raise ValueError("Charles Jubilees visual review crop derivation changed.")
    if full_page and crop.get("render_bbox") != [0, 0, 1275, 1650]:
        raise ValueError("Charles Jubilees visual review full-page crop changed.")
    x1, y1, x2, y2 = crop["render_bbox"]
    if not (0 <= x1 < x2 <= 1275 and 0 <= y1 < y2 <= 1650):
        raise ValueError("Charles Jubilees visual review crop bounds are invalid.")
    return crop


def _validate_visual_review_payload(
    payload: dict[str, object], verification_root: Path,
) -> dict[str, object]:
    if (
        type(payload) is not dict
        or sha256(_json_bytes(payload)).hexdigest() != VISUAL_REVIEW_SHA256
        or set(payload) != {
            "schema_version", "family_id", "pdf_sha256", "pdf_pages", "reviewer",
            "human_visual_review_claimed", "reviewed_at", "render_profile", "samples",
            "marker_repairs", "chapter_27_recovery",
        }
        or payload.get("schema_version") != 1
        or payload.get("family_id") != "rh-charles-jubilees-1902"
        or payload.get("pdf_sha256") != _HISTORICAL_ARTIFACT_IDENTITIES["scan_authority"][2]
        or payload.get("pdf_pages") != 380
        or payload.get("reviewer") != "OpenAI Codex (AI-assisted source verification)"
        or payload.get("human_visual_review_claimed") is not False
        or payload.get("reviewed_at") != "2026-08-30T08:55:00Z"
        or payload.get("render_profile") != {
            "renderer": "Poppler pdftoppm 26.05.0", "render_canvas": [1275, 1650],
            "color_mode": "RGB", "pixel_margin": 24,
            "crop_hash": "SHA-256 of row-major RGB bytes",
            "timeout_seconds": 30, "file_limit_bytes": 6311267,
        }
    ):
        raise ValueError("Charles Jubilees visual review identity is invalid.")
    root = Path(verification_root)
    _validate_historical_lock(root)
    xml_snapshot = _secure_read(
        root / "artifacts/bookofjubileesor00char_djvu.xml", maximum=13_000_000,
        context="Charles Jubilees visual review OCR XML",
    )
    scandata_snapshot = _secure_read(
        root / "artifacts/bookofjubileesor00char_scandata.xml", maximum=256_000,
        context="Charles Jubilees visual review scandata",
    )
    pages = _visual_ocr_pages(xml_snapshot)
    scan_mapping = _visual_scan_mapping(scandata_snapshot)
    from app.library.verification.registry import load_source_registry
    definition = load_source_registry(root / "source-registry.json").families[
        "rh-charles-jubilees-1902"
    ]
    source_rows = parse_charles_jubilees(
        root / "artifacts" / definition.artifact_filename,
        definition, expected_sha256=SOURCE_ARTIFACT_SHA256,
    )
    rows = {(row.chapter, row.verse): row.text for row in source_rows}
    samples = payload.get("samples")
    if type(samples) is not list or len(samples) != len(_HISTORICAL_SAMPLES):
        raise ValueError("Charles Jubilees visual review sample inventory is invalid.")
    for record, expected in zip(samples, _HISTORICAL_SAMPLES, strict=True):
        phase, chapter, verse, page = expected
        if (
            type(record) is not dict
            or set(record) != {"phase", "chapter", "verse", "visual_review"}
            or (record["phase"], record["chapter"], record["verse"]) != (
                phase, chapter, verse,
            )
        ):
            raise ValueError("Charles Jubilees visual review sample location is invalid.")
        _validate_visual_crop(
            record["visual_review"], chapter=chapter, verse=verse,
            expected_page=page, rows=rows, pages=pages, scan_mapping=scan_mapping,
        )
    repairs = payload.get("marker_repairs")
    if type(repairs) is not list or len(repairs) != 7:
        raise ValueError("Charles Jubilees visual review repair inventory is invalid.")
    for record, repair, location in zip(
        repairs, MARKER_REPAIRS, _REPAIR_REVIEW_PAGES, strict=True,
    ):
        chapter, verse, source_fragment, repaired_fragment = repair
        if (
            type(record) is not dict
            or set(record) != {
                "chapter", "verse", "source_fragment", "repaired_fragment",
                "visual_review",
            }
            or (record["chapter"], record["verse"], record["source_fragment"],
                record["repaired_fragment"]) != repair
            or location[:2] != repair[:2]
        ):
            raise ValueError("Charles Jubilees visual review repair location is invalid.")
        _validate_visual_crop(
            record["visual_review"], chapter=chapter, verse=verse,
            expected_page=location[2], rows=rows, pages=pages, scan_mapping=scan_mapping,
        )
    recovery = payload.get("chapter_27_recovery")
    if (
        type(recovery) is not dict
        or set(recovery) != {
            "chapter", "positions", "page_position_coverage", "crops",
        }
        or recovery.get("chapter") != 27
        or recovery.get("positions") != list(range(1, 14))
        or recovery.get("page_position_coverage") != [
            {"pdf_page": 263, "positions": list(range(1, 7))},
            {"pdf_page": 264, "positions": list(range(7, 14))},
        ]
        or type(recovery.get("crops")) is not list
        or len(recovery["crops"]) != 2
    ):
        raise ValueError("Charles Jubilees visual review chapter-27 recovery is invalid.")
    for crop, verse, page in zip(recovery["crops"], (1, 13), (263, 264), strict=True):
        if type(crop) is not dict or crop.get("verse") != verse:
            raise ValueError("Charles Jubilees visual review chapter-27 crop is invalid.")
        crop_without_verse = dict(crop)
        crop_without_verse.pop("verse")
        _validate_visual_crop(
            crop_without_verse, chapter=27, verse=verse, expected_page=page,
            rows=rows, pages=pages, scan_mapping=scan_mapping, full_page=True,
        )
    return payload


def _load_visual_review(verification_root: Path) -> tuple[dict[str, object], str]:
    path = Path(verification_root) / "reports" / VISUAL_REVIEW_FILENAME
    snapshot = _secure_read(
        path, maximum=64 * 1024, context="Charles Jubilees visual review",
    )
    try:
        payload = json.loads(snapshot)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Charles Jubilees visual review is invalid.") from error
    if type(payload) is not dict or _json_bytes(payload) != snapshot:
        raise ValueError("Charles Jubilees visual review is not canonical.")
    return _validate_visual_review_payload(payload, verification_root), sha256(snapshot).hexdigest()


def _read_json_object(path: Path, *, maximum: int, context: str) -> dict[str, object]:
    snapshot = _secure_read(path, maximum=maximum, context=context)
    try:
        value = json.loads(snapshot)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{context} must be strict JSON.") from error
    if type(value) is not dict:
        raise ValueError(f"{context} must contain one JSON object.")
    return value


_HISTORICAL_ARTIFACT_IDENTITIES = {
    "catalog_metadata": (
        "bookofjubileesor00char_metadata.json", 73370,
        "e55412f7b61f0f7dc98585b769dc1760154618531ca98625634bce391e3d5449",
        "https://archive.org/metadata/bookofjubileesor00char",
    ),
    "scan_authority": (
        "bookofjubileesor00char.pdf", 22516657,
        "bf8b2578e258b2798ca5ee89b9083b7733e5ed89dc4c338473df685913ad7203",
        "https://archive.org/download/bookofjubileesor00char/bookofjubileesor00char.pdf",
    ),
    "ocr_text_page_anchor": (
        "bookofjubileesor00char_djvu.txt", 953770,
        "491e1726cdca207a4bc3a8b6877faed30cb43ba247246354567d43dfd84e35c5",
        "https://archive.org/download/bookofjubileesor00char/bookofjubileesor00char_djvu.txt",
    ),
    "ocr_coordinate_page_anchor": (
        "bookofjubileesor00char_djvu.xml", 12939768,
        "21c2e93b423168a4d35b685efd0a69ce21fa4a617dd51d68e4fc3958ffc34e46",
        "https://archive.org/download/bookofjubileesor00char/bookofjubileesor00char_djvu.xml",
    ),
    "scan_page_map": (
        "bookofjubileesor00char_scandata.xml", 197013,
        "cbd17bf7165b4122ad81ec347135f677759011a41b8663ae8c163e085f132e96",
        "https://archive.org/download/bookofjubileesor00char/bookofjubileesor00char_scandata.xml",
    ),
}


def _validate_historical_lock_payload(
    lock: dict[str, object], verification_root: Path,
) -> dict[str, object]:
    root = Path(verification_root)
    if (
        set(lock) != {
            "archive_identifier", "archive_ark", "artifacts", "catalog_metadata",
            "retrieved_at", "version",
        }
        or lock.get("version") != 1
        or lock.get("archive_identifier") != "bookofjubileesor00char"
        or lock.get("archive_ark") != "ark:/13960/t44q88j4t"
        or lock.get("retrieved_at") != "2026-08-30T02:00:00Z"
        or lock.get("catalog_metadata") != {
            "creator": "Charles, R. H. (Robert Henry), 1855-1931",
            "date": "1902",
            "publisher": "London, A. and C. Black",
            "title": "The book of Jubilees, or The little Genesis",
        }
    ):
        raise ValueError("Charles Jubilees historical artifact identity is invalid.")
    artifacts = lock.get("artifacts")
    if type(artifacts) is not list or len(artifacts) != 5:
        raise ValueError("Charles Jubilees historical artifact inventory is invalid.")
    roles = set()
    for record in artifacts:
        if type(record) is not dict or set(record) != {
            "artifact_path", "role", "sha256", "size_bytes", "source_url",
        }:
            raise ValueError("Charles Jubilees historical artifact record is invalid.")
        name, size, digest, role, source_url = (
            record.get("artifact_path"), record.get("size_bytes"),
            record.get("sha256"), record.get("role"), record.get("source_url"),
        )
        if (
            type(name) is not str or Path(name).name != name
            or type(size) is not int or not 0 < size <= 32 * 1024 * 1024
            or type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or type(role) is not str or role in roles
        ):
            raise ValueError("Charles Jubilees historical artifact record is unsafe.")
        if (name, size, digest, source_url) != _HISTORICAL_ARTIFACT_IDENTITIES.get(role):
            raise ValueError("Charles Jubilees historical artifact identity is invalid.")
        roles.add(role)
        snapshot = _secure_read(
            root / "artifacts" / name, maximum=32 * 1024 * 1024,
            context=f"Charles Jubilees historical artifact {role}",
        )
        if len(snapshot) != size or sha256(snapshot).hexdigest() != digest:
            raise ValueError("Charles Jubilees historical artifact does not match its lock.")
    if roles != set(_HISTORICAL_ARTIFACT_IDENTITIES):
        raise ValueError("Charles Jubilees historical artifact roles are invalid.")
    return lock


def _validate_historical_lock(verification_root: Path) -> dict[str, object]:
    root = Path(verification_root)
    lock = _read_json_object(
        root / HISTORICAL_LOCK_FILENAME, maximum=64 * 1024,
        context="Charles Jubilees historical artifact lock",
    )
    return _validate_historical_lock_payload(lock, root)


def build_historical_evidence(verification_root: Path) -> dict[str, object]:
    """Reproduce the fixed AI-assisted scan-correlation evidence payload."""
    root = Path(verification_root)
    historical_lock = _validate_historical_lock(root)
    definition_path = root / "source-registry.json"
    from app.library.verification.registry import load_source_registry
    definition = load_source_registry(definition_path).families["rh-charles-jubilees-1902"]
    rows = parse_charles_jubilees(
        root / "artifacts" / definition.artifact_filename,
        definition, expected_sha256=SOURCE_ARTIFACT_SHA256,
    )
    by_position = {(row.chapter, row.verse): row.text for row in rows}
    visual_review, visual_review_sha256 = _load_visual_review(root)
    visual_samples = {
        (record["phase"], record["chapter"], record["verse"]): record["visual_review"]
        for record in visual_review["samples"]
    }
    samples = []
    for phase, chapter, verse, pdf_page in _HISTORICAL_SAMPLES:
        text = by_position[(chapter, verse)]
        samples.append({
            "phase": phase,
            "chapter": chapter,
            "verse": verse,
            "scan_pdf_page": pdf_page,
            "source_text_sha256": sha256(text.encode("utf-8")).hexdigest(),
            "result": "confirmed_visual",
            "review_method": "AI visual comparison of locked scan page to locked transcription",
            "visual_review": visual_samples[(phase, chapter, verse)],
        })
    return {
        "schema_version": 1,
        "family_id": "rh-charles-jubilees-1902",
        "reviewer": "OpenAI Codex (AI-assisted source verification)",
        "human_visual_review_claimed": False,
        "reviewed_at": "2026-08-30T08:55:00Z",
        "scan_authority_sha256": next(
            item["sha256"] for item in historical_lock["artifacts"]
            if item["role"] == "scan_authority"
        ),
        "publication_transcription_sha256": SOURCE_ARTIFACT_SHA256,
        "visual_review_sha256": visual_review_sha256,
        "edition_equivalence": "sampled_no_revision_detected",
        "edition_finding": (
            "The authorized 1917 reprint identifies its text as Charles's translation "
            "published in 1902; nine fixed beginning, middle, and end samples agree with "
            "the locked 1902 scan. This is sampled evidence, not a full-edition collation."
        ),
        "numbered_position_count": 1307,
        "rejected_secondary_claim": (
            "The 1,341-position claim conflicts with the primary 1902 numbering; "
            "the 50 chapter maxima total 1,307."
        ),
        "samples": samples,
        "marker_repairs": visual_review["marker_repairs"],
        "collapsed_paragraph_recovery": {
            "chapter": 27, "positions": list(range(1, 14)),
            "method": "split only explicit numeric markers confirmed in the 1902 scan",
            "page_position_coverage": visual_review["chapter_27_recovery"][
                "page_position_coverage"
            ],
            "visual_review": visual_review["chapter_27_recovery"]["crops"],
        },
        "transformations": [
            "Exclude introductory, editorial, footnote, page-header, and end matter.",
            "Remove marginal A.M. date labels without changing scripture wording.",
            "Normalize HTML whitespace, Unicode to NFC, and marker whitespace.",
            "Repair only seven scan-confirmed numeric marker defects.",
            "Recover chapter 27 positions 1-13 only from explicit scan-confirmed markers.",
        ],
    }


def validate_historical_evidence(
    evidence_path: Path, verification_root: Path, definition: SourceDefinition,
) -> dict[str, object]:
    _validate_definition(definition)
    path = Path(evidence_path)
    root = Path(verification_root)
    if path.parent.resolve() != root.resolve() or path.name != HISTORICAL_EVIDENCE_FILENAME:
        raise ValueError("Charles Jubilees historical evidence path is invalid.")
    committed = _read_json_object(
        path, maximum=256 * 1024, context="Charles Jubilees historical evidence",
    )
    expected = build_historical_evidence(root)
    if committed != expected:
        raise ValueError("Charles Jubilees historical evidence is not reproducible.")
    return committed


def _current_rows(snapshot: bytes) -> tuple[SourceVerse, ...]:
    try:
        with ZipFile(BytesIO(snapshot)) as archive:
            names = archive.namelist()
            if names.count(CURRENT_MEMBER) != 1:
                raise ValueError("current publication has an invalid Jubilees member.")
            info = archive.getinfo(CURRENT_MEMBER)
            if info.file_size > 4 * 1024 * 1024 or info.compress_size > 4 * 1024 * 1024:
                raise ValueError("current Jubilees member exceeds its size bound.")
            payload = json.loads(archive.read(info))
    except (OSError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("current Jubilees publication is invalid.") from error
    if type(payload) is not list or len(payload) != 50:
        raise ValueError("current Jubilees publication must contain 50 chapters.")
    rows = []
    for chapter_number, chapter in enumerate(payload, 1):
        if type(chapter) is not dict or chapter.get("c") != chapter_number:
            raise ValueError("current Jubilees chapter sequence is invalid.")
        verses = chapter.get("v")
        if type(verses) is not list or not verses or len(verses) > 100:
            raise ValueError("current Jubilees chapter inventory is invalid.")
        for verse_number, verse in enumerate(verses, 1):
            if (
                type(verse) is not dict or verse.get("n") != verse_number
                or type(verse.get("t")) is not str or not verse["t"]
            ):
                raise ValueError("current Jubilees position is invalid.")
            rows.append(SourceVerse("jubilees", chapter_number, verse_number, verse["t"]))
    if len(rows) > 2000:
        raise ValueError("current Jubilees publication exceeds its position bound.")
    return tuple(rows)


def _render_rows(rows: tuple[SourceVerse, ...]) -> bytes:
    chapters: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        chapters[row.chapter].append({"n": row.verse, "t": row.text})
    return _json_bytes([
        {"c": chapter, "v": chapters[chapter]} for chapter in sorted(chapters)
    ])


class CharlesJubileesAdapter:
    """Evidence-gated adapter for the exact Charles-numbered Jubilees text."""

    def compare_family(
        self, *, definition, lock_record, artifact_path, current_bundle, output,
    ):
        from app.library.verification.cli import CompareFamilyResult

        _validate_definition(definition)
        if (
            lock_record.family_id != definition.family_id
            or lock_record.artifact_path != definition.artifact_filename
            or lock_record.source_url != definition.artifact_url
            or lock_record.landing_url != definition.landing_url
            or lock_record.size_bytes != SOURCE_ARTIFACT_SIZE
            or lock_record.sha256 != SOURCE_ARTIFACT_SHA256
        ):
            raise ValueError("Charles Jubilees artifact lock identity is invalid.")
        verification_root = Path(artifact_path).parent.parent
        validate_historical_evidence(
            verification_root / HISTORICAL_EVIDENCE_FILENAME,
            verification_root,
            definition,
        )
        source = parse_charles_jubilees(
            artifact_path, definition, expected_sha256=lock_record.sha256,
        )
        snapshot = _secure_read(
            current_bundle, maximum=256 * 1024 * 1024,
            context="current Jubilees publication bundle",
        )
        report = compare_work(
            "jubilees", _current_rows(snapshot), source, ComparisonRules(),
            source_artifact_sha256=lock_record.sha256,
            current_publication_sha256=sha256(snapshot).hexdigest(),
            parser_version=PARSER_VERSION,
        )
        output = Path(output)
        write_report_pair(report, output / definition.family_id, "jubilees")
        totals = {
            name: getattr(report.totals, name)
            for name in ("exact", "formatting", "missing", "extra", "wording")
        }
        family = {
            "schema_version": 1,
            "family_id": definition.family_id,
            "source_artifact_sha256": lock_record.sha256,
            "current_publication_sha256": sha256(snapshot).hexdigest(),
            "parser_version": PARSER_VERSION,
            "edition_equivalence": "sampled_no_revision_detected",
            "numbered_position_count": 1307,
            "totals": totals,
            "works": [{
                "work_id": "jubilees", "report_sha256": report_sha256(report),
                "totals": totals,
            }],
        }
        _atomic_write(output / f"{definition.family_id}.json", _json_bytes(family))
        _atomic_write(
            output / f"{definition.family_id}.md",
            ("# R. H. Charles Jubilees Source Verification\n\n"
             "This is a source-specific research publication, not a complete or official "
             "Ethiopian Bible.\n\n" + "\n".join(
                 f"- {name.title()}: {totals[name]}" for name in totals
             ) + "\n").encode("utf-8"),
        )
        return CompareFamilyResult(report_count=1, output_id=definition.family_id)

    def build_candidate(
        self, *, definition, lock_record, artifact_path, report_dir, output,
        replace_from_source,
    ):
        from app.library.verification.cli import CandidateBuildResult

        if not replace_from_source:
            raise ValueError("Charles Jubilees candidates require explicit source replacement.")
        _validate_definition(definition)
        if (
            lock_record.family_id != definition.family_id
            or lock_record.artifact_path != definition.artifact_filename
            or lock_record.source_url != definition.artifact_url
            or lock_record.landing_url != definition.landing_url
            or lock_record.size_bytes != SOURCE_ARTIFACT_SIZE
            or lock_record.sha256 != SOURCE_ARTIFACT_SHA256
        ):
            raise ValueError("Charles Jubilees candidate artifact lock identity is invalid.")
        report_dir = Path(report_dir)
        if report_dir.name != definition.family_id or report_dir.parent.name != "reports":
            raise ValueError("Charles Jubilees candidate report directory is invalid.")
        root = report_dir.parents[1]
        validate_historical_evidence(root / HISTORICAL_EVIDENCE_FILENAME, root, definition)
        family_snapshot = _secure_read(
            report_dir.parent / f"{definition.family_id}.json", maximum=1024 * 1024,
            context="Charles Jubilees final family report",
        )
        try:
            family = json.loads(family_snapshot)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Charles Jubilees final family report is invalid.") from error
        expected_totals = {
            "exact": 1307, "formatting": 0, "missing": 0, "extra": 0, "wording": 0,
        }
        if (
            type(family) is not dict
            or _json_bytes(family) != family_snapshot
            or set(family) != {
                "schema_version", "family_id", "source_artifact_sha256",
                "current_publication_sha256", "parser_version", "edition_equivalence",
                "numbered_position_count", "totals", "works",
            }
            or family.get("schema_version") != 1
            or family.get("family_id") != definition.family_id
            or family.get("source_artifact_sha256") != SOURCE_ARTIFACT_SHA256
            or family.get("current_publication_sha256")
            != REVIEWED_FINAL_PUBLICATION_SHA256
            or family.get("parser_version") != PARSER_VERSION
            or family.get("edition_equivalence") != "sampled_no_revision_detected"
            or family.get("numbered_position_count") != 1307
            or family.get("totals") != expected_totals
            or type(family.get("works")) is not list
            or len(family["works"]) != 1
            or type(family["works"][0]) is not dict
            or set(family["works"][0]) != {"work_id", "report_sha256", "totals"}
            or family["works"][0].get("work_id") != "jubilees"
            or family["works"][0].get("totals") != expected_totals
            or type(family["works"][0].get("report_sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", family["works"][0]["report_sha256"]) is None
        ):
            raise ValueError("Charles Jubilees final family report gate is not satisfied.")
        report_snapshot = _secure_read(
            report_dir / "jubilees.json", maximum=8 * 1024 * 1024,
            context="Charles Jubilees final work report",
        )
        try:
            from app.library.verification.cli import _strict_report
            report = _strict_report(json.loads(report_snapshot))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError("Charles Jubilees final work report is invalid.") from error
        if (
            report_json_bytes(report) != report_snapshot
            or sha256(report_snapshot).hexdigest() != family["works"][0]["report_sha256"]
            or report.work_id != "jubilees"
            or report.source_artifact.sha256 != SOURCE_ARTIFACT_SHA256
            or report.current_publication.sha256
            != REVIEWED_FINAL_PUBLICATION_SHA256
            or report.current_publication.sha256 != family["current_publication_sha256"]
            or report.parser_version != PARSER_VERSION
            or report.rules != ComparisonRules()
            or report.totals.exact != 1307
            or any(getattr(report.totals, name) for name in (
                "formatting", "missing", "extra", "wording",
            ))
            or report.differences
            or report.declared_omissions
            or report.is_verified_candidate is not True
        ):
            raise ValueError("Charles Jubilees final exact report gate is not satisfied.")
        rows = parse_charles_jubilees(
            artifact_path, definition, expected_sha256=lock_record.sha256,
        )
        members = {
            CURRENT_MEMBER: _render_rows(rows),
            "data/index.json": _json_bytes({"books": [{
                "work_id": "jubilees", "file": CURRENT_MEMBER, "chapters": 50,
                "source_label": "R. H. Charles 1902 translation",
            }]}),
        }
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(members):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = ZIP_DEFLATED
                archive.writestr(
                    info, members[name], compress_type=ZIP_DEFLATED, compresslevel=9,
                )
        return CandidateBuildResult(work_count=1, output_id=output.name)
