# Ethiopian Bible Phase 3: Verified Source Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the Ethiopian canon with the broadest lawful English-first collection available, preserve truthful recension labels, and publish an auditable coverage report for all canon entries.

**Architecture:** Add source-specific adapters backed by frozen fixtures and strict manifests, acquire authorized remote editions into a local cache, then stage, validate, review, and publish each edition independently through Phase 2. Record explicit translation-needed coverage instead of creating scripture placeholders where lawful English is unavailable.

**Tech Stack:** Python 3.12, httpx, BeautifulSoup, USFM parsing, Pydantic, SQLAlchemy, Pytest, SQLite/PostgreSQL

---

## File Map

- Create `backend/app/library/ingest/adapters/base.py`: adapter protocol.
- Create `backend/app/library/ingest/adapters/usfm.py`: structured eBible ingestion.
- Create `backend/app/library/ingest/adapters/ertale.py`: provenance-aware public-domain transcription ingestion.
- Create `backend/app/library/ingest/adapters/wikisource.py`: CC BY-SA export ingestion.
- Create `backend/app/library/ingest/acquire.py`: verified TLS, caching, checksums, retries, and rate limits.
- Create `backend/app/library/sources/*.json`: one manifest per independently identified edition.
- Create `backend/tests/library/ingest/fixtures/`: small frozen source extracts and expected normalized rows.
- Create `backend/app/library/coverage.py`: collection coverage report.
- Create `backend/app/library/quarantine.py`: placeholder discovery and quarantine report.
- Create `docs/scripture-sources.md`: human-readable attribution and limitations.

## Approved Initial Edition Registry

Create separate manifests for these editions; never combine them under `ETH81`:

| Edition code | Coverage purpose | Relationship | License |
|---|---|---|---|
| `KJV1769` | Shared 66-book English reading text | general reading | Public domain |
| `KJV-APOCRYPHA` | Tobit, Judith, Wisdom, Sirach, Baruch, additions, Esdras, Manasseh | related recension | Public domain |
| `RV-APOCRYPHA` | Complete 2 Esdras 7 long fragment | related recension | Public domain |
| `BRENTON-LXX` | Psalm 151 and LXX comparison | related recension | Public domain |
| `ENOCH-CHARLES-1912` | 1 Enoch | exact Ethiopian-derived English | Public domain |
| `JUBILEES-CHARLES-1902` | Jubilees | exact Ethiopian-derived English | Public domain |
| `MEQ1-WIKISOURCE`, `MEQ2-WIKISOURCE`, `MEQ3-WIKISOURCE` | Meqabyan 1-3 | exact Ethiopian-derived English | CC BY-SA 4.0 |
| `DIDASCALIA-HARDEN-1920` | Didesqelya | exact Ethiopian-derived English | Public domain |
| `TEEZAZ-HORNER-1904` | Tizaz | exact Ethiopian-derived English | Public domain |
| `ABTILIS-SCHODDE-1885` | Abtilis | exact Ethiopian-derived English | Public domain |
| `KIDAN1-COOPER-1902` | Metsihafe Kidan I | related Syriac recension | Public domain |
| `KIDAN2-JAMES-1924` | Metsihafe Kidan II related material | related recension | Public domain in the US |
| `QALEMENTOS2-JAMES-1924` | Public-domain portion of Qalementos | related/partial | Public domain in the US |

Do not use the 1972 CCAT 4 Baruch text because its non-commercial restriction is incompatible with an unrestricted application distribution. Register a public-domain earlier edition only after its transcription and provenance are verified.

## Standard Per-Edition Runbook

Use this exact sequence for every manifest in Tasks 3-6, replacing the manifest filename and the run UUID printed by `stage`:

```bash
export DATABASE_URL=sqlite:////tmp/unbound-source-review.db
PYTHONPATH=backend uv run python -m app.library.ingest.cli stage --manifest backend/app/library/sources/kjv1769.json
PYTHONPATH=backend uv run python -m app.library.ingest.cli validate --run-id "$RUN_ID"
PYTHONPATH=backend uv run python -m app.library.ingest.cli coverage-report --run-id "$RUN_ID" --format markdown
PYTHONPATH=backend uv run python -m app.library.ingest.cli publish --run-id "$RUN_ID" --confirm
PYTHONPATH=backend uv run python -m app.library.ingest.cli coverage-report --canon ETHIO81 --format markdown
```

