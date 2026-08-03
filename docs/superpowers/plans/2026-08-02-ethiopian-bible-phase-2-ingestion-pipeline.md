# Ethiopian Bible Phase 2: Verified Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct database scraping and placeholder insertion with a licensed, staged, validated, transactional, auditable, and reversible scripture ingestion pipeline.

**Architecture:** Parse authorized sources into immutable staging rows, validate metadata and observed coverage, then publish an edition atomically into the existing `biblical_texts` table. Record source checksums, validation findings, and publication history so repeated imports are idempotent and one edition can be rolled back independently.

**Tech Stack:** Python 3.12, SQLAlchemy, Alembic, Pydantic, Typer, httpx, Pytest, SQLite/PostgreSQL

---

## File Map

- Create `backend/app/library/ingest/models.py`: ingest-run, staging-row, finding, and publication models.
- Create `backend/alembic/versions/0008_verified_scripture_ingestion.py`: ingestion audit schema and scripture uniqueness index.
- Create `backend/app/library/ingest/manifest.py`: strict source-manifest schema and license policy.
- Create `backend/app/library/ingest/types.py`: normalized verse and validation-result types.
- Create `backend/app/library/ingest/normalize.py`: alias, Unicode, HTML, and whitespace normalization.
- Create `backend/app/library/ingest/validate.py`: deterministic validation rules.
- Create `backend/app/library/ingest/publish.py`: transactional publication and rollback.
- Create `backend/app/library/ingest/cli.py`: seed, stage, validate, publish, rollback, and report commands.
- Create `backend/tests/library/ingest/`: unit and integration tests with frozen fixtures.
- Create `backend/tests/library/ingest/conftest.py`: isolated application/session and ingest-run factories.

### Task 1: Enforce Source Metadata and License Policy

**Files:**
- Create: `backend/app/library/ingest/manifest.py`
- Create: `backend/tests/library/ingest/test_manifest.py`

- [ ] **Step 1: Write failing manifest tests**

```python
import pytest
from pydantic import ValidationError
from app.library.ingest.manifest import SourceManifest


VALID = {
    'edition_code': 'KJV', 'name': 'King James Version',
    'reading_language': 'English', 'source_language': 'Hebrew/Greek',
    'script': 'Latin', 'translator': 'KJV translators',
    'publisher': 'Public domain', 'published_year': 1769,
    'license_spdx': 'LicenseRef-Public-Domain',
    'attribution': 'King James Version, public domain',
    'provenance_url': 'https://ebible.org/find/show.php?id=eng-kjv',
    'source_tradition': 'Masoretic Text / Textus Receptus',
    'relationship': 'general_reading', 'versification': 'KJV',
    'expected_works': {'genesis': {'chapters': 50}},
}


def test_manifest_requires_provenance_and_attribution():
    for key in ('license_spdx', 'attribution', 'provenance_url'):
        value = {**VALID, key: ''}
        with pytest.raises(ValidationError):
            SourceManifest.model_validate(value)


def test_manifest_rejects_unsupported_license_and_relationship():
    with pytest.raises(ValidationError):
        SourceManifest.model_validate({**VALID, 'license_spdx': 'All rights reserved'})
    with pytest.raises(ValidationError):
        SourceManifest.model_validate({**VALID, 'relationship': 'ethiopian'})
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_manifest.py -q`

Expected: import fails because the manifest model is absent.

- [ ] **Step 3: Implement strict Pydantic models**

Use `extra='forbid'`, `HttpUrl`, non-empty constrained strings, and the exact relationship values from Phase 1. Permit only `LicenseRef-Public-Domain`, `CC0-1.0`, `CC-BY-4.0`, and `CC-BY-SA-4.0` initially. Add `source_files`, `adapter`, and `adapter_options` fields; do not permit a blank or inferred license.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest backend/tests/library/ingest/test_manifest.py -q`

Expected: all manifest tests pass.

```bash
git add backend/app/library/ingest/manifest.py backend/tests/library/ingest/test_manifest.py
git commit -m "feat: validate scripture source manifests"
```

### Task 2: Add Staging and Audit Tables

**Files:**
- Create: `backend/app/library/ingest/models.py`
- Create: `backend/alembic/versions/0008_verified_scripture_ingestion.py`
- Modify: `backend/app/application.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/tests/library/ingest/test_schema.py`
- Create: `backend/tests/library/ingest/conftest.py`

- [ ] **Step 1: Write the failing table test**

```python
from sqlalchemy import inspect
from app.application import create_application


