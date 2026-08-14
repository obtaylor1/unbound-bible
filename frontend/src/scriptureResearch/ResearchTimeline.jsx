const confidenceLabel = (confidence) => `${confidence[0].toUpperCase()}${confidence.slice(1)} confidence`

function CitationButtons({ sourceIds, sourceLookup, onCitation }) {
  return sourceIds.map((sourceId) => {
    const source = sourceLookup.get(sourceId)
    if (!source) return null
    return (
      <button
        type="button"
        key={sourceId}
        aria-label={`Cite ${source.reference}`}
        onClick={(event) => onCitation?.(source, event.currentTarget)}
      >
        {source.reference}
      </button>
    )
  })
}

export default function ResearchTimeline({ events, sources = [], sourceLookup, onCitation, onEventResearch }) {
  if (!events?.length) return null
  const lookup = sourceLookup ?? new Map(sources.map((source) => [source.id, source]))
  return (
    <section className="research-timeline" aria-labelledby="research-timeline-title">
      <h2 id="research-timeline-title">Timeline</h2>
      <ol>
        {events.map((event, index) => (
          <li key={`${event.title}-${index}`} className="research-timeline__event">
            <article>
              <h3>{event.title}</h3>
              {event.dateLabel && <p className="research-timeline__date">{event.dateLabel}</p>}
              <p>{event.description}</p>
              <p className="research-timeline__confidence">{confidenceLabel(event.confidence)}</p>
              <div className="research-timeline__citations">
                <CitationButtons sourceIds={event.sourceIds} sourceLookup={lookup} onCitation={onCitation} />
              </div>
              {onEventResearch && (
                <button type="button" onClick={() => onEventResearch(event)}>Research {event.title}</button>
              )}
            </article>
          </li>
        ))}
      </ol>
    </section>
  )
}
