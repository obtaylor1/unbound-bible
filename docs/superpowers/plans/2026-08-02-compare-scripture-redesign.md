# Compare Scripture Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the existing `#compare` page as the approved accessible, comparison-first workspace while retaining its data, note, bookmark, share, and study behavior.

**Architecture:** Keep `TextualComparisonWorkspace` as the state and request orchestrator, but move metadata, pure comparison rules, toolbar, translation selection, summary, source cards, and study drawer into focused files under `components/textualComparison`. Use abortable API requests and derived view models so stale passages cannot overwrite current state. Apply a page-scoped token system and responsive grid/drawer layout without changing the global navigation or Scripture Reader.

**Tech Stack:** React 19, Vite 7, Vitest 3, Testing Library, Playwright, axe-core, CSS.

---

## File Structure

- Create `frontend/src/components/textualComparison/comparisonModel.js`: translation metadata, category definitions, canon membership, availability states, word differences, and summary helpers.
- Create `frontend/src/components/textualComparison/comparisonModel.test.js`: pure behavior tests.
- Create `frontend/src/components/textualComparison/ComparisonToolbar.jsx`: grouped passage, view, base-reference, difference, and Study Tools controls.
- Create `frontend/src/components/textualComparison/TranslationSelector.jsx`: search, category filters, compact checkbox rows, and selection count.
- Create `frontend/src/components/textualComparison/ComparisonSummary.jsx`: beginner summary and primary actions.
- Create `frontend/src/components/textualComparison/TranslationComparisonCard.jsx`: consistent source card and availability messaging.
- Create `frontend/src/components/textualComparison/ComparisonStudyDrawer.jsx`: accessible drawer shell around the existing study assistant.
- Create `frontend/src/components/textualComparison/CompareComponents.test.jsx`: focused component interaction and accessibility-contract tests.
- Modify `frontend/src/components/TextualComparisonWorkspace.jsx`: orchestration, abortable data loading, responsive panel state, notes, bookmarks, sharing, verse and chapter composition.
- Replace `frontend/src/components/TextualComparisonWorkspace.css`: approved visual system and responsive layout.
- Create `frontend/src/components/TextualComparisonWorkspace.test.jsx`: integrated data, selection, drawer, error, and regression tests.
- Create `frontend/e2e/compare-scripture.spec.js`: live desktop, tablet, mobile, keyboard, and axe checks.

### Task 1: Pure Comparison Model

**Files:**
- Create: `frontend/src/components/textualComparison/comparisonModel.js`
- Create: `frontend/src/components/textualComparison/comparisonModel.test.js`

- [ ] **Step 1: Write failing model tests**

Cover the default pair, four-source limit, category/search filtering, base-source replacement, canon membership, database-missing versus canon-excluded messaging, normalized word differences, and summary counts:

```js
import { describe, expect, it } from 'vitest'
import {
  DEFAULT_TRANSLATIONS,
  applyTranslationToggle,
  buildSourceState,
  filterTranslations,
  summarizeComparison,
} from './comparisonModel'

it('starts with Ethiopian Critical Text and KJV', () => {
  expect(DEFAULT_TRANSLATIONS).toEqual(['eth81', 'kjv'])
})

it('limits comparison to four sources', () => {
  expect(applyTranslationToggle(['eth81', 'kjv', 'asv', 'web'], 'webbe', 'eth81'))
    .toMatchObject({ selected: ['eth81', 'kjv', 'asv', 'web'], limitReached: true })
})

it('describes missing Ethiopian Genesis text as unavailable, not excluded', () => {
  expect(buildSourceState({ key: 'eth81', book: 'Genesis', text: null }).kind)
    .toBe('database-missing')
})

it('filters translations by category and query', () => {
  expect(filterTranslations({ category: 'ethiopian', query: 'enoch' }).map((item) => item.key))
    .toContain('1en_ch')
})

it('summarizes wording differences for beginners', () => {
  expect(summarizeComparison(['In the beginning God created', 'At first God made']).differenceCount)
    .toBeGreaterThan(0)
})
```

