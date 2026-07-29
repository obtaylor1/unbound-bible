import { readFileSync } from 'node:fs'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/authContext'
import { ReaderPreferencesProvider } from './ReaderPreferences'
import PassageToolbar from './PassageToolbar'
import ReaderHeader from './ReaderHeader'

const readerTokensCss = readFileSync('src/reader/readerTokens.css', 'utf8')

function cssDeclarations(selector) {
  return Object.fromEntries(
    [...readerTokensCss.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
      .filter(([, selectorList]) => (
        selectorList
          .split(',')
          .map((item) => item.trim())
          .includes(selector)
      ))
      .flatMap(([, , declarations]) => (
        [...declarations.matchAll(/^\s*([\w-]+):\s*([^;]+);/gm)]
      ))
      .map(([, property, value]) => [property, value.trim()]),
  )
}

function renderHeader(authValue = { user: null, status: 'anonymous' }, props = {}) {
  const callbacks = {
    onHome: vi.fn(),
    onOpenBooks: vi.fn(),
    onOpenStudyTools: vi.fn(),
    ...props,
  }

  render(
    <AuthContext.Provider value={authValue}>
      <ReaderHeader {...callbacks} />
    </AuthContext.Provider>,
  )

  return callbacks
}

function renderToolbar(props = {}) {
  const callbacks = {
    reference: 'John 3',
    translation: 'NRSV',
    translations: [
      { code: 'NRSV', name: 'New Revised Standard Version' },
      { code: 'KJV', name: 'King James Version' },
    ],
    onTranslationChange: vi.fn(),
    canGoPrevious: true,
    canGoNext: true,
    onPrevious: vi.fn(),
    onNext: vi.fn(),
    ...props,
  }

  render(
    <ReaderPreferencesProvider>
      <PassageToolbar {...callbacks} />
    </ReaderPreferencesProvider>,
  )

  return callbacks
}

beforeEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.readerTheme
})

describe('ReaderHeader', () => {
  it('exposes the reader brand and word-labelled navigation actions', () => {
    const callbacks = renderHeader()
    const header = screen.getByRole('banner')
    const actions = within(header).getByRole('navigation', { name: 'Scripture reader actions' })

    fireEvent.click(within(header).getByRole('button', { name: 'The Unbound Bible home' }))
    fireEvent.click(within(actions).getByRole('button', { name: 'Choose a book' }))
    fireEvent.click(within(actions).getByRole('button', { name: 'Open study tools' }))

    expect(callbacks.onHome).toHaveBeenCalledOnce()
    expect(callbacks.onOpenBooks).toHaveBeenCalledOnce()
    expect(callbacks.onOpenStudyTools).toHaveBeenCalledOnce()
  })

  it('opens and closes the existing authentication dialog for signed-out readers', () => {
    renderHeader()

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('dialog', { name: 'Welcome back' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('uses the existing account menu for signed-in readers', () => {
    renderHeader({
      user: { username: 'Miriam', email: 'miriam@example.com' },
      status: 'authenticated',
      logout: vi.fn(),
    })

    const accountButton = screen.getByRole('button', { name: 'Miriam' })
    expect(accountButton).toHaveAttribute('aria-expanded', 'false')
    expect(within(accountButton).getByText('Miriam')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Sign in' })).not.toBeInTheDocument()

    fireEvent.click(accountButton)
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('keeps mobile actions wrapping so the account popover is not clipped', () => {
    const mobileActions = cssDeclarations('.reader-header__actions')

    expect(mobileActions['flex-wrap']).toBe('wrap')
    expect(mobileActions['overflow-x']).toBeUndefined()
  })

  it('overrides narrow navigation styles for the reader account trigger and username', () => {
    const accountTrigger = cssDeclarations('.reader-header__actions .nav-signin')
    const username = cssDeclarations(
      '.reader-header__actions .nav-signin span:last-child',
    )

    expect(accountTrigger['min-width']).toBe('48px')
    expect(accountTrigger['min-height']).toBe('48px')
    expect(accountTrigger.width).toBe('auto')
    expect(username.position).toBe('static')
    expect(username.width).toBe('auto')
    expect(username.height).toBe('auto')
    expect(username.overflow).toBe('visible')
    expect(username.clip).toBe('auto')
  })
})

describe('PassageToolbar', () => {
  it('announces the reference and changes translation by code', () => {
    const callbacks = renderToolbar()
    const toolbar = screen.getByRole('toolbar', { name: 'Passage controls' })
    const reference = within(toolbar).getByText('John 3')
    const translation = within(toolbar).getByRole('combobox', { name: 'Change translation' })

    expect(reference).toHaveAttribute('aria-live', 'polite')
    expect(translation).toHaveValue('NRSV')

    fireEvent.change(translation, { target: { value: 'KJV' } })
    expect(callbacks.onTranslationChange).toHaveBeenCalledWith('KJV')
  })

  it('calls both enabled chapter controls', () => {
    const callbacks = renderToolbar()
    const previous = screen.getByRole('button', { name: 'Previous chapter' })
    const next = screen.getByRole('button', { name: 'Next chapter' })

    fireEvent.click(previous)
    fireEvent.click(next)

    expect(callbacks.onPrevious).toHaveBeenCalledOnce()
    expect(callbacks.onNext).toHaveBeenCalledOnce()
  })

  it('preserves the disabled previous chapter state', () => {
    const callbacks = renderToolbar({ canGoPrevious: false })
    const previous = screen.getByRole('button', { name: 'Previous chapter' })
    const next = screen.getByRole('button', { name: 'Next chapter' })

    expect(previous).toBeDisabled()
    expect(next).toBeEnabled()

    fireEvent.click(previous)
    fireEvent.click(next)

    expect(callbacks.onPrevious).not.toHaveBeenCalled()
    expect(callbacks.onNext).toHaveBeenCalledOnce()
  })

  it('supports disabling the next chapter control', () => {
    renderToolbar({ canGoNext: false })

    expect(screen.getByRole('button', { name: 'Previous chapter' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Next chapter' })).toBeDisabled()
  })

  it('cycles through every plain-language text size and wraps to small', () => {
    renderToolbar()

    const expectedSizes = ['Medium', 'Large', 'Extra large', 'Extra extra large', 'Small']
    for (const size of expectedSizes) {
      expect(screen.getByText(`Current size: ${size}`)).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: /Change text size/ }))
    }

    expect(screen.getByText('Current size: Medium')).toBeInTheDocument()
  })

  it('clearly names and toggles the reader theme action', () => {
    renderToolbar()

    fireEvent.click(screen.getByRole('button', { name: 'Use light mode' }))
    expect(screen.getByRole('button', { name: 'Use dark mode' })).toBeInTheDocument()
    expect(document.documentElement.dataset.readerTheme).toBe('light')
  })
})
