from __future__ import annotations

from pathlib import Path
import hashlib
import json
import stat
import struct
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from app.library.verification.registry import APPROVED_SOURCE_DEFINITIONS
from app.library.verification.registry import ArtifactLockRecord


DEFINITION = APPROVED_SOURCE_DEFINITIONS["world-messianic-bible"]

CODE_BY_WORK = {
    "genesis": "GEN", "exodus": "EXO", "leviticus": "LEV",
    "numbers": "NUM", "deuteronomy": "DEU", "joshua": "JOS",
    "judges": "JDG", "ruth": "RUT", "1-samuel": "1SA",
    "2-samuel": "2SA", "1-kings": "1KI", "2-kings": "2KI",
    "1-chronicles": "1CH", "2-chronicles": "2CH", "ezra": "EZR",
    "nehemiah": "NEH", "esther": "EST", "job": "JOB",
    "psalms": "PSA", "proverbs": "PRO", "ecclesiastes": "ECC",
    "song-of-solomon": "SOL", "isaiah": "ISA", "jeremiah": "JER",
    "lamentations": "LAM", "ezekiel": "EZE", "daniel": "DAN",
    "hosea": "HOS", "joel": "JOE", "amos": "AMO", "obadiah": "OBA",
    "jonah": "JON", "micah": "MIC", "nahum": "NAH",
    "habakkuk": "HAB", "zephaniah": "ZEP", "haggai": "HAG",
    "zechariah": "ZEC", "malachi": "MAL",
}
NT_CODES = (
    "MAT", "MAR", "LUK", "JOH", "ACT", "ROM", "1CO", "2CO", "GAL",
    "EPH", "PHI", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM",
    "HEB", "JAM", "1PE", "2PE", "1JO", "2JO", "3JO", "JUD", "REV",
)


def _payload() -> bytes:
    lines = [
        f"{CODE_BY_WORK[work]} 1:1 {work} official text"
        for work in DEFINITION.expected_work_ids
    ]
    lines.extend(f"{code} 1:1 New Testament must not leak" for code in NT_CODES)
    return ("\n".join(lines) + "\n").encode("utf-8")


ANCILLARY_MEMBERS = (
    ("engwmb_about.htm", b"<html>about</html>"),
    ("engwmb_vpl.sql", b"sql"),
    ("engwmb_vpl.xml", b"<bible/>"),
    ("haiola.css", b"body{}"),
)


def _members(payload=None):
    return (("engwmb_vpl.txt", _payload() if payload is None else payload), *ANCILLARY_MEMBERS)


def _write_zip(path: Path, members=None) -> Path:
    members = _members() if members is None else members
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, payload in members:
            archive.writestr(name, _payload() if payload is None else payload)
    return path


def _parse(path: Path):
    from app.library.verification.adapters.wmb_vpl import parse_wmb_vpl

    return parse_wmb_vpl(path, DEFINITION)


def _patch_flags(payload: bytes, flag: int) -> bytes:
    patched = bytearray(payload)
    offset = 0
    while True:
        offset = patched.find(b"PK\x03\x04", offset)
        if offset < 0:
            break
        struct.pack_into("<H", patched, offset + 6, flag)
        offset += 4
    offset = 0
    while True:
        offset = patched.find(b"PK\x01\x02", offset)
        if offset < 0:
            break
        struct.pack_into("<H", patched, offset + 8, flag)
        offset += 4
    return bytes(patched)


def test_parser_returns_immutable_exact_39_work_inventory_without_leakage(tmp_path):
    from app.library.verification.types import SourceVerse

    rows = _parse(_write_zip(tmp_path / "engwmb_vpl.zip"))

    assert type(rows) is tuple
    assert all(type(row) is SourceVerse for row in rows)
    assert {row.work_id for row in rows} == set(DEFINITION.expected_work_ids)
    assert len(rows) == 39
    assert all(row.chapter > 0 and row.verse > 0 and row.text.strip() for row in rows)
    assert not ({"matthew", "tobit"} & {row.work_id for row in rows})


def test_parser_rejects_wrong_or_extra_member_structure(tmp_path):
    with pytest.raises(ValueError, match="reviewed five-member set"):
        _parse(_write_zip(tmp_path / "wrong.zip", (("changed.txt", _payload()), *ANCILLARY_MEMBERS)))
    with pytest.raises(ValueError, match="reviewed five-member set"):
        _parse(_write_zip(
            tmp_path / "extra.zip",
            (*_members(), ("readme.txt", b"extra")),
        ))


def test_parser_rejects_duplicate_member_name(tmp_path):
    path = tmp_path / "duplicate.zip"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, payload in _members():
            archive.writestr(name, payload)
        archive.writestr("engwmb_vpl.txt", _payload())
    with pytest.raises(ValueError, match="reviewed five-member set|duplicate"):
        _parse(path)


