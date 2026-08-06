import { readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterAll, describe, expect, it, vi } from 'vitest'
import ScripturePane from './ScripturePane'

const readerTokensCss = readFileSync('src/reader/readerTokens.css', 'utf8')
const readerStyle = document.createElement('style')
readerStyle.textContent = readerTokensCss
document.head.append(readerStyle)

function cssDeclarations(selector, {
  mediaCondition,
  sheet = readerStyle.sheet,
} = {}) {
  const matchingRules = []

  function visitRules(rules, mediaStack = []) {
    for (const rule of rules) {
      if ('selectorText' in rule) {
        const selectors = rule.selectorText
          .split(',')
          .map((item) => item.trim())

        const mediaMatches = mediaCondition
          ? mediaStack.includes(mediaCondition)
          : mediaStack.length === 0

        if (selectors.includes(selector) && mediaMatches) {
          matchingRules.push(rule)
        }
      }

      if ('cssRules' in rule) {
        const nextMediaStack = 'conditionText' in rule
          ? [...mediaStack, rule.conditionText]
          : mediaStack
        visitRules(rule.cssRules, nextMediaStack)
      }
    }
  }

  visitRules(sheet.cssRules)

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

  it('shows the selected content source near the passage and updates without stale details', () => {
    const { rerender } = render(
      <ScripturePane
        book="Genesis"
        chapter={1}
        verses={verses}
        source={{ sourceLabel: 'World Messianic Bible', verificationStatus: 'provisional' }}
      />,
    )
    expect(screen.getByText('World Messianic Bible')).toBeVisible()

    rerender(
      <ScripturePane
        book="Matthew"
        chapter={1}
        verses={verses}
        source={{ sourceLabel: 'Murdock Peshitta', verificationStatus: 'provisional' }}
      />,
    )

    expect(screen.getByText('Murdock Peshitta')).toBeVisible()
    expect(screen.queryByText('World Messianic Bible')).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Text source' }).compareDocumentPosition(
      screen.getByRole('list'),
    ) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
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
      name: /^John 1 verse 1\b/,
    })

    expect(firstVerse).toHaveTextContent('1')
    expect(firstVerse).toHaveTextContent('In the beginning was the Word.')
    expect(firstVerse).toHaveAccessibleName(
      'John 1 verse 1 In the beginning was the Word.',
    )
    expect(firstVerse).not.toHaveAttribute('aria-label')
    const labelIds = firstVerse.getAttribute('aria-labelledby').split(' ')
    expect(labelIds).toHaveLength(2)
    expect(document.getElementById(labelIds[0])).toHaveTextContent('John 1 verse 1')
    expect(document.getElementById(labelIds[1])).toHaveTextContent(
      'In the beginning was the Word.',
    )
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

    const firstVerse = screen.getByRole('button', { name: /^John 1 verse 1\b/ })
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

    expect(screen.getByRole('button', { name: /^John 1 verse 1\b/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByRole('button', { name: /^John 1 verse 2\b/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('preserves the native verse control and its focus when selection changes', () => {
    const onSelectVerse = vi.fn()
    const { rerender } = render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        selectedVerse={1}
        onSelectVerse={onSelectVerse}
      />,
    )
    const secondVerse = screen.getByRole('button', { name: /^John 1 verse 2\b/ })
    secondVerse.focus()

    rerender(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        selectedVerse={2}
        onSelectVerse={onSelectVerse}
      />,
    )

    expect(screen.getByRole('button', { name: /^John 1 verse 2\b/ })).toBe(secondVerse)
    expect(secondVerse).toHaveFocus()
    expect(secondVerse).toHaveAttribute('type', 'button')
    expect(secondVerse).toHaveAttribute('aria-pressed', 'true')
    expect(within(secondVerse).getByText('The same was in the beginning with God.')).toBeInTheDocument()
  })

  it('politely announces only verse changes made while Commentary is active', () => {
    const { rerender } = render(
      <ScripturePane
        book="Genesis"
        chapter={1}
        verses={verses}
        selectedVerse={1}
        commentaryActive={false}
        onSelectVerse={vi.fn()}
      />,
    )
    expect(screen.queryByRole('status', { name: 'Commentary selection status' })).not.toBeInTheDocument()

    rerender(
      <ScripturePane
        book="Genesis"
        chapter={1}
        verses={verses}
        selectedVerse={1}
        commentaryActive
        onSelectVerse={vi.fn()}
      />,
    )
    const status = screen.getByRole('status', { name: 'Commentary selection status' })
    expect(status).toBeEmptyDOMElement()

    rerender(
      <ScripturePane
        book="Genesis"
        chapter={1}
        verses={[...verses]}
        selectedVerse={2}
        commentaryActive
        onSelectVerse={vi.fn()}
      />,
    )
    expect(status).toHaveTextContent('Commentary selected for Genesis 1 verse 2')

    rerender(
      <ScripturePane
        book="Genesis"
        chapter={1}
        verses={[...verses]}
        selectedVerse={2}
        commentaryActive
        onSelectVerse={vi.fn()}
      />,
    )
    expect(status).toHaveTextContent('Commentary selected for Genesis 1 verse 2')
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
    expect(controls.map((control) => (
      within(control).getByText(/rendering\.$/).textContent
    ))).toEqual([
      'First rendering.',
      'Second rendering.',
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
    const originalFirstVerse = screen.getByRole('button', {
      name: /^John 1 verse 1\b/,
    })

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

    expect(screen.getByRole('button', { name: /^John 1 verse 1\b/ })).toBe(
      originalFirstVerse,
    )
  })

  it('retains a focused verse control when text changes for the same source id', () => {
    const onSelectVerse = vi.fn()
    const { rerender } = render(
      <ScripturePane
        book="John"
        chapter={1}
        verses={verses}
        onSelectVerse={onSelectVerse}
      />,
    )
    const originalFirstVerse = screen.getByRole('button', {
      name: /^John 1 verse 1\b/,
    })
    originalFirstVerse.focus()

    rerender(
      <ScripturePane
        book="John"
        chapter={1}
        verses={[
          { ...verses[0], text: 'The Word was present at creation.' },
          verses[1],
        ]}
        onSelectVerse={onSelectVerse}
      />,
    )

    const updatedFirstVerse = screen.getByRole('button', {
      name: 'John 1 verse 1 The Word was present at creation.',
    })
    expect(updatedFirstVerse).toBe(originalFirstVerse)
    expect(updatedFirstVerse).toHaveFocus()
  })

  it.each([
    ['undefined', undefined],
    ['a non-array value', { verse: 1, text: 'Not a row collection' }],
  ])('renders no verse controls or status message for %s verses', (_, value) => {
    render(<ScripturePane book="Obadiah" chapter={2} verses={value} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('article')).not.toHaveTextContent(/no text|empty/i)
  })

  it('renders readable noninteractive verses when selection is unavailable', () => {
    render(<ScripturePane book="John" chapter={1} verses={verses} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    const firstVerse = screen.getByText('In the beginning was the Word.').closest('div')
    expect(firstVerse).toHaveClass(
      'scripture-pane__verse',
      'scripture-pane__verse--static',
    )
    expect(firstVerse).not.toHaveAttribute('tabindex')
    expect(firstVerse).not.toHaveAttribute('aria-pressed')
    expect(firstVerse).toHaveTextContent('John 1 verse 1')
  })

  it('creates unique heading references for simultaneous panes', () => {
    render(
      <>
        <ScripturePane
          book="John"
          chapter={1}
          verses={[verses[0]]}
          onSelectVerse={vi.fn()}
        />
        <ScripturePane
          book="John"
          chapter={1}
          verses={[verses[0]]}
          onSelectVerse={vi.fn()}
        />
      </>,
    )

    const articles = screen.getAllByRole('article', { name: 'John 1' })
    const headingIds = articles.map((article) => article.getAttribute('aria-labelledby'))

    expect(new Set(headingIds)).toHaveProperty('size', 2)
    headingIds.forEach((headingId) => {
      expect(document.getElementById(headingId)).toBeInstanceOf(HTMLHeadingElement)
    })

    const verseLabelIds = screen.getAllByRole('button')
      .flatMap((button) => button.getAttribute('aria-labelledby').split(' '))
    expect(new Set(verseLabelIds)).toHaveProperty('size', verseLabelIds.length)
  })
})

describe('ScripturePane reading styles', () => {
  it('ignores inactive media declarations unless their condition is requested', () => {
    const mediaStyle = document.createElement('style')
    mediaStyle.textContent = `
      .media-fixture { width: 46rem; }
      @media (max-width: 1px) {
        .media-fixture { width: 12rem; }
      }
    `
    document.head.append(mediaStyle)

    expect(cssDeclarations('.media-fixture', {
      sheet: mediaStyle.sheet,
    }).width).toBe('46rem')
    expect(cssDeclarations('.media-fixture', {
      mediaCondition: '(max-width: 1px)',
      sheet: mediaStyle.sheet,
    }).width).toBe('12rem')

    mediaStyle.remove()
  })

  it('declares comfortable and wide reading-measure contracts', () => {
    // Computed viewport geometry is exercised with a real layout engine in Task 9.
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
    const verseInteraction = cssDeclarations('button.scripture-pane__verse:hover')
    const staticVerse = cssDeclarations('.scripture-pane__verse--static')
    const selected = cssDeclarations(".scripture-pane__verse[aria-pressed='true']")
    const eyebrow = cssDeclarations('.scripture-pane__eyebrow')
    const verseNumber = cssDeclarations('.scripture-pane__verse-number')
    const hiddenReference = cssDeclarations('.scripture-pane__verse-reference')

    expect(pane['font-family']).toContain('Source Serif 4')
    expect(pane['font-family']).toContain('Georgia')
    expect(pane.color).toBe('var(--reader-scripture)')
    expect(Number.parseFloat(pane['line-height'])).toBeGreaterThanOrEqual(1.7)
    expect(verse['min-height']).toBe('48px')
    expect(verse.background).toBe('transparent')
    expect(verse['overflow-wrap']).toBe('anywhere')
    expect(verseInteraction.background).toBe('var(--reader-surface)')
    expect(verseInteraction['border-color']).toBe('var(--reader-teal)')
    expect(staticVerse.cursor).toBe('default')
    expect(selected.background).toBe('var(--reader-elevated)')
    expect(selected['box-shadow']).toContain('var(--reader-violet)')
    expect(Number.parseInt(selected['font-weight'], 10)).toBeGreaterThanOrEqual(600)
    expect(eyebrow.color).toBe('var(--reader-secondary)')
    expect(verseNumber.color).toBe('var(--reader-violet)')
    expect(Number.parseInt(verseNumber['font-weight'], 10)).toBeGreaterThanOrEqual(700)
    expect(hiddenReference.position).toBe('absolute')
    expect(hiddenReference.width).toBe('1px')
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
