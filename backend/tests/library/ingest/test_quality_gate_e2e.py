import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from typer.testing import CliRunner


BACKEND_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = Path(__file__).parent / 'fixtures' / 'quality_gate'
MANIFESTS = (
    FIXTURE_ROOT / 'manifest-v1.json',
    FIXTURE_ROOT / 'manifest-v2.json',
)
runner = CliRunner()


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
