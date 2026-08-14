import { api } from '../api/client'
import {
  createEmptyResearchSession,
  DEFAULT_RESEARCH_MODE,
  DEFAULT_RESEARCH_SETTINGS,
  RESEARCH_DEPTHS,
  RESEARCH_MODES,
  SOURCE_SCOPES,
  deepFreeze,
} from './researchModel'

export const GUEST_RESEARCH_STORAGE_KEY = 'unbound.scriptureResearch.v1'
const GUEST_RESEARCH_VERSION = 1
const MAX_GUEST_STORAGE_CHARS = 500_000
const MAX_COLLECTION_ITEMS = 100
const MAX_SOURCES = 32
const MAX_RELATED_QUESTIONS = 5
const MAX_EVENTS = 64
const MAX_EVENT_QUERY_CHARS = 4_096
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const SOURCE_SCOPE_VALUES = new Set(SOURCE_SCOPES.map(({ value }) => value))
const DEPTH_VALUES = new Set(RESEARCH_DEPTHS.map(({ value }) => value))
const MODE_VALUES = new Set(RESEARCH_MODES.map(({ value }) => value))
const GROUNDING_VALUES = new Set(['grounded', 'partially-grounded', 'evidence-only', 'insufficient'])
const CONFIDENCE_VALUES = new Set(['high', 'medium', 'low', 'disputed'])
const CLASSIFICATION_VALUES = new Set([
  'canonical-scripture', 'ethiopian-canon', 'ancient-text', 'commentary',
  'tradition', 'historical', 'scholarship', 'ai-synthesis',
])
const SOURCE_TYPE_VALUES = new Set([
  'canonical-scripture', 'ethiopian-canon', 'ancient-text', 'manuscript',
  'historical-source', 'early-christian-writing', 'jewish-tradition',
  'church-tradition', 'commentary', 'scholarship', 'ai-synthesis',
])

export class ResearchClientError extends TypeError {
  constructor(message, field, cause) {
    super(message, cause ? { cause } : undefined)
    this.name = 'ResearchClientError'
    this.code = 'invalid_research_request'
    this.field = field
  }
}

