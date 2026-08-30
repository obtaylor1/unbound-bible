from __future__ import annotations

from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import shutil
import stat
import struct
import subprocess
import unicodedata
import zlib
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from app.library.verification.registry import APPROVED_SOURCE_DEFINITIONS
from app.library.verification.types import SourceVerse


DEFINITION = APPROVED_SOURCE_DEFINITIONS["murdock-peshitta-1852"]
DATA_ROOT = Path(__file__).parents[3] / "data/scripture/eotc-composite-en"
LIVE_ARTIFACT = DATA_ROOT / "verification/artifacts/murdock-source.zip"


def _parse(path: Path = LIVE_ARTIFACT):
    from app.library.verification.adapters.murdock_sword import parse_murdock_sword

    return parse_murdock_sword(path, DEFINITION)


def _copy_zip(path: Path, transform) -> Path:
    with ZipFile(LIVE_ARTIFACT) as source, ZipFile(path, "w", ZIP_DEFLATED) as output:
        for info in source.infolist():
            name, payload = transform(info.filename, source.read(info))
            output.writestr(name, payload)
    return path


def _rewrite_ztext(path: Path, block_transform) -> Path:
    """Rebuild the reviewed zText streams after a synthetic block mutation."""
    with ZipFile(LIVE_ARTIFACT) as source:
        payloads = {info.filename: source.read(info) for info in source.infolist()}
    bzs_name = "modules/texts/ztext/murdock/nt.bzs"
    bzz_name = "modules/texts/ztext/murdock/nt.bzz"
    bzs, bzz = payloads[bzs_name], payloads[bzz_name]
    header = bzz[:10]
    compressed = []
    for number, offset in enumerate(range(0, len(bzs), 12)):
        start, size, expected = struct.unpack_from("<III", bzs, offset)
        raw = zlib.decompress(bzz[start:start + size])
        assert len(raw) == expected
        compressed.append(zlib.compress(block_transform(number, raw)) + b"\0" * 1024)
    rebuilt_index = bytearray()
    rebuilt_text = bytearray(header)
    for block in compressed:
        start = len(rebuilt_text)
        raw = zlib.decompress(block[:-1024])
        rebuilt_index.extend(struct.pack("<III", start, len(block), len(raw)))
        rebuilt_text.extend(block)
    payloads[bzs_name] = bytes(rebuilt_index)
    payloads[bzz_name] = bytes(rebuilt_text)
    with ZipFile(path, "w", ZIP_DEFLATED) as output:
        for name, payload in payloads.items():
            output.writestr(name, payload)
    return path


def test_live_module_has_exact_reviewed_identity_inventory_and_positions():
    from app.library.verification.adapters.murdock_sword import (
        DECLARED_OMISSIONS,
        MODULE_VERSION,
        PARSER_VERSION,
    )

    rows = _parse()

    assert MODULE_VERSION == "1.2"
    assert PARSER_VERSION == "murdock-sword/1"
    assert type(rows) is tuple
    assert {row.work_id for row in rows} == set(DEFINITION.expected_work_ids)
    assert len(rows) == 7_947
    assert len({(row.work_id, row.chapter, row.verse) for row in rows}) == len(rows)
    assert all(row.chapter > 0 and row.verse > 0 and row.text.strip() for row in rows)
    assert all(
        unicodedata.category(character) != "Cc"
        for row in rows for character in row.text
    )
    assert sum(len(positions) for positions in DECLARED_OMISSIONS.values()) == 10


def test_live_module_recovers_philemon_1_1_from_crosswire_spill_marker():
    rows = _parse()
    text = next(
        row.text for row in rows
        if (row.work_id, row.chapter, row.verse) == ("philemon", 1, 1)
    )

    assert text == (
        "PAUL, a prisoner of Jesus the Messiah, and Timothy a brother; "
        "to the beloved Philemon, a laborer with us,"
    )
    assert "These things speak thou" not in text
    assert sum(row.text == text for row in rows) == 1


def test_live_module_decodes_only_reviewed_matthew_dagger_byte():
    rows = _parse()
    text = next(
        row.text for row in rows
        if (row.work_id, row.chapter, row.verse) == ("matthew", 27, 42)
    )

    assert text == (
        "and said: He gave life to others, his own life he cannot preserve. "
        "If he is the king of Israel, let him now descend from the cross, "
        "and we will believe in him. †"
    )


