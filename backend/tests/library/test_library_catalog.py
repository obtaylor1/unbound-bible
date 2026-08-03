from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError

from app.application import create_application
from app.config import Settings
from app.database import create_database_engine
from app.library.models import CanonEntry, CanonEntryWork, LibraryWork, LibraryWorkAlias


BACKEND_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_TABLES = {
    'library_works',
    'library_work_aliases',
    'canon_entries',
    'canon_entry_works',
    'text_editions',
    'edition_coverage',
}


def test_application_registers_scripture_library_tables(test_settings):
    application = create_application(test_settings)
    table_names = set(inspect(application.state.database_engine).get_table_names())

    assert LIBRARY_TABLES <= table_names


def test_library_catalog_schema_exposes_catalog_and_edition_metadata(test_settings):
    application = create_application(test_settings)
    inspector = inspect(application.state.database_engine)

    assert {
        'id',
        'title',
    } <= {column['name'] for column in inspector.get_columns('library_works')}
    assert {'alias', 'work_id'} <= {
        column['name'] for column in inspector.get_columns('library_work_aliases')
    }
    assert {'canon_code', 'testament', 'canonical_order'} <= {
        column['name'] for column in inspector.get_columns('canon_entries')
    }
    assert {
        'edition_code',
        'name',
        'reading_language',
        'source_language',
        'script',
        'translator',
        'publisher',
        'published_year',
        'license_spdx',
        'attribution',
        'provenance_url',
        'source_tradition',
        'relationship',
        'versification',
        'expected_coverage',
        'verification_status',
        'source_checksum',
    } <= {column['name'] for column in inspector.get_columns('text_editions')}
    assert {'edition_code', 'work_id', 'status', 'chapter_count', 'verse_count', 'note'} <= {
        column['name'] for column in inspector.get_columns('edition_coverage')
    }


def test_library_catalog_schema_enforces_uniqueness_foreign_keys_and_statuses(test_settings):
    application = create_application(test_settings)
    inspector = inspect(application.state.database_engine)

    alias_uniques = inspector.get_unique_constraints('library_work_aliases')
    assert any(constraint['column_names'] == ['alias'] for constraint in alias_uniques)
    canon_uniques = inspector.get_unique_constraints('canon_entries')
    assert any(
        constraint['column_names'] == ['canon_code', 'testament', 'canonical_order']
        for constraint in canon_uniques
    )
    coverage_uniques = inspector.get_unique_constraints('edition_coverage')
    assert any(
        constraint['column_names'] == ['edition_code', 'work_id']
        for constraint in coverage_uniques
    )
    assert {foreign_key['referred_table'] for foreign_key in inspector.get_foreign_keys('edition_coverage')} == {
        'library_works',
        'text_editions',
    }
    edition_checks = {constraint['name']: constraint['sqltext'] for constraint in inspector.get_check_constraints('text_editions')}
    assert set(edition_checks) >= {
        'ck_text_editions_relationship',
        'ck_text_editions_verification_status',
    }
    assert "'queued'" in edition_checks['ck_text_editions_verification_status']
    assert "'exact_ethiopian'" in edition_checks['ck_text_editions_relationship']
    coverage_checks = {constraint['name']: constraint['sqltext'] for constraint in inspector.get_check_constraints('edition_coverage')}
    assert "'translation_needed'" in coverage_checks['ck_edition_coverage_status']


def test_sqlite_rejects_orphaned_library_rows(test_settings):
    application = create_application(test_settings)

    with pytest.raises(IntegrityError):
        with application.state.database_engine.begin() as connection:
            connection.execute(
                LibraryWorkAlias.__table__.insert(),
                {'alias': 'Orphaned alias', 'work_id': 'missing-work'},
            )


def test_deleting_a_work_cascades_to_dependent_rows(test_settings):
    application = create_application(test_settings)

    with application.state.database_engine.begin() as connection:
        connection.execute(
            LibraryWork.__table__.insert(),
            {'id': 'genesis', 'title': 'Genesis'},
        )
        connection.execute(
            LibraryWorkAlias.__table__.insert(),
            {'alias': 'Book of Genesis', 'work_id': 'genesis'},
        )
        canon_entry_id = connection.execute(
            CanonEntry.__table__.insert(),
            {
                'canon_code': 'ethiopian-orthodox',
                'testament': 'OT',
                'canonical_order': 1,
                'title': 'Genesis',
            },
        ).inserted_primary_key[0]
        connection.execute(
            CanonEntryWork.__table__.insert(),
            {'canon_entry_id': canon_entry_id, 'work_id': 'genesis'},
        )

        connection.execute(delete(LibraryWork).where(LibraryWork.id == 'genesis'))

        assert connection.execute(select(LibraryWorkAlias)).all() == []
        assert connection.execute(select(CanonEntryWork)).all() == []


def test_library_migration_round_trips_on_fresh_sqlite_database(tmp_path):
    database_path = tmp_path / 'library-migration.db'
    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database_path}')

    command.upgrade(config, '0006_ethiopian_library_foundation')
    assert LIBRARY_TABLES <= migration_table_names(database_path)

    command.downgrade(config, '0005_community_migration')
    assert not LIBRARY_TABLES & migration_table_names(database_path)

    command.upgrade(config, 'head')
    assert LIBRARY_TABLES <= migration_table_names(database_path)


def migration_table_names(database_path: Path) -> set[str]:
    database_engine = create_database_engine(
        Settings(database_url=f'sqlite:///{database_path}', environment='test')
    )
    try:
        return set(inspect(database_engine).get_table_names())
    finally:
        database_engine.dispose()