- [ ] **Step 2: Run the model test and verify RED**

Run: `cd frontend && npm test -- --run src/components/textualComparison/comparisonModel.test.js`

Expected: FAIL because `comparisonModel.js` does not exist.

- [ ] **Step 3: Implement the model**

Export complete immutable translation records with `key`, `code`, `name`, `tradition`, `year`, `language`, and `categories`. Implement:

```js
export const DEFAULT_TRANSLATIONS = ['eth81', 'kjv']
export const MAX_TRANSLATIONS = 4

export function applyTranslationToggle(selected, key, base) {
  if (selected.includes(key)) {
    if (selected.length === 1) return { selected, base, minimumReached: true }
    const next = selected.filter((item) => item !== key)
    return { selected: next, base: base === key ? next[0] : base }
  }
  if (selected.length >= MAX_TRANSLATIONS) return { selected, base, limitReached: true }
  return { selected: [...selected, key], base }
}
```

Add canonical sets and return one of `available`, `canon-excluded`, `translation-unavailable`, or `database-missing`. Difference helpers must normalize punctuation and case while retaining the original displayed words.

- [ ] **Step 4: Run the model test and verify GREEN**

Run: `cd frontend && npm test -- --run src/components/textualComparison/comparisonModel.test.js`

Expected: all model tests PASS.

- [ ] **Step 5: Commit the model**

```bash
git add frontend/src/components/textualComparison/comparisonModel.js frontend/src/components/textualComparison/comparisonModel.test.js
git commit -m "feat: add scripture comparison model"
```

### Task 2: Toolbar and Translation Selector

**Files:**
- Create: `frontend/src/components/textualComparison/ComparisonToolbar.jsx`
- Create: `frontend/src/components/textualComparison/TranslationSelector.jsx`
- Create: `frontend/src/components/textualComparison/CompareComponents.test.jsx`

- [ ] **Step 1: Write failing toolbar and selector tests**

Render the components with real callbacks and assert visible grouping, accessible names, selected/pressed state, compact filters, search, selection count, disabled rows at the four-source limit, and the Study Tools trigger:

```jsx
expect(screen.getByRole('group', { name: 'Passage' })).toBeInTheDocument()
expect(screen.getByRole('group', { name: 'View' })).toBeInTheDocument()
expect(screen.getByRole('button', { name: 'Open Study Tools' })).toBeInTheDocument()
expect(screen.getByRole('button', { name: 'Ethiopian' })).toHaveAttribute('aria-pressed', 'false')
await user.click(screen.getByRole('button', { name: 'Ethiopian' }))
expect(screen.getByRole('checkbox', { name: /Ethiopian Orthodox Critical Text/ })).toBeVisible()
expect(screen.getByText('Comparing 2 translations')).toBeInTheDocument()
```

- [ ] **Step 2: Run the component test and verify RED**

Run: `cd frontend && npm test -- --run src/components/textualComparison/CompareComponents.test.jsx`

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement grouped toolbar controls**

Use `<fieldset>` and `<legend>` for Passage, View, and Comparison. Use labeled native selects, a two-button `aria-pressed` segmented control, a switch-style difference button, and an explicit `Open Study Tools` button. Disable Verse only in chapter mode.

- [ ] **Step 4: Implement the compact translation selector**

Use a labeled search input, category buttons with `aria-pressed`, compact native checkboxes, identity badges, tradition metadata, and live count feedback. Call `onToggle(key)` only when the row is enabled and keep the selection limit explanation visible.

- [ ] **Step 5: Run the component test and verify GREEN**

Run: `cd frontend && npm test -- --run src/components/textualComparison/CompareComponents.test.jsx`

Expected: toolbar and selector tests PASS.

- [ ] **Step 6: Commit toolbar and selector**

```bash
git add frontend/src/components/textualComparison/ComparisonToolbar.jsx frontend/src/components/textualComparison/TranslationSelector.jsx frontend/src/components/textualComparison/CompareComponents.test.jsx
git commit -m "feat: add comparison controls"
```

