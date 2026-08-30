"""Strict, dependency-free reader for CrossWire's Murdock SWORD module."""

from __future__ import annotations

from collections import defaultdict
import difflib
from hashlib import sha1, sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tempfile
import xml.etree.ElementTree as ET
import zlib
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from app.library.verification.compare import compare_work
from app.library.verification.registry import SourceDefinition
from app.library.verification.report import report_json_bytes, report_sha256, write_report_pair
from app.library.verification.types import ComparisonCounts, ComparisonRules, SourceVerse, VersePosition


PARSER_VERSION = "murdock-sword/1"
MODULE_VERSION = "1.2"
MODULE_CONF_SHA256 = "f0791130aa0409b0a49710e08733f21fa5b6d53149f4dac3285d12e70e405178"
MODULE_CONF_SIZE = 646
SOURCE_ARTIFACT_SHA256 = "4f0adeba385acbfa37921f66677d4aaf99e23b4e65ca162f122832689036641f"
PRE_REBUILD_PUBLICATION_SHA256 = "370d680b248d935d7b6e4217f10124d58c918b5d0f80a83af422b82fbf3370a9"
PRE_REBUILD_FAMILY_SHA256 = "a74cd77bddd3532ff34afcaae87d6784fa7a420695049c4b5f664e7b05683c6e"
HISTORICAL_EVIDENCE_FILENAME = "murdock-peshitta-1852-historical-samples.json"
HISTORICAL_LOCK_FILENAME = "murdock-historical-artifacts.lock.json"
VISUAL_REVIEW_FILENAME = "murdock-peshitta-1852-visual-review.json"
VISUAL_REVIEW_SHA256 = "d36071bc290300cde201af82cb88390f2317ea439989294aaf9a5dfb311b9960"
VISUAL_REVIEWER = "OpenAI Codex (AI-assisted source verification)"
VISUAL_REVIEWED_AT = "2026-08-29T19:56:29Z"
HISTORICAL_EDITION_NOTE = (
    "The locked 1915 ninth edition is historical corroboration for James "
    "Murdock's translation, first published in 1852; it is not represented "
    "as an 1852 scan."
)

_HISTORICAL_ARTIFACTS = (
    (
        "historical_scan", "syriacnewtestam00murdgoog.djvu", 25_984_230,
        "8777ab6536ba7242e017b0aca426858c85fa791ba5d1ed601f93c069a5775f9e",
        "7c9b8edcd7b292d6823bb8651fe6c73352e9168b",
        "https://archive.org/download/syriacnewtestam00murdgoog/syriacnewtestam00murdgoog.djvu",
        "https://archive.org/details/syriacnewtestam00murdgoog",
        "2026-08-29T09:31:34Z",
    ),
    (
        "ocr_plain_text_derivative", "syriacnewtestam00murdgoog_djvu.txt",
        1_572_696,
        "cf6177896ffd5c4fe882650115bef249574d583ddeca12dbf2b1a16583104751",
        "9d6c20db9df8f1a0a090667f21427d63dc809349",
        "https://archive.org/download/syriacnewtestam00murdgoog/syriacnewtestam00murdgoog_djvu.txt",
        "https://archive.org/details/syriacnewtestam00murdgoog",
        "2026-08-29T06:02:27Z",
    ),
    (
        "scan_leaf_mapping_derivative", "syriacnewtestam00murdgoog_scandata.xml",
        188_168,
        "0ba6968c1a4995dec7e432ead7bf4bd77bf78e34abbca4845795ebb4a5d67fa3",
        "3ffb73016d32b6d401e350550f29a92030a2f27e",
        "https://archive.org/download/syriacnewtestam00murdgoog/syriacnewtestam00murdgoog_scandata.xml",
        "https://archive.org/details/syriacnewtestam00murdgoog",
        "2026-08-29T06:02:46Z",
    ),
    (
        "page_structured_ocr_derivative", "syriacnewtestam00murdgoog_djvu.xml",
        20_240_247,
        "a6ba38a2e524e3c64e5713f51c0fcf2940d4cc1ba9262cf22b1c5fad26b99639",
        "13a2fe38fd6d5bfa46e0dbaf54916ef20a108c7f",
        "https://archive.org/download/syriacnewtestam00murdgoog/syriacnewtestam00murdgoog_djvu.xml",
        "https://archive.org/details/syriacnewtestam00murdgoog",
        "2026-08-29T07:12:51Z",
    ),
    (
        "visual_pdf_derivative", "syriacnewtestam00murdgoog.pdf", 16_716_405,
        "be4d1425fe69b4ff24fa418e15a2a2fbfb924db50d7e06861a937cfd3c81bc05",
        "76b33ccd3a0d80d6aeb8e7f56a2be80ae0732257",
        "https://archive.org/download/syriacnewtestam00murdgoog/syriacnewtestam00murdgoog.pdf",
        "https://archive.org/details/syriacnewtestam00murdgoog",
        "2026-08-29T18:44:41Z",
    ),
)

# First scan leaf for each work, plus the leaf after Revelation.  Boundary
# leaves can contain the preceding work's ending and the next work's heading.
_WORK_LEAF_BOUNDARIES = (
    53, 113, 151, 216, 264, 329, 354, 379, 395, 403, 411, 417, 423,
    428, 431, 438, 443, 446, 447, 466, 472, 479, 483, 490, 491, 492,
    494, 524,
)

CONF_MEMBER = "mods.d/murdock.conf"
MODULE_ROOT = "modules/texts/ztext/murdock/"
REVIEWED_MEMBERS = frozenset({
    CONF_MEMBER,
    f"{MODULE_ROOT}errata",
    f"{MODULE_ROOT}nt.bzv",
    f"{MODULE_ROOT}nt.bzs",
    f"{MODULE_ROOT}nt.bzz",
    f"{MODULE_ROOT}appendix",
})
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200

SOURCE_CODE_TO_WORK_ID = {
    "MAT": "matthew", "MRK": "mark", "LUK": "luke", "JHN": "john",
    "ACT": "acts", "ROM": "romans", "1CO": "1-corinthians",
    "2CO": "2-corinthians", "GAL": "galatians", "EPH": "ephesians",
    "PHP": "philippians", "COL": "colossians",
    "1TH": "1-thessalonians", "2TH": "2-thessalonians",
    "1TI": "1-timothy", "2TI": "2-timothy", "TIT": "titus",
    "PHM": "philemon", "HEB": "hebrews", "JAS": "james",
    "1PE": "1-peter", "2PE": "2-peter", "1JN": "1-john",
    "2JN": "2-john", "3JN": "3-john", "JUD": "jude",
    "REV": "revelation",
}

