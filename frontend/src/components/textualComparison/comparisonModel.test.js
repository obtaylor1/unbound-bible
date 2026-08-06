import { describe, expect, it } from 'vitest'
import {
  DEFAULT_TRANSLATIONS,
  applyTranslationToggle,
  buildInstalledSources,
  buildSourceState,
  diffWords,
  filterTranslations,
  reconcileSourceSelection,
  registerInstalledSources,
  sourceFromRow,
  summarizeComparison,
} from './comparisonModel'

describe('comparisonModel', () => {
  it('starts with preferred source codes rather than phantom catalogue entries', () => {
    expect(DEFAULT_TRANSLATIONS).toEqual(['eotc-composite-en', 'geez1980-research', 'kjv'])
  })

  it('derives the installed edition and its literal work-level provenance', () => {
    expect(sourceFromRow({
      translation: 'ignored',
      edition: {
        code: 'eotc-composite-en',
        name: 'Ethiopian Orthodox Bible — Composite English Edition',
        language: 'English',
        source_tradition: 'Ethiopian Orthodox Tewahedo',
      },
      work_source: {
        source_label: 'KJV 1611 fallback',
        source_tradition: 'King James tradition',
        translator: 'King James Version translators',
        attribution: 'Public-domain archive text.',
        provenance_url: 'https://example.test/source',
        fallback: true,
        verification_status: 'provisional',
        canon_scope: 'ethio81',
      },
    })).toMatchObject({
      key: 'eotc-composite-en',
      code: 'EOTC-COMPOSITE-EN',
      name: 'Ethiopian Orthodox Bible — Composite English Edition',
      language: 'English',
      tradition: 'King James tradition',
      sourceLabel: 'KJV 1611 fallback',
      translator: 'King James Version translators',
      attribution: 'Public-domain archive text.',
      provenanceUrl: 'https://example.test/source',
      fallback: true,
      provisional: true,
      canonScope: 'ethio81',
    })
  })

  it('uses strict booleans, rejects unsafe provenance links, and supports legacy rows', () => {
    expect(sourceFromRow({
      translation: ' KJV ',
      edition: { language: '', source_tradition: '' },
      work_source: {
        fallback: 'true',
        provenance_url: 'javascript:alert(1)',
      },
    })).toMatchObject({
      key: 'kjv',
      name: 'KJV',
      language: 'Unknown language',
      tradition: 'Source details pending',
      fallback: false,
      provisional: false,
      provenanceUrl: null,
    })
    expect(sourceFromRow({ translation: '   ' })).toBeNull()
  })

  it('builds deterministic installed choices and deduplicates by actual edition code', () => {
    const sources = buildInstalledSources([
      { translation: 'WEB', edition: { code: 'WEB', name: 'World English Bible' } },
      { translation: 'KJV', edition: { code: 'KJV', name: 'King James Version' } },
      { translation: 'WEB', edition: { code: 'web', name: 'Duplicate WEB label' } },
    ])
    expect(sources.map(({ code, name }) => [code, name])).toEqual([
      ['KJV', 'King James Version'],
      ['WEB', 'World English Bible'],
    ])
  })

  it('preserves installed selections and prefers the composite edition as base', () => {
    const installed = buildInstalledSources([
      { translation: 'KJV', edition: { code: 'KJV' } },
      { translation: 'EOTC-COMPOSITE-EN', edition: { code: 'EOTC-COMPOSITE-EN' } },
      { translation: 'ASV', edition: { code: 'ASV' } },
    ])
    expect(reconcileSourceSelection({
      installed,
      selected: ['kjv', 'missing-edition'],
      base: 'kjv',
    })).toEqual({
      selected: ['kjv', 'eotc-composite-en'],
      base: 'eotc-composite-en',
    })
  })

  it('keeps the preferred composite source selected when four other sources were retained', () => {
    const installed = buildInstalledSources([
      ...['KJV', 'ASV', 'WEB', 'DRA', 'EOTC-COMPOSITE-EN'].map((code) => ({
        translation: code,
        edition: { code },
      })),
    ])
    const result = reconcileSourceSelection({
      installed,
      selected: ['kjv', 'asv', 'web', 'dra'],
      base: 'kjv',
    })
    expect(result.selected).toHaveLength(4)
    expect(result.selected).toContain('eotc-composite-en')
    expect(result.base).toBe('eotc-composite-en')
  })

  it('limits a comparison to four sources', () => {
    expect(applyTranslationToggle(['eth81', 'kjv', 'asv', 'web'], 'webbe', 'eth81'))
      .toEqual({
        selected: ['eth81', 'kjv', 'asv', 'web'],
        base: 'eth81',
        limitReached: true,
      })
  })

  it('keeps one translation selected', () => {
    expect(applyTranslationToggle(['kjv'], 'kjv', 'kjv')).toEqual({
      selected: ['kjv'],
      base: 'kjv',
      minimumReached: true,
    })
  })

  it('selects a new base after removing the current base', () => {
    expect(applyTranslationToggle(['eth81', 'kjv'], 'eth81', 'eth81')).toEqual({
      selected: ['kjv'],
      base: 'kjv',
    })
  })

  it('filters translations by category and query', () => {
    registerInstalledSources([
      { key: 'eotc-composite-en', code: 'EOTC-COMPOSITE-EN', name: 'Composite English', tradition: 'Ethiopian Orthodox', year: 'Provisional', language: 'English', categories: ['ethiopian'] },
      { key: 'kjv', code: 'KJV', name: 'King James Version', tradition: 'Protestant', year: '1611', language: 'English', categories: ['protestant'] },
    ])
    expect(filterTranslations({ category: 'ethiopian', query: 'composite' }).map(({ key }) => key))
      .toEqual(['eotc-composite-en'])
  })

  it('searches numeric publication years from installed source metadata', () => {
    registerInstalledSources([sourceFromRow({
      translation: 'KJV',
      work_source: { published_year: 1611 },
    })])
    expect(filterTranslations({ query: '1611' }).map(({ key }) => key)).toEqual(['kjv'])
  })

  it('describes an installed source with blank text as unavailable', () => {
    expect(buildSourceState({ key: 'eotc-composite-en', book: 'Genesis', text: '  ' })).toMatchObject({
      kind: 'translation-unavailable',
      title: 'Text unavailable',
    })
  })

  it('distinguishes a canon exclusion from a missing translation', () => {
    expect(buildSourceState({ key: 'kjv', book: '1 Enoch', text: null }).kind)
      .toBe('canon-excluded')
    expect(buildSourceState({ key: 'asv', book: 'Genesis', text: null }).kind)
      .toBe('translation-unavailable')
  })

  it('returns available text without a warning', () => {
    expect(buildSourceState({ key: 'kjv', book: 'Genesis', text: 'In the beginning' }))
      .toEqual({ kind: 'available', text: 'In the beginning' })
  })

  it('marks words that differ from the base while ignoring case and punctuation', () => {
    expect(diffWords('At first, God made.', 'In the beginning God created.'))
      .toEqual([
        { text: 'At', differs: true },
        { text: ' ', differs: false },
        { text: 'first,', differs: true },
        { text: ' ', differs: false },
        { text: 'God', differs: false },
        { text: ' ', differs: false },
        { text: 'made.', differs: true },
      ])
  })

  it('creates a beginner summary only from available texts', () => {
    expect(summarizeComparison([
      'In the beginning God created the heaven and the earth.',
      'At first God made the heaven and the earth.',
      null,
    ])).toMatchObject({
      availableCount: 2,
      differenceCount: 3,
      message: 'The available sources preserve the same passage with some differences in wording.',
    })
  })

  it('does not count a missing source as a wording difference', () => {
    expect(summarizeComparison(['In the beginning', null])).toEqual({
      availableCount: 1,
      differenceCount: 0,
      message: 'One source is available. Add another source to compare wording.',
    })
  })
})
