import json
from hashlib import sha256
from pathlib import Path
import stat
import struct
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from app.library.ingest.manifest import SourceManifest


def _work_source(source_key="world-messianic-bible", *, scope="ethio81"):
    return {
        "source_key": source_key,
        "source_label": "Reviewed source",
        "translator": None,
        "source_language": "English",
        "source_tradition": "English Bible translation",
        "published_year": 2000,
        "license_spdx": "LicenseRef-Public-Domain",
        "attribution": "Public-domain test fixture.",
        "provenance_url": "https://example.com/source",
        "fallback": False,
        "modified": False,
        "modification_note": None,
        "verification_status": "verified",
        "canon_scope": scope,
    }


def _manifest(
    archive_name: str,
    archive_bytes: bytes,
    *,
    book_map=None,
    expected_works=None,
    source_keys=None,
    known_missing_verses=None,
) -> SourceManifest:
    book_map = book_map or {"GEN": "genesis"}
    expected_works = expected_works or {
        work_id: {"chapters": 1, "verse_counts": {"1": 2}}
        for work_id in book_map.values()
    }
    source_keys = source_keys or {
        work_id: "world-messianic-bible" for work_id in book_map.values()
    }
    return SourceManifest.model_validate({
        "edition_code": "COMPOSITE-ENGLISH-TEST",
        "name": "Composite English test fixture",
        "reading_language": "English",
        "source_language": "English",
        "script": "Latin",
        "translator": None,
        "publisher": None,
        "published_year": 2000,
        "license_spdx": "LicenseRef-Mixed",
        "attribution": "Synthetic test fixture.",
        "provenance_url": "https://example.com/bundle",
        "source_tradition": "Composite English sources",
        "relationship": "general_reading",
        "versification": "Source versification",
        "expected_works": expected_works,
        "source_files": [{
            "path": archive_name,
            "sha256": sha256(archive_bytes).hexdigest(),
            "source_url": "https://example.com/bundle.zip",
        }],
        "adapter": "composite_english_bundle",
        "adapter_options": {
            "book_map": book_map,
            "work_sources": {
                work_id: _work_source(source_keys[work_id])
                for work_id in book_map.values()
            },
            "supplemental_works": [],
            "known_missing_verses": known_missing_verses or {},
        },
    })


def _book(name="Genesis", *, chapters=None):
    return chapters or [
        {"c": 1, "v": [
            {"n": 1, "t": "In  the beginning"},
            {"n": 2, "t": "The earth was formless."},
        ]},
    ]


def _index_record(
    source_id="GEN", *, name="Genesis", file="data/gen.json", chapters=1, src="wmb"
):
    return {
        "id": source_id,
        "name": name,
        "file": file,
        "src": src,
        "chapters": chapters,
    }


def _write_zip(path: Path, members, *, duplicate_members=()):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, payload in members:
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            archive.writestr(name, data)
        for name, payload in duplicate_members:
            archive.writestr(name, json.dumps(payload).encode())
    return path.read_bytes()


def _write_bundle(path: Path, *, index=None, books=None, extra_members=()):
    index = index if index is not None else {"books": [_index_record()]}
    books = books if books is not None else {"data/gen.json": _book()}
    members = [("data/index.json", index), *books.items(), *extra_members]
    return _write_zip(path, members)


def _parse(path, archive_bytes, **manifest_kwargs):
    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )

    return parse_composite_english_bundle(
        _manifest(path.name, archive_bytes, **manifest_kwargs), path.parent
    )


def _patch_zip_flags(payload: bytes, flag: int) -> bytes:
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


def _patch_first_declared_size(payload: bytes, size: int) -> bytes:
    patched = bytearray(payload)
    local = patched.index(b"PK\x03\x04")
    central = patched.index(b"PK\x01\x02")
    struct.pack_into("<I", patched, local + 22, size)
    struct.pack_into("<I", patched, central + 24, size)
    return bytes(patched)


def test_parses_mapped_books_in_manifest_then_numeric_order(tmp_path):
    archive_path = tmp_path / "bundle.zip"
    index = {"books": [
        _index_record("EXO", name="Exodus", file="data/exo.json"),
        _index_record(chapters=2),
        {"id": "TOB", "name": "Tobit", "chapters": 0},
    ]}
    books = {
        "data/gen.json": [
            {"c": "2", "v": [{"n": 1, "t": "Chapter two."}]},
            {"c": 1, "v": [
                {"n": 2, "t": "Second verse."},
                {"n": 1, "t": "In  the beginning"},
            ]},
        ],
        "data/exo.json": _book("Exodus"),
    }
    archive_bytes = _write_bundle(archive_path, index=index, books=books)
    manifest = _manifest(
        archive_path.name,
        archive_bytes,
        book_map={"GEN": "genesis", "EXO": "exodus"},
        expected_works={
            "genesis": {"chapters": 2},
            "exodus": {"chapters": 1},
        },
    )

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )
    rows = parse_composite_english_bundle(manifest, tmp_path)

    assert [(r.work_id, r.chapter, r.verse, r.text) for r in rows] == [
        ("genesis", 1, 1, "In the beginning"),
        ("genesis", 1, 2, "Second verse."),
        ("genesis", 2, 1, "Chapter two."),
        ("exodus", 1, 1, "In the beginning"),
        ("exodus", 1, 2, "The earth was formless."),
    ]
    assert rows[0].source_locator == "bundle.zip!/data/gen.json#1:1"


