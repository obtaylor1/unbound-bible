import { readFileSync } from 'node:fs'
import { useState } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/authContext'
import { ReaderPreferencesProvider } from './ReaderPreferences'
import PassageToolbar from './PassageToolbar'
import ReaderHeader from './ReaderHeader'

const readerTokensCss = readFileSync('src/reader/readerTokens.css', 'utf8')
const MOBILE_READER_MEDIA = '(max-width: 767px)'
const INTERMEDIATE_READER_MEDIA = '(max-width: 1180px)'

const readerStyle = document.createElement('style')
readerStyle.textContent = readerTokensCss
document.head.append(readerStyle)

function cssDeclarations(selector, mediaCondition) {
  const matchingRules = []

  function visitRules(rules, mediaStack = []) {
    for (const rule of rules) {
      if ('selectorText' in rule) {
        const selectors = rule.selectorText
          .split(',')
          .map((item) => item.trim())

        if (
          selectors.includes(selector)
          && (!mediaCondition || mediaStack.includes(mediaCondition))
        ) {
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

function AuthenticatingHeader({ onLogin }) {
  const [user, setUser] = useState(null)

  const login = async (payload) => {
    onLogin(payload)
    const authenticatedUser = {
      username: 'Miriam',
      email: payload.email,
    }
    setUser(authenticatedUser)
    return authenticatedUser
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        status: user ? 'authenticated' : 'anonymous',
        login,
        register: vi.fn(),
        logout: vi.fn(),
      }}
    >
      <ReaderHeader
        onHome={vi.fn()}
        onOpenBooks={vi.fn()}
        onOpenStudyTools={vi.fn()}
      />
    </AuthContext.Provider>
  )
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
    onOpenBooks: vi.fn(),
    onOpenStudyTools: vi.fn(),
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

  it('focuses the sign-in form, closes with Escape, and restores the trigger', async () => {
    const user = userEvent.setup()
    renderHeader()
    const trigger = screen.getByRole('button', { name: 'Sign in' })

    await user.click(trigger)
    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('wraps forward and backward Tab focus within the authentication dialog', async () => {
    const user = userEvent.setup()
    renderHeader()

    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    const close = screen.getByRole('button', { name: 'Close' })
    const switchMode = screen.getByRole('button', {
      name: 'New here? Create an account',
    })

    switchMode.focus()
    await user.tab()
    expect(close).toHaveFocus()

    close.focus()
    await user.tab({ shift: true })
    expect(switchMode).toHaveFocus()
  })

  it('restores focus when the dialog close control is used', async () => {
    const user = userEvent.setup()
    renderHeader()
    const trigger = screen.getByRole('button', { name: 'Sign in' })

    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: 'Close' }))

    expect(trigger).toHaveFocus()
  })

  it('moves focus to the account trigger after successful sign in', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    render(<AuthenticatingHeader onLogin={onLogin} />)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    const dialog = screen.getByRole('dialog', { name: 'Welcome back' })
    await user.type(within(dialog).getByRole('textbox', { name: 'Email' }), 'miriam@example.com')
    await user.type(within(dialog).getByLabelText('Password'), 'a-secure-password')
    await user.click(within(dialog).getByRole('button', { name: 'Sign in' }))

    const accountTrigger = await screen.findByRole('button', { name: 'Miriam' })
    expect(onLogin).toHaveBeenCalledWith({
      email: 'miriam@example.com',
      password: 'a-secure-password',
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(accountTrigger).toHaveFocus()
  })

  it('reopens in sign-in mode after closing registration mode', async () => {
    const user = userEvent.setup()
    renderHeader()

    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await user.click(screen.getByRole('button', {
      name: 'New here? Create an account',
    }))
    expect(screen.getByRole('dialog', { name: 'Create your account' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Close' }))
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByRole('dialog', { name: 'Welcome back' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Create your account' })).not.toBeInTheDocument()
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
    const mobileActions = cssDeclarations(
      '.reader-header__actions',
      MOBILE_READER_MEDIA,
    )

    expect(mobileActions['flex-wrap']).toBe('wrap')
    expect(mobileActions['overflow-x']).toBeUndefined()
  })

  it('overrides narrow navigation styles for the reader account trigger and username', () => {
    const accountTrigger = cssDeclarations(
      '.reader-header__actions .nav-signin',
      MOBILE_READER_MEDIA,
    )
    const username = cssDeclarations(
      '.reader-header__actions .nav-signin span:last-child',
      MOBILE_READER_MEDIA,
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

  it('anchors the mobile account menu within the viewport when actions wrap', () => {
    const accountWrapper = cssDeclarations(
      '.reader-header__actions .account-menu',
      MOBILE_READER_MEDIA,
    )
    const accountPopover = cssDeclarations(
      '.reader-header__actions .account-popover',
    )

    expect(accountWrapper['margin-inline-start']).toBe('auto')
    expect(accountPopover.right).toBe('0')
    expect(accountPopover.width).toBe('min(15rem, calc(100vw - 2rem))')
  })

  it.each(['dark', 'light'])(
    'uses readable authentication colors and 48px actions in %s mode',
    (theme) => {
      const tokens = themeTokens(theme)
      const dialog = cssDeclarations('.scripture-reader .auth-dialog')
      const label = cssDeclarations('.scripture-reader .auth-dialog label')
      const input = cssDeclarations('.scripture-reader .auth-dialog input')
      const placeholder = cssDeclarations(
        '.scripture-reader .auth-dialog input::placeholder',
      )
      const close = cssDeclarations('.scripture-reader .auth-close')
      const switchMode = cssDeclarations('.scripture-reader .auth-switch')
      const error = cssDeclarations('.scripture-reader .auth-error')
      const primary = cssDeclarations(
        '.scripture-reader .auth-dialog .primary-button',
      )

      const dialogBackground = resolveToken(dialog.background, tokens)
      const inputBackground = resolveToken(input.background, tokens)
      const readablePairs = [
        [resolveToken(dialog.color, tokens), dialogBackground],
        [resolveToken(label.color, tokens), dialogBackground],
        [resolveToken(input.color, tokens), inputBackground],
        [resolveToken(placeholder.color, tokens), inputBackground],
        [resolveToken(close.color, tokens), dialogBackground],
        [resolveToken(switchMode.color, tokens), dialogBackground],
        [resolveToken(error.color, tokens), dialogBackground],
        [
          resolveToken(primary.color, tokens),
          resolveToken(primary.background, tokens),
        ],
      ]

      for (const [foreground, background] of readablePairs) {
        expect(foreground).toMatch(/^#[\dA-F]{6}$/i)
        expect(background).toMatch(/^#[\dA-F]{6}$/i)
        expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5)
      }

      expect(close['min-width']).toBe('48px')
      expect(close['min-height']).toBe('48px')
      expect(switchMode['min-height']).toBe('48px')
    },
  )
})

describe('PassageToolbar', () => {
  it('opens reader destinations from the passage toolbar', () => {
    const callbacks = renderToolbar()
    const controls = screen.getByRole('region', { name: 'Passage controls' })
    const actions = within(controls).getByRole('group', { name: 'Reader actions' })

    fireEvent.click(within(actions).getByRole('button', { name: 'Choose a book' }))
    fireEvent.click(within(actions).getByRole('button', { name: 'Open study tools' }))

    expect(callbacks.onOpenBooks).toHaveBeenCalledOnce()
    expect(callbacks.onOpenStudyTools).toHaveBeenCalledOnce()
  })

  it('keeps toolbar groups horizontally scrollable at intermediate widths', () => {
    const toolbar = cssDeclarations('.passage-toolbar', INTERMEDIATE_READER_MEDIA)
    const chapterControls = cssDeclarations(
      '.passage-toolbar__chapter-controls',
      INTERMEDIATE_READER_MEDIA,
    )
    const settings = cssDeclarations(
      '.passage-toolbar__settings',
      INTERMEDIATE_READER_MEDIA,
    )

    expect(toolbar.display).toBe('flex')
    expect(toolbar['overflow-x']).toBe('auto')
    expect(chapterControls.flex).toBe('0 0 auto')
    expect(settings.flex).toBe('0 0 auto')
  })

  it('announces the reference and changes translation by code', () => {
    const callbacks = renderToolbar()
    const controls = screen.getByRole('region', { name: 'Passage controls' })
    const reference = within(controls).getByText('John 3')
    const translation = within(controls).getByRole('combobox', { name: 'Change translation' })

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

  it('disables translation selection when no usable options or callback exist', () => {
    renderToolbar({
      translation: '',
      translations: [null, {}, { code: '' }, { code: '   ' }],
      onTranslationChange: undefined,
    })

    const selector = screen.getByRole('combobox', { name: 'Change translation' })
    expect(selector).toBeDisabled()
    expect(selector).toHaveValue('')
    expect(within(selector).getByRole('option')).toHaveTextContent(
      'No translations available',
    )
    expect(() => fireEvent.change(selector, { target: { value: 'KJV' } })).not.toThrow()
  })

  it('normalizes usable translation codes and enables selection after rerender', () => {
    const onTranslationChange = vi.fn()
    const initialProps = {
      reference: 'John 3',
      translation: '',
      translations: [],
      onPrevious: vi.fn(),
      onNext: vi.fn(),
    }
    const view = render(
      <ReaderPreferencesProvider>
        <PassageToolbar {...initialProps} />
      </ReaderPreferencesProvider>,
    )

    expect(screen.getByRole('combobox', { name: 'Change translation' })).toBeDisabled()

    view.rerender(
      <ReaderPreferencesProvider>
        <PassageToolbar
          {...initialProps}
          translation="KJV"
          translations={[
            null,
            { code: ' KJV ', name: ' King James Version ' },
            { code: 'KJV', name: 'Duplicate' },
            { label: 'Missing code' },
          ]}
          onTranslationChange={onTranslationChange}
        />
      </ReaderPreferencesProvider>,
    )

    const selector = screen.getByRole('combobox', { name: 'Change translation' })
    expect(selector).toBeEnabled()
    expect(selector).toHaveValue('KJV')
    expect(within(selector).getAllByRole('option')).toHaveLength(1)
    expect(within(selector).getByRole('option')).toHaveTextContent('King James Version')

    fireEvent.change(selector, { target: { value: 'KJV' } })
    expect(onTranslationChange).toHaveBeenCalledWith('KJV')
  })
})
