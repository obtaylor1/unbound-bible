import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { STUDY_TOOLS } from './studyToolRegistry'
import useDialogFocus from './useDialogFocus'

const INLINE_TOOLS = STUDY_TOOLS.filter(({ kind }) => kind === 'inline')
const CONTEXT_TOOL = INLINE_TOOLS[0]

function cleanText(value) {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || null
  }
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return null
}

function positiveInteger(value) {
  if (
    typeof value === 'string'
    && (!value.trim() || !/^\d+$/.test(value.trim()))
  ) return null
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? number : null
}

function normalizeReference(reference) {
  if (!reference || typeof reference !== 'object' || Array.isArray(reference)) {
    return { value: {}, label: 'Current passage', hasVerse: false }
  }

  const book = cleanText(reference.book)
  const chapter = positiveInteger(reference.chapter)
  const verse = positiveInteger(reference.verse)

  if (!book || !chapter) {
    return { value: {}, label: 'Current passage', hasVerse: false }
  }

  const value = verse ? { book, chapter, verse } : { book, chapter }
  return {
    value,
    label: `${book} ${chapter}${verse ? `:${verse}` : ''}`,
    hasVerse: Boolean(verse),
  }
}

function readableLabel(value) {
  const text = cleanText(value)
  if (!text) return null
  const words = text.replace(/[_-]+/g, ' ').toLocaleLowerCase()
  return words.charAt(0).toLocaleUpperCase() + words.slice(1)
}

function translationLabel(value) {
  const text = cleanText(value)
  if (!text) return null
  return /^[a-z0-9]+$/i.test(text) && text.length <= 6
    ? text.toUpperCase()
    : readableLabel(text)
}

function recordEntries(record, excluded = []) {
  if (!record || typeof record !== 'object' || Array.isArray(record)) return []
  const excludedKeys = new Set(excluded)
  return Object.entries(record)
    .filter(([key]) => !excludedKeys.has(key))
    .map(([key, value]) => [readableLabel(key), value])
    .filter(([key, value]) => key && usableValue(value))
}

function usableValue(value, seen = new Set()) {
  if (cleanText(value)) return true
  if (!value || typeof value !== 'object' || seen.has(value)) return false
  const nextSeen = new Set(seen)
  nextSeen.add(value)
  if (Array.isArray(value)) return value.some((entry) => usableValue(entry, nextSeen))
  return Object.values(value).some((entry) => usableValue(entry, nextSeen))
}

function RecordDetails({ entries }) {
  if (!entries.length) return null
  return (
    <dl className="study-tools__record-details">
      {entries.map(([label, value], index) => (
        <div key={`${label}-${index}`}>
          <dt>{label}</dt>
          <dd>{cleanText(value) ?? <GeneralContent value={value} />}</dd>
        </div>
      ))}
    </dl>
  )
}

function GeneralContent({ value }) {
  const scalar = cleanText(value)
  if (scalar) return <p className="study-tools__prose">{scalar}</p>

  if (Array.isArray(value)) {
    const entries = value.filter((entry) => usableValue(entry))
    if (!entries.length) return null
    return (
      <ul className="study-tools__list">
        {entries.map((entry, index) => {
          const entryScalar = cleanText(entry)
          if (entryScalar) return <li key={`${entryScalar}-${index}`}>{entryScalar}</li>
          const title = cleanText(entry.title ?? entry.label ?? entry.term ?? entry.word)
          const text = cleanText(entry.text ?? entry.content ?? entry.description)
          const details = recordEntries(
            entry,
            ['title', 'label', 'term', 'word', 'text', 'content', 'description'],
          )
          return (
            <li key={`${title ?? 'entry'}-${index}`}>
              {title && <strong>{title}</strong>}
              {text && <p>{text}</p>}
              <RecordDetails entries={details} />
            </li>
          )
        })}
      </ul>
    )
  }

  const entries = recordEntries(value)
  return entries.length ? (
    <RecordDetails entries={entries} />
  ) : null
}

function translationRows(value) {
  if (Array.isArray(value)) {
    return value.flatMap((entry, index) => {
      const scalar = cleanText(entry)
      if (scalar) return [{ name: `Translation ${index + 1}`, text: scalar, detail: null }]
      if (!entry || typeof entry !== 'object') return []
      const name = cleanText(
        entry.code ?? entry.translation ?? entry.name ?? entry.label,
      )
      const text = cleanText(entry.text ?? entry.content ?? entry.value)
      const detail = cleanText(entry.language ?? entry.title)
      return name && (text || detail) ? [{ name, text, detail }] : []
    })
  }

  if (!value || typeof value !== 'object') {
    const scalar = cleanText(value)
    return scalar ? [{ name: 'Translation', text: scalar, detail: null }] : []
  }

  return Object.entries(value).flatMap(([code, entry]) => {
    const scalar = cleanText(entry)
    if (scalar) return [{ name: code, text: scalar, detail: null }]
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return []
    const text = cleanText(entry.text ?? entry.content ?? entry.value)
    const detail = cleanText(entry.language ?? entry.name ?? entry.title)
    return text || detail ? [{ name: code, text, detail }] : []
  })
}

