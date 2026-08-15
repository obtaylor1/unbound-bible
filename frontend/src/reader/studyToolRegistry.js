function cleanReferenceText(value) {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed || null
}

function toWellFormedReferenceText(value) {
  if (typeof value.toWellFormed === 'function') return value.toWellFormed()
  let result = ''
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    if (code >= 0xD800 && code <= 0xDBFF) {
      const next = value.charCodeAt(index + 1)
      if (next >= 0xDC00 && next <= 0xDFFF) {
        result += value[index] + value[index + 1]
        index += 1
      } else {
        result += '\uFFFD'
      }
    } else if (code >= 0xDC00 && code <= 0xDFFF) {
      result += '\uFFFD'
    } else {
      result += value[index]
    }
  }
  return result
}

export function positiveStudyInteger(value) {
  if (typeof value === 'number') {
    return Number.isFinite(value) && Number.isSafeInteger(value) && value > 0
      ? value
      : null
  }
  if (typeof value !== 'string' || !/^\d+$/.test(value)) return null
  const number = Number(value)
  return Number.isSafeInteger(number) && number > 0 ? number : null
}

export function normalizeStudyReference(reference) {
  if (!reference || typeof reference !== 'object' || Array.isArray(reference)) {
    return { value: {}, label: 'Current passage', hasVerse: false }
  }

  const book = cleanReferenceText(reference.book)
  const chapter = positiveStudyInteger(reference.chapter)
  const verse = positiveStudyInteger(reference.verse)
  if (!book || book.length > 120 || !chapter) {
    return { value: {}, label: 'Current passage', hasVerse: false }
  }

  const value = verse ? { book, chapter, verse } : { book, chapter }
  return {
    value,
    label: `${book} ${chapter}${verse ? `:${verse}` : ''}`,
    hasVerse: Boolean(verse),
  }
}

export function studyReferenceKey(reference) {
  const { value } = normalizeStudyReference(reference)
  if (!value.book || !value.chapter) return 'current-passage'
  return [
    encodeURIComponent(toWellFormedReferenceText(value.book.toLocaleLowerCase())),
    value.chapter,
    value.verse ?? '',
  ].join('|')
}

const tools = [
  {
    id: 'context',
    kind: 'inline',
    label: 'Context',
    detailKeys: ['historical_context'],
  },
  { id: 'commentary', kind: 'data', label: 'Commentary' },
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
  { id: 'notes', kind: 'route', label: 'Add or view notes', page: 'notes' },
  { id: 'markers', kind: 'local', label: 'Highlights and bookmarks' },
  { id: 'ask', kind: 'route', label: 'Scripture Research AI', page: 'chat' },
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