def test_live_module_applies_only_reviewed_gbf_and_separator_cleanup():
    from app.library.verification.adapters.murdock_sword import clean_murdock_text

    assert clean_murdock_text("before <FI>emphasis<Fi> after") == (
        "before emphasis after"
    )
    assert clean_murdock_text("one<RF>translator note<Rf> two") == "one two"
    assert clean_murdock_text("surrounding\x0fwords") == "surrounding words"
    assert clean_murdock_text("surrounding \x0f words") == "surrounding words"
    with pytest.raises(ValueError, match="unexpected GBF|apparatus"):
        clean_murdock_text("text <WG123>word")
    with pytest.raises(ValueError, match="unbalanced|apparatus"):
        clean_murdock_text("text <RF>note")
    # FI is a presentation state in this old GBF module and may cross a verse
    # boundary; either delimiter is therefore independently removable.
    assert clean_murdock_text("text<Fi> continues") == "text continues"


def test_parser_rejects_wrong_module_configuration(tmp_path):
    def changed(name: str, payload: bytes):
        if name == "mods.d/murdock.conf":
            payload = payload.replace(b"Version=1.2", b"Version=9.9")
        return name, payload

    with pytest.raises(ValueError, match="module identity|Version"):
        _parse(_copy_zip(tmp_path / "wrong-version.zip", changed))


@pytest.mark.parametrize("suffix", [b"Version=1.2\n", b"Unexpected=field\n"])
def test_parser_rejects_duplicate_or_extra_configuration_fields(tmp_path, suffix):
    def changed(name: str, payload: bytes):
        if name == "mods.d/murdock.conf":
            payload += suffix
        return name, payload

    with pytest.raises(ValueError, match="configuration|identity|canonical"):
        _parse(_copy_zip(tmp_path / "noncanonical-conf.zip", changed))


def test_parser_rejects_extra_duplicate_or_unsafe_members(tmp_path):
    with ZipFile(LIVE_ARTIFACT) as source, ZipFile(
        tmp_path / "extra.zip", "w", ZIP_DEFLATED,
    ) as output:
        for info in source.infolist():
            output.writestr(info.filename, source.read(info))
        output.writestr("unexpected.txt", b"not reviewed")
    with pytest.raises(ValueError, match="exact reviewed|member"):
        _parse(tmp_path / "extra.zip")

    def unsafe(name: str, payload: bytes):
        if name == "mods.d/murdock.conf":
            return "../murdock.conf", payload
        return name, payload

    with pytest.raises(ValueError, match="exact reviewed|unsafe|member"):
        _parse(_copy_zip(tmp_path / "unsafe.zip", unsafe))


def test_parser_rejects_truncated_binary_indexes(tmp_path):
    def truncated(name: str, payload: bytes):
        if name.endswith("nt.bzv"):
            payload = payload[:-1]
        return name, payload

    with pytest.raises(ValueError, match="index|size|structure"):
        _parse(_copy_zip(tmp_path / "truncated.zip", truncated))


def test_parser_rejects_wrong_rights_metadata_and_corrupt_text_block(tmp_path):
    def wrong_rights(name: str, payload: bytes):
        if name == "mods.d/murdock.conf":
            payload = payload.replace(
                b"DistributionLicense=Public Domain",
                b"DistributionLicense=Copyright",
            )
        return name, payload

    with pytest.raises(ValueError, match="identity|Version"):
        _parse(_copy_zip(tmp_path / "wrong-rights.zip", wrong_rights))

    def corrupt_block(name: str, payload: bytes):
        if name.endswith("nt.bzz"):
            offset = 1_000
            payload = (
                payload[:offset] + bytes([payload[offset] ^ 0xFF])
                + payload[offset + 1:]
            )
        return name, payload

    with pytest.raises(ValueError, match="compressed block|invalid"):
        _parse(_copy_zip(tmp_path / "corrupt-block.zip", corrupt_block))


