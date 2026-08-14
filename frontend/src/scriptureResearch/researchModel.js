function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value
  Object.freeze(value)
  Object.values(value).forEach(deepFreeze)
  return value
}

export const SOURCE_SCOPES = deepFreeze([
  { value: 'biblical-canon', label: 'Biblical Canon' },
  { value: 'ethiopian-tradition', label: 'Ethiopian Tradition' },
  { value: 'apocrypha', label: 'Apocrypha' },
  { value: '1-enoch', label: '1 Enoch' },
  { value: 'jubilees', label: 'Jubilees' },
  { value: 'ancient-sources', label: 'Ancient Sources' },
  { value: 'commentary', label: 'Commentary' },
  { value: 'all-sources', label: 'All Sources' },
])

export const RESEARCH_DEPTHS = deepFreeze([
  { value: 'quick', label: 'Quick Answer' },
  { value: 'study', label: 'Study' },
  { value: 'deep-research', label: 'Deep Research' },
  { value: 'scholar', label: 'Scholar' },
])

export const RESEARCH_MODES = deepFreeze([
  { value: 'what-happened-between', label: 'What Happened Between?' },
  { value: 'explain-a-book', label: 'Explain a Book' },
  { value: 'compare-accounts', label: 'Compare Accounts' },
  { value: 'people-and-places', label: 'People & Places' },
  { value: 'original-languages', label: 'Original Languages' },
  { value: 'genealogy', label: 'Genealogy' },
])

export const DEFAULT_RESEARCH_MODE = 'what-happened-between'

export const DEFAULT_RESEARCH_SETTINGS = deepFreeze({
  sourceScopes: ['biblical-canon'],
  depth: 'deep-research',
  modeParameters: {},
})

export function createEmptyResearchSession() {
  return {
    nodes: [],
    activeNodeId: null,
    settings: {
      sourceScopes: [...DEFAULT_RESEARCH_SETTINGS.sourceScopes],
      depth: DEFAULT_RESEARCH_SETTINGS.depth,
      modeParameters: {},
    },
  }
}

export const EMPTY_RESEARCH_SESSION = deepFreeze(createEmptyResearchSession())

export { deepFreeze }
