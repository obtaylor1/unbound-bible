import { useId, useMemo, useRef, useState } from 'react'
import {
  normalizeStudyReference,
  positiveStudyInteger,
  STUDY_TOOLS,
  studyReferenceKey,
} from './studyToolRegistry'
import useDialogFocus from './useDialogFocus'

const INLINE_TOOLS = STUDY_TOOLS.filter(({ kind }) => kind === 'inline')
const SELECTABLE_TOOLS = STUDY_TOOLS.filter(({ kind }) => ['inline', 'local'].includes(kind))
const CONTEXT_TOOL = INLINE_TOOLS[0]
const MAX_RENDER_DEPTH = 6
const MAX_RENDER_NODES = 200
const MAX_COLLECTION_ITEMS = 50
const MAX_STRING_LENGTH = 5000
const OMITTED_MESSAGE = 'Additional details omitted'
const DETAILS_ANNOUNCEMENT_IDS = new WeakMap()
let nextDetailsAnnouncementId = 1
const VERSE_MARKERS_KEY = 'unbound_verse_markers'

function readVerseMarkers() {
  try {
    const value = JSON.parse(window.localStorage.getItem(VERSE_MARKERS_KEY) || '{}')
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
  } catch {
    return {}
  }
}

function MarkerPanel({ headingId, reference, referenceKey }) {
  const [markers, setMarkers] = useState(readVerseMarkers)
  const [message, setMessage] = useState('')
  const entry = markers[referenceKey] ?? {}

  const toggle = (kind) => {
    const active = !entry[kind]
    const nextEntry = {
      reference: reference.label,
      highlighted: Boolean(entry.highlighted),
      bookmarked: Boolean(entry.bookmarked),
      [kind]: active,
    }
    const next = { ...markers, [referenceKey]: nextEntry }
    if (!nextEntry.highlighted && !nextEntry.bookmarked) delete next[referenceKey]
    window.localStorage.setItem(VERSE_MARKERS_KEY, JSON.stringify(next))
    setMarkers(next)
    const action = kind === 'highlighted' ? 'Highlight' : 'Bookmark'
    setMessage(`${active ? `${action}ed` : `${action} removed from`} ${reference.label}`)
  }

  return (
    <section className="study-tools__content" role="region" aria-labelledby={headingId}>
      <h3 id={headingId}>Highlights and bookmarks</h3>
      {!reference.hasVerse ? (
        <p className="study-tools__empty">Select a verse before adding a highlight or bookmark.</p>
      ) : (
        <>
          <p className="study-tools__prose">Save <strong>{reference.label}</strong> on this device.</p>
          <div className="study-tools__marker-actions">
            <button
              type="button"
              className="study-tools__control"
              aria-label={`Highlight ${reference.label}`}
              aria-pressed={Boolean(entry.highlighted)}
              onClick={() => toggle('highlighted')}
            >
              {entry.highlighted ? 'Remove highlight' : 'Highlight verse'}
            </button>
            <button
              type="button"
              className="study-tools__control"
              aria-label={`Bookmark ${reference.label}`}
              aria-pressed={Boolean(entry.bookmarked)}
              onClick={() => toggle('bookmarked')}
            >
              {entry.bookmarked ? 'Remove bookmark' : 'Bookmark verse'}
            </button>
          </div>
          <p role="status" aria-live="polite" aria-atomic="true">{message}</p>
        </>
      )}
    </section>
  )
}

function cleanText(value) {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || null
  }
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return null
}

function limitedText(value, state) {
  const text = cleanText(value)
  if (!text) return null
  if (text.length <= MAX_STRING_LENGTH) return text
  if (state) state.omitted = true
  return `${text.slice(0, MAX_STRING_LENGTH)}…`
}

function announcementRevision(details, explicitRevision) {
  if (explicitRevision !== undefined) {
    try {
      return `request-${String(explicitRevision)}`
    } catch {
      return 'request-explicit'
    }
  }
  if (details && (typeof details === 'object' || typeof details === 'function')) {
    if (!DETAILS_ANNOUNCEMENT_IDS.has(details)) {
      DETAILS_ANNOUNCEMENT_IDS.set(details, nextDetailsAnnouncementId)
      nextDetailsAnnouncementId += 1
    }
    return `details-${DETAILS_ANNOUNCEMENT_IDS.get(details)}`
  }
  return `details-${details == null ? 'empty' : typeof details}`
}