function object(value, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${path} must be an object`)
  }
  return value
}

function field(value, snakeName, camelName = snakeName) {
  if (Object.hasOwn(value, snakeName)) return value[snakeName]
  return value[camelName]
}

function text(value, path, { min = 1, max = 50_000, optional = false } = {}) {
  if (optional && value === null) return null
  if (typeof value !== 'string') throw new TypeError(`${path} must be a string${optional ? ' or null' : ''}`)
  if (value.length < min || value.length > max) {
    throw new RangeError(`${path} must contain ${min} to ${max.toLocaleString()} characters`)
  }
  return value
}

function optionalText(value, path, max = 50_000) {
  return text(value, path, { max, optional: true })
}

function uuid(value, path) {
  const result = text(value, path, { max: 36 })
  if (!UUID_PATTERN.test(result)) throw new TypeError(`${path} must be a UUID`)
  return result
}

function nullableUuid(value, path) {
  return value === null ? null : uuid(value, path)
}

function choice(value, path, allowed) {
  if (!allowed.has(value)) throw new TypeError(`${path} has an unsupported value`)
  return value
}

function array(value, path, { max = MAX_COLLECTION_ITEMS } = {}) {
  if (!Array.isArray(value)) throw new TypeError(`${path} must be an array`)
  if (value.length > max) throw new RangeError(`${path} must contain at most ${max} items`)
  return value
}

function stringArray(value, path, { max = MAX_COLLECTION_ITEMS, itemMax = 500 } = {}) {
  return array(value, path, { max }).map((item, index) => text(item, `${path}[${index}]`, { max: itemMax }))
}

function normalizeSourceIds(value, path, { max = MAX_COLLECTION_ITEMS } = {}) {
  const result = stringArray(value, path, { max })
  const seen = new Set()
  result.forEach((id) => {
    if (!id.trim()) throw new TypeError(`${path} contains a blank source ID`)
    if (seen.has(id)) throw new TypeError(`duplicate source ID: ${id}`)
    seen.add(id)
  })
  return result
}

function normalizeModeParameters(value, path = 'settings.mode_parameters') {
  object(value, path)
  const entries = Object.entries(value)
  if (entries.length > 8) throw new RangeError(`${path} must contain at most 8 items`)
  const normalized = new Map()
  entries.forEach(([rawKey, rawItem]) => {
    if (typeof rawKey !== 'string' || typeof rawItem !== 'string') {
      throw new TypeError(`${path} keys and values must be strings`)
    }
    const key = rawKey.trim()
    const item = rawItem.trim()
    text(key, `${path} key`, { max: 64 })
    text(item, `${path}.${key}`, { max: 256 })
    if (normalized.has(key)) throw new TypeError(`${path} keys must be unique after normalization`)
    normalized.set(key, item)
  })
  return Object.fromEntries(normalized)
}

function normalizeSourceScopes(value, path = 'settings.source_scopes') {
  const result = array(value, path, { max: 8 }).map((scope) => choice(scope, path, SOURCE_SCOPE_VALUES))
  if (result.length === 0) throw new RangeError(`${path} must contain at least 1 item`)
  if (new Set(result).size !== result.length) throw new TypeError(`${path} must contain unique values`)
  if (result.includes('all-sources') && result.length !== 1) {
    throw new TypeError(`${path} cannot mix all-sources with another source`)
  }
  return result
}

function normalizeSettings(value, path = 'settings') {
  object(value, path)
  return {
    sourceScopes: normalizeSourceScopes(field(value, 'source_scopes', 'sourceScopes'), `${path}.source_scopes`),
    depth: choice(value.depth, `${path}.depth`, DEPTH_VALUES),
    modeParameters: normalizeModeParameters(field(value, 'mode_parameters', 'modeParameters'), `${path}.mode_parameters`),
  }
}

function normalizeClaim(value, path) {
  object(value, path)
  return {
    id: text(value.id, `${path}.id`, { max: 500 }),
    statement: text(value.statement, `${path}.statement`),
    classification: choice(value.classification, `${path}.classification`, CLASSIFICATION_VALUES),
    confidence: choice(value.confidence, `${path}.confidence`, CONFIDENCE_VALUES),
    sourceIds: normalizeSourceIds(field(value, 'source_ids', 'sourceIds'), `${path}.source_ids`),
  }
}

function normalizeSection(value, path) {
  object(value, path)
  return {
    title: text(value.title, `${path}.title`, { max: 1_000 }),
    narrative: optionalText(value.narrative, `${path}.narrative`),
    claims: array(value.claims, `${path}.claims`).map((item, index) => normalizeClaim(item, `${path}.claims[${index}]`)),
  }
}

function normalizeOptionalSection(value, path) {
  return value === null ? null : normalizeSection(value, path)
}

function normalizeTimelineEvent(value, path) {
  object(value, path)
  return {
    title: text(value.title, `${path}.title`, { max: 1_000 }),
    description: text(value.description, `${path}.description`),
    dateLabel: optionalText(field(value, 'date_label', 'dateLabel'), `${path}.date_label`),
    sourceIds: normalizeSourceIds(field(value, 'source_ids', 'sourceIds'), `${path}.source_ids`),
    confidence: choice(value.confidence, `${path}.confidence`, CONFIDENCE_VALUES),
  }
}

function normalizePerson(value, path) {
  object(value, path)
  return {
    name: text(value.name, `${path}.name`, { max: 1_000 }),
    description: optionalText(value.description, `${path}.description`),
    role: optionalText(value.role, `${path}.role`, 1_000),
    sourceIds: normalizeSourceIds(field(value, 'source_ids', 'sourceIds'), `${path}.source_ids`),
  }
}

function normalizePlace(value, path) {
  object(value, path)
  return {
    name: text(value.name, `${path}.name`, { max: 1_000 }),
    description: optionalText(value.description, `${path}.description`),
    location: optionalText(value.location, `${path}.location`, 2_000),
    sourceIds: normalizeSourceIds(field(value, 'source_ids', 'sourceIds'), `${path}.source_ids`),
  }
}

function normalizeSource(value, path) {
  object(value, path)
  return {
    id: text(value.id, `${path}.id`, { max: 500 }),
    title: text(value.title, `${path}.title`, { max: 1_000 }),
    reference: text(value.reference, `${path}.reference`, { max: 2_000 }),
    excerpt: optionalText(value.excerpt, `${path}.excerpt`, 250_000),
    text: optionalText(value.text, `${path}.text`, 250_000),
    sourceType: choice(field(value, 'source_type', 'sourceType'), `${path}.source_type`, SOURCE_TYPE_VALUES),
    tradition: optionalText(value.tradition, `${path}.tradition`, 2_000),
    dateOrEra: optionalText(field(value, 'date_or_era', 'dateOrEra'), `${path}.date_or_era`, 2_000),
    originalLanguage: optionalText(field(value, 'original_language', 'originalLanguage'), `${path}.original_language`, 2_000),
    translation: optionalText(value.translation, `${path}.translation`, 2_000),
    relevance: optionalText(value.relevance, `${path}.relevance`, 2_000),
    openTarget: optionalText(field(value, 'open_target', 'openTarget'), `${path}.open_target`, 2_000),
  }
}

function normalizeTrailNode(value, path = 'trail_node') {
  if (value === null) return null
  object(value, path)
  const parentNodeId = field(value, 'parent_node_id', 'parentNodeId')
  return {
    id: uuid(value.id, `${path}.id`),
    parentNodeId: nullableUuid(parentNodeId, `${path}.parent_node_id`),
    question: text(value.question, `${path}.question`, { min: 2, max: 10_000 }),
    label: optionalText(value.label, `${path}.label`, 1_000),
  }
}

function validateSourceReferences(response) {
  const sourceIds = new Set()
  for (const source of response.sources) {
    if (sourceIds.has(source.id)) throw new TypeError(`duplicate source ID: ${source.id}`)
    sourceIds.add(source.id)
  }

  const visit = (value) => {
    if (!value || typeof value !== 'object') return
    if (Array.isArray(value)) {
      value.forEach(visit)
      return
    }
    if (Array.isArray(value.sourceIds)) {
      value.sourceIds.forEach((id) => {
        if (!sourceIds.has(id)) throw new TypeError(`unknown source ID: ${id}`)
      })
    }
    Object.values(value).forEach(visit)
  }
  Object.entries(response).forEach(([key, value]) => { if (key !== 'sources') visit(value) })
}

export function normalizeResearchResponse(value) {
  object(value, 'research response')
  const timeline = value.timeline
  const response = {
    id: uuid(value.id, 'id'),
    query: text(value.query, 'query', { min: 2, max: 10_000 }),
    mode: choice(value.mode, 'mode', MODE_VALUES),
    settings: normalizeSettings(value.settings),
    summary: normalizeSection(value.summary, 'summary'),
    timeline: timeline === null ? null : array(timeline, 'timeline').map((item, index) => normalizeTimelineEvent(item, `timeline[${index}]`)),
    canonicalAccount: normalizeOptionalSection(field(value, 'canonical_account', 'canonicalAccount'), 'canonical_account'),
    historicalContext: normalizeOptionalSection(field(value, 'historical_context', 'historicalContext'), 'historical_context'),
    unknowns: normalizeOptionalSection(value.unknowns, 'unknowns'),
    trailNode: normalizeTrailNode(field(value, 'trail_node', 'trailNode')),
    ancientAccounts: array(field(value, 'ancient_accounts', 'ancientAccounts'), 'ancient_accounts').map((item, index) => normalizeSection(item, `ancient_accounts[${index}]`)),
    languageNotes: array(field(value, 'language_notes', 'languageNotes'), 'language_notes').map((item, index) => normalizeSection(item, `language_notes[${index}]`)),
    people: array(value.people, 'people').map((item, index) => normalizePerson(item, `people[${index}]`)),
    places: array(value.places, 'places').map((item, index) => normalizePlace(item, `places[${index}]`)),
    sources: array(value.sources, 'sources', { max: MAX_SOURCES }).map((item, index) => normalizeSource(item, `sources[${index}]`)),
    relatedQuestions: stringArray(field(value, 'related_questions', 'relatedQuestions'), 'related_questions', { max: MAX_RELATED_QUESTIONS, itemMax: 1_000 }),
    groundingStatus: choice(field(value, 'grounding_status', 'groundingStatus'), 'grounding status', GROUNDING_VALUES),
    provider: text(value.provider, 'provider', { max: 1_000 }),
    model: text(value.model, 'model', { max: 1_000 }),
  }
  validateSourceReferences(response)
  return deepFreeze(response)
}

function definedEntries(entries) {
  return Object.fromEntries(entries.filter(([, value]) => value !== undefined))
}

function optionalUuid(value, fieldName) {
  if (value === null || value === undefined) return undefined
  try {
    return uuid(value, fieldName)
  } catch {
    throw new ResearchClientError(`${fieldName} must be a UUID string`, fieldName)
  }
}

export function toApiRequest(input) {
  try {
    object(input, 'research input')
    const question = text(input.question, 'question', { min: 2, max: 10_000 })
    const mode = choice(input.mode ?? DEFAULT_RESEARCH_MODE, 'mode', MODE_VALUES)
    const sourceScopes = normalizeSourceScopes(input.sourceScopes ?? DEFAULT_RESEARCH_SETTINGS.sourceScopes, 'sourceScopes')
    const depth = choice(input.depth ?? DEFAULT_RESEARCH_SETTINGS.depth, 'depth', DEPTH_VALUES)
    const modeParameters = normalizeModeParameters(input.modeParameters ?? DEFAULT_RESEARCH_SETTINGS.modeParameters, 'modeParameters')

    return definedEntries([
      ['question', question],
      ['session_id', optionalUuid(input.sessionId, 'sessionId')],
      ['parent_node_id', optionalUuid(input.parentNodeId, 'parentNodeId')],
      ['mode', mode],
      ['source_scopes', [...sourceScopes]],
      ['depth', depth],
      ['mode_parameters', { ...modeParameters }],
    ])
  } catch (error) {
    if (error instanceof ResearchClientError) throw error
    throw new ResearchClientError(error.message, undefined, error)
  }
}

export function runResearch(input, { signal } = {}) {
  return api.post('/research/query', toApiRequest(input), { signal }).then(normalizeResearchResponse)
}

function encodePathValue(value) {
  return encodeURIComponent(String(value)).replace(/[!'()*]/g, (character) => (
    `%${character.charCodeAt(0).toString(16).toUpperCase()}`
  ))
}

function normalizeTrailSummary(value, path) {
  object(value, path)
  const parentNodeId = field(value, 'parent_node_id', 'parentNodeId')
  return {
    id: uuid(value.id, `${path}.id`),
    parentNodeId: nullableUuid(parentNodeId, `${path}.parent_node_id`),
    question: text(value.question, `${path}.question`, { min: 2, max: 10_000 }),
    mode: choice(value.mode, `${path}.mode`, MODE_VALUES),
    createdAt: optionalText(field(value, 'created_at', 'createdAt'), `${path}.created_at`, 100),
    updatedAt: optionalText(field(value, 'updated_at', 'updatedAt'), `${path}.updated_at`, 100),
  }
}

export function normalizeResearchTrail(value) {
  object(value, 'research trail')
  const childrenTruncated = field(value, 'children_truncated', 'childrenTruncated')
  if (typeof childrenTruncated !== 'boolean') throw new TypeError('children_truncated must be a boolean')
  return deepFreeze({
    ancestry: array(value.ancestry, 'ancestry', { max: 64 }).map((item, index) => normalizeTrailSummary(item, `ancestry[${index}]`)),
    active: normalizeTrailSummary(value.active, 'active'),
    children: array(value.children, 'children', { max: 64 }).map((item, index) => normalizeTrailSummary(item, `children[${index}]`)),
    childrenTruncated,
  })
}

function normalizeResearchEvent(value, path) {
  object(value, path)
  return {
    id: text(value.id, `${path}.id`, { max: 500 }),
    title: text(value.title, `${path}.title`, { max: 1_000 }),
    description: text(value.description, `${path}.description`),
    reference: text(value.reference, `${path}.reference`, { max: 2_000 }),
    sourceIds: normalizeSourceIds(field(value, 'source_ids', 'sourceIds'), `${path}.source_ids`, { max: MAX_SOURCES }),
    people: stringArray(value.people, `${path}.people`, { itemMax: 1_000 }),
    places: stringArray(value.places, `${path}.places`, { itemMax: 1_000 }),
  }
}

export function normalizeResearchEvents(value) {
  object(value, 'research events')
  const eventIds = new Set()
  const events = array(value.events, 'events', { max: MAX_EVENTS }).map((item, index) => {
    const event = normalizeResearchEvent(item, `events[${index}]`)
    if (eventIds.has(event.id)) throw new TypeError(`duplicate event ID: ${event.id}`)
    eventIds.add(event.id)
    return event
  })
  return deepFreeze({ events })
}

export function searchResearchEvents(query, { signal } = {}) {
  if (typeof query !== 'string') throw new ResearchClientError('query must be a string', 'query')
  if (query.length > MAX_EVENT_QUERY_CHARS) {
    throw new ResearchClientError(`query must contain at most ${MAX_EVENT_QUERY_CHARS.toLocaleString()} characters`, 'query')
  }
  return api.get(`/research/events?q=${encodePathValue(query)}`, { signal }).then(normalizeResearchEvents)
}

export function getResearchTrail(nodeId, { signal } = {}) {
  const normalizedNodeId = optionalUuid(nodeId, 'nodeId')
  if (!normalizedNodeId) throw new ResearchClientError('nodeId must be a UUID string', 'nodeId')
  return api.get(`/research/trail/${encodePathValue(normalizedNodeId)}`, { signal }).then(normalizeResearchTrail)
}

function storageOrNull(storage) {
  if (storage) return storage
  try {
    return globalThis.localStorage ?? null
  } catch {
    return null
  }
}

function normalizedGuestNode(value, index) {
  object(value, `nodes[${index}]`)
  const parentNodeId = value.parentNodeId ?? null
  return {
    id: text(value.id, `nodes[${index}].id`, { max: 500 }),
    parentNodeId: parentNodeId === null ? null : text(parentNodeId, `nodes[${index}].parentNodeId`, { max: 500 }),
    response: normalizeResearchResponse(value.response),
  }
}

function validateGuestTopology(nodes, activeNodeId) {
  const nodesById = new Map()
  nodes.forEach((node) => {
    if (nodesById.has(node.id)) throw new TypeError(`duplicate guest node ID: ${node.id}`)
    nodesById.set(node.id, node)
  })

  nodes.forEach((node) => {
    if (node.parentNodeId === node.id) throw new TypeError(`guest node ${node.id} cannot parent itself`)
    if (node.parentNodeId !== null && !nodesById.has(node.parentNodeId)) {
      throw new TypeError(`guest node ${node.id} references a missing parent`)
    }
  })

  nodes.forEach((start) => {
    const path = new Set()
    let current = start
    for (let steps = 0; current !== null && steps <= nodes.length; steps += 1) {
      if (path.has(current.id)) throw new TypeError('guest research trail contains a cycle')
      path.add(current.id)
      current = current.parentNodeId === null ? null : nodesById.get(current.parentNodeId)
    }
    if (current !== null) throw new TypeError('guest research trail exceeds its node bound')
  })

  if (activeNodeId !== null && !nodesById.has(activeNodeId)) {
    throw new TypeError('activeNodeId must reference a stored node')
  }
}

function normalizedGuestSession(value) {
  object(value, 'guest session')
  const nodes = array(value.nodes, 'nodes', { max: 64 }).map(normalizedGuestNode)
  const activeNodeId = value.activeNodeId ?? null
  if (activeNodeId !== null) text(activeNodeId, 'activeNodeId', { max: 500 })
  validateGuestTopology(nodes, activeNodeId)
  return {
    nodes,
    activeNodeId,
    settings: normalizeSettings(value.settings, 'settings'),
  }
}

function safelyRemove(storage) {
  try {
    storage?.removeItem(GUEST_RESEARCH_STORAGE_KEY)
    return true
  } catch {
    return false
  }
}

export function loadGuestResearchSession(storage) {
  const target = storageOrNull(storage)
  if (!target) return createEmptyResearchSession()
  try {
    const serialized = target.getItem(GUEST_RESEARCH_STORAGE_KEY)
    if (serialized === null) return createEmptyResearchSession()
    if (serialized.length > MAX_GUEST_STORAGE_CHARS) throw new RangeError('stored session is too large')
    const envelope = JSON.parse(serialized)
    object(envelope, 'stored research session')
    if (envelope.version !== GUEST_RESEARCH_VERSION) throw new TypeError('unsupported stored research session version')
    return deepFreeze(normalizedGuestSession(envelope.session))
  } catch {
    safelyRemove(target)
    return createEmptyResearchSession()
  }
}

export function saveGuestResearchSession(session, storage) {
  const target = storageOrNull(storage)
  if (!target) return false
  try {
    const envelope = { version: GUEST_RESEARCH_VERSION, session: normalizedGuestSession(session) }
    const serialized = JSON.stringify(envelope)
    if (serialized.length > MAX_GUEST_STORAGE_CHARS) return false
    target.setItem(GUEST_RESEARCH_STORAGE_KEY, serialized)
    return true
  } catch {
    return false
  }
}

export function clearGuestResearchSession(storage) {
  return safelyRemove(storageOrNull(storage))
}