# The reviewed KJV-versification structure used by this version-1.2 module.
# These immutable counts account for 7,957 canonical New Testament positions.
CHAPTER_VERSE_COUNTS = {
    "MAT": (25,23,17,25,48,34,29,34,38,42,30,50,58,36,39,28,27,35,30,34,46,46,39,51,46,75,66,20),
    "MRK": (45,28,35,41,43,56,37,38,50,52,33,44,37,72,47,20),
    "LUK": (80,52,38,44,39,49,50,56,62,42,54,59,35,35,32,31,37,43,48,47,38,71,56,53),
    "JHN": (51,25,36,54,47,71,53,59,41,42,57,50,38,31,27,33,26,40,42,31,25),
    "ACT": (26,47,26,37,42,15,60,40,43,48,30,25,52,28,41,40,34,28,41,38,40,30,35,27,27,32,44,31),
    "ROM": (32,29,31,25,21,23,25,39,33,21,36,21,14,23,33,27),
    "1CO": (31,16,23,21,13,20,40,13,27,33,34,31,13,40,58,24),
    "2CO": (24,17,18,18,21,18,16,24,15,18,33,21,14),
    "GAL": (24,21,29,31,26,18), "EPH": (23,22,21,32,33,24),
    "PHP": (30,30,21,23), "COL": (29,23,25,18),
    "1TH": (10,20,13,18,28), "2TH": (12,17,18),
    "1TI": (20,15,16,16,25,21), "2TI": (18,26,17,22),
    "TIT": (16,15,15), "PHM": (25,),
    "HEB": (14,18,19,16,14,20,28,13,28,39,40,29,25),
    "JAS": (27,26,18,17,20), "1PE": (25,25,22,19,14),
    "2PE": (21,22,18), "1JN": (10,29,24,21,21),
    "2JN": (13,), "3JN": (14,), "JUD": (25,),
    "REV": (20,29,22,11,14,17,17,13,21,11,19,17,18,20,8,21,18,24,21,15,27,21),
}

DECLARED_OMISSIONS = {
    "matthew": ((26, 30), (26, 45)),
    "mark": ((4, 10), (8, 19), (9, 31), (11, 19)),
    "luke": ((18, 35),),
    "acts": ((19, 41), (20, 17)),
    "2-corinthians": ((13, 14),),
}
_DECLARED_OMISSION_SET = {
    (work_id, chapter, verse)
    for work_id, positions in DECLARED_OMISSIONS.items()
    for chapter, verse in positions
}
_PHILEMON_SPILL = re.compile(r"philemon1:01 ([^\x00]+)\Z")
_RF = re.compile(r"<RF>.*?<Rf>", re.DOTALL)
_ANY_TAG = re.compile(r"<[^>]*>")


def clean_murdock_text(value: str) -> str:
    """Apply only the reviewed GBF apparatus and U+000F transformations."""
    if type(value) is not str or not value:
        raise ValueError("Murdock source text must be a nonempty string.")
    if value.count("<RF>") != value.count("<Rf>"):
        raise ValueError("Murdock RF apparatus is unbalanced.")
    value = _RF.sub(" ", value)
    if "<RF>" in value or "<Rf>" in value:
        raise ValueError("Murdock RF apparatus is unbalanced.")
    # FI/Fi are stateful presentation delimiters in this legacy GBF source;
    # CrossWire has four more closing than opening delimiters and some pairs
    # cross verse boundaries, so each delimiter is intentionally stripped.
    value = value.replace("<FI>", "").replace("<Fi>", "")
    if _ANY_TAG.search(value):
        raise ValueError("Murdock source contains unexpected GBF apparatus.")
    value = re.sub(r"[ \t]*\x0f[ \t]*", " ", value)
    value = re.sub(r"[ \t]{2,}", " ", value).strip()
    if not value:
        raise ValueError("Murdock source text became blank after apparatus cleanup.")
    return value


