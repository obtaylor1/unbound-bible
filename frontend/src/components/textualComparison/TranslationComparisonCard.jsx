import { diffWords } from './comparisonModel'

function SourceStatus({ state, onChooseSource, onLearnMore }) {
  const warning = ['database-missing', 'translation-unavailable'].includes(state.kind)
  return (
    <div className={`source-status source-status-${warning ? 'warning' : 'neutral'}`} role="status">
      <span className="source-status-icon" aria-hidden="true">{warning ? 'i' : '—'}</span>
      <div>
        <h4>{state.title}</h4>
        <p>{state.message}</p>
        <div className="source-status-actions">
          <button type="button" aria-label="Learn more about text availability" onClick={onLearnMore}>
            Learn more
          </button>
          <button type="button" onClick={onChooseSource}>Choose another source</button>
        </div>
      </div>
    </div>
  )
}

export default function TranslationComparisonCard({
  reference,
  source,
  state,
  baseText,
  isBase,
  highlightDifferences,
  differenceCount,
  bookmarked,
  onBookmark,
  onOpenNotes,
  onChooseSource,
  onLearnMore,
}) {
  const renderedWords = state.kind === 'available'
    ? diffWords(state.text, highlightDifferences ? baseText : state.text)
    : []

  return (
    <article
      className={`translation-card ${isBase ? 'is-base' : ''}`}
      aria-label={source.name}
      aria-current={isBase ? 'true' : undefined}
    >
      <header className="translation-card-header">
        <span className="translation-card-code">{source.code}</span>
        <div>
          <h3>{source.name}</h3>
          <p>{source.tradition} · {source.year}</p>
        </div>
        {isBase && <span className="translation-base-chip">Base reference</span>}
        <button type="button" className="translation-card-menu" aria-label={`More actions for ${source.code}`}>⋮</button>
      </header>

      <div className="translation-card-body">
        <div className="translation-card-reference">
          <span>{reference}</span>
          {state.kind === 'available' && differenceCount > 0 && (
            <span className="difference-chip">{differenceCount} {differenceCount === 1 ? 'difference' : 'differences'}</span>
          )}
        </div>
        {state.kind === 'available' ? (
          <p className="translation-scripture">
            {renderedWords.map((word, index) => word.differs ? (
              <mark key={`${word.text}-${index}`}>{word.text}</mark>
            ) : word.text)}
          </p>
        ) : (
          <SourceStatus state={state} onChooseSource={onChooseSource} onLearnMore={onLearnMore} />
        )}
      </div>

      <footer className="translation-card-footer">
        <span>{source.language} · {source.tradition}</span>
        <div>
          <button
            type="button"
            aria-pressed={bookmarked}
            aria-label={`Bookmark ${reference} in ${source.code}`}
            onClick={onBookmark}
          >
            {bookmarked ? 'Saved' : 'Bookmark'}
          </button>
          <button type="button" onClick={onOpenNotes}>View notes</button>
        </div>
      </footer>
    </article>
  )
}
