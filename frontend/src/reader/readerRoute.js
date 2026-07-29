const DEFAULT_READER_ROUTE = {
  book: 'Genesis',
  chapter: 1,
  translation: 'KJV',
  canon: 'ETHIO81',
  verse: null
}

const positiveInteger = (value, fallback) => {
  if (!/^[1-9]\d*$/.test(String(value ?? ''))) return fallback
  const number = Number(value)
  return Number.isSafeInteger(number) ? number : fallback
}

const normalizedText = (value, fallback) => {
  const text = String(value ?? '').trim()
  return text || fallback
}

export const parseReaderHash = (hash = globalThis.window?.location?.hash ?? '') => {
  const query = String(hash).split('?')[1] ?? ''
  const params = new URLSearchParams(query)

  return {
    book: normalizedText(params.get('book'), DEFAULT_READER_ROUTE.book),
    chapter: positiveInteger(params.get('chapter'), DEFAULT_READER_ROUTE.chapter),
    translation: normalizedText(params.get('translation'), DEFAULT_READER_ROUTE.translation).toUpperCase(),
    canon: normalizedText(params.get('canon'), DEFAULT_READER_ROUTE.canon).toUpperCase(),
    verse: positiveInteger(params.get('verse'), DEFAULT_READER_ROUTE.verse)
  }
}

export const readerHash = (route = {}) => {
  const normalized = {
    book: normalizedText(route.book, DEFAULT_READER_ROUTE.book),
    chapter: positiveInteger(route.chapter, DEFAULT_READER_ROUTE.chapter),
    translation: normalizedText(route.translation, DEFAULT_READER_ROUTE.translation).toUpperCase(),
    canon: normalizedText(route.canon, DEFAULT_READER_ROUTE.canon).toUpperCase(),
    verse: positiveInteger(route.verse, DEFAULT_READER_ROUTE.verse)
  }
  const params = new URLSearchParams({
    book: normalized.book,
    chapter: String(normalized.chapter),
    translation: normalized.translation,
    canon: normalized.canon
  })

  if (normalized.verse !== null) params.set('verse', String(normalized.verse))

  return `#scriptures?${params}`
}
