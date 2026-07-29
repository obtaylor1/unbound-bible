import { createContext, useContext, useEffect, useState } from 'react'
import './readerTokens.css'

const STORAGE_KEY = 'unbound.reader.preferences'

const DEFAULT_PREFERENCES = {
  theme: 'dark',
  fontSize: 'md',
  readingWidth: 'comfortable',
}

const validValues = {
  theme: ['light', 'dark'],
  fontSize: ['sm', 'md', 'lg', 'xl', 'xxl'],
  readingWidth: ['comfortable', 'wide'],
}

const ReaderPreferencesContext = createContext(null)

function isValidPreference(key, value) {
  return validValues[key].includes(value)
}

function getStoredPreferences() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    const parsed = stored ? JSON.parse(stored) : {}

    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return DEFAULT_PREFERENCES
    }

    return Object.fromEntries(
      Object.entries(DEFAULT_PREFERENCES).map(([key, defaultValue]) => [
        key,
        isValidPreference(key, parsed[key]) ? parsed[key] : defaultValue,
      ]),
    )
  } catch {
    return DEFAULT_PREFERENCES
  }
}

export function ReaderPreferencesProvider({ children }) {
  const [preferences, setPreferences] = useState(getStoredPreferences)

  useEffect(() => {
    document.documentElement.dataset.readerTheme = preferences.theme
  }, [preferences.theme])

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
    } catch {
      // Preferences remain available for the current session when storage is unavailable.
    }
  }, [preferences])

  function setPreference(key, value) {
    if (isValidPreference(key, value)) {
      setPreferences((current) => ({ ...current, [key]: value }))
    }
  }

  const value = {
    ...preferences,
    setTheme: (theme) => setPreference('theme', theme),
    setFontSize: (fontSize) => setPreference('fontSize', fontSize),
    setReadingWidth: (readingWidth) => setPreference('readingWidth', readingWidth),
  }

  return (
    <ReaderPreferencesContext.Provider value={value}>
      {children}
    </ReaderPreferencesContext.Provider>
  )
}

// This hook is intentionally exported with its provider as the public reader preferences API.
// eslint-disable-next-line react-refresh/only-export-components
export function useReaderPreferences() {
  const preferences = useContext(ReaderPreferencesContext)

  if (!preferences) {
    throw new Error('useReaderPreferences must be used within a ReaderPreferencesProvider')
  }

  return preferences
}
