# Scripture Source Verification and Progressive Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep all 83 supplied works readable while adding reproducible work-level provenance, honest public status labels, deterministic source comparison, and reviewed official-source replacement for the 73 works with incomplete provenance.

**Architecture:** Extend the existing `EditionWorkSource`, manifest, verified-ingest, and atomic-publication paths rather than building a second scripture store. A local-only verification package freezes source artifacts, parses each source family through a dedicated adapter, compares normalized positions, writes deterministic evidence, and produces reviewed replacement candidates; public and admin APIs expose safe status data, while the reader and comparison workspace render plain-language disclosures.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Typer, pytest, React 19, Vitest, Testing Library, Playwright, axe-core.

---

## Scope and Delivery Structure

This plan is implemented as five independently reversible milestones:

1. verification foundation and public labels;
2. 39 World Messianic Bible works;
3. 27 Murdock Peshitta works;
4. six KJV fallback works;
5. Jubilees plus final production audit.

Every milestone ends with a commit and a healthy readable edition. Source-family work cannot mark unrelated works verified.

## File Structure

### Backend foundation

- Create `backend/alembic/versions/0011_scripture_work_verification.py` — migrate work-level statuses and evidence columns.
- Modify `backend/app/library/models.py` — persist work-level evidence and comparison totals.
- Modify `backend/app/library/ingest/manifest.py` — validate the five approved statuses and evidence contract.
- Modify `backend/app/library/ingest/publish.py` — atomically promote and compare expanded work-source records.
- Create `backend/app/library/verification/types.py` — immutable source verse, comparison, and report types.
- Create `backend/app/library/verification/normalize.py` — declared comparison normalization only.
- Create `backend/app/library/verification/compare.py` — complete-position comparator.
- Create `backend/app/library/verification/report.py` — deterministic JSON/Markdown evidence writer.
- Create `backend/app/library/verification/registry.py` — strict local source-registry loader and artifact checksum gate.
- Create `backend/app/library/verification/cli.py` — local acquisition registration, comparison, and candidate-build commands.
- Create `backend/app/library/verification/adapters/` — one parser module per source family.
- Modify `backend/app/library/router.py` — public source details and admin progress endpoints.
- Create `backend/app/library/schemas.py` — bounded public/admin response models.

### Composite edition data

- Create `backend/data/scripture/eotc-composite-en/verification/source-registry.json` — reviewed source definitions.
- Create `backend/data/scripture/eotc-composite-en/verification/source-artifacts.lock.json` — generated immutable URL/file/checksum/retrieval records.
- Create `backend/data/scripture/eotc-composite-en/verification/reports/` — deterministic work reports.
- Modify `backend/data/scripture/eotc-composite-en/build_bundle.py` — consume verified family outputs.
- Modify `backend/data/scripture/eotc-composite-en/build_manifest.py` — emit expanded work-level evidence/status.
- Modify `backend/data/scripture/eotc-composite-en/README.md` — document commands, source identity, rights evidence, and collection naming.

### Frontend

- Modify `frontend/src/reader/scriptureApi.js` — normalize expanded source evidence.
- Create `frontend/src/reader/sourceVerification.js` — centralize the public status-to-label mapping.
- Modify `frontend/src/reader/TextSourceDisclosure.jsx` — render all public status labels and safe evidence.
- Modify `frontend/src/reader/readerTokens.css` — accessible badge and evidence-detail styling.
- Modify `frontend/src/components/TextualComparisonWorkspace.jsx` — reuse the same status disclosure.
- Modify `frontend/src/components/TextualComparisonWorkspace.css` — shared comparison-card status styles.
- Create `frontend/src/admin/ScriptureVerificationPage.jsx` — authenticated verification inventory.
- Create `frontend/src/admin/scriptureVerificationApi.js` — admin progress client.
- Modify `frontend/src/routing/pageRoutes.js` and `frontend/src/App.jsx` — register the admin-only page route.

---

### Task 1: Migrate the work-level verification contract

**Files:**
- Create: `backend/alembic/versions/0011_scripture_work_verification.py`
- Modify: `backend/app/library/models.py`
- Test: `backend/tests/migrations/test_scripture_work_verification.py`
- Test: `backend/tests/library/ingest/test_schema.py`

- [ ] **Step 1: Write failing migration and model tests**

Add assertions for the five statuses and every evidence field:

```python
EXPECTED_STATUSES = {
    'in_progress', 'verified_exact', 'verified_formatting',
    'verified_rebuilt', 'review_required',
}

def test_work_source_has_reproducible_verification_evidence(migrated_connection):
    columns = {
        column['name']
        for column in sa.inspect(migrated_connection).get_columns('edition_work_sources')
    }
    assert {
        'source_edition', 'source_revision', 'rights_url', 'rights_jurisdiction',
        'artifact_filename', 'artifact_retrieved_at', 'artifact_size',
        'artifact_sha256', 'parser_version', 'transformations',
        'comparison_exact', 'comparison_formatting', 'comparison_missing',
        'comparison_extra', 'comparison_wording', 'comparison_report_sha256',
        'reviewer', 'reviewed_at', 'review_note',
    } <= columns
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest backend/tests/migrations/test_scripture_work_verification.py backend/tests/library/ingest/test_schema.py -q`

Expected: FAIL because revision `0011_scripture_work_verification` and the evidence columns do not exist.

- [ ] **Step 3: Add the migration and SQLAlchemy fields**

