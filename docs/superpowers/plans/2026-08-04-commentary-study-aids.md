# Commentary Study Aids Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five verified, locally stored public-domain commentary collections to the Scripture reader as accessible chapter- and verse-level Study Tools.

**Architecture:** A dedicated `app.commentary` backend domain owns normalized commentary records, source provenance, staged ingestion, validation, transactional publication, and read APIs. The React reader lazy-loads commentary only after its Study Tools choice is opened, uses the existing selected Scripture reference, and renders published source text in a focused component instead of mixing commentary into the generic verse-details payload.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic, Typer, pytest, React 19, Vite, Vitest, Testing Library, Playwright, axe-core.

---

## Scope and sequencing

This plan delivers the approved first release: trusted ingestion, five-source import, public read APIs, the core Commentary tool, citations, accessible verse selection, text sizing, in-entry search, copy actions, and expanded reading. Two-source comparison and AI grounding remain separate milestones because neither is required to publish a complete, testable commentary reader; plan them only after this release passes its acceptance gate.

Preserve all unrelated working-tree changes. At execution time, create an isolated worktree from the intended base or confirm every overlapping dirty file with the user before editing. This feature branch's committed Alembic chain ends at `0007_verified_ingest`; the commentary revision below must use that exact head as its `down_revision`. If another migration is merged first, rebase and update the revision dependency before running migrations.

## File structure

### Backend domain

- Create `backend/app/commentary/__init__.py`: package marker.
- Create `backend/app/commentary/models.py`: source, edition, entry, import-run, staging, finding, and publication tables.
- Create `backend/app/commentary/schemas.py`: bounded public and administrator API contracts.
- Create `backend/app/commentary/service.py`: published-source and reference queries plus exact availability states.
- Create `backend/app/commentary/router.py`: public read routes and administrator publication/rollback routes.
- Create `backend/app/commentary/ingest/__init__.py`: ingestion package marker.
- Create `backend/app/commentary/ingest/types.py`: immutable normalized entry type and deterministic checksums.
- Create `backend/app/commentary/ingest/adapter.py`: strict adapter for reviewed HelloAO JSON bundles.
- Create `backend/app/commentary/ingest/validate.py`: deterministic validation and coverage reporting.
- Create `backend/app/commentary/ingest/publish.py`: staging, atomic publication, and rollback services.
- Create `backend/app/commentary/ingest/acquire.py`: bounded, resumable acquisition of approved source artifacts.
- Create `backend/app/commentary/ingest/cli.py`: administrator CLI commands.
- Create `backend/data/commentaries/sources.json`: reviewed metadata for the five approved sources; no commentary text.
- Create `backend/alembic/versions/0008_commentary_library.py`: commentary schema and indexes.
- Modify `backend/app/application.py`: register commentary models for test metadata creation.
- Modify `backend/app/api/router.py`: mount the commentary router.
- Modify `backend/app/auth/dependencies.py`: add a reusable administrator dependency.

### Backend tests and operations

- Create `backend/tests/commentary/conftest.py`: source and entry factories.
- Create `backend/tests/commentary/test_models.py`: database constraints and migration-facing behavior.
- Create `backend/tests/commentary/ingest/test_adapter.py`: fixture parsing and reference normalization.
- Create `backend/tests/commentary/ingest/test_validate.py`: findings and coverage gates.
- Create `backend/tests/commentary/ingest/test_publish.py`: staging, publication, rollback, and isolation.
- Create `backend/tests/commentary/test_routes.py`: public contracts and administrator authorization.
- Create `backend/tests/commentary/fixtures/helloao-genesis-1.json`: a small representative upstream fixture.
- Create `docs/operations/commentary-import.md`: acquisition, license review, validation, publication, and rollback procedure.

### Frontend

- Create `frontend/src/reader/commentaryApi.js`: source and passage request helpers with response normalization.
- Create `frontend/src/reader/commentaryApi.test.js`: URL, bounds, status, and abort tests.
- Create `frontend/src/reader/CommentaryPanel.jsx`: commentary-specific state and accessible UI.
- Create `frontend/src/reader/CommentaryPanel.test.jsx`: chapter, verse, range, source, search, copy, and empty-state tests.
- Modify `frontend/src/reader/studyToolRegistry.js`: register Commentary as a data-backed Study Tool.
- Modify `frontend/src/reader/StudyTools.jsx`: delegate the Commentary choice to `CommentaryPanel`.
- Modify `frontend/src/reader/StudyTools.test.jsx`: registry, selection, focus, and persistence coverage.
- Modify `frontend/src/reader/ScriptureReaderPage.jsx`: pass the current reference, verse list, and verse navigation callback.
- Modify `frontend/src/reader/ScriptureReaderPage.test.jsx`: lazy-loading and stale-reference integration tests.
- Modify `frontend/src/reader/ScripturePane.jsx`: preserve accessible selected-verse behavior and announce commentary selection.
- Modify `frontend/src/reader/ScripturePane.test.jsx`: selected marker and announcement tests.
- Modify `frontend/src/reader/readerTokens.css`: responsive commentary, typography, focus, theme, and expanded-view styles.
- Modify `frontend/e2e/scripture-reader-accessibility.spec.js`: desktop, mobile, keyboard, zoom, and axe coverage.
- Modify `frontend/src/components/StudyAssistantSidebar.jsx`: remove or relabel synthetic commentary cards.

## Task 1: Add administrator authorization

**Files:**
- Modify: `backend/app/auth/dependencies.py`
- Test: `backend/tests/commentary/test_routes.py`

- [ ] **Step 1: Write the failing authorization test**

Create the test module with a local registration helper and an active dependency test:

```python
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application import create_application
from app.auth.dependencies import require_admin
from app.auth.models import User


def _register(client: TestClient, email: str, username: str) -> dict[str, str]:
    response = client.post('/api/v1/auth/register', json={
        'email': email,
        'username': username,
        'password': 'correct-horse-battery-staple',
    })
    assert response.status_code == 201
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _mount_probe(app) -> None:
    router = APIRouter()

    @router.get('/admin-probe')
    def admin_probe(_user=Depends(require_admin)) -> dict[str, bool]:
        return {'allowed': True}

    app.include_router(router)


def test_require_admin_rejects_member(test_settings):
    app = create_application(test_settings)
    _mount_probe(app)
    with TestClient(app) as client:
        headers = _register(client, 'member@example.com', 'member')
        response = client.get('/admin-probe', headers=headers)
        assert response.status_code == 403
        assert response.json() == {'detail': 'Administrator access required'}


def test_require_admin_accepts_admin(test_settings):
    app = create_application(test_settings)
    _mount_probe(app)
    with TestClient(app) as client:
        headers = _register(client, 'admin@example.com', 'admin-reader')
        with app.state.session_factory() as session, session.begin():
            user = session.scalar(select(User).where(User.email_normalized == 'admin@example.com'))
            user.role = 'admin'
        assert client.get('/admin-probe', headers=headers).json() == {'allowed': True}
```

