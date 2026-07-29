import { readFileSync } from 'node:fs'
import { Suspense, useRef, useState, useTransition } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BookPicker from './BookPicker'
import useDialogFocus from './useDialogFocus'

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

function DialogFocusHarness({
  onClose,
  initialKind = 'valid',
  controls = 'many',
  outsideControl = false,
  withContainer = true,
}) {
  const containerRef = useRef(null)
  const initialRef = useRef(null)

  useDialogFocus({
    open: true,
    containerRef,
    initialRef,
    onClose,
  })

  if (!withContainer) {
    return <button data-testid="outside-focus-target">Outside the missing dialog</button>
  }

  let initialControl = <button ref={initialRef}>Initial control</button>
  if (initialKind === 'hidden') {
    initialControl = <span hidden><button ref={initialRef}>Hidden initial control</button></span>
  } else if (initialKind === 'aria-hidden') {
    initialControl = (
      <span aria-hidden="true">
        <button ref={initialRef}>Aria-hidden initial control</button>
      </span>
    )
  } else if (initialKind === 'disabled') {
    initialControl = <button ref={initialRef} disabled>Disabled initial control</button>
  } else if (initialKind === 'inert') {
    initialControl = <span inert><button ref={initialRef}>Inert initial control</button></span>
  } else if (initialKind === 'disabled-fieldset') {
    initialControl = (
      <fieldset disabled>
        <button ref={initialRef}>Fieldset initial control</button>
      </fieldset>
    )
  } else if (initialKind === 'negative-tabindex') {
    initialControl = (
      <button ref={initialRef} tabIndex={-1}>Negative tabindex initial control</button>
    )
  } else if (initialKind === 'closed-details') {
    initialControl = (
      <details>
        <summary tabIndex={-1}>Collapsed details</summary>
        <button ref={initialRef}>Hidden details control</button>
      </details>
    )
  } else if (initialKind === 'closed-summary') {
    initialControl = (
      <details>
        <summary ref={initialRef}>Visible details summary</summary>
        <button>Hidden details control</button>
      </details>
    )
  } else if (initialKind === 'closed-summary-descendant') {
    initialControl = (
      <details>
        <summary>
          Visible details summary
          <button ref={initialRef}>Summary action</button>
        </summary>
        <button>Hidden details control</button>
      </details>
    )
  }

  return (
    <>
      {outsideControl && <button>Outside control</button>}
      {initialKind === 'outside' && (
        <button ref={initialRef}>Outside initial control</button>
      )}
      <div ref={containerRef} data-testid="focus-dialog" tabIndex={-1}>
        {controls !== 'zero' && initialKind !== 'outside' && initialControl}
        {controls === 'many' && <button>Fallback control</button>}
      </div>
    </>
  )
}

const neverSettles = new Promise(() => {})

function SuspendForever() {
  throw neverSettles
}

function AbandonedCloseHarness({ request }) {
  const [attemptedClose, setAttemptedClose] = useState(false)
  const [, startTransition] = useTransition()

  return (
    <>
      <button
        onClick={() => {
          startTransition(() => setAttemptedClose(true))
        }}
      >
        Attempt suspended close
      </button>
      <Suspense fallback={<p>Suspended fallback</p>}>
        <BookPicker
          open={!attemptedClose}
          books={['Genesis']}
          selectedCanon="PROT66"
          loadChapters={() => request.promise}
          onClose={vi.fn()}
        />
        {attemptedClose && <SuspendForever />}
      </Suspense>
    </>
  )
}

function AbandonedCallbackHarness({ committedClose, abandonedClose }) {
  const [attemptedUpdate, setAttemptedUpdate] = useState(false)
  const [, startTransition] = useTransition()

  return (
    <>
      <button
        onClick={() => {
          startTransition(() => setAttemptedUpdate(true))
        }}
      >
        Attempt callback update
      </button>
      <Suspense fallback={<p>Callback fallback</p>}>
        <DialogFocusHarness
          onClose={attemptedUpdate ? abandonedClose : committedClose}
        />
        {attemptedUpdate && <SuspendForever />}
      </Suspense>
    </>
  )
}

function StackedDialog({ name, open, onClose }) {
  const containerRef = useRef(null)
  const initialRef = useRef(null)

  useDialogFocus({
    open,
    containerRef,
    initialRef,
    onClose,
  })

  if (!open) return null

  return (
    <div ref={containerRef} role="dialog" aria-label={name} tabIndex={-1}>
      <button ref={initialRef}>{name} first</button>
      <button>{name} last</button>
    </div>
  )
}

