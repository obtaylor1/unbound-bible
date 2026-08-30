import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner


BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_ROOT.parent
FIXTURE_ROOT = Path(__file__).parent / 'fixtures' / 'quality_gate'
COMPOSITE_ROOT = BACKEND_ROOT / 'data' / 'scripture' / 'eotc-composite-en'
COMPOSITE_MANIFEST = COMPOSITE_ROOT / 'manifest.json'
COMPOSITE_RELEASE_GUIDE = REPOSITORY_ROOT / 'docs' / 'source-verification' / 'eotc-composite-en.md'
MANIFESTS = (
    FIXTURE_ROOT / 'manifest-v1.json',
    FIXTURE_ROOT / 'manifest-v2.json',
)
runner = CliRunner()


def test_reviewed_composite_release_contract_is_exact_and_truthful():
    manifest = json.loads(COMPOSITE_MANIFEST.read_text(encoding='utf-8'))
    assert manifest['name'] == 'Ethiopian Canon Research Collection — Mixed-source English'
    sources = manifest['adapter_options']['work_sources']
    verified = {
        work_id: source for work_id, source in sources.items()
        if source['verification_status'].startswith('verified_')
    }
    pending = {
        work_id: source for work_id, source in sources.items()
        if source['verification_status'] == 'in_progress'
    }

    assert len(sources) == 83
    assert len(verified) == 73
    assert len(pending) == 10
    assert sum(
        source['source_key'] == 'world-messianic-bible'
        for source in verified.values()
    ) == 39
    assert sum(
        source['source_key'] == 'murdock-peshitta-1852'
        for source in verified.values()
    ) == 27
    assert sum(
        source['source_key'] == 'kjv-1611-fallback'
        for source in verified.values()
    ) == 6
    assert verified['jubilees']['source_key'] == 'rh-charles-ethiopic'

    fallback_ids = {
        work_id for work_id, source in sources.items() if source['fallback']
    }
    assert fallback_ids == {
        'baruch', 'letter-of-jeremiah', 'prayer-of-azariah',
        'susanna', 'bel-and-the-dragon', 'prayer-of-manasseh',
    }
    assert all(sources[work_id]['source_key'] == 'kjv-1611-fallback'
               for work_id in fallback_ids)
    assert all(
        source['comparison_missing'] == 0
        and source['comparison_extra'] == 0
        and source['comparison_formatting'] == 0
        and source['comparison_wording'] == 0
        and source['comparison_exact'] > 0
        and len(source['artifact_sha256']) == 64
        and len(source['comparison_report_sha256']) == 64
        and source['reviewer']
        and source['reviewed_at']
        for source in verified.values()
    )
    report_directories = {
        'world-messianic-bible': 'world-messianic-bible',
        'murdock-peshitta-1852': 'murdock-peshitta-1852',
        'kjv-1611-fallback': 'kjv-1611-fallback',
        'rh-charles-ethiopic': 'rh-charles-jubilees-1902',
    }
    publication_sha256 = manifest['source_files'][0]['sha256']
    for work_id, source in verified.items():
        report_path = (
            COMPOSITE_ROOT / 'verification' / 'reports'
            / report_directories[source['source_key']] / f'{work_id}.json'
        )
        assert report_path.is_file()
        assert sha256(report_path.read_bytes()).hexdigest() == (
            source['comparison_report_sha256']
        )
        report = json.loads(report_path.read_text(encoding='utf-8'))
        assert report['work_id'] == work_id
        assert report['current_publication_sha256'] == publication_sha256

    guide = COMPOSITE_RELEASE_GUIDE.read_text(encoding='utf-8')
    readme = (COMPOSITE_ROOT / 'README.md').read_text(encoding='utf-8')
    source_guide = (REPOSITORY_ROOT / 'docs' / 'scripture-sources.md').read_text(
        encoding='utf-8'
    )
    for document in (guide, readme):
        assert 'Ethiopian Canon Research Collection' in document
        assert 'mixed-source English research collection' in document
        assert 'not complete, official, uniform, or ecclesiastically authorized' in document
        assert '39 WMB + 27 Murdock + 6 permanent KJV fallback + 1 Jubilees = 73' in document
    assert 'LIVE_SOURCE_E2E=1 npm run test:e2e' in guide
    assert guide.index("sqlite3 \"$COMPOSITE_DB_DIR/staging.db\"") < guide.index(
        'alembic -c backend/alembic.ini upgrade head'
    )
    for health_gate in (
        '.run_id == $run_id', '.active_run_id == $run_id',
        '.is_active == true', '.status == "published"',
        '.staged_count == 38487', '.published_count == 38487',
        '.errors == 0',
    ):
        assert health_gate in guide
    assert '.inventory.catalog_unavailable_work_ids == [' in guide
    for work_id in (
        'abtilis', 'didesqelya', 'esther-greek-additions', 'gitsew',
        'josippon', 'metsihafe-kidan-1', 'metsihafe-kidan-2',
        'paralipomena-jeremiah', 'psalm-151', 'qalementos',
        'sirate-tsion', 'tegsats', 'tizaz',
    ):
        assert f'"{work_id}"' in guide

    stale_claims = (
        'World Messianic Bible (WMB), user-archive revision',
        'upstream revision is unverified',
        'Retain the provisional archive-revision label',
        'KJV 1611 archive fallback',
        'per-work verification remains provisional',
    )
    for document in (source_guide, readme):
        assert all(claim not in document for claim in stale_claims)
        assert '73 verified' in document
        assert 'World Messianic Bible' in document
        assert 'CrossWire Murdock' in document
        assert 'permanent KJV fallback' in document
        assert 'Jubilees' in document


