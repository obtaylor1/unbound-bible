import { readFileSync } from 'node:fs'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/authContext'
import App from '../App'
import { ReaderPreferencesProvider } from './ReaderPreferences'
import ReaderBottomNavigation from './ReaderBottomNavigation'
import ScriptureReaderPage from './ScriptureReaderPage'
import {
  getBookChapters,
  getBooks,
  getChapter,
  getVerseDetails,
} from './scriptureApi'

vi.mock('./scriptureApi', () => ({
  getBooks: vi.fn(),
  getChapter: vi.fn(),
  getBookChapters: vi.fn(),
  getVerseDetails: vi.fn(),
}))

vi.mock('../search/SearchDialog', () => ({
  default: ({ open, onClose, onNavigate }) => open ? (
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
      <button type="button" onClick={onClose}>Close search</button>
    </div>
  ) : null,
}))

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

beforeEach(() => {
  window.location.hash = '#scriptures?book=Genesis&chapter=1&translation=KJV&canon=ETHIO81'
  window.localStorage.clear()
  getBooks.mockResolvedValue(['Genesis', 'Exodus'])
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

  it('reacts to browser hash navigation and ignores stale chapter results', async () => {
    const genesis = deferred()
    const exodus = deferred()
    getChapter
      .mockReturnValueOnce(genesis.promise)
      .mockReturnValueOnce(exodus.promise)
    renderReader()

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
    const firstChapters = deferred()
    const currentChapters = deferred()
    getBooks
      .mockReturnValueOnce(firstBooks.promise)
      .mockReturnValueOnce(currentBooks.promise)
      .mockResolvedValue(['Exodus'])
    getBookChapters
      .mockReturnValueOnce(firstChapters.promise)
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
    firstChapters.resolve([1, 3])
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

  it('supports picker canon and chapter choice flows', async () => {
    const user = userEvent.setup()
    getBooks.mockImplementation((canon) => Promise.resolve(
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

  it('shows recoverable books and chapter-navigation metadata failures', async () => {
    const user = userEvent.setup()
    getBooks.mockRejectedValueOnce(new Error('books down')).mockResolvedValueOnce(['Genesis'])
    getBookChapters.mockRejectedValueOnce(new Error('chapters down')).mockResolvedValueOnce([1, 3])
    renderReader()
    await screen.findByText('In the beginning.')

    expect(screen.getByRole('status', { name: 'Chapter navigation unavailable' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous chapter' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next chapter' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Try chapter navigation again' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Next chapter' })).toBeEnabled())

    await user.click(screen.getByRole('button', { name: 'Choose a book' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Bible books could not load')
    await user.click(screen.getByRole('button', { name: 'Try loading books again' }))
    expect(await screen.findByRole('button', { name: 'Genesis' })).toBeInTheDocument()
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
    renderReader({ onPageChange })
    await screen.findByText('In the beginning.')
    await user.click(screen.getByRole('button', { name: 'Open study tools' }))
    await user.click(screen.getByRole('button', { name: 'Notes' }))
    expect(onPageChange).toHaveBeenCalledWith('notes', {
      book: 'Genesis', chapter: 1,
    })
    expect(screen.queryByRole('dialog', { name: 'Genesis 1' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    expect(screen.getByRole('dialog', { name: 'Search' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open Scripture result' }))
    expect(window.location.hash).toContain('book=Exodus&chapter=3&verse=2')
    expect(screen.queryByRole('dialog', { name: 'Search' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    await user.click(screen.getByRole('button', { name: 'Open library result' }))
    expect(onPageChange).toHaveBeenLastCalledWith('notes')
    expect(screen.queryByRole('dialog', { name: 'Search' })).not.toBeInTheDocument()
  })

  it('performs a real document navigation for non-hash search results', async () => {
    const user = userEvent.setup()
    const navigateDocument = vi.fn()
    renderReader({ navigateDocument })
    await screen.findByText('In the beginning.')

    await user.click(screen.getByRole('button', { name: 'Search', hidden: true }))
    await user.click(screen.getByRole('button', { name: 'Open shared study' }))

    expect(navigateDocument).toHaveBeenCalledWith(
      new URL('/share/public-study', window.location.href).href,
    )
  })

  it('does not refetch a chapter when tools open and keeps overlays mutually exclusive', async () => {
    const user = userEvent.setup()
    renderReader()
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

  it('aborts requests and removes its hash listener on unmount', async () => {
    const chapterSignals = []
    const booksSignals = []
    const chapterNumberSignals = []
    getBooks.mockImplementation((_, signal) => {
      booksSignals.push(signal)
      return new Promise(() => {})
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
    await user.click(screen.getByRole('button', { name: 'Genesis' }))
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
})