- [ ] **Step 2: Run the test and verify the missing dependency failure**

Run: `uv run pytest backend/tests/commentary/test_routes.py::test_require_admin_rejects_member -v`

Expected: collection fails because `require_admin` is not exported.

- [ ] **Step 3: Implement the dependency**

Append to `backend/app/auth/dependencies.py`:

```python
def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Administrator access required',
        )
    return user
```

Extend the test using the existing authenticated-user fixture pattern to assert an administrator receives `200` and `{'allowed': True}`.

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest backend/tests/commentary/test_routes.py -v`

Expected: both member and administrator dependency tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/dependencies.py backend/tests/commentary/test_routes.py
git commit -m "feat: add administrator authorization dependency"
```

## Task 2: Create the normalized commentary schema

**Files:**
- Create: `backend/app/commentary/__init__.py`
- Create: `backend/app/commentary/models.py`
- Create: `backend/alembic/versions/0008_commentary_library.py`
- Modify: `backend/app/application.py`
- Create: `backend/tests/commentary/conftest.py`
- Test: `backend/tests/commentary/test_models.py`

- [ ] **Step 1: Write failing model tests**

Cover these invariants with real session flushes:

```python
def test_commentary_entry_rejects_reversed_verse_range(session, published_edition, genesis):
    session.add(CommentaryEntry(
        edition_id=published_edition.id,
        work_id=genesis.id,
        chapter=1,
        verse_start=3,
        verse_end=1,
        entry_type='verse_range',
        heading=None,
        body='A range entry.',
        source_locator='GEN.1.1-3',
        row_checksum='a' * 64,
        position=1,
    ))
    with pytest.raises(IntegrityError):
        session.flush()


def test_only_one_active_publication_exists_per_source(session, source, two_editions):
    session.add_all([
        CommentaryPublication(source_id=source.id, edition_id=two_editions[0].id, version=1, active=True),
        CommentaryPublication(source_id=source.id, edition_id=two_editions[1].id, version=2, active=True),
    ])
    with pytest.raises(IntegrityError):
        session.flush()
```

Create `backend/tests/commentary/conftest.py` with a transaction-scoped real database and explicit factories:

```python
import pytest
from sqlalchemy import select

from app.database import Base, create_database_engine
from app.library.models import LibraryWork
from app.library.seed import seed_ethiopian_canon
from app.commentary.models import CommentaryEdition, CommentarySource


@pytest.fixture
def session(test_settings):
    engine = create_database_engine(test_settings)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    with Session(engine) as database_session:
        seed_ethiopian_canon(database_session)
        database_session.commit()
        yield database_session


@pytest.fixture
def genesis(session):
    return session.scalar(select(LibraryWork).where(LibraryWork.id == 'genesis'))


@pytest.fixture
def source(session):
    value = CommentarySource(
        id='matthew-henry', title='Matthew Henry Bible Commentary', abbreviation='MHC',
        author='Matthew Henry', publication_period='1706–1710', tradition='Reformed Protestant',
        language='eng', license_spdx='LicenseRef-Public-Domain',
        license_url='https://creativecommons.org/publicdomain/mark/1.0/',
        attribution='Matthew Henry Bible Commentary, public domain.',
        provenance_url='https://bible.helloao.org/',
    )
    session.add(value)
    session.flush()
    return value


@pytest.fixture
def two_editions(session, source):
    values = [
        CommentaryEdition(source_id=source.id, dataset_version=f'v{index}', source_checksum=str(index) * 64, status='verified', record_count=1, coverage={})
        for index in (1, 2)
    ]
    session.add_all(values)
    session.flush()
    return values


@pytest.fixture
def published_edition(two_editions):
    return two_editions[0]
```

- [ ] **Step 2: Run the tests and verify imports fail**

Run: `uv run pytest backend/tests/commentary/test_models.py -v`

Expected: collection fails because `app.commentary.models` does not exist.

- [ ] **Step 3: Implement focused SQLAlchemy models**

Define these tables in `models.py`:

```python
class CommentarySource(Base):
    __tablename__ = 'commentary_sources'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    abbreviation: Mapped[str] = mapped_column(String(16))
    author: Mapped[str] = mapped_column(String(200))
    publication_period: Mapped[str] = mapped_column(String(100))
    tradition: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(16), default='eng')
    license_spdx: Mapped[str] = mapped_column(String(64))
    license_url: Mapped[str] = mapped_column(String(2048))
    attribution: Mapped[str] = mapped_column(Text)
    provenance_url: Mapped[str] = mapped_column(String(2048))


class CommentaryEdition(Base):
    __tablename__ = 'commentary_editions'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(ForeignKey('commentary_sources.id', ondelete='CASCADE'))
    dataset_version: Mapped[str] = mapped_column(String(100))
    source_checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommentaryEntry(Base):
    __tablename__ = 'commentary_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('commentary_editions.id', ondelete='CASCADE'))
    work_id: Mapped[str] = mapped_column(ForeignKey('library_works.id', ondelete='CASCADE'))
    chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(24))
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    source_locator: Mapped[str] = mapped_column(String(2048))
    row_checksum: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, default=0)
```

Define the lifecycle models with these interfaces; expand each named constraint directly in `__table_args__` so SQLite and PostgreSQL enforce the same rules:

