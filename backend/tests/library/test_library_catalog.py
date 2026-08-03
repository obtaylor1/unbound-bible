from sqlalchemy import inspect

from app.application import create_application


def test_application_registers_scripture_library_tables(test_settings):
    application = create_application(test_settings)
    table_names = set(inspect(application.state.database_engine).get_table_names())

    assert {
        'library_works',
        'library_work_aliases',
        'canon_entries',
        'canon_entry_works',
        'text_editions',
        'edition_coverage',
    } <= table_names


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