def _json(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _fixture_adapter(manifest, manifest_directory):
    from app.library.ingest.types import NormalizedVerse

    rows = []
    for source in manifest.source_files:
        source_path = manifest_directory / source.path
        content = source_path.read_bytes()
        assert sha256(content).hexdigest() == source.sha256
        for row in json.loads(content):
            rows.append(NormalizedVerse(**row))
    return tuple(rows)


def _alembic_config(database_path):
    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_ROOT / 'alembic'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database_path}')
    return config


def _create_legacy_biblical_texts(database_path):
    engine = create_engine(f'sqlite:///{database_path}')
    try:
        with engine.begin() as connection:
            connection.execute(text('''
                CREATE TABLE biblical_texts (
                    id INTEGER PRIMARY KEY,
                    book TEXT NOT NULL,
                    chapter INTEGER NOT NULL,
                    verse INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    translation TEXT
                )
            '''))
    finally:
        engine.dispose()


def _previous_composite_manifest(tmp_path):
    tmp_path.mkdir(parents=True)
    current_bundle = COMPOSITE_ROOT / 'corrected-bundle.zip'
    previous_bundle = tmp_path / 'corrected-bundle.zip'
    with ZipFile(current_bundle) as source, ZipFile(
        previous_bundle, 'w', compression=ZIP_DEFLATED,
    ) as destination:
        for source_info in source.infolist():
            content = source.read(source_info.filename)
            if source_info.filename == 'data/gen.json':
                chapters = json.loads(content)
                chapters[0]['v'][0]['t'] = 'Previous reviewed Genesis publication.'
                content = json.dumps(
                    chapters, ensure_ascii=False, separators=(',', ':'),
                ).encode('utf-8')
            destination.writestr(source_info, content)

    manifest = json.loads(COMPOSITE_MANIFEST.read_text(encoding='utf-8'))
    manifest['name'] = 'Ethiopian Canon Research Collection rehearsal predecessor'
    manifest['source_files'][0]['sha256'] = sha256(
        previous_bundle.read_bytes()
    ).hexdigest()
    for source in manifest['adapter_options']['work_sources'].values():
        source['verification_status'] = 'in_progress'
        source['transformations'] = []
        for field_name in (
            'artifact_filename', 'artifact_retrieved_at', 'artifact_size',
            'artifact_sha256', 'parser_version', 'comparison_report_sha256',
            'reviewer', 'reviewed_at', 'review_note',
        ):
            source[field_name] = None
        for field_name in (
            'comparison_exact', 'comparison_formatting', 'comparison_missing',
            'comparison_extra', 'comparison_wording',
        ):
            source[field_name] = 0
    genesis = manifest['adapter_options']['work_sources']['genesis']
    genesis['source_label'] = 'Previous reviewed WMB snapshot'
    genesis['source_revision'] = 'Previous locked WMB revision'
    genesis['modification_note'] = (
        'Synthetic predecessor text used only for isolated rollback rehearsal.'
    )
    previous_manifest = tmp_path / 'manifest.json'
    previous_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    return previous_manifest


