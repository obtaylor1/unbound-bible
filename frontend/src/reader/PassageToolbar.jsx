import { useId } from 'react'
import { useReaderPreferences } from './ReaderPreferences'

const FONT_SIZES = ['sm', 'md', 'lg', 'xl', 'xxl']

const FONT_SIZE_NAMES = {
  sm: 'Small',
  md: 'Medium',
  lg: 'Large',
  xl: 'Extra large',
  xxl: 'Extra extra large',
}

function translationDetails(item) {
  if (typeof item === 'string') {
    const code = item.trim()
    return code ? { code, name: code } : null
  }

  if (!item || typeof item !== 'object') return null

  const code = typeof item.code === 'string' ? item.code.trim() : ''
  if (!code) return null

  const suppliedName = typeof item.name === 'string'
    ? item.name
    : typeof item.label === 'string'
      ? item.label
      : ''

  return {
    code,
    name: suppliedName.trim() || code,
  }
}

export default function PassageToolbar({
  reference,
  translation,
  translations = [],
  onTranslationChange,
  canGoPrevious = false,
  onPrevious,
  onNext,
  canGoNext = true,
}) {
  const translationId = useId()
  const { theme, fontSize, setTheme, setFontSize } = useReaderPreferences()
  const textSizeName = FONT_SIZE_NAMES[fontSize]
  const themeAction = theme === 'dark' ? 'Use light mode' : 'Use dark mode'
  const seenTranslationCodes = new Set()
  const usableTranslations = translations
    .map(translationDetails)
    .filter((details) => {
      if (!details || seenTranslationCodes.has(details.code)) return false
      seenTranslationCodes.add(details.code)
      return true
    })
  const selectedTranslation = usableTranslations.some(
    ({ code }) => code === translation,
  )
    ? translation
    : ''
  const canChangeTranslation = (
    usableTranslations.length > 0
    && typeof onTranslationChange === 'function'
  )

  function cycleTextSize() {
    const currentIndex = FONT_SIZES.indexOf(fontSize)
    const nextIndex = (currentIndex + 1) % FONT_SIZES.length
    setFontSize(FONT_SIZES[nextIndex])
  }

  return (
    <section
      className="passage-toolbar"
      aria-label="Passage controls"
      data-text-size={fontSize}
    >
      <div className="passage-toolbar__chapter-controls">
        <button
          className="passage-toolbar__chapter-button"
          type="button"
          disabled={!canGoPrevious}
          onClick={onPrevious}
        >
          Previous chapter
        </button>
        <p className="passage-toolbar__reference" aria-live="polite">
          {reference}
        </p>
        <button
          className="passage-toolbar__chapter-button"
          type="button"
          disabled={!canGoNext}
          onClick={onNext}
        >
          Next chapter
        </button>
      </div>

      <div className="passage-toolbar__settings">
        <label className="passage-toolbar__translation" htmlFor={translationId}>
          <span>Change translation</span>
          <select
            id={translationId}
            value={selectedTranslation}
            disabled={!canChangeTranslation}
            onChange={(event) => {
              if (typeof onTranslationChange === 'function') {
                onTranslationChange(event.target.value)
              }
            }}
          >
            {usableTranslations.length === 0 && (
              <option value="">No translations available</option>
            )}
            {usableTranslations.map((details) => (
              <option key={details.code} value={details.code}>
                {details.name}
              </option>
            ))}
          </select>
        </label>

        <button
          className="passage-toolbar__setting-button"
          type="button"
          onClick={cycleTextSize}
        >
          <span>Change text size</span>
          <span className="passage-toolbar__setting-state">
            Current size: {textSizeName}
          </span>
        </button>

        <button
          className="passage-toolbar__setting-button"
          type="button"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          {themeAction}
        </button>
      </div>
    </section>
  )
}
