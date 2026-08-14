import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GUEST_RESEARCH_STORAGE_KEY, runResearch } from './researchApi'
import { api } from '../api/client'
import { useAuth } from '../auth/authContext'
import ScriptureResearchPage from './ScriptureResearchPage'

vi.mock('./researchApi', async (importOriginal) => {
  const original = await importOriginal()
  return { ...original, runResearch: vi.fn(), searchResearchEvents: vi.fn().mockResolvedValue({ events: [] }) }
})
vi.mock('../api/client', () => ({ api: { post: vi.fn() } }))
vi.mock('../auth/authContext', () => ({ useAuth: vi.fn() }))
vi.mock('../components/ShareStudyModal', () => ({
  default: ({ isOpen, shareData, onClose }) => isOpen ? (
    <div role="dialog" aria-label="Share study session">
      <span>{shareData.title}</span><span>{shareData.type}</span>
      <button type="button" onClick={onClose}>Close share</button>
    </div>
  ) : null,
}))

const IDS = {
  response: '11111111-1111-4111-8111-111111111111',
  node: '22222222-2222-4222-8222-222222222222',
  followup: '33333333-3333-4333-8333-333333333333',
}

function response(overrides = {}) {
  return {
    id: IDS.response,
    query: 'What happened between Eden and Abel?',
    mode: 'what-happened-between',
    settings: { sourceScopes: ['biblical-canon'], depth: 'deep-research', modeParameters: {} },
    summary: {
      title: 'Overview', narrative: null,
      claims: [{ id: 'claim-1', statement: 'Genesis records expulsion, births, offerings, and Abel’s death.', classification: 'canonical-scripture', confidence: 'high', sourceIds: ['gen-2-4'] }],
    },
    timeline: null,
    canonicalAccount: null,
    historicalContext: null,
    unknowns: null,
    trailNode: { id: IDS.node, parentNodeId: null, question: 'What happened between Eden and Abel?', label: 'Eden to Abel' },
    ancientAccounts: [], languageNotes: [], people: [], places: [],
    sources: [{ id: 'gen-2-4', title: 'Genesis', reference: 'Genesis 2–4', excerpt: 'The canonical account.', text: null, sourceType: 'canonical-scripture', tradition: 'Biblical Canon', dateOrEra: null, originalLanguage: 'Hebrew', translation: 'KJV', relevance: 'Direct account', openTarget: '#scriptures?book=Genesis&chapter=2' }],
    relatedQuestions: ['What happened to Cain after Abel’s death?'],
    groundingStatus: 'grounded', provider: 'library-provider', model: 'grounded-v1',
    ...overrides,
  }
}

const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise })
  return { promise, resolve, reject }
}

function submitQuestion(question = 'What happened between Eden and Abel?') {
  fireEvent.change(screen.getByLabelText('Research question'), { target: { value: question } })
  fireEvent.click(screen.getByRole('button', { name: /ask/i }))
}

