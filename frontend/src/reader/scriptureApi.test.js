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
      rights_url: 'https://ebible.org/engwmb/copyright.htm',
      rights_jurisdiction: 'Worldwide dedication; naming condition applies',
      source_edition: 'August 2022 stable text',
      source_revision: 'engwmb source 2026-07-24',
      fallback: 1,
      modified: true,
      modification_note: 'Book names were standardized.',
      transformations: ['Unicode NFC', 'Line endings normalized'],
      verification: {
        status: 'verified_formatting',
        label: 'Untrusted API label',
        verified_at: '2026-08-17T13:00:00Z',
      },
      canon_scope: 'ethio81',
      artifact_filename: '/private/verification/engwmb.zip',
      artifact_sha256: 'a'.repeat(64),
      reviewer: 'Private reviewer',
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
      rightsUrl: 'https://ebible.org/engwmb/copyright.htm',
      rightsJurisdiction: 'Worldwide dedication; naming condition applies',
      sourceEdition: 'August 2022 stable text',
      sourceRevision: 'engwmb source 2026-07-24',
      fallback: false,
      modified: true,
      modificationNote: 'Book names were standardized.',
      transformations: ['Unicode NFC', 'Line endings normalized'],
      verificationStatus: 'verified_formatting',
      verifiedAt: '2026-08-17T13:00:00Z',
      canonScope: 'ethio81',
    })
    expect(normalizeWorkSource(null)).toBeNull()
    expect(normalizeWorkSource('not a source')).toBeNull()
  })

  it('keeps only bounded public evidence and rejects unsafe or suspicious source URLs', () => {
    const result = normalizeWorkSource({
      source_label: 'A'.repeat(201),
      attribution: 'B'.repeat(2001),
      provenance_url: 'javascript:alert(1)',
      rights_url: 'https://example.org/%0ASet-Cookie:secret',
      transformations: [
        'Unicode NFC',
        '',
        'x'.repeat(301),
        ...Array.from({ length: 10 }, (_, index) => `Safe transformation ${index}`),
      ],
      verification: {
        status: 'not-a-real-status',
        verified_at: '/private/source/review.txt',
      },
      artifact_filename: '/private/source/archive.zip',
      artifact_sha256: 'a'.repeat(64),
      comparison_report_sha256: 'b'.repeat(64),
    })

    expect(result).toMatchObject({
      sourceLabel: 'Source details unavailable',
      attribution: null,
      provenanceUrl: null,
      rightsUrl: null,
      verificationStatus: 'not-a-real-status',
      verifiedAt: null,
    })
    expect(result.transformations).toHaveLength(8)
    expect(result).not.toHaveProperty('artifactFilename')
    expect(result).not.toHaveProperty('artifactSha256')
    expect(result).not.toHaveProperty('comparisonReportSha256')
  })

  it('redacts local paths, credentials, secrets, and deeply encoded disclosure content', () => {
    const deeplyEncodedPath = Array.from({ length: 6 }).reduce(
      (value) => encodeURIComponent(value),
      '/Users/obie/private/source.txt',
    )
    const githubToken = `ghp_${'A'.repeat(36)}`
    const safeProse = 'Psalm 23/1 retains Hebrew/Aramaic chapter/verse markers.'
    const result = normalizeWorkSource({
      source_label: 'Imported from C:\\Users\\obie\\source.txt',
      translator: `Review value ${githubToken}`,
      source_language: safeProse,
      source_tradition: 'Compared at /custom-root/archive',
      attribution: 'The secret things belong to God; the token of the covenant remained.',
      modification_note: 'clientSecret=do-not-disclose',
      rights_jurisdiction: deeplyEncodedPath,
      source_edition: '~/private/source',
      source_revision: 'Hidden\u2028separator',
      transformations: [
        safeProse,
        deeplyEncodedPath,
        'Bearer do-not-disclose',
        `Removed ${githubToken}`,
        'Hidden\u00a0separator',
        'FI/RF apparatus markers were removed.',
      ],
    })

    expect(result).toMatchObject({
      sourceLabel: 'Source details unavailable',
      translator: null,
      sourceLanguage: safeProse,
      sourceTradition: null,
      attribution: 'The secret things belong to God; the token of the covenant remained.',
      modificationNote: null,
      rightsJurisdiction: null,
      sourceEdition: null,
      sourceRevision: null,
      transformations: [safeProse, 'FI/RF apparatus markers were removed.'],
    })
  })

  it.each([
    'https://localhost/source',
    'https://localhost./source',
    'https://LOCALHOST./source',
    'https://localhost%2e/source',
    'https://localhost.localdomain/source',
    'https://localhost.localdomain./source',
    'https://archive.local/source',
    'https://ARCHIVE.LOCAL./source',
    'https://127.0.0.1/source',
    'https://2130706433/source',
    'https://0x7f000001/source',
    'https://10.0.0.1/source',
    'https://169.254.10.2/source',
    'https://192.168.1.2/source',
    'https://[::1]/source',
    'https://[100::1]/source',
    'https://[64:ff9b::1]/source',
    'https://[64:FF9B::5db8:d822]/source',
    'https://[64:ff9b::cb00:7101]/source',
    'https://[64:ff9b:1::1]/source',
    'https://[64:FF9B:1::5db8:d822]/source',
    'https://[2001:10::1]/source',
    'https://[::7f00:1]/source',
    'https://[2001:db8::1]/source',
    'https://[fc00::1]/source',
    'https://[fe80::1]/source',
    'https://[ff02::1]/source',
    'https://example.org/source path',
    'https://100.64.0.1/source',
    'https://192.0.2.1/source',
    'https://198.51.100.1/source',
    'https://203.0.113.1/source',
    'https://example.org/source?client_secret=do-not-disclose',
    'https://example.org/source?path=%252525252FUsers%252525252Fobie',
    'https://example.org/source#/private/review.txt',
    `https://example.org/source?value=ghp_${'A'.repeat(36)}`,
  ])('rejects non-public or disclosure-bearing URL %s', (provenanceUrl) => {
    expect(normalizeWorkSource({ provenance_url: provenanceUrl }).provenanceUrl).toBeNull()
  })

  it.each([
    'https://example.org./source',
    'https://[2001:db80::1]/source',
    'https://93.184.216.34/source',
    'https://192.0.3.1/source',
  ])('accepts globally routable source URL %s', (provenanceUrl) => {
    expect(normalizeWorkSource({ provenance_url: provenanceUrl }).provenanceUrl).toBe(provenanceUrl)
  })

  it('normalizes only real UTC calendar timestamps for verified statuses', () => {
    const source = (verifiedAt) => normalizeWorkSource({
      verification: { status: 'verified_exact', verified_at: verifiedAt },
    }).verifiedAt

    expect(source('2024-02-29T13:00:00Z')).toBe('2024-02-29T13:00:00Z')
    for (const invalid of [
      '2026-02-29T13:00:00Z',
      '2024-02-30T13:00:00Z',
      '2026-04-31T13:00:00Z',
      '2026-01-01T24:00:00Z',
      '2026-01-01T13:60:00Z',
      '2026-01-01T13:00:60Z',
      '2026-01-01T13:00:00+01:00',
    ]) expect(source(invalid)).toBeNull()
  })

  it('preserves legitimate named HTTPS sources and ordinary Bible prose', () => {
    expect(normalizeWorkSource({
      attribution: 'The secret things belong to God; the token of the covenant remained; 100% of the prose was retained.',
      provenance_url: 'https://ebible.org/find/show.php?id=engwmb',
      rights_url: 'https://www.gutenberg.org/policy/license.html',
    })).toMatchObject({
      attribution: 'The secret things belong to God; the token of the covenant remained; 100% of the prose was retained.',
      provenanceUrl: 'https://ebible.org/find/show.php?id=engwmb',
      rightsUrl: 'https://www.gutenberg.org/policy/license.html',
    })
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
