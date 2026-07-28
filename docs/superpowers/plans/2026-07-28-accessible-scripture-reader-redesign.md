# Accessible Scripture Reader Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the crowded three-panel Scripture workspace with an accessible, responsive, reading-first reader that preserves every existing study entry point and the Unbound color identity.

**Architecture:** Build a new bounded `frontend/src/reader` feature rather than extending the 3,000-line `AncientTexts` component. Route state owns the selected passage; a preferences provider owns persisted visual settings; temporary Book and Study drawers receive explicit state and callbacks. Existing backend endpoints remain unchanged, and the old component stays available until the new reader passes parity and browser checks.

**Tech Stack:** React 19, Vite 7, plain CSS with semantic custom properties, Vitest, Testing Library, Playwright, existing FastAPI biblical-text endpoints.

---

## File map

### Create

- `frontend/src/reader/readerTokens.css` — semantic light/dark tokens, typography, motion, focus, and shared reader primitives.
- `frontend/src/reader/ReaderPreferences.jsx` — persisted theme, Scripture size, and reading-width state.
- `frontend/src/reader/ReaderPreferences.test.jsx` — persistence and document-theme tests.
- `frontend/src/reader/readerRoute.js` — parse and serialize `#scriptures` passage parameters.
- `frontend/src/reader/readerRoute.test.js` — route normalization tests.
- `frontend/src/reader/scriptureApi.js` — normalized book, chapter, and verse-detail requests.
- `frontend/src/reader/scriptureApi.test.js` — response and failure tests.
- `frontend/src/reader/ReaderErrorBoundary.jsx` — lazy/render failure recovery instead of a blank page.
- `frontend/src/reader/ReaderStatus.jsx` — loading, empty, offline, and recoverable request states.
- `frontend/src/reader/ReaderStatus.test.jsx` — actionable state tests.
- `frontend/src/reader/ReaderHeader.jsx` — reader brand and global reader actions.
- `frontend/src/reader/PassageToolbar.jsx` — passage, translation, text, theme, and chapter navigation.
- `frontend/src/reader/ReaderChrome.test.jsx` — labels, targets, and navigation callbacks.
- `frontend/src/reader/ScripturePane.jsx` — semantic chapter and verse rendering.
- `frontend/src/reader/ScripturePane.test.jsx` — reading semantics and verse selection.
- `frontend/src/reader/BookPicker.jsx` — canon, search, book, and chapter picker.
- `frontend/src/reader/BookPicker.test.jsx` — keyboard, filtering, selection, and dismissal.
- `frontend/src/reader/useDialogFocus.js` — Escape, focus containment, and focus restoration shared by reader dialogs.
- `frontend/src/reader/studyToolRegistry.js` — one source of truth for visible study-tool labels and destinations.
- `frontend/src/reader/StudyTools.jsx` — desktop drawer/mobile sheet and inline verse-detail tabs.
- `frontend/src/reader/StudyTools.test.jsx` — focus, dismissal, labels, and study routing.
- `frontend/src/reader/ReaderBottomNavigation.jsx` — labeled mobile destinations.
- `frontend/src/reader/ScriptureReaderPage.jsx` — route-level orchestration.
- `frontend/src/reader/ScriptureReaderPage.test.jsx` — end-to-end component flow.
- `frontend/e2e/scripture-reader-accessibility.spec.js` — responsive, keyboard, preference, and recovery journeys.

### Modify

- `frontend/src/App.jsx` — lazy-load the new reader inside the error boundary and provider.
- `frontend/src/routing/pageRoutes.js` — recognize `#scriptures?...` as the reader route.
- `frontend/src/routing/pageRoutes.test.js` — parameterized reader hash coverage.
- `frontend/src/index.css` — load reader fonts or privacy-safe fallbacks without overriding feature tokens.
- `frontend/src/components/AncientTexts.jsx` — remove from the active route only after feature parity; keep temporarily as a reference during extraction.
- `frontend/src/components/AncientTexts.css` — remove from the active route with `AncientTexts`; do not delete until final parity verification.
- `frontend/playwright.config.js` — add small-phone coverage if it is not already represented.
- `frontend/package.json` and `frontend/package-lock.json` — add `@axe-core/playwright` for deterministic browser accessibility checks.

## Task 1: Semantic tokens and persisted reader preferences

**Files:**
- Create: `frontend/src/reader/readerTokens.css`
- Create: `frontend/src/reader/ReaderPreferences.jsx`
- Create: `frontend/src/reader/ReaderPreferences.test.jsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Write the failing preferences tests**

```jsx
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ReaderPreferencesProvider, useReaderPreferences } from './ReaderPreferences'

function Harness() {
  const value = useReaderPreferences()
  return (
    <>
      <output>{`${value.theme}:${value.fontSize}:${value.readingWidth}`}</output>
      <button onClick={() => value.setTheme('light')}>Use light</button>
      <button onClick={() => value.setFontSize('xl')}>Use extra large text</button>
    </>
  )
}

