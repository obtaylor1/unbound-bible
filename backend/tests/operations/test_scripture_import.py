from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.operations.scripture_import import (
    CatalogExpectation,
    ScriptureImportPolicyError,
    _lock_target,
    import_scripture_rows,
)


def _database_url(path: Path) -> str:
    return f"sqlite:///{path}"


def _create_source(path: Path) -> str:
    url = _database_url(path)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation TEXT
            )
        """))
        connection.execute(text("""
            INSERT INTO biblical_texts (book, chapter, verse, text, translation)
            VALUES
              ('Genesis', 1, 1, 'In the beginning', 'KJV'),
              ('Genesis', 1, 2, 'The earth was without form', 'KJV'),
              ('Genesis', 1, 1, 'In the beginning, God created', 'EOTC-COMPOSITE-EN')
        """))
    engine.dispose()
    return url


def _create_target(path: Path) -> str:
    url = _database_url(path)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE biblical_texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                translation TEXT
            )
        """))
        connection.execute(text("""
            CREATE UNIQUE INDEX uq_biblical_texts_translation_book_chapter_verse
            ON biblical_texts (coalesce(translation, ''), book, chapter, verse)
        """))
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)"))
        connection.execute(text("INSERT INTO users VALUES (1, 'reader@example.com')"))
    engine.dispose()
    return url


def test_confirmed_import_copies_scriptures_without_touching_other_tables(tmp_path):
    source_url = _create_source(tmp_path / "source.db")
    target_url = _create_target(tmp_path / "target.db")

    result = import_scripture_rows(
        source_url=source_url,
        target_url=target_url,
        confirm=True,
        batch_size=2,
        expectation=CatalogExpectation(
            total_count=3,
            translation_counts={"EOTC-COMPOSITE-EN": 1, "KJV": 2},
        ),
    )

    assert result.source_count == 3
    assert result.imported_count == 3
    assert result.translation_counts == {"EOTC-COMPOSITE-EN": 1, "KJV": 2}

    engine = create_engine(target_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM biblical_texts")) == 3
        assert connection.scalar(text("SELECT email FROM users WHERE id = 1")) == (
            "reader@example.com"
        )
    engine.dispose()


def test_import_refuses_without_confirmation_or_into_nonempty_target(tmp_path):
    source_url = _create_source(tmp_path / "source.db")
    target_url = _create_target(tmp_path / "target.db")

    with pytest.raises(ScriptureImportPolicyError, match="confirmation"):
        import_scripture_rows(source_url=source_url, target_url=target_url)

    expectation = CatalogExpectation(
        total_count=3,
        translation_counts={"EOTC-COMPOSITE-EN": 1, "KJV": 2},
    )
    import_scripture_rows(
        source_url=source_url,
        target_url=target_url,
        confirm=True,
        expectation=expectation,
    )
    with pytest.raises(ScriptureImportPolicyError, match="not empty"):
        import_scripture_rows(
            source_url=source_url,
            target_url=target_url,
            confirm=True,
            expectation=expectation,
        )


def test_import_rejects_wrong_catalog_before_any_target_write(tmp_path):
    source_url = _create_source(tmp_path / "truncated-source.db")
    target_url = _create_target(tmp_path / "target.db")

    with pytest.raises(ScriptureImportPolicyError, match="catalog manifest"):
        import_scripture_rows(
            source_url=source_url,
            target_url=target_url,
            confirm=True,
            expectation=CatalogExpectation(
                total_count=4,
                translation_counts={"EOTC-COMPOSITE-EN": 2, "KJV": 2},
            ),
        )

    engine = create_engine(target_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM biblical_texts")) == 0
        assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 1
    engine.dispose()


def test_postgresql_import_locks_scripture_table_against_concurrent_writers():
    class _Dialect:
        name = "postgresql"

    class _Connection:
        dialect = _Dialect()

        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(str(statement))

    connection = _Connection()

    _lock_target(connection)

    assert connection.statements == [
        "LOCK TABLE biblical_texts IN SHARE ROW EXCLUSIVE MODE"
    ]