```python
class CommentaryImportRun(Base):
    __tablename__ = 'commentary_import_runs'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(ForeignKey('commentary_sources.id', ondelete='CASCADE'))
    source_checksum: Mapped[str] = mapped_column(String(64))
    metadata_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))
    staged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)


class StagedCommentaryEntry(Base):
    __tablename__ = 'staged_commentary_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('commentary_import_runs.id', ondelete='CASCADE'))
    work_id: Mapped[str] = mapped_column(ForeignKey('library_works.id', ondelete='CASCADE'))
    chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(24))
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    source_locator: Mapped[str] = mapped_column(String(2048))
    row_checksum: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)


class CommentaryValidationFinding(Base):
    __tablename__ = 'commentary_validation_findings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('commentary_import_runs.id', ondelete='CASCADE'))
    severity: Mapped[str] = mapped_column(String(7))
    code: Mapped[str] = mapped_column(String(100))
    work_id: Mapped[str | None] = mapped_column(ForeignKey('library_works.id', ondelete='SET NULL'), nullable=True)
    chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text)


class CommentaryPublication(Base):
    __tablename__ = 'commentary_publications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey('commentary_sources.id', ondelete='CASCADE'))
    edition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('commentary_editions.id', ondelete='RESTRICT'))
    version: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Add named checks for allowed statuses/types, positive coordinates, paired verse bounds, `verse_end >= verse_start`, 64-character checksums, and nonnegative counts. Add a partial unique index for one active publication per source and a lookup index on `(edition_id, work_id, chapter, verse_start, verse_end)`.

Create the Alembic revision with `revision = '0008_commentary_library'` and `down_revision = '0007_verified_ingest'`. Its upgrade and downgrade must mirror every model constraint and index. Import the model module in `backend/app/application.py` beside the existing library imports.

- [ ] **Step 4: Run model and application tests**

Run: `uv run pytest backend/tests/commentary/test_models.py backend/tests/test_application.py -v`

Expected: all tests pass and test application creation creates every commentary table.

- [ ] **Step 5: Verify the migration on an empty database**

Run: `DATABASE_URL=sqlite:////tmp/unbound-commentary-plan.db uv run alembic -c backend/alembic.ini upgrade head`

Expected: upgrade completes at `0008_commentary_library`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/commentary backend/alembic/versions/0008_commentary_library.py backend/app/application.py backend/tests/commentary/conftest.py backend/tests/commentary/test_models.py
git commit -m "feat: add commentary library schema"
```

## Task 3: Normalize HelloAO commentary records

**Files:**
- Create: `backend/app/commentary/ingest/__init__.py`
- Create: `backend/app/commentary/ingest/types.py`
- Create: `backend/app/commentary/ingest/adapter.py`
- Create: `backend/tests/commentary/fixtures/helloao-genesis-1.json`
- Create: `backend/tests/commentary/ingest/test_adapter.py`

- [ ] **Step 1: Add the representative fixture and failing adapter tests**

The fixture must contain a book introduction, chapter introduction, verse 1, and a range-like verse record represented by the upstream shape. Assert exact normalized output:

```python
def test_adapter_emits_introductions_and_verse_entries(fixture_path):
    rows = tuple(load_helloao_bundle(fixture_path, {'GEN': 'genesis'}))
    assert [(row.entry_type, row.chapter, row.verse_start, row.verse_end) for row in rows] == [
        ('book_intro', None, None, None),
        ('chapter_intro', 1, None, None),
        ('verse', 1, 1, 1),
        ('verse_range', 1, 2, 3),
    ]
    assert all(row.source_locator.startswith('helloao:') for row in rows)
    assert all(len(row.row_checksum) == 64 for row in rows)