describe('ReaderPreferences', () => {
  beforeEach(() => localStorage.clear())

  it('persists accessible reader choices and applies the theme', () => {
    render(<ReaderPreferencesProvider><Harness /></ReaderPreferencesProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Use light' }))
    fireEvent.click(screen.getByRole('button', { name: 'Use extra large text' }))
    expect(localStorage.getItem('unbound.reader.preferences')).toContain('"theme":"light"')
    expect(localStorage.getItem('unbound.reader.preferences')).toContain('"fontSize":"xl"')
    expect(document.documentElement).toHaveAttribute('data-reader-theme', 'light')
  })
})
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run: `cd frontend && npm test -- --run src/reader/ReaderPreferences.test.jsx`

Expected: FAIL because `ReaderPreferences.jsx` does not exist.

- [ ] **Step 3: Implement the provider with validated stored values**

```jsx
import { createContext, useContext, useEffect, useState } from 'react'
import './readerTokens.css'

const STORAGE_KEY = 'unbound.reader.preferences'
const defaults = { theme: 'dark', fontSize: 'md', readingWidth: 'comfortable' }
const allowed = {
  theme: new Set(['light', 'dark']),
  fontSize: new Set(['sm', 'md', 'lg', 'xl', 'xxl']),
  readingWidth: new Set(['comfortable', 'wide'])
}
const ReaderPreferencesContext = createContext(null)

function readPreferences() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return Object.fromEntries(
      Object.entries(defaults).map(([key, fallback]) => [key, allowed[key].has(value[key]) ? value[key] : fallback])
    )
  } catch {
    return defaults
  }
}

export function ReaderPreferencesProvider({ children }) {
  const [preferences, setPreferences] = useState(readPreferences)
  const update = (key) => (value) => setPreferences((current) => ({ ...current, [key]: value }))
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
    document.documentElement.dataset.readerTheme = preferences.theme
  }, [preferences])
  const value = {
    ...preferences,
    setTheme: update('theme'),
    setFontSize: update('fontSize'),
    setReadingWidth: update('readingWidth')
  }
  return <ReaderPreferencesContext.Provider value={value}>{children}</ReaderPreferencesContext.Provider>
}

export function useReaderPreferences() {
  const value = useContext(ReaderPreferencesContext)
  if (!value) throw new Error('useReaderPreferences must be used within ReaderPreferencesProvider')
  return value
}
```

- [ ] **Step 4: Add semantic tokens and shared accessibility primitives**

```css
.scripture-reader {
  --reader-canvas: #070a12;
  --reader-surface: #0e1422;
  --reader-elevated: #161d2e;
  --reader-text: #f5f7fb;
  --reader-scripture: #edf0f7;
  --reader-secondary: #aeb8ca;
  --reader-border: #35405a;
  --reader-primary: #6d3fe0;
  --reader-violet: #b49cff;
  --reader-teal: #2dd4bf;
  --reader-gold: #f6c453;
  --reader-danger: #fb7185;
  --reader-font-size: 21px;
  color: var(--reader-text);
  background: var(--reader-canvas);
}

[data-reader-theme='light'] .scripture-reader {
  --reader-canvas: #f7f5fc;
  --reader-surface: #ffffff;
  --reader-elevated: #f1eef8;
  --reader-text: #171325;
  --reader-scripture: #272233;
  --reader-secondary: #565064;
  --reader-border: #cbc4da;
  --reader-violet: #5426bb;
  --reader-teal: #086f65;
  --reader-gold: #7a5200;
}

.scripture-reader button,
.scripture-reader a,
.scripture-reader input,
.scripture-reader select {
  font: inherit;
}

.scripture-reader :focus-visible {
  outline: 3px solid var(--reader-teal);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  .scripture-reader *, .scripture-reader *::before, .scripture-reader *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Run focused tests, lint, and commit**

Run: `cd frontend && npm test -- --run src/reader/ReaderPreferences.test.jsx && npm run lint`

Expected: test PASS and lint exits 0.

```bash
git add frontend/src/reader/readerTokens.css frontend/src/reader/ReaderPreferences.jsx frontend/src/reader/ReaderPreferences.test.jsx frontend/src/index.css
git commit -m "feat: add accessible reader theme preferences"
```

## Task 2: Passage routing and normalized Scripture API

**Files:**
- Create: `frontend/src/reader/readerRoute.js`
- Create: `frontend/src/reader/readerRoute.test.js`
- Create: `frontend/src/reader/scriptureApi.js`
- Create: `frontend/src/reader/scriptureApi.test.js`
- Modify: `frontend/src/routing/pageRoutes.js`
- Modify: `frontend/src/routing/pageRoutes.test.js`

- [ ] **Step 1: Write failing route and API tests**

```js
import { describe, expect, it, vi } from 'vitest'
import { parseReaderHash, readerHash } from './readerRoute'
import { getBookChapters, getChapter } from './scriptureApi'

describe('reader route', () => {
  it('normalizes a parameterized Scripture hash', () => {
    expect(parseReaderHash('#scriptures?book=Genesis&chapter=2&translation=KJV')).toEqual({
      book: 'Genesis', chapter: 2, translation: 'KJV', canon: 'ETHIO81', verse: null
    })
    expect(readerHash({ book: '1 Enoch', chapter: 1, translation: 'ETH81', canon: 'ETHIO81' }))
      .toBe('#scriptures?book=1+Enoch&chapter=1&translation=ETH81&canon=ETHIO81')
  })
})

it('normalizes chapter content', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ content: [{ book: 'Genesis', chapter: 1, verse: 1, text: 'In the beginning', translation: 'KJV' }] })
  }))
  await expect(getChapter({ book: 'Genesis', chapter: 1, translation: 'KJV' }))
    .resolves.toEqual([{ book: 'Genesis', chapter: 1, verse: 1, text: 'In the beginning', translation: 'KJV' }])
})

it('derives real chapter numbers from loaded book content', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ content: [{ chapter: 1 }, { chapter: 2 }, { chapter: 2 }] })
  }))
  await expect(getBookChapters('Exodus')).resolves.toEqual([1, 2])
})
```

- [ ] **Step 2: Run tests and verify missing exports**

Run: `cd frontend && npm test -- --run src/reader/readerRoute.test.js src/reader/scriptureApi.test.js`

Expected: FAIL because the reader modules do not exist.

- [ ] **Step 3: Implement safe hash parsing and serialization**

```js
const defaults = { book: 'Genesis', chapter: 1, translation: 'KJV', canon: 'ETHIO81', verse: null }

export function parseReaderHash(hash = window.location.hash) {
  const [, query = ''] = hash.split('?')
  const params = new URLSearchParams(query)
  const chapter = Number(params.get('chapter'))
  const verse = Number(params.get('verse'))
  return {
    book: params.get('book')?.trim() || defaults.book,
    chapter: Number.isInteger(chapter) && chapter > 0 ? chapter : defaults.chapter,
    translation: params.get('translation')?.trim().toUpperCase() || defaults.translation,
    canon: params.get('canon')?.trim().toUpperCase() || defaults.canon,
    verse: Number.isInteger(verse) && verse > 0 ? verse : null
  }
}

export function readerHash({ book, chapter, translation, canon, verse }) {
  const params = new URLSearchParams({ book, chapter: String(chapter), translation, canon })
  if (verse) params.set('verse', String(verse))
  return `#scriptures?${params.toString()}`
}
```

- [ ] **Step 4: Implement normalized API functions and parameter-aware page routing**

```js
async function requestJson(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`The Scripture library returned ${response.status}.`)
  return response.json()
}

export async function getBooks(canon = 'ETHIO81', signal) {
  const data = await requestJson(`/api/v1/books?canon=${encodeURIComponent(canon)}`, signal)
  return (data.books || []).map((book) => typeof book === 'string' ? book : book.name).filter(Boolean)
}

export async function getChapter({ book, chapter }, signal) {
  const data = await requestJson(
    `/api/biblical-texts/chapter-content?book=${encodeURIComponent(book)}&chapter=${chapter}`,
    signal
  )
  return data.content || []
}

export async function getBookChapters(book, signal) {
  const data = await requestJson(`/api/biblical-texts/book-content?book=${encodeURIComponent(book)}`, signal)
  return [...new Set((data.content || []).map((row) => Number(row.chapter)).filter((chapter) => chapter > 0))].sort((a, b) => a - b)
}

