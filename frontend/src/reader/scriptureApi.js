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
      name,
      testament: normalizedTaxonomy(book?.testament, 'testament'),
      collection: normalizedTaxonomy(book?.collection, 'collection'),
    }]
  })
}

export async function getChapter({ book, chapter }, signal) {
  const params = new URLSearchParams({ book: String(book), chapter: String(chapter) })
  const data = await requestJson(`/api/biblical-texts/chapter-content?${params}`, signal)
  return data.content ?? []
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
