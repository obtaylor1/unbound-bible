import { describe, expect, it } from 'vitest'
import {
  COMPOSITE_ENGLISH_EDITION_CODE,
  isCompositeEnglishEdition,
} from './compositeEdition'

describe('compositeEdition', () => {
  it('owns the normalized composite edition identity in one shared contract', () => {
    expect(COMPOSITE_ENGLISH_EDITION_CODE).toBe('EOTC-COMPOSITE-EN')
    expect(isCompositeEnglishEdition({ code: '  eotc-composite-en  ' })).toBe(true)

    for (const edition of [
      null,
      {},
      { code: null },
      { code: 'KJV' },
      { code: 'EOTC-COMPOSITE-ENGLISH' },
    ]) expect(isCompositeEnglishEdition(edition)).toBe(false)
  })
})