def test_ingestion_tables_are_registered(test_settings):
    app = create_application(test_settings)
    tables = set(inspect(app.state.database_engine).get_table_names())
    assert {'scripture_ingest_runs', 'staged_scripture_verses', 'scripture_validation_findings', 'scripture_publications'} <= tables
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_schema.py -q`

Expected: FAIL with missing table names.

- [ ] **Step 3: Define ingestion models**

`ScriptureIngestRun` stores UUID, edition code, source checksum, manifest snapshot JSON, status, timestamps, and counts. `StagedScriptureVerse` stores run ID, work ID, source book, chapter, verse, normalized text, source locator, and row checksum with a unique `(run_id, work_id, chapter, verse)` constraint. `ScriptureValidationFinding` stores severity `error|warning`, code, work/chapter/verse, and message. `ScripturePublication` stores edition, run ID, publication version, previous run ID, published timestamp, and active flag.

Create an `ingest_session` fixture that calls `create_application(test_settings)`, opens `Session(app.state.database_engine)`, yields it, and rolls it back/close after each test. Add `make_ingest_run(session, edition_code, text, status='verified', finding=None)` that inserts one Genesis 1:1 staging row and an optional finding, then returns the run.

- [ ] **Step 4: Add migration and model registration**

Set `down_revision = '0007_ethiopian_library_foundation'`. Add a unique index on `biblical_texts(translation, book, chapter, verse)` only after a preflight duplicate query; the migration must raise a clear error listing duplicate keys instead of deleting data.

- [ ] **Step 5: Verify schema and migration reversibility**

Run:

```bash
uv run pytest backend/tests/library/ingest/test_schema.py -q
DATABASE_URL=sqlite:////tmp/unbound-ingest.db uv run alembic -c backend/alembic.ini upgrade head
DATABASE_URL=sqlite:////tmp/unbound-ingest.db uv run alembic -c backend/alembic.ini downgrade 0007_ethiopian_library_foundation
```

Expected: tests pass; upgrade/downgrade succeed on a clean database.

- [ ] **Step 6: Commit the audit schema**

```bash
git add backend/app/library/ingest/models.py backend/alembic/versions/0008_verified_scripture_ingestion.py backend/app/application.py backend/alembic/env.py backend/tests/library/ingest/test_schema.py
git commit -m "feat: add verified ingestion audit schema"
```

### Task 3: Normalize Without Rewriting the Source

**Files:**
- Create: `backend/app/library/ingest/types.py`
- Create: `backend/app/library/ingest/normalize.py`
- Create: `backend/tests/library/ingest/test_normalize.py`

- [ ] **Step 1: Write failing normalization tests**

```python
from app.library.ingest.normalize import normalize_verse


def test_normalizer_resolves_aliases_and_preserves_punctuation():
    row = normalize_verse('Song of Songs', 1, 1, '  The song\u00a0of songs — which is Solomon’s.  ')
    assert row.work_id == 'song-of-solomon'
    assert row.text == 'The song of songs — which is Solomon’s.'


def test_normalizer_rejects_html_and_invalid_positions():
    for values in [
        ('Genesis', 0, 1, 'text'),
        ('Genesis', 1, 0, 'text'),
        ('Genesis', 1, 1, '<script>alert(1)</script>'),
    ]:
        try:
            normalize_verse(*values)
        except ValueError:
            pass
        else:
            raise AssertionError(values)
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_normalize.py -q`

Expected: import failure.

- [ ] **Step 3: Implement normalization**

Use NFC Unicode normalization, replace non-breaking spaces, collapse whitespace, reject markup, require positive integer positions, and resolve aliases through `app.library.canon.alias_target`. Preserve punctuation, capitalization, paragraph meaning, and source verse numbering.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest backend/tests/library/ingest/test_normalize.py -q`

