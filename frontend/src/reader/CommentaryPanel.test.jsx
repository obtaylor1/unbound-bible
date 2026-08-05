import { readFileSync } from 'node:fs'
import { useState } from 'react'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CommentaryPanel from './CommentaryPanel'

const readerTokensCss = readFileSync('src/reader/readerTokens.css', 'utf8')

const sources = [
  {
    id: 'john-gill',
    title: 'John Gill’s Exposition',
    abbreviation: 'Gill',
    author: 'John Gill',
    publication_period: '1746–1763',
    tradition: 'Reformed Baptist',
    language: 'English',
    attribution: 'Public-domain edition prepared by HelloAO',
  },
  {
    id: 'matthew-henry',
    title: 'Matthew Henry’s Commentary',
    author: 'Matthew Henry',
    publication_period: '1706',
    tradition: 'Presbyterian',
    language: 'English',
  },
]

function entry({
  body = 'The first verse establishes God as the author of creation.\n\nThe heavens and earth include all created things.',
  citation = 'John Gill, Exposition of Genesis 1:1',
  heading = 'The beginning',
  entryType = 'verse',
  start = 1,
  end = 1,
} = {}) {
  return {
    body,
    citation,
    heading,
    entry_type: entryType,
    scope: { verse_start: start, verse_end: end },
  }
}

function result({ availability = 'available', entries = [entry()], truncated = false } = {}) {
  return {
    reference: { book: 'Genesis', chapter: 1 },
    availability,
    truncated,
    source: sources[0],
    entries,
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve
    reject = nextReject
  })
  return { promise, resolve, reject }
}

function renderPanel(props = {}) {
  return render(
    <CommentaryPanel
      headingId="commentary-heading"
      reference={{ book: 'Genesis', chapter: 1 }}
      verses={[1, 2, 3]}
      loadSources={vi.fn().mockResolvedValue(sources)}
      loadEntries={vi.fn().mockResolvedValue(result())}
      {...props}
    />,
  )
}

beforeEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('CommentaryPanel requests and navigation', () => {
  it('opens with a chapter overview and switches to the selected verse without reloading sources', async () => {
    const loadSources = vi.fn().mockResolvedValue(sources)
    const loadEntries = vi.fn().mockResolvedValue(result())
    const view = renderPanel({ loadSources, loadEntries })

    expect(await screen.findByRole('heading', { name: 'Genesis 1 commentary' })).toBeVisible()
    expect(screen.getByRole('tab', { name: 'Chapter overview' })).toHaveAttribute('aria-selected', 'true')
    await waitFor(() => expect(loadEntries).toHaveBeenCalledWith(
      { source: 'john-gill', book: 'Genesis', chapter: 1 },
      expect.any(AbortSignal),
    ))

    view.rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Genesis', chapter: 1, verse: 2 }}
        verses={[1, 2, 3]}
        loadSources={loadSources}
        loadEntries={loadEntries}
      />,
    )

    expect(await screen.findByText('Commentary for Genesis 1:2')).toBeVisible()
    expect(screen.getByRole('tab', { name: 'Selected verse' })).toHaveAttribute('aria-selected', 'true')
    expect(loadSources).toHaveBeenCalledOnce()
    await waitFor(() => expect(loadEntries).toHaveBeenLastCalledWith(
      { source: 'john-gill', book: 'Genesis', chapter: 1, verse: 2 },
      expect.any(AbortSignal),
    ))
  })

  it('uses only an installed saved source and persists a new source choice', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem('unbound_commentary_source', 'matthew-henry')
    const loadEntries = vi.fn().mockResolvedValue(result())
    renderPanel({ loadEntries })

    const select = await screen.findByRole('combobox', { name: 'Commentary source' })
    expect(select).toHaveValue('matthew-henry')
    await user.selectOptions(select, 'john-gill')
    expect(window.localStorage.getItem('unbound_commentary_source')).toBe('john-gill')
    await waitFor(() => expect(loadEntries).toHaveBeenLastCalledWith(
      expect.objectContaining({ source: 'john-gill' }),
      expect.any(AbortSignal),
    ))
  })

  it('ignores an uninstalled saved source and survives unavailable local storage', async () => {
    window.localStorage.setItem('unbound_commentary_source', 'unknown-source')
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    renderPanel()

    expect(await screen.findByRole('combobox', { name: 'Commentary source' })).toHaveValue('john-gill')
    expect(getItem).toHaveBeenCalled()
  })

  it('returns to overview and moves only through existing sorted valid verses', async () => {
    const user = userEvent.setup()
    function Harness() {
      const [verse, setVerse] = useState(4)
      return (
        <CommentaryPanel
          headingId="commentary-heading"
          reference={{ book: 'Genesis', chapter: 1, verse }}
          verses={[8, 2, 4, 4, 0, -1, 3.5, '6']}
          onSelectVerse={setVerse}
          loadSources={vi.fn().mockResolvedValue(sources)}
          loadEntries={vi.fn().mockResolvedValue(result())}
        />
      )
    }
    render(<Harness />)

    await user.click(await screen.findByRole('button', { name: 'Previous verse' }))
    expect(await screen.findByText('Commentary for Genesis 1:2')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Previous verse' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Next verse' }))
    expect(await screen.findByText('Commentary for Genesis 1:4')).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Chapter overview' }))
    expect(await screen.findByText('Commentary for Genesis 1')).toBeVisible()
  })

  it('disables selected verse when no verse exists', async () => {
    renderPanel({ reference: { book: 'Genesis', chapter: 1 } })
    expect(await screen.findByRole('tab', { name: 'Selected verse' })).toBeDisabled()
  })

  it('aborts source loading on unmount and entry loading on a reference change', async () => {
    const sourceRequest = deferred()
    const loadSources = vi.fn((signal) => {
      signal.addEventListener('abort', () => sourceRequest.reject(new DOMException('aborted', 'AbortError')))
      return sourceRequest.promise
    })
    const first = renderPanel({ loadSources })
    await waitFor(() => expect(loadSources).toHaveBeenCalledOnce())
    const sourceSignal = loadSources.mock.calls[0][0]
    first.unmount()
    expect(sourceSignal.aborted).toBe(true)

    const entryRequests = []
    const loadEntries = vi.fn((request, signal) => {
      const pending = deferred()
      entryRequests.push({ request, signal, pending })
      return pending.promise
    })
    const stableSources = vi.fn().mockResolvedValue(sources)
    const view = renderPanel({ loadEntries, loadSources: stableSources })
    await waitFor(() => expect(entryRequests).toHaveLength(1))
    view.rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Genesis', chapter: 2 }}
        verses={[1]}
        loadSources={stableSources}
        loadEntries={loadEntries}
      />,
    )
    await waitFor(() => expect(entryRequests).toHaveLength(2))
    expect(entryRequests[0].signal.aborted).toBe(true)
  })

  it('suppresses stale responses that settle after a newer request', async () => {
    const requests = []
    const loadEntries = vi.fn(() => {
      const pending = deferred()
      requests.push(pending)
      return pending.promise
    })
    const loadSources = vi.fn().mockResolvedValue(sources)
    const view = renderPanel({ loadSources, loadEntries })
    await waitFor(() => expect(requests).toHaveLength(1))
    view.rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Genesis', chapter: 1, verse: 2 }}
        verses={[1, 2]}
        loadSources={loadSources}
        loadEntries={loadEntries}
      />,
    )
    await waitFor(() => expect(requests).toHaveLength(2))
    requests[1].resolve(result({ entries: [entry({ body: 'New verse response' })] }))
    expect(await screen.findByText('New verse response')).toBeVisible()
    await act(async () => {
      requests[0].resolve(result({ entries: [entry({ body: 'Stale chapter response' })] }))
      await requests[0].promise
    })
    expect(screen.getByText('New verse response')).toBeVisible()
    expect(screen.queryByText('Stale chapter response')).not.toBeInTheDocument()
  })

  it('immediately removes owned entries and an expanded dialog when the reference changes', async () => {
    const user = userEvent.setup()
    const second = deferred()
    const loadSources = vi.fn().mockResolvedValue(sources)
    const loadEntries = vi.fn()
      .mockResolvedValueOnce(result({ entries: [entry({ body: 'Owned chapter response' })] }))
      .mockReturnValueOnce(second.promise)
    const view = renderPanel({ loadSources, loadEntries })
    await screen.findByText('Owned chapter response')
    await user.click(screen.getByRole('button', { name: 'Expand commentary reading view' }))
    expect(screen.getByRole('dialog')).toBeVisible()

    view.rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Exodus', chapter: 2 }}
        verses={[1, 2]}
        loadSources={loadSources}
        loadEntries={loadEntries}
      />,
    )

    expect(screen.queryByText('Owned chapter response')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Expand commentary reading view' })).not.toBeInTheDocument()
    expect(screen.getByText(/Loading commentary for Exodus 2/)).toBeVisible()
  })

  it('immediately removes the previous source result when another source is chosen', async () => {
    const user = userEvent.setup()
    const second = deferred()
    const loadEntries = vi.fn()
      .mockResolvedValueOnce(result({ entries: [entry({ body: 'John Gill owned note' })] }))
      .mockReturnValueOnce(second.promise)
    renderPanel({ loadEntries })
    await screen.findByText('John Gill owned note')
    await user.click(screen.getByRole('button', { name: 'Expand commentary reading view' }))
    expect(screen.getByRole('dialog')).toBeVisible()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Commentary source' }), 'matthew-henry')
    expect(screen.queryByText('John Gill owned note')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Expand commentary reading view' })).not.toBeInTheDocument()
  })

  it('never shows an error owned by an old reference or source', async () => {
    const user = userEvent.setup()
    const delayedReference = deferred()
    const delayedSource = deferred()
    const loadSources = vi.fn().mockResolvedValue(sources)
    const loadEntries = vi.fn()
      .mockRejectedValueOnce(new Error('old request'))
      .mockReturnValueOnce(delayedReference.promise)
      .mockRejectedValueOnce(new Error('old source'))
      .mockReturnValueOnce(delayedSource.promise)
    const view = renderPanel({ loadSources, loadEntries })
    expect(await screen.findByRole('alert')).toHaveTextContent('Commentary could not be loaded')

    view.rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Exodus', chapter: 2 }}
        verses={[1]}
        loadSources={loadSources}
        loadEntries={loadEntries}
      />,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText(/Loading commentary for Exodus 2/)).toBeVisible()

    await act(async () => {
      delayedReference.resolve(result())
      await delayedReference.promise
    })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Expand commentary reading view' })).toBeVisible())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Commentary source' }), 'matthew-henry')
    expect(await screen.findByRole('alert')).toHaveTextContent('Commentary could not be loaded')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Commentary source' }), 'john-gill')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText(/Loading commentary for Exodus 2/)).toBeVisible()
  })

  it('implements labelled controlled tabpanels and keyboard tab activation', async () => {
    const user = userEvent.setup()
    const onSelectVerse = vi.fn()
    renderPanel({
      reference: { book: 'Genesis', chapter: 1, verse: 2 },
      onSelectVerse,
    })
    const overview = await screen.findByRole('tab', { name: 'Chapter overview' })
    const selected = screen.getByRole('tab', { name: 'Selected verse' })
    const panel = screen.getByRole('tabpanel')
    expect(selected).toHaveAttribute('tabindex', '0')
    expect(overview).toHaveAttribute('tabindex', '-1')
    expect(selected).toHaveAttribute('aria-controls', panel.id)
    expect(panel).toHaveAttribute('aria-labelledby', selected.id)
    const overviewPanel = document.getElementById(overview.getAttribute('aria-controls'))
    expect(overviewPanel).toHaveAttribute('role', 'tabpanel')
    expect(overviewPanel).toHaveAttribute('hidden')

    selected.focus()
    await user.keyboard('{End}')
    expect(onSelectVerse).not.toHaveBeenCalled()
    await user.keyboard('{Home}')
    expect(onSelectVerse).toHaveBeenCalledWith(null)
  })

  it('moves between enabled tabs with ArrowLeft and ArrowRight', async () => {
    const user = userEvent.setup()
    const onSelectVerse = vi.fn()
    renderPanel({
      reference: { book: 'Genesis', chapter: 1, verse: 2 },
      onSelectVerse,
    })
    const overview = await screen.findByRole('tab', { name: 'Chapter overview' })
    const selected = screen.getByRole('tab', { name: 'Selected verse' })
    selected.focus()
    await user.keyboard('{ArrowLeft}')
    expect(overview).toHaveFocus()
    expect(onSelectVerse).toHaveBeenLastCalledWith(null)
    const calls = onSelectVerse.mock.calls.length
    await user.keyboard('{ArrowRight}')
    expect(selected).toHaveFocus()
    expect(onSelectVerse).toHaveBeenCalledTimes(calls)
  })
})

