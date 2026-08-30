import { describe, expect, it } from 'vitest'
import {
  hashForPage,
  pageFromHash,
  pageFromKnownHash,
  titleForPage,
} from './pageRoutes'

describe('page routes', () => {
  it('maps the supplied AI Study deep link to Scripture Research AI', () => {
    expect(pageFromHash('#aistudy')).toBe('chat')
  })

  it('falls back to home for unknown hashes', () => {
    expect(pageFromHash('#not-a-page')).toBe('home')
    expect(pageFromKnownHash('#not-a-page')).toBeNull()
    expect(pageFromKnownHash('#library')).toBe('notes')
  })

  it('ignores query parameters when resolving a page', () => {
    expect(pageFromHash('#scriptures?book=Genesis&chapter=2')).toBe('apocrypha')
    expect(pageFromHash('#apocrypha?translation=KJV')).toBe('apocrypha')
  })

  it('creates stable canonical hashes', () => {
    expect(hashForPage('chat')).toBe('#aistudy')
    expect(hashForPage('textual')).toBe('#compare')
    expect(hashForPage('scripture-verification-admin')).toBe('#admin-scripture-verification')
    expect(pageFromHash('#admin-scripture-verification')).toBe('scripture-verification-admin')
  })

  it('provides a stable accessible page title', () => {
    expect(titleForPage('chat')).toBe('Scripture Research AI')
    expect(titleForPage('textual')).toBe('Compare Scripture')
    expect(titleForPage('scripture-verification-admin')).toBe('Scripture source verification')
    expect(titleForPage('missing')).toBe('The Unbound Bible')
  })
})
