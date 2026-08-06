#!/usr/bin/env python3
"""Generate the reviewed manifest for the corrected composite-English bundle."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any
from zipfile import ZipFile


SOURCE_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SOURCE_DIRECTORY.parents[2]
if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.library.ingest.manifest import SourceManifest  # noqa: E402


def _load_bundle_module(source_dir: Path):
    path = source_dir / "build_bundle.py"
    spec = importlib.util.spec_from_file_location("eotc_build_bundle_constants", path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("could not load build_bundle.py")
    spec.loader.exec_module(module)
    return module


MEQABYAN_URLS = {
    "1-meqabyan": "https://en.wikisource.org/w/index.php?title=Translation:1_Meqabyan&oldid=16044809",
    "2-meqabyan": "https://en.wikisource.org/w/index.php?title=Translation:2_Meqabyan&oldid=16044810",
    "3-meqabyan": "https://en.wikisource.org/w/index.php?title=Translation:3_Meqabyan&oldid=16044811",
}
KJV_WORKS = {
    "baruch", "letter-of-jeremiah", "prayer-of-azariah", "susanna",
    "bel-and-the-dragon", "prayer-of-manasseh",
}
WEB_WORKS = {
    "ezra-sutuel", "second-ezra", "tobit", "judith",
    "wisdom-of-solomon", "sirach",
}
UNNUMBERED_ENOCH_CHAPTERS = [3, 4, 35, 44]


def _base_source(
    *, source_key: str, source_label: str, translator: str | None,
    source_language: str, source_tradition: str, published_year: int | None,
    license_spdx: str, attribution: str, provenance_url: str | None,
    fallback: bool = False, modified: bool = False,
    modification_note: str | None = None,
) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "source_label": source_label,
        "translator": translator,
        "source_language": source_language,
        "source_tradition": source_tradition,
        "published_year": published_year,
        "license_spdx": license_spdx,
        "attribution": attribution,
        "provenance_url": provenance_url,
        "fallback": fallback,
        "modified": modified,
        "modification_note": modification_note,
        "verification_status": "provisional",
    }


def _work_source(work_id: str, source_group: str) -> dict[str, Any]:
    if source_group == "wmb":
        source = _base_source(
            source_key="world-messianic-bible",
            source_label="World Messianic Bible (archive revision unverified)",
            translator="World Messianic Bible contributors",
            source_language="Hebrew",
            source_tradition="Hebrew Masoretic tradition",
            published_year=None,
            license_spdx="LicenseRef-Public-Domain",
            attribution="Public-domain World Messianic Bible text supplied by the user archive; exact upstream revision is not preserved.",
            provenance_url=None,
            modified=True,
            modification_note="Source chapter identifiers were normalized to numeric order and app work names were standardized; scripture prose and source verse labels were not changed.",
        )
    elif source_group == "peshitta":
        source = _base_source(
            source_key="murdock-peshitta-1852",
            source_label="Murdock Peshitta (1852; archive revision unverified)",
            translator="James Murdock",
            source_language="Syriac Aramaic",
            source_tradition="Syriac Peshitta New Testament",
            published_year=1852,
            license_spdx="LicenseRef-Public-Domain",
            attribution="James Murdock's 1852 public-domain English Peshitta translation supplied by the user archive; exact upstream revision is not preserved.",
            provenance_url=None,
            modified=True,
            modification_note="Source chapter identifiers were normalized to numeric order, FI emphasis delimiters and RF translator-note blocks were removed, ten blank reserved source positions were omitted and declared, four U+000F separators across three verse texts were normalized to spaces, and app work names were standardized; scripture words outside source apparatus and source verse labels were not changed.",
        )
    elif work_id in WEB_WORKS:
        source = _base_source(
            source_key="world-english-bible-apocrypha",
            source_label="World English Bible British Edition with Deuterocanon",
            translator="World English Bible contributors",
            source_language="Greek and Hebrew",
            source_tradition="World English Bible Deuterocanon",
            published_year=None,
            license_spdx="LicenseRef-Public-Domain",
            attribution="Official public-domain World English Bible British Edition with Deuterocanon from eBible.org.",
            provenance_url="https://ebible.org/details.php?id=eng-webbe",
            modified=work_id == "sirach",
            modification_note=(
                "The official VPL's 24 explicit blank Sirach rows and 12 additional absent numeric labels were omitted and declared as known missing positions; every nonblank scripture row retains its official chapter and verse identity."
                if work_id == "sirach" else None
            ),
        )
    elif work_id in KJV_WORKS:
        source = _base_source(
            source_key="kjv-1611-fallback",
            source_label="KJV 1611 fallback (archive text)",
            translator="King James Version translators",
            source_language="Greek and Hebrew",
            source_tradition="King James Version Apocrypha",
            published_year=1611,
            license_spdx="LicenseRef-Public-Domain",
            attribution="Public-domain KJV 1611 fallback supplied by the user archive; this is not a distinct Ethiopian Orthodox English translation.",
            provenance_url=None,
            fallback=True,
        )
    elif source_group == "meqabyan":
        note = (
            "Source extraction and JSON formatting were applied without invented text. "
            "Verse labels 16:9 and 21:9 are absent in permanent revision oldid 16044810."
            if work_id == "2-meqabyan"
            else "Source extraction and JSON formatting were applied without changing scripture prose."
        )
        source = _base_source(
            source_key="wikisource-meqabyan-geez",
            source_label="Wikisource Meqabyan translation from Ge'ez",
            translator="Wikisource contributors",
            source_language="Ge'ez",
            source_tradition="Ethiopian Meqabyan",
            published_year=None,
            license_spdx="CC-BY-SA-4.0",
            attribution="Wikisource contributors, CC BY-SA 4.0. Reuse must give attribution, identify changes, link the license, and preserve ShareAlike terms.",
            provenance_url=MEQABYAN_URLS[work_id],
            modified=True,
            modification_note=note,
        )
    elif work_id == "1-enoch":
        source = _base_source(
            source_key="rh-charles-ethiopic",
            source_label="R. H. Charles, The Book of Enoch (Project Gutenberg 77935)",
            translator="R. H. Charles",
            source_language="Ethiopic and Greek",
            source_tradition="Ethiopic Enoch",
            published_year=1917,
            license_spdx="LicenseRef-Public-Domain",
            attribution="R. H. Charles, The Book of Enoch (1917), Project Gutenberg ebook 77935; public domain in the USA.",
            provenance_url="https://www.gutenberg.org/ebooks/77935",
            modified=True,
            modification_note="The displayed reading follows R. H. Charles's Ethiopic (E) main text; separately marked Greek alternate-recension blocks are excluded. Wrapped lines and lettered verse fragments were deterministically joined and presentation whitespace normalized. Source chapters 3, 4, 35, and 44 have no verse numbering and are stored as structural verse 1 solely for the app container.",
        )
    elif work_id == "jubilees":
        source = _base_source(
            source_key="rh-charles-ethiopic",
            source_label="R. H. Charles Jubilees (archive text; revision unverified)",
            translator="R. H. Charles",
            source_language="Ethiopic and Greek",
            source_tradition="Ethiopic Jubilees",
            published_year=None,
            license_spdx="LicenseRef-Public-Domain",
            attribution="Public-domain R. H. Charles Jubilees text supplied by the user archive; exact edition is not preserved.",
            provenance_url=None,
            modified=True,
            modification_note="Source chapter identifiers were normalized to numeric order and the app work identifier was standardized; scripture prose was not changed.",
        )
    else:
        raise ValueError(f"unsupported source mapping for {work_id}: {source_group}")
    source["canon_scope"] = "supplemental" if work_id == "prayer-of-manasseh" else "ethio81"
    return source


def _coverage(corrected_zip: Path, book_map: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    expected: dict[str, Any] = {}
    groups: dict[str, str] = {}
    with ZipFile(corrected_zip) as archive:
        index = json.loads(archive.read("data/index.json"))
        records = index["books"]
        if len(records) != 83 or {record["id"] for record in records} != set(book_map):
            raise ValueError("corrected index does not match the reviewed book map")
        for record in records:
            work_id = book_map[record["id"]]
            chapters = json.loads(archive.read(record["file"]))
            expected[work_id] = {
                "chapters": len(chapters),
                "verse_counts": {
                    str(chapter["c"]): len(chapter["v"]) for chapter in chapters
                },
            }
            groups[work_id] = record["src"]
    return expected, groups


def build(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    bundle = _load_bundle_module(source_dir)
    report = json.loads((output_dir / "data-quality-report.json").read_text(encoding="utf-8"))
    corrected_zip = output_dir / "corrected-bundle.zip"
    actual_checksum = sha256(corrected_zip.read_bytes()).hexdigest()
    expected_checksum = report.get("corrected_bundle_sha256")
    if actual_checksum != expected_checksum:
        raise ValueError(
            "corrected bundle checksum mismatch: "
            f"{actual_checksum} != {expected_checksum}"
        )
    expected, groups = _coverage(corrected_zip, bundle.BOOK_MAP)
    if sum(item["chapters"] for item in expected.values()) != 1_520:
        raise ValueError("corrected coverage must contain 1,520 chapters")
    if sum(sum(item["verse_counts"].values()) for item in expected.values()) != report["corrected_verse_count"]:
        raise ValueError("manifest coverage does not match corrected report")
    work_sources = {
        work_id: _work_source(work_id, groups[work_id]) for work_id in expected
    }
    if Counter(source["canon_scope"] for source in work_sources.values()) != Counter({"ethio81": 82, "supplemental": 1}):
        raise ValueError("work source scopes do not match 82+1 reviewed scope")

    raw = {
        "edition_code": "EOTC-COMPOSITE-EN",
        "name": "Ethiopian Orthodox Composite English",
        "reading_language": "English",
        "source_language": "Mixed",
        "script": "Latin",
        "translator": None,
        "publisher": None,
        "published_year": None,
        "license_spdx": "LicenseRef-Mixed",
        "attribution": "A provisional mixed-source general-reading compilation combining public-domain sources with CC BY-SA 4.0 Meqabyan translations. See each work source and README.md.",
        "provenance_url": "https://github.com/obtaylor1/unbound-bible",
        "source_tradition": "Composite English sources associated with ETHIO81 works",
        "relationship": "general_reading",
        "versification": "Source-specific chapter and verse numbering",
        "expected_works": expected,
        "source_files": [{
            "path": "corrected-bundle.zip",
            "sha256": report["corrected_bundle_sha256"],
            "source_url": None,
        }],
        "adapter": "composite_english_bundle",
        "adapter_options": {
            "book_map": bundle.BOOK_MAP,
            "work_sources": work_sources,
            "supplemental_works": ["prayer-of-manasseh"],
            "known_missing_verses": {
                work: {str(chapter): verses for chapter, verses in chapters.items()}
                for work, chapters in bundle.KNOWN_MISSING.items()
            },
        },
        "source_verification": "provisional",
    }
    manifest = SourceManifest.model_validate(raw).model_dump(mode="json")
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (output_dir / "manifest.json").write_text(rendered, encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=SOURCE_DIRECTORY)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary)
            bundle = _load_bundle_module(SOURCE_DIRECTORY)
            bundle.build(SOURCE_DIRECTORY, generated)
            build(SOURCE_DIRECTORY, generated)
            if not (args.output_dir / "manifest.json").exists() or (args.output_dir / "manifest.json").read_bytes() != (generated / "manifest.json").read_bytes():
                print("manifest.json is missing or stale", file=sys.stderr)
                return 1
        return 0
    build(SOURCE_DIRECTORY, args.output_dir)
    print(f"wrote {args.output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