def test_accepts_only_declared_numeric_verse_gap_without_placeholders(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, books={
        "data/gen.json": [{"c": 1, "v": [
            {"n": 4, "t": "Verse four."},
            {"n": 1, "t": "Verse one."},
            {"n": 2, "t": "Verse two."},
        ]}],
    })
    rows = _parse(
        path,
        payload,
        expected_works={"genesis": {"chapters": 1, "verse_counts": {"1": 3}}},
        known_missing_verses={"genesis": {"1": [3]}},
    )

    assert [(row.verse, row.text) for row in rows] == [
        (1, "Verse one."),
        (2, "Verse two."),
        (4, "Verse four."),
    ]
    assert [row.source_locator for row in rows] == [
        "bundle.zip!/data/gen.json#1:1",
        "bundle.zip!/data/gen.json#1:2",
        "bundle.zip!/data/gen.json#1:4",
    ]


@pytest.mark.parametrize(
    ("verses", "known_missing_verses", "message"),
    (
        ([{"n": 1, "t": "One"}, {"n": 2, "t": "Two"}, {"n": 4, "t": "Four"}], {}, "undeclared|contiguous"),
        ([{"n": 1, "t": "One"}, {"n": 2, "t": "Two"}, {"n": 3, "t": "Three"}], {"genesis": {"1": [3]}}, "actually present|disjoint"),
        ([{"n": 1, "t": "One"}, {"n": 3, "t": "Three"}], {"genesis": {"1": [4]}}, "undeclared|contiguous"),
        ([], {"genesis": {"1": [1]}}, "no verses"),
        ([{"n": 1, "t": "One"}, {"n": 1, "t": "Again"}], {"genesis": {"1": [2]}}, "duplicate verse"),
    ),
)
def test_rejects_incorrect_missing_verse_declarations(
    tmp_path, verses, known_missing_verses, message
):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, books={
        "data/gen.json": [{"c": 1, "v": verses}],
    })
    with pytest.raises(ValueError, match=message):
        _parse(path, payload, known_missing_verses=known_missing_verses)


def test_rejects_missing_verse_declaration_for_absent_archive_chapter(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path)
    with pytest.raises(ValueError, match="declaration.*chapter|chapter count"):
        _parse(
            path,
            payload,
            expected_works={"genesis": {"chapters": 2}},
            known_missing_verses={"genesis": {"2": [1]}},
        )


def test_requires_matching_checksum_and_one_regular_local_archive(tmp_path):
    archive_path = tmp_path / "bundle.zip"
    archive_bytes = _write_bundle(archive_path)
    manifest = _manifest(archive_path.name, archive_bytes)
    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )

    archive_path.write_bytes(archive_bytes + b"changed")
    with pytest.raises(ValueError, match="checksum"):
        parse_composite_english_bundle(manifest, tmp_path)

    archive_path.write_bytes(archive_bytes)
    for sources in ([], [manifest.source_files[0], manifest.source_files[0]]):
        invalid = manifest.model_copy(update={"source_files": sources})
        with pytest.raises(ValueError, match="exactly one"):
            parse_composite_english_bundle(invalid, tmp_path)

    archive_path.unlink()
    archive_path.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        parse_composite_english_bundle(manifest, tmp_path)


def test_rejects_source_symlink_even_when_target_is_inside_manifest_directory(tmp_path):
    target = tmp_path / "target.zip"
    archive_bytes = _write_bundle(target)
    link = tmp_path / "bundle.zip"
    link.symlink_to(target)
    manifest = _manifest(link.name, archive_bytes)

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )
    with pytest.raises(ValueError, match="regular file"):
        parse_composite_english_bundle(manifest, tmp_path)


def test_rejects_symlink_in_archive_path_ancestor(tmp_path):
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    archive_path = real_directory / "bundle.zip"
    archive_bytes = _write_bundle(archive_path)
    (tmp_path / "linked").symlink_to(real_directory, target_is_directory=True)
    manifest = _manifest("linked/bundle.zip", archive_bytes)

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )
    with pytest.raises(ValueError, match="symlink|regular file"):
        parse_composite_english_bundle(manifest, tmp_path)


