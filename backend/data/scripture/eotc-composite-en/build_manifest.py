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
from app.library.verification.adapters.wmb_vpl import parse_wmb_vpl  # noqa: E402
from app.library.verification.adapters.murdock_sword import (  # noqa: E402
    DECLARED_OMISSIONS as MURDOCK_DECLARED_OMISSIONS,
    HISTORICAL_EVIDENCE_FILENAME as MURDOCK_HISTORICAL_EVIDENCE_FILENAME,
    parse_murdock_sword,
    validate_historical_evidence as validate_murdock_historical_evidence,
)
from app.library.verification.adapters.gutenberg_kjv_apocrypha import (  # noqa: E402
    HISTORICAL_EVIDENCE_FILENAME as KJV_HISTORICAL_EVIDENCE_FILENAME,
    PARSER_VERSION as KJV_PARSER_VERSION,
    REPORT_TRANSFORMATIONS as KJV_REPORT_TRANSFORMATIONS,
    reviewed_gutenberg_kjv_apocrypha,
    validate_historical_evidence as validate_kjv_historical_evidence,
)
from app.library.verification.adapters.charles_jubilees import (  # noqa: E402
    HISTORICAL_EVIDENCE_FILENAME as JUBILEES_HISTORICAL_EVIDENCE_FILENAME,
    PARSER_VERSION as JUBILEES_PARSER_VERSION,
    SOURCE_ARTIFACT_SHA256 as JUBILEES_ARTIFACT_SHA256,
    SOURCE_ARTIFACT_SIZE as JUBILEES_ARTIFACT_SIZE,
    parse_charles_jubilees,
    validate_historical_evidence as validate_jubilees_historical_evidence,
)
from app.library.verification.registry import (  # noqa: E402
    APPROVED_SOURCE_DEFINITIONS,
    ArtifactLockRecord,
    load_artifact_lock,
    verify_artifact,
)
from app.library.verification.report import report_json_bytes, report_sha256  # noqa: E402
from app.library.verification.types import (  # noqa: E402
    ComparisonCounts,
    ComparisonRules,
    CurrentPublicationIdentity,
    DifferenceClassification,
    SourceArtifactIdentity,
    VerseDifference,
    VersePosition,
    WorkComparisonReport,
)


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
WMB_ARTIFACT_SHA256 = "02aef8d71addf7bf01438d1d132536f3d2cceb21820df6427015cddd608cfbf8"
WMB_ARTIFACT_SIZE = 4_283_520
WMB_RETRIEVED_AT = "2026-08-18T11:09:49Z"
WMB_REVIEWED_AT = "2026-08-29T00:38:39Z"
WMB_ARTIFACT_FILENAME = "engwmb_vpl.zip"
WMB_SOURCE_URL = "https://ebible.org/Scriptures/engwmb_vpl.zip"
WMB_LANDING_URL = "https://ebible.org/find/show.php?id=engwmb"
# Immutable provenance contract for the publication that produced the retained
# pre-rebuild comparison evidence and its canonical family summary.
WMB_PRE_REBUILD_BUNDLE_SHA256 = (
    "4383d4af7c6768fdd093ff37fecb61dcaf657673dcea184ad27bb1ee1eaecf63"
)
WMB_PRE_REBUILD_FAMILY_REPORT_SHA256 = (
    "11cf7360feb44945cb969b7205673ea56c89825a5cff245dd0e7e9d1fbd94eff"
)
MURDOCK_ARTIFACT_SHA256 = "4f0adeba385acbfa37921f66677d4aaf99e23b4e65ca162f122832689036641f"
MURDOCK_ARTIFACT_SIZE = 396_427
MURDOCK_RETRIEVED_AT = "2026-08-29T05:53:51Z"
MURDOCK_REVIEWED_AT = "2026-08-29T19:56:29Z"
MURDOCK_REVIEWER = "OpenAI Codex (AI-assisted source verification)"
MURDOCK_ARTIFACT_FILENAME = "murdock-source.zip"
MURDOCK_SOURCE_URL = "https://crosswire.org/ftpmirror/pub/sword/packages/rawzip/Murdock.zip"
MURDOCK_LANDING_URL = "https://crosswire.org/sword/modules/ModInfo.jsp?modName=Murdock"
MURDOCK_PRE_REBUILD_BUNDLE_SHA256 = (
    "370d680b248d935d7b6e4217f10124d58c918b5d0f80a83af422b82fbf3370a9"
)
MURDOCK_PRE_REBUILD_FAMILY_REPORT_SHA256 = (
    "a74cd77bddd3532ff34afcaae87d6784fa7a420695049c4b5f664e7b05683c6e"
)
KJV_ARTIFACT_SHA256 = "83de0c18742ba22b3d442c3a5bc828fe9e91dff27ae3c298e9b5c9a6ecfbf4d4"
KJV_ARTIFACT_SIZE = 835_071
KJV_RETRIEVED_AT = "2026-08-29T22:27:25Z"
KJV_REVIEWED_AT = "2026-08-30T01:18:59Z"
KJV_REVIEWER = "OpenAI Codex (AI-assisted source verification)"
KJV_ARTIFACT_FILENAME = "project-gutenberg-124.txt"
KJV_SOURCE_URL = "https://www.gutenberg.org/cache/epub/124/pg124.txt"
KJV_LANDING_URL = "https://www.gutenberg.org/ebooks/124"
KJV_PRE_REBUILD_BUNDLE_SHA256 = (
    "49a874a784640bc2b698e1e23c38b3fb7643715e7230c190539c6242e2849bd9"
)
KJV_PRE_REBUILD_FAMILY_REPORT_SHA256 = (
    "d167b92e9862685e35656f5afb16a8e3994c87624fafd9e845e2755416fb91d2"
)
JUBILEES_ARTIFACT_FILENAME = "rh-charles-jubilees-1917-authorized-reprint.html"
JUBILEES_SOURCE_URL = "https://www.globalgreyebooks.com/online-ebooks/r-h-charles_book-of-jubilees_complete-text.html"
JUBILEES_RETRIEVED_AT = "2026-08-30T02:00:00Z"
JUBILEES_REVIEWED_AT = "2026-08-30T08:55:00Z"
JUBILEES_PRE_REBUILD_BUNDLE_SHA256 = (
    "122c991ad814bf1e34f0b4baf0f59d31c4636207e6effa5142ad08cf9ce550bf"
)
JUBILEES_PRE_REBUILD_FAMILY_REPORT_SHA256 = (
    "8c8538e4261d6766ee13ecccefd9c30a605b66755b1e4cf25bdda226fcccdf7f"
)
_REVIEWED_ARTIFACT_FAMILIES = {
    "world-messianic-bible", "murdock-peshitta-1852", "kjv-1611-fallback",
    "rh-charles-jubilees-1902",
}
_REPORT_FIELDS = {
    "schema_version", "work_id", "source_artifact_sha256",
    "current_publication_sha256", "parser_version", "rules", "totals",
    "declared_omissions", "differences", "is_verified_candidate",
}
_TOTAL_FIELDS = {"exact", "formatting", "missing", "extra", "wording"}
_FAMILY_FIELDS = {
    "schema_version", "family_id", "source_artifact_sha256",
    "current_publication_sha256", "parser_version", "totals", "works",
}
_MURDOCK_FAMILY_FIELDS = _FAMILY_FIELDS | {"declared_omission_count"}
_KJV_FAMILY_FIELDS = _FAMILY_FIELDS | {"transformations", "comparison_source_stage"}


