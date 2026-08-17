# Research Library User and Admin Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give readers a consistent Source Inspector and understandable research scopes, and give administrators a read-only operations dashboard backed by protected APIs.

**Architecture:** A single source-detail API feeds one accessible React inspector used by Research AI, Scripture reader, comparison, and commentary. Public source choices come from the eligible catalog, not hard-coded UI arrays. The administrator dashboard is observational; state changes remain protected operator commands until a later, separately reviewed write-console phase.

**Tech Stack:** React 19, Vite, Vitest, Testing Library, FastAPI, Pydantic 2, SQLAlchemy 2, Playwright, axe-core.

---

## Scope and ordering

This is plan 4 of 4. Begin after the catalog APIs and hybrid retrieval metadata are stable.

### Task 1: Add public source catalog and inspector APIs

**Files:**
- Create: `backend/app/research_library/schemas.py`
- Create: `backend/app/research_library/service.py`
- Create: `backend/app/research_library/router.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/research_library/test_routes.py`

- [ ] Write failing route tests for `GET /api/v1/research-library/scopes`, `GET /api/v1/research-library/sources/{edition_id}`, and `GET /api/v1/research-library/publications/{publication_id}/anchors/{anchor_key}`. Assert ineligible sources return 404, not explanatory metadata.
- [ ] Run `uv run pytest backend/tests/research_library/test_routes.py -q` and confirm 404s from missing routes.
- [ ] Implement strict response models. Source detail includes title, work, edition, tradition, language, translator, date, license name, attribution, provenance URL, publication version, validation status, and available open target. It never returns internal review notes.
- [ ] Implement grouped scopes from eligible active publications: Biblical Canon, Ethiopian Tradition, Ancient Sources, and Commentary. Include stable `value`, plain-language `label`, `description`, and `available_source_count`.
- [ ] Register the router in `backend/app/api/router.py`.
- [ ] Run the route tests and confirm all pass.
- [ ] Commit with `git add backend/app/research_library backend/app/api/router.py backend/tests/research_library/test_routes.py && git commit -m "feat: expose eligible research source catalog"`.

### Task 2: Add protected read-only administrator APIs

**Files:**
- Create: `backend/app/research_library/admin_router.py`
- Create: `backend/app/research_library/admin_schemas.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/research_library/test_admin_routes.py`

- [ ] Write failing tests proving anonymous users receive 401, readers receive 403, administrators can list editions/publications/runs/findings/audit events, and no POST/PATCH/DELETE route exists.
- [ ] Run `uv run pytest backend/tests/research_library/test_admin_routes.py -q` and confirm failures.
- [ ] Implement `/api/v1/admin/research-library/summary`, `/sources`, `/ingest-runs`, and `/audit-events`, all dependent on `require_administrator`. Paginate lists with bounded `limit <= 100` and stable cursor/order.
- [ ] Summary counts must separate `active`, `needs_rights_review`, `restricted`, `disabled`, failed validation, and unindexed active publications.
- [ ] Run the admin route tests and confirm all pass.
- [ ] Commit with `git add backend/app/research_library/admin_router.py backend/app/research_library/admin_schemas.py backend/app/api/router.py backend/tests/research_library/test_admin_routes.py && git commit -m "feat: add read-only research library administration API"`.

### Task 3: Build the shared Source Inspector

**Files:**
- Create: `frontend/src/sourceInspector/SourceInspector.jsx`
- Create: `frontend/src/sourceInspector/SourceInspector.css`
- Create: `frontend/src/sourceInspector/sourceInspectorApi.js`
- Create: `frontend/src/sourceInspector/SourceInspector.test.jsx`
- Modify: `frontend/src/scriptureResearch/CitationDrawer.jsx`
- Modify: `frontend/src/scriptureResearch/ResearchWorkspace.jsx`
- Modify: `frontend/src/scriptureResearch/ScriptureResearchPage.css`

- [ ] Write failing component tests for focus transfer/restoration, Escape, keyboard trap fallback, loading/error/retry, attribution, license, provenance link, unavailable full text, and open-full-text action.
- [ ] Run `cd frontend && npm test -- --run src/sourceInspector/SourceInspector.test.jsx` and confirm the missing component failure.
- [ ] Implement `SourceInspector` as the only detail drawer. Use native `<dialog>` when supported, the existing accessible fallback otherwise, a visible Close button, at least 18px body copy, clear labels, and a 44px minimum target size.
- [ ] Replace `CitationDrawer` internals with a compatibility wrapper around `SourceInspector`, then update Research Workspace to pass source/publication identifiers.
- [ ] Run the component test plus `cd frontend && npm test -- --run src/scriptureResearch` and confirm all pass.
- [ ] Commit with `git add frontend/src/sourceInspector frontend/src/scriptureResearch && git commit -m "feat: add shared source inspector"`.

### Task 4: Replace hard-coded research scopes with eligible grouped sources

**Files:**
- Modify: `frontend/src/scriptureResearch/researchModel.js`
- Modify: `frontend/src/scriptureResearch/researchApi.js`
- Modify: `frontend/src/scriptureResearch/ResearchComposer.jsx`
- Modify: `frontend/src/scriptureResearch/ScriptureResearchPage.jsx`
- Modify: `frontend/src/scriptureResearch/ResearchComposer.test.jsx`
- Modify: `frontend/src/scriptureResearch/researchApi.test.js`

