import { readFileSync } from 'node:fs'
import { useState } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BookPicker from './BookPicker'

const readerTokensCss = readFileSync('src/reader/readerTokens.css', 'utf8')

const books = ['Genesis', { name: 'Exodus' }, ' Psalms ', 'Genesis', '', null]

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function PickerHarness({ initiallyOpen = true, ...props }) {
  const [open, setOpen] = useState(initiallyOpen)

  return (
    <>
      <button onClick={() => setOpen(true)}>Open picker</button>
      <BookPicker
        open={open}
        books={books}
        selectedCanon="PROT66"
        loadChapters={() => [1, 2, 3]}
        onClose={() => setOpen(false)}
        {...props}
      />
    </>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('BookPicker', () => {
  it('renders a named modal dialog and filters normalized books with trimmed, case-insensitive search', async () => {
    const user = userEvent.setup()
    render(<PickerHarness />)

    const dialog = screen.getByRole('dialog', { name: 'Choose a book and chapter' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getAllByRole('button', { name: 'Genesis' })).toHaveLength(1)
    expect(within(dialog).getByRole('button', { name: 'Exodus' })).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Psalms' })).toBeInTheDocument()

    const search = within(dialog).getByRole('searchbox', { name: 'Search Bible books' })
    expect(search).toHaveFocus()
    await user.type(search, '  EXO  ')

    expect(within(dialog).getByRole('button', { name: 'Exodus' })).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Genesis' })).not.toBeInTheDocument()
  })

  it('shows clear empty search and defensive books states', () => {
    const { rerender } = render(
      <BookPicker open books={books} selectedCanon="PROT66" onClose={vi.fn()} />,
    )

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Leviticus' } })
    expect(screen.getByText('No books match “Leviticus”.')).toBeInTheDocument()

    rerender(
      <BookPicker open books={{ name: 'Genesis' }} selectedCanon="PROT66" onClose={vi.fn()} />,
    )
    expect(screen.getByText('No Bible books are available for this canon.')).toBeInTheDocument()
  })

  it('changes canon from a visibly labelled complete list and clears stale selection state', async () => {
    const user = userEvent.setup()
    const onCanonChange = vi.fn()
    render(<PickerHarness onCanonChange={onCanonChange} />)

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    expect(await screen.findByRole('heading', { name: 'Genesis chapters' })).toBeInTheDocument()

    const canon = screen.getByRole('combobox', { name: 'Canon' })
    expect(within(canon).getAllByRole('option').map((option) => option.textContent)).toEqual([
      'Protestant',
      'Catholic',
      'Ethiopian Orthodox',
      'Broader canon and scholarly texts',
    ])
    await user.selectOptions(canon, 'CATH73')

    expect(onCanonChange).toHaveBeenCalledWith('CATH73')
    expect(screen.getByRole('button', { name: 'Genesis' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Genesis chapters' })).not.toBeInTheDocument()
  })

  it('loads normalized chapters and chooses a chapter', async () => {
    const user = userEvent.setup()
    const loadChapters = vi.fn().mockResolvedValue([3, '2', 2, 0, -1, 1.5, 1, null])
    const onChoose = vi.fn()
    render(<PickerHarness loadChapters={loadChapters} onChoose={onChoose} />)

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    expect(loadChapters).toHaveBeenCalledWith('Genesis')
    const chapterGrid = await screen.findByRole('group', { name: 'Genesis chapters' })
    expect(within(chapterGrid).getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Chapter 1',
      'Chapter 2',
      'Chapter 3',
    ])

    await user.click(within(chapterGrid).getByRole('button', { name: 'Chapter 2' }))
    expect(onChoose).toHaveBeenCalledWith({ book: 'Genesis', chapter: 2 })
  })

  it('announces loading, retries failures, and handles an empty chapter result', async () => {
    const user = userEvent.setup()
    const pending = deferred()
    const loadChapters = vi.fn()
      .mockReturnValueOnce(pending.promise)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([1])
    render(<PickerHarness loadChapters={loadChapters} />)

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    expect(screen.getByRole('status')).toHaveTextContent('Loading chapters for Genesis')

    pending.reject(new Error('offline'))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not load chapters for Genesis.',
    )

    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not load chapters for Genesis.',
    )

    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No chapters are available for Genesis.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Back to books' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('button', { name: 'Chapter 1' })).toBeInTheDocument()
  })

  it('turns a missing loader into an actionable failure and tolerates absent callbacks', async () => {
    const user = userEvent.setup()
    render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not load chapters for Genesis.',
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await user.click(screen.getByRole('button', { name: 'Back to books' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Canon' }), {
      target: { value: 'ETHIO81' },
    })
    await user.click(screen.getByRole('button', { name: 'Close book picker' }))
  })

  it('ignores stale out-of-order chapter loads', async () => {
    const user = userEvent.setup()
    const genesis = deferred()
    const exodus = deferred()
    const loadChapters = vi.fn((name) => (
      name === 'Genesis' ? genesis.promise : exodus.promise
    ))
    render(<PickerHarness loadChapters={loadChapters} />)

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(screen.getByRole('button', { name: 'Back to books' }))
    await user.click(screen.getByRole('button', { name: 'Exodus' }))
    exodus.resolve([1, 2])
    expect(await screen.findByRole('group', { name: 'Exodus chapters' })).toBeInTheDocument()

    genesis.resolve([50])
    await waitFor(() => {
      expect(screen.getByRole('group', { name: 'Exodus chapters' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Chapter 50' })).not.toBeInTheDocument()
    })
  })

  it('closes explicitly, restores focus, resets on reopen, and does not reset on rerender', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<PickerHarness initiallyOpen={false} />)
    const opener = screen.getByRole('button', { name: 'Open picker' })

    await user.click(opener)
    await user.type(screen.getByRole('searchbox'), 'gen')
    rerender(<PickerHarness initiallyOpen={false} />)
    expect(screen.getByRole('searchbox')).toHaveValue('gen')
    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    expect(await screen.findByRole('heading', { name: 'Genesis chapters' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Close book picker' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
    expect(document.body.style.overflow).toBe('')

    await user.click(opener)
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.getByRole('searchbox')).toHaveFocus()
  })

  it('traps forward and backward focus, closes on Escape, and has no listener while closed', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { rerender } = render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => [1]}
        onClose={onClose}
      />,
    )

    const close = screen.getByRole('button', { name: 'Close book picker' })
    const book = screen.getByRole('button', { name: 'Genesis' })
    book.focus()
    await user.tab()
    expect(close).toHaveFocus()
    close.focus()
    await user.tab({ shift: true })
    expect(book).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()

    onClose.mockClear()
    rerender(
      <BookPicker
        open={false}
        books={['Genesis']}
        selectedCanon="PROT66"
        onClose={onClose}
      />,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('does not update after closing and supports back navigation during loading', async () => {
    const user = userEvent.setup()
    const request = deferred()
    const { rerender } = render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => request.promise}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(screen.getByRole('button', { name: 'Back to books' }))
    rerender(
      <BookPicker
        open={false}
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => request.promise}
        onClose={vi.fn()}
      />,
    )
    request.resolve([99])

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('uses unique heading ids for multiple instances', () => {
    render(
      <>
        <BookPicker open books={['Genesis']} selectedCanon="PROT66" onClose={vi.fn()} />
        <BookPicker open books={['Exodus']} selectedCanon="PROT66" onClose={vi.fn()} />
      </>,
    )

    const dialogs = screen.getAllByRole('dialog', { name: 'Choose a book and chapter' })
    const labelledBy = dialogs.map((dialog) => dialog.getAttribute('aria-labelledby'))
    expect(new Set(labelledBy).size).toBe(2)
    labelledBy.forEach((id) => expect(document.getElementById(id)).toBeInTheDocument())
  })
})

describe('BookPicker responsive styles', () => {
  it('defines a token-driven desktop drawer and full-screen mobile adaptation', () => {
    expect(readerTokensCss).toMatch(/\.book-picker__dialog\s*\{[^}]*position:\s*fixed/i)
    expect(readerTokensCss).toMatch(/\.book-picker__dialog\s*\{[^}]*width:\s*min\(30rem,\s*100vw\)/i)
    expect(readerTokensCss).toMatch(/\.book-picker__dialog\s*\{[^}]*overflow-y:\s*auto/i)
    expect(readerTokensCss).toMatch(/\.book-picker__dialog\s*\{[^}]*var\(--reader-surface\)/i)
    expect(readerTokensCss).toMatch(/\.book-picker__control\s*\{[^}]*min-height:\s*48px/i)
    expect(readerTokensCss).toMatch(/\.book-picker__books\s*\{[^}]*grid-template-columns:\s*repeat\(2/i)
    expect(readerTokensCss).toMatch(
      /@media\s*\(max-width:\s*767px\)[\s\S]*\.book-picker__dialog\s*\{[^}]*width:\s*100%/i,
    )
    expect(readerTokensCss).toMatch(
      /@media\s*\(max-width:\s*359px\)[\s\S]*\.book-picker__books\s*\{[^}]*grid-template-columns:\s*1fr/i,
    )
    const bookPickerCss = readerTokensCss.slice(readerTokensCss.indexOf('.book-picker {'))
      .split('@media (prefers-reduced-motion: reduce)')[0]
    expect(bookPickerCss).not.toContain('!important')
  })
})
