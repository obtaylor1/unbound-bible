from __future__ import annotations

from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
import hashlib
import json
import shutil
import stat
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from app.library.verification.registry import APPROVED_SOURCE_DEFINITIONS


DATA_ROOT = Path(__file__).parents[3] / "data/scripture/eotc-composite-en"
ARTIFACT = DATA_ROOT / "verification/artifacts/project-gutenberg-124.txt"
CURRENT_BUNDLE = DATA_ROOT / "corrected-bundle.zip"
DEFINITION = APPROVED_SOURCE_DEFINITIONS["kjv-1611-fallback"]
EXPECTED_COUNTS = {
    "baruch": 140,
    "letter-of-jeremiah": 73,
    "prayer-of-azariah": 67,
    "susanna": 64,
    "bel-and-the-dragon": 42,
    "prayer-of-manasseh": 1,
}


def _lock_record():
    from app.library.verification.registry import ArtifactLockRecord

    return ArtifactLockRecord(
        family_id=DEFINITION.family_id,
        artifact_path=ARTIFACT.name,
        source_url=DEFINITION.artifact_url,
        landing_url=DEFINITION.landing_url,
        retrieved_at="2026-08-29T22:27:25Z",
        size_bytes=ARTIFACT.stat().st_size,
        sha256=hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(),
    )


def _parse(path: Path = ARTIFACT, *, expected_sha256: str | None = None):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        parse_gutenberg_kjv_apocrypha,
    )

    return parse_gutenberg_kjv_apocrypha(
        path, DEFINITION, expected_sha256=expected_sha256,
    )


def test_registry_selects_reviewed_ebook_124_artifact_and_not_ebook_30():
    assert DEFINITION.artifact_filename == "project-gutenberg-124.txt"
    assert DEFINITION.artifact_url == (
        "https://www.gutenberg.org/cache/epub/124/pg124.txt"
    )
    assert DEFINITION.landing_url == "https://www.gutenberg.org/ebooks/124"
    assert DEFINITION.expected_work_ids == tuple(EXPECTED_COUNTS)
    assert "30" not in DEFINITION.artifact_filename


def test_live_parser_returns_exact_six_work_387_position_inventory():
    from app.library.verification.types import SourceVerse

    rows = _parse(expected_sha256=(
        "83de0c18742ba22b3d442c3a5bc828fe9e91dff27ae3c298e9b5c9a6ecfbf4d4"
    ))

    assert type(rows) is tuple
    assert all(type(row) is SourceVerse for row in rows)
    assert Counter(row.work_id for row in rows) == Counter(EXPECTED_COUNTS)
    assert len(rows) == 387
    assert len({(row.work_id, row.chapter, row.verse) for row in rows}) == 387
    assert all(row.chapter > 0 and row.verse > 0 and row.text.strip() for row in rows)


def test_parser_applies_only_reviewed_section_and_versification_mappings():
    rows = _parse()
    by_position = {
        (row.work_id, row.chapter, row.verse): row.text for row in rows
    }

    assert by_position[("letter-of-jeremiah", 1, 1)].startswith(
        "A copy of an epistle"
    )
    assert by_position[("letter-of-jeremiah", 1, 73)].startswith(
        "Better therefore is the just man"
    )
    assert by_position[("prayer-of-azariah", 1, 1)].startswith(
        "Then Azarias stood up"
    )
    assert by_position[("prayer-of-azariah", 1, 67)].startswith(
        "O all ye that worship the Lord"
    )
    all_text = "\n".join(by_position.values())
    assert "And they walked in the midst of the fire" not in all_text
    assert "fell down bound into the midst" not in all_text
    assert "Then Nebuchadnezzar" not in all_text
    assert "King of Judah" not in by_position[("prayer-of-manasseh", 1, 1)]


def test_parser_rejects_duplicate_section_heading_and_duplicate_position(tmp_path):
    payload = ARTIFACT.read_bytes()
    duplicate_heading = tmp_path / "duplicate-heading.txt"
    duplicate_heading.write_bytes(payload + b"\r\nThe Book of Baruch\r\n")
    with pytest.raises(ValueError, match="heading|section|inventory"):
        _parse(duplicate_heading)

    duplicate_position = tmp_path / "duplicate-position.txt"
    duplicate_position.write_bytes(
        payload.replace(
            b"1:2 In the fifth year, and in the seventh day of the month",
            b"1:1 In the fifth year, and in the seventh day of the month",
            1,
        )
    )
    with pytest.raises(ValueError, match="duplicate|position"):
        _parse(duplicate_position)


