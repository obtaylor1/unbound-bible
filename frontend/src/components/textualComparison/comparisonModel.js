export const DEFAULT_TRANSLATIONS = ['eotc-composite-en', 'geez1980-research', 'kjv']
export const MAX_TRANSLATIONS = 4

export const TRANSLATIONS = []
export const TRANSLATION_BY_KEY = {}

export const TRANSLATION_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'ethiopian', label: 'Ethiopian' },
  { id: 'protestant', label: 'Protestant' },
  { id: 'catholic', label: 'Catholic' },
  { id: 'original', label: 'Original Languages' },
]

const PROTESTANT_BOOKS = new Set([
  'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth',
  '1 Samuel', '2 Samuel', '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles', 'Ezra',
  'Nehemiah', 'Esther', 'Job', 'Psalms', 'Proverbs', 'Ecclesiastes', 'Song of Solomon',
  'Isaiah', 'Jeremiah', 'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos',
  'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah',
  'Malachi', 'Matthew', 'Mark', 'Luke', 'John', 'Acts', 'Romans', '1 Corinthians',
  '2 Corinthians', 'Galatians', 'Ephesians', 'Philippians', 'Colossians', '1 Thessalonians',
  '2 Thessalonians', '1 Timothy', '2 Timothy', 'Titus', 'Philemon', 'Hebrews', 'James',
  '1 Peter', '2 Peter', '1 John', '2 John', '3 John', 'Jude', 'Revelation',
])

const CATHOLIC_BOOKS = new Set([
  ...PROTESTANT_BOOKS,
  'Tobit', 'Judith', 'Wisdom of Solomon', 'Sirach', 'Baruch', '1 Maccabees', '2 Maccabees',
])

const SOURCE_BOOKS = {
  '1en_ch': new Set(['1 Enoch', 'Enoch']),
  jub_ch: new Set(['Jubilees']),
  meq1: new Set(['1 Meqabyan', 'Meqabyan 1']),
  meq2: new Set(['2 Meqabyan', 'Meqabyan 2']),
  meq3: new Set(['3 Meqabyan', 'Meqabyan 3']),
}

