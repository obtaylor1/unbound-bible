import { TRANSLATION_BY_KEY } from './comparisonModel'

function LabeledSelect({ id, label, value, onChange, children, disabled = false }) {
  return (
    <label className="compare-control" htmlFor={id}>
      <span>{label}</span>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </label>
  )
}

export default function ComparisonToolbar({
  books,
  chapters,
  verses,
  book,
  chapter,
  verse,
  viewMode,
  baseTranslation,
  selectedTranslations,
  highlightDifferences,
  onBookChange,
  onChapterChange,
  onVerseChange,
  onViewModeChange,
  onBaseTranslationChange,
  onHighlightDifferencesChange,
  onOpenStudyTools,
  studyTriggerRef,
}) {
  return (
    <section className="compare-toolbar" aria-label="Comparison controls">
      <fieldset className="compare-toolbar-group compare-toolbar-passage">
        <legend>Passage</legend>
        <div className="compare-toolbar-row">
          <LabeledSelect id="compare-book" label="Book" value={book} onChange={onBookChange}>
            {books.map((item) => <option key={item} value={item}>{item}</option>)}
          </LabeledSelect>
          <LabeledSelect id="compare-chapter" label="Chapter" value={chapter} onChange={onChapterChange}>
            {chapters.map((item) => <option key={item} value={String(item)}>{item}</option>)}
          </LabeledSelect>
          <LabeledSelect
            id="compare-verse"
            label="Verse"
            value={verse}
            onChange={onVerseChange}
            disabled={viewMode === 'chapter'}
          >
            {verses.map((item) => <option key={item} value={String(item)}>{item}</option>)}
          </LabeledSelect>
        </div>
      </fieldset>

      <fieldset className="compare-toolbar-group compare-toolbar-view">
        <legend>View</legend>
        <div className="compare-segmented-control">
          <button
            type="button"
            aria-label="Verse view"
            aria-pressed={viewMode === 'verse'}
            onClick={() => onViewModeChange('verse')}
          >
            Verse
          </button>
          <button
            type="button"
            aria-label="Chapter view"
            aria-pressed={viewMode === 'chapter'}
            onClick={() => onViewModeChange('chapter')}
          >
            Chapter
          </button>
        </div>
      </fieldset>

      <fieldset className="compare-toolbar-group compare-toolbar-options">
        <legend>Comparison</legend>
        <div className="compare-toolbar-row">
          <LabeledSelect
            id="compare-base"
            label="Base reference"
            value={baseTranslation}
            onChange={onBaseTranslationChange}
          >
            {selectedTranslations.map((key) => (
              <option key={key} value={key}>
                {TRANSLATION_BY_KEY[key]?.name ?? key.toUpperCase()}
              </option>
            ))}
          </LabeledSelect>
          <button
            type="button"
            className="compare-difference-switch"
            role="switch"
            aria-checked={highlightDifferences}
            onClick={() => onHighlightDifferencesChange(!highlightDifferences)}
          >
            <span className="compare-switch-track" aria-hidden="true"><span /></span>
            Highlight differences
          </button>
        </div>
      </fieldset>

      <button ref={studyTriggerRef} type="button" className="compare-study-trigger" onClick={onOpenStudyTools}>
        Open Study Tools <span aria-hidden="true">›</span>
      </button>
    </section>
  )
}