function readableLabel(value) {
  const text = cleanText(value)
  if (!text) return null
  const words = text.slice(0, 120).replace(/[_-]+/g, ' ').toLocaleLowerCase()
  return words.charAt(0).toLocaleUpperCase() + words.slice(1)
}

function translationLabel(value) {
  const text = cleanText(value)
  if (!text) return null
  return /^[a-z0-9]+$/i.test(text) && text.length <= 6
    ? text.toUpperCase()
    : readableLabel(text)
}

function isUserFacingKey(key) {
  const normalized = key
    .replace(/([a-z])([A-Z])/g, '$1_$2')
    .toLocaleLowerCase()
  return !(
    normalized === 'id'
    || normalized.endsWith('_id')
    || normalized === 'created_at'
    || normalized === 'updated_at'
    || normalized === 'deleted_at'
    || normalized.startsWith('internal')
    || normalized.startsWith('system')
    || normalized.startsWith('__')
  )
}

function safeEntries(value) {
  try {
    return Object.entries(value)
  } catch {
    return []
  }
}

function normalizeGeneralValue(value, sharedState) {
  const state = sharedState ?? { nodes: 0, omitted: false }
  const omissionBefore = state.omitted

  function normalizeNode(current, depth, path) {
    const scalar = cleanText(current)
    if (scalar) {
      if (state.nodes >= MAX_RENDER_NODES) {
        state.omitted = true
        return null
      }
      state.nodes += 1
      if (scalar.length > MAX_STRING_LENGTH) {
        state.omitted = true
        return { kind: 'text', text: `${scalar.slice(0, MAX_STRING_LENGTH)}…` }
      }
      return { kind: 'text', text: scalar }
    }

    if (!current || typeof current !== 'object') return null
    if (depth >= MAX_RENDER_DEPTH || path.has(current)) {
      state.omitted = true
      return null
    }
    if (state.nodes >= MAX_RENDER_NODES) {
      state.omitted = true
      return null
    }

    state.nodes += 1
    const nextPath = new Set(path)
    nextPath.add(current)

    if (Array.isArray(current)) {
      if (current.length > MAX_COLLECTION_ITEMS) state.omitted = true
      const items = current
        .slice(0, MAX_COLLECTION_ITEMS)
        .map((entry) => normalizeNode(entry, depth + 1, nextPath))
        .filter(Boolean)
      return items.length ? { kind: 'list', items } : null
    }

    const entries = safeEntries(current)
      .filter(([key]) => isUserFacingKey(key))
    if (entries.length > MAX_COLLECTION_ITEMS) state.omitted = true
    const normalizedEntries = entries
      .slice(0, MAX_COLLECTION_ITEMS)
      .map(([key, entry]) => [
        readableLabel(key),
        normalizeNode(entry, depth + 1, nextPath),
      ])
      .filter(([label, entry]) => label && entry)
    return normalizedEntries.length
      ? { kind: 'record', entries: normalizedEntries }
      : null
  }

  return {
    node: normalizeNode(value, 0, new Set()),
    omitted: state.omitted && !omissionBefore,
  }
}

function GeneralNode({ node, block = false }) {
  if (!node) return null
  if (node.kind === 'text') {
    return block
      ? <p className="study-tools__prose">{node.text}</p>
      : node.text
  }
  if (node.kind === 'list') {
    return (
      <ul className="study-tools__list">
        {node.items.map((item, index) => (
          <li key={index}><GeneralNode node={item} /></li>
        ))}
      </ul>
    )
  }
  return (
    <dl className="study-tools__record-details">
      {node.entries.map(([label, entry], index) => (
        <div key={`${label}-${index}`}>
          <dt>{label}</dt>
          <dd><GeneralNode node={entry} /></dd>
        </div>
      ))}
    </dl>
  )
}