def _strict_object(value: object, fields: set[str], context: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f"{context} must contain exactly the required fields")
    return value


def _strict_work_report(payload: object) -> WorkComparisonReport:
    value = _strict_object(payload, _REPORT_FIELDS, "WMB work report")
    rules = _strict_object(
        value["rules"],
        {"unicode_form", "normalize_line_endings", "collapse_whitespace"},
        "WMB comparison rules",
    )
    totals = _strict_object(value["totals"], _TOTAL_FIELDS, "WMB comparison totals")
    omissions_value = value["declared_omissions"]
    differences_value = value["differences"]
    if type(omissions_value) is not list or type(differences_value) is not list:
        raise ValueError("WMB report omissions and differences must be lists")
    omissions = tuple(
        VersePosition(**_strict_object(item, {"chapter", "verse"}, "WMB omission"))
        for item in omissions_value
    )
    differences: list[VerseDifference] = []
    for value_item in differences_value:
        item = _strict_object(
            value_item,
            {"chapter", "verse", "classification", "current_text", "source_text"},
            "WMB difference",
        )
        try:
            classification = DifferenceClassification(item["classification"])
        except (TypeError, ValueError) as error:
            raise ValueError("WMB difference classification is invalid") from error
        differences.append(VerseDifference(
            position=VersePosition(item["chapter"], item["verse"]),
            classification=classification,
            current_text=item["current_text"],
            source_text=item["source_text"],
        ))
    parsed = WorkComparisonReport(
        schema_version=value["schema_version"],
        work_id=value["work_id"],
        source_artifact=SourceArtifactIdentity(value["source_artifact_sha256"]),
        current_publication=CurrentPublicationIdentity(
            value["current_publication_sha256"]
        ),
        parser_version=value["parser_version"],
        rules=ComparisonRules(**rules),
        totals=ComparisonCounts(**totals),
        declared_omissions=omissions,
        differences=tuple(differences),
    )
    if type(value["is_verified_candidate"]) is not bool or (
        value["is_verified_candidate"] != parsed.is_verified_candidate
    ):
        raise ValueError("WMB verified-candidate flag is invalid")
    return parsed


def _read_strict_work_report(
    path: Path, *, expected_checksum: object, label: str,
) -> WorkComparisonReport:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ValueError(f"{label} WMB child report inventory is invalid") from error
    if sha256(raw).hexdigest() != expected_checksum:
        raise ValueError(f"{label} WMB work report checksum mismatch: {path.stem}")
    try:
        parsed = _strict_work_report(json.loads(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} WMB work report is invalid: {path.stem}") from error
    if raw != report_json_bytes(parsed) or report_sha256(parsed) != expected_checksum:
        raise ValueError(f"{label} WMB work report is not canonical: {path.stem}")
    return parsed


def _strict_family_report(
    report: object, *, label: str, expected_work_ids: list[str],
) -> dict[str, Any]:
    value = _strict_object(report, _FAMILY_FIELDS, f"{label} WMB family report")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["family_id"] != "world-messianic-bible"
        or value["source_artifact_sha256"] != WMB_ARTIFACT_SHA256
        or value["parser_version"] != "wmb-vpl/1"
        or type(value["works"]) is not list
    ):
        raise ValueError(f"{label} WMB report does not match reviewed evidence")
    SourceArtifactIdentity(value["source_artifact_sha256"])
    CurrentPublicationIdentity(value["current_publication_sha256"])
    totals = _strict_object(
        value["totals"], _TOTAL_FIELDS, f"{label} WMB family totals",
    )
    ComparisonCounts(**totals)
    work_ids: list[str] = []
    summed = Counter({name: 0 for name in _TOTAL_FIELDS})
    for raw_item in value["works"]:
        item = _strict_object(
            raw_item, {"work_id", "report_sha256", "totals"},
            f"{label} WMB family work",
        )
        work_ids.append(item["work_id"])
        SourceArtifactIdentity(item["report_sha256"])
        item_totals = _strict_object(
            item["totals"], _TOTAL_FIELDS, f"{label} WMB work totals",
        )
        ComparisonCounts(**item_totals)
        summed.update(item_totals)
    if work_ids != expected_work_ids or len(set(work_ids)) != len(work_ids):
        raise ValueError(f"{label} WMB report has an invalid work inventory")
    if dict(summed) != totals:
        raise ValueError(f"{label} WMB family totals do not match its work reports")
    return value


def _strict_murdock_family_report(
    report: object, *, label: str, expected_work_ids: list[str],
) -> dict[str, Any]:
    value = _strict_object(
        report, _MURDOCK_FAMILY_FIELDS, f"{label} Murdock family report",
    )
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["family_id"] != "murdock-peshitta-1852"
        or value["source_artifact_sha256"] != MURDOCK_ARTIFACT_SHA256
        or value["parser_version"] != "murdock-sword/1"
        or value["declared_omission_count"] != 10
        or type(value["works"]) is not list
    ):
        raise ValueError(f"{label} Murdock report does not match reviewed evidence")
    SourceArtifactIdentity(value["source_artifact_sha256"])
    CurrentPublicationIdentity(value["current_publication_sha256"])
    totals = _strict_object(
        value["totals"], _TOTAL_FIELDS, f"{label} Murdock family totals",
    )
    ComparisonCounts(**totals)
    work_ids: list[str] = []
    summed = Counter({name: 0 for name in _TOTAL_FIELDS})
    for raw_item in value["works"]:
        item = _strict_object(
            raw_item, {"work_id", "report_sha256", "totals"},
            f"{label} Murdock family work",
        )
        work_ids.append(item["work_id"])
        SourceArtifactIdentity(item["report_sha256"])
        item_totals = _strict_object(
            item["totals"], _TOTAL_FIELDS, f"{label} Murdock work totals",
        )
        ComparisonCounts(**item_totals)
        summed.update(item_totals)
    if work_ids != expected_work_ids or len(set(work_ids)) != len(work_ids):
        raise ValueError(f"{label} Murdock report has an invalid work inventory")
    if dict(summed) != totals:
        raise ValueError(f"{label} Murdock family totals do not match its work reports")
    return value


