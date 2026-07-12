# Unbound Bible Product Quality Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make The Unbound Bible reliably navigable, accessible, responsive, testable, and visually coherent while preserving its research-grade, decolonial study mission.

**Architecture:** Stabilize the application shell first, then extract AI Study data/service concerns from its presentation, and finally apply shared design-system primitives across the highest-value screens. Introduce automated tests at each boundary so routing, keyboard navigation, AI response states, and responsive layouts are protected before visual refinement.

**Tech Stack:** React 19, Vite 7, Vitest, React Testing Library, ESLint, CSS custom properties, FastAPI APIs.

---

## Current audit baseline

- `http://localhost:5001/#aistudy` renders Home because `App.jsx` always initializes `currentPage` to `home` and never reads or writes the URL.
- The frontend production build succeeds, but emits a large-chunk warning: the initial JavaScript bundle is about 718 kB (208 kB gzip) and the CSS bundle is about 235 kB (46 kB gzip).
- `npm run lint` fails with 49 errors and 7 warnings, including unused state, empty blocks, and missing React hook dependencies.
- There is no frontend test suite; the only discovered test is a backend Adam and Eve integration script.
- `AskTheBible.jsx` imports and populates `ShareStudyModal` state but never renders the modal, so Share has no visible result.
- Popular question keyword matching bypasses the API and presents fixture content as though it were a live grounded answer.
- Navigation dropdowns lack `aria-expanded`, `aria-controls`, Escape handling, and focus management. Search, notifications, and sign-in controls are visually present but do not perform a defined action.
- Trending questions are clickable `<li>` elements rather than keyboard-operable controls.
- Native `alert()` is used for help, save success, and failures, interrupting study flow and providing inconsistent feedback.
- The interface has strong mission-specific content, but visual hierarchy is diluted by many equally prominent cards, emoji iconography, repeated gradients, multiple font imports, and page-specific design systems.
- Several components are too large to reason about safely, especially `AncientTexts.jsx` (3,085 lines), `ResearchHub.jsx` (966), and `InteractiveMap.jsx` (907).

## Target file structure

- Create `frontend/src/routing/pageRoutes.js`: canonical page IDs, hash aliases, and URL conversion helpers.
- Create `frontend/src/routing/pageRoutes.test.js`: hash parsing and serialization tests.
- Create `frontend/src/components/AppShell.test.jsx`: browser-history and navigation integration tests.
- Modify `frontend/src/App.jsx`: source page state from the route helper and lazy-load page modules.
- Modify `frontend/src/components/Navigation.jsx`: semantic, keyboard-accessible responsive navigation.
- Modify `frontend/src/components/Navigation.css`: desktop navigation plus a true mobile menu.
- Create `frontend/src/components/Navigation.test.jsx`: dropdown, Escape, and accessible-name tests.
- Create `frontend/src/services/studyApi.js`: AI Study request/response/error contract.
- Create `frontend/src/services/studyApi.test.js`: API contract and failure tests.
- Create `frontend/src/components/ask-the-bible/AskComposer.jsx`: labeled question form.
- Create `frontend/src/components/ask-the-bible/AnswerPanel.jsx`: answer, source, provenance, and confidence presentation.
- Create `frontend/src/components/ask-the-bible/StudyDiscovery.jsx`: suggestions, paths, trending prompts, and topics.
- Modify `frontend/src/components/AskTheBible.jsx`: orchestration only.
- Modify `frontend/src/components/AskTheBible.css`: calmer editorial study layout and responsive rules.
- Create `frontend/src/components/AskTheBible.test.jsx`: submit, loading, error, citations, save, share, and keyboard tests.
- Modify `frontend/src/components/ShareStudyModal.jsx`: real render path, dialog semantics, and focus behavior.
- Create `frontend/src/components/ShareStudyModal.test.jsx`: dialog and clipboard tests.
- Create `frontend/src/styles/tokens.css`: shared colors, type, spacing, radii, elevation, focus, and motion.
- Modify `frontend/src/index.css`: global reset, typography, and accessibility defaults.
- Modify `frontend/src/main.jsx`: import the token layer.
- Create `frontend/src/test/setup.js`: DOM test setup.
- Modify `frontend/package.json` and `frontend/vite.config.js`: Vitest and coverage configuration.

### Task 1: Add the frontend test harness

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.js`
- Create: `frontend/src/test/setup.js`
- Create: `frontend/src/routing/pageRoutes.test.js`

- [ ] **Step 1: Add Vitest and Testing Library dependencies and scripts**

Add `test`, `test:watch`, and `test:coverage` scripts. Add `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, and `@testing-library/user-event` as dev dependencies.

- [ ] **Step 2: Configure the DOM test environment**

