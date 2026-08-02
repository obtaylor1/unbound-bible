export const DEFAULT_TRANSLATIONS = ['eth81', 'kjv']
export const MAX_TRANSLATIONS = 4

export const TRANSLATIONS = [
  { key: 'eth81', code: 'ETH81', name: 'Ethiopian Orthodox Critical Text', tradition: "Ancient Orthodox / Ge'ez Canon", year: 'Critical edition', language: "Amharic / Ge'ez", categories: ['ethiopian'] },
  { key: 'kjv', code: 'KJV', name: 'King James Version', tradition: 'Protestant', year: '1611 / 1769', language: 'English', categories: ['protestant'] },
  { key: 'asv', code: 'ASV', name: 'American Standard Version', tradition: 'Protestant', year: '1901', language: 'English', categories: ['protestant'] },
  { key: 'web', code: 'WEB', name: 'World English Bible', tradition: 'Protestant / Ecumenical', year: '2001', language: 'English', categories: ['protestant'] },
  { key: 'webbe', code: 'WEBBE', name: 'World English Bible, British Edition', tradition: 'Protestant / Ecumenical', year: '2023', language: 'English', categories: ['protestant'] },
  { key: 'bbe', code: 'BBE', name: 'Bible in Basic English', tradition: 'Protestant', year: '1949', language: 'English', categories: ['protestant'] },
  { key: 'darby', code: 'DARBY', name: 'Darby Translation', tradition: 'Protestant', year: '1890', language: 'English', categories: ['protestant'] },
  { key: 'dra', code: 'DRA', name: 'Douay-Rheims Version', tradition: 'Catholic', year: '1899', language: 'English', categories: ['catholic'] },
  { key: 'ylt', code: 'YLT', name: "Young's Literal Translation", tradition: 'Protestant', year: '1862', language: 'English', categories: ['protestant'] },
  { key: 'nlt', code: 'NLT', name: 'New Living Translation', tradition: 'Protestant', year: '1996 / 2004', language: 'English', categories: ['protestant'] },
  { key: 'erv', code: 'ERV', name: 'Easy-to-Read Version', tradition: 'Protestant', year: '2006', language: 'English', categories: ['protestant'] },
  { key: 'oshb', code: 'OSHB', name: 'Open Scriptures Hebrew Bible', tradition: 'Masoretic Text', year: 'Critical text', language: 'Biblical Hebrew', categories: ['original'] },
  { key: '1en_ch', code: '1EN_CH', name: '1 Enoch, R. H. Charles', tradition: 'Ethiopian Pseudepigrapha', year: '1912', language: 'English', categories: ['ethiopian'] },
  { key: 'jub_ch', code: 'JUB_CH', name: 'Jubilees, R. H. Charles', tradition: 'Ethiopian Pseudepigrapha', year: '1917', language: 'English', categories: ['ethiopian'] },
  { key: 'meq1', code: 'MEQ1', name: '1 Meqabyan', tradition: 'Ethiopian Deuterocanon', year: 'English translation', language: 'English', categories: ['ethiopian'] },
  { key: 'meq2', code: 'MEQ2', name: '2 Meqabyan', tradition: 'Ethiopian Deuterocanon', year: 'English translation', language: 'English', categories: ['ethiopian'] },
  { key: 'meq3', code: 'MEQ3', name: '3 Meqabyan', tradition: 'Ethiopian Deuterocanon', year: 'English translation', language: 'English', categories: ['ethiopian'] },
]

export const TRANSLATION_BY_KEY = Object.fromEntries(
  TRANSLATIONS.map((translation) => [translation.key, translation]),
)

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
    ].some((value) => value.toLocaleLowerCase().includes(normalizedQuery))
  })
}

function belongsToSource(key, book) {
  if (SOURCE_BOOKS[key]) return SOURCE_BOOKS[key].has(book)
  const categories = TRANSLATION_BY_KEY[key]?.categories ?? []
  if (key === 'eth81') return true
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
  if (key === 'eth81') {
    return {
      kind: 'database-missing',
      title: 'Text unavailable',
      message: 'This passage has not yet been added to the Ethiopian Critical Text database.',
    }
  }
  return {
    kind: 'translation-unavailable',
    title: 'Translation unavailable',
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

export function summarizeComparison(texts) {
  const available = texts.filter((text) => typeof text === 'string' && text.trim())
  if (available.length < 2) {
    return {
      availableCount: available.length,
      differenceCount: 0,
      message: available.length
        ? 'One source is available. Add another source to compare wording.'
        : 'Choose an available source to begin comparing this passage.',
    }
  }

  const base = uniqueWords(available[0])
  const differenceCount = available.slice(1).reduce((largest, text) => {
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
