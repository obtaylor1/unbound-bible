import { useEffect, useId, useMemo, useRef, useState } from 'react'

import { getCommentaryEntries, getCommentarySources } from './commentaryApi'
import useDialogFocus from './useDialogFocus'

const SOURCE_KEY = 'unbound_commentary_source'

function positiveVerseList(verses) {
  if (!Array.isArray(verses)) return []
  return [...new Set(verses.filter((verse) => Number.isSafeInteger(verse) && verse > 0))]
    .sort((left, right) => left - right)
}

function safeReference(reference) {
  const book = typeof reference?.book === 'string' && reference.book.trim()
    ? reference.book.trim()
    : 'Scripture'
  const chapter = Number.isSafeInteger(reference?.chapter) && reference.chapter > 0
    ? reference.chapter
    : 1
  const verse = Number.isSafeInteger(reference?.verse) && reference.verse > 0
    ? reference.verse
    : null
  return { book, chapter, verse }
}

function sourceDetails(source) {
  if (!source) return []
  return [
    ['Author', source.author],
    ['Published', source.publication_period],
    ['Tradition', source.tradition],
    ['Language', source.language],
    ['License', source.license_spdx],
    ['Attribution', source.attribution],
  ].filter(([, value]) => typeof value === 'string' && value.trim())
}

function scopeLabel(entry, availability) {
  const start = entry?.scope?.verse_start
  const end = entry?.scope?.verse_end
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end)) return null
  if (availability === 'wider_range' || start !== end) {
    return start === end ? `Covers verse ${start}` : `Covers verses ${start}–${end}`
  }
  return null
}

function paragraphs(body) {
  return String(body ?? '')
    .split(/\n\s*\n/u)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
}

function EntryArticle({ entry, availability, onCopy, searchMatched, source }) {
  const range = scopeLabel(entry, availability)
  return (
    <article className={`commentary-panel__entry${searchMatched ? ' commentary-panel__entry--search-match' : ''}`}>
      {source ? (
        <p className="commentary-panel__entry-source">
          <strong>{source.title}</strong>
          {source.abbreviation ? <span>{source.abbreviation}</span> : null}
        </p>
      ) : null}
      {entry.heading || range ? (
        <header className="commentary-panel__entry-header">
          {entry.heading ? <h4>{entry.heading}</h4> : null}
          {range ? <span className="commentary-panel__range-badge">{range}</span> : null}
        </header>
      ) : null}
      <div className="commentary-panel__body">
        {paragraphs(entry.body).map((paragraph, index) => (
          <p key={`${index}-${paragraph.slice(0, 32)}`}>{paragraph}</p>
        ))}
      </div>
      <footer className="commentary-panel__citation">
        <cite>{entry.citation}</cite>
        <div className="commentary-panel__entry-actions">
          <button
            type="button"
            className="commentary-panel__control commentary-panel__quiet-action"
            onClick={() => onCopy(entry.body, 'Commentary text')}
          >
            Copy commentary text
          </button>
          <button
            type="button"
            className="commentary-panel__control commentary-panel__quiet-action"
            onClick={() => onCopy(entry.citation, 'Citation')}
          >
            Copy commentary citation
          </button>
        </div>
      </footer>
    </article>
  )
}

function ExpandedCommentary({
  open,
  title,
  entries,
  availability,
  onCopy,
  onClose,
  openerRef,
  searchMatched,
  source,
  copyNotice,
}) {
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const titleId = useId()

  useDialogFocus({
    open,
    containerRef: dialogRef,
    initialRef: closeRef,
    restoreRef: openerRef,
    onClose,
  })

  if (!open) return null
  return (
    <div className="commentary-panel__expanded-layer">
      <div className="commentary-panel__expanded-backdrop" aria-hidden="true" />
      <dialog
        ref={dialogRef}
        open
        className="commentary-panel__expanded"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="commentary-panel__expanded-header">
          <div>
            <p className="commentary-panel__eyebrow">Expanded reading view</p>
            <h3 id={titleId}>Expanded {title}</h3>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="commentary-panel__control commentary-panel__close"
            onClick={onClose}
          >
            Close expanded commentary
          </button>
        </header>
        <div className="commentary-panel__expanded-content">
          {entries.map((entry, index) => (
            <EntryArticle
              key={`${entry.citation}-${index}`}
              entry={entry}
              availability={availability}
              onCopy={onCopy}
              searchMatched={searchMatched}
              source={source}
            />
          ))}
        </div>
        {copyNotice.message ? (
          <p
            key={copyNotice.revision}
            className="commentary-panel__visually-hidden"
            role="status"
            aria-label="Copy status"
            aria-live="polite"
            aria-atomic="true"
          >
            {copyNotice.message}
          </p>
        ) : null}
      </dialog>
    </div>
  )
}