```js
test: {
  environment: 'jsdom',
  setupFiles: './src/test/setup.js',
  css: true,
}
```

- [ ] **Step 3: Create the setup file**

```js
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 4: Run the empty suite**

Run: `npm test -- --run`

Expected: PASS with no configuration errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/src/test/setup.js
git commit -m "test: add frontend test harness"
```

### Task 2: Make URLs authoritative and deep links reliable

**Files:**
- Create: `frontend/src/routing/pageRoutes.js`
- Create: `frontend/src/routing/pageRoutes.test.js`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/components/AppShell.test.jsx`

- [ ] **Step 1: Write failing route-helper tests**

```js
import { describe, expect, it } from 'vitest'
import { pageFromHash, hashForPage } from './pageRoutes'

describe('page routes', () => {
  it('maps the supplied AI Study deep link to Ask the Bible', () => {
    expect(pageFromHash('#aistudy')).toBe('chat')
  })

  it('falls back to home for unknown hashes', () => {
    expect(pageFromHash('#not-a-page')).toBe('home')
  })

  it('creates stable canonical hashes', () => {
    expect(hashForPage('chat')).toBe('#aistudy')
    expect(hashForPage('textual')).toBe('#compare')
  })
})
```

- [ ] **Step 2: Verify the route tests fail**

Run: `npm test -- --run src/routing/pageRoutes.test.js`

Expected: FAIL because `pageRoutes.js` does not exist.

- [ ] **Step 3: Implement the route table**

```js
const HASH_TO_PAGE = {
  home: 'home',
  aistudy: 'chat',
  sermon: 'sermon',
  scriptures: 'apocrypha',
  compare: 'textual',
  canon: 'canon-compare',
  research: 'research',
  map: 'map',
  library: 'notes',
  community: 'forum',
}

const PAGE_TO_HASH = Object.fromEntries(
  Object.entries(HASH_TO_PAGE).map(([hash, page]) => [page, `#${hash}`]),
)

