from io import StringIO
import hashlib
import os
from pathlib import Path
import re
from uuid import uuid4

import psycopg2
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.database import Base
from app.research_library import models as research_library_models  # noqa: F401
from tests.migrations.research_library_0014_manifest import (
    ACTIVE_POINTER,
    SQLITE_OBJECT_DIGESTS,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = BACKEND_ROOT / "alembic/versions/0014_research_library_core.py"
TABLE_ORDER = (
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
)
TABLES = set(TABLE_ORDER)
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


def _normalize_sql(value) -> str | None:
    if value is None:
        return None
    return re.sub(r'[\s"`\[\]]+', "", str(value)).lower()


def _type_sql(type_, dialect) -> str:
    return re.sub(r"\s+", " ", type_.compile(dialect=dialect).upper()).strip()


def _model_default(column, dialect) -> str | None:
    if column.server_default is None:
        return None
    return _normalize_sql(column.server_default.arg.compile(dialect=dialect))


def _offline_sql(config: Config, revision_range: str, *, downgrade: bool = False) -> str:
    buffer = StringIO()
    config.output_buffer = buffer
    if downgrade:
        command.downgrade(config, revision_range, sql=True)
    else:
        command.upgrade(config, revision_range, sql=True)
    return buffer.getvalue()


def test_revision_is_frozen_from_application_metadata():
    source = MIGRATION_PATH.read_text()
    assert "from app" not in source
    assert "Base.metadata" not in source


def test_migrated_schema_matches_frozen_0014_snapshot(migrated):
    _, engine = migrated
    with engine.connect() as connection:
        objects = connection.execute(
            text(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE sql IS NOT NULL AND tbl_name IN :tables"
            ).bindparams(sa.bindparam("tables", expanding=True)),
            {"tables": tuple(TABLES)},
        ).all()
    actual = {
        f"{object_type}:{name}": hashlib.sha256(
            _normalize_sql(sql).encode()
        ).hexdigest()
        for object_type, name, _table_name, sql in objects
    }
    assert actual == SQLITE_OBJECT_DIGESTS
    active_pointer = next(
        foreign_key
        for foreign_key in inspect(engine).get_foreign_keys(ACTIVE_POINTER['table'])
        if foreign_key['name'] == 'fk_source_editions_active_publication_same_edition'
    )
    assert tuple(active_pointer['constrained_columns']) == ACTIVE_POINTER['local_columns']
    assert active_pointer['referred_table'] == ACTIVE_POINTER['remote_table']
    assert tuple(active_pointer['referred_columns']) == ACTIVE_POINTER['remote_columns']
    assert active_pointer['options']['ondelete'] == ACTIVE_POINTER['ondelete']


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
            "'member', :is_active)"
        ),
        {"id": user_id, "is_active": True},
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
        "VALUES (:id, :edition, :license, :version, 'active', :approved, "
        ":visible, :source, :content)"
    )
    defaults = {"approved": True, "visible": True}
    connection.execute(publication_sql, defaults | {"id": publication_1, "edition": edition_1, "license": license_1, "version": 1, "source": "s1", "content": "c1"})
    connection.execute(publication_sql, defaults | {"id": publication_2, "edition": edition_1, "license": license_1, "version": 2, "source": "s2", "content": "c2"})
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
        model_table = Base.metadata.tables[table_name]
        reflected_columns = inspector.get_columns(table_name)
        actual_columns = {column["name"]: column for column in reflected_columns}
        expected_pk = tuple(column.name for column in model_table.primary_key.columns)
        assert tuple(inspector.get_pk_constraint(table_name)["constrained_columns"]) == expected_pk
        assert set(actual_columns) == {column.name for column in model_table.columns}
        for column in model_table.columns:
            reflected = actual_columns[column.name]
            assert _type_sql(reflected["type"], engine.dialect) == _type_sql(
                column.type, engine.dialect
            )
            assert reflected["nullable"] == column.nullable
            assert _normalize_sql(reflected["default"]) == _model_default(
                column, engine.dialect
            )
            expected_pk_position = (
                expected_pk.index(column.name) + 1 if column.name in expected_pk else 0
            )
            assert reflected["primary_key"] == expected_pk_position

        actual_unique = {
            constraint["name"]: tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table_name)
        }
        expected_unique = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in model_table.constraints
            if isinstance(constraint, UniqueConstraint) and constraint.name
        }
        assert actual_unique == expected_unique

        actual_fks = {
            constraint["name"]: (
                tuple(constraint["constrained_columns"]),
                constraint["referred_table"],
                tuple(constraint["referred_columns"]),
                constraint["options"].get("ondelete"),
            )
            for constraint in inspector.get_foreign_keys(table_name)
        }
        expected_fks = {
            constraint.name: (
                tuple(element.parent.name for element in constraint.elements),
                constraint.referred_table.name,
                tuple(element.column.name for element in constraint.elements),
                constraint.ondelete,
            )
            for constraint in model_table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert actual_fks == expected_fks

        actual_checks = {
            constraint["name"]: _normalize_sql(constraint["sqltext"])
            for constraint in inspector.get_check_constraints(table_name)
        }
        expected_checks = {
            constraint.name: _normalize_sql(constraint.sqltext)
            for constraint in model_table.constraints
            if isinstance(constraint, CheckConstraint) and constraint.name
        }
        assert actual_checks == expected_checks

        actual_indexes = {
            index["name"]: (tuple(index["column_names"]), index["unique"])
            for index in inspector.get_indexes(table_name)
        }
        expected_indexes = {
            index.name: (
                tuple(expression.name for expression in index.expressions),
                index.unique,
            )
            for index in model_table.indexes
        }
        assert actual_indexes == expected_indexes

    with engine.connect() as connection:
        partial_index_sql = dict(
            connection.execute(
                text(
                    "SELECT name, sql FROM sqlite_master WHERE type='index' "
                    "AND name IN ('uq_work_divisions_root_ordinal', "
                    "'uq_work_divisions_child_ordinal')"
                )
            ).all()
        )
    assert _normalize_sql(partial_index_sql["uq_work_divisions_root_ordinal"].split("WHERE", 1)[1]) == "parent_idisnull"
    assert _normalize_sql(partial_index_sql["uq_work_divisions_child_ordinal"].split("WHERE", 1)[1]) == "parent_idisnotnull"
    engine.dispose()


def test_composite_scope_constraints_reject_cross_edition_references(migrated):
    _, engine = migrated
    with engine.begin() as connection:
        ids = _insert_snapshot_graph(connection)

    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        with pytest.raises(IntegrityError):
            connection.execute(text("INSERT INTO source_publications (id, source_edition_id, license_record_id, version, status, validation_approved, public_visibility, source_checksum, content_checksum) VALUES (:id, :edition, :license, 3, 'verified', 1, 0, 's3', 'c3')"), {"id": uuid4().hex, "edition": ids["edition_1"], "license": ids["license_2"]})
        connection.rollback()
        connection.execute(text("PRAGMA foreign_keys=ON"))
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "UPDATE source_editions SET active_publication_id=:publication "
                    "WHERE id=:edition"
                ),
                {
                    "publication": ids["source_publications"],
                    "edition": ids["edition_2"],
                },
            )
        connection.rollback()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO work_divisions "
                    "(id, work_id, division_type, label, normalized_locator, "
                    "canonical_key, ordinal) VALUES "
                    "(:id, 'gen', 'invalid', 'Bad', 'bad', 'bad', 0)"
                ),
                {"id": uuid4().hex},
            )
        connection.rollback()


