import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

import pytest


DATA_ROOT = Path(__file__).parents[3] / "data/scripture/eotc-composite-en"
VERIFICATION = DATA_ROOT / "verification"
ARTIFACT = VERIFICATION / "artifacts/rh-charles-jubilees-1917-authorized-reprint.html"
CURRENT_BUNDLE = DATA_ROOT / "corrected-bundle.zip"
EXPECTED_COUNTS = (
    29, 33, 35, 33, 32, 38, 39, 30, 15, 36,
    24, 31, 29, 24, 34, 31, 18, 19, 31, 13,
    26, 30, 32, 33, 23, 35, 27, 30, 20, 26,
    32, 34, 23, 21, 27, 24, 25, 24, 18, 13,
    28, 25, 24, 34, 16, 16, 12, 19, 23, 13,
)


def _definition():
    from app.library.verification.registry import load_source_registry

    return load_source_registry(VERIFICATION / "source-registry.json").families[
        "rh-charles-jubilees-1902"
    ]


def test_parser_requires_the_authorized_reprint_identity_and_exact_1307_positions():
    from app.library.verification.adapters.charles_jubilees import (
        SOURCE_ARTIFACT_SHA256,
        parse_charles_jubilees,
    )

    rows = parse_charles_jubilees(
        ARTIFACT, _definition(), expected_sha256=SOURCE_ARTIFACT_SHA256,
    )

    assert len(rows) == sum(EXPECTED_COUNTS) == 1307
    assert {(row.work_id, row.chapter, row.verse) for row in rows} == {
        ("jubilees", chapter, verse)
        for chapter, count in enumerate(EXPECTED_COUNTS, 1)
        for verse in range(1, count + 1)
    }
    assert rows[0].text.startswith("And it came to pass in the first year")
    assert rows[-1].text.endswith("according to the division of their days.")
    joined = " ".join(row.text for row in rows)
    assert "Editors’ Preface" not in joined
    assert "Footnotes" not in joined
    assert "Herewith is completed" not in joined
    assert "THE END" not in joined
    assert "THE BOOK OF JUBILEES" not in joined


def test_parser_repairs_only_the_seven_scan_confirmed_markers_and_collapsed_chapter_27():
    from app.library.verification.adapters.charles_jubilees import (
        MARKER_REPAIRS,
        SOURCE_ARTIFACT_SHA256,
        parse_charles_jubilees,
    )

    rows = parse_charles_jubilees(
        ARTIFACT, _definition(), expected_sha256=SOURCE_ARTIFACT_SHA256,
    )
    positions = {(row.chapter, row.verse): row.text for row in rows}

    assert tuple((chapter, verse) for chapter, verse, *_ in MARKER_REPAIRS) == (
        (4, 2), (4, 13), (6, 15), (9, 9), (13, 13), (22, 21), (22, 26),
    )
    assert all(positions[position] for position in (
        (4, 2), (4, 13), (6, 15), (9, 9), (13, 13), (22, 21), (22, 26),
    ))
    assert [positions[(27, verse)] for verse in range(1, 28)]
    assert positions[(27, 1)].startswith("And the words of Esau")
    assert positions[(27, 13)].startswith("And it came to pass after Jacob")


def test_parser_rejects_wrong_identity_footnote_leakage_and_unsafe_inputs(tmp_path):
    from app.library.verification.adapters.charles_jubilees import parse_charles_jubilees

    definition = _definition()
    wrong_hash = "0" * 64
    with pytest.raises(ValueError, match="lock|checksum|identity"):
        parse_charles_jubilees(ARTIFACT, definition, expected_sha256=wrong_hash)

    altered = tmp_path / "altered.html"
    altered.write_bytes(ARTIFACT.read_bytes().replace(
        b'<footer class="footnotes">',
        b'<p>1. leaked scholarly footnote</p><footer class="footnotes">',
        1,
    ))
    with pytest.raises(ValueError, match="position|inventory|footer|leak"):
        parse_charles_jubilees(altered, definition)

    invalid = tmp_path / "invalid.html"
    invalid.write_bytes(ARTIFACT.read_bytes().replace(b"Jubilees", b"Jubil\xffes", 1))
    with pytest.raises(ValueError, match="UTF-8|encoding"):
        parse_charles_jubilees(invalid, definition)

    link = tmp_path / "link.html"
    link.symlink_to(ARTIFACT)
    with pytest.raises(ValueError, match="unsafe|regular|snapshot"):
        parse_charles_jubilees(link, definition)


