import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from app.library.audit import AuditError, audit_bundle, render_markdown


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REVIEWED_BUNDLE = REPOSITORY_ROOT / "backend/data/scripture/eotc-composite-en"


def test_reviewed_composite_bundle_matches_the_frozen_release_scope():
    report = audit_bundle(REVIEWED_BUNDLE)

    assert report["scope"] == {
        "works": 83,
        "ethio81_works": 82,
        "supplemental_works": 1,
        "chapters": 1520,
        "verses": 38938,
    }
    assert report["source_group_work_counts"] == {
        "extra": 2,
        "kjv_apocrypha": 6,
        "meqabyan": 3,
        "peshitta": 27,
        "web_apocrypha": 6,
        "wmb": 39,
    }
    assert report["provisional_source_records"]["count"] == 83
    assert report["kjv_fallback_works"] == [
        "baruch",
        "bel-and-the-dragon",
        "letter-of-jeremiah",
        "prayer-of-azariah",
        "prayer-of-manasseh",
        "susanna",
    ]
    assert report["gap_status"]["undeclared_output_gaps"] == []


def test_audit_rejects_a_mismatched_corrected_verse_count(tmp_path):
    bundle = tmp_path / "bundle"
    shutil.copytree(REVIEWED_BUNDLE, bundle)
    report_path = bundle / "data-quality-report.json"
    quality_report = json.loads(report_path.read_text())
    quality_report["corrected_verse_count"] += 1
    report_path.write_text(json.dumps(quality_report))

    with pytest.raises(AuditError, match="corrected_verse_count"):
        audit_bundle(bundle)


def test_markdown_names_the_composite_scope_and_provenance_caveat():
    markdown = render_markdown(audit_bundle(REVIEWED_BUNDLE))

    assert "83 works" in markdown
    assert "82 ETHIO81 works" in markdown
    assert "1 supplemental work" in markdown
    assert "1,520 chapters" in markdown
    assert "38,938 verses" in markdown
    assert "extra: 2" in markdown
    assert "kjv_apocrypha: 6" in markdown
    assert "83 provisional source records" in markdown
    assert "KJV fallback works (6)" in markdown
    assert "Declared output gaps: 48" in markdown
    assert "Undeclared output gaps: none" in markdown
    assert "not one uniform Ethiopian translation" in markdown


def test_cli_writes_the_markdown_report_atomically(tmp_path):
    output = tmp_path / "ethiopian-composite-release-audit.md"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.library.audit",
            "--bundle",
            "data/scripture/eotc-composite-en",
            "--markdown",
            str(output),
        ],
        cwd=REPOSITORY_ROOT / "backend",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text() == render_markdown(audit_bundle(REVIEWED_BUNDLE))
    assert not list(tmp_path.glob(".*.tmp"))


def test_cli_returns_nonzero_without_writing_a_report_for_a_failed_audit(tmp_path):
    bundle = tmp_path / "bundle"
    shutil.copytree(REVIEWED_BUNDLE, bundle)
    report_path = bundle / "data-quality-report.json"
    quality_report = json.loads(report_path.read_text())
    quality_report["corrected_verse_count"] += 1
    report_path.write_text(json.dumps(quality_report))
    output = tmp_path / "failed-audit.md"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.library.audit",
            "--bundle",
            str(bundle),
            "--markdown",
            str(output),
        ],
        cwd=REPOSITORY_ROOT / "backend",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "corrected_verse_count" in result.stderr
    assert not output.exists()
