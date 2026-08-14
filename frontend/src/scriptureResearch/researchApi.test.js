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
  normalizeResearchEvents,
  normalizeResearchResponse,
  normalizeResearchTrail,
  ResearchClientError,
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
    sources: [{ ...source }],
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
      question: 'Compare it',
      sessionId: '9b913a39-d88c-413c-ac5e-f23372161289',
      parentNodeId: '07449bd5-e672-4504-ab7d-45a1e6615cb1',
      mode: 'timeline', sourceScopes: ['historical-sources'], depth: 'study',
      modeParameters: { from: 'Eden' }, ignored: undefined,
    }
    const snapshot = structuredClone(input)

    expect(toApiRequest(input)).toEqual({
      question: 'Compare it',
      session_id: '9b913a39-d88c-413c-ac5e-f23372161289',
      parent_node_id: '07449bd5-e672-4504-ab7d-45a1e6615cb1',
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
      ancestry: [{ id: '9b913a39-d88c-413c-ac5e-f23372161289', parent_node_id: null, question: 'Root question', mode: 'research-question', created_at: '2026-08-14T00:00:00Z', updated_at: null }],
      active: { id: '07449bd5-e672-4504-ab7d-45a1e6615cb1', parent_node_id: '9b913a39-d88c-413c-ac5e-f23372161289', question: 'Child question', mode: 'timeline', created_at: null, updated_at: null },
      children: [],
      children_truncated: false,
    })
    const trail = await getResearchTrail('07449bd5-e672-4504-ab7d-45a1e6615cb1', { signal })
    expect(api.get).toHaveBeenLastCalledWith('/research/trail/07449bd5-e672-4504-ab7d-45a1e6615cb1', { signal })
    expect(trail).toMatchObject({
      ancestry: [{ parentNodeId: null, createdAt: '2026-08-14T00:00:00Z' }],
      active: { id: '07449bd5-e672-4504-ab7d-45a1e6615cb1', parentNodeId: '9b913a39-d88c-413c-ac5e-f23372161289' },
      children: [],
      childrenTruncated: false,
    })
    expect(Object.isFrozen(trail.active)).toBe(true)
  })

  it('normalizes and freezes reviewed event results', async () => {
    api.get.mockResolvedValue({
      events: [{
        id: 'eden',
        title: 'Life in the Garden of Eden',
        description: 'The man and woman live in Eden.',
        reference: 'Genesis 2:8–25',
        source_ids: ['genesis-2'],
        people: ['adam', 'eve'],
        places: ['garden-of-eden'],
      }],
    })

    const result = await searchResearchEvents('Eden')

    expect(result).toEqual({ events: [{
      id: 'eden',
      title: 'Life in the Garden of Eden',
      description: 'The man and woman live in Eden.',
      reference: 'Genesis 2:8–25',
      sourceIds: ['genesis-2'],
      people: ['adam', 'eve'],
      places: ['garden-of-eden'],
    }] })
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.events[0].sourceIds)).toBe(true)
  })

  it('rejects malformed, oversized, and duplicate event data', () => {
    expect(() => normalizeResearchEvents({ events: [{ id: 'eden' }] })).toThrow(/title/i)
    expect(() => normalizeResearchEvents({ events: Array.from({ length: 65 }, () => ({})) })).toThrow(/events.*64/i)
    expect(() => normalizeResearchEvents({
      events: [{
        id: 'eden', title: 'Eden', description: 'Description', reference: 'Genesis 2',
        source_ids: ['same', 'same'], people: [], places: [],
      }],
    })).toThrow(/duplicate source ID/i)
    const event = {
      id: 'eden', title: 'Eden', description: 'Description', reference: 'Genesis 2',
      source_ids: ['genesis-2'], people: [], places: [],
    }
    expect(() => normalizeResearchEvents({ events: [event, { ...event }] })).toThrow(/duplicate event ID/i)
  })

  it.each([
    ['non-object input', null],
    ['short question', { question: 'x' }],
    ['bad session ID', { question: 'Valid?', sessionId: 'session' }],
    ['bad parent ID', { question: 'Valid?', parentNodeId: 12 }],
    ['bad mode', { question: 'Valid?', mode: 'web-search' }],
    ['bad source scope', { question: 'Valid?', sourceScopes: ['the-web'] }],
    ['bad depth', { question: 'Valid?', depth: 'unbounded' }],
    ['bad mode parameter', { question: 'Valid?', modeParameters: { from: 12 } }],
  ])('rejects %s before calling the API', (_name, input) => {
    expect(() => runResearch(input)).toThrow()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('normalizes UUID identifiers and trimmed mode parameters without mutating input', () => {
    const input = {
      question: '  Compare it  ',
      sessionId: '9b913a39-d88c-413c-ac5e-f23372161289',
      parentNodeId: '07449bd5-e672-4504-ab7d-45a1e6615cb1',
      modeParameters: { ' from ': ' Eden ' },
    }
    const snapshot = structuredClone(input)

    expect(toApiRequest(input)).toMatchObject({
      question: '  Compare it  ',
      session_id: input.sessionId,
      parent_node_id: input.parentNodeId,
      mode_parameters: { from: 'Eden' },
    })
    expect(input).toEqual(snapshot)
  })

  it('omits null identifiers and uses the typed client boundary error', () => {
    expect(toApiRequest({ question: 'Valid?', sessionId: null, parentNodeId: undefined })).toEqual({
      question: 'Valid?',
      mode: 'what-happened-between',
      source_scopes: ['biblical-canon'],
      depth: 'deep-research',
      mode_parameters: {},
    })
    expect(() => toApiRequest({ question: 'Valid?', sessionId: 'not-a-uuid' })).toThrow(ResearchClientError)
  })

  it('preserves prototype-sensitive mode parameters as serialized own properties', () => {
    const modeParameters = JSON.parse('{"__proto__":"kept","constructor":"also kept","prototype":"still kept"}')
    const request = toApiRequest({ question: 'Valid?', modeParameters })

    expect(Object.hasOwn(request.mode_parameters, '__proto__')).toBe(true)
    expect(Object.hasOwn(request.mode_parameters, 'constructor')).toBe(true)
    expect(Object.hasOwn(request.mode_parameters, 'prototype')).toBe(true)
    expect(request.mode_parameters.__proto__).toBe('kept')
    expect(JSON.stringify(request)).toContain('"__proto__":"kept"')
  })

  it('rejects invalid event queries and trail IDs before calling the API', () => {
    expect(() => searchResearchEvents(123)).toThrow(/query.*string/i)
    expect(() => searchResearchEvents('x'.repeat(4_097))).toThrow(/query.*4,?096/i)
    expect(() => getResearchTrail('not-a-uuid')).toThrow(/nodeId.*UUID/i)
    expect(api.get).not.toHaveBeenCalled()
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

  it.each([
    ['claim', (value) => { value.summary.claims[0].source_ids = [source.id, source.id] }],
    ['timeline event', (value) => { value.timeline[0].source_ids = [source.id, source.id] }],
    ['person', (value) => { value.people[0].source_ids = [source.id, source.id] }],
    ['place', (value) => { value.places[0].source_ids = [source.id, source.id] }],
  ])('rejects duplicate source IDs in a %s', (_name, mutate) => {
    const value = validEdenResponse()
    mutate(value)
    expect(() => normalizeResearchResponse(value)).toThrow(/duplicate source ID/i)
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

  it.each([
    ['response ID', (value) => { value.id = 'not-a-uuid' }],
    ['trail node ID', (value) => { value.trail_node.id = 'not-a-uuid' }],
    ['trail parent node ID', (value) => { value.trail_node.parent_node_id = 'not-a-uuid' }],
  ])('rejects a malformed server-issued %s', (_name, mutate) => {
    const value = validEdenResponse()
    mutate(value)
    expect(() => normalizeResearchResponse(value)).toThrow(/UUID/i)
  })

  it('rejects malformed UUIDs throughout research trail snapshots', () => {
    const trail = {
      ancestry: [{ id: '9b913a39-d88c-413c-ac5e-f23372161289', parent_node_id: null, question: 'Root question', mode: 'research-question', created_at: null, updated_at: null }],
      active: { id: '07449bd5-e672-4504-ab7d-45a1e6615cb1', parent_node_id: '9b913a39-d88c-413c-ac5e-f23372161289', question: 'Child question', mode: 'timeline', created_at: null, updated_at: null },
      children: [{ id: 'c8d77469-b3ca-40ad-a15b-9c228cd00898', parent_node_id: '07449bd5-e672-4504-ab7d-45a1e6615cb1', question: 'Next question', mode: 'timeline', created_at: null, updated_at: null }],
      children_truncated: false,
    }
    const badActive = structuredClone(trail)
    badActive.active.id = 'child'
    expect(() => normalizeResearchTrail(badActive)).toThrow(/active.id.*UUID/i)

    const badAncestryParent = structuredClone(trail)
    badAncestryParent.ancestry[0].parent_node_id = 'root'
    expect(() => normalizeResearchTrail(badAncestryParent)).toThrow(/ancestry.*parent_node_id.*UUID/i)

    const badChild = structuredClone(trail)
    badChild.children[0].id = 'next'
    expect(() => normalizeResearchTrail(badChild)).toThrow(/children.*id.*UUID/i)
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

  it.each([
    ['duplicate node IDs', [
      { id: 'guest-a', parentNodeId: null, response: validEdenResponse() },
      { id: 'guest-a', parentNodeId: null, response: validEdenResponse() },
    ]],
    ['a self parent', [
      { id: 'guest-a', parentNodeId: 'guest-a', response: validEdenResponse() },
    ]],
    ['a missing parent', [
      { id: 'guest-a', parentNodeId: 'missing', response: validEdenResponse() },
    ]],
    ['a two-node cycle', [
      { id: 'guest-a', parentNodeId: 'guest-b', response: validEdenResponse() },
      { id: 'guest-b', parentNodeId: 'guest-a', response: validEdenResponse() },
    ]],
  ])('rejects guest topology with %s on save and load', (_name, nodes) => {
    const session = {
      nodes,
      activeNodeId: null,
      settings: { sourceScopes: ['biblical-canon'], depth: 'study', modeParameters: {} },
    }
    expect(saveGuestResearchSession(session)).toBe(false)
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()

    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, JSON.stringify({ version: 1, session }))
    expect(loadGuestResearchSession()).toEqual(EMPTY_RESEARCH_SESSION)
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })

  it('clears the versioned key safely', () => {
    localStorage.setItem(GUEST_RESEARCH_STORAGE_KEY, '{}')
    expect(clearGuestResearchSession()).toBe(true)
    expect(localStorage.getItem(GUEST_RESEARCH_STORAGE_KEY)).toBeNull()
  })
})
