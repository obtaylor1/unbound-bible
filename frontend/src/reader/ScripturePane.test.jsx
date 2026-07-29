import { readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterAll, describe, expect, it, vi } from 'vitest'
import ScripturePane from './ScripturePane'

const readerTokensCss = readFileSync('src/reader/readerTokens.css', 'utf8')
const readerStyle = document.createElement('style')
readerStyle.textContent = readerTokensCss
document.head.append(readerStyle)

function cssDeclarations(selector) {
  const matchingRules = []

  function visitRules(rules) {
    for (const rule of rules) {
      if ('selectorText' in rule) {
        const selectors = rule.selectorText
          .split(',')
          .map((item) => item.trim())

        if (selectors.includes(selector)) {
          matchingRules.push(rule)
        }
      }

      if ('cssRules' in rule) {
        visitRules(rule.cssRules)
      }
    }
  }

  visitRules(readerStyle.sheet.cssRules)

  return Object.fromEntries(
    matchingRules.flatMap((rule) => (
      Array.from({ length: rule.style.length }, (_, index) => {
        const property = rule.style[index]
        return [property, rule.style.getPropertyValue(property).trim()]
      })
    )),
  )
}

function relativeLuminance(hexColor) {
  const channels = hexColor
    .slice(1)
    .match(/.{2}/g)
    .map((channel) => Number.parseInt(channel, 16) / 255)
    .map((channel) => (
      channel <= 0.04045
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4
    ))

  return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2])
}

function contrastRatio(firstColor, secondColor) {
  const first = relativeLuminance(firstColor)
  const second = relativeLuminance(secondColor)
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
}

function themeTokens(theme) {
  const tokens = cssDeclarations('.scripture-reader')
  if (theme === 'light') {
    Object.assign(
      tokens,
      cssDeclarations("[data-reader-theme='light'] .scripture-reader"),
    )
  }
  return tokens
}

function resolveToken(value, tokens) {
  const tokenName = value.match(/^var\((--[\w-]+)\)$/)?.[1]
  return tokenName ? tokens[tokenName] : value
}

afterAll(() => readerStyle.remove())

const verses = [
  { id: 10, verse: 1, text: 'In the beginning was the Word.', translation: 'KJV' },
  { id: 11, verse: 2, text: 'The same was in the beginning with God.', translation: 'KJV' },
]

