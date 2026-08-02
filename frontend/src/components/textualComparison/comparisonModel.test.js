import { describe, expect, it } from 'vitest'
import {
  DEFAULT_TRANSLATIONS,
  applyTranslationToggle,
  buildSourceState,
  diffWords,
  filterTranslations,
  summarizeComparison,
} from './comparisonModel'

describe('comparisonModel', () => {
  it('starts with the Ethiopian Critical Text and KJV', () => {
    expect(DEFAULT_TRANSLATIONS).toEqual(['eth81', 'kjv'])
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
    expect(filterTranslations({ category: 'ethiopian', query: 'enoch' }).map(({ key }) => key))
      .toEqual(['1en_ch'])
    expect(filterTranslations({ category: 'original', query: '' }).map(({ key }) => key))
      .toContain('oshb')
  })

  it('describes missing Ethiopian Genesis text as a missing database record', () => {
    expect(buildSourceState({ key: 'eth81', book: 'Genesis', text: null })).toMatchObject({
      kind: 'database-missing',
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
      message: 'Both available sources describe God as the creator at the beginning of creation.',
    })
  })
})
