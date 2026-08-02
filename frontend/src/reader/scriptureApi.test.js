import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getBookChapters,
  getBookCatalog,
  getBooks,
  getChapter,
  getVerseDetails,
  requestJson
} from './scriptureApi'

afterEach(() => vi.unstubAllGlobals())

describe('scripture API', () => {
  it('normalizes book strings and named records while forwarding the signal', async () => {
    const signal = new AbortController().signal
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ books: ['Genesis', { name: '1 Enoch' }, { title: 'Ignored' }] })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(getBooks('ethio81', signal)).resolves.toEqual(['Genesis', '1 Enoch'])
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/books?canon=ETHIO81', { signal })
  })

  it('preserves normalized testament and collection metadata in the catalog contract', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ books: [
        { name: ' Genesis ', testament: 'old', collection: 'Pentateuch' },
        { name: 'Matthew', testament: 'New Testament', collection: 'Gospels' },
        { name: '1 Enoch' },
        { title: 'Ignored' },
      ] }),
    }))

    await expect(getBookCatalog('ethio81')).resolves.toEqual([
      { name: 'Genesis', testament: 'Old Testament', collection: 'Pentateuch' },
      { name: 'Matthew', testament: 'New Testament', collection: 'Gospels' },
      { name: '1 Enoch', testament: null, collection: null },
    ])
  })

  it.each([
    ['omitted', undefined],
    ['null', null],
    ['blank', '   ']
  ])('defaults a %s canon value to the Ethiopian catalog', async (_, canon) => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ books: [] })
    })
    vi.stubGlobal('fetch', fetchMock)

    await getBooks(canon)

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/books?canon=ETHIO81', { signal: undefined })
  })

  it('returns all chapter content without translation filtering', async () => {
    const content = [
      { verse: 1, translation: 'KJV', text: 'First' },
      { verse: 1, translation: 'NRSV', text: 'Second' }
    ]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ content })
    }))

    await expect(getChapter({ book: 'Song of Songs', chapter: 2 })).resolves.toEqual(content)
    expect(fetch).toHaveBeenCalledWith(
      '/api/biblical-texts/chapter-content?book=Song+of+Songs&chapter=2',
      { signal: undefined }
    )
  })

  it('derives sorted unique positive chapter numbers from book content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        content: [
          { chapter: 3 },
          { chapter: '1' },
          { chapter: 2 },
          { chapter: 3 },
          { chapter: 0 },
          { chapter: 'not-a-number' }
        ]
      })
    }))

    await expect(getBookChapters('1 Enoch')).resolves.toEqual([1, 2, 3])
  })

  it('safely encodes verse detail path segments', async () => {
    const details = { reference: 'Song of Songs 2:3' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => details
    }))

    await expect(getVerseDetails({ book: 'Song/Songs', chapter: '2', verse: '3' })).resolves.toEqual(details)
    expect(fetch).toHaveBeenCalledWith('/api/v1/texts/Song%2FSongs/2/3/details', { signal: undefined })
  })

  it('throws a clear error for failed responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, statusText: 'Unavailable' }))

    await expect(requestJson('/api/example')).rejects.toThrow(
      'Scripture request failed (503 Unavailable)'
    )
  })
})