export async function getVerseDetails({ book, chapter, verse }, signal) {
  return requestJson(`/api/v1/texts/${encodeURIComponent(book)}/${chapter}/${verse}/details`, signal)
}
```

Modify `pageFromHash` to ignore reader parameters:

```js
export const pageFromHash = (hash = '') => {
  const route = hash.replace(/^#/, '').split('?')[0].toLowerCase()
  return HASH_TO_PAGE[route] ?? 'home'
}
```

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend && npm test -- --run src/reader/readerRoute.test.js src/reader/scriptureApi.test.js src/routing/pageRoutes.test.js`

Expected: all selected tests PASS.

```bash
git add frontend/src/reader/readerRoute.js frontend/src/reader/readerRoute.test.js frontend/src/reader/scriptureApi.js frontend/src/reader/scriptureApi.test.js frontend/src/routing/pageRoutes.js frontend/src/routing/pageRoutes.test.js
git commit -m "feat: add Scripture reader routing and data client"
```

## Task 3: Reader status states and route error recovery

**Files:**
- Create: `frontend/src/reader/ReaderStatus.jsx`
- Create: `frontend/src/reader/ReaderStatus.test.jsx`
- Create: `frontend/src/reader/ReaderErrorBoundary.jsx`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Write failing actionable-state tests**

```jsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import ReaderStatus from './ReaderStatus'

it('offers a retry without losing the passage reference', () => {
  const retry = vi.fn()
  render(<ReaderStatus state="error" reference="Genesis 1" onRetry={retry} onOpenBooks={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('Genesis 1')
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(retry).toHaveBeenCalledOnce()
})

it('labels an empty library and offers Books', () => {
  render(<ReaderStatus state="empty" reference="Genesis 1" onRetry={vi.fn()} onOpenBooks={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Choose another book' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the test and verify failure**

Run: `cd frontend && npm test -- --run src/reader/ReaderStatus.test.jsx`

Expected: FAIL because `ReaderStatus.jsx` does not exist.

- [ ] **Step 3: Implement explicit loading, empty, offline, and error copy**

```jsx
export default function ReaderStatus({ state, reference, onRetry, onOpenBooks }) {
  if (state === 'loading') return <div className="reader-status reader-status--loading" role="status">Loading {reference}…</div>
  if (state === 'empty') return (
    <section className="reader-status" aria-labelledby="reader-empty-title">
      <h2 id="reader-empty-title">No text is available for {reference}</h2>
      <p>Choose another book or translation to continue reading.</p>
      <button onClick={onOpenBooks}>Choose another book</button>
    </section>
  )
  if (state === 'offline') return (
    <div className="reader-status" role="status">
      <strong>You are offline.</strong> Loaded Scripture remains available, but online study tools may not work.
    </div>
  )
  if (state === 'error') return (
    <section className="reader-status" role="alert" aria-labelledby="reader-error-title">
      <h2 id="reader-error-title">We could not load {reference}</h2>
      <p>Your place is saved. Check the connection and try again.</p>
      <button onClick={onRetry}>Try again</button>
      <button onClick={onOpenBooks}>Choose another book</button>
    </section>
  )
  return null
}
```

- [ ] **Step 4: Implement a route-level error boundary**

```jsx
import { Component } from 'react'

export default class ReaderErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <section className="reader-fatal-error" role="alert">
        <h1>The Scripture Reader could not open</h1>
        <p>Your saved notes and reading preferences were not changed.</p>
        <button onClick={() => window.location.reload()}>Reload the reader</button>
        <a href="#home">Return home</a>
      </section>
    )
  }
}
```

- [ ] **Step 5: Run tests, lint, and commit**

Run: `cd frontend && npm test -- --run src/reader/ReaderStatus.test.jsx && npm run lint`

Expected: test PASS and lint exits 0.

```bash
git add frontend/src/reader/ReaderStatus.jsx frontend/src/reader/ReaderStatus.test.jsx frontend/src/reader/ReaderErrorBoundary.jsx frontend/src/reader/readerTokens.css
git commit -m "feat: add Scripture reader recovery states"
```

## Task 4: Accessible reader header and passage toolbar

**Files:**
- Create: `frontend/src/reader/ReaderHeader.jsx`
- Create: `frontend/src/reader/PassageToolbar.jsx`
- Create: `frontend/src/reader/ReaderChrome.test.jsx`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Write failing label and callback tests**

```jsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import ReaderHeader from './ReaderHeader'
import PassageToolbar from './PassageToolbar'

