import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import app.library.audit as audit_module
from app.library.audit import (
    AuditError,
    audit_bundle,
    audit_composite_release,
    render_markdown,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REVIEWED_BUNDLE = REPOSITORY_ROOT / "backend/data/scripture/eotc-composite-en"


def _copy_reviewed_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    shutil.copytree(REVIEWED_BUNDLE, bundle)
    return bundle


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")


def test_reviewed_composite_bundle_matches_the_frozen_release_scope():
    report = audit_composite_release(REVIEWED_BUNDLE)

    assert report["status"] == "pass"
    assert report["scope"] == {
        "works": 83,
        "ethio81_works": 82,
        "supplemental_works": 1,
        "chapters": 1520,
        "verses": 38487,
    }
    assert report["source_groups"] == {
        "extra": 2,
        "kjv_apocrypha": 6,
        "meqabyan": 3,
        "peshitta": 27,
        "web_apocrypha": 6,
        "wmb": 39,
    }
    assert report["undeclared_output_gaps"] == []
    assert report["verified_works"] == 73
    assert report["in_progress_works"] == 10
    assert report["fallback_works"] == 6
    assert report["verification_status_records"]["verified_exact"]["count"] == 13
    assert report["verification_status_records"]["verified_rebuilt"]["count"] == 60
    assert report["verification_status_records"]["in_progress"]["count"] == 10
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
    bundle = _copy_reviewed_bundle(tmp_path)
    report_path = bundle / "data-quality-report.json"
    quality_report = _read_json(report_path)
    quality_report["corrected_verse_count"] += 1
    _write_json(report_path, quality_report)

    with pytest.raises(AuditError, match="corrected_verse_count"):
        audit_composite_release(bundle)


def test_audit_rejects_manifest_gaps_that_disagree_with_the_quality_report(tmp_path):
    bundle = _copy_reviewed_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = _read_json(manifest_path)
    manifest["adapter_options"]["known_missing_verses"].pop("sirach")
    _write_json(manifest_path, manifest)

    with pytest.raises(AuditError, match="known_missing_verses"):
        audit_composite_release(bundle)


def test_audit_rejects_coordinated_declared_gap_drift(tmp_path):
    bundle = _copy_reviewed_bundle(tmp_path)
    for filename, path in (
        ("manifest.json", ("adapter_options", "known_missing_verses")),
        ("data-quality-report.json", ("known_missing_verses",)),
    ):
        json_path = bundle / filename
        document = _read_json(json_path)
        gaps = document
        for key in path:
            gaps = gaps[key]
        gaps["sirach"]["1"].remove(5)
        _write_json(json_path, document)

    with pytest.raises(AuditError, match="frozen declared gaps"):
        audit_composite_release(bundle)


def test_audit_rejects_noninteger_declared_gap_values(tmp_path):
    bundle = _copy_reviewed_bundle(tmp_path)
    for filename, path in (
        ("manifest.json", ("adapter_options", "known_missing_verses")),
        ("data-quality-report.json", ("known_missing_verses",)),
    ):
        json_path = bundle / filename
        document = _read_json(json_path)
        gaps = document
        for key in path:
            gaps = gaps[key]
        gaps["sirach"]["1"] = ["5", 7, 21]
        _write_json(json_path, document)

    with pytest.raises(AuditError, match="positive integer lists"):
        audit_composite_release(bundle)


def test_audit_rejects_moved_fallback_flag_with_the_same_count(tmp_path):
    bundle = _copy_reviewed_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = _read_json(manifest_path)
    sources = manifest["adapter_options"]["work_sources"]
    sources["baruch"]["fallback"] = False
    sources["genesis"]["fallback"] = True
    _write_json(manifest_path, manifest)

    with pytest.raises(AuditError, match="KJV fallback work IDs"):
        audit_composite_release(bundle)


def test_audit_rejects_changed_review_status_for_a_reviewed_work(tmp_path):
    bundle = _copy_reviewed_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = _read_json(manifest_path)
    manifest["adapter_options"]["work_sources"]["genesis"][
        "verification_status"
    ] = "in_progress"
    _write_json(manifest_path, manifest)

    with pytest.raises(AuditError, match="verification-status|work IDs"):
        audit_composite_release(bundle)


def test_source_group_report_fields_do_not_share_mutable_state():
    first = audit_composite_release(REVIEWED_BUNDLE)
    try:
        first["source_groups"]["extra"] = 999

        assert first["source_group_work_counts"]["extra"] == 2
        assert audit_composite_release(REVIEWED_BUNDLE)["source_groups"]["extra"] == 2
    finally:
        first["source_groups"]["extra"] = 2


def test_markdown_names_the_composite_scope_and_provenance_caveat():
    markdown = render_markdown(audit_bundle(REVIEWED_BUNDLE))

    assert "83 works" in markdown
    assert "82 ETHIO81 works" in markdown
    assert "1 supplemental work" in markdown
    assert "1,520 chapters" in markdown
    assert "38,487 verses" in markdown
    assert "extra: 2" in markdown
    assert "kjv_apocrypha: 6" in markdown
    assert "73 verified source records" in markdown
    assert "13 exact matches" in markdown
    assert "60 rebuilt from verified sources" in markdown
    assert "10 source records in progress" in markdown
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
    assert output.read_bytes().endswith(b"\n")
    assert b"\r\n" not in output.read_bytes()
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_replace_failure_preserves_destination_and_returns_controlled_error(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "ethiopian-composite-release-audit.md"
    output.write_text("previous reviewed report\n", encoding="utf-8", newline="\n")

    def reject_replace(_source, _destination):
        raise OSError("replace denied")

    monkeypatch.setattr(audit_module.os, "replace", reject_replace)

    return_code = audit_module.main(
        ["--bundle", str(REVIEWED_BUNDLE), "--markdown", str(output)]
    )

    assert return_code == 1
    assert "Unable to write" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "previous reviewed report\n"
    assert not list(tmp_path.glob(f".{output.name}.*.tmp"))


def test_atomic_write_failure_is_wrapped_as_an_audit_error(tmp_path, monkeypatch):
    def reject_open(_path, *_args, **_kwargs):
        raise OSError("write denied")

    monkeypatch.setattr(Path, "open", reject_open)

    with pytest.raises(AuditError, match="Unable to write"):
        audit_module._write_atomically(tmp_path / "report.md", "report\n")


def test_invalid_utf8_json_is_reported_as_an_audit_error(tmp_path):
    bundle = _copy_reviewed_bundle(tmp_path)
    (bundle / "manifest.json").write_bytes(b"\xff")

    with pytest.raises(AuditError, match="Unable to load manifest.json"):
        audit_composite_release(bundle)


def test_cli_returns_nonzero_without_writing_a_report_for_a_failed_audit(tmp_path):
    bundle = _copy_reviewed_bundle(tmp_path)
    report_path = bundle / "data-quality-report.json"
    quality_report = _read_json(report_path)
    quality_report["corrected_verse_count"] += 1
    _write_json(report_path, quality_report)
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
