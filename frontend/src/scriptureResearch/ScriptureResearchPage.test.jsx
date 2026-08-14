import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import {
  GUEST_RESEARCH_STORAGE_KEY,
  getResearchTrail,
  linkResearchStudy,
  listResearchTrails,
  runResearch,
} from './researchApi'
import { api } from '../api/client'
import { useAuth } from '../auth/authContext'
import ScriptureResearchPage from './ScriptureResearchPage'

vi.mock('./researchApi', async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    getResearchTrail: vi.fn(),
    linkResearchStudy: vi.fn(),
    listResearchTrails: vi.fn(),
    runResearch: vi.fn(),
    searchResearchEvents: vi.fn().mockResolvedValue({ events: [] }),
  }
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
    window.location.hash = '#aistudy'
    vi.clearAllMocks()
    runResearch.mockReset()
    getResearchTrail.mockReset()
    linkResearchStudy.mockReset()
    listResearchTrails.mockReset().mockResolvedValue({ nodes: [] })
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
        modeParameters: {
          from_event_id: 'eden',
          to_event_id: 'abel-killed',
        },
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ))
    expect(await screen.findByText('Genesis records expulsion, births, offerings, and Abel’s death.')).toBeInTheDocument()
  })

  it('clears event IDs when the main question is edited after an event example', async () => {
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Eden to Abel' }))
    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText('Research question'), {
      target: { value: 'What does Genesis teach about creation?' },
    })
    fireEvent.click(screen.getByRole('button', { name: /ask/i }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(2))
    expect(runResearch.mock.calls[1][0]).toEqual(expect.objectContaining({
      question: 'What does Genesis teach about creation?',
      modeParameters: {},
    }))
  })

  it('clears event IDs when changing away from between-events mode', async () => {
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Eden to Abel' }))
    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByRole('button', { name: 'Explain a Book' }))
    fireEvent.click(screen.getByRole('button', { name: /ask/i }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(2))
    expect(runResearch.mock.calls[1][0]).toEqual(expect.objectContaining({
      mode: 'explain-a-book',
      modeParameters: {},
    }))
  })

  it('replaces event IDs when choosing a different example', async () => {
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Eden to Abel' }))
    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByRole('button', { name: 'Explain Enoch' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(2))
    expect(runResearch.mock.calls[1][0]).toEqual(expect.objectContaining({
      mode: 'explain-a-book',
      modeParameters: {},
    }))
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

  it('aborts an in-flight request on unmount and ignores its late result', async () => {
    const first = deferred()
    runResearch.mockReturnValueOnce(first.promise)
    const { unmount } = render(<ScriptureResearchPage />)

    submitQuestion('First research question')
    const firstSignal = runResearch.mock.calls[0][1].signal
    unmount()
    expect(firstSignal.aborted).toBe(true)
    await act(async () => first.resolve(response({ query: 'First research question' })))
  })

  it('completes research after React StrictMode replays the mount effect', async () => {
    const pending = deferred()
    runResearch.mockReturnValue(pending.promise)
    render(<StrictMode><ScriptureResearchPage /></StrictMode>)
    submitQuestion('Strict mode research')

    await act(async () => pending.resolve(response({ query: 'Strict mode research' })))

    expect(await screen.findByRole('heading', { name: 'Strict mode research' })).toBeInTheDocument()
  })

  it('clears user A research when the authenticated principal changes to user B', async () => {
    let auth = { status: 'authenticated', user: { id: 'user-a' } }
    useAuth.mockImplementation(() => auth)
    runResearch.mockResolvedValue(response({ query: 'Private user A research' }))
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Private user A research')
    expect(await screen.findByRole('heading', { name: 'Private user A research' })).toBeInTheDocument()

    auth = { status: 'authenticated', user: { id: 'user-b' } }
    rerender(<ScriptureResearchPage />)

    expect(screen.queryByRole('heading', { name: 'Private user A research' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Research question')).toHaveValue('')
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })

  it('ignores user A in-flight completion after logout and restores guest research', async () => {
    const guest = response({ id: IDS.followup, query: 'Saved guest research', trailNode: null })
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: {
        nodes: [{ id: guest.id, parentNodeId: null, response: guest }],
        activeNodeId: guest.id,
        settings: guest.settings,
      },
    }))
    const pending = deferred()
    let auth = { status: 'authenticated', user: { id: 'user-a' } }
    useAuth.mockImplementation(() => auth)
    runResearch.mockReturnValue(pending.promise)
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Private pending user A research')

    auth = { status: 'anonymous', user: null }
    rerender(<ScriptureResearchPage />)
    await act(async () => pending.resolve(response({ query: 'Private pending user A research' })))

    expect(await screen.findByRole('heading', { name: 'Saved guest research' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Private pending user A research' })).not.toBeInTheDocument()
    const stored = JSON.parse(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).session
    expect(stored.nodes).toHaveLength(1)
    expect(stored.nodes[0].response.query).toBe('Saved guest research')
  })

  it('ignores user A in-flight completion after switching to user B', async () => {
    const pending = deferred()
    let auth = { status: 'authenticated', user: { id: 'user-a' } }
    useAuth.mockImplementation(() => auth)
    runResearch.mockReturnValue(pending.promise)
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Private pending user A research')

    auth = { status: 'authenticated', user: { id: 'user-b' } }
    rerender(<ScriptureResearchPage />)
    await act(async () => pending.resolve(response({ query: 'Private pending user A research' })))

    expect(screen.queryByRole('heading', { name: 'Private pending user A research' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Research question')).toHaveValue('')
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })

  it('prevents every in-flight duplicate submission', () => {
    runResearch.mockReturnValue(new Promise(() => {}))
    render(<ScriptureResearchPage />)
    submitQuestion()

    expect(screen.queryByRole('button', { name: 'Start new request' })).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Research question' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Eden to Abel' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Eden to Abel' }))
    expect(runResearch).toHaveBeenCalledOnce()
  })

  it('retries an error with the exact original question and settings', async () => {
    runResearch.mockRejectedValueOnce(new Error('Network unavailable')).mockResolvedValueOnce(response())
    render(<ScriptureResearchPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ethiopian Tradition' }))
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
    if (groundingStatus === 'insufficient') {
      const notice = screen.getByRole('heading', { name: heading }).closest('section')
      expect(within(notice).getByText(/Biblical Canon/)).toBeInTheDocument()
    }
  })

  it.each([
    ['grounded', 'Grounded research is ready.'],
    ['insufficient', 'Research completed with insufficient verified evidence.'],
    ['evidence-only', 'Verified evidence is ready without AI synthesis.'],
  ])('announces the %s completion transition politely', async (groundingStatus, announcement) => {
    runResearch.mockResolvedValue(response({ groundingStatus }))
    render(<ScriptureResearchPage />)
    submitQuestion()

    expect(await screen.findByText(announcement)).toHaveAttribute('role', 'status')
    expect(screen.getByText(announcement)).toHaveAttribute('aria-live', 'polite')
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

  it('turns a timeline event into a focused follow-up request', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    const timelineEvent = {
      title: 'Expulsion from Eden',
      dateLabel: 'After Eden',
      description: 'Adam and Eve leave the garden.',
      confidence: 'high',
      sourceIds: ['gen-2-4'],
    }
    runResearch
      .mockResolvedValueOnce(response({ timeline: [timelineEvent] }))
      .mockResolvedValueOnce(response({
        id: IDS.followup,
        query: 'What does the verified evidence show about Expulsion from Eden?',
        trailNode: {
          id: IDS.followup,
          parentNodeId: IDS.node,
          question: 'What does the verified evidence show about Expulsion from Eden?',
          label: null,
        },
      }))
    render(<ScriptureResearchPage />)
    submitQuestion()

    fireEvent.click(await screen.findByRole('button', { name: 'Research Expulsion from Eden' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(2))
    expect(runResearch.mock.calls[1][0]).toEqual(expect.objectContaining({
      question: 'What does the verified evidence show about Expulsion from Eden?',
      parentNodeId: IDS.node,
    }))
  })

  it('restores the current user’s latest research branch and keeps it navigable after reload', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    const rootSummary = {
      id: IDS.node,
      parentNodeId: null,
      question: 'What happened between Eden and Abel?',
      mode: 'what-happened-between',
      createdAt: null,
      updatedAt: null,
    }
    const childSummary = {
      id: IDS.followup,
      parentNodeId: IDS.node,
      question: 'What happened to Cain after Abel’s death?',
      mode: 'what-happened-between',
      createdAt: null,
      updatedAt: null,
    }
    const rootResponse = response()
    const childResponse = response({
      id: IDS.followup,
      query: childSummary.question,
      trailNode: {
        id: IDS.followup,
        parentNodeId: IDS.node,
        question: childSummary.question,
        label: null,
      },
    })
    listResearchTrails.mockResolvedValue({ nodes: [childSummary] })
    getResearchTrail
      .mockResolvedValueOnce({
        ancestry: [rootSummary], active: childSummary, children: [],
        childrenTruncated: false, activeResponse: childResponse,
      })
      .mockResolvedValueOnce({
        ancestry: [], active: rootSummary, children: [childSummary],
        childrenTruncated: false, activeResponse: rootResponse,
      })

    render(<ScriptureResearchPage />)

    expect(await screen.findByRole('heading', { name: childSummary.question })).toBeInTheDocument()
    expect(listResearchTrails).toHaveBeenCalledOnce()
    expect(getResearchTrail).toHaveBeenNthCalledWith(1, IDS.followup, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    const trail = screen.getByRole('navigation', { name: 'Research trail' })
    fireEvent.click(within(trail).getByRole('button', { name: rootSummary.question }))
    expect(await screen.findByRole('heading', { name: rootSummary.question })).toBeInTheDocument()
    expect(getResearchTrail).toHaveBeenNthCalledWith(2, IDS.node, expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('cancels background trail restoration when the user starts new research', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    const restoring = deferred()
    const researching = deferred()
    listResearchTrails.mockReturnValue(restoring.promise)
    runResearch.mockReturnValue(researching.promise)
    render(<ScriptureResearchPage />)
    await waitFor(() => expect(listResearchTrails).toHaveBeenCalledOnce())
    const restoreSignal = listResearchTrails.mock.calls[0][0].signal

    submitQuestion('Start a fresh investigation')

    expect(restoreSignal.aborted).toBe(true)
    await act(async () => restoring.resolve({ nodes: [] }))
    await act(async () => researching.resolve(response({ query: 'Start a fresh investigation' })))
    expect(await screen.findByRole('heading', { name: 'Start a fresh investigation' })).toBeInTheDocument()
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
    const saved = response({
      people: [{ name: 'Cain', description: 'Prior prose must not be sent.', role: 'son', sourceIds: ['gen-2-4'] }],
      places: [{ name: 'Eden', description: 'Prior prose must not be sent.', location: 'unknown', sourceIds: ['gen-2-4'] }],
    })
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
    expect(runResearch.mock.calls[0][0]).toMatchObject({
      conversationContext: {
        entityNames: ['Cain', 'Eden'],
        sourceReferences: ['Genesis 2–4'],
      },
    })
    expect(JSON.stringify(runResearch.mock.calls[0][0])).not.toContain('Prior prose')
    expect(JSON.parse(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).session.nodes).toHaveLength(2)
  })

  it('hydrates a saved guest session once when authentication resolves to anonymous', () => {
    const saved = response()
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: { nodes: [{ id: saved.id, parentNodeId: null, response: saved }], activeNodeId: saved.id, settings: saved.settings },
    }))
    let status = 'loading'
    useAuth.mockImplementation(() => ({ status, user: null }))
    const { rerender } = render(<ScriptureResearchPage />)
    expect(screen.queryByRole('heading', { name: saved.query })).not.toBeInTheDocument()

    status = 'anonymous'
    rerender(<ScriptureResearchPage />)
    expect(screen.getByRole('heading', { name: saved.query })).toBeInTheDocument()
  })

  it('does not overwrite user work when authentication resolves to anonymous', () => {
    const saved = response()
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: { nodes: [{ id: saved.id, parentNodeId: null, response: saved }], activeNodeId: saved.id, settings: saved.settings },
    }))
    let status = 'loading'
    useAuth.mockImplementation(() => ({ status, user: null }))
    const { rerender } = render(<ScriptureResearchPage />)
    fireEvent.change(screen.getByLabelText('Research question'), { target: { value: 'My new draft' } })

    status = 'anonymous'
    rerender(<ScriptureResearchPage />)
    expect(screen.getByLabelText('Research question')).toHaveValue('My new draft')
    expect(screen.queryByRole('heading', { name: saved.query })).not.toBeInTheDocument()
  })

  it('retains and stores a query that completes after auth loading resolves anonymous', async () => {
    const pending = deferred()
    let status = 'loading'
    useAuth.mockImplementation(() => ({ status, user: null }))
    runResearch.mockReturnValue(pending.promise)
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Who was Cain?')

    status = 'anonymous'
    rerender(<ScriptureResearchPage />)
    await act(async () => pending.resolve(response({ query: 'Who was Cain?', trailNode: null })))

    expect(await screen.findByRole('heading', { name: 'Who was Cain?' })).toBeInTheDocument()
    const stored = JSON.parse(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY))
    expect(stored.session.nodes).toHaveLength(1)
    expect(stored.session.nodes[0].response.query).toBe('Who was Cain?')
  })

  it('recovers an anonymous in-flight request after sign-in and retries the exact request as the authenticated user', async () => {
    const pendingGuest = deferred()
    let auth = { status: 'anonymous', user: null }
    useAuth.mockImplementation(() => auth)
    runResearch
      .mockReturnValueOnce(pendingGuest.promise)
      .mockResolvedValueOnce(response({
        query: 'Who was Cain?',
        trailNode: { id: IDS.node, parentNodeId: null, question: 'Who was Cain?', label: null },
      }))
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Who was Cain?')
    const originalRequest = runResearch.mock.calls[0][0]
    const guestSignal = runResearch.mock.calls[0][1].signal

    auth = { status: 'authenticated', user: { id: 'user-1' } }
    rerender(<ScriptureResearchPage />)

    expect(guestSignal.aborted).toBe(true)
    expect(await screen.findByRole('alert')).toHaveTextContent(/sign-in changed.*retry/i)
    expect(screen.getByLabelText('Research question')).not.toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Retry research' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(2))
    expect(runResearch.mock.calls[1][0]).toEqual(originalRequest)
    expect(await screen.findByRole('heading', { name: 'Who was Cain?' })).toBeInTheDocument()
    await act(async () => pendingGuest.resolve(response({ query: 'Leaked guest result', trailNode: null })))
    expect(screen.queryByRole('heading', { name: 'Leaked guest result' })).not.toBeInTheDocument()
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })

  it('preserves an interrupted guest follow-up as an authenticated parent-revalidation retry', async () => {
    const parent = response({ query: 'Who was Cain?', trailNode: null })
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: {
        nodes: [{ id: parent.id, parentNodeId: null, response: parent }],
        activeNodeId: parent.id,
        settings: parent.settings,
      },
    }))
    const pendingGuestFollowUp = deferred()
    let auth = { status: 'anonymous', user: null }
    useAuth.mockImplementation(() => auth)
    runResearch
      .mockReturnValueOnce(pendingGuestFollowUp.promise)
      .mockResolvedValueOnce(response({
        query: 'Who was Cain?',
        trailNode: { id: IDS.node, parentNodeId: null, question: 'Who was Cain?', label: null },
      }))
      .mockResolvedValueOnce(response({
        id: IDS.followup,
        query: 'What happened to Cain after Abel’s death?',
        trailNode: { id: IDS.followup, parentNodeId: IDS.node, question: 'What happened to Cain after Abel’s death?', label: null },
      }))
    const { rerender } = render(<ScriptureResearchPage />)
    fireEvent.click(screen.getByRole('button', { name: 'What happened to Cain after Abel’s death?' }))

    auth = { status: 'authenticated', user: { id: 'user-1' } }
    rerender(<ScriptureResearchPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/sign-in changed.*retry/i)
    fireEvent.click(screen.getByRole('button', { name: 'Retry research' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(3))
    expect(runResearch.mock.calls[1][0]).toMatchObject({ question: 'Who was Cain?' })
    expect(runResearch.mock.calls[1][0]).not.toHaveProperty('parentNodeId')
    expect(runResearch.mock.calls[1][0]).not.toHaveProperty('conversationContext')
    expect(runResearch.mock.calls[2][0]).toMatchObject({
      question: 'What happened to Cain after Abel’s death?',
      parentNodeId: IDS.node,
    })
    expect(runResearch.mock.calls[2][0]).not.toHaveProperty('conversationContext')
    await act(async () => pendingGuestFollowUp.resolve(response({ query: 'Leaked guest follow-up', trailNode: null })))
    expect(screen.queryByRole('heading', { name: 'Leaked guest follow-up' })).not.toBeInTheDocument()
  })

  it('merges saved guest ancestry when a startup query resolves anonymous', async () => {
    const saved = response({ trailNode: null })
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: {
        nodes: [{ id: saved.id, parentNodeId: null, response: saved }],
        activeNodeId: saved.id,
        settings: saved.settings,
      },
    }))
    const pending = deferred()
    let status = 'loading'
    useAuth.mockImplementation(() => ({ status, user: null }))
    runResearch.mockReturnValue(pending.promise)
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Who was Cain?')

    status = 'anonymous'
    rerender(<ScriptureResearchPage />)
    await act(async () => pending.resolve(response({
      id: IDS.followup,
      query: 'Who was Cain?',
      trailNode: null,
    })))

    const stored = JSON.parse(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).session
    expect(stored.nodes).toHaveLength(2)
    expect(stored.nodes.map((node) => node.id)).toEqual([saved.id, IDS.followup])
    expect(stored.nodes[1].parentNodeId).toBe(saved.id)
    expect(stored.activeNodeId).toBe(IDS.followup)

    const trail = await screen.findByRole('navigation', { name: 'Research trail' })
    expect(trail).toHaveTextContent(saved.query)
    expect(trail).toHaveTextContent('Who was Cain?')
    fireEvent.click(within(trail).getByRole('button', { name: saved.query }))
    expect(screen.getByRole('heading', { name: saved.query })).toBeInTheDocument()
  })

  it('revalidates a local parent before its first authenticated follow-up', async () => {
    const pending = deferred()
    let status = 'loading'
    useAuth.mockImplementation(() => ({
      status,
      user: status === 'authenticated' ? { id: 'user-1' } : null,
    }))
    runResearch
      .mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce(response({
        query: 'Who was Cain?',
        trailNode: { id: IDS.node, parentNodeId: null, question: 'Who was Cain?', label: null },
      }))
      .mockResolvedValueOnce(response({
        id: IDS.followup,
        query: 'What happened to Cain after Abel’s death?',
        trailNode: { id: IDS.followup, parentNodeId: IDS.node, question: 'What happened to Cain after Abel’s death?', label: null },
      }))
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Who was Cain?')

    status = 'authenticated'
    rerender(<ScriptureResearchPage />)
    await act(async () => pending.resolve(response({ query: 'Who was Cain?', trailNode: null })))

    expect(await screen.findByRole('heading', { name: 'Who was Cain?' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Research trail' })).toHaveTextContent('Who was Cain?')
    fireEvent.click(screen.getByRole('button', { name: 'What happened to Cain after Abel’s death?' }))
    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(3))
    expect(runResearch.mock.calls[1][0]).toMatchObject({ question: 'Who was Cain?' })
    expect(runResearch.mock.calls[1][0]).not.toHaveProperty('parentNodeId')
    expect(runResearch.mock.calls[1][0]).not.toHaveProperty('conversationContext')
    expect(runResearch.mock.calls[2][0]).toMatchObject({
      question: 'What happened to Cain after Abel’s death?',
      parentNodeId: IDS.node,
    })
    expect(runResearch.mock.calls[2][0]).not.toHaveProperty('conversationContext')
    const trail = await screen.findByRole('navigation', { name: 'Research trail' })
    expect(within(trail).getByRole('button', { name: 'Who was Cain?' })).toBeInTheDocument()
    expect(within(trail).getByRole('button', { name: 'What happened to Cain after Abel’s death?' })).toBeInTheDocument()
  })

  it('reuses the authoritative parent when a revalidated child request is retried', async () => {
    const parent = response({ query: 'Who was Cain?', trailNode: null })
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: {
        nodes: [{ id: parent.id, parentNodeId: null, response: parent }],
        activeNodeId: parent.id,
        settings: parent.settings,
      },
    }))
    let auth = { status: 'anonymous', user: null }
    useAuth.mockImplementation(() => auth)
    runResearch
      .mockResolvedValueOnce(response({
        query: 'Who was Cain?',
        trailNode: { id: IDS.node, parentNodeId: null, question: 'Who was Cain?', label: null },
      }))
      .mockRejectedValueOnce(new Error('Child request unavailable'))
      .mockResolvedValueOnce(response({
        id: IDS.followup,
        query: 'What happened to Cain after Abel’s death?',
        trailNode: { id: IDS.followup, parentNodeId: IDS.node, question: 'What happened to Cain after Abel’s death?', label: null },
      }))
    const { rerender } = render(<ScriptureResearchPage />)
    auth = { status: 'authenticated', user: { id: 'user-1' } }
    rerender(<ScriptureResearchPage />)

    fireEvent.click(screen.getByRole('button', { name: 'What happened to Cain after Abel’s death?' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Child request unavailable')
    expect(screen.getByLabelText('Research question')).toHaveValue('What happened to Cain after Abel’s death?')
    fireEvent.click(screen.getByRole('button', { name: 'Retry research' }))

    await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(3))
    expect(runResearch.mock.calls.filter(([request]) => request.question === 'Who was Cain?')).toHaveLength(1)
    expect(runResearch.mock.calls[2][0]).toMatchObject({
      question: 'What happened to Cain after Abel’s death?',
      parentNodeId: IDS.node,
    })
    expect(runResearch.mock.calls[2][0]).not.toHaveProperty('conversationContext')
    const trail = await screen.findByRole('navigation', { name: 'Research trail' })
    expect(within(trail).getByRole('button', { name: 'Who was Cain?' })).toBeInTheDocument()
    expect(within(trail).getByRole('button', { name: 'What happened to Cain after Abel’s death?' })).toBeInTheDocument()
  })

  it.each(['insufficient', 'evidence-only', 'failure'])(
    'keeps the follow-up visible and retryable when parent revalidation ends with %s',
    async (outcome) => {
      const parent = response({ query: 'Who was Cain?', trailNode: null })
      localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
        version: 1,
        session: {
          nodes: [{ id: parent.id, parentNodeId: null, response: parent }],
          activeNodeId: parent.id,
          settings: parent.settings,
        },
      }))
      let auth = { status: 'anonymous', user: null }
      useAuth.mockImplementation(() => auth)
      if (outcome === 'failure') runResearch.mockRejectedValueOnce(new Error('Parent validation unavailable'))
      else runResearch.mockResolvedValueOnce(response({
        query: 'Who was Cain?',
        groundingStatus: outcome,
        trailNode: { id: IDS.node, parentNodeId: null, question: 'Who was Cain?', label: null },
      }))
      runResearch
        .mockResolvedValueOnce(response({
          query: 'Who was Cain?',
          trailNode: { id: IDS.node, parentNodeId: null, question: 'Who was Cain?', label: null },
        }))
        .mockResolvedValueOnce(response({
          id: IDS.followup,
          query: 'What happened to Cain after Abel’s death?',
          trailNode: { id: IDS.followup, parentNodeId: IDS.node, question: 'What happened to Cain after Abel’s death?', label: null },
        }))
      const { rerender } = render(<ScriptureResearchPage />)
      auth = { status: 'authenticated', user: { id: 'user-1' } }
      rerender(<ScriptureResearchPage />)

      fireEvent.click(screen.getByRole('button', { name: 'What happened to Cain after Abel’s death?' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(/prior research.*revalidated/i)
      expect(screen.getByLabelText('Research question')).toHaveValue('What happened to Cain after Abel’s death?')
      expect(screen.queryByRole('heading', { name: 'Who was Cain?' })).not.toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Retry research' }))

      await waitFor(() => expect(runResearch).toHaveBeenCalledTimes(3))
      expect(runResearch.mock.calls[1][0]).toMatchObject({ question: 'Who was Cain?' })
      expect(runResearch.mock.calls[2][0]).toMatchObject({
        question: 'What happened to Cain after Abel’s death?',
        parentNodeId: IDS.node,
      })
      expect(await screen.findByRole('heading', { name: 'What happened to Cain after Abel’s death?' })).toBeInTheDocument()
    },
  )

  it('stops authenticated local-parent revalidation when the principal changes mid-chain', async () => {
    const saved = response({ query: 'Who was Cain?', trailNode: null })
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({
      version: 1,
      session: {
        nodes: [{ id: saved.id, parentNodeId: null, response: saved }],
        activeNodeId: saved.id,
        settings: saved.settings,
      },
    }))
    const pendingParent = deferred()
    let auth = { status: 'anonymous', user: null }
    useAuth.mockImplementation(() => auth)
    runResearch.mockReturnValueOnce(pendingParent.promise)
    const { rerender } = render(<ScriptureResearchPage />)
    auth = { status: 'authenticated', user: { id: 'user-a' } }
    rerender(<ScriptureResearchPage />)

    fireEvent.click(screen.getByRole('button', { name: 'What happened to Cain after Abel’s death?' }))
    await waitFor(() => expect(runResearch).toHaveBeenCalledOnce())
    const parentSignal = runResearch.mock.calls[0][1].signal
    auth = { status: 'authenticated', user: { id: 'user-b' } }
    rerender(<ScriptureResearchPage />)
    expect(parentSignal.aborted).toBe(true)
    await act(async () => pendingParent.resolve(response({
      query: 'Who was Cain?',
      trailNode: { id: IDS.node, parentNodeId: null, question: 'Who was Cain?', label: null },
    })))

    expect(runResearch).toHaveBeenCalledOnce()
    expect(screen.queryByRole('heading', { name: 'Who was Cain?' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Research question')).toHaveValue('')
  })

  it('retains the local trail when authentication resolves after query completion', async () => {
    const pending = deferred()
    let status = 'loading'
    useAuth.mockImplementation(() => ({
      status,
      user: status === 'authenticated' ? { id: 'user-1' } : null,
    }))
    runResearch.mockReturnValueOnce(pending.promise)
    const { rerender } = render(<ScriptureResearchPage />)
    submitQuestion('Who was Cain?')

    await act(async () => pending.resolve(response({ query: 'Who was Cain?', trailNode: null })))
    expect(await screen.findByRole('navigation', { name: 'Research trail' })).toHaveTextContent('Who was Cain?')

    status = 'authenticated'
    rerender(<ScriptureResearchPage />)
    expect(screen.getByRole('navigation', { name: 'Research trail' })).toHaveTextContent('Who was Cain?')
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
    expect(linkResearchStudy).toHaveBeenCalledWith(IDS.node, 'study-1')
    expect(await screen.findByText(/saved privately/i)).toHaveAttribute('role', 'status')
  })

  it('shares one in-flight persistence operation across rapid Save and Share actions', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    runResearch.mockResolvedValue(response())
    const creatingStudy = deferred()
    api.post.mockImplementation((url) => (
      url === '/studies' ? creatingStudy.promise : Promise.resolve({})
    ))
    render(<ScriptureResearchPage />)
    submitQuestion()
    const save = await screen.findByRole('button', { name: 'Save research' })
    const share = screen.getByRole('button', { name: 'Share research' })

    fireEvent.click(save)
    fireEvent.click(share)

    expect(api.post.mock.calls.filter(([url]) => url === '/studies')).toHaveLength(1)
    expect(save).toBeDisabled()
    expect(share).toBeDisabled()
    await act(async () => creatingStudy.resolve({ id: 'study-1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Share research' }))

    expect(await screen.findByRole('dialog', { name: 'Share study session' })).toBeInTheDocument()
    expect(api.post.mock.calls.filter(([url]) => url === '/studies')).toHaveLength(1)
  })

  it('retries partial authenticated persistence without duplicating completed writes', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    runResearch.mockResolvedValue(response())
    let assistantAttempts = 0
    api.post.mockImplementation((url, payload) => {
      if (url === '/studies') return Promise.resolve({ id: 'study-1' })
      if (url.endsWith('/messages') && payload.role === 'assistant') {
        assistantAttempts += 1
        return assistantAttempts === 1
          ? Promise.reject(new Error('assistant write failed'))
          : Promise.resolve({})
      }
      return Promise.resolve({})
    })
    render(<ScriptureResearchPage />)
    submitQuestion()
    const save = await screen.findByRole('button', { name: 'Save research' })

    fireEvent.click(save)
    expect(await screen.findByText(/could not be saved/i)).toHaveTextContent('assistant write failed')
    fireEvent.click(save)
    expect(await screen.findByText(/saved privately/i)).toBeInTheDocument()

    expect(api.post.mock.calls.filter(([url]) => url === '/studies')).toHaveLength(1)
    expect(api.post.mock.calls.filter(([url, payload]) => url.endsWith('/messages') && payload.role === 'user')).toHaveLength(1)
    expect(api.post.mock.calls.filter(([url, payload]) => url.endsWith('/messages') && payload.role === 'assistant')).toHaveLength(2)
    expect(api.post.mock.calls.filter(([url]) => url.endsWith('/sources'))).toHaveLength(1)
  })

  it('saves guest research to the existing resilient local study collection', async () => {
    localStorage.setItem('unbound_saved_studies', '{malformed')
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'Save research' }))

    const saved = JSON.parse(localStorage.getItem('unbound_saved_studies'))
    expect(saved).toHaveLength(1)
    expect(saved[0]).toMatchObject({
      type: 'scripture-research',
      question: 'What happened between Eden and Abel?',
      title: expect.stringContaining('Eden and Abel'),
      result: expect.stringContaining('Genesis records expulsion'),
      sources: [{ title: 'Genesis', reference: 'Genesis 2–4' }],
    })
    expect(saved[0].date).toEqual(expect.any(String))
    expect(screen.getByText(/saved to My Library on this device/i)).toHaveAttribute('role', 'status')
    expect(api.post).not.toHaveBeenCalled()
  })

  it.each([
    ['/api/v1/texts/Genesis/9/1/details', '#scriptures?book=Genesis&chapter=9&translation=KJV&canon=ETHIO81&verse=1'],
    ['bible://Genesis/3', '#scriptures?book=Genesis&chapter=3&translation=KJV&canon=ETHIO81'],
    ['#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81&verse=2', '#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81&verse=2'],
  ])('opens the internal full-text target %s without losing reader parameters', async (openTarget, expectedHash) => {
    const onPageChange = vi.fn()
    const source = response().sources[0]
    runResearch.mockResolvedValue(response({ sources: [{ ...source, openTarget }] }))
    render(<ScriptureResearchPage onPageChange={onPageChange} />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'Cite Genesis 2–4' }))
    fireEvent.click(screen.getByRole('button', { name: /Open Full Text/i }))

    expect(onPageChange).toHaveBeenCalledWith('apocrypha')
    expect(window.location.hash).toBe(expectedHash)
  })

  it.each([
    ['/api/v1/texts/Genesis/9/1/details', '#scriptures?book=Genesis&chapter=9&translation=NRSV&canon=ETHIO81&verse=1'],
    ['/api/v1/texts/Genesis/9/1/details?translation=WEB', '#scriptures?book=Genesis&chapter=9&translation=WEB&canon=ETHIO81&verse=1'],
    ['bible://Genesis/3', '#scriptures?book=Genesis&chapter=3&translation=NRSV&canon=ETHIO81'],
    ['bible://Genesis/3?translation=WEB', '#scriptures?book=Genesis&chapter=3&translation=WEB&canon=ETHIO81'],
    ['#scriptures?book=Exodus&chapter=3&canon=ETHIO81&verse=2', '#scriptures?book=Exodus&chapter=3&translation=NRSV&canon=ETHIO81&verse=2'],
    ['#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81', '#scriptures?book=Exodus&chapter=3&translation=KJV&canon=ETHIO81'],
  ])('opens %s in its source translation unless the target supplies one', async (openTarget, expectedHash) => {
    const source = response().sources[0]
    runResearch.mockResolvedValue(response({
      sources: [{ ...source, translation: 'NRSV', openTarget }],
    }))
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'Cite Genesis 2–4' }))
    fireEvent.click(screen.getByRole('button', { name: /Open Full Text/i }))

    expect(window.location.hash).toBe(expectedHash)
  })

  it('opens ShareStudyModal with meaningful result data', async () => {
    useAuth.mockReturnValue({ status: 'authenticated', user: { id: 'user-1' } })
    runResearch.mockResolvedValue(response())
    api.post.mockResolvedValueOnce({ id: 'study-1' }).mockResolvedValue({})
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'Share research' }))

    const dialog = await screen.findByRole('dialog', { name: 'Share study session' })
    expect(dialog).toBeInTheDocument()
    expect(within(dialog).getByText('Scripture Research AI')).toBeInTheDocument()
    expect(within(dialog).getByText(/Eden and Abel/)).toBeInTheDocument()
  })

  it('does not open a dead share dialog for guests and gives a sign-in path', async () => {
    runResearch.mockResolvedValue(response())
    render(<ScriptureResearchPage />)
    submitQuestion()
    fireEvent.click(await screen.findByRole('button', { name: 'Share research' }))

    expect(screen.queryByRole('dialog', { name: 'Share study session' })).not.toBeInTheDocument()
    expect(await screen.findByText(/sign in.*top navigation.*share/i)).toHaveAttribute('role', 'status')
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
