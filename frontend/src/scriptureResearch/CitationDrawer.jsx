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

function DrawerContent({ source, titleId, descriptionId, requestClose, onOpenTarget }) {
  return <>
    <header className="citation-drawer__header">
      <h2 id={titleId}>{source.title}</h2>
      <button type="button" aria-label="Close citation" onClick={requestClose}>Close</button>
    </header>
    <div id={descriptionId} className="citation-drawer__content">
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
    </div>
    {source.openTarget && (
      <button type="button" onClick={() => onOpenTarget?.(source.openTarget, source)}>Open Full Text</button>
    )}
  </>
}

export default function CitationDrawer({ open, source, triggerRef, onClose, onOpenTarget }) {
  const dialogRef = useRef(null)
  const titleId = useId()
  const descriptionId = useId()
  const nativeDialogSupported = (
    typeof HTMLDialogElement !== 'undefined'
    && typeof HTMLDialogElement.prototype.showModal === 'function'
    && typeof HTMLDialogElement.prototype.close === 'function'
  )

  useEffect(() => {
    if (!open || !source) return undefined
    const dialog = dialogRef.current
    if (!dialog) return undefined
    const trigger = triggerRef?.current
    if (nativeDialogSupported && !dialog.open) dialog.showModal()
    dialog.querySelector('button')?.focus()
    return () => {
      if (nativeDialogSupported && dialog.open) dialog.close()
      trigger?.focus()
    }
  }, [nativeDialogSupported, open, source, triggerRef])

  if (!open || !source) return null

  const requestClose = (event) => {
    event?.preventDefault?.()
    onClose?.()
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      requestClose(event)
      return
    }
    if (nativeDialogSupported || event.key !== 'Tab') return
    const buttons = [...dialogRef.current.querySelectorAll('button:not([disabled])')]
    if (!buttons.length) return
    const first = buttons[0]
    const last = buttons[buttons.length - 1]
    if (event.shiftKey && (document.activeElement === first || !dialogRef.current.contains(document.activeElement))) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const content = (
    <DrawerContent
      source={source} titleId={titleId} descriptionId={descriptionId}
      requestClose={requestClose} onOpenTarget={onOpenTarget}
    />
  )

  if (nativeDialogSupported) return (
    <dialog
      ref={dialogRef}
      className="citation-drawer"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      aria-modal="true"
      onCancel={requestClose}
      onKeyDown={handleKeyDown}
    >
      {content}
    </dialog>
  )

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      className="citation-drawer citation-drawer--fallback"
      onKeyDown={handleKeyDown}
    >
      {content}
    </div>
  )
}
