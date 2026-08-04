import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.library.ingest.manifest import SourceManifest


def _write_bundle(path: Path, *, verses=None, member_name="data/books/01-genesis.json") -> bytes:
    verses = verses or [
        {"n": 1, "t": "በቀዳሚ  ገብረ እግዚአብሔር።"},
        {"n": 2, "t": "ወምድርሰ ኢታስተርኢ።"},
        {"n": 3, "t": "ወይቤ እግዚአብሔር።"},
    ]
    index = {
        "source": {"primary": "EOTCOpenSource/80-weahadu"},
        "books": [{
            "id": "GEN", "name": "Genesis", "file": "books/01-genesis.json",
        }],
    }
    book = {
        "id": "GEN",
        "name": "Genesis",
        "editions": {
            "gez-1980": {
                "language": "gez",
                "chapters": [{"n": 1, "verses": verses}],
            }
        },
    }
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("data/index.json", json.dumps(index, ensure_ascii=False))
        archive.writestr(member_name, json.dumps(book, ensure_ascii=False))
    return path.read_bytes()


def _manifest(archive_name: str, archive_bytes: bytes) -> SourceManifest:
    return SourceManifest.model_validate({
        "edition_code": "GEEZ1980-RESEARCH",
        "name": "Ge'ez Bible (1980 EC) — Research Use",
        "reading_language": "Ge'ez",
        "source_language": "Ge'ez",
        "script": "Ethiopic",
        "translator": None,
        "publisher": "Ethiopian Bible Society",
        "published_year": None,
        "license_spdx": "CC-BY-NC-ND-4.0",
        "attribution": (
            "Research-only local prototype source from EOTCOpenSource/80-weahadu; "
            "Bible text copyright Ethiopian Bible Society."
        ),
        "provenance_url": "https://github.com/EOTCOpenSource/80-weahadu",
        "source_tradition": "Ethiopian Orthodox Tewahedo Ge'ez",
        "relationship": "exact_ethiopian",
        "versification": "Ethiopian Orthodox source versification",
        "expected_works": {
            "genesis": {"chapters": 1, "verse_counts": {"1": 3}},
        },
        "source_files": [{
            "path": archive_name,
            "sha256": sha256(archive_bytes).hexdigest(),
            "source_url": "https://github.com/EOTCOpenSource/80-weahadu",
        }],
        "adapter": "weahadu_bundle",
        "adapter_options": {
            "edition": "gez-1980",
            "book_map": {"GEN": "genesis"},
        },
    })


def test_parses_only_mapped_geez_edition_with_traceable_locators(tmp_path):
    from app.library.ingest.adapters.weahadu_bundle import parse_weahadu_bundle

    archive_path = tmp_path / "bundle.zip"
    manifest = _manifest(archive_path.name, _write_bundle(archive_path))

    rows = parse_weahadu_bundle(manifest, tmp_path)

    assert [(row.work_id, row.chapter, row.verse, row.text) for row in rows] == [
        ("genesis", 1, 1, "በቀዳሚ ገብረ እግዚአብሔር።"),
        ("genesis", 1, 2, "ወምድርሰ ኢታስተርኢ።"),
        ("genesis", 1, 3, "ወይቤ እግዚአብሔር።"),
    ]
    assert rows[0].source_locator == (
        "bundle.zip!/data/books/01-genesis.json#gez-1980:1:1"
    )


def test_rejects_archive_when_bytes_do_not_match_manifest_checksum(tmp_path):
    from app.library.ingest.adapters.weahadu_bundle import parse_weahadu_bundle

    archive_path = tmp_path / "bundle.zip"
    archive_bytes = _write_bundle(archive_path)
    manifest = _manifest(archive_path.name, archive_bytes)
    archive_path.write_bytes(archive_bytes + b"changed")

    with pytest.raises(ValueError, match="checksum"):
        parse_weahadu_bundle(manifest, tmp_path)


@pytest.mark.parametrize(
    "verses, message",
    [
        ([{"n": 1, "t": "፩"}, {"n": 1, "t": "፩ duplicate"}], "duplicate"),
        ([{"n": 1, "t": ""}], "empty"),
        ([{"n": None, "t": "፩"}], "positive integer"),
    ],
)
def test_rejects_invalid_verse_records_before_staging(tmp_path, verses, message):
    from app.library.ingest.adapters.weahadu_bundle import parse_weahadu_bundle

    archive_path = tmp_path / "bundle.zip"
    manifest = _manifest(archive_path.name, _write_bundle(archive_path, verses=verses))

    with pytest.raises(ValueError, match=message):
        parse_weahadu_bundle(manifest, tmp_path)


def test_rejects_unsafe_zip_member_paths(tmp_path):
    from app.library.ingest.adapters.weahadu_bundle import parse_weahadu_bundle

    archive_path = tmp_path / "bundle.zip"
    archive_bytes = _write_bundle(archive_path, member_name="../01-genesis.json")
    manifest = _manifest(archive_path.name, archive_bytes)

    with pytest.raises(ValueError, match="unsafe archive member"):
        parse_weahadu_bundle(manifest, tmp_path)


def test_rejects_source_symlink_that_escapes_manifest_directory(tmp_path):
    from app.library.ingest.adapters.weahadu_bundle import parse_weahadu_bundle

    source_directory = tmp_path / "source"
    source_directory.mkdir()
    outside_archive = tmp_path / "outside.zip"
    archive_bytes = _write_bundle(outside_archive)
    (source_directory / "bundle.zip").symlink_to(outside_archive)
    manifest = _manifest("bundle.zip", archive_bytes)

    with pytest.raises(ValueError, match="regular file"):
        parse_weahadu_bundle(manifest, source_directory)