def _strict_kjv_family_report(
    report: object, *, label: str, expected_work_ids: list[str], parser_version: str,
    source_stage: str,
) -> dict[str, Any]:
    value = _strict_object(
        report, _KJV_FAMILY_FIELDS, f"{label} KJV fallback family report",
    )
    if (
        value["schema_version"] != 1
        or value["family_id"] != "kjv-1611-fallback"
        or value["source_artifact_sha256"] != KJV_ARTIFACT_SHA256
        or value["parser_version"] != parser_version
        or value["comparison_source_stage"] != source_stage
        or type(value["transformations"]) is not list
        or tuple(value["transformations"]) != KJV_REPORT_TRANSFORMATIONS
        or type(value["works"]) is not list
    ):
        raise ValueError(f"{label} KJV fallback report does not match reviewed evidence")
    SourceArtifactIdentity(value["source_artifact_sha256"])
    CurrentPublicationIdentity(value["current_publication_sha256"])
    totals = _strict_object(
        value["totals"], _TOTAL_FIELDS, f"{label} KJV fallback family totals",
    )
    ComparisonCounts(**totals)
    work_ids: list[str] = []
    summed = Counter({name: 0 for name in _TOTAL_FIELDS})
    for raw_item in value["works"]:
        item = _strict_object(
            raw_item, {"work_id", "report_sha256", "totals"},
            f"{label} KJV fallback family work",
        )
        work_ids.append(item["work_id"])
        SourceArtifactIdentity(item["report_sha256"])
        item_totals = _strict_object(
            item["totals"], _TOTAL_FIELDS, f"{label} KJV fallback work totals",
        )
        ComparisonCounts(**item_totals)
        summed.update(item_totals)
    if work_ids != expected_work_ids or len(set(work_ids)) != len(work_ids):
        raise ValueError(f"{label} KJV fallback report work inventory is invalid")
    if dict(summed) != totals:
        raise ValueError(f"{label} KJV fallback family totals do not reconcile")
    return value


def _verified_wmb_artifact(source_dir: Path) -> tuple[Path, ArtifactLockRecord]:
    try:
        lock = load_artifact_lock(
            source_dir / "verification/source-artifacts.lock.json"
        )
        if set(lock.artifacts) != _REVIEWED_ARTIFACT_FAMILIES:
            raise ValueError("lock must contain exactly the reviewed WMB and Murdock artifacts")
        record = lock.artifacts["world-messianic-bible"]
        retrieved_at = record.retrieved_at.isoformat().replace("+00:00", "Z")
        if (
            record.family_id != "world-messianic-bible"
            or record.artifact_path != WMB_ARTIFACT_FILENAME
            or record.source_url != WMB_SOURCE_URL
            or record.landing_url != WMB_LANDING_URL
            or retrieved_at != WMB_RETRIEVED_AT
            or record.size_bytes != WMB_ARTIFACT_SIZE
            or record.sha256 != WMB_ARTIFACT_SHA256
        ):
            raise ValueError("lock does not match the reviewed WMB artifact identity")
        definition = APPROVED_SOURCE_DEFINITIONS["world-messianic-bible"]
        identity = verify_artifact(
            record, definition, source_dir / "verification/artifacts",
        )
        if (
            identity.size_bytes != WMB_ARTIFACT_SIZE
            or identity.sha256 != WMB_ARTIFACT_SHA256
        ):
            raise ValueError("verified identity does not match reviewed WMB artifact")
    except (OSError, ValueError) as error:
        raise ValueError("WMB artifact lock or local artifact is invalid") from error
    return source_dir / "verification/artifacts" / record.artifact_path, record


def _verified_murdock_artifact(source_dir: Path) -> tuple[Path, ArtifactLockRecord]:
    try:
        lock = load_artifact_lock(
            source_dir / "verification/source-artifacts.lock.json"
        )
        if set(lock.artifacts) != _REVIEWED_ARTIFACT_FAMILIES:
            raise ValueError("lock must contain exactly the reviewed WMB and Murdock artifacts")
        record = lock.artifacts["murdock-peshitta-1852"]
        retrieved_at = record.retrieved_at.isoformat().replace("+00:00", "Z")
        if (
            record.family_id != "murdock-peshitta-1852"
            or record.artifact_path != MURDOCK_ARTIFACT_FILENAME
            or record.source_url != MURDOCK_SOURCE_URL
            or record.landing_url != MURDOCK_LANDING_URL
            or retrieved_at != MURDOCK_RETRIEVED_AT
            or record.size_bytes != MURDOCK_ARTIFACT_SIZE
            or record.sha256 != MURDOCK_ARTIFACT_SHA256
        ):
            raise ValueError("lock does not match the reviewed Murdock artifact identity")
        definition = APPROVED_SOURCE_DEFINITIONS["murdock-peshitta-1852"]
        identity = verify_artifact(
            record, definition, source_dir / "verification/artifacts",
        )
        if (
            identity.size_bytes != MURDOCK_ARTIFACT_SIZE
            or identity.sha256 != MURDOCK_ARTIFACT_SHA256
        ):
            raise ValueError("verified identity does not match reviewed Murdock artifact")
    except (OSError, ValueError) as error:
        raise ValueError("Murdock artifact lock or local artifact is invalid") from error
    return source_dir / "verification/artifacts" / record.artifact_path, record


def _verified_kjv_artifact(source_dir: Path) -> tuple[Path, ArtifactLockRecord]:
    try:
        lock = load_artifact_lock(source_dir / "verification/source-artifacts.lock.json")
        if set(lock.artifacts) != _REVIEWED_ARTIFACT_FAMILIES:
            raise ValueError("lock must contain exactly the three reviewed artifacts")
        record = lock.artifacts["kjv-1611-fallback"]
        retrieved_at = record.retrieved_at.isoformat().replace("+00:00", "Z")
        if (
            record.artifact_path != KJV_ARTIFACT_FILENAME
            or record.source_url != KJV_SOURCE_URL
            or record.landing_url != KJV_LANDING_URL
            or retrieved_at != KJV_RETRIEVED_AT
            or record.size_bytes != KJV_ARTIFACT_SIZE
            or record.sha256 != KJV_ARTIFACT_SHA256
        ):
            raise ValueError("lock does not match the reviewed KJV fallback artifact")
        definition = APPROVED_SOURCE_DEFINITIONS["kjv-1611-fallback"]
        identity = verify_artifact(
            record, definition, source_dir / "verification/artifacts",
        )
        if identity.size_bytes != KJV_ARTIFACT_SIZE or identity.sha256 != KJV_ARTIFACT_SHA256:
            raise ValueError("verified identity does not match reviewed KJV artifact")
    except (OSError, ValueError) as error:
        raise ValueError("KJV fallback artifact lock or local artifact is invalid") from error
    return source_dir / "verification/artifacts" / record.artifact_path, record


