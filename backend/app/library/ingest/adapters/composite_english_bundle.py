"""Strict adapter for a reviewed composite English scripture bundle."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
import unicodedata
from zipfile import BadZipFile, ZipFile, ZipInfo

from app.library.ingest.manifest import (
    CompositeEnglishBundleAdapterOptions,
    SourceManifest,
)
from app.library.ingest.normalize import normalize_verse
from app.library.ingest.types import NormalizedVerse


_INDEX_MEMBER = "data/index.json"
_MAX_ARCHIVE_MEMBERS = 1_024
_MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
_SOURCE_KEYS = {
    "wmb": "world-messianic-bible",
    "peshitta": "murdock-peshitta-1852",
    "web_apocrypha": "world-english-bible-apocrypha",
    "kjv_apocrypha": "kjv-1611-fallback",
    "meqabyan": "wikisource-meqabyan-geez",
    "extra": "rh-charles-ethiopic",
}
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def _file_checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_locator_normalization_stable(value: str) -> bool:
    return value == " ".join(unicodedata.normalize("NFC", value).split())


def _safe_relative_path(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a nonempty relative POSIX path.")
    path = PurePosixPath(value)
    if (
        value.startswith(("/", "\\"))
        or _DRIVE_PREFIX.match(value)
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or path.is_absolute()
    ):
        raise ValueError(f"{label} contains an unsafe source file path.")
    if not _is_locator_normalization_stable(value):
        raise ValueError(f"{label} must be normalization-stable.")
    return value


def _is_safe_member(info: ZipInfo) -> bool:
    name = info.filename
    unix_mode = info.external_attr >> 16
    try:
        _safe_relative_path(name, label="archive member")
    except ValueError:
        return False
    return not stat.S_ISLNK(unix_mode) and not (info.flag_bits & 0x1)


def _validated_archive(path: Path) -> ZipFile:
    try:
        archive = ZipFile(path)
    except (BadZipFile, OSError) as error:
        raise ValueError(f"invalid source archive: {path.name}") from error

    try:
        infos = archive.infolist()
        if len(infos) > _MAX_ARCHIVE_MEMBERS:
            raise ValueError("source archive contains too many members.")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("source archive contains a duplicate archive member filename.")
        if any(not _is_safe_member(info) for info in infos):
            raise ValueError("source archive contains an unsafe archive member.")
        if sum(info.file_size for info in infos) > _MAX_UNCOMPRESSED_BYTES:
            raise ValueError("source archive exceeds the uncompressed size limit.")
    except Exception:
        archive.close()
        raise
    return archive


def _read_json(archive: ZipFile, member: str) -> Any:
    try:
        encoded = archive.read(member)
    except KeyError as error:
        raise ValueError(f"missing required archive member: {member}") from error
    except (BadZipFile, OSError, RuntimeError) as error:
        raise ValueError(f"cannot read source archive member: {member}") from error
    try:
        return json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid UTF-8 JSON archive member: {member}") from error


def _strict_positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer.")
    return value


def _chapter_number(value: object) -> int:
    if type(value) is int:
        if value > 0:
            return value
    elif type(value) is str and re.fullmatch(r"[1-9][0-9]*", value):
        return int(value)
    raise ValueError("chapter number must be a positive integer or canonical decimal string.")


def _book_member(record: dict[str, Any]) -> str:
    member = _safe_relative_path(record.get("file"), label="indexed book")
    if not member.startswith("data/"):
        raise ValueError("indexed book source file must already begin with data/.")
    return member


def _validate_index(
    index: object, options: CompositeEnglishBundleAdapterOptions
) -> dict[str, dict[str, Any]]:
    if not isinstance(index, dict):
        raise ValueError("bundle index must contain a JSON object.")
    books = index.get("books")
    if not isinstance(books, list):
        raise ValueError("bundle index must contain a books list.")

    by_id: dict[str, dict[str, Any]] = {}
    populated: set[str] = set()
    for record in books:
        if not isinstance(record, dict):
            raise ValueError("bundle index contains an invalid book record.")
        source_id = record.get("id")
        if type(source_id) is not str or not source_id.strip():
            raise ValueError("bundle index book id must be a nonblank string.")
        identity = source_id.strip().casefold()
        if identity in by_id:
            raise ValueError(f"bundle index contains duplicate book id {source_id!r}.")
        by_id[identity] = record

        file_value = record.get("file")
        if file_value is not None and file_value != "":
            populated.add(identity)
            continue
        if (
            record.get("src") not in (None, "")
            or type(record.get("chapters")) is not int
            or record.get("chapters") != 0
        ):
            raise ValueError(f"bundle index contains malformed placeholder {source_id!r}.")

    mapped = {source_id.casefold() for source_id in options.book_map}
    missing = mapped - populated
    if missing:
        source_id = next(key for key in options.book_map if key.casefold() in missing)
        raise ValueError(f"bundle index is missing mapped book {source_id!r}.")
    unexpected = populated - mapped
    if unexpected:
        record = by_id[next(iter(unexpected))]
        raise ValueError(f"bundle index contains unexpected populated book {record['id']!r}.")
    return by_id


def _rows_for_book(
    *,
    archive: ZipFile,
    archive_name: str,
    record: dict[str, Any],
    work_id: str,
    expected_source_key: str,
) -> list[NormalizedVerse]:
    source_id = record["id"]
    source_book = record.get("name")
    if type(source_book) is not str or not source_book.strip():
        raise ValueError(f"book {source_id!r} has no nonblank source name.")
    member = _book_member(record)
    chapter_count = _strict_positive_integer(record.get("chapters"), "index chapters")
    source_family = record.get("src")
    if type(source_family) is not str or not source_family or source_family not in _SOURCE_KEYS:
        raise ValueError(f"book {source_id!r} has an unknown source family.")
    if _SOURCE_KEYS[source_family] != expected_source_key:
        raise ValueError(
            f"book {source_id!r} source family does not match its manifest work source."
        )

    book = _read_json(archive, member)
    if not isinstance(book, list):
        raise ValueError(f"book archive member must contain a JSON list: {member}")

    chapters: dict[int, dict[str, Any]] = {}
    for chapter_record in book:
        if not isinstance(chapter_record, dict):
            raise ValueError(f"book {source_id!r} contains an invalid chapter record.")
        chapter = _chapter_number(chapter_record.get("c"))
        if chapter in chapters:
            raise ValueError(f"book {source_id!r} contains duplicate chapter {chapter}.")
        chapters[chapter] = chapter_record
    if len(chapters) != chapter_count:
        raise ValueError(f"book {source_id!r} chapter count does not match its index record.")
    if set(chapters) != set(range(1, chapter_count + 1)):
        raise ValueError(f"book {source_id!r} chapters must be contiguous from 1.")

    rows: list[NormalizedVerse] = []
    for chapter in range(1, chapter_count + 1):
        verse_records = chapters[chapter].get("v")
        if not isinstance(verse_records, list) or not verse_records:
            raise ValueError(f"book {source_id!r} chapter {chapter} has no verses.")
        verses: dict[int, dict[str, Any]] = {}
        for verse_record in verse_records:
            if not isinstance(verse_record, dict):
                raise ValueError("book contains an invalid verse record.")
            verse = _strict_positive_integer(verse_record.get("n"), "verse number")
            if verse in verses:
                raise ValueError(
                    f"book {source_id!r} chapter {chapter} contains duplicate verse {verse}."
                )
            verses[verse] = verse_record
        if set(verses) != set(range(1, len(verses) + 1)):
            raise ValueError(
                f"book {source_id!r} chapter {chapter} verses must be contiguous from 1."
            )
        for verse in range(1, len(verses) + 1):
            locator = f"{archive_name}!/{member}#{chapter}:{verse}"
            row = normalize_verse(
                source_book,
                chapter,
                verse,
                verses[verse].get("t"),
                locator,
            )
            if row.source_locator != locator:
                raise ValueError("source locator must remain exact after normalization.")
            if row.work_id != work_id:
                raise ValueError(
                    f"book {source_id!r} resolved to {row.work_id!r}, expected {work_id!r}."
                )
            rows.append(row)
    return rows


def parse_composite_english_bundle(
    manifest: SourceManifest, manifest_directory: Path
) -> tuple[NormalizedVerse, ...]:
    """Read only explicitly mapped books from one checksummed ZIP source."""
    options = manifest.adapter_options
    if manifest.adapter != "composite_english_bundle" or not isinstance(
        options, CompositeEnglishBundleAdapterOptions
    ):
        raise ValueError("manifest does not contain composite_english_bundle adapter options.")
    if len(manifest.source_files) != 1:
        raise ValueError("composite_english_bundle requires exactly one source archive.")
    if set(options.book_map.values()) != set(manifest.expected_works):
        raise ValueError("book_map targets must exactly match expected_works keys.")

    source = manifest.source_files[0]
    if not _is_locator_normalization_stable(source.path):
        raise ValueError("source archive path must be normalization-stable.")
    manifest_root = manifest_directory.resolve()
    archive_path = manifest_directory / source.path
    if (
        archive_path.is_symlink()
        or not archive_path.is_file()
        or not archive_path.resolve().is_relative_to(manifest_root)
    ):
        raise ValueError(
            "source archive must be a regular file inside the manifest directory: "
            f"{source.path}"
        )
    if _file_checksum(archive_path) != source.sha256:
        raise ValueError(f"source archive checksum does not match manifest: {source.path}")

    with _validated_archive(archive_path) as archive:
        by_id = _validate_index(_read_json(archive, _INDEX_MEMBER), options)
        rows: list[NormalizedVerse] = []
        for source_id, work_id in options.book_map.items():
            record = by_id[source_id.casefold()]
            rows.extend(_rows_for_book(
                archive=archive,
                archive_name=source.path,
                record=record,
                work_id=work_id,
                expected_source_key=options.work_sources[work_id].source_key,
            ))
    return tuple(rows)
