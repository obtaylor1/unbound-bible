import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ComparisonToolbar from './ComparisonToolbar'
import TranslationSelector from './TranslationSelector'

const toolbarProps = {
  books: ['Genesis', 'Exodus'],
  chapters: [1, 2],
  verses: [1, 2, 3],
  book: 'Genesis',
  chapter: '1',
  verse: '1',
  viewMode: 'verse',
  baseTranslation: 'eth81',
  selectedTranslations: ['eth81', 'kjv'],
  highlightDifferences: true,
  onBookChange: vi.fn(),
  onChapterChange: vi.fn(),
  onVerseChange: vi.fn(),
  onViewModeChange: vi.fn(),
  onBaseTranslationChange: vi.fn(),
  onHighlightDifferencesChange: vi.fn(),
  onOpenStudyTools: vi.fn(),
}

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
        selected={['eth81', 'kjv']}
        baseTranslation="eth81"
        onToggle={vi.fn()}
      />,
    )

    expect(screen.getByTestId('translation-selector')).toBeInTheDocument()
    expect(screen.getByText('Comparing 2 translations')).toBeInTheDocument()
    expect(screen.getByText('Add up to 2 more')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('checkbox', { name: /Ethiopian Orthodox Critical Text/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /King James Version/ })).toBeChecked()
  })

  it('filters by Ethiopian category and search query', async () => {
    const user = userEvent.setup()
    render(
      <TranslationSelector
        selected={['eth81', 'kjv']}
        baseTranslation="eth81"
        onToggle={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Ethiopian' }))
    expect(screen.getByRole('button', { name: 'Ethiopian' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('checkbox', { name: /King James Version/ })).not.toBeInTheDocument()

    await user.type(screen.getByRole('searchbox', { name: 'Search translations' }), 'enoch')
    expect(screen.getByRole('checkbox', { name: /1 Enoch, R. H. Charles/ })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: /Ethiopian Orthodox Critical Text/ })).not.toBeInTheDocument()
  })

  it('calls onToggle and disables unselected rows at the four-source limit', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    render(
      <TranslationSelector
        selected={['eth81', 'kjv', 'asv', 'web']}
        baseTranslation="eth81"
        onToggle={onToggle}
      />,
    )

    expect(screen.getByText('Maximum of 4 translations selected')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /World English Bible, British Edition/ })).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /King James Version/ }))
    expect(onToggle).toHaveBeenCalledWith('kjv')
  })
})