def test_clean_migrated_database_supports_full_fixture_publication_lifecycle(
    tmp_path, monkeypatch
):
    from app.library.ingest import cli
    from app.library.ingest.models import ScripturePublication, ScripturePublicationVerse
    from app.library.models import EditionCoverage, TextEdition

    database_path = tmp_path / 'unbound-ingest-e2e.db'
    database_url = f'sqlite:///{database_path}'
    monkeypatch.delenv('DATABASE_URL', raising=False)
    command.upgrade(_alembic_config(database_path), 'head')
    hostile_database_path = tmp_path / 'ambient-database-must-not-be-touched.db'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{hostile_database_path}')

    assert set(cli.ADAPTERS) == {'weahadu_bundle', 'composite_english_bundle'}
    assert callable(cli.ADAPTERS['weahadu_bundle'])
    monkeypatch.setattr(cli, 'ADAPTERS', {'usfm': _fixture_adapter})

    seeded = _json(runner.invoke(cli.app, [
        'seed-canon', '--database-url', database_url,
    ]))
    assert seeded['canon_entries'] == 81

    engine, session_factory = cli._database(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text('''
                INSERT INTO biblical_texts (book, chapter, verse, text, translation)
                VALUES ('Genesis', 1, 1, 'Existing KJV text.', 'KJV')
            '''))

        published_runs = []
        first_snapshot_checksums = None
        for manifest_path in MANIFESTS:
            staged = _json(runner.invoke(cli.app, [
                'stage', '--manifest', str(manifest_path),
                '--database-url', database_url,
            ]))
            validated = _json(runner.invoke(cli.app, [
                'validate', '--run-id', staged['run_id'],
                '--database-url', database_url,
            ]))
            assert validated['errors'] == 0
            published = _json(runner.invoke(cli.app, [
                'publish', '--run-id', staged['run_id'], '--confirm',
                '--database-url', database_url,
            ]))
            assert published['changed'] is True
            assert published['published_count'] == 2
            published_runs.append((staged, published))

            if len(published_runs) == 1:
                repeated = _json(runner.invoke(cli.app, [
                    'publish', '--run-id', staged['run_id'], '--confirm',
                    '--database-url', database_url,
                ]))
                assert repeated['changed'] is False
                assert repeated['run_id'] == staged['run_id']
                assert repeated['publication_version'] == 1

                coverage = _json(runner.invoke(cli.app, [
                    'coverage-report', '--edition', 'PHASE2-FIXTURE',
                    '--database-url', database_url,
                ]))
                assert coverage['run_id'] == staged['run_id']
                assert coverage['checksum'] == staged['checksum']
                assert coverage['status'] == 'published'
                assert coverage['coverage'] == [{
                    'chapter_count': 1,
                    'status': 'verified_english',
                    'verse_count': 2,
                    'work_id': 'genesis',
                }]
                with session_factory() as session:
                    first_publication = session.scalar(select(ScripturePublication).where(
                        ScripturePublication.edition_code == 'PHASE2-FIXTURE',
                        ScripturePublication.active.is_(True),
                    ))
                    first_snapshot_checksums = session.scalars(
                        select(ScripturePublicationVerse.row_checksum).where(
                            ScripturePublicationVerse.publication_id == first_publication.id
                        ).order_by(ScripturePublicationVerse.verse)
                    ).all()
                assert len(first_snapshot_checksums) == 2
                assert all(len(checksum) == 64 for checksum in first_snapshot_checksums)

        first, second = published_runs
        assert first[1]['publication_version'] == 1
        assert second[1]['publication_version'] == 2
        assert first[0]['checksum'] != second[0]['checksum']

        with session_factory() as session:
            version_two_edition = session.get(TextEdition, 'PHASE2-FIXTURE')
            assert (
                version_two_edition.name,
                version_two_edition.publisher,
                version_two_edition.attribution,
                version_two_edition.source_checksum,
            ) == (
                'Phase 2 Quality Gate Fixture v2',
                'Unbound Bible Test Fixtures v2',
                'Committed deterministic Phase 2 fixture version 2.',
                second[0]['checksum'],
            )
            assert session.execute(text('''
                SELECT text FROM biblical_texts
                WHERE translation = 'PHASE2-FIXTURE' AND chapter = 1 AND verse = 1
            ''')).scalar_one() == 'Alpha records the revised verified line.'
            assert session.execute(text('''
                SELECT text FROM biblical_texts
                WHERE translation = 'KJV' AND chapter = 1 AND verse = 1
            ''')).scalar_one() == 'Existing KJV text.'

        rolled_back = _json(runner.invoke(cli.app, [
            'rollback', '--edition', 'PHASE2-FIXTURE',
            '--database-url', database_url,
        ]))
        assert rolled_back['run_id'] == first[0]['run_id']
        assert rolled_back['displaced_run_id'] == second[0]['run_id']
        assert rolled_back['checksum'] == first[0]['checksum']
        assert rolled_back['publication_version'] == 3

        with session_factory() as session:
            legacy_rows = session.execute(text('''
                SELECT translation, book, chapter, verse, text
                FROM biblical_texts
                ORDER BY translation, chapter, verse
            ''')).all()
            assert legacy_rows == [
                ('KJV', 'Genesis', 1, 1, 'Existing KJV text.'),
                ('PHASE2-FIXTURE', 'Genesis', 1, 1, 'Alpha records the first verified line.'),
                ('PHASE2-FIXTURE', 'Genesis', 1, 2, 'Beta records the second verified line.'),
            ]

            edition = session.get(TextEdition, 'PHASE2-FIXTURE')
            assert (
                edition.name,
                edition.publisher,
                edition.attribution,
                edition.source_checksum,
            ) == (
                'Phase 2 Quality Gate Fixture v1',
                'Unbound Bible Test Fixtures v1',
                'Committed deterministic Phase 2 fixture version 1.',
                first[0]['checksum'],
            )

            active = session.scalar(select(ScripturePublication).where(
                ScripturePublication.edition_code == 'PHASE2-FIXTURE',
                ScripturePublication.active.is_(True),
            ))
            assert active.run_id == UUID(first[0]['run_id'])
            snapshot = session.scalars(select(ScripturePublicationVerse).where(
                ScripturePublicationVerse.publication_id == active.id
            ).order_by(ScripturePublicationVerse.verse)).all()
            assert [row.row_checksum for row in snapshot] == first_snapshot_checksums
            coverage = session.scalar(select(EditionCoverage).where(
                EditionCoverage.edition_code == 'PHASE2-FIXTURE',
                EditionCoverage.work_id == 'genesis',
            ))
            assert coverage.note.endswith(f"source checksum {first[0]['checksum']}.")
    finally:
        engine.dispose()
    assert not hostile_database_path.exists()