Implement the status constraint and nullable evidence fields. Preserve existing rows by converting `provisional` to `in_progress` and `verified` to `verified_exact` before replacing the constraint. Use these model types:

```python
verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
source_edition: Mapped[str | None] = mapped_column(String(200), nullable=True)
source_revision: Mapped[str | None] = mapped_column(String(200), nullable=True)
rights_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
rights_jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
artifact_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
artifact_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
artifact_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
transformations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
comparison_exact: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
comparison_formatting: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
comparison_missing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
comparison_extra: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
comparison_wording: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
comparison_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Add nonnegative count checks and 64-character checksum checks. Downgrade maps all verified variants to legacy `verified`, maps the other two statuses to `provisional`, drops the new fields, and restores the old constraint.

- [ ] **Step 4: Run migration tests and the full migration chain**

Run: `pytest backend/tests/migrations/test_scripture_work_verification.py backend/tests/library/ingest/test_schema.py -q`

Expected: PASS.

Run: `alembic -c backend/alembic.ini upgrade head && alembic -c backend/alembic.ini downgrade 0010_merge_platform_composite && alembic -c backend/alembic.ini upgrade head`

Expected: all three commands exit 0 on the temporary test database.

- [ ] **Step 5: Commit the schema milestone**

```bash
git add backend/alembic/versions/0011_scripture_work_verification.py backend/app/library/models.py backend/tests/migrations/test_scripture_work_verification.py backend/tests/library/ingest/test_schema.py
git commit -m "feat: add scripture work verification evidence"
```

### Task 2: Extend strict manifest validation and atomic promotion

**Files:**
- Modify: `backend/app/library/ingest/manifest.py`
- Modify: `backend/app/library/ingest/publish.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_manifest.py`
- Test: `backend/tests/library/ingest/test_manifest.py`
- Test: `backend/tests/library/ingest/test_publish.py`

- [ ] **Step 1: Write failing manifest tests**

Add a complete verified fixture and reject incomplete evidence:

```python
def test_verified_work_requires_evidence(complete_work_source):
    complete_work_source.update({
        'verification_status': 'verified_exact',
        'source_edition': 'August 2022 stable text',
        'source_revision': 'engwmb source 2026-07-24',
        'rights_url': 'https://ebible.org/find/show.php?id=engwmb',
        'rights_jurisdiction': 'Worldwide dedication; naming condition applies',
        'artifact_filename': 'engwmb_vpl.zip',
        'artifact_retrieved_at': '2026-08-17T12:00:00Z',
        'artifact_size': 4284852,
        'artifact_sha256': 'a' * 64,
        'parser_version': 'wmb-vpl/1',
        'transformations': ['Unicode NFC', 'line endings normalized'],
        'comparison_exact': 100,
        'comparison_formatting': 0,
        'comparison_missing': 0,
        'comparison_extra': 0,
        'comparison_wording': 0,
        'comparison_report_sha256': 'b' * 64,
        'reviewer': 'Obie Taylor',
        'reviewed_at': '2026-08-17T13:00:00Z',
        'review_note': 'Complete source comparison reviewed.',
    })
    assert WorkSourceManifest.model_validate(complete_work_source).verification_status == 'verified_exact'

@pytest.mark.parametrize('missing', ['artifact_sha256', 'rights_url', 'reviewer', 'reviewed_at'])
def test_verified_work_rejects_missing_evidence(complete_work_source, missing):
    source = verified_source_dict(complete_work_source)
    source[missing] = None
    with pytest.raises(ValidationError):
        WorkSourceManifest.model_validate(source)
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `pytest backend/tests/library/ingest/test_manifest.py backend/tests/library/ingest/test_publish.py -q`

Expected: FAIL because only `provisional` and `verified` are accepted and publication ignores expanded evidence.

- [ ] **Step 3: Implement the strict Pydantic contract**

Define:

```python
VerificationStatus = Literal[
    'in_progress', 'verified_exact', 'verified_formatting',
    'verified_rebuilt', 'review_required',
]
VERIFIED_STATUSES = {'verified_exact', 'verified_formatting', 'verified_rebuilt'}
```

Require all immutable artifact, rights, report, and review fields for verified statuses. Require `comparison_missing == comparison_extra == comparison_wording == 0`. Require at least one transformation for `verified_formatting`; require `modified=True` and a modification note for `verified_rebuilt`. Permit partial evidence for `in_progress` and `review_required`.

- [ ] **Step 4: Promote every field atomically**

Expand `_work_source_values()` and `_replace_work_sources()` in the same field order. Extend `build_manifest.py::_base_source()` so every current provisional record emits `in_progress`, empty comparison totals, and an empty transformation list while preserving current disclosures.

- [ ] **Step 5: Run tests and reproducibility checks**

Run: `pytest backend/tests/library/ingest/test_manifest.py backend/tests/library/ingest/test_publish.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py -q`

Expected: PASS.

Run: `python backend/data/scripture/eotc-composite-en/build_manifest.py --check`

Expected: exit 0 and no uncommitted manifest drift after regenerating the reviewed manifest.

- [ ] **Step 6: Commit the contract milestone**

```bash
git add backend/app/library/ingest/manifest.py backend/app/library/ingest/publish.py backend/data/scripture/eotc-composite-en/build_manifest.py backend/data/scripture/eotc-composite-en/manifest.json backend/tests/library/ingest/test_manifest.py backend/tests/library/ingest/test_publish.py
git commit -m "feat: enforce work source verification states"
```

