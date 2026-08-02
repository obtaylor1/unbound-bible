import { useMemo, useState } from 'react'
import {
  MAX_TRANSLATIONS,
  TRANSLATION_FILTERS,
  filterTranslations,
} from './comparisonModel'

export default function TranslationSelector({ selected, baseTranslation, onToggle }) {
  const [category, setCategory] = useState('all')
  const [query, setQuery] = useState('')
  const translations = useMemo(
    () => filterTranslations({ category, query }),
    [category, query],
  )
  const remaining = MAX_TRANSLATIONS - selected.length

  return (
    <aside className="translation-selector" data-testid="translation-selector" aria-labelledby="translation-selector-title">
      <div className="translation-selector-heading">
        <div>
          <p className="compare-eyebrow">Sources</p>
          <h2 id="translation-selector-title">Select translations</h2>
        </div>
        <span className="translation-count-badge">{selected.length}/{MAX_TRANSLATIONS}</span>
      </div>

      <label className="translation-search">
        <span className="sr-only">Search translations</span>
        <input
          type="search"
          value={query}
          placeholder="Search translations…"
          onChange={(event) => setQuery(event.target.value)}
        />
        <span aria-hidden="true">⌕</span>
      </label>

      <div className="translation-filters" aria-label="Translation categories">
        {TRANSLATION_FILTERS.map((filter) => (
          <button
            type="button"
            key={filter.id}
            aria-pressed={category === filter.id}
            onClick={() => setCategory(filter.id)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <div className="translation-list" aria-live="polite">
        {translations.length ? translations.map((translation) => {
          const checked = selected.includes(translation.key)
          const disabled = !checked && selected.length >= MAX_TRANSLATIONS
          return (
            <label
              key={translation.key}
              className={`translation-row ${checked ? 'is-selected' : ''} ${disabled ? 'is-disabled' : ''}`}
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={disabled}
                onChange={() => onToggle(translation.key)}
                aria-label={`${translation.name}, ${translation.code}`}
              />
              <span className="translation-check" aria-hidden="true">✓</span>
              <span className="translation-row-copy">
                <strong>
                  {translation.name}
                  {translation.key === baseTranslation && <span className="base-source-label">Base</span>}
                </strong>
                <small>{translation.tradition} · {translation.year}</small>
              </span>
              <span className="translation-code">{translation.code}</span>
            </label>
          )
        }) : (
          <p className="translation-empty">No translations match this search.</p>
        )}
      </div>

      <div className="translation-capacity" role="status">
        <strong>Comparing {selected.length} {selected.length === 1 ? 'translation' : 'translations'}</strong>
        <span>{remaining > 0 ? `Add up to ${remaining} more` : `Maximum of ${MAX_TRANSLATIONS} translations selected`}</span>
      </div>
    </aside>
  )
}