def _validate_member(info: ZipInfo) -> None:
    pure = PurePosixPath(info.filename)
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if (
        info.filename not in REVIEWED_MEMBERS
        or pure.is_absolute()
        or "\\" in info.filename
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError("Murdock archive must contain the exact reviewed member set.")
    if info.flag_bits & 1:
        raise ValueError("encrypted Murdock ZIP members are forbidden.")
    if info.is_dir() or file_type not in (0, stat.S_IFREG):
        raise ValueError("Murdock ZIP members must be regular files.")
    if info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
        raise ValueError("Murdock ZIP member compression is unsupported.")
    if not 0 < info.file_size <= MAX_MEMBER_BYTES:
        raise ValueError("Murdock ZIP member exceeds its reviewed size limit.")
    if info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO:
        raise ValueError("Murdock ZIP member exceeds its compression ratio limit.")


def _secure_read(path: Path, *, maximum: int, context: str) -> bytes:
    """Read one stable regular-file snapshot without following replacements."""
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
            not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(opened.st_mode)
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
            raise ValueError(f"{context} exceeds its secure snapshot size.")
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


def _read_archive_bytes(snapshot: bytes, definition: SourceDefinition) -> dict[str, bytes]:
    if type(definition) is not SourceDefinition or definition.adapter_id != "murdock_sword":
        raise ValueError("definition must select the Murdock SWORD adapter.")
    if tuple(SOURCE_CODE_TO_WORK_ID.values()) != definition.expected_work_ids:
        raise ValueError("definition must contain the exact approved Murdock work inventory.")
    try:
        with ZipFile(BytesIO(snapshot)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (
                len(infos) != len(REVIEWED_MEMBERS)
                or len(set(names)) != len(names)
                or set(names) != REVIEWED_MEMBERS
            ):
                raise ValueError("Murdock archive must contain the exact reviewed member set.")
            if sum(info.file_size for info in infos) > MAX_TOTAL_BYTES:
                raise ValueError("Murdock archive exceeds its total uncompressed size limit.")
            payloads: dict[str, bytes] = {}
            for info in infos:
                _validate_member(info)
                payload = archive.read(info)
                if len(payload) != info.file_size:
                    raise ValueError("Murdock ZIP member size changed while reading.")
                payloads[info.filename] = payload
    except BadZipFile as error:
        raise ValueError("Murdock artifact must be a valid ZIP archive.") from error
    return payloads


def _validate_conf(payload: bytes) -> None:
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("Murdock module identity configuration must be ASCII.") from error
    lines = text.splitlines()
    keys = [line.split("=", 1)[0] for line in lines[1:] if "=" in line]
    if len(keys) != len(set(keys)):
        raise ValueError("Murdock module configuration contains duplicate keys.")
    if (
        len(payload) != MODULE_CONF_SIZE
        or sha256(payload).hexdigest() != MODULE_CONF_SHA256
        or lines[0:1] != ["[Murdock]"]
    ):
        raise ValueError(
            "Murdock module identity, Version, or canonical configuration changed."
        )


def _bounded_decompress(payload: bytes, expected_size: int) -> bytes:
    if not 0 < expected_size <= MAX_MEMBER_BYTES:
        raise ValueError("Murdock compressed block output size exceeds its limit.")
    try:
        stream = zlib.decompressobj()
        block = stream.decompress(payload, expected_size + 1)
        if len(block) > expected_size:
            raise ValueError("Murdock compressed block output exceeds its declared size.")
        remaining = expected_size - len(block)
        block += stream.flush(remaining + 1)
    except zlib.error as error:
        raise ValueError("Murdock compressed block is invalid.") from error
    if (
        len(block) != expected_size or not stream.eof
        or stream.unused_data or stream.unconsumed_tail
    ):
        raise ValueError("Murdock compressed block size or stream boundary is invalid.")
    return block


def _decompress_blocks(bzs: bytes, bzz: bytes) -> tuple[bytes, ...]:
    if len(bzs) != 27 * 12:
        raise ValueError("Murdock block index size or structure is invalid.")
    blocks: list[bytes] = []
    if bzz[:10] != b"\0" * 10:
        raise ValueError("Murdock compressed text header is not the reviewed 10-byte header.")
    previous_end = 10
    for offset in range(0, len(bzs), 12):
        start, compressed_size, uncompressed_size = struct.unpack_from("<III", bzs, offset)
        if (
            not compressed_size or not uncompressed_size
            or start != previous_end or start + compressed_size > len(bzz)
            or uncompressed_size > MAX_MEMBER_BYTES
        ):
            raise ValueError(
                "Murdock compressed block index is not contiguous or contains a gap."
            )
        payload = bzz[start:start + compressed_size]
        # SWORD zText BOOK blocks reserve exactly 1 KiB of zero padding inside
        # every indexed range. It is structural padding, not part of zlib.
        if len(payload) <= 1024 or payload[-1024:] != b"\0" * 1024:
            raise ValueError("Murdock compressed block padding is invalid.")
        block = _bounded_decompress(payload[:-1024], uncompressed_size)
        blocks.append(block)
        previous_end = start + compressed_size
    if previous_end != len(bzz):
        raise ValueError("Murdock compressed text contains unindexed bytes.")
    return tuple(blocks)


def parse_murdock_sword(
    path: Path, definition: SourceDefinition, *, expected_sha256: str | None = None,
) -> tuple[SourceVerse, ...]:
    """Return all nonblank reviewed positions from CrossWire Murdock 1.2."""
    snapshot = _secure_read(
        path, maximum=definition.max_artifact_bytes, context="Murdock artifact",
    )
    if expected_sha256 is not None and sha256(snapshot).hexdigest() != expected_sha256:
        raise ValueError("Murdock artifact snapshot does not match its lock.")
    return _parse_murdock_snapshot(snapshot, definition)


def _parse_murdock_snapshot(
    snapshot: bytes, definition: SourceDefinition,
) -> tuple[SourceVerse, ...]:
    payloads = _read_archive_bytes(snapshot, definition)
    _validate_conf(payloads[CONF_MEMBER])
    verse_index = payloads[f"{MODULE_ROOT}nt.bzv"]
    if len(verse_index) != 8_246 * 10:
        raise ValueError("Murdock verse index size or structure is invalid.")
    blocks = _decompress_blocks(
        payloads[f"{MODULE_ROOT}nt.bzs"], payloads[f"{MODULE_ROOT}nt.bzz"],
    )
    dagger_positions = [
        (block_number, offset)
        for block_number, block in enumerate(blocks)
        for offset, value in enumerate(block) if value == 0x86
    ]
    if dagger_positions != [(0, 118_088), (0, 118_830)]:
        raise ValueError("Murdock 0x86 dagger markers moved or changed.")
    expected_contexts = (
        b"Greek._ Translator. \x86 In some editions: that we may see, and believe in him.<Rf>",
        b"and we will believe in him. \x86He trusted in God; let him rescue him now",
    )
    if any(context not in blocks[0] for context in expected_contexts):
        raise ValueError("Murdock 0x86 dagger marker context changed.")

    index_position = 2  # module and New Testament introductions
    raw_rows: list[tuple[str, int, int, str]] = []
    source_omissions: set[tuple[str, int, int]] = set()
    spill_values: list[str] = []
    reviewed_pointers: dict[tuple[str, int, int], tuple[int, int, int]] = {}
    if sum(block.count(b"philemon1:01 ") for block in blocks) != 1:
        raise ValueError("Murdock Philemon spill marker must occur exactly once in source bytes.")
    for code, work_id in SOURCE_CODE_TO_WORK_ID.items():
        index_position += 1  # book introduction
        for chapter, verse_count in enumerate(CHAPTER_VERSE_COUNTS[code], 1):
            index_position += 1  # chapter introduction
            for verse in range(1, verse_count + 1):
                block_number, start, size = struct.unpack_from(
                    "<IIH", verse_index, index_position * 10,
                )
                index_position += 1
                if (work_id, chapter, verse) in {
                    ("titus", 2, 15), ("philemon", 1, 1),
                }:
                    reviewed_pointers[(work_id, chapter, verse)] = (
                        block_number, start, size,
                    )
                if block_number >= len(blocks) or start + size > len(blocks[block_number]):
                    raise ValueError("Murdock verse index points outside reviewed blocks.")
                raw = blocks[block_number][start:start + size]
                if not raw:
                    source_omissions.add((work_id, chapter, verse))
                    continue
                try:
                    raw_text = raw.decode("latin-1")
                    # Exactly two reviewed 0x86 bytes mark the Matthew 27:42
                    # dagger footnote (one is inside removed RF apparatus and
                    # one follows the verse). The 1915 ninth edition prints that dagger.
                    # No other Latin-1 byte is reinterpreted.
                    raw_text = raw_text.replace("\x86", "†")
                except UnicodeDecodeError as error:  # pragma: no cover - latin-1 is total
                    raise ValueError("Murdock source text encoding is invalid.") from error
                matches = list(_PHILEMON_SPILL.finditer(raw_text))
                if matches:
                    if (work_id, chapter, verse) != ("colossians", 4, 18):
                        raise ValueError("Murdock Philemon spill marker is at an unexpected position.")
                    if len(matches) != 1:
                        raise ValueError("Murdock Philemon spill marker must be unique.")
                    match = matches[0]
                    spill_values.append(match.group(1))
                    raw_text = raw_text[:match.start()]
                raw_rows.append((work_id, chapter, verse, raw_text))

    if index_position != len(verse_index) // 10:
        raise ValueError("Murdock verse index has an unexpected canonical length.")
    if source_omissions != _DECLARED_OMISSION_SET:
        raise ValueError("Murdock source omissions do not match the ten reviewed positions.")
    if len(spill_values) != 1:
        raise ValueError("Murdock Philemon spill marker must occur exactly once.")
    if (
        reviewed_pointers.get(("philemon", 1, 1))
        != reviewed_pointers.get(("titus", 2, 15))
    ):
        raise ValueError("Murdock Philemon 1:1 must have the reviewed duplicate index pointer.")
    indexed = {
        (work_id, chapter, verse): raw_text
        for work_id, chapter, verse, raw_text in raw_rows
        if (work_id, chapter, verse) in {
            ("titus", 2, 15), ("philemon", 1, 1),
        }
    }
    if (
        indexed.get(("philemon", 1, 1)) != indexed.get(("titus", 2, 15))
        or indexed.get(("philemon", 1, 1)) != (
            "These things speak thou, and exhort, and inculcate, with all "
            "authority; and let no one despise thee."
        )
    ):
        raise ValueError("Murdock Philemon 1:1 duplicate index evidence changed.")

    result: list[SourceVerse] = []
    seen: set[tuple[str, int, int]] = set()
    for work_id, chapter, verse, raw_text in raw_rows:
        if (work_id, chapter, verse) == ("philemon", 1, 1):
            raw_text = spill_values[0]
        position = (work_id, chapter, verse)
        if position in seen:
            raise ValueError("Murdock source contains a duplicate position.")
        seen.add(position)
        result.append(SourceVerse(work_id, chapter, verse, clean_murdock_text(raw_text)))
    if len(result) != 7_947 or {row.work_id for row in result} != set(definition.expected_work_ids):
        raise ValueError("Murdock source must contain the exact reviewed 27-work inventory.")
    return tuple(result)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ) + "\n").encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _group_rows(rows: tuple[SourceVerse, ...]) -> dict[str, tuple[SourceVerse, ...]]:
    grouped: dict[str, list[SourceVerse]] = defaultdict(list)
    for row in rows:
        grouped[row.work_id].append(row)
    return {work_id: tuple(values) for work_id, values in grouped.items()}