describe('ScriptureResearchPage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    useAuth.mockReturnValue({ status: 'anonymous', user: null })
  })

  afterEach(() => vi.useRealTimers())

  it('opens empty-first and submits a compact example without preloading a result', async () => {
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)

    expect(screen.getByRole('heading', { name: /Scripture Research AI/i })).toBeInTheDocument()
    expect(screen.queryByText('Genesis records expulsion')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Eden to Abel' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledWith(
      expect.objectContaining({
        question: 'What happened between Eden and Abel?',
        sourceScopes: ['biblical-canon'], depth: 'deep-research', mode: 'what-happened-between',
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ))
    expect(await screen.findByText('Genesis records expulsion, births, offerings, and Abel’s death.')).toBeInTheDocument()
  })

  it('announces honest loading stages and renders a successful workspace', async () => {
    const request = deferred()
    runResearch.mockReturnValue(request.promise)
    render(<ScriptureResearchPage />)
    submitQuestion()

    expect(screen.getByText('Searching selected library sources…')).toHaveAttribute('role', 'status')
    expect(screen.queryByText(/searching the web|thinking|reasoning/i)).not.toBeInTheDocument()

    await act(async () => request.resolve(response()))
    expect(await screen.findByText('Genesis records expulsion, births, offerings, and Abel’s death.')).toBeInTheDocument()
    expect(screen.getByText('Grounded')).toBeInTheDocument()
  })

  it('aborts the previous request, ignores its stale result, and aborts on unmount', async () => {
    const first = deferred()
    const second = deferred()
    runResearch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const { unmount } = render(<ScriptureResearchPage />)

    submitQuestion('First research question')
    const firstSignal = runResearch.mock.calls[0][1].signal
    // Starting a new request is permitted through the retry path after an error-free cancellation.
    fireEvent.change(screen.getByLabelText('Research question'), { target: { value: 'Second research question' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start new request' }))
    expect(firstSignal.aborted).toBe(true)

    const secondSignal = runResearch.mock.calls[1][1].signal
    await act(async () => second.resolve(response({ query: 'Second research question' })))
    await act(async () => first.resolve(response({ query: 'First research question' })))
    expect(screen.getByRole('heading', { name: 'Second research question' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'First research question' })).not.toBeInTheDocument()

    unmount()
    expect(secondSignal.aborted).toBe(true)
  })

  it('retries an error with the exact original question and settings', async () => {
    runResearch.mockRejectedValueOnce(new Error('Network unavailable')).mockResolvedValueOnce(response())
    render(<ScriptureResearchPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Commentary' }))
    submitQuestion('Why was Cain’s offering rejected?')

    expect(await screen.findByRole('alert')).toHaveTextContent('Network unavailable')
    fireEvent.change(screen.getByLabelText('Research question'), { target: { value: 'Changed draft' } })
    fireEvent.click(screen.getByRole('button', { name: 'Retry research' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(2))
    expect(runResearch.mock.calls[1][0]).toEqual(runResearch.mock.calls[0][0])
  })

  it.each([
    ['insufficient', 'Not enough verified evidence', 'Try a narrower question'],
    ['evidence-only', 'Verified evidence only', 'The synthesis provider was unavailable'],
  ])('renders an honest %s result state with retry', async (groundingStatus, heading, detail) => {
    runResearch.mockResolvedValue(response({ groundingStatus, summary: { title: 'Overview', narrative: null, claims: [] } }))
    render(<ScriptureResearchPage />)
    submitQuestion()

    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getByText(new RegExp(detail, 'i'))).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry research' })).toBeInTheDocument()
  })

  it('sends authenticated follow-ups with the active parent node', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    runResearch
      .mockResolvedValueOnce(response())
      .mockResolvedValueOnce(response({ id: IDS.followup, query: 'What happened to Cain after Abel’s death?', trailNode: { id: IDS.followup, parentNodeId: IDS.node, question: 'What happened to Cain after Abel’s death?', label: null } }))
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'What happened to Cain after Abel’s death?' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(2))
    expect(runResearch.mock.calls[1][0]).toEqual(expect.objectContaining({ parentNodeId: IDS.node }))
  })

  it('keeps authenticated responses navigable in the active research trail', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    runResearch
      .mockResolvedValueOnce(response())
      .mockResolvedValueOnce(response({ id: IDS.followup, query: 'What happened to Cain after Abel’s death?', trailNode: { id: IDS.followup, parentNodeId: IDS.node, question: 'What happened to Cain after Abel’s death?', label: 'Cain after Abel' } }))
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'What happened to Cain after Abel’s death?' }))
    expect(await screen.findByRole('heading', { name: 'What happened to Cain after Abel’s death?' })).toBeInTheDocument()

    const trail = screen.getByRole('navigation', { name: 'Research trail' })
    fireEvent.click(within(trail).getByRole('button', { name: 'Eden to Abel' }))
    expect(screen.getByRole('heading', { name: 'What happened between Eden and Abel?' })).toBeInTheDocument()
  })

  it('keeps guest follow-ups standalone while restoring a validated local trail', async () => {
    const saved = response()
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: {
        nodes: [{ id: saved.id, parentNodeId: null, response: saved }], activeNodeId: saved.id,
        settings: saved.settings,
      },
    }))
    runResearch.mockResolvedValue(response({ id: IDS.followup, query: 'What happened to Cain after Abel’s death?', trailNode: null }))
    render(<ScriptureResearchPage />)

    expect(screen.getByRole('heading', { name: saved.query })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'What happened to Cain after Abel’s death?' }))
    await waitFor(() => expect(runResearch).toHaveBeenCalledOnce())
    expect(runResearch.mock.calls[0][0]).not.toHaveProperty('parentNodeId')
    expect(JSON.parse(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).session.nodes).toHaveLength(2)
  })

  it('recovers safely from malformed guest storage', () => {
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, '{not json')
    render(<ScriptureResearchPage />)
    expect(screen.getByRole('heading', { name: /Scripture Research AI/i })).toBeInTheDocument()
    expect(screen.queryByText('Genesis records expulsion')).not.toBeInTheDocument()
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })

  it('retries a restored recoverable guest result with its saved settings', async () => {
    const saved = response({ groundingStatus: 'evidence-only' })
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: {
        nodes: [{ id: saved.id, parentNodeId: null, response: saved }], activeNodeId: saved.id,
        settings: saved.settings,
      },
    }))
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Retry research' }))
    await waitFor(() => expect(runResearch).toHaveBeenCalledWith(
      expect.objectContaining({ question: saved.query, sourceScopes: ['biblical-canon'], depth: 'deep-research' }),
      expect.any(Object),
    ))
  })

  it('saves authenticated research through the existing study, messages, and sources workflow', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    runResearch.mockResolvedValue(response())
    api.post.mockResolvedValueOnce({ id: 'study-1' }).mockResolvedValue({})
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'Save research' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/studies', expect.objectContaining({ title: expect.stringContaining('Eden') })))
    expect(api.post).toHaveBeenCalledWith('/studies/study-1/messages', { role: 'user', content: 'What happened between Eden and Abel?' })
    expect(api.post).toHaveBeenCalledWith('/studies/study-1/messages', expect.objectContaining({ role: 'assistant', content: expect.stringContaining('Genesis records expulsion') }))
    expect(api.post).toHaveBeenCalledWith('/studies/study-1/sources', expect.objectContaining({ title: 'Genesis', citation: 'Genesis 2–4' }))
    expect(await screen.findByText(/saved privately/i)).toHaveAttribute('role', 'status')
  })

  it('opens ShareStudyModal with meaningful result data', async () => {
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'Share research' }))

    const dialog = screen.getByRole('dialog', { name: 'Share study session' })
    expect(dialog).toBeInTheDocument()
    expect(within(dialog).getByText('Scripture Research AI')).toBeInTheDocument()
    expect(within(dialog).getByText(/Eden and Abel/)).toBeInTheDocument()
  })

  it('starts New Research by clearing question, result, and guest trail', async () => {
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)
    submitQuestion()
    expect(await screen.findByText('Genesis records expulsion, births, offerings, and Abel’s death.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'New Research' }))
    expect(screen.getByLabelText('Research question')).toHaveValue('')
    expect(screen.queryByText('Genesis records expulsion, births, offerings, and Abel’s death.')).not.toBeInTheDocument()
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })
})
