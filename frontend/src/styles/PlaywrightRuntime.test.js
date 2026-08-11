import { describe, expect, it } from 'vitest'

import { parsePort, shellQuote } from '../../playwright.runtime.js'


describe('Playwright runtime inputs', () => {
  it.each(['0', '65536', 'abc', '8011; touch /tmp/unsafe'])('rejects unsafe ports: %s', (value) => {
    expect(() => parsePort(value)).toThrow(/valid TCP port/)
  })

  it('accepts a valid TCP port', () => {
    expect(parsePort('8011')).toBe(8011)
  })

  it('single-quotes shell arguments without permitting substitution', () => {
    expect(shellQuote('/tmp/python $(touch /tmp/unsafe)')).toBe("'/tmp/python $(touch /tmp/unsafe)'")
    expect(shellQuote("it's/python")).toBe("'it'\"'\"'s/python'")
  })
})
