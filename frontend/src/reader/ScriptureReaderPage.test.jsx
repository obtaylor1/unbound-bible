import { readFileSync } from 'node:fs'
import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/authContext'
import App, { ReaderLoadingFallback } from '../App'
import { ReaderPreferencesProvider } from './ReaderPreferences'
import ReaderBottomNavigation from './ReaderBottomNavigation'
import ScriptureReaderPage from './ScriptureReaderPage'
import {
  getBookChapters,
  getBookCatalog,
  getChapter,
  getVerseDetails,
} from './scriptureApi'

vi.mock('./scriptureApi', () => ({
  getBookCatalog: vi.fn(),
  getChapter: vi.fn(),
  getBookChapters: vi.fn(),
  getVerseDetails: vi.fn(),
}))

function MockSearchDialog({ open, onClose, onNavigate }) {
  return open ? (
    <div role="dialog" aria-label="Search">
      <button type="button" onClick={() => onNavigate('/#scriptures?book=Exodus&chapter=3&verse=2')}>
        Open Scripture result
      </button>
      <button type="button" onClick={() => onNavigate('/#library')}>
        Open library result
      </button>
      <button type="button" onClick={() => onNavigate('/share/public-study')}>
        Open shared study
      </button>
      <button type="button" onClick={() => onNavigate('/share/public-study#section')}>
        Open shared section
      </button>
      <button type="button" onClick={() => onNavigate('javascript:alert(1)')}>
        Open unsafe result
      </button>
      <button type="button" onClick={() => onNavigate('https://example.org/#library')}>
        Open external result
      </button>
      <button type="button" onClick={() => onNavigate('/#not-a-page')}>
        Open unknown result
      </button>
      <button type="button" onClick={() => onNavigate('http://[invalid')}>
        Open invalid result
      </button>
      <button type="button" onClick={onClose}>Close search</button>
    </div>
  ) : null
}

const rows = [
  { id: 1, verse: 1, translation: 'KJV', text: 'In the beginning.' },
  { id: 2, verse: 2, translation: 'KJV', text: 'The earth was without form.' },
  { id: 3, verse: 1, translation: 'WEB', text: 'At first.' },
]
const readerCss = readFileSync('src/reader/readerTokens.css', 'utf8')

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function renderReader(props = {}) {
  return render(
    <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
      <ReaderPreferencesProvider>
        <ScriptureReaderPage {...props} />
      </ReaderPreferencesProvider>
    </AuthContext.Provider>,
  )
}

function renderStrictReader(props = {}) {
  return render(
    <StrictMode>
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <ReaderPreferencesProvider>
          <ScriptureReaderPage {...props} />
        </ReaderPreferencesProvider>
      </AuthContext.Provider>
    </StrictMode>,
  )
}

beforeEach(() => {
  window.location.hash = '#scriptures?book=Genesis&chapter=1&translation=KJV&canon=ETHIO81'
  window.localStorage.clear()
  getBookCatalog.mockResolvedValue(['Genesis', 'Exodus'])
  getBookChapters.mockResolvedValue([1, 3])
  getChapter.mockResolvedValue(rows)
  getVerseDetails.mockResolvedValue({
    book: 'Genesis',
    chapter: 1,
    verse: 1,
    historical_context: 'Creation setting',
  })
})