Expected: `stage` prints a UUID; `validate` reports zero errors; warnings match the manifest's declared recension/OCR limitations; `publish` reports one activated edition; the final report still totals 46 OT plus 35 NT. Stop before publication if any observed count differs from the manifest.

### Task 1: Implement Secure, Reproducible Acquisition

**Files:**
- Create: `backend/app/library/ingest/acquire.py`
- Create: `backend/tests/library/ingest/test_acquire.py`

- [ ] **Step 1: Write failing acquisition tests**

Use `httpx.MockTransport` to prove acquisition verifies HTTPS, sends `UnboundBibleSourceVerifier/1.0`, rejects redirects to non-HTTPS origins, enforces a 20-second timeout, retries only 429/502/503/504 responses, limits response bytes, saves by SHA-256 checksum, and returns the cached file on an unchanged ETag.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_acquire.py -q`

- [ ] **Step 3: Implement `SourceAcquirer`**

Use `httpx.Client(verify=True, follow_redirects=False, timeout=20)` and a configurable 50 MiB maximum. Cache under `var/scripture-sources/<edition>/<sha256>` and store response URL, ETag, Last-Modified, content type, bytes, and checksum in a sidecar JSON file. Never execute downloaded content.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest backend/tests/library/ingest/test_acquire.py -q`

```bash
git add backend/app/library/ingest/acquire.py backend/tests/library/ingest/test_acquire.py
git commit -m "feat: acquire scripture sources reproducibly"
```

### Task 2: Add Adapter Contracts and Frozen Fixtures

**Files:**
- Create: `backend/app/library/ingest/adapters/base.py`
- Create: `backend/app/library/ingest/adapters/usfm.py`
- Create: `backend/app/library/ingest/adapters/ertale.py`
- Create: `backend/app/library/ingest/adapters/wikisource.py`
- Create: `backend/tests/library/ingest/test_adapters.py`
- Create: `backend/tests/library/ingest/fixtures/`

- [ ] **Step 1: Write failing adapter contract tests**

For each adapter, parse a committed two-chapter fixture and assert exact `NormalizedVerse` output, work ID, chapter/verse positions, source locator, attribution, and deterministic row checksum. Include malformed markup, duplicate verse, and chapter-heading fixtures.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_adapters.py -q`

- [ ] **Step 3: Implement the adapter protocol**

```python
class SourceAdapter(Protocol):
    def parse(self, source_path: Path, manifest: SourceManifest) -> Iterable[NormalizedVerse]: ...
```

The USFM adapter handles `\id`, `\c`, `\v`, continuation lines, and canonical book maps. The Ertale adapter accepts only `.verse[id] .verse-text`, rejects unexpected page metadata, and preserves the page URL as locator. The Wikisource adapter parses exported page text and attaches `CC-BY-SA-4.0` attribution; it must not scrape rendered HTML.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest backend/tests/library/ingest/test_adapters.py -q`

```bash
git add backend/app/library/ingest/adapters backend/tests/library/ingest/test_adapters.py backend/tests/library/ingest/fixtures
git commit -m "feat: parse verified scripture source formats"
```

### Task 3: Register and Import the Shared English Corpus

**Files:**
- Create: `backend/app/library/sources/kjv1769.json`
- Create: `backend/tests/library/ingest/test_source_manifests.py`
- Modify: `docs/scripture-sources.md`

- [ ] **Step 1: Add a failing manifest coverage test**

