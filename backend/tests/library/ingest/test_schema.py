import importlib.util
import os
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import (
    Column,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    delete,
    event,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex

from app.application import create_application
from app.database import Base
from app.library import models as library_models
from app.library.models import TextEdition

from .conftest import make_ingest_run


MODELS_AVAILABLE = importlib.util.find_spec('app.library.ingest.models') is not None
pytestmark = pytest.mark.skipif(not MODELS_AVAILABLE, reason='verified ingestion models are not implemented yet')

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REVISION = '0007_verified_ingest'
COMPOSITE_REVISION = '0009_composite_edition_sources'
INGEST_TABLES = {
    'scripture_ingest_runs',
    'staged_scripture_verses',
    'scripture_validation_findings',
    'scripture_publications',
    'scripture_publication_verses',
}


def test_edition_work_source_model_has_required_columns_constraints_and_index():
    table = library_models.EditionWorkSource.__table__

    assert table.name == 'edition_work_sources'
    assert set(table.columns.keys()) == {
        'id', 'edition_code', 'work_id', 'source_key', 'source_label', 'translator',
        'source_language', 'source_tradition', 'published_year', 'license_spdx',
        'attribution', 'provenance_url', 'fallback', 'modified', 'modification_note',
        'verification_status', 'canon_scope',
    }
    assert table.primary_key.columns.keys() == ['id']
    assert {
        column.name for column in table.columns if column.nullable
    } == {'translator', 'published_year', 'provenance_url', 'modification_note'}
    assert table.c.fallback.default.arg is False
    assert table.c.modified.default.arg is False
    assert {
        (foreign_key.parent.name, foreign_key.column.table.name, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    } == {
        ('edition_code', 'text_editions', 'CASCADE'),
        ('work_id', 'library_works', 'CASCADE'),
    }
    assert {
        (constraint.name, tuple(constraint.columns.keys()))
        for constraint in table.constraints
        if constraint.__class__.__name__ == 'UniqueConstraint'
    } == {('uq_edition_work_sources_edition_work', ('edition_code', 'work_id'))}
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if constraint.__class__.__name__ == 'CheckConstraint'
    }
    assert checks == {
        'ck_edition_work_sources_verification_status': (
            "verification_status IN ('provisional', 'verified')"
        ),
        'ck_edition_work_sources_canon_scope': "canon_scope IN ('ethio81', 'supplemental')",
    }
    assert {index.name: tuple(index.columns.keys()) for index in table.indexes} == {
        'ix_edition_work_sources_work_id': ('work_id',),
    }


def test_text_edition_verification_status_allows_provisional():
    constraint = next(
        constraint
        for constraint in TextEdition.__table__.constraints
        if constraint.name == 'ck_text_editions_verification_status'
    )

    assert "'provisional'" in str(constraint.sqltext)


def test_application_registers_verified_ingestion_tables(test_settings):
    application = create_application(test_settings)

    assert INGEST_TABLES <= set(inspect(application.state.database_engine).get_table_names())


def test_ingestion_schema_has_exact_columns_named_constraints_foreign_keys_and_indexes(test_settings):
    application = create_application(test_settings)
    inspector = inspect(application.state.database_engine)

    assert {column['name'] for column in inspector.get_columns('scripture_ingest_runs')} == {
        'id', 'edition_code', 'source_checksum', 'manifest_snapshot', 'status', 'created_at',
        'updated_at', 'staged_count', 'error_count', 'warning_count', 'published_count',
    }
    assert {column['name'] for column in inspector.get_columns('staged_scripture_verses')} == {
        'id', 'run_id', 'work_id', 'source_book', 'chapter', 'verse', 'normalized_text',
        'source_locator', 'row_checksum', 'created_at',
    }
    assert {column['name'] for column in inspector.get_columns('scripture_validation_findings')} == {
        'id', 'run_id', 'severity', 'code', 'work_id', 'chapter', 'verse', 'message', 'created_at',
    }
    assert {column['name'] for column in inspector.get_columns('scripture_publications')} == {
        'id', 'edition_code', 'run_id', 'previous_run_id', 'publication_version', 'published_at', 'active',
    }
    assert {column['name'] for column in inspector.get_columns('scripture_publication_verses')} == {
        'id', 'publication_id', 'work_id', 'source_book', 'chapter', 'verse',
        'normalized_text', 'source_locator', 'row_checksum',
    }

    checks = {
        table: {item['name'] for item in inspector.get_check_constraints(table)}
        for table in INGEST_TABLES
    }
    assert checks['scripture_ingest_runs'] >= {
        'ck_scripture_ingest_runs_status', 'ck_scripture_ingest_runs_source_checksum_length',
        'ck_scripture_ingest_runs_staged_count_nonnegative',
        'ck_scripture_ingest_runs_error_count_nonnegative',
        'ck_scripture_ingest_runs_warning_count_nonnegative',
        'ck_scripture_ingest_runs_published_count_nonnegative',
    }
    assert checks['staged_scripture_verses'] >= {
        'ck_staged_scripture_verses_chapter_positive',
        'ck_staged_scripture_verses_verse_positive',
        'ck_staged_scripture_verses_row_checksum_length',
    }
    assert checks['scripture_validation_findings'] >= {
        'ck_scripture_validation_findings_severity',
        'ck_scripture_validation_findings_chapter_positive',
        'ck_scripture_validation_findings_verse_positive',
    }
    assert checks['scripture_publications'] >= {'ck_scripture_publications_version_positive'}
    assert checks['scripture_publication_verses'] >= {
        'ck_scripture_publication_verses_chapter_positive',
        'ck_scripture_publication_verses_verse_positive',
        'ck_scripture_publication_verses_row_checksum_length',
    }

    uniques = {item['name'] for item in inspector.get_unique_constraints('staged_scripture_verses')}
    assert 'uq_staged_scripture_verses_run_work_chapter_verse' in uniques
    assert 'uq_scripture_ingest_runs_id_edition' in {
        item['name'] for item in inspector.get_unique_constraints('scripture_ingest_runs')
    }
    assert 'uq_scripture_publications_edition_version' in {
        item['name'] for item in inspector.get_unique_constraints('scripture_publications')
    }
    assert 'uq_scripture_publication_verses_publication_work_chapter_verse' in {
        item['name'] for item in inspector.get_unique_constraints('scripture_publication_verses')
    }
    assert {item['name'] for item in inspector.get_indexes('staged_scripture_verses')} >= {
        'ix_staged_scripture_verses_run_id', 'ix_staged_scripture_verses_work_id',
        'ix_staged_scripture_verses_row_checksum',
    }
    assert 'uq_scripture_publications_active_edition' in {
        item['name'] for item in inspector.get_indexes('scripture_publications')
    }
    assert {item['name'] for item in inspector.get_indexes('scripture_publication_verses')} >= {
        'ix_scripture_publication_verses_publication_id',
        'ix_scripture_publication_verses_work_id',
        'ix_scripture_publication_verses_row_checksum',
    }
    assert {item['referred_table'] for item in inspector.get_foreign_keys('staged_scripture_verses')} == {
        'scripture_ingest_runs', 'library_works'
    }
    assert {item['referred_table'] for item in inspector.get_foreign_keys('scripture_publications')} == {
        'text_editions', 'scripture_ingest_runs'
    }
    assert {
        item['referred_table']
        for item in inspector.get_foreign_keys('scripture_publication_verses')
    } == {'scripture_publications', 'library_works'}
    publication_foreign_keys = {
        item['name']: (
            item['constrained_columns'], item['referred_columns'], item['options'].get('ondelete')
        )
        for item in inspector.get_foreign_keys('scripture_publications')
    }
    assert publication_foreign_keys['fk_scripture_publications_run_edition'] == (
        ['run_id', 'edition_code'], ['id', 'edition_code'], 'CASCADE'
    )
    assert publication_foreign_keys['fk_scripture_publications_previous_run_edition'] == (
        ['previous_run_id', 'edition_code'], ['id', 'edition_code'], 'RESTRICT'
    )


def test_database_rejects_invalid_workflow_severity_orphans_and_positions(ingest_session):
    from app.library.ingest.models import ScriptureIngestRun, ScriptureValidationFinding, StagedScriptureVerse

    run = make_ingest_run(ingest_session, 'INGEST-TEST', 'In the beginning')
    invalid_rows = [
        ScriptureIngestRun(
            id=uuid4(), edition_code='INGEST-TEST', source_checksum='a' * 64,
            manifest_snapshot={}, status='not-a-state',
        ),
        ScriptureIngestRun(
            id=uuid4(), edition_code='missing-edition', source_checksum='a' * 64,
            manifest_snapshot={}, status='staged',
        ),
        StagedScriptureVerse(
            run_id=run.id, work_id='genesis', source_book='Genesis', chapter=0, verse=1,
            normalized_text='x', source_locator='x', row_checksum='b' * 64,
        ),
        StagedScriptureVerse(
            run_id=uuid4(), work_id='genesis', source_book='Genesis', chapter=1, verse=2,
            normalized_text='x', source_locator='x', row_checksum='c' * 64,
        ),
        ScriptureValidationFinding(
            run_id=run.id, severity='info', code='invalid', message='x',
        ),
        ScriptureValidationFinding(
            run_id=run.id, severity='error', code='invalid-position', chapter=-1, message='x',
        ),
    ]
    for invalid in invalid_rows:
        with ingest_session.begin_nested():
            ingest_session.add(invalid)
            with pytest.raises(IntegrityError):
                ingest_session.flush()


def test_deleting_an_ingest_run_cascades_staged_verses_and_findings(ingest_session):
    from app.library.ingest.models import ScriptureIngestRun, ScriptureValidationFinding, StagedScriptureVerse

    run = make_ingest_run(
        ingest_session, 'CASCADE-TEST', 'In the beginning',
        finding={'severity': 'warning', 'code': 'style', 'message': 'Review punctuation'},
    )
    ingest_session.execute(delete(ScriptureIngestRun).where(ScriptureIngestRun.id == run.id))
    ingest_session.flush()

    assert ingest_session.scalar(select(StagedScriptureVerse.id).where(StagedScriptureVerse.run_id == run.id)) is None
    assert ingest_session.scalar(select(ScriptureValidationFinding.id).where(ScriptureValidationFinding.run_id == run.id)) is None


@pytest.mark.parametrize('link', ('current', 'previous'))
def test_publications_reject_cross_edition_run_links(ingest_session, link):
    from app.library.ingest.models import ScripturePublication

    current = make_ingest_run(ingest_session, 'CURRENT-EDITION', 'Current text')
    other = make_ingest_run(ingest_session, 'OTHER-EDITION', 'Other text')
    values = {
        'edition_code': current.edition_code,
        'run_id': other.id if link == 'current' else current.id,
        'previous_run_id': other.id if link == 'previous' else None,
        'publication_version': 1,
        'active': False,
    }

    with ingest_session.begin_nested():
        ingest_session.add(ScripturePublication(**values))
        with pytest.raises(IntegrityError):
            ingest_session.flush()


def _alembic_config(database_path):
    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_ROOT / 'alembic'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database_path}')
    return config