def test_path_replacement_cannot_change_bytes_parsed_after_checksum(
    tmp_path, monkeypatch
):
    import app.library.ingest.adapters.composite_english_bundle as adapter

    archive_path = tmp_path / "bundle.zip"
    original_bytes = _write_bundle(archive_path)
    replacement_path = tmp_path / "replacement.zip"
    _write_bundle(replacement_path, books={
        "data/gen.json": [{"c": 1, "v": [
            {"n": 1, "t": "Replacement text."},
            {"n": 2, "t": "Replacement text two."},
        ]}],
    })
    manifest = _manifest(archive_path.name, original_bytes)
    real_zip_file = adapter.ZipFile
    opened_arguments = []

    def replace_path_then_open(opened_archive, *args, **kwargs):
        opened_arguments.append(opened_archive)
        replacement_path.replace(archive_path)
        return real_zip_file(opened_archive, *args, **kwargs)

    monkeypatch.setattr(adapter, "ZipFile", replace_path_then_open)

    rows = adapter.parse_composite_english_bundle(manifest, tmp_path)

    assert rows[0].text == "In the beginning"
    assert len(opened_arguments) == 1
    assert hasattr(opened_arguments[0], "read")


@pytest.mark.parametrize(
    "index_payload,message",
    [
        (b"\xff", "UTF-8 JSON"),
        (b"{", "UTF-8 JSON"),
        ([], "JSON object"),
        ({}, "books"),
        ({"books": {}}, "books"),
    ],
)
def test_rejects_invalid_index_json(tmp_path, index_payload, message):
    path = tmp_path / "bundle.zip"
    payload = _write_zip(path, [("data/index.json", index_payload)])
    with pytest.raises(ValueError, match=message):
        _parse(path, payload)


def test_rejects_bad_zip(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = b"not a zip"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="invalid source archive"):
        _parse(path, payload)


def test_rejects_os_error_while_opening_archive(tmp_path, monkeypatch):
    import app.library.ingest.adapters.composite_english_bundle as adapter

    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path)

    def fail_to_open(_path):
        raise OSError("permission-safe simulated open failure")

    monkeypatch.setattr(adapter, "ZipFile", fail_to_open)
    with pytest.raises(ValueError, match="invalid source archive"):
        _parse(path, payload)


def test_translates_checksum_read_oserror_with_cause():
    from app.library.ingest.adapters.composite_english_bundle import (
        _checksum_open_file,
    )

    class BrokenArchive:
        def seek(self, _offset):
            return 0

        def read(self, _size):
            raise OSError("simulated read failure")

    with pytest.raises(ValueError, match="checksum") as raised:
        _checksum_open_file(BrokenArchive())

    assert isinstance(raised.value.__cause__, OSError)


def test_rejects_archive_outside_manifest_directory(tmp_path):
    outside_path = tmp_path / "outside.zip"
    payload = _write_bundle(outside_path)
    manifest_directory = tmp_path / "manifest"
    manifest_directory.mkdir()
    manifest = _manifest("bundle.zip", payload)
    forged_source = manifest.source_files[0].model_copy(
        update={"path": "../outside.zip"}
    )
    manifest = manifest.model_copy(update={"source_files": [forged_source]})

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )
    with pytest.raises(ValueError, match="inside the manifest directory"):
        parse_composite_english_bundle(manifest, manifest_directory)


@pytest.mark.parametrize("name", ["", "/abs", "\\abs", "a\\b", ".", "..", "a/./b", "a/../b"])
def test_rejects_unsafe_archive_member_names(tmp_path, name):
    path = tmp_path / "bundle.zip"
    try:
        payload = _write_bundle(path, extra_members=[(name, b"x")])
    except IndexError:
        pytest.skip("stdlib cannot construct an empty-name ZIP member")
    with pytest.raises(ValueError, match="unsafe archive member"):
        _parse(path, payload)


