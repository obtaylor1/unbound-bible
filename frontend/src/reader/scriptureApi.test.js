import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getBookChapters,
  getBookCatalog,
  getBooks,
  getChapter,
  getVerseDetails,
  normalizeWorkSource,
  requestJson
} from './scriptureApi'

afterEach(() => vi.unstubAllGlobals())

describe('scripture API', () => {
  it('normalizes API work-source fields once with strict booleans and readable defaults', () => {
    expect(normalizeWorkSource({
      source_key: 'webbe-deuterocanon',
      source_label: '  ',
      translator: 'World English Bible contributors',
      source_language: 'Greek and Hebrew',
      source_tradition: 'Septuagint and Masoretic',
      published_year: 2024,
      license: 'Public Domain',
      attribution: 'World English Bible British Edition.',
      provenance_url: 'https://ebible.org/details.php?id=eng-webbe',
      fallback: 1,
      modified: true,
      modification_note: 'Book names were standardized.',
      verification_status: 'provisional',
      canon_scope: 'ethio81',
    })).toEqual({
      sourceKey: 'webbe-deuterocanon',
      sourceLabel: 'Source details unavailable',
      translator: 'World English Bible contributors',
      sourceLanguage: 'Greek and Hebrew',
      sourceTradition: 'Septuagint and Masoretic',
      publishedYear: 2024,
      license: 'Public Domain',
      attribution: 'World English Bible British Edition.',
      provenanceUrl: 'https://ebible.org/details.php?id=eng-webbe',
      fallback: false,
      modified: true,
      modificationNote: 'Book names were standardized.',
      verificationStatus: 'provisional',
      canonScope: 'ethio81',
    })
    expect(normalizeWorkSource(null)).toBeNull()
    expect(normalizeWorkSource('not a source')).toBeNull()
  })

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
      {
        id: 'genesis',
        name: 'Genesis',
        testament: 'Old Testament',
        collection: 'Pentateuch',
        coverage: null,
        recommendedEdition: null,
        unavailableReason: null,
      },
      {
        id: 'matthew',
        name: 'Matthew',
        testament: 'New Testament',
        collection: 'Gospels',
        coverage: null,
        recommendedEdition: null,
        unavailableReason: null,
      },
      {
        id: '1-enoch',
        name: '1 Enoch',
        testament: null,
        collection: null,
        coverage: null,
        recommendedEdition: null,
        unavailableReason: null,
      },
    ])
  })

  it('normalizes Ethiopian recommendations and safely clones coverage metadata', async () => {
    const coverage = [{ edition_code: 'EOTC-COMPOSITE-EN', chapters: 50 }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ books: [{
        id: ' genesis ',
        name: ' Genesis ',
        testament: 'old',
        collection: 'Pentateuch',
        coverage,
        recommended_edition: ' eotc-composite-en ',
        unavailable_reason: null,
      }] }),
    }))

    const catalog = await getBookCatalog('ETHIO81')

    expect(catalog).toEqual([{
      id: 'genesis',
      name: 'Genesis',
      testament: 'Old Testament',
      collection: 'Pentateuch',
      coverage: [{ edition_code: 'EOTC-COMPOSITE-EN', chapters: 50 }],
      recommendedEdition: 'EOTC-COMPOSITE-EN',
      unavailableReason: null,
    }])
    expect(catalog[0].coverage).not.toBe(coverage)
    expect(catalog[0].coverage[0]).not.toBe(coverage[0])
  })

  it('keeps old string and sparse object book payloads compatible', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ books: ['Genesis', { name: '1 Enoch' }] }),
    }))

    await expect(getBookCatalog('ETHIO81')).resolves.toEqual([
      {
        id: 'genesis', name: 'Genesis', testament: null, collection: null,
        coverage: null, recommendedEdition: null, unavailableReason: null,
      },
      {
        id: '1-enoch', name: '1 Enoch', testament: null, collection: null,
        coverage: null, recommendedEdition: null, unavailableReason: null,
      },
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

  it('adds normalized source metadata without changing legacy chapter rows', async () => {
    const legacy = { verse: 1, translation: 'KJV', text: 'First' }
    const sourced = {
      verse: 2,
      translation: 'EOTC-COMPOSITE-EN',
      text: 'Second',
      work_source: {
        source_label: 'Murdock Peshitta',
        translator: 'James Murdock',
        fallback: false,
        modified: false,
      },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ content: [legacy, sourced] }),
    }))

    const result = await getChapter({ book: 'Matthew', chapter: 1 })

    expect(result[0]).toEqual(legacy)
    expect(result[1]).toMatchObject({
      work_source: sourced.work_source,
      workSource: {
        sourceLabel: 'Murdock Peshitta',
        translator: 'James Murdock',
        fallback: false,
        modified: false,
      },
    })
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
