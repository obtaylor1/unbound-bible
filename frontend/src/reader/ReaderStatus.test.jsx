import { readFileSync } from 'node:fs'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ReaderErrorBoundary from './ReaderErrorBoundary'
import ReaderStatus from './ReaderStatus'

const readerTokensCss = readFileSync(
  'src/reader/readerTokens.css',
  'utf8',
)

function cssBlock(selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return readerTokensCss.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`))?.[1] ?? ''
}

function colorTokens(selector) {
  return Object.fromEntries(
    [...cssBlock(selector).matchAll(/(--[\w-]+):\s*(#[\dA-F]{6})/gi)]
      .map(([, name, value]) => [name, value]),
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
    render(<ReaderStatus state="loading" reference="John 3" />)

    const status = screen.getByRole('status')
    expect(status).toHaveClass('reader-status', 'reader-status--loading')
    expect(status).toHaveTextContent('Loading John 3…')
  })

  it('explains offline limitations without implying loaded Scripture is lost', () => {
    render(<ReaderStatus state="offline" reference="John 3" />)

    expect(screen.getByRole('status')).toHaveTextContent(/offline/i)
    expect(screen.getByRole('status')).toHaveTextContent(/already-loaded Scripture remains available/i)
    expect(screen.getByRole('status')).toHaveTextContent(/online study tools may not work/i)
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

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    fireEvent.click(screen.getByRole('button', { name: 'Choose another book' }))
    expect(onRetry).toHaveBeenCalledOnce()
    expect(onOpenBooks).toHaveBeenCalledOnce()
  })

  it.each(['ready', 'unexpected'])('renders nothing for the %s state', (state) => {
    const { container } = render(<ReaderStatus state={state} reference="John 3" />)

    expect(container).toBeEmptyDOMElement()
  })
})

describe('reader action colors', () => {
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
    const actionRule = cssBlock([
      '.reader-status button',
      '.reader-fatal-error button',
      '.reader-fatal-error a',
    ].join(',\n'))

    expect(actionRule).toMatch(/color:\s*var\(--reader-on-primary\)/)
    expect(actionRule).toMatch(/background:\s*var\(--reader-primary\)/)
  })
})

function BrokenReader() {
  throw new Error('Reader render failed')
}

describe('ReaderErrorBoundary', () => {
  it('renders its children while the reader is healthy', () => {
    render(
      <ReaderErrorBoundary resetKey="John 3">
        <p>John 3 passage text</p>
      </ReaderErrorBoundary>,
    )

    expect(screen.getByText('John 3 passage text')).toBeInTheDocument()
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

    fireEvent.click(screen.getByRole('button', { name: 'Reload the reader' }))
    expect(onReload).toHaveBeenCalledOnce()
    expect(screen.getByRole('link', { name: 'Return home' })).toHaveAttribute('href', '#home')
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
