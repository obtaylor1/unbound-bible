import { readFileSync } from 'node:fs'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ReaderErrorBoundary from './ReaderErrorBoundary'
import ReaderStatus from './ReaderStatus'

const readerTokensCss = readFileSync(
  'src/reader/readerTokens.css',
  'utf8',
)

function cssBlocks(selector, source = readerTokensCss) {
  return [...source.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, selectorList]) => (
      selectorList
        .split(',')
        .map((item) => item.trim())
        .includes(selector)
    ))
    .map(([, , declarations]) => declarations)
}

function cssDeclarations(selector, source = readerTokensCss) {
  return Object.fromEntries(
    cssBlocks(selector, source)
      .flatMap((block) => [...block.matchAll(/^\s*([\w-]+):\s*([^;]+);/gm)])
      .map(([, property, value]) => [property, value.trim()]),
  )
}

function colorTokens(selector, source = readerTokensCss) {
  return Object.fromEntries(
    Object.entries(cssDeclarations(selector, source))
      .filter(([property, value]) => (
        property.startsWith('--') && /^#[\dA-F]{6}$/i.test(value)
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
  const lighter = Math.max(
    relativeLuminance(firstColor),
    relativeLuminance(secondColor),
  )
  const darker = Math.min(
    relativeLuminance(firstColor),
    relativeLuminance(secondColor),
  )

  return (lighter + 0.05) / (darker + 0.05)
}

describe('ReaderStatus', () => {
  it('announces the passage while it is loading', () => {
    const { container } = render(<ReaderStatus state="loading" reference="John 3" />)

    const status = screen.getByRole('status')
    expect(status).toHaveClass('reader-status', 'reader-status--loading')
    expect(status).toHaveTextContent('Loading John 3…')
    const skeleton = container.querySelector('.reader-loading-skeleton')
    expect(skeleton).toHaveAttribute('aria-hidden', 'true')
    expect(skeleton.querySelectorAll('.reader-loading-skeleton__line')).toHaveLength(4)
  })

  it('explains offline limitations without implying loaded Scripture is lost', () => {
    render(
      <ReaderStatus
        state="offline"
        reference="John 3"
        hasLoadedContent
        compact
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent(/offline/i)
    expect(screen.getByRole('status')).toHaveTextContent(/loaded Scripture remains available/i)
    expect(screen.getByRole('status')).toHaveTextContent(/online study tools may not work/i)
    expect(screen.getByRole('heading', {
      level: 2,
      name: 'You’re offline',
    })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('truthfully reports an initial offline failure and offers recovery', () => {
    const onRetry = vi.fn()
    render(
      <ReaderStatus
        state="offline"
        reference="John 3"
        onRetry={onRetry}
      />,
    )

    const status = screen.getByRole('status', {
      name: 'Scripture unavailable offline',
    })
    expect(status).toHaveTextContent(/could not load John 3 while you’re offline/i)
    expect(status).not.toHaveTextContent(/remains available/i)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('offers the Books action when no passage text is available', () => {
    const onOpenBooks = vi.fn()
    render(
      <ReaderStatus
        state="empty"
        reference="Obadiah 2"
        onOpenBooks={onOpenBooks}
      />,
    )

    const section = screen.getByRole('region', { name: /no text available/i })
    expect(section).toHaveTextContent('No text is available for Obadiah 2')
    expect(section).toHaveTextContent(/choose another book or translation/i)
    expect(screen.getByRole('heading', {
      level: 1,
      name: 'No text available',
    })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Choose another book' }))
    expect(onOpenBooks).toHaveBeenCalledOnce()
  })

  it('names a work whose English text is not yet available and offers a next step', () => {
    const onOpenBooks = vi.fn()
    render(
      <ReaderStatus
        state="unavailable"
        reference="Tegsats 1"
        workName="Tegsats"
        onOpenBooks={onOpenBooks}
      />,
    )

    expect(screen.getByRole('heading', {
      level: 1,
      name: 'English text not yet available for Tegsats',
    })).toBeInTheDocument()
    expect(screen.getByRole('region', {
      name: 'English text not yet available for Tegsats',
    })).toHaveTextContent(/choose another book/i)
    fireEvent.click(screen.getByRole('button', { name: 'Choose another book' }))
    expect(onOpenBooks).toHaveBeenCalledOnce()
  })

  it('retains the failed reference and lets the reader retry or choose a book', () => {
    const onRetry = vi.fn()
    const onOpenBooks = vi.fn()
    render(
      <ReaderStatus
        state="error"
        reference="Psalm 23"
        onRetry={onRetry}
        onOpenBooks={onOpenBooks}
      />,
    )

    const alert = screen.getByRole('alert', { name: /could not open Psalm 23/i })
    expect(alert).toHaveTextContent('Psalm 23')
    expect(alert).toHaveTextContent(/reader’s place is saved/i)
    expect(screen.getByRole('heading', {
      level: 1,
      name: 'Could not open Psalm 23',
    })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    fireEvent.click(screen.getByRole('button', { name: 'Choose another book' }))
    expect(onRetry).toHaveBeenCalledOnce()
    expect(onOpenBooks).toHaveBeenCalledOnce()
  })

  it.each(['ready', 'unexpected'])('renders nothing for the %s state', (state) => {
    const { container } = render(<ReaderStatus state={state} reference="John 3" />)

    expect(container).toBeEmptyDOMElement()
  })

  it('gives simultaneous recovery states unique accessible heading references', () => {
    render(
      <>
        <ReaderStatus state="empty" reference="Obadiah 2" />
        <ReaderStatus state="empty" reference="Obadiah 3" />
        <ReaderStatus state="error" reference="Psalm 23" />
        <ReaderStatus state="error" reference="Psalm 24" />
        <ReaderStatus state="offline" reference="John 3" />
        <ReaderStatus state="offline" reference="John 4" />
      </>,
    )

    const surfaces = [
      ...screen.getAllByRole('region', { name: 'No text available' }),
      ...screen.getAllByRole('alert'),
      ...screen.getAllByRole('status', { name: 'Scripture unavailable offline' }),
    ]
    const headingIds = surfaces.map((surface) => surface.getAttribute('aria-labelledby'))

    expect(new Set(headingIds)).toHaveProperty('size', surfaces.length)
    headingIds.forEach((headingId) => {
      expect(document.getElementById(headingId)).toBeInstanceOf(HTMLHeadingElement)
    })
  })
})

describe('reader action colors', () => {
  it('honors later token declarations for a repeated selector', () => {
    const repeatedSelectorCss = `
      .token-fixture { --fixture-color: #000000; }
      .token-fixture { --fixture-color: #FFFFFF; }
    `

    expect(colorTokens('.token-fixture', repeatedSelectorCss)).toEqual({
      '--fixture-color': '#FFFFFF',
    })
  })

  it('keeps the semantic primary foreground at WCAG AA contrast in both themes', () => {
    const darkTokens = colorTokens('.scripture-reader')
    const lightOverrides = colorTokens("[data-reader-theme='light'] .scripture-reader")

    for (const themeTokens of [
      darkTokens,
      { ...darkTokens, ...lightOverrides },
    ]) {
      expect(themeTokens['--reader-on-primary']).toMatch(/^#[\dA-F]{6}$/i)
      expect(
        contrastRatio(
          themeTokens['--reader-on-primary'],
          themeTokens['--reader-primary'],
        ),
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('uses the semantic primary foreground on reader action controls', () => {
    for (const selector of [
      '.reader-status button',
      '.reader-fatal-error button',
    ]) {
      const declarations = cssDeclarations(selector)
      expect(declarations.color).toBe('var(--reader-on-primary)')
      expect(declarations.background).toBe('var(--reader-primary)')
    }
  })

  it('keeps secondary actions visibly bounded and readable in both themes', () => {
    const darkTokens = colorTokens('.scripture-reader')
    const lightOverrides = colorTokens("[data-reader-theme='light'] .scripture-reader")

    for (const themeTokens of [
      darkTokens,
      { ...darkTokens, ...lightOverrides },
    ]) {
      for (const token of [
        '--reader-secondary-control-border',
        '--reader-secondary-control-background',
        '--reader-on-secondary-control',
      ]) {
        expect(themeTokens[token]).toBeDefined()
      }
      expect(
        contrastRatio(
          themeTokens['--reader-secondary-control-border'],
          themeTokens['--reader-surface'],
        ),
      ).toBeGreaterThanOrEqual(3)
      expect(
        contrastRatio(
          themeTokens['--reader-secondary-control-border'],
          themeTokens['--reader-secondary-control-background'],
        ),
      ).toBeGreaterThanOrEqual(3)
      expect(
        contrastRatio(
          themeTokens['--reader-on-secondary-control'],
          themeTokens['--reader-secondary-control-background'],
        ),
      ).toBeGreaterThanOrEqual(4.5)
    }

    for (const selector of [
      '.reader-status__actions button + button',
      '.reader-fatal-error a',
    ]) {
      const declarations = cssDeclarations(selector)
      expect(declarations.color).toBe('var(--reader-on-secondary-control)')
      expect(declarations.background).toBe('var(--reader-secondary-control-background)')
      expect(declarations['border-color']).toBe('var(--reader-secondary-control-border)')
    }
  })
})

function BrokenReader() {
  throw new Error('Reader render failed')
}

function NullThrowingReader() {
  throw null
}

describe('ReaderErrorBoundary', () => {
  it('renders its children while the reader is healthy', () => {
    render(
      <ReaderErrorBoundary resetKey="John 3">
        <main id="main-content">John 3 passage text</main>
      </ReaderErrorBoundary>,
    )

    expect(screen.getByText('John 3 passage text')).toBeInTheDocument()
    expect(screen.getAllByRole('main')).toHaveLength(1)
  })

  it('shows a route-level fallback with reload and home actions', () => {
    const onReload = vi.fn()

    render(
      <ReaderErrorBoundary resetKey="John 3" onReload={onReload}>
        <BrokenReader />
      </ReaderErrorBoundary>,
      { onCaughtError: () => {} },
    )

    const alert = screen.getByRole('alert', {
      name: 'The Scripture Reader could not open',
    })
    expect(alert).toHaveClass('scripture-reader', 'reader-fatal-error')
    expect(alert).toHaveTextContent(/saved notes and preferences were unchanged/i)
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')

    fireEvent.click(screen.getByRole('button', { name: 'Reload the reader' }))
    expect(onReload).toHaveBeenCalledOnce()
    expect(screen.getByRole('link', { name: 'Return home' })).toHaveAttribute('href', '#home')
  })

  it('shows its fallback when a descendant throws a falsy value', () => {
    render(
      <ReaderErrorBoundary resetKey="John 3">
        <NullThrowingReader />
      </ReaderErrorBoundary>,
      { onCaughtError: () => {} },
    )

    expect(screen.getByRole('alert', {
      name: 'The Scripture Reader could not open',
    })).toBeInTheDocument()
  })

  it('gives simultaneous boundary fallbacks unique accessible heading references', () => {
    render(
      <>
        <ReaderErrorBoundary resetKey="John 3">
          <BrokenReader />
        </ReaderErrorBoundary>
        <ReaderErrorBoundary resetKey="Psalm 23">
          <BrokenReader />
        </ReaderErrorBoundary>
      </>,
      { onCaughtError: () => {} },
    )

    const alerts = screen.getAllByRole('alert', {
      name: 'The Scripture Reader could not open',
    })
    const headingIds = alerts.map((alert) => alert.getAttribute('aria-labelledby'))

    expect(new Set(headingIds)).toHaveProperty('size', alerts.length)
    headingIds.forEach((headingId) => {
      expect(document.getElementById(headingId)).toBeInstanceOf(HTMLHeadingElement)
    })
  })

  it('recovers when the passage reset key changes', () => {
    const { rerender } = render(
      <ReaderErrorBoundary resetKey="John 3">
        <BrokenReader />
      </ReaderErrorBoundary>,
      { onCaughtError: () => {} },
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()

    rerender(
      <ReaderErrorBoundary resetKey="John 4">
        <p>John 4 passage text</p>
      </ReaderErrorBoundary>,
    )

    expect(screen.getByText('John 4 passage text')).toBeInTheDocument()
  })
})
