import { useMemo, useRef, useState } from 'react'
import CitationDrawer from './CitationDrawer'
import ResearchInspector from './ResearchInspector'
import ResearchTimeline from './ResearchTimeline'

const CLASSIFICATION_LABELS = {
  'canonical-scripture': 'Canonical Scripture', 'ethiopian-canon': 'Ethiopian Canon',
  'ancient-text': 'Ancient Text', commentary: 'Commentary', tradition: 'Tradition',
  historical: 'Historical', scholarship: 'Scholarship', 'ai-synthesis': 'AI synthesis',
}

const confidenceLabel = (confidence) => `${confidence[0].toUpperCase()}${confidence.slice(1)} confidence`
const statusLabel = (status) => status.split('-').map((part) => `${part[0].toUpperCase()}${part.slice(1)}`).join(' ')

function Claim({ claim, sourceLookup, onCitation }) {
  const isSynthesis = claim.classification === 'ai-synthesis'
  return (
    <article className={`research-claim research-claim--${claim.classification}`}>
      <p className="research-claim__classification">
        {isSynthesis && <span aria-hidden="true">✦ </span>}
        <span className={isSynthesis ? 'research-claim__synthesis-label' : undefined}>
          {CLASSIFICATION_LABELS[claim.classification] ?? claim.classification}
        </span>
      </p>
      <p>{claim.statement}</p>
      <p className="research-claim__confidence">{confidenceLabel(claim.confidence)}</p>
      <div className="research-claim__citations">
        {claim.sourceIds.map((sourceId) => {
          const source = sourceLookup.get(sourceId)
          if (!source) return null
          return (
            <button
              type="button"
              key={sourceId}
              aria-label={`Cite ${source.reference}`}
              onClick={(event) => onCitation(source, event.currentTarget)}
            >
              {source.reference}
            </button>
          )
        })}
      </div>
    </article>
  )
}

function ClaimSection({ section, fallbackTitle, sourceLookup, onCitation, always = false }) {
  if (!section || (!always && section.claims.length === 0)) return null
  return (
    <section className="research-workspace__section">
      <h2>{section.title || fallbackTitle}</h2>
      {section.claims.map((claim) => (
        <Claim key={claim.id} claim={claim} sourceLookup={sourceLookup} onCitation={onCitation} />
      ))}
    </section>
  )
}

export default function ResearchWorkspace({
  response, onCitation, onCitationClose, onOpenTarget, onRelatedQuestion,
  onEventResearch, onPersonResearch, onPlaceResearch, onFeedback,
  actionBar, continueResearch, bookExplainer,
}) {
  const [selectedSource, setSelectedSource] = useState(null)
  const citationTriggerRef = useRef(null)
  const sourceLookup = useMemo(() => new Map(response.sources.map((source) => [source.id, source])), [response.sources])

  const openCitation = (source, trigger) => {
    citationTriggerRef.current = trigger
    setSelectedSource(source)
    onCitation?.(source, trigger)
  }
  const closeCitation = () => {
    setSelectedSource(null)
    onCitationClose?.()
  }

  return (
    <div className="research-workspace">
      <header className="research-workspace__header">
        <p className="research-workspace__query">{response.query}</p>
        <p className={`research-workspace__status research-workspace__status--${response.groundingStatus}`}>
          {statusLabel(response.groundingStatus)}
        </p>
        <p className="research-workspace__provenance">Provenance: {response.provider} · {response.model}</p>
      </header>
      <main className="research-workspace__main">
        <ClaimSection section={response.summary} fallbackTitle="Summary" sourceLookup={sourceLookup} onCitation={openCitation} always />
        <ResearchTimeline events={response.timeline} sourceLookup={sourceLookup} onCitation={openCitation} onEventResearch={onEventResearch} />
        <ClaimSection section={response.canonicalAccount} fallbackTitle="Canonical Account" sourceLookup={sourceLookup} onCitation={openCitation} />
        {response.ancientAccounts.map((section, index) => (
          <ClaimSection key={`${section.title}-${index}`} section={section} fallbackTitle="Ancient Accounts" sourceLookup={sourceLookup} onCitation={openCitation} />
        ))}
        <ClaimSection section={response.historicalContext} fallbackTitle="Historical Context" sourceLookup={sourceLookup} onCitation={openCitation} />
        {response.languageNotes.map((section, index) => (
          <ClaimSection key={`${section.title}-${index}`} section={section} fallbackTitle="Language Notes" sourceLookup={sourceLookup} onCitation={openCitation} />
        ))}
        <ClaimSection section={response.unknowns} fallbackTitle="What We Don't Know" sourceLookup={sourceLookup} onCitation={openCitation} />
        {response.relatedQuestions.length > 0 && (
          <section className="research-workspace__related">
            <h2>Related Questions</h2>
            {response.relatedQuestions.map((question) => (
              <button type="button" key={question} onClick={() => onRelatedQuestion?.(question)}>{question}</button>
            ))}
          </section>
        )}
        {(actionBar || onFeedback) && (
          <div className="research-workspace__actions" aria-label="Research result actions">
            {actionBar}
            {onFeedback && <>
              <button type="button" onClick={() => onFeedback('helpful')}>Helpful</button>
              <button type="button" onClick={() => onFeedback('not-helpful')}>Not helpful</button>
            </>}
          </div>
        )}
      </main>
      <ResearchInspector
        sources={response.sources} people={response.people} places={response.places}
        continueResearch={continueResearch} bookExplainer={bookExplainer}
        onCitation={openCitation} onPersonResearch={onPersonResearch} onPlaceResearch={onPlaceResearch}
      />
      <CitationDrawer
        open={Boolean(selectedSource)} source={selectedSource} triggerRef={citationTriggerRef}
        onClose={closeCitation} onOpenTarget={onOpenTarget}
      />
    </div>
  )
}
