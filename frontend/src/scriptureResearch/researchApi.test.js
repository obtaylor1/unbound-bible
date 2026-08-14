import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import { api } from '../api/client'
import {
  clearGuestResearchSession,
  getResearchTrail,
  GUEST_RESEARCH_STORAGE_KEY,
  loadGuestResearchSession,
  normalizeResearchResponse,
  runResearch,
  saveGuestResearchSession,
  searchResearchEvents,
  toApiRequest,
} from './researchApi'
import {
  createEmptyResearchSession,
  DEFAULT_RESEARCH_SETTINGS,
  EMPTY_RESEARCH_SESSION,
  RESEARCH_DEPTHS,
  RESEARCH_MODES,
  SOURCE_SCOPES,
} from './researchModel'

const source = {
  id: 'genesis-3-4',
  title: 'Genesis',
  reference: 'Genesis 3–4',
  excerpt: 'They left Eden.',
  text: 'A longer source text.',
  source_type: 'canonical-scripture',
  tradition: 'biblical canon',
  date_or_era: 'Ancient',
  original_language: 'Hebrew',
  translation: 'Example translation',
  relevance: 'Primary canonical account',
  open_target: 'bible://Genesis/3',
}

const claim = (id) => ({
  id,
  statement: 'A grounded claim.',
  classification: 'canonical-scripture',
  confidence: 'high',
  source_ids: [source.id],
})