afterEach(() => {
  vi.clearAllMocks()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('ReaderBottomNavigation', () => {
  it('uses word labels and routes each available action', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    const onSearch = vi.fn()
    const onOpenBooks = vi.fn()
    render(
      <ReaderBottomNavigation
        onNavigate={onNavigate}
        onSearch={onSearch}
        onOpenBooks={onOpenBooks}
      />,
    )

    const nav = screen.getByRole('navigation', { hidden: true })
    expect(nav).toHaveAttribute('aria-label', 'Mobile reader navigation')
    expect(within(nav).getByRole('button', { name: 'Bible', hidden: true })).toHaveAttribute('aria-current', 'page')
    for (const label of ['Home', 'Bible', 'Search', 'Library', 'More']) {
      expect(within(nav).getByRole('button', { name: label, hidden: true })).toBeInTheDocument()
    }

    await user.click(within(nav).getByRole('button', { name: 'Home', hidden: true }))
    await user.click(within(nav).getByRole('button', { name: 'Bible', hidden: true }))
    await user.click(within(nav).getByRole('button', { name: 'Search', hidden: true }))
    await user.click(within(nav).getByRole('button', { name: 'Library', hidden: true }))
    await user.click(within(nav).getByRole('button', { name: 'More', hidden: true }))

    expect(onNavigate).toHaveBeenNthCalledWith(1, 'home')
    expect(onNavigate).toHaveBeenNthCalledWith(2, 'notes')
    expect(onNavigate).toHaveBeenNthCalledWith(3, 'research')
    expect(onOpenBooks).toHaveBeenCalledOnce()
    expect(onSearch).toHaveBeenCalledOnce()
  })

  it('disables unavailable actions without throwing', () => {
    render(<ReaderBottomNavigation />)
    for (const button of screen.getAllByRole('button', { hidden: true })) expect(button).toBeDisabled()
  })

  it('is a safe-area-aware fixed mobile bar below reader dialogs', () => {
    expect(readerCss).toMatch(/@media \(max-width: 767px\)[\s\S]*\.reader-bottom-navigation\s*\{[\s\S]*position:\s*fixed/)
    expect(readerCss).toMatch(/\.reader-bottom-navigation\s*\{[^}]*grid-template-columns:\s*repeat\(5,\s*minmax\(0,\s*1fr\)\)/)
    expect(readerCss).toMatch(/\.reader-bottom-navigation button\s*\{[^}]*min-height:\s*52px/)
    expect(readerCss).toMatch(/\.reader-bottom-navigation button\[aria-current='page'\]\s*\{[^}]*text-decoration:\s*underline/)
    expect(readerCss).toContain('env(safe-area-inset-bottom)')
  })
})

describe('ScriptureReaderPage', () => {
  it('moves from loading to the selected translation and applies preferences', async () => {
    const chapter = deferred()
    getChapter.mockReturnValue(chapter.promise)
    window.localStorage.setItem('unbound.reader.preferences', JSON.stringify({
      theme: 'dark',
      fontSize: 'lg',
      readingWidth: 'wide',
    }))
    renderReader()

    expect(screen.getByRole('status')).toHaveTextContent('Loading Genesis 1')
    chapter.resolve(rows)
    expect(await screen.findByRole('heading', { level: 1, name: 'Genesis 1' })).toBeInTheDocument()
    expect(screen.getByText('In the beginning.')).toBeInTheDocument()
    expect(screen.queryByText('At first.')).not.toBeInTheDocument()
    expect(screen.getByTestId('scripture-reader')).toHaveClass('reader-font-lg', 'reader-width-wide')
  })

  it('falls back to the first available translation and keeps the route shareable', async () => {
    window.location.hash = '#scriptures?book=Genesis&chapter=1&translation=NRSV&canon=ETHIO81'
    renderReader()

    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
    await waitFor(() => expect(window.location.hash).toContain('translation=KJV'))
    expect(getChapter).toHaveBeenCalledTimes(1)
  })

  it('selects a verse in the hash without refetching the chapter', async () => {
    renderReader()
    await screen.findByText('In the beginning.')
    fireEvent.click(screen.getByRole('button', { name: /Genesis 1 verse 2/ }))

    expect(window.location.hash).toContain('verse=2')
    expect(getChapter).toHaveBeenCalledTimes(1)
  })

  it('keeps navigation state updates pure under StrictMode', async () => {
    renderStrictReader()
    await screen.findByText('In the beginning.')
    getChapter.mockClear()
    const hashChanges = vi.fn()
    window.addEventListener('hashchange', hashChanges)

    fireEvent.click(screen.getByRole('button', { name: /Genesis 1 verse 2/ }))

    expect(window.location.hash).toContain('verse=2')
    await waitFor(() => expect(hashChanges).toHaveBeenCalledTimes(1))
    expect(getChapter).not.toHaveBeenCalled()
    window.removeEventListener('hashchange', hashChanges)
  })

  it('reacts to browser hash navigation and ignores stale chapter results', async () => {
    const genesis = deferred()
    const exodus = deferred()
    getChapter
      .mockReturnValueOnce(genesis.promise)
      .mockReturnValueOnce(exodus.promise)
    renderReader()
    await waitFor(() => expect(getChapter).toHaveBeenCalledTimes(1))

    window.location.hash = '#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    exodus.resolve([{ verse: 1, translation: 'KJV', text: 'Exodus current.' }])
    expect(await screen.findByText('Exodus current.')).toBeInTheDocument()

    genesis.resolve([{ verse: 1, translation: 'KJV', text: 'Genesis stale.' }])
    await Promise.resolve()
    expect(screen.queryByText('Genesis stale.')).not.toBeInTheDocument()
  })

  it('ignores stale books and chapter-number metadata after hash back/forward navigation', async () => {
    const firstBooks = deferred()
    const currentBooks = deferred()
    const currentChapters = deferred()
    getBookCatalog
      .mockReturnValueOnce(firstBooks.promise)
      .mockReturnValueOnce(currentBooks.promise)
      .mockResolvedValue(['Exodus'])
    getBookChapters
      .mockReturnValueOnce(currentChapters.promise)
    getChapter.mockImplementation(({ book }) => Promise.resolve([
      { verse: 1, translation: 'KJV', text: `${book} current.` },
    ]))
    renderReader()

    window.location.hash = '#scriptures?book=Exodus&chapter=2&translation=KJV&canon=CATH73'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    currentBooks.resolve(['Exodus'])
    currentChapters.resolve([2, 4])
    expect(await screen.findByText('Exodus current.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Next chapter' })).toBeEnabled())

    firstBooks.resolve(['Genesis'])
    await Promise.resolve()
    fireEvent.click(screen.getByRole('button', { name: 'Choose a book' }))
    expect(screen.getByRole('button', { name: 'Exodus' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Genesis' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close book picker' }))
    fireEvent.click(screen.getByRole('button', { name: 'Next chapter' }))
    expect(window.location.hash).toContain('chapter=4')
  })

  it('uses actual adjacent chapters and disables chapter boundaries', async () => {
    renderReader()
    await screen.findByText('In the beginning.')
    expect(screen.getByRole('button', { name: 'Previous chapter' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Next chapter' }))
    expect(window.location.hash).toContain('chapter=3')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Next chapter' })).toBeDisabled())
  })

  it('shows empty, error, offline, and retry states truthfully', async () => {
    getChapter.mockResolvedValueOnce([])
    const { unmount } = renderReader()
    expect(await screen.findByRole('heading', { name: 'No text available' })).toBeInTheDocument()
    unmount()

    getChapter.mockRejectedValueOnce(new Error('broken')).mockResolvedValueOnce(rows)
    renderReader()
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not open Genesis 1')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
  })

  it('labels network failures offline', async () => {
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    getChapter.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    renderReader()
    expect(await screen.findByRole('heading', { name: 'Scripture unavailable offline' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('preserves an established empty passage across offline and online events', async () => {
    getChapter.mockResolvedValueOnce([])
    renderReader()
    expect(await screen.findByRole('heading', {
      name: 'No text available',
    })).toBeInTheDocument()

    fireEvent(window, new Event('offline'))
    expect(screen.getByRole('heading', { name: 'No text available' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', {
      name: 'Scripture unavailable offline',
    })).not.toBeInTheDocument()

    fireEvent(window, new Event('online'))
    expect(screen.getByRole('heading', { name: 'No text available' })).toBeInTheDocument()
    expect(getChapter).toHaveBeenCalledTimes(1)
  })

  it('preserves only the current loaded passage under a compact offline recovery banner', async () => {
    const user = userEvent.setup()
    renderReader()
    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()

    window.dispatchEvent(new Event('offline'))
    expect(await screen.findByRole('heading', { level: 2, name: 'You’re offline' })).toBeInTheDocument()
    expect(screen.getByText('In the beginning.')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)

    getChapter.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('never preserves loaded text after the passage route changes', async () => {
    renderReader()
    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
    getChapter.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    window.location.hash = '#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81'
    window.dispatchEvent(new HashChangeEvent('hashchange'))

    expect(await screen.findByRole('heading', {
      name: 'Scripture unavailable offline',
    })).toBeInTheDocument()
    expect(screen.queryByText('In the beginning.')).not.toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('does not expose translations or verses owned by a previous route', async () => {
    const exodus = deferred()
    renderReader()
    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
    getChapter.mockReturnValueOnce(exodus.promise)

    window.location.hash = '#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81'
    window.dispatchEvent(new HashChangeEvent('hashchange'))

    await waitFor(() => expect(screen.queryByText('In the beginning.')).not.toBeInTheDocument())
    expect(screen.getByLabelText('Change translation')).toHaveTextContent('No translations available')
    expect(screen.getByLabelText('Change translation')).not.toHaveTextContent('WEB')

    exodus.reject(new Error('broken'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not open Exodus 3')
    expect(screen.getByLabelText('Change translation')).toHaveTextContent('No translations available')
  })

  it('supports picker canon and chapter choice flows', async () => {
    const user = userEvent.setup()
    getBookCatalog.mockImplementation((canon) => Promise.resolve(
      canon === 'CATH73' ? ['Tobit'] : ['Genesis', 'Exodus'],
    ))
    renderReader()
    await screen.findByText('In the beginning.')
    await user.click(screen.getByRole('button', { name: 'Choose a book' }))
    const picker = screen.getByRole('dialog', { name: 'Choose a book and chapter' })
    await user.selectOptions(within(picker).getByLabelText('Canon'), 'CATH73')
    await waitFor(() => expect(window.location.hash).toContain('book=Tobit'))
    expect(window.location.hash).toContain('canon=CATH73')

    await user.click(within(picker).getByRole('button', { name: 'Tobit' }))
    await user.click(await within(picker).findByRole('button', { name: 'Chapter 1' }))
    expect(screen.queryByRole('dialog', { name: 'Choose a book and chapter' })).not.toBeInTheDocument()
  })

  it('atomically swaps canon catalogs before validating or fetching a passage', async () => {
    const catholicBooks = deferred()
    getBookCatalog.mockImplementation((canon) => (
      canon === 'CATH73' ? catholicBooks.promise : Promise.resolve(['Genesis', 'Exodus'])
    ))
    renderReader()
    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
    getBookChapters.mockClear()
    getChapter.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Choose a book' }))
    const picker = screen.getByRole('dialog', { name: 'Choose a book and chapter' })
    fireEvent.change(within(picker).getByLabelText('Canon'), { target: { value: 'CATH73' } })

    expect(within(picker).queryByRole('button', { name: 'Genesis' })).not.toBeInTheDocument()
    expect(within(picker).getByRole('status')).toHaveTextContent(/loading bible books/i)
    expect(getBookChapters).not.toHaveBeenCalled()
    expect(getChapter).not.toHaveBeenCalled()

    catholicBooks.resolve(['Tobit'])
    await waitFor(() => expect(window.location.hash).toContain('book=Tobit'))
    await waitFor(() => expect(getBookChapters).toHaveBeenCalledTimes(1))
    expect(getBookChapters).toHaveBeenCalledWith('Tobit', expect.any(AbortSignal))
    expect(getChapter).toHaveBeenCalledTimes(1)
    expect(getChapter).toHaveBeenCalledWith(
      expect.objectContaining({ book: 'Tobit', chapter: 1 }),
      expect.any(AbortSignal),
    )
  })

  it('shows recoverable books and chapter-navigation metadata failures', async () => {
    const user = userEvent.setup()
    getBookCatalog.mockRejectedValueOnce(new Error('books down')).mockResolvedValueOnce(['Genesis'])
    getBookChapters.mockRejectedValueOnce(new Error('chapters down')).mockResolvedValueOnce([1, 3])
    renderReader()

    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
    expect(window.location.hash).toContain('book=Genesis')
    expect(screen.getByRole('status', { name: 'Chapter navigation unavailable' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous chapter' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next chapter' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Choose a book' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Bible books could not load')
    await user.click(screen.getByRole('button', { name: 'Try loading books again' }))
    expect(await screen.findByRole('button', { name: 'Genesis' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Chapter navigation unavailable' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try chapter navigation again' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Next chapter' })).toBeEnabled())
  })

  it('preserves the passage while retrying its failed canon catalog', async () => {
    const user = userEvent.setup()
    const retryBooks = deferred()
    getBookCatalog
      .mockRejectedValueOnce(new Error('books down'))
      .mockReturnValueOnce(retryBooks.promise)
    renderReader()

    expect(await screen.findByText('In the beginning.')).toBeInTheDocument()
    expect(getChapter).toHaveBeenCalledTimes(1)
    expect(getBookChapters).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: 'Choose a book' }))
    await user.click(screen.getByRole('button', { name: 'Try loading books again' }))
    const picker = screen.getByRole('dialog', { name: 'Choose a book and chapter' })
    expect(within(picker).getByRole('status')).toHaveTextContent(/loading bible books/i)
    await user.click(screen.getByRole('button', { name: 'Close book picker' }))

    expect(screen.getByText('In the beginning.')).toBeInTheDocument()
    expect(getChapter).toHaveBeenCalledTimes(1)
    expect(getBookChapters).toHaveBeenCalledTimes(1)

    retryBooks.resolve(['Tobit'])
    await waitFor(() => expect(window.location.hash).toContain('book=Tobit'))
    await waitFor(() => expect(getChapter).toHaveBeenCalledTimes(2))
    expect(getChapter).toHaveBeenLastCalledWith(
      expect.objectContaining({ book: 'Tobit', chapter: 1 }),
      expect.any(AbortSignal),
    )
    expect(getBookChapters).toHaveBeenCalledTimes(2)
    expect(getBookChapters).toHaveBeenLastCalledWith('Tobit', expect.any(AbortSignal))
  })

  it('owns verse detail requests by reference and increments revisions', async () => {
    const first = deferred()
    const second = deferred()
    getVerseDetails.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    renderReader()
    await screen.findByText('In the beginning.')
    fireEvent.click(screen.getByRole('button', { name: /Genesis 1 verse 1/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Open study tools' }))
    expect(screen.getByRole('dialog', { name: 'Genesis 1:1' })).toHaveTextContent(/loading/i)

    fireEvent.click(screen.getByRole('button', { name: 'Close study tools' }))
    fireEvent.click(screen.getByRole('button', { name: /Genesis 1 verse 2/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Open study tools' }))
    second.resolve({
      book: 'Genesis', chapter: 1, verse: 2, historical_context: 'Current detail',
    })
    expect(await screen.findByText('Current detail')).toBeInTheDocument()
    first.resolve({
      book: 'Genesis', chapter: 1, verse: 1, historical_context: 'Stale detail',
    })
    await Promise.resolve()
    expect(screen.queryByText('Stale detail')).not.toBeInTheDocument()
  })

  it('routes study tools and bottom search through existing app navigation', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    renderReader({ onPageChange, SearchComponent: MockSearchDialog })
    await screen.findByText('In the beginning.')
    await user.click(screen.getByRole('button', { name: 'Open study tools' }))
    await user.click(screen.getByRole('button', { name: 'Add or view notes' }))
    expect(onPageChange).toHaveBeenCalledWith('notes', {
      book: 'Genesis', chapter: 1,
    })
    expect(screen.queryByRole('dialog', { name: 'Genesis 1' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    expect(screen.getByRole('dialog', { name: 'Search' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open Scripture result' }))
    expect(window.location.hash).toContain('book=Exodus&chapter=3')
    expect(window.location.hash).toContain('verse=2')
    expect(screen.queryByRole('dialog', { name: 'Search' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    await user.click(screen.getByRole('button', { name: 'Open library result' }))
    expect(onPageChange).toHaveBeenLastCalledWith('notes')
    expect(screen.queryByRole('dialog', { name: 'Search' })).not.toBeInTheDocument()
  })

  it('performs a real document navigation for non-hash search results', async () => {
    const user = userEvent.setup()
    const navigateDocument = vi.fn()
    renderReader({ navigateDocument, SearchComponent: MockSearchDialog })
    await screen.findByText('In the beginning.')

    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    await user.click(screen.getByRole('button', { name: 'Open shared study' }))

    expect(navigateDocument).toHaveBeenCalledWith(
      new URL('/share/public-study', window.location.href).href,
    )
  })

  it('only accepts safe same-origin search result navigation', async () => {
    const user = userEvent.setup()
    const navigateDocument = vi.fn()
    const onPageChange = vi.fn()
    renderReader({ navigateDocument, onPageChange, SearchComponent: MockSearchDialog })
    await screen.findByText('In the beginning.')

    for (const label of [
      'Open unsafe result',
      'Open external result',
      'Open unknown result',
      'Open invalid result',
    ]) {
      await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
      await user.click(screen.getByRole('button', { name: label }))
    }
    expect(navigateDocument).not.toHaveBeenCalled()
    expect(onPageChange).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    await user.click(screen.getByRole('button', { name: 'Open shared section' }))
    expect(navigateDocument).toHaveBeenCalledWith(
      new URL('/share/public-study#section', window.location.href).href,
    )
  })

  it('does not expose a reader route in the URL before React commits it', async () => {
    let hashInsideHandler
    function CommitObserverSearch({ open, onNavigate }) {
      return open ? (
        <button
          type="button"
          onClick={() => {
            onNavigate('/#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81')
            hashInsideHandler = window.location.hash
          }}
        >
          Observe Scripture navigation
        </button>
      ) : null
    }
    renderReader({ SearchComponent: CommitObserverSearch })
    await screen.findByText('In the beginning.')
    const oldHash = window.location.hash

    fireEvent.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    fireEvent.click(screen.getByRole('button', { name: 'Observe Scripture navigation' }))

    expect(hashInsideHandler).toBe(oldHash)
    await waitFor(() => expect(window.location.hash).toContain('book=Exodus'))
  })

  it('integrates the real accessible search dialog', async () => {
    const user = userEvent.setup()
    renderReader()
    await screen.findByText('In the beginning.')
    const opener = screen.getByRole('button', { name: 'Search', hidden: true })
    await user.click(opener)

    const input = screen.getByRole('combobox', { name: 'Search the library' })
    expect(input).toHaveFocus()
    expect(document.body).toHaveStyle({ overflow: 'hidden' })
    await user.keyboard('{Escape}')
    expect(opener).toHaveFocus()
  })

  it('does not refetch a chapter when tools open and keeps overlays mutually exclusive', async () => {
    const user = userEvent.setup()
    renderReader({ SearchComponent: MockSearchDialog })
    await screen.findByText('In the beginning.')
    await user.click(screen.getByRole('button', { name: 'Choose a book' }))
    expect(screen.getByRole('dialog', { name: 'Choose a book and chapter' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    expect(screen.queryByRole('dialog', { name: 'Choose a book and chapter' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Search' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close search' }))
    await user.click(screen.getByRole('button', { name: 'Open study tools' }))
    expect(getChapter).toHaveBeenCalledTimes(1)
  })

  it('reuses resolved chapter metadata when the picker opens the current book', async () => {
    const user = userEvent.setup()
    renderReader()
    await screen.findByText('In the beginning.')
    await waitFor(() => expect(getBookChapters).toHaveBeenCalledTimes(1))

    await user.click(screen.getByRole('button', { name: 'Choose a book' }))
    await user.click(screen.getByRole('button', { name: 'Genesis' }))

    expect(await screen.findByRole('button', { name: 'Chapter 1' })).toBeVisible()
    expect(getBookChapters).toHaveBeenCalledTimes(1)
  })

  it('aborts requests and removes its hash listener on unmount', async () => {
    const chapterSignals = []
    const booksSignals = []
    const chapterNumberSignals = []
    getBookCatalog.mockImplementation((_, signal) => {
      booksSignals.push(signal)
      return Promise.resolve(['Genesis'])
    })
    getBookChapters.mockImplementation((_, signal) => {
      chapterNumberSignals.push(signal)
      return new Promise(() => {})
    })
    getChapter.mockImplementation((_, signal) => {
      chapterSignals.push(signal)
      return new Promise(() => {})
    })
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const { unmount } = renderReader()
    await waitFor(() => {
      expect(chapterSignals).toHaveLength(1)
      expect(chapterNumberSignals).toHaveLength(1)
    })
    unmount()

    expect(chapterSignals[0].aborted).toBe(true)
    expect(booksSignals[0].aborted).toBe(true)
    expect(chapterNumberSignals[0].aborted).toBe(true)
    expect(removeSpy).toHaveBeenCalledWith('hashchange', expect.any(Function))
  })

  it('aborts detail and picker chapter requests when overlays change or the page unmounts', async () => {
    const user = userEvent.setup()
    const detailSignals = []
    const pickerSignals = []
    getVerseDetails.mockImplementation((_, signal) => {
      detailSignals.push(signal)
      return new Promise(() => {})
    })
    getBookChapters.mockImplementation((_, signal) => {
      if (getBookChapters.mock.calls.length > 1) pickerSignals.push(signal)
      return getBookChapters.mock.calls.length === 1
        ? Promise.resolve([1, 3])
        : new Promise(() => {})
    })
    const { unmount } = renderReader()
    await screen.findByText('In the beginning.')
    await user.click(screen.getByRole('button', { name: /Genesis 1 verse 1/ }))
    await user.click(screen.getByRole('button', { name: 'Open study tools' }))
    await waitFor(() => expect(detailSignals).toHaveLength(1))

    await user.click(screen.getByRole('button', { name: 'Choose a book' }))
    expect(detailSignals[0].aborted).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Exodus' }))
    await waitFor(() => expect(pickerSignals).toHaveLength(1))
    unmount()
    expect(pickerSignals[0].aborted).toBe(true)
  })

  it('is lazy-integrated in App without the legacy workspace or nested main landmarks', async () => {
    render(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <App />
      </AuthContext.Provider>,
    )

    expect(await screen.findByTestId('scripture-reader')).toBeInTheDocument()
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(document.querySelector('.ancient-texts')).not.toBeInTheDocument()
  })

  it('preserves the selected verse when App opens the note destination', async () => {
    const user = userEvent.setup()
    render(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <App />
      </AuthContext.Provider>,
    )

    await screen.findByText('The earth was without form.')
    await user.click(screen.getByRole('button', { name: /Genesis 1 verse 2/ }))
    await user.click(screen.getByRole('button', { name: 'Open study tools' }))
    await user.click(screen.getByRole('button', { name: 'Add or view notes' }))

    expect(await screen.findByRole('heading', { name: 'Add a note for Genesis 1:2' })).toBeVisible()
  })

  it('focuses the reader main from its skip link without destroying the shareable route', async () => {
    const user = userEvent.setup()
    render(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <App />
      </AuthContext.Provider>,
    )
    await screen.findByTestId('scripture-reader')
    const originalHash = window.location.hash

    await user.click(screen.getByRole('link', { name: 'Skip to main content' }))

    expect(await screen.findByTestId('scripture-reader')).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(screen.getByRole('main')).toHaveFocus()
    expect(window.location.hash).toBe(originalHash)
  })

  it('returns Home when browser history reaches the hashless root', async () => {
    render(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <App />
      </AuthContext.Provider>,
    )
    await screen.findByTestId('scripture-reader')

    window.location.hash = ''
    window.dispatchEvent(new HashChangeEvent('hashchange'))

    expect(await screen.findByRole('heading', {
      level: 1,
      name: /Unlocking Scripture Through Historical Context/i,
    })).toBeInTheDocument()
    expect(screen.queryByTestId('scripture-reader')).not.toBeInTheDocument()
  })

  it('returns Home when the hash changes to an unknown route', async () => {
    render(
      <AuthContext.Provider value={{ user: null, status: 'anonymous' }}>
        <App />
      </AuthContext.Provider>,
    )
    await screen.findByTestId('scripture-reader')

    window.location.hash = '#not-a-page'
    window.dispatchEvent(new HashChangeEvent('hashchange'))

    expect(await screen.findByRole('heading', {
      level: 1,
      name: /Unlocking Scripture Through Historical Context/i,
    })).toBeInTheDocument()
    expect(screen.queryByTestId('scripture-reader')).not.toBeInTheDocument()
  })

  it('gives the lazy reader fallback a meaningful skip target and main landmark', () => {
    render(<ReaderLoadingFallback />)

    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute(
      'href',
      '#main-content',
    )
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getByRole('main', { name: 'Scripture Reader' })).toHaveAttribute(
      'id',
      'main-content',
    )
    expect(screen.getByRole('status')).toHaveTextContent('Opening Scripture reader')
    expect(document.querySelectorAll('.reader-loading-skeleton__line').length).toBeGreaterThan(2)
    expect(document.querySelector('.reader-loading-skeleton')).toHaveAttribute('aria-hidden', 'true')
  })
})
