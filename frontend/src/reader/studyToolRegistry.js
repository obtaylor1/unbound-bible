const tools = [
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
]

export const STUDY_TOOLS = Object.freeze(
  tools.map((tool) => Object.freeze({
    ...tool,
    ...(tool.detailKeys ? { detailKeys: Object.freeze([...tool.detailKeys]) } : {}),
  })),
)
