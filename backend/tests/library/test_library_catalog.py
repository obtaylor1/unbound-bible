from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.application import create_application
from app.config import Settings
from app.database import Base, create_database_engine
from app.library.canon import (
    ALIASES,
    ETHIOPIAN_CANON,
    SUPPLEMENTAL_LIBRARY_WORKS,
    WORKS,
    alias_target,
)
from app.library.models import CanonEntry, CanonEntryWork, LibraryWork, LibraryWorkAlias
from app.library.seed import seed_ethiopian_canon


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


def test_test_startup_seeds_the_complete_ethiopian_catalog_only(test_settings, tmp_path):
    application = create_application(test_settings)

    with application.state.session_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(CanonEntry).where(CanonEntry.canon_code == 'ETHIO81')
        ) == 81

    development_settings = test_settings.model_copy(update={
        'environment': 'development',
        'database_url': f'sqlite:///{tmp_path / "development.db"}',
    })
    development_application = create_application(development_settings)
    Base.metadata.create_all(development_application.state.database_engine)
    with development_application.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CanonEntry)) == 0


def test_seed_ethiopian_canon_is_idempotent_and_persists_navigation_metadata(test_settings):
    application = create_application(test_settings)

    with application.state.session_factory() as session:
        first = seed_ethiopian_canon(session)
        genesis_id = session.scalar(
            select(CanonEntry.id).where(
                CanonEntry.canon_code == 'ETHIO81',
                CanonEntry.testament == 'OT',
                CanonEntry.canonical_order == 1,
            )
        )
        second = seed_ethiopian_canon(session)

        entries = session.scalars(
            select(CanonEntry)
            .where(CanonEntry.canon_code == 'ETHIO81')
            .order_by(CanonEntry.testament, CanonEntry.canonical_order)
        ).all()
        entry_work_pairs = session.execute(
            select(CanonEntry.testament, CanonEntry.canonical_order, CanonEntryWork.work_id)
            .join(CanonEntryWork, CanonEntryWork.canon_entry_id == CanonEntry.id)
            .where(CanonEntry.canon_code == 'ETHIO81')
            .order_by(CanonEntry.testament, CanonEntry.canonical_order, CanonEntryWork.work_id)
        ).all()

        assert first.old_testament_count == second.old_testament_count == 46
        assert first.new_testament_count == second.new_testament_count == 35
        assert first.entry_count == second.entry_count == 81
        assert first.navigation_work_count == second.navigation_work_count == len(WORKS)
        assert len(entries) == 81
        assert sum(entry.testament == 'OT' for entry in entries) == 46
        assert sum(entry.testament == 'NT' for entry in entries) == 35
        genesis = next(entry for entry in entries if entry.testament == 'OT' and entry.canonical_order == 1)
        assert genesis.title == 'Genesis'
        assert genesis.id == genesis_id
        expected_entry_work_pairs = sorted(
            (entry.testament, entry.order, work_id)
            for entry in ETHIOPIAN_CANON
            for work_id in entry.work_ids
        )
        assert [tuple(pair) for pair in entry_work_pairs] == expected_entry_work_pairs
        assert len(entry_work_pairs) == len(WORKS)
        assert session.scalar(
            select(LibraryWorkAlias.work_id).where(LibraryWorkAlias.alias == 'book of josephus')
        ) == alias_target('Book of Josephus') == 'josippon'
        seeded_work_ids = {work.id for work in (*WORKS, *SUPPLEMENTAL_LIBRARY_WORKS)}
        persisted_work_ids = set(session.scalars(select(LibraryWork.id)))
        assert persisted_work_ids >= seeded_work_ids
        assert session.scalar(
            select(LibraryWorkAlias.work_id).where(LibraryWorkAlias.alias == 'i maccabees')
        ) == '1-maccabees'
        assert set(ALIASES.values()) - seeded_work_ids
        assert not (
            persisted_work_ids
            & (set(ALIASES.values()) - seeded_work_ids)
        )


def test_seed_ethiopian_canon_reconciles_its_catalog_and_rolls_back_failures(test_settings, monkeypatch):
    application = create_application(test_settings)

    with application.state.session_factory() as session:
        genesis_id = session.scalar(
            select(CanonEntry.id).where(
                CanonEntry.canon_code == 'ETHIO81',
                CanonEntry.testament == 'OT',
                CanonEntry.canonical_order == 1,
            )
        )
        session.add_all((
            LibraryWork(id='unrelated-work', title='Unrelated work'),
            CanonEntry(
                canon_code='OTHER', testament='OT', canonical_order=1, title='Unrelated canon entry',
            ),
            CanonEntry(canon_code='ETHIO81', testament='OT', canonical_order=99, title='Stale entry'),
        ))
        session.flush()
        other_entry_id = session.scalar(
            select(CanonEntry.id).where(CanonEntry.canon_code == 'OTHER')
        )
        stale_entry_id = session.scalar(
            select(CanonEntry.id).where(
                CanonEntry.canon_code == 'ETHIO81', CanonEntry.canonical_order == 99
            )
        )
        session.add(CanonEntryWork(canon_entry_id=other_entry_id, work_id='unrelated-work'))
        session.add(CanonEntryWork(canon_entry_id=stale_entry_id, work_id='unrelated-work'))
        session.commit()

        seed_ethiopian_canon(session)
        assert session.get(CanonEntry, stale_entry_id) is None
        assert session.get(CanonEntry, other_entry_id).title == 'Unrelated canon entry'
        assert session.get(CanonEntryWork, (other_entry_id, 'unrelated-work')) is not None
        assert session.get(CanonEntry, genesis_id).title == 'Genesis'

        session.get(LibraryWork, 'genesis').title = 'Incorrect title'
        session.commit()

    import app.library.seed as seed_module

    def force_failure(*_args, **_kwargs):
        raise RuntimeError('forced seed failure')

    monkeypatch.setattr(seed_module, '_sync_entries', force_failure)
    with application.state.session_factory() as session:
        with pytest.raises(RuntimeError, match='forced seed failure'):
            seed_ethiopian_canon(session)

    with application.state.session_factory() as session:
        assert session.get(LibraryWork, 'genesis').title == 'Incorrect title'


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
            {'id': 'cascade-work', 'title': 'Cascade work'},
        )
        connection.execute(
            LibraryWorkAlias.__table__.insert(),
            {'alias': 'Cascade alias', 'work_id': 'cascade-work'},
        )
        canon_entry_id = connection.execute(
            CanonEntry.__table__.insert(),
            {
                'canon_code': 'cascade-canon',
                'testament': 'OT',
                'canonical_order': 1,
                'title': 'Cascade entry',
            },
        ).inserted_primary_key[0]
        connection.execute(
            CanonEntryWork.__table__.insert(),
            {'canon_entry_id': canon_entry_id, 'work_id': 'cascade-work'},
        )

        connection.execute(delete(LibraryWork).where(LibraryWork.id == 'cascade-work'))

        assert connection.execute(
            select(LibraryWorkAlias).where(LibraryWorkAlias.work_id == 'cascade-work')
        ).all() == []
        assert connection.execute(
            select(CanonEntryWork).where(CanonEntryWork.canon_entry_id == canon_entry_id)
        ).all() == []


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