def test_parser_excludes_headings_page_headers_and_notes_and_joins_hyphenated_wraps(
    tmp_path,
):
    from app.library.verification.adapters.charles_jubilees import parse_charles_jubilees

    snapshot = ARTIFACT.read_bytes()
    snapshot = snapshot.replace(
        b'<a name="_Toc233264794">',
        b'<a name="_Toc233264794"><h2>SCANNED CHAPTER HEADER</h2>'
        b'<p class="page-header">THE BOOK OF JUBILEES 2</p>',
        1,
    )
    story = snapshot.index(b'<a name="_Toc233264794">')
    snapshot = snapshot[:story] + snapshot[story:].replace(
        b"commandment", b"com-<br>mandment", 1,
    )
    snapshot = snapshot.replace(
        b"children of Israel",
        b'children<a href="#_ftn999"><sup>[999]</sup></a> of Israel',
        1,
    )
    fixture = tmp_path / "layout-fixture.html"
    fixture.write_bytes(snapshot)

    rows = parse_charles_jubilees(fixture, _definition())
    joined = " ".join(row.text for row in rows)
    assert "SCANNED CHAPTER HEADER" not in joined
    assert "THE BOOK OF JUBILEES 2" not in joined
    assert "[999]" not in joined
    assert "law and of the commandment, which" in rows[0].text
    assert "com- mandment" not in rows[0].text