def test_parser_rejects_ztext_header_gap_and_trailing_deflate_data(tmp_path):
    def shifted_header(name: str, payload: bytes):
        if name.endswith("nt.bzz"):
            return name, b"\0" + payload
        if name.endswith("nt.bzs"):
            rows = bytearray(payload)
            for offset in range(0, len(rows), 12):
                start = struct.unpack_from("<I", rows, offset)[0]
                struct.pack_into("<I", rows, offset, start + 1)
            return name, bytes(rows)
        return name, payload

    with pytest.raises(ValueError, match="header|contiguous|gap"):
        _parse(_copy_zip(tmp_path / "header-gap.zip", shifted_header))

    def trailing_stream(name: str, payload: bytes):
        if name.endswith("nt.bzz"):
            return name, payload[:10] + payload[10:10 + 41_547] + b"junk" + payload[10 + 41_547:]
        if name.endswith("nt.bzs"):
            rows = bytearray(payload)
            first_start, first_size, first_raw = struct.unpack_from("<III", rows, 0)
            struct.pack_into("<III", rows, 0, first_start, first_size + 4, first_raw)
            for offset in range(12, len(rows), 12):
                start = struct.unpack_from("<I", rows, offset)[0]
                struct.pack_into("<I", rows, offset, start + 4)
            return name, bytes(rows)
        return name, payload

    with pytest.raises(ValueError, match="compressed block|trailing|stream"):
        _parse(_copy_zip(tmp_path / "trailing-deflate.zip", trailing_stream))


def test_parser_rejects_additional_or_moved_0x86_markers(tmp_path):
    def extra_marker(number: int, raw: bytes) -> bytes:
        if number == 0:
            position = raw.index(b"Jesus")
            return raw[:position] + b"\x86" + raw[position + 1:]
        return raw

    with pytest.raises(ValueError, match="0x86|dagger|marker"):
        _parse(_rewrite_ztext(tmp_path / "extra-marker.zip", extra_marker))

    def moved_markers(number: int, raw: bytes) -> bytes:
        if number == 0:
            positions = [index for index, value in enumerate(raw) if value == 0x86]
            assert len(positions) == 2
            changed = bytearray(raw)
            changed[positions[0]] = ord("!")
            target = raw.index(b"Jesus")
            changed[target] = 0x86
            return bytes(changed)
        return raw

    with pytest.raises(ValueError, match="0x86|dagger|marker|context"):
        _parse(_rewrite_ztext(tmp_path / "moved-marker.zip", moved_markers))


def test_parser_rejects_symlink_duplicate_and_compression_bomb_members(tmp_path):
    with ZipFile(LIVE_ARTIFACT) as source, ZipFile(
        tmp_path / "symlink.zip", "w", ZIP_DEFLATED,
    ) as output:
        for source_info in source.infolist():
            info = ZipInfo(source_info.filename)
            info.create_system = 3
            info.external_attr = (
                (stat.S_IFLNK | 0o777) if source_info.filename.endswith("errata")
                else (stat.S_IFREG | 0o644)
            ) << 16
            output.writestr(info, source.read(source_info))
    with pytest.raises(ValueError, match="regular files|member"):
        _parse(tmp_path / "symlink.zip")

    with ZipFile(LIVE_ARTIFACT) as source, ZipFile(
        tmp_path / "duplicate.zip", "w", ZIP_DEFLATED,
    ) as output:
        for source_info in source.infolist():
            output.writestr(source_info.filename, source.read(source_info))
        with pytest.warns(UserWarning, match="Duplicate name"):
            output.writestr(
                "mods.d/murdock.conf", source.read("mods.d/murdock.conf")
            )
    with pytest.raises(ValueError, match="exact reviewed|member"):
        _parse(tmp_path / "duplicate.zip")

    def compression_bomb(name: str, payload: bytes):
        if name.endswith("appendix"):
            payload = b"0" * 1_000_000
        return name, payload

    with pytest.raises(ValueError, match="compression ratio|limit"):
        _parse(_copy_zip(tmp_path / "bomb.zip", compression_bomb))


def test_historical_lock_rejects_tampered_derivative_identity(tmp_path):
    from app.library.verification.adapters.murdock_sword import (
        HISTORICAL_LOCK_FILENAME,
        build_historical_evidence,
    )

    verification = tmp_path / "verification"
    verification.mkdir()
    lock_path = verification / HISTORICAL_LOCK_FILENAME
    lock_path.write_bytes(
        (DATA_ROOT / "verification" / HISTORICAL_LOCK_FILENAME).read_bytes()
    )
    lock = json.loads(lock_path.read_text())
    lock["artifacts"][0]["sha256"] = "0" * 64
    lock_path.write_text(json.dumps(lock))

    with pytest.raises(ValueError, match="historical artifact lock|identity"):
        build_historical_evidence(verification)