export default function CommentaryPanel({
  headingId,
  reference,
  verses = [],
  onSelectVerse,
  loadSources = getCommentarySources,
  loadEntries = getCommentaryEntries,
}) {
  const generatedHeadingId = useId()
  const tabIds = useId()
  const resolvedHeadingId = headingId || generatedHeadingId
  const normalizedReference = safeReference(reference)
  const { book, chapter, verse } = normalizedReference
  const title = `${book} ${chapter} commentary`
  const referenceLabel = `${book} ${chapter}${verse ? `:${verse}` : ''}`
  const [sources, setSources] = useState([])
  const [sourceId, setSourceId] = useState('')
  const [sourceStatus, setSourceStatus] = useState('loading')
  const [sourceRetry, setSourceRetry] = useState(0)
  const [result, setResult] = useState(null)
  const [resultOwnership, setResultOwnership] = useState('')
  const [status, setStatus] = useState('idle')
  const [errorOwnership, setErrorOwnership] = useState('')
  const [requestRetry, setRequestRetry] = useState(0)
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [copyNotice, setCopyNotice] = useState({ message: '', revision: 0 })
  const requestGeneration = useRef(0)
  const expandButtonRef = useRef(null)
  const overviewTabRef = useRef(null)
  const verseTabRef = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    setSourceStatus('loading')
    Promise.resolve().then(() => loadSources(controller.signal)).then((nextSources) => {
      if (controller.signal.aborted) return
      const installed = Array.isArray(nextSources)
        ? nextSources.filter((source) => source && typeof source.id === 'string' && typeof source.title === 'string')
        : []
      setSources(installed)
      let saved = null
      try {
        saved = window.localStorage.getItem(SOURCE_KEY)
      } catch {
        saved = null
      }
      const selected = installed.find(({ id }) => id === saved) ?? installed[0]
      setSourceId(selected?.id ?? '')
      setSourceStatus('ready')
    }).catch((nextError) => {
      if (controller.signal.aborted || nextError?.name === 'AbortError') return
      setSources([])
      setSourceId('')
      setSourceStatus('error')
    })
    return () => controller.abort()
  }, [loadSources, sourceRetry])

  const requestOwnership = `${sourceId}|${book}|${chapter}|${verse ?? ''}`
  const requestKey = `${requestOwnership}|${requestRetry}`
  useEffect(() => {
    if (!sourceId || !book || !chapter) {
      setResult(null)
      setResultOwnership('')
      setStatus('idle')
      return undefined
    }
    const controller = new AbortController()
    const generation = ++requestGeneration.current
    setStatus('loading')
    setErrorOwnership('')
    const request = { source: sourceId, book, chapter }
    if (verse) request.verse = verse
    Promise.resolve().then(() => loadEntries(request, controller.signal))
      .then((nextResult) => {
        if (generation !== requestGeneration.current || controller.signal.aborted) return
        setResult(nextResult)
        setResultOwnership(requestOwnership)
        setErrorOwnership('')
        setStatus('ready')
      })
      .catch((nextError) => {
        if (
          generation !== requestGeneration.current
          || controller.signal.aborted
          || nextError?.name === 'AbortError'
        ) return
        setResult(null)
        setResultOwnership('')
        setErrorOwnership(requestOwnership)
        setStatus('error')
      })
    return () => controller.abort()
  }, [loadEntries, requestKey, requestOwnership, sourceId, book, chapter, verse])

  useEffect(() => {
    setExpanded(false)
    setCopyNotice((current) => current.message
      ? { message: '', revision: current.revision + 1 }
      : current)
  }, [requestOwnership])

  const validVerses = useMemo(() => positiveVerseList(verses), [verses])
  const currentIndex = verse ? validVerses.indexOf(verse) : -1
  const previousVerse = verse
    ? (currentIndex >= 0
        ? validVerses[currentIndex - 1]
        : validVerses.filter((candidate) => candidate < verse).at(-1))
    : null
  const nextVerse = verse
    ? (currentIndex >= 0
        ? validVerses[currentIndex + 1]
        : validVerses.find((candidate) => candidate > verse))
    : null
  const ownedResult = resultOwnership === requestOwnership ? result : null
  const ownsError = status === 'error' && errorOwnership === requestOwnership
  const displayStatus = ownsError
    ? 'error'
    : resultOwnership === requestOwnership
      ? status
      : sourceId
        ? 'loading'
        : status
  const selectedSource = sources.find(({ id }) => id === sourceId) ?? ownedResult?.source ?? null
  const normalizedQuery = query.toLocaleLowerCase()
  const filteredEntries = (Array.isArray(ownedResult?.entries) ? ownedResult.entries : [])
    .filter((item) => typeof item?.body === 'string')
    .filter((item) => item.body.toLocaleLowerCase().includes(normalizedQuery))

  const chooseSource = (nextSource) => {
    setSourceId(nextSource)
    setQuery('')
    setExpanded(false)
    try {
      window.localStorage.setItem(SOURCE_KEY, nextSource)
    } catch {
      // The selection still works for this session when storage is unavailable.
    }
  }

  const chooseAnotherSource = () => {
    if (sources.length < 2) return
    const index = Math.max(0, sources.findIndex(({ id }) => id === sourceId))
    chooseSource(sources[(index + 1) % sources.length].id)
  }

  const copyText = async (text, label) => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(String(text))
      setCopyNotice((current) => ({
        message: `${label} copied`,
        revision: current.revision + 1,
      }))
    } catch {
      setCopyNotice((current) => ({
        message: `${label} could not be copied`,
        revision: current.revision + 1,
      }))
    }
  }

  const selectVerse = (nextVerse) => {
    if (typeof onSelectVerse === 'function') onSelectVerse(nextVerse)
  }

  const firstCoveredVerse = filteredEntries
    .map((item) => item?.scope?.verse_start)
    .find((candidate) => validVerses.includes(candidate))
  const overviewTabId = `${tabIds}-overview-tab`
  const verseTabId = `${tabIds}-verse-tab`
  const activePanelId = `${tabIds}-${verse ? 'verse' : 'overview'}-panel`
  const activeTabId = verse ? verseTabId : overviewTabId
  const inactivePanelId = `${tabIds}-${verse ? 'overview' : 'verse'}-panel`
  const inactiveTabId = verse ? overviewTabId : verseTabId
  const expandedOpen = expanded && Boolean(ownedResult)

  const handleTabKeyDown = (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    const activeIndex = verse ? 1 : 0
    const focusedIndex = event.currentTarget === verseTabRef.current ? 1 : 0
    let targetIndex = focusedIndex
    if (event.key === 'Home') targetIndex = 0
    else if (event.key === 'End') targetIndex = verse ? 1 : 0
    else if (event.key === 'ArrowLeft') targetIndex = focusedIndex === 0 ? (verse ? 1 : 0) : 0
    else if (event.key === 'ArrowRight') targetIndex = focusedIndex === 1 ? 0 : (verse ? 1 : 0)
    event.preventDefault()
    const target = targetIndex === 0 ? overviewTabRef.current : verseTabRef.current
    target?.focus()
    if (targetIndex !== activeIndex) selectVerse(targetIndex === 0 ? null : verse)
  }

  return (
    <section
      className="commentary-panel"
      role="region"
      aria-labelledby={resolvedHeadingId}
      aria-busy={displayStatus === 'loading' || sourceStatus === 'loading'}
    >
      <header className="commentary-panel__masthead">
        <div>
          <p className="commentary-panel__eyebrow">Verified study library</p>
          <h3 id={resolvedHeadingId}>{title}</h3>
          <p className="commentary-panel__reference">Commentary for {referenceLabel}</p>
        </div>
        {displayStatus === 'ready' && filteredEntries.length > 0 ? (
          <button
            ref={expandButtonRef}
            type="button"
            className="commentary-panel__control commentary-panel__expand"
            onClick={() => setExpanded(true)}
          >
            Expand commentary reading view
          </button>
        ) : null}
      </header>

      <div className="commentary-panel__tabs" role="tablist" aria-label="Commentary scope">
        <button
          ref={overviewTabRef}
          id={overviewTabId}
          type="button"
          role="tab"
          className="commentary-panel__control commentary-panel__tab"
          aria-selected={!verse}
          aria-controls={`${tabIds}-overview-panel`}
          tabIndex={verse ? -1 : 0}
          onKeyDown={handleTabKeyDown}
          onClick={() => selectVerse(null)}
        >
          Chapter overview
        </button>
        <button
          ref={verseTabRef}
          id={verseTabId}
          type="button"
          role="tab"
          className="commentary-panel__control commentary-panel__tab"
          aria-selected={Boolean(verse)}
          aria-controls={`${tabIds}-verse-panel`}
          tabIndex={verse ? 0 : -1}
          onKeyDown={handleTabKeyDown}
          disabled={!verse}
        >
          Selected verse
        </button>
      </div>

      <div
        id={inactivePanelId}
        role="tabpanel"
        aria-labelledby={inactiveTabId}
        hidden
      />
      <div
        id={activePanelId}
        className="commentary-panel__tabpanel"
        role="tabpanel"
        aria-labelledby={activeTabId}
        tabIndex={0}
      >

      {sourceStatus === 'error' ? (
        <div className="commentary-panel__callout commentary-panel__callout--error" role="alert">
          <h4>Commentary sources could not be loaded</h4>
          <p>Check your connection, then try again.</p>
          <button
            type="button"
            className="commentary-panel__control"
            onClick={() => setSourceRetry((value) => value + 1)}
          >
            Retry loading commentary sources
          </button>
        </div>
      ) : sourceStatus === 'ready' && sources.length === 0 ? (
        <div className="commentary-panel__callout" role="status">
          <h4>No commentary sources are installed.</h4>
          <p>An administrator can add a verified public-domain commentary collection.</p>
          <button
            type="button"
            className="commentary-panel__control"
            onClick={() => setSourceRetry((value) => value + 1)}
          >
            Retry loading commentary sources
          </button>
        </div>
      ) : null}

      {sources.length > 0 ? (
        <div className="commentary-panel__source-desk">
          <div className="commentary-panel__source-field">
            <label htmlFor={`${resolvedHeadingId}-source`}>Commentary source</label>
            <select
              id={`${resolvedHeadingId}-source`}
              className="commentary-panel__control"
              value={sourceId}
              onChange={(event) => chooseSource(event.target.value)}
            >
              {sources.map((source) => (
                <option key={source.id} value={source.id}>{source.title}</option>
              ))}
            </select>
          </div>
          {selectedSource ? (
            <aside className="commentary-panel__source-card" aria-label="Selected commentary source details">
              <strong>{selectedSource.title}</strong>
              <dl>
                {sourceDetails(selectedSource).map(([label, value]) => (
                  <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
                ))}
              </dl>
            </aside>
          ) : null}
        </div>
      ) : null}

      {verse ? (
        <nav className="commentary-panel__verse-nav" aria-label="Commentary verse navigation">
          <button
            type="button"
            className="commentary-panel__control"
            disabled={!previousVerse}
            onClick={() => selectVerse(previousVerse)}
          >
            Previous verse
          </button>
          <span>Verse {verse}</span>
          <button
            type="button"
            className="commentary-panel__control"
            disabled={!nextVerse}
            onClick={() => selectVerse(nextVerse)}
          >
            Next verse
          </button>
        </nav>
      ) : null}

      {displayStatus === 'loading' ? (
        <div className="commentary-panel__loading" role="status" aria-live="polite">
          <span className="commentary-panel__loading-mark" aria-hidden="true" />
          Loading commentary for {referenceLabel}…
        </div>
      ) : null}

      {displayStatus === 'error' ? (
        <div className="commentary-panel__callout commentary-panel__callout--error" role="alert">
          <h4>Commentary could not be loaded</h4>
          <p>The source is temporarily unavailable. Your Scripture reading has not been interrupted.</p>
          <button
            type="button"
            className="commentary-panel__control"
            onClick={() => setRequestRetry((value) => value + 1)}
          >
            Retry loading commentary
          </button>
        </div>
      ) : null}

      {displayStatus === 'ready' && ownedResult?.availability === 'no_entry' ? (
        <div className="commentary-panel__callout" role="status">
          <h4>No commentary entry for {referenceLabel}</h4>
          <p>This verified source does not include a note for the selected passage.</p>
          <div className="commentary-panel__next-actions">
            {verse && typeof onSelectVerse === 'function' ? (
              <button type="button" className="commentary-panel__control" onClick={() => selectVerse(null)}>
                View chapter overview
              </button>
            ) : null}
            <button
              type="button"
              className="commentary-panel__control"
              disabled={sources.length < 2}
              onClick={chooseAnotherSource}
            >
              Choose another commentary source
            </button>
          </div>
        </div>
      ) : null}

      {displayStatus === 'ready' && ownedResult?.availability === 'coverage_incomplete' ? (
        <div className="commentary-panel__callout commentary-panel__callout--incomplete" role="status">
          <h4>This source has incomplete coverage for {referenceLabel}</h4>
          <p>The passage is part of the source, but a verified entry has not yet been published.</p>
          <div className="commentary-panel__next-actions">
            {verse && typeof onSelectVerse === 'function' ? (
              <button type="button" className="commentary-panel__control" onClick={() => selectVerse(null)}>
                View chapter overview
              </button>
            ) : null}
            <button
              type="button"
              className="commentary-panel__control"
              disabled={sources.length < 2}
              onClick={chooseAnotherSource}
            >
              Choose another commentary source
            </button>
          </div>
        </div>
      ) : null}

      {displayStatus === 'ready' && ownedResult?.availability === 'wider_range' ? (
        <div className="commentary-panel__callout commentary-panel__callout--range" role="status">
          <p>This note discusses a wider passage that includes {referenceLabel}.</p>
          <div className="commentary-panel__next-actions">
            {verse && typeof onSelectVerse === 'function' ? (
              <button type="button" className="commentary-panel__control" onClick={() => selectVerse(null)}>
                View chapter overview
              </button>
            ) : null}
            {firstCoveredVerse && typeof onSelectVerse === 'function' ? (
              <button
                type="button"
                className="commentary-panel__control"
                onClick={() => selectVerse(firstCoveredVerse)}
              >
                Read covered passage from verse {firstCoveredVerse}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {displayStatus === 'ready' && ownedResult?.truncated ? (
        <div className="commentary-panel__callout commentary-panel__callout--truncated" role="status">
          <p>More matching commentary is available than can be shown here.</p>
          <div className="commentary-panel__next-actions">
            {!verse && validVerses.length > 0 && typeof onSelectVerse === 'function' ? (
              <button
                type="button"
                className="commentary-panel__control"
                onClick={() => selectVerse(validVerses[0])}
              >
                Narrow commentary to verse {validVerses[0]}
              </button>
            ) : null}
            <button
              type="button"
              className="commentary-panel__control"
              disabled={sources.length < 2}
              onClick={chooseAnotherSource}
            >
              Choose another commentary source
            </button>
          </div>
        </div>
      ) : null}

      {displayStatus === 'ready' && Array.isArray(ownedResult?.entries) && ownedResult.entries.length > 0 ? (
        <div className="commentary-panel__library">
          <div className="commentary-panel__search">
            <label htmlFor={`${resolvedHeadingId}-search`}>Search this commentary</label>
            <input
              id={`${resolvedHeadingId}-search`}
              type="search"
              className="commentary-panel__control"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Find a word or phrase"
            />
            <span>{filteredEntries.length} {filteredEntries.length === 1 ? 'note' : 'notes'} shown</span>
          </div>
          {filteredEntries.length > 0 ? (
            <div className="commentary-panel__entries">
              {filteredEntries.map((item, index) => (
                <EntryArticle
                  key={`${item.citation}-${index}`}
                  entry={item}
                  availability={ownedResult.availability}
                  onCopy={copyText}
                  searchMatched={Boolean(query)}
                  source={ownedResult.source ?? selectedSource}
                />
              ))}
            </div>
          ) : (
            <div className="commentary-panel__callout" role="status">
              No commentary notes match “{query}”.
            </div>
          )}
        </div>
      ) : null}

      {copyNotice.message && !expandedOpen ? (
        <p
          key={copyNotice.revision}
          className="commentary-panel__visually-hidden"
          role="status"
          aria-label="Copy status"
          aria-live="polite"
          aria-atomic="true"
        >
          {copyNotice.message}
        </p>
      ) : null}
      </div>

      <ExpandedCommentary
        open={expandedOpen}
        title={title}
        entries={filteredEntries}
        availability={ownedResult?.availability}
        onCopy={copyText}
        onClose={() => setExpanded(false)}
        openerRef={expandButtonRef}
        searchMatched={Boolean(query)}
        source={ownedResult?.source ?? selectedSource}
        copyNotice={copyNotice}
      />
    </section>
  )
}