def test_active_pointer_replacement_and_rollback_are_transactional(migrated):
    _, engine = migrated
    with engine.begin() as connection:
        ids = _insert_snapshot_graph(connection)

    pointer_sql = text(
        "UPDATE source_editions SET active_publication_id=:publication WHERE id=:edition"
    )
    pointer_value_sql = text(
        "SELECT active_publication_id FROM source_editions WHERE id=:edition"
    )
    params = {"edition": ids["edition_1"]}
    publication_a = ids["source_publications"]
    publication_b = ids["publication_2"]

    with engine.connect() as connection:
        connection.execute(pointer_sql, params | {"publication": publication_a})
        connection.commit()
        assert connection.scalar(pointer_value_sql, params) == publication_a

        connection.execute(pointer_sql, params | {"publication": publication_b})
        connection.commit()
        assert connection.scalar(pointer_value_sql, params) == publication_b

        connection.execute(pointer_sql, params | {"publication": publication_a})
        connection.rollback()
        assert connection.scalar(pointer_value_sql, params) == publication_b

        connection.execute(pointer_sql, params | {"publication": publication_a})
        connection.commit()
        assert connection.scalar(pointer_value_sql, params) == publication_a

        publications = connection.execute(
            text(
                "SELECT id, status, source_checksum, content_checksum "
                "FROM source_publications WHERE source_edition_id=:edition ORDER BY version"
            ),
            params,
        ).all()
        assert publications == [
            (publication_a, "active", "s1", "c1"),
            (publication_b, "active", "s2", "c2"),
        ]


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