- [ ] Write failing tests for server-loaded scope groups, friendly empty state, preserved saved legacy scope values, failed catalog request fallback to Biblical Canon, and `all-sources` mutual exclusivity.
- [ ] Run `cd frontend && npm test -- --run src/scriptureResearch/ResearchComposer.test.jsx src/scriptureResearch/researchApi.test.js` and confirm failures.
- [ ] Add `getResearchSourceScopes()` to the client, strictly validate its payload, and store scope descriptions/counts separately from request values.
- [ ] Render grouped, plain-language controls. Keep the default Biblical Canon, explain what each group includes, and display unavailable groups as disabled with “No reviewed sources yet.”
- [ ] Preserve deferred values when restoring saved sessions but do not offer them unless the catalog reports eligible content.
- [ ] Run all Scripture Research frontend tests and confirm they pass.
- [ ] Commit with `git add frontend/src/scriptureResearch && git commit -m "feat: present source-aware research scopes"`.

### Task 5: Connect the inspector to reader, comparison, and commentary

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/reader/ScriptureReaderPage.jsx`
- Modify: `frontend/src/components/TextualComparisonWorkspace.jsx`
- Modify: `frontend/src/components/textualComparison/TranslationComparisonCard.jsx`
- Modify: `frontend/src/reader/CommentaryPanel.jsx`
- Modify existing tests beside each component.

- [ ] Write failing tests that activate “Source details” from each surface and assert the same `SourceInspector` labels and focus behavior.
- [ ] Add one application-level inspector host in `App.jsx` and a small `useSourceInspector()` context so feature pages open it by stable source/publication ID instead of duplicating state.
- [ ] Add clearly named “Source details” actions beside translation/edition names. Do not make a decorative icon the only control.
- [ ] Run the targeted tests and `cd frontend && npm test -- --run`.
- [ ] Commit with `git add frontend/src && git commit -m "feat: share source details across study tools"`.

### Task 6: Build the read-only administrator dashboard

**Files:**
- Create: `frontend/src/admin/ResearchLibraryAdminPage.jsx`
- Create: `frontend/src/admin/ResearchLibraryAdminPage.css`
- Create: `frontend/src/admin/researchLibraryAdminApi.js`
- Create: `frontend/src/admin/ResearchLibraryAdminPage.test.jsx`
- Modify: `frontend/src/routing/pageRoutes.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Navigation.jsx`

- [ ] Write failing tests for route protection, reader redirect, administrator navigation visibility, summary cards, filterable source table, ingest findings, audit timeline, loading/error/retry, and absence of mutation controls.
- [ ] Run `cd frontend && npm test -- --run src/admin/ResearchLibraryAdminPage.test.jsx` and confirm failures.
- [ ] Implement an administrator-only `#admin-library` route. The dashboard must show operational status using text plus color, expose attribution and rights status, and link to Source Inspector. Buttons are limited to refresh, filter, inspect, and copy operator command.
- [ ] Do not embed Obie Taylor’s email in the frontend. Authorization comes only from the authenticated user role returned by the existing auth API.
- [ ] Run admin, routing, navigation, and auth tests.
- [ ] Commit with `git add frontend/src/admin frontend/src/routing frontend/src/App.jsx frontend/src/components/Navigation.jsx && git commit -m "feat: add research library admin dashboard"`.

### Task 7: Accessibility, responsive layout, and end-to-end verification

**Files:**
- Create: `frontend/e2e/research-library.spec.js`
- Modify: `frontend/src/styles/tokens.css`
- Modify relevant CSS only where tests identify a problem.

- [ ] Add Playwright flows for a 13-year-old/first-time-reader path (choose source, ask question, inspect citation, open text) and a large-text/keyboard path (200% zoom, keyboard only, light/dark mode). Add an administrator dashboard read-only path.
- [ ] Assert no axe serious/critical violations, no horizontal page scrolling at 320 CSS px, visible focus, minimum touch targets, comprehensible button text, and WCAG AA text contrast.
- [ ] Add shared-component tests proving Hebrew `dir="rtl"` rendering and preservation of Hebrew diacritics, Greek Unicode, and Ge'ez Unicode in the inspector and excerpts.
- [ ] Add `research_library_enabled` and `research_hybrid_search_enabled` release flags to backend settings and a frontend runtime capability response. Verify disabling the library returns the existing research interface and retriever without a broken control.
- [ ] Run `cd frontend && npm run test:e2e -- research-library.spec.js` against the local test server.
- [ ] Run `cd frontend && npm test -- --run && npm run build && npm run lint`.
- [ ] Run `uv run pytest backend/tests/research_library backend/tests/research -q`.
- [ ] Run `git diff --check`.
- [ ] Commit accessibility adjustments with `git commit -am "test: verify research library experience"`.

## Completion criteria

- Readers see only source groups with eligible content and can understand what each includes.
- Every major study surface opens the same accessible Source Inspector.
- Attribution, licensing, provenance, edition, and publication identity are visible without exposing internal review notes.
- Administrators can diagnose catalog, rights, ingestion, and indexing status but cannot mutate production data through the dashboard.
- The experience remains readable and operable at small screens, 200% zoom, keyboard-only use, and both color modes.