Load `kjv1769.json` and assert 66 expected work IDs, Genesis has 50 chapters, Revelation has 22, the license is `LicenseRef-Public-Domain`, and relationship is `general_reading`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_source_manifests.py -q -k kjv`

- [ ] **Step 3: Add the manifest and attribution**

Use the eBible KJV landing page as provenance and its structured USFM archive as the acquisition URL. Record KJV as an English reading edition shared by the Ethiopian canon, not as an Ethiopian recension.

- [ ] **Step 4: Acquire, stage, validate, and review without publishing**

Run the CLI against a disposable copy of the active database. Expected validation: 66 works, 1,189 chapters, 31,102 verses, zero errors; document any source-specific count difference before proceeding.

- [ ] **Step 5: Publish only after the review report is clean**

Publish `KJV1769`, rerun the same import to prove idempotency, and confirm Genesis 1 returns `KJV1769` while canon count remains 81.

- [ ] **Step 6: Commit manifest, tests, and attribution**

```bash
git add backend/app/library/sources/kjv1769.json backend/tests/library/ingest/test_source_manifests.py docs/scripture-sources.md
git commit -m "data: register public-domain KJV reading text"
```

Do not commit the production database or downloaded cache.

### Task 4: Import Deuterocanonical and Related-Recension English Editions

**Files:**
- Create: `backend/app/library/sources/kjv-apocrypha.json`
- Create: `backend/app/library/sources/rv-apocrypha.json`
- Create: `backend/app/library/sources/brenton-lxx.json`
- Modify: `backend/tests/library/ingest/test_source_manifests.py`
- Modify: `docs/scripture-sources.md`

- [ ] **Step 1: Add failing expected-work tests**

Assert each work is mapped once, 2 Esdras uses `RV-APOCRYPHA`, Psalm 151 uses `BRENTON-LXX`, additions to Esther and Daniel remain navigable subworks, and every edition is `related_recension`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/ingest/test_source_manifests.py -q -k 'apocrypha or brenton'`

- [ ] **Step 3: Add manifests and source notes**

Record that these are Greek/Latin/LXX-related English readings rather than exact Ge'ez recensions. Keep Baruch, Letter of Jeremiah, Esther additions, and Daniel additions mapped to their official composite canon entries.

- [ ] **Step 4: Stage and publish edition by edition**

For each edition: acquire, checksum, stage, validate, inspect warnings, publish, and generate coverage. Do not combine them into a synthetic translation code.

- [ ] **Step 5: Commit**

```bash
git add backend/app/library/sources/kjv-apocrypha.json backend/app/library/sources/rv-apocrypha.json backend/app/library/sources/brenton-lxx.json backend/tests/library/ingest/test_source_manifests.py docs/scripture-sources.md
git commit -m "data: add public-domain related canon editions"
```

### Task 5: Import Ethiopian-Derived English Texts

**Files:**
- Create: `backend/app/library/sources/enoch-charles-1912.json`
- Create: `backend/app/library/sources/jubilees-charles-1902.json`
- Create: `backend/app/library/sources/meq1-wikisource.json`
- Create: `backend/app/library/sources/meq2-wikisource.json`
- Create: `backend/app/library/sources/meq3-wikisource.json`
- Modify: `backend/tests/library/ingest/test_source_manifests.py`
- Modify: `docs/scripture-sources.md`

- [ ] **Step 1: Add failing source and chapter-system tests**

Assert Enoch has 108 chapters, Jubilees 50, Meqabyan 2 has 21, Meqabyan 3 has 10, and Meqabyan 1 records the seven-chapter community structure without pretending it is the traditional 36-chapter system. Assert CC BY-SA attribution is non-empty for all Meqabyan manifests.

- [ ] **Step 2: Add verified manifests**

Use the cited Charles editions and Wikisource export pages. `source_tradition` must say `translated from Ge'ez`; `relationship` is `exact_ethiopian` while the Meqabyan 1 versification note discloses its different chapter division.

- [ ] **Step 3: Stage, validate, and publish separately**

Expected hard gates: no placeholder prose, no duplicate positions, exact observed chapter counts, CC BY-SA attribution retained in edition metadata and documentation.

- [ ] **Step 4: Commit**

```bash
git add backend/app/library/sources/enoch-charles-1912.json backend/app/library/sources/jubilees-charles-1902.json backend/app/library/sources/meq1-wikisource.json backend/app/library/sources/meq2-wikisource.json backend/app/library/sources/meq3-wikisource.json backend/tests/library/ingest/test_source_manifests.py docs/scripture-sources.md
git commit -m "data: add Ethiopian-derived English editions"
```

Stage only the five new manifest files, not unrelated files already present in the directory.

### Task 6: Import Available Church-Order Texts and Record Gaps

**Files:**
- Create: `backend/app/library/sources/didascalia-harden-1920.json`
- Create: `backend/app/library/sources/teezaz-horner-1904.json`
- Create: `backend/app/library/sources/abtilis-schodde-1885.json`
- Create: `backend/app/library/sources/kidan1-cooper-1902.json`
- Create: `backend/app/library/sources/kidan2-james-1924.json`
- Create: `backend/app/library/sources/qalementos2-james-1924.json`
- Create: `backend/app/library/sources/coverage-gaps.json`
- Modify: `backend/tests/library/ingest/test_source_manifests.py`
- Modify: `docs/scripture-sources.md`