@pytest.mark.parametrize("member", ["../engwmb_vpl.txt", "/engwmb_vpl.txt", "folder/engwmb_vpl.txt"])
def test_parser_rejects_traversal_or_nested_member(tmp_path, member):
    with pytest.raises(ValueError, match="reviewed five-member set|unsafe"):
        _parse(_write_zip(tmp_path / "unsafe.zip", ((member, _payload()), *ANCILLARY_MEMBERS)))


def test_parser_rejects_symlink_member(tmp_path):
    path = tmp_path / "symlink.zip"
    info = ZipInfo("engwmb_vpl.txt")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(path, "w") as archive:
        archive.writestr(info, b"target")
        for name, payload in ANCILLARY_MEMBERS:
            archive.writestr(name, payload)
    with pytest.raises(ValueError, match="regular file"):
        _parse(path)


def test_parser_rejects_encrypted_flag(tmp_path):
    path = _write_zip(tmp_path / "encrypted.zip")
    path.write_bytes(_patch_flags(path.read_bytes(), 1))
    with pytest.raises(ValueError, match="encrypted"):
        _parse(path)


def test_parser_rejects_invalid_utf8(tmp_path):
    with pytest.raises(ValueError, match="UTF-8"):
        _parse(_write_zip(tmp_path / "bad-encoding.zip", _members(b"\xff")))


@pytest.mark.parametrize("replacement", ["\r", "\r\n"])
def test_parser_rejects_nonreviewed_newline_conventions(tmp_path, replacement):
    text = _payload().decode("utf-8").replace("\n", replacement, 1)
    with pytest.raises(ValueError, match="reviewed LF newline convention"):
        _parse(_write_zip(tmp_path / "bad-newline.zip", _members(text.encode("utf-8"))))


@pytest.mark.parametrize(
    "character", ["\u0000", "\u0009", "\u001c", "\u0085", "\u2028", "\u2029"],
)
def test_parser_rejects_controls_and_unicode_line_separators_before_splitting(
    tmp_path, character,
):
    text = _payload().decode("utf-8").replace(
        "genesis official", f"genesis{character} official",
    )
    with pytest.raises(ValueError, match="control or Unicode line separator"):
        _parse(_write_zip(tmp_path / "bad-control.zip", _members(text.encode("utf-8"))))


@pytest.mark.parametrize("replacement", ["\r\n", "\u0085", "\u2028", "\u2029"])
def test_live_payload_mutations_reject_replaced_lf_before_line_parsing(
    tmp_path, replacement,
):
    live = (
        Path(__file__).parents[3]
        / "data/scripture/eotc-composite-en/verification/artifacts/engwmb_vpl.zip"
    )
    with ZipFile(live) as archive:
        members = [(info.filename, archive.read(info)) for info in archive.infolist()]
    mutated = []
    for name, payload in members:
        if name == "engwmb_vpl.txt":
            text = payload.decode("utf-8").replace("\n", replacement, 1)
            payload = text.encode("utf-8")
        mutated.append((name, payload))
    with pytest.raises(
        ValueError,
        match="reviewed LF newline convention|control or Unicode line separator",
    ):
        _parse(_write_zip(tmp_path / "mutated-live.zip", mutated))


@pytest.mark.parametrize("line", [
    "GEN 0:1 invalid chapter", "GEN 1:0 invalid verse", "GEN 1:1    ",
    "GEN 1:1 valid\x00control", "GEN 1:2 valid\nmalformed",
])
def test_parser_rejects_invalid_vpl_rows(tmp_path, line):
    payload = _payload() + (line + "\n").encode("utf-8")
    with pytest.raises(ValueError, match="invalid WMB VPL|nonblank|control"):
        _parse(_write_zip(tmp_path / "bad-row.zip", _members(payload)))


def test_parser_rejects_duplicate_position(tmp_path):
    payload = _payload() + b"GEN 1:1 duplicate\n"
    with pytest.raises(ValueError, match="duplicate"):
        _parse(_write_zip(tmp_path / "duplicate-position.zip", _members(payload)))


def test_parser_rejects_missing_approved_work(tmp_path):
    payload = _payload().replace(b"MAL 1:1 malachi official text\n", b"")
    with pytest.raises(ValueError, match="exact reviewed 66-code inventory"):
        _parse(_write_zip(tmp_path / "missing.zip", _members(payload)))


def test_parser_rejects_missing_reviewed_new_testament_code(tmp_path):
    payload = _payload().replace(b"MAR 1:1 New Testament must not leak\n", b"")
    with pytest.raises(ValueError, match="exact reviewed 66-code inventory"):
        _parse(_write_zip(tmp_path / "missing-mar.zip", _members(payload)))


