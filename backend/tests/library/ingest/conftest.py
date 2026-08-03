from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.application import create_application
from app.library.models import TextEdition


@pytest.fixture
def ingest_session(test_settings):
    application = create_application(test_settings)
    session = application.state.session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def make_ingest_run(session, edition_code, text, status='verified', finding=None):
    from app.library.ingest.models import (
        ScriptureIngestRun,
        ScriptureValidationFinding,
        StagedScriptureVerse,
    )
    from app.library.ingest.types import row_checksum

    if session.get(TextEdition, edition_code) is None:
        session.add(TextEdition(
            edition_code=edition_code,
            name=f'{edition_code} test edition',
            reading_language='English',
            source_language='Hebrew/Greek',
            script='Latin',
            relationship='general_reading',
            expected_coverage={},
            verification_status='verified',
        ))
        session.flush()

    source_checksum = sha256(f'{edition_code}:{text}'.encode()).hexdigest()
    manifest_snapshot = {
        'edition_code': edition_code,
        'name': f'{edition_code} test edition',
        'reading_language': 'English',
        'source_language': 'Hebrew/Greek',
        'script': 'Latin',
        'translator': None,
        'publisher': None,
        'published_year': None,
        'license_spdx': 'LicenseRef-Public-Domain',
        'attribution': 'Test fixture source.',
        'provenance_url': 'https://example.org/test-source',
        'source_tradition': 'Test tradition',
        'relationship': 'general_reading',
        'versification': 'Test',
        'expected_works': {'genesis': {'chapters': 1, 'verse_counts': {'1': 1}}},
        'source_files': [{
            'path': 'genesis.usfm',
            'sha256': source_checksum,
            'source_url': 'https://example.org/genesis.usfm',
        }],
        'adapter': 'usfm',
        'adapter_options': {},
    }
    run = ScriptureIngestRun(
        id=uuid4(),
        edition_code=edition_code,
        source_checksum=source_checksum,
        manifest_snapshot=manifest_snapshot,
        status=status,
        error_count=1 if finding is not None and finding['severity'] == 'error' else 0,
        warning_count=1 if finding is not None and finding['severity'] == 'warning' else 0,
    )
    session.add(run)
    session.flush()
    session.add(StagedScriptureVerse(
        run_id=run.id,
        work_id='genesis',
        source_book='Genesis',
        chapter=1,
        verse=1,
        normalized_text=text,
        source_locator='genesis.usfm:1:1',
        row_checksum=row_checksum(
            'genesis', 'Genesis', 1, 1, text, 'genesis.usfm:1:1'
        ),
    ))
    if finding is not None:
        session.add(ScriptureValidationFinding(run_id=run.id, **finding))
    session.flush()
    return run