def _create_legacy_biblical_texts(engine):
    table = Table(
        'biblical_texts', MetaData(),
        Column('id', Integer, primary_key=True),
        Column('translation', String(100), nullable=True),
        Column('book', String(100), nullable=False),
        Column('chapter', Integer, nullable=False),
        Column('verse', Integer, nullable=False),
    )
    table.create(engine)
    return table


def test_composite_source_migration_adds_source_schema_and_supplemental_work(tmp_path):
    config = _alembic_config(tmp_path / 'composite-sources.db')

    command.upgrade(config, COMPOSITE_REVISION)
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    inspector = inspect(engine)

    assert {column['name'] for column in inspector.get_columns('edition_work_sources')} == {
        'id', 'edition_code', 'work_id', 'source_key', 'source_label', 'translator',
        'source_language', 'source_tradition', 'published_year', 'license_spdx',
        'attribution', 'provenance_url', 'fallback', 'modified', 'modification_note',
        'verification_status', 'canon_scope',
    }
    assert {item['name'] for item in inspector.get_check_constraints('edition_work_sources')} == {
        'ck_edition_work_sources_verification_status',
        'ck_edition_work_sources_canon_scope',
    }
    assert {item['name'] for item in inspector.get_unique_constraints('edition_work_sources')} == {
        'uq_edition_work_sources_edition_work',
    }
    assert {item['name'] for item in inspector.get_indexes('edition_work_sources')} == {
        'ix_edition_work_sources_work_id',
    }
    assert {
        (item['referred_table'], item['options'].get('ondelete'))
        for item in inspector.get_foreign_keys('edition_work_sources')
    } == {('text_editions', 'CASCADE'), ('library_works', 'CASCADE')}
    edition_status = next(
        item['sqltext']
        for item in inspector.get_check_constraints('text_editions')
        if item['name'] == 'ck_text_editions_verification_status'
    )
    assert "'provisional'" in edition_status
    with engine.connect() as connection:
        assert connection.execute(__import__('sqlalchemy').text(
            "SELECT title FROM library_works WHERE id = 'prayer-of-manasseh'"
        )).scalar_one() == 'Prayer of Manasseh'

    command.downgrade(config, '0008_commentary_library')
    inspector = inspect(engine)
    assert 'edition_work_sources' not in inspector.get_table_names()
    downgraded_status = next(
        item['sqltext']
        for item in inspector.get_check_constraints('text_editions')
        if item['name'] == 'ck_text_editions_verification_status'
    )
    assert "'provisional'" not in downgraded_status
    with engine.connect() as connection:
        assert connection.execute(__import__('sqlalchemy').text(
            "SELECT title FROM library_works WHERE id = 'prayer-of-manasseh'"
        )).scalar_one_or_none() is None