```

- [ ] **Step 2: Run the adapter tests and verify failure**

Run: `uv run pytest backend/tests/commentary/ingest/test_adapter.py -v`

Expected: collection fails because the adapter and normalized type do not exist.

- [ ] **Step 3: Implement strict normalized entries**

Define an immutable `NormalizedCommentaryEntry` with `work_id`, optional chapter and verse bounds, `entry_type`, optional heading, body, locator, and position. Validate the four allowed entry types and their coordinate combinations in `__post_init__`. Reuse `normalize_string`, `contains_markup`, and canonical work resolution from `app.library.ingest.types`, but preserve paragraph breaks in commentary body with NFC normalization and bounded whitespace rather than collapsing the entire body to one line.

Use a typed checksum payload:

```python
def commentary_row_checksum(entry: NormalizedCommentaryEntry) -> str:
    payload = [
        'commentary-row-v1', entry.work_id, entry.chapter, entry.verse_start,
        entry.verse_end, entry.entry_type, entry.heading, entry.body,
        entry.source_locator, entry.position,
    ]
    return sha256(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
```

Implement `load_helloao_bundle(path, book_map)` with strict top-level keys, a maximum 5 MiB per JSON artifact, exact positive integer checks, approved book mapping, string-only content fragments, and deterministic source ordering. Reject HTML/XML markup rather than rendering it.

- [ ] **Step 4: Run adapter tests**

Run: `uv run pytest backend/tests/commentary/ingest/test_adapter.py -v`

Expected: all adapter tests pass, including malformed Unicode, unknown books, markup, oversized files, invalid ranges, and empty content.

- [ ] **Step 5: Commit**

```bash
git add backend/app/commentary/ingest backend/tests/commentary/ingest/test_adapter.py backend/tests/commentary/fixtures/helloao-genesis-1.json
git commit -m "feat: normalize commentary source bundles"
```

## Task 4: Validate coverage and provenance

**Files:**
- Create: `backend/app/commentary/ingest/validate.py`
- Create: `backend/data/commentaries/sources.json`
- Create: `backend/tests/commentary/ingest/test_validate.py`

- [ ] **Step 1: Write failing validation tests**

Test duplicate identities, reversed or overlapping ranges, empty books, source/license mismatch, record-count regression, and stable coverage output:

```python
def test_validation_reports_stable_coverage(valid_rows):
    result = validate_commentary(valid_rows, expected_books={'genesis'}, previous_coverage=None)
    assert result.publishable is True
    assert result.coverage == {
        'books': 1,
        'chapters': 1,
        'entries': len(valid_rows),
        'by_work': {'genesis': {'chapters': 1, 'entries': len(valid_rows)}},
    }


def test_validation_blocks_large_regression(valid_rows):
    result = validate_commentary(
        valid_rows[:1],
        expected_books={'genesis'},
        previous_coverage={'entries': 10},
    )
    assert result.publishable is False
    assert 'coverage_regression' in {finding.code for finding in result.findings}
```

- [ ] **Step 2: Run validation tests and verify failure**

Run: `uv run pytest backend/tests/commentary/ingest/test_validate.py -v`

Expected: collection fails because `validate_commentary` does not exist.

- [ ] **Step 3: Implement deterministic validation**

Return an immutable result containing sorted findings, coverage, error count, warning count, and `publishable`. Block publication for unknown works, missing expected books, duplicate row identity, unsafe markup, invalid locators, unsupported licenses, blank attribution, and a greater-than-5-percent entry regression from a prior edition unless no prior edition exists.

Create `sources.json` with exactly the approved IDs:

```json
{
  "matthew-henry": {"license_spdx": "LicenseRef-Public-Domain"},
  "john-gill": {"license_spdx": "LicenseRef-Public-Domain"},
  "adam-clarke": {"license_spdx": "LicenseRef-Public-Domain"},
  "jamieson-fausset-brown": {"license_spdx": "LicenseRef-Public-Domain"},
  "keil-delitzsch": {"license_spdx": "LicenseRef-Public-Domain"}
}
```

Each object must additionally contain the reviewed title, abbreviation, author, publication period, tradition, language, attribution, upstream URL, license URL, expected source book IDs, and explicit `license_reviewed_on` date. Validation rejects an object missing any field; it also rejects `tyndale` or any unapproved source ID.

- [ ] **Step 4: Run validation tests**

Run: `uv run pytest backend/tests/commentary/ingest/test_validate.py -v`

Expected: all validation and metadata allowlist tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/commentary/ingest/validate.py backend/data/commentaries/sources.json backend/tests/commentary/ingest/test_validate.py
git commit -m "feat: validate commentary coverage and provenance"
```

## Task 5: Stage, publish, and roll back commentary editions

**Files:**
- Create: `backend/app/commentary/ingest/publish.py`
- Modify: `backend/tests/commentary/conftest.py`
- Create: `backend/tests/commentary/ingest/test_publish.py`

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_publish_switches_active_edition_atomically(session, staged_verified_run):
    publication = publish_run(session, staged_verified_run.id)
    session.commit()
    assert publication.active is True
    assert session.scalar(select(CommentaryEntry).where(
        CommentaryEntry.edition_id == publication.edition_id
    )) is not None


def test_staged_run_does_not_create_a_publication(session, staged_verified_run):
    publication = session.scalar(select(CommentaryPublication).where(
        CommentaryPublication.source_id == staged_verified_run.source_id,
        CommentaryPublication.active.is_(True),
    ))
    assert publication is None


def test_rollback_reactivates_previous_edition(session, two_publications):
    restored = rollback_publication(session, two_publications.current.id)
    assert restored.edition_id == two_publications.previous.edition_id
    assert restored.active is True
```

- [ ] **Step 2: Run lifecycle tests and verify failure**

Run: `uv run pytest backend/tests/commentary/ingest/test_publish.py -v`

Expected: collection fails because publication services are absent.

- [ ] **Step 3: Implement the lifecycle**

Implement `stage_bundle`, `validate_run`, `publish_run`, and `rollback_publication` using caller-owned SQLAlchemy transactions. `publish_run` must lock or otherwise serialize the active source publication, refuse runs not in `verified` state, copy staged rows to immutable published entries, deactivate the previous publication, create the next monotonically increasing version, and update the run only after all inserts succeed. `rollback_publication` creates a new publication version that points to the selected earlier immutable edition; it never mutates historical entries.

Expose `stage_bundle(session, *, source_id, source_checksum, metadata_snapshot, rows)`, `validate_run(session, run_id)`, `publish_run(session, run_id)`, and `rollback_publication(session, publication_id)`. Use this publication transaction shape:

```python
def publish_run(session: Session, run_id: UUID) -> CommentaryPublication:
    run = session.scalar(
        select(CommentaryImportRun).where(CommentaryImportRun.id == run_id).with_for_update()
    )
    if run is None or run.status != 'verified' or run.error_count:
        raise ValueError('Only an error-free verified commentary run may be published.')
    previous = session.scalar(select(CommentaryPublication).where(
        CommentaryPublication.source_id == run.source_id,
        CommentaryPublication.active.is_(True),
    ).with_for_update())
    edition = CommentaryEdition(
        source_id=run.source_id,
        dataset_version=str(run.id),
        source_checksum=run.source_checksum,
        status='published',
        record_count=run.staged_count,
        coverage=run.metadata_snapshot['coverage'],
    )
    session.add(edition)
    session.flush()
    staged = session.scalars(select(StagedCommentaryEntry).where(
        StagedCommentaryEntry.run_id == run.id
    ).order_by(StagedCommentaryEntry.position, StagedCommentaryEntry.id)).all()
    session.add_all([CommentaryEntry(
        edition_id=edition.id, work_id=row.work_id, chapter=row.chapter,
        verse_start=row.verse_start, verse_end=row.verse_end,
        entry_type=row.entry_type, heading=row.heading, body=row.body,
        source_locator=row.source_locator, row_checksum=row.row_checksum,
        position=row.position,
    ) for row in staged])
    if previous is not None:
        previous.active = False
    version = session.scalar(select(func.coalesce(func.max(CommentaryPublication.version), 0)).where(
        CommentaryPublication.source_id == run.source_id
    )) + 1
    publication = CommentaryPublication(
        source_id=run.source_id, edition_id=edition.id, version=version, active=True,
    )
    session.add(publication)
    run.status = 'published'
    session.flush()
    return publication
```

`stage_bundle` snapshots every normalized scalar into `StagedCommentaryEntry`; `validate_run` replaces findings for the run and persists coverage into `metadata_snapshot['coverage']`; `rollback_publication` deactivates the current publication and creates a new active publication version referencing the selected prior edition. Each function flushes but does not commit so its caller owns atomicity.

- [ ] **Step 4: Run lifecycle and SQLite foreign-key tests**

Run: `uv run pytest backend/tests/commentary/ingest/test_publish.py backend/tests/security/test_security_controls.py -v`

Expected: all tests pass; injected mid-publication failure leaves the prior edition active and staged rows hidden.

- [ ] **Step 5: Commit**

```bash
git add backend/app/commentary/ingest/publish.py backend/tests/commentary/conftest.py backend/tests/commentary/ingest/test_publish.py
git commit -m "feat: publish verified commentary editions"
```

## Task 6: Add safe acquisition and administrator CLI

**Files:**
- Create: `backend/app/commentary/ingest/acquire.py`
- Create: `backend/app/commentary/ingest/cli.py`
- Create: `backend/tests/commentary/ingest/test_acquire.py`
- Create: `backend/tests/commentary/ingest/test_cli.py`
- Create: `docs/operations/commentary-import.md`

- [ ] **Step 1: Write failing acquisition tests**

Mock the HTTP transport and assert HTTPS-only URLs, allowlisted host and source IDs, 10-second connect/read timeouts, 5 MiB response caps, JSON content type, three bounded retries, `.part` resume behavior, SHA-256 sidecars, and no final file after checksum or JSON failure.

```python
def test_acquire_rejects_unapproved_host(tmp_path):
    with pytest.raises(ValueError, match='approved host'):
        acquire_source('matthew-henry', 'https://example.com/data.json', tmp_path)
```

- [ ] **Step 2: Run acquisition tests and verify failure**

Run: `uv run pytest backend/tests/commentary/ingest/test_acquire.py backend/tests/commentary/ingest/test_cli.py -v`

Expected: collection fails because acquisition and CLI modules do not exist.

- [ ] **Step 3: Implement acquisition and commands**

Use `urllib.request` so no dependency is added. Restrict acquisition to `https://bible.helloao.org/api/`, the five IDs in `sources.json`, and book IDs listed by each reviewed source. Write through a temporary `.part` file, call `fsync`, validate JSON, compute SHA-256, then atomically rename.

Expose these Typer commands:

```text
commentary acquire --source matthew-henry --output backend/data/commentaries/raw
commentary stage --source matthew-henry --input backend/data/commentaries/raw/matthew-henry
commentary validate --run-id <uuid>
commentary report --run-id <uuid> --output commentary-coverage.json
commentary publish --run-id <uuid> --confirm
commentary rollback --publication-id <integer> --confirm
```

Every command emits machine-readable JSON and returns nonzero on a blocked gate. Add `docs/operations/commentary-import.md` with the exact command sequence, license-review checklist, expected statuses, backup instruction, coverage review, publish confirmation, smoke-test URLs, and rollback procedure.

- [ ] **Step 4: Run CLI tests**

Run: `uv run pytest backend/tests/commentary/ingest/test_acquire.py backend/tests/commentary/ingest/test_cli.py -v`

Expected: all acquisition, resume, output, confirmation, and error-code tests pass without network access.

- [ ] **Step 5: Commit**

```bash
git add backend/app/commentary/ingest/acquire.py backend/app/commentary/ingest/cli.py backend/tests/commentary/ingest/test_acquire.py backend/tests/commentary/ingest/test_cli.py docs/operations/commentary-import.md
git commit -m "feat: add controlled commentary import workflow"
```

## Task 7: Serve published commentary through bounded APIs

**Files:**
- Create: `backend/app/commentary/schemas.py`
- Create: `backend/app/commentary/service.py`
- Create: `backend/app/commentary/router.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/commentary/test_routes.py`

- [ ] **Step 1: Write failing route tests**

Cover source listing, chapter overview, exact verse, covering range, unknown work, no entry, incomplete coverage, cache validators, two-source maximum, and admin authorization:

```python
def test_verse_query_returns_covering_range(client, published_commentary):
    response = client.get('/api/v1/commentaries/entries', params={
        'source': 'matthew-henry', 'book': 'Genesis', 'chapter': 1, 'verse': 2,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload['reference'] == {'book': 'Genesis', 'chapter': 1, 'verse': 2}
    assert payload['availability'] == 'available'
    assert payload['entries'][0]['scope'] == {'verse_start': 1, 'verse_end': 3}
    assert payload['entries'][0]['source']['id'] == 'matthew-henry'


def test_public_route_never_returns_staged_text(client, staged_run):
    response = client.get('/api/v1/commentaries/entries', params={
        'source': staged_run.source_id, 'book': 'Genesis', 'chapter': 1, 'verse': 1,
    })
    assert response.status_code == 404
    assert response.json()['detail']['code'] == 'source_not_published'
```

- [ ] **Step 2: Run route tests and verify 404/import failures**

Run: `uv run pytest backend/tests/commentary/test_routes.py -v`

Expected: commentary endpoints are unavailable.

- [ ] **Step 3: Implement public and administrator routes**

Mount a router with prefix `/commentaries`. Public routes:

```text
GET /api/v1/commentaries/sources
GET /api/v1/commentaries/entries?source=<id>&book=<name>&chapter=<n>[&verse=<n>]
GET /api/v1/commentaries/compare?sources=<id>&sources=<id>&book=<name>&chapter=<n>&verse=<n>
```

`entries` returns a maximum of 50 ordered entries and bodies of at most 100,000 characters per response. `compare` accepts one or two distinct published sources and reuses the same entry schema. Resolve book aliases through the existing library canon mapping. Include edition/version, source metadata, citation, coverage, and one of `available`, `no_entry`, `coverage_incomplete`, or `wider_range`.

Administrator routes use `Depends(require_admin)`:

```text
GET  /api/v1/commentaries/admin/imports/{run_id}
POST /api/v1/commentaries/admin/imports/{run_id}/publish
POST /api/v1/commentaries/admin/publications/{publication_id}/rollback
```

The two mutation bodies require `{"confirm": true}`. Register the router in `backend/app/api/router.py`.

- [ ] **Step 4: Run route and application tests**

Run: `uv run pytest backend/tests/commentary/test_routes.py backend/tests/test_application.py -v`

Expected: all public contracts, bounds, cache headers, aliases, staging isolation, and administrator checks pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/commentary/schemas.py backend/app/commentary/service.py backend/app/commentary/router.py backend/app/api/router.py backend/tests/commentary/test_routes.py
git commit -m "feat: serve published commentary passages"
```

## Task 8: Add the frontend commentary client

**Files:**
- Create: `frontend/src/reader/commentaryApi.js`
- Create: `frontend/src/reader/commentaryApi.test.js`

- [ ] **Step 1: Write failing API-client tests**

```javascript
it('requests a verse with encoded source and reference', async () => {
  fetch.mockResolvedValue(new Response(JSON.stringify({ entries: [] }), { status: 200 }))
  await getCommentaryEntries({
    source: 'john-gill', book: 'Song of Solomon', chapter: 1, verse: 2,
  })
  expect(fetch).toHaveBeenCalledWith(
    '/api/v1/commentaries/entries?source=john-gill&book=Song+of+Solomon&chapter=1&verse=2',
    { signal: undefined },
  )
})
```

Also test chapter requests omit `verse`, invalid coordinates fail before fetch, malformed payloads normalize to safe empty arrays, error objects preserve status/code, and AbortError is rethrown unchanged.

- [ ] **Step 2: Run client tests and verify import failure**

Run: `npm test -- --run src/reader/commentaryApi.test.js`

Working directory: `frontend`

Expected: test collection fails because `commentaryApi.js` does not exist.

- [ ] **Step 3: Implement the bounded client**

Create `commentaryApi.js` with the complete request boundary below. Add small `normalizeSource` and `normalizeEntry` helpers beside it that copy only documented scalar fields and discard malformed array items.

```javascript
export class CommentaryRequestError extends Error {
  constructor(message, { status, code } = {}) {
    super(message)
    this.name = 'CommentaryRequestError'
    this.status = status
    this.code = code
  }
}

function positiveInteger(value, name) {
  const number = Number(value)
  if (!Number.isSafeInteger(number) || number <= 0) {
    throw new TypeError(`${name} must be a positive integer`)
  }
  return number
}

function nonblank(value, name) {
  const text = typeof value === 'string' ? value.trim() : ''
  if (!text) throw new TypeError(`${name} must be a nonblank string`)
  return text
}

async function requestCommentary(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    let detail = {}
    try { detail = (await response.json()).detail ?? {} } catch { detail = {} }
    throw new CommentaryRequestError(
      detail.message || `Commentary request failed (${response.status})`,
      { status: response.status, code: detail.code },
    )
  }
  return response.json()
}

