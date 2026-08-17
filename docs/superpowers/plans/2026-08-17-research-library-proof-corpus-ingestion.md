# Research Library Proof Corpus Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, review-gated ingestion pipeline and publish a proof corpus consisting of WEB plus the repository’s already-sourced 1 Enoch and Jubilees content.

**Architecture:** Reuse the existing stage/validate/publish discipline while targeting immutable `SourcePublication`, `ContentUnit`, and `CitationAnchor` rows. Acquisition stays separate from parsing. Manifests carry checksums and asserted metadata; an administrator must attach a reviewed `LicenseRecord` before activation. Publishing is atomic and idempotent.

**Tech Stack:** Python 3.11, Typer, Pydantic 2, SQLAlchemy 2, PostgreSQL/SQLite, pytest, existing library ingestion adapters.

---

## Scope and ordering

This is plan 2 of 4. Start only after the core rights plan is merged. Do not download or publish new Internet material in this plan; use repository-local, provenance-recorded source artifacts.

### Task 1: Define a generalized source manifest and normalized unit contract

**Files:**
- Create: `backend/app/research_library/ingest/__init__.py`
- Create: `backend/app/research_library/ingest/manifest.py`
- Create: `backend/app/research_library/ingest/types.py`
- Create: `backend/tests/research_library/ingest/test_manifest.py`
- Create: `backend/tests/research_library/ingest/__init__.py`

- [ ] Write failing strict-validation tests for source artifacts, edition metadata, work/division maps, checksums, rights record reference, and adapter name.
- [ ] Run `uv run pytest backend/tests/research_library/ingest/test_manifest.py -q` and confirm the missing module failure.
- [ ] Implement `ResearchSourceManifest` with `extra='forbid'`, normalized identifiers, SHA-256 validation, local relative artifact paths, and no network URL as an input path.

```python
class SourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(pattern=r"^(?!/)(?!.*\.\.).+$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

class ResearchSourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_edition_id: uuid.UUID
    adapter: Literal["scripture_rows", "enoch_sections", "jubilees_chapters"]
    artifacts: list[SourceArtifact] = Field(min_length=1)
    work_id: str
    language: str
    expected_units: int = Field(gt=0)
    source_note: str = Field(min_length=1, max_length=4000)
```

- [ ] Implement immutable `NormalizedContentUnit` and `NormalizedAnchor` dataclasses. Compute unit checksums from publication-independent canonical fields.
- [ ] Run the test and confirm it passes.
- [ ] Commit with `git add backend/app/research_library/ingest backend/tests/research_library/ingest && git commit -m "feat: define research source ingest contract"`.

### Task 2: Implement staging runs and deterministic validation

**Files:**
- Create: `backend/app/research_library/ingest/models.py`
- Create: `backend/app/research_library/ingest/stage.py`
- Create: `backend/app/research_library/ingest/validate.py`
- Create: `backend/alembic/versions/0016_research_source_ingest.py`
- Create: `backend/tests/research_library/ingest/test_stage_validate.py`

- [ ] Write failing tests for checksum mismatch, duplicate unit position, missing division, blank text, unexpected count, invalid anchor range, and a valid run becoming `verified`.
- [ ] Run `uv run pytest backend/tests/research_library/ingest/test_stage_validate.py -q` and confirm failures.
- [ ] Add staging models `ResearchIngestRun`, `StagedContentUnit`, `StagedCitationAnchor`, and `ResearchValidationFinding`; migrate them in revision `0016`.
- [ ] Implement staging that verifies every artifact before invoking an adapter and persists the normalized rows plus the exact manifest snapshot in one transaction.
- [ ] Implement deterministic validation with stable codes:

```python
ERROR_CODES = {
    "artifact_checksum_mismatch", "duplicate_unit_position", "division_missing",
    "blank_content", "expected_count_mismatch", "anchor_out_of_range",
    "source_locator_missing", "unit_checksum_mismatch",
}
```

Only a run with zero errors may become `verified`; warnings remain visible.
- [ ] Run `uv run pytest backend/tests/research_library/ingest/test_stage_validate.py backend/tests/migrations/test_research_library_core.py -q` and confirm all pass.
- [ ] Commit with `git add backend/app/research_library/ingest backend/alembic/versions/0016_research_source_ingest.py backend/tests/research_library/ingest && git commit -m "feat: stage and validate research sources"`.

### Task 3: Implement atomic publication and activation gate

**Files:**
- Create: `backend/app/research_library/ingest/publish.py`
- Create: `backend/tests/research_library/ingest/test_publish.py`

- [ ] Write failing tests proving publication refuses an unverified run, missing license, failed eligibility, checksum mutation, and concurrent active publication; prove idempotent retry and rollback to the immediate predecessor.
- [ ] Run `uv run pytest backend/tests/research_library/ingest/test_publish.py -q` and confirm the missing implementation failure.
- [ ] Implement publication in one transaction: lock the edition and history, revalidate staged checksums, create an immutable version, copy units and anchors, append audit events, then activate only after `evaluate_publication()` succeeds.

