import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { normalizeResearchResponse, normalizeResearchTrail } from './researchApi'
import ResearchInspector from './ResearchInspector'
import ResearchTrail from './ResearchTrail'
import ResearchWorkspace from './ResearchWorkspace'

const GENESIS_ID = 'genesis-eden-source'
const SCHOLAR_ID = 'eden-scholar-source'

const claim = (id, statement, classification = 'canonical-scripture', sourceIds = [GENESIS_ID]) => ({
  id, statement, classification, confidence: classification === 'ai-synthesis' ? 'medium' : 'high', source_ids: sourceIds,
})

function edenResponse() {
  return normalizeResearchResponse({
    id: '9b913a39-d88c-413c-ac5e-f23372161289',
    query: 'What happened between Eden and Abel?',
    mode: 'what-happened-between',
    settings: { source_scopes: ['biblical-canon'], depth: 'deep-research', mode_parameters: {} },
    summary: { title: 'Summary', narrative: '<script>unchecked()</script>', claims: [
      claim('summary-1', 'Adam and Eve lived outside Eden. <script>alert(1)</script>'),
      claim('summary-2', 'The chronology is a synthesis.', 'ai-synthesis', [SCHOLAR_ID]),
    ] },
    timeline: [{
      title: 'Expulsion from Eden', description: 'The pair left the garden.', date_label: 'After Eden',
      source_ids: [GENESIS_ID], confidence: 'high',
    }],
    canonical_account: { title: 'Canonical Account', narrative: null, claims: [claim('canonical-1', 'Genesis places the family east of Eden.')] },
    historical_context: null,
    unknowns: { title: "What We Don't Know", narrative: null, claims: [claim('unknown-1', 'The text gives no elapsed duration.', 'ai-synthesis', [SCHOLAR_ID])] },
    trail_node: null,
    ancient_accounts: [],
    language_notes: [],
    people: [{ name: 'Abel', description: 'Son of Adam and Eve.', role: 'son', source_ids: [GENESIS_ID] }],
    places: [],
    sources: [{
      id: GENESIS_ID, title: 'Genesis', reference: 'Genesis 3:23–4:2', excerpt: 'He sent him out from the garden.',
      text: 'The complete selected passage.', source_type: 'canonical-scripture', tradition: 'Biblical canon',
      date_or_era: 'Ancient Israel', original_language: 'Hebrew', translation: 'Example Translation',
      relevance: 'Primary canonical account', open_target: 'bible://Genesis/3',
    }, {
      id: SCHOLAR_ID, title: 'Eden chronology study', reference: 'Study, pp. 10–12', excerpt: null, text: null,
      source_type: 'scholarship', tradition: null, date_or_era: '2024', original_language: null,
      translation: null, relevance: 'Chronology analysis', open_target: null,
    }],
    related_questions: ['What happened next?'], grounding_status: 'grounded', provider: 'test-provider', model: 'test-model',
  })
}

beforeAll(() => {
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal() { this.open = true }
  }
  if (!HTMLDialogElement.prototype.close) {
    HTMLDialogElement.prototype.close = function close() { this.open = false }
  }
})

