export async function requestJson(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    const status = [response.status, response.statusText].filter(Boolean).join(' ')
    throw new Error(`Scripture request failed${status ? ` (${status})` : ''}`)
  }
  return response.json()
}

export async function getBooks(canon, signal) {
  const params = new URLSearchParams({ canon: String(canon ?? '').toUpperCase() })
  const data = await requestJson(`/api/v1/books?${params}`, signal)

  return (data.books ?? [])
    .map((book) => typeof book === 'string' ? book : book?.name)
    .filter((book) => typeof book === 'string')
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