def test_parser_rejects_unknown_source_code_even_with_all_66_reviewed_codes(tmp_path):
    payload = _payload() + b"XYZ 1:1 Unknown source code\n"
    with pytest.raises(ValueError, match="exact reviewed 66-code inventory"):
        _parse(_write_zip(tmp_path / "unknown-code.zip", _members(payload)))


def test_parser_rejects_zip_bomb_ratio(tmp_path, monkeypatch):
    from app.library.verification.adapters import wmb_vpl

    monkeypatch.setattr(wmb_vpl, "MAX_COMPRESSION_RATIO", 1)
    with pytest.raises(ValueError, match="compression ratio"):
        _parse(_write_zip(tmp_path / "bomb.zip"))


def test_live_locked_artifact_has_exact_39_work_inventory_and_verse_count():
    artifact = (
        Path(__file__).parents[3]
        / "data/scripture/eotc-composite-en/verification/artifacts/engwmb_vpl.zip"
    )
    rows = _parse(artifact)

    assert len(rows) == 23_145
    assert {row.work_id for row in rows} == set(DEFINITION.expected_work_ids)
    assert sum(row.work_id == "genesis" for row in rows) == 1_533
    assert sum(row.work_id == "ezekiel" for row in rows) == 1_273


def _current_bundle(path: Path, *, changed_genesis=False) -> Path:
    books = []
    members = []
    for index, work_id in enumerate(DEFINITION.expected_work_ids):
        code = CODE_BY_WORK[work_id]
        member = f"data/{code.casefold()}.json"
        text = f"{work_id} official text"
        if changed_genesis and work_id == "genesis":
            text = "different wording"
        books.append({
            "id": code, "name": work_id, "file": member, "src": "wmb",
            "chapters": 1,
        })
        members.append((member, json.dumps([
            {"c": 1, "v": [{"n": 1, "t": text}]},
        ]).encode("utf-8")))
    members.append(("data/index.json", json.dumps({"books": books}).encode("utf-8")))
    _write_zip(path, members)
    return path


def _lock_record(path: Path) -> ArtifactLockRecord:
    payload = path.read_bytes()
    return ArtifactLockRecord(
        family_id="world-messianic-bible",
        artifact_path=path.name,
        source_url=DEFINITION.artifact_url,
        landing_url=DEFINITION.landing_url,
        retrieved_at="2026-08-18T11:09:49Z",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_adapter_compares_all_39_works_and_classifies_every_difference(tmp_path):
    from app.library.verification.adapters.wmb_vpl import WmbVplAdapter

    artifact = _write_zip(tmp_path / "engwmb_vpl.zip")
    current = _current_bundle(tmp_path / "current.zip", changed_genesis=True)
    output = tmp_path / "reports"
    result = WmbVplAdapter().compare_family(
        definition=DEFINITION,
        lock_record=_lock_record(artifact),
        artifact_path=artifact,
        current_bundle=current,
        output=output,
    )

    assert result.report_count == 39
    assert len(list((output / "world-messianic-bible").glob("*.json"))) == 39
    summary = json.loads((output / "world-messianic-bible.json").read_text())
    assert summary["totals"] == {
        "exact": 38, "formatting": 0, "missing": 0, "extra": 0, "wording": 1,
    }
    genesis = json.loads(
        (output / "world-messianic-bible/genesis.json").read_text()
    )
    assert genesis["differences"][0]["classification"] == "wording"


def test_adapter_builds_deterministic_source_candidate_for_exact_39_works(tmp_path):
    from app.library.verification.adapters.wmb_vpl import WmbVplAdapter

    artifact = _write_zip(tmp_path / "engwmb_vpl.zip")
    output = tmp_path / "candidate.zip"
    result = WmbVplAdapter().build_candidate(
        definition=DEFINITION,
        lock_record=_lock_record(artifact),
        artifact_path=artifact,
        report_dir=tmp_path,
        output=output,
        replace_from_source=True,
    )

    assert result.work_count == 39
    first = output.read_bytes()
    WmbVplAdapter().build_candidate(
        definition=DEFINITION,
        lock_record=_lock_record(artifact),
        artifact_path=artifact,
        report_dir=tmp_path,
        output=output,
        replace_from_source=True,
    )
    assert output.read_bytes() == first
    with ZipFile(output) as archive:
        index = json.loads(archive.read("data/index.json"))
        assert [book["work_id"] for book in index["books"]] == list(
            DEFINITION.expected_work_ids
        )
        genesis = json.loads(archive.read("data/genesis.json"))
        assert genesis[0]["v"][0]["t"] == "genesis official text"


def test_task4_cli_installs_reviewed_wmb_adapter():
    from app.library.verification.adapters.wmb_vpl import WmbVplAdapter
    from app.library.verification.cli import ADAPTERS

    assert type(ADAPTERS["wmb_vpl"]) is WmbVplAdapter
