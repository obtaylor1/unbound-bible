from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.orm import Session

from app.library.models import EditionCoverage, EditionWorkSource, TextEdition
from app.library.seed import seed_ethiopian_canon
from app.operations.library_catalog_import import (
    CatalogExpectation,
    LibraryCatalogImportPolicyError,
    _lock_target,
    _source_manifest,
    import_library_catalog,
)


TABLES = (
    "library_works",
    "library_work_aliases",
    "canon_entries",
    "canon_entry_works",
    "text_editions",
    "edition_coverage",
    "edition_work_sources",
)
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _database_url(path: Path) -> str:
    return f"sqlite:///{path}"


def _create_database(path: Path, *, populated: bool, sentinel: bool = False) -> str:
    url = _database_url(path)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE library_works (id TEXT PRIMARY KEY, title TEXT NOT NULL)"))
        connection.execute(text("CREATE TABLE library_work_aliases (id INTEGER PRIMARY KEY, alias TEXT, work_id TEXT)"))
        connection.execute(text("CREATE TABLE canon_entries (id INTEGER PRIMARY KEY, canon_code TEXT, testament TEXT, canonical_order INTEGER, title TEXT)"))
        connection.execute(text("CREATE TABLE canon_entry_works (canon_entry_id INTEGER, work_id TEXT, PRIMARY KEY (canon_entry_id, work_id))"))
        connection.execute(text("CREATE TABLE text_editions (edition_code TEXT PRIMARY KEY, name TEXT)"))
        connection.execute(text("CREATE TABLE edition_coverage (id INTEGER PRIMARY KEY, edition_code TEXT, work_id TEXT, status TEXT)"))
        connection.execute(text("CREATE TABLE edition_work_sources (id INTEGER PRIMARY KEY, edition_code TEXT, work_id TEXT, source_key TEXT)"))
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)"))
        connection.execute(text("INSERT INTO users VALUES (1, 'reader@example.com')"))
        if populated:
            connection.execute(text("INSERT INTO library_works VALUES ('genesis', 'Genesis')"))
            connection.execute(text("INSERT INTO library_work_aliases VALUES (1, 'Genesis', 'genesis')"))
            connection.execute(text("INSERT INTO canon_entries VALUES (1, 'ETHIO81', 'OT', 1, 'Genesis')"))
            connection.execute(text("INSERT INTO canon_entry_works VALUES (1, 'genesis')"))
            connection.execute(text("INSERT INTO text_editions VALUES ('EOTC-COMPOSITE-EN', 'Ethiopian English')"))
            connection.execute(text("INSERT INTO edition_coverage VALUES (1, 'EOTC-COMPOSITE-EN', 'genesis', 'verified_english')"))
            connection.execute(text("INSERT INTO edition_work_sources VALUES (1, 'EOTC-COMPOSITE-EN', 'genesis', 'source')"))
        elif sentinel:
            connection.execute(text(
                "INSERT INTO library_works VALUES "
                "('prayer-of-manasseh', 'Prayer of Manasseh')"
            ))
    engine.dispose()
    return url


def _expectation(source_url: str) -> CatalogExpectation:
    engine = create_engine(source_url)
    metadata = MetaData()
    tables = {name: Table(name, metadata, autoload_with=engine) for name in TABLES}
    with engine.connect() as connection:
        expectation = _source_manifest(connection, tables)
    engine.dispose()
    return expectation


