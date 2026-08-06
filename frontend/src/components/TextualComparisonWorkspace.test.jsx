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

const edition = (code, name) => ({ code, name, language: 'English' })

const genesisRows = [
  { id: 1, book: 'Genesis', chapter: 1, verse: 1, translation: 'KJV', edition: edition('KJV', 'King James Version'), text: 'In the beginning God created the heaven and the earth.' },
  { id: 2, book: 'Genesis', chapter: 1, verse: 1, translation: 'ASV', edition: edition('ASV', 'American Standard Version'), text: 'In the beginning God created the heavens and the earth.' },
  { id: 3, book: 'Genesis', chapter: 1, verse: 1, translation: 'WEB', edition: edition('WEB', 'World English Bible'), text: 'In the beginning, God created the heavens and the earth.' },
  { id: 4, book: 'Genesis', chapter: 1, verse: 2, translation: 'KJV', edition: edition('KJV', 'King James Version'), text: 'And the earth was without form, and void.' },
]

const compositeRow = {
  id: 5,
  book: 'Genesis',
  chapter: 1,
  verse: 1,
  translation: 'EOTC-COMPOSITE-EN',
  text: 'In the beginning, God created the heavens and the earth.',
  edition: edition('EOTC-COMPOSITE-EN', 'Ethiopian Orthodox Bible — Composite English Edition'),
  work_source: {
    source_label: 'KJV 1611 fallback',
    source_tradition: 'King James tradition',
    translator: 'King James Version translators',
    attribution: 'Public-domain archive text.',
    provenance_url: 'https://example.test/kjv',
    fallback: true,
    verification_status: 'provisional',
    canon_scope: 'ethio81',
  },
}

function jsonResponse(data, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(data) })
}

