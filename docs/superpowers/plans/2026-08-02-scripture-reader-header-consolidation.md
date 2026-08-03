# Scripture Reader Header Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Scripture Reader’s duplicated second header with one compact passage toolbar beneath the existing global navigation.

**Architecture:** Keep `Navigation` as the only site-level header and authentication surface. Move the reader’s book-picker and study-tools triggers into `PassageToolbar`, then stop rendering `ReaderHeader` from `ScriptureReaderPage`; Scripture routing, data loading, dialogs, preferences, and mobile navigation remain unchanged.

**Tech Stack:** React 19, Vite, Vitest, React Testing Library, user-event, CSS

---

## File Map

- Modify `frontend/src/reader/PassageToolbar.jsx`: accept and render the two reader destination actions.
- Modify `frontend/src/reader/ReaderChrome.test.jsx`: define and verify the new toolbar callback contract.
- Modify `frontend/src/reader/ScriptureReaderPage.jsx`: wire existing picker/tool callbacks to the toolbar and remove the redundant header instance.
- Modify `frontend/src/reader/ScriptureReaderPage.test.jsx`: enforce one application header, one sign-in action, one skip link, and one main landmark.
- Modify `frontend/src/reader/readerTokens.css`: visually group the two reader actions and preserve readable 48px targets across responsive layouts.

`ReaderHeader.jsx` remains unchanged in this focused patch. It is no longer rendered by the Scripture Reader, but deleting the component and its independent authentication tests would broaden this visual consolidation into an unrelated authentication cleanup.

### Task 1: Add Reader Actions to the Passage Toolbar

**Files:**
- Modify: `frontend/src/reader/ReaderChrome.test.jsx`
- Modify: `frontend/src/reader/PassageToolbar.jsx`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Extend the toolbar test helper with destination callbacks**

Add these callbacks to the `callbacks` object in `renderToolbar`:

```jsx
onOpenBooks: vi.fn(),
onOpenStudyTools: vi.fn(),
```

- [ ] **Step 2: Write the failing toolbar interaction test**

Add this test inside `describe('PassageToolbar', ...)`:

```jsx
it('opens reader destinations from the passage toolbar', () => {
  const callbacks = renderToolbar()
  const controls = screen.getByRole('region', { name: 'Passage controls' })

  fireEvent.click(within(controls).getByRole('button', { name: 'Choose a book' }))
  fireEvent.click(within(controls).getByRole('button', { name: 'Open study tools' }))

  expect(callbacks.onOpenBooks).toHaveBeenCalledOnce()
  expect(callbacks.onOpenStudyTools).toHaveBeenCalledOnce()
})
```

- [ ] **Step 3: Run the test and verify the RED state**

Run:

```bash
cd frontend
npm test -- --run src/reader/ReaderChrome.test.jsx -t "opens reader destinations from the passage toolbar"
```

Expected: FAIL because the two buttons do not yet exist in `PassageToolbar`.

- [ ] **Step 4: Add the toolbar callback props**

Extend the `PassageToolbar` parameter list after `onTranslationChange`:

```jsx
onOpenBooks,
onOpenStudyTools,
```

- [ ] **Step 5: Render the destination actions inside the settings group**

Insert this block as the first child of `.passage-toolbar__settings`, before the translation label:

```jsx
<div className="passage-toolbar__reader-actions" aria-label="Reader actions">
  <button
    className="passage-toolbar__reader-action"
    type="button"
    onClick={onOpenBooks}
  >
    Choose a book
  </button>
  <button
    className="passage-toolbar__reader-action"
    type="button"
    onClick={onOpenStudyTools}
  >
    Open study tools
  </button>
</div>
```

The wrapper is a `div`, not a second `nav`, so the page retains one primary-navigation landmark and the toolbar remains one labelled region.

- [ ] **Step 6: Add focused action-group styling**

Add beside the existing passage-toolbar group rules in `readerTokens.css`:

```css
.passage-toolbar__reader-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.65rem;
}

.passage-toolbar__reader-action {
  flex: 0 0 auto;
  padding: 0.7rem 1rem;
  font-size: 0.95rem;
  font-weight: 750;
  white-space: nowrap;
}
```

The existing `.passage-toolbar button` rule already supplies the 48px minimum height, border, contrast-aware colors, and pointer behavior.

- [ ] **Step 7: Run the component suite and verify GREEN**

Run:

```bash
cd frontend
npm test -- --run src/reader/ReaderChrome.test.jsx
```

Expected: all `ReaderChrome` tests PASS, including the new destination-action test.

- [ ] **Step 8: Commit the toolbar contract**

```bash
git add frontend/src/reader/PassageToolbar.jsx frontend/src/reader/ReaderChrome.test.jsx frontend/src/reader/readerTokens.css
git commit -m "feat: move reader actions into passage toolbar"
```

### Task 2: Remove the Duplicate Reader Header at Runtime

**Files:**
- Modify: `frontend/src/reader/ScriptureReaderPage.test.jsx`
- Modify: `frontend/src/reader/ScriptureReaderPage.jsx`

