import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TextualComparisonWorkspace from './TextualComparisonWorkspace'

vi.mock('./textualComparison/ComparisonStudyDrawer', () => ({
  default: ({ open, onClose, book, chapter, verse }) => open ? (
    <div role="dialog" aria-label="Study Tools">
      <span>Tools for {book} {chapter}:{verse}</span>
      <button type="button" onClick={onClose}>Close Study Tools</button>
    </div>
  ) : null,
}))

vi.mock('./ShareStudyModal', () => ({
  default: ({ isOpen, onClose }) => isOpen ? (
    <div role="dialog" aria-label="Share comparison">
      <button type="button" onClick={onClose}>Close share</button>
    </div>
  ) : null,
}))

const genesisRows = [
  { id: 1, book: 'Genesis', chapter: 1, verse: 1, translation: 'KJV', text: 'In the beginning God created the heaven and the earth.' },
  { id: 2, book: 'Genesis', chapter: 1, verse: 1, translation: 'ASV', text: 'In the beginning God created the heavens and the earth.' },
  { id: 3, book: 'Genesis', chapter: 1, verse: 1, translation: 'WEB', text: 'In the beginning, God created the heavens and the earth.' },
  { id: 4, book: 'Genesis', chapter: 1, verse: 2, translation: 'KJV', text: 'And the earth was without form, and void.' },
]

function jsonResponse(data, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(data) })
}

function installFetch({ rows = genesisRows, chapterOk = true } = {}) {
  global.fetch = vi.fn((url) => {
    if (String(url).includes('available-books')) return jsonResponse({ books: ['Genesis', '1 Enoch'] })
    if (String(url).includes('chapter-content')) return jsonResponse({ content: rows }, chapterOk)
    return jsonResponse({})
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  installFetch()
})

describe('TextualComparisonWorkspace', () => {
  it('starts with two sources, prioritizes the comparison, and keeps Study Tools closed', async () => {
    render(<TextualComparisonWorkspace />)

    expect(await screen.findByRole('heading', { name: 'Compare translations' })).toBeInTheDocument()
    expect(screen.getByTestId('comparison-workspace')).toBeInTheDocument()
    expect(screen.getByText('Comparing 2 translations')).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Ethiopian Orthodox Critical Text' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'King James Version' })).toBeInTheDocument()
    expect(screen.queryByRole('article', { name: 'American Standard Version' })).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Study Tools' })).not.toBeInTheDocument()
  })

  it('renders KJV text and an accurate Ethiopian database availability state', async () => {
    render(<TextualComparisonWorkspace />)

    const kjvCard = await screen.findByRole('article', { name: 'King James Version' })
    expect(kjvCard).toHaveTextContent('In the beginning God created the heaven and the earth.')
    expect(screen.getByText('Text unavailable')).toBeInTheDocument()
    expect(screen.getByText(/has not yet been added to the Ethiopian Critical Text database/)).toBeInTheDocument()
    expect(screen.queryByText('Canon Exclusion')).not.toBeInTheDocument()
  })

  it('opens Study Tools from the explicit toolbar action', async () => {
    const user = userEvent.setup()
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'King James Version' })

    await user.click(screen.getByRole('button', { name: 'Open Study Tools' }))
    expect(screen.getByRole('dialog', { name: 'Study Tools' })).toHaveTextContent('Tools for Genesis 1:1')
    await user.click(screen.getByRole('button', { name: 'Close Study Tools' }))
    expect(screen.queryByRole('dialog', { name: 'Study Tools' })).not.toBeInTheDocument()
  })

  it('adds translations and moves the base when its source is removed', async () => {
    const user = userEvent.setup()
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'King James Version' })

    await user.click(screen.getByRole('checkbox', { name: /American Standard Version/ }))
    expect(screen.getByRole('article', { name: 'American Standard Version' })).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: /Ethiopian Orthodox Critical Text/ }))
    expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('kjv')
  })

  it('switches to an aligned chapter view', async () => {
    const user = userEvent.setup()
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'King James Version' })

    await user.click(screen.getByRole('button', { name: 'Chapter view' }))
    expect(screen.getByRole('heading', { name: 'Genesis chapter 1 comparison' })).toBeInTheDocument()
    expect(screen.getByText('Verse 2')).toBeInTheDocument()
  })

  it('shows a retryable request error instead of an unavailable-source warning', async () => {
    installFetch({ chapterOk: false })
    render(<TextualComparisonWorkspace />)

    expect(await screen.findByRole('heading', { name: 'We could not load this passage' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.queryByText('Text unavailable')).not.toBeInTheDocument()
  })

  it('preserves bookmarks and exposes sharing', async () => {
    const user = userEvent.setup()
    render(<TextualComparisonWorkspace />)
    const bookmark = await screen.findByRole('button', { name: 'Bookmark Genesis 1:1 in KJV' })

    await user.click(bookmark)
    expect(JSON.parse(localStorage.getItem('unbound_bookmarks'))).toContain('Genesis 1:1')
    await user.click(screen.getByRole('button', { name: 'Share comparison' }))
    expect(screen.getByRole('dialog', { name: 'Share comparison' })).toBeInTheDocument()
  })

  it('ignores a stale chapter response after the book changes', async () => {
    let resolveGenesis
    const genesisPromise = new Promise((resolve) => { resolveGenesis = resolve })
    global.fetch = vi.fn((url) => {
      const value = String(url)
      if (value.includes('available-books')) return jsonResponse({ books: ['Genesis', '1 Enoch'] })
      if (value.includes('book=Genesis')) return genesisPromise
      if (value.includes('book=1%20Enoch')) {
        return jsonResponse({ content: [{ id: 9, book: '1 Enoch', chapter: 1, verse: 1, translation: '1EN_CH', text: 'The words of the blessing of Enoch.' }] })
      }
      return jsonResponse({ content: [] })
    })

    const user = userEvent.setup()
    render(<TextualComparisonWorkspace />)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Book' }), '1 Enoch')
    expect(await screen.findByText('The words of the blessing of Enoch.')).toBeInTheDocument()

    resolveGenesis({ ok: true, json: () => Promise.resolve({ content: genesisRows }) })
    await waitFor(() => expect(screen.queryByText('In the beginning God created the heaven and the earth.')).not.toBeInTheDocument())
  })
})