def test_confirmed_import_copies_catalog_without_touching_other_tables(tmp_path):
    source_url = _create_database(tmp_path / "source.db", populated=True)
    target_url = _create_database(tmp_path / "target.db", populated=False)
    expectation = _expectation(source_url)

    result = import_library_catalog(
        source_url=source_url,
        target_url=target_url,
        confirm=True,
        expectation=expectation,
    )

    assert result.table_counts == expectation.table_counts
    engine = create_engine(target_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT title FROM library_works")) == "Genesis"
        assert connection.scalar(text("SELECT email FROM users WHERE id = 1")) == "reader@example.com"
    engine.dispose()


def test_import_rejects_wrong_manifest_before_any_target_write(tmp_path):
    source_url = _create_database(tmp_path / "source.db", populated=True)
    target_url = _create_database(tmp_path / "target.db", populated=False)
    expected = _expectation(source_url)
    wrong = CatalogExpectation(
        table_counts={**expected.table_counts, "edition_coverage": 2},
        edition_codes=expected.edition_codes,
        coverage_counts={"EOTC-COMPOSITE-EN": 2},
        source_counts=expected.source_counts,
        content_digests=expected.content_digests,
    )

    with pytest.raises(LibraryCatalogImportPolicyError, match="manifest mismatch"):
        import_library_catalog(
            source_url=source_url,
            target_url=target_url,
            confirm=True,
            expectation=wrong,
        )

    engine = create_engine(target_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM library_works")) == 0
    engine.dispose()


def test_import_rejects_nonempty_target(tmp_path):
    source_url = _create_database(tmp_path / "source.db", populated=True)
    target_url = _create_database(tmp_path / "target.db", populated=True)

    with pytest.raises(LibraryCatalogImportPolicyError, match="not empty"):
        import_library_catalog(
            source_url=source_url,
            target_url=target_url,
            confirm=True,
            expectation=_expectation(source_url),
        )


def test_import_accepts_only_the_known_migration_sentinel(tmp_path):
    source_url = _create_database(tmp_path / "source.db", populated=True)
    source_engine = create_engine(source_url)
    with source_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO library_works VALUES "
            "('prayer-of-manasseh', 'Prayer of Manasseh')"
        ))
    source_engine.dispose()
    target_url = _create_database(
        tmp_path / "target.db", populated=False, sentinel=True
    )

    result = import_library_catalog(
        source_url=source_url,
        target_url=target_url,
        confirm=True,
        expectation=_expectation(source_url),
    )

    assert result.table_counts["library_works"] == 2


def test_import_accepts_a_fresh_alembic_head_target(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    source_url = _database_url(tmp_path / "migrated-source.db")
    target_url = _database_url(tmp_path / "migrated-target.db")
    command.upgrade(_alembic_config(source_url), "head")
    command.upgrade(_alembic_config(target_url), "head")

    source_engine = create_engine(source_url)
    with Session(source_engine) as session:
        seed_ethiopian_canon(session)
        session.add(TextEdition(
            edition_code="EOTC-COMPOSITE-EN",
            name="Ethiopian English",
            reading_language="English",
            source_language="Mixed",
            script="Latin",
            relationship="general_reading",
            expected_coverage={},
            verification_status="provisional",
        ))
        session.add(EditionCoverage(
            edition_code="EOTC-COMPOSITE-EN",
            work_id="genesis",
            status="verified_english",
        ))
        session.add(EditionWorkSource(
            edition_code="EOTC-COMPOSITE-EN",
            work_id="genesis",
            source_key="fixture",
            source_label="Fixture",
            source_language="English",
            source_tradition="Fixture",
            license_spdx="CC0-1.0",
            attribution="Fixture",
            verification_status="provisional",
            canon_scope="ethio81",
        ))
        session.commit()
    source_engine.dispose()

    result = import_library_catalog(
        source_url=source_url,
        target_url=target_url,
        confirm=True,
        expectation=_expectation(source_url),
    )

    assert result.table_counts["library_works"] == 98
    target_engine = create_engine(target_url)
    with target_engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT COUNT(*) FROM library_works "
            "WHERE id = 'prayer-of-manasseh'"
        )) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM canon_entries")) == 81
    target_engine.dispose()


def test_import_rejects_content_change_without_count_change(tmp_path):
    source_url = _create_database(tmp_path / "source.db", populated=True)
    target_url = _create_database(tmp_path / "target.db", populated=False)
    expectation = _expectation(source_url)
    source_engine = create_engine(source_url)
    with source_engine.begin() as connection:
        connection.execute(text(
            "UPDATE library_works SET title = 'Altered title' WHERE id = 'genesis'"
        ))
    source_engine.dispose()

    with pytest.raises(LibraryCatalogImportPolicyError, match="manifest mismatch"):
        import_library_catalog(
            source_url=source_url,
            target_url=target_url,
            confirm=True,
            expectation=expectation,
        )

    engine = create_engine(target_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM library_works")) == 0
    engine.dispose()


def test_postgresql_import_locks_all_catalog_tables():
    class _Dialect:
        name = "postgresql"

    class _Connection:
        dialect = _Dialect()

        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(" ".join(str(statement).split()))

    connection = _Connection()
    _lock_target(connection)

    assert connection.statements == [
        "LOCK TABLE library_works, library_work_aliases, canon_entries, "
        "canon_entry_works, text_editions, edition_coverage, "
        "edition_work_sources IN SHARE ROW EXCLUSIVE MODE"
    ]