def test_parser_rejects_missing_required_heading_bad_encoding_and_symlink(tmp_path):
    payload = ARTIFACT.read_bytes()
    missing = tmp_path / "missing.txt"
    missing.write_bytes(
        payload.replace(b"The Prayer of Manasses", b"Removed", 2)
    )
    with pytest.raises(ValueError, match="heading|section|inventory"):
        _parse(missing)

    invalid = tmp_path / "invalid.txt"
    invalid.write_bytes(ARTIFACT.read_bytes().replace(b"Baruch", b"\xffaruch", 1))
    with pytest.raises(ValueError, match="UTF-8|encoding"):
        _parse(invalid)

    link = tmp_path / "link.txt"
    link.symlink_to(ARTIFACT)
    with pytest.raises(ValueError, match="unsafe|regular|snapshot"):
        _parse(link)


def test_live_comparison_is_complete_after_all_pre_rebuild_wording_is_adjudicated(tmp_path):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        GutenbergKjvApocryphaAdapter,
    )
    from app.library.verification.registry import ArtifactLockRecord

    lock = ArtifactLockRecord(
        family_id=DEFINITION.family_id,
        artifact_path=ARTIFACT.name,
        source_url=DEFINITION.artifact_url,
        landing_url=DEFINITION.landing_url,
        retrieved_at="2026-08-29T22:27:00Z",
        size_bytes=ARTIFACT.stat().st_size,
        sha256=hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(),
    )
    result = GutenbergKjvApocryphaAdapter().compare_family(
        definition=DEFINITION,
        lock_record=lock,
        artifact_path=ARTIFACT,
        current_bundle=CURRENT_BUNDLE,
        output=tmp_path,
    )

    assert result.report_count == 6
    summary = json.loads((tmp_path / "kjv-1611-fallback.json").read_text())
    assert summary["totals"] == {
        "exact": 387,
        "formatting": 0,
        "missing": 0,
        "extra": 0,
        "wording": 0,
    }
    assert [work["work_id"] for work in summary["works"]] == list(EXPECTED_COUNTS)
    pre = json.loads((
        DATA_ROOT / "verification/reports/kjv-1611-fallback-pre-rebuild.json"
    ).read_text())
    assert pre["totals"] == {
        "exact": 9,
        "formatting": 0,
        "missing": 0,
        "extra": 0,
        "wording": 378,
    }


def test_candidate_requires_canonical_scan_evidence_before_replacement(tmp_path):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        GutenbergKjvApocryphaAdapter,
    )
    from app.library.verification.registry import ArtifactLockRecord

    lock = ArtifactLockRecord(
        family_id=DEFINITION.family_id,
        artifact_path=ARTIFACT.name,
        source_url=DEFINITION.artifact_url,
        landing_url=DEFINITION.landing_url,
        retrieved_at="2026-08-29T22:27:00Z",
        size_bytes=ARTIFACT.stat().st_size,
        sha256=hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(),
    )
    report_dir = tmp_path / "verification/reports/kjv-1611-fallback"
    report_dir.mkdir(parents=True)
    with pytest.raises(ValueError, match="historical|scan|evidence"):
        GutenbergKjvApocryphaAdapter().build_candidate(
            definition=DEFINITION,
            lock_record=lock,
            artifact_path=ARTIFACT,
            report_dir=report_dir,
            output=tmp_path / "candidate.zip",
            replace_from_source=True,
        )