def test_composite_source_migration_preserves_populated_dependent_rows_with_sqlite_fks(tmp_path):
    config = _alembic_config(tmp_path / 'populated-composite-sources.db')
    command.upgrade(config, '0008_commentary_library')

    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute('PRAGMA foreign_keys=ON')

    event.listen(Engine, 'connect', enable_foreign_keys)
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO library_works (id, title) VALUES ('genesis', 'Genesis')"
            ))
            connection.execute(text("""
                INSERT INTO text_editions (
                    edition_code, name, reading_language, source_language, script,
                    translator, publisher, published_year, license_spdx, attribution,
                    provenance_url, source_tradition, relationship, versification,
                    expected_coverage, verification_status, source_checksum
                ) VALUES (
                    'PRESERVE', 'Preserved Edition', 'eng', 'gez', 'Latin',
                    'Test Translator', 'Test Publisher', 2024, 'CC0-1.0',
                    'Test Attribution', 'https://example.test/source', 'Ethiopian',
                    'general_reading', 'standard', '{}', 'staged', 'abc123'
                )
            """))
            connection.execute(text("""
                INSERT INTO edition_coverage (
                    edition_code, work_id, status, chapter_count, verse_count, note
                ) VALUES (
                    'PRESERVE', 'genesis', 'verified_english', 50, 1533, 'Keep this row'
                )
            """))

        def assert_rows_are_intact():
            with engine.connect() as connection:
                assert connection.execute(text("""
                    SELECT name, verification_status, source_checksum
                    FROM text_editions WHERE edition_code = 'PRESERVE'
                """)).one() == ('Preserved Edition', 'staged', 'abc123')
                assert connection.execute(text("""
                    SELECT edition_code, work_id, status, chapter_count, verse_count, note
                    FROM edition_coverage WHERE edition_code = 'PRESERVE'
                """)).one() == (
                    'PRESERVE', 'genesis', 'verified_english', 50, 1533, 'Keep this row'
                )

        command.upgrade(config, COMPOSITE_REVISION)
        assert_rows_are_intact()
        command.downgrade(config, '0008_commentary_library')
        assert_rows_are_intact()
    finally:
        engine.dispose()
        event.remove(Engine, 'connect', enable_foreign_keys)


