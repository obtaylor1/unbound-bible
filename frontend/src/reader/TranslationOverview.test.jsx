import { readFileSync } from 'node:fs'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import TranslationOverview from './TranslationOverview'

const readerCss = readFileSync('src/reader/readerTokens.css', 'utf8')
const navigationCss = readFileSync('src/components/Navigation.css', 'utf8')
const appCss = readFileSync('src/App.css', 'utf8')
const compositeEdition = {
  code: 'EOTC-COMPOSITE-EN',
  name: 'Ethiopian Orthodox Bible — Composite English Edition',
}

afterEach(() => {
  document.body.style.overflow = ''
})

describe('TranslationOverview', () => {
  it('explains the composite scope, source families, limits, and exact-source path', async () => {
    const user = userEvent.setup()
    render(<TranslationOverview edition={compositeEdition} />)

    await user.click(screen.getByRole('button', { name: 'About this translation' }))
    const dialog = screen.getByRole('dialog', {
      name: 'About the Ethiopian Composite English edition',
    })

    for (const text of [
      'combines public-domain and openly licensed English sources',
      'not one uniform Ethiopian Orthodox translation',
      '83 works',
      '1,520 chapters',
      '38,938 verses',
      '82 ETHIO81 works plus one supplemental work',
      'Hebrew-based World Messianic Bible (WMB) Old Testament',
      'Murdock Syriac Peshitta New Testament',
      'World English Bible (WEB) deuterocanon',
      'Ge’ez-sourced Meqabyan',
      'R. H. Charles editions of Enoch and Jubilees',
      'Six works use a clearly labeled KJV fallback',
      'All source records remain provisional pending more precise upstream revision verification',
      'About this text',
    ]) expect(within(dialog).getByText(new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'))).toBeVisible()

    const auditLink = within(dialog).getByRole('link', {
      name: /read the detailed source audit/i,
    })
    expect(auditLink).toHaveAttribute(
      'href',
      'https://github.com/obtaylor1/unbound-bible/blob/main/docs/operations/ethiopian-composite-release-audit.md',
    )
    expect(auditLink).toHaveAttribute('target', '_blank')
    expect(auditLink).toHaveAttribute('rel', expect.stringMatching(/noopener/))
    expect(auditLink).toHaveAttribute('rel', expect.stringMatching(/noreferrer/))
    expect(dialog.querySelector('a button, button a')).toBeNull()
  })

  it('normalizes the composite code and stays absent for every other edition', () => {
    const { rerender } = render(
      <TranslationOverview edition={{ code: '  eotc-composite-en  ' }} />,
    )
    expect(screen.getByRole('button', { name: 'About this translation' })).toBeVisible()

    rerender(<TranslationOverview edition={{ code: 'KJV' }} />)
    expect(screen.queryByRole('button', { name: 'About this translation' })).not.toBeInTheDocument()

    rerender(<TranslationOverview edition={null} />)
    expect(screen.queryByRole('button', { name: 'About this translation' })).not.toBeInTheDocument()
  })

  it('focuses the close control, closes with Escape, restores focus, and preserves body overflow', async () => {
    const user = userEvent.setup()
    document.body.style.overflow = 'clip'
    render(<TranslationOverview edition={compositeEdition} />)
    const trigger = screen.getByRole('button', { name: 'About this translation' })

    trigger.focus()
    await user.keyboard('{Enter}')
    const close = screen.getByRole('button', { name: 'Close translation information' })
    expect(close).toHaveFocus()
    expect(document.body).toHaveStyle({ overflow: 'hidden' })

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    expect(document.body).toHaveStyle({ overflow: 'clip' })
  })

  it('closes from its close control and returns focus to the trigger', async () => {
    const user = userEvent.setup()
    render(<TranslationOverview edition={compositeEdition} />)
    const trigger = screen.getByRole('button', { name: 'About this translation' })

    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: 'Close translation information' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('cycles forward and backward through the actual dialog controls in document order', async () => {
    const user = userEvent.setup()
    render(<TranslationOverview edition={compositeEdition} />)

    await user.click(screen.getByRole('button', { name: 'About this translation' }))
    const close = screen.getByRole('button', { name: 'Close translation information' })
    const audit = screen.getByRole('link', { name: /read the detailed source audit/i })
    expect(close).toHaveFocus()

    await user.tab()
    expect(audit).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()
    await user.tab({ shift: true })
    expect(audit).toHaveFocus()
    await user.tab({ shift: true })
    expect(close).toHaveFocus()
  })

  it('ignores dialog clicks but closes from the backdrop', async () => {
    const user = userEvent.setup()
    const { container } = render(<TranslationOverview edition={compositeEdition} />)
    const trigger = screen.getByRole('button', { name: 'About this translation' })
    await user.click(trigger)
    const dialog = screen.getByRole('dialog', {
      name: 'About the Ethiopian Composite English edition',
    })

    fireEvent.mouseDown(dialog)
    expect(dialog).toBeInTheDocument()

    fireEvent.mouseDown(container.querySelector('.translation-overview__backdrop'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('uses unique dialog labels when more than one disclosure is mounted', async () => {
    const user = userEvent.setup()
    render(
      <>
        <TranslationOverview edition={compositeEdition} />
        <TranslationOverview edition={compositeEdition} />
      </>,
    )

    const triggers = screen.getAllByRole('button', { name: 'About this translation' })
    await user.click(triggers[0])
    await user.click(triggers[1])
    const labelIds = screen.getAllByRole('dialog').map((dialog) => (
      dialog.getAttribute('aria-labelledby')
    ))
    expect(new Set(labelIds)).toHaveProperty('size', 2)
    labelIds.forEach((labelId) => {
      expect(document.getElementById(labelId)).toHaveTextContent(
        'About the Ethiopian Composite English edition',
      )
    })
  })

  it('uses reader theme tokens, 44px controls, strong focus, zoom-safe wrapping, mobile containment, and reduced motion', () => {
    expect(readerCss).toMatch(/\.translation-overview__trigger\s*\{[^}]*min-height:\s*44px/s)
    expect(readerCss).toMatch(/\.translation-overview__close\s*\{[^}]*min-height:\s*44px/s)
    expect(readerCss).toMatch(/\.translation-overview__(?:trigger|close):focus-visible\s*\{[^}]*outline:\s*3px solid var\(--reader-gold\)/s)
    expect(readerCss).toMatch(/\.translation-overview__dialog\s*\{[^}]*color:\s*var\(--reader-text\)[^}]*background:\s*var\(--reader-surface\)/s)
    expect(readerCss).toMatch(/\.translation-overview__dialog\s*\{[^}]*max-width:\s*min\([^;]*calc\(100vw - 2rem\)/s)
    expect(readerCss).toMatch(/\.translation-overview__content\s*\{[^}]*overflow-wrap:\s*anywhere[^}]*max-width:\s*65ch/s)
    expect(readerCss).toMatch(/@media \(max-width: 30rem\)[\s\S]*\.translation-overview__dialog/s)
    expect(readerCss).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*\.translation-overview/s)
  })

  it('keeps its scrollable dialog bounded to the viewport', () => {
    expect(readerCss).toMatch(/\.translation-overview__dialog\s*\{[^}]*max-height:\s*min\([^;]*100dvh[^;]*\)[^}]*overflow:\s*hidden/s)
    expect(readerCss).toMatch(/\.translation-overview__content\s*\{[^}]*overflow-y:\s*auto/s)
    expect(readerCss).toMatch(/\.translation-overview__backdrop\s*\{[^}]*inset:\s*0[^}]*overflow:\s*hidden/s)
  })

  it('places the pointer-intercepting backdrop above persistent app navigation without an ancestor stacking context', () => {
    const navigationLayer = Number(
      navigationCss.match(/\.navigation\s*\{[^}]*z-index:\s*(\d+)/s)?.[1],
    )
    const translationLayer = Number(
      readerCss.match(/\.translation-overview__backdrop\s*\{[^}]*z-index:\s*(\d+)/s)?.[1],
    )

    expect(navigationLayer).toBeGreaterThan(0)
    expect(translationLayer).toBeGreaterThan(navigationLayer)
    expect(readerCss).toMatch(/\.translation-overview__backdrop\s*\{[^}]*pointer-events:\s*auto/s)

    const stackingContextProperties = /(?:^|;)\s*(?:transform|filter|perspective|isolation|contain|will-change|opacity)\s*:/
    for (const [css, selector] of [
      [appCss, '.app'],
      [readerCss, '.scripture-reader'],
      [readerCss, '.scripture-reader-shell__main'],
      [readerCss, '.scripture-pane'],
      [readerCss, '.text-source-disclosure'],
      [readerCss, '.translation-overview'],
    ]) {
      const escapedSelector = selector.replaceAll('.', '\\.')
      const declarations = css.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`))?.[1]
      expect(declarations, `${selector} must have a readable CSS block`).toBeTruthy()
      expect(declarations).not.toMatch(stackingContextProperties)
      expect(declarations).not.toMatch(/position:\s*[^;]+;[^}]*z-index:/s)
    }
  })
})
