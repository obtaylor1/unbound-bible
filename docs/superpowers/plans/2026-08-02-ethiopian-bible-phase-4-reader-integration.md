# Ethiopian Bible Phase 4: Reader and Comparison Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let readers navigate every Ethiopian canon entry, automatically open the best lawful English edition, inspect its provenance, and compare only editions that contain real passage text.

**Architecture:** Extend the library API with edition metadata, coverage, and a deterministic recommended-edition policy. Keep canon selection and edition selection independent in the React reader, add a compact About-this-text disclosure, and drive comparison sources from API metadata instead of hard-coded translation claims.

**Tech Stack:** FastAPI, SQLAlchemy, React 19, Vite, Vitest, React Testing Library, Playwright, CSS

---

## File Map

- Modify `backend/app/library/router.py`: richer canon, passage-edition, and recommendation responses.
- Create `backend/app/library/recommend.py`: deterministic edition ranking.
- Modify `backend/tests/library/test_library_routes.py`: API contracts and failure semantics.
- Modify `frontend/src/reader/scriptureApi.js`: catalog, editions, and chapter response normalization.
- Modify `frontend/src/reader/ScriptureReaderPage.jsx`: separate canon/work/edition selection and fallback.
- Modify `frontend/src/reader/PassageToolbar.jsx`: display edition names rather than codes.
- Create `frontend/src/reader/TextEditionPanel.jsx`: About-this-text disclosure.
- Modify `frontend/src/reader/ReaderStatus.jsx`: canon-versus-edition coverage states.
- Modify `frontend/src/reader/readerTokens.css`: accessible panel and status styling.
- Modify comparison model/workspace/card files to consume API edition metadata.
- Add reader, comparison, API, accessibility, and end-to-end tests.

### Task 1: Rank Reading Editions Deterministically

**Files:**
- Create: `backend/app/library/recommend.py`
- Create: `backend/tests/library/test_recommend.py`

- [ ] **Step 1: Write failing ranking tests**

```python
from app.library.recommend import recommend_edition


def test_prefers_verified_english_exact_then_general_then_related():
    editions = [
        {'code': 'REL', 'status': 'related_recension', 'verified': True, 'language': 'English'},
        {'code': 'KJV1769', 'status': 'verified_english', 'verified': True, 'language': 'English'},
        {'code': 'GEEZ', 'status': 'verified_original', 'verified': True, 'language': "Ge'ez"},
    ]
    assert recommend_edition(editions)['code'] == 'KJV1769'


def test_never_recommends_translation_needed_or_withdrawn():
    assert recommend_edition([
        {'code': 'GAP', 'status': 'translation_needed', 'verified': True, 'language': 'English'},
        {'code': 'OLD', 'status': 'verified_english', 'verified': False, 'language': 'English'},
    ]) is None
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/test_recommend.py -q`

- [ ] **Step 3: Implement stable ranking**

Rank active verified coverage as: exact Ethiopian-derived English, verified general English, related-recension English, verified Ge'ez/Amharic original. Break ties with a source-manifest `reader_priority`, then edition code. Never infer edition identity from canon membership.

- [ ] **Step 4: Verify GREEN and commit**

Run: `uv run pytest backend/tests/library/test_recommend.py -q`

```bash
git add backend/app/library/recommend.py backend/tests/library/test_recommend.py
git commit -m "feat: recommend verified reading editions"
```

### Task 2: Expose Work, Edition, and Passage Metadata

**Files:**
- Modify: `backend/app/library/router.py`
- Modify: `backend/tests/library/test_library_routes.py`

- [ ] **Step 1: Add failing API contract tests**

Assert:

