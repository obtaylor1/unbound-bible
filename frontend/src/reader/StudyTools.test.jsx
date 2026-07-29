import { readFileSync } from 'node:fs'
import { useState } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import StudyTools from './StudyTools'
import { STUDY_TOOLS } from './studyToolRegistry'

const readerTokensCss = readFileSync('src/reader/readerTokens.css', 'utf8')

const reference = { book: 'Genesis', chapter: 1, verse: 2 }

function StudyToolsHarness({ initialReference = reference, initialDetails = {}, onNavigate }) {
  const [open, setOpen] = useState(false)
  const [currentReference, setCurrentReference] = useState(initialReference)
  const [details, setDetails] = useState(initialDetails)

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Open study tools</button>
      <button
        type="button"
        onClick={() => setCurrentReference({ book: 'Exodus', chapter: 3, verse: 14 })}
      >
        Change reference
      </button>
      <button
        type="button"
        onClick={() => setDetails({ historical_context: 'Updated details' })}
      >
        Refresh details
      </button>
      <StudyTools
        open={open}
        reference={currentReference}
        details={details}
        onClose={() => setOpen(false)}
        onNavigate={onNavigate}
      />
    </>
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('study tool registry', () => {
  it('is the single immutable mapping for all seven exact tool labels and routes', () => {
    expect(STUDY_TOOLS).toEqual([
      {
        id: 'context',
        kind: 'inline',
        label: 'Context',
        detailKeys: ['historical_context'],
      },
      {
        id: 'compare',
        kind: 'inline',
        label: 'Compare translations',
        detailKeys: ['translations'],
      },
      {
        id: 'languages',
        kind: 'inline',
        label: 'Original languages',
        detailKeys: ['original_language_insights', 'original_words'],
      },
      {
        id: 'cross-references',
        kind: 'inline',
        label: 'Cross-references',
        detailKeys: ['cross_references'],
      },
      { id: 'notes', kind: 'route', label: 'Notes', page: 'notes' },
      { id: 'ask', kind: 'route', label: 'Ask the Bible', page: 'chat' },
      {
        id: 'audit',
        kind: 'route',
        label: 'Decolonial audit',
        page: 'race-misuse',
      },
    ])
    expect(Object.isFrozen(STUDY_TOOLS)).toBe(true)
    expect(STUDY_TOOLS.every(Object.isFrozen)).toBe(true)
  })
})

describe('StudyTools', () => {
  it('renders nothing while closed and a uniquely labelled modal drawer while open', () => {
    const { rerender } = render(
      <StudyTools
        open={false}
        reference={reference}
        details={{}}
        onClose={vi.fn()}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    rerender(
      <>
        <StudyTools open reference={reference} details={{}} onClose={vi.fn()} />
        <StudyTools
          open
          reference={{ book: 'John', chapter: 3 }}
          details={{}}
          onClose={vi.fn()}
        />
      </>,
    )

    const dialogs = screen.getAllByRole('dialog')
    expect(dialogs).toHaveLength(2)
    expect(dialogs[0]).toHaveAttribute('aria-modal', 'true')
    expect(dialogs[0]).toHaveAccessibleName('Genesis 1:2')
    expect(dialogs[1]).toHaveAccessibleName('John 3')
    expect(dialogs[0].getAttribute('aria-labelledby')).not.toBe(
      dialogs[1].getAttribute('aria-labelledby'),
    )
    expect(
      within(dialogs[0]).getByRole('heading', { name: 'Context' }).id,
    ).not.toBe(
      within(dialogs[1]).getByRole('heading', { name: 'Context' }).id,
    )
    expect(within(dialogs[0]).getByText('Study Tools')).toBeVisible()
    expect(within(dialogs[0]).getByRole('button', { name: 'Close study tools' })).toBeVisible()
  })

  it('renders every registry tool as a word-labelled choice with inline active state', async () => {
    const user = userEvent.setup()
    render(
      <StudyTools
        open
        reference={reference}
        details={{ historical_context: 'First-century setting.' }}
        onClose={vi.fn()}
        onNavigate={vi.fn()}
      />,
    )

    const navigation = screen.getByRole('navigation', { name: 'Study tool choices' })
    expect(within(navigation).getAllByRole('button').map((button) => button.textContent)).toEqual(
      STUDY_TOOLS.map(({ label }) => label),
    )
    expect(screen.getByRole('button', { name: 'Context' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByText('First-century setting.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Compare translations' }))
    expect(screen.getByRole('button', { name: 'Compare translations' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    const panel = screen.getByRole('region', { name: 'Compare translations' })
    expect(panel).toHaveAttribute('aria-live', 'polite')
    expect(panel).toHaveAttribute('aria-atomic', 'false')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('calls route destinations with a normalized reference without changing the inline panel', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(
      <StudyTools
        open
        reference={{ book: '  Genesis ', chapter: '1', verse: '2' }}
        details={{ historical_context: 'Ancient setting.' }}
        onClose={vi.fn()}
        onNavigate={onNavigate}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Notes' }))
    await user.click(screen.getByRole('button', { name: 'Ask the Bible' }))
    await user.click(screen.getByRole('button', { name: 'Decolonial audit' }))

    expect(onNavigate.mock.calls).toEqual([
      ['notes', reference],
      ['chat', reference],
      ['race-misuse', reference],
    ])
    expect(screen.getByRole('button', { name: 'Context' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByText('Ancient setting.')).toBeInTheDocument()
  })

  it('disables route tools accessibly when navigation is unavailable', async () => {
    const user = userEvent.setup()
    render(<StudyTools open />)

    const notes = screen.getByRole('button', { name: 'Notes' })
    expect(notes).toBeDisabled()
    expect(notes).toHaveAccessibleDescription('Navigation unavailable')
    await user.click(notes)
    await user.click(screen.getByRole('button', { name: 'Close study tools' }))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.getByRole('dialog', { name: 'Current passage' })).toBeInTheDocument()
  })

  it('renders context scalars and labelled records semantically without unsafe object text', async () => {
    const user = userEvent.setup()
    render(
      <StudyTools
        open
        reference={reference}
        details={{
          historical_context: [
            'Roman Judea',
            { title: 'Setting', text: 'A village gathering', empty: null },
            {},
          ],
        }}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('list')).toHaveTextContent('Roman Judea')
    expect(screen.getByRole('list')).toHaveTextContent('Setting')
    expect(screen.getByRole('list')).toHaveTextContent('A village gathering')
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument()
    expect(screen.queryByText(/undefined|null/)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Context' }))
  })

  it('renders translation objects as a wrapping semantic table', async () => {
    const user = userEvent.setup()
    render(
      <StudyTools
        open
        reference={reference}
        details={{
          translations: {
            kjv: 'And the earth was without form.',
            web: { text: 'The earth was formless.', language: 'English' },
            empty: null,
          },
        }}
        onClose={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Compare translations' }))

    const table = screen.getByRole('table', { name: 'Compare translations' })
    expect(within(table).getByRole('columnheader', { name: 'Translation' })).toBeInTheDocument()
    expect(within(table).getByText('KJV')).toBeInTheDocument()
    expect(within(table).getByText('WEB')).toBeInTheDocument()
    expect(within(table).getByText('The earth was formless.')).toBeInTheDocument()
    expect(within(table).getByText('English')).toBeInTheDocument()
  })

  it('renders original-language arrays as a semantic description list with readable labels', async () => {
    const user = userEvent.setup()
    render(
      <StudyTools
        open
        reference={reference}
        details={{
          original_language_insights: [
            {
              text: 'רוּחַ',
              transliteration: 'ruach',
              strong_number: 'H7307',
              definition: 'wind, breath, spirit',
            },
          ],
        }}
        onClose={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Original languages' }))

    const list = screen.getByTestId('study-tool-description-list')
    expect(list.tagName).toBe('DL')
    expect(list).toHaveTextContent('רוּחַ')
    expect(list).toHaveTextContent('Transliteration')
    expect(list).toHaveTextContent('Strong number')
    expect(list).toHaveTextContent('wind, breath, spirit')
  })

  it('falls back to original_words and renders cross-reference records as semantic lists', async () => {
    const user = userEvent.setup()
    render(
      <StudyTools
        open
        reference={reference}
        details={{
          original_words: [
            { word_text: 'λόγος', language: 'Greek', definition: 'word or reason' },
          ],
          cross_references: [
            {
              target_book: 'John',
              target_chapter: 1,
              target_verse: 1,
              target_text: 'In the beginning was the Word.',
              description: 'Shared creation language',
            },
          ],
        }}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Original languages' }))
    expect(screen.getByText('λόγος')).toBeInTheDocument()
    expect(screen.getByText('word or reason')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cross-references' }))
    const list = screen.getByRole('list')
    expect(list).toHaveTextContent('John 1:1')
    expect(list).toHaveTextContent('In the beginning was the Word.')
    expect(list).toHaveTextContent('Shared creation language')
  })

  it('shows truthful empty states for verse and passage tools', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <StudyTools open reference={reference} details={null} onClose={vi.fn()} />,
    )
    expect(screen.getByText(
      'No verified context information is available for this verse.',
    )).toBeInTheDocument()

    rerender(
      <StudyTools
        open
        reference={{ book: 'Psalms', chapter: 23 }}
        details={{ translations: [null, {}, '', { text: null }] }}
        onClose={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Compare translations' }))
    expect(screen.getByText(
      'No verified compare translations information is available for this passage.',
    )).toBeInTheDocument()
  })

  it('announces refreshed and empty results through the labelled live panel', () => {
    const { rerender } = render(
      <StudyTools
        open
        reference={reference}
        details={{ historical_context: 'Verified historical setting.' }}
        onClose={vi.fn()}
      />,
    )

    const panel = screen.getByRole('region', { name: 'Context' })
    expect(panel).toHaveAttribute('aria-live', 'polite')
    expect(panel).toHaveTextContent('Verified historical setting.')

    rerender(
      <StudyTools
        open
        reference={reference}
        details={{ historical_context: 'Updated verified setting.' }}
        onClose={vi.fn()}
      />,
    )
    expect(panel).toHaveTextContent('Updated verified setting.')

    rerender(
      <StudyTools open reference={reference} details={{}} onClose={vi.fn()} />,
    )
    expect(panel).toHaveTextContent(
      'No verified context information is available for this verse.',
    )
  })

  it('normalizes missing and malformed references without leaking implementation values', () => {
    const malformed = {
      book: { name: 'Genesis' },
      chapter: Number.NaN,
      verse: undefined,
    }
    render(
      <StudyTools
        open
        reference={malformed}
        details={{ historical_context: { value: null } }}
        onClose={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: 'Current passage' })
    expect(dialog).toBeInTheDocument()
    expect(dialog).not.toHaveTextContent(/undefined|NaN|\[object Object\]|null/)
    expect(screen.getByText(
      'No verified context information is available for this passage.',
    )).toBeInTheDocument()
  })

  it('closes on its action and Escape, restores focus, and locks background scrolling', async () => {
    const user = userEvent.setup()
    render(<StudyToolsHarness />)
    const opener = screen.getByRole('button', { name: 'Open study tools' })

    await user.click(opener)
    expect(screen.getByRole('button', { name: 'Close study tools' })).toHaveFocus()
    expect(document.body.style.overflow).toBe('hidden')
    await user.click(screen.getByRole('button', { name: 'Close study tools' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
    expect(document.body.style.overflow).toBe('')

    await user.click(opener)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('resets Context on reopen and reference changes but not details rerenders or route actions', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(
      <StudyToolsHarness
        initialDetails={{
          historical_context: 'Context copy',
          translations: { kjv: 'Translation copy' },
        }}
        onNavigate={onNavigate}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Open study tools' }))
    await user.click(screen.getByRole('button', { name: 'Compare translations' }))
    await user.click(screen.getByRole('button', { name: 'Refresh details' }))
    await user.click(screen.getByRole('button', { name: 'Notes' }))
    expect(screen.getByRole('button', { name: 'Compare translations' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    await user.click(screen.getByRole('button', { name: 'Close study tools' }))
    await user.click(screen.getByRole('button', { name: 'Open study tools' }))
    expect(screen.getByRole('button', { name: 'Context' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    await user.click(screen.getByRole('button', { name: 'Compare translations' }))
    await user.click(screen.getByRole('button', { name: 'Change reference' }))
    expect(screen.getByRole('button', { name: 'Context' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Exodus 3:14')
  })
})

describe('StudyTools responsive styles', () => {
  it('defines a token-driven right drawer and mobile bottom sheet contract', () => {
    expect(readerTokensCss).toMatch(/\.study-tools__dialog\s*\{[^}]*width:\s*min\(31rem,\s*100vw\)/i)
    expect(readerTokensCss).toMatch(/\.study-tools__dialog\s*\{[^}]*overflow-y:\s*auto/i)
    expect(readerTokensCss).toMatch(/\.study-tools__dialog\s*\{[^}]*var\(--reader-surface\)/i)
    expect(readerTokensCss).toMatch(/\.study-tools__control\s*\{[^}]*min-height:\s*48px/i)
    expect(readerTokensCss).toMatch(
      /@media\s*\(max-width:\s*767px\)[\s\S]*\.study-tools__dialog\s*\{[^}]*max-height:\s*min\(78vh,\s*44rem\)/i,
    )
    expect(readerTokensCss).toMatch(
      /@media\s*\(max-width:\s*767px\)[\s\S]*\.study-tools__dialog\s*\{[^}]*inset:\s*auto\s+0\s+0/i,
    )
    const studyToolsCss = readerTokensCss.slice(readerTokensCss.indexOf('.study-tools {'))
      .split('@media (prefers-reduced-motion: reduce)')[0]
    expect(studyToolsCss).not.toContain('!important')
    expect(studyToolsCss).not.toMatch(/#[0-9a-f]{3,8}\b/i)
  })
})
