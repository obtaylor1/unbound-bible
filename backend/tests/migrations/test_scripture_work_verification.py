import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REVISION = '0011_scripture_work_verification'
PREVIOUS_REVISION = '0010_merge_platform_composite'
VERIFICATION_STATUSES = (
    'in_progress',
    'verified_exact',
    'verified_formatting',
    'verified_rebuilt',
    'review_required',
)
EVIDENCE_COLUMNS = {
    'source_edition',
    'source_revision',
    'rights_url',
    'rights_jurisdiction',
    'artifact_filename',
    'artifact_retrieved_at',
    'artifact_size',
    'artifact_sha256',
    'parser_version',
    'transformations',
    'comparison_exact',
    'comparison_formatting',
    'comparison_missing',
    'comparison_extra',
    'comparison_wording',
    'comparison_report_sha256',
    'reviewer',
    'reviewed_at',
    'review_note',
}
NEW_CHECKS = {
    'ck_edition_work_sources_verification_status',
    'ck_edition_work_sources_canon_scope',
    'ck_edition_work_sources_comparison_exact_nonnegative',
    'ck_edition_work_sources_comparison_formatting_nonnegative',
    'ck_edition_work_sources_comparison_missing_nonnegative',
    'ck_edition_work_sources_comparison_extra_nonnegative',
    'ck_edition_work_sources_comparison_wording_nonnegative',
    'ck_edition_work_sources_artifact_size_nonnegative',
    'ck_edition_work_sources_artifact_sha256_length',
    'ck_edition_work_sources_comparison_report_sha256_length',
}


@pytest.fixture
def sqlite_foreign_keys():
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute('PRAGMA foreign_keys=ON')

    event.listen(Engine, 'connect', enable_foreign_keys)
    try:
        yield
    finally:
        event.remove(Engine, 'connect', enable_foreign_keys)


def _alembic_config(database_path: Path) -> Config:
    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_ROOT / 'alembic'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database_path}')
    return config


