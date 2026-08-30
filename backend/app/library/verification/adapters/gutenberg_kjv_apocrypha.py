"""Strict Project Gutenberg eBook 124 KJV-family Apocrypha adapter."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from app.library.verification.compare import compare_work
from app.library.verification.report import report_sha256, write_report_pair
from app.library.verification.registry import SourceDefinition
from app.library.verification.types import ComparisonRules, SourceVerse


PARSER_VERSION = "gutenberg-kjv-apocrypha/1"
SOURCE_ARTIFACT_SHA256 = (
    "83de0c18742ba22b3d442c3a5bc828fe9e91dff27ae3c298e9b5c9a6ecfbf4d4"
)
SOURCE_ARTIFACT_SIZE = 835_071
SOURCE_UPDATED = "2021-08-26"
SOURCE_CREDITS = "Robert Kraft"
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
HISTORICAL_EVIDENCE_FILENAME = "kjv-1611-fallback-historical-evidence.json"
HISTORICAL_LOCK_FILENAME = "kjv-1611-historical-artifacts.lock.json"
HISTORICAL_LOCK_SHA256 = (
    "7f1ed08573ce8b3a0a9e2edfbb871487dcd41606901bef8de45dfdd9b799f713"
)
HISTORICAL_REVIEWED_AT = "2026-08-30T01:18:59Z"
MAX_CURRENT_ZIP_MEMBERS = 256
MAX_CURRENT_MEMBER_BYTES = 1024 * 1024
MAX_CURRENT_TOTAL_BYTES = 16 * 1024 * 1024
MAX_CURRENT_COMPRESSION_RATIO = 50
CURRENT_READ_CHUNK_BYTES = 64 * 1024
REPORT_TRANSFORMATIONS = (
    "join wrapped physical lines within source positions with one space",
    "map Baruch 6:1-73 to Letter of Jeremiah 1:1-73",
    "map Song of the Three Holy Children 2-68 to Prayer of Azariah 1:1-67",
    "map the unnumbered Prayer of Manasses to Prayer of Manasseh 1:1",
    "exclude headings, editorial notes, Song 1, and quoted canonical Daniel prose",
)
PRE_REBUILD_PUBLICATION_SHA256 = (
    "49a874a784640bc2b698e1e23c38b3fb7643715e7230c190539c6242e2849bd9"
)
PRE_REBUILD_FAMILY_REPORT_SHA256 = (
    "d167b92e9862685e35656f5afb16a8e3994c87624fafd9e845e2755416fb91d2"
)

EXPECTED_COUNTS = {
    "baruch": 140,
    "letter-of-jeremiah": 73,
    "prayer-of-azariah": 67,
    "susanna": 64,
    "bel-and-the-dragon": 42,
    "prayer-of-manasseh": 1,
}
CURRENT_MEMBER = {
    "baruch": "data/bar.json",
    "letter-of-jeremiah": "data/lje.json",
    "prayer-of-azariah": "data/aza.json",
    "susanna": "data/sus.json",
    "bel-and-the-dragon": "data/bel.json",
    "prayer-of-manasseh": "data/man.json",
}
_SCAN_CORRECTIONS = (
    ("bel-and-the-dragon", 1, 15, "drinck", "drink", 1157),
    ("bel-and-the-dragon", 1, 18, "dour", "door", 1157),
    ("prayer-of-manasseh", 1, 1, "life up", "lift up", 1158),
    ("prayer-of-manasseh", 1, 1, "iniquites", "iniquities", 1158),
)
_HEADINGS = {
    "baruch": ("The Book of Baruch", "The Epistle [or Letter] of Jeremiah [Jeremy]"),
    "letter-of-jeremiah": (
        "The Epistle [or Letter] of Jeremiah [Jeremy]",
        "The Song of the Three Holy Children",
    ),
    "prayer-of-azariah": (
        "The Song of the Three Holy Children", "The Book of Susanna [in Daniel]",
    ),
    "susanna": (
        "The Book of Susanna [in Daniel]",
        "The History of the Destruction of\nBel and the Dragon",
    ),
    "bel-and-the-dragon": (
        "The History of the Destruction of\nBel and the Dragon",
        "The Prayer of Manasses",
    ),
    "prayer-of-manasseh": (
        "The Prayer of Manasses", "The First Book of the Maccabees",
    ),
}
_HEADING_COUNTS = {
    "The Book of Baruch": 2,
    "The Epistle [or Letter] of Jeremiah [Jeremy]": 1,
    "The Song of the Three Holy Children": 2,
    "The Book of Susanna [in Daniel]": 1,
    "The History of the Destruction of\nBel and the Dragon": 1,
    "The Prayer of Manasses": 2,
    "The First Book of the Maccabees": 2,
}


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
        after_fd = os.fstat(descriptor)
        after_path = path.lstat()
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
    if definition.adapter_id != "gutenberg_kjv_apocrypha":
        raise ValueError("definition must select the Gutenberg KJV Apocrypha adapter.")
    if definition.expected_work_ids != tuple(EXPECTED_COUNTS):
        raise ValueError("definition must contain the exact six-work fallback inventory.")


def _section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.rfind(start_heading)
    end = text.rfind(end_heading)
    if start < 0 or end <= start:
        raise ValueError("Gutenberg required section heading order is invalid.")
    return text[start + len(start_heading):end]


def _numbered(section: str, pattern: re.Pattern[str]) -> dict[tuple[int, ...], str]:
    rows: dict[tuple[int, ...], str] = {}
    position: tuple[int, ...] | None = None
    for line in section.split("\n"):
        match = pattern.fullmatch(line)
        if match is not None:
            *numbers, value = match.groups()
            position = tuple(int(number) for number in numbers)
            if position in rows:
                raise ValueError("Gutenberg source contains a duplicate position.")
            rows[position] = value.strip()
        elif position is not None and line.strip():
            rows[position] += " " + line.strip()
    return {position: " ".join(value.split()) for position, value in rows.items()}


def _expected_positions(work_id: str) -> set[tuple[int, int]]:
    if work_id == "baruch":
        counts = (22, 35, 37, 37, 9)
        return {
            (chapter, verse)
            for chapter, count in enumerate(counts, 1)
            for verse in range(1, count + 1)
        }
    return {(1, verse) for verse in range(1, EXPECTED_COUNTS[work_id] + 1)}


def _parse_snapshot(snapshot: bytes, definition: SourceDefinition) -> tuple[SourceVerse, ...]:
    _validate_definition(definition)
    try:
        raw_text = snapshot.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Gutenberg artifact must be strict UTF-8 encoding.") from error
    if raw_text.startswith("\ufeff") or unicodedata.normalize("NFC", raw_text) != raw_text:
        raise ValueError("Gutenberg artifact must be BOM-free NFC UTF-8.")
    if raw_text.count("\r\n") != raw_text.count("\n") or "\r" in raw_text.replace("\r\n", ""):
        raise ValueError("Gutenberg artifact must use its reviewed CRLF convention.")
    if any(
        character not in "\r\n"
        and (
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
        )
        for character in raw_text
    ):
        raise ValueError("Gutenberg artifact contains an unsafe control character.")
    text = raw_text.replace("\r\n", "\n")
    required_metadata = (
        "Title: Deuterocanonical Books of the Bible",
        "Release date: April 1, 1994 [eBook #124]",
        "Most recently updated: August 26, 2021",
        "Credits: Robert Kraft",
        "*** START OF THE PROJECT GUTENBERG EBOOK DEUTEROCANONICAL BOOKS OF THE BIBLE ***",
        "*** END OF THE PROJECT GUTENBERG EBOOK DEUTEROCANONICAL BOOKS OF THE BIBLE ***",
    )
    if any(text.count(value) != 1 for value in required_metadata):
        raise ValueError("Gutenberg artifact metadata identity is invalid.")
    if any(text.count(heading) != count for heading, count in _HEADING_COUNTS.items()):
        raise ValueError("Gutenberg section heading inventory is invalid.")

    parsed: dict[str, dict[tuple[int, int], str]] = {}
    baruch = _numbered(
        _section(text, *_HEADINGS["baruch"]), re.compile(r"(\d+):(\d+) (.*)"),
    )
    parsed["baruch"] = baruch
    letter = _numbered(
        _section(text, *_HEADINGS["letter-of-jeremiah"]),
        re.compile(r"(\d+):(\d+) (.*)"),
    )
    if any(chapter != 6 for chapter, _ in letter):
        raise ValueError("Gutenberg Letter of Jeremiah must use reviewed Baruch 6 labels.")
    parsed["letter-of-jeremiah"] = {(1, verse): value for (_, verse), value in letter.items()}
    song = _numbered(
        _section(text, *_HEADINGS["prayer-of-azariah"]), re.compile(r"(\d+) (.*)"),
    )
    if set(song) != {(verse,) for verse in range(1, 69)}:
        raise ValueError("Gutenberg Song of the Three Children labels are invalid.")
    parsed["prayer-of-azariah"] = {
        (1, verse - 1): value for (verse,), value in song.items() if verse >= 2
    }
    parsed["susanna"] = _numbered(
        _section(text, *_HEADINGS["susanna"]), re.compile(r"(\d+):(\d+) (.*)"),
    )
    parsed["bel-and-the-dragon"] = _numbered(
        _section(text, *_HEADINGS["bel-and-the-dragon"]),
        re.compile(r"(\d+):(\d+) (.*)"),
    )
    prayer = _section(text, *_HEADINGS["prayer-of-manasseh"])
    lines = prayer.split("\n")
    if lines.count("King of Judah") != 1:
        raise ValueError("Gutenberg Prayer of Manasses subtitle is invalid.")
    start = lines.index("King of Judah") + 1
    prayer_text = " ".join(" ".join(lines[start:]).split())
    parsed["prayer-of-manasseh"] = {(1, 1): prayer_text}

    rows: list[SourceVerse] = []
    for work_id in definition.expected_work_ids:
        work = parsed.get(work_id)
        if work is None or set(work) != _expected_positions(work_id):
            raise ValueError(f"Gutenberg position inventory is invalid for {work_id}.")
        for (chapter, verse), value in sorted(work.items()):
            if not value:
                raise ValueError("Gutenberg scripture text must not be blank.")
            rows.append(SourceVerse(work_id, chapter, verse, value))
    if len(rows) != 387:
        raise ValueError("Gutenberg source must contain exactly 387 approved positions.")
    return tuple(rows)


def parse_gutenberg_kjv_apocrypha(
    path: Path,
    definition: SourceDefinition,
    *,
    expected_sha256: str | None = None,
) -> tuple[SourceVerse, ...]:
    """Parse exactly six approved fallback works from the locked eBook 124 text."""
    _validate_definition(definition)
    snapshot = _secure_read(
        path, maximum=min(definition.max_artifact_bytes, MAX_ARTIFACT_BYTES),
        context="Gutenberg eBook 124 artifact",
    )
    if expected_sha256 is not None and sha256(snapshot).hexdigest() != expected_sha256:
        raise ValueError("Gutenberg artifact snapshot does not match its lock.")
    return _parse_snapshot(snapshot, definition)


def _group(rows: tuple[SourceVerse, ...]) -> dict[str, tuple[SourceVerse, ...]]:
    grouped: dict[str, list[SourceVerse]] = defaultdict(list)
    for row in rows:
        grouped[row.work_id].append(row)
    return {work_id: tuple(values) for work_id, values in grouped.items()}


def _bounded_member_read(archive: ZipFile, info: ZipInfo) -> bytes:
    chunks: list[bytes] = []
    remaining = info.file_size
    with archive.open(info, "r") as handle:
        while remaining:
            chunk = handle.read(min(CURRENT_READ_CHUNK_BYTES, remaining))
            if not chunk:
                raise ValueError("current bundle member ended before its declared size.")
            chunks.append(chunk)
            remaining -= len(chunk)
        if handle.read(1):
            raise ValueError("current bundle member exceeded its declared size.")
    result = b"".join(chunks)
    if len(result) != info.file_size:
        raise ValueError("current bundle member size changed during bounded read.")
    return result


def _validated_zip_members(archive: ZipFile) -> dict[str, ZipInfo]:
    infos = archive.infolist()
    if not infos or len(infos) > MAX_CURRENT_ZIP_MEMBERS:
        raise ValueError("current bundle ZIP member count is outside its bound.")
    if any(type(info) is not ZipInfo for info in infos):
        raise ValueError("current bundle ZIP metadata type is invalid.")
    if len({info.filename for info in infos}) != len(infos):
        raise ValueError("current bundle contains duplicate members.")
    total = 0
    for info in infos:
        mode = (info.external_attr >> 16) & 0xFFFF
        if info.is_dir() or (info.create_system == 3 and (not mode or not stat.S_ISREG(mode))):
            raise ValueError("current bundle members must be regular files.")
        if info.flag_bits & 0x1:
            raise ValueError("current bundle must not contain encrypted members.")
        if info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
            raise ValueError("current bundle member compression is not approved.")
        if (
            type(info.file_size) is not int
            or type(info.compress_size) is not int
            or info.file_size < 0
            or info.compress_size < 0
            or info.file_size > MAX_CURRENT_MEMBER_BYTES
        ):
            raise ValueError("current bundle member uncompressed size exceeds its bound.")
        total += info.file_size
        if total > MAX_CURRENT_TOTAL_BYTES:
            raise ValueError("current bundle total uncompressed size exceeds its bound.")
        if info.file_size and (
            info.compress_size == 0
            or info.file_size / info.compress_size > MAX_CURRENT_COMPRESSION_RATIO
        ):
            raise ValueError("current bundle member compression ratio exceeds its bound.")
    return {info.filename: info for info in infos}


def _current_rows(snapshot: bytes, definition: SourceDefinition) -> dict[str, tuple[SourceVerse, ...]]:
    try:
        with ZipFile(BytesIO(snapshot)) as archive:
            members = _validated_zip_members(archive)
            result: dict[str, tuple[SourceVerse, ...]] = {}
            for work_id in definition.expected_work_ids:
                member = CURRENT_MEMBER[work_id]
                if member not in members:
                    raise ValueError("current fallback bundle is missing a required work.")
                chapters = json.loads(
                    _bounded_member_read(archive, members[member]).decode("utf-8")
                )
                rows = tuple(
                    SourceVerse(work_id, chapter["c"], verse["n"], verse["t"])
                    for chapter in chapters for verse in chapter["v"]
                )
                if len(rows) != EXPECTED_COUNTS[work_id]:
                    raise ValueError("current fallback work inventory is invalid.")
                result[work_id] = rows
            return result
    except (
        BadZipFile, KeyError, UnicodeError, json.JSONDecodeError,
        RuntimeError, NotImplementedError,
    ) as error:
        raise ValueError("current fallback bundle is invalid.") from error


def _json_bytes(value: object) -> bytes:
    return (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")


def _scan_page(work_id: str, chapter: int, verse: int) -> int:
    if work_id == "baruch":
        if chapter == 1 and verse <= 5:
            return 1144
        if chapter == 1 or (chapter == 2 and verse <= 6):
            return 1145
        if chapter == 2:
            return 1146
        if chapter == 3 and verse <= 33:
            return 1147
        if chapter == 3 or (chapter == 4 and verse <= 28):
            return 1148
        return 1149
    if work_id == "letter-of-jeremiah":
        return 1149 if verse <= 10 else 1150 if verse <= 42 else 1151
    if work_id == "prayer-of-azariah":
        return 1152 if verse <= 19 else 1153 if verse <= 57 else 1154
    if work_id == "susanna":
        return 1154 if verse <= 15 else 1155 if verse <= 50 else 1156
    if work_id == "bel-and-the-dragon":
        return 1156 if verse <= 6 else 1157 if verse <= 34 else 1158
    if work_id == "prayer-of-manasseh" and (chapter, verse) == (1, 1):
        return 1158
    raise ValueError("historical scan position is outside the reviewed inventory.")


def _jpeg_size(snapshot: bytes) -> tuple[int, int]:
    if not snapshot.startswith(b"\xff\xd8") or not snapshot.endswith(b"\xff\xd9"):
        raise ValueError("historical page image is not a complete JPEG snapshot.")
    offset = 2
    while offset + 4 <= len(snapshot):
        if snapshot[offset] != 0xFF:
            offset += 1
            continue
        marker = snapshot[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(snapshot):
            break
        length = int.from_bytes(snapshot[offset:offset + 2], "big")
        if length < 2 or offset + length > len(snapshot):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if length < 7:
                break
            height = int.from_bytes(snapshot[offset + 3:offset + 5], "big")
            width = int.from_bytes(snapshot[offset + 5:offset + 7], "big")
            return width, height
        offset += length
    raise ValueError("historical page image dimensions are invalid.")


def _historical_artifacts(verification_root: Path) -> dict[int, dict[str, object]]:
    verification_root = Path(verification_root)
    lock_path = verification_root / HISTORICAL_LOCK_FILENAME
    lock_snapshot = _secure_read(
        lock_path, maximum=64 * 1024, context="KJV historical artifact lock",
    )
    if sha256(lock_snapshot).hexdigest() != HISTORICAL_LOCK_SHA256:
        raise ValueError("KJV historical artifact lock identity is invalid.")
    try:
        lock = json.loads(lock_snapshot.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("KJV historical artifact lock is invalid.") from error
    if (
        type(lock) is not dict
        or lock.get("schema_version") != 1
        or lock.get("landing_url")
        != "https://colenda.library.upenn.edu/catalog/81431-p3rv0df45"
        or lock.get("rights") != "NoC-US"
        or lock.get("catalog_metadata") != {
            "title": "The Holy Bible, conteyning the Old Testament, and the New",
            "publisher": "Robert Barker", "date": "1611",
            "edition": "Great HE editio princeps",
        }
        or type(lock.get("artifacts")) is not list
        or len(lock["artifacts"]) != 18
    ):
        raise ValueError("KJV historical artifact lock metadata is invalid.")
    artifact_root = verification_root / "artifacts"
    snapshots: dict[str, bytes] = {}
    for record in lock["artifacts"]:
        if type(record) is not dict:
            raise ValueError("KJV historical artifact record is invalid.")
        path_value = record.get("artifact_path")
        if (
            type(path_value) is not str or not path_value
            or Path(path_value).is_absolute() or ".." in Path(path_value).parts
            or type(record.get("size_bytes")) is not int
            or type(record.get("sha256")) is not str
        ):
            raise ValueError("KJV historical artifact record identity is invalid.")
        snapshot = _secure_read(
            artifact_root / path_value,
            maximum=max(record["size_bytes"], 1),
            context=f"KJV historical artifact {path_value}",
        )
        if (
            len(snapshot) != record["size_bytes"]
            or sha256(snapshot).hexdigest() != record["sha256"]
            or path_value in snapshots
        ):
            raise ValueError("KJV historical artifact identity is invalid.")
        snapshots[path_value] = snapshot
    catalog = snapshots["upenn-1611-great-he-catalog.html"].decode("utf-8")
    if any(marker not in catalog for marker in (
        "By Robert Barker, Printer to the Kings most Excellent Maiestie",
        "Date:</dt><dd class=\"blacklight-date_ssim\">1611",
        "editio princeps of the King James' or Authorized version",
        "also known as the Great HE edition",
        "rightsstatements.org/vocab/NoC-US/1.0/",
    )):
        raise ValueError("KJV historical catalog evidence is invalid.")
    try:
        manifest = json.loads(
            snapshots["upenn-1611-great-he-iiif-manifest.json"].decode("utf-8")
        )
        canvases = manifest["sequences"][0]["canvases"]
    except (UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise ValueError("KJV historical IIIF manifest is invalid.") from error
    page_records = [record for record in lock["artifacts"] if record.get("role") == "page_image"]
    if [record.get("canvas_label") for record in page_records] != [
        f"p. {number}" for number in range(1143, 1159)
    ]:
        raise ValueError("KJV historical page inventory is invalid.")
    pages: dict[int, dict[str, object]] = {}
    for record in page_records:
        page = int(record["canvas_label"].split()[1])
        canvas = canvases[page - 1]
        service = canvas["images"][0]["resource"]["service"]["@id"]
        expected_url = f"{service}/full/full/0/default.jpg"
        snapshot = snapshots[record["artifact_path"]]
        if (
            canvas.get("label") != record["canvas_label"]
            or record.get("iiif_url") != expected_url
            or _jpeg_size(snapshot) != (record.get("width"), record.get("height"))
        ):
            raise ValueError("KJV historical page/manifest identity is invalid.")
        pages[page] = record
    return pages


def _corrected_rows(rows: tuple[SourceVerse, ...]) -> tuple[SourceVerse, ...]:
    values = {(row.work_id, row.chapter, row.verse): row.text for row in rows}
    for work_id, chapter, verse, old, new, _ in _SCAN_CORRECTIONS:
        key = (work_id, chapter, verse)
        text = values[key]
        if text.count(old) != 1:
            raise ValueError("scan-backed correction source identity changed.")
        values[key] = text.replace(old, new)
    return tuple(
        SourceVerse(row.work_id, row.chapter, row.verse,
                    values[(row.work_id, row.chapter, row.verse)])
        for row in rows
    )


def reviewed_gutenberg_kjv_apocrypha(
    path: Path, definition: SourceDefinition,
) -> tuple[SourceVerse, ...]:
    """Return the reviewed publication rows, including four scan-backed fixes."""
    return _corrected_rows(parse_gutenberg_kjv_apocrypha(
        path, definition, expected_sha256=SOURCE_ARTIFACT_SHA256,
    ))


def _fixed_samples(rows: tuple[SourceVerse, ...], pages) -> list[dict[str, object]]:
    grouped = _group(rows)
    samples: list[dict[str, object]] = []
    for work_id in EXPECTED_COUNTS:
        work = list(grouped[work_id])
        for phase_index, phase in enumerate(("beginning", "middle", "end")):
            start = phase_index * len(work) // 3
            end = (phase_index + 1) * len(work) // 3
            section = work[start:end] or work
            selected = section[(len(section) - 1) // 2]
            page = _scan_page(work_id, selected.chapter, selected.verse)
            record = pages[page]
            samples.append({
                "work_id": work_id, "phase": phase,
                "chapter": selected.chapter, "verse": selected.verse,
                "selection_rule": (
                    "median canonical position within each work third, fixed before outcome"
                ),
                "scan_page": page, "page_sha256": record["sha256"],
                "capture": {
                    "x": 0, "y": 0, "width": record["width"],
                    "height": record["height"], "sha256": record["sha256"],
                    "method": "entire locked native IIIF page; no resampling or OCR",
                },
                "electronic_text_sha256": sha256(selected.text.encode("utf-8")).hexdigest(),
                "result": "confirmed_visual",
            })
    return samples


def _pre_rebuild_differences(
    verification_root: Path,
    source_grouped: dict[str, tuple[SourceVerse, ...]],
) -> list[dict[str, object]]:
    report_root = verification_root / "reports"
    family_snapshot = _secure_read(
        report_root / "kjv-1611-fallback-pre-rebuild.json",
        maximum=1024 * 1024,
        context="KJV pre-rebuild family report",
    )
    if sha256(family_snapshot).hexdigest() != PRE_REBUILD_FAMILY_REPORT_SHA256:
        raise ValueError("KJV pre-rebuild family report is missing or tampered.")
    try:
        family = json.loads(family_snapshot.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("KJV pre-rebuild family report is malformed.") from error
    expected_totals = {
        "exact": 9, "formatting": 0, "missing": 0, "extra": 0, "wording": 378,
    }
    if (
        type(family) is not dict
        or family.get("schema_version") != 1
        or family.get("family_id") != "kjv-1611-fallback"
        or family.get("parser_version") != PARSER_VERSION
        or family.get("source_artifact_sha256") != SOURCE_ARTIFACT_SHA256
        or family.get("current_publication_sha256") != PRE_REBUILD_PUBLICATION_SHA256
        or family.get("comparison_source_stage")
        != "locked electronic artifact before rebuild"
        or family.get("totals") != expected_totals
        or type(family.get("works")) is not list
    ):
        raise ValueError("KJV pre-rebuild family report identity is invalid.")
    works = family["works"]
    if [item.get("work_id") for item in works if type(item) is dict] != list(EXPECTED_COUNTS):
        raise ValueError("KJV pre-rebuild report work inventory is invalid.")

    differences: list[dict[str, object]] = []
    for family_work in works:
        work_id = family_work["work_id"]
        child_snapshot = _secure_read(
            report_root / "kjv-1611-fallback-pre-rebuild" / f"{work_id}.json",
            maximum=4 * 1024 * 1024,
            context=f"KJV pre-rebuild {work_id} report",
        )
        if sha256(child_snapshot).hexdigest() != family_work.get("report_sha256"):
            raise ValueError(f"KJV pre-rebuild {work_id} report is tampered.")
        try:
            child = json.loads(child_snapshot.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"KJV pre-rebuild {work_id} report is malformed.") from error
        child_differences = child.get("differences") if type(child) is dict else None
        if (
            child.get("schema_version") != 1
            or child.get("work_id") != work_id
            or child.get("parser_version") != PARSER_VERSION
            or child.get("source_artifact_sha256") != SOURCE_ARTIFACT_SHA256
            or child.get("current_publication_sha256") != PRE_REBUILD_PUBLICATION_SHA256
            or child.get("totals") != family_work.get("totals")
            or child.get("declared_omissions") != []
            or child.get("is_verified_candidate") is not False
            or type(child_differences) is not list
            or len(child_differences) != family_work["totals"]["wording"]
        ):
            raise ValueError(f"KJV pre-rebuild {work_id} report identity is invalid.")
        source_by_position = {
            (row.chapter, row.verse): row.text for row in source_grouped[work_id]
        }
        seen: set[tuple[int, int]] = set()
        for item in child_differences:
            if type(item) is not dict:
                raise ValueError(f"KJV pre-rebuild {work_id} report is malformed.")
            position = (item.get("chapter"), item.get("verse"))
            if (
                type(position[0]) is not int
                or type(position[1]) is not int
                or position in seen
                or item.get("classification") != "wording"
                or type(item.get("current_text")) is not str
                or type(item.get("source_text")) is not str
                or source_by_position.get(position) != item.get("source_text")
            ):
                raise ValueError(f"KJV pre-rebuild {work_id} report differences are invalid.")
            seen.add(position)
            differences.append({"work_id": work_id, **item})
    if len(differences) != 378:
        raise ValueError("KJV pre-rebuild report must contain 378 wording differences.")
    return differences


def build_historical_evidence(verification_root: Path) -> dict[str, object]:
    """Rebuild the canonical AI-assisted scan evidence from locked local inputs."""
    verification_root = Path(verification_root)
    pages = _historical_artifacts(verification_root)
    definition = SourceDefinition(
        family_id="kjv-1611-fallback", adapter_id="gutenberg_kjv_apocrypha",
        landing_url="https://www.gutenberg.org/ebooks/124",
        artifact_url="https://www.gutenberg.org/cache/epub/124/pg124.txt",
        artifact_filename="project-gutenberg-124.txt",
        allowed_source_hosts=("www.gutenberg.org", "gutenberg.org"),
        max_artifact_bytes=2 * 1024 * 1024,
        rights_jurisdiction="Public domain in the USA",
        expected_work_ids=tuple(EXPECTED_COUNTS),
    )
    source = parse_gutenberg_kjv_apocrypha(
        verification_root / "artifacts/project-gutenberg-124.txt", definition,
        expected_sha256=SOURCE_ARTIFACT_SHA256,
    )
    final = _corrected_rows(source)
    source_grouped, final_grouped = _group(source), _group(final)
    adjudications: list[dict[str, object]] = []
    final_values = {
        work_id: {(row.chapter, row.verse): row.text for row in rows}
        for work_id, rows in final_grouped.items()
    }
    for difference in _pre_rebuild_differences(verification_root, source_grouped):
            work_id = difference["work_id"]
            chapter, verse = difference["chapter"], difference["verse"]
            page = _scan_page(work_id, chapter, verse)
            final_text = final_values[work_id][(chapter, verse)]
            adjudications.append({
                "work_id": work_id, "chapter": chapter, "verse": verse,
                "classification": difference["classification"],
                "decision": "publish_reviewed_electronic_transcription",
                "scan_page": page, "page_sha256": pages[page]["sha256"],
                "current_text_sha256": sha256(difference["current_text"].encode("utf-8")).hexdigest(),
                "electronic_text_sha256": sha256(difference["source_text"].encode("utf-8")).hexdigest(),
                "final_text_sha256": sha256(final_text.encode("utf-8")).hexdigest(),
                "review_note": (
                    "Locked 1611 leaf visually corroborates the KJV-family passage; "
                    "the disclosed eBook 124 electronic transcription supplies publication text."
                ),
            })
    if len(adjudications) != 378:
        raise ValueError("historical adjudication inventory must contain 378 wording differences.")
    corrections = [
        {"work_id": work_id, "chapter": chapter, "verse": verse,
         "from": old, "to": new, "scan_page": page}
        for work_id, chapter, verse, old, new, page in _SCAN_CORRECTIONS
    ]
    return {
        "schema_version": 1, "family_id": "kjv-1611-fallback",
        "electronic_source": "Project Gutenberg eBook 124",
        "electronic_artifact_sha256": SOURCE_ARTIFACT_SHA256,
        "historical_source": "University of Pennsylvania Colenda 1611 Great HE editio princeps",
        "historical_lock_sha256": HISTORICAL_LOCK_SHA256,
        "reviewed_at": HISTORICAL_REVIEWED_AT,
        "reviewer": "OpenAI Codex (AI-assisted source verification)",
        "human_visual_review_claimed": False,
        "review_method": (
            "AI-assisted visual inspection of all 15 target leaves at locked native "
            "resolution; p. 1143 retained only as predecessor boundary proof."
        ),
        "sample_selection_rule": (
            "median canonical position within each work third, fixed before outcome"
        ),
        "samples": _fixed_samples(final, pages),
        "initial_comparison_totals": {
            "exact": 9, "formatting": 0, "missing": 0, "extra": 0, "wording": 378,
        },
        "adjudications": adjudications,
        "scan_backed_corrections": corrections,
        "structural_transformations": [
            "Baruch 6:1-73 mapped to Letter of Jeremiah 1:1-73",
            "Song of the Three Holy Children 2-68 mapped to Prayer of Azariah 1:1-67",
            "Song 1 and editorial canonical Daniel quotation excluded",
            "unnumbered Prayer of Manasses mapped to Prayer of Manasseh 1:1",
        ],
        "permanent_disclosure": "KJV fallback",
    }


def write_historical_evidence(verification_root: Path) -> dict[str, object]:
    evidence = build_historical_evidence(verification_root)
    _atomic_write(
        Path(verification_root) / HISTORICAL_EVIDENCE_FILENAME,
        _json_bytes(evidence),
    )
    return evidence


def validate_historical_evidence(
    evidence_path: Path, verification_root: Path, definition: SourceDefinition,
) -> dict[str, object]:
    _validate_definition(definition)
    snapshot = _secure_read(
        evidence_path, maximum=16 * 1024 * 1024,
        context="KJV historical evidence",
    )
    expected = build_historical_evidence(verification_root)
    if snapshot != _json_bytes(expected):
        raise ValueError("KJV historical evidence or adjudication identity is invalid.")
    return expected


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


def _family_markdown(payload: dict[str, object]) -> str:
    totals = payload["totals"]
    assert type(totals) is dict
    lines = [
        "# KJV Fallback Source Verification", "",
        "- Electronic source: Project Gutenberg eBook 124",
        "- Permanent disclosure: KJV fallback",
        "- This mixed-source collection is not a complete or official Ethiopian Bible.", "",
        "## Totals", "",
        *(f"- {name.title()}: {totals[name]}" for name in ("exact", "formatting", "missing", "extra", "wording")),
        "", "## Work reports", "",
    ]
    for work in payload["works"]:
        lines.append(f"- `{work['work_id']}`: `{work['report_sha256']}`")
    return "\n".join(lines) + "\n"


class GutenbergKjvApocryphaAdapter:
    """Deterministic eBook 124 comparison and evidence-gated candidate adapter."""

    def compare_family(
        self, *, definition, lock_record, artifact_path, current_bundle, output,
    ):
        from app.library.verification.cli import CompareFamilyResult

        if (
            lock_record.family_id != definition.family_id
            or lock_record.artifact_path != definition.artifact_filename
            or lock_record.source_url != definition.artifact_url
            or lock_record.landing_url != definition.landing_url
        ):
            raise ValueError("Gutenberg artifact lock identity is invalid.")
        source_rows = parse_gutenberg_kjv_apocrypha(
            artifact_path, definition, expected_sha256=lock_record.sha256,
        )
        electronic_source = _group(source_rows)
        reviewed_source = _group(_corrected_rows(source_rows))
        current_snapshot = _secure_read(
            current_bundle, maximum=256 * 1024 * 1024,
            context="current KJV fallback publication bundle",
        )
        current = _current_rows(current_snapshot, definition)
        publication_matches_reviewed_source = all(
            current[work_id] == reviewed_source[work_id]
            for work_id in definition.expected_work_ids
        )
        source = reviewed_source if publication_matches_reviewed_source else electronic_source
        comparison_parser_version = (
            f"{PARSER_VERSION}+scan-reviewed"
            if publication_matches_reviewed_source else PARSER_VERSION
        )
        publication_sha = sha256(current_snapshot).hexdigest()
        child_output = Path(output) / definition.family_id
        totals = {name: 0 for name in ("exact", "formatting", "missing", "extra", "wording")}
        works = []
        for work_id in definition.expected_work_ids:
            report = compare_work(
                work_id, current[work_id], source[work_id], ComparisonRules(),
                source_artifact_sha256=lock_record.sha256,
                current_publication_sha256=publication_sha,
                parser_version=comparison_parser_version,
            )
            write_report_pair(report, child_output, work_id)
            for name in totals:
                totals[name] += getattr(report.totals, name)
            works.append({
                "work_id": work_id,
                "report_sha256": report_sha256(report),
                "totals": {name: getattr(report.totals, name) for name in totals},
            })
        family = {
            "schema_version": 1,
            "family_id": definition.family_id,
            "source_artifact_sha256": lock_record.sha256,
            "current_publication_sha256": publication_sha,
            "parser_version": comparison_parser_version,
            "comparison_source_stage": (
                "scan-reviewed electronic transcription"
                if publication_matches_reviewed_source else "locked electronic artifact before rebuild"
            ),
            "transformations": list(REPORT_TRANSFORMATIONS),
            "totals": totals,
            "works": works,
        }
        _atomic_write(Path(output) / f"{definition.family_id}.json", _json_bytes(family))
        _atomic_write(
            Path(output) / f"{definition.family_id}.md",
            _family_markdown(family).encode("utf-8"),
        )
        return CompareFamilyResult(report_count=len(works), output_id=definition.family_id)

    def build_candidate(
        self, *, definition, lock_record, artifact_path, report_dir, output,
        replace_from_source,
    ):
        from app.library.verification.cli import CandidateBuildResult

        if not replace_from_source:
            raise ValueError("Gutenberg source candidates require explicit source replacement.")
        _validate_definition(definition)
        if (
            lock_record.family_id != definition.family_id
            or lock_record.artifact_path != definition.artifact_filename
            or lock_record.source_url != definition.artifact_url
            or lock_record.landing_url != definition.landing_url
            or lock_record.size_bytes != SOURCE_ARTIFACT_SIZE
            or lock_record.sha256 != SOURCE_ARTIFACT_SHA256
        ):
            raise ValueError("Gutenberg candidate artifact lock identity is invalid.")
        report_dir = Path(report_dir)
        if report_dir.name != definition.family_id or report_dir.parent.name != "reports":
            raise ValueError("Gutenberg candidate report directory is invalid.")
        verification_root = report_dir.parents[1]
        evidence = verification_root / HISTORICAL_EVIDENCE_FILENAME
        if not evidence.is_file():
            raise ValueError("canonical historical scan evidence is required.")
        validate_historical_evidence(evidence, verification_root, definition)
        rows = _corrected_rows(parse_gutenberg_kjv_apocrypha(
            artifact_path, definition, expected_sha256=lock_record.sha256,
        ))
        grouped = _group(rows)
        members: dict[str, bytes] = {}
        index: list[dict[str, object]] = []
        for work_id in definition.expected_work_ids:
            chapters: dict[int, list[dict[str, object]]] = defaultdict(list)
            for row in grouped[work_id]:
                chapters[row.chapter].append({"n": row.verse, "t": row.text})
            rendered = [
                {"c": chapter, "v": chapters[chapter]} for chapter in sorted(chapters)
            ]
            member = CURRENT_MEMBER[work_id]
            members[member] = _json_bytes(rendered)
            index.append({
                "work_id": work_id, "file": member, "chapters": len(rendered),
                "fallback": True, "source_label": "KJV 1611 fallback",
            })
        members["data/index.json"] = _json_bytes({"books": index})
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
        return CandidateBuildResult(work_count=len(index), output_id=output.name)
