import { useId } from 'react'

function normalizedVerses(verses) {
  if (!Array.isArray(verses)) {
    return []
  }

  const keyOccurrences = new Map()

  return verses.flatMap((row, sourceIndex) => {
    const verse = row?.verse
    const text = typeof row?.text === 'string' ? row.text.trim() : ''

    if (!Number.isInteger(verse) || verse <= 0 || !text) {
      return []
    }

    const hasSourceId = ['string', 'number'].includes(typeof row.id)
    const translationType = typeof row.translation
    const translation = ['string', 'number'].includes(translationType)
      ? row.translation
      : null
    const keyBase = hasSourceId
      ? `id:${typeof row.id}:${JSON.stringify(row.id)}`
      : `translation:${translationType}:${JSON.stringify(translation)}:verse:${verse}`
    const occurrence = keyOccurrences.get(keyBase) ?? 0
    keyOccurrences.set(keyBase, occurrence + 1)

    return [{
      key: `${keyBase}-${occurrence}`,
      sourceIndex,
      verse,
      text,
    }]
  })
}

function VerseContent({ reference, row, referenceId, textId }) {
  return (
    <>
      <span
        id={referenceId}
        className="scripture-pane__verse-reference"
      >
        {`${reference} verse ${row.verse}`}
      </span>
      <span className="scripture-pane__verse-number" aria-hidden="true">
        {row.verse}
      </span>
      <span id={textId} className="scripture-pane__verse-text">{row.text}</span>
    </>
  )
}

export default function ScripturePane({
  book,
  chapter,
  verses,
  selectedVerse,
  onSelectVerse,
}) {
  const headingId = `scripture-pane-heading-${useId()}`
  const verseLabelPrefix = `scripture-pane-verse-${useId()}`
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
        {normalizedVerses(verses).map((row) => {
          const referenceId = `${verseLabelPrefix}-reference-${row.sourceIndex}`
          const textId = `${verseLabelPrefix}-text-${row.sourceIndex}`

          return (
            <li key={row.key}>
              {canSelect ? (
                <button
                  type="button"
                  className="scripture-pane__verse"
                  aria-labelledby={`${referenceId} ${textId}`}
                  aria-pressed={selectedVerse === row.verse}
                  onClick={() => onSelectVerse(row.verse)}
                >
                  <VerseContent
                    reference={reference}
                    row={row}
                    referenceId={referenceId}
                    textId={textId}
                  />
                </button>
              ) : (
                <div className="scripture-pane__verse scripture-pane__verse--static">
                  <VerseContent reference={reference} row={row} />
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </article>
  )
}