def test_historical_artifact_lock_binds_exact_catalog_manifest_and_16_pages():
    lock = json.loads((
        DATA_ROOT / "verification/kjv-1611-historical-artifacts.lock.json"
    ).read_text())

    assert lock["landing_url"] == (
        "https://colenda.library.upenn.edu/catalog/81431-p3rv0df45"
    )
    assert lock["catalog_metadata"]["publisher"] == "Robert Barker"
    assert lock["catalog_metadata"]["date"] == "1611"
    assert lock["catalog_metadata"]["edition"] == "Great HE editio princeps"
    assert lock["rights"] == "NoC-US"
    assert lock["artifacts"][0]["role"] == "catalog_metadata"
    assert lock["artifacts"][1]["role"] == "iiif_manifest"
    pages = [item for item in lock["artifacts"] if item["role"] == "page_image"]
    assert [item["canvas_label"] for item in pages] == [
        f"p. {number}" for number in range(1143, 1159)
    ]
    assert all(item["iiif_url"].endswith("/full/full/0/default.jpg") for item in pages)
    for record in lock["artifacts"]:
        path = DATA_ROOT / "verification/artifacts" / record["artifact_path"]
        assert path.stat().st_size == record["size_bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]


def test_historical_evidence_is_reproducible_exhaustive_and_truthfully_ai_reviewed():
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        build_historical_evidence,
        validate_historical_evidence,
    )

    verification = DATA_ROOT / "verification"
    evidence = build_historical_evidence(verification)
    validate_historical_evidence(
        verification / "kjv-1611-fallback-historical-evidence.json",
        verification,
        DEFINITION,
    )

    assert evidence == json.loads((
        verification / "kjv-1611-fallback-historical-evidence.json"
    ).read_text())
    assert evidence["reviewer"] == "OpenAI Codex (AI-assisted source verification)"
    assert evidence["human_visual_review_claimed"] is False
    lock = json.loads((
        verification / "source-artifacts.lock.json"
    ).read_text())["artifacts"]["kjv-1611-fallback"]
    assert datetime.fromisoformat(evidence["reviewed_at"].replace("Z", "+00:00")) > (
        datetime.fromisoformat(lock["retrieved_at"].replace("Z", "+00:00"))
    )
    assert evidence["sample_selection_rule"] == (
        "median canonical position within each work third, fixed before outcome"
    )
    assert len(evidence["samples"]) == 18
    assert {(item["work_id"], item["phase"]) for item in evidence["samples"]} == {
        (work_id, phase)
        for work_id in EXPECTED_COUNTS
        for phase in ("beginning", "middle", "end")
    }
    assert len(evidence["adjudications"]) == 378
    assert len({
        (item["work_id"], item["chapter"], item["verse"])
        for item in evidence["adjudications"]
    }) == 378
    assert evidence["scan_backed_corrections"] == [
        {"work_id": "bel-and-the-dragon", "chapter": 1, "verse": 15,
         "from": "drinck", "to": "drink", "scan_page": 1157},
        {"work_id": "bel-and-the-dragon", "chapter": 1, "verse": 18,
         "from": "dour", "to": "door", "scan_page": 1157},
        {"work_id": "prayer-of-manasseh", "chapter": 1, "verse": 1,
         "from": "life up", "to": "lift up", "scan_page": 1158},
        {"work_id": "prayer-of-manasseh", "chapter": 1, "verse": 1,
         "from": "iniquites", "to": "iniquities", "scan_page": 1158},
    ]


def test_candidate_is_deterministic_and_applies_only_scan_backed_corrections(tmp_path):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        GutenbergKjvApocryphaAdapter,
    )

    output = tmp_path / "candidate.zip"
    result = GutenbergKjvApocryphaAdapter().build_candidate(
        definition=DEFINITION,
        lock_record=_lock_record(),
        artifact_path=ARTIFACT,
        report_dir=DATA_ROOT / "verification/reports/kjv-1611-fallback",
        output=output,
        replace_from_source=True,
    )
    assert result.work_count == 6
    first = output.read_bytes()
    GutenbergKjvApocryphaAdapter().build_candidate(
        definition=DEFINITION, lock_record=_lock_record(), artifact_path=ARTIFACT,
        report_dir=DATA_ROOT / "verification/reports/kjv-1611-fallback",
        output=output, replace_from_source=True,
    )
    assert output.read_bytes() == first
    with ZipFile(output) as archive:
        index = json.loads(archive.read("data/index.json"))
        assert [book["work_id"] for book in index["books"]] == list(EXPECTED_COUNTS)
        bel = json.loads(archive.read("data/bel.json"))[0]["v"]
        man = json.loads(archive.read("data/man.json"))[0]["v"][0]["t"]
        assert "drinck" not in bel[14]["t"] and "drink" in bel[14]["t"]
        assert "dour" not in bel[17]["t"] and "door" in bel[17]["t"]
        assert "life up" not in man and "lift up" in man
        assert "iniquites" not in man and "iniquities" in man