```python
def publish_run(session: Session, run_id: uuid.UUID, actor_id: uuid.UUID) -> PublicationResult:
    with atomic(session):
        run = lock_verified_run(session, run_id)
        edition = lock_source_edition(session, run.source_edition_id)
        prior = lock_publication_history(session, edition.id)
        units, anchors = verified_staged_content(session, run)
        existing = publication_for_run(prior, run.id)
        if existing is not None:
            return publication_result(existing, changed=False)
        publication = create_publication_snapshot(session, edition, run, prior)
        copy_publication_content(session, publication, units, anchors)
        activate_eligible_publication(session, publication, prior)
        append_publication_audit(session, actor_id, publication, prior)
        return publication_result(publication, changed=True)
```

Implement and unit-test every named helper in the same module; none may skip checksum, rights, validation, locking, or audit checks.
- [ ] Add a rollback command that never deletes history and reactivates only the immediately previous eligible publication.
- [ ] Run the publish tests and confirm all pass.
- [ ] Commit with `git add backend/app/research_library/ingest/publish.py backend/tests/research_library/ingest/test_publish.py && git commit -m "feat: publish immutable research sources"`.

### Task 4: Add proof-corpus adapters

**Files:**
- Create: `backend/app/research_library/ingest/adapters/__init__.py`
- Create: `backend/app/research_library/ingest/adapters/scripture_rows.py`
- Create: `backend/app/research_library/ingest/adapters/enoch_sections.py`
- Create: `backend/app/research_library/ingest/adapters/jubilees_chapters.py`
- Create: `backend/tests/research_library/ingest/fixtures/`
- Create: `backend/tests/research_library/ingest/test_adapters.py`

- [ ] Add small licensed test fixtures for Genesis 1 WEB, 1 Enoch chapters spanning all five approved section boundaries, and Jubilees chapters 1–2.
- [ ] Write failing adapter tests asserting normalized divisions, stable ordinals, source locators, anchors, and exact section boundaries for 1 Enoch: Watchers 1–36, Parables 37–71, Astronomical 72–82, Dream Visions 83–90, Epistle 91–108.
- [ ] Run `uv run pytest backend/tests/research_library/ingest/test_adapters.py -q` and confirm failures.
- [ ] Implement adapters as pure parsers. They may read only manifest-listed files and must reject unexpected books, chapters, or record shapes.
- [ ] Run the adapter tests and confirm all pass.
- [ ] Commit with `git add backend/app/research_library/ingest backend/tests/research_library/ingest && git commit -m "feat: add proof corpus source adapters"`.

### Task 5: Add operator commands and reviewed manifests

**Files:**
- Create: `backend/app/research_library/ingest/cli.py`
- Create: `backend/data/research_library/manifests/web.json`
- Create: `backend/data/research_library/manifests/first-enoch.json`
- Create: `backend/data/research_library/manifests/jubilees.json`
- Create: `backend/tests/research_library/ingest/test_cli.py`

- [ ] Write failing CLI tests for `stage`, `validate`, `inspect`, `publish`, `activate`, `restrict`, and `rollback`; assert JSON output and nonzero exit on missing database URL or actor.
- [ ] Run `uv run pytest backend/tests/research_library/ingest/test_cli.py -q` and confirm failures.
- [ ] Implement local-only Typer commands modeled on `backend/app/library/ingest/cli.py`. `publish`, `activate`, `restrict`, and `rollback` require an authenticated administrator user ID; `stage` and `validate` record the operator ID. Restriction takes a required reason, immediately removes the active state, invalidates cached eligibility, and appends an audit event.
- [ ] Create manifests using the repository’s actual source artifact paths and computed hashes. Do not invent licensing claims. Set sources awaiting documented review to `needs_rights_review` and stop before activation.
- [ ] Run the CLI tests and a dry inspection against a disposable migrated database.
- [ ] Commit with `git add backend/app/research_library/ingest backend/data/research_library/manifests backend/tests/research_library/ingest && git commit -m "feat: add proof corpus operator workflow"`.

### Task 6: Verify full proof-corpus publication

- [ ] In a disposable PostgreSQL database, migrate to head and register legacy catalog links.
- [ ] Stage and validate WEB, 1 Enoch, and Jubilees from the reviewed local artifacts.
- [ ] Attach administrator-reviewed license records with exact attribution and provenance evidence.
- [ ] Publish the three editions and run an integrity query confirming one active publication per edition, expected unit counts, no blank text, unique positions, and all anchors resolve.
- [ ] Run `uv run pytest backend/tests/research_library/ingest backend/tests/library/ingest backend/tests/commentary/ingest -q`.
- [ ] Run `git diff --check`.
- [ ] Commit the finalized manifests and evidence references with `git commit -am "data: verify research proof corpus"`.

## Completion criteria

- WEB, 1 Enoch, and Jubilees have reproducible manifests and immutable active publications.
- Rights uncertainty blocks public activation.
- Every public unit has a stable source locator, checksum, citation anchor, and visible attribution path.
- Re-running stage/publish is safe, and rollback preserves history.