def _seed_legacy_sources(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO library_works (id, title) VALUES
                ('status-in-progress', 'In Progress'),
                ('status-exact', 'Exact'),
                ('status-formatting', 'Formatting'),
                ('status-rebuilt', 'Rebuilt'),
                ('status-review', 'Review')
        """))
        connection.execute(text("""
            INSERT INTO text_editions (
                edition_code, name, reading_language, source_language, script,
                relationship, expected_coverage, verification_status
            ) VALUES (
                'VERIFY', 'Verification Test', 'eng', 'gez', 'Latin',
                'general_reading', '{}', 'verified'
            )
        """))
        connection.execute(text("""
            INSERT INTO edition_work_sources (
                edition_code, work_id, source_key, source_label, source_language,
                source_tradition, license_spdx, attribution, verification_status, canon_scope
            ) VALUES
                ('VERIFY', 'status-in-progress', 'in-progress', 'In Progress', 'eng',
                 'Test', 'CC0-1.0', 'Test', 'provisional', 'ethio81'),
                ('VERIFY', 'status-exact', 'exact', 'Exact', 'eng',
                 'Test', 'CC0-1.0', 'Test', 'verified', 'ethio81')
        """))


def _insert_source(connection, work_id: str, status: str) -> None:
    connection.execute(
        text("""
            INSERT INTO edition_work_sources (
                edition_code, work_id, source_key, source_label, source_language,
                source_tradition, license_spdx, attribution, verification_status, canon_scope
            ) VALUES (
                'VERIFY', :work_id, :work_id, :work_id, 'eng',
                'Test', 'CC0-1.0', 'Test', :status, 'ethio81'
            )
        """),
        {'work_id': work_id, 'status': status},
    )


def _assert_preexisting_table_relationships_are_preserved(inspector) -> None:
    assert inspector.get_unique_constraints('edition_work_sources') == [{
        'name': 'uq_edition_work_sources_edition_work',
        'column_names': ['edition_code', 'work_id'],
    }]
    assert inspector.get_indexes('edition_work_sources') == [{
        'name': 'ix_edition_work_sources_work_id',
        'column_names': ['work_id'],
        'unique': 0,
        'dialect_options': {},
    }]
    foreign_keys = {
        (
            tuple(item['constrained_columns']),
            item['referred_table'],
            tuple(item['referred_columns']),
            item['options'].get('ondelete'),
        )
        for item in inspector.get_foreign_keys('edition_work_sources')
    }
    assert foreign_keys == {
        (('edition_code',), 'text_editions', ('edition_code',), 'CASCADE'),
        (('work_id',), 'library_works', ('id',), 'CASCADE'),
    }


def test_revision_follows_merge_head() -> None:
    scripts = ScriptDirectory.from_config(_alembic_config(Path('unused.db')))
    revision = scripts.get_revision(REVISION)

    assert revision is not None
    assert revision.down_revision == PREVIOUS_REVISION


def test_upgrade_maps_legacy_statuses_and_installs_evidence_contract(
    tmp_path, sqlite_foreign_keys
) -> None:
    config = _alembic_config(tmp_path / 'scripture-work-verification.db')
    command.upgrade(config, PREVIOUS_REVISION)
    engine = create_engine(config.get_main_option('sqlalchemy.url'))
    _seed_legacy_sources(engine)

    command.upgrade(config, REVISION)

    inspector = inspect(engine)
    _assert_preexisting_table_relationships_are_preserved(inspector)
    columns = {column['name']: column for column in inspector.get_columns('edition_work_sources')}
    assert EVIDENCE_COLUMNS <= columns.keys()
    assert {name for name in EVIDENCE_COLUMNS if columns[name]['nullable']} == {
        'source_edition', 'source_revision', 'rights_url', 'rights_jurisdiction',
        'artifact_filename', 'artifact_retrieved_at', 'artifact_size', 'artifact_sha256',
        'parser_version', 'comparison_report_sha256', 'reviewer', 'reviewed_at', 'review_note',
    }
    assert {
        item['name'] for item in inspector.get_check_constraints('edition_work_sources')
    } == NEW_CHECKS
    status_check = next(
        item['sqltext']
        for item in inspector.get_check_constraints('edition_work_sources')
        if item['name'] == 'ck_edition_work_sources_verification_status'
    )
    assert set(re.findall(r"'([^']+)'", status_check)) == set(VERIFICATION_STATUSES)
    with engine.connect() as connection:
        assert connection.execute(text("""
            SELECT work_id, verification_status, transformations,
                   comparison_exact, comparison_formatting, comparison_missing,
                   comparison_extra, comparison_wording
            FROM edition_work_sources
            WHERE edition_code = 'VERIFY'
            ORDER BY work_id
        """)).all() == [
            ('status-exact', 'verified_exact', '[]', 0, 0, 0, 0, 0),
            ('status-in-progress', 'in_progress', '[]', 0, 0, 0, 0, 0),
        ]


def test_upgrade_enforces_all_new_checks(tmp_path, sqlite_foreign_keys) -> None:
    config = _alembic_config(tmp_path / 'scripture-work-constraints.db')
    command.upgrade(config, PREVIOUS_REVISION)
    engine = create_engine(config.get_main_option('sqlalchemy.url'))
    _seed_legacy_sources(engine)
    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        connection.execute(
            text("""
                UPDATE edition_work_sources
                SET artifact_size = 0,
                    artifact_sha256 = :artifact_sha256,
                    comparison_report_sha256 = :report_sha256
                WHERE work_id = 'status-in-progress'
            """),
            {'artifact_sha256': 'a' * 64, 'report_sha256': 'b' * 64},
        )
        for status in VERIFICATION_STATUSES:
            connection.execute(
                text("""
                    UPDATE edition_work_sources SET verification_status = :status
                    WHERE work_id = 'status-in-progress'
                """),
                {'status': status},
            )
        invalid_updates = (
            ("verification_status = 'verified'", {}),
            ('comparison_exact = -1', {}),
            ('comparison_formatting = -1', {}),
            ('comparison_missing = -1', {}),
            ('comparison_extra = -1', {}),
            ('comparison_wording = -1', {}),
            ('artifact_size = -1', {}),
            ('artifact_sha256 = :value', {'value': 'a' * 63}),
            ('comparison_report_sha256 = :value', {'value': 'b' * 65}),
        )
        for assignment, parameters in invalid_updates:
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text(f"""
                        UPDATE edition_work_sources SET {assignment}
                        WHERE work_id = 'status-in-progress'
                    """),
                    parameters,
                )


def test_downgrade_maps_every_new_status_and_removes_evidence_columns(
    tmp_path, sqlite_foreign_keys
) -> None:
    config = _alembic_config(tmp_path / 'scripture-work-downgrade.db')
    command.upgrade(config, PREVIOUS_REVISION)
    engine = create_engine(config.get_main_option('sqlalchemy.url'))
    _seed_legacy_sources(engine)
    command.upgrade(config, REVISION)
    with engine.begin() as connection:
        _insert_source(connection, 'status-formatting', 'verified_formatting')
        _insert_source(connection, 'status-rebuilt', 'verified_rebuilt')
        _insert_source(connection, 'status-review', 'review_required')

    command.downgrade(config, PREVIOUS_REVISION)

    inspector = inspect(engine)
    _assert_preexisting_table_relationships_are_preserved(inspector)
    assert not EVIDENCE_COLUMNS & {
        column['name'] for column in inspector.get_columns('edition_work_sources')
    }
    assert {
        item['name'] for item in inspector.get_check_constraints('edition_work_sources')
    } == {
        'ck_edition_work_sources_verification_status',
        'ck_edition_work_sources_canon_scope',
    }
    status_check = next(
        item['sqltext']
        for item in inspector.get_check_constraints('edition_work_sources')
        if item['name'] == 'ck_edition_work_sources_verification_status'
    )
    assert "'provisional'" in status_check
    assert "'verified'" in status_check
    assert all(status not in status_check for status in VERIFICATION_STATUSES)
    with engine.connect() as connection:
        assert connection.execute(text("""
            SELECT work_id, verification_status
            FROM edition_work_sources
            WHERE edition_code = 'VERIFY'
            ORDER BY work_id
        """)).all() == [
            ('status-exact', 'verified'),
            ('status-formatting', 'verified'),
            ('status-in-progress', 'provisional'),
            ('status-rebuilt', 'verified'),
            ('status-review', 'provisional'),
        ]
        with pytest.raises(IntegrityError):
            connection.execute(text("""
                UPDATE edition_work_sources SET verification_status = 'in_progress'
                WHERE work_id = 'status-in-progress'
            """))