describe('CommentaryPanel availability and reading tools', () => {
  it('shows an understandable loading state', async () => {
    const pending = deferred()
    renderPanel({ loadEntries: vi.fn().mockReturnValue(pending.promise) })
    expect(await screen.findByText(/Loading commentary for Genesis 1/)).toHaveAttribute('role', 'status')
    expect(screen.getByRole('region', { name: 'Genesis 1 commentary' })).toHaveAttribute('aria-busy', 'true')
  })

  it('shows no-entry and incomplete-coverage explanations', async () => {
    const { rerender } = renderPanel({ loadEntries: vi.fn().mockResolvedValue(result({ availability: 'no_entry', entries: [] })) })
    expect(await screen.findByText('No commentary entry for Genesis 1')).toBeVisible()

    const incompleteLoader = vi.fn().mockResolvedValue(result({ availability: 'coverage_incomplete', entries: [] }))
    rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Genesis', chapter: 2 }}
        verses={[1]}
        loadSources={vi.fn().mockResolvedValue(sources)}
        loadEntries={incompleteLoader}
      />,
    )
    expect(await screen.findByText('This source has incomplete coverage for Genesis 2')).toBeVisible()
  })

  it('labels wider ranges and warns when results were truncated', async () => {
    renderPanel({
      reference: { book: 'Genesis', chapter: 1, verse: 2 },
      loadEntries: vi.fn().mockResolvedValue(result({
        availability: 'wider_range',
        truncated: true,
        entries: [entry({ start: 1, end: 3 })],
      })),
    })
    expect(await screen.findByText('Covers verses 1–3')).toBeVisible()
    expect(screen.getByText('More matching commentary is available than can be shown here.')).toBeVisible()
  })

  it('offers working next actions for missing, incomplete, wider-range, and truncated results', async () => {
    const user = userEvent.setup()
    const onSelectVerse = vi.fn()
    const loadEntries = vi.fn().mockResolvedValue(result({ availability: 'no_entry', entries: [] }))
    const view = renderPanel({
      reference: { book: 'Genesis', chapter: 1, verse: 2 },
      onSelectVerse,
      loadEntries,
    })
    await user.click(await screen.findByRole('button', { name: 'View chapter overview' }))
    expect(onSelectVerse).toHaveBeenCalledWith(null)
    await user.click(screen.getByRole('button', { name: 'Choose another commentary source' }))
    expect(screen.getByRole('combobox', { name: 'Commentary source' })).toHaveValue('matthew-henry')

    const widerLoader = vi.fn().mockResolvedValue(result({
      availability: 'wider_range',
      entries: [entry({ start: 1, end: 3 })],
    }))
    view.rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Genesis', chapter: 1, verse: 2 }}
        verses={[1, 2, 3]}
        onSelectVerse={onSelectVerse}
        loadSources={vi.fn().mockResolvedValue(sources)}
        loadEntries={widerLoader}
      />,
    )
    await user.click(await screen.findByRole('button', { name: 'Read covered passage from verse 1' }))
    expect(onSelectVerse).toHaveBeenLastCalledWith(1)

    const truncatedLoader = vi.fn().mockResolvedValue(result({ truncated: true }))
    view.rerender(
      <CommentaryPanel
        headingId="commentary-heading"
        reference={{ book: 'Genesis', chapter: 1 }}
        verses={[3, 1, 2]}
        onSelectVerse={onSelectVerse}
        loadSources={vi.fn().mockResolvedValue(sources)}
        loadEntries={truncatedLoader}
      />,
    )
    await user.click(await screen.findByRole('button', { name: 'Narrow commentary to verse 1' }))
    expect(onSelectVerse).toHaveBeenLastCalledWith(1)
  })

  it('offers overview for incomplete coverage and disables source switching when no alternative exists', async () => {
    const user = userEvent.setup()
    const onSelectVerse = vi.fn()
    renderPanel({
      reference: { book: 'Genesis', chapter: 1, verse: 2 },
      onSelectVerse,
      loadSources: vi.fn().mockResolvedValue([sources[0]]),
      loadEntries: vi.fn().mockResolvedValue(result({ availability: 'coverage_incomplete', entries: [] })),
    })
    await user.click(await screen.findByRole('button', { name: 'View chapter overview' }))
    expect(onSelectVerse).toHaveBeenCalledWith(null)
    expect(screen.getByRole('button', { name: 'Choose another commentary source' })).toBeDisabled()
  })

  it('shows a safe error and retries the exact request', async () => {
    const user = userEvent.setup()
    const loadEntries = vi.fn()
      .mockRejectedValueOnce(new Error('database password leaked'))
      .mockResolvedValueOnce(result())
    renderPanel({ loadEntries })

    expect(await screen.findByRole('alert')).toHaveTextContent('Commentary could not be loaded')
    expect(screen.queryByText(/password leaked/i)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry loading commentary' }))
    expect(await screen.findByText('The first verse establishes God as the author of creation.')).toBeVisible()
    expect(loadEntries).toHaveBeenCalledTimes(2)
  })

  it('handles a missing source catalog and allows retrying it', async () => {
    const user = userEvent.setup()
    const loadSources = vi.fn()
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce(sources)
    renderPanel({ loadSources })
    expect(await screen.findByText('No commentary sources are installed.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Retry loading commentary sources' }))
    expect(await screen.findByRole('combobox', { name: 'Commentary source' })).toHaveValue('john-gill')
  })

  it('distinguishes a rejected source request from an empty catalog and recovers on retry', async () => {
    const user = userEvent.setup()
    const loadSources = vi.fn()
      .mockRejectedValueOnce(new Error('private upstream detail'))
      .mockResolvedValueOnce(sources)
    renderPanel({ loadSources })
    expect(await screen.findByRole('alert')).toHaveTextContent('Commentary sources could not be loaded')
    expect(screen.queryByText('No commentary sources are installed.')).not.toBeInTheDocument()
    expect(screen.queryByText(/private upstream/i)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry loading commentary sources' }))
    expect(await screen.findByRole('combobox', { name: 'Commentary source' })).toHaveValue('john-gill')
  })

  it('filters as plain text without interpreting or injecting markup', async () => {
    const user = userEvent.setup()
    renderPanel({ loadEntries: vi.fn().mockResolvedValue(result({ entries: [
      entry({ heading: 'Creation note', body: '<img src=x onerror=alert(1)> literal record' }),
      entry({ heading: 'Second note', body: 'A separate meditation' }),
    ] })) })

    const search = await screen.findByRole('searchbox', { name: 'Search this commentary' })
    await user.type(search, '<img')
    const literal = screen.getByText('<img src=x onerror=alert(1)> literal record')
    expect(literal).toBeVisible()
    expect(literal.closest('article')).toHaveClass('commentary-panel__entry--search-match')
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByText('A separate meditation')).not.toBeInTheDocument()
    expect(document.querySelector('mark')).toBeNull()
  })

  it('copies entry text and citations only from labelled button actions and announces outcomes', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    renderPanel()

    await user.click(await screen.findByRole('button', { name: 'Copy commentary text' }))
    expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining('The first verse establishes God'))
    expect(screen.getByRole('status', { name: 'Copy status' })).toHaveTextContent('Commentary text copied')

    writeText.mockRejectedValueOnce(new Error('denied'))
    await user.click(screen.getByRole('button', { name: 'Copy commentary citation' }))
    expect(writeText).toHaveBeenLastCalledWith('John Gill, Exposition of Genesis 1:1')
    expect(screen.getByRole('status', { name: 'Copy status' })).toHaveTextContent('Citation could not be copied')
  })

  it('replaces the live status node when an identical copy outcome repeats', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    renderPanel()
    const copy = await screen.findByRole('button', { name: 'Copy commentary text' })
    await user.click(copy)
    const firstAnnouncement = screen.getByRole('status', { name: 'Copy status' })
    await user.click(copy)
    const secondAnnouncement = screen.getByRole('status', { name: 'Copy status' })
    expect(secondAnnouncement).not.toBe(firstAnnouncement)
    expect(secondAnnouncement).toHaveTextContent('Commentary text copied')
    expect(writeText).toHaveBeenCalledTimes(2)
  })

  it('opens an accessible expanded dialog, repeats filtered articles, and restores focus when closed', async () => {
    const user = userEvent.setup()
    renderPanel()
    const open = await screen.findByRole('button', { name: 'Expand commentary reading view' })
    open.focus()
    await user.click(open)

    const dialog = screen.getByRole('dialog', { name: 'Expanded Genesis 1 commentary' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByText('The first verse establishes God as the author of creation.')).toBeVisible()
    const close = within(dialog).getByRole('button', { name: 'Close expanded commentary' })
    expect(close).toHaveFocus()
    await user.click(close)
    expect(screen.queryByRole('dialog', { name: /Expanded Genesis/ })).not.toBeInTheDocument()
    expect(open).toHaveFocus()
  })

  it('closes the expanded dialog with Escape and restores focus to the word-labelled opener', async () => {
    const user = userEvent.setup()
    renderPanel()
    const open = await screen.findByRole('button', { name: 'Expand commentary reading view' })
    await user.click(open)
    expect(screen.getByRole('dialog')).toBeVisible()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(open).toHaveFocus()
  })

  it('announces success, failure, and repeated copy outcomes inside the modal dialog only', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn()
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('denied'))
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    renderPanel()
    await user.click(await screen.findByRole('button', { name: 'Expand commentary reading view' }))
    const dialog = screen.getByRole('dialog')
    const dialogCopy = within(dialog).getByRole('button', { name: 'Copy commentary text' })

    await user.click(dialogCopy)
    const first = within(dialog).getByRole('status', { name: 'Copy status' })
    expect(first).toHaveTextContent('Commentary text copied')
    expect(screen.getAllByRole('status', { name: 'Copy status' })).toHaveLength(1)
    await user.click(dialogCopy)
    const second = within(dialog).getByRole('status', { name: 'Copy status' })
    expect(second).not.toBe(first)
    expect(second).toHaveTextContent('Commentary text copied')
    await user.click(dialogCopy)
    expect(within(dialog).getByRole('status', { name: 'Copy status' })).toHaveTextContent(
      'Commentary text could not be copied',
    )
  })

  it('does not move an old copy announcement between the base panel and modal', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    renderPanel()
    await user.click(await screen.findByRole('button', { name: 'Copy commentary text' }))
    expect(screen.getByRole('status', { name: 'Copy status' })).toHaveTextContent('Commentary text copied')

    await user.click(screen.getByRole('button', { name: 'Expand commentary reading view' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).queryByRole('status', { name: 'Copy status' })).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Copy commentary citation' }))
    expect(within(dialog).getByRole('status', { name: 'Copy status' })).toHaveTextContent('Citation copied')

    await user.click(within(dialog).getByRole('button', { name: 'Close expanded commentary' }))
    expect(screen.queryByRole('status', { name: 'Copy status' })).not.toBeInTheDocument()
  })

  it('preserves body paragraphs, omits absent headings, and identifies the source on every article', async () => {
    renderPanel({ loadEntries: vi.fn().mockResolvedValue(result({ entries: [entry({ heading: '', body: 'First paragraph.\n\nSecond paragraph.' })] })) })
    const article = await screen.findByRole('article')
    expect(within(article).queryByRole('heading')).not.toBeInTheDocument()
    expect(within(article).getAllByText(/paragraph\./)).toHaveLength(2)
    expect(within(article).getByText('John Gill’s Exposition')).toBeVisible()
    expect(within(article).getByText('Gill')).toBeVisible()

    await userEvent.setup().click(screen.getByRole('button', { name: 'Expand commentary reading view' }))
    const dialogArticle = within(screen.getByRole('dialog')).getByRole('article')
    expect(within(dialogArticle).getByText('John Gill’s Exposition')).toBeVisible()
  })
})

