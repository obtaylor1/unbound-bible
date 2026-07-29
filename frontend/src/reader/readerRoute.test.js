import { describe, expect, it } from 'vitest'
import { parseReaderHash, readerHash } from './readerRoute'

describe('reader route', () => {
  it('uses reader defaults when parameters are absent', () => {
    expect(parseReaderHash('#scriptures')).toEqual({
      book: 'Genesis',
      chapter: 1,
      translation: 'KJV',
      canon: 'ETHIO81',
      verse: null
    })
  })

  it('reads the current location hash when no hash is supplied', () => {
    window.location.hash = '#scriptures?book=Exodus&chapter=3'

    expect(parseReaderHash()).toMatchObject({ book: 'Exodus', chapter: 3 })
  })

  it('normalizes valid reader parameters', () => {
    expect(parseReaderHash('#scriptures?book=1%20Enoch&chapter=2&translation=nrsv&canon=ethio81&verse=3')).toEqual({
      book: '1 Enoch',
      chapter: 2,
      translation: 'NRSV',
      canon: 'ETHIO81',
      verse: 3
    })
  })

  it('falls back for invalid chapter and verse values', () => {
    expect(parseReaderHash('#scriptures?chapter=0&verse=2.5')).toMatchObject({
      chapter: 1,
      verse: null
    })
    expect(parseReaderHash('#scriptures?chapter=-2&verse=nope')).toMatchObject({
      chapter: 1,
      verse: null
    })
  })

  it('serializes normalized reader state and includes only a valid verse', () => {
    expect(readerHash({
      book: 'Song of Songs',
      chapter: 4,
      translation: 'nrsv',
      canon: 'ethio81',
      verse: 7
    })).toBe('#scriptures?book=Song+of+Songs&chapter=4&translation=NRSV&canon=ETHIO81&verse=7')

    expect(readerHash({ verse: 0 })).toBe(
      '#scriptures?book=Genesis&chapter=1&translation=KJV&canon=ETHIO81'
    )
  })
})
