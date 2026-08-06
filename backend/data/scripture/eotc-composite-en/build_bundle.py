#!/usr/bin/env python3
"""Build the reviewed, deterministic composite-English scripture bundle."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


RAW_ARCHIVE = "Ethiopian Orthodox Bible (Non-KJV Edition).zip"
WEB_ARCHIVE = "eng-webbe_vpl.zip"
ENOCH_TEXT = "project-gutenberg-77935.txt"
INPUT_CHECKSUMS = {
    RAW_ARCHIVE: "0f4bdff8e24ee7e67afbd939d68a8dc40c0f1cf27026066dbb9f92ce34b183a2",
    WEB_ARCHIVE: "dc16460ed5e890e7b169cd3caeaa7e4adb4f7a6b5031bff85e4503389cd03b11",
    ENOCH_TEXT: "10d325355a810badf67bbbd1fe6bda77dc6e294eae78c2f6c69290188af45b14",
}

BOOK_MAP = {
    "GEN": "genesis", "EXO": "exodus", "LEV": "leviticus",
    "NUM": "numbers", "DEU": "deuteronomy", "JOS": "joshua",
    "JDG": "judges", "RUT": "ruth", "1SA": "1-samuel",
    "2SA": "2-samuel", "1KI": "1-kings", "2KI": "2-kings",
    "1CH": "1-chronicles", "2CH": "2-chronicles", "JUB": "jubilees",
    "ENO": "1-enoch", "EZR": "ezra", "NEH": "nehemiah",
    "2ES": "second-ezra", "1ES": "ezra-sutuel", "TOB": "tobit",
    "JDT": "judith", "EST": "esther", "1MQ": "1-meqabyan",
    "2MQ": "2-meqabyan", "3MQ": "3-meqabyan", "JOB": "job",
    "PSA": "psalms", "PRO": "proverbs", "ECC": "ecclesiastes",
    "SNG": "song-of-solomon", "WIS": "wisdom-of-solomon", "SIR": "sirach",
    "ISA": "isaiah", "JER": "jeremiah", "LAM": "lamentations",
    "BAR": "baruch", "LJE": "letter-of-jeremiah", "EZK": "ezekiel",
    "DAN": "daniel", "AZA": "prayer-of-azariah", "SUS": "susanna",
    "BEL": "bel-and-the-dragon", "HOS": "hosea", "JOL": "joel",
    "AMO": "amos", "OBA": "obadiah", "JON": "jonah", "MIC": "micah",
    "NAM": "nahum", "HAB": "habakkuk", "ZEP": "zephaniah",
    "HAG": "haggai", "ZEC": "zechariah", "MAL": "malachi",
    "MAN": "prayer-of-manasseh", "MAT": "matthew", "MRK": "mark",
    "LUK": "luke", "JHN": "john", "ACT": "acts", "ROM": "romans",
    "1CO": "1-corinthians", "2CO": "2-corinthians", "GAL": "galatians",
    "EPH": "ephesians", "PHP": "philippians", "COL": "colossians",
    "1TH": "1-thessalonians", "2TH": "2-thessalonians",
    "1TI": "1-timothy", "2TI": "2-timothy", "TIT": "titus",
    "PHM": "philemon", "HEB": "hebrews", "JAS": "james",
    "1PE": "1-peter", "2PE": "2-peter", "1JN": "1-john",
    "2JN": "2-john", "3JN": "3-john", "JUD": "jude",
    "REV": "revelation",
}

SOURCE_GROUP_COUNTS = {
    "wmb": 39, "peshitta": 27, "web_apocrypha": 6,
    "kjv_apocrypha": 6, "meqabyan": 3, "extra": 2,
}
WEB_REPLACEMENTS = {
    "1ES": "1ES", "2ES": "4ES", "TOB": "TOB",
    "JDT": "JDT", "WIS": "WIS", "SIR": "SIR",
}
WEB_DISPLAY_NAMES = {
    "1ES": "1 Esdras", "2ES": "2 Esdras", "TOB": "Tobit",
    "JDT": "Judith", "WIS": "Wisdom of Solomon", "SIR": "Sirach",
}
WEB_EXPECTED_NONBLANK_COUNTS = {
    "1ES": 448, "2ES": 944, "TOB": 244,
    "JDT": 339, "WIS": 436, "SIR": 1_359,
}
KNOWN_MISSING = {
    "2-meqabyan": {16: [9], 21: [9]},
    "matthew": {26: [30, 45]},
    "mark": {4: [10], 8: [19], 9: [31], 11: [19]},
    "luke": {18: [35]},
    "acts": {19: [41], 20: [17]},
    "2-corinthians": {13: [14]},
    "sirach": {
        1: [5, 7, 21], 3: [19], 10: [21], 11: [15, 16], 13: [14],
        16: [15, 16], 17: [5, 9, 16, 18, 21], 18: [3],
        19: [18, 19, 21], 20: [3, 32], 22: [9, 10], 23: [28],
        24: [18, 24], 25: [12], 26: [19, 20, 21, 22, 23, 24, 25, 26, 27],
    },
}
WEB_RESERVED_BLANKS = {
    "1ES": {}, "2ES": {}, "TOB": {}, "JDT": {}, "WIS": {},
    "SIR": {
        1: [5, 7, 21], 3: [19], 10: [21], 11: [15], 13: [14],
        16: [15], 17: [5, 9, 16, 18, 21], 18: [3], 19: [18, 21],
        20: [3, 32], 22: [9], 23: [28], 24: [18, 24], 25: [12],
        26: [19],
    },
}
WEB_ABSENT_WITHOUT_ROWS = {
    "1ES": {}, "2ES": {}, "TOB": {}, "JDT": {}, "WIS": {},
    "SIR": {
        11: [16], 16: [16], 19: [19], 22: [10],
        26: [20, 21, 22, 23, 24, 25, 26, 27],
    },
}
EXPECTED_CORRECTED_VERSE_COUNT = 38_938

_LINE = re.compile(r"([^\s]+) ([1-9]\d*):([1-9]\d*) (.*)")
_ROMAN_CHAPTER = re.compile(r"^([IVXLCDM]+)\.\s*(.*)$")
_VERSE_MARKER = re.compile(
    r"(?<![\w])([1-9]\d*)(?:\s*_([a-z])\._|\^(?:\{)?([a-z])(?:\})?\.\s*|\s*([a-z])\s*\.\s*|\.\s*)"
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _verify_inputs(source_dir: Path) -> None:
    for name, expected in INPUT_CHECKSUMS.items():
        actual = _digest(source_dir / name)
        if actual != expected:
            raise ValueError(f"input checksum mismatch for {name}: {actual}")


def _roman_to_int(value: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = previous = 0
    for character in reversed(value):
        current = values[character]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u00a0", " ").split())


def _parse_enoch(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    starts = list(re.finditer(r"(?m)^I\. 1\. The words of the blessing of Enoch", text))
    if len(starts) != 1:
        raise ValueError("Gutenberg text must contain one Enoch scripture start")
    end = text.find("\nPRINTED IN GREAT BRITAIN", starts[0].start())
    if end < 0:
        raise ValueError("Gutenberg text is missing the Enoch scripture terminator")
    scripture = text[starts[0].start():end]
    blocks = [
        block for block in re.split(r"(?:\r?\n){2,}", scripture)
        if _clean_text(block)
    ]
    fragments: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    chapter = 0
    current_verse: int | None = None
    recension: str | None = None

    for raw_block in blocks:
        block = _clean_text(raw_block)
        if block == "E":
            recension = "ethiopic-main"
            continue
        if block in {"G^g", "G^s", "G^{s1}", "G^{s2}"}:
            recension = "alternate-greek"
            continue
        first_line = next(line for line in raw_block.splitlines() if line.strip())
        indent = len(first_line) - len(first_line.lstrip())
        if recension is not None and indent == 0:
            recension = None
        elif recension == "alternate-greek":
            continue
        marker = _ROMAN_CHAPTER.match(block)
        if marker:
            candidate = _roman_to_int(marker.group(1))
            remainder = marker.group(2)
            first_marker = _VERSE_MARKER.search(remainder)
            starts_with_verse = first_marker is not None and first_marker.start() <= 1
            unnumbered_chapter = candidate in {3, 4, 35, 44}
            if 1 <= candidate <= 108 and (
                starts_with_verse or unnumbered_chapter or "_" in remainder
            ):
                chapter = candidate
                current_verse = None
                if not starts_with_verse and not unnumbered_chapter:
                    continue
                block = remainder
        if not chapter or not block:
            continue
        matches = list(_VERSE_MARKER.finditer(block))
        if not matches:
            if current_verse is None:
                current_verse = 1
            fragments[chapter][current_verse].append(block)
            continue
        prefix = _clean_text(block[:matches[0].start()])
        if prefix and current_verse is not None:
            fragments[chapter][current_verse].append(prefix)
        for index, match in enumerate(matches):
            verse = int(match.group(1))
            end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
            text = _clean_text(block[match.end():end])
            current_verse = verse
            if text:
                fragments[chapter][verse].append(text)

    if set(fragments) != set(range(1, 109)):
        missing = sorted(set(range(1, 109)) - set(fragments))
        raise ValueError(f"Enoch must contain chapters I-CVIII; missing {missing}")
    chapters: list[dict[str, Any]] = []
    for chapter_number in range(1, 109):
        verses = fragments[chapter_number]
        if set(verses) != set(range(1, max(verses) + 1)):
            missing = sorted(set(range(1, max(verses) + 1)) - set(verses))
            raise ValueError(
                f"Enoch {chapter_number}: non-contiguous verse markers; missing {missing}"
            )
        rendered = []
        for verse_number in range(1, max(verses) + 1):
            text = _clean_text(" ".join(verses[verse_number]))
            if not text:
                raise ValueError(f"Enoch {chapter_number}:{verse_number} is empty")
            rendered.append({"n": verse_number, "t": text})
        chapters.append({"c": chapter_number, "v": rendered})
    if not chapters[79]["v"][0]["t"]:
        raise ValueError("Enoch 80:1 is missing")
    return chapters


def _parse_web(path: Path) -> dict[str, list[dict[str, Any]]]:
    positions: dict[str, dict[int, list[tuple[int, str]]]] = {
        source_id: defaultdict(list) for source_id in WEB_REPLACEMENTS
    }
    reverse = {external: source_id for source_id, external in WEB_REPLACEMENTS.items()}
    blanks: dict[str, dict[int, list[int]]] = {
        source_id: defaultdict(list) for source_id in WEB_REPLACEMENTS
    }
    with ZipFile(path) as archive:
        names = archive.namelist()
        if names.count("eng-webbe_vpl.txt") != 1:
            raise ValueError("WEB archive must contain exactly one eng-webbe_vpl.txt")
        lines = archive.read("eng-webbe_vpl.txt").decode("utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        match = _LINE.fullmatch(line)
        if not match:
            if line.split(" ", 1)[0] in reverse:
                raise ValueError(f"invalid WEB VPL line {line_number}")
            continue
        external, chapter_text, verse_text, text = match.groups()
        if external not in reverse:
            continue
        source_id = reverse[external]
        if not text.strip():
            blanks[source_id][int(chapter_text)].append(int(verse_text))
            continue
        positions[source_id][int(chapter_text)].append((int(verse_text), _clean_text(text)))

    output: dict[str, list[dict[str, Any]]] = {}
    for source_id, chapters in positions.items():
        if not chapters or set(chapters) != set(range(1, max(chapters) + 1)):
            raise ValueError(f"{source_id}: unexpected or missing WEB chapters")
        rendered_chapters = []
        for chapter_number in range(1, max(chapters) + 1):
            source_rows = chapters[chapter_number]
            labels = [number for number, _ in source_rows]
            if len(labels) != len(set(labels)) or labels != sorted(labels):
                raise ValueError(f"{source_id} {chapter_number}: duplicate/out-of-order WEB labels")
            verses = [
                {"n": source_number, "t": text}
                for source_number, text in source_rows
            ]
            if not verses:
                raise ValueError(f"{source_id} {chapter_number}: no WEB text")
            rendered_chapters.append({"c": chapter_number, "v": verses})
        output[source_id] = rendered_chapters
        if sum(len(chapter["v"]) for chapter in rendered_chapters) != WEB_EXPECTED_NONBLANK_COUNTS[source_id]:
            raise ValueError(f"{source_id}: official WEB nonblank row count changed")
        observed_blanks = {chapter: verses for chapter, verses in blanks[source_id].items()}
        if observed_blanks != WEB_RESERVED_BLANKS[source_id]:
            raise ValueError(f"{source_id}: official WEB reserved blank labels changed")
        observed_labels = {
            chapter: {number for number, _ in rows}
            for chapter, rows in positions[source_id].items()
        }
        for chapter, labels in blanks[source_id].items():
            observed_labels.setdefault(chapter, set()).update(labels)
        unexpected_present = {
            chapter: sorted(set(labels) & observed_labels.get(chapter, set()))
            for chapter, labels in WEB_ABSENT_WITHOUT_ROWS[source_id].items()
            if set(labels) & observed_labels.get(chapter, set())
        }
        if unexpected_present:
            raise ValueError(
                f"{source_id}: reviewed absent WEB labels unexpectedly appeared"
            )
    return output


def _raw_audit(archive: ZipFile, records: list[dict[str, Any]]) -> dict[str, int]:
    positions: dict[tuple[str, int, int], list[str]] = defaultdict(list)
    chapters = 0
    source_counts: Counter[str] = Counter()
    for record in records:
        source_counts[record["src"]] += 1
        book = json.loads(archive.read(record["file"]).decode("utf-8"))
        chapters += len(book)
        for chapter in book:
            for verse in chapter["v"]:
                positions[(record["id"], int(chapter["c"]), int(verse["n"]))].append(verse["t"])
    if source_counts != Counter(SOURCE_GROUP_COUNTS):
        raise ValueError(f"unexpected raw source groups: {source_counts}")
    exact = conflicting = 0
    for texts in positions.values():
        for text in texts[1:]:
            if text == texts[0]:
                exact += 1
            else:
                conflicting += 1
    audit = {
        "verse_records": sum(len(texts) for texts in positions.values()),
        "unique_verse_positions": len(positions),
        "exact_duplicate_excess_records": exact,
        "conflicting_duplicate_excess_records": conflicting,
        "chapters": chapters,
    }
    expected = {
        "verse_records": 44_114, "unique_verse_positions": 38_845,
        "exact_duplicate_excess_records": 5_252,
        "conflicting_duplicate_excess_records": 17, "chapters": 1_520,
    }
    if audit != expected:
        raise ValueError(f"raw archive audit changed: {audit}")
    return audit


def _canonical_untouched(
    source_id: str, chapters: Any, *, source_group: str | None = None
) -> list[dict[str, Any]]:
    if not isinstance(chapters, list) or not chapters:
        raise ValueError(f"{source_id}: book must be a nonempty list")
    by_number: dict[int, dict[str, Any]] = {}
    for chapter in chapters:
        if not isinstance(chapter, dict):
            raise ValueError(f"{source_id}: invalid chapter record")
        number = chapter.get("c")
        if (
            isinstance(number, str)
            and number.isdecimal()
            and str(int(number)) == number
            and int(number) > 0
        ):
            number = int(number)
        if type(number) is not int or number < 1:
            raise ValueError(f"{source_id}: invalid chapter ID")
        if number in by_number:
            raise ValueError(f"{source_id}: duplicate chapter {number}")
        verses = chapter.get("v")
        if source_group == "peshitta" and isinstance(verses, list):
            cleaned = []
            for verse in verses:
                verse = dict(verse)
                text = verse.get("t")
                if isinstance(text, str):
                    text = text.replace("\x0f", " ")
                    text = re.sub(r"<RF>.*?<Rf>", "", text, flags=re.DOTALL)
                    text = text.replace("<FI>", "").replace("<Fi>", "")
                    if re.search(r"<[^>]+>", text):
                        raise ValueError(f"{source_id}: unexpected source formatting code")
                    verse["t"] = text
                if isinstance(verse.get("t"), str) and verse["t"].strip():
                    cleaned.append(verse)
            verses = cleaned
        by_number[number] = {"c": number, "v": verses}
    if set(by_number) != set(range(1, len(chapters) + 1)):
        raise ValueError(f"{source_id}: chapters are not contiguous")
    return [by_number[number] for number in range(1, len(chapters) + 1)]


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_deterministic_zip(path: Path, members: dict[str, bytes]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(members):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, members[name], compress_type=ZIP_DEFLATED, compresslevel=9)


def build(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _verify_inputs(source_dir)
    web = _parse_web(source_dir / WEB_ARCHIVE)
    enoch = _parse_enoch(source_dir / ENOCH_TEXT)

    with ZipFile(source_dir / RAW_ARCHIVE) as raw:
        index = json.loads(raw.read("data/index.json").decode("utf-8"))
        records = [record for record in index.get("books", []) if record.get("file")]
        if len(records) != 83 or {record["id"] for record in records} != set(BOOK_MAP):
            raise ValueError("raw archive does not contain the reviewed 83-book map")
        audit = _raw_audit(raw, records)
        members: dict[str, bytes] = {}
        corrected_index = []
        per_work: dict[str, dict[str, int | str]] = {}
        per_source: Counter[str] = Counter()
        for record in records:
            source_id = record["id"]
            if source_id in web:
                chapters = web[source_id]
            elif source_id == "ENO":
                chapters = enoch
            else:
                chapters = _canonical_untouched(
                    source_id,
                    json.loads(raw.read(record["file"]).decode("utf-8")),
                    source_group=record["src"],
                )
            if len(chapters) != int(record["chapters"]):
                raise ValueError(f"{source_id}: corrected chapter count changed")
            corrected_record = dict(record)
            corrected_record["chapters"] = len(chapters)
            if source_id in WEB_DISPLAY_NAMES:
                corrected_record["name"] = WEB_DISPLAY_NAMES[source_id]
            corrected_index.append(corrected_record)
            members[record["file"]] = _json_bytes(chapters)
            count = sum(len(chapter["v"]) for chapter in chapters)
            work_id = BOOK_MAP[source_id]
            per_work[work_id] = {
                "source_id": source_id, "source_group": record["src"],
                "chapters": len(chapters), "verses": count,
            }
            per_source[record["src"]] += count
        corrected_index.sort(key=lambda item: list(BOOK_MAP).index(item["id"]))
        members["data/index.json"] = _json_bytes({"books": corrected_index})

    output_zip = output_dir / "corrected-bundle.zip"
    _write_deterministic_zip(output_zip, members)
    positions: set[tuple[str, int, int]] = set()
    undeclared: list[str] = []
    for work_id, details in per_work.items():
        member = next(r["file"] for r in corrected_index if r["id"] == details["source_id"])
        chapters = json.loads(members[member])
        declared = KNOWN_MISSING.get(work_id, {})
        for chapter in chapters:
            present = {int(verse["n"]) for verse in chapter["v"]}
            expected = set(range(1, max(present | set(declared.get(chapter["c"], []))) + 1))
            missing = expected - present
            if missing != set(declared.get(chapter["c"], [])):
                undeclared.append(f"{work_id} {chapter['c']}: {sorted(missing)}")
            for verse in chapter["v"]:
                key = (work_id, chapter["c"], verse["n"])
                if key in positions:
                    raise ValueError(f"duplicate corrected output position: {key}")
                positions.add(key)
    if undeclared:
        raise ValueError(f"corrected bundle contains undeclared gaps: {undeclared[:5]}")
    if len(positions) != EXPECTED_CORRECTED_VERSE_COUNT:
        raise ValueError(
            "corrected verse count changed: "
            f"{len(positions)} != {EXPECTED_CORRECTED_VERSE_COUNT}"
        )

    report = {
        "schema_version": 1,
        "generator_version": 1,
        "inputs": {
            name: {"sha256": checksum} for name, checksum in INPUT_CHECKSUMS.items()
        },
        "corrected_bundle_sha256": _digest(output_zip),
        "raw_archive": audit,
        "corrected_verse_count": len(positions),
        "per_work": dict(sorted(per_work.items())),
        "per_source_group_verses": dict(sorted(per_source.items())),
        "source_group_work_counts": SOURCE_GROUP_COUNTS,
        "replacements": {
            "official_webbe": sorted(BOOK_MAP[source] for source in WEB_REPLACEMENTS),
            "project_gutenberg_enoch": ["1-enoch"],
        },
        "web_reserved_blank_labels": {
            "sirach": {
                str(chapter): verses
                for chapter, verses in WEB_RESERVED_BLANKS["SIR"].items()
            }
        },
        "web_absent_labels_without_rows": {
            "sirach": {
                str(chapter): verses
                for chapter, verses in WEB_ABSENT_WITHOUT_ROWS["SIR"].items()
            }
        },
        "enoch_source_chapters_without_verse_numbers": [3, 4, 35, 44],
        "enoch_recension_handling": {
            "displayed_reading": "R. H. Charles Ethiopic (E) main reading",
            "excluded_alternates": ["G^g", "G^s", "G^{s1}", "G^{s2}"],
        },
        "archive_presentation_cleanup": {
            "murdock_peshitta": "Removed FI formatting delimiters and RF translator-note blocks; omitted and declared ten blank reserved positions; normalized four U+000F source separators across three verse texts to spaces; scripture words outside source apparatus and source verse labels were preserved."
        },
        "known_missing_verses": {
            work: {str(chapter): verses for chapter, verses in chapters.items()}
            for work, chapters in KNOWN_MISSING.items()
        },
        "duplicate_output_positions": 0,
        "undeclared_output_gaps": [],
        "scope": {
            "works": 83, "chapters": 1_520,
            "ethio81_works": 82, "supplemental_works": 1,
        },
    }
    (output_dir / "data-quality-report.json").write_bytes(_json_bytes(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source_dir = Path(__file__).resolve().parent
    if args.check:
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary)
            build(source_dir, generated)
            for name in ("corrected-bundle.zip", "data-quality-report.json"):
                if not (args.output_dir / name).exists() or (args.output_dir / name).read_bytes() != (generated / name).read_bytes():
                    print(f"{name} is missing or stale", file=sys.stderr)
                    return 1
        return 0
    report = build(source_dir, args.output_dir)
    print(f"wrote corrected bundle with {report['corrected_verse_count']:,} verses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