- [ ] **Step 1: Strengthen the App integration regression test**

In the existing test named `is lazy-integrated in App with primary navigation and no nested main landmarks`, add the following assertions after the reader is found:

```jsx
expect(screen.getAllByRole('banner')).toHaveLength(1)
expect(screen.getAllByRole('button', { name: 'Sign in' })).toHaveLength(1)
expect(document.querySelector('.reader-header')).not.toBeInTheDocument()
expect(screen.getAllByRole('link', { name: 'Skip to main content' })).toHaveLength(1)
```

Keep the existing primary-navigation and one-main-landmark assertions.

- [ ] **Step 2: Run the integration test and verify the RED state**

Run:

```bash
cd frontend
npm test -- --run src/reader/ScriptureReaderPage.test.jsx -t "primary navigation and no nested main landmarks"
```

Expected: FAIL because the page currently renders both the global banner and `.reader-header`, producing duplicate branding and sign-in actions.

- [ ] **Step 3: Remove the redundant component import and render**

Delete this import from `ScriptureReaderPage.jsx`:

```jsx
import ReaderHeader from './ReaderHeader'
```

Delete this rendered block:

```jsx
<ReaderHeader
  onHome={() => changePage('home')}
  onOpenBooks={openBooks}
  onOpenStudyTools={openStudyTools}
/>
```

- [ ] **Step 4: Wire the existing actions into `PassageToolbar`**

Add these props to the existing toolbar instance:

```jsx
onOpenBooks={openBooks}
onOpenStudyTools={openStudyTools}
```

Do not change `openBooks`, `openStudyTools`, route navigation, data requests, or overlay state. This keeps the change limited to control placement.

- [ ] **Step 5: Run the focused integration test and verify GREEN**

Run:

```bash
cd frontend
npm test -- --run src/reader/ScriptureReaderPage.test.jsx -t "primary navigation and no nested main landmarks"
```

Expected: PASS with one application banner, one sign-in action, no runtime `.reader-header`, one skip link, and one main landmark.

- [ ] **Step 6: Run the full reader-page integration suite**

Run:

```bash
cd frontend
npm test -- --run src/reader/ScriptureReaderPage.test.jsx
```

Expected: all reader-page tests PASS, including the existing book-picker and study-tools interaction flows.

- [ ] **Step 7: Commit the page consolidation**

```bash
git add frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/ScriptureReaderPage.test.jsx
git commit -m "fix: consolidate scripture reader header"
```

### Task 3: Verify Accessibility, Responsive Behavior, and Production Output

**Files:**
- Verify only: `frontend/src/reader/PassageToolbar.jsx`
- Verify only: `frontend/src/reader/ScriptureReaderPage.jsx`
- Verify only: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Run the combined reader and navigation regression suites**

Run:

```bash
cd frontend
npm test -- --run src/reader/ReaderChrome.test.jsx src/reader/ScriptureReaderPage.test.jsx src/components/Navigation.test.jsx
```

Expected: all tests PASS with zero failures.

- [ ] **Step 2: Run the complete frontend test suite**

Run:

```bash
cd frontend
npm test -- --run
```

Expected: all frontend tests PASS with zero failures.

- [ ] **Step 3: Run lint and the production build**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: both commands exit successfully with no lint errors and a completed Vite production build.

- [ ] **Step 4: Verify the live desktop reader**

Open:

```text
http://localhost:5001/#scriptures?book=Genesis&chapter=1&translation=KJV&canon=ETHIO81
```

Verify all of the following from the rendered DOM and visible page:

```text
Primary navigation landmarks: 1
Banner landmarks: 1
Buttons named “Sign in”: 1
Elements matching .reader-header: 0
Main landmarks: 1
Links named “Skip to main content”: 1
Genesis 1 verse text becomes visible
“Choose a book” opens the existing picker
“Open study tools” opens the existing study panel
```

- [ ] **Step 5: Verify the narrow reader layout**

At a viewport no wider than 767px, verify:

```text
The passage-toolbar control groups remain reachable without clipping.
Each reader action retains its full text label.
The existing mobile reader navigation remains visible and usable.
The Scripture text does not gain horizontal page overflow.
```

- [ ] **Step 6: Inspect the final scoped diff**

Run:

```bash
git diff --check -- frontend/src/reader/PassageToolbar.jsx frontend/src/reader/ReaderChrome.test.jsx frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/ScriptureReaderPage.test.jsx frontend/src/reader/readerTokens.css
git status --short
```

Expected: no whitespace errors in the scoped files; unrelated pre-existing worktree changes remain untouched.

- [ ] **Step 7: Commit verification-only adjustments if any were required**

If verification required a scoped CSS or test adjustment, commit only those reader files:

```bash
git add frontend/src/reader/PassageToolbar.jsx frontend/src/reader/ReaderChrome.test.jsx frontend/src/reader/ScriptureReaderPage.jsx frontend/src/reader/ScriptureReaderPage.test.jsx frontend/src/reader/readerTokens.css
git commit -m "test: verify consolidated reader controls"
```

If no adjustment was needed, do not create an empty commit.
