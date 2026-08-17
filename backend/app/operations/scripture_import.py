"""One-purpose, fail-closed import of legacy scripture rows.

This operation never creates schema and never writes any table other than
``biblical_texts``. The target must be empty so a production import is an
atomic bootstrap rather than an accidental overwrite.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    select,
    text,
)


TABLE_NAME = "biblical_texts"
COPY_COLUMNS = ("book", "chapter", "verse", "text", "translation")
REQUIRED_COLUMNS = {"id", *COPY_COLUMNS}


class ScriptureImportPolicyError(RuntimeError):
    """Raised before any write when the guarded import policy is not met."""


@dataclass(frozen=True, slots=True)
class ScriptureImportResult:
    source_count: int
    imported_count: int
    translation_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class CatalogExpectation:
    total_count: int
    translation_counts: dict[str, int]


PRODUCTION_CATALOG = CatalogExpectation(
    total_count=144_413,
    translation_counts={
        "1EN_CH": 1_060,
        "ASV": 3_535,
        "BBE": 4_287,
        "DARBY": 4_350,
        "DRA": 4_264,
        "EOTC-COMPOSITE-EN": 38_938,
        "ERV": 30_458,
        "ETH81": 566,
        "GEEZ1980-RESEARCH": 1_533,
        "JOSEPHUS": 1,
        "JUB_CH": 1_758,
        "KJV": 36_899,
        "MEQ1": 240,
        "MEQ2": 421,
        "MEQ3": 208,
        "NLT": 7_496,
        "OSHB": 1,
        "TARG_ON": 1,
        "WEB": 3_504,
        "WEBBE": 4_014,
        "YLT": 879,
    },
)


def _require_schema(engine, *, role: str) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(TABLE_NAME):
        raise ScriptureImportPolicyError(f"{role} biblical_texts table is missing")
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    missing = sorted(REQUIRED_COLUMNS - columns)
    if missing:
        raise ScriptureImportPolicyError(
            f"{role} biblical_texts table is missing columns: {', '.join(missing)}"
        )


def _copy_table() -> Table:
    return Table(
        TABLE_NAME,
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("book", String(100), nullable=False),
        Column("chapter", Integer, nullable=False),
        Column("verse", Integer, nullable=False),
        Column("text", Text, nullable=False),
        Column("translation", String(100)),
    )


def _source_catalog(connection) -> CatalogExpectation:
    total_count = connection.scalar(text("SELECT COUNT(*) FROM biblical_texts"))
    counts = {
        str(row.translation or ""): row.row_count
        for row in connection.execute(text("""
            SELECT translation, COUNT(*) AS row_count
            FROM biblical_texts
            GROUP BY translation
        """))
    }
    return CatalogExpectation(
        total_count=total_count,
        translation_counts=dict(sorted(counts.items())),
    )


def _require_expected_catalog(
    actual: CatalogExpectation,
    expected: CatalogExpectation,
) -> None:
    if actual != expected:
        raise ScriptureImportPolicyError(
            "source catalog manifest mismatch: "
            f"expected {expected.total_count} rows across "
            f"{len(expected.translation_counts)} translations; "
            f"found {actual.total_count} rows across "
            f"{len(actual.translation_counts)} translations"
        )


def _lock_target(connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text(
            "LOCK TABLE biblical_texts IN SHARE ROW EXCLUSIVE MODE"
        ))


def import_scripture_rows(
    *,
    source_url: str,
    target_url: str,
    confirm: bool = False,
    batch_size: int = 1_000,
    expectation: CatalogExpectation = PRODUCTION_CATALOG,
) -> ScriptureImportResult:
    """Copy every scripture row into an empty target in one transaction."""
    if not confirm:
        raise ScriptureImportPolicyError("explicit import confirmation is required")
    if batch_size < 1:
        raise ScriptureImportPolicyError("batch_size must be positive")

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)
    try:
        _require_schema(source_engine, role="source")
        _require_schema(target_engine, role="target")
        target_table = _copy_table()
        translation_counts: Counter[str] = Counter()
        imported_count = 0

        with source_engine.connect() as source_connection:
            source_catalog = _source_catalog(source_connection)
            _require_expected_catalog(source_catalog, expectation)
            source_count = source_catalog.total_count
            with target_engine.begin() as target_connection:
                _lock_target(target_connection)
                target_count = target_connection.scalar(
                    text("SELECT COUNT(*) FROM biblical_texts")
                )
                if target_count:
                    raise ScriptureImportPolicyError(
                        "target biblical_texts table is not empty"
                    )

                result = source_connection.execution_options(stream_results=True).execute(
                    text("""
                        SELECT book, chapter, verse, text, translation
                        FROM biblical_texts
                        ORDER BY id
                    """)
                ).mappings()
                while True:
                    rows = result.fetchmany(batch_size)
                    if not rows:
                        break
                    payload = [dict(row) for row in rows]
                    target_connection.execute(target_table.insert(), payload)
                    imported_count += len(payload)
                    translation_counts.update(
                        str(row["translation"] or "") for row in payload
                    )

                verified_count = target_connection.scalar(
                    select(text("count(*)")).select_from(target_table)
                )
                if imported_count != source_count or verified_count != source_count:
                    raise RuntimeError(
                        "scripture import count verification failed before commit"
                    )

        return ScriptureImportResult(
            source_count=source_count,
            imported_count=imported_count,
            translation_counts=dict(sorted(translation_counts.items())),
        )
    finally:
        source_engine.dispose()
        target_engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target-url-stdin", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.target_url_stdin:
        raise ScriptureImportPolicyError(
            "target URL must be supplied through standard input"
        )
    target_url = sys.stdin.readline().strip()
    if not target_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise ScriptureImportPolicyError("target must be PostgreSQL")
    source_path = args.source.expanduser().resolve(strict=True)
    result = import_scripture_rows(
        source_url=f"sqlite:///{source_path}",
        target_url=target_url,
        confirm=args.confirm,
        batch_size=args.batch_size,
    )
    translations = ", ".join(
        f"{code or '(unlabeled)'}={count}"
        for code, count in result.translation_counts.items()
    )
    print(
        f"Imported {result.imported_count} verified scripture rows "
        f"from {len(result.translation_counts)} translations."
    )
    print(translations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