### Task 3: Summary and Translation Cards

**Files:**
- Create: `frontend/src/components/textualComparison/ComparisonSummary.jsx`
- Create: `frontend/src/components/textualComparison/TranslationComparisonCard.jsx`
- Modify: `frontend/src/components/textualComparison/CompareComponents.test.jsx`

- [ ] **Step 1: Add failing summary and card tests**

Assert the readable summary, the three beginner actions, consistent source hierarchy, base badge, scripture typography hook, difference count, and each status message:

```jsx
expect(screen.getByRole('heading', { name: 'Genesis 1:1 comparison' })).toBeInTheDocument()
expect(screen.getByRole('button', { name: 'Show Differences' })).toBeInTheDocument()
expect(screen.getByRole('button', { name: 'Explain This Verse' })).toBeInTheDocument()
expect(screen.getByRole('button', { name: 'View Original Words' })).toBeInTheDocument()
expect(screen.getByText('Text unavailable')).toBeInTheDocument()
expect(screen.queryByText('Canon Exclusion')).not.toBeInTheDocument()
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd frontend && npm test -- --run src/components/textualComparison/CompareComponents.test.jsx`

Expected: FAIL because summary and card exports are missing.

- [ ] **Step 3: Implement the summary**

Render the passage heading, one-sentence beginner explanation, comparison/difference count, and three callback-driven buttons. The summary must not claim agreement when fewer than two texts are available.

- [ ] **Step 4: Implement the consistent translation card**

Render a sticky source header; reference; either highlighted scripture or one compact semantic status; optional `Learn more` and `Choose another source`; difference badge; bookmark and notes actions; and a source footer. Use `aria-current="true"` or visible text for the base source instead of color alone.

- [ ] **Step 5: Run the component tests and verify GREEN**

Run: `cd frontend && npm test -- --run src/components/textualComparison/CompareComponents.test.jsx`

Expected: all component tests PASS.

- [ ] **Step 6: Commit summary and cards**

```bash
git add frontend/src/components/textualComparison/ComparisonSummary.jsx frontend/src/components/textualComparison/TranslationComparisonCard.jsx frontend/src/components/textualComparison/CompareComponents.test.jsx
git commit -m "feat: add comparison summary and source cards"
```

### Task 4: Accessible Study Tools Drawer

**Files:**
- Create: `frontend/src/components/textualComparison/ComparisonStudyDrawer.jsx`
- Modify: `frontend/src/components/textualComparison/CompareComponents.test.jsx`
- Reuse: `frontend/src/components/StudyAssistantSidebar.jsx`

- [ ] **Step 1: Add failing drawer tests**

Assert the drawer is absent when closed, becomes a named dialog when open, has Insights/Cross-References/Words/Notes primary tabs, closes with its button and Escape, and restores focus to the provided trigger ref.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd frontend && npm test -- --run src/components/textualComparison/CompareComponents.test.jsx`

Expected: FAIL because `ComparisonStudyDrawer` is missing.

- [ ] **Step 3: Implement the drawer shell**

Use `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, a backdrop, close button, one tool row, scrollable content, and a persistent `Ask Study Assistant` action. Use the existing `StudyAssistantSidebar` inside the selected tool surface so saved notes and assistant behavior remain intact. Add Escape handling, focus containment, body-scroll cleanup, and trigger focus restoration.

- [ ] **Step 4: Run the component tests and verify GREEN**

Run: `cd frontend && npm test -- --run src/components/textualComparison/CompareComponents.test.jsx`

Expected: all drawer tests PASS.

- [ ] **Step 5: Commit the drawer**

```bash
git add frontend/src/components/textualComparison/ComparisonStudyDrawer.jsx frontend/src/components/textualComparison/CompareComponents.test.jsx
git commit -m "feat: add comparison study drawer"
```

### Task 5: Recompose the Workspace with Abortable Data