it('uses words for every primary reader action', () => {
  const openBooks = vi.fn()
  render(<ReaderHeader onHome={vi.fn()} onOpenBooks={openBooks} onOpenStudyTools={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Choose a book' }))
  expect(openBooks).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'Open study tools' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
})

it('provides labeled chapter, translation, and reading controls', () => {
  const changeTranslation = vi.fn()
  render(<PassageToolbar reference="Genesis 1" translation="KJV" translations={['KJV', 'ETH81']} onTranslationChange={changeTranslation} canGoPrevious={false} onPrevious={vi.fn()} onNext={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Previous chapter' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Next chapter' })).toBeEnabled()
  expect(screen.getByRole('button', { name: 'Change text size' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('combobox', { name: 'Change translation' }), { target: { value: 'ETH81' } })
  expect(changeTranslation).toHaveBeenCalledWith('ETH81')
})
```

- [ ] **Step 2: Run tests and verify missing components**

Run: `cd frontend && npm test -- --run src/reader/ReaderChrome.test.jsx`

Expected: FAIL because the chrome components do not exist.

- [ ] **Step 3: Implement the header**

```jsx
import { useState } from 'react'
import AccountMenu from '../auth/AccountMenu'
import AuthDialog from '../auth/AuthDialog'
import { useAuth } from '../auth/authContext'

export default function ReaderHeader({ onHome, onOpenBooks, onOpenStudyTools }) {
  const { user } = useAuth()
  const [authOpen, setAuthOpen] = useState(false)
  return (
    <header className="reader-header">
      <button className="reader-brand" onClick={onHome} aria-label="The Unbound Bible home">✦ <span>The Unbound Bible</span></button>
      <nav aria-label="Scripture reader actions">
        <button onClick={onOpenBooks}>Choose a book</button>
        <button className="reader-primary-action" onClick={onOpenStudyTools}>Open study tools</button>
        {user ? <AccountMenu /> : <button onClick={() => setAuthOpen(true)}>Sign in</button>}
      </nav>
      <AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} />
    </header>
  )
}
```

- [ ] **Step 4: Implement the toolbar using the preferences provider**

```jsx
import { useReaderPreferences } from './ReaderPreferences'

const sizes = ['sm', 'md', 'lg', 'xl', 'xxl']

export default function PassageToolbar({ reference, translation, translations, onTranslationChange, canGoPrevious, onPrevious, onNext }) {
  const { theme, setTheme, fontSize, setFontSize } = useReaderPreferences()
  const nextSize = sizes[(sizes.indexOf(fontSize) + 1) % sizes.length]
  return (
    <div className="passage-toolbar" aria-label="Passage controls">
      <button onClick={onPrevious} disabled={!canGoPrevious}>Previous chapter</button>
      <strong aria-live="polite">{reference}</strong>
      <label>Translation
        <select aria-label="Change translation" value={translation} onChange={(event) => onTranslationChange(event.target.value)}>
          {translations.map((code) => <option key={code} value={code}>{code}</option>)}
        </select>
      </label>
      <button onClick={() => setFontSize(nextSize)} aria-label="Change text size">Text size: {fontSize.toUpperCase()}</button>
      <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
        Use {theme === 'dark' ? 'light' : 'dark'} mode
      </button>
      <button onClick={onNext}>Next chapter</button>
    </div>
  )
}
```

- [ ] **Step 5: Add 48px control styling, run tests, and commit**

Add to `readerTokens.css`:

```css
.reader-header {
  min-height: 64px;
  padding: .5rem clamp(1rem, 3vw, 2rem);
  display: flex;
  align-items: center;
  gap: 1rem;
  background: var(--reader-surface);
  border-bottom: 1px solid var(--reader-border);
}
.reader-header nav { margin-left: auto; display: flex; align-items: center; gap: .75rem; }
.reader-header button, .passage-toolbar button, .passage-toolbar select {
  min-height: 48px;
  padding: .65rem .9rem;
  color: var(--reader-text);
  background: var(--reader-elevated);
  border: 1px solid var(--reader-border);
  border-radius: .7rem;
}
.reader-primary-action { background: var(--reader-primary) !important; color: #fff !important; }
.passage-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .75rem;
  padding: .65rem 1rem;
  background: color-mix(in srgb, var(--reader-surface) 94%, transparent);
  border-bottom: 1px solid var(--reader-border);
}
@media (max-width: 767px) {
  .reader-header { min-height: 56px; }
  .reader-brand span { display: none; }
  .passage-toolbar { justify-content: flex-start; overflow-x: auto; }
  .passage-toolbar > * { flex: 0 0 auto; }
}
```

Run: `cd frontend && npm test -- --run src/reader/ReaderChrome.test.jsx src/reader/ReaderPreferences.test.jsx && npm run lint`

Expected: selected tests PASS and lint exits 0.

```bash
git add frontend/src/reader/ReaderHeader.jsx frontend/src/reader/PassageToolbar.jsx frontend/src/reader/ReaderChrome.test.jsx frontend/src/reader/readerTokens.css
git commit -m "feat: add accessible Scripture reader controls"
```

## Task 5: Semantic Scripture pane and verse selection

**Files:**
- Create: `frontend/src/reader/ScripturePane.jsx`
- Create: `frontend/src/reader/ScripturePane.test.jsx`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Write failing reading and selection tests**

```jsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import ScripturePane from './ScripturePane'

const verses = [
  { book: 'Genesis', chapter: 1, verse: 1, text: 'In the beginning', translation: 'KJV' },
  { book: 'Genesis', chapter: 1, verse: 2, text: 'And the earth was without form', translation: 'KJV' }
]

it('renders a semantic chapter and keyboard-selectable verses', () => {
  const select = vi.fn()
  render(<ScripturePane book="Genesis" chapter={1} verses={verses} selectedVerse={null} onSelectVerse={select} />)
  expect(screen.getByRole('heading', { name: 'Genesis 1' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Genesis 1 verse 2' }))
  expect(select).toHaveBeenCalledWith(2)
})
```

- [ ] **Step 2: Run the test and verify missing component failure**

Run: `cd frontend && npm test -- --run src/reader/ScripturePane.test.jsx`

Expected: FAIL because `ScripturePane.jsx` does not exist.

- [ ] **Step 3: Implement one reading responsibility**

```jsx
export default function ScripturePane({ book, chapter, verses, selectedVerse, onSelectVerse }) {
  return (
    <article className="scripture-pane" aria-labelledby="scripture-chapter-title">
      <p className="scripture-eyebrow">Scripture Reader</p>
      <h1 id="scripture-chapter-title">{book} {chapter}</h1>
      <ol className="verse-list">
        {verses.map((verse) => (
          <li key={`${verse.translation}-${verse.verse}`}>
            <button
              className="verse"
              aria-label={`${book} ${chapter} verse ${verse.verse}`}
              aria-pressed={selectedVerse === verse.verse}
              onClick={() => onSelectVerse(verse.verse)}
            >
              <sup aria-hidden="true">{verse.verse}</sup>
              <span>{verse.text}</span>
            </button>
          </li>
        ))}
      </ol>
    </article>
  )
}
```

- [ ] **Step 4: Add reading measure, font-size mappings, and selected-state styles**

```css
.scripture-pane {
  width: min(100% - 2rem, 46rem);
  margin-inline: auto;
  padding: clamp(2rem, 5vw, 4.5rem) 0;
}
.reader-font-sm { --reader-font-size: 18px; }
.reader-font-md { --reader-font-size: 21px; }
.reader-font-lg { --reader-font-size: 24px; }
.reader-font-xl { --reader-font-size: 27px; }
.reader-font-xxl { --reader-font-size: 30px; }
.verse-list { list-style: none; padding: 0; }
.verse {
  width: 100%;
  min-height: 48px;
  padding: .45rem .65rem;
  border: 0;
  border-radius: .65rem;
  color: var(--reader-scripture);
  background: transparent;
  text-align: left;
  font-family: "Source Serif 4", Georgia, serif;
  font-size: var(--reader-font-size);
  line-height: 1.75;
}
.verse[aria-pressed='true'] { background: var(--reader-elevated); box-shadow: inset 3px 0 var(--reader-violet); }
```

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend && npm test -- --run src/reader/ScripturePane.test.jsx && npm run lint`

Expected: test PASS and lint exits 0.

```bash
git add frontend/src/reader/ScripturePane.jsx frontend/src/reader/ScripturePane.test.jsx frontend/src/reader/readerTokens.css
git commit -m "feat: add focused semantic Scripture pane"
```

## Task 6: Responsive Books picker

**Files:**
- Create: `frontend/src/reader/BookPicker.jsx`
- Create: `frontend/src/reader/BookPicker.test.jsx`
- Create: `frontend/src/reader/useDialogFocus.js`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Write failing picker tests**

```jsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import BookPicker from './BookPicker'

it('filters books, selects a chapter, and closes clearly', async () => {
  const choose = vi.fn()
  const close = vi.fn()
  const loadChapters = vi.fn().mockResolvedValue([1, 2, 3])
  render(<BookPicker open books={['Genesis', 'Exodus']} selectedCanon="PROT66" loadChapters={loadChapters} onCanonChange={vi.fn()} onChoose={choose} onClose={close} />)
  fireEvent.change(screen.getByRole('searchbox', { name: 'Search Bible books' }), { target: { value: 'exo' } })
  fireEvent.click(screen.getByRole('button', { name: 'Exodus' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Chapter 2' }))
  expect(choose).toHaveBeenCalledWith({ book: 'Exodus', chapter: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'Close book picker' }))
  expect(close).toHaveBeenCalledOnce()
})
```

- [ ] **Step 2: Run the test and verify failure**

Run: `cd frontend && npm test -- --run src/reader/BookPicker.test.jsx`

Expected: FAIL because `BookPicker.jsx` does not exist.

- [ ] **Step 3: Implement searchable two-step selection**

```jsx
import { useEffect, useRef, useState } from 'react'

export default function BookPicker({ open, books, selectedCanon, loadChapters, onCanonChange, onChoose, onClose }) {
  const [query, setQuery] = useState('')
  const [book, setBook] = useState(null)
  const [chapters, setChapters] = useState([])
  const [chaptersLoading, setChaptersLoading] = useState(false)
  const [chaptersError, setChaptersError] = useState('')
  const closeRef = useRef(null)
  useEffect(() => { if (open) closeRef.current?.focus() }, [open])
  useEffect(() => {
    const closeOnEscape = (event) => { if (open && event.key === 'Escape') onClose() }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [open, onClose])
  if (!open) return null
  const filtered = books.filter((name) => name.toLowerCase().includes(query.toLowerCase()))
  const chooseBook = async (name) => {
    setBook(name)
    setChaptersLoading(true)
    setChaptersError('')
    try { setChapters(await loadChapters(name)) }
    catch { setChaptersError(`We could not load chapters for ${name}.`) }
    finally { setChaptersLoading(false) }
  }
  return (
    <aside className="book-picker" role="dialog" aria-modal="true" aria-labelledby="book-picker-title">
      <header><h2 id="book-picker-title">Choose a book and chapter</h2><button ref={closeRef} onClick={onClose}>Close book picker</button></header>
      <label>Canon
        <select value={selectedCanon} onChange={(event) => onCanonChange(event.target.value)}>
          <option value="PROT66">Protestant</option>
          <option value="CATH73">Catholic</option>
          <option value="ETHIO81">Ethiopian Orthodox</option>
          <option value="BROADER">Broader canon and scholarly texts</option>
        </select>
      </label>
      <label>Search books<input type="search" aria-label="Search Bible books" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      {!book ? (
        <div className="book-grid">{filtered.map((name) => <button key={name} onClick={() => chooseBook(name)}>{name}</button>)}</div>
      ) : (
        <div className="chapter-grid" aria-label={`${book} chapters`}>
          {chaptersLoading && <p role="status">Loading {book} chapters…</p>}
          {chaptersError && <p role="alert">{chaptersError} <button onClick={() => chooseBook(book)}>Try again</button></p>}
          {chapters.map((chapter) => (
            <button key={chapter} onClick={() => onChoose({ book, chapter })}>Chapter {chapter}</button>
          ))}
        </div>
      )}
    </aside>
  )
}
```

- [ ] **Step 4: Share complete dialog focus behavior with Study Tools**

Create `useDialogFocus.js`:

```js
import { useEffect, useRef } from 'react'

const selector = 'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export default function useDialogFocus({ open, containerRef, initialRef, onClose }) {
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  useEffect(() => {
    if (!open) return undefined
    const opener = document.activeElement
    initialRef.current?.focus()
    const handleKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current(); return }
      if (event.key !== 'Tab') return
      const focusable = [...containerRef.current.querySelectorAll(selector)]
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', handleKey)
    return () => { document.removeEventListener('keydown', handleKey); opener?.focus() }
  }, [open, containerRef, initialRef])
}
```

Apply the hook in `BookPicker.jsx`:

```jsx
import { useRef, useState } from 'react'
import useDialogFocus from './useDialogFocus'

// Inside BookPicker:
const closeRef = useRef(null)
const containerRef = useRef(null)
useDialogFocus({ open, containerRef, initialRef: closeRef, onClose })

// On the existing dialog element:
<aside ref={containerRef} className="book-picker" role="dialog" aria-modal="true" aria-labelledby="book-picker-title">
```

Remove the component's separate Escape/focus effects. Extend the test to focus the opener before rendering, dismiss with Escape, and assert the opener regains focus.

- [ ] **Step 5: Add overlay/full-screen responsive CSS, run tests, and commit**

Add to `readerTokens.css`:

```css
.book-picker {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 100;
  width: min(30rem, 100vw);
  padding: 1.25rem;
  overflow-y: auto;
  color: var(--reader-text);
  background: var(--reader-surface);
  border-right: 1px solid var(--reader-border);
  box-shadow: 1.25rem 0 3rem rgb(0 0 0 / .3);
}
.book-picker header { display: flex; align-items: center; gap: 1rem; }
.book-picker header button { margin-left: auto; }
.book-picker input, .book-picker select { width: 100%; min-height: 48px; margin: .4rem 0 1rem; }
.book-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .65rem; }
.chapter-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .55rem; }
.book-grid button, .chapter-grid button { min-height: 48px; }
@media (max-width: 767px) {
  .book-picker { width: 100vw; border-right: 0; }
}
```

Run: `cd frontend && npm test -- --run src/reader/BookPicker.test.jsx && npm run lint`

Expected: test PASS and lint exits 0.

```bash
git add frontend/src/reader/BookPicker.jsx frontend/src/reader/BookPicker.test.jsx frontend/src/reader/useDialogFocus.js frontend/src/reader/readerTokens.css
git commit -m "feat: add responsive Scripture book picker"
```

## Task 7: Study Tools drawer/sheet and preserved destinations

**Files:**
- Create: `frontend/src/reader/studyToolRegistry.js`
- Create: `frontend/src/reader/StudyTools.jsx`
- Create: `frontend/src/reader/StudyTools.test.jsx`
- Modify: `frontend/src/reader/readerTokens.css`

- [ ] **Step 1: Write failing registry, focus, and routing tests**

```jsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import StudyTools from './StudyTools'

it('shows every existing study entry point with words', () => {
  const navigate = vi.fn()
  render(<StudyTools open reference={{ book: 'Genesis', chapter: 1, verse: 1 }} details={{ translations: { kjv: 'In the beginning' } }} onClose={vi.fn()} onNavigate={navigate} />)
  for (const name of ['Context', 'Compare translations', 'Original languages', 'Cross-references', 'Notes', 'Ask the Bible', 'Decolonial audit']) {
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  }
  fireEvent.click(screen.getByRole('button', { name: 'Ask the Bible' }))
  expect(navigate).toHaveBeenCalledWith('chat', { book: 'Genesis', chapter: 1, verse: 1 })
})

it('closes with Escape', () => {
  const close = vi.fn()
  render(<StudyTools open reference={{ book: 'Genesis', chapter: 1, verse: 1 }} details={{}} onClose={close} onNavigate={vi.fn()} />)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(close).toHaveBeenCalledOnce()
})
```

- [ ] **Step 2: Run the test and verify missing modules**

Run: `cd frontend && npm test -- --run src/reader/StudyTools.test.jsx`

Expected: FAIL because the study-tool modules do not exist.

- [ ] **Step 3: Define the registry once**

```js
export const STUDY_TOOLS = [
  { id: 'context', label: 'Context', kind: 'inline' },
  { id: 'compare', label: 'Compare translations', kind: 'inline' },
  { id: 'languages', label: 'Original languages', kind: 'inline' },
  { id: 'cross-references', label: 'Cross-references', kind: 'inline' },
  { id: 'notes', label: 'Notes', kind: 'route', page: 'notes' },
  { id: 'ask', label: 'Ask the Bible', kind: 'route', page: 'chat' },
  { id: 'audit', label: 'Decolonial audit', kind: 'route', page: 'race-misuse' }
]
```

- [ ] **Step 4: Implement the shared desktop/mobile study surface**

```jsx
import { useRef, useState } from 'react'
import { STUDY_TOOLS } from './studyToolRegistry'
import useDialogFocus from './useDialogFocus'

export default function StudyTools({ open, reference, details, onClose, onNavigate }) {
  const [active, setActive] = useState('context')
  const closeRef = useRef(null)
  const containerRef = useRef(null)
  const referenceLabel = reference.verse
    ? `${reference.book} ${reference.chapter}:${reference.verse}`
    : `${reference.book} ${reference.chapter}`
  useDialogFocus({ open, containerRef, initialRef: closeRef, onClose })
  if (!open) return null
  const choose = (tool) => tool.kind === 'route' ? onNavigate(tool.page, reference) : setActive(tool.id)
  const inlineContent = {
    context: details?.historical_context,
    compare: details?.translations,
    languages: details?.original_language_insights || details?.original_words,
    'cross-references': details?.cross_references
  }[active]
  return (
    <aside ref={containerRef} className="study-tools" role="dialog" aria-modal="true" aria-labelledby="study-tools-title">
      <header>
        <div><p>Study Tools</p><h2 id="study-tools-title">{referenceLabel}</h2></div>
        <button ref={closeRef} onClick={onClose}>Close study tools</button>
      </header>
      <nav aria-label="Study tool choices">
        {STUDY_TOOLS.map((tool) => <button key={tool.id} onClick={() => choose(tool)}>{tool.label}</button>)}
      </nav>
      <section aria-live="polite">
        {inlineContent && Object.keys(inlineContent).length
          ? <pre className="study-tool-content">{JSON.stringify(inlineContent, null, 2)}</pre>
          : <p>No verified {active.replace('-', ' ')} information is available for this verse.</p>}
      </section>
    </aside>
  )
}
```

Replace the temporary `<pre>` before committing with semantic lists/tables for each known API field:

```jsx
function DetailList({ value }) {
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={item.id || index}>{typeof item === 'string' ? item : item.text || item.reference || item.title}</li>)}</ul>
  if (value && typeof value === 'object') return <dl>{Object.entries(value).map(([term, text]) => <div key={term}><dt>{term.toUpperCase()}</dt><dd>{String(text)}</dd></div>)}</dl>
  return <p>No verified information is available for this verse.</p>
}
```

- [ ] **Step 5: Add right-drawer/bottom-sheet CSS, run tests, and commit**

Add to `readerTokens.css`:

```css
.study-tools {
  position: fixed;
  inset: 0 0 0 auto;
  z-index: 100;
  width: min(31rem, 100vw);
  padding: 1.25rem;
  overflow-y: auto;
  color: var(--reader-text);
  background: var(--reader-surface);
  border-left: 1px solid var(--reader-border);
  box-shadow: -1.25rem 0 3rem rgb(0 0 0 / .3);
}
.study-tools header { display: flex; align-items: flex-start; gap: 1rem; }
.study-tools header button { min-height: 48px; margin-left: auto; }
.study-tools nav { display: grid; gap: .55rem; margin: 1rem 0; }
.study-tools nav button { min-height: 48px; text-align: left; }
.study-tools dt { color: var(--reader-teal); font-weight: 700; }
.study-tools dd { margin: .25rem 0 1rem; }
@media (max-width: 767px) {
  .study-tools {
    inset: auto 0 0;
    width: 100vw;
    max-height: min(78vh, 44rem);
    border: 1px solid var(--reader-border);
    border-radius: 1rem 1rem 0 0;
    box-shadow: 0 -1.25rem 3rem rgb(0 0 0 / .35);
  }
}
```

Run: `cd frontend && npm test -- --run src/reader/StudyTools.test.jsx && npm run lint`

Expected: test PASS and lint exits 0.

```bash
git add frontend/src/reader/studyToolRegistry.js frontend/src/reader/StudyTools.jsx frontend/src/reader/StudyTools.test.jsx frontend/src/reader/readerTokens.css
git commit -m "feat: add progressive Scripture study tools"
```

## Task 8: Reader page orchestration and app integration

**Files:**
- Create: `frontend/src/reader/ReaderBottomNavigation.jsx`
- Create: `frontend/src/reader/ScriptureReaderPage.jsx`
- Create: `frontend/src/reader/ScriptureReaderPage.test.jsx`
- Modify: `frontend/src/App.jsx`
- Reference only: `frontend/src/components/AncientTexts.jsx`
- Reference only: `frontend/src/components/AncientTexts.css`

- [ ] **Step 1: Write the failing integrated reader flow**

```jsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import ScriptureReaderPage from './ScriptureReaderPage'
import { ReaderPreferencesProvider } from './ReaderPreferences'

vi.mock('./scriptureApi', () => ({
  getBooks: vi.fn().mockResolvedValue(['Genesis', 'Exodus']),
  getChapter: vi.fn().mockResolvedValue([{ book: 'Genesis', chapter: 1, verse: 1, text: 'In the beginning', translation: 'KJV' }]),
  getVerseDetails: vi.fn().mockResolvedValue({ translations: { kjv: 'In the beginning' }, historical_context: [] })
}))

it('loads Scripture first and opens study tools for the selected verse', async () => {
  render(<ReaderPreferencesProvider><ScriptureReaderPage onPageChange={vi.fn()} /></ReaderPreferencesProvider>)
  expect(screen.getByRole('status')).toHaveTextContent('Loading Genesis 1')
  expect(await screen.findByRole('heading', { name: 'Genesis 1' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Genesis 1 verse 1' }))
  fireEvent.click(screen.getByRole('button', { name: 'Open study tools' }))
  await waitFor(() => expect(screen.getByRole('dialog', { name: 'Genesis 1:1' })).toBeInTheDocument())
})
```

- [ ] **Step 2: Run the test and verify missing page failure**

Run: `cd frontend && npm test -- --run src/reader/ScriptureReaderPage.test.jsx`

Expected: FAIL because `ScriptureReaderPage.jsx` does not exist.

- [ ] **Step 3: Implement the labeled mobile bottom navigation**

```jsx
export default function ReaderBottomNavigation({ onNavigate, onBooks, onSearch }) {
  return (
    <nav className="reader-bottom-navigation" aria-label="Mobile reader navigation">
      <button onClick={() => onNavigate('home')}>Home</button>
      <button aria-current="page" onClick={onBooks}>Bible</button>
      <button onClick={onSearch}>Search</button>
      <button onClick={() => onNavigate('notes')}>Library</button>
      <button onClick={() => onNavigate('research')}>More</button>
    </nav>
  )
}
```

Add assertions to `ReaderChrome.test.jsx` that all five labels exist and each callback receives the expected destination.

Add to `readerTokens.css`:

```css
.reader-bottom-navigation { display: none; }
@media (max-width: 767px) {
  .scripture-reader { min-height: 100dvh; padding-bottom: calc(72px + env(safe-area-inset-bottom)); }
  .reader-bottom-navigation {
    position: fixed;
    inset: auto 0 0;
    z-index: 20;
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    padding: .4rem .35rem calc(.4rem + env(safe-area-inset-bottom));
    background: var(--reader-surface);
    border-top: 1px solid var(--reader-border);
  }
  .reader-bottom-navigation button { min-width: 0; min-height: 52px; color: var(--reader-text); background: transparent; border: 0; }
  .reader-bottom-navigation [aria-current='page'] { color: var(--reader-violet); font-weight: 700; }
}
```

- [ ] **Step 4: Implement page state and request lifecycle**

```jsx
import { useCallback, useEffect, useState } from 'react'
import BookPicker from './BookPicker'
import PassageToolbar from './PassageToolbar'
import ReaderBottomNavigation from './ReaderBottomNavigation'
import ReaderHeader from './ReaderHeader'
import ReaderStatus from './ReaderStatus'
import ScripturePane from './ScripturePane'
import StudyTools from './StudyTools'
import SearchDialog from '../search/SearchDialog'
import { useReaderPreferences } from './ReaderPreferences'
import { parseReaderHash, readerHash } from './readerRoute'
import { getBookChapters, getBooks, getChapter, getVerseDetails } from './scriptureApi'

export default function ScriptureReaderPage({ onPageChange }) {
  const [route, setRoute] = useState(parseReaderHash)
  const [books, setBooks] = useState([])
  const [verses, setVerses] = useState([])
  const [details, setDetails] = useState(null)
  const [status, setStatus] = useState('loading')
  const [booksOpen, setBooksOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const { fontSize } = useReaderPreferences()
  const translations = [...new Set(verses.map((row) => row.translation?.toUpperCase()).filter(Boolean))]
  const displayedVerses = verses.filter((row) => row.translation?.toUpperCase() === route.translation)
  const load = useCallback(() => {
    const controller = new AbortController()
    setStatus('loading')
    Promise.all([getBooks(route.canon, controller.signal), getChapter(route, controller.signal)])
      .then(([nextBooks, nextVerses]) => {
        setBooks(nextBooks)
        setVerses(nextVerses)
        const availableTranslations = [...new Set(nextVerses.map((row) => row.translation?.toUpperCase()).filter(Boolean))]
        if (availableTranslations.length && !availableTranslations.includes(route.translation)) {
          const nextRoute = { ...route, translation: availableTranslations[0], verse: null }
          window.location.hash = readerHash(nextRoute)
          setRoute(nextRoute)
        }
        setStatus(nextVerses.length ? 'ready' : 'empty')
      })
      .catch((error) => { if (error.name !== 'AbortError') setStatus(navigator.onLine ? 'error' : 'offline') })
    return () => controller.abort()
  }, [route])
  useEffect(load, [load])
  useEffect(() => {
    const handler = () => setRoute(parseReaderHash())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])
  useEffect(() => {
    if (!route.verse) { setDetails(null); return }
    const controller = new AbortController()
    getVerseDetails(route, controller.signal).then(setDetails).catch(() => setDetails(null))
    return () => controller.abort()
  }, [route])
  const navigate = (next) => { window.location.hash = readerHash(next); setRoute(next) }
  return (
    <div className={`scripture-reader reader-font-${fontSize}`}>
      <ReaderHeader onHome={() => onPageChange('home')} onOpenBooks={() => setBooksOpen(true)} onOpenStudyTools={() => setToolsOpen(true)} />
      <PassageToolbar
        reference={`${route.book} ${route.chapter}`}
        translation={route.translation}
        translations={translations.length ? translations : [route.translation]}
        onTranslationChange={(translation) => navigate({ ...route, translation, verse: null })}
        canGoPrevious={route.chapter > 1}
        onPrevious={() => navigate({ ...route, chapter: route.chapter - 1, verse: null })}
        onNext={() => navigate({ ...route, chapter: route.chapter + 1, verse: null })}
      />
      {status === 'ready'
        ? <ScripturePane book={route.book} chapter={route.chapter} verses={displayedVerses} selectedVerse={route.verse} onSelectVerse={(verse) => navigate({ ...route, verse })} />
        : <ReaderStatus state={status} reference={`${route.book} ${route.chapter}`} onRetry={load} onOpenBooks={() => setBooksOpen(true)} />}
      <BookPicker
        open={booksOpen}
        books={books}
        selectedCanon={route.canon}
        loadChapters={getBookChapters}
        onCanonChange={(canon) => navigate({ ...route, canon, book: 'Genesis', chapter: 1, verse: null })}
        onChoose={({ book, chapter }) => { navigate({ ...route, book, chapter, verse: null }); setBooksOpen(false) }}
        onClose={() => setBooksOpen(false)}
      />
      <StudyTools open={toolsOpen} reference={route} details={details} onClose={() => setToolsOpen(false)} onNavigate={onPageChange} />
      <ReaderBottomNavigation onNavigate={onPageChange} onBooks={() => setBooksOpen(true)} onSearch={() => setSearchOpen(true)} />
      <SearchDialog
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onNavigate={(url) => {
          setSearchOpen(false)
          if (url.startsWith('/#')) window.location.hash = url.slice(1)
          else window.location.assign(url)
        }}
      />
    </div>
  )
}
```

- [ ] **Step 5: Integrate with App behind the existing Scripture route**

```jsx
import ReaderErrorBoundary from './reader/ReaderErrorBoundary'
import { ReaderPreferencesProvider } from './reader/ReaderPreferences'

const ScriptureReaderPage = lazy(() => import('./reader/ScriptureReaderPage'))

// In the apocrypha route:
return (
  <ReaderErrorBoundary>
    <ReaderPreferencesProvider>
      <ScriptureReaderPage onPageChange={handlePageChange} />
    </ReaderPreferencesProvider>
  </ReaderErrorBoundary>
)
```

Keep `AncientTexts.jsx` and its stylesheet in source for one commit so comparisons are possible, but remove its import and active rendering from `App.jsx`.

- [ ] **Step 6: Run all component tests, build, and commit**

Run: `cd frontend && npm test -- --run && npm run lint && npm run build`

Expected: all tests PASS, lint exits 0, and Vite build succeeds.

```bash
git add frontend/src/reader frontend/src/App.jsx
git commit -m "feat: replace Scripture workspace with focused reader"
```

## Task 9: Responsive, accessibility, and regression verification

**Files:**
- Create: `frontend/e2e/scripture-reader-accessibility.spec.js`
- Modify: `frontend/playwright.config.js`
- Modify: `frontend/src/reader/readerTokens.css`
- Modify: `frontend/src/reader/ScriptureReaderPage.jsx`
- Modify: `frontend/src/reader/BookPicker.jsx`
- Modify: `frontend/src/reader/StudyTools.jsx`
- Modify: `frontend/src/reader/PassageToolbar.jsx`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1: Add browser tests that initially expose layout and interaction gaps**

```js
import { test, expect } from '@playwright/test'

test('reader is Scripture-first and has no horizontal overflow', async ({ page }) => {
  await page.goto('/#scriptures?book=Genesis&chapter=1&translation=KJV')
  await expect(page.getByRole('heading', { name: 'Genesis 1' })).toBeVisible()
  const dimensions = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth
  }))
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1)
  await expect(page.getByRole('button', { name: 'Choose a book' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open study tools' })).toBeVisible()
})

test('reader preferences persist', async ({ page }) => {
  await page.goto('/#scriptures?book=Genesis&chapter=1&translation=KJV')
  await page.getByRole('button', { name: 'Change text size' }).click()
  await page.getByRole('button', { name: 'Use light mode' }).click()
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-reader-theme', 'light')
  await expect(page.locator('.scripture-reader')).toHaveClass(/reader-font-lg/)
})

test('book picker and study tools are keyboard dismissible', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name.includes('mobile'), 'Hardware Tab behavior is checked in desktop Chromium')
  await page.goto('/#scriptures?book=Genesis&chapter=1&translation=KJV')
  await page.getByRole('button', { name: 'Choose a book' }).click()
  await expect(page.getByRole('dialog', { name: 'Choose a book and chapter' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'Choose a book and chapter' })).toBeHidden()
})
```

- [ ] **Step 2: Add explicit 320px and 390px projects**

```js
{
  name: 'mobile-390',
  use: { ...devices['iPhone 13'], viewport: { width: 390, height: 844 } }
},
{
  name: 'mobile-320',
  use: { ...devices['iPhone SE'], viewport: { width: 320, height: 568 } }
}
```

- [ ] **Step 3: Add automated axe checks**

Run: `cd frontend && npm install --save-dev @axe-core/playwright`

Expected: installation completes and `npm audit --audit-level=high` reports zero high-severity findings.

Add to the reader Playwright spec:

```js
import AxeBuilder from '@axe-core/playwright'

test('reader has no automatically detectable WCAG A or AA violations', async ({ page }) => {
  await page.goto('/#scriptures?book=Genesis&chapter=1&translation=KJV')
  await expect(page.getByRole('heading', { name: 'Genesis 1' })).toBeVisible()
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  expect(results.violations).toEqual([])
})
```

- [ ] **Step 4: Run the complete verification matrix and fix only evidenced failures**

Run:

```bash
cd frontend
npm test -- --run
npm run lint
npm run build
npx playwright test e2e/scripture-reader-accessibility.spec.js
```

Expected:

- All Vitest files pass.
- ESLint exits 0.
- Vite production build succeeds.
- Desktop, tablet, 390px, and 320px reader journeys pass.
- No horizontal overflow.
- No overlapping panels.
- No browser console errors.

- [ ] **Step 5: Perform the manual age-range usability checklist**

At 1440px, 390px, 200% browser zoom, light mode, and dark mode, verify:

```text
[ ] A first-time user can choose Genesis 1 without guessing an icon.
[ ] Scripture is visible before dashboards or AI output.
[ ] Every primary control has a word label.
[ ] Text size can be increased without clipping or horizontal scrolling.
[ ] Books and Study Tools close with a visible button and Escape.
[ ] Focus is visible and restored to the opener.
[ ] Offline/error states preserve the selected passage and offer a next action.
[ ] Context, comparison, language, notes, Ask, and audit remain reachable.
```

- [ ] **Step 6: Remove the inactive legacy reader only after parity is proven**

Run: `rg -n "AncientTexts" frontend/src`

Expected before deletion: only the inactive component file/import references that are no longer used. Delete `frontend/src/components/AncientTexts.jsx` and `frontend/src/components/AncientTexts.css` only if no production route imports them and every parity item above passes. Otherwise keep them unreferenced and record the remaining extraction as a follow-up issue rather than deleting working code.

- [ ] **Step 7: Run final verification and commit**

Run: `cd frontend && npm test -- --run && npm run lint && npm run build && npx playwright test`

Expected: all unit, integration, build, and applicable browser checks pass.

```bash
git add frontend/src/reader frontend/src/App.jsx frontend/src/routing frontend/e2e/scripture-reader-accessibility.spec.js frontend/playwright.config.js frontend/package.json frontend/package-lock.json frontend/src/components/AncientTexts.jsx frontend/src/components/AncientTexts.css
git commit -m "test: verify accessible Scripture reader redesign"
```

## Final handoff checklist

- [ ] Confirm `git status --short` contains no accidentally staged databases, logs, caches, ingestion scripts, or unrelated pre-existing work.
- [ ] Confirm the new reader commits do not include `.superpowers/` mockup artifacts.
- [ ] Record exact Vitest, lint, build, Playwright, and accessibility results in the final handoff.
- [ ] Open `/#scriptures?book=Genesis&chapter=1&translation=KJV` in the browser and verify the final screenshot at desktop and 390px.
- [ ] Only after the Scripture Reader is accepted, create a separate spec and plan for applying the design system to the rest of the app.