def _historical_snapshots(verification_root: Path) -> dict[str, bytes]:
    """Validate and return four immutable historical artifact snapshots."""
    root = Path(verification_root)
    lock_path = root / HISTORICAL_LOCK_FILENAME
    try:
        raw = _secure_read(
            lock_path, maximum=64 * 1024, context="Murdock historical artifact lock",
        )
        lock = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Murdock historical artifact lock is invalid.") from error
    expected_fields = {
        "schema_version", "internet_archive_identifier", "edition", "artifacts",
    }
    if (
        type(lock) is not dict or set(lock) != expected_fields
        or lock["schema_version"] != 1
        or lock["internet_archive_identifier"] != "syriacnewtestam00murdgoog"
        or lock["edition"] != "1915 ninth edition of James Murdock's 1852 translation"
        or type(lock["artifacts"]) is not list
        or len(lock["artifacts"]) != len(_HISTORICAL_ARTIFACTS)
    ):
        raise ValueError("Murdock historical artifact lock identity is invalid.")
    snapshots: dict[str, bytes] = {}
    fields = {
        "role", "filename", "size_bytes", "sha256", "sha1", "source_url",
        "landing_url", "retrieved_at",
    }
    for record, expected in zip(lock["artifacts"], _HISTORICAL_ARTIFACTS, strict=True):
        role, filename, size, checksum, checksum_sha1, source_url, landing_url, retrieved_at = expected
        if type(record) is not dict or set(record) != fields or record != {
            "role": role, "filename": filename, "size_bytes": size,
            "sha256": checksum, "sha1": checksum_sha1, "source_url": source_url,
            "landing_url": landing_url, "retrieved_at": retrieved_at,
        }:
            raise ValueError("Murdock historical artifact lock record is invalid.")
        payload = _secure_read(
            root / "artifacts" / filename,
            maximum=max(size, 1), context=f"Murdock historical artifact {role}",
        )
        if (
            len(payload) != size or sha256(payload).hexdigest() != checksum
            or sha1(payload).hexdigest() != checksum_sha1
        ):
            raise ValueError("Murdock historical artifact identity is invalid.")
        snapshots[role] = payload
    try:
        title_page = " ".join(
            snapshots["ocr_plain_text_derivative"].decode("utf-8").split()
        )[:6_000]
    except UnicodeDecodeError as error:
        raise ValueError("Murdock historical title-page OCR is invalid.") from error
    if not all(phrase in title_page for phrase in (
        "Syriac New Testament", "By JAMES MURDOCK", "NINTH EDITION", "1915",
    )):
        raise ValueError("Murdock historical witness must identify the 1915 ninth edition.")
    return snapshots


def _scan_leaf_metadata(payload: bytes) -> dict[int, str | None]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise ValueError("Murdock scan leaf mapping is invalid.") from error
    if (
        root.tag != "book" or root.findtext("./bookData/bookId")
        != "syriacnewtestam00murdgoog"
        or root.findtext("./bookData/leafCount") != "569"
    ):
        raise ValueError("Murdock scan leaf mapping identity is invalid.")
    result: dict[int, str | None] = {}
    for page in root.findall("./pageData/page"):
        raw_leaf = page.get("leafNum")
        if raw_leaf is None or not raw_leaf.isdecimal():
            raise ValueError("Murdock scan leaf mapping is invalid.")
        leaf = int(raw_leaf)
        if leaf in result:
            raise ValueError("Murdock scan leaf mapping contains a duplicate leaf.")
        result[leaf] = page.findtext("pageNumber")
    if set(result) != set(range(569)):
        raise ValueError("Murdock scan leaf mapping must contain exactly 569 leaves.")
    return result


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z]+", value.lower()))


def _ocr_object_tokens(element: ET.Element) -> tuple[str, ...]:
    """Return every OCR WORD token in unmodified DOM reading order."""
    return _tokens(" ".join((word.text or "").strip() for word in element.iter("WORD")))


def _ocr_object_records(
    element: ET.Element,
) -> tuple[tuple[int, int], tuple[tuple[str, tuple[int, int, int, int]], ...]]:
    """Return the exact OCR canvas and token/coordinate records in DOM order."""
    try:
        canvas = (int(element.attrib["width"]), int(element.attrib["height"]))
    except (KeyError, ValueError) as error:
        raise ValueError("Murdock page OCR canvas is invalid.") from error
    if canvas[0] <= 0 or canvas[1] <= 0:
        raise ValueError("Murdock page OCR canvas is invalid.")
    records: list[tuple[str, tuple[int, int, int, int]]] = []
    for word in element.iter("WORD"):
        raw = word.get("coords", "")
        try:
            coords = tuple(int(value) for value in raw.split(","))
        except ValueError as error:
            raise ValueError("Murdock page OCR WORD coordinates are invalid.") from error
        if (
            len(coords) != 4 or min(coords) < 0
            or coords[0] >= coords[2] or coords[1] == coords[3]
        ):
            raise ValueError("Murdock page OCR WORD coordinates are invalid.")
        for token in _tokens(word.text or ""):
            records.append((token, coords))
    return canvas, tuple(records)


def _ocr_leaf_records(
    payload: bytes | Path,
) -> tuple[tuple[tuple[int, int], tuple[tuple[str, tuple[int, int, int, int]], ...]], ...]:
    if isinstance(payload, Path):
        payload = _secure_read(payload, maximum=32 * 1024 * 1024, context="Murdock page OCR")
    leaves = []
    try:
        for _, element in ET.iterparse(BytesIO(payload), events=("end",)):
            if element.tag != "OBJECT":
                continue
            expected = f"syriacnewtestam00murdgoog_{len(leaves):04d}.djvu"
            if element.get("usemap") != expected:
                raise ValueError("Murdock page OCR leaf order is invalid.")
            leaves.append(_ocr_object_records(element))
            element.clear()
    except ET.ParseError as error:
        raise ValueError("Murdock page OCR is invalid.") from error
    if len(leaves) != 569 or any(not leaves[leaf][1] for leaf in range(53, 524)):
        raise ValueError("Murdock page OCR must contain the exact 569-leaf inventory.")
    return tuple(leaves)


def _ocr_leaves(payload: bytes | Path) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(token for token, _ in records) for _, records in _ocr_leaf_records(payload))