### Task 3: Build the deterministic comparison engine

**Files:**
- Create: `backend/app/library/verification/__init__.py`
- Create: `backend/app/library/verification/types.py`
- Create: `backend/app/library/verification/normalize.py`
- Create: `backend/app/library/verification/compare.py`
- Create: `backend/app/library/verification/report.py`
- Test: `backend/tests/library/verification/test_compare.py`
- Test: `backend/tests/library/verification/test_report.py`

- [ ] **Step 1: Write failing comparator tests**

```python
def verse(work, chapter, number, text):
    return SourceVerse(work_id=work, chapter=chapter, verse=number, text=text)

def test_comparator_classifies_every_position():
    current = [
        verse('genesis', 1, 1, 'In the beginning'),
        verse('genesis', 1, 2, 'The  earth'),
        verse('genesis', 1, 3, 'Current only'),
        verse('genesis', 1, 5, 'Different words'),
    ]
    source = [
        verse('genesis', 1, 1, 'In the beginning'),
        verse('genesis', 1, 2, 'The earth'),
        verse('genesis', 1, 4, 'Source only'),
        verse('genesis', 1, 5, 'Changed words'),
    ]
    report = compare_work('genesis', current, source, ComparisonRules())
    assert report.counts.model_dump() == {
        'exact': 1, 'formatting': 1, 'missing': 1, 'extra': 1, 'wording': 1,
    }
```

Also test duplicate rejection, Unicode NFC, line-ending normalization, whitespace-only classification, declared omissions, deterministic ordering, and that punctuation or letter changes remain wording differences.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest backend/tests/library/verification -q`

Expected: FAIL because `app.library.verification` does not exist.

- [ ] **Step 3: Implement immutable types and explicit normalization**

```python
@dataclass(frozen=True, slots=True)
class SourceVerse:
    work_id: str
    chapter: int
    verse: int
    text: str

@dataclass(frozen=True, slots=True)
class ComparisonRules:
    unicode_form: str = 'NFC'
    normalize_line_endings: bool = True
    collapse_whitespace: bool = True

def comparison_text(value: str, rules: ComparisonRules) -> str:
    text = unicodedata.normalize(rules.unicode_form, value)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return ' '.join(text.split()) if rules.collapse_whitespace else text
```

`compare_work()` first validates unique positive positions, then compares the union of positions. Exact uses original normalized Unicode text; formatting uses `comparison_text`; any remaining value difference is wording.

- [ ] **Step 4: Implement deterministic reports**

Serialize JSON with `ensure_ascii=False`, `sort_keys=True`, and compact separators. Include source artifact checksum, current publication checksum, parser version, rules, totals, and every non-exact position. Write Markdown from the same report object. Return the JSON SHA-256 for manifest evidence.

- [ ] **Step 5: Run tests twice to prove deterministic output**

Run: `pytest backend/tests/library/verification -q`

Expected: PASS, including byte-identical report assertions across two temporary directories.

- [ ] **Step 6: Commit the comparison engine**

```bash
git add backend/app/library/verification backend/tests/library/verification
git commit -m "feat: add deterministic scripture source comparison"
```

### Task 4: Add the strict source registry and local operator CLI

**Files:**
- Create: `backend/app/library/verification/registry.py`
- Create: `backend/app/library/verification/cli.py`
- Create: `backend/data/scripture/eotc-composite-en/verification/source-registry.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/source-artifacts.lock.json`
- Test: `backend/tests/library/verification/test_registry.py`
- Test: `backend/tests/library/verification/test_cli.py`

- [ ] **Step 1: Write failing registry security tests**

Test exact HTTPS URLs, supported source-family identifiers, relative artifact paths, duplicate normalized keys, URL credentials/query secrets, checksum mismatch, oversized artifacts, redirects to unapproved hosts, and paths containing traversal or control characters.

```python
def test_registry_rejects_checksum_mismatch(tmp_path):
    artifact = tmp_path / 'source.zip'
    artifact.write_bytes(b'changed')
    entry = source_entry(path='source.zip', sha256='0' * 64)
    with pytest.raises(SourceArtifactError, match='checksum mismatch'):
        verify_artifact(entry, tmp_path)
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `pytest backend/tests/library/verification/test_registry.py backend/tests/library/verification/test_cli.py -q`

Expected: FAIL because the registry and CLI do not exist.

- [ ] **Step 3: Implement the reviewed registry**

The registry declares four families and exact landing/download URLs:

```json
{
  "version": 1,
  "families": {
    "world-messianic-bible": {
      "landing_url": "https://ebible.org/find/show.php?id=engwmb",
      "artifact_url": "https://ebible.org/Scriptures/engwmb_vpl.zip",
      "artifact_filename": "engwmb_vpl.zip",
      "adapter": "wmb_vpl",
      "rights_jurisdiction": "Public-domain dedication; World Messianic Bible naming condition applies"
    },
    "murdock-peshitta-1852": {
      "landing_url": "https://crosswire.org/sword/modules/ModInfo.jsp?modName=Murdock",
      "artifact_filename": "murdock-source.zip",
      "adapter": "murdock_sword",
      "rights_jurisdiction": "Public domain; historical edition cross-check required"
    },
    "kjv-1611-fallback": {
      "landing_url": "https://www.gutenberg.org/ebooks/124",
      "artifact_url": "https://www.gutenberg.org/cache/epub/124/pg124.txt",
      "artifact_filename": "project-gutenberg-124.txt",
      "adapter": "gutenberg_kjv_apocrypha",
      "rights_jurisdiction": "Public domain in the USA"
    },
    "rh-charles-jubilees-1902": {
      "landing_url": "https://archive.org/details/bookofjubileesor00char",
      "artifact_filename": "bookofjubileesor00char_djvu.txt",
      "adapter": "charles_jubilees",
      "rights_jurisdiction": "Public-domain historical edition"
    }
  }
}
```

