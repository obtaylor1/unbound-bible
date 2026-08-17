# Research Library Core Rights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generalized, source-aware research catalog with centralized rights, immutable publications, compatibility links, administrator authorization, and append-only audit history without disrupting the existing Scripture reader.

**Architecture:** Extend `library_works` rather than replacing it. New source editions publish immutable snapshots, and every public read passes through a single eligibility policy. Existing `text_editions`, `edition_work_sources`, `biblical_texts`, and commentary rows remain authoritative during migration and are connected through compatibility links. Administration uses the existing `User.role` field with an explicit `administrator` value and never infers privileges from an email address.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, PostgreSQL, SQLite test database, Typer, pytest.

---

## Scope and ordering

This is plan 1 of 4. Complete it before proof-corpus ingestion, hybrid retrieval, or the user/admin experience. It establishes the safety boundary those plans consume.

### Task 1: Lock the domain vocabulary in tests

**Files:**
- Create: `backend/tests/research_library/test_models.py`
- Create: `backend/tests/research_library/__init__.py`
- Create: `backend/app/research_library/__init__.py`
- Create: `backend/app/research_library/models.py`

- [ ] Write a failing model test covering valid work profiles, divisions, editions, licenses, edition/work joins, immutable publications, units, anchors, chunks, legacy links, and audit events.

```python
from app.research_library.models import (
    CitationAnchor,
    ContentUnit,
    LicenseRecord,
    ResearchChunk,
    ResearchWorkProfile,
    SourceAuditEvent,
    SourceEdition,
    SourceEditionWork,
    SourcePublication,
    WorkDivision,
)


def test_research_library_models_have_expected_tables():
    assert ResearchWorkProfile.__tablename__ == "research_work_profiles"
    assert WorkDivision.__tablename__ == "work_divisions"
    assert SourceEdition.__tablename__ == "source_editions"
    assert SourceEditionWork.__tablename__ == "source_edition_works"
    assert LicenseRecord.__tablename__ == "license_records"
    assert SourcePublication.__tablename__ == "source_publications"
    assert ContentUnit.__tablename__ == "content_units"
    assert CitationAnchor.__tablename__ == "citation_anchors"
    assert ResearchChunk.__tablename__ == "research_chunks"
    assert SourceAuditEvent.__tablename__ == "source_audit_events"
```

- [ ] Run `uv run pytest backend/tests/research_library/test_models.py -q` and confirm it fails with `ModuleNotFoundError: No module named 'app.research_library.models'`.

- [ ] Implement the SQLAlchemy models in `backend/app/research_library/models.py`. Use UUID primary keys, timezone-aware timestamps, named foreign keys, and check constraints. Required fields are:

```python
PUBLICATION_STATUSES = (
    "needs_rights_review", "importing", "verified", "active", "disabled",
    "restricted", "internal_research_only",
)

class ResearchWorkProfile(Base):
    __tablename__ = "research_work_profiles"
    work_id: Mapped[str] = mapped_column(
        ForeignKey("library_works.id", ondelete="CASCADE"), primary_key=True
    )
    work_type: Mapped[str] = mapped_column(String(40), nullable=False)
    tradition: Mapped[str | None] = mapped_column(String(120), nullable=True)
    original_language: Mapped[str | None] = mapped_column(String(80), nullable=True)
    date_or_era: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

class WorkDivision(Base):
    __tablename__ = "work_divisions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    work_id: Mapped[str] = mapped_column(ForeignKey("library_works.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_divisions.id", ondelete="CASCADE"), nullable=True)
    division_type: Mapped[str] = mapped_column(String(40), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(240), nullable=False)
```

Implement the remaining models with the exact relationships approved in the design spec: `SourceEdition`, `SourceEditionWork`, `LicenseRecord`, `SourcePublication`, `ContentUnit`, `CitationAnchor`, `ResearchChunk` (without a vector column until plan 3), `LegacySourceLink`, `LegacyContentLink`, and `SourceAuditEvent`. Put normalized content and checksums on immutable publication-owned rows. Add unique constraints for division position, edition/work membership, publication version, unit position, anchor key, chunk position, and legacy entity identity.

- [ ] Import the model module in `backend/app/application.py` so test metadata includes it.

```python
from app.research_library import models as research_library_models  # noqa: F401
```

- [ ] Run `uv run pytest backend/tests/research_library/test_models.py -q` and confirm it passes.

- [ ] Commit with `git add backend/app/research_library backend/tests/research_library backend/app/application.py && git commit -m "feat: add research library domain models"`.

### Task 2: Add the migration and database invariants

**Files:**
- Create: `backend/alembic/versions/0014_research_library_core.py`
- Create: `backend/tests/migrations/test_research_library_core.py`

