import { useId } from 'react'

function normalizedVerses(verses) {
  if (!Array.isArray(verses)) {
    return []
  }

  const keyOccurrences = new Map()

  return verses.flatMap((row) => {
    const verse = row?.verse
    const text = typeof row?.text === 'string' ? row.text.trim() : ''

    if (!Number.isInteger(verse) || verse <= 0 || !text) {
      return []
    }

    const sourceId = ['string', 'number'].includes(typeof row.id)
      ? row.id
      : null
    const translation = ['string', 'number'].includes(typeof row.translation)
      ? row.translation
      : null
    const keyBase = JSON.stringify([sourceId, translation, verse, text])
    const occurrence = keyOccurrences.get(keyBase) ?? 0
    keyOccurrences.set(keyBase, occurrence + 1)

    return [{
      key: `${keyBase}-${occurrence}`,
      verse,
      text,
    }]
  })
}

export default function ScripturePane({
  book,
  chapter,
  verses,
  selectedVerse,
  onSelectVerse,
}) {
  const headingId = `scripture-pane-heading-${useId()}`
  const displayBook = typeof book === 'string' && book.trim()
    ? book.trim()
    : 'Scripture'
  const displayChapter = ['string', 'number'].includes(typeof chapter)
    ? String(chapter)
    : ''
  const reference = `${displayBook}${displayChapter ? ` ${displayChapter}` : ''}`
  const canSelect = typeof onSelectVerse === 'function'

  return (
    <article className="scripture-pane" aria-labelledby={headingId}>
      <header className="scripture-pane__header">
        <p className="scripture-pane__eyebrow">Scripture Reader</p>
        <h1 id={headingId}>{reference}</h1>
      </header>

      <ol className="scripture-pane__verses" role="list">
        {normalizedVerses(verses).map((row) => (
          <li key={row.key}>
            <button
              type="button"
              className="scripture-pane__verse"
              aria-label={`${reference} verse ${row.verse}`}
              aria-pressed={selectedVerse === row.verse}
              aria-disabled={!canSelect}
              onClick={() => {
                if (canSelect) {
                  onSelectVerse(row.verse)
                }
              }}
            >
              <span className="scripture-pane__verse-number" aria-hidden="true">
                {row.verse}
              </span>
              <span className="scripture-pane__verse-text">{row.text}</span>
            </button>
          </li>
        ))}
      </ol>
    </article>
  )
}