**Files:**
- Modify: `frontend/src/components/TextualComparisonWorkspace.jsx`
- Create: `frontend/src/components/TextualComparisonWorkspace.test.jsx`

- [ ] **Step 1: Write failing integrated workspace tests**

Mock only `fetch` boundaries. Assert:

- initial Ethiopian/KJV pair and closed Study Tools;
- real Genesis rows render KJV while ETH81 shows database-missing copy;
- opening and closing Study Tools;
- four-source selection limit and base replacement;
- verse/chapter switching;
- stale chapter responses are ignored after a rapid passage change;
- request failure renders a retryable error rather than an unavailable-source notice;
- bookmark, local scratchpad, and share callbacks remain available.

Use deferred promises for stale-response coverage and restore globals after every test.

- [ ] **Step 2: Run the workspace test and verify RED**

Run: `cd frontend && npm test -- --run src/components/TextualComparisonWorkspace.test.jsx`

Expected: FAIL against the old four-source, open-sidebar workspace.

- [ ] **Step 3: Rebuild workspace orchestration**

Replace embedded UI with the focused components. Initialize `selectedTranslations` from `DEFAULT_TRANSLATIONS` and `showStudyTools` to `false`. Add `AbortController` cleanup to books, chapter, and detail requests. Track `loading`, `ready`, `empty`, `offline`, and `error` separately. Derive source view models from selected translations and the current verse rows.

- [ ] **Step 4: Preserve chapter mode and study behaviors**

Keep aligned chapter rendering, bookmark storage, note autosave keys, share payloads, and `StudyAssistantSidebar` note callbacks. Route summary actions to difference highlighting and the appropriate Study Tools tab.

- [ ] **Step 5: Run workspace and existing related tests**

Run: `cd frontend && npm test -- --run src/components/TextualComparisonWorkspace.test.jsx src/components/textualComparison/CompareComponents.test.jsx src/components/Navigation.test.jsx`

Expected: all tests PASS.

- [ ] **Step 6: Commit workspace integration**

```bash
git add frontend/src/components/TextualComparisonWorkspace.jsx frontend/src/components/TextualComparisonWorkspace.test.jsx
git commit -m "feat: rebuild compare scripture workspace"
```

### Task 6: Implement the Approved Visual System and Responsive Layout

**Files:**
- Replace: `frontend/src/components/TextualComparisonWorkspace.css`
- Modify: `frontend/src/components/TextualComparisonWorkspace.jsx`
- Modify: `frontend/src/components/textualComparison/ComparisonToolbar.jsx`
- Modify: `frontend/src/components/textualComparison/TranslationSelector.jsx`
- Modify: `frontend/src/components/textualComparison/ComparisonSummary.jsx`
- Modify: `frontend/src/components/textualComparison/TranslationComparisonCard.jsx`
- Modify: `frontend/src/components/textualComparison/ComparisonStudyDrawer.jsx`

- [ ] **Step 1: Add structural CSS assertions to the workspace test**

Assert stable layout hooks such as `data-testid="comparison-workspace"`, `data-testid="translation-selector"`, `data-testid="comparison-grid"`, and drawer state classes. These hooks support browser layout measurement without testing cosmetic implementation details.

- [ ] **Step 2: Run the workspace test and verify RED**

Run: `cd frontend && npm test -- --run src/components/TextualComparisonWorkspace.test.jsx`

Expected: FAIL until the layout hooks are present.

- [ ] **Step 3: Replace the page-scoped CSS**

Implement the approved navy/slate surfaces, subtle manuscript-gold borders, purple translation identity, cyan differences, amber availability, ivory text, serif scripture, 270px selector, flexible card grid, 360px overlay drawer, sticky card headers, 44px controls, visible focus, reduced motion, and scroll containment.

Use breakpoints:

```css
@media (max-width: 1180px) { /* selector drawer + two-card comparison */ }
@media (max-width: 760px) { /* stacked toolbar and one-card reading stream */ }
@media (prefers-reduced-motion: reduce) { /* remove drawer and reveal motion */ }
```