def test_rejects_symlink_encrypted_and_duplicate_members(tmp_path):
    path = tmp_path / "bundle.zip"
    info = ZipInfo("unsafe-link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(path, "w") as archive:
        archive.writestr("data/index.json", json.dumps({"books": []}))
        archive.writestr(info, "target")
    payload = path.read_bytes()
    with pytest.raises(ValueError, match="unsafe archive member"):
        _parse(path, payload, book_map={"GEN": "genesis"})

    payload = _write_bundle(path)
    encrypted = _patch_zip_flags(payload, 1)
    path.write_bytes(encrypted)
    with pytest.raises(ValueError, match="unsafe archive member"):
        _parse(path, encrypted)

    with pytest.warns(UserWarning, match="Duplicate name"):
        duplicate = _write_zip(
            path,
            [("data/index.json", {"books": [_index_record()]}), ("data/gen.json", _book())],
            duplicate_members=[("data/gen.json", _book())],
        )
    with pytest.raises(ValueError, match="duplicate archive member"):
        _parse(path, duplicate)


def test_rejects_too_many_members_and_excessive_declared_size(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(
        path,
        extra_members=[(f"empty/{number}", b"") for number in range(1023)],
    )
    with pytest.raises(ValueError, match="too many members"):
        _parse(path, payload)

    payload = _write_bundle(path)
    oversized = _patch_first_declared_size(payload, 128 * 1024 * 1024 + 1)
    path.write_bytes(oversized)
    with pytest.raises(ValueError, match="uncompressed size"):
        _parse(path, oversized)


@pytest.mark.parametrize(
    "books,message",
    [
        ([{"id": " ", "chapters": 0}], "nonblank"),
        ([_index_record(), {"id": "gen", "chapters": 0}], "duplicate book id"),
        ([_index_record("EXO", name="Exodus", file="data/exo.json")], "missing mapped"),
        ([_index_record(), _index_record("EXO", name="Exodus", file="data/exo.json")], "unexpected populated"),
    ],
)
def test_index_ids_and_populated_set_must_match_mapping(tmp_path, books, message):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, index={"books": books})
    with pytest.raises(ValueError, match=message):
        _parse(path, payload)


def test_reports_first_unexpected_populated_book_in_index_order(tmp_path):
    path = tmp_path / "bundle.zip"
    records = [
        _index_record(),
        _index_record("ZZZ", file="data/zzz.json"),
        _index_record("AAA", file="data/aaa.json"),
    ]
    payload = _write_bundle(path, index={"books": records})

    with pytest.raises(ValueError, match="unexpected populated book 'ZZZ'"):
        _parse(path, payload)


@pytest.mark.parametrize(
    "exo_member",
    ["data/shared.json", "data/SHARED.json"],
    ids=["exact", "case-folded"],
)
def test_rejects_populated_books_that_alias_one_member_path(tmp_path, exo_member):
    path = tmp_path / "bundle.zip"
    records = [
        _index_record(file="data/shared.json"),
        _index_record("EXO", name="Exodus", file=exo_member),
    ]
    books = {"data/shared.json": _book()}
    if exo_member != "data/shared.json":
        books[exo_member] = _book()
    payload = _write_bundle(path, index={"books": records}, books=books)

    with pytest.raises(ValueError, match="duplicate populated member path"):
        _parse(
            path,
            payload,
            book_map={"GEN": "genesis", "EXO": "exodus"},
            expected_works={
                "genesis": {"chapters": 1},
                "exodus": {"chapters": 1},
            },
        )


@pytest.mark.parametrize(
    "placeholder",
    [
        "not a record",
        {"id": "TOB"},
        {"id": "TOB", "chapters": False},
        {"id": "TOB", "chapters": 1},
        {"id": "TOB", "chapters": 0, "src": "wmb"},
    ],
)
def test_rejects_malformed_placeholder_records(tmp_path, placeholder):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, index={"books": [_index_record(), placeholder]})
    with pytest.raises(ValueError, match="placeholder|book record"):
        _parse(path, payload)


@pytest.mark.parametrize(
    "change,message",
    [
        ({"name": " "}, "source name"),
        ({"file": "gen.json"}, "data/"),
        ({"file": "data/../gen.json"}, "unsafe source file"),
        ({"file": "data\\gen.json"}, "unsafe source file"),
        ({"file": "/data/gen.json"}, "unsafe source file"),
        ({"chapters": 0}, "positive integer"),
        ({"chapters": True}, "positive integer"),
        ({"src": "unknown"}, "source family"),
    ],
)
def test_rejects_invalid_populated_record_fields(tmp_path, change, message):
    path = tmp_path / "bundle.zip"
    record = _index_record()
    record.update(change)
    payload = _write_bundle(path, index={"books": [record]})
    with pytest.raises(ValueError, match=message):
        _parse(path, payload)


@pytest.mark.parametrize(
    "src,source_key",
    [
        ("wmb", "world-messianic-bible"),
        ("peshitta", "murdock-peshitta-1852"),
        ("web_apocrypha", "world-english-bible-apocrypha"),
        ("kjv_apocrypha", "kjv-1611-fallback"),
        ("meqabyan", "wikisource-meqabyan-geez"),
        ("extra", "rh-charles-ethiopic"),
    ],
)
def test_accepts_each_exact_source_family_mapping(tmp_path, src, source_key):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, index={"books": [_index_record(src=src)]})
    assert len(_parse(path, payload, source_keys={"genesis": source_key})) == 2


def test_rejects_source_family_mismatch_and_missing_file(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path)
    with pytest.raises(ValueError, match="source family"):
        _parse(path, payload, source_keys={"genesis": "murdock-peshitta-1852"})

    payload = _write_bundle(path, books={})
    with pytest.raises(ValueError, match="missing required archive member"):
        _parse(path, payload)