def test_all_alembic_revision_identifiers_fit_the_version_table(tmp_path):
    scripts = ScriptDirectory.from_config(_alembic_config(tmp_path / 'revision-length.db'))

    assert {
        revision.revision: len(revision.revision)
        for revision in scripts.walk_revisions()
        if len(revision.revision) > 32
    } == {}


@pytest.mark.parametrize('database_url', ('sqlite://', 'postgresql://offline/ingest'))
@pytest.mark.parametrize(
    ('direction', 'target', 'forbidden_ddl'),
    (
        ('upgrade', REVISION, 'create table scripture_ingest_runs'),
        ('downgrade', f'{REVISION}:0006_ethiopian_library', 'drop table scripture_ingest_runs'),
    ),
)
def test_offline_migration_refuses_before_task2_ddl(
    database_url, direction, target, forbidden_ddl
):
    result = subprocess.run(
        [sys.executable, '-m', 'alembic', '-c', 'alembic.ini', direction, target, '--sql'],
        cwd=BACKEND_ROOT,
        env={**os.environ, 'DATABASE_URL': database_url, 'PYTHONPATH': str(BACKEND_ROOT)},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    output = f'{result.stdout}\n{result.stderr}'.lower()

    assert result.returncode != 0
    assert 'offline migration refused for 0007_verified_ingest' in output
    assert 'run alembic online without --sql' in output
    assert 'inspect biblical_texts' in output
    assert 'preflight duplicate verse identities' in output
    assert 'conditionally manage the functional unique index' in output
    assert forbidden_ddl not in output
    assert 'create table scripture_publications' not in output
    assert 'drop table scripture_publications' not in output
    if direction == 'upgrade':
        assert 'create table library_works' in result.stdout.lower()


def test_legacy_functional_unique_index_compiles_for_sqlite_and_postgresql():
    migration_path = BACKEND_ROOT / 'alembic' / 'versions' / '0007_verified_ingest.py'
    spec = importlib.util.spec_from_file_location('verified_ingest_migration', migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    index_factory = getattr(migration, '_legacy_identity_index', None)

    assert callable(index_factory)
    for dialect in (sqlite.dialect(), postgresql.dialect()):
        ddl = ' '.join(str(CreateIndex(index_factory()).compile(dialect=dialect)).lower().split())
        assert 'create unique index uq_biblical_texts_translation_book_chapter_verse' in ddl
        assert "coalesce(translation, '')" in ddl
        assert '(book, chapter, verse)' in ddl or ', book, chapter, verse)' in ddl


def test_migration_succeeds_without_the_legacy_biblical_texts_table(tmp_path):
    config = _alembic_config(tmp_path / 'absent.db')

    command.upgrade(config, REVISION)
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    assert INGEST_TABLES <= set(inspect(engine).get_table_names())
    command.downgrade(config, '0006_ethiopian_library')
    command.upgrade(config, REVISION)


def test_migration_adds_the_named_legacy_unique_index_when_rows_are_clean(tmp_path):
    config = _alembic_config(tmp_path / 'clean.db')
    command.upgrade(config, '0006_ethiopian_library')
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    _create_legacy_biblical_texts(engine)

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        index_sql = connection.scalar(__import__('sqlalchemy').text(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = "
            "'uq_biblical_texts_translation_book_chapter_verse'"
        ))
    normalized_index_sql = ' '.join(index_sql.lower().split())
    assert 'create unique index uq_biblical_texts_translation_book_chapter_verse' in normalized_index_sql
    assert "coalesce(translation, '')" in normalized_index_sql

    command.downgrade(config, '0006_ethiopian_library')
    with engine.connect() as connection:
        assert connection.scalar(__import__('sqlalchemy').text(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = "
            "'uq_biblical_texts_translation_book_chapter_verse'"
        )) == 0


def test_migration_rejects_duplicate_legacy_verses_without_deleting_rows(tmp_path):
    config = _alembic_config(tmp_path / 'duplicates.db')
    command.upgrade(config, '0006_ethiopian_library')
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    legacy = _create_legacy_biblical_texts(engine)
    with engine.begin() as connection:
        connection.execute(legacy.insert(), [
            {'translation': 'KJV', 'book': 'Genesis', 'chapter': 1, 'verse': 1},
            {'translation': 'KJV', 'book': 'Genesis', 'chapter': 1, 'verse': 1},
        ])

    with pytest.raises(RuntimeError, match=r'KJV.*Genesis.*1.*1.*2'):
        command.upgrade(config, REVISION)

    with engine.connect() as connection:
        assert connection.scalar(select(__import__('sqlalchemy').func.count()).select_from(legacy)) == 2


def test_legacy_index_rejects_duplicate_null_translation_after_migration(tmp_path):
    config = _alembic_config(tmp_path / 'null-identity.db')
    command.upgrade(config, '0006_ethiopian_library')
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    legacy = _create_legacy_biblical_texts(engine)
    verse = {'translation': None, 'book': 'Genesis', 'chapter': 1, 'verse': 1}
    with engine.begin() as connection:
        connection.execute(legacy.insert(), verse)

    command.upgrade(config, REVISION)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(legacy.insert(), verse)


def test_migration_rejects_duplicate_null_translation_without_deleting_rows(tmp_path):
    config = _alembic_config(tmp_path / 'duplicate-null-identity.db')
    command.upgrade(config, '0006_ethiopian_library')
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    legacy = _create_legacy_biblical_texts(engine)
    verse = {'translation': None, 'book': 'Genesis', 'chapter': 1, 'verse': 1}
    with engine.begin() as connection:
        connection.execute(legacy.insert(), [verse, verse])

    with pytest.raises(RuntimeError, match=r"''.*Genesis.*1.*1.*2"):
        command.upgrade(config, REVISION)

    with engine.connect() as connection:
        assert connection.scalar(select(__import__('sqlalchemy').func.count()).select_from(legacy)) == 2


def test_migration_matches_model_schema(test_settings, tmp_path):
    application = create_application(test_settings)
    model_inspector = inspect(application.state.database_engine)
    config = _alembic_config(tmp_path / 'parity.db')
    command.upgrade(config, REVISION)
    migrated_inspector = inspect(__import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url')))

    for table in INGEST_TABLES:
        assert _column_signatures(migrated_inspector, table) == _column_signatures(
            model_inspector, table
        )
        assert {item['name'] for item in migrated_inspector.get_check_constraints(table)} == {
            item['name'] for item in model_inspector.get_check_constraints(table)
        }
        assert _unique_signatures(migrated_inspector, table) == _unique_signatures(
            model_inspector, table
        )
        assert _foreign_key_signatures(migrated_inspector, table) == _foreign_key_signatures(
            model_inspector, table
        )
        assert _index_signatures(migrated_inspector, table) == _index_signatures(
            model_inspector, table
        )


def _column_signatures(inspector, table):
    return {
        column['name']: (
            str(column['type']).lower(),
            column['nullable'],
            None if column.get('default') is None else str(column['default']).lower(),
        )
        for column in inspector.get_columns(table)
    }


def _unique_signatures(inspector, table):
    return {
        (item['name'], tuple(item['column_names']))
        for item in inspector.get_unique_constraints(table)
    }


def _foreign_key_signatures(inspector, table):
    return {
        (
            item['name'],
            tuple(item['constrained_columns']),
            item['referred_table'],
            tuple(item['referred_columns']),
            item['options'].get('ondelete'),
        )
        for item in inspector.get_foreign_keys(table)
    }


def _index_signatures(inspector, table):
    signatures = set()
    for item in inspector.get_indexes(table):
        dialect_options = item.get('dialect_options', {})
        predicate = dialect_options.get('sqlite_where')
        if predicate is None:
            predicate = dialect_options.get('postgresql_where')
        signatures.add((
            item['name'],
            tuple(item['column_names']),
            bool(item['unique']),
            None if predicate is None else ' '.join(str(predicate).lower().split()),
        ))
    return signatures
