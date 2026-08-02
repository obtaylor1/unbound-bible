import { useId } from 'react'

export default function ReaderStatus({
  state,
  reference,
  onRetry,
  onOpenBooks,
  hasLoadedContent = false,
  compact = false,
}) {
  const headingId = useId()

  if (state === 'loading') {
    return (
      <section
        className="reader-status reader-status--loading"
        role="status"
        aria-labelledby={headingId}
      >
        <h1 id={headingId}>Loading {reference}…</h1>
        <div className="reader-loading-skeleton" aria-hidden="true">
          <span className="reader-loading-skeleton__title" />
          <span className="reader-loading-skeleton__line" />
          <span className="reader-loading-skeleton__line" />
          <span className="reader-loading-skeleton__line reader-loading-skeleton__line--short" />
          <span className="reader-loading-skeleton__line" />
        </div>
      </section>
    )
  }

  if (state === 'empty') {
    return (
      <section
        className="reader-status reader-status--empty"
        aria-labelledby={headingId}
      >
        <h1 id={headingId}>No text available</h1>
        <p>No text is available for {reference}.</p>
        <p>Choose another book or translation to continue reading.</p>
        <button type="button" onClick={onOpenBooks}>
          Choose another book
        </button>
      </section>
    )
  }

  if (state === 'offline') {
    const Heading = compact && hasLoadedContent ? 'h2' : 'h1'
    const heading = hasLoadedContent
      ? 'You’re offline'
      : 'Scripture unavailable offline'
    return (
      <section
        className={`reader-status reader-status--offline${compact ? ' reader-status--compact' : ''}`}
        role="status"
        aria-labelledby={headingId}
      >
        <Heading id={headingId}>{heading}</Heading>
        {hasLoadedContent ? (
          <p>
            Loaded Scripture remains available, but online study tools may not
            work until your connection returns.
          </p>
        ) : (
          <p>We could not load {reference} while you’re offline.</p>
        )}
        {typeof onRetry === 'function' && (
          <button type="button" onClick={onRetry}>Try again</button>
        )}
      </section>
    )
  }

  if (state === 'error') {
    return (
      <section
        className="reader-status reader-status--error"
        role="alert"
        aria-labelledby={headingId}
      >
        <h1 id={headingId}>Could not open {reference}</h1>
        <p>
          We couldn’t load this passage. The reader’s place is saved, so it is
          safe to try again.
        </p>
        <div className="reader-status__actions">
          <button type="button" onClick={onRetry}>
            Try again
          </button>
          <button type="button" onClick={onOpenBooks}>
            Choose another book
          </button>
        </div>
      </section>
    )
  }

  return null
}