def test_postgresql_offline_upgrade_and_downgrade_execute_real_revision_paths():
    config = _config("postgresql://unused")
    upgrade_sql = _offline_sql(
        config, "0013_scripture_compatibility:0014_research_library_core"
    )
    downgrade_sql = _offline_sql(
        config,
        "0014_research_library_core:0013_scripture_compatibility",
        downgrade=True,
    )
    normalized_upgrade = _normalize_sql(upgrade_sql)
    normalized_downgrade = _normalize_sql(downgrade_sql)

    create_positions = [
        normalized_upgrade.index(f"createtable{table_name}") for table_name in TABLE_ORDER
    ]
    assert create_positions == sorted(create_positions)
    active_fk_statement = (
        "altertablesource_editionsaddconstraint"
        "fk_source_editions_active_publication_same_edition"
        "foreignkey(active_publication_id,id)"
        "referencessource_publications(id,source_edition_id)ondeleterestrict"
    )
    active_fk_position = normalized_upgrade.index(active_fk_statement)
    assert normalized_upgrade.index("createtablesource_editions") < active_fk_position
    assert normalized_upgrade.index("createtablesource_publications") < active_fk_position
    for dependent_table in (
        "content_units",
        "citation_anchors",
        "research_chunks",
        "source_audit_events",
    ):
        assert active_fk_position < normalized_upgrade.index(
            f"createtable{dependent_table}"
        )
    assert "whereparent_idisnull" in normalized_upgrade
    assert "whereparent_idisnotnull" in normalized_upgrade

    function_position = normalized_upgrade.index(
        "createfunctionresearch_library_reject_immutable_dml"
    )
    assert "usingerrcode='55000'" in normalized_upgrade
    for table_name in IMMUTABLE_TABLES:
        complete_trigger = (
            f"createtriggertrg_rl_immutable_{table_name}beforeupdateordelete"
            f"on{table_name}foreachrowexecutefunction"
            "research_library_reject_immutable_dml()"
        )
        trigger_position = normalized_upgrade.index(complete_trigger)
        assert normalized_upgrade.index(f"createtable{table_name}") < trigger_position
        assert function_position < trigger_position
        assert active_fk_position < trigger_position

    trigger_drop_positions = [
        normalized_downgrade.index(f"droptriggerifexiststrg_rl_immutable_{table_name}")
        for table_name in IMMUTABLE_TABLES
    ]
    function_drop_position = normalized_downgrade.index(
        "dropfunctionifexistsresearch_library_reject_immutable_dml"
    )
    assert all(position < function_drop_position for position in trigger_drop_positions)
    active_fk_drop_position = normalized_downgrade.index(
        "dropconstraintfk_source_editions_active_publication_same_edition"
    )
    table_drop_positions = [
        normalized_downgrade.index(f"droptable{table_name}")
        for table_name in reversed(TABLE_ORDER)
    ]
    assert active_fk_drop_position < min(table_drop_positions)
    assert table_drop_positions == sorted(table_drop_positions)


def _postgres_connect(url, database=None):
    parsed = make_url(url)
    return psycopg2.connect(
        host=parsed.host,
        port=parsed.port,
        user=parsed.username,
        password=parsed.password,
        dbname=database or parsed.database,
    )