- [ ] Write a migration test that upgrades from `0013_scripture_compatibility` to `0014_research_library_core`, inspects every new table/index/check constraint, and downgrades back to `0013_scripture_compatibility`.

```python
def test_research_library_upgrade_creates_catalog_tables(migrated_connection):
    command.upgrade(alembic_config(migrated_connection), "0014_research_library_core")
    tables = set(inspect(migrated_connection).get_table_names())
    assert {
        "research_work_profiles", "work_divisions", "source_editions",
        "source_edition_works", "license_records", "source_publications",
        "content_units", "citation_anchors", "research_chunks",
        "legacy_source_links", "legacy_content_links", "source_audit_events",
    } <= tables
```

- [ ] Run `uv run pytest backend/tests/migrations/test_research_library_core.py -q` and confirm the missing revision failure.

- [ ] Implement the migration with `down_revision = "0013_scripture_compatibility"`. Create tables in foreign-key order and drop them in reverse order. Add a PostgreSQL partial unique index enforcing one active publication per edition:

```python
op.create_index(
    "uq_source_publications_one_active",
    "source_publications",
    ["source_edition_id"],
    unique=True,
    postgresql_where=sa.text("status = 'active'"),
    sqlite_where=sa.text("status = 'active'"),
)
```

- [ ] Run the migration test and `uv run pytest backend/tests/migrations -q`; confirm all pass.

- [ ] Commit with `git add backend/alembic/versions/0014_research_library_core.py backend/tests/migrations/test_research_library_core.py && git commit -m "feat: migrate research library catalog"`.

### Task 3: Centralize rights and public eligibility

**Files:**
- Create: `backend/app/research_library/eligibility.py`
- Create: `backend/tests/research_library/test_eligibility.py`

- [ ] Write table-driven failing tests for every approved exclusion reason and one eligible publication.

```python
@pytest.mark.parametrize("change,reason", [
    ({"status": "verified"}, "publication_not_active"),
    ({"validation_approved": False}, "validation_not_approved"),
    ({"public_visibility": False}, "not_public"),
    ({"commercial_display_allowed": False}, "commercial_display_not_allowed"),
    ({"redistribution_allowed": False}, "redistribution_not_allowed"),
    ({"attribution_text": None}, "attribution_missing"),
])
def test_publication_eligibility_fails_closed(publication_bundle, change, reason):
    publication_bundle.apply(change)
    result = evaluate_publication(publication_bundle.publication)
    assert result.eligible is False
    assert reason in result.reasons
```

- [ ] Run `uv run pytest backend/tests/research_library/test_eligibility.py -q` and confirm the import failure.

- [ ] Implement a pure `evaluate_publication()` policy returning an immutable `EligibilityDecision`. It must require active status, approved validation, public visibility, permitted commercial display, permitted redistribution, displayable nonblank attribution, and no restricted/internal flags. Unknown or null rights values fail closed.

```python
@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    reasons: tuple[str, ...]

def evaluate_publication(publication: SourcePublication) -> EligibilityDecision:
    reasons: list[str] = []
    license_record = publication.license_record
    if publication.status != "active": reasons.append("publication_not_active")
    if not publication.validation_approved: reasons.append("validation_not_approved")
    if not publication.public_visibility: reasons.append("not_public")
    if license_record is None: reasons.append("license_missing")
    else:
        if license_record.commercial_display_allowed is not True:
            reasons.append("commercial_display_not_allowed")
        if license_record.redistribution_allowed is not True:
            reasons.append("redistribution_not_allowed")
        if not (license_record.attribution_text or "").strip():
            reasons.append("attribution_missing")
    return EligibilityDecision(not reasons, tuple(reasons))
```

- [ ] Add a SQL predicate builder for public list/retrieval queries. Test it against real rows so Python evaluation and database filtering return identical IDs.

- [ ] Run `uv run pytest backend/tests/research_library/test_eligibility.py -q` and confirm all pass.

- [ ] Commit with `git add backend/app/research_library/eligibility.py backend/tests/research_library/test_eligibility.py && git commit -m "feat: enforce source publication eligibility"`.

### Task 4: Make administrator assignment explicit and auditable

**Files:**
- Modify: `backend/app/auth/models.py`
- Modify: `backend/app/auth/dependencies.py`
- Create: `backend/app/research_library/admin_cli.py`
- Create: `backend/app/research_library/audit.py`
- Create: `backend/tests/research_library/test_admin_roles.py`
- Create: `backend/alembic/versions/0015_administrator_role.py`

- [ ] Write failing tests proving new users default to `reader`, `administrator` is accepted, legacy `member` and `admin` values migrate deterministically, and a non-administrator receives 403.