def test_production_like_composite_staging_rollback_and_republish_rehearsal(
    tmp_path, monkeypatch,
):
    from app.library.ingest import cli
    from app.library.canon import WORKS
    from app.library.models import EditionCoverage, EditionWorkSource

    database_path = tmp_path / 'composite-staging-rehearsal.db'
    database_url = f'sqlite:///{database_path}'
    monkeypatch.delenv('DATABASE_URL', raising=False)
    _create_legacy_biblical_texts(database_path)
    command.upgrade(_alembic_config(database_path), 'head')
    bootstrap_engine, _ = cli._database(database_url)
    try:
        with bootstrap_engine.connect() as connection:
            assert connection.scalar(text('''
                SELECT name FROM sqlite_master
                WHERE type = 'index'
                  AND name = 'uq_biblical_texts_translation_book_chapter_verse'
            ''')) == 'uq_biblical_texts_translation_book_chapter_verse'
        with bootstrap_engine.begin() as connection:
            connection.execute(text('''
                INSERT INTO biblical_texts
                    (book, chapter, verse, text, translation)
                VALUES ('Migration probe', 1, 1, 'First.', 'MIGRATION-PROBE')
            '''))
        with pytest.raises(IntegrityError):
            with bootstrap_engine.begin() as connection:
                connection.execute(text('''
                    INSERT INTO biblical_texts
                        (book, chapter, verse, text, translation)
                    VALUES ('Migration probe', 1, 1, 'Duplicate.', 'MIGRATION-PROBE')
                '''))
    finally:
        bootstrap_engine.dispose()
    _json(runner.invoke(cli.app, [
        'seed-canon', '--database-url', database_url,
    ]))

    previous_manifest = _previous_composite_manifest(tmp_path / 'previous')
    reviewed_text = 'In the beginning, God created the heavens and the earth.'
    unavailable_work_ids = {
        'abtilis', 'didesqelya', 'esther-greek-additions', 'gitsew', 'josippon',
        'metsihafe-kidan-1', 'metsihafe-kidan-2', 'paralipomena-jeremiah',
        'psalm-151', 'qalementos', 'sirate-tsion', 'tegsats', 'tizaz',
    }

    def stage_validate_publish(manifest_path):
        staged = _json(runner.invoke(cli.app, [
            'stage', '--manifest', str(manifest_path),
            '--database-url', database_url,
        ]))
        validated = _json(runner.invoke(cli.app, [
            'validate', '--run-id', staged['run_id'],
            '--database-url', database_url,
        ]))
        assert validated['errors'] == 0
        published = _json(runner.invoke(cli.app, [
            'publish', '--run-id', staged['run_id'], '--confirm',
            '--database-url', database_url,
        ]))
        return staged, published

    previous, previous_publication = stage_validate_publish(previous_manifest)
    reviewed, reviewed_publication = stage_validate_publish(COMPOSITE_MANIFEST)
    assert previous_publication['publication_version'] == 1
    assert reviewed_publication['publication_version'] == 2

    engine, session_factory = cli._database(database_url)
    try:
        def active_genesis():
            with session_factory() as session:
                text_value = session.execute(text('''
                    SELECT text FROM biblical_texts
                    WHERE translation = 'EOTC-COMPOSITE-EN'
                      AND book = 'Genesis' AND chapter = 1 AND verse = 1
                ''')).scalar_one()
                source = session.scalar(select(EditionWorkSource).where(
                    EditionWorkSource.edition_code == 'EOTC-COMPOSITE-EN',
                    EditionWorkSource.work_id == 'genesis',
                ))
                return (
                    text_value,
                    source.source_label,
                    source.source_revision,
                    source.comparison_report_sha256,
                    source.verification_status,
                )

        assert active_genesis() == (
            reviewed_text,
            'World Messianic Bible',
            'Official eBible engwmb VPL archive',
            '045f1ca31cac1d5427beb5dcfa9e9e0c29f4ef255406ab0e204ec7e7587831f3',
            'verified_rebuilt',
        )

        with session_factory() as session:
            coverage_rows = tuple(session.scalars(select(EditionCoverage).where(
                EditionCoverage.edition_code == 'EOTC-COMPOSITE-EN'
            )))
            source_rows = tuple(session.scalars(select(EditionWorkSource).where(
                EditionWorkSource.edition_code == 'EOTC-COMPOSITE-EN'
            )))
            assert len(coverage_rows) == 83
            assert sum(row.chapter_count for row in coverage_rows) == 1_520
            assert sum(row.verse_count for row in coverage_rows) == 38_487
            assert len(source_rows) == 83
            assert sum(row.verification_status.startswith('verified_') for row in source_rows) == 73
            assert sum(row.verification_status == 'in_progress' for row in source_rows) == 10
            assert sum(row.fallback for row in source_rows) == 6
            populated = {row.work_id for row in coverage_rows}
            assert {work.id for work in WORKS} - populated == unavailable_work_ids
            assert populated.isdisjoint(unavailable_work_ids)

        health = _json(runner.invoke(cli.app, [
            'coverage-report', '--run-id', reviewed['run_id'],
            '--edition', 'EOTC-COMPOSITE-EN', '--database-url', database_url,
        ]))
        assert health['run_id'] == reviewed['run_id']
        assert health['active_run_id'] == reviewed['run_id']
        assert health['is_active'] is True
        assert health['status'] == 'published'
        assert health['checksum'] == (
            '35b5878274f1287b0edf28315275ac7fcdff7bb7d7d41ffe2a5984a4e78b46cd'
        )
        assert health['staged_count'] == 38_487
        assert health['published_count'] == 38_487
        assert health['errors'] == 0
        assert health['inventory'] == {
            'populated_work_count': 83,
            'chapter_count': 1_520,
            'verse_count': 38_487,
            'verified_work_count': 73,
            'in_progress_work_count': 10,
            'fallback_work_count': 6,
            'catalog_unavailable_work_count': 13,
            'catalog_unavailable_work_ids': sorted(unavailable_work_ids),
            'verification_status_totals': {
                'in_progress': 10,
                'verified_exact': 13,
                'verified_rebuilt': 60,
            },
        }

        from app.application import create_application
        from app.config import Settings
        from fastapi.testclient import TestClient

        live_app = create_application(Settings(
            environment='development', database_url=database_url,
        ))
        try:
            with TestClient(live_app) as client:
                reader = client.get(
                    '/api/biblical-texts/chapter-content',
                    params={'book': 'Genesis', 'chapter': 1},
                )
                assert reader.status_code == 200
                reader_rows = reader.json()['content']
                assert reader_rows[0]['text'] == reviewed_text
                assert reader_rows[0]['work_source']['verification']['status'] == 'verified_rebuilt'

                comparison = client.get(
                    '/api/biblical-texts/chapter-content',
                    params={'book': 'Baruch', 'chapter': 1},
                )
                assert comparison.status_code == 200
                assert comparison.json()['content'][0]['work_source']['fallback'] is True

                search = client.get('/api/v1/search', params={'q': 'Genesis'})
                assert search.status_code == 200
                assert any(row['title'] == 'Genesis 1:1' for row in search.json()['results'])

                source = client.get(
                    '/api/v1/library/editions/EOTC-COMPOSITE-EN/works/genesis/source'
                )
                assert source.status_code == 200
                assert source.json()['verification']['status'] == 'verified_rebuilt'

                commentary = client.get('/api/v1/commentaries/sources')
                assert commentary.status_code == 200
                assert commentary.json() == {'sources': []}

                catalog = client.get('/api/v1/books', params={'canon': 'ETHIO81'})
                assert catalog.status_code == 200
                unavailable = {
                    row['id'] for row in catalog.json()['books']
                    if row['unavailable_reason'] is not None
                }
                assert unavailable == unavailable_work_ids

                # Research has no backend router; its local route consumes the
                # same real reader/search endpoints verified above.
                assert client.get('/api/v1/health').json()['status'] == 'healthy'
        finally:
            live_app.state.database_engine.dispose()

        rolled_back = _json(runner.invoke(cli.app, [
            'rollback', '--edition', 'EOTC-COMPOSITE-EN',
            '--database-url', database_url,
        ]))
        assert rolled_back['run_id'] == previous['run_id']
        assert rolled_back['displaced_run_id'] == reviewed['run_id']
        assert active_genesis() == (
            'Previous reviewed Genesis publication.',
            'Previous reviewed WMB snapshot',
            'Previous locked WMB revision',
            None,
            'in_progress',
        )
        with session_factory() as session:
            predecessor_source = session.scalar(select(EditionWorkSource).where(
                EditionWorkSource.edition_code == 'EOTC-COMPOSITE-EN',
                EditionWorkSource.work_id == 'genesis',
            ))
            assert predecessor_source.artifact_sha256 is None
            assert predecessor_source.parser_version is None
            assert predecessor_source.comparison_exact == 0
            assert predecessor_source.reviewer is None
            assert predecessor_source.reviewed_at is None

        displaced_health = _json(runner.invoke(cli.app, [
            'coverage-report', '--run-id', reviewed['run_id'],
            '--edition', 'EOTC-COMPOSITE-EN', '--database-url', database_url,
        ]))
        assert displaced_health['run_id'] == reviewed['run_id']
        assert displaced_health['active_run_id'] == previous['run_id']
        assert displaced_health['is_active'] is False
        assert displaced_health['status'] == 'rolled_back'

        republished_run, republished = stage_validate_publish(COMPOSITE_MANIFEST)
        assert republished['publication_version'] == 4
        assert republished['run_id'] == republished_run['run_id']
        assert active_genesis() == (
            reviewed_text,
            'World Messianic Bible',
            'Official eBible engwmb VPL archive',
            '045f1ca31cac1d5427beb5dcfa9e9e0c29f4ef255406ab0e204ec7e7587831f3',
            'verified_rebuilt',
        )
    finally:
        engine.dispose()