describe('ScripturePane', () => {
  it('associates its reading article with the route-level chapter heading', () => {
    render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        onSelectVerse={vi.fn()}
      />,
    )

    const heading = screen.getByRole('heading', { level: 1, name: 'John 1' })
    const article = screen.getByRole('article', { name: 'John 1' })

    expect(article).toHaveAttribute('aria-labelledby', heading.id)
    expect(heading.id).not.toBe('')
    expect(within(article).getByText('Scripture Reader')).toBeInTheDocument()
    const verseList = within(article).getByRole('list')
    expect(verseList.tagName).toBe('OL')
    expect(verseList).toHaveAttribute('role', 'list')
  })

  it('names verse controls readably and selects a numeric verse', async () => {
    const user = userEvent.setup()
    const onSelectVerse = vi.fn()
    render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        onSelectVerse={onSelectVerse}
      />,
    )

    const firstVerse = screen.getByRole('button', {
      name: 'John 1 verse 1',
    })

    expect(firstVerse).toHaveTextContent('1')
    expect(firstVerse).toHaveTextContent('In the beginning was the Word.')
    expect(within(firstVerse).getByText('1')).toHaveAttribute('aria-hidden', 'true')

    await user.click(firstVerse)
    expect(onSelectVerse).toHaveBeenCalledWith(1)
  })

  it('uses native Enter and Space button activation', async () => {
    const user = userEvent.setup()
    const onSelectVerse = vi.fn()
    render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        onSelectVerse={onSelectVerse}
      />,
    )

    const firstVerse = screen.getByRole('button', { name: 'John 1 verse 1' })
    firstVerse.focus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')

    expect(onSelectVerse).toHaveBeenNthCalledWith(1, 1)
    expect(onSelectVerse).toHaveBeenNthCalledWith(2, 1)
  })

  it('exposes the selected verse as a pressed toggle', () => {
    render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        selectedVerse={2}
        onSelectVerse={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'John 1 verse 1' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByRole('button', { name: 'John 1 verse 2' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('keeps valid duplicate rows in source order and ignores malformed content', () => {
    const { container } = render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={[
          null,
          { verse: 0, text: 'Zero' },
          { verse: 1, text: '  First rendering.  ', translation: 'KJV' },
          { verse: 1, text: 'Second rendering.', translation: 'NRSV' },
          { verse: 2, text: '' },
          { verse: 3, text: { content: 'Object text' } },
          { verse: 4.5, text: 'Fractional verse' },
          { verse: '5', text: 'String verse' },
          { verse: 6, text: '   ' },
        ]}
        onSelectVerse={vi.fn()}
      />,
    )

    const controls = screen.getAllByRole('button')
    expect(controls).toHaveLength(2)
    expect(controls.map((control) => control.textContent)).toEqual([
      '1First rendering.',
      '1Second rendering.',
    ])
    expect(container).not.toHaveTextContent('[object Object]')
  })

  it('keeps verse controls mounted when earlier source rows are inserted', () => {
    const onSelectVerse = vi.fn()
    const { rerender } = render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        onSelectVerse={onSelectVerse}
      />,
    )
    const originalFirstVerse = screen.getByRole('button', { name: 'John 1 verse 1' })

    rerender(
      <ScripturePane
        book="John"
        chapter={1}
        verses={[
          { id: 9, verse: 3, text: 'A newly inserted source row.' },
          ...verses,
        ]}
        onSelectVerse={onSelectVerse}
      />,
    )

    expect(screen.getByRole('button', { name: 'John 1 verse 1' })).toBe(
      originalFirstVerse,
    )
  })

  it.each([
    ['undefined', undefined],
    ['a non-array value', { verse: 1, text: 'Not a row collection' }],
  ])('renders no verse controls or status message for %s verses', (_, value) => {
    render(<ScripturePane book="Obadiah" chapter={2} verses={value} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('article')).not.toHaveTextContent(/no text|empty/i)
  })

  it('keeps verse controls safely readable when selection is unavailable', async () => {
    const user = userEvent.setup()
    render(<ScripturePane book="John" chapter={1} verses={verses} />)

    const firstVerse = screen.getByRole('button', { name: 'John 1 verse 1' })
    expect(firstVerse).toHaveAttribute('aria-disabled', 'true')

    firstVerse.focus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')
    expect(firstVerse).toHaveFocus()
  })

  it('creates unique heading references for simultaneous panes', () => {
    render(
      <>
        <ScripturePane book="John" chapter={1} verses={[]} />
        <ScripturePane book="John" chapter={1} verses={[]} />
      </>,
    )

    const articles = screen.getAllByRole('article', { name: 'John 1' })
    const headingIds = articles.map((article) => article.getAttribute('aria-labelledby'))

    expect(new Set(headingIds)).toHaveProperty('size', 2)
    headingIds.forEach((headingId) => {
      expect(document.getElementById(headingId)).toBeInstanceOf(HTMLHeadingElement)
    })
  })
})

describe('ScripturePane reading styles', () => {
  it('defines comfortable and wide reading measures without horizontal overflow', () => {
    const pane = cssDeclarations('.scripture-pane')
    const widePane = cssDeclarations('.reader-width-wide .scripture-pane')
    const list = cssDeclarations('.scripture-pane__verses')

    expect(pane['max-width']).toBe('46rem')
    expect(pane.width).toBe('100%')
    expect(pane['box-sizing']).toBe('border-box')
    expect(pane['margin-inline']).toBe('auto')
    expect(pane.padding).toContain('clamp(')
    expect(widePane['max-width']).toBe('64rem')
    expect(list['list-style']).toBe('none')
    expect(list.padding).toBe('0')
  })

  it.each([
    ['sm', '18px'],
    ['md', '21px'],
    ['lg', '24px'],
    ['xl', '27px'],
    ['xxl', '30px'],
  ])('maps %s reader text to %s', (size, pixels) => {
    const declarations = cssDeclarations(`.reader-font-${size} .scripture-pane`)

    expect(declarations['font-size']).toBe(pixels)
  })

  it('uses reading typography and spacious, visibly selected verse targets', () => {
    const pane = cssDeclarations('.scripture-pane')
    const verse = cssDeclarations('.scripture-pane__verse')
    const verseInteraction = cssDeclarations('.scripture-pane__verse:hover')
    const selected = cssDeclarations(".scripture-pane__verse[aria-pressed='true']")
    const eyebrow = cssDeclarations('.scripture-pane__eyebrow')
    const verseNumber = cssDeclarations('.scripture-pane__verse-number')

    expect(pane['font-family']).toContain('Source Serif 4')
    expect(pane['font-family']).toContain('Georgia')
    expect(pane.color).toBe('var(--reader-scripture)')
    expect(Number.parseFloat(pane['line-height'])).toBeGreaterThanOrEqual(1.7)
    expect(verse['min-height']).toBe('48px')
    expect(verse.background).toBe('transparent')
    expect(verse['overflow-wrap']).toBe('anywhere')
    expect(verseInteraction.background).toBe('var(--reader-surface)')
    expect(verseInteraction['border-color']).toBe('var(--reader-teal)')
    expect(selected.background).toBe('var(--reader-elevated)')
    expect(selected['box-shadow']).toContain('var(--reader-violet)')
    expect(Number.parseInt(selected['font-weight'], 10)).toBeGreaterThanOrEqual(600)
    expect(eyebrow.color).toBe('var(--reader-secondary)')
    expect(verseNumber.color).toBe('var(--reader-violet)')
    expect(Number.parseInt(verseNumber['font-weight'], 10)).toBeGreaterThanOrEqual(700)
  })

  it('keeps selected text and inset accent distinguishable in both themes', () => {
    const selected = cssDeclarations(".scripture-pane__verse[aria-pressed='true']")

    for (const theme of ['dark', 'light']) {
      const tokens = themeTokens(theme)
      const background = resolveToken(selected.background, tokens)
      const text = resolveToken(selected.color, tokens)
      const accentToken = selected['box-shadow'].match(/var\((--[\w-]+)\)/)?.[1]
      const accent = tokens[accentToken]

      expect(contrastRatio(text, background)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(accent, background)).toBeGreaterThanOrEqual(3)
    }
  })
})
