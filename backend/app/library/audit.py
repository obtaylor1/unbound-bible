"""Release-scope audit for the reviewed Ethiopian composite English bundle."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4


FROZEN_SCOPE = {
    "works": 83,
    "ethio81_works": 82,
    "supplemental_works": 1,
    "chapters": 1520,
    "verses": 38938,
}
FROZEN_SOURCE_GROUP_WORK_COUNTS = {
    "extra": 2,
    "kjv_apocrypha": 6,
    "meqabyan": 3,
    "peshitta": 27,
    "web_apocrypha": 6,
    "wmb": 39,
}
SOURCE_GROUP_KEYS = {
    "extra": "rh-charles-ethiopic",
    "kjv_apocrypha": "kjv-1611-fallback",
    "meqabyan": "wikisource-meqabyan-geez",
    "peshitta": "murdock-peshitta-1852",
    "web_apocrypha": "world-english-bible-apocrypha",
    "wmb": "world-messianic-bible",
}


class AuditError(ValueError):
    """Raised when the reviewed bundle no longer matches its frozen release scope."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise AuditError(f"Unable to load {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise AuditError(f"{path.name} must contain a JSON object.")
    return value


def _declared_gap_count(known_missing_verses: Any) -> int:
    if not isinstance(known_missing_verses, dict):
        return 0
    return sum(
        len(verses)
        for chapters in known_missing_verses.values()
        if isinstance(chapters, dict)
        for verses in chapters.values()
        if isinstance(verses, list)
    )


def _fail_if_any(errors: list[str]) -> None:
    if errors:
        raise AuditError("Composite release audit failed:\n- " + "\n- ".join(errors))


def audit_bundle(bundle: Path) -> dict[str, Any]:
    """Validate the reviewed bundle and return its deterministic audit report."""
    bundle = Path(bundle)
    manifest = _load_json(bundle / "manifest.json")
    quality = _load_json(bundle / "data-quality-report.json")
    errors: list[str] = []

    expected_works = manifest.get("expected_works")
    adapter_options = manifest.get("adapter_options")
    if not isinstance(adapter_options, dict):
        errors.append("manifest.adapter_options must be an object")
        adapter_options = {}
    work_sources = adapter_options.get("work_sources")
    per_work = quality.get("per_work")
    if not isinstance(expected_works, dict):
        errors.append("manifest.expected_works must be an object")
        expected_works = {}
    if not isinstance(work_sources, dict):
        errors.append("manifest.adapter_options.work_sources must be an object")
        work_sources = {}
    if not isinstance(per_work, dict):
        errors.append("data-quality-report.per_work must be an object")
        per_work = {}

    manifest_work_ids = set(expected_works)
    if manifest_work_ids != set(work_sources):
        errors.append("manifest expected works and work_sources do not name the same works")
    if manifest_work_ids != set(per_work):
        errors.append("manifest expected works and quality-report per_work do not name the same works")

    manifest_chapters = 0
    manifest_verses = 0
    quality_chapters = 0
    quality_verses = 0
    source_group_counts: dict[str, int] = {}
    for work_id in sorted(manifest_work_ids & set(per_work)):
        expected = expected_works[work_id]
        observed = per_work[work_id]
        if not isinstance(expected, dict) or not isinstance(observed, dict):
            errors.append(f"{work_id} has invalid coverage metadata")
            continue
        chapters = expected.get("chapters")
        verse_counts = expected.get("verse_counts")
        report_chapters = observed.get("chapters")
        report_verses = observed.get("verses")
        if not isinstance(chapters, int) or not isinstance(verse_counts, dict):
            errors.append(f"manifest expected coverage for {work_id} is invalid")
            continue
        if not all(isinstance(count, int) for count in verse_counts.values()):
            errors.append(f"manifest verse counts for {work_id} are invalid")
            continue
        manifest_chapters += chapters
        manifest_verses += sum(verse_counts.values())
        if not isinstance(report_chapters, int) or not isinstance(report_verses, int):
            errors.append(f"quality-report coverage for {work_id} is invalid")
            continue
        quality_chapters += report_chapters
        quality_verses += report_verses
        if chapters != report_chapters:
            errors.append(f"{work_id} chapter count differs between manifest and quality report")
        if sum(verse_counts.values()) != report_verses:
            errors.append(f"{work_id} verse count differs between manifest and quality report")
        source_group = observed.get("source_group")
        if not isinstance(source_group, str):
            errors.append(f"quality-report source group for {work_id} is invalid")
            continue
        source_group_counts[source_group] = source_group_counts.get(source_group, 0) + 1
        source = work_sources.get(work_id)
        expected_source_key = SOURCE_GROUP_KEYS.get(source_group)
        if not isinstance(source, dict) or source.get("source_key") != expected_source_key:
            errors.append(f"{work_id} source group does not match manifest work_sources")

    actual_scope = {
        "works": len(manifest_work_ids),
        "ethio81_works": sum(
            source.get("canon_scope") == "ethio81"
            for source in work_sources.values()
            if isinstance(source, dict)
        ),
        "supplemental_works": sum(
            source.get("canon_scope") == "supplemental"
            for source in work_sources.values()
            if isinstance(source, dict)
        ),
        "chapters": manifest_chapters,
        "verses": manifest_verses,
    }
    if actual_scope != FROZEN_SCOPE:
        errors.append(f"manifest release scope differs from frozen scope: {actual_scope}")
    if quality.get("scope") != {
        key: FROZEN_SCOPE[key]
        for key in ("works", "ethio81_works", "supplemental_works", "chapters")
    }:
        errors.append("quality-report scope differs from frozen scope")
    if quality.get("corrected_verse_count") != FROZEN_SCOPE["verses"]:
        errors.append("quality-report corrected_verse_count differs from frozen scope")
    if quality_chapters != FROZEN_SCOPE["chapters"] or quality_verses != FROZEN_SCOPE["verses"]:
        errors.append("quality-report per-work totals differ from frozen scope")
    if quality.get("source_group_work_counts") != FROZEN_SOURCE_GROUP_WORK_COUNTS:
        errors.append("quality-report source-group work counts differ from frozen scope")
    if source_group_counts != FROZEN_SOURCE_GROUP_WORK_COUNTS:
        errors.append("quality-report per-work source groups differ from frozen scope")
    if quality.get("undeclared_output_gaps") != []:
        errors.append("quality-report undeclared_output_gaps must be empty")

    provisional_work_ids = sorted(
        work_id
        for work_id, source in work_sources.items()
        if isinstance(source, dict) and source.get("verification_status") == "provisional"
    )
    fallback_work_ids = sorted(
        work_id
        for work_id, source in work_sources.items()
        if isinstance(source, dict) and source.get("fallback") is True
    )
    if len(fallback_work_ids) != FROZEN_SOURCE_GROUP_WORK_COUNTS["kjv_apocrypha"]:
        errors.append("manifest KJV fallback work count differs from frozen source-group scope")

    _fail_if_any(errors)
    return {
        "scope": actual_scope,
        "source_group_work_counts": FROZEN_SOURCE_GROUP_WORK_COUNTS,
        "provisional_source_records": {
            "count": len(provisional_work_ids),
            "work_ids": provisional_work_ids,
        },
        "kjv_fallback_works": fallback_work_ids,
        "gap_status": {
            "declared_output_gaps": _declared_gap_count(quality.get("known_missing_verses")),
            "undeclared_output_gaps": quality["undeclared_output_gaps"],
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the human-readable audit record for a validated bundle."""
    scope = report["scope"]
    source_groups = report["source_group_work_counts"]
    provisional = report["provisional_source_records"]
    fallback_works = report["kjv_fallback_works"]
    gaps = report["gap_status"]
    group_lines = "\n".join(
        f"- {group}: {source_groups[group]}"
        for group in sorted(source_groups)
    )
    fallback_list = ", ".join(fallback_works)
    undeclared = "none" if not gaps["undeclared_output_gaps"] else ", ".join(
        map(str, gaps["undeclared_output_gaps"])
    )
    return f"""# Ethiopian Composite English release audit

This reviewed release is a mixed-source general-reading compilation, **not one uniform Ethiopian translation**.

## Frozen scope

- {scope["works"]} works
- {scope["ethio81_works"]} ETHIO81 works
- {scope["supplemental_works"]} supplemental work
- {scope["chapters"]:,} chapters
- {scope["verses"]:,} verses

## Source groups

{group_lines}

## Source-record status

- {provisional["count"]} provisional source records
- KJV fallback works ({len(fallback_works)}): {fallback_list}

## Output gaps

- Declared output gaps: {gaps["declared_output_gaps"]}
- Undeclared output gaps: {undeclared}
"""


def _write_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = audit_bundle(arguments.bundle)
        _write_atomically(arguments.markdown, render_markdown(report))
    except AuditError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