- [ ] Run `uv run pytest backend/tests/research_library/test_admin_roles.py -q` and confirm failures show the current `member`/`admin` vocabulary.

- [ ] Change the application vocabulary to `reader` and `administrator`:

```python
class User(Base):
    # existing columns remain unchanged
    role: Mapped[str] = mapped_column(String(20), default="reader", server_default="reader")

def require_administrator(user: User = Depends(get_current_user)) -> User:
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user
```

Keep `require_admin = require_administrator` temporarily for compatibility and add a removal note to the release checklist, not application behavior.

- [ ] Implement migration `0015_administrator_role.py`, revising `member -> reader` and `admin -> administrator`, setting the server default to `reader`, and adding a role check constraint.

- [ ] Add a protected one-time operator command. It accepts `--user-id` and `--confirmation`, requires confirmation text `GRANT-ADMINISTRATOR`, refuses inactive/missing users, refuses to demote, and appends a `SourceAuditEvent` with actor, target user ID, previous role, and new role. It must not accept or inspect email addresses.

- [ ] Run `uv run pytest backend/tests/research_library/test_admin_roles.py backend/tests/auth -q` and confirm all pass.

- [ ] Commit with `git add backend/app/auth backend/app/research_library backend/tests/research_library backend/alembic/versions/0015_administrator_role.py && git commit -m "feat: add explicit administrator authorization"`.

### Task 5: Register legacy catalog compatibility without copying content

**Files:**
- Create: `backend/app/research_library/compatibility.py`
- Create: `backend/app/research_library/compatibility_cli.py`
- Create: `backend/tests/research_library/test_compatibility.py`

- [ ] Write failing tests that seed a `TextEdition`, `EditionWorkSource`, `EditionCoverage`, and commentary source; run registration twice; and assert stable, nonduplicated `LegacySourceLink` records.

- [ ] Run `uv run pytest backend/tests/research_library/test_compatibility.py -q` and confirm the missing implementation failure.

- [ ] Implement idempotent registration. Scripture links use `legacy_type="text_edition"`, `legacy_key=TextEdition.edition_code`; per-work links use `legacy_type="edition_work_source"`; commentary links use the existing commentary source primary key. Create catalog shells with `needs_rights_review`; never infer approved rights from a legacy license string.

```python
def register_legacy_sources(session: Session, actor_id: uuid.UUID) -> RegistrationResult:
    editions = tuple(session.scalars(select(TextEdition).order_by(TextEdition.edition_code)))
    created = 0
    for edition in editions:
        link = session.scalar(select(LegacySourceLink).where(
            LegacySourceLink.legacy_type == "text_edition",
            LegacySourceLink.legacy_key == edition.edition_code,
        ))
        if link is not None:
            continue
        source = SourceEdition(name=edition.name, language=edition.reading_language)
        session.add(source)
        session.flush()
        session.add(LegacySourceLink(
            source_edition_id=source.id,
            legacy_type="text_edition",
            legacy_key=edition.edition_code,
        ))
        created += 1
    append_audit_event(session, actor_id, "legacy_sources_registered", {"created": created})
    return RegistrationResult(created=created)
```

- [ ] Expose `python -m app.research_library.compatibility_cli register --database-url ... --actor-id ...` with JSON output and transaction rollback on any failure.

- [ ] Run `uv run pytest backend/tests/research_library/test_compatibility.py backend/tests/library backend/tests/commentary -q` and confirm all pass.

- [ ] Commit with `git add backend/app/research_library backend/tests/research_library && git commit -m "feat: register legacy sources in research catalog"`.

### Task 6: Core regression and handoff

- [ ] Run `uv run pytest backend/tests/research_library backend/tests/migrations backend/tests/auth backend/tests/library backend/tests/commentary -q`.
- [ ] Run `uv run ruff check backend/app backend/tests` if Ruff is available; otherwise run the repository's configured backend lint command and record it in the commit message body.
- [ ] Run `uv run alembic -c backend/alembic.ini upgrade head` against a disposable PostgreSQL database and confirm revisions `0014` and `0015` succeed.
- [ ] Inspect `git diff --check` and confirm no whitespace errors.
- [ ] Confirm no operator command grants access by email: `rg -n "obtaylor@gmail|grant.*email|email.*administrator" backend/app backend/tests` must return no application match.
- [ ] Commit any verification-only adjustments with `git commit -am "test: verify research library safety boundary"`.

## Completion criteria

- Every public-source decision uses the centralized policy.
- No mutable content row is treated as a published snapshot.
- Existing Scripture and commentary APIs still pass their suites.
- Obie Taylor can be granted administrator access only through the explicit user-ID operator command after authentication creates the account.
- Existing editions are linked, not copied or silently re-licensed.