For Murdock, the raw module URL is recorded in the generated lock only after the operator follows CrossWire's current download redirect and confirms the landing-page identity. No application request performs downloads.

- [ ] **Step 4: Implement CLI commands**

Expose:

```python
app = typer.Typer(no_args_is_help=True)

@app.command('lock-artifact')
def lock_artifact(family: str, file: Path, source_url: str, retrieved_at: datetime): ...

@app.command('compare-family')
def compare_family(family: str, current_bundle: Path, artifact_root: Path, output: Path): ...

@app.command('build-candidate')
def build_candidate(family: str, report_dir: Path, output: Path): ...
```

`lock-artifact` never downloads. It validates a user-downloaded artifact, calculates size/SHA-256, and atomically rewrites the sorted lock file. `compare-family` refuses an unlocked artifact. `build-candidate` refuses missing/extra/wording differences unless `--replace-from-source` is explicitly supplied.

- [ ] **Step 5: Run registry and CLI tests**

Run: `pytest backend/tests/library/verification/test_registry.py backend/tests/library/verification/test_cli.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the registry milestone**

```bash
git add backend/app/library/verification/registry.py backend/app/library/verification/cli.py backend/data/scripture/eotc-composite-en/verification/source-registry.json backend/data/scripture/eotc-composite-en/verification/source-artifacts.lock.json backend/tests/library/verification/test_registry.py backend/tests/library/verification/test_cli.py
git commit -m "feat: add reviewed scripture source registry"
```

### Task 5: Expose safe public details and administrator progress

**Files:**
- Create: `backend/app/library/schemas.py`
- Modify: `backend/app/library/router.py`
- Test: `backend/tests/library/test_library_router.py`
- Test: `backend/tests/library/test_verification_admin.py`

- [ ] **Step 1: Write failing public and admin API tests**

```python
def test_public_source_detail_uses_plain_language(client, seeded_verified_source):
    response = client.get('/api/v1/library/editions/EOTC-COMPOSITE-EN/works/genesis/source')
    assert response.status_code == 200
    assert response.json()['verification'] == {
        'status': 'verified_exact',
        'label': 'Source verified',
        'verified_at': '2026-08-17T13:00:00Z',
    }
    assert 'artifact_filename' not in response.json()

def test_admin_inventory_requires_admin(client, user_token):
    response = client.get('/api/v1/library/admin/scripture-verification', headers=user_token)
    assert response.status_code == 403
```

Also assert the admin response contains 83 work rows, family/status totals, safe source URLs, checksums, comparison totals, reviewer/date, and no local paths.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest backend/tests/library/test_library_router.py backend/tests/library/test_verification_admin.py -q`

Expected: FAIL because the endpoints and schemas do not exist.

- [ ] **Step 3: Add bounded schemas and endpoints**

Define the label mapping once:

```python
VERIFICATION_LABELS = {
    'in_progress': 'Source verification in progress',
    'verified_exact': 'Source verified',
    'verified_formatting': 'Verified with documented formatting changes',
    'verified_rebuilt': 'Rebuilt from verified source',
    'review_required': 'Source review required',
}
```

Extend `_work_source_payload()` with safe public fields. Add the focused public source-detail endpoint. Add an admin endpoint protected by `Depends(require_admin)` that returns sorted rows and computed totals. Never expose evidence filesystem paths.

- [ ] **Step 4: Run API and auth tests**

Run: `pytest backend/tests/library/test_library_router.py backend/tests/library/test_verification_admin.py backend/tests/auth -q`

Expected: PASS.

- [ ] **Step 5: Commit the API milestone**

```bash
git add backend/app/library/schemas.py backend/app/library/router.py backend/tests/library/test_library_router.py backend/tests/library/test_verification_admin.py
git commit -m "feat: expose scripture verification status"
```

### Task 6: Upgrade reader and comparison disclosures

**Files:**
- Modify: `frontend/src/reader/scriptureApi.js`
- Modify: `frontend/src/reader/TextSourceDisclosure.jsx`
- Modify: `frontend/src/reader/readerTokens.css`
- Modify: `frontend/src/components/TextualComparisonWorkspace.jsx`
- Modify: `frontend/src/components/TextualComparisonWorkspace.css`
- Test: `frontend/src/reader/scriptureApi.test.js`
- Test: `frontend/src/reader/TextSourceDisclosure.test.jsx`
- Test: `frontend/src/components/TextualComparisonWorkspace.test.jsx`

- [ ] **Step 1: Write failing frontend status tests**

```jsx
it.each([
  ['in_progress', 'Source verification in progress'],
  ['verified_exact', 'Source verified'],
  ['verified_formatting', 'Verified with documented formatting changes'],
  ['verified_rebuilt', 'Rebuilt from verified source'],
  ['review_required', 'Source review required'],
])('renders %s as plain language', (status, label) => {
  render(<TextSourceDisclosure source={{ ...completeSource, verificationStatus: status }} />)
  expect(screen.getByText(label)).toBeVisible()
})
```

