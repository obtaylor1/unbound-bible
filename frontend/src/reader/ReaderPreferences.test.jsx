import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ReaderPreferencesProvider, useReaderPreferences } from './ReaderPreferences'

function PreferenceControls() {
  const {
    theme,
    fontSize,
    readingWidth,
    setTheme,
    setFontSize,
    setReadingWidth,
  } = useReaderPreferences()

  return (
    <>
      <output>{`${theme}:${fontSize}:${readingWidth}`}</output>
      <button onClick={() => setTheme('light')}>Light theme</button>
      <button onClick={() => setFontSize('xxl')}>Extra large text</button>
      <button onClick={() => setReadingWidth('wide')}>Wide reading width</button>
    </>
  )
}

afterEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.readerTheme
})

describe('ReaderPreferencesProvider', () => {
  it('uses defaults and applies the default theme', () => {
    render(
      <ReaderPreferencesProvider>
        <PreferenceControls />
      </ReaderPreferencesProvider>,
    )

    expect(screen.getByRole('status')).toHaveTextContent('dark:md:comfortable')
    expect(document.documentElement.dataset.readerTheme).toBe('dark')
  })

  it('persists changed preferences and applies the selected theme', () => {
    render(
      <ReaderPreferencesProvider>
        <PreferenceControls />
      </ReaderPreferencesProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Light theme' }))
    fireEvent.click(screen.getByRole('button', { name: 'Extra large text' }))
    fireEvent.click(screen.getByRole('button', { name: 'Wide reading width' }))

    expect(screen.getByRole('status')).toHaveTextContent('light:xxl:wide')
    expect(JSON.parse(window.localStorage.getItem('unbound.reader.preferences'))).toEqual({
      theme: 'light',
      fontSize: 'xxl',
      readingWidth: 'wide',
    })
    expect(document.documentElement.dataset.readerTheme).toBe('light')
  })

  it('recovers from malformed stored preferences', () => {
    window.localStorage.setItem('unbound.reader.preferences', '{not json')

    render(
      <ReaderPreferencesProvider>
        <PreferenceControls />
      </ReaderPreferencesProvider>,
    )

    expect(screen.getByRole('status')).toHaveTextContent('dark:md:comfortable')
  })

  it('falls back to defaults for invalid stored settings independently', () => {
    window.localStorage.setItem('unbound.reader.preferences', JSON.stringify({
      theme: 'light',
      fontSize: 'huge',
      readingWidth: 'narrow',
    }))

    render(
      <ReaderPreferencesProvider>
        <PreferenceControls />
      </ReaderPreferencesProvider>,
    )

    expect(screen.getByRole('status')).toHaveTextContent('light:md:comfortable')
    expect(document.documentElement.dataset.readerTheme).toBe('light')
  })

  it('throws a clear error when used outside its provider', () => {
    expect(() => render(<PreferenceControls />)).toThrow(
      'useReaderPreferences must be used within a ReaderPreferencesProvider',
    )
  })
})
