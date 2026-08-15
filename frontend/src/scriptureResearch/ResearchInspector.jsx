const SOURCE_TYPE_LABELS = {
  'canonical-scripture': 'Canonical Scripture',
  'ethiopian-canon': 'Ethiopian Canon',
  'ancient-text': 'Ancient Text',
  manuscript: 'Manuscript',
  'historical-source': 'Historical Source',
  'early-christian-writing': 'Early Christian Writing',
  'jewish-tradition': 'Jewish Tradition',
  'church-tradition': 'Church Tradition',
  commentary: 'Commentary', scholarship: 'Scholarship', 'ai-synthesis': 'AI Synthesis',
}

export default function ResearchInspector({
  response, sources = response?.sources ?? [], people = response?.people ?? [], places = response?.places ?? [], continueResearch, bookExplainer,
  onCitation, onPersonResearch, onPlaceResearch,
}) {
  const hasContent = sources.length || people.length || places.length || continueResearch || bookExplainer
  if (!hasContent) return null
  return (
    <aside className="research-inspector" aria-label="Research details">
      {sources.length > 0 && (
        <section className="research-inspector__card">
          <h2>Sources</h2>
          <ul>{sources.map((source) => (
            <li key={source.id}>
              <h3>{source.title}</h3>
              <p>{SOURCE_TYPE_LABELS[source.sourceType] ?? source.sourceType}</p>
              {source.tradition && <p>{source.tradition}</p>}
              {source.reference && <p>{source.reference}</p>}
              <button type="button" onClick={(event) => onCitation?.(source, event.currentTarget)}>
                Open citation for {source.reference || source.title}
              </button>
            </li>
          ))}</ul>
        </section>
      )}
      {people.length > 0 && (
        <section className="research-inspector__card">
          <h2>People</h2>
          <ul>{people.map((person, index) => (
            <li key={`${person.name}-${index}`}>
              <h3>{person.name}</h3>
              {person.role && <p>{person.role}</p>}
              {person.description && <p>{person.description}</p>}
              {onPersonResearch && <button type="button" onClick={() => onPersonResearch(person)}>Research {person.name}</button>}
            </li>
          ))}</ul>
        </section>
      )}
      {places.length > 0 && (
        <section className="research-inspector__card">
          <h2>Places</h2>
          <ul>{places.map((place, index) => (
            <li key={`${place.name}-${index}`}>
              <h3>{place.name}</h3>
              {place.location && <p>{place.location}</p>}
              {place.description && <p>{place.description}</p>}
              {onPlaceResearch && <button type="button" onClick={() => onPlaceResearch(place)}>Research {place.name}</button>}
            </li>
          ))}</ul>
        </section>
      )}
      {continueResearch && <section className="research-inspector__card"><h2>Continue Research</h2>{continueResearch}</section>}
      {bookExplainer && <section className="research-inspector__card"><h2>Book Explainer</h2>{bookExplainer}</section>}
    </aside>
  )
}
