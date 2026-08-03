import importlib.util
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, Column, Integer, String, delete, inspect, select
from sqlalchemy.exc import IntegrityError

from app.application import create_application
from app.database import Base
from app.library.models import TextEdition

from .conftest import make_ingest_run


MODELS_AVAILABLE = importlib.util.find_spec('app.library.ingest.models') is not None
pytestmark = pytest.mark.skipif(not MODELS_AVAILABLE, reason='verified ingestion models are not implemented yet')

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REVISION = '0007_verified_scripture_ingestion'
INGEST_TABLES = {
    'scripture_ingest_runs',
    'staged_scripture_verses',
    'scripture_validation_findings',
    'scripture_publications',
}


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

    uniques = {item['name'] for item in inspector.get_unique_constraints('staged_scripture_verses')}
    assert 'uq_staged_scripture_verses_run_work_chapter_verse' in uniques
    assert 'uq_scripture_publications_edition_version' in {
        item['name'] for item in inspector.get_unique_constraints('scripture_publications')
    }
    assert {item['name'] for item in inspector.get_indexes('staged_scripture_verses')} >= {
        'ix_staged_scripture_verses_run_id', 'ix_staged_scripture_verses_work_id',
        'ix_staged_scripture_verses_row_checksum',
    }
    assert 'uq_scripture_publications_active_edition' in {
        item['name'] for item in inspector.get_indexes('scripture_publications')
    }
    assert {item['referred_table'] for item in inspector.get_foreign_keys('staged_scripture_verses')} == {
        'scripture_ingest_runs', 'library_works'
    }
    assert {item['referred_table'] for item in inspector.get_foreign_keys('scripture_publications')} == {
        'text_editions', 'scripture_ingest_runs'
    }


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


def _alembic_config(database_path):
    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_ROOT / 'alembic'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database_path}')
    return config


def _create_legacy_biblical_texts(engine):
    table = Table(
        'biblical_texts', MetaData(),
        Column('id', Integer, primary_key=True),
        Column('translation', String(100), nullable=False),
        Column('book', String(100), nullable=False),
        Column('chapter', Integer, nullable=False),
        Column('verse', Integer, nullable=False),
    )
    table.create(engine)
    return table


def test_migration_succeeds_without_the_legacy_biblical_texts_table(tmp_path):
    config = _alembic_config(tmp_path / 'absent.db')

    command.upgrade(config, REVISION)
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    assert INGEST_TABLES <= set(inspect(engine).get_table_names())
    command.downgrade(config, '0006_ethiopian_library_foundation')
    command.upgrade(config, REVISION)


def test_migration_adds_the_named_legacy_unique_index_when_rows_are_clean(tmp_path):
    config = _alembic_config(tmp_path / 'clean.db')
    command.upgrade(config, '0006_ethiopian_library_foundation')
    engine = __import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url'))
    _create_legacy_biblical_texts(engine)

    command.upgrade(config, REVISION)

    legacy_indexes = {index['name']: index for index in inspect(engine).get_indexes('biblical_texts')}
    assert legacy_indexes['uq_biblical_texts_translation_book_chapter_verse']['unique']
    assert legacy_indexes['uq_biblical_texts_translation_book_chapter_verse']['column_names'] == [
        'translation', 'book', 'chapter', 'verse'
    ]


def test_migration_rejects_duplicate_legacy_verses_without_deleting_rows(tmp_path):
    config = _alembic_config(tmp_path / 'duplicates.db')
    command.upgrade(config, '0006_ethiopian_library_foundation')
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


def test_migration_matches_model_schema(test_settings, tmp_path):
    application = create_application(test_settings)
    model_inspector = inspect(application.state.database_engine)
    config = _alembic_config(tmp_path / 'parity.db')
    command.upgrade(config, REVISION)
    migrated_inspector = inspect(__import__('sqlalchemy').create_engine(config.get_main_option('sqlalchemy.url')))

    for table in INGEST_TABLES:
        assert {column['name'] for column in migrated_inspector.get_columns(table)} == {
            column['name'] for column in model_inspector.get_columns(table)
        }
        assert {item['name'] for item in migrated_inspector.get_check_constraints(table)} == {
            item['name'] for item in model_inspector.get_check_constraints(table)
        }
        assert {item['name'] for item in migrated_inspector.get_indexes(table)} == {
            item['name'] for item in model_inspector.get_indexes(table)
        }