@pytest.mark.skipif(
    not os.environ.get('TEST_POSTGRES_DATABASE_URL'),
    reason='TEST_POSTGRES_DATABASE_URL is not configured for live PostgreSQL tests.',
)
def test_postgresql_live_research_library_migration_is_reversible_and_enforced():
    service_url = os.environ['TEST_POSTGRES_DATABASE_URL']
    database_name = f"unbound_rl_{uuid4().hex}"
    admin = _postgres_connect(service_url)
    admin.autocommit = True
    engine = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{database_name}"')
        isolated_url = make_url(service_url).set(database=database_name).render_as_string(
            hide_password=False
        )
        config = _config(isolated_url)
        command.upgrade(config, '0013_scripture_compatibility')
        engine = create_engine(isolated_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO biblical_texts (book, chapter, verse, text) "
                    "VALUES ('Genesis', 1, 1, 'In the beginning')"
                )
            )
        engine.dispose()
        command.upgrade(config, '0014_research_library_core')
        engine = create_engine(isolated_url)

        inspector = inspect(engine)
        assert TABLES <= set(inspector.get_table_names())
        active_pointer = next(
            foreign_key
            for foreign_key in inspector.get_foreign_keys('source_editions')
            if foreign_key['name'] == 'fk_source_editions_active_publication_same_edition'
        )
        assert tuple(active_pointer['constrained_columns']) == ACTIVE_POINTER['local_columns']
        assert tuple(active_pointer['referred_columns']) == ACTIVE_POINTER['remote_columns']
        assert active_pointer['options']['ondelete'] == 'RESTRICT'
        with engine.connect() as connection:
            trigger_names = set(
                connection.execute(
                    text(
                        "SELECT tgname FROM pg_trigger "
                        "WHERE NOT tgisinternal AND tgname LIKE 'trg_rl_immutable_%'"
                    )
                ).scalars()
            )
        assert trigger_names == {
            f'trg_rl_immutable_{table_name}' for table_name in IMMUTABLE_TABLES
        }

        with engine.begin() as connection:
            ids = _insert_snapshot_graph(connection)

        with engine.connect() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO source_publications "
                        "(id, source_edition_id, license_record_id, version, status, "
                        "validation_approved, public_visibility, source_checksum, "
                        "content_checksum) VALUES "
                        "(:id, :edition, :license, 3, 'verified', :approved, "
                        ":visible, 's3', 'c3')"
                    ),
                    {
                        'id': uuid4().hex,
                        'edition': ids['edition_1'],
                        'license': ids['license_2'],
                        'approved': True,
                        'visible': False,
                    },
                )
            connection.rollback()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "UPDATE source_editions SET active_publication_id=:publication "
                        "WHERE id=:edition"
                    ),
                    {
                        'publication': ids['source_publications'],
                        'edition': ids['edition_2'],
                    },
                )
            connection.rollback()

        for table_name in IMMUTABLE_TABLES:
            for verb in ('UPDATE', 'DELETE'):
                with engine.connect() as connection:
                    statement = (
                        f'UPDATE {table_name} SET id=id WHERE id=:id'
                        if verb == 'UPDATE'
                        else f'DELETE FROM {table_name} WHERE id=:id'
                    )
                    with pytest.raises(DBAPIError, match='immutable'):
                        connection.execute(text(statement), {'id': ids[table_name]})
                    connection.rollback()

        pointer_sql = text(
            "UPDATE source_editions SET active_publication_id=:publication "
            "WHERE id=:edition"
        )
        pointer_value = text(
            "SELECT active_publication_id FROM source_editions WHERE id=:edition"
        )
        params = {'edition': ids['edition_1']}
        with engine.connect() as connection:
            connection.execute(
                pointer_sql, params | {'publication': ids['source_publications']}
            )
            connection.commit()
            connection.execute(pointer_sql, params | {'publication': ids['publication_2']})
            connection.commit()
            connection.execute(
                pointer_sql, params | {'publication': ids['source_publications']}
            )
            connection.rollback()
            selected = connection.scalar(pointer_value, params)
            assert str(selected).replace('-', '') == ids['publication_2']
            statuses = connection.execute(
                text(
                    "SELECT status, source_checksum, content_checksum "
                    "FROM source_publications WHERE source_edition_id=:edition "
                    "ORDER BY version"
                ),
                params,
            ).all()
            assert statuses == [('active', 's1', 'c1'), ('active', 's2', 'c2')]

        engine.dispose()
        command.downgrade(config, '0013_scripture_compatibility')
        engine = create_engine(isolated_url)
        assert not TABLES.intersection(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM biblical_texts')) == 1
        engine.dispose()
        command.upgrade(config, '0014_research_library_core')
        engine = create_engine(isolated_url)
        assert TABLES <= set(inspect(engine).get_table_names())
    finally:
        if engine is not None:
            engine.dispose()
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            cursor.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        admin.close()