def _verified_jubilees_artifact(source_dir: Path) -> tuple[Path, ArtifactLockRecord]:
    try:
        lock = load_artifact_lock(source_dir / "verification/source-artifacts.lock.json")
        if set(lock.artifacts) != _REVIEWED_ARTIFACT_FAMILIES:
            raise ValueError("lock must contain exactly the four reviewed artifacts")
        record = lock.artifacts["rh-charles-jubilees-1902"]
        retrieved_at = record.retrieved_at.isoformat().replace("+00:00", "Z")
        if (
            record.artifact_path != JUBILEES_ARTIFACT_FILENAME
            or record.source_url != JUBILEES_SOURCE_URL
            or record.landing_url != JUBILEES_SOURCE_URL
            or retrieved_at != JUBILEES_RETRIEVED_AT
            or record.size_bytes != JUBILEES_ARTIFACT_SIZE
            or record.sha256 != JUBILEES_ARTIFACT_SHA256
        ):
            raise ValueError("lock does not match the reviewed Jubilees artifact")
        definition = APPROVED_SOURCE_DEFINITIONS["rh-charles-jubilees-1902"]
        identity = verify_artifact(
            record, definition, source_dir / "verification/artifacts",
        )
        if (
            identity.size_bytes != JUBILEES_ARTIFACT_SIZE
            or identity.sha256 != JUBILEES_ARTIFACT_SHA256
        ):
            raise ValueError("verified identity does not match reviewed Jubilees artifact")
    except (OSError, ValueError) as error:
        raise ValueError("Jubilees artifact lock or local artifact is invalid") from error
    return source_dir / "verification/artifacts" / record.artifact_path, record


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
        "verification_status": "in_progress",
        "source_edition": None,
        "source_revision": None,
        "rights_url": None,
        "rights_jurisdiction": None,
        "artifact_filename": None,
        "artifact_retrieved_at": None,
        "artifact_size": None,
        "artifact_sha256": None,
        "parser_version": None,
        "transformations": [],
        "comparison_exact": 0,
        "comparison_formatting": 0,
        "comparison_missing": 0,
        "comparison_extra": 0,
        "comparison_wording": 0,
        "comparison_report_sha256": None,
        "reviewer": None,
        "reviewed_at": None,
        "review_note": None,
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
            source_label="R. H. Charles, The Book of Jubilees (1902 translation)",
            translator="R. H. Charles",
            source_language="Ethiopic and Greek",
            source_tradition="Ethiopic Jubilees",
            published_year=1902,
            license_spdx="LicenseRef-Public-Domain",
            attribution="R. H. Charles's public-domain 1902 English translation, transcribed from the authorized 1917 reprint and correlated to the locked 1902 A. and C. Black scan.",
            provenance_url=JUBILEES_SOURCE_URL,
            modified=True,
            modification_note="Rebuilt to the exact 1,307 Charles-numbered positions. Introductory/editorial material, footnotes, page headers, marginal A.M. labels, and end matter were excluded; HTML whitespace and Unicode were normalized; only seven scan-confirmed marker defects and the scan-confirmed collapsed chapter-27 structure were repaired.",
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