def test_source_and_historical_locks_bind_every_local_artifact():
    from app.library.verification.adapters.charles_jubilees import (
        _validate_historical_lock_payload,
    )

    source_lock = json.loads((VERIFICATION / "source-artifacts.lock.json").read_text())
    source = source_lock["artifacts"]["rh-charles-jubilees-1902"]
    assert source["artifact_path"] == ARTIFACT.name
    assert source["source_url"].startswith("https://www.globalgreyebooks.com/")
    assert ARTIFACT.stat().st_size == source["size_bytes"]
    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() == source["sha256"]

    historical = json.loads((
        VERIFICATION / "rh-charles-jubilees-1902-historical-artifacts.lock.json"
    ).read_text())
    assert historical["archive_identifier"] == "bookofjubileesor00char"
    assert historical["catalog_metadata"] == {
        "creator": "Charles, R. H. (Robert Henry), 1855-1931",
        "date": "1902",
        "publisher": "London, A. and C. Black",
        "title": "The book of Jubilees, or The little Genesis",
    }
    assert {item["role"] for item in historical["artifacts"]} == {
        "catalog_metadata", "scan_authority", "ocr_text_page_anchor",
        "ocr_coordinate_page_anchor", "scan_page_map",
    }
    for record in historical["artifacts"]:
        path = VERIFICATION / "artifacts" / record["artifact_path"]
        assert path.stat().st_size == record["size_bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]

    tampered = json.loads(json.dumps(historical))
    tampered["artifacts"][0]["source_url"] = "https://example.invalid/substitute"
    with pytest.raises(ValueError, match="identity"):
        _validate_historical_lock_payload(tampered, VERIFICATION)


def test_historical_evidence_is_truthful_fixed_and_reproducible():
    from app.library.verification.adapters.charles_jubilees import (
        VISUAL_REVIEW_FILENAME,
        _validate_visual_review_payload,
        build_historical_evidence,
        validate_historical_evidence,
    )

    evidence = build_historical_evidence(VERIFICATION)
    validate_historical_evidence(
        VERIFICATION / "rh-charles-jubilees-1902-historical-evidence.json",
        VERIFICATION,
        _definition(),
    )
    committed = json.loads((
        VERIFICATION / "rh-charles-jubilees-1902-historical-evidence.json"
    ).read_text())
    assert evidence == committed
    assert evidence["reviewer"] == "OpenAI Codex (AI-assisted source verification)"
    assert evidence["human_visual_review_claimed"] is False
    assert evidence["edition_equivalence"] == "sampled_no_revision_detected"
    assert evidence["numbered_position_count"] == 1307
    assert evidence["rejected_secondary_claim"] == (
        "The 1,341-position claim conflicts with the primary 1902 numbering; "
        "the 50 chapter maxima total 1,307."
    )
    assert len(evidence["samples"]) == 9
    assert {sample["phase"] for sample in evidence["samples"]} == {
        "beginning", "middle", "end",
    }
    assert all(sample["result"] == "confirmed_visual" for sample in evidence["samples"])
    assert len(evidence["marker_repairs"]) == 7
    assert evidence["collapsed_paragraph_recovery"]["chapter"] == 27
    assert evidence["collapsed_paragraph_recovery"]["positions"] == list(range(1, 14))
    assert evidence["collapsed_paragraph_recovery"]["page_position_coverage"] == [
        {"pdf_page": 263, "positions": list(range(1, 7))},
        {"pdf_page": 264, "positions": list(range(7, 14))},
    ]
    review_path = VERIFICATION / "reports" / VISUAL_REVIEW_FILENAME
    review = json.loads(review_path.read_text())
    assert evidence["visual_review_sha256"] == hashlib.sha256(
        review_path.read_bytes()
    ).hexdigest()
    assert review["pdf_pages"] == 380
    assert len(review["samples"]) == 9
    assert len(review["marker_repairs"]) == 7
    from app.library.verification.adapters.charles_jubilees import MARKER_REPAIRS
    assert [
        (
            record["chapter"], record["verse"], record["source_fragment"],
            record["repaired_fragment"],
        )
        for record in review["marker_repairs"]
    ] == list(MARKER_REPAIRS)
    assert review["chapter_27_recovery"]["positions"] == list(range(1, 14))
    assert len(review["chapter_27_recovery"]["crops"]) == 2
    assert review["chapter_27_recovery"]["page_position_coverage"] == [
        {"pdf_page": 263, "positions": list(range(1, 7))},
        {"pdf_page": 264, "positions": list(range(7, 14))},
    ]
    assert all(
        crop["render_bbox"] == [0, 0, 1275, 1650]
        for crop in review["chapter_27_recovery"]["crops"]
    )
    assert all(sample["visual_review"] for sample in evidence["samples"])
    assert all(repair["visual_review"] for repair in evidence["marker_repairs"])
    assert evidence["collapsed_paragraph_recovery"]["visual_review"]
    _validate_visual_review_payload(review, VERIFICATION)


@pytest.mark.parametrize(
    "mutation", ["page", "coordinates", "crop_hash", "repair", "repair_fragment", "coverage"],
)
def test_visual_review_rejects_tampered_page_crop_and_repair_evidence(mutation):
    from app.library.verification.adapters.charles_jubilees import (
        VISUAL_REVIEW_FILENAME,
        _validate_visual_review_payload,
    )

    review = json.loads((VERIFICATION / "reports" / VISUAL_REVIEW_FILENAME).read_text())
    if mutation == "page":
        review["samples"][0]["visual_review"]["pdf_page"] += 1
    elif mutation == "coordinates":
        review["samples"][0]["visual_review"]["render_bbox"][2] += 1
    elif mutation == "crop_hash":
        review["samples"][0]["visual_review"]["crop_rgb_sha256"] = "0" * 64
    elif mutation == "repair":
        review["marker_repairs"][0]["chapter"] = 5
    elif mutation == "repair_fragment":
        review["marker_repairs"][0]["source_fragment"] = "42"
    else:
        review["chapter_27_recovery"]["page_position_coverage"][0]["positions"].pop()
    with pytest.raises(ValueError, match="visual review"):
        _validate_visual_review_payload(review, VERIFICATION)


def _pdf_review_script():
    path = DATA_ROOT / "verify_jubilees_pdf_review.py"
    spec = importlib.util.spec_from_file_location("verify_jubilees_pdf_review_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pdf_review_renderer_is_bounded_and_reproduces_all_locked_crops(
    tmp_path, monkeypatch,
):
    module = _pdf_review_script()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout", 0))

    with monkeypatch.context() as patch:
        patch.setattr(module.subprocess, "run", timeout)
        with pytest.raises(ValueError, match="timed out"):
            module._run_checked(["pdftoppm", "-v"], timeout_seconds=1)

    oversized = tmp_path / "oversized.ppm"
    oversized.write_bytes(b"P6\n1275 1650\n255\n")
    with oversized.open("r+b") as stream:
        stream.truncate(module.MAX_PPM_BYTES + 1)
    with pytest.raises(ValueError, match="size|limit"):
        module._ppm(oversized)

    renderer = shutil.which("pdftoppm")
    if renderer is None:
        pytest.skip("Poppler is unavailable; locked crop reproduction cannot run")
    version = module._run_checked(
        [renderer, "-v"], timeout_seconds=module.VERSION_TIMEOUT_SECONDS,
    )
    if b"pdftoppm version 26.05.0" not in version:
        with pytest.raises(ValueError, match="recorded Poppler 26.05.0"):
            module.verify(Path(renderer))
        pytest.skip("The recorded Poppler 26.05.0 renderer is unavailable")
    assert module.verify(Path(renderer)) == 18


def test_final_report_is_exact_and_candidate_is_deterministic(tmp_path, monkeypatch):
    import app.library.verification.adapters.charles_jubilees as module
    from app.library.verification.adapters.charles_jubilees import (
        CharlesJubileesAdapter,
        REVIEWED_FINAL_PUBLICATION_SHA256,
        SOURCE_ARTIFACT_SHA256,
    )
    from app.library.verification.registry import ArtifactLockRecord

    definition = _definition()
    lock = ArtifactLockRecord(
        family_id=definition.family_id,
        artifact_path=ARTIFACT.name,
        source_url=definition.artifact_url,
        landing_url=definition.landing_url,
        retrieved_at="2026-08-30T02:00:00Z",
        size_bytes=ARTIFACT.stat().st_size,
        sha256=SOURCE_ARTIFACT_SHA256,
    )
    adapter = CharlesJubileesAdapter()
    assert hashlib.sha256(CURRENT_BUNDLE.read_bytes()).hexdigest() == (
        REVIEWED_FINAL_PUBLICATION_SHA256
    )
    result = adapter.compare_family(
        definition=definition,
        lock_record=lock,
        artifact_path=ARTIFACT,
        current_bundle=CURRENT_BUNDLE,
        output=tmp_path / "reports",
    )
    assert result.report_count == 1
    summary = json.loads((
        tmp_path / "reports/rh-charles-jubilees-1902.json"
    ).read_text())
    assert summary["totals"] == {
        "exact": 1307, "formatting": 0, "missing": 0, "extra": 0, "wording": 0,
    }
    assert summary["edition_equivalence"] == "sampled_no_revision_detected"

    with monkeypatch.context() as patch:
        patch.setattr(
            module, "validate_historical_evidence",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ValueError("historical evidence rejected")
            ),
        )
        with pytest.raises(ValueError, match="historical evidence rejected"):
            adapter.compare_family(
                definition=definition,
                lock_record=lock,
                artifact_path=ARTIFACT,
                current_bundle=CURRENT_BUNDLE,
                output=tmp_path / "ungated-reports",
            )

    output = tmp_path / "candidate.zip"
    candidate = adapter.build_candidate(
        definition=definition,
        lock_record=lock,
        artifact_path=ARTIFACT,
        report_dir=VERIFICATION / "reports/rh-charles-jubilees-1902",
        output=output,
        replace_from_source=True,
    )
    assert candidate.work_count == 1
    with pytest.raises(ValueError, match="lock identity"):
        adapter.build_candidate(
            definition=definition,
            lock_record=replace(lock, source_url="https://example.invalid/substitute"),
            artifact_path=ARTIFACT,
            report_dir=VERIFICATION / "reports/rh-charles-jubilees-1902",
            output=tmp_path / "tampered.zip",
            replace_from_source=True,
        )
    first = output.read_bytes()
    adapter.build_candidate(
        definition=definition, lock_record=lock, artifact_path=ARTIFACT,
        report_dir=VERIFICATION / "reports/rh-charles-jubilees-1902",
        output=output, replace_from_source=True,
    )
    assert output.read_bytes() == first
    with ZipFile(output) as archive:
        chapters = json.loads(archive.read("data/jub.json"))
        assert len(chapters) == 50
        assert sum(len(chapter["v"]) for chapter in chapters) == 1307