Assert the permanent KJV fallback label appears alongside every status, source links reject unsafe protocols, evidence details are keyboard reachable, and comparison cards use identical labels.

- [ ] **Step 2: Run frontend tests and confirm failure**

Run: `npm test -- --run src/reader/scriptureApi.test.js src/reader/TextSourceDisclosure.test.jsx src/components/TextualComparisonWorkspace.test.jsx`

Working directory: `frontend`

Expected: FAIL because the current component only knows `provisional`.

- [ ] **Step 3: Normalize expanded evidence and centralize labels**

Add `frontend/src/reader/sourceVerification.js`:

```javascript
export const SOURCE_VERIFICATION_LABELS = Object.freeze({
  in_progress: 'Source verification in progress',
  verified_exact: 'Source verified',
  verified_formatting: 'Verified with documented formatting changes',
  verified_rebuilt: 'Rebuilt from verified source',
  review_required: 'Source review required',
})

export function sourceVerificationLabel(status) {
  return SOURCE_VERIFICATION_LABELS[status] ?? 'Source status unavailable'
}
```

Use this helper in the reader and comparison workspace. Normalize safe public evidence in `normalizeWorkSource()` without accepting filesystem paths from the API.

- [ ] **Step 4: Implement accessible visual treatment**

Use visible text, `role="status"` only when status changes after load, 44px disclosure targets, existing gold focus rings, wrapping at narrow widths, and no essential color-only distinction. The KJV fallback badge remains red/gold and textual.

- [ ] **Step 5: Run unit, accessibility-static, lint, and build checks**

Run: `npm test -- --run src/reader/scriptureApi.test.js src/reader/TextSourceDisclosure.test.jsx src/components/TextualComparisonWorkspace.test.jsx && npm run lint && npm run build`

Working directory: `frontend`

Expected: all commands exit 0.

- [ ] **Step 6: Commit the public UI milestone**

```bash
git add frontend/src/reader/sourceVerification.js frontend/src/reader/scriptureApi.js frontend/src/reader/TextSourceDisclosure.jsx frontend/src/reader/readerTokens.css frontend/src/reader/scriptureApi.test.js frontend/src/reader/TextSourceDisclosure.test.jsx frontend/src/components/TextualComparisonWorkspace.jsx frontend/src/components/TextualComparisonWorkspace.css frontend/src/components/TextualComparisonWorkspace.test.jsx
git commit -m "feat: show honest scripture source status"
```

### Task 7: Add the administrator verification inventory

**Files:**
- Create: `frontend/src/admin/scriptureVerificationApi.js`
- Create: `frontend/src/admin/ScriptureVerificationPage.jsx`
- Create: `frontend/src/admin/ScriptureVerificationPage.css`
- Create: `frontend/src/admin/ScriptureVerificationPage.test.jsx`
- Modify: `frontend/src/routing/pageRoutes.js`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Write failing route, auth, filtering, and table tests**

Test totals of 83 supplied works, grouping by four affected families plus already-provenanced works, status filters, evidence expansion, admin 401/403 handling, mobile card layout, and a meaningful empty/error state.

```jsx
it('summarizes work verification without a false completion claim', async () => {
  render(<ScriptureVerificationPage />)
  expect(await screen.findByRole('heading', { name: 'Scripture source verification' })).toBeVisible()
  expect(screen.getByText('83 supplied works')).toBeVisible()
  expect(screen.getByText('73 awaiting exact provenance')).toBeVisible()
  expect(screen.queryByText(/complete ethiopian bible/i)).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `npm test -- --run src/admin/ScriptureVerificationPage.test.jsx src/routing/pageRoutes.test.js`

Working directory: `frontend`

Expected: FAIL because the page and route do not exist.

- [ ] **Step 3: Implement the admin-only page**

Render a semantic summary, filter controls, source-family sections, status text, comparison totals, reviewer/date, and expandable source evidence. Fetch with the existing bearer-token pattern. A 401 directs the user to sign in; a 403 says administrator access is required. Do not provide a client-only button that marks a work verified.

- [ ] **Step 4: Register the lazy route**

Register `#admin-scripture-verification` as `scripture-verification-admin`, lazy-load it in `App.jsx`, and expose it only from an authenticated admin context. Direct navigation remains protected by the backend even if frontend role state is stale.

- [ ] **Step 5: Run tests, lint, and build**

Run: `npm test -- --run src/admin/ScriptureVerificationPage.test.jsx src/routing/pageRoutes.test.js && npm run lint && npm run build`

Working directory: `frontend`

Expected: all commands exit 0.

- [ ] **Step 6: Commit the admin UI milestone**

```bash
git add frontend/src/admin frontend/src/routing/pageRoutes.js frontend/src/App.jsx
git commit -m "feat: add scripture verification admin inventory"
```

### Task 8: Verify and rebuild the 39 World Messianic Bible works

**Files:**
- Create: `backend/app/library/verification/adapters/wmb_vpl.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_bundle.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_manifest.py`
- Modify: `backend/data/scripture/eotc-composite-en/verification/source-artifacts.lock.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/world-messianic-bible.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/world-messianic-bible.md`
- Test: `backend/tests/library/verification/test_wmb_vpl.py`
- Test: `backend/tests/library/ingest/test_composite_english_bundle_adapter.py`