function StackedDialogsHarness({ lowerClose, upperClose }) {
  const [upperOpen, setUpperOpen] = useState(true)

  return (
    <>
      <StackedDialog name="Lower dialog" open onClose={lowerClose} />
      <StackedDialog
        name="Upper dialog"
        open={upperOpen}
        onClose={() => {
          upperClose()
          setUpperOpen(false)
        }}
      />
    </>
  )
}

function RemovedOpenerHarness() {
  const [open, setOpen] = useState(false)
  const [showOpener, setShowOpener] = useState(true)
  const containerRef = useRef(null)
  const initialRef = useRef(null)
  const fallbackRef = useRef(null)

  useDialogFocus({
    open,
    containerRef,
    initialRef,
    onClose: () => {
      setShowOpener(false)
      setOpen(false)
    },
    restoreRef: fallbackRef,
  })

  return (
    <>
      <button>Unrelated page action</button>
      <main ref={fallbackRef} tabIndex={-1}>Reader content</main>
      {showOpener && <button onClick={() => setOpen(true)}>Open temporary dialog</button>}
      {open && (
        <div ref={containerRef} role="dialog" aria-label="Temporary dialog" tabIndex={-1}>
          <button ref={initialRef} onClick={() => {
            setShowOpener(false)
            setOpen(false)
          }}>
            Close temporary dialog
          </button>
        </div>
      )}
    </>
  )
}

function ChainLowerDialog({ open, onOpenUpper }) {
  const containerRef = useRef(null)
  const initialRef = useRef(null)

  useDialogFocus({
    open,
    containerRef,
    initialRef,
    onClose: vi.fn(),
  })

  if (!open) return null

  return (
    <div ref={containerRef} role="dialog" aria-label="Chain lower" tabIndex={-1}>
      <button ref={initialRef}>Chain lower first</button>
      <button onClick={onOpenUpper}>Open chain upper</button>
    </div>
  )
}

function RestoreChainHarness({ upperClose }) {
  const [lowerOpen, setLowerOpen] = useState(false)
  const [upperOpen, setUpperOpen] = useState(false)

  return (
    <>
      <button onClick={() => setLowerOpen(true)}>Page dialog opener</button>
      <button onClick={() => setLowerOpen(false)}>Remove lower out of order</button>
      <ChainLowerDialog
        open={lowerOpen}
        onOpenUpper={() => setUpperOpen(true)}
      />
      <StackedDialog
        name="Chain upper"
        open={upperOpen}
        onClose={() => {
          upperClose()
          setUpperOpen(false)
        }}
      />
    </>
  )
}

function ReplacementFallbackHarness() {
  const [open, setOpen] = useState(false)
  const [showOpener, setShowOpener] = useState(true)
  const [replacement, setReplacement] = useState(false)
  const containerRef = useRef(null)
  const initialRef = useRef(null)
  const fallbackRef = useRef(null)

  useDialogFocus({
    open,
    containerRef,
    initialRef,
    onClose: () => setOpen(false),
    restoreRef: fallbackRef,
  })

  return (
    <>
      <section
        key={replacement ? 'replacement' : 'original'}
        ref={fallbackRef}
        data-testid={replacement ? 'replacement-fallback' : 'original-fallback'}
        tabIndex={-1}
      >
        Reader fallback
      </section>
      {showOpener && <button onClick={() => setOpen(true)}>Open fallback dialog</button>}
      {open && (
        <div ref={containerRef} role="dialog" aria-label="Fallback dialog" tabIndex={-1}>
          <button ref={initialRef} onClick={() => {
            setReplacement(true)
            setShowOpener(false)
          }}>
            Replace fallback and opener
          </button>
          <button onClick={() => setOpen(false)}>Close fallback dialog</button>
        </div>
      )}
    </>
  )
}