function validEdenResponse() {
  return {
    id: '9b913a39-d88c-413c-ac5e-f23372161289',
    query: 'What happened between Eden and Abel?',
    mode: 'what-happened-between',
    settings: {
      source_scopes: ['biblical-canon', 'ethiopian-tradition'],
      depth: 'scholar',
      mode_parameters: { from: 'Eden', to: 'Abel' },
    },
    summary: { title: 'Summary', narrative: 'A summary.', claims: [claim('summary')] },
    timeline: [{
      title: 'Outside Eden',
      description: 'The family lived outside Eden.',
      date_label: 'After Eden',
      source_ids: [source.id],
      confidence: 'high',
    }],
    canonical_account: { title: 'Canonical account', narrative: null, claims: [claim('canonical')] },
    historical_context: { title: 'Historical context', narrative: null, claims: [claim('history')] },
    unknowns: { title: 'Unknowns', narrative: null, claims: [claim('unknown')] },
    ancient_accounts: [{ title: 'Ancient accounts', narrative: null, claims: [claim('ancient')] }],
    language_notes: [{ title: 'Language notes', narrative: null, claims: [claim('language')] }],
    people: [{ name: 'Abel', description: null, role: 'son', source_ids: [source.id] }],
    places: [{ name: 'Eden', description: null, location: 'unknown', source_ids: [source.id] }],
    trail_node: {
      id: '07449bd5-e672-4504-ab7d-45a1e6615cb1',
      parent_node_id: null,
      question: 'What happened between Eden and Abel?',
      label: 'Eden to Abel',
    },
    sources: [source],
    related_questions: ['What happened next?'],
    grounding_status: 'grounded',
    provider: 'test-provider',
    model: 'test-model',
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('research model', () => {
  it('exports exact immutable options and defaults', () => {
    expect(SOURCE_SCOPES).toEqual([
      { value: 'biblical-canon', label: 'Biblical Canon' },
      { value: 'ethiopian-tradition', label: 'Ethiopian Tradition' },
      { value: 'ancient-accounts', label: 'Ancient Accounts' },
      { value: 'historical-sources', label: 'Historical Sources' },
      { value: 'commentaries', label: 'Commentaries' },
      { value: 'language-resources', label: 'Language Resources' },
      { value: 'user-library', label: 'User Library' },
      { value: 'all-sources', label: 'All Sources' },
    ])
    expect(RESEARCH_DEPTHS).toEqual([
      { value: 'quick', label: 'Quick Answer' },
      { value: 'study', label: 'Study' },
      { value: 'deep-research', label: 'Deep Research' },
      { value: 'scholar', label: 'Scholar' },
    ])
    expect(RESEARCH_MODES).toEqual([
      { value: 'what-happened-between', label: 'What Happened Between?' },
      { value: 'research-question', label: 'Research Question' },
      { value: 'topic-research', label: 'Topic Research' },
      { value: 'person-study', label: 'Person Study' },
      { value: 'place-study', label: 'Place Study' },
      { value: 'timeline', label: 'Timeline' },
      { value: 'people-and-places', label: 'People & Places' },
    ])
    expect(DEFAULT_RESEARCH_SETTINGS).toEqual({
      sourceScopes: ['biblical-canon'], depth: 'deep-research', modeParameters: {},
    })
    expect(Object.isFrozen(SOURCE_SCOPES)).toBe(true)
    expect(Object.isFrozen(SOURCE_SCOPES[0])).toBe(true)
    expect(Object.isFrozen(DEFAULT_RESEARCH_SETTINGS.sourceScopes)).toBe(true)
  })

  it('creates empty sessions without shared mutable structures', () => {
    const first = createEmptyResearchSession()
    const second = createEmptyResearchSession()
    expect(first).toEqual(EMPTY_RESEARCH_SESSION)
    expect(first).not.toBe(second)
    expect(first.nodes).not.toBe(second.nodes)
    expect(first.settings).not.toBe(second.settings)
  })
})

describe('research requests', () => {
  it('sends approved defaults and the signal through the shared API client', async () => {
    const signal = new AbortController().signal
    api.post.mockResolvedValue(validEdenResponse())

    await runResearch({ question: 'What happened between Eden and Abel?' }, { signal })

    expect(api.post).toHaveBeenCalledWith('/research/query', {
      question: 'What happened between Eden and Abel?',
      mode: 'what-happened-between',
      source_scopes: ['biblical-canon'],
      depth: 'deep-research',
      mode_parameters: {},
    }, { signal })
  })

  it('converts custom camel-case fields and omits undefined values without mutation', () => {
    const input = {
      question: 'Compare it', sessionId: 'session', parentNodeId: 'parent',
      mode: 'timeline', sourceScopes: ['historical-sources'], depth: 'study',
      modeParameters: { from: 'Eden' }, ignored: undefined,
    }
    const snapshot = structuredClone(input)

    expect(toApiRequest(input)).toEqual({
      question: 'Compare it', session_id: 'session', parent_node_id: 'parent',
      mode: 'timeline', source_scopes: ['historical-sources'], depth: 'study',
      mode_parameters: { from: 'Eden' },
    })
    expect(input).toEqual(snapshot)
  })

  it('encodes event queries and trail node IDs', async () => {
    const signal = new AbortController().signal
    api.get.mockResolvedValue({ events: [] })
    await searchResearchEvents("Cain's birth & Eden", { signal })
    expect(api.get).toHaveBeenCalledWith('/research/events?q=Cain%27s%20birth%20%26%20Eden', { signal })

    api.get.mockResolvedValue({
      ancestry: [{ id: 'root', parent_node_id: null, question: 'Root question', mode: 'research-question', created_at: '2026-08-14T00:00:00Z', updated_at: null }],
      active: { id: 'child', parent_node_id: 'root', question: 'Child question', mode: 'timeline', created_at: null, updated_at: null },
      children: [],
      children_truncated: false,
    })
    const trail = await getResearchTrail('node/with space', { signal })
    expect(api.get).toHaveBeenLastCalledWith('/research/trail/node%2Fwith%20space', { signal })
    expect(trail).toMatchObject({
      ancestry: [{ parentNodeId: null, createdAt: '2026-08-14T00:00:00Z' }],
      active: { id: 'child', parentNodeId: 'root' },
      children: [],
      childrenTruncated: false,
    })
    expect(Object.isFrozen(trail.active)).toBe(true)
  })
})

describe('response normalization', () => {
  it('normalizes the full Eden fixture once and deeply freezes it', () => {
    const raw = validEdenResponse()
    const untouched = structuredClone(raw)
    const result = normalizeResearchResponse(raw)

    expect(result).toMatchObject({
      id: raw.id,
      settings: { sourceScopes: ['biblical-canon', 'ethiopian-tradition'], modeParameters: { from: 'Eden', to: 'Abel' } },
      timeline: [{ dateLabel: 'After Eden', sourceIds: [source.id] }],
      canonicalAccount: { claims: [{ sourceIds: [source.id] }] },
      historicalContext: { claims: [{ id: 'history' }] },
      ancientAccounts: [{ claims: [{ id: 'ancient' }] }],
      languageNotes: [{ claims: [{ id: 'language' }] }],
      people: [{ sourceIds: [source.id] }],
      places: [{ sourceIds: [source.id] }],
      trailNode: { parentNodeId: null },
      sources: [{ sourceType: 'canonical-scripture', dateOrEra: 'Ancient', originalLanguage: 'Hebrew', openTarget: 'bible://Genesis/3' }],
      relatedQuestions: ['What happened next?'],
      groundingStatus: 'grounded',
    })
    expect(result.summary.source_ids).toBeUndefined()
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.summary.claims[0].sourceIds)).toBe(true)
    expect(raw).toEqual(untouched)
  })

  it.each([
    ['summary claim', (value) => { value.summary.claims[0].source_ids = ['missing'] }],
    ['timeline event', (value) => { value.timeline[0].source_ids = ['missing'] }],
    ['person', (value) => { value.people[0].source_ids = ['missing'] }],
    ['place', (value) => { value.places[0].source_ids = ['missing'] }],
    ['nested section claim', (value) => { value.language_notes[0].claims[0].source_ids = ['missing'] }],
  ])('rejects an unknown source ID in a %s', (_name, mutate) => {
    const value = validEdenResponse()
    mutate(value)
    expect(() => normalizeResearchResponse(value)).toThrow(/unknown source ID/i)
  })

  it('rejects duplicate sources, missing required fields, malformed arrays, and invalid grounding', () => {
    const duplicate = validEdenResponse()
    duplicate.sources.push({ ...source })
    expect(() => normalizeResearchResponse(duplicate)).toThrow(/duplicate source ID/i)

    const missing = validEdenResponse()
    delete missing.summary
    expect(() => normalizeResearchResponse(missing)).toThrow(/summary/i)

    const malformed = validEdenResponse()
    malformed.people = {}
    expect(() => normalizeResearchResponse(malformed)).toThrow(/people.*array/i)

    const invalidGrounding = validEdenResponse()
    invalidGrounding.grounding_status = 'unknown'
    expect(() => normalizeResearchResponse(invalidGrounding)).toThrow(/grounding status/i)
  })

  it('rejects absurd collection and string sizes', () => {
    const tooManySources = validEdenResponse()
    tooManySources.sources = Array.from({ length: 33 }, (_, index) => ({ ...source, id: `source-${index}` }))
    tooManySources.summary.claims = []
    tooManySources.timeline = []
    tooManySources.canonical_account.claims = []
    tooManySources.historical_context.claims = []
    tooManySources.unknowns.claims = []
    tooManySources.ancient_accounts = []
    tooManySources.language_notes = []
    tooManySources.people = []
    tooManySources.places = []
    expect(() => normalizeResearchResponse(tooManySources)).toThrow(/sources.*32/i)

    const tooManyRelated = validEdenResponse()
    tooManyRelated.related_questions = Array.from({ length: 6 }, () => 'Question?')
    expect(() => normalizeResearchResponse(tooManyRelated)).toThrow(/related_questions.*5/i)

    const tooLong = validEdenResponse()
    tooLong.summary.claims[0].statement = 'x'.repeat(50_001)
    expect(() => normalizeResearchResponse(tooLong)).toThrow(/statement.*50,?000/i)
  })
})