function recordEntries(record, excluded = [], state) {
  if (!record || typeof record !== 'object' || Array.isArray(record)) return []
  const excludedKeys = new Set(excluded)
  const entries = safeEntries(record)
    .filter(([key]) => !excludedKeys.has(key) && isUserFacingKey(key))
  if (state && entries.length > MAX_COLLECTION_ITEMS) state.omitted = true
  return entries.slice(0, MAX_COLLECTION_ITEMS)
    .map(([key, value]) => [readableLabel(key), normalizeGeneralValue(value, state)])
    .filter(([key, result]) => key && result.node)
}

function usableValue(value) {
  return Boolean(normalizeGeneralValue(value).node)
}

function RecordDetails({ entries }) {
  if (!entries.length) return null
  return (
    <dl className="study-tools__record-details">
      {entries.map(([label, result], index) => (
        <div key={`${label}-${index}`}>
          <dt>{label}</dt>
          <dd>
            <GeneralNode node={result.node} />
            {result.omitted && <OmittedMarker />}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function GeneralContent({ value }) {
  const result = normalizeGeneralValue(value)
  if (!result.node) return result.omitted ? <OmittedMarker /> : null
  return (
    <>
      <GeneralNode node={result.node} block />
      {result.omitted && <OmittedMarker />}
    </>
  )
}

function translationRows(value) {
  const state = { omitted: false }
  const boundedText = (candidate) => limitedText(candidate, state)
  const fromArray = (entries) => {
    if (entries.length > MAX_COLLECTION_ITEMS) state.omitted = true
    return entries.slice(0, MAX_COLLECTION_ITEMS).flatMap((entry, index) => {
      const scalar = boundedText(entry)
      if (scalar) return [{ name: `Translation ${index + 1}`, text: scalar, detail: null }]
      if (!entry || typeof entry !== 'object') return []
      const name = boundedText(
        entry.code ?? entry.translation ?? entry.name ?? entry.label,
      )
      const text = boundedText(entry.text ?? entry.content ?? entry.value)
      const detail = boundedText(entry.language ?? entry.title)
      return name && (text || detail) ? [{ name, text, detail }] : []
    })
  }
  if (Array.isArray(value)) return { rows: fromArray(value), omitted: state.omitted }

  if (!value || typeof value !== 'object') {
    const scalar = boundedText(value)
    return {
      rows: scalar ? [{ name: 'Translation', text: scalar, detail: null }] : [],
      omitted: state.omitted,
    }
  }

  if ('code' in value || 'translation' in value || 'name' in value) {
    return { rows: fromArray([value]), omitted: state.omitted }
  }

  const entries = safeEntries(value)
  if (entries.length > MAX_COLLECTION_ITEMS) state.omitted = true
  const rows = entries.slice(0, MAX_COLLECTION_ITEMS).flatMap(([code, entry]) => {
    const scalar = boundedText(entry)
    if (scalar) return [{ name: code, text: scalar, detail: null }]
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return []
    const text = boundedText(entry.text ?? entry.content ?? entry.value)
    const detail = boundedText(entry.language ?? entry.name ?? entry.title)
    return text || detail ? [{ name: code, text, detail }] : []
  })
  return { rows, omitted: state.omitted }
}

function TranslationContent({ value, label }) {
  const { rows, omitted } = translationRows(value)
  if (!rows.length) return null
  return (
    <>
      <div className="study-tools__table-wrap">
        <table aria-label={label} className="study-tools__table">
          <thead>
            <tr>
              <th scope="col">Translation</th>
              <th scope="col">Text</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ name, text, detail }, index) => (
              <tr key={`${name}-${index}`}>
                <th scope="row">
                  {translationLabel(name)}
                  {detail && <small>{detail}</small>}
                </th>
                <td>{text ?? 'Translation text unavailable'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {omitted && <OmittedMarker />}
    </>
  )
}

function languageRecords(value) {
  const allCandidates = Array.isArray(value) ? value : [value]
  const state = {
    nodes: 0,
    omitted: allCandidates.length > MAX_COLLECTION_ITEMS,
  }
  const records = allCandidates.slice(0, MAX_COLLECTION_ITEMS).flatMap((entry) => {
    const scalar = limitedText(entry, state)
    if (scalar) return [{ title: scalar, entries: [] }]
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return []
    const title = limitedText(
      entry.text ?? entry.word_text ?? entry.word ?? entry.term ?? entry.title,
      state,
    )
    const entries = recordEntries(
      entry,
      ['text', 'word_text', 'word', 'term', 'title'],
      state,
    )
    return title || entries.length ? [{ title: title ?? 'Language insight', entries }] : []
  })
  return { records, omitted: state.omitted }
}

function LanguageContent({ value }) {
  const { records, omitted } = languageRecords(value)
  if (!records.length) return null
  return (
    <>
      <dl className="study-tools__definitions" data-testid="study-tool-description-list">
        {records.map(({ title, entries }, index) => (
          <div key={`${title}-${index}`}>
            <dt>{title}</dt>
            <dd>
              {entries.length ? <RecordDetails entries={entries} /> : 'Language detail'}
            </dd>
          </div>
        ))}
      </dl>
      {omitted && <OmittedMarker />}
    </>
  )
}

function crossReferenceRecords(value) {
  const allCandidates = Array.isArray(value) ? value : [value]
  const state = {
    nodes: 0,
    omitted: allCandidates.length > MAX_COLLECTION_ITEMS,
  }
  const records = allCandidates.slice(0, MAX_COLLECTION_ITEMS).flatMap((entry) => {
    const scalar = limitedText(entry, state)
    if (scalar) return [{ title: scalar, text: null, description: null, details: [] }]
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return []
    const book = limitedText(entry.book ?? entry.target_book, state)
    const chapter = positiveStudyInteger(entry.chapter ?? entry.target_chapter)
    const verse = positiveStudyInteger(entry.verse ?? entry.target_verse)
    const derivedReference = book && chapter
      ? `${book} ${chapter}${verse ? `:${verse}` : ''}`
      : null
    const title = limitedText(entry.reference ?? entry.title, state) ?? derivedReference
    const text = limitedText(entry.text ?? entry.target_text ?? entry.content, state)
    const description = limitedText(entry.description ?? entry.context, state)
    const details = recordEntries(entry, [
      'book', 'target_book', 'chapter', 'target_chapter', 'verse', 'target_verse',
      'reference', 'title', 'text', 'target_text', 'content', 'description', 'context',
    ], state)
    return title || text || description || details.length
      ? [{ title: title ?? 'Related passage', text, description, details }]
      : []
  })
  return { records, omitted: state.omitted }
}

function CrossReferenceContent({ value }) {
  const { records, omitted } = crossReferenceRecords(value)
  if (!records.length) return null
  return (
    <>
      <ul className="study-tools__list study-tools__references">
        {records.map(({ title, text, description, details }, index) => (
          <li key={`${title}-${index}`}>
            <strong>{title}</strong>
            {text && <p>{text}</p>}
            {description && <p>{description}</p>}
            <RecordDetails entries={details} />
          </li>
        ))}
      </ul>
      {omitted && <OmittedMarker />}
    </>
  )
}

function OmittedMarker() {
  return <p className="study-tools__omitted">{OMITTED_MESSAGE}</p>
}

function detailValue(details, tool) {
  if (!details || typeof details !== 'object' || Array.isArray(details)) return null
  for (const key of tool.detailKeys) {
    if (usableValue(details[key])) return details[key]
  }
  return null
}

function coordinateOwnership(details, normalizedReference) {
  if (!details || typeof details !== 'object' || Array.isArray(details)) return 'none'
  const owns = (key) => Object.prototype.hasOwnProperty.call(details, key)
  if (!['book', 'chapter', 'verse'].some(owns)) return 'none'

  const requiredKeys = normalizedReference.hasVerse
    ? ['book', 'chapter', 'verse']
    : ['book', 'chapter']
  if (!requiredKeys.every(owns)) return 'mismatch'
  if (!normalizedReference.hasVerse && owns('verse')) return 'mismatch'

  const book = cleanText(details.book)
  const chapter = positiveStudyInteger(details.chapter)
  const verse = normalizedReference.hasVerse
    ? positiveStudyInteger(details.verse)
    : null
  return (
    book?.toLocaleLowerCase() === normalizedReference.value.book?.toLocaleLowerCase()
    && chapter === normalizedReference.value.chapter
    && (!normalizedReference.hasVerse || verse === normalizedReference.value.verse)
  )
    ? 'match'
    : 'mismatch'
}

function resultLabel(count, verified = false) {
  return `${count} ${verified ? 'verified ' : ''}${count === 1 ? 'result' : 'results'}`
}

function InlinePanel({
  tool,
  value,
  hasVerse,
  headingId,
  detailState,
  referenceLabel,
  announcementRevision,
}) {
  let content
  let hasContent
  let resultCount
  if (tool.id === 'compare') {
    const { rows } = translationRows(value)
    hasContent = rows.length > 0
    resultCount = rows.filter(({ text }) => text).length
    content = <TranslationContent value={value} label={tool.label} />
  } else if (tool.id === 'languages') {
    const { records } = languageRecords(value)
    hasContent = records.length > 0
    resultCount = records.length
    content = <LanguageContent value={value} />
  } else if (tool.id === 'cross-references') {
    const { records } = crossReferenceRecords(value)
    hasContent = records.length > 0
    resultCount = records.length
    content = <CrossReferenceContent value={value} />
  } else {
    const normalized = normalizeGeneralValue(value)
    hasContent = Boolean(normalized.node)
    resultCount = normalized.node?.kind === 'list'
      ? normalized.node.items.length
      : (normalized.node ? 1 : 0)
    content = <GeneralContent value={value} />
  }

  let status
  if (detailState === 'loading') {
    status = `Study information is loading for ${referenceLabel}.`
  } else if (detailState === 'stale') {
    status = `Study information is updating for ${referenceLabel}.`
  } else if (detailState === 'error') {
    status = `Verified study information could not be loaded for ${referenceLabel}.`
  } else if (detailState === 'mismatch') {
    status = `Verified study information is unavailable for ${referenceLabel}.`
  } else if (!hasContent) {
    status = `No verified ${tool.label.toLocaleLowerCase()} information is available for this ${hasVerse ? 'verse' : 'passage'}.`
  } else {
    status = `${tool.label} updated — ${resultLabel(resultCount, tool.id === 'compare')}`
  }

  return (
    <section
      className="study-tools__content"
      aria-labelledby={headingId}
      aria-busy={detailState === 'stale' || detailState === 'loading'}
    >
      <h3 id={headingId}>{tool.label}</h3>
      <p
        className={hasContent && detailState === 'ready'
          ? 'study-tools__visually-hidden'
          : 'study-tools__empty'}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span key={`${tool.id}-${detailState}-${announcementRevision}`}>
          {status}
        </span>
      </p>
      {detailState === 'ready' && hasContent ? content : null}
    </section>
  )
}

export default function StudyTools({
  open,
  reference,
  details,
  detailsReferenceKey,
  detailsRevision,
  detailsStatus,
  onClose,
  onNavigate,
}) {
  const titleId = useId()
  const unavailableId = useId()
  const panelId = useId()
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const normalizedReference = useMemo(
    () => normalizeStudyReference(reference),
    [reference],
  )
  const referenceKey = studyReferenceKey(reference)
  const ownershipRef = useRef({
    lastReferenceKey: referenceKey,
    referenceChanged: false,
  })
  const wasOpenRef = useRef(open)
  const [activeSelection, setActiveSelection] = useState(() => ({
    id: CONTEXT_TOOL.id,
    referenceKey,
  }))

  useDialogFocus({
    open,
    containerRef: dialogRef,
    initialRef: closeRef,
    onClose,
  })

  if (ownershipRef.current.lastReferenceKey !== referenceKey) {
    ownershipRef.current.lastReferenceKey = referenceKey
    ownershipRef.current.referenceChanged = true
  }
  const freshOpen = open && !wasOpenRef.current
  wasOpenRef.current = open
  const resetActiveTool = activeSelection.referenceKey !== referenceKey || freshOpen
  if (
    resetActiveTool
    && (
      activeSelection.id !== CONTEXT_TOOL.id
      || activeSelection.referenceKey !== referenceKey
    )
  ) {
    setActiveSelection({ id: CONTEXT_TOOL.id, referenceKey })
  }
  const effectiveActiveToolId = resetActiveTool
    ? CONTEXT_TOOL.id
    : activeSelection.id

  const normalizedStatus = ['loading', 'ready', 'error'].includes(detailsStatus)
    ? detailsStatus
    : 'ready'
  const coordinates = coordinateOwnership(details, normalizedReference)
  const hasExplicitKey = typeof detailsReferenceKey === 'string'
  const detailsKeyToken = hasExplicitKey ? detailsReferenceKey : 'implicit'
  const liveRevision = announcementRevision(details, detailsRevision)
  let detailState = 'ready'
  if (normalizedStatus === 'loading') detailState = 'loading'
  else if (normalizedStatus === 'error') detailState = 'error'
  else if (details == null) detailState = 'ready'
  else if (hasExplicitKey && detailsReferenceKey !== referenceKey) detailState = 'stale'
  else if (coordinates === 'mismatch') detailState = 'mismatch'
  else if (
    !hasExplicitKey
    && coordinates === 'none'
    && ownershipRef.current.referenceChanged
  ) detailState = 'stale'

  if (!open) return null

  const activeTool = SELECTABLE_TOOLS.find(({ id }) => id === effectiveActiveToolId)
    ?? CONTEXT_TOOL
  const value = activeTool.kind === 'inline' && detailState === 'ready'
    ? detailValue(details, activeTool)
    : null
  const navigationAvailable = typeof onNavigate === 'function'

  return (
    <div className="study-tools" aria-hidden="false">
      <div className="study-tools__backdrop" aria-hidden="true" />
      <aside
        ref={dialogRef}
        className="study-tools__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <span className="study-tools__drag-handle" aria-hidden="true" />
        <header className="study-tools__header">
          <div>
            <p className="study-tools__eyebrow">Study Tools</p>
            <h2 id={titleId}>{normalizedReference.label}</h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="study-tools__control study-tools__close"
            aria-label="Close study tools"
            onClick={() => {
              if (typeof onClose === 'function') onClose()
            }}
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <nav className="study-tools__choices" aria-label="Study tool choices">
          {STUDY_TOOLS.map((tool) => {
            const selectable = ['inline', 'local'].includes(tool.kind)
            const unavailable = tool.kind === 'route' && !navigationAvailable
            return (
              <button
                key={tool.id}
                type="button"
                className={`study-tools__control study-tools__choice${selectable && tool.id === activeTool.id ? ' study-tools__choice--active' : ''}`}
                aria-pressed={selectable ? tool.id === activeTool.id : undefined}
                aria-describedby={unavailable ? unavailableId : undefined}
                disabled={unavailable}
                onClick={() => {
                  if (selectable) setActiveSelection({ id: tool.id, referenceKey })
                  else if (navigationAvailable) onNavigate(tool.page, normalizedReference.value)
                }}
              >
                {tool.label}
              </button>
            )
          })}
        </nav>
        <span id={unavailableId} className="study-tools__visually-hidden">
          Navigation unavailable
        </span>

        {activeTool.kind === 'local' ? (
          <MarkerPanel
            headingId={`${panelId}-${activeTool.id}`}
            reference={normalizedReference}
            referenceKey={referenceKey}
          />
        ) : (
          <InlinePanel
            tool={activeTool}
            value={value}
            hasVerse={normalizedReference.hasVerse}
            headingId={`${panelId}-${activeTool.id}`}
            detailState={detailState}
            referenceLabel={normalizedReference.label}
            announcementRevision={`${referenceKey}-${normalizedStatus}-${detailsKeyToken}-${liveRevision}`}
          />
        )}
      </aside>
    </div>
  )
}