function TranslationContent({ value, label }) {
  const rows = translationRows(value)
  if (!rows.length) return null
  return (
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
              <td>{text ?? 'Details available'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function languageRecords(value) {
  const candidates = Array.isArray(value) ? value : [value]
  return candidates.flatMap((entry) => {
    const scalar = cleanText(entry)
    if (scalar) return [{ title: scalar, entries: [] }]
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return []
    const title = cleanText(
      entry.text ?? entry.word_text ?? entry.word ?? entry.term ?? entry.title,
    )
    const entries = recordEntries(
      entry,
      ['text', 'word_text', 'word', 'term', 'title'],
    )
    return title || entries.length ? [{ title: title ?? 'Language insight', entries }] : []
  })
}

function LanguageContent({ value }) {
  const records = languageRecords(value)
  if (!records.length) return null
  return (
    <dl className="study-tools__definitions" data-testid="study-tool-description-list">
      {records.map(({ title, entries }, index) => (
        <div key={`${title}-${index}`}>
          <dt>{title}</dt>
          <dd>
            {entries.length
              ? (
                <dl className="study-tools__record-details">
                  {entries.map(([label, entryValue], entryIndex) => (
                    <div key={`${label}-${entryIndex}`}>
                      <dt>{label}</dt>
                      <dd>
                        {cleanText(entryValue) ?? <GeneralContent value={entryValue} />}
                      </dd>
                    </div>
                  ))}
                </dl>
              )
              : 'Language detail'}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function crossReferenceRecords(value) {
  const candidates = Array.isArray(value) ? value : [value]
  return candidates.flatMap((entry) => {
    const scalar = cleanText(entry)
    if (scalar) return [{ title: scalar, text: null, description: null, details: [] }]
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return []
    const book = cleanText(entry.book ?? entry.target_book)
    const chapter = positiveInteger(entry.chapter ?? entry.target_chapter)
    const verse = positiveInteger(entry.verse ?? entry.target_verse)
    const derivedReference = book && chapter
      ? `${book} ${chapter}${verse ? `:${verse}` : ''}`
      : null
    const title = cleanText(entry.reference ?? entry.title) ?? derivedReference
    const text = cleanText(entry.text ?? entry.target_text ?? entry.content)
    const description = cleanText(entry.description ?? entry.context)
    const details = recordEntries(entry, [
      'book', 'target_book', 'chapter', 'target_chapter', 'verse', 'target_verse',
      'reference', 'title', 'text', 'target_text', 'content', 'description', 'context',
    ])
    return title || text || description || details.length
      ? [{ title: title ?? 'Related passage', text, description, details }]
      : []
  })
}

function CrossReferenceContent({ value }) {
  const records = crossReferenceRecords(value)
  if (!records.length) return null
  return (
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
  )
}

function detailValue(details, tool) {
  if (!details || typeof details !== 'object' || Array.isArray(details)) return null
  for (const key of tool.detailKeys) {
    if (usableValue(details[key])) return details[key]
  }
  return null
}

function InlinePanel({ tool, value, hasVerse, headingId }) {
  let content = null
  let hasContent = false
  if (tool.id === 'compare') {
    hasContent = translationRows(value).length > 0
    content = <TranslationContent value={value} label={tool.label} />
  } else if (tool.id === 'languages') {
    hasContent = languageRecords(value).length > 0
    content = <LanguageContent value={value} />
  } else if (tool.id === 'cross-references') {
    hasContent = crossReferenceRecords(value).length > 0
    content = <CrossReferenceContent value={value} />
  } else {
    hasContent = usableValue(value)
    content = <GeneralContent value={value} />
  }

  return (
    <section className="study-tools__content" aria-labelledby={headingId}>
      <h3 id={headingId}>{tool.label}</h3>
      {hasContent ? content : (
        <p className="study-tools__empty">
          No verified {tool.label.toLocaleLowerCase()} information is available for this {hasVerse ? 'verse' : 'passage'}.
        </p>
      )}
    </section>
  )
}

export default function StudyTools({
  open,
  reference,
  details,
  onClose,
  onNavigate,
}) {
  const titleId = useId()
  const unavailableId = useId()
  const panelId = useId()
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const [activeToolId, setActiveToolId] = useState(CONTEXT_TOOL.id)
  const normalizedReference = useMemo(
    () => normalizeReference(reference),
    [reference],
  )
  const referenceKey = [
    normalizedReference.value.book ?? '',
    normalizedReference.value.chapter ?? '',
    normalizedReference.value.verse ?? '',
  ].join(':')

  useDialogFocus({
    open,
    containerRef: dialogRef,
    initialRef: closeRef,
    onClose,
  })

  useEffect(() => {
    if (open) setActiveToolId(CONTEXT_TOOL.id)
  }, [open, referenceKey])

  if (!open) return null

  const activeTool = INLINE_TOOLS.find(({ id }) => id === activeToolId) ?? CONTEXT_TOOL
  const value = detailValue(details, activeTool)
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
            const inline = tool.kind === 'inline'
            const unavailable = !inline && !navigationAvailable
            return (
              <button
                key={tool.id}
                type="button"
                className={`study-tools__control study-tools__choice${inline && tool.id === activeTool.id ? ' study-tools__choice--active' : ''}`}
                aria-pressed={inline ? tool.id === activeTool.id : undefined}
                aria-describedby={unavailable ? unavailableId : undefined}
                disabled={unavailable}
                onClick={() => {
                  if (inline) setActiveToolId(tool.id)
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

        <p className="study-tools__visually-hidden" role="status" aria-live="polite">
          {activeTool.label} selected
        </p>
        <InlinePanel
          tool={activeTool}
          value={value}
          hasVerse={normalizedReference.hasVerse}
          headingId={`${panelId}-${activeTool.id}`}
        />
      </aside>
    </div>
  )
}