def test_historical_lock_binds_primary_and_derivatives_to_exact_ia_item():
    lock = json.loads((
        DATA_ROOT / "verification/murdock-historical-artifacts.lock.json"
    ).read_text())
    assert lock["internet_archive_identifier"] == "syriacnewtestam00murdgoog"
    assert {record["landing_url"] for record in lock["artifacts"]} == {
        "https://archive.org/details/syriacnewtestam00murdgoog"
    }
    assert all(
        record["source_url"].startswith(
            "https://archive.org/download/syriacnewtestam00murdgoog/"
        )
        and len(record["sha1"]) == 40
        and len(record["sha256"]) == 64
        for record in lock["artifacts"]
    )
    primary = lock["artifacts"][0]
    assert primary["filename"] == "syriacnewtestam00murdgoog.djvu"
    assert primary["sha1"] == "7c9b8edcd7b292d6823bb8651fe6c73352e9168b"
    assert primary["sha256"] == (
        "8777ab6536ba7242e017b0aca426858c85fa791ba5d1ed601f93c069a5775f9e"
    )
    assert lock["edition"] == (
        "1915 ninth edition of James Murdock's 1852 translation"
    )
    pdf = next(record for record in lock["artifacts"] if record["role"] == "visual_pdf_derivative")
    assert pdf == {
        "filename": "syriacnewtestam00murdgoog.pdf",
        "landing_url": "https://archive.org/details/syriacnewtestam00murdgoog",
        "retrieved_at": "2026-08-29T18:44:41Z",
        "role": "visual_pdf_derivative",
        "sha1": "76b33ccd3a0d80d6aeb8e7f56a2be80ae0732257",
        "sha256": "be4d1425fe69b4ff24fa418e15a2a2fbfb924db50d7e06861a937cfd3c81bc05",
        "size_bytes": 16_716_405,
        "source_url": (
            "https://archive.org/download/syriacnewtestam00murdgoog/"
            "syriacnewtestam00murdgoog.pdf"
        ),
    }
    review = json.loads((
        DATA_ROOT / "verification/reports/murdock-peshitta-1852-visual-review.json"
    ).read_text())
    assert review["reviewer"] == "OpenAI Codex (AI-assisted source verification)"
    assert datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00")) > datetime.fromisoformat(
        pdf["retrieved_at"].replace("Z", "+00:00")
    )


def test_ocr_word_stream_preserves_dom_order_across_structures():
    import xml.etree.ElementTree as ET
    import app.library.verification.adapters.murdock_sword as module

    page = ET.fromstring(
        "<OBJECT><HIDDENTEXT><PAGECOLUMN><REGION><PARAGRAPH><LINE>"
        "<WORD>alpha</WORD></LINE></PARAGRAPH></REGION></PAGECOLUMN>"
        "<PAGECOLUMN><REGION><PARAGRAPH><LINE><WORD>beta</WORD>"
        "<WORD>gamma</WORD></LINE></PARAGRAPH></REGION></PAGECOLUMN>"
        "</HIDDENTEXT></OBJECT>"
    )
    assert module._ocr_object_tokens(page) == ("alpha", "beta", "gamma")


def test_historical_exact_match_rejects_inserted_non_source_token():
    from app.library.verification.adapters.murdock_sword import _sample_candidate

    rows = tuple(
        SourceVerse(
            "matthew", 1, index + 1,
            "alpha beta gamma delta" if index == 1 else f"unselected verse {index}",
        )
        for index in range(9)
    )
    sample = _sample_candidate(
        rows, "beginning", 0, 0,
        (("alpha", "inserted", "beta", "gamma", "delta"),),
    )
    assert (sample["chapter"], sample["verse"]) == (1, 2)
    assert sample["result"] == "review_required"


def test_historical_selection_is_fixed_before_ocr_outcome():
    from app.library.verification.adapters.murdock_sword import _sample_candidate

    labels = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight")
    rows = tuple(
        SourceVerse(
            "matthew", 1, index + 1,
            f"fixed source verse label {label} alpha beta gamma delta",
        )
        for index, label in enumerate(labels)
    )
    # The first verse matches OCR, but the predetermined beginning-third median
    # is verse 2 (index 1) and must not be replaced with that successful result.
    ocr = (("fixed", "source", "verse", "label", "zero", "alpha", "beta", "gamma", "delta"),)
    sample = _sample_candidate(rows, "beginning", 0, 0, ocr)

    assert sample["selection_rule"] == "median source position within canonical work third"
    assert sample["selection_index"] == 1
    assert (sample["chapter"], sample["verse"]) == (1, 2)
    assert sample["result"] == "review_required"