def _sample_candidate(
    rows: tuple[SourceVerse, ...], phase: str, start_leaf: int,
    end_leaf: int, ocr_leaves: tuple[tuple[str, ...], ...],
) -> dict[str, object]:
    count = len(rows)
    if phase == "beginning":
        lower, upper = 0, max(1, count // 3)
    elif phase == "middle":
        lower, upper = count // 3, max(count // 3 + 1, 2 * count // 3)
    elif phase == "end":
        lower, upper = 2 * count // 3, count
    else:  # pragma: no cover - private call contract
        raise ValueError("unknown historical sampling phase")
    selection_index = lower + (upper - lower) // 2
    row = rows[selection_index]
    source_tokens = _tokens(row.text)
    if not source_tokens:
        raise ValueError("Murdock predetermined historical verse has no comparable tokens.")
    expected_leaf_float = (
        start_leaf + (end_leaf - start_leaf) * selection_index / max(1, count - 1)
    )
    expected_leaf = round(expected_leaf_float)
    first_leaf = max(start_leaf, expected_leaf - 4)
    last_leaf = min(end_leaf, expected_leaf + 4)
    searchable_pages = {
        leaf: "\0" + "\0".join(ocr_leaves[leaf]) + "\0"
        for leaf in range(first_leaf, last_leaf + 1)
    }
    exact_hits = [
        (abs(leaf - expected_leaf_float), leaf)
        for leaf in range(first_leaf, last_leaf + 1)
        if ("\0" + "\0".join(source_tokens) + "\0") in searchable_pages[leaf]
    ]
    if exact_hits:
        _, leaf = min(exact_hits)
        anchor_tokens = source_tokens
        result = "confirmed"
        mismatch_evidence = None
    else:
        best_partial: tuple[int, float, int, tuple[str, ...]] | None = None
        for leaf in range(first_leaf, last_leaf + 1):
            blocks = difflib.SequenceMatcher(
                None, source_tokens, ocr_leaves[leaf], autojunk=False,
            ).get_matching_blocks()
            longest = max(blocks, key=lambda block: block.size)
            anchor = ocr_leaves[leaf][longest.b:longest.b + longest.size]
            score = (longest.size, -abs(leaf - expected_leaf_float), -leaf, anchor)
            if best_partial is None or score > best_partial:
                best_partial = score
        assert best_partial is not None
        matched, _, negative_leaf, anchor_tokens = best_partial
        leaf = -negative_leaf
        result = "review_required"
        mismatch_evidence = (
            f"Predetermined verse did not equal one contiguous OCR token window in "
            f"scan leaves {first_leaf}-{last_leaf}; longest contiguous match was "
            f"{matched} of {len(source_tokens)} tokens on leaf {leaf}."
        )
    return {
        "work_id": row.work_id,
        "phase": phase,
        "chapter": row.chapter,
        "verse": row.verse,
        "electronic_text": row.text,
        "selection_rule": "median source position within canonical work third",
        "selection_index": selection_index,
        "expected_scan_leaf": expected_leaf,
        "inspected_leaf_start": first_leaf,
        "inspected_leaf_end": last_leaf,
        "scan_leaf": leaf,
        "scan_page": None,  # filled from the separately locked leaf mapping
        "image_anchor": (
            "https://archive.org/download/syriacnewtestam00murdgoog/page/"
            f"n{leaf}/mode/1up"
        ),
        "ocr_text_anchor": " ".join(anchor_tokens),
        "matched_token_count": len(anchor_tokens),
        "electronic_token_count": len(source_tokens),
        "token_coverage": f"{len(anchor_tokens) / len(source_tokens):.6f}",
        "result": result,
        "mismatch_evidence": mismatch_evidence,
    }


def _load_visual_reviews(
    verification_root: Path, samples: list[dict[str, object]],
) -> dict[tuple[str, str, int, int], dict[str, object]]:
    """Load the exact disclosed manual review of OCR-failed fixed samples."""
    path = Path(verification_root) / "reports" / VISUAL_REVIEW_FILENAME
    try:
        raw = _secure_read(
            path, maximum=1024 * 1024, context="Murdock PDF visual review",
        )
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Murdock PDF visual review is missing or invalid.") from error
    top_fields = {
        "schema_version", "family_id", "pdf_sha256", "pdf_pages", "reviewer",
        "reviewed_at", "manual_review_method", "render_profile", "samples",
    }
    profile = {
        "renderer": "Poppler pdftoppm 26.05.0",
        "pdf_600dpi_canvas": [5100, 6600], "render_canvas": [1275, 1650],
        "color_mode": "RGB", "ocr_token_margin": "electronic token count plus 8",
        "pixel_margin": 24, "crop_hash": "SHA-256 of row-major RGB bytes",
    }
    if (
        sha256(raw).hexdigest() != VISUAL_REVIEW_SHA256
        or type(payload) is not dict or set(payload) != top_fields
        or payload["schema_version"] != 1
        or payload["family_id"] != "murdock-peshitta-1852"
        or payload["pdf_sha256"]
        != "be4d1425fe69b4ff24fa418e15a2a2fbfb924db50d7e06861a937cfd3c81bc05"
        or payload["pdf_pages"] != 569
        or payload["reviewer"] != VISUAL_REVIEWER
        or payload["reviewed_at"] != VISUAL_REVIEWED_AT
        or payload["reviewed_at"] <= _HISTORICAL_ARTIFACTS[-1][-1]
        or not str(payload["manual_review_method"]).startswith(
            "Render only each predetermined sample page"
        )
        or payload["render_profile"] != profile
        or type(payload["samples"]) is not list
    ):
        raise ValueError("Murdock PDF visual review identity is invalid.")
    unresolved = {
        (sample["work_id"], sample["phase"], sample["chapter"], sample["verse"]): sample
        for sample in samples if sample["result"] == "review_required"
    }
    reviewed: dict[tuple[str, str, int, int], dict[str, object]] = {}
    default_fields = {
        "work_id", "phase", "chapter", "verse", "classification", "finding",
        "crops",
    }
    crop_fields = {
        "leaf", "pdf_page", "ocr_bbox", "render_bbox", "crop_rgb_sha256",
        "ocr_token_start", "ocr_token_end", "anchor_source_start",
        "anchor_page_start", "anchor_size", "ocr_canvas",
        "pdf_600dpi_canvas", "render_canvas", "token_margin", "pixel_margin",
    }
    for record in payload["samples"]:
        if type(record) is not dict:
            raise ValueError("Murdock PDF visual review sample is invalid.")
        key = (
            record.get("work_id"), record.get("phase"),
            record.get("chapter"), record.get("verse"),
        )
        sample = unresolved.get(key)
        if sample is None or key in reviewed:
            raise ValueError("Murdock PDF visual review sample inventory changed.")
        classification = record.get("classification")
        expected_fields = set(default_fields)
        if classification == "confirmed_formatting":
            expected_fields |= {"electronic_reading", "printed_reading", "variance"}
            if (
                key != ("jude", "middle", 1, 13)
                or record.get("electronic_reading") != "shootingstars"
                or record.get("printed_reading") != "shooting-stars"
                or record.get("variance")
                != "closed compound versus hyphenated compound"
            ):
                raise ValueError("Murdock PDF formatting variance is not the reviewed one.")
        elif classification != "confirmed_visual":
            raise ValueError("Murdock PDF visual review classification is invalid.")
        if set(record) != expected_fields or type(record["crops"]) is not list or not record["crops"]:
            raise ValueError("Murdock PDF visual review sample fields are invalid.")
        for crop in record["crops"]:
            if (
                type(crop) is not dict or set(crop) != crop_fields
                or type(crop["leaf"]) is not int
                or not sample["inspected_leaf_start"] <= crop["leaf"] <= sample["inspected_leaf_end"]
                or crop["pdf_page"] != crop["leaf"] + 1
                or crop["pdf_600dpi_canvas"] != [5100, 6600]
                or crop["render_canvas"] != [1275, 1650]
                or crop["pixel_margin"] != 24
                or crop["token_margin"] != sample["electronic_token_count"] + 8
                or any(type(crop[field]) is not int or crop[field] < 0 for field in (
                    "ocr_token_start", "ocr_token_end", "anchor_source_start",
                    "anchor_page_start", "anchor_size",
                ))
                or crop["ocr_token_start"] >= crop["ocr_token_end"]
                or type(crop["ocr_canvas"]) is not list or len(crop["ocr_canvas"]) != 2
                or any(type(value) is not int or value <= 0 for value in crop["ocr_canvas"])
                or any(
                    type(box) is not list or len(box) != 4
                    or any(type(value) is not int or value < 0 for value in box)
                    or box[0] >= box[2] or box[1] >= box[3]
                    for box in (crop["ocr_bbox"], crop["render_bbox"])
                )
                or not re.fullmatch(r"[0-9a-f]{64}", crop["crop_rgb_sha256"])
            ):
                raise ValueError("Murdock PDF visual review crop is invalid.")
        reviewed[key] = record
    if set(reviewed) != set(unresolved) or len(reviewed) != 42:
        raise ValueError("Murdock PDF visual review must cover the exact 42 OCR failures.")
    if sum(item["classification"] == "confirmed_formatting" for item in reviewed.values()) != 1:
        raise ValueError("Murdock PDF visual review formatting inventory changed.")
    return reviewed


def build_historical_evidence(verification_root: Path) -> dict[str, object]:
    """Reproduce 81 historical samples from the exact locked scan derivatives."""
    snapshots = _historical_snapshots(verification_root)
    leaf_metadata = _scan_leaf_metadata(snapshots["scan_leaf_mapping_derivative"])
    leaves = _ocr_leaves(snapshots["page_structured_ocr_derivative"])
    # Import here avoids a registry import cycle during CLI adapter creation.
    from app.library.verification.registry import APPROVED_SOURCE_DEFINITIONS
    definition = APPROVED_SOURCE_DEFINITIONS["murdock-peshitta-1852"]
    source_snapshot = _secure_read(
        Path(verification_root) / "artifacts" / "murdock-source.zip",
        maximum=definition.max_artifact_bytes, context="Murdock artifact",
    )
    if sha256(source_snapshot).hexdigest() != SOURCE_ARTIFACT_SHA256:
        raise ValueError("Murdock artifact snapshot does not match historical evidence.")
    rows = _group_rows(_parse_murdock_snapshot(source_snapshot, definition))
    samples: list[dict[str, object]] = []
    for index, work_id in enumerate(definition.expected_work_ids):
        for phase in ("beginning", "middle", "end"):
            sample = _sample_candidate(
                rows[work_id], phase, _WORK_LEAF_BOUNDARIES[index],
                _WORK_LEAF_BOUNDARIES[index + 1], leaves,
            )
            sample["scan_page"] = leaf_metadata[sample["scan_leaf"]]
            samples.append(sample)
    visual_reviews = _load_visual_reviews(verification_root, samples)
    for sample in samples:
        if sample["result"] != "review_required":
            sample["result"] = "confirmed_ocr"
            continue
        key = (
            sample["work_id"], sample["phase"], sample["chapter"], sample["verse"],
        )
        review = visual_reviews[key]
        sample["ocr_mismatch_evidence"] = sample.pop("mismatch_evidence")
        sample["visual_review"] = review
        sample["result"] = review["classification"]
    artifact_checksums = {
        role: checksum for role, _, _, checksum, _, _, _, _ in _HISTORICAL_ARTIFACTS
    }
    totals = {
        "confirmed_ocr": sum(sample["result"] == "confirmed_ocr" for sample in samples),
        "confirmed_visual": sum(
            sample["result"] == "confirmed_visual" for sample in samples
        ),
        "confirmed_formatting": sum(
            sample["result"] == "confirmed_formatting" for sample in samples
        ),
        "review_required": sum(
            sample["result"] == "review_required" for sample in samples
        ),
    }
    return {
        "schema_version": 1,
        "family_id": "murdock-peshitta-1852",
        "electronic_source_sha256": (
            "4f0adeba385acbfa37921f66677d4aaf99e23b4e65ca162f122832689036641f"
        ),
        "historical_artifact_sha256": artifact_checksums,
        "historical_source_title": "The Syriac New Testament",
        "historical_source_edition": "Ninth edition",
        "historical_source_year": 1915,
        "edition_note": HISTORICAL_EDITION_NOTE,
        "sampling_method": (
            "Before OCR inspection, select the median source position in each canonical "
            "work third; then require that verse's complete normalized token sequence "
            "to equal one contiguous OCR token window within ±4 expected scan leaves."
        ),
        "encoding_evidence": {
            "position": "matthew 27:42",
            "module_byte": "0x86",
            "decoded_glyph": "†",
            "scan_leaf": 110,
            "scan_page": "68",
            "ocr_anchor": (
                "he gave life to others his own life he cannot preserve if he is "
                "the king of israel let him now descend from the cross"
            ),
            "explanation": (
                "The locked 1915 ninth-edition scan prints a dagger after Matthew 27:42 and its "
                "footnote. Exactly two 0x86 bytes occur in the reviewed module block: "
                "one in the RF footnote apparatus and one at the verse boundary. Those "
                "two reviewed bytes are decoded as the dagger; other Latin-1 bytes are unchanged."
            ),
        },
        "samples": samples,
        "totals": totals,
    }


def validate_historical_evidence(
    path: Path, verification_root: Path, definition: SourceDefinition,
) -> dict[str, object]:
    """Require byte-canonical evidence equal to a fresh 81-sample rebuild."""
    if definition.family_id != "murdock-peshitta-1852":
        raise ValueError("Murdock historical evidence definition is invalid.")
    expected = build_historical_evidence(verification_root)
    try:
        raw = _secure_read(
            Path(path), maximum=4 * 1024 * 1024,
            context="Murdock historical evidence",
        )
        actual = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Murdock historical evidence is missing or invalid.") from error
    if raw != _json_bytes(expected) or actual != expected:
        raise ValueError("Murdock historical evidence is not canonical or is review_required.")
    return actual


def write_historical_evidence(verification_root: Path, output: Path) -> dict[str, object]:
    evidence = build_historical_evidence(verification_root)
    _atomic_write(Path(output), _json_bytes(evidence))
    return evidence


def historical_evidence_markdown(evidence: dict[str, object]) -> str:
    totals = evidence["totals"]
    assert type(totals) is dict
    lines = [
        "# Murdock Historical Scan Samples", "",
        f"- {evidence['edition_note']}",
        "- Samples: 81 (beginning, middle, and end of each of 27 works)",
        f"- Confirmed by exact OCR window: {totals['confirmed_ocr']}",
        f"- Confirmed by locked-PDF visual review: {totals['confirmed_visual']}",
        f"- Confirmed formatting variance: {totals['confirmed_formatting']}",
        f"- Review required: {totals['review_required']}",
        "- OCR is a page locator; visual confirmations are tied to the locked PDF derivative.", "",
        "## Encoding evidence", "",
        f"- {evidence['encoding_evidence']['explanation']}", "",
        "## Work samples", "",
        "| Work | Phase | Selection index | Electronic verse | Evidence leaf(s) | Printed/PDF page(s) | OCR anchor | Result |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for sample in evidence["samples"]:
        assert type(sample) is dict
        anchor = str(sample["ocr_text_anchor"]).replace("|", "\\|")
        if "visual_review" in sample:
            crops = sample["visual_review"]["crops"]
            leaf = ", ".join(str(crop["leaf"]) for crop in crops)
            page = ", ".join(str(crop["pdf_page"]) for crop in crops)
        else:
            leaf = str(sample["scan_leaf"])
            page = sample["scan_page"] if sample["scan_page"] is not None else "unprinted"
        lines.append(
            f"| {sample['work_id']} | {sample['phase']} | {sample['selection_index']} | "
            f"{sample['chapter']}:{sample['verse']} | {leaf} | "
            f"{page} | {anchor} | {sample['result']} |"
        )
    return "\n".join(lines) + "\n"


def write_historical_evidence_pair(
    verification_root: Path, output_directory: Path,
) -> dict[str, object]:
    evidence = build_historical_evidence(verification_root)
    output_directory = Path(output_directory)
    stem = HISTORICAL_EVIDENCE_FILENAME.removesuffix(".json")
    _atomic_write(output_directory / f"{stem}.json", _json_bytes(evidence))
    _atomic_write(
        output_directory / f"{stem}.md",
        historical_evidence_markdown(evidence).encode("utf-8"),
    )
    return evidence


def _load_current_rows(
    path: Path, definition: SourceDefinition,
) -> tuple[SourceVerse, ...]:
    snapshot = _secure_read(
        path, maximum=256 * 1024 * 1024,
        context="current Murdock publication bundle",
    )
    return _load_current_snapshot(snapshot, definition)


def _load_current_snapshot(
    snapshot: bytes, definition: SourceDefinition,
) -> tuple[SourceVerse, ...]:
    try:
        with ZipFile(BytesIO(snapshot)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or "data/index.json" not in names:
                raise ValueError("current Murdock publication bundle index is invalid.")
            index = json.loads(archive.read("data/index.json").decode("utf-8"))
            records = index.get("books") if type(index) is dict else None
            if type(records) is not list:
                raise ValueError("current Murdock publication index is invalid.")
            selected = [
                record for record in records
                if type(record) is dict and record.get("src") == "peshitta"
            ]
            reverse = {code: work_id for code, work_id in SOURCE_CODE_TO_WORK_ID.items()}
            if (
                len(selected) != 27
                or [reverse.get(record.get("id")) for record in selected]
                != list(definition.expected_work_ids)
            ):
                raise ValueError("current publication must contain the exact 27 Murdock works.")
            rows: list[SourceVerse] = []
            seen: set[tuple[str, int, int]] = set()
            for record in selected:
                member = record.get("file")
                if type(member) is not str or names.count(member) != 1:
                    raise ValueError("current Murdock publication member is invalid.")
                chapters = json.loads(archive.read(member).decode("utf-8"))
                work_id = reverse[record["id"]]
                if type(chapters) is not list or len(chapters) != len(
                    CHAPTER_VERSE_COUNTS[record["id"]]
                ):
                    raise ValueError("current Murdock publication chapter inventory is invalid.")
                for chapter_record in chapters:
                    if type(chapter_record) is not dict:
                        raise ValueError("current Murdock publication chapter is invalid.")
                    chapter = chapter_record.get("c")
                    verses = chapter_record.get("v")
                    if type(chapter) is not int or chapter <= 0 or type(verses) is not list:
                        raise ValueError("current Murdock publication chapter is invalid.")
                    for verse_record in verses:
                        if type(verse_record) is not dict:
                            raise ValueError("current Murdock publication verse is invalid.")
                        verse, text = verse_record.get("n"), verse_record.get("t")
                        if (
                            type(verse) is not int or verse <= 0
                            or type(text) is not str or not text.strip()
                            or (work_id, chapter, verse) in seen
                        ):
                            raise ValueError("current Murdock publication verse is invalid.")
                        seen.add((work_id, chapter, verse))
                        rows.append(SourceVerse(work_id, chapter, verse, text))
    except (BadZipFile, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("current Murdock publication bundle is malformed.") from error
    if len(rows) != 7_947:
        raise ValueError("current Murdock publication must contain 7,947 verses.")
    return tuple(rows)


def _family_markdown(payload: dict[str, object]) -> str:
    totals = payload["totals"]
    assert type(totals) is dict
    lines = [
        "# Murdock Peshitta Source Verification", "",
        "- Collection role: 27-work New Testament source family in a mixed-source English research collection",
        "- Collection claim: not a complete or official Ethiopian Bible",
        f"- CrossWire artifact SHA-256: `{payload['source_artifact_sha256']}`",
        f"- Current publication SHA-256: `{payload['current_publication_sha256']}`",
        f"- Parser: `{payload['parser_version']}`",
        f"- Declared omissions: {payload['declared_omission_count']}", "",
        "## Totals", "",
        *(f"- {name.title()}: {totals[name]}" for name in (
            "exact", "formatting", "missing", "extra", "wording"
        )), "", "## Work reports", "",
    ]
    for work in payload["works"]:
        assert type(work) is dict
        lines.append(f"- `{work['work_id']}`: report SHA-256 `{work['report_sha256']}`")
    return "\n".join(lines) + "\n"


def _validate_candidate_lock(definition, lock_record, artifact_path: Path) -> bytes:
    payload = _secure_read(
        artifact_path, maximum=definition.max_artifact_bytes,
        context="Murdock candidate artifact",
    )
    retrieved = lock_record.retrieved_at.isoformat().replace("+00:00", "Z")
    if (
        lock_record.family_id != definition.family_id
        or lock_record.artifact_path != definition.artifact_filename
        or lock_record.source_url != definition.artifact_url
        or lock_record.landing_url != definition.landing_url
        or retrieved != "2026-08-29T05:53:51Z"
        or lock_record.size_bytes != 396_427
        or lock_record.sha256 != SOURCE_ARTIFACT_SHA256
        or len(payload) != lock_record.size_bytes
        or sha256(payload).hexdigest() != lock_record.sha256
    ):
        raise ValueError("Murdock candidate lock or source artifact identity is invalid.")
    return payload


def _validate_pre_rebuild_reports(report_dir: Path, definition) -> None:
    """Validate the immutable comparison evidence authorizing source replacement."""
    from app.library.verification.cli import _strict_report

    reports_root = Path(report_dir).parent
    summary_path = reports_root / f"{definition.family_id}-pre-rebuild.json"
    try:
        summary_bytes = _secure_read(
            summary_path, maximum=4 * 1024 * 1024,
            context="Murdock pre-rebuild family report",
        )
        summary = json.loads(summary_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Murdock pre-rebuild family report is missing or invalid.") from error
    family_fields = {
        "schema_version", "family_id", "source_artifact_sha256",
        "current_publication_sha256", "parser_version",
        "declared_omission_count", "totals", "works",
    }
    total_fields = {"exact", "formatting", "missing", "extra", "wording"}
    if (
        sha256(summary_bytes).hexdigest() != PRE_REBUILD_FAMILY_SHA256
        or type(summary) is not dict or set(summary) != family_fields
        or summary["schema_version"] != 1
        or summary["family_id"] != definition.family_id
        or summary["source_artifact_sha256"] != SOURCE_ARTIFACT_SHA256
        or summary["current_publication_sha256"] != PRE_REBUILD_PUBLICATION_SHA256
        or summary["parser_version"] != PARSER_VERSION
        or summary["declared_omission_count"] != 10
        or summary["totals"] != {
            "exact": 6_872, "formatting": 1, "missing": 0,
            "extra": 0, "wording": 1_074,
        }
        or type(summary["works"]) is not list
        or [item.get("work_id") if type(item) is dict else None for item in summary["works"]]
        != list(definition.expected_work_ids)
    ):
        raise ValueError("Murdock pre-rebuild family report is not canonical.")
    directory = reports_root / f"{definition.family_id}-pre-rebuild"
    expected_names = {f"{work_id}.json" for work_id in definition.expected_work_ids}
    if not directory.is_dir() or {path.name for path in directory.glob("*.json")} != expected_names:
        raise ValueError("Murdock pre-rebuild report inventory is incomplete.")
    aggregate = {name: 0 for name in total_fields}
    for item in summary["works"]:
        if type(item) is not dict or set(item) != {"work_id", "report_sha256", "totals"}:
            raise ValueError("Murdock pre-rebuild work summary is invalid.")
        work_id = item["work_id"]
        if type(item["totals"]) is not dict or set(item["totals"]) != total_fields:
            raise ValueError("Murdock pre-rebuild work totals are invalid.")
        path = directory / f"{work_id}.json"
        try:
            raw = _secure_read(
                path, maximum=32 * 1024 * 1024,
                context=f"Murdock pre-rebuild report {work_id}",
            )
            report = _strict_report(json.loads(raw.decode("utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"Murdock pre-rebuild report is invalid: {work_id}.") from error
        expected_omissions = tuple(
            VersePosition(chapter, verse)
            for chapter, verse in DECLARED_OMISSIONS.get(work_id, ())
        )
        if (
            raw != report_json_bytes(report)
            or report.work_id != work_id
            or report_sha256(report) != item["report_sha256"]
            or report.source_artifact.sha256 != SOURCE_ARTIFACT_SHA256
            or report.current_publication.sha256 != PRE_REBUILD_PUBLICATION_SHA256
            or report.parser_version != PARSER_VERSION
            or report.rules != ComparisonRules()
            or report.totals != ComparisonCounts(**item["totals"])
            or report.declared_omissions != expected_omissions
        ):
            raise ValueError(f"Murdock pre-rebuild report identity changed: {work_id}.")
        for name in aggregate:
            aggregate[name] += getattr(report.totals, name)
    if aggregate != summary["totals"]:
        raise ValueError("Murdock pre-rebuild report totals do not reconcile.")


class MurdockSwordAdapter:
    """Deterministic comparison and source-candidate adapter for Murdock 1.2."""

    def compare_family(
        self, *, definition, lock_record, artifact_path, current_bundle, output,
    ):
        from app.library.verification.cli import CompareFamilyResult

        source = _group_rows(parse_murdock_sword(
            artifact_path, definition, expected_sha256=lock_record.sha256,
        ))
        current_snapshot = _secure_read(
            current_bundle, maximum=256 * 1024 * 1024,
            context="current Murdock publication bundle",
        )
        current = _group_rows(_load_current_snapshot(current_snapshot, definition))
        publication_sha = sha256(current_snapshot).hexdigest()
        child_output = Path(output) / definition.family_id
        reports = []
        totals = {name: 0 for name in ("exact", "formatting", "missing", "extra", "wording")}
        for work_id in definition.expected_work_ids:
            report = compare_work(
                work_id, current[work_id], source[work_id], ComparisonRules(),
                declared_omissions=DECLARED_OMISSIONS.get(work_id, ()),
                source_artifact_sha256=lock_record.sha256,
                current_publication_sha256=publication_sha,
                parser_version=PARSER_VERSION,
            )
            write_report_pair(report, child_output, work_id)
            for name in totals:
                totals[name] += getattr(report.totals, name)
            reports.append({
                "work_id": work_id,
                "report_sha256": report_sha256(report),
                "totals": {name: getattr(report.totals, name) for name in totals},
            })
        family = {
            "schema_version": 1,
            "family_id": definition.family_id,
            "source_artifact_sha256": lock_record.sha256,
            "current_publication_sha256": publication_sha,
            "parser_version": PARSER_VERSION,
            "declared_omission_count": len(_DECLARED_OMISSION_SET),
            "totals": totals,
            "works": reports,
        }
        _atomic_write(Path(output) / f"{definition.family_id}.json", _json_bytes(family))
        _atomic_write(
            Path(output) / f"{definition.family_id}.md",
            _family_markdown(family).encode("utf-8"),
        )
        return CompareFamilyResult(report_count=len(reports), output_id=definition.family_id)

    def build_candidate(
        self, *, definition, lock_record, artifact_path, report_dir, output,
        replace_from_source,
    ):
        from app.library.verification.cli import CandidateBuildResult

        if not replace_from_source:
            raise ValueError("Murdock source candidates require explicit source replacement.")
        source_snapshot = _validate_candidate_lock(
            definition, lock_record, artifact_path,
        )
        report_dir = Path(report_dir)
        historical = validate_historical_evidence(
            report_dir.parent / HISTORICAL_EVIDENCE_FILENAME,
            report_dir.parents[1], definition,
        )
        _validate_pre_rebuild_reports(report_dir, definition)
        if historical["totals"]["review_required"]:
            raise ValueError(
                "Murdock source candidate is blocked by review_required historical samples."
            )
        grouped = _group_rows(_parse_murdock_snapshot(source_snapshot, definition))
        members: dict[str, bytes] = {}
        index = []
        for work_id in definition.expected_work_ids:
            chapters: dict[int, list[dict[str, object]]] = defaultdict(list)
            for row in grouped[work_id]:
                chapters[row.chapter].append({"n": row.verse, "t": row.text})
            rendered = [
                {"c": chapter, "v": chapters[chapter]} for chapter in sorted(chapters)
            ]
            member = f"data/{work_id}.json"
            members[member] = _json_bytes(rendered)
            index.append({"work_id": work_id, "file": member, "chapters": len(rendered)})
        members["data/index.json"] = _json_bytes({"books": index})
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(members):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, members[name], compress_type=ZIP_DEFLATED, compresslevel=9)
        return CandidateBuildResult(work_count=len(index), output_id="murdock-candidate.zip")