export async function getCommentarySources(signal) {
  const payload = await requestCommentary('/api/v1/commentaries/sources', signal)
  return Array.isArray(payload.sources) ? payload.sources.map(normalizeSource).filter(Boolean) : []
}

export async function getCommentaryEntries({ source, book, chapter, verse }, signal) {
  const params = new URLSearchParams({
    source: nonblank(source, 'source'),
    book: nonblank(book, 'book'),
    chapter: String(positiveInteger(chapter, 'chapter')),
  })
  if (verse !== undefined && verse !== null) {
    params.set('verse', String(positiveInteger(verse, 'verse')))
  }
  const payload = await requestCommentary(`/api/v1/commentaries/entries?${params}`, signal)
  return {
    reference: payload.reference && typeof payload.reference === 'object' ? payload.reference : {},
    availability: typeof payload.availability === 'string' ? payload.availability : 'no_entry',
    source: normalizeSource(payload.source),
    entries: Array.isArray(payload.entries) ? payload.entries.map(normalizeEntry).filter(Boolean) : [],
  }
}
```

`normalizeSource` requires `id` and `title`; it retains `abbreviation`, `author`, `publication_period`, `tradition`, `language`, `license_spdx`, `license_url`, `attribution`, and `edition_version` only when they are strings or safe integers. `normalizeEntry` requires nonblank `body` and `citation`; it retains safe positive scope coordinates and optional heading/source locator. Do not convert aborts into user-visible failures.

- [ ] **Step 4: Run client tests**

Run: `npm test -- --run src/reader/commentaryApi.test.js`

Working directory: `frontend`

Expected: all commentary client tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/reader/commentaryApi.js frontend/src/reader/commentaryApi.test.js
git commit -m "feat: add commentary reader client"
```