function cleanText(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function safeProvenanceUrl(value) {
  const candidate = cleanText(value)
  if (!candidate) return null
  try {
    const parsed = new URL(candidate)
    return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null
  } catch {
    return null
  }
}

function sourceCategories({ code, tradition, language }) {
  const description = `${code} ${tradition}`.toLocaleLowerCase()
  const categories = []
  if (/ethiop|eotc|geez|ge'ez|meqabyan|enoch|jubilees/.test(description)) categories.push('ethiopian')
  if (/catholic|douay/.test(description)) categories.push('catholic')
  if (/protestant|king james|world english|american standard|\bkjv\b|\basv\b|\bweb(?:be)?\b/.test(description)) categories.push('protestant')
  if (/original|masoretic|hebrew|greek/.test(`${description} ${language}`.toLocaleLowerCase())) categories.push('original')
  return [...new Set(categories)]
}

export function sourceFromRow(row) {
  if (!row || typeof row !== 'object') return null
  const edition = row.edition && typeof row.edition === 'object' ? row.edition : {}
  const workSource = row.work_source && typeof row.work_source === 'object' ? row.work_source : {}
  const rawCode = cleanText(edition.code) ?? cleanText(row.translation)
  if (!rawCode) return null

  const code = rawCode.toLocaleUpperCase()
  const language = cleanText(edition.language) ?? 'Unknown language'
  const tradition = cleanText(workSource.source_tradition)
    ?? cleanText(edition.source_tradition)
    ?? 'Source details pending'

  return {
    key: code.toLocaleLowerCase(),
    code,
    name: cleanText(edition.name) ?? code,
    language,
    tradition,
    year: workSource.published_year ?? edition.published_year ?? 'Date not listed',
    sourceLabel: cleanText(workSource.source_label),
    fallback: workSource.fallback === true,
    provisional: workSource.verification_status === 'provisional',
    translator: cleanText(workSource.translator),
    attribution: cleanText(workSource.attribution),
    provenanceUrl: safeProvenanceUrl(workSource.provenance_url),
    canonScope: cleanText(workSource.canon_scope),
    categories: sourceCategories({ code, tradition, language }),
  }
}

export function buildInstalledSources(rows = []) {
  const byCode = new Map()
  rows.map(sourceFromRow).filter(Boolean).forEach((source) => {
    if (!byCode.has(source.code)) byCode.set(source.code, source)
  })
  return [...byCode.values()].sort((left, right) => left.code.localeCompare(right.code))
}

export function registerInstalledSources(sources = []) {
  TRANSLATIONS.splice(0, TRANSLATIONS.length, ...sources)
  Object.keys(TRANSLATION_BY_KEY).forEach((key) => delete TRANSLATION_BY_KEY[key])
  sources.forEach((source) => { TRANSLATION_BY_KEY[source.key] = source })
}

export function reconcileSourceSelection({ installed = [], selected = [], base = null }) {
  const installedKeys = new Set(installed.map(({ key }) => key))
  const next = [...new Set(selected.filter((key) => installedKeys.has(key)))]
  const preferred = installed.find(({ key }) => key === 'eotc-composite-en')?.key

  if (preferred && !next.includes(preferred)) {
    if (next.length >= MAX_TRANSLATIONS) next.pop()
    next.push(preferred)
  }
  for (const source of installed) {
    if (next.length >= 2) break
    if (!next.includes(source.key)) next.push(source.key)
  }

  return {
    selected: next.slice(0, MAX_TRANSLATIONS),
    base: installedKeys.has(base) && next.includes(base)
      ? base
      : preferred ?? next[0] ?? null,
  }
}

export function applyTranslationToggle(selected, key, base) {
  if (selected.includes(key)) {
    if (selected.length === 1) return { selected, base, minimumReached: true }
    const next = selected.filter((item) => item !== key)
    return { selected: next, base: base === key ? next[0] : base }
  }
  if (selected.length >= MAX_TRANSLATIONS) return { selected, base, limitReached: true }
  return { selected: [...selected, key], base }
}

export function filterTranslations({ category = 'all', query = '' } = {}) {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  return TRANSLATIONS.filter((translation) => {
    if (category !== 'all' && !translation.categories.includes(category)) return false
    if (!normalizedQuery) return true
    return [
      translation.code,
      translation.name,
      translation.tradition,
      translation.year,
      translation.language,
    ].some((value) => String(value ?? '').toLocaleLowerCase().includes(normalizedQuery))
  })
}

function belongsToSource(key, book) {
  if (SOURCE_BOOKS[key]) return SOURCE_BOOKS[key].has(book)
  const categories = TRANSLATION_BY_KEY[key]?.categories ?? []
  if (key === 'geez1980-research' || key === 'eotc-composite-en') return true
  if (categories.includes('catholic')) return CATHOLIC_BOOKS.has(book)
  if (categories.includes('protestant') || categories.includes('original')) {
    return PROTESTANT_BOOKS.has(book)
  }
  return true
}

export function buildSourceState({ key, book, text }) {
  if (typeof text === 'string' && text.trim()) return { kind: 'available', text }

  const source = TRANSLATION_BY_KEY[key]
  if (!belongsToSource(key, book)) {
    return {
      kind: 'canon-excluded',
      title: 'Not part of this canon',
      message: `${book} is not included in the ${source?.tradition ?? 'selected'} tradition.`,
    }
  }
  return {
    kind: 'translation-unavailable',
    title: 'Text unavailable',
    message: `${source?.name ?? 'This source'} does not currently provide this passage.`,
  }
}

function normalizedWord(word) {
  return word.toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, '')
}

export function diffWords(text, baseText) {
  const baseWords = new Set(
    String(baseText ?? '').split(/\s+/).map(normalizedWord).filter(Boolean),
  )
  return String(text ?? '').split(/(\s+)/).filter((part) => part !== '').map((part) => {
    const normalized = normalizedWord(part)
    return { text: part, differs: Boolean(normalized && !baseWords.has(normalized)) }
  })
}

function uniqueWords(text) {
  return new Set(String(text ?? '').split(/\s+/).map(normalizedWord).filter(Boolean))
}

export function summarizeComparison(texts, { baseIndex = 0 } = {}) {
  const available = texts
    .map((text, index) => ({ text, index }))
    .filter(({ text }) => typeof text === 'string' && text.trim())
  if (available.length < 2) {
    return {
      availableCount: available.length,
      differenceCount: 0,
      message: available.length
        ? 'One source is available. Add another source to compare wording.'
        : 'Choose an available source to begin comparing this passage.',
    }
  }

  const baseEntry = available.find(({ index }) => index === baseIndex) ?? available[0]
  const base = uniqueWords(baseEntry.text)
  const differenceCount = available.filter((entry) => entry !== baseEntry).reduce((largest, { text }) => {
    const words = uniqueWords(text)
    const baseOnly = [...base].filter((word) => !words.has(word)).length
    const comparisonOnly = [...words].filter((word) => !base.has(word)).length
    return Math.max(largest, baseOnly, comparisonOnly)
  }, 0)

  return {
    availableCount: available.length,
    differenceCount,
    message: differenceCount
      ? 'The available sources preserve the same passage with some differences in wording.'
      : 'The available sources use the same wording for this passage.',
  }
}