@pytest.mark.parametrize(
    ("target", "mutation"),
    [
        ("work", lambda value: value.__setitem__("work_id", "genesis")),
        ("work", lambda value: value.__setitem__("schema_version", 2)),
        ("work", lambda value: value.__setitem__("parser_version", "other/1")),
        ("work", lambda value: value.__setitem__("source_artifact_sha256", "0" * 64)),
        ("work", lambda value: value["rules"].__setitem__("unicode_form", "NFKC")),
        ("work", lambda value: value["totals"].__setitem__("exact", 1306)),
        ("work", lambda value: value["differences"].append({"tampered": True})),
        ("work", lambda value: value["declared_omissions"].append({"tampered": True})),
        ("work", lambda value: value.__setitem__("current_publication_sha256", "0" * 64)),
        ("work", lambda value: value.__setitem__("is_verified_candidate", False)),
        ("work", lambda value: value.__setitem__("unexpected", True)),
        ("family", lambda value: value.__setitem__("schema_version", 2)),
        ("family", lambda value: value.__setitem__("family_id", "other-family")),
        ("family", lambda value: value.__setitem__("source_artifact_sha256", "0" * 64)),
        ("family", lambda value: value.__setitem__("current_publication_sha256", "0" * 64)),
        ("family", lambda value: value.__setitem__("parser_version", "other/1")),
        ("family", lambda value: value.__setitem__("edition_equivalence", "other")),
        ("family", lambda value: value.__setitem__("numbered_position_count", 1306)),
        ("family", lambda value: value["totals"].__setitem__("exact", 1306)),
        ("family", lambda value: value["works"][0].__setitem__("work_id", "genesis")),
        ("family", lambda value: value["works"][0]["totals"].__setitem__("exact", 1306)),
        ("family", lambda value: value["works"][0].__setitem__("report_sha256", "0" * 64)),
        ("family", lambda value: value.__setitem__("unexpected", True)),
    ],
    ids=(
        "work-id", "work-schema", "work-parser", "work-source", "rules",
        "work-totals", "differences", "omissions", "publication", "verified-flag",
        "work-extra", "family-schema", "family-id", "family-source",
        "family-publication", "family-parser", "edition-equivalence", "position-count",
        "family-totals", "family-work-id", "family-work-totals", "checksum",
        "family-extra",
    ),
)
def test_candidate_rejects_every_mutated_report_field_and_checksum(
    tmp_path, target, mutation, monkeypatch,
):
    import app.library.verification.adapters.charles_jubilees as module
    from app.library.verification.adapters.charles_jubilees import (
        CharlesJubileesAdapter,
        SOURCE_ARTIFACT_SHA256,
    )
    from app.library.verification.registry import ArtifactLockRecord

    definition = _definition()
    monkeypatch.setattr(module, "validate_historical_evidence", lambda *_args: None)
    lock = ArtifactLockRecord(
        family_id=definition.family_id,
        artifact_path=ARTIFACT.name,
        source_url=definition.artifact_url,
        landing_url=definition.landing_url,
        retrieved_at="2026-08-30T02:00:00Z",
        size_bytes=ARTIFACT.stat().st_size,
        sha256=SOURCE_ARTIFACT_SHA256,
    )
    report_dir = tmp_path / "reports" / definition.family_id
    shutil.copytree(VERIFICATION / "reports" / definition.family_id, report_dir)
    shutil.copy2(
        VERIFICATION / "reports" / f"{definition.family_id}.json",
        report_dir.parent / f"{definition.family_id}.json",
    )
    path = (
        report_dir / "jubilees.json"
        if target == "work" else report_dir.parent / f"{definition.family_id}.json"
    )
    payload = json.loads(path.read_text())
    mutation(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="report"):
        CharlesJubileesAdapter().build_candidate(
            definition=definition,
            lock_record=lock,
            artifact_path=ARTIFACT,
            report_dir=report_dir,
            output=tmp_path / "candidate.zip",
            replace_from_source=True,
        )