def _lock_record():
    from app.library.verification.registry import ArtifactLockRecord

    payload = LIVE_ARTIFACT.read_bytes()
    return ArtifactLockRecord(
        family_id=DEFINITION.family_id,
        artifact_path=LIVE_ARTIFACT.name,
        source_url=DEFINITION.artifact_url,
        landing_url=DEFINITION.landing_url,
        retrieved_at="2026-08-29T05:53:51Z",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_adapter_compares_all_27_works_with_ten_declared_omissions(tmp_path):
    from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter

    output = tmp_path / "reports"
    result = MurdockSwordAdapter().compare_family(
        definition=DEFINITION,
        lock_record=_lock_record(),
        artifact_path=LIVE_ARTIFACT,
        current_bundle=DATA_ROOT / "corrected-bundle.zip",
        output=output,
    )

    assert result.report_count == 27
    child_reports = list((output / DEFINITION.family_id).glob("*.json"))
    assert len(child_reports) == 27
    summary = json.loads((output / f"{DEFINITION.family_id}.json").read_text())
    assert summary["family_id"] == DEFINITION.family_id
    assert summary["source_artifact_sha256"] == _lock_record().sha256
    assert summary["totals"] == {
        "exact": 7_947, "formatting": 0, "missing": 0, "extra": 0,
        "wording": 0,
    }
    assert summary["declared_omission_count"] == 10


def test_adapter_builds_deterministic_source_candidate_for_27_works(tmp_path):
    from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter

    output = tmp_path / "candidate.zip"
    result = MurdockSwordAdapter().build_candidate(
        definition=DEFINITION,
        lock_record=_lock_record(),
        artifact_path=LIVE_ARTIFACT,
        report_dir=DATA_ROOT / f"verification/reports/{DEFINITION.family_id}",
        output=output,
        replace_from_source=True,
    )
    assert result.work_count == 27
    first = output.read_bytes()
    MurdockSwordAdapter().build_candidate(
        definition=DEFINITION,
        lock_record=_lock_record(),
        artifact_path=LIVE_ARTIFACT,
        report_dir=DATA_ROOT / f"verification/reports/{DEFINITION.family_id}",
        output=output,
        replace_from_source=True,
    )
    assert output.read_bytes() == first
    with ZipFile(output) as archive:
        assert len(json.loads(archive.read("data/index.json"))["books"]) == 27
        philemon = json.loads(archive.read("data/philemon.json"))
        assert philemon[0]["v"][0]["t"].startswith(
            "PAUL, a prisoner"
        )


def test_cli_installs_reviewed_murdock_adapter():
    from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter
    from app.library.verification.cli import ADAPTERS

    assert type(ADAPTERS["murdock_sword"]) is MurdockSwordAdapter


def test_historical_artifacts_and_81_samples_are_reproducible(tmp_path):
    from app.library.verification.adapters.murdock_sword import (
        HISTORICAL_EVIDENCE_FILENAME,
        _ocr_leaves,
        build_historical_evidence,
        validate_historical_evidence, write_historical_evidence,
    )

    evidence = build_historical_evidence(DATA_ROOT / "verification")
    ocr_leaves = _ocr_leaves(
        DATA_ROOT / "verification/artifacts/syriacnewtestam00murdgoog_djvu.xml"
    )
    positions = {}
    for row in _parse():
        positions.setdefault(row.work_id, []).append((row.chapter, row.verse))

    assert evidence["schema_version"] == 1
    assert evidence["edition_note"] == (
        "The locked 1915 ninth edition is historical corroboration for James "
        "Murdock's translation, first published in 1852; it is not represented "
        "as an 1852 scan."
    )
    assert evidence["historical_source_title"] == "The Syriac New Testament"
    assert evidence["historical_source_edition"] == "Ninth edition"
    assert evidence["historical_source_year"] == 1915
    assert evidence["totals"] == {
        "confirmed_ocr": 39,
        "confirmed_visual": 41,
        "confirmed_formatting": 1,
        "review_required": 0,
    }
    assert len(evidence["samples"]) == 81
    assert all(sample["selection_rule"] == (
        "median source position within canonical work third"
    ) for sample in evidence["samples"])
    for sample in evidence["samples"]:
        electronic = tuple(re.findall(r"[a-z]+", sample["electronic_text"].lower()))
        anchor = tuple(sample["ocr_text_anchor"].split())
        if sample["result"] == "confirmed_ocr":
            assert anchor == electronic
        else:
            assert sample["result"] in {"confirmed_visual", "confirmed_formatting"}
            assert sample["ocr_mismatch_evidence"]
            review = sample["visual_review"]
            assert review["classification"] == sample["result"]
            assert review["crops"]
            for crop in review["crops"]:
                assert crop["pdf_page"] == crop["leaf"] + 1
                assert crop["ocr_token_start"] < crop["ocr_token_end"]
                assert crop["anchor_page_start"] >= crop["ocr_token_start"]
                assert crop["anchor_size"] > 0
                assert crop["ocr_canvas"] == [crop["ocr_canvas"][0], crop["ocr_canvas"][1]]
                assert crop["pdf_600dpi_canvas"] == [5100, 6600]
                assert crop["render_canvas"] == [1275, 1650]
        assert sample["matched_token_count"] <= len(electronic)
        assert sample["electronic_token_count"] == len(electronic)
        work_positions = positions[sample["work_id"]]
        selected_index = work_positions.index((sample["chapter"], sample["verse"]))
        lower = {
            "beginning": 0,
            "middle": len(work_positions) // 3,
            "end": 2 * len(work_positions) // 3,
        }[sample["phase"]]
        upper = {
            "beginning": len(work_positions) // 3,
            "middle": 2 * len(work_positions) // 3,
            "end": len(work_positions),
        }[sample["phase"]]
        assert lower <= selected_index < max(lower + 1, upper)
        page = ocr_leaves[sample["scan_leaf"]]
        if sample["result"] == "confirmed_ocr":
            assert any(
                page[index:index + len(anchor)] == anchor
                for index in range(len(page) - len(anchor) + 1)
            )
    formatting = next(
        sample for sample in evidence["samples"]
        if sample["result"] == "confirmed_formatting"
    )
    assert (formatting["work_id"], formatting["chapter"], formatting["verse"]) == (
        "jude", 1, 13,
    )
    assert formatting["visual_review"]["electronic_reading"] == "shootingstars"
    assert formatting["visual_review"]["printed_reading"] == "shooting-stars"
    assert evidence["encoding_evidence"]["module_byte"] == "0x86"
    assert evidence["encoding_evidence"]["decoded_glyph"] == "†"
    assert evidence["encoding_evidence"]["scan_leaf"] == 110
    assert {
        (sample["work_id"], sample["phase"])
        for sample in evidence["samples"]
    } == {
        (work_id, phase)
        for work_id in DEFINITION.expected_work_ids
        for phase in ("beginning", "middle", "end")
    }

    output = tmp_path / HISTORICAL_EVIDENCE_FILENAME
    write_historical_evidence(DATA_ROOT / "verification", output)
    validate_historical_evidence(output, DATA_ROOT / "verification", DEFINITION)


def _pdf_review_script():
    import importlib.util

    path = DATA_ROOT / "verify_murdock_pdf_review.py"
    spec = importlib.util.spec_from_file_location("verify_murdock_pdf_review_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pdf_review_renderer_timeout_is_bounded(monkeypatch):
    module = _pdf_review_script()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout", 0))

    monkeypatch.setattr(module.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="timed out"):
        module._run_checked(["pdftoppm", "-v"], timeout_seconds=1)


def test_pdf_review_ppm_rejects_oversize_and_malformed_files(tmp_path):
    module = _pdf_review_script()
    oversized = tmp_path / "oversized.ppm"
    oversized.write_bytes(b"P6\n1275 1650\n255\n")
    with oversized.open("r+b") as stream:
        stream.truncate(module.MAX_PPM_BYTES + 1)
    with pytest.raises(ValueError, match="size|large|limit"):
        module._ppm(oversized)

    malformed = tmp_path / "malformed.ppm"
    malformed.write_bytes(b"P3\n1275 1650\n255\nnot-binary-rgb")
    with pytest.raises(ValueError, match="canonical|dimensions|payload"):
        module._ppm(malformed)


@pytest.mark.parametrize("field", [
    "ocr_token_start", "anchor_page_start", "ocr_bbox", "render_bbox",
    "ocr_canvas", "pdf_600dpi_canvas", "render_canvas", "pixel_margin",
])
def test_pdf_review_rejects_tampered_crop_derivation(field):
    module = _pdf_review_script()
    derived = {
        "ocr_token_start": 1, "ocr_token_end": 4,
        "anchor_source_start": 0, "anchor_page_start": 2, "anchor_size": 2,
        "ocr_canvas": [100, 200], "pdf_600dpi_canvas": [5100, 6600],
        "render_canvas": [1275, 1650], "token_margin": 11, "pixel_margin": 24,
        "ocr_bbox": [1, 2, 3, 4], "render_bbox": [5, 6, 7, 8],
    }
    crop = dict(derived)
    crop[field] = 999 if isinstance(crop[field], int) else [999] * len(crop[field])
    with pytest.raises(ValueError, match="selection evidence"):
        module._validate_crop_evidence(crop, derived)


def test_bounded_zlib_decode_caps_output_before_allocation(monkeypatch):
    import app.library.verification.adapters.murdock_sword as module

    calls = []

    class Stream:
        eof = True
        unused_data = b""
        unconsumed_tail = b""

        def decompress(self, payload, max_length):
            calls.append(max_length)
            return b"x" * max_length

        def flush(self, length):
            calls.append(length)
            return b""

    monkeypatch.setattr(module.zlib, "decompressobj", lambda: Stream())
    with pytest.raises(ValueError, match="size|limit|exceeds"):
        module._bounded_decompress(b"compressed", 12)
    assert calls == [13]


def test_secure_snapshot_rejects_path_replacement_between_lstat_and_open(
    tmp_path, monkeypatch,
):
    import app.library.verification.adapters.murdock_sword as module

    path = tmp_path / "evidence.bin"
    replacement = tmp_path / "replacement.bin"
    path.write_bytes(b"reviewed")
    replacement.write_bytes(b"replaced")
    real_open = module.os.open

    def replace_then_open(value, flags):
        replacement.replace(path)
        return real_open(value, flags)

    monkeypatch.setattr(module.os, "open", replace_then_open)
    with pytest.raises(ValueError, match="changed|snapshot|identity"):
        module._secure_read(path, maximum=100, context="test evidence")


def test_module_parser_rejects_concurrent_artifact_replacement(tmp_path, monkeypatch):
    import app.library.verification.adapters.murdock_sword as module

    artifact = tmp_path / "murdock.zip"
    replacement = tmp_path / "replacement.zip"
    shutil.copyfile(LIVE_ARTIFACT, artifact)
    shutil.copyfile(LIVE_ARTIFACT, replacement)
    real_open = module.os.open
    swapped = False

    def replace_then_open(value, flags):
        nonlocal swapped
        if Path(value) == artifact and not swapped:
            swapped = True
            replacement.replace(artifact)
        return real_open(value, flags)

    monkeypatch.setattr(module.os, "open", replace_then_open)
    with pytest.raises(ValueError, match="changed|snapshot|identity"):
        module.parse_murdock_sword(artifact, DEFINITION)


def test_historical_builder_rejects_concurrent_lock_replacement(tmp_path, monkeypatch):
    import app.library.verification.adapters.murdock_sword as module

    verification = tmp_path / "verification"
    shutil.copytree(DATA_ROOT / "verification", verification)
    lock = verification / module.HISTORICAL_LOCK_FILENAME
    replacement = verification / "replacement.lock.json"
    shutil.copyfile(lock, replacement)
    real_open = module.os.open
    swapped = False

    def replace_then_open(value, flags):
        nonlocal swapped
        if Path(value) == lock and not swapped:
            swapped = True
            replacement.replace(lock)
        return real_open(value, flags)

    monkeypatch.setattr(module.os, "open", replace_then_open)
    with pytest.raises(ValueError, match="changed|snapshot|identity|lock"):
        module.build_historical_evidence(verification)


def test_candidate_rejects_concurrent_pre_rebuild_report_replacement(
    tmp_path, monkeypatch,
):
    import app.library.verification.adapters.murdock_sword as module

    verification = tmp_path / "verification"
    shutil.copytree(DATA_ROOT / "verification", verification)
    reports = verification / "reports"
    summary = reports / f"{DEFINITION.family_id}-pre-rebuild.json"
    replacement = reports / "replacement-pre-rebuild.json"
    shutil.copyfile(summary, replacement)
    real_open = module.os.open
    swapped = False

    def replace_then_open(value, flags):
        nonlocal swapped
        if Path(value) == summary and not swapped:
            swapped = True
            replacement.replace(summary)
        return real_open(value, flags)

    monkeypatch.setattr(module.os, "open", replace_then_open)
    with pytest.raises(ValueError, match="changed|snapshot|identity|report"):
        module.MurdockSwordAdapter().build_candidate(
            definition=DEFINITION,
            lock_record=_lock_record(),
            artifact_path=LIVE_ARTIFACT,
            report_dir=reports / DEFINITION.family_id,
            output=tmp_path / "candidate.zip",
            replace_from_source=True,
        )


def test_historical_evidence_rejects_unexplained_or_tampered_sample(tmp_path):
    from app.library.verification.adapters.murdock_sword import (
        build_historical_evidence,
        validate_historical_evidence,
    )

    evidence = build_historical_evidence(DATA_ROOT / "verification")
    evidence["samples"][0]["result"] = "review_required"
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="review_required|confirmed|historical"):
        validate_historical_evidence(path, DATA_ROOT / "verification", DEFINITION)


def test_historical_builder_rejects_tampered_visual_variance(tmp_path):
    import app.library.verification.adapters.murdock_sword as module

    verification = tmp_path / "verification"
    shutil.copytree(DATA_ROOT / "verification", verification)
    review = verification / "reports" / module.VISUAL_REVIEW_FILENAME
    payload = json.loads(review.read_text())
    jude = next(
        item for item in payload["samples"]
        if item["work_id"] == "jude" and item["phase"] == "middle"
    )
    jude["printed_reading"] = "shooting stars"
    review.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="visual|formatting|identity"):
        module.build_historical_evidence(verification)


