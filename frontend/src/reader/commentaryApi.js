const AVAILABILITY_STATES = new Set([
  'available',
  'no_entry',
  'coverage_incomplete',
  'wider_range',
])

const ENTRY_TYPES = new Set([
  'book_intro',
  'chapter_intro',
  'verse',
  'verse_range',
])

export class CommentaryRequestError extends Error {
  constructor(message, { status, code } = {}) {
    super(message)
    this.name = 'CommentaryRequestError'
    this.status = status
    this.code = code
  }
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function rethrowAbort(error) {
  if (error?.name === 'AbortError') throw error
}

function nonblank(value, name) {
  const text = typeof value === 'string' ? value.trim() : ''
  if (!text) throw new TypeError(`${name} must be a nonblank string`)
  return text
}

function boundedInteger(value, name, maximum) {
  const number = Number(value)
  if (!Number.isSafeInteger(number) || number < 1 || number > maximum) {
    throw new TypeError(`${name} must be an integer between 1 and ${maximum}`)
  }
  return number
}

function optionalText(target, source, key) {
  if (typeof source[key] !== 'string') return
  const text = source[key].trim()
  if (text) target[key] = text
}

function normalizeSource(value) {
  if (!isRecord(value)) return null
  const id = typeof value.id === 'string' ? value.id.trim() : ''
  const title = typeof value.title === 'string' ? value.title.trim() : ''
  if (!id || !title) return null

  const source = { id, title }
  for (const key of [
    'abbreviation',
    'author',
    'publication_period',
    'tradition',
    'language',
    'license_spdx',
    'license_url',
    'attribution',
  ]) {
    optionalText(source, value, key)
  }
  if (Number.isSafeInteger(value.edition_version)) {
    source.edition_version = value.edition_version
  }
  return source
}

function normalizeScope(value) {
  if (!isRecord(value)) return null
  const { verse_start: start, verse_end: end } = value
  if (start === null && end === null) {
    return { verse_start: null, verse_end: null }
  }
  if (
    !Number.isSafeInteger(start) || start < 1 || start > 1000
    || !Number.isSafeInteger(end) || end < start || end > 1000
  ) {
    return null
  }
  return { verse_start: start, verse_end: end }
}

function normalizeEntry(value) {
  if (!isRecord(value)) return null
  const body = typeof value.body === 'string' ? value.body.trim() : ''
  const citation = typeof value.citation === 'string' ? value.citation.trim() : ''
  const scope = normalizeScope(value.scope)
  if (!body || !citation || !scope) return null

  const entry = { body, citation }
  if (ENTRY_TYPES.has(value.entry_type)) entry.entry_type = value.entry_type
  optionalText(entry, value, 'heading')
  optionalText(entry, value, 'source_locator')
  entry.scope = scope
  return entry
}

function normalizeReference(value) {
  if (!isRecord(value)) return {}
  const book = typeof value.book === 'string' ? value.book.trim() : ''
  const chapter = value.chapter
  if (!book || !Number.isSafeInteger(chapter) || chapter < 1 || chapter > 500) return {}

  const reference = { book, chapter }
  if (Number.isSafeInteger(value.verse) && value.verse >= 1 && value.verse <= 1000) {
    reference.verse = value.verse
  }
  return reference
}

function safeErrorDetail(payload) {
  const detail = isRecord(payload) || typeof payload === 'string' ? payload : undefined
  if (!isRecord(detail)) {
    return typeof detail === 'string' && detail.trim()
      ? { message: detail.trim(), code: undefined }
      : { message: undefined, code: undefined }
  }
  return {
    message: typeof detail.message === 'string' && detail.message.trim()
      ? detail.message.trim()
      : undefined,
    code: typeof detail.code === 'string' && detail.code.trim()
      ? detail.code.trim()
      : undefined,
  }
}

export async function requestCommentary(url, signal) {
  let response
  try {
    response = await fetch(url, { signal })
  } catch (error) {
    rethrowAbort(error)
    throw new CommentaryRequestError('Commentary request failed')
  }

  if (!response.ok) {
    let payload
    try {
      payload = await response.json()
    } catch (error) {
      rethrowAbort(error)
      payload = undefined
    }
    const detail = safeErrorDetail(isRecord(payload) ? payload.detail : undefined)
    throw new CommentaryRequestError(
      detail.message || `Commentary request failed (${response.status})`,
      { status: response.status, code: detail.code },
    )
  }

  try {
    return await response.json()
  } catch (error) {
    rethrowAbort(error)
    throw new CommentaryRequestError('Commentary response was invalid', {
      status: response.status,
    })
  }
}

export async function getCommentarySources(signal) {
  const payload = await requestCommentary('/api/v1/commentaries/sources', signal)
  if (!isRecord(payload) || !Array.isArray(payload.sources)) return []
  return payload.sources.map(normalizeSource).filter(Boolean)
}

export async function getCommentaryEntries({ source, book, chapter, verse } = {}, signal) {
  const params = new URLSearchParams({
    source: nonblank(source, 'source'),
    book: nonblank(book, 'book'),
    chapter: String(boundedInteger(chapter, 'chapter', 500)),
  })
  if (verse !== undefined && verse !== null) {
    params.set('verse', String(boundedInteger(verse, 'verse', 1000)))
  }

  const payload = await requestCommentary(`/api/v1/commentaries/entries?${params}`, signal)
  const document = isRecord(payload) ? payload : {}
  return {
    reference: normalizeReference(document.reference),
    availability: AVAILABILITY_STATES.has(document.availability)
      ? document.availability
      : 'no_entry',
    source: normalizeSource(document.source),
    entries: Array.isArray(document.entries)
      ? document.entries.map(normalizeEntry).filter(Boolean)
      : [],
  }
}