@pytest.mark.parametrize("source_family", [None, True, False, 1, 1.5, [], {}])
def test_rejects_non_string_source_family_with_controlled_error(
    tmp_path, source_family
):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(
        path, index={"books": [_index_record(src=source_family)]}
    )
    with pytest.raises(ValueError, match="source family"):
        _parse(path, payload)


@pytest.mark.parametrize("source_id", [None, True, False, 1, 1.5, [], {}])
def test_rejects_non_string_index_ids(tmp_path, source_id):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(
        path, index={"books": [_index_record(source_id)]}
    )
    with pytest.raises(ValueError, match="book id"):
        _parse(path, payload)


@pytest.mark.parametrize(
    "book_payload",
    [b"\xff", b"{"],
    ids=["invalid-utf8", "invalid-json"],
)
def test_rejects_invalid_book_member_encoding_or_json(tmp_path, book_payload):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, books={"data/gen.json": book_payload})
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        _parse(path, payload)


@pytest.mark.parametrize(
    "member",
    [
        "data/repeated  space.json",
        "data/tab\tname.json",
        "data/" + unicodedata.normalize("NFD", "café") + ".json",
    ],
    ids=["repeated-space", "tab", "decomposed-unicode"],
)
def test_rejects_locator_unstable_book_member_paths(tmp_path, member):
    path = tmp_path / "bundle.zip"
    record = _index_record(file=member)
    payload = _write_bundle(
        path,
        index={"books": [record]},
        books={member: _book()},
    )
    with pytest.raises(ValueError, match="normalization-stable|unsafe archive member"):
        _parse(path, payload)


def test_rejects_locator_unstable_archive_path(tmp_path):
    path = tmp_path / "bundle  name.zip"
    payload = _write_bundle(path)
    with pytest.raises(ValueError, match="normalization-stable"):
        _parse(path, payload)


def test_accepts_intended_archive_filename_with_single_spaces(tmp_path):
    path = tmp_path / "Ethiopian Orthodox Bible (Non-KJV Edition).zip"
    payload = _write_bundle(path)

    rows = _parse(path, payload)

    assert rows[0].source_locator == (
        "Ethiopian Orthodox Bible (Non-KJV Edition).zip!/data/gen.json#1:1"
    )


@pytest.mark.parametrize(
    "chapters,message",
    [
        ({"c": 1, "v": [{"n": 1, "t": "Text"}]}, "JSON list"),
        (["chapter"], "chapter record"),
        ([{"c": True, "v": [{"n": 1, "t": "Text"}]}], "chapter number"),
        ([{"c": 0, "v": [{"n": 1, "t": "Text"}]}], "chapter number"),
        ([
            {"c": 1, "v": [{"n": 1, "t": "Text"}]},
            {"c": "1", "v": [{"n": 1, "t": "Again"}]},
        ], "duplicate chapter"),
        ([{"c": 2, "v": [{"n": 1, "t": "Text"}]}], "contiguous"),
    ],
)
def test_rejects_invalid_duplicate_or_gapped_chapters(tmp_path, chapters, message):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, books={"data/gen.json": chapters})
    with pytest.raises(ValueError, match=message):
        _parse(path, payload)


@pytest.mark.parametrize("chapter", ["01", "+1", " 1", "1 ", "1.0", 1.0, None])
def test_rejects_noncanonical_chapter_numbers(tmp_path, chapter):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, books={
        "data/gen.json": [{"c": chapter, "v": [{"n": 1, "t": "Text"}]}]
    })
    with pytest.raises(ValueError, match="chapter number"):
        _parse(path, payload)


def test_chapter_count_must_equal_index_and_be_contiguous(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, books={
        "data/gen.json": [
            {"c": 1, "v": [{"n": 1, "t": "One"}]},
            {"c": 2, "v": [{"n": 1, "t": "Two"}]},
        ]
    })
    with pytest.raises(ValueError, match="chapter count"):
        _parse(path, payload)


@pytest.mark.parametrize(
    "verses,message",
    [
        ([], "no verses"),
        ({}, "no verses"),
        (["verse"], "verse record"),
        ([{"n": True, "t": "Text"}], "verse number"),
        ([{"n": 0, "t": "Text"}], "verse number"),
        ([{"n": 1.0, "t": "Text"}], "verse number"),
        ([{"n": 1, "t": 3}], "text must be a string"),
        ([{"n": 1, "t": "One"}, {"n": 1, "t": "Again"}], "duplicate verse"),
        ([{"n": 2, "t": "Two"}], "contiguous"),
        ([{"n": 1, "t": ""}], "empty"),
        ([{"n": 1, "t": "<script>x</script>"}], "markup"),
    ],
)
def test_rejects_invalid_duplicate_gapped_or_unsafe_verses(tmp_path, verses, message):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, books={
        "data/gen.json": [{"c": 1, "v": verses}]
    })
    with pytest.raises(ValueError, match=message):
        _parse(path, payload)


