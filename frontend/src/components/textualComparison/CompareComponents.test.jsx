import { useRef, useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ComparisonToolbar from './ComparisonToolbar'
import TranslationSelector from './TranslationSelector'
import ComparisonSummary from './ComparisonSummary'
import TranslationComparisonCard from './TranslationComparisonCard'
import ComparisonStudyDrawer from './ComparisonStudyDrawer'
import { buildSourceState, registerInstalledSources, TRANSLATION_BY_KEY } from './comparisonModel'

vi.mock('../StudyAssistantSidebar', () => ({
  default: ({ book, chapter, verse, initialTab, initialInsightSubTab }) => (
    <div data-testid="existing-study-assistant" data-active-tab={initialTab} data-active-tool={initialInsightSubTab}>Study content for {book} {chapter}:{verse}</div>
  ),
}))

const toolbarProps = {
  books: ['Genesis', 'Exodus'],
  chapters: [1, 2],
  verses: [1, 2, 3],
  book: 'Genesis',
  chapter: '1',
  verse: '1',
  viewMode: 'verse',
  baseTranslation: 'geez1980-research',
  selectedTranslations: ['geez1980-research', 'kjv'],
  highlightDifferences: true,
  onBookChange: vi.fn(),
  onChapterChange: vi.fn(),
  onVerseChange: vi.fn(),
  onViewModeChange: vi.fn(),
  onBaseTranslationChange: vi.fn(),
  onHighlightDifferencesChange: vi.fn(),
  onOpenStudyTools: vi.fn(),
}

const installedFixture = [
  { key: 'geez1980-research', code: 'GEEZ1980-RESEARCH', name: "Ge'ez Bible (1980 EC) — Research Use", tradition: 'Ethiopian Orthodox Tewahedo', year: '1980 EC', language: "Ge'ez", categories: ['ethiopian'] },
  { key: 'kjv', code: 'KJV', name: 'King James Version', tradition: 'Protestant', year: '1611 / 1769', language: 'English', categories: ['protestant'] },
  { key: 'asv', code: 'ASV', name: 'American Standard Version', tradition: 'Protestant', year: '1901', language: 'English', categories: ['protestant'] },
  { key: 'web', code: 'WEB', name: 'World English Bible', tradition: 'Protestant', year: '2001', language: 'English', categories: ['protestant'] },
  { key: 'webbe', code: 'WEBBE', name: 'World English Bible, British Edition', tradition: 'Protestant', year: '2023', language: 'English', categories: ['protestant'] },
  { key: '1en_ch', code: '1EN_CH', name: '1 Enoch, R. H. Charles', tradition: 'Ethiopian Pseudepigrapha', year: '1912', language: 'English', categories: ['ethiopian'] },
]

beforeEach(() => registerInstalledSources(installedFixture))

describe('ComparisonToolbar', () => {
  it('groups passage, view, and comparison controls with visible labels', () => {
    render(<ComparisonToolbar {...toolbarProps} />)

    expect(screen.getByRole('group', { name: 'Passage' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'View' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Comparison' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Book' })).toHaveValue('Genesis')
    expect(screen.getByRole('combobox', { name: 'Chapter' })).toHaveValue('1')
    expect(screen.getByRole('combobox', { name: 'Verse' })).toHaveValue('1')
    expect(screen.getByRole('button', { name: 'Verse view' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Open Study Tools' })).toBeInTheDocument()
  })

  it('reports toolbar changes through callbacks', async () => {
    const user = userEvent.setup()
    const onViewModeChange = vi.fn()
    const onOpenStudyTools = vi.fn()
    render(
      <ComparisonToolbar
        {...toolbarProps}
        onViewModeChange={onViewModeChange}
        onOpenStudyTools={onOpenStudyTools}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Chapter view' }))
    await user.click(screen.getByRole('button', { name: 'Open Study Tools' }))
    expect(onViewModeChange).toHaveBeenCalledWith('chapter')
    expect(onOpenStudyTools).toHaveBeenCalledOnce()
  })

  it('disables verse selection in chapter view', () => {
    render(<ComparisonToolbar {...toolbarProps} viewMode="chapter" />)
    expect(screen.getByRole('combobox', { name: 'Verse' })).toBeDisabled()
  })
})

describe('TranslationSelector', () => {
  it('shows compact translations, filters, and comparison capacity', () => {
    render(
      <TranslationSelector
        selected={['geez1980-research', 'kjv']}
        baseTranslation="geez1980-research"
        onToggle={vi.fn()}
      />,
    )

    expect(screen.getByTestId('translation-selector')).toBeInTheDocument()
    expect(screen.getByText('Comparing 2 translations')).toBeInTheDocument()
    expect(screen.getByText('Add up to 2 more')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('checkbox', { name: /Ge'ez Bible \(1980 EC\)/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /King James Version/ })).toBeChecked()
  })

  it('filters by Ethiopian category and search query', async () => {
    const user = userEvent.setup()
    render(
      <TranslationSelector
        selected={['geez1980-research', 'kjv']}
        baseTranslation="geez1980-research"
        onToggle={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Ethiopian' }))
    expect(screen.getByRole('button', { name: 'Ethiopian' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('checkbox', { name: /King James Version/ })).not.toBeInTheDocument()

    await user.type(screen.getByRole('searchbox', { name: 'Search translations' }), 'enoch')
    expect(screen.getByRole('checkbox', { name: /1 Enoch, R. H. Charles/ })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: /Ge'ez Bible \(1980 EC\)/ })).not.toBeInTheDocument()
  })

  it('calls onToggle and disables unselected rows at the four-source limit', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    render(
      <TranslationSelector
        selected={['geez1980-research', 'kjv', 'asv', 'web']}
        baseTranslation="geez1980-research"
        onToggle={onToggle}
      />,
    )

    expect(screen.getByText('Maximum of 4 translations selected')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /World English Bible, British Edition/ })).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /King James Version/ }))
    expect(onToggle).toHaveBeenCalledWith('kjv')
  })
})

describe('ComparisonSummary', () => {
  it('gives beginners a clear summary and three next actions', () => {
    render(
      <ComparisonSummary
        reference="Genesis 1:1"
        summary={{
          availableCount: 2,
          differenceCount: 3,
          message: 'Both available sources describe God as the creator at the beginning of creation.',
        }}
        onShowDifferences={vi.fn()}
        onExplainVerse={vi.fn()}
        onViewOriginalWords={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Genesis 1:1 comparison' })).toBeInTheDocument()
    expect(screen.getByText(/Both available sources describe God/)).toBeInTheDocument()
    expect(screen.getByText('3 wording differences found')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show Differences' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Explain This Verse' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View Original Words' })).toBeInTheDocument()
  })
})

describe('TranslationComparisonCard', () => {
  const commonProps = {
    reference: 'Genesis 1:1',
    source: installedFixture.find(({ key }) => key === 'kjv'),
    state: { kind: 'available', text: 'In the beginning God created the heaven and the earth.' },
    baseText: 'At first God made the heaven and the earth.',
    isBase: false,
    highlightDifferences: true,
    differenceCount: 3,
    bookmarked: false,
    onBookmark: vi.fn(),
    onOpenNotes: vi.fn(),
    onChooseSource: vi.fn(),
  }

  it('uses a consistent source hierarchy and visible difference state', () => {
    render(<TranslationComparisonCard {...commonProps} />)

    expect(screen.getByRole('article', { name: 'King James Version' })).toBeInTheDocument()
    expect(screen.getByText('KJV')).toBeInTheDocument()
    expect(screen.getByText('Genesis 1:1')).toBeInTheDocument()
    expect(screen.getByText('3 differences')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Bookmark Genesis 1:1 in KJV' })).toBeInTheDocument()
  })

  it('does not mark every word when the selected base text is unavailable', () => {
    const { container } = render(
      <TranslationComparisonCard {...commonProps} baseText="" differenceCount={0} />,
    )

    expect(container.querySelectorAll('mark')).toHaveLength(0)
  })

  it('uses an accurate compact notice for missing Ethiopian text', () => {
    render(
      <TranslationComparisonCard
        {...commonProps}
        source={TRANSLATION_BY_KEY['geez1980-research']}
        state={buildSourceState({ key: 'geez1980-research', book: 'Genesis', text: null })}
        isBase
      />,
    )

    expect(screen.getByText('Text unavailable')).toBeInTheDocument()
    expect(screen.getByText(/does not currently provide this passage/)).toBeInTheDocument()
    expect(screen.queryByText('Canon Exclusion')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Learn more about text availability' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose another source' })).toBeInTheDocument()
    expect(screen.getByText('Base reference')).toBeInTheDocument()
  })

  it('renders attribution and a safe permanent source link accessibly', () => {
    render(
      <TranslationComparisonCard
        {...commonProps}
        source={{
          ...commonProps.source,
          sourceLabel: "Wikisource Meqabyan translation from Ge'ez",
          attribution: 'Wikisource contributors, licensed CC BY-SA 4.0.',
          provenanceUrl: 'https://en.wikisource.org/w/index.php?oldid=16044809',
        }}
      />,
    )

    expect(screen.getByText('Wikisource contributors, licensed CC BY-SA 4.0.')).toBeVisible()
    const link = screen.getByRole('link', {
      name: "View source record for Wikisource Meqabyan translation from Ge'ez",
    })
    expect(link).toHaveAttribute('href', 'https://en.wikisource.org/w/index.php?oldid=16044809')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('never links an unsafe provenance value', () => {
    render(
      <TranslationComparisonCard
        {...commonProps}
        source={{
          ...commonProps.source,
          attribution: 'Archive attribution remains visible.',
          provenanceUrl: 'javascript:alert(1)',
        }}
      />,
    )

    expect(screen.getByText('Archive attribution remains visible.')).toBeVisible()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})

function DrawerHarness() {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef(null)
  return (
    <>
      <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>Open Study Tools</button>
      <ComparisonStudyDrawer
        open={open}
        triggerRef={triggerRef}
        book="Genesis"
        chapter={1}
        verse={1}
        onClose={() => setOpen(false)}
        onAddNote={vi.fn()}
      />
    </>
  )
}

describe('ComparisonStudyDrawer', () => {
  it('is closed by default and exposes one clear tool row when opened', async () => {
    const user = userEvent.setup()
    render(<DrawerHarness />)

    expect(screen.queryByRole('dialog', { name: 'Study Tools' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open Study Tools' }))

    expect(screen.getByRole('dialog', { name: 'Study Tools' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Insights' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Cross-References' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Words' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Notes' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask Study Assistant' })).toBeInTheDocument()
  })

  it('closes with Escape and restores focus to the trigger', async () => {
    const user = userEvent.setup()
    render(<DrawerHarness />)
    const trigger = screen.getByRole('button', { name: 'Open Study Tools' })
    await user.click(trigger)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Study Tools' })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('routes each outer tab to the matching existing study tool', async () => {
    const user = userEvent.setup()
    render(<DrawerHarness />)
    await user.click(screen.getByRole('button', { name: 'Open Study Tools' }))

    await user.click(screen.getByRole('tab', { name: 'Words' }))
    expect(screen.getByTestId('existing-study-assistant')).toHaveAttribute('data-active-tool', 'lexicon')

    await user.click(screen.getByRole('tab', { name: 'Cross-References' }))
    expect(screen.getByTestId('existing-study-assistant')).toHaveAttribute('data-active-tool', 'crossrefs')
  })

  it('supports arrow-key navigation across study tool tabs', async () => {
    const user = userEvent.setup()
    render(<DrawerHarness />)
    await user.click(screen.getByRole('button', { name: 'Open Study Tools' }))

    const insights = screen.getByRole('tab', { name: 'Insights' })
    insights.focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Cross-References' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Cross-References' })).toHaveAttribute('aria-selected', 'true')
  })

  it('opens the existing assistant chat from the persistent action', async () => {
    const user = userEvent.setup()
    render(<DrawerHarness />)
    await user.click(screen.getByRole('button', { name: 'Open Study Tools' }))
    await user.click(screen.getByRole('button', { name: 'Ask Study Assistant' }))

    expect(screen.getByTestId('existing-study-assistant')).toHaveAttribute('data-active-tab', 'chat')
  })

  it('closes with its visible close button', async () => {
    const user = userEvent.setup()
    render(<DrawerHarness />)
    await user.click(screen.getByRole('button', { name: 'Open Study Tools' }))
    await user.click(screen.getByRole('button', { name: 'Close Study Tools' }))
    expect(screen.queryByRole('dialog', { name: 'Study Tools' })).not.toBeInTheDocument()
  })
})