## Task 9: Build the accessible Commentary panel

**Files:**
- Create: `frontend/src/reader/CommentaryPanel.jsx`
- Create: `frontend/src/reader/CommentaryPanel.test.jsx`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Write failing component tests**

Test the initial chapter request, selected verse request, source persistence, wider-range label, loading, no-entry, coverage-incomplete, retry, abort on reference change, stale-response suppression, Previous/Next Verse, search filtering/highlighting without HTML injection, copy text, copy citation, and expanded view.

```javascript
it('opens with a chapter overview and switches to the selected verse', async () => {
  const user = userEvent.setup()
  render(<CommentaryPanel reference={{ book: 'Genesis', chapter: 1 }} verses={[1, 2, 3]} />)
  expect(await screen.findByRole('heading', { name: 'Genesis 1 commentary' })).toBeVisible()
  expect(screen.getByRole('tab', { name: 'Chapter overview' })).toHaveAttribute('aria-selected', 'true')

  rerender(<CommentaryPanel reference={{ book: 'Genesis', chapter: 1, verse: 2 }} verses={[1, 2, 3]} />)
  expect(await screen.findByText('Commentary for Genesis 1:2')).toBeVisible()
  expect(screen.getByRole('tab', { name: 'Selected verse' })).toHaveAttribute('aria-selected', 'true')
})
```

- [ ] **Step 2: Run component tests and verify import failure**

Run: `npm test -- --run src/reader/CommentaryPanel.test.jsx`

Working directory: `frontend`

Expected: collection fails because `CommentaryPanel.jsx` does not exist.

- [ ] **Step 3: Implement the component**

`CommentaryPanel` accepts `reference`, `verses`, `onSelectVerse`, and injectable API functions for tests. It loads source metadata once per open instance, restores only an installed source from `localStorage['unbound_commentary_source']`, fetches entries in an abortable effect, and associates every response with a normalized reference/source key before committing state.

Use this state and request ownership pattern exactly:

```jsx
const SOURCE_KEY = 'unbound_commentary_source'

export default function CommentaryPanel({
  headingId,
  reference,
  verses = [],
  onSelectVerse,
  loadSources = getCommentarySources,
  loadEntries = getCommentaryEntries,
}) {
  const [sources, setSources] = useState([])
  const [sourceId, setSourceId] = useState('')
  const [result, setResult] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState(false)
  const requestGeneration = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    loadSources(controller.signal).then((nextSources) => {
      if (controller.signal.aborted) return
      setSources(nextSources)
      const saved = window.localStorage.getItem(SOURCE_KEY)
      const selected = nextSources.find(({ id }) => id === saved) ?? nextSources[0]
      setSourceId(selected?.id ?? '')
    }).catch((nextError) => {
      if (nextError?.name !== 'AbortError') setError(nextError)
    })
    return () => controller.abort()
  }, [loadSources])

  const requestKey = `${sourceId}|${reference.book}|${reference.chapter}|${reference.verse ?? ''}`
  useEffect(() => {
    if (!sourceId || !reference.book || !reference.chapter) return undefined
    const controller = new AbortController()
    const generation = ++requestGeneration.current
    setStatus('loading')
    setError(null)
    loadEntries({ source: sourceId, ...reference }, controller.signal)
      .then((nextResult) => {
        if (generation !== requestGeneration.current || controller.signal.aborted) return
        setResult(nextResult)
        setStatus('ready')
      })
      .catch((nextError) => {
        if (generation !== requestGeneration.current || nextError?.name === 'AbortError') return
        setResult(null)
        setError(nextError)
        setStatus('error')
      })
    return () => controller.abort()
  }, [loadEntries, requestKey])

  const chooseSource = (nextSource) => {
    setSourceId(nextSource)
    window.localStorage.setItem(SOURCE_KEY, nextSource)
  }

  // Render the semantic structure specified below from these owned states.
}
```

Render semantic tabs, a labeled `<select>`, source metadata, availability callouts, `<article>` entries with citation footers, a local plain-text search input, copy buttons, and an expanded `<dialog>`. Use `navigator.clipboard.writeText` only from a button action and expose success/failure through `role="status"`. Render text as React text nodes; never use `dangerouslySetInnerHTML`.

The root is a `section` labelled by `headingId`. The heading text is `<book> <chapter> commentary`. The two tab buttons use `role="tab"` and `aria-selected`; Chapter Overview calls `onSelectVerse(null)`, while Selected Verse is disabled without a verse. Every returned entry is an `article` containing an optional heading, paragraph-preserving body, wider-range badge when applicable, and a citation footer. Filter displayed entries with `body.toLocaleLowerCase().includes(query.toLocaleLowerCase())`; do not inject highlighting markup. The expanded dialog repeats the same articles and has a word-labelled **Close expanded commentary** button.

- [ ] **Step 4: Add focused styles**