def test_rejects_book_identity_resolution_mismatch(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path, index={"books": [_index_record(name="Exodus")]})
    with pytest.raises(ValueError, match="resolved to.*expected"):
        _parse(path, payload)


def test_validates_manifest_adapter_options_and_expected_work_keys(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path)
    manifest = _manifest(path.name, payload)
    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )

    wrong_adapter = manifest.model_copy(update={"adapter": "weahadu_bundle"})
    with pytest.raises(ValueError, match="adapter options"):
        parse_composite_english_bundle(wrong_adapter, tmp_path)

    wrong_options = manifest.model_construct(
        **{
            **manifest.__dict__,
            "adapter_options": {"book_map": {"GEN": "genesis"}},
        }
    )
    with pytest.raises(ValueError, match="adapter options"):
        parse_composite_english_bundle(wrong_options, tmp_path)

    wrong_expected = manifest.model_copy(update={"expected_works": {"exodus": {}}})
    with pytest.raises(ValueError, match="expected_works"):
        parse_composite_english_bundle(wrong_expected, tmp_path)


def test_revalidates_forged_duplicate_book_map_targets(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path)
    manifest = _manifest(path.name, payload)
    options_type = type(manifest.adapter_options)
    forged_options = options_type.model_construct(
        book_map={"GEN": "genesis", "GEN2": "genesis"},
        work_sources=manifest.adapter_options.work_sources,
        supplemental_works=[],
    )
    manifest = manifest.model_copy(update={"adapter_options": forged_options})

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )
    with pytest.raises(ValueError, match="adapter options|multiple source books"):
        parse_composite_english_bundle(manifest, tmp_path)


def test_revalidates_forged_missing_verse_options(tmp_path):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path)
    manifest = _manifest(path.name, payload)
    original = manifest.adapter_options
    forged_options = type(original).model_construct(
        book_map=original.book_map,
        work_sources=original.work_sources,
        supplemental_works=[],
        known_missing_verses={"genesis": {"1": [True]}},
    )
    manifest = manifest.model_copy(update={"adapter_options": forged_options})

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )
    with pytest.raises(ValueError, match="invalid composite adapter options"):
        parse_composite_english_bundle(manifest, tmp_path)


@pytest.mark.parametrize("forgery", ["empty", "nested", "scope", "supplemental"])
def test_revalidates_forged_nested_source_and_scope_options(tmp_path, forgery):
    path = tmp_path / "bundle.zip"
    payload = _write_bundle(path)
    manifest = _manifest(path.name, payload)
    original = manifest.adapter_options
    options_type = type(original)
    book_map = original.book_map
    work_sources = original.work_sources
    supplemental_works = []

    if forgery == "empty":
        book_map = {}
        work_sources = {}
    elif forgery == "nested":
        work_sources = {"genesis": {"source_key": []}}
    elif forgery == "scope":
        work_sources = {
            "genesis": original.work_sources["genesis"].model_copy(
                update={"canon_scope": "supplemental"}
            )
        }
    else:
        supplemental_works = ["exodus"]

    forged_options = options_type.model_construct(
        book_map=book_map,
        work_sources=work_sources,
        supplemental_works=supplemental_works,
    )
    manifest = manifest.model_copy(update={"adapter_options": forged_options})

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )
    with pytest.raises(ValueError, match="adapter options"):
        parse_composite_english_bundle(manifest, tmp_path)