export const pageFromHash = (hash) => HASH_TO_PAGE[hash.replace(/^#/, '')] ?? 'home'
export const hashForPage = (page) => PAGE_TO_HASH[page] ?? '#home'
```

- [ ] **Step 4: Test App initialization, navigation, back, and forward**

Write integration tests that set `window.location.hash`, render `App`, click a navigation destination, dispatch `hashchange`, and assert that the correct page heading is visible.

- [ ] **Step 5: Bind App state to the URL**

Initialize from `pageFromHash(window.location.hash)`, update the hash in `handlePageChange`, listen for `hashchange`, and focus the main heading after route changes.

- [ ] **Step 6: Run route and shell tests**

Run: `npm test -- --run src/routing/pageRoutes.test.js src/components/AppShell.test.jsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routing frontend/src/App.jsx frontend/src/components/AppShell.test.jsx
git commit -m "fix: make app navigation deep-linkable"
```

### Task 3: Replace the compressed mobile navigation with an accessible menu

**Files:**
- Modify: `frontend/src/components/Navigation.jsx`
- Modify: `frontend/src/components/Navigation.css`
- Create: `frontend/src/components/Navigation.test.jsx`

- [ ] **Step 1: Write failing accessibility tests**

Test that the mobile menu button has the accessible name `Open navigation`, dropdown triggers expose `aria-expanded`, Escape closes the open dropdown, and icon-only actions retain names such as `Search` and `Notifications`.

- [ ] **Step 2: Verify the tests fail**

Run: `npm test -- --run src/components/Navigation.test.jsx`

Expected: FAIL because the current controls lack these semantics.

- [ ] **Step 3: Implement button semantics and keyboard behavior**

Add `aria-expanded`, `aria-controls`, stable menu IDs, Escape handling, focus return, and descriptive `aria-label` values. Replace hover-dependent disclosure with explicit open state.

- [ ] **Step 4: Implement a mobile drawer**

At widths below 768px, show brand, menu trigger, and one primary action in the header. Put destinations in a full-width drawer with readable labels and at least 44px touch targets; remove the current two-row icon strip.

- [ ] **Step 5: Verify tests and keyboard behavior**

Run: `npm test -- --run src/components/Navigation.test.jsx`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Navigation.jsx frontend/src/components/Navigation.css frontend/src/components/Navigation.test.jsx
git commit -m "fix: make navigation responsive and accessible"
```

### Task 4: Make AI Study provenance honest and behavior reliable

**Files:**
- Create: `frontend/src/services/studyApi.js`
- Create: `frontend/src/services/studyApi.test.js`
- Modify: `frontend/src/components/AskTheBible.jsx`
- Create: `frontend/src/components/AskTheBible.test.jsx`

- [ ] **Step 1: Write failing service tests**

```js
it('normalizes a grounded API answer', async () => {
  fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ answer: 'Answer', context_used: ['Source A'] }),
  })
  await expect(askStudyQuestion('Question')).resolves.toMatchObject({
    answer: 'Answer',
    provenance: 'live',
    sources: [{ citation: 'Source A' }],
  })
})
```

Add tests for HTTP errors, malformed payloads, and offline/demo mode.

- [ ] **Step 2: Verify the tests fail**

Run: `npm test -- --run src/services/studyApi.test.js`

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement one request path**

Move all fetch and normalization behavior into `askStudyQuestion(question)`. Do not intercept broad keywords with fixture answers. If demo fixtures remain available, label them `provenance: 'demo'` in the UI.

- [ ] **Step 4: Replace the percentage “Verification Score”**

Show evidence states that can be justified: `Cited library sources`, `Demo answer`, or `No sources returned`. Do not display an unexplained numerical confidence value.

- [ ] **Step 5: Add component tests for loading, failure, provenance, and retry**

Assert that duplicate submissions are prevented, errors preserve the user question, retry is available, and source cards appear only when sources exist.

- [ ] **Step 6: Run the focused suite**

Run: `npm test -- --run src/services/studyApi.test.js src/components/AskTheBible.test.jsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/services frontend/src/components/AskTheBible.jsx frontend/src/components/AskTheBible.test.jsx
git commit -m "fix: make AI study provenance explicit"
```

### Task 5: Repair save, share, help, and trending interactions

**Files:**
- Modify: `frontend/src/components/AskTheBible.jsx`
- Modify: `frontend/src/components/ShareStudyModal.jsx`
- Modify: `frontend/src/components/ShareStudyModal.css`
- Create: `frontend/src/components/ShareStudyModal.test.jsx`

- [ ] **Step 1: Write failing interaction tests**

Test that Share opens a dialog, Close returns focus to Share, Escape closes the dialog, trending questions are buttons, save confirmation uses an in-page live region, and Help opens an in-page disclosure rather than a native alert.

- [ ] **Step 2: Verify the tests fail**

Run: `npm test -- --run src/components/ShareStudyModal.test.jsx src/components/AskTheBible.test.jsx`

Expected: FAIL because the modal is never rendered and alerts are still used.

- [ ] **Step 3: Render the modal and add dialog semantics**

```jsx
{showShareModal && shareData && (
  <ShareStudyModal
    data={shareData}
    onClose={() => setShowShareModal(false)}
  />
)}
```

Give the modal `role="dialog"`, `aria-modal="true"`, an accessible title, initial focus, focus containment, and Escape behavior.

- [ ] **Step 4: Replace alerts and non-semantic list clicks**

Use an `aria-live="polite"` status region for save/copy results. Render each trending question as a `<button type="button">` inside its list item.

- [ ] **Step 5: Run tests**

Run: `npm test -- --run src/components/ShareStudyModal.test.jsx src/components/AskTheBible.test.jsx`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AskTheBible.jsx frontend/src/components/ShareStudyModal.jsx frontend/src/components/ShareStudyModal.css frontend/src/components/ShareStudyModal.test.jsx
git commit -m "fix: repair study save and share interactions"
```

### Task 6: Simplify the AI Study information architecture and visual hierarchy

**Files:**
- Create: `frontend/src/components/ask-the-bible/AskComposer.jsx`
- Create: `frontend/src/components/ask-the-bible/AnswerPanel.jsx`
- Create: `frontend/src/components/ask-the-bible/StudyDiscovery.jsx`
- Modify: `frontend/src/components/AskTheBible.jsx`
- Modify: `frontend/src/components/AskTheBible.css`

- [ ] **Step 1: Add tests for the intended reading order**

Assert the accessible order: page title and purpose, question form, answer/status region, suggested prompts, study paths, then topic discovery.

- [ ] **Step 2: Verify the test fails against the existing dense layout**

Run: `npm test -- --run src/components/AskTheBible.test.jsx`

Expected: FAIL on the new structural expectations.

- [ ] **Step 3: Extract focused components**

Keep request and session state in `AskTheBible`. Move the form to `AskComposer`, response rendering to `AnswerPanel`, and optional discovery content to `StudyDiscovery`.

- [ ] **Step 4: Apply the recommended editorial-study direction**

Use one restrained dark ink background, warm parchment text surfaces for long answers, amethyst only for primary actions, and brass only for citations/provenance. Replace decorative emoji with a small consistent SVG icon set. Keep the composer visible near the top, reduce the hero height, and collapse secondary discovery content after a conversation begins.

- [ ] **Step 5: Improve typography and spacing**

Use a readable serif for scripture and long-form answers and a humanist sans for controls. Target 65–75 characters per answer line, 1.6–1.75 line height, consistent 8px spacing increments, and visible focus rings that meet contrast requirements.

- [ ] **Step 6: Verify desktop and mobile layouts**

Check widths 390, 768, 1024, and 1440. At 390px, content must fit without horizontal scroll; the input and submit control must remain usable; cards must become one column; and touch targets must be at least 44px.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ask-the-bible frontend/src/components/AskTheBible.jsx frontend/src/components/AskTheBible.css frontend/src/components/AskTheBible.test.jsx
git commit -m "refactor: focus the AI study experience"
```

### Task 7: Establish shared visual tokens and accessibility defaults

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Define a minimal token contract**

Create variables for canvas, surface, raised surface, primary text, muted text, amethyst action, brass citation, danger, focus ring, serif/sans families, 4/8/12/16/24/32/48 spacing, three radii, and three elevations.

- [ ] **Step 2: Consolidate global font loading**

Load fonts once, remove repeated `@import` declarations from component styles, and provide resilient local fallbacks. Avoid blocking page rendering on multiple CSS imports.

- [ ] **Step 3: Add global interaction defaults**

```css
:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 4: Apply tokens to the shell and AI Study first**

Replace duplicated raw colors and shadows in `App.css`, `Navigation.css`, and `AskTheBible.css`. Defer unrelated page conversions to later, screen-specific passes.

- [ ] **Step 5: Run tests, lint, and build**

Run: `npm test -- --run && npm run lint && npm run build`

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles frontend/src/index.css frontend/src/main.jsx frontend/src/App.css frontend/src/components/Navigation.css frontend/src/components/AskTheBible.css
git commit -m "style: add shared accessible design tokens"
```

### Task 8: Reduce technical debt and initial bundle cost

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: files reported by `npm run lint`
- Create: `frontend/src/components/PageLoading.jsx`

- [ ] **Step 1: Capture the baseline**

Run: `npm run lint` and `npm run build`.

Expected baseline: 49 lint errors, 7 warnings, and a JavaScript chunk larger than 500 kB.

- [ ] **Step 2: Lazy-load route-level screens**

Use `React.lazy` for screens and wrap the current page in `Suspense` with a calm, accessible `PageLoading` fallback. Keep Navigation and the Home screen eager.

- [ ] **Step 3: Resolve lint findings by root cause**

Delete truly unused state/imports, render intended state where functionality is incomplete, and repair hook dependency problems by stabilizing callbacks or restructuring effects. Do not silence rules globally.

- [ ] **Step 4: Split oversized components only along behavior boundaries**

After tests cover current behavior, extract data fetching, reader navigation, notes, and AI sidebar concerns from `AncientTexts.jsx`. Extract map filters, detail panel, and timeline from `InteractiveMap.jsx`. Each extraction must keep focused tests green.

- [ ] **Step 5: Verify quality gates**

Run: `npm test -- --run && npm run lint && npm run build`.

Expected: tests pass, lint reports zero errors/warnings, build exits 0, and no route chunk exceeds the current monolithic 718 kB baseline.

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/package.json frontend/package-lock.json
git commit -m "refactor: reduce frontend debt and bundle size"
```

### Task 9: Complete an end-to-end product verification pass

**Files:**
- Create: `frontend/docs/qa-checklist.md`
- Modify: `README.md`

- [ ] **Step 1: Document critical journeys**

Cover direct-link entry, navigation/back-forward, Ask the Bible success/failure/retry, citations, save/share/clear, keyboard-only navigation, reduced motion, 200% zoom, and mobile layout.

- [ ] **Step 2: Run automated verification**

Run: `npm test -- --run && npm run lint && npm run build`.

Expected: all commands exit 0.

- [ ] **Step 3: Run browser verification**

Verify Home, AI Study, Scripture Reader, Compare, Research, Map, Library, and Community at desktop and mobile widths. Confirm there are no console errors, broken images, horizontal scrolling, dead controls, or misleading demo/live states.

- [ ] **Step 4: Update the README**

Document local services, ports, environment variables, demo-mode behavior, test commands, and known data-source limitations.

- [ ] **Step 5: Commit**

```bash
git add frontend/docs/qa-checklist.md README.md
git commit -m "docs: add product verification checklist"
```

## Recommended delivery order

1. Tasks 1–3: reliability and navigation foundation.
2. Tasks 4–6: trustworthy and focused AI Study experience.
3. Tasks 7–8: shared design quality, maintainability, and performance.
4. Task 9: complete regression and accessibility verification.

This ordering deliberately fixes broken behavior before visual polish and limits early design-system work to the application shell and AI Study screen. Other feature screens can then migrate to the shared tokens in separate, testable passes.