- `GET /api/v1/books?canon=ETHIO81` returns 81 counted entries, navigable works, coverage summaries, and `recommended_edition`.
- `GET /api/v1/library/works/genesis` returns aliases and all active edition metadata.
- `GET /api/biblical-texts/chapter-content?book=Genesis&chapter=1` returns each row with an `edition` object containing code, name, language, license, relationship, and verification.
- an API error remains a non-200 response; no route converts it into `translation_needed`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest backend/tests/library/test_library_routes.py -q`

- [ ] **Step 3: Implement joined response helpers**

Use one edition metadata query per request and map by edition code to avoid N+1 queries. Keep `translation` for backward compatibility and add `edition`. Catalog coverage includes no verse text.

- [ ] **Step 4: Add `GET /api/v1/library/coverage`**

Return the same 81-entry structured coverage used by the Markdown report. Support `canon=ETHIO81`; reject unknown canon codes with 404.

- [ ] **Step 5: Verify GREEN and commit**

Run: `uv run pytest backend/tests/library backend/tests/test_application.py -q`

```bash
git add backend/app/library/router.py backend/tests/library/test_library_routes.py
git commit -m "feat: expose scripture edition coverage"
```

### Task 3: Normalize Rich Reader API Responses

**Files:**
- Modify: `frontend/src/reader/scriptureApi.js`
- Modify: `frontend/src/reader/scriptureApi.test.js`

- [ ] **Step 1: Write failing normalization tests**

```javascript
it('keeps canon membership and edition coverage separate', async () => {
  fetchMock.mockResolvedValue(jsonResponse({
    canon_count: 81,
    books: [{ id: 'genesis', name: 'Genesis', canon_included: true, recommended_edition: 'KJV1769', coverage: [] }],
  }))
  const catalog = await getBookCatalog('ETHIO81')
  expect(catalog[0]).toMatchObject({ id: 'genesis', canonIncluded: true, recommendedEdition: 'KJV1769' })
})

it('normalizes edition metadata without replacing the legacy translation code', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ content: [{ verse: 1, text: 'In the beginning', translation: 'KJV1769', edition: { code: 'KJV1769', name: 'King James Version', relationship: 'general_reading' } }] }))
  const rows = await getChapter({ book: 'Genesis', chapter: 1 })
  expect(rows[0].edition.name).toBe('King James Version')
  expect(rows[0].translation).toBe('KJV1769')
})
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/reader/scriptureApi.test.js`

- [ ] **Step 3: Implement defensive normalization**

Reject malformed coverage arrays, preserve valid unknown edition codes, and provide `name: code` only when metadata is genuinely absent. Do not synthesize Ethiopian labels.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd frontend && npm test -- --run src/reader/scriptureApi.test.js`

```bash
git add frontend/src/reader/scriptureApi.js frontend/src/reader/scriptureApi.test.js
git commit -m "feat: consume scripture edition metadata"
```

### Task 4: Separate Canon Navigation from Edition Selection

**Files:**
- Modify: `frontend/src/reader/ScriptureReaderPage.jsx`
- Modify: `frontend/src/reader/ScriptureReaderPage.test.jsx`
- Modify: `frontend/src/reader/PassageToolbar.jsx`
- Modify: `frontend/src/reader/ReaderChrome.test.jsx`

- [ ] **Step 1: Write failing reader tests**

Test that Genesis remains in the ETHIO81 picker when no Ethiopian-derived edition exists, the reader navigates to `KJV1769` when it is the recommended verified English edition, the translation menu shows `King James Version` instead of only `KJV1769`, and changing editions leaves `canon=ETHIO81` unchanged.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/reader/ScriptureReaderPage.test.jsx src/reader/ReaderChrome.test.jsx`

- [ ] **Step 3: Replace code-only translation normalization**

Build translation choices from row edition metadata:

```javascript
function normalizedEditions(rows) {
  const byCode = new Map()
  for (const row of Array.isArray(rows) ? rows : []) {
    const code = String(row?.edition?.code ?? row?.translation ?? '').trim().toUpperCase()
    if (!code || byCode.has(code)) continue
    byCode.set(code, { code, name: row?.edition?.name?.trim() || code, metadata: row?.edition ?? null })
  }
  return [...byCode.values()]
}
```

When the route edition is absent, select the catalog's `recommendedEdition` if present in the chapter; otherwise select the first verified available edition. Never change the canon during fallback.

- [ ] **Step 4: Update toolbar option labels**

Render each option's human name with its code in parentheses only when useful. Keep the accessible label `Change translation` and current 48px control height.

- [ ] **Step 5: Verify GREEN and commit**

Run: `cd frontend && npm test -- --run src/reader/ScriptureReaderPage.test.jsx src/reader/ReaderChrome.test.jsx`

```bash
git add frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/ScriptureReaderPage.test.jsx frontend/src/reader/PassageToolbar.jsx frontend/src/reader/ReaderChrome.test.jsx
git commit -m "fix: separate canon and edition selection"
```

### Task 5: Add the About-This-Text Disclosure

**Files:**
- Create: `frontend/src/reader/TextEditionPanel.jsx`
- Create: `frontend/src/reader/TextEditionPanel.test.jsx`
- Modify: `frontend/src/reader/ScriptureReaderPage.jsx`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Write failing accessible-panel tests**

Render general-reading, exact-Ethiopian, related-recension, and CC BY-SA editions. Assert the collapsed button says `About this text`, `aria-expanded` changes, and expanded content shows translation, language, translator, license, source tradition, relationship label, provenance link, and coverage status. Verify Escape closes and returns focus.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/reader/TextEditionPanel.test.jsx`