def test_candidate_rejects_coordinated_canonical_publication_report_forgery(
    tmp_path, monkeypatch,
):
    import app.library.verification.adapters.charles_jubilees as module
    from app.library.verification.adapters.charles_jubilees import (
        CharlesJubileesAdapter,
        SOURCE_ARTIFACT_SHA256,
        _json_bytes,
    )
    from app.library.verification.registry import ArtifactLockRecord

    definition = _definition()
    monkeypatch.setattr(module, "validate_historical_evidence", lambda *_args: None)
    lock = ArtifactLockRecord(
        family_id=definition.family_id,
        artifact_path=ARTIFACT.name,
        source_url=definition.artifact_url,
        landing_url=definition.landing_url,
        retrieved_at="2026-08-30T02:00:00Z",
        size_bytes=ARTIFACT.stat().st_size,
        sha256=SOURCE_ARTIFACT_SHA256,
    )
    report_dir = tmp_path / "reports" / definition.family_id
    shutil.copytree(VERIFICATION / "reports" / definition.family_id, report_dir)
    family_path = report_dir.parent / f"{definition.family_id}.json"
    shutil.copy2(VERIFICATION / "reports" / family_path.name, family_path)

    forged_publication = "0" * 64
    work_path = report_dir / "jubilees.json"
    work = json.loads(work_path.read_text())
    work["current_publication_sha256"] = forged_publication
    work_snapshot = _json_bytes(work)
    work_path.write_bytes(work_snapshot)
    family = json.loads(family_path.read_text())
    family["current_publication_sha256"] = forged_publication
    family["works"][0]["report_sha256"] = hashlib.sha256(work_snapshot).hexdigest()
    family_path.write_bytes(_json_bytes(family))

    with pytest.raises(ValueError, match="report"):
        CharlesJubileesAdapter().build_candidate(
            definition=definition,
            lock_record=lock,
            artifact_path=ARTIFACT,
            report_dir=report_dir,
            output=tmp_path / "candidate.zip",
            replace_from_source=True,
        )
