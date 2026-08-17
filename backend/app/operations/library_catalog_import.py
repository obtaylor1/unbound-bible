"""Fail-closed import of the normalized scripture library catalog.

This operation complements the legacy scripture-row bootstrap. It copies only
the seven normalized catalog and edition metadata tables, requires an exact
source manifest, and refuses to overwrite an initialized target.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text


TABLES = (
    "library_works",
    "library_work_aliases",
    "canon_entries",
    "canon_entry_works",
    "text_editions",
    "edition_coverage",
    "edition_work_sources",
)
SEQUENCED_TABLES = (
    "library_work_aliases",
    "canon_entries",
    "edition_coverage",
    "edition_work_sources",
)


class LibraryCatalogImportPolicyError(RuntimeError):
    """Raised before commit when the catalog bootstrap policy is not met."""


@dataclass(frozen=True, slots=True)
class CatalogExpectation:
    table_counts: dict[str, int]
    edition_codes: tuple[str, ...]
    coverage_counts: dict[str, int]
    source_counts: dict[str, int]
    content_digests: dict[str, str]


@dataclass(frozen=True, slots=True)
class LibraryCatalogImportResult:
    table_counts: dict[str, int]


PRODUCTION_CATALOG = CatalogExpectation(
    table_counts={
        "library_works": 98,
        "library_work_aliases": 152,
        "canon_entries": 81,
        "canon_entry_works": 95,
        "text_editions": 2,
        "edition_coverage": 84,
        "edition_work_sources": 83,
    },
    edition_codes=("EOTC-COMPOSITE-EN", "GEEZ1980-RESEARCH"),
    coverage_counts={"EOTC-COMPOSITE-EN": 83, "GEEZ1980-RESEARCH": 1},
    source_counts={"EOTC-COMPOSITE-EN": 83},
    content_digests={
        "library_works": "02ad0a0a9ad986f2a0447b39f57e2a5fa888df7f2c9fa5c9739f476705ef8b18",
        "library_work_aliases": "75af4096aa6e0d39452fbc07436c9380dab7296541a2403d07168456d8c00af4",
        "canon_entries": "b12e0a507e8a346a3da58c6265c726f790915f9ebffe57ce363f07be7ff70aff",
        "canon_entry_works": "ab4a91607f1ce8e7b2ff5659a3df0b89c3cee20e5480a766477f75cee7f38a3a",
        "text_editions": "26c243bd519e8b2db01e6ae60af562bd78f30456e7da5e38fe8a8625f6c48c7b",
        "edition_coverage": "33a890940228071935fd4dfd8440890e862565bf28515e5e85afe9c0b295f269",
        "edition_work_sources": "53f226f6b38dd9aa6512b29aa8fa14dd8c373ba2cf62d4dbeb7ad96b98e55b49",
    },
)


def _require_schema(engine, *, role: str) -> None:
    available = set(inspect(engine).get_table_names())
    missing = sorted(set(TABLES) - available)
    if missing:
        raise LibraryCatalogImportPolicyError(
            f"{role} catalog schema is missing tables: {', '.join(missing)}"
        )


def _grouped_counts(connection, table_name: str) -> dict[str, int]:
    return {
        str(row.edition_code): int(row.row_count)
        for row in connection.execute(text(
            f"SELECT edition_code, COUNT(*) AS row_count "
            f"FROM {table_name} GROUP BY edition_code"
        ))
    }


def _table_digest(connection, table: Table) -> str:
    order_columns = tuple(table.primary_key.columns) or tuple(table.columns)
    rows = connection.execute(select(table).order_by(*order_columns)).mappings()
    digest = hashlib.sha256()
    for row in rows:
        encoded = json.dumps(
            dict(row),
            default=str,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")
    return digest.hexdigest()


def _source_manifest(connection, tables: dict[str, Table]) -> CatalogExpectation:
    return CatalogExpectation(
        table_counts={
            table_name: int(connection.scalar(text(f"SELECT COUNT(*) FROM {table_name}")))
            for table_name in TABLES
        },
        edition_codes=tuple(sorted(
            str(code)
            for code in connection.scalars(text(
                "SELECT edition_code FROM text_editions ORDER BY edition_code"
            ))
        )),
        coverage_counts=dict(sorted(_grouped_counts(connection, "edition_coverage").items())),
        source_counts=dict(sorted(_grouped_counts(connection, "edition_work_sources").items())),
        content_digests={
            name: _table_digest(connection, tables[name])
            for name in TABLES
        },
    )


def _require_expected_catalog(
    actual: CatalogExpectation,
    expected: CatalogExpectation,
) -> None:
    if actual != expected:
        raise LibraryCatalogImportPolicyError(
            "source catalog manifest mismatch: normalized library metadata "
            "does not match the reviewed production catalog"
        )


def _lock_target(connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text(
            "LOCK TABLE " + ", ".join(TABLES) + " IN SHARE ROW EXCLUSIVE MODE"
        ))


def _target_sentinel_state(connection) -> bool:
    counts = {
        name: int(connection.scalar(text(f"SELECT COUNT(*) FROM {name}")))
        for name in TABLES
    }
    if not any(counts.values()):
        return False
    expected_counts = {name: 0 for name in TABLES}
    expected_counts["library_works"] = 1
    if counts != expected_counts:
        nonempty = [name for name, count in counts.items() if count]
        raise LibraryCatalogImportPolicyError(
            "target catalog is not empty: " + ", ".join(nonempty)
        )
    row = connection.execute(text(
        "SELECT id, title FROM library_works"
    )).mappings().one()
    if dict(row) != {
        "id": "prayer-of-manasseh",
        "title": "Prayer of Manasseh",
    }:
        raise LibraryCatalogImportPolicyError(
            "target catalog contains an unrecognized migration sentinel"
        )
    return True


def _reset_sequences(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    for table_name in SEQUENCED_TABLES:
        connection.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
            f"(SELECT MAX(id) FROM {table_name}), true)"
        ))


def import_library_catalog(
    *,
    source_url: str,
    target_url: str,
    confirm: bool = False,
    expectation: CatalogExpectation = PRODUCTION_CATALOG,
) -> LibraryCatalogImportResult:
    """Copy the reviewed normalized catalog into an empty target atomically."""
    if not confirm:
        raise LibraryCatalogImportPolicyError("explicit import confirmation is required")

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)
    try:
        _require_schema(source_engine, role="source")
        _require_schema(target_engine, role="target")
        source_metadata = MetaData()
        target_metadata = MetaData()
        source_tables = {
            name: Table(name, source_metadata, autoload_with=source_engine)
            for name in TABLES
        }
        target_tables = {
            name: Table(name, target_metadata, autoload_with=target_engine)
            for name in TABLES
        }
        for name in TABLES:
            source_columns = tuple(source_tables[name].columns.keys())
            target_columns = tuple(target_tables[name].columns.keys())
            if source_columns != target_columns:
                raise LibraryCatalogImportPolicyError(
                    f"source and target schemas differ for {name}"
                )

        with source_engine.connect() as source_connection:
            source_manifest = _source_manifest(source_connection, source_tables)
            _require_expected_catalog(source_manifest, expectation)
            with target_engine.begin() as target_connection:
                _lock_target(target_connection)
                sentinel_present = _target_sentinel_state(target_connection)

                for name in TABLES:
                    rows = source_connection.execute(select(source_tables[name])).mappings().all()
                    if name == "library_works" and sentinel_present:
                        rows = [
                            row for row in rows
                            if row["id"] != "prayer-of-manasseh"
                        ]
                    if rows:
                        target_connection.execute(
                            target_tables[name].insert(),
                            [dict(row) for row in rows],
                        )

                verified = {
                    name: int(target_connection.scalar(text(f"SELECT COUNT(*) FROM {name}")))
                    for name in TABLES
                }
                if verified != expectation.table_counts:
                    raise RuntimeError("catalog import count verification failed before commit")
                _reset_sequences(target_connection)

        return LibraryCatalogImportResult(table_counts=expectation.table_counts.copy())
    finally:
        source_engine.dispose()
        target_engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target-url-stdin", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.target_url_stdin:
        raise LibraryCatalogImportPolicyError(
            "target URL must be supplied through standard input"
        )
    target_url = sys.stdin.readline().strip()
    if not target_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise LibraryCatalogImportPolicyError("target must be PostgreSQL")
    source_path = args.source.expanduser().resolve(strict=True)
    result = import_library_catalog(
        source_url=f"sqlite:///{source_path}",
        target_url=target_url,
        confirm=args.confirm,
    )
    print(
        "Imported verified library catalog: "
        + ", ".join(f"{name}={count}" for name, count in result.table_counts.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
