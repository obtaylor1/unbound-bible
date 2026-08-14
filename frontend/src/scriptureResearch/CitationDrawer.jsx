import { useEffect, useId, useRef } from 'react'

const SOURCE_TYPE_LABELS = {
  'canonical-scripture': 'Biblical Canon',
  'ethiopian-canon': 'Ethiopian Canon',
  'ancient-text': 'Ancient Text',
  manuscript: 'Manuscript',
  'historical-source': 'Historical Source',
  'early-christian-writing': 'Early Christian Writing',
  'jewish-tradition': 'Jewish Tradition',
  'church-tradition': 'Church Tradition',
  commentary: 'Commentary',
  scholarship: 'Scholarship',
  'ai-synthesis': 'AI Synthesis',
}

function Detail({ label, value }) {
  if (!value) return null
  return <div className="citation-drawer__detail"><dt>{label}</dt><dd>{value}</dd></div>
}

export default function CitationDrawer({ open, source, triggerRef, onClose, onOpenTarget }) {
  const dialogRef = useRef(null)
  const titleId = useId()

  useEffect(() => {
    if (!open || !source) return undefined
    const dialog = dialogRef.current
    if (!dialog) return undefined
    const trigger = triggerRef?.current
    if (typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal()
    dialog.querySelector('button')?.focus()
    return () => {
      if (dialog.open && typeof dialog.close === 'function') dialog.close()
      trigger?.focus()
    }
  }, [open, source, triggerRef])

  if (!open || !source) return null

  const requestClose = (event) => {
    event?.preventDefault?.()
    onClose?.()
  }

  return (
    <dialog
      ref={dialogRef}
      className="citation-drawer"
      aria-labelledby={titleId}
      aria-modal="true"
      onCancel={requestClose}
      onKeyDown={(event) => { if (event.key === 'Escape') requestClose(event) }}
    >
      <header className="citation-drawer__header">
        <h2 id={titleId}>{source.title}</h2>
        <button type="button" aria-label="Close citation" onClick={requestClose}>Close</button>
      </header>
      {source.reference && <p className="citation-drawer__reference">{source.reference}</p>}
      {source.excerpt && <blockquote>{source.excerpt}</blockquote>}
      {source.text && <p className="citation-drawer__text">{source.text}</p>}
      <dl className="citation-drawer__details">
        <Detail label="Source type" value={SOURCE_TYPE_LABELS[source.sourceType] ?? source.sourceType} />
        <Detail label="Tradition" value={source.tradition} />
        <Detail label="Date or era" value={source.dateOrEra} />
        <Detail label="Original language" value={source.originalLanguage} />
        <Detail label="Translation" value={source.translation} />
        <Detail label="Relevance" value={source.relevance} />
      </dl>
      {source.openTarget && (
        <button type="button" onClick={() => onOpenTarget?.(source.openTarget, source)}>Open Full Text</button>
      )}
    </dialog>
  )
}