```bash
git add backend/app/library/ingest/types.py backend/app/library/ingest/normalize.py backend/tests/library/ingest/test_normalize.py
git commit -m "feat: normalize scripture imports safely"
```

### Task 4: Validate Coverage and Block Placeholders

**Files:**
- Create: `backend/app/library/ingest/validate.py`
- Create: `backend/tests/library/ingest/test_validate.py`

- [ ] **Step 1: Write failing validation tests**

```python
from app.library.ingest.types import NormalizedVerse
from app.library.ingest.validate import validate_edition


def verse(number, text='Verified verse text'):
    return NormalizedVerse(work_id='genesis', source_book='Genesis', chapter=1, verse=number, text=text, source_locator=f'fixture:{number}')


def test_validator_blocks_duplicates_gaps_and_placeholders():
    result = validate_edition([verse(1), verse(1), verse(3, '[Awaiting full Ge\'ez source text]')], {'genesis': {'chapters': 1, 'verse_counts': {'1': 3}}})
    assert {finding.code for finding in result.errors} == {'duplicate_verse', 'missing_verse', 'placeholder_text'}


def test_validator_allows_reviewed_source_warning_but_not_error():
    result = validate_edition([verse(1)], {'genesis': {'chapters': 1, 'verse_counts': {'1': 1}}}, warnings=['related_recension'])
    assert result.publishable is True
    assert result.warnings[0].code == 'related_recension'
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_validate.py -q`

Expected: import failure.

- [ ] **Step 3: Implement deterministic validation**

Detect duplicate positions, missing expected chapters/verses, empty text, markup, placeholder patterns (`awaiting`, `sample placeholder`, `text unavailable`, `not yet added`, bracketed book descriptions), checksum duplicates with different positions, and observed coverage mismatches. Warnings never hide errors; `publishable` is true only when `errors` is empty.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest backend/tests/library/ingest/test_validate.py -q`

```bash
git add backend/app/library/ingest/validate.py backend/tests/library/ingest/test_validate.py
git commit -m "feat: validate scripture edition coverage"
```

### Task 5: Publish and Roll Back Atomically

**Files:**
- Create: `backend/app/library/ingest/publish.py`
- Create: `backend/tests/library/ingest/test_publish.py`

- [ ] **Step 1: Write failing publication tests**

```python
def text_for(session, edition):
    return session.execute(text('SELECT text FROM biblical_texts WHERE translation=:edition'), {'edition': edition}).scalar_one()


def test_publish_replaces_only_one_verified_edition(ingest_session, make_ingest_run):
    ingest_session.execute(text("INSERT INTO biblical_texts (book,chapter,verse,text,translation) VALUES ('Genesis',1,1,'Existing KJV text','KJV1769')"))
    old = make_ingest_run(ingest_session, 'ETH-TEST', 'Old verified text')
    new = make_ingest_run(ingest_session, 'ETH-TEST', 'New verified text')
    publish_run(ingest_session, old.id)
    publish_run(ingest_session, new.id)
    assert text_for(ingest_session, 'KJV1769') == 'Existing KJV text'
    assert text_for(ingest_session, 'ETH-TEST') == 'New verified text'