Add `.commentary-panel*` selectors using existing reader tokens. Commentary body uses `font-family: Georgia, 'Times New Roman', serif`, `font-size: var(--reader-font-size)`, `line-height: 1.75`, and a maximum 70-character measure. Controls have a 48-pixel minimum height. Add visible selected tab text/underline, source metadata cards, amber incomplete-coverage state, range badge, search match styling, expanded dialog, light theme support, `prefers-reduced-motion`, and mobile safe-area padding without horizontal scrolling.

- [ ] **Step 5: Run component and CSS tests**

Run: `npm test -- --run src/reader/CommentaryPanel.test.jsx src/reader/StudyTools.test.jsx`

Working directory: `frontend`

Expected: all tests pass and CSS assertions confirm 48-pixel controls, readable line height, light/dark tokens, and mobile width containment.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/reader/CommentaryPanel.jsx frontend/src/reader/CommentaryPanel.test.jsx frontend/src/reader/readerTokens.css
git commit -m "feat: add accessible commentary panel"
```

## Task 10: Integrate Commentary with Study Tools and verse navigation

**Files:**
- Modify: `frontend/src/reader/studyToolRegistry.js`
- Modify: `frontend/src/reader/StudyTools.jsx`
- Modify: `frontend/src/reader/StudyTools.test.jsx`
- Modify: `frontend/src/reader/ScriptureReaderPage.jsx`
- Modify: `frontend/src/reader/ScriptureReaderPage.test.jsx`
- Modify: `frontend/src/reader/ScripturePane.jsx`
- Modify: `frontend/src/reader/ScripturePane.test.jsx`

- [ ] **Step 1: Write failing integration tests**

Add Commentary to the expected immutable registry immediately after Context:

```javascript
{
  id: 'commentary',
  kind: 'data',
  label: 'Commentary',
}
```

Assert Study Tools is still closed by default, choosing Commentary renders the dedicated panel, clicking a verse while Commentary is open changes its reference without closing the drawer, **Back to chapter overview** clears only the verse, Previous/Next selects an existing verse, selected verse exposes `aria-pressed="true"`, and a polite live region announces `Commentary selected for Genesis 1 verse 2`.

- [ ] **Step 2: Run integration tests and verify failure**

Run: `npm test -- --run src/reader/StudyTools.test.jsx src/reader/ScriptureReaderPage.test.jsx src/reader/ScripturePane.test.jsx`

Working directory: `frontend`

Expected: registry and Commentary integration assertions fail.

- [ ] **Step 3: Connect the dedicated data tool**

Permit `kind === 'data'` in the selectable tool filter. Add `verses` and `onSelectVerse` props to `StudyTools`. When active tool ID is `commentary`, render:

```jsx
<CommentaryPanel
  headingId={`${panelId}-commentary`}
  reference={normalizedReference.value}
  verses={verses}
  onSelectVerse={onSelectVerse}
/>
```

Do not fetch generic verse details merely because Commentary is active; its client owns its lazy request. In `ScriptureReaderPage`, pass the sorted unique positive verse numbers and `onSelectVerse={(verse) => navigate({ verse })}`. `Back to chapter overview` calls the same callback with `null`, which `normalizeRoute` already converts into a chapter reference.

Add an off-screen polite status node to `ScripturePane` whose text changes only after a selected verse changes while commentary is active. Preserve native button semantics, `aria-labelledby`, text selection behavior, notes, highlights, and reader scroll position.

- [ ] **Step 4: Run integration tests**

Run: `npm test -- --run src/reader/StudyTools.test.jsx src/reader/ScriptureReaderPage.test.jsx src/reader/ScripturePane.test.jsx`

Working directory: `frontend`

Expected: all integration, stale-response, focus-restoration, and existing verse-control tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/reader/studyToolRegistry.js frontend/src/reader/StudyTools.jsx frontend/src/reader/StudyTools.test.jsx frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/ScriptureReaderPage.test.jsx frontend/src/reader/ScripturePane.jsx frontend/src/reader/ScripturePane.test.jsx
git commit -m "feat: integrate commentary with scripture study tools"
```

## Task 11: Remove synthetic commentary presentation

**Files:**
- Modify: `frontend/src/components/StudyAssistantSidebar.jsx`
- Create: `frontend/src/components/StudyAssistantSidebar.test.jsx`

- [ ] **Step 1: Write the failing authenticity test**

```javascript
it('does not present generated sample prose as published commentary', () => {
  renderWithAuth(
    <StudyAssistantSidebar
      book="Genesis"
      chapter={1}
      verse={1}
      initialInsightSubTab="commentary"
      onClose={vi.fn()}
    />,
  )
  expect(screen.queryByText(/Decolonized Commentary \(Axum Studies\)/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/Library Commentary \(Standard Exegesis\)/i)).not.toBeInTheDocument()
  expect(screen.getByText('Verified commentary is available in the Scripture Reader Study Tools.')).toBeVisible()
})
```

At the top of the test module, use this deterministic auth and fetch setup:

```javascript
vi.mock('../auth/authContext', () => ({
  useAuth: () => ({ status: 'anonymous' }),
}))

function renderWithAuth(node) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({}), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })))
  return render(node)
}
```

- [ ] **Step 2: Run the test and verify the static cards fail it**

Run: `npm test -- --run src/components/StudyAssistantSidebar.test.jsx`

Working directory: `frontend`

Expected: the test fails because hard-coded commentary cards are rendered.

- [ ] **Step 3: Remove the cards and point users to verified Commentary**

Delete both static commentary cards and the **Generate Full Commentary Review** button. In that empty branch render exactly:

```jsx
<div className="empty-state">
  <p>Verified commentary is available in the Scripture Reader Study Tools.</p>
</div>
```

Do not add navigation or a new callback to this legacy sidebar in the first release.

- [ ] **Step 4: Run the focused component test**

Run: `npm test -- --run src/components/StudyAssistantSidebar.test.jsx`

Working directory: `frontend`