- [ ] **Step 1: Write failing VPL parser and 39-work inventory tests**

Require exactly the 39 approved work IDs, unique positive positions, nonblank text, expected book-code mapping, and rejection of changed file/member structure. Assert that no Apocrypha or New Testament rows leak into the WMB replacement group.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest backend/tests/library/verification/test_wmb_vpl.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py -q`

Expected: FAIL because `wmb_vpl` is not implemented and WMB still comes from the user archive.

- [ ] **Step 3: Lock the reviewed official artifact**

Download `https://ebible.org/Scriptures/engwmb_vpl.zip` outside the application request path. Record it with:

```bash
python -m app.library.verification.cli lock-artifact world-messianic-bible --file backend/data/scripture/eotc-composite-en/verification/artifacts/engwmb_vpl.zip --source-url https://ebible.org/Scriptures/engwmb_vpl.zip --retrieved-at 2026-08-17T12:00:00Z
```

Working directory: `backend`

Expected: the lock contains a 64-character checksum, exact byte size, retrieval time, landing URL, and source URL. Review the eBible public-domain and naming statement before committing.

- [ ] **Step 4: Implement the WMB parser and compare all positions**

Parse the single reviewed VPL member, map official book codes to the 39 work IDs, and emit `SourceVerse` rows. Run:

```bash
python -m app.library.verification.cli compare-family world-messianic-bible --current-bundle data/scripture/eotc-composite-en/corrected-bundle.zip --artifact-root data/scripture/eotc-composite-en/verification/artifacts --output data/scripture/eotc-composite-en/verification/reports
```

Expected: a deterministic report for 39 works. Every non-exact position is classified.

- [ ] **Step 5: Rebuild from the official source where required**

Run `build-candidate ... --replace-from-source`, update `build_bundle.py` to use the locked WMB output for the 39 works, regenerate the bundle and manifest, and set each status according to its reviewed result: `verified_exact`, `verified_formatting`, or `verified_rebuilt`. The source label remains World Messianic Bible only when the installed wording is the official text.

- [ ] **Step 6: Run WMB, ingest, reader API, and reproducibility tests**

Run: `pytest backend/tests/library/verification/test_wmb_vpl.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py backend/tests/library/test_library_router.py -q`

Expected: PASS and exactly 39 WMB work-source records with no `in_progress` status.

Run both bundle and manifest builders with `--check`; expected: exit 0.

- [ ] **Step 7: Commit the WMB milestone**

```bash
git add backend/app/library/verification/adapters/wmb_vpl.py backend/data/scripture/eotc-composite-en backend/tests/library/verification/test_wmb_vpl.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py
git commit -m "data: verify World Messianic Bible sources"
```

### Task 9: Verify and rebuild the 27 Murdock Peshitta works

**Files:**
- Create: `backend/app/library/verification/adapters/murdock_sword.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_bundle.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_manifest.py`
- Modify: `backend/data/scripture/eotc-composite-en/verification/source-artifacts.lock.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/murdock-peshitta-1852.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/murdock-peshitta-1852.md`
- Test: `backend/tests/library/verification/test_murdock_sword.py`

- [ ] **Step 1: Write failing parser and historical cross-check tests**

Require the CrossWire module identity `Murdock`, module version, 27-work coverage, public-domain metadata, unique positions, and the ten already-declared alignment omissions. Test removal of `FI`/`RF` apparatus and U+000F normalization without changing surrounding words.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest backend/tests/library/verification/test_murdock_sword.py -q`

Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Lock both electronic and historical evidence**

Download the current CrossWire Murdock raw module from its official module page and the Wikimedia/Internet Archive historical scan. Lock both artifacts. The electronic module supplies comparison rows; the 1852 scan establishes edition identity and is sampled at the beginning, middle, and end of every New Testament work.

- [ ] **Step 4: Implement the adapter and produce the 27-work report**

Parse only the Murdock module, retain source verse labels, apply only the documented apparatus transformations, compare all positions, and emit scan-sample evidence in the report. Any unexplained transcription disagreement sets the affected work to `review_required` rather than verified.

- [ ] **Step 5: Rebuild reviewed differences and regenerate artifacts**

Replace from the locked electronic source only after the historical sampling passes. Regenerate the composite bundle and manifest. Preserve the ten declared omissions and their disclosure.

- [ ] **Step 6: Run Murdock, ingest, and application regression tests**

Run: `pytest backend/tests/library/verification/test_murdock_sword.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py backend/tests/library/test_library_router.py -q`

Expected: PASS; all 27 records have an evidence-complete verified status. If any record is `review_required`, stop this milestone, preserve readability, resolve its edition or transcription evidence, and rerun before committing the family as complete.

- [ ] **Step 7: Commit the Murdock milestone**

```bash
git add backend/app/library/verification/adapters/murdock_sword.py backend/data/scripture/eotc-composite-en backend/tests/library/verification/test_murdock_sword.py
git commit -m "data: verify Murdock Peshitta sources"
```

### Task 10: Verify and rebuild the six KJV fallback works

> **Reviewed source amendment (approved 2026-08-29):** Project Gutenberg eBook 30 does not contain the required six-work Apocrypha inventory and must not be used. The approved electronic artifact is Project Gutenberg eBook 124 (`https://www.gutenberg.org/cache/epub/124/pg124.txt`, SHA-256 `83de0c18742ba22b3d442c3a5bc828fe9e91dff27ae3c298e9b5c9a6ecfbf4d4`, 835,071 bytes), corroborated against the University of Pennsylvania Colenda original 1611 Robert Barker Great HE editio princeps catalog, IIIF manifest, and locked native page images p. 1143–1158. eBook 124 metadata alone is not represented as proof of edition identity. The review is explicitly AI-assisted and makes no human visual-review claim.