function ReopenRaceHarness({ firstRequest, secondRequest }) {
  const [open, setOpen] = useState(true)
  const calls = useRef(0)

  return (
    <>
      <button onClick={() => setOpen(true)}>Reopen picker</button>
      <BookPicker
        open={open}
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => {
          calls.current += 1
          return calls.current === 1 ? firstRequest.promise : secondRequest.promise
        }}
        onClose={() => setOpen(false)}
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

  it('distinguishes loading, failed, and genuinely empty book catalogs', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    const { rerender } = render(
      <BookPicker
        open
        books={[]}
        booksStatus="loading"
        selectedCanon="PROT66"
        onRetryBooks={retry}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Loading Bible books')
    expect(screen.queryByText(/No Bible books are available/)).not.toBeInTheDocument()

    rerender(
      <BookPicker
        open
        books={[]}
        booksStatus="error"
        selectedCanon="PROT66"
        onRetryBooks={retry}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Bible books could not load')
    await user.click(screen.getByRole('button', { name: 'Try loading books again' }))
    expect(retry).toHaveBeenCalledOnce()

    rerender(
      <BookPicker
        open
        books={[]}
        booksStatus="ready"
        selectedCanon="PROT66"
        onClose={vi.fn()}
      />,
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
    expect(loadChapters).toHaveBeenCalledWith('Genesis', expect.any(AbortSignal))
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

  it('aborts chapter loads on replacement, Back, close, and unmount', async () => {
    const user = userEvent.setup()
    const signals = []
    const loadChapters = vi.fn((_, signal) => {
      signals.push(signal)
      return new Promise(() => {})
    })
    const { unmount } = render(
      <PickerHarness loadChapters={loadChapters} />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    expect(signals[0].aborted).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Back to books' }))
    expect(signals[0].aborted).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(screen.getByRole('button', { name: 'Close book picker' }))
    expect(signals[1].aborted).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Open picker' }))
    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    unmount()
    expect(signals[2].aborted).toBe(true)
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

  it('uses the latest committed close callback', () => {
    const firstClose = vi.fn()
    const latestClose = vi.fn()
    const { rerender } = render(<DialogFocusHarness onClose={firstClose} />)

    rerender(<DialogFocusHarness onClose={latestClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })

    expect(latestClose).toHaveBeenCalledOnce()
    expect(firstClose).not.toHaveBeenCalled()
  })

  it('does not expose a close callback from an abandoned render', async () => {
    const user = userEvent.setup()
    const committedClose = vi.fn()
    const abandonedClose = vi.fn()
    render(
      <AbandonedCallbackHarness
        committedClose={committedClose}
        abandonedClose={abandonedClose}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Attempt callback update' }))
    expect(screen.queryByText('Callback fallback')).not.toBeInTheDocument()
    await user.keyboard('{Escape}')

    expect(committedClose).toHaveBeenCalledOnce()
    expect(abandonedClose).not.toHaveBeenCalled()
  })

  it.each([
    'hidden',
    'aria-hidden',
    'disabled',
    'inert',
    'disabled-fieldset',
    'negative-tabindex',
    'closed-details',
    'outside',
  ])(
    'skips a %s initial target and focuses the eligible fallback',
    (initialKind) => {
      render(
        <DialogFocusHarness
          initialKind={initialKind}
          onClose={vi.fn()}
        />,
      )

      expect(screen.getByRole('button', { name: 'Fallback control' })).toHaveFocus()
    },
  )

  it('allows the visible summary control of a closed details element', () => {
    render(
      <DialogFocusHarness
        initialKind="closed-summary"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('Visible details summary')).toHaveFocus()
  })

  it('allows a focusable descendant inside the visible summary of closed details', () => {
    render(
      <DialogFocusHarness
        initialKind="closed-summary-descendant"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Summary action' })).toHaveFocus()
  })

  it.each(['negative-tabindex', 'closed-details'])(
    'excludes %s controls from the forward wrap list',
    (initialKind) => {
      render(
        <DialogFocusHarness
          initialKind={initialKind}
          onClose={vi.fn()}
          outsideControl
        />,
      )

      screen.getByRole('button', { name: 'Outside control' }).focus()
      fireEvent.keyDown(document, { key: 'Tab' })
      expect(screen.getByRole('button', { name: 'Fallback control' })).toHaveFocus()
    },
  )

  it('focuses the dialog itself and safely contains Tab when it has no eligible controls', async () => {
    const user = userEvent.setup()
    render(
      <DialogFocusHarness
        controls="zero"
        onClose={vi.fn()}
      />,
    )

    const dialog = screen.getByTestId('focus-dialog')
    expect(dialog).toHaveFocus()
    await user.tab()
    expect(dialog).toHaveFocus()
    await user.tab({ shift: true })
    expect(dialog).toHaveFocus()
  })

  it('keeps forward and backward Tab on the sole eligible control', async () => {
    const user = userEvent.setup()
    render(
      <DialogFocusHarness
        controls="one"
        onClose={vi.fn()}
      />,
    )

    const control = screen.getByRole('button', { name: 'Initial control' })
    expect(control).toHaveFocus()
    await user.tab()
    expect(control).toHaveFocus()
    await user.tab({ shift: true })
    expect(control).toHaveFocus()
  })

  it('does not focus outside the dialog when its container is missing', () => {
    render(
      <DialogFocusHarness
        withContainer={false}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByTestId('outside-focus-target')).not.toHaveFocus()
    expect(document.body).toHaveFocus()
  })

  it('lets only the top dialog handle Escape and restores focus inside the lower dialog', async () => {
    const user = userEvent.setup()
    const lowerClose = vi.fn()
    const upperClose = vi.fn()
    render(
      <StackedDialogsHarness
        lowerClose={lowerClose}
        upperClose={upperClose}
      />,
    )

    await user.keyboard('{Escape}')

    expect(upperClose).toHaveBeenCalledOnce()
    expect(lowerClose).not.toHaveBeenCalled()
    const lowerDialog = screen.getByRole('dialog', { name: 'Lower dialog' })
    expect(screen.queryByRole('dialog', { name: 'Upper dialog' })).not.toBeInTheDocument()
    expect(lowerDialog).toContainElement(document.activeElement)
    expect(screen.getByRole('button', { name: 'Lower dialog first' })).toHaveFocus()
  })

  it('lets only the top dialog trap Tab', async () => {
    const user = userEvent.setup()
    render(
      <StackedDialogsHarness
        lowerClose={vi.fn()}
        upperClose={vi.fn()}
      />,
    )

    const lowerFirst = screen.getByRole('button', { name: 'Lower dialog first' })
    const upperFirst = screen.getByRole('button', { name: 'Upper dialog first' })
    const lowerFocus = vi.spyOn(lowerFirst, 'focus')
    const upperFocus = vi.spyOn(upperFirst, 'focus')
    const upperLast = screen.getByRole('button', { name: 'Upper dialog last' })
    upperLast.focus()
    lowerFocus.mockClear()
    upperFocus.mockClear()
    await user.tab()

    expect(upperFirst).toHaveFocus()
    expect(upperFocus).toHaveBeenCalled()
    expect(lowerFocus).not.toHaveBeenCalled()
  })

  it('restores a removed opener to the provided stable reader target', async () => {
    const user = userEvent.setup()
    render(<RemovedOpenerHarness />)

    await user.click(screen.getByRole('button', { name: 'Open temporary dialog' }))
    await user.click(screen.getByRole('button', { name: 'Close temporary dialog' }))

    expect(screen.queryByRole('button', { name: 'Open temporary dialog' })).not.toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Unrelated page action' })).not.toHaveFocus()
  })

  it('preserves the original page opener when a lower dialog unmounts out of order', async () => {
    const user = userEvent.setup()
    const upperClose = vi.fn()
    render(<RestoreChainHarness upperClose={upperClose} />)

    const pageOpener = screen.getByRole('button', { name: 'Page dialog opener' })
    await user.click(pageOpener)
    await user.click(screen.getByRole('button', { name: 'Open chain upper' }))
    fireEvent.click(screen.getByRole('button', { name: 'Remove lower out of order' }))
    expect(screen.queryByRole('dialog', { name: 'Chain lower' })).not.toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(upperClose).toHaveBeenCalledOnce()
    expect(pageOpener).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(upperClose).toHaveBeenCalledOnce()
  })

  it('uses the live replacement restore node when the opening fallback was removed', async () => {
    const user = userEvent.setup()
    render(<ReplacementFallbackHarness />)

    await user.click(screen.getByRole('button', { name: 'Open fallback dialog' }))
    await user.click(screen.getByRole('button', { name: 'Replace fallback and opener' }))
    expect(screen.queryByTestId('original-fallback')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close fallback dialog' }))

    expect(screen.getByTestId('replacement-fallback')).toHaveFocus()
  })

  it('moves focus through book, loading, chapter, and back transitions', async () => {
    const user = userEvent.setup()
    const request = deferred()
    render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => request.promise}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    expect(screen.getByRole('button', { name: 'Back to books' })).toHaveFocus()

    await act(async () => request.resolve([1, 2]))
    expect(screen.getByRole('button', { name: 'Chapter 1' })).toHaveFocus()

    await user.click(screen.getByRole('button', { name: 'Back to books' }))
    expect(screen.getByRole('searchbox', { name: 'Search Bible books' })).toHaveFocus()
  })

  it('moves focus to a stable loading control when retry unmounts', async () => {
    const user = userEvent.setup()
    const retryRequest = deferred()
    const loadChapters = vi.fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockReturnValueOnce(retryRequest.promise)
    render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={loadChapters}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(await screen.findByRole('button', { name: 'Try again' }))

    expect(screen.getByRole('button', { name: 'Back to books' })).toHaveFocus()
  })

  it('does not steal focus when chapter loading finishes after the user moves elsewhere', async () => {
    const user = userEvent.setup()
    const request = deferred()
    render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => request.promise}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    const close = screen.getByRole('button', { name: 'Close book picker' })
    close.focus()
    await act(async () => request.resolve([1]))

    expect(close).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Chapter 1' })).not.toHaveFocus()
  })

  it('invalidates a pending request before calling close from the close button', async () => {
    const user = userEvent.setup()
    const request = deferred()
    const onClose = vi.fn()
    render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => request.promise}
        onClose={onClose}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(screen.getByRole('button', { name: 'Close book picker' }))
    expect(onClose).toHaveBeenCalledOnce()

    await act(async () => request.resolve([99]))
    expect(screen.queryByRole('button', { name: 'Chapter 99' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Genesis' })).toBeInTheDocument()
  })

  it('invalidates a pending rejection before calling close from Escape', async () => {
    const user = userEvent.setup()
    const request = deferred()
    const onClose = vi.fn()
    render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={() => request.promise}
        onClose={onClose}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()

    await act(async () => request.reject(new Error('late failure')))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Genesis' })).toBeInTheDocument()
  })

  it('can start a successful load after a no-op close keeps the picker committed open', async () => {
    const user = userEvent.setup()
    const firstRequest = deferred()
    const secondRequest = deferred()
    const loadChapters = vi.fn()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={loadChapters}
        onClose={() => {}}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(screen.getByRole('button', { name: 'Close book picker' }))
    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await act(async () => secondRequest.resolve([4]))

    expect(screen.getByRole('button', { name: 'Chapter 4' })).toBeInTheDocument()
    expect(loadChapters).toHaveBeenCalledTimes(2)
  })

  it('keeps an old session response out of a reopened picker', async () => {
    const user = userEvent.setup()
    const firstRequest = deferred()
    const secondRequest = deferred()
    render(
      <ReopenRaceHarness
        firstRequest={firstRequest}
        secondRequest={secondRequest}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(screen.getByRole('button', { name: 'Close book picker' }))
    await user.click(screen.getByRole('button', { name: 'Reopen picker' }))
    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await act(async () => secondRequest.resolve([2]))
    expect(screen.getByRole('button', { name: 'Chapter 2' })).toBeInTheDocument()

    await act(async () => firstRequest.resolve([99]))
    expect(screen.getByRole('button', { name: 'Chapter 2' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Chapter 99' })).not.toBeInTheDocument()
  })

  it('resets and invalidates in-flight work when selectedCanon changes externally', async () => {
    const user = userEvent.setup()
    const firstRequest = deferred()
    const secondRequest = deferred()
    const loadChapters = vi.fn()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    const { rerender } = render(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="PROT66"
        loadChapters={loadChapters}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    rerender(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="CATH73"
        loadChapters={loadChapters}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByRole('searchbox')).toHaveFocus()
    await act(async () => firstRequest.resolve([99]))
    expect(screen.queryByRole('button', { name: 'Chapter 99' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    rerender(
      <BookPicker
        open
        books={['Genesis']}
        selectedCanon="ETHIO81"
        loadChapters={loadChapters}
        onClose={vi.fn()}
      />,
    )
    await act(async () => secondRequest.reject(new Error('late canon failure')))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Genesis' })).toBeInTheDocument()
  })

  it('does not let an abandoned close render invalidate the committed open session', async () => {
    const user = userEvent.setup()
    const request = deferred()
    render(<AbandonedCloseHarness request={request} />)

    await user.click(screen.getByRole('button', { name: 'Genesis' }))
    await user.click(screen.getByRole('button', { name: 'Attempt suspended close' }))
    expect(screen.getByRole('dialog', { name: 'Choose a book and chapter' })).toBeInTheDocument()
    expect(screen.queryByText('Suspended fallback')).not.toBeInTheDocument()

    await act(async () => request.resolve([7]))
    expect(screen.getByRole('button', { name: 'Chapter 7' })).toBeInTheDocument()
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
