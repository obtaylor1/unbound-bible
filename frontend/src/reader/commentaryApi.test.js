import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  CommentaryRequestError,
  getCommentaryEntries,
  getCommentarySources,
  requestCommentary,
} from './commentaryApi'

afterEach(() => vi.unstubAllGlobals())

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('commentary API', () => {
  it('requests a verse with encoded source and reference and forwards the signal', async () => {
    const signal = new AbortController().signal
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      availability: 'no_entry', entries: [],
    }))
    vi.stubGlobal('fetch', fetchMock)

    await getCommentaryEntries({
      source: ' john/gill ', book: ' Song of Solomon ', chapter: 1, verse: 2,
    }, signal)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/commentaries/entries?source=john%2Fgill&book=Song+of+Solomon&chapter=1&verse=2',
      { signal },
    )
  })

  it('omits verse from chapter requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      availability: 'no_entry', entries: [],
    }))
    vi.stubGlobal('fetch', fetchMock)

    await getCommentaryEntries({ source: 'john-gill', book: 'Genesis', chapter: 1 })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/commentaries/entries?source=john-gill&book=Genesis&chapter=1',
      { signal: undefined },
    )
  })

  it.each([
    [{ source: '', book: 'Genesis', chapter: 1 }, 'source must be a nonblank string'],
    [{ source: 'john-gill', book: '  ', chapter: 1 }, 'book must be a nonblank string'],
    [{ source: 'john-gill', book: 'Genesis', chapter: 0 }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: 501 }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: 1.5 }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: 1, verse: 0 }, 'verse must be an integer between 1 and 1000'],
    [{ source: 'john-gill', book: 'Genesis', chapter: 1, verse: 1001 }, 'verse must be an integer between 1 and 1000'],
    [{ source: 'john-gill', book: 'Genesis', chapter: 1, verse: Number.MAX_SAFE_INTEGER + 1 }, 'verse must be an integer between 1 and 1000'],
    [{ source: 'john-gill', book: 'Genesis', chapter: true }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: [1] }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: '1e2' }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: '0x10' }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: ' 1 ' }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: '+1' }, 'chapter must be an integer between 1 and 500'],
    [{ source: 'john-gill', book: 'Genesis', chapter: '01' }, 'chapter must be an integer between 1 and 500'],
  ])('rejects invalid request coordinates before fetching', async (request, message) => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(getCommentaryEntries(request)).rejects.toThrow(message)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('accepts canonical base-10 coordinate strings', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      availability: 'available', entries: [],
    }))
    vi.stubGlobal('fetch', fetchMock)

    await getCommentaryEntries({
      source: 'john-gill', book: 'Genesis', chapter: '500', verse: '1000',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/commentaries/entries?source=john-gill&book=Genesis&chapter=500&verse=1000',
      { signal: undefined },
    )
  })

  it('returns only normalized sources with documented scalar fields', async () => {
    const polluted = JSON.parse('{"id":"unsafe","title":"Unsafe","__proto__":{"polluted":true}}')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      sources: [
        {
          id: ' john-gill ', title: ' Exposition ', abbreviation: ' JG ', author: 'John Gill',
          publication_period: '1746–1763', tradition: 'Baptist', language: 'English',
          license_spdx: 'CC0-1.0', license_url: 'https://example.test/license',
          attribution: 'Public domain', edition_version: 3, coverage: { books: 66 },
          extra: 'discard me',
        },
        { id: '', title: 'Missing id' },
        { id: 'missing-title' },
        { id: 'bad-types', title: 'Bad Types', abbreviation: 9, edition_version: 1.5 },
        null,
        polluted,
      ],
    })))

    await expect(getCommentarySources()).resolves.toEqual([
      {
        id: 'john-gill', title: 'Exposition', abbreviation: 'JG', author: 'John Gill',
        publication_period: '1746–1763', tradition: 'Baptist', language: 'English',
        license_spdx: 'CC0-1.0', license_url: 'https://example.test/license',
        attribution: 'Public domain', edition_version: 3,
      },
      { id: 'bad-types', title: 'Bad Types' },
      { id: 'unsafe', title: 'Unsafe' },
    ])
    expect({}.polluted).toBeUndefined()
  })

  it.each([
    [{}, []],
    [{ sources: null }, []],
    [{ sources: 'not-an-array' }, []],
  ])('normalizes malformed source collections to an empty array', async (payload, expected) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(payload)))
    await expect(getCommentarySources()).resolves.toEqual(expected)
  })

  it('normalizes reference, availability, source, and valid entries without copying extras', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      reference: { book: ' Genesis ', chapter: 1, verse: 2, unsafe: true },
      availability: 'wider_range',
      truncated: true,
      source: { id: 'john-gill', title: 'Exposition', edition_version: 2, extra: true },
      entries: [
        {
          body: ' Commentary body. ', citation: ' Gill, Genesis 1:1–2. ',
          entry_type: 'verse_range', heading: ' Creation ', source_locator: ' GEN.1.1-2 ',
          scope: { verse_start: 1, verse_end: 2, unsafe: true }, position: 0,
          checksum: 'not-public', extra: true,
        },
        { body: 'Missing citation', citation: '  ', scope: { verse_start: 1, verse_end: 1 } },
        { body: 'Reversed', citation: 'Citation', scope: { verse_start: 3, verse_end: 2 } },
        { body: 'Bad coordinate', citation: 'Citation', scope: { verse_start: 0, verse_end: 1 } },
        null,
      ],
    })))

    await expect(getCommentaryEntries({ source: 'john-gill', book: 'Genesis', chapter: 1, verse: 2 }))
      .resolves.toEqual({
        reference: { book: 'Genesis', chapter: 1, verse: 2 },
        availability: 'wider_range',
        truncated: true,
        source: { id: 'john-gill', title: 'Exposition', edition_version: 2 },
        entries: [{
          body: 'Commentary body.', citation: 'Gill, Genesis 1:1–2.',
          entry_type: 'verse_range', heading: 'Creation', source_locator: 'GEN.1.1-2',
          scope: { verse_start: 1, verse_end: 2 },
        }],
      })
  })

  it.each(['unknown', '', null, {}, 7, undefined])('rejects an invalid availability value', async (availability) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ availability, entries: [] })))
    await expect(getCommentaryEntries({ source: 'john-gill', book: 'Genesis', chapter: 1 }))
      .rejects.toMatchObject({
        name: 'CommentaryRequestError', message: 'Commentary response was invalid',
        status: 200, code: 'invalid_commentary_response',
      })
  })

  it('defaults an absent truncated flag to false', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      availability: 'available', entries: [],
    })))
    await expect(getCommentaryEntries({ source: 'john-gill', book: 'Genesis', chapter: 1 }))
      .resolves.toMatchObject({ truncated: false })
  })

  it.each([null, 0, 1, 'false', {}, []])('rejects a malformed truncated flag', async (truncated) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      availability: 'available', truncated, entries: [],
    })))
    await expect(getCommentaryEntries({ source: 'john-gill', book: 'Genesis', chapter: 1 }))
      .rejects.toMatchObject({
        name: 'CommentaryRequestError', status: 200, code: 'invalid_commentary_response',
      })
  })

  it.each([
    [null, {}],
    [{ book: ' ', chapter: 0, verse: 1001 }, {}],
    [{ book: 'Genesis', chapter: 1 }, { book: 'Genesis', chapter: 1 }],
  ])('normalizes malformed reference fields', async (reference, expected) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      reference, availability: 'no_entry', entries: [],
    })))
    const result = await getCommentaryEntries({ source: 'john-gill', book: 'Genesis', chapter: 1 })
    expect(result.reference).toEqual(expected)
  })

  it.each([
    [{ detail: { code: 'source_not_found', message: 'Commentary source was not found.' } }, 'Commentary source was not found.', 'source_not_found'],
    [{ detail: 'Not permitted' }, 'Not permitted', undefined],
    [{ detail: { code: 42, message: { unsafe: true } } }, 'Commentary request failed (404)', undefined],
  ])('preserves safe API error status and code', async (payload, message, code) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(payload, 404)))

    const error = await requestCommentary('/api/v1/commentaries/sources').catch((caught) => caught)

    expect(error).toBeInstanceOf(CommentaryRequestError)
    expect(error).toMatchObject({ message, status: 404, code })
  })

  it('uses a generic status-bearing message for malformed error JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>nope</html>', { status: 503 })))
    await expect(requestCommentary('/api/v1/commentaries/sources')).rejects.toMatchObject({
      name: 'CommentaryRequestError', message: 'Commentary request failed (503)', status: 503,
    })
  })

  it('rethrows AbortError without changing its identity', async () => {
    const abort = new DOMException('The operation was aborted.', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))

    const caught = await requestCommentary('/api/v1/commentaries/sources').catch((error) => error)
    expect(caught).toBe(abort)
  })

  it.each([true, false])('rethrows AbortError from response parsing for ok=%s', async (ok) => {
    const abort = new DOMException('The operation was aborted.', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok,
      status: ok ? 200 : 503,
      json: vi.fn().mockRejectedValue(abort),
    }))

    const caught = await requestCommentary('/api/v1/commentaries/sources').catch((error) => error)
    expect(caught).toBe(abort)
  })

  it('converts network failures to a safe generic request error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private upstream hostname leaked')))
    await expect(requestCommentary('/api/v1/commentaries/sources')).rejects.toMatchObject({
      name: 'CommentaryRequestError', message: 'Commentary request failed',
      status: undefined, code: undefined,
    })
  })

  it('converts successful malformed JSON to a safe request error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not json', { status: 200 })))
    await expect(requestCommentary('/api/v1/commentaries/sources')).rejects.toMatchObject({
      name: 'CommentaryRequestError', message: 'Commentary response was invalid', status: 200,
    })
  })
})