Do not change app-wide tokens or navigation styles.

- [ ] **Step 4: Run component tests, lint, and build**

Run: `cd frontend && npm test -- --run src/components/TextualComparisonWorkspace.test.jsx src/components/textualComparison/CompareComponents.test.jsx && npm run lint && npm run build`

Expected: tests PASS, lint exits 0, and Vite build succeeds.

- [ ] **Step 5: Commit the visual redesign**

```bash
git add frontend/src/components/TextualComparisonWorkspace.css frontend/src/components/TextualComparisonWorkspace.jsx frontend/src/components/textualComparison
git commit -m "style: redesign compare scripture workspace"
```

### Task 7: Live Browser and Accessibility Verification

**Files:**
- Create: `frontend/e2e/compare-scripture.spec.js`

- [ ] **Step 1: Write the browser checks**

At `#compare`, verify:

```js
await expect(page.getByRole('heading', { name: 'Compare translations' })).toBeVisible()
await expect(page.getByText('Comparing 2 translations')).toBeVisible()
await expect(page.getByRole('dialog', { name: 'Study Tools' })).toHaveCount(0)
await page.getByRole('button', { name: 'Open Study Tools' }).click()
await expect(page.getByRole('dialog', { name: 'Study Tools' })).toBeVisible()
expect(await new AxeBuilder({ page }).include('[data-testid="comparison-workspace"]').analyze()).toMatchObject({ violations: [] })
```

Add desktop, tablet, and phone projects; measure that `document.documentElement.scrollWidth <= document.documentElement.clientWidth`; verify visible keyboard focus; and confirm 1 Enoch can be selected from live Ethiopian data.

- [ ] **Step 2: Run E2E and verify RED if a contract is missing**

Run: `cd frontend && npx playwright test e2e/compare-scripture.spec.js --reporter=line`

Expected: any missing live-browser contract fails with a specific assertion.

- [ ] **Step 3: Make only contract-level corrections**

Adjust accessible names, focus restoration, overflow containment, or breakpoint CSS required by the failing assertion. Do not add unrelated features.

- [ ] **Step 4: Run the complete verification suite**

Run:

```bash
cd frontend
npm test -- --run
npm run lint
npm run build
npx playwright test e2e/compare-scripture.spec.js --reporter=line
```

Expected: all unit tests, lint, build, and Compare Scripture browser projects PASS with no axe violations.

- [ ] **Step 5: Commit browser coverage and final corrections**

```bash
git add frontend/e2e/compare-scripture.spec.js frontend/src/components/TextualComparisonWorkspace.jsx frontend/src/components/TextualComparisonWorkspace.css frontend/src/components/textualComparison
git commit -m "test: verify compare scripture redesign"
```

### Task 8: Final Review

**Files:**
- Review only the paths listed in this plan.

- [ ] **Step 1: Compare against the design specification**

Confirm every section in `docs/superpowers/specs/2026-08-02-compare-scripture-redesign-design.md` is represented by a component, state, style, or test.

- [ ] **Step 2: Check the working tree carefully**

Run: `git status --short` and `git diff --check HEAD -- frontend/src/components/TextualComparisonWorkspace.jsx frontend/src/components/TextualComparisonWorkspace.css frontend/src/components/textualComparison frontend/e2e/compare-scripture.spec.js`

Expected: no whitespace errors in redesign paths. Unrelated user changes remain untouched.

- [ ] **Step 3: Visually inspect the live page**

Open `http://localhost:5001/#compare`, compare it to the supplied mockup, exercise translation selection and Study Tools, and verify both a standard passage and 1 Enoch.

- [ ] **Step 4: Request code review**

Use the `requesting-code-review` skill, address High and Medium findings, and rerun the affected verification commands.

- [ ] **Step 5: Finish the branch**

Use the `verification-before-completion` and `finishing-a-development-branch` skills. Report exact test totals, the final commit, and any preserved pre-existing working-tree changes.