def _load_wmb_verification(
    source_dir: Path, corrected_bundle_sha256: str, expected_work_ids: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    artifact_path, artifact_lock = _verified_wmb_artifact(source_dir)
    reports_dir = source_dir / "verification/reports"
    pre_summary_bytes = (
        reports_dir / "world-messianic-bible-pre-rebuild.json"
    ).read_bytes()
    if sha256(pre_summary_bytes).hexdigest() != WMB_PRE_REBUILD_FAMILY_REPORT_SHA256:
        raise ValueError("pre-rebuild WMB family report is not the reviewed evidence")
    pre_payload = json.loads(pre_summary_bytes)
    final_payload = json.loads(
        (reports_dir / "world-messianic-bible.json").read_text(encoding="utf-8")
    )
    expected = list(expected_work_ids)
    try:
        pre = _strict_family_report(
            pre_payload, label="pre-rebuild", expected_work_ids=expected,
        )
        final = _strict_family_report(
            final_payload, label="final", expected_work_ids=expected,
        )
    except ValueError as error:
        if "WMB" in str(error):
            raise
        raise ValueError("WMB family report is invalid") from error
    if pre["current_publication_sha256"] != WMB_PRE_REBUILD_BUNDLE_SHA256:
        raise ValueError("pre-rebuild WMB report does not bind the reviewed publication")
    if final["current_publication_sha256"] != corrected_bundle_sha256:
        raise ValueError("final WMB report does not bind the generated bundle")
    if final["totals"] != {
        "exact": 23_145, "formatting": 0, "missing": 0,
        "extra": 0, "wording": 0,
    }:
        raise ValueError("final WMB report must be an exact 23,145-position match")
    if pre["totals"] != {
        "exact": 22_922, "formatting": 0, "missing": 0,
        "extra": 0, "wording": 223,
    }:
        raise ValueError("pre-rebuild WMB report does not match reviewed totals")

    expected_filenames = {f"{work_id}.json" for work_id in expected}
    for family in ("world-messianic-bible-pre-rebuild", "world-messianic-bible"):
        directory = reports_dir / family
        try:
            filenames = {path.name for path in directory.glob("*.json") if path.is_file()}
        except OSError as error:
            raise ValueError(f"{family} WMB child report inventory is invalid") from error
        if filenames != expected_filenames:
            raise ValueError(f"{family} WMB child report inventory is invalid")

    definition = APPROVED_SOURCE_DEFINITIONS["world-messianic-bible"]
    source_rows = parse_wmb_vpl(artifact_path, definition)
    source_counts = Counter(row.work_id for row in source_rows)
    if set(source_counts) != set(expected):
        raise ValueError("WMB source rows do not match the reviewed work inventory")

    pre_by_work = {item["work_id"]: item for item in pre["works"]}
    final_by_work = {item["work_id"]: item for item in final["works"]}
    rebuilt = {
        work_id for work_id, item in pre_by_work.items()
        if item.get("totals", {}).get("wording", 0) > 0
    }
    if len(rebuilt) != 27 or len(set(expected) - rebuilt) != 12:
        raise ValueError("WMB review must classify exactly 27 rebuilt and 12 exact works")

    evidence: dict[str, dict[str, Any]] = {}
    for work_id in expected:
        pre_item = pre_by_work[work_id]
        final_item = final_by_work[work_id]
        pre_totals = pre_item["totals"]
        totals = final_item["totals"]
        if (
            any(totals[name] != 0 for name in ("formatting", "missing", "extra", "wording"))
            or totals["exact"] <= 0
            or totals["exact"] != source_counts[work_id]
        ):
            raise ValueError(f"final WMB work report is not exact: {work_id}")
        work_report = reports_dir / "world-messianic-bible" / f"{work_id}.json"
        final_report = _read_strict_work_report(
            work_report,
            expected_checksum=final_item["report_sha256"],
            label="final",
        )
        canonical_checksum = report_sha256(final_report)
        pre_work_report = (
            reports_dir / "world-messianic-bible-pre-rebuild" / f"{work_id}.json"
        )
        pre_report = _read_strict_work_report(
            pre_work_report,
            expected_checksum=pre_item["report_sha256"],
            label="pre-rebuild",
        )
        for label, report, publication_sha, summary_item in (
            ("pre-rebuild", pre_report, pre["current_publication_sha256"], pre_item),
            ("final", final_report, corrected_bundle_sha256, final_item),
        ):
            if (
                report.work_id != work_id
                or report.source_artifact.sha256 != WMB_ARTIFACT_SHA256
                or report.current_publication.sha256 != publication_sha
                or report.parser_version != "wmb-vpl/1"
                or report.rules != ComparisonRules()
                or report.totals != ComparisonCounts(**summary_item["totals"])
            ):
                raise ValueError(f"{label} WMB work report identity mismatch: {work_id}")
        if (
            any(pre_totals[name] != 0 for name in ("formatting", "missing", "extra"))
            or pre_totals["exact"] + pre_totals["wording"] != totals["exact"]
        ):
            raise ValueError(f"pre-rebuild WMB work totals are invalid: {work_id}")
        prior_wording = pre_totals["wording"]
        was_rebuilt = work_id in rebuilt
        evidence[work_id] = {
            "source_label": "World Messianic Bible",
            "published_year": 2022,
            "attribution": (
                "Official World Messianic Bible August 2022 stable text from eBible.org, "
                "dedicated to the public domain. The World Messianic Bible name is a "
                "trademark and may not be used for changed wording."
            ),
            "provenance_url": artifact_lock.landing_url,
            "modified": was_rebuilt,
            "modification_note": (
                f"Official-source rebuild replaced {prior_wording} wording-different "
                "positions from the prior archive; the installed wording now exactly "
                "matches the official eBible VPL source. The World Messianic Bible "
                "name is retained because its scripture wording was not changed."
                if was_rebuilt else
                "The work was deterministically rebuilt from the official eBible VPL "
                "source; its prior wording was already exact, so no scripture wording "
                "changed. The World Messianic Bible name is retained because its "
                "scripture wording was not changed."
            ),
            "verification_status": "verified_rebuilt" if was_rebuilt else "verified_exact",
            "source_edition": "World Messianic Bible, August 2022 stable text",
            "source_revision": "Official eBible engwmb VPL archive",
            "rights_url": artifact_lock.landing_url,
            "rights_jurisdiction": (
                "Public-domain dedication; World Messianic Bible naming condition applies"
            ),
            "artifact_filename": artifact_lock.artifact_path,
            "artifact_retrieved_at": artifact_lock.retrieved_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "artifact_size": artifact_lock.size_bytes,
            "artifact_sha256": artifact_lock.sha256,
            "parser_version": "wmb-vpl/1",
            "transformations": [
                "Converted the official VPL rows to deterministic app JSON while preserving every work, chapter, verse label, and scripture text."
            ],
            "comparison_exact": totals["exact"],
            "comparison_formatting": 0,
            "comparison_missing": 0,
            "comparison_extra": 0,
            "comparison_wording": 0,
            "comparison_report_sha256": canonical_checksum,
            "reviewer": "Obie Taylor",
            "reviewed_at": WMB_REVIEWED_AT,
            "review_note": (
                "Administrator review approved the official eBible VPL source, its "
                "public-domain dedication and World Messianic Bible naming condition, "
                "the pre-rebuild comparison, the official-source rebuild where "
                "required, and the final exact comparison on 2026-08-28 "
                "America/New_York (2026-08-29T00:38:39Z)."
            ),
        }
    return evidence


def _load_murdock_verification(
    source_dir: Path, corrected_bundle_sha256: str,
    expected_work_ids: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    artifact_path, artifact_lock = _verified_murdock_artifact(source_dir)
    definition = APPROVED_SOURCE_DEFINITIONS["murdock-peshitta-1852"]
    reports_dir = source_dir / "verification/reports"
    historical_evidence = validate_murdock_historical_evidence(
        reports_dir / MURDOCK_HISTORICAL_EVIDENCE_FILENAME,
        source_dir / "verification", definition,
    )
    historical_formatting_works = {
        sample["work_id"] for sample in historical_evidence["samples"]
        if sample["result"] == "confirmed_formatting"
    }
    if historical_formatting_works != {"jude"}:
        raise ValueError("Murdock historical formatting inventory is not canonical")
    pre_summary_path = reports_dir / "murdock-peshitta-1852-pre-rebuild.json"
    pre_summary_bytes = pre_summary_path.read_bytes()
    if sha256(pre_summary_bytes).hexdigest() != MURDOCK_PRE_REBUILD_FAMILY_REPORT_SHA256:
        raise ValueError("pre-rebuild Murdock family report is not the reviewed evidence")
    pre = _strict_murdock_family_report(
        json.loads(pre_summary_bytes), label="pre-rebuild",
        expected_work_ids=list(expected_work_ids),
    )
    final = _strict_murdock_family_report(
        json.loads((reports_dir / "murdock-peshitta-1852.json").read_text()),
        label="final", expected_work_ids=list(expected_work_ids),
    )
    if pre["current_publication_sha256"] != MURDOCK_PRE_REBUILD_BUNDLE_SHA256:
        raise ValueError("pre-rebuild Murdock report does not bind the reviewed publication")
    if final["current_publication_sha256"] != corrected_bundle_sha256:
        raise ValueError("final Murdock report does not bind the generated bundle")
    if pre["totals"] != {
        "exact": 6_872, "formatting": 1, "missing": 0,
        "extra": 0, "wording": 1_074,
    }:
        raise ValueError("pre-rebuild Murdock report does not match reviewed totals")
    if final["totals"] != {
        "exact": 7_947, "formatting": 0, "missing": 0,
        "extra": 0, "wording": 0,
    }:
        raise ValueError("final Murdock report must be an exact 7,947-position match")
    expected_filenames = {f"{work_id}.json" for work_id in expected_work_ids}
    for family in ("murdock-peshitta-1852-pre-rebuild", "murdock-peshitta-1852"):
        directory = reports_dir / family
        filenames = {path.name for path in directory.glob("*.json") if path.is_file()}
        if filenames != expected_filenames:
            raise ValueError(f"{family} Murdock child report inventory is invalid")
    source_rows = parse_murdock_sword(artifact_path, definition)
    source_counts = Counter(row.work_id for row in source_rows)
    if set(source_counts) != set(expected_work_ids):
        raise ValueError("Murdock source rows do not match the reviewed work inventory")
    pre_by_work = {item["work_id"]: item for item in pre["works"]}
    final_by_work = {item["work_id"]: item for item in final["works"]}
    rebuilt = {
        work_id for work_id, item in pre_by_work.items()
        if item["totals"]["wording"] or item["totals"]["formatting"]
    }
    if len(rebuilt) != 26 or set(expected_work_ids) - rebuilt != {"3-john"}:
        raise ValueError("Murdock review must classify exactly 26 rebuilt and one exact work")
    evidence: dict[str, dict[str, Any]] = {}
    for work_id in expected_work_ids:
        pre_item = pre_by_work[work_id]
        final_item = final_by_work[work_id]
        pre_report = _read_strict_work_report(
            reports_dir / "murdock-peshitta-1852-pre-rebuild" / f"{work_id}.json",
            expected_checksum=pre_item["report_sha256"], label="pre-rebuild Murdock",
        )
        final_report = _read_strict_work_report(
            reports_dir / "murdock-peshitta-1852" / f"{work_id}.json",
            expected_checksum=final_item["report_sha256"], label="final Murdock",
        )
        expected_omissions = tuple(
            VersePosition(chapter, verse)
            for chapter, verse in MURDOCK_DECLARED_OMISSIONS.get(work_id, ())
        )
        for label, report, publication_sha, summary_item in (
            ("pre-rebuild", pre_report, MURDOCK_PRE_REBUILD_BUNDLE_SHA256, pre_item),
            ("final", final_report, corrected_bundle_sha256, final_item),
        ):
            if (
                report.work_id != work_id
                or report.source_artifact.sha256 != MURDOCK_ARTIFACT_SHA256
                or report.current_publication.sha256 != publication_sha
                or report.parser_version != "murdock-sword/1"
                or report.rules != ComparisonRules()
                or report.totals != ComparisonCounts(**summary_item["totals"])
                or report.declared_omissions != expected_omissions
            ):
                raise ValueError(f"{label} Murdock work report identity mismatch: {work_id}")
        totals = final_item["totals"]
        if (
            any(totals[name] for name in ("formatting", "missing", "extra", "wording"))
            or totals["exact"] != source_counts[work_id]
        ):
            raise ValueError(f"final Murdock work report is not exact: {work_id}")
        pre_totals = pre_item["totals"]
        if (
            pre_totals["missing"] or pre_totals["extra"]
            or sum(pre_totals[name] for name in ("exact", "formatting", "wording"))
            != totals["exact"]
        ):
            raise ValueError(f"pre-rebuild Murdock work totals are invalid: {work_id}")
        was_rebuilt = work_id in rebuilt
        evidence[work_id] = {
            "source_label": "James Murdock's Translation of the Syriac Peshitta",
            "published_year": 1852,
            "attribution": (
                "James Murdock's 1852 public-domain English translation of the "
                "Syriac Peshitta, CrossWire SWORD module Murdock version 1.2."
            ),
            "provenance_url": artifact_lock.landing_url,
            "modified": was_rebuilt,
            "modification_note": (
                "Deterministically rebuilt from the locked official CrossWire module; "
                f"the prior archive differed at {pre_totals['wording']} wording and "
                f"{pre_totals['formatting']} formatting positions. Reviewed RF translator "
                "apparatus, FI presentation delimiters, and U+000F separators were "
                "normalized. The uniquely marked Philemon 1:1 spill was recovered "
                "from the locked module bytes without inventing wording."
                if was_rebuilt else
                "Deterministically rebuilt from the locked official CrossWire module; "
                "the prior wording was already exact. Reviewed source apparatus and "
                "separator transformations were applied without changing its scripture wording."
            ),
            "verification_status": (
                "review_required"
                if historical_evidence["totals"]["review_required"]
                else ("verified_rebuilt" if was_rebuilt else "verified_exact")
            ),
            "source_edition": (
                "Murdock Peshitta translation (published 1852); historical witness: "
                "ninth edition (1915)"
            ),
            "source_revision": (
                "CrossWire SWORD module Murdock 1.2 (2002-01-01); locked 1915 "
                "ninth-edition scan witness"
            ),
            "rights_url": artifact_lock.landing_url,
            "rights_jurisdiction": "Public domain",
            "artifact_filename": artifact_lock.artifact_path,
            "artifact_retrieved_at": artifact_lock.retrieved_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "artifact_size": artifact_lock.size_bytes,
            "artifact_sha256": artifact_lock.sha256,
            "parser_version": "murdock-sword/1",
            "transformations": [
                "Removed RF/Rf translator-note apparatus and FI/Fi presentation delimiters.",
                "Normalized U+000F separators to spaces while preserving surrounding words.",
                "Recovered Philemon 1:1 from its unique philemon1:01 spill marker and removed that spill from Colossians 4:18.",
                "Decoded exactly two reviewed 0x86 bytes in the Matthew 27:42 source context as the printed dagger (†): one inside removed RF apparatus and one retained at the verse boundary; no other Latin-1 byte was reinterpreted.",
                "Preserved and disclosed the exact ten blank source positions as declared omissions.",
            ],
            "comparison_exact": totals["exact"],
            "comparison_formatting": 0,
            "comparison_missing": 0,
            "comparison_extra": 0,
            "comparison_wording": 0,
            "comparison_report_sha256": report_sha256(final_report),
            "reviewer": MURDOCK_REVIEWER,
            "reviewed_at": MURDOCK_REVIEWED_AT,
            "review_note": (
                "The locked CrossWire electronic source passed final exact comparison. "
                "A locked 1915 ninth edition supplied historical corroboration through "
                "81 outcome-independent samples (one predetermined median position in "
                "each work third): "
                f"{historical_evidence['totals']['confirmed_ocr']} exact OCR-window "
                f"confirmations, {historical_evidence['totals']['confirmed_visual']} "
                "locked-PDF visual confirmations, one disclosed formatting variance, "
                f"and {historical_evidence['totals']['review_required']} unresolved. "
                "The electronic-source comparison remains exact. This was an "
                "AI-assisted evidence review; no human visual review is claimed."
            ),
        }
        if work_id == "jude":
            evidence[work_id]["review_note"] += (
                " Retained the locked CrossWire electronic reading 'shootingstars' at "
                "Jude 1:13 while disclosing that the 1915 ninth-edition witness prints "
                "'shooting-stars'; this exact closed-compound versus hyphenated-compound "
                "variance belongs to the historical witness review and does not change "
                "the final exact electronic-source comparison or rebuilt status."
            )
        if work_id == "matthew":
            evidence[work_id]["modification_note"] += (
                " At Matthew 27:42, exactly two reviewed 0x86 bytes were decoded "
                "as the historically printed dagger (†): one was inside removed RF "
                "apparatus and one was retained at the verse boundary; no other "
                "Latin-1 byte was reinterpreted."
            )
    return evidence


def _load_kjv_verification(
    source_dir: Path, corrected_bundle_sha256: str,
    expected_work_ids: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    artifact_path, artifact_lock = _verified_kjv_artifact(source_dir)
    definition = APPROVED_SOURCE_DEFINITIONS["kjv-1611-fallback"]
    verification_root = source_dir / "verification"
    historical = validate_kjv_historical_evidence(
        verification_root / KJV_HISTORICAL_EVIDENCE_FILENAME,
        verification_root, definition,
    )
    if (
        len(historical["samples"]) != 18
        or len(historical["adjudications"]) != 378
        or len(historical["scan_backed_corrections"]) != 4
        or historical["human_visual_review_claimed"] is not False
    ):
        raise ValueError("KJV fallback historical evidence inventory is invalid")
    reports_dir = verification_root / "reports"
    pre_path = reports_dir / "kjv-1611-fallback-pre-rebuild.json"
    pre_bytes = pre_path.read_bytes()
    if sha256(pre_bytes).hexdigest() != KJV_PRE_REBUILD_FAMILY_REPORT_SHA256:
        raise ValueError("pre-rebuild KJV fallback family report is not reviewed evidence")
    pre = _strict_kjv_family_report(
        json.loads(pre_bytes), label="pre-rebuild",
        expected_work_ids=list(expected_work_ids), parser_version=KJV_PARSER_VERSION,
        source_stage="locked electronic artifact before rebuild",
    )
    final = _strict_kjv_family_report(
        json.loads((reports_dir / "kjv-1611-fallback.json").read_text()),
        label="final", expected_work_ids=list(expected_work_ids),
        parser_version=f"{KJV_PARSER_VERSION}+scan-reviewed",
        source_stage="scan-reviewed electronic transcription",
    )
    if pre["current_publication_sha256"] != KJV_PRE_REBUILD_BUNDLE_SHA256:
        raise ValueError("pre-rebuild KJV fallback report publication identity changed")
    if final["current_publication_sha256"] != corrected_bundle_sha256:
        raise ValueError("final KJV fallback report does not bind generated bundle")
    if pre["totals"] != {
        "exact": 9, "formatting": 0, "missing": 0, "extra": 0, "wording": 378,
    }:
        raise ValueError("pre-rebuild KJV fallback totals are invalid")
    if final["totals"] != {
        "exact": 387, "formatting": 0, "missing": 0, "extra": 0, "wording": 0,
    }:
        raise ValueError("final KJV fallback comparison must be exact")
    expected_names = {f"{work_id}.json" for work_id in expected_work_ids}
    for family in ("kjv-1611-fallback-pre-rebuild", "kjv-1611-fallback"):
        directory = reports_dir / family
        if {path.name for path in directory.glob("*.json") if path.is_file()} != expected_names:
            raise ValueError(f"{family} child report inventory is invalid")
    source_rows = reviewed_gutenberg_kjv_apocrypha(artifact_path, definition)
    source_counts = Counter(row.work_id for row in source_rows)
    if set(source_counts) != set(expected_work_ids) or sum(source_counts.values()) != 387:
        raise ValueError("KJV fallback reviewed source inventory is invalid")
    pre_by_work = {item["work_id"]: item for item in pre["works"]}
    final_by_work = {item["work_id"]: item for item in final["works"]}
    if any(not pre_by_work[work_id]["totals"]["wording"] for work_id in expected_work_ids):
        raise ValueError("all six KJV fallback works must retain rebuilt provenance")
    evidence: dict[str, dict[str, Any]] = {}
    for work_id in expected_work_ids:
        pre_item, final_item = pre_by_work[work_id], final_by_work[work_id]
        pre_report = _read_strict_work_report(
            reports_dir / "kjv-1611-fallback-pre-rebuild" / f"{work_id}.json",
            expected_checksum=pre_item["report_sha256"], label="pre-rebuild KJV fallback",
        )
        final_report = _read_strict_work_report(
            reports_dir / "kjv-1611-fallback" / f"{work_id}.json",
            expected_checksum=final_item["report_sha256"], label="final KJV fallback",
        )
        for label, report, publication, item, parser in (
            ("pre-rebuild", pre_report, KJV_PRE_REBUILD_BUNDLE_SHA256,
             pre_item, KJV_PARSER_VERSION),
            ("final", final_report, corrected_bundle_sha256,
             final_item, f"{KJV_PARSER_VERSION}+scan-reviewed"),
        ):
            if (
                report.work_id != work_id
                or report.source_artifact.sha256 != KJV_ARTIFACT_SHA256
                or report.current_publication.sha256 != publication
                or report.parser_version != parser
                or report.rules != ComparisonRules()
                or report.totals != ComparisonCounts(**item["totals"])
            ):
                raise ValueError(f"{label} KJV fallback work identity mismatch: {work_id}")
        totals = final_item["totals"]
        if (
            any(totals[name] for name in ("formatting", "missing", "extra", "wording"))
            or totals["exact"] != source_counts[work_id]
        ):
            raise ValueError(f"final KJV fallback work is not exact: {work_id}")
        evidence[work_id] = {
            "source_label": "KJV 1611 fallback (reviewed electronic transcription)",
            "published_year": 1611,
            "attribution": (
                "Public-domain KJV Apocrypha electronic transcription from Project "
                "Gutenberg eBook 124, historically corroborated against the University "
                "of Pennsylvania Colenda 1611 Great HE editio princeps scan. This remains "
                "a fallback source, not a distinct Ethiopian Orthodox English translation."
            ),
            "provenance_url": artifact_lock.landing_url,
            "fallback": True,
            "modified": True,
            "modification_note": (
                f"Rebuilt from the reviewed electronic source after {pre_item['totals']['wording']} "
                "disclosed pre-rebuild wording differences. Structural source mappings were "
                "applied and only four electronic transcription defects across the six-work "
                "family were corrected from the locked 1611 scan."
            ),
            "verification_status": "verified_rebuilt",
            "source_edition": (
                "King James Version Apocrypha (1611 Great HE family); Project Gutenberg "
                "eBook 124 electronic transcription"
            ),
            "source_revision": "Project Gutenberg eBook 124, updated 2021-08-26",
            "rights_url": artifact_lock.landing_url,
            "rights_jurisdiction": "Public domain in the USA",
            "artifact_filename": artifact_lock.artifact_path,
            "artifact_retrieved_at": artifact_lock.retrieved_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "artifact_size": artifact_lock.size_bytes,
            "artifact_sha256": artifact_lock.sha256,
            "parser_version": f"{KJV_PARSER_VERSION}+scan-reviewed",
            "transformations": [
                "Joined wrapped physical lines within each locked source position using one space.",
                "Mapped source Baruch 6:1-73 to Letter of Jeremiah 1:1-73.",
                "Mapped source Song of the Three Holy Children 2-68 to Prayer of Azariah 1:1-67; excluded Song 1 and editorial canonical Daniel prose.",
                "Mapped the unnumbered Prayer of Manasses to Prayer of Manasseh 1:1.",
                "Applied exactly four scan-backed transcription corrections: drinck→drink, dour→door, life up→lift up, and iniquites→iniquities.",
            ],
            "comparison_exact": totals["exact"],
            "comparison_formatting": 0, "comparison_missing": 0,
            "comparison_extra": 0, "comparison_wording": 0,
            "comparison_report_sha256": report_sha256(final_report),
            "reviewer": KJV_REVIEWER, "reviewed_at": KJV_REVIEWED_AT,
            "review_note": (
                "The final publication exactly matches the reviewed electronic transcription "
                "after the four narrowly recorded scan-backed corrections. All 378 initial "
                "wording differences were individually adjudicated against the locked 1611 "
                "page set, and 18 beginning/middle/end samples were fixed before outcome. "
                "This was an AI-assisted visual evidence review; no human visual review is claimed."
            ),
        }
    return evidence


def _load_jubilees_verification(
    source_dir: Path, corrected_bundle_sha256: str,
) -> dict[str, Any]:
    artifact_path, artifact_lock = _verified_jubilees_artifact(source_dir)
    definition = APPROVED_SOURCE_DEFINITIONS["rh-charles-jubilees-1902"]
    verification_root = source_dir / "verification"
    historical = validate_jubilees_historical_evidence(
        verification_root / JUBILEES_HISTORICAL_EVIDENCE_FILENAME,
        verification_root, definition,
    )
    if (
        historical["edition_equivalence"] != "sampled_no_revision_detected"
        or historical["numbered_position_count"] != 1307
        or len(historical["samples"]) != 9
        or len(historical["marker_repairs"]) != 7
        or historical["human_visual_review_claimed"] is not False
    ):
        raise ValueError("Jubilees historical evidence inventory is invalid")
    reports = verification_root / "reports"
    pre_bytes = (reports / "rh-charles-jubilees-1902-pre-rebuild.json").read_bytes()
    if sha256(pre_bytes).hexdigest() != JUBILEES_PRE_REBUILD_FAMILY_REPORT_SHA256:
        raise ValueError("pre-rebuild Jubilees family report is not reviewed evidence")
    pre = json.loads(pre_bytes)
    final = json.loads((reports / "rh-charles-jubilees-1902.json").read_bytes())
    required_family = _FAMILY_FIELDS | {"edition_equivalence", "numbered_position_count"}
    for label, value in (("pre-rebuild", pre), ("final", final)):
        _strict_object(value, required_family, f"{label} Jubilees family report")
        if (
            value["family_id"] != definition.family_id
            or value["source_artifact_sha256"] != JUBILEES_ARTIFACT_SHA256
            or value["parser_version"] != JUBILEES_PARSER_VERSION
            or value["edition_equivalence"] != "sampled_no_revision_detected"
            or value["numbered_position_count"] != 1307
            or type(value["works"]) is not list or len(value["works"]) != 1
            or value["works"][0].get("work_id") != "jubilees"
        ):
            raise ValueError(f"{label} Jubilees family report identity is invalid")
    if pre["current_publication_sha256"] != JUBILEES_PRE_REBUILD_BUNDLE_SHA256:
        raise ValueError("pre-rebuild Jubilees report publication identity changed")
    if final["current_publication_sha256"] != corrected_bundle_sha256:
        raise ValueError("final Jubilees report does not bind generated bundle")
    if pre["totals"] != {
        "exact": 54, "formatting": 0, "missing": 0, "extra": 451, "wording": 1253,
    }:
        raise ValueError("pre-rebuild Jubilees totals are invalid")
    final_totals = {
        "exact": 1307, "formatting": 0, "missing": 0, "extra": 0, "wording": 0,
    }
    if final["totals"] != final_totals:
        raise ValueError("final Jubilees comparison must be exact")
    rows = parse_charles_jubilees(
        artifact_path, definition, expected_sha256=JUBILEES_ARTIFACT_SHA256,
    )
    if len(rows) != 1307:
        raise ValueError("reviewed Jubilees source inventory is invalid")
    pre_item, final_item = pre["works"][0], final["works"][0]
    pre_report = _read_strict_work_report(
        reports / "rh-charles-jubilees-1902-pre-rebuild/jubilees.json",
        expected_checksum=pre_item["report_sha256"], label="pre-rebuild Jubilees",
    )
    final_report = _read_strict_work_report(
        reports / "rh-charles-jubilees-1902/jubilees.json",
        expected_checksum=final_item["report_sha256"], label="final Jubilees",
    )
    for label, report, publication, totals in (
        ("pre-rebuild", pre_report, JUBILEES_PRE_REBUILD_BUNDLE_SHA256, pre["totals"]),
        ("final", final_report, corrected_bundle_sha256, final_totals),
    ):
        if (
            report.work_id != "jubilees"
            or report.source_artifact.sha256 != JUBILEES_ARTIFACT_SHA256
            or report.current_publication.sha256 != publication
            or report.parser_version != JUBILEES_PARSER_VERSION
            or report.rules != ComparisonRules()
            or report.totals != ComparisonCounts(**totals)
        ):
            raise ValueError(f"{label} Jubilees work report identity mismatch")
    return {
        "source_label": "R. H. Charles, The Book of Jubilees (1902 translation)",
        "published_year": 1902,
        "attribution": (
            "R. H. Charles's public-domain 1902 English translation. The machine-readable "
            "text is the authorized 1917 reprint transcription, correlated to the locked "
            "1902 A. and C. Black scan."
        ),
        "provenance_url": artifact_lock.landing_url,
        "modified": True,
        "modification_note": (
            "Rebuilt from the reviewed matching edition after 1,253 wording/segmentation "
            "differences and 451 extra fragments. The installed text now matches all 1,307 "
            "Charles-numbered positions. Editorial matter, footnotes, page headers, marginal "
            "A.M. labels, and end matter were excluded; only seven scan-confirmed marker "
            "defects and the scan-confirmed chapter-27 structure were repaired."
        ),
        "verification_status": "verified_rebuilt",
        "source_edition": "R. H. Charles, The Book of Jubilees (London: A. and C. Black, 1902)",
        "source_revision": "Authorized 1917 reprint transcription; 1902 scan authority",
        "rights_url": artifact_lock.landing_url,
        "rights_jurisdiction": "Public domain in the USA",
        "artifact_filename": artifact_lock.artifact_path,
        "artifact_retrieved_at": artifact_lock.retrieved_at.isoformat().replace("+00:00", "Z"),
        "artifact_size": artifact_lock.size_bytes,
        "artifact_sha256": artifact_lock.sha256,
        "parser_version": JUBILEES_PARSER_VERSION,
        "transformations": historical["transformations"],
        "comparison_exact": 1307,
        "comparison_formatting": 0,
        "comparison_missing": 0,
        "comparison_extra": 0,
        "comparison_wording": 0,
        "comparison_report_sha256": report_sha256(final_report),
        "reviewer": "OpenAI Codex (AI-assisted source verification)",
        "reviewed_at": JUBILEES_REVIEWED_AT,
        "review_note": (
            "Nine fixed beginning/middle/end scan correlations detected no revision in "
            "the sampled passages; this is not a full-edition collation. "
            "The primary 1902 numbering totals 1,307 positions; the inconsistent secondary "
            "1,341 claim was rejected. This was AI-assisted review; no human visual review "
            "is claimed, and this source record makes no complete or official Ethiopian Bible claim."
        ),
    }


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
    wmb_definition = bundle.APPROVED_SOURCE_DEFINITIONS["world-messianic-bible"]
    wmb_evidence = _load_wmb_verification(
        source_dir,
        report["corrected_bundle_sha256"],
        wmb_definition.expected_work_ids,
    )
    for work_id, evidence in wmb_evidence.items():
        work_sources[work_id].update(evidence)
    murdock_definition = bundle.APPROVED_SOURCE_DEFINITIONS["murdock-peshitta-1852"]
    murdock_evidence = _load_murdock_verification(
        source_dir,
        report["corrected_bundle_sha256"],
        murdock_definition.expected_work_ids,
    )
    for work_id, evidence in murdock_evidence.items():
        work_sources[work_id].update(evidence)
    kjv_definition = bundle.APPROVED_SOURCE_DEFINITIONS["kjv-1611-fallback"]
    kjv_evidence = _load_kjv_verification(
        source_dir,
        report["corrected_bundle_sha256"],
        kjv_definition.expected_work_ids,
    )
    for work_id, evidence in kjv_evidence.items():
        work_sources[work_id].update(evidence)
    work_sources["jubilees"].update(
        _load_jubilees_verification(source_dir, report["corrected_bundle_sha256"])
    )
    if Counter(source["canon_scope"] for source in work_sources.values()) != Counter({"ethio81": 82, "supplemental": 1}):
        raise ValueError("work source scopes do not match 82+1 reviewed scope")

    raw = {
        "edition_code": "EOTC-COMPOSITE-EN",
        "name": "Ethiopian Canon Research Collection — Mixed-source English",
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
