from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.database import Base
from app.research_library import models as research_library_models  # noqa: F401


BACKEND_ROOT = Path(__file__).resolve().parents[2]
TABLES = {
    "research_work_profiles",
    "work_divisions",
    "source_editions",
    "source_edition_works",
    "license_records",
    "source_publications",
    "content_units",
    "citation_anchors",
    "research_chunks",
    "legacy_source_links",
    "legacy_content_links",
    "source_audit_events",
}
IMMUTABLE_TABLES = {
    "source_publications",
    "content_units",
    "citation_anchors",
    "research_chunks",
    "source_audit_events",
}


def _config(url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = f"sqlite:///{tmp_path / 'research-library.db'}"
    config = _config(url)
    command.upgrade(config, "0014_research_library_core")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
    try:
        yield config, engine
    finally:
        engine.dispose()


def _insert_foundations(connection):
    user_id = uuid4().hex
    connection.execute(
        text(
            "INSERT INTO users "
            "(id, email, email_normalized, username, password_hash, role, is_active) "
            "VALUES (:id, 'owner@example.test', 'owner@example.test', 'owner', 'x', "
            "'member', 1)"
        ),
        {"id": user_id},
    )
    connection.execute(text("INSERT INTO library_works (id, title) VALUES ('gen', 'Genesis')"))
    return user_id


def _insert_snapshot_graph(connection):
    user_id = _insert_foundations(connection)
    edition_1, edition_2 = uuid4().hex, uuid4().hex
    license_1, license_2 = uuid4().hex, uuid4().hex
    publication_1, publication_2 = uuid4().hex, uuid4().hex
    division_id, unit_id, anchor_id, chunk_id, audit_id = (uuid4().hex for _ in range(5))
    edition_sql = text(
        "INSERT INTO source_editions "
        "(id, title, edition_label, language, checksum, locator_scheme) "
        "VALUES (:id, :title, 'First', 'en', :checksum, 'book.chapter.verse')"
    )
    connection.execute(edition_sql, {"id": edition_1, "title": "Edition 1", "checksum": "e1"})
    connection.execute(edition_sql, {"id": edition_2, "title": "Edition 2", "checksum": "e2"})
    connection.execute(
        text("INSERT INTO source_edition_works (id, source_edition_id, work_id, source_label) VALUES (:id, :edition, 'gen', 'Genesis')"),
        {"id": uuid4().hex, "edition": edition_1},
    )
    license_sql = text(
        "INSERT INTO license_records "
        "(id, source_edition_id, license_name, reviewed_source_urls) "
        "VALUES (:id, :edition, 'Public domain', '[]')"
    )
    connection.execute(license_sql, {"id": license_1, "edition": edition_1})
    connection.execute(license_sql, {"id": license_2, "edition": edition_2})
    publication_sql = text(
        "INSERT INTO source_publications "
        "(id, source_edition_id, license_record_id, version, status, validation_approved, "
        "public_visibility, source_checksum, content_checksum) "
        "VALUES (:id, :edition, :license, :version, 'active', 1, 1, :source, :content)"
    )
    connection.execute(publication_sql, {"id": publication_1, "edition": edition_1, "license": license_1, "version": 1, "source": "s1", "content": "c1"})
    connection.execute(publication_sql, {"id": publication_2, "edition": edition_1, "license": license_1, "version": 2, "source": "s2", "content": "c2"})
    connection.execute(
        text("INSERT INTO work_divisions (id, work_id, division_type, label, normalized_locator, canonical_key, ordinal) VALUES (:id, 'gen', 'verse', 'Genesis 1:1', 'gen.1.1', 'gen-1-1', 1)"),
        {"id": division_id},
    )
    connection.execute(
        text("INSERT INTO content_units (id, source_publication_id, source_edition_id, work_id, work_division_id, language, direction, ordinal, normalized_text, source_locator, textual_certainty, checksum) VALUES (:id, :publication, :edition, 'gen', :division, 'en', 'ltr', 1, 'In the beginning', 'Gen 1:1', 'visible_text', 'u1')"),
        {"id": unit_id, "publication": publication_1, "edition": edition_1, "division": division_id},
    )
    connection.execute(
        text("INSERT INTO citation_anchors (id, source_publication_id, content_unit_id, work_division_id, anchor_key, human_locator, inspector_route, open_target) VALUES (:id, :publication, :unit, :division, 'gen-1-1', 'Genesis 1:1', '/inspect', '{}')"),
        {"id": anchor_id, "publication": publication_1, "unit": unit_id, "division": division_id},
    )
    connection.execute(
        text("INSERT INTO research_chunks (id, source_edition_id, source_publication_id, work_id, work_division_id, citation_anchor_id, ordinal, boundary_type, classification, hierarchy_level, language, content_digest, text_content) VALUES (:id, :edition, :publication, 'gen', :division, :anchor, 1, 'verse', 'canonical_scripture', 'verse', 'en', 'd1', 'In the beginning')"),
        {"id": chunk_id, "edition": edition_1, "publication": publication_1, "division": division_id, "anchor": anchor_id},
    )
    connection.execute(
        text("INSERT INTO source_audit_events (id, actor_id, source_edition_id, source_publication_id, action, resulting_state) VALUES (:id, :actor, :edition, :publication, 'published', '{}')"),
        {"id": audit_id, "actor": user_id, "edition": edition_1, "publication": publication_1},
    )
    return {
        "source_publications": publication_1,
        "content_units": unit_id,
        "citation_anchors": anchor_id,
        "research_chunks": chunk_id,
        "source_audit_events": audit_id,
        "edition_1": edition_1,
        "edition_2": edition_2,
        "license_2": license_2,
        "publication_2": publication_2,
    }


def test_revision_is_head_and_upgrade_adds_exact_catalog(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = f"sqlite:///{tmp_path / 'catalog.db'}"
    config = _config(url)
    assert [revision.revision for revision in ScriptDirectory.from_config(config).get_revisions("heads")] == ["0014_research_library_core"]

    command.upgrade(config, "0013_scripture_compatibility")
    engine = create_engine(url)
    assert not TABLES.intersection(inspect(engine).get_table_names())
    command.upgrade(config, "0014_research_library_core")
    inspector = inspect(engine)
    assert TABLES <= set(inspector.get_table_names())

    for table_name in TABLES:
        actual_columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        model_table = Base.metadata.tables[table_name]
        assert set(actual_columns) == {column.name for column in model_table.columns}
        for column in model_table.columns:
            assert actual_columns[column.name]["nullable"] == column.nullable
        actual_unique = {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}
        expected_unique = {constraint.name for constraint in model_table.constraints if constraint.__class__.__name__ == "UniqueConstraint" and constraint.name}
        assert expected_unique <= actual_unique
        actual_checks = {
            constraint["name"] for constraint in inspector.get_check_constraints(table_name)
        }
        expected_checks = {
            constraint.name
            for constraint in model_table.constraints
            if constraint.__class__.__name__ == "CheckConstraint" and constraint.name
        }
        assert expected_checks == actual_checks
        actual_fks = {
            constraint["name"] for constraint in inspector.get_foreign_keys(table_name)
        }
        expected_fks = {
            constraint.name
            for constraint in model_table.constraints
            if constraint.__class__.__name__ == "ForeignKeyConstraint" and constraint.name
        }
        assert expected_fks == actual_fks
        assert {index.name for index in model_table.indexes} == {index["name"] for index in inspector.get_indexes(table_name)}
    engine.dispose()


def test_composite_scope_constraints_and_active_pointer(migrated):
    _, engine = migrated
    with engine.begin() as connection:
        ids = _insert_snapshot_graph(connection)
        # Historical snapshots may both remain active; only the pointer changes.
        connection.execute(text("UPDATE source_editions SET active_publication_id=:publication WHERE id=:edition"), {"publication": ids["source_publications"], "edition": ids["edition_1"]})
        connection.execute(text("UPDATE source_editions SET active_publication_id=:publication WHERE id=:edition"), {"publication": ids["publication_2"], "edition": ids["edition_1"]})
        connection.execute(text("UPDATE source_editions SET active_publication_id=:publication WHERE id=:edition"), {"publication": ids["source_publications"], "edition": ids["edition_1"]})
        statuses = connection.execute(text("SELECT status FROM source_publications WHERE source_edition_id=:edition ORDER BY version"), {"edition": ids["edition_1"]}).scalars().all()
        assert statuses == ["active", "active"]

    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        with pytest.raises(IntegrityError):
            connection.execute(text("INSERT INTO source_publications (id, source_edition_id, license_record_id, version, status, validation_approved, public_visibility, source_checksum, content_checksum) VALUES (:id, :edition, :license, 3, 'verified', 1, 0, 's3', 'c3')"), {"id": uuid4().hex, "edition": ids["edition_1"], "license": ids["license_2"]})
        connection.rollback()
        connection.execute(text("PRAGMA foreign_keys=ON"))
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE source_editions SET active_publication_id=:publication WHERE id=:edition"), {"publication": ids["source_publications"], "edition": ids["edition_2"]})
        connection.rollback()
        with pytest.raises(IntegrityError):
            connection.execute(
                text("INSERT INTO work_divisions (id, work_id, division_type, label, normalized_locator, canonical_key, ordinal) VALUES (:id, 'gen', 'invalid', 'Bad', 'bad', 'bad', 0)"),
                {"id": uuid4().hex},
            )
        connection.rollback()


def test_database_triggers_make_snapshot_tables_immutable(migrated):
    _, engine = migrated
    with engine.begin() as connection:
        ids = _insert_snapshot_graph(connection)

    for table_name in sorted(IMMUTABLE_TABLES):
        for verb in ("UPDATE", "DELETE"):
            with engine.connect() as connection:
                statement = (f"UPDATE {table_name} SET id=id WHERE id=:id" if verb == "UPDATE" else f"DELETE FROM {table_name} WHERE id=:id")
                with pytest.raises(DBAPIError, match="immutable"):
                    connection.execute(text(statement), {"id": ids[table_name]})
                connection.rollback()

    with engine.begin() as connection:
        connection.execute(text("UPDATE source_editions SET title='Changed' WHERE id=:id"), {"id": ids["edition_1"]})
        connection.execute(text("DELETE FROM license_records WHERE id=:id"), {"id": ids["license_2"]})


def test_downgrade_removes_catalog_and_triggers_but_preserves_legacy(migrated):
    config, engine = migrated
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO biblical_texts (book, chapter, verse, text) VALUES ('Genesis', 1, 1, 'In the beginning')"))
        _insert_snapshot_graph(connection)
    engine.dispose()
    command.downgrade(config, "0013_scripture_compatibility")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    inspector = inspect(engine)
    assert not TABLES.intersection(inspector.get_table_names())
    assert inspector.has_table("biblical_texts")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM biblical_texts")) == 1
        trigger_count = connection.scalar(text("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_rl_immutable_%'"))
        assert trigger_count == 0
    engine.dispose()


def test_postgresql_ddl_helpers_cover_cycle_partial_indexes_and_triggers():
    config = _config("postgresql://unused")
    migration = ScriptDirectory.from_config(config).get_revision(
        "0014_research_library_core"
    ).module
    upgrade_sql = migration._postgresql_upgrade_sql()
    downgrade_sql = migration._postgresql_downgrade_sql()
    assert "fk_source_editions_active_publication_same_edition" in upgrade_sql
    assert "ALTER TABLE source_editions" in upgrade_sql
    assert "WHERE parent_id IS NULL" in upgrade_sql
    assert "WHERE parent_id IS NOT NULL" in upgrade_sql
    for table_name in IMMUTABLE_TABLES:
        assert table_name in upgrade_sql
    assert upgrade_sql.index("CREATE TABLE source_publications") < upgrade_sql.index("fk_source_editions_active_publication_same_edition")
    assert downgrade_sql.index("DROP TRIGGER") < downgrade_sql.index("DROP TABLE source_publications")