def test_historical_validation_rejects_tampering(tmp_path):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        validate_historical_evidence,
    )

    verification = tmp_path / "verification"
    shutil.copytree(DATA_ROOT / "verification", verification)
    shutil.copy2(CURRENT_BUNDLE, tmp_path / "corrected-bundle.zip")
    evidence = verification / "kjv-1611-fallback-historical-evidence.json"
    payload = json.loads(evidence.read_text())
    payload["adjudications"][0]["decision"] = "silently-modernized"
    evidence.write_text(json.dumps(payload, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="historical|adjudication|evidence"):
        validate_historical_evidence(evidence, verification, DEFINITION)


def test_historical_evidence_binds_the_locked_pre_rebuild_reports(tmp_path):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import (
        build_historical_evidence,
    )

    verification = tmp_path / "verification"
    shutil.copytree(DATA_ROOT / "verification", verification)
    assert build_historical_evidence(verification) == json.loads((
        DATA_ROOT / "verification/kjv-1611-fallback-historical-evidence.json"
    ).read_text())
    child = verification / "reports/kjv-1611-fallback-pre-rebuild/baruch.json"
    payload = json.loads(child.read_text())
    payload["differences"][0]["current_text"] = "tampered baseline"
    child.write_text(json.dumps(payload, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="pre-rebuild|report|tamper"):
        build_historical_evidence(verification)


def _single_member_zip(info: ZipInfo, payload: bytes, *, compression=ZIP_STORED) -> bytes:
    output = BytesIO()
    info.compress_type = compression
    if info.external_attr == 0:
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
    with ZipFile(output, "w", compression=compression) as archive:
        archive.writestr(info, payload)
    return output.getvalue()


def _patch_zip_security_fields(payload: bytes, *, flag_bits=None, compression=None) -> bytes:
    changed = bytearray(payload)
    for signature, flag_offset, compression_offset in (
        (b"PK\x03\x04", 6, 8),
        (b"PK\x01\x02", 8, 10),
    ):
        offset = changed.find(signature)
        assert offset >= 0
        if flag_bits is not None:
            changed[offset + flag_offset:offset + flag_offset + 2] = flag_bits.to_bytes(2, "little")
        if compression is not None:
            changed[offset + compression_offset:offset + compression_offset + 2] = compression.to_bytes(2, "little")
    return bytes(changed)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            lambda: _patch_zip_security_fields(
                _single_member_zip(ZipInfo("encrypted.json"), b"{}"), flag_bits=1,
            ),
            "encrypted",
        ),
        (
            lambda: _patch_zip_security_fields(
                _single_member_zip(ZipInfo("unsupported.json"), b"{}"), compression=99,
            ),
            "compression",
        ),
    ],
)
def test_current_bundle_rejects_unsafe_zip_metadata(payload, message):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import _current_rows

    snapshot = payload()
    with pytest.raises(ValueError, match=message):
        _current_rows(snapshot, DEFINITION)


def test_current_bundle_rejects_non_regular_zip_member():
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import _current_rows

    info = ZipInfo("unsafe-link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(ValueError, match="regular file|type"):
        _current_rows(_single_member_zip(info, b"target"), DEFINITION)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: _single_member_zip(
                ZipInfo("oversized.bin"), b"x" * (1024 * 1024 + 1),
            ),
            "member.*size|uncompressed",
        ),
        (
            lambda: _single_member_zip(
                ZipInfo("ratio-bomb.bin"), b"x" * (1024 * 1024),
                compression=ZIP_DEFLATED,
            ),
            "compression ratio",
        ),
    ],
)
def test_current_bundle_rejects_bounded_zip_expansion(factory, message):
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import _current_rows

    with pytest.raises(ValueError, match=message):
        _current_rows(factory(), DEFINITION)


def test_current_bundle_rejects_excess_total_uncompressed_size():
    from app.library.verification.adapters.gutenberg_kjv_apocrypha import _current_rows

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for index in range(17):
            info = ZipInfo(f"padding-{index}.bin")
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, b"x" * 1024 * 1024)
    with pytest.raises(ValueError, match="total.*uncompressed|uncompressed.*total"):
        _current_rows(output.getvalue(), DEFINITION)


def test_permanent_fallback_contract_survives_verified_status():
    manifest = json.loads((DATA_ROOT / "manifest.json").read_text())
    works = {
        work_id: source
        for work_id, source in manifest["adapter_options"]["work_sources"].items()
        if work_id in EXPECTED_COUNTS
    }

    assert set(works) == set(EXPECTED_COUNTS)
    for source in works.values():
        assert source["fallback"] is True
        assert "KJV" in source["source_label"]
        assert "fallback" in source["source_label"].casefold()