def test_candidate_requires_canonical_historical_evidence(tmp_path):
    from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter

    with pytest.raises(ValueError, match="historical"):
        MurdockSwordAdapter().build_candidate(
            definition=DEFINITION,
            lock_record=_lock_record(),
            artifact_path=LIVE_ARTIFACT,
            report_dir=tmp_path / DEFINITION.family_id,
            output=tmp_path / "candidate.zip",
            replace_from_source=True,
        )


def test_candidate_rejects_empty_or_tampered_pre_rebuild_reports(tmp_path):
    from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter

    verification = tmp_path / "verification"
    shutil.copytree(DATA_ROOT / "verification", verification)
    reports_root = verification / "reports"
    family = reports_root / DEFINITION.family_id
    pre_family = reports_root / f"{DEFINITION.family_id}-pre-rebuild"
    for child in pre_family.glob("*.json"):
        child.unlink()
    with pytest.raises(ValueError, match="report|inventory|pre-rebuild"):
        MurdockSwordAdapter().build_candidate(
            definition=DEFINITION, lock_record=_lock_record(),
            artifact_path=LIVE_ARTIFACT, report_dir=family,
            output=tmp_path / "empty.zip", replace_from_source=True,
        )

    shutil.rmtree(verification)
    shutil.copytree(DATA_ROOT / "verification", verification)
    reports_root = verification / "reports"
    summary = reports_root / "murdock-peshitta-1852-pre-rebuild.json"
    payload = json.loads(summary.read_text())
    payload["parser_version"] = "tampered/1"
    summary.write_text(json.dumps(payload, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="report|parser|canonical|pre-rebuild"):
        MurdockSwordAdapter().build_candidate(
            definition=DEFINITION, lock_record=_lock_record(),
            artifact_path=LIVE_ARTIFACT,
            report_dir=reports_root / DEFINITION.family_id,
            output=tmp_path / "tampered.zip", replace_from_source=True,
        )


def test_candidate_rejects_tampered_lock_record(tmp_path):
    from dataclasses import replace
    from app.library.verification.adapters.murdock_sword import MurdockSwordAdapter

    with pytest.raises(ValueError, match="lock|artifact|source"):
        MurdockSwordAdapter().build_candidate(
            definition=DEFINITION,
            lock_record=replace(_lock_record(), sha256="0" * 64),
            artifact_path=LIVE_ARTIFACT,
            report_dir=DATA_ROOT / f"verification/reports/{DEFINITION.family_id}",
            output=tmp_path / "candidate.zip", replace_from_source=True,
        )