Expected: no synthetic source text is rendered and the verified Commentary action is accessible.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StudyAssistantSidebar.jsx frontend/src/components/StudyAssistantSidebar.test.jsx
git commit -m "fix: remove synthetic commentary cards"
```

## Task 12: Import and verify the five approved collections

**Files:**
- Modify: `backend/data/commentaries/sources.json` only if license review discovers inaccurate metadata.
- Create locally, do not commit: `backend/data/commentaries/raw/`
- Create locally, do not commit: `commentary-coverage/`
- Modify: `.gitignore`

- [ ] **Step 1: Protect raw licensed data from accidental commits**

Add these exact ignore rules:

```gitignore
backend/data/commentaries/raw/
commentary-coverage/
```

- [ ] **Step 2: Verify provenance before acquisition**

For each of the five IDs, compare `available_commentaries.json`, its `books.json`, the upstream repository/license notice, and the historical work's edition identity. Record the reviewed URLs, reviewer, and review date in `sources.json`. Stop that individual source if its redistribution status or edition identity is ambiguous; do not weaken the validation gate for the other sources.

- [ ] **Step 3: Acquire each approved source**

Run one command per source:

```bash
PYTHONPATH=backend uv run python -m app.commentary.ingest.cli acquire --source matthew-henry --output backend/data/commentaries/raw
PYTHONPATH=backend uv run python -m app.commentary.ingest.cli acquire --source john-gill --output backend/data/commentaries/raw
PYTHONPATH=backend uv run python -m app.commentary.ingest.cli acquire --source adam-clarke --output backend/data/commentaries/raw
PYTHONPATH=backend uv run python -m app.commentary.ingest.cli acquire --source jamieson-fausset-brown --output backend/data/commentaries/raw
PYTHONPATH=backend uv run python -m app.commentary.ingest.cli acquire --source keil-delitzsch --output backend/data/commentaries/raw
```

Expected: each command reports only approved HTTPS URLs, a SHA-256 checksum, downloaded books/chapters, and no failed artifacts.

- [ ] **Step 4: Stage, validate, and generate coverage**

For each source, run `stage`, then use the emitted run UUID for `validate` and `report`. Expected: zero errors; warnings are reviewed individually; the report's source book/entry counts agree with upstream metadata or contain an explained variance.

- [ ] **Step 5: Publish and smoke-test one source at a time**

Run `publish --run-id <reviewed-run-id> --confirm`, then request:

```bash
curl -fsS 'http://localhost:8000/api/v1/commentaries/entries?source=matthew-henry&book=Genesis&chapter=1&verse=1'
```

Expected: the response identifies the published source and edition, includes a citation and nonblank entry when the source covers the verse, and contains no staged records. Repeat with the other four source IDs and one known covered reference per source.

- [ ] **Step 6: Commit metadata and ignore rules, not downloaded text**

```bash
git add .gitignore backend/data/commentaries/sources.json
git commit -m "data: register verified public domain commentaries"
```

## Task 13: Add browser-level accessibility and responsive coverage

**Files:**
- Modify: `frontend/e2e/scripture-reader-accessibility.spec.js`

- [ ] **Step 1: Write failing browser tests**

Intercept commentary source and entry routes with deterministic published fixtures. Test desktop and a 390-by-844 mobile viewport. Cover opening Study Tools, selecting Commentary, chapter overview, verse selection, source change, range status, copy feedback, Escape close/focus restoration, 200-percent zoom, no horizontal document overflow, light/dark contrast smoke checks, reduced motion, and `axe` with no serious or critical violations.

```javascript
await page.getByRole('button', { name: 'Open study tools' }).click()
await page.getByRole('button', { name: 'Commentary' }).click()
await expect(page.getByRole('heading', { name: 'Genesis 1 commentary' })).toBeVisible()
await page.getByRole('button', { name: /^Genesis 1 verse 1/ }).click()
await expect(page.getByText('Commentary for Genesis 1:1')).toBeVisible()
```

- [ ] **Step 2: Run the focused browser tests and verify failure**

Run: `npm run test:e2e -- scripture-reader-accessibility.spec.js --project=chromium`

Working directory: `frontend`

Expected: new Commentary assertions fail before the complete integration is available.

- [ ] **Step 3: Classify any browser-test failure before changing code**

If the command fails, record the exact failing assertion and reproduce it in the nearest component test file named in Task 13. Return to the relevant prior task's explicit test-first step, make the smallest correction described by that task, and rerun that component test before rerunning Playwright. If the command passes, make no production change in this step.

- [ ] **Step 4: Run browser and component suites**

Run: `npm run test:e2e -- scripture-reader-accessibility.spec.js --project=chromium`

Run: `npm test -- --run src/reader/commentaryApi.test.js src/reader/CommentaryPanel.test.jsx src/reader/StudyTools.test.jsx src/reader/ScriptureReaderPage.test.jsx src/reader/ScripturePane.test.jsx`

Working directory: `frontend`

Expected: all focused tests pass with no serious/critical axe findings and no horizontal overflow.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/scripture-reader-accessibility.spec.js frontend/src/reader
git commit -m "test: verify commentary reader accessibility"
```

## Task 14: Run the release quality gate

**Files:**
- Modify only files required by a reproduced failing test.

- [ ] **Step 1: Run backend commentary and migration suites**

Run: `uv run pytest backend/tests/commentary backend/tests/library backend/tests/migrations backend/tests/test_application.py -v`

Expected: all tests pass.

- [ ] **Step 2: Run the full backend suite**

Run: `uv run pytest -q`

Expected: all backend tests pass.

- [ ] **Step 3: Run frontend unit tests, lint, and production build**

Run: `npm test -- --run`

Run: `npm run lint`

Run: `npm run build`

Working directory: `frontend`

Expected: all tests pass, lint reports no errors, and Vite creates the production bundle.

- [ ] **Step 4: Run the Scripture reader browser suite**

Run: `npm run test:e2e -- scripture-reader-accessibility.spec.js --project=chromium`

Working directory: `frontend`

Expected: the complete reader accessibility suite passes.

- [ ] **Step 5: Perform a manual source-authenticity audit**

For one chapter overview and two verse entries from each published source, compare the displayed text, source name, reference/range, citation, and license metadata against the acquired checksum-protected artifact. Confirm AI copy is absent from published commentary and missing records show an explicit availability state.

- [ ] **Step 6: Review the final diff and commit any test-driven corrections**

Run: `git diff --check`

Run: `git status --short`

Expected: no whitespace errors, no raw commentary downloads or coverage artifacts staged, and only intentional feature files changed.

If the quality gate required corrections, commit them:

```bash
git add backend/app/commentary backend/tests/commentary frontend/src/reader frontend/e2e/scripture-reader-accessibility.spec.js docs/operations/commentary-import.md
git commit -m "fix: complete commentary release quality gate"
```

## First-release acceptance gate

- All five source records have independently reviewed provenance and redistribution status.
- Every published edition has zero blocking validation errors and a reviewed coverage report.
- The public reader serves only immutable locally published entries.
- Chapter overview and verse/range commentary work inside the existing Study Tools drawer and mobile sheet.
- Scripture stays primary, and verse selection remains compatible with notes, markers, copying, keyboard navigation, and assistive technology.
- Every entry displays source identity and a copyable citation.
- No hard-coded or AI-generated prose is presented as published commentary.
- Light/dark themes, mobile layouts, 200-percent zoom, keyboard use, and automated accessibility checks pass.
- Backend tests, frontend tests, lint, production build, and focused browser tests are green.