function installFetch({ rows = genesisRows, chapterOk = true } = {}) {
  globalThis.fetch = vi.fn((url) => {
    if (String(url).includes('available-books')) return jsonResponse({ books: ['Genesis', '1 Enoch'] })
    if (String(url).includes('chapter-content')) return jsonResponse({ content: rows }, chapterOk)
    return jsonResponse({})
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  window.history.replaceState(null, '', '#compare?book=Genesis&chapter=1&verse=1&canon=ETHIO81')
  installFetch()
})

describe('TextualComparisonWorkspace', () => {
  it('shows only installed sources and keeps Study Tools closed', async () => {
    render(<TextualComparisonWorkspace />)

    expect(await screen.findByRole('heading', { name: 'Compare translations' })).toBeInTheDocument()
    expect(screen.getByTestId('comparison-workspace')).toBeInTheDocument()
    expect(screen.getByText('Comparing 2 translations')).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'King James Version' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'American Standard Version' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: /Ge'ez Bible/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Study Tools' })).not.toBeInTheDocument()
  })

  it('renders KJV text without a phantom unavailable Ethiopian card', async () => {
    render(<TextualComparisonWorkspace />)

    const kjvCard = await screen.findByRole('article', { name: 'King James Version' })
    expect(kjvCard).toHaveTextContent('In the beginning God created the heaven and the earth.')
    expect(screen.queryByText('Text unavailable')).not.toBeInTheDocument()
  })

  it('renders the verified Ge\'ez Genesis source when the API provides it', async () => {
    installFetch({ rows: [
      ...genesisRows,
      {
        id: 10,
        book: 'Genesis',
        chapter: 1,
        verse: 1,
        translation: 'GEEZ1980-RESEARCH',
        text: 'በቀዳሚ ገብረ እግዚአብሔር።',
        edition: {
          code: 'GEEZ1980-RESEARCH',
          name: "Ge'ez Bible (1980 EC) — Research Use",
          relationship: 'exact_ethiopian',
        },
      },
    ] })

    render(<TextualComparisonWorkspace />)

    const geezCard = await screen.findByRole('article', {
      name: "Ge'ez Bible (1980 EC) — Research Use",
    })
    expect(geezCard).toHaveTextContent('በቀዳሚ ገብረ እግዚአብሔር።')
    expect(geezCard).not.toHaveTextContent('Text unavailable')
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

    await user.click(screen.getByRole('checkbox', { name: /World English Bible/ }))
    expect(screen.getByRole('article', { name: 'World English Bible' })).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: /King James Version/ }))
    expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('asv')
  })

  it('prefers composite English as base and shows literal source warnings without relying on color', async () => {
    installFetch({ rows: [compositeRow, ...genesisRows] })
    render(<TextualComparisonWorkspace />)

    const card = await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })
    expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('eotc-composite-en')
    expect(card).toHaveTextContent('KJV fallback')
    expect(card).toHaveTextContent('Provisional source')
    expect(card).toHaveTextContent('KJV 1611 fallback')
    expect(card).toHaveTextContent('Translated by King James Version translators')
  })

  it('keeps an explicit same-passage route source through hash navigation and browser back', async () => {
    window.history.replaceState(null, '', '#compare?book=Genesis&chapter=1&verse=1&translation=KJV&canon=ETHIO81')
    installFetch({ rows: [compositeRow, ...genesisRows] })
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })

    const kjvHash = window.location.hash
    expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('kjv')
    expect(kjvHash).toContain('translation=KJV')

    window.history.pushState(null, '', '#compare?book=Genesis&chapter=1&verse=1&translation=EOTC-COMPOSITE-EN&canon=ETHIO81')
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('eotc-composite-en'))
    expect(window.location.hash).toContain('translation=EOTC-COMPOSITE-EN')

    window.history.back()
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('kjv'))
    expect(window.location.hash).toBe(kjvHash)
  })

  it('uses the first available verse source as the visible and mathematical base', async () => {
    const user = userEvent.setup()
    installFetch({ rows: [
      { ...compositeRow, text: '   ' },
      { ...genesisRows[0], text: 'one two three' },
      { ...genesisRows[1], text: 'one two four' },
    ] })
    render(<TextualComparisonWorkspace />)
    const compositeCard = await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })
    await user.click(screen.getByRole('checkbox', { name: /American Standard Version/ }))

    const kjvCard = screen.getByRole('article', { name: 'King James Version' })
    expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('kjv')
    expect(kjvCard).toHaveTextContent('Base reference')
    expect(compositeCard).toHaveTextContent('Text unavailable')
    expect(compositeCard).not.toHaveTextContent('Base reference')
    expect(screen.getByText('1 wording difference found')).toBeVisible()
    expect(screen.getByText('four', { selector: 'mark' })).toBeVisible()
    expect(screen.getByText(/Differences are highlighted against King James Version/)).toBeVisible()
    expect(window.location.hash).toContain('translation=EOTC-COMPOSITE-EN')
  })

  it('uses the effective available base consistently in chapter view', async () => {
    const user = userEvent.setup()
    installFetch({ rows: [
      { ...compositeRow, text: '   ' },
      { ...genesisRows[0], text: 'one two three' },
      { ...genesisRows[1], text: 'one two four' },
    ] })
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })
    await user.click(screen.getByRole('checkbox', { name: /American Standard Version/ }))
    await user.click(screen.getByRole('button', { name: 'Chapter view' }))

    expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('kjv')
    expect(screen.getByRole('article', { name: 'King James Version, verse 1' })).toHaveTextContent('Base reference')
    expect(screen.getByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition, verse 1' })).not.toHaveTextContent('Base reference')
    expect(screen.getByText('four', { selector: 'mark' })).toBeVisible()
    expect(screen.getByText(/each verse is highlighted against its labeled available base.*Genesis 1:1 currently uses King James Version/i)).toBeVisible()
    expect(window.location.hash).toContain('translation=EOTC-COMPOSITE-EN')
  })

  it('returns to the requested chapter base when its text becomes available on a later verse', async () => {
    const user = userEvent.setup()
    installFetch({ rows: [
      { ...compositeRow, text: '   ' },
      { ...genesisRows[0], text: 'one two three' },
      { ...genesisRows[1], text: 'one two four' },
      { ...compositeRow, id: 40, verse: 2, text: 'alpha beta' },
      { ...genesisRows[0], id: 41, verse: 2, text: 'alpha gamma delta' },
      { ...genesisRows[1], id: 42, verse: 2, text: 'alpha beta' },
    ] })
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })
    await user.click(screen.getByRole('checkbox', { name: /American Standard Version/ }))
    await user.click(screen.getByRole('button', { name: 'Chapter view' }))

    expect(screen.getByRole('article', { name: 'King James Version, verse 1' })).toHaveTextContent('Base reference')
    expect(screen.getByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition, verse 1' })).not.toHaveTextContent('Base reference')
    expect(screen.getByRole('article', { name: 'King James Version, verse 2' })).not.toHaveTextContent('Base reference')
    expect(screen.getByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition, verse 2' })).toHaveTextContent('Base reference')
    expect(screen.getByText('2 differences', { selector: '.chapter-difference-count' })).toBeVisible()
    const kjvVerseTwo = screen.getByRole('article', { name: 'King James Version, verse 2' })
    expect([...kjvVerseTwo.querySelectorAll('mark')].map((mark) => mark.textContent)).toEqual(['gamma', 'delta'])
  })

  it('calculates three-source difference totals from the active base translation', async () => {
    const user = userEvent.setup()
    installFetch({ rows: [
      { ...compositeRow, text: 'one two three' },
      { ...genesisRows[0], text: 'one two three four' },
      { ...genesisRows[1], text: 'one two' },
    ] })
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })

    await user.click(screen.getByRole('checkbox', { name: /American Standard Version/ }))
    expect(screen.getByRole('combobox', { name: 'Base reference' })).toHaveValue('eotc-composite-en')
    expect(screen.getByText('1 wording difference found')).toBeVisible()
    expect(screen.queryByText('2 wording differences found')).not.toBeInTheDocument()
  })

  it('does not report missing source text as a wording difference', async () => {
    installFetch({ rows: [{ ...compositeRow, text: null }, genesisRows[0]] })
    render(<TextualComparisonWorkspace />)

    expect(await screen.findByText('One source is available. Add another source to compare wording.')).toBeInTheDocument()
    expect(screen.getByText('0 wording differences found')).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })).toHaveTextContent('Text unavailable')
  })

  it('highlights chapter differences against an available source when the preferred base is blank', async () => {
    const user = userEvent.setup()
    installFetch({ rows: [
      { ...compositeRow, text: '   ' },
      genesisRows[0],
      genesisRows[1],
    ] })
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })

    await user.click(screen.getByRole('checkbox', { name: /American Standard Version/ }))
    await user.click(screen.getByRole('button', { name: 'Chapter view' }))
    expect(screen.getByText('heavens', { selector: 'mark' })).toBeInTheDocument()
    expect(screen.queryByText('God', { selector: 'mark' })).not.toBeInTheDocument()
  })

  it('renders whitespace-only chapter text as unavailable instead of a blank paragraph', async () => {
    const user = userEvent.setup()
    installFetch({ rows: [
      { ...compositeRow, text: '   ' },
      genesisRows[0],
    ] })
    const { container } = render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })

    await user.click(screen.getByRole('button', { name: 'Chapter view' }))
    expect(screen.getByText('Text unavailable', { selector: '.chapter-source-empty' })).toBeVisible()
    const paragraphs = [...container.querySelectorAll('.comparison-chapter-row article p')]
    expect(paragraphs.some((paragraph) => paragraph.textContent.trim() === '')).toBe(false)
  })

  it('retains the ETHIO81 canon when sources and passage controls update the route', async () => {
    const user = userEvent.setup()
    installFetch({ rows: [compositeRow, ...genesisRows] })
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'Ethiopian Orthodox Bible — Composite English Edition' })

    await user.selectOptions(screen.getByRole('combobox', { name: 'Base reference' }), 'kjv')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Verse' }), '2')
    await waitFor(() => expect(window.location.hash).toContain('canon=ETHIO81'))
    expect(window.location.hash).toContain('translation=KJV')
    expect(window.location.hash).toContain('verse=2')
  })

  it('excludes supplemental Prayer of Manasseh from ETHIO81 book navigation', async () => {
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('available-books')) {
        return jsonResponse({ books: ['Genesis', 'Prayer of Manasseh'] })
      }
      return jsonResponse({ content: genesisRows })
    })
    render(<TextualComparisonWorkspace />)

    await screen.findByRole('article', { name: 'King James Version' })
    expect(screen.getByRole('combobox', { name: 'Book' })).not.toHaveTextContent('Prayer of Manasseh')
  })

  it('does not expose supplemental works for an arbitrary non-library canon', async () => {
    window.history.replaceState(null, '', '#compare?book=Genesis&chapter=1&verse=1&canon=UNKNOWN')
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('available-books')) {
        return jsonResponse({ books: ['Genesis', 'Prayer of Manasseh'] })
      }
      return jsonResponse({ content: genesisRows })
    })
    render(<TextualComparisonWorkspace />)

    await screen.findByRole('article', { name: 'King James Version' })
    expect(screen.getByRole('combobox', { name: 'Book' })).not.toHaveTextContent('Prayer of Manasseh')
    expect(window.location.hash).toContain('canon=UNKNOWN')
  })

  it('safely redirects a direct supplemental route outside LIBRARY context', async () => {
    window.history.replaceState(null, '', '#compare?book=Prayer%20of%20Manasseh&chapter=1&verse=1&canon=PROTESTNAT')
    const requestedChapterUrls = []
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('available-books')) {
        return jsonResponse({ books: ['Genesis', 'Prayer of Manasseh'] })
      }
      requestedChapterUrls.push(String(url))
      return jsonResponse({ content: genesisRows })
    })
    render(<TextualComparisonWorkspace />)

    await screen.findByRole('article', { name: 'King James Version' })
    expect(screen.getByRole('combobox', { name: 'Book' })).toHaveValue('Genesis')
    expect(requestedChapterUrls).toEqual(expect.arrayContaining([
      expect.stringContaining('book=Genesis'),
    ]))
    expect(requestedChapterUrls.some((url) => url.includes('Prayer'))).toBe(false)
    expect(window.location.hash).toContain('book=Genesis')
    expect(window.location.hash).toContain('canon=PROTESTNAT')
  })

  it('allows an explicitly requested supplemental work in broader library context', async () => {
    window.history.replaceState(null, '', '#compare?book=Prayer%20of%20Manasseh&chapter=1&verse=1&canon=LIBRARY')
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('available-books')) {
        return jsonResponse({ books: ['Genesis', 'Prayer of Manasseh'] })
      }
      return jsonResponse({ content: [{
        id: 20,
        book: 'Prayer of Manasseh',
        chapter: 1,
        verse: 1,
        translation: 'EOTC-COMPOSITE-EN',
        edition: edition('EOTC-COMPOSITE-EN', 'Ethiopian Orthodox Bible — Composite English Edition'),
        text: 'O Lord Almighty, God of our fathers.',
        work_source: { canon_scope: 'supplemental', verification_status: 'provisional' },
      }] })
    })
    render(<TextualComparisonWorkspace />)

    expect(await screen.findByText('O Lord Almighty, God of our fathers.')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Book' })).toHaveValue('Prayer of Manasseh')
    expect(window.location.hash).toContain('canon=LIBRARY')
  })

  it('synchronizes a mounted workspace across compare hash navigation and back', async () => {
    const requestedUrls = []
    globalThis.fetch = vi.fn((url) => {
      const value = String(url)
      if (value.includes('available-books')) return jsonResponse({ books: ['Genesis', '1 Enoch'] })
      requestedUrls.push(value)
      if (value.includes('book=1%20Enoch')) {
        return jsonResponse({ content: [{
          id: 30,
          book: '1 Enoch',
          chapter: 2,
          verse: 3,
          translation: '1EN_CH',
          edition: edition('1EN_CH', '1 Enoch, R. H. Charles'),
          text: 'Observe everything that takes place in the heaven.',
        }] })
      }
      return jsonResponse({ content: genesisRows })
    })
    render(<TextualComparisonWorkspace />)
    await screen.findByRole('article', { name: 'King James Version' })

    const genesisHash = window.location.hash
    window.history.pushState(null, '', '#compare?book=1%20Enoch&chapter=2&verse=3&translation=1EN_CH&canon=LIBRARY')
    window.dispatchEvent(new HashChangeEvent('hashchange'))

    expect(await screen.findByText('Observe everything that takes place in the heaven.')).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Book' })).toHaveValue('1 Enoch')
    expect(screen.getByRole('combobox', { name: 'Chapter' })).toHaveValue('2')
    expect(screen.getByRole('combobox', { name: 'Verse' })).toHaveValue('3')
    expect(window.location.hash).toContain('canon=LIBRARY')

    window.history.back()
    expect(await screen.findByText('In the beginning God created the heaven and the earth.')).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Book' })).toHaveValue('Genesis')
    expect(window.location.hash).toBe(genesisHash)
    expect(requestedUrls.some((url) => url.includes('book=1%20Enoch&chapter=2'))).toBe(true)
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
    globalThis.fetch = vi.fn((url) => {
      const value = String(url)
      if (value.includes('available-books')) return jsonResponse({ books: ['Genesis', '1 Enoch'] })
      if (value.includes('book=Genesis')) return genesisPromise
      if (value.includes('book=1%20Enoch')) {
        return jsonResponse({ content: [{ id: 9, book: '1 Enoch', chapter: 1, verse: 1, translation: '1EN_CH', edition: edition('1EN_CH', '1 Enoch, R. H. Charles'), text: 'The words of the blessing of Enoch.' }] })
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