- [ ] **Step 3: Implement a disclosure, not a modal**

Use a button and a region with `aria-labelledby`. Relationship copy is exactly:

- `Ethiopian-derived English translation`
- `General English reading edition`
- `Related recension - differences may exist`

External provenance opens safely with `target="_blank" rel="noreferrer"`. Do not show technical metadata when no edition is selected.

- [ ] **Step 4: Add responsive styles**

Use existing reader color tokens, a 48px trigger, readable 16px minimum body copy, a two-column definition list above 720px, and one column below. Honor light/dark and reduced-motion preferences.

- [ ] **Step 5: Integrate below `PassageToolbar` and verify**

Run: `cd frontend && npm test -- --run src/reader/TextEditionPanel.test.jsx src/reader/ScriptureReaderPage.test.jsx`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/reader/TextEditionPanel.jsx frontend/src/reader/TextEditionPanel.test.jsx frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/readerTokens.css
git commit -m "feat: explain scripture edition provenance"
```

### Task 6: Make Coverage States Truthful and Actionable

**Files:**
- Modify: `frontend/src/reader/ReaderStatus.jsx`
- Modify: `frontend/src/reader/ReaderStatus.test.jsx`
- Modify: `frontend/src/reader/ScriptureReaderPage.jsx`

- [ ] **Step 1: Write failing state tests**

Assert distinct rendered states for request error, canon-included/English-needed, verified-original-only, and related-recension-only. The Genesis edition gap must say `Genesis is included in the Ethiopian Orthodox canon`; it must not say `No text is available` when a recommended KJV reading exists.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/reader/ReaderStatus.test.jsx`

- [ ] **Step 3: Add coverage-specific state props**

Use `coverageState`, `book`, `recommendedEdition`, and `onChooseEdition`. Preserve existing retry behavior for request failures. Never turn an HTTP failure into an edition gap.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd frontend && npm test -- --run src/reader/ReaderStatus.test.jsx src/reader/ScriptureReaderPage.test.jsx`

```bash
git add frontend/src/reader/ReaderStatus.jsx frontend/src/reader/ReaderStatus.test.jsx frontend/src/reader/ScriptureReaderPage.jsx
git commit -m "fix: distinguish canon and edition coverage states"
```

### Task 7: Drive Comparison Sources from Edition Metadata

**Files:**
- Modify: `frontend/src/components/TextualComparisonWorkspace.jsx`
- Modify: `frontend/src/components/TextualComparisonWorkspace.test.jsx`
- Modify: `frontend/src/components/textualComparison/comparisonModel.js`
- Modify: `frontend/src/components/textualComparison/comparisonModel.test.js`
- Modify: `frontend/src/components/textualComparison/TranslationSelector.jsx`
- Modify: `frontend/src/components/textualComparison/TranslationComparisonCard.jsx`
- Modify: `frontend/src/components/textualComparison/CompareComponents.test.jsx`

- [ ] **Step 1: Write failing dynamic-source tests**

Mock API rows with KJV1769, ENOCH-CHARLES-1912, and one coverage-only missing edition. Assert selectors use API names, an unavailable edition cannot become base text, only real rows count toward summary/differences, and related-recension labels appear on cards.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/components/TextualComparisonWorkspace.test.jsx src/components/textualComparison`

