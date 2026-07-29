export default function ReaderStatus({
  state,
  reference,
  onRetry,
  onOpenBooks,
}) {
  if (state === 'loading') {
    return (
      <p className="reader-status reader-status--loading" role="status">
        Loading {reference}…
      </p>
    )
  }

  if (state === 'empty') {
    return (
      <section
        className="reader-status reader-status--empty"
        aria-labelledby="reader-empty-heading"
      >
        <h2 id="reader-empty-heading">No text available</h2>
        <p>No text is available for {reference}.</p>
        <p>Choose another book or translation to continue reading.</p>
        <button type="button" onClick={onOpenBooks}>
          Choose another book
        </button>
      </section>
    )
  }

  if (state === 'offline') {
    return (
      <section
        className="reader-status reader-status--offline"
        role="status"
        aria-labelledby="reader-offline-heading"
      >
        <h2 id="reader-offline-heading">You’re offline</h2>
        <p>
          Already-loaded Scripture remains available, but online study tools may
          not work until your connection returns.
        </p>
      </section>
    )
  }

  if (state === 'error') {
    return (
      <section
        className="reader-status reader-status--error"
        role="alert"
        aria-labelledby="reader-error-heading"
      >
        <h2 id="reader-error-heading">Could not open {reference}</h2>
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
