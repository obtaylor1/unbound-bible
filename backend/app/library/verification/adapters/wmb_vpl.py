"""Strict parser for the reviewed eBible World Messianic Bible VPL archive."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import unicodedata
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from app.library.verification.compare import compare_work
from app.library.verification.report import report_sha256, write_report_pair
from app.library.verification.registry import SourceDefinition
from app.library.verification.types import ComparisonRules, SourceVerse


PARSER_VERSION = "wmb-vpl/1"
REVIEWED_MEMBER = "engwmb_vpl.txt"
REVIEWED_MEMBERS = frozenset({
    "engwmb_about.htm", "engwmb_vpl.sql", REVIEWED_MEMBER,
    "engwmb_vpl.xml", "haiola.css",
})
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
READ_CHUNK_BYTES = 1024 * 1024

WMB_CODE_TO_WORK_ID = {
    "GEN": "genesis", "EXO": "exodus", "LEV": "leviticus",
    "NUM": "numbers", "DEU": "deuteronomy", "JOS": "joshua",
    "JDG": "judges", "RUT": "ruth", "1SA": "1-samuel",
    "2SA": "2-samuel", "1KI": "1-kings", "2KI": "2-kings",
    "1CH": "1-chronicles", "2CH": "2-chronicles", "EZR": "ezra",
    "NEH": "nehemiah", "EST": "esther", "JOB": "job",
    "PSA": "psalms", "PRO": "proverbs", "ECC": "ecclesiastes",
    "SOL": "song-of-solomon", "ISA": "isaiah", "JER": "jeremiah",
    "LAM": "lamentations", "EZE": "ezekiel", "DAN": "daniel",
    "HOS": "hosea", "JOE": "joel", "AMO": "amos", "OBA": "obadiah",
    "JON": "jonah", "MIC": "micah", "NAH": "nahum",
    "HAB": "habakkuk", "ZEP": "zephaniah", "HAG": "haggai",
    "ZEC": "zechariah", "MAL": "malachi",
}

_NON_WMB_CODES = frozenset({
    "MAT", "MAR", "LUK", "JOH", "ACT", "ROM", "1CO", "2CO", "GAL",
    "EPH", "PHI", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM",
    "HEB", "JAM", "1PE", "2PE", "1JO", "2JO", "3JO", "JUD", "REV",
})
REVIEWED_SOURCE_CODES = frozenset(WMB_CODE_TO_WORK_ID) | _NON_WMB_CODES
_CURRENT_BUNDLE_CODE_TO_WORK_ID = {
    **WMB_CODE_TO_WORK_ID,
    "SNG": "song-of-solomon", "EZK": "ezekiel", "JOL": "joel", "NAM": "nahum",
}
_LINE = re.compile(r"([A-Z0-9]{3}) ([1-9]\d*):([1-9]\d*) (.*)\Z")


def _validate_archive_file(path: Path, definition: SourceDefinition) -> None:
    try:
        status = path.lstat()
    except OSError as error:
        raise ValueError("WMB artifact is missing.") from error
    if not stat.S_ISREG(status.st_mode):
        raise ValueError("WMB artifact must be a nonsymlink regular file.")
    if not 0 < status.st_size <= definition.max_artifact_bytes:
        raise ValueError("WMB artifact exceeds its reviewed byte limit.")


def _validate_member(info: ZipInfo) -> None:
    name = info.filename
    pure = PurePosixPath(name)
    if (
        name not in REVIEWED_MEMBERS
        or pure.is_absolute()
        or len(pure.parts) != 1
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "\\" in name
    ):
        raise ValueError("WMB archive must contain exactly the reviewed five-member set.")
    if info.flag_bits & 0x1:
        raise ValueError("encrypted ZIP members are forbidden.")
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if info.is_dir() or file_type not in (0, stat.S_IFREG):
        raise ValueError("the reviewed WMB member must be a regular file.")
    if info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
        raise ValueError("the reviewed WMB member uses unsupported compression.")
    if not 0 < info.file_size <= MAX_MEMBER_BYTES:
        raise ValueError("the reviewed WMB member exceeds its byte limit.")
    if info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO:
        raise ValueError("the reviewed WMB member exceeds the compression ratio limit.")


def _read_member(archive: ZipFile, info: ZipInfo) -> bytes:
    chunks: list[bytes] = []
    total = 0
    with archive.open(info, "r") as handle:
        while True:
            chunk = handle.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_MEMBER_BYTES or total > info.file_size:
                raise ValueError("the reviewed WMB member exceeds its byte limit.")
            chunks.append(chunk)
    if total != info.file_size:
        raise ValueError("the reviewed WMB member size changed while reading.")
    return b"".join(chunks)


def parse_wmb_vpl(path: Path, definition: SourceDefinition) -> tuple[SourceVerse, ...]:
    """Return the approved 39-work Old Testament inventory from official VPL."""
    if type(definition) is not SourceDefinition:
        raise ValueError("definition must be a SourceDefinition.")
    if definition.adapter_id != "wmb_vpl":
        raise ValueError("definition must select the WMB VPL adapter.")
    if tuple(WMB_CODE_TO_WORK_ID.values()) != definition.expected_work_ids:
        raise ValueError("definition must contain the exact approved WMB work inventory.")
    path = Path(path)
    _validate_archive_file(path, definition)
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) != 5 or len(set(names)) != 5 or set(names) != REVIEWED_MEMBERS:
                raise ValueError(
                    "WMB archive must contain exactly the reviewed five-member set."
                )
            if sum(info.file_size for info in infos) > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ValueError("WMB archive exceeds its total uncompressed byte limit.")
            for member_info in infos:
                _validate_member(member_info)
            info = next(item for item in infos if item.filename == REVIEWED_MEMBER)
            payload = _read_member(archive, info)
    except BadZipFile as error:
        raise ValueError("WMB artifact must be a valid ZIP archive.") from error
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("the reviewed WMB member must be strict UTF-8.") from error
    if text.startswith("\ufeff") or unicodedata.normalize("NFC", text) != text:
        raise ValueError("the reviewed WMB member must be BOM-free NFC UTF-8.")
    if "\r" in text or not text.endswith("\n"):
        raise ValueError("the reviewed WMB member must use the reviewed LF newline convention.")
    if any(
        character != "\n"
        and (
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
        )
        for character in text
    ):
        raise ValueError(
            "the reviewed WMB member contains a control or Unicode line separator."
        )

    rows: list[SourceVerse] = []
    positions: set[tuple[str, int, int]] = set()
    seen_works: set[str] = set()
    seen_codes: set[str] = set()
    previous_by_work: dict[str, tuple[int, int]] = {}
    for line_number, line in enumerate(text.split("\n"), 1):
        if not line:
            continue
        match = _LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid WMB VPL line {line_number}.")
        code, chapter_text, verse_text, verse_text_value = match.groups()
        seen_codes.add(code)
        if code not in WMB_CODE_TO_WORK_ID:
            continue
        if not verse_text_value.strip():
            raise ValueError(f"WMB VPL line {line_number} must contain nonblank text.")
        work_id = WMB_CODE_TO_WORK_ID[code]
        chapter = int(chapter_text)
        verse = int(verse_text)
        position = (work_id, chapter, verse)
        if position in positions:
            raise ValueError(f"duplicate WMB VPL position {work_id} {chapter}:{verse}.")
        numeric_position = (chapter, verse)
        if numeric_position <= previous_by_work.get(work_id, (0, 0)):
            raise ValueError(f"WMB VPL positions are out of order for {work_id}.")
        previous_by_work[work_id] = numeric_position
        positions.add(position)
        seen_works.add(work_id)
        rows.append(SourceVerse(work_id, chapter, verse, verse_text_value))

    if seen_codes != REVIEWED_SOURCE_CODES:
        raise ValueError("WMB VPL must contain the exact reviewed 66-code inventory.")
    if seen_works != set(definition.expected_work_ids):
        raise ValueError("WMB VPL must contain exactly the 39 approved works.")
    return tuple(rows)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _load_current_rows(
    path: Path, definition: SourceDefinition,
) -> tuple[SourceVerse, ...]:
    try:
        status = path.lstat()
    except OSError as error:
        raise ValueError("current publication bundle is missing.") from error
    if not stat.S_ISREG(status.st_mode):
        raise ValueError("current publication bundle must be a regular file.")
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or "data/index.json" not in names:
                raise ValueError("current publication has duplicate members or no index.")
            if any(
                PurePosixPath(name).is_absolute()
                or "\\" in name
                or any(part in {"", ".", ".."} for part in PurePosixPath(name).parts)
                for name in names
            ):
                raise ValueError("current publication contains an unsafe member path.")
            index = json.loads(archive.read("data/index.json").decode("utf-8"))
            records = index.get("books") if type(index) is dict else None
            if type(records) is not list:
                raise ValueError("current publication index is invalid.")
            selected = [record for record in records if type(record) is dict and record.get("src") == "wmb"]
            if (
                len(selected) != 39
                or [_CURRENT_BUNDLE_CODE_TO_WORK_ID.get(record.get("id")) for record in selected]
                != list(definition.expected_work_ids)
            ):
                raise ValueError("current publication must contain the exact 39 WMB works.")
            rows: list[SourceVerse] = []
            for record in selected:
                member = record.get("file")
                if type(member) is not str or names.count(member) != 1:
                    raise ValueError("current publication work member is invalid.")
                chapters = json.loads(archive.read(member).decode("utf-8"))
                if type(chapters) is not list or not chapters:
                    raise ValueError("current publication work must contain chapters.")
                work_id = _CURRENT_BUNDLE_CODE_TO_WORK_ID[record["id"]]
                seen: set[tuple[int, int]] = set()
                for chapter_record in chapters:
                    if type(chapter_record) is not dict:
                        raise ValueError("current publication chapter is invalid.")
                    chapter = chapter_record.get("c")
                    verses = chapter_record.get("v")
                    if type(chapter) is not int or chapter <= 0 or type(verses) is not list:
                        raise ValueError("current publication chapter is invalid.")
                    for verse_record in verses:
                        if type(verse_record) is not dict:
                            raise ValueError("current publication verse is invalid.")
                        verse = verse_record.get("n")
                        text = verse_record.get("t")
                        if type(verse) is not int or verse <= 0 or type(text) is not str or not text.strip():
                            raise ValueError("current publication verse is invalid.")
                        if (chapter, verse) in seen:
                            raise ValueError("current publication contains a duplicate position.")
                        seen.add((chapter, verse))
                        rows.append(SourceVerse(work_id, chapter, verse, text))
    except (BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("current publication bundle is malformed.") from error
    return tuple(rows)


def _group_rows(rows: tuple[SourceVerse, ...]) -> dict[str, tuple[SourceVerse, ...]]:
    grouped: dict[str, list[SourceVerse]] = defaultdict(list)
    for row in rows:
        grouped[row.work_id].append(row)
    return {work_id: tuple(values) for work_id, values in grouped.items()}


def _family_markdown(payload: dict[str, object]) -> str:
    totals = payload["totals"]
    assert type(totals) is dict
    lines = [
        "# World Messianic Bible Source Verification",
        "",
        "- Collection role: 39-work source family in a mixed-source English research collection",
        "- Collection claim: not a complete or official Ethiopian Bible",
        f"- Source artifact SHA-256: `{payload['source_artifact_sha256']}`",
        f"- Current publication SHA-256: `{payload['current_publication_sha256']}`",
        f"- Parser: `{payload['parser_version']}`",
        "- Rights and naming condition: public-domain dedication; modified wording must not be called World Messianic Bible",
        "",
        "## Totals",
        "",
        *(f"- {name.title()}: {totals[name]}" for name in ("exact", "formatting", "missing", "extra", "wording")),
        "",
        "## Work reports",
        "",
    ]
    for work in payload["works"]:
        assert type(work) is dict
        lines.append(
            f"- `{work['work_id']}`: report SHA-256 `{work['report_sha256']}`"
        )
    return "\n".join(lines) + "\n"


class WmbVplAdapter:
    """Task-4 CLI adapter for deterministic WMB comparison and candidates."""

    def compare_family(
        self, *, definition, lock_record, artifact_path, current_bundle, output,
    ):
        from app.library.verification.cli import CompareFamilyResult

        source = _group_rows(parse_wmb_vpl(artifact_path, definition))
        current = _group_rows(_load_current_rows(current_bundle, definition))
        publication_sha = sha256(Path(current_bundle).read_bytes()).hexdigest()
        work_output = Path(output) / definition.family_id
        reports = []
        totals = {name: 0 for name in ("exact", "formatting", "missing", "extra", "wording")}
        for work_id in definition.expected_work_ids:
            report = compare_work(
                work_id, current[work_id], source[work_id], ComparisonRules(),
                source_artifact_sha256=lock_record.sha256,
                current_publication_sha256=publication_sha,
                parser_version=PARSER_VERSION,
            )
            write_report_pair(report, work_output, work_id)
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

        del lock_record, report_dir
        if not replace_from_source:
            raise ValueError("WMB source candidates require explicit source replacement.")
        grouped = _group_rows(parse_wmb_vpl(artifact_path, definition))
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
        return CandidateBuildResult(work_count=len(index), output_id="wmb-candidate.zip")