- [ ] **Step 3: Replace the static translation registry**

Keep pure helpers for toggling and differences, but build source objects from chapter rows plus work coverage metadata. Remove the fictional `Ethiopian Orthodox Critical Text` definition. Use edition code as stable key and retain metadata on every source.

- [ ] **Step 4: Fix chapter-view missing-source copy**

Replace the hard-coded `Text unavailable` cell with the same coverage-state title used on cards. Missing text renders no difference marks.

- [ ] **Step 5: Verify GREEN and commit**

Run: `cd frontend && npm test -- --run src/components/TextualComparisonWorkspace.test.jsx src/components/textualComparison`

```bash
git add frontend/src/components/TextualComparisonWorkspace.jsx frontend/src/components/TextualComparisonWorkspace.test.jsx frontend/src/components/textualComparison/comparisonModel.js frontend/src/components/textualComparison/comparisonModel.test.js frontend/src/components/textualComparison/TranslationSelector.jsx frontend/src/components/textualComparison/TranslationComparisonCard.jsx frontend/src/components/textualComparison/CompareComponents.test.jsx
git commit -m "fix: compare verified scripture editions"
```

### Task 8: Correct Static Canon Consumers

**Files:**
- Modify: `frontend/src/data/bibleCanons.js`
- Modify: any canon-comparison component consuming it.
- Add: matching Vitest coverage.

- [ ] **Step 1: Write a failing count-and-group test**

Assert ETHIO81 reports 46 OT and 35 NT counted entries, composite groups retain navigable children, and Meqabyan is not mapped to Greek Maccabees.

- [ ] **Step 2: Replace the contradictory static list**

Prefer the backend catalog for runtime views. If a static fallback remains, mirror the same counted-entry shape and add a comment naming the API as authority.

- [ ] **Step 3: Verify and commit**

Run the focused canon component tests, then commit with `fix: align Ethiopian canon presentation`.

### Task 9: Accessibility and End-to-End Verification

**Files:**
- Modify: `frontend/e2e/scripture-reader-accessibility.spec.js`
- Create: `frontend/e2e/ethiopian-canon-reader.spec.js`

- [ ] Test keyboard-only flow: open picker, choose ETHIO81, select Genesis, change edition, open/close About this text, select a verse.
- [ ] Test large text and 320px viewport without horizontal page overflow.
- [ ] Test light and dark contrast with automated accessibility checks.
- [ ] Test Genesis remains readable at the ETHIO81 URL and retains `canon=ETHIO81` after automatic KJV fallback.
- [ ] Test a translation-needed work shows truthful coverage and no scripture placeholder.
- [ ] Run `cd frontend && npm test -- --run`, `npm run lint`, `npm run build`, and the two Playwright specs.

Expected: all checks pass with zero accessibility violations and zero console errors.

### Task 10: Final Data and Application Quality Gate

- [ ] Run `uv run pytest backend/tests -q`.
- [ ] Run the complete frontend unit, lint, build, and selected end-to-end suites.
- [ ] Generate the 81-entry coverage report from the deployment database copy.
- [ ] Query published text for placeholder patterns and require zero matches.
- [ ] Verify every active edition has provenance, license, checksum, and an active publication record.
- [ ] Verify each translation-needed gap has no fake `biblical_texts` row.
- [ ] Perform a live reader and comparison smoke test for Genesis, Enoch, Jubilees, all three Meqabyan books, one church-order work, and one translation-needed work.
- [ ] Commit only verification corrections with `fix: complete Ethiopian Bible integration`; do not commit databases, caches, screenshots, or generated temporary files.

## Phase 4 Exit Criteria

- Every official canon entry is navigable.
- Genesis opens a lawful English reading edition under ETHIO81.
- Canon and edition choices remain independent.
- Edition names, provenance, licenses, and recension relationships are visible.
- Missing editions do not create false comparison differences.
- Remaining English gaps are honest and actionable.
- Unit, integration, accessibility, build, ingestion, and data-integrity gates all pass.