describe('guest research storage', () => {
  it('round trips only validated normalized data', () => {
    const response = normalizeResearchResponse(validEdenResponse())
    const session = {
      nodes: [{ id: 'guest-1', parentNodeId: null, response }],
      activeNodeId: 'guest-1',
      settings: { sourceScopes: ['biblical-canon'], depth: 'study', modeParameters: {} },
    }

    expect(saveGuestResearchSession(session)).toBe(true)
    const loaded = loadGuestResearchSession()
    expect(loaded.nodes[0].response).toEqual(response)
    expect(Object.isFrozen(loaded.nodes[0].response)).toBe(true)
    expect(JSON.parse(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY))).toMatchObject({ version: 1 })
  })

  it.each([
    ['corrupt JSON', '{broken'],
    ['wrong version', JSON.stringify({ version: 999, session: {} })],
  ])('returns empty and removes %s storage', (_name, stored) => {
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, stored)
    expect(loadGuestResearchSession()).toEqual(EMPTY_RESEARCH_SESSION)
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })

  it('handles quota failures and oversized sessions without throwing', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Quota exceeded', 'QuotaExceededError')
    })
    expect(saveGuestResearchSession(createEmptyResearchSession())).toBe(false)
    setItem.mockRestore()

    const oversizedResponse = validEdenResponse()
    oversizedResponse.sources[0].excerpt = 'x'.repeat(250_000)
    oversizedResponse.sources[0].text = 'x'.repeat(250_000)
    expect(saveGuestResearchSession({
      ...createEmptyResearchSession(),
      nodes: [{ id: 'guest-1', parentNodeId: null, response: oversizedResponse }],
    })).toBe(false)
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })

  it('clears the versioned key safely', () => {
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, '{}')
    expect(clearGuestResearchSession()).toBe(true)
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })
})