def test_reviewed_corrected_ethiopian_composite_bundle_is_reproducible_and_truthful(
    tmp_path,
):
    """Exercise the checked-in generators and the production adapter end to end."""
    import importlib.util
    import shutil

    from app.library.ingest.adapters.composite_english_bundle import (
        parse_composite_english_bundle,
    )

    source_dir = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "scripture"
        / "eotc-composite-en"
    )

    def load_script(name):
        path = source_dir / name
        spec = importlib.util.spec_from_file_location(f"eotc_{name[:-3]}", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    build_bundle = load_script("build_bundle.py")
    build_manifest = load_script("build_manifest.py")
    original_checksums = {
        name: sha256((source_dir / name).read_bytes()).hexdigest()
        for name in build_bundle.INPUT_CHECKSUMS
    }

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    for output in (first, second):
        build_bundle.build(source_dir, output)
        build_manifest.build(source_dir, output)

    assert (first / "corrected-bundle.zip").read_bytes() == (
        second / "corrected-bundle.zip"
    ).read_bytes()
    assert (first / "data-quality-report.json").read_bytes() == (
        second / "data-quality-report.json"
    ).read_bytes()
    assert (first / "manifest.json").read_bytes() == (
        second / "manifest.json"
    ).read_bytes()
    assert original_checksums == {
        name: sha256((source_dir / name).read_bytes()).hexdigest()
        for name in build_bundle.INPUT_CHECKSUMS
    }

    report = json.loads((first / "data-quality-report.json").read_text())
    assert report["raw_archive"] == {
        "verse_records": 44_114,
        "unique_verse_positions": 38_845,
        "exact_duplicate_excess_records": 5_252,
        "conflicting_duplicate_excess_records": 17,
        "chapters": 1_520,
    }
    assert report["scope"] == {
        "works": 83,
        "chapters": 1_520,
        "ethio81_works": 82,
        "supplemental_works": 1,
    }
    assert report["known_missing_verses"] == {
        "2-meqabyan": {"16": [9], "21": [9]},
        "matthew": {"26": [30, 45]},
        "mark": {"4": [10], "8": [19], "9": [31], "11": [19]},
        "luke": {"18": [35]},
        "acts": {"19": [41], "20": [17]},
        "2-corinthians": {"13": [14]},
        "sirach": {
            "1": [5, 7, 21], "3": [19], "10": [21], "11": [15, 16],
            "13": [14], "16": [15, 16], "17": [5, 9, 16, 18, 21],
            "18": [3], "19": [18, 19, 21], "20": [3, 32],
            "22": [9, 10], "23": [28], "24": [18, 24], "25": [12],
            "26": [19, 20, 21, 22, 23, 24, 25, 26, 27],
        },
    }
    assert report["corrected_verse_count"] == 38_938
    assert sum(
        len(verses)
        for chapters in report["known_missing_verses"].values()
        for verses in chapters.values()
    ) == 48
    assert report["web_reserved_blank_labels"] == {
        "sirach": {
            "1": [5, 7, 21], "3": [19], "10": [21], "11": [15],
            "13": [14], "16": [15], "17": [5, 9, 16, 18, 21],
            "18": [3], "19": [18, 21], "20": [3, 32], "22": [9],
            "23": [28], "24": [18, 24], "25": [12], "26": [19],
        }
    }
    assert report["web_absent_labels_without_rows"] == {
        "sirach": {
            "11": [16], "16": [16], "19": [19], "22": [10],
            "26": [20, 21, 22, 23, 24, 25, 26, 27],
        }
    }
    assert report["duplicate_output_positions"] == 0
    assert report["undeclared_output_gaps"] == []
    assert report["enoch_source_chapters_without_verse_numbers"] == [3, 4, 35, 44]
    assert report["enoch_recension_handling"] == {
        "displayed_reading": "R. H. Charles Ethiopic (E) main reading",
        "excluded_alternates": ["G^g", "G^s", "G^{s1}", "G^{s2}"],
    }

    manifest = SourceManifest.model_validate_json(
        (first / "manifest.json").read_text()
    )
    shutil.copy2(first / "corrected-bundle.zip", tmp_path / "corrected-bundle.zip")
    rows = parse_composite_english_bundle(manifest, tmp_path)
    assert len(rows) == report["corrected_verse_count"]
    assert len({row.work_id for row in rows}) == 83
    assert len({(row.work_id, row.chapter) for row in rows}) == 1_520
    assert len({(row.work_id, row.chapter, row.verse) for row in rows}) == len(rows)
    assert any(
        row.work_id == "1-enoch" and row.chapter == 80 and row.verse == 1
        and row.text
        for row in rows
    )
    assert any(row.work_id == "tobit" and row.text for row in rows)
    sirach_1 = {
        row.verse: row.text
        for row in rows if row.work_id == "sirach" and row.chapter == 1
    }
    assert 5 not in sirach_1
    assert 7 not in sirach_1
    assert 21 not in sirach_1
    assert sirach_1[6] == (
        "To whom has the root of wisdom been revealed? "
        "Who has known her shrewd counsels?"
    )
    for chapter in (3, 4, 35, 44):
        chapter_rows = [
            row for row in rows if row.work_id == "1-enoch" and row.chapter == chapter
        ]
        assert [(row.verse, bool(row.text)) for row in chapter_rows] == [(1, True)]
    enoch = {
        (row.chapter, row.verse): row.text
        for row in rows if row.work_id == "1-enoch"
    }
    assert all("G^g" not in text and text != "E" for text in enoch.values())
    assert "there was in it †four† =hollow= places" in enoch[22, 2]
    assert "there were †four† hollow places" not in enoch[22, 2]
    assert "G^g" not in enoch[22, 2]
    assert "Then I asked Raphael" in enoch[22, 6]
    assert enoch[22, 6].count("Then I asked Raphael") == 1
    assert "spectacle of righteous judgement" in enoch[27, 3]
    assert "true judgement" not in enoch[27, 3]
    assert "towards the north over the mountains" in enoch[32, 1]
    assert "To the north-east" not in enoch[32, 1]
    assert "many large trees growing there" in enoch[32, 3]
    assert "from afar off trees more numerous" not in enoch[32, 3]
    assert "that ram begat many sheep" in enoch[89, 48]
    assert "that ram begat many sheep" not in enoch[89, 49]

    options = manifest.adapter_options
    assert len(options.work_sources) == 83
    assert sum(s.canon_scope == "ethio81" for s in options.work_sources.values()) == 82
    assert sum(s.canon_scope == "supplemental" for s in options.work_sources.values()) == 1
    assert options.supplemental_works == ["prayer-of-manasseh"]
    assert options.known_missing_verses == {
        "2-meqabyan": {"16": [9], "21": [9]},
        "matthew": {"26": [30, 45]},
        "mark": {"4": [10], "8": [19], "9": [31], "11": [19]},
        "luke": {"18": [35]},
        "acts": {"19": [41], "20": [17]},
        "2-corinthians": {"13": [14]},
        "sirach": {
            "1": [5, 7, 21], "3": [19], "10": [21], "11": [15, 16],
            "13": [14], "16": [15, 16], "17": [5, 9, 16, 18, 21],
            "18": [3], "19": [18, 19, 21], "20": [3, 32],
            "22": [9, 10], "23": [28], "24": [18, 24], "25": [12],
            "26": [19, 20, 21, 22, 23, 24, 25, 26, 27],
        },
    }
    fallback = {
        work_id for work_id, source in options.work_sources.items() if source.fallback
    }
    assert fallback == {
        "baruch", "letter-of-jeremiah", "prayer-of-azariah", "susanna",
        "bel-and-the-dragon", "prayer-of-manasseh",
    }
    assert all(
        "KJV" in options.work_sources[work_id].source_label for work_id in fallback
    )
    assert str(options.work_sources["tobit"].provenance_url) == (
        "https://ebible.org/details.php?id=eng-webbe"
    )
    assert str(options.work_sources["1-enoch"].provenance_url) == (
        "https://www.gutenberg.org/ebooks/77935"
    )


def test_corrected_bundle_builder_canonicalizes_lexicographic_chapters(tmp_path):
    import importlib.util

    script = (
        Path(__file__).resolve().parents[3]
        / "data/scripture/eotc-composite-en/build_bundle.py"
    )
    spec = importlib.util.spec_from_file_location("eotc_build_bundle", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    chapters = [
        {"c": "1", "v": [{"n": 1, "t": "One"}]},
        {"c": "10", "v": [{"n": 1, "t": "Ten"}]},
        *(
            {"c": str(number), "v": [{"n": 1, "t": str(number)}]}
            for number in range(2, 10)
        ),
    ]

    corrected = module._canonical_untouched("GEN", chapters)
    assert [chapter["c"] for chapter in corrected] == list(range(1, 11))
    assert corrected[-1]["v"][0]["t"] == "Ten"

    with pytest.raises(ValueError, match="duplicate chapter"):
        module._canonical_untouched("GEN", chapters + [chapters[0]])
    with pytest.raises(ValueError, match="contiguous"):
        module._canonical_untouched("GEN", chapters[:-1])
    with pytest.raises(ValueError, match="invalid chapter"):
        module._canonical_untouched("GEN", [{"c": "01", "v": []}])


def test_corrected_bundle_builder_cleans_only_murdock_presentation_artifacts():
    import importlib.util

    script = (
        Path(__file__).resolve().parents[3]
        / "data/scripture/eotc-composite-en/build_bundle.py"
    )
    spec = importlib.util.spec_from_file_location("eotc_build_bundle_cleanup", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    corrected = module._canonical_untouched(
        "MAT",
        [{"c": "1", "v": [
            {"n": 1, "t": "Before\x0fafter <FI>emphasis<Fi>."},
            {"n": 2, "t": "Verse.<RF>Translator note.<Rf>"},
            {"n": 3, "t": ""},
        ]}],
        source_group="peshitta",
    )

    assert corrected == [{"c": 1, "v": [
        {"n": 1, "t": "Before after emphasis."},
        {"n": 2, "t": "Verse."},
    ]}]


def test_corrected_manifest_rejects_bundle_appended_after_quality_report(tmp_path):
    import importlib.util

    source_dir = (
        Path(__file__).resolve().parents[3]
        / "data/scripture/eotc-composite-en"
    )

    def load(name):
        spec = importlib.util.spec_from_file_location(name, source_dir / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    bundle = load("build_bundle")
    manifest = load("build_manifest")
    bundle.build(source_dir, tmp_path)
    manifest.build(source_dir, tmp_path)
    with (tmp_path / "corrected-bundle.zip").open("ab") as stream:
        stream.write(b"tampered-after-reviewed-zip")

    with pytest.raises(ValueError, match="corrected bundle checksum mismatch"):
        manifest.build(source_dir, tmp_path)
