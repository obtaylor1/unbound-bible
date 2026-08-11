import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'


describe('runtime font loading', () => {
  it('keeps global page styles independent from remote font services', () => {
    for (const stylesheet of [
      'src/components/HomePage.css',
      'src/components/ForumPage.css',
    ]) {
      const css = readFileSync(stylesheet, 'utf8')
      expect(css).not.toMatch(/fonts\.(?:googleapis|gstatic)\.com/)
      expect(css).not.toMatch(/@import\s+url\(['"]?https?:\/\//)
    }
  })
})