**Files:**
- Create: `backend/app/library/verification/adapters/gutenberg_kjv_apocrypha.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_bundle.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_manifest.py`
- Modify: `backend/data/scripture/eotc-composite-en/verification/source-artifacts.lock.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/kjv-1611-fallback.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/kjv-1611-fallback.md`
- Test: `backend/tests/library/verification/test_gutenberg_kjv_apocrypha.py`

- [ ] **Step 1: Write failing six-work parser and permanent-label tests**

Require exactly Baruch, Letter of Jeremiah, Prayer of Azariah, Susanna, Bel and the Dragon, and Prayer of Manasseh. Test edition headings, unique positions, no accidental inclusion of canonical Daniel prose, and permanent `fallback=True` regardless of verification status.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest backend/tests/library/verification/test_gutenberg_kjv_apocrypha.py -q`

Expected: FAIL because the adapter does not exist.

Run: `npm test -- --run src/reader/TextSourceDisclosure.test.jsx`

Working directory for the second command: `frontend`

Expected: FAIL until the expanded fixture and permanent combined-status assertion are added.

- [ ] **Step 3: Lock the amended electronic and historical artifacts**

Use the exact eBook 124 artifact and UPenn 1611 evidence named in the reviewed amendment. Record final and landing URLs, timestamps, checksums, byte sizes, rights evidence, catalog identity, IIIF canvas identity, and exact page-image hashes. Parse exactly 387 positions and bind all 378 initial wording adjudications plus the predetermined samples to the locked leaves. Any later source substitution requires a new source-review decision.

- [ ] **Step 4: Parse, compare, and rebuild reviewed differences**

Parse the six named Apocrypha works only. Produce the deterministic comparison report and replacement candidate. Keep `KJV fallback` in `source_label`, attribution, API `fallback`, reader badge, and comparison badge.

- [ ] **Step 5: Run backend and frontend fallback regression suites**

Run: `pytest backend/tests/library/verification/test_gutenberg_kjv_apocrypha.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py backend/tests/library/test_library_router.py -q`

Run: `npm test -- --run src/reader/TextSourceDisclosure.test.jsx src/components/TextualComparisonWorkspace.test.jsx`

Working directory for the second command: `frontend`

Expected: PASS; all six work records expose both verification and fallback labels.

- [ ] **Step 6: Commit the KJV milestone**

```bash
git add backend/app/library/verification/adapters/gutenberg_kjv_apocrypha.py backend/data/scripture/eotc-composite-en backend/tests/library/verification/test_gutenberg_kjv_apocrypha.py frontend/src/reader/TextSourceDisclosure.test.jsx frontend/src/components/TextualComparisonWorkspace.test.jsx
git commit -m "data: verify KJV fallback sources"
```

### Task 11: Verify Jubilees against the R. H. Charles historical edition

**Approved source amendment (2026-08-30):** The exact Internet Archive 1902 scan remains the edition and numbering authority. Its OCR TXT/XML and scandata are locked only for page anchoring because raw OCR is not publication quality. The machine-readable publication transcription is the clean Global Grey transcription of the authorized 1917 reprint, whose prefatory notice identifies it as Charles's translation published in 1902. Nine fixed beginning/middle/end scan correlations detected no revision in those sampled passages; this is not a full-edition collation. A pinned Poppler 26.05.0 reproducer verifies 18 locked crops covering all nine samples, all seven exact parser repairs, and full-page evidence for chapter 27 positions 1–13. The former app text's 1,758 fragments were rejected as non-Charles segmentation. The primary scan's 50 chapter maxima total exactly 1,307 numbered positions; the inconsistent secondary 1,341 claim was rejected and no positions were invented. Only seven scan-confirmed marker defects (4:2, 4:13, 6:15, 9:9, 13:13, 22:21, and 22:26) and the explicit scan-confirmed chapter-27 collapsed markers may be structurally repaired. Review attribution is AI-assisted and makes no human-review, official-edition, or complete-Ethiopian-Bible claim.

**Files:**
- Create: `backend/app/library/verification/adapters/charles_jubilees.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_bundle.py`
- Modify: `backend/data/scripture/eotc-composite-en/build_manifest.py`
- Modify: `backend/data/scripture/eotc-composite-en/verification/source-artifacts.lock.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/rh-charles-jubilees-1902.json`
- Create: `backend/data/scripture/eotc-composite-en/verification/reports/rh-charles-jubilees-1902.md`
- Test: `backend/tests/library/verification/test_charles_jubilees.py`

- [x] **Step 1: Write failing edition-identity and parser tests**

Require the 1902 R. H. Charles edition, Internet Archive identifier `bookofjubileesor00char`, 50 chapters, unique positive positions, no introduction/footnote leakage, and deterministic paragraph-to-verse handling. Add fixtures for chapter headings, footnotes, page headers, and hyphenated line wraps.

- [x] **Step 2: Run tests and confirm failure**

Run: `pytest backend/tests/library/verification/test_charles_jubilees.py -q`

Expected: FAIL because the adapter does not exist.

- [x] **Step 3: Lock the historical scan and machine-readable derivative**

Lock the Internet Archive/Wikimedia 1902 scan and its IA full-text derivative. Record both checksums and the immutable archive identifier. Use the scan as edition authority; use the derivative for parsing only after page-sample comparison confirms it represents the scan.

- [x] **Step 4: Determine whether the current archive matches 1902**

Run the full comparison. If another Charles edition is detected, keep the work `review_required`, identify the matching historical edition, and amend the source registry through review before replacement. Never label a mixed or modern edited text as Charles 1902.

- [x] **Step 5: Rebuild from the reviewed matching edition**

Once edition identity is established, replace material differences from that frozen edition, document paragraph/verse transformations, regenerate the bundle and manifest, and emit the final report checksum.

- [x] **Step 6: Run Jubilees and full composite data tests**

Run: `pytest backend/tests/library/verification/test_charles_jubilees.py backend/tests/library/ingest/test_composite_english_bundle_adapter.py backend/tests/library/ingest/test_quality_gate_e2e.py -q`

Expected: PASS and Jubilees has one evidence-complete verified status. `review_required` remains readable but blocks completion of this milestone.

- [x] **Step 7: Commit the Jubilees milestone**

```bash
git add backend/app/library/verification/adapters/charles_jubilees.py backend/data/scripture/eotc-composite-en backend/tests/library/verification/test_charles_jubilees.py
git commit -m "data: verify R H Charles Jubilees source"
```

### Task 12: Complete end-to-end accessibility, rollback, documentation, and production gates

**Files:**
- Modify: `backend/data/scripture/eotc-composite-en/README.md`
- Create: `docs/source-verification/eotc-composite-en.md`
- Create: `frontend/e2e/scripture-source-verification.spec.js`
- Modify: `frontend/e2e/scripture-reader.spec.js`
- Test: `backend/tests/library/ingest/test_quality_gate_e2e.py`

- [ ] **Step 1: Write failing end-to-end assertions**

Cover a verified WMB work, a verified/review-required Murdock work, a KJV fallback, Jubilees, a previously provenanced Meqabyan work, mobile layout, keyboard disclosure, 200% zoom, light/dark themes, screen-reader names, admin authorization, and rollback to the previous publication.

- [ ] **Step 2: Run focused E2E tests and confirm failure**

Run: `npm run test:e2e -- scripture-source-verification.spec.js scripture-reader.spec.js`

Working directory: `frontend`

Expected: FAIL until fixtures and final production wiring are complete.

- [ ] **Step 3: Document the public collection and operator runbook**

The documentation must state:

- **Ethiopian Canon Research Collection / mixed-source English research collection**;
- not complete, official, uniform, or ecclesiastically authorized;
- exact 39/27/6/1 verification grouping;
- source URLs, immutable identifiers, checksums, rights evidence, jurisdiction, transformations, reviewer, and report checksums;
- permanent KJV fallback treatment;
- local-only acquisition, comparison, candidate build, staging, publication, health-check, and rollback commands.

- [ ] **Step 4: Run the full backend gate**

Run: `pytest -q`

Working directory: repository root.

Expected: all backend tests pass.

- [ ] **Step 5: Run the full frontend gate**

Run: `npm test -- --run && npm run lint && npm run build && npm run test:e2e`

Working directory: `frontend`

Expected: unit, lint, production build, desktop/mobile E2E, and axe checks all pass.

- [ ] **Step 6: Run deterministic data and migration gates**

Run:

```bash
python backend/data/scripture/eotc-composite-en/build_bundle.py --check
python backend/data/scripture/eotc-composite-en/build_manifest.py --check
alembic -c backend/alembic.ini upgrade head
```

Expected: all commands exit 0 with no generated-file drift.

- [ ] **Step 7: Perform staging publication and rollback rehearsal**

Stage, validate, verify, and publish `EOTC-COMPOSITE-EN` using a production-like staging database. Confirm the public reader, search, comparison, commentary, and research routes. Roll back one version, confirm the old text and source evidence return together, then republish the reviewed version.

- [ ] **Step 8: Commit the release gate**

```bash
git add backend/data/scripture/eotc-composite-en/README.md docs/source-verification/eotc-composite-en.md frontend/e2e/scripture-source-verification.spec.js frontend/e2e/scripture-reader.spec.js backend/tests/library/ingest/test_quality_gate_e2e.py
git commit -m "docs: complete scripture verification release gate"
```

## Final Acceptance Checklist

- [ ] All 83 supplied works remain readable.
- [ ] The affected inventory is exactly 39 WMB + 27 Murdock + 6 KJV fallback + 1 Jubilees = 73.
- [ ] Every work exposes one of the five approved statuses.
- [ ] All 73 remediation works finish in `verified_exact`, `verified_formatting`, or `verified_rebuilt`; `review_required` blocks completion but not readability.
- [ ] Every verified work has exact artifact, rights, checksum, report, reviewer, and date evidence.
- [ ] No verified report contains unexplained missing, extra, or wording differences.
- [ ] All six KJV-derived works retain permanent fallback labels.
- [ ] No user-facing copy calls the collection complete or official.
- [ ] Reader, search, comparison, commentary, AI research, and navigation remain functional.
- [ ] Backend, frontend, accessibility, migration, deterministic-build, publication, health, and rollback gates pass.