describe('ResearchWorkspace', () => {
  it('does not create a nested main landmark and labels its result region', () => {
    render(<main><ResearchWorkspace response={edenResponse()} /></main>)
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getByRole('region', { name: 'What happened between Eden and Abel?' })).toBeInTheDocument()
  })

  it('renders grounded claim sections and omits unsupported ornamental sections and narratives', () => {
    const { container } = render(<ResearchWorkspace response={edenResponse()} />)
    expect(screen.getByRole('heading', { name: 'Summary' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Timeline' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Canonical Account' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "What We Don't Know" })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Sources' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'People' })).toBeInTheDocument()
    for (const absent of ['Ancient Accounts', 'Historical Context', 'Language Notes', 'Places', 'Book Explainer']) {
      expect(screen.queryByRole('heading', { name: absent })).not.toBeInTheDocument()
    }
    expect(screen.getByText('Adam and Eve lived outside Eden. <script>alert(1)</script>')).toBeInTheDocument()
    expect(container.querySelector('script')).toBeNull()
    expect(screen.queryByText('<script>unchecked()</script>')).not.toBeInTheDocument()
    screen.getAllByText('AI synthesis').forEach((label) => expect(label).toHaveClass('research-claim__synthesis-label'))
    expect(screen.getAllByText('High confidence').length).toBeGreaterThan(0)
  })

  it('opens known-source citations, reports provenance, closes on Escape, and restores focus', async () => {
    const user = userEvent.setup()
    const onCitation = vi.fn()
    const onClose = vi.fn()
    const onOpenTarget = vi.fn()
    render(<ResearchWorkspace response={edenResponse()} onCitation={onCitation} onCitationClose={onClose} onOpenTarget={onOpenTarget} />)
    const citations = screen.getAllByRole('button', { name: /Genesis 3:23–4:2/i })
    expect(citations.length).toBeGreaterThan(1)
    await user.click(citations[0])
    expect(onCitation).toHaveBeenCalledWith(expect.objectContaining({ id: GENESIS_ID }), citations[0])
    const dialog = screen.getByRole('dialog', { name: 'Genesis' })
    expect(within(dialog).getByText('Biblical Canon')).toBeInTheDocument()
    expect(within(dialog).getByText('Biblical canon')).toBeInTheDocument()
    expect(within(dialog).getByText('Example Translation')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Open Full Text' }))
    expect(onOpenTarget).toHaveBeenCalledWith('bible://Genesis/3', expect.objectContaining({ id: GENESIS_ID }))
    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(citations[0]).toHaveFocus()
  })

  it('provides a visible trapped-focus dialog fallback when showModal is unavailable', async () => {
    const nativeShowModal = HTMLDialogElement.prototype.showModal
    const nativeClose = HTMLDialogElement.prototype.close
    HTMLDialogElement.prototype.showModal = undefined
    HTMLDialogElement.prototype.close = undefined
    try {
      const user = userEvent.setup()
      const onClose = vi.fn()
      render(<ResearchWorkspace response={edenResponse()} onCitationClose={onClose} />)
      const trigger = screen.getAllByRole('button', { name: /Cite Genesis 3:23–4:2/i })[0]
      await user.click(trigger)
      const dialog = screen.getByRole('dialog', { name: 'Genesis' })
      expect(dialog.tagName).toBe('DIV')
      expect(dialog).toHaveAttribute('aria-modal', 'true')
      const close = within(dialog).getByRole('button', { name: 'Close citation' })
      const open = within(dialog).getByRole('button', { name: 'Open Full Text' })
      expect(close).toHaveFocus()

      fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
      expect(open).toHaveFocus()
      fireEvent.keyDown(open, { key: 'Tab' })
      expect(close).toHaveFocus()

      fireEvent.keyDown(dialog, { key: 'Escape' })
      expect(onClose).toHaveBeenCalledOnce()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(trigger).toHaveFocus()
    } finally {
      HTMLDialogElement.prototype.showModal = nativeShowModal
      HTMLDialogElement.prototype.close = nativeClose
    }
  })

  it('only renders citation controls backed by returned source records', () => {
    const response = edenResponse()
    render(<ResearchWorkspace response={response} />)
    const labels = response.sources.map((source) => source.reference)
    screen.getAllByRole('button', { name: /Cite / }).forEach((button) => {
      expect(labels.some((label) => button.accessibleName?.includes(label) || button.textContent.includes(label))).toBe(true)
    })
  })

  it('uses an ordered timeline and explicit event research actions', async () => {
    const user = userEvent.setup()
    const onEventResearch = vi.fn()
    const { container } = render(<ResearchWorkspace response={edenResponse()} onEventResearch={onEventResearch} />)
    const timeline = screen.getByRole('heading', { name: 'Timeline' }).closest('section')
    expect(timeline.querySelector('ol')).toBeInTheDocument()
    expect(within(timeline).getByText('After Eden')).toBeInTheDocument()
    await user.click(within(timeline).getByRole('button', { name: 'Research Expulsion from Eden' }))
    expect(onEventResearch).toHaveBeenCalledWith(edenResponse().timeline[0])
    expect(container.querySelector('[onclick]:not(button)')).toBeNull()
  })

  it('calls related-question and feedback actions with their values', async () => {
    const user = userEvent.setup()
    const onRelatedQuestion = vi.fn()
    const onFeedback = vi.fn()
    render(<ResearchWorkspace response={edenResponse()} onRelatedQuestion={onRelatedQuestion} onFeedback={onFeedback} />)
    await user.click(screen.getByRole('button', { name: 'What happened next?' }))
    expect(onRelatedQuestion).toHaveBeenCalledWith('What happened next?')
    await user.click(screen.getByRole('button', { name: 'Helpful' }))
    expect(onFeedback).toHaveBeenCalledWith('helpful')
  })
})

describe('ResearchInspector', () => {
  it('omits empty cards, distinguishes source types, and dispatches person/place actions', async () => {
    const user = userEvent.setup()
    const onPersonResearch = vi.fn()
    const onPlaceResearch = vi.fn()
    const response = edenResponse()
    render(<ResearchInspector
      sources={response.sources} people={response.people}
      places={[{ name: 'Eden', description: null, location: 'Unknown', sourceIds: [GENESIS_ID] }]}
      onPersonResearch={onPersonResearch} onPlaceResearch={onPlaceResearch}
    />)
    expect(screen.getByText('Canonical Scripture')).toBeInTheDocument()
    expect(screen.getByText('Scholarship')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Research Abel' }))
    expect(onPersonResearch).toHaveBeenCalledWith(response.people[0])
    await user.click(screen.getByRole('button', { name: 'Research Eden' }))
    expect(onPlaceResearch).toHaveBeenCalledWith(expect.objectContaining({ name: 'Eden' }))
    expect(screen.queryByRole('heading', { name: 'Continue Research' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Book Explainer' })).not.toBeInTheDocument()
  })
})

describe('ResearchTrail', () => {
  it('deduplicates active ancestry, marks active, selects nodes, and announces truncation', async () => {
    const user = userEvent.setup()
    const onSelectNode = vi.fn()
    const active = { id: '07449bd5-e672-4504-ab7d-45a1e6615cb1', parent_node_id: null, question: 'Active question?', mode: 'compare-accounts', created_at: null, updated_at: null }
    const trail = normalizeResearchTrail({
      ancestry: [
        { id: '9b913a39-d88c-413c-ac5e-f23372161289', parent_node_id: null, question: 'Root question?', mode: 'what-happened-between', created_at: null, updated_at: null },
        active,
      ],
      active,
      children: [{ id: 'c8d77469-b3ca-40ad-a15b-9c228cd00898', parent_node_id: active.id, question: 'Child question?', mode: 'genealogy', created_at: null, updated_at: null }],
      children_truncated: true,
    })
    render(<ResearchTrail trail={trail} onSelectNode={onSelectNode} />)
    expect(screen.getAllByRole('button', { name: 'Active question?' })).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Active question?' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText(/additional branches are not shown/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Child question?' }))
    expect(onSelectNode).toHaveBeenCalledWith(trail.children[0])
  })
})