- [ ] **Step 1: Add failing recension and gap tests**

Assert Didascalia, Te'ezaz, and Abtilis are labeled Ethiopian-derived; Kidan I, Kidan II, and Qalementos II are partial or related recensions; Sirate Tsion, Gitsew, untranslated Qalementos portions, and any unverified work receive `translation_needed` coverage without a scripture row.

- [ ] **Step 2: Add manifests and explicit limitations**

Record OCR warnings, single-verse-per-chapter structure where applicable, source publication details, and exact public-domain basis. Do not use modern copyrighted compilations.

- [ ] **Step 3: Stage and publish only validated editions**

Warnings require an operator review record. Translation-needed entries update `edition_coverage` through a non-text coverage command and never enter `biblical_texts`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/library/sources/didascalia-harden-1920.json backend/app/library/sources/teezaz-horner-1904.json backend/app/library/sources/abtilis-schodde-1885.json backend/app/library/sources/kidan1-cooper-1902.json backend/app/library/sources/kidan2-james-1924.json backend/app/library/sources/qalementos2-james-1924.json backend/app/library/sources/coverage-gaps.json backend/tests/library/ingest/test_source_manifests.py docs/scripture-sources.md
git commit -m "data: register church-order texts and coverage gaps"
```

### Task 7: Quarantine Existing Placeholder Scripture

**Files:**
- Create: `backend/app/library/quarantine.py`
- Create: `backend/tests/library/test_quarantine.py`

- [ ] **Step 1: Write failing detection tests**

Seed rows containing `[Book - description]`, `Awaiting full Ge'ez source text`, `This book is part of...`, and real short verses. Assert only placeholders are reported and no rows are deleted during scan mode.

- [ ] **Step 2: Implement report and confirmed quarantine modes**

Quarantine copies matching rows into an audit JSON export, records IDs and checksums, then marks them non-latest or removes them only inside a confirmed transaction. Default command is report-only.

- [ ] **Step 3: Verify against a database copy**

Generate the report, review every match, quarantine with confirmation, and rerun validation. Expected: zero published placeholder matches and no loss of verified verses.

- [ ] **Step 4: Commit code and tests, not generated reports**

```bash
git add backend/app/library/quarantine.py backend/tests/library/test_quarantine.py
git commit -m "fix: quarantine placeholder scripture records"
```

### Task 8: Generate the Canon Coverage Report

**Files:**
- Create: `backend/app/library/coverage.py`
- Create: `backend/tests/library/test_coverage.py`
- Create: `docs/ethiopian-bible-coverage.md`

- [ ] **Step 1: Write a failing 81-entry coverage test**

Assert the report has exactly 81 counted entries, every navigation work appears under one entry, Genesis selects `KJV1769`, unavailable Qalementos portions show `translation_needed`, and totals reconcile by status.

- [ ] **Step 2: Implement JSON and Markdown renderers**

Each row contains counted entry, navigable work, best English edition, Ethiopian-derived edition, related edition, status, license, and note. Sort by testament and official entry order.

- [ ] **Step 3: Generate and inspect the report**

Run coverage report against the staged production database copy. Correct metadata inconsistencies at source; never hand-edit generated status rows.

- [ ] **Step 4: Commit report code, tests, and reviewed snapshot**

```bash
git add backend/app/library/coverage.py backend/tests/library/test_coverage.py docs/ethiopian-bible-coverage.md
git commit -m "docs: publish Ethiopian Bible coverage report"
```

### Task 9: Phase 3 Quality Gate

- [ ] Run all backend and ingestion tests: `uv run pytest backend/tests -q`.
- [ ] Run every manifest through license, checksum, adapter, coverage, and placeholder validation.
- [ ] Confirm no downloaded cache or database file is staged by Git.
- [ ] Confirm every active edition can roll back to its previous publication.
- [ ] Confirm the coverage report totals 46 OT plus 35 NT and clearly identifies every remaining translation gap.

## Phase 3 Exit Criteria

- Genesis and the shared corpus have a lawful English reading edition.
- Additional works use independently named and attributed editions.
- Related recensions are never labeled exact Ge'ez translations.
- CC BY-SA attribution is retained.
- Remaining lawful-English gaps are explicit data, not placeholders.
- All source downloads, checksums, validation findings, and publications are auditable.
