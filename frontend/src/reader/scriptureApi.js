import {
  boundedPublicText,
  isVerifiedSourceStatus,
  normalizedTransformations,
  normalizedVerifiedAt,
  safePublicSourceUrl,
} from './sourceVerification'

export async function requestJson(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    const status = [response.status, response.statusText].filter(Boolean).join(' ')
    throw new Error(`Scripture request failed${status ? ` (${status})` : ''}`)
  }
  return response.json()
}

export async function getBooks(canon, signal) {
  const catalog = await getBookCatalog(canon, signal)
  return catalog.map(({ name }) => name)
}

function normalizedTaxonomy(value, kind) {
  if (typeof value !== 'string' || !value.trim()) return null
  const text = value.trim()
  if (kind === 'testament') {
    const compact = text.toLocaleLowerCase().replace(/[^a-z]/g, '')
    if (compact === 'old' || compact === 'oldtestament') return 'Old Testament'
    if (compact === 'new' || compact === 'newtestament') return 'New Testament'
  }
  return text
}

function normalizedIdentifier(value, fallbackName) {
  const supplied = typeof value === 'string' ? value.trim() : ''
  const source = supplied || fallbackName
  return source
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
}

function clonedJsonValue(value, seen = new WeakMap()) {
  if (value === null || typeof value !== 'object') return value
  if (seen.has(value)) return null

  const clone = Array.isArray(value) ? [] : {}
  seen.set(value, clone)
  for (const [key, entry] of Object.entries(value)) {
    Object.defineProperty(clone, key, {
      configurable: true,
      enumerable: true,
      value: clonedJsonValue(entry, seen),
      writable: true,
    })
  }
  return clone
}

function normalizedOptionalText(value, { uppercase = false } = {}) {
  if (typeof value !== 'string' || !value.trim()) return null
  const text = value.trim()
  return uppercase ? text.toUpperCase() : text
}

function normalizedSourceText(value) {
  return boundedPublicText(value, 200)
}

export function normalizeWorkSource(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null

  const verification = value.verification && typeof value.verification === 'object'
    && !Array.isArray(value.verification)
    ? value.verification
    : {}

  const verificationStatus = boundedPublicText(
    verification.status ?? value.verification_status,
    32,
  )

  return {
    sourceKey: boundedPublicText(value.source_key, 100),
    sourceLabel: normalizedSourceText(value.source_label) || 'Source details unavailable',
    translator: normalizedSourceText(value.translator),
    sourceLanguage: boundedPublicText(value.source_language, 100),
    sourceTradition: normalizedSourceText(value.source_tradition),
    publishedYear: Number.isSafeInteger(value.published_year)
      && value.published_year >= 1 && value.published_year <= 9999
      ? value.published_year
      : null,
    license: boundedPublicText(value.license, 100),
    attribution: boundedPublicText(value.attribution, 2000),
    provenanceUrl: safePublicSourceUrl(value.provenance_url),
    rightsUrl: safePublicSourceUrl(value.rights_url),
    rightsJurisdiction: boundedPublicText(value.rights_jurisdiction, 500),
    sourceEdition: normalizedSourceText(value.source_edition),
    sourceRevision: normalizedSourceText(value.source_revision),
    fallback: value.fallback === true,
    modified: value.modified === true,
    modificationNote: boundedPublicText(value.modification_note, 2000),
    transformations: normalizedTransformations(value.transformations),
    verificationStatus,
    verifiedAt: isVerifiedSourceStatus(verificationStatus)
      ? normalizedVerifiedAt(verification.verified_at)
      : null,
    canonScope: boundedPublicText(value.canon_scope, 20),
  }
}

export async function getBookCatalog(canon, signal) {
  const normalizedCanon = String(canon ?? '').trim().toUpperCase() || 'ETHIO81'
  const params = new URLSearchParams({ canon: normalizedCanon })
  const data = await requestJson(`/api/v1/books?${params}`, signal)

  const seen = new Set()
  return (data.books ?? []).flatMap((book) => {
    const name = (typeof book === 'string' ? book : book?.name)?.trim()
    if (!name) return []
    const key = name.toLocaleLowerCase()
    if (seen.has(key)) return []
    seen.add(key)
    return [{
      id: normalizedIdentifier(book?.id, name),
      name,
      testament: normalizedTaxonomy(book?.testament, 'testament'),
      collection: normalizedTaxonomy(book?.collection, 'collection'),
      coverage: book?.coverage && typeof book.coverage === 'object'
        ? clonedJsonValue(book.coverage)
        : null,
      recommendedEdition: normalizedOptionalText(book?.recommended_edition, { uppercase: true }),
      unavailableReason: normalizedOptionalText(book?.unavailable_reason),
    }]
  })
}

export async function getChapter({ book, chapter }, signal) {
  const params = new URLSearchParams({ book: String(book), chapter: String(chapter) })
  const data = await requestJson(`/api/biblical-texts/chapter-content?${params}`, signal)
  return (data.content ?? []).map((row) => (
    row && typeof row === 'object' && Object.hasOwn(row, 'work_source')
      ? { ...row, workSource: normalizeWorkSource(row.work_source) }
      : row
  ))
}

export async function getBookChapters(book, signal) {
  const params = new URLSearchParams({ book: String(book) })
  const data = await requestJson(`/api/biblical-texts/book-content?${params}`, signal)
  const chapters = (data.content ?? [])
    .map(({ chapter }) => Number(chapter))
    .filter((chapter) => Number.isInteger(chapter) && chapter > 0)

  return [...new Set(chapters)].sort((left, right) => left - right)
}

export async function getVerseDetails({ book, chapter, verse }, signal) {
  const path = [book, chapter, verse].map((segment) => encodeURIComponent(String(segment))).join('/')
  return requestJson(`/api/v1/texts/${path}/details`, signal)
}