describe('CommentaryPanel presentation contract', () => {
  it('defines readable editorial typography, large controls, themes, mobile containment, and reduced motion', () => {
    expect(readerTokensCss).toMatch(/\.commentary-panel__body\s*\{[^}]*font-family:\s*Georgia,\s*'Times New Roman',\s*serif/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__body\s*\{[^}]*font-size:\s*var\(--reader-font-size\)/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__body\s*\{[^}]*line-height:\s*1\.75/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__body\s*\{[^}]*max-width:\s*70ch/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__control\s*\{[^}]*min-height:\s*48px/i)
    expect(readerTokensCss).toMatch(/\[data-reader-theme='light'\][^{]*\.commentary-panel/i)
    expect(readerTokensCss).toMatch(/@media\s*\(max-width:\s*767px\)[\s\S]*\.commentary-panel/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel\s*\{[^}]*min-width:\s*0/i)
    expect(readerTokensCss).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*\.commentary-panel/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__entry\s*\{[^}]*var\(--reader-surface\)/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__callout--incomplete\s*\{[^}]*var\(--reader-gold\)/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__callout--truncated\s*\{[^}]*var\(--reader-gold\)/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__range-badge\s*\{[^}]*var\(--reader-teal\)/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__entry--search-match\s*\{[^}]*var\(--reader-teal\)/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__tab\[aria-selected='true'\]\s*\{[^}]*box-shadow:\s*inset\s+0\s+-3px\s+0\s+var\(--reader-gold\)/i)
    expect(readerTokensCss).toMatch(/@media\s*\(max-width:\s*767px\)[\s\S]*\.commentary-panel\s*\{[^}]*env\(safe-area-inset-bottom\)/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__expanded\s*\{[^}]*overflow-x:\s*hidden/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__eyebrow\s*\{[^}]*font-size:\s*0\.875rem/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__citation cite\s*\{[^}]*font-size:\s*0\.875rem/i)
    expect(readerTokensCss).toMatch(/\.commentary-panel__quiet-action\s*\{[^}]*font-size:\s*0\.875rem/i)
  })
})