def test_unverified_run_cannot_publish(ingest_session, make_ingest_run):
    staged_run_with_error = make_ingest_run(
        ingest_session, 'ETH-TEST', '[Awaiting text]', status='staged', finding='placeholder_text'
    )
    with pytest.raises(PublicationBlocked):
        publish_run(ingest_session, staged_run_with_error.id)
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_publish.py -q`

Expected: import failure.

- [ ] **Step 3: Implement publication**

Inside one transaction, lock the edition publication row, reject non-verified runs, archive the active publication, delete only `biblical_texts` rows for the target edition, insert staged rows using canonical database book names, update `edition_coverage`, and activate the new publication. Rollback restores the previous publication's saved run rows through the same transaction path.

- [ ] **Step 4: Verify idempotency and rollback**

Add tests proving an unchanged checksum is a no-op and rollback restores exact prior verse checksums. Run `uv run pytest backend/tests/library/ingest/test_publish.py -q`.

Expected: all publication tests pass.

- [ ] **Step 5: Commit publication service**

```bash
git add backend/app/library/ingest/publish.py backend/tests/library/ingest/test_publish.py
git commit -m "feat: publish verified scripture editions atomically"
```

### Task 6: Add a Safe Operator CLI

**Files:**
- Create: `backend/app/library/ingest/cli.py`
- Create: `backend/tests/library/ingest/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Use Typer's `CliRunner` to assert `seed-canon`, `stage --manifest`, `validate --run-id`, `publish --run-id`, `rollback --edition`, and `coverage-report` commands. Assert `publish` requires `--confirm` and refuses runs with errors.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_cli.py -q`

- [ ] **Step 3: Implement commands and structured output**

Every mutating command accepts `--database-url`; remote acquisition is separate from publication. Output run ID, edition code, checksum, staged row count, errors, warnings, and next permitted action. Never default to the production database when `--database-url` is absent; require `DATABASE_URL` explicitly.

- [ ] **Step 4: Verify GREEN and help text**

Run:

```bash
uv run pytest backend/tests/library/ingest/test_cli.py -q
uv run python -m app.library.ingest.cli --help
```

Expected: tests pass and all six commands are listed.

- [ ] **Step 5: Commit the CLI**

```bash
git add backend/app/library/ingest/cli.py backend/tests/library/ingest/test_cli.py
git commit -m "feat: add scripture ingestion operator CLI"
```

### Task 7: Retire Unsafe Direct Ingestion Paths

**Files:**
- Modify: `server/data/ingest_ertale_canon.py`
- Modify: `server/data/ingest_report_data.py`
- Modify: `server/data/ingest_ethiopian_canon.py`
- Create: `backend/tests/library/ingest/test_legacy_ingesters.py`

- [ ] **Step 1: Write a source-level safety test**

Assert the three scripts contain no `_create_unverified_context`, no generated scripture placeholders, and no direct delete/insert of Ethiopian edition rows. Assert they exit with a message directing operators to the verified CLI.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_legacy_ingesters.py -q`

Expected: failures identify disabled TLS verification, placeholder text, and direct mutation.

- [ ] **Step 3: Convert legacy scripts into non-mutating migration notices**

Keep filenames for operator discoverability, but replace execution bodies with a clear error explaining the matching manifest/adapter and the new CLI command. Do not leave a compatibility flag that bypasses validation.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest backend/tests/library/ingest/test_legacy_ingesters.py -q`

```bash
git add server/data/ingest_ertale_canon.py server/data/ingest_report_data.py server/data/ingest_ethiopian_canon.py backend/tests/library/ingest/test_legacy_ingesters.py
git commit -m "fix: retire unsafe scripture ingestion paths"
```

### Task 8: Phase 2 Quality Gate

- [ ] **Step 1: Run ingestion and backend suites**

Run: `uv run pytest backend/tests/library/ingest backend/tests/library backend/tests/test_application.py -q`

Expected: zero failures.

- [ ] **Step 2: Exercise a fixture import end to end**

Run stage, validate, publish, repeat publish, coverage report, and rollback against `/tmp/unbound-ingest-e2e.db` using the committed fixture manifest. Expected: first publish changes one fixture edition, repeated publish is a no-op, KJV rows remain untouched, and rollback restores the previous checksum.

- [ ] **Step 3: Commit verification corrections only if needed**

Use `fix: verify scripture ingestion pipeline`; do not create an empty commit.

## Phase 2 Exit Criteria

- No production path disables TLS verification or writes scraped text directly.
- No placeholders can pass validation.
- Publication is edition-scoped, transactional, auditable, idempotent, and reversible.
- Source license and provenance metadata are mandatory.
- No remote source has been imported yet; Phase 3 performs source-specific acquisition and verification.
