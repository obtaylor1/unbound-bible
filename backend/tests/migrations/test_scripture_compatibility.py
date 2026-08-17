from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_fresh_database_migration_creates_scripture_compatibility_table(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database_url = f"sqlite:///{tmp_path / 'scripture-compatibility.db'}"
    config = _alembic_config(database_url)

    scripts = ScriptDirectory.from_config(config)
    assert [head.revision for head in scripts.get_revisions("heads")] == [
        "0014_research_library_core"
    ]

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    inspector = inspect(engine)

    assert inspector.has_table("biblical_texts")
    assert {column["name"] for column in inspector.get_columns("biblical_texts")} == {
        "id",
        "book",
        "chapter",
        "verse",
        "text",
        "translation",
    }
    with engine.connect() as connection:
        index_sql = connection.scalar(text(
            "SELECT sql FROM sqlite_master WHERE type = 'index' "
            "AND name = 'uq_biblical_texts_translation_book_chapter_verse'"
        ))
    assert index_sql is not None
    assert "coalesce(translation, '')" in index_sql.lower()
    engine.dispose()
