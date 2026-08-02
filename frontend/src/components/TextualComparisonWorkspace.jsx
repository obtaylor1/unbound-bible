import { useEffect, useMemo, useRef, useState } from 'react'
import './TextualComparisonWorkspace.css'
import ShareStudyModal from './ShareStudyModal'
import ComparisonToolbar from './textualComparison/ComparisonToolbar'
import TranslationSelector from './textualComparison/TranslationSelector'
import ComparisonSummary from './textualComparison/ComparisonSummary'
import TranslationComparisonCard from './textualComparison/TranslationComparisonCard'
import ComparisonStudyDrawer from './textualComparison/ComparisonStudyDrawer'
import {
  DEFAULT_TRANSLATIONS,
  MAX_TRANSLATIONS,
  TRANSLATION_BY_KEY,
  applyTranslationToggle,
  buildSourceState,
  diffWords,
  summarizeComparison,
} from './textualComparison/comparisonModel'

const BOOK_CHAPTERS = {
  Genesis: 50, Exodus: 40, Leviticus: 27, Numbers: 36, Deuteronomy: 34,
  Joshua: 24, Judges: 21, Ruth: 4, '1 Samuel': 31, '2 Samuel': 24,
  '1 Kings': 22, '2 Kings': 25, '1 Chronicles': 29, '2 Chronicles': 36,
  Ezra: 10, Nehemiah: 13, Esther: 10, Job: 42, Psalms: 150, Proverbs: 31,
  Ecclesiastes: 12, 'Song of Solomon': 8, Isaiah: 66, Jeremiah: 52,
  Lamentations: 5, Ezekiel: 48, Daniel: 12, Hosea: 14, Joel: 3, Amos: 9,
  Obadiah: 1, Jonah: 4, Micah: 7, Nahum: 3, Habakkuk: 3, Zephaniah: 3,
  Haggai: 2, Zechariah: 14, Malachi: 4, Matthew: 28, Mark: 16, Luke: 24,
  John: 21, Acts: 28, Romans: 16, '1 Corinthians': 16, '2 Corinthians': 13,
  Galatians: 6, Ephesians: 6, Philippians: 4, Colossians: 4,
  '1 Thessalonians': 5, '2 Thessalonians': 3, '1 Timothy': 6, '2 Timothy': 4,
  Titus: 3, Philemon: 1, Hebrews: 13, James: 5, '1 Peter': 5, '2 Peter': 3,
  '1 John': 5, '2 John': 1, '3 John': 1, Jude: 1, Revelation: 22,
  '1 Enoch': 108, Enoch: 108, Jubilees: 50, '1 Meqabyan': 36,
  '2 Meqabyan': 22, '3 Meqabyan': 10, Tobit: 14, Judith: 16,
  'Wisdom of Solomon': 19, Sirach: 51, Baruch: 5, '1 Maccabees': 16,
  '2 Maccabees': 15, '1 Esdras': 9, '2 Esdras': 16, 'Psalm 151': 1,
}

function safeStoredList(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

function RequestState({ status, onRetry }) {
  if (status === 'loading') {
    return (
      <div className="comparison-request-state" role="status">
        <span className="comparison-loader" aria-hidden="true" />
        <h2>Loading scripture translations…</h2>
        <p>Gathering the selected passage and available sources.</p>
      </div>
    )
  }
  if (status === 'error' || status === 'offline') {
    return (
      <div className="comparison-request-state is-error" role="alert">
        <span aria-hidden="true">!</span>
        <h2>We could not load this passage</h2>
        <p>{status === 'offline' ? 'Your device appears to be offline.' : 'The scripture service did not return this passage.'}</p>
        <button type="button" onClick={onRetry}>Try again</button>
      </div>
    )
  }
  return (
    <div className="comparison-request-state">
      <h2>No text is available for this passage</h2>
      <p>Choose another book, chapter, or source to continue.</p>
    </div>
  )
}

function ChapterComparison({
  book,
  chapter,
  verses,
  selectedTranslations,
  baseTranslation,
  rows,
  highlightDifferences,
}) {
  const getText = (key, verse) => {
    const source = TRANSLATION_BY_KEY[key]
    return rows.find((row) => (
      Number(row.verse) === Number(verse)
      && String(row.translation).toLocaleLowerCase() === source?.code.toLocaleLowerCase()
    ))?.text ?? null
  }

  return (
    <section className="comparison-chapter" aria-labelledby="comparison-chapter-title">
      <header>
        <p className="compare-eyebrow">Aligned chapter view</p>
        <h2 id="comparison-chapter-title">{book} chapter {chapter} comparison</h2>
        <p>Each row keeps the same verse aligned across the selected sources.</p>
      </header>
      <div className="comparison-chapter-table">
        {verses.map((verse) => {
          const baseText = getText(baseTranslation, verse) ?? ''
          return (
            <section className="comparison-chapter-row" key={verse} aria-labelledby={`compare-verse-${verse}`}>
              <h3 id={`compare-verse-${verse}`}>Verse {verse}</h3>
              <div style={{ '--chapter-columns': selectedTranslations.length }}>
                {selectedTranslations.map((key) => {
                  const source = TRANSLATION_BY_KEY[key]
                  const text = getText(key, verse)
                  return (
                    <article key={key} aria-label={`${source.name}, verse ${verse}`}>
                      <strong>{source.code}</strong>
                      {text ? (
                        <p>{diffWords(text, highlightDifferences && baseText ? baseText : text).map((word, index) => (
                          word.differs ? <mark key={`${word.text}-${index}`}>{word.text}</mark> : word.text
                        ))}</p>
                      ) : <p className="chapter-source-empty">Text unavailable</p>}
                    </article>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>
    </section>
  )
}

export default function TextualComparisonWorkspace() {
  const [book, setBook] = useState('Genesis')
  const [chapter, setChapter] = useState('1')
  const [verse, setVerse] = useState('1')
  const [books, setBooks] = useState([])
  const [rows, setRows] = useState([])
  const [requestStatus, setRequestStatus] = useState('loading')
  const [requestRevision, setRequestRevision] = useState(0)
  const [selectedTranslations, setSelectedTranslations] = useState(DEFAULT_TRANSLATIONS)
  const [baseTranslation, setBaseTranslation] = useState(DEFAULT_TRANSLATIONS[0])
  const [highlightDifferences, setHighlightDifferences] = useState(true)
  const [viewMode, setViewMode] = useState('verse')
  const [studyToolsOpen, setStudyToolsOpen] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [studyTool, setStudyTool] = useState('insights')
  const [shareOpen, setShareOpen] = useState(false)
  const [bookmarks, setBookmarks] = useState(() => safeStoredList('unbound_bookmarks'))
  const [comparisonNote, setComparisonNote] = useState('')
  const [noteStatus, setNoteStatus] = useState('saved')
  const requestGeneration = useRef(0)
  const noteTimer = useRef(null)
  const studyTriggerRef = useRef(null)
  const sourcesTriggerRef = useRef(null)
  const sourcesPanelRef = useRef(null)
  const sourcesCloseRef = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/biblical-texts/available-books', { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Books unavailable')))
      .then((data) => {
        if (!controller.signal.aborted) setBooks(Array.isArray(data.books) ? data.books : [])
      })
      .catch((error) => {
        if (error?.name !== 'AbortError') setBooks([])
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const generation = ++requestGeneration.current
    setRequestStatus('loading')
    setRows([])
    fetch(`/api/biblical-texts/chapter-content?book=${encodeURIComponent(book)}&chapter=${chapter}`, {
      signal: controller.signal,
    })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Passage unavailable')))
      .then((data) => {
        if (controller.signal.aborted || generation !== requestGeneration.current) return
        const nextRows = Array.isArray(data.content) ? data.content : []
        setRows(nextRows)
        setRequestStatus(nextRows.length ? 'ready' : 'empty')

        const verseValues = [...new Set(nextRows.map((row) => String(row.verse)))]
        if (verseValues.length) {
          setVerse((current) => verseValues.includes(current) ? current : verseValues[0])
        }

      })
      .catch((error) => {
        if (controller.signal.aborted || generation !== requestGeneration.current || error?.name === 'AbortError') return
        setRequestStatus(navigator.onLine === false ? 'offline' : 'error')
      })
    return () => {
      controller.abort()
      requestGeneration.current += 1
    }
  }, [book, chapter, requestRevision]) // selected sources do not refetch passage data

  useEffect(() => {
    const key = `note-${book}-${chapter}-${verse}`
    setComparisonNote(localStorage.getItem(key) || '')
    setNoteStatus('saved')
  }, [book, chapter, verse])

  useEffect(() => () => {
    if (noteTimer.current) clearTimeout(noteTimer.current)
  }, [])

  useEffect(() => {
    if (!sourcesOpen) return undefined
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusTimer = setTimeout(() => sourcesCloseRef.current?.focus(), 0)
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setSourcesOpen(false)
        sourcesTriggerRef.current?.focus()
        return
      }
      if (event.key !== 'Tab') return
      const focusable = sourcesPanelRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled])',
      )
      if (!focusable?.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      clearTimeout(focusTimer)
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [sourcesOpen])

  const bookOptions = books.length ? books : Object.keys(BOOK_CHAPTERS)
  const chapterOptions = Array.from({ length: BOOK_CHAPTERS[book] ?? 1 }, (_, index) => index + 1)
  const verseOptions = useMemo(
    () => [...new Set(rows.map((row) => Number(row.verse)))].filter(Number.isFinite).sort((left, right) => left - right),
    [rows],
  )
  const reference = `${book} ${chapter}:${verse}`
  const referenceKey = `${book} ${chapter}:${verse}`

  const textFor = (key, verseNumber = verse) => {
    const source = TRANSLATION_BY_KEY[key]
    return rows.find((row) => (
      Number(row.chapter) === Number(chapter)
      && Number(row.verse) === Number(verseNumber)
      && String(row.translation).trim().toLocaleLowerCase() === source?.code.toLocaleLowerCase()
    ))?.text ?? null
  }

  const selectedTexts = selectedTranslations.map((key) => textFor(key))
  const summary = summarizeComparison(selectedTexts)
  const baseText = textFor(baseTranslation) ?? ''

  const handleToggleTranslation = (key) => {
    const result = applyTranslationToggle(selectedTranslations, key, baseTranslation)
    setSelectedTranslations(result.selected)
    setBaseTranslation(result.base)
  }

  const handleBookChange = (nextBook) => {
    setBook(nextBook)
    setChapter('1')
    setVerse('1')
  }

  const handleBookmark = () => {
    setBookmarks((current) => {
      const next = current.includes(referenceKey)
        ? current.filter((item) => item !== referenceKey)
        : [...current, referenceKey]
      localStorage.setItem('unbound_bookmarks', JSON.stringify(next))
      return next
    })
  }

  const openStudyTools = (tool = 'insights') => {
    setStudyTool(tool)
    setStudyToolsOpen(true)
  }

  const handleNoteChange = (event) => {
    const value = event.target.value
    setComparisonNote(value)
    setNoteStatus('saving')
    if (noteTimer.current) clearTimeout(noteTimer.current)
    noteTimer.current = setTimeout(() => {
      const key = `note-${book}-${chapter}-${verse}`
      if (value.trim()) localStorage.setItem(key, value)
      else localStorage.removeItem(key)
      setNoteStatus('saved')
    }, 500)
  }

  const shareData = {
    title: `Translation Study: ${reference}`,
    verses: [reference],
    type: 'Textual Comparison Workspace',
    content: {
      translationsCompared: selectedTranslations.map((key) => TRANSLATION_BY_KEY[key]?.name ?? key),
      baseTranslation: TRANSLATION_BY_KEY[baseTranslation]?.name ?? baseTranslation,
      notes: comparisonNote,
    },
  }

  return (
    <div className="comparison-workspace" data-testid="comparison-workspace">
      <div className="comparison-atmosphere" aria-hidden="true" />
      <header className="comparison-page-heading">
        <div>
          <p className="compare-eyebrow">Scripture study workspace</p>
          <h1>Compare translations</h1>
          <p>Read scripture sources side by side and understand where their wording differs.</p>
        </div>
        <button type="button" className="comparison-share-button" onClick={() => setShareOpen(true)}>
          Share comparison
        </button>
      </header>

      <ComparisonToolbar
        books={bookOptions}
        chapters={chapterOptions}
        verses={verseOptions.length ? verseOptions : [1]}
        book={book}
        chapter={chapter}
        verse={verse}
        viewMode={viewMode}
        baseTranslation={baseTranslation}
        selectedTranslations={selectedTranslations}
        highlightDifferences={highlightDifferences}
        onBookChange={handleBookChange}
        onChapterChange={(value) => { setChapter(value); setVerse('1') }}
        onVerseChange={setVerse}
        onViewModeChange={setViewMode}
        onBaseTranslationChange={setBaseTranslation}
        onHighlightDifferencesChange={setHighlightDifferences}
        onOpenStudyTools={() => openStudyTools('insights')}
        studyTriggerRef={studyTriggerRef}
      />

      <div className="comparison-main-layout">
        <button
          ref={sourcesTriggerRef}
          type="button"
          className="comparison-sources-trigger"
          aria-expanded={sourcesOpen}
          aria-controls="comparison-sources-panel"
          onClick={() => setSourcesOpen(true)}
        >
          Choose translations <span>{selectedTranslations.length}/{MAX_TRANSLATIONS}</span>
        </button>
        {sourcesOpen && (
          <button
            type="button"
            className="comparison-sources-backdrop"
            aria-label="Dismiss translation selector"
            onClick={() => { setSourcesOpen(false); sourcesTriggerRef.current?.focus() }}
          />
        )}
        <div
          ref={sourcesPanelRef}
          id="comparison-sources-panel"
          className={`comparison-left-rail ${sourcesOpen ? 'is-open' : ''}`}
          role={sourcesOpen ? 'dialog' : undefined}
          aria-modal={sourcesOpen ? 'true' : undefined}
          aria-label={sourcesOpen ? 'Translation sources' : undefined}
        >
          <header className="comparison-sources-mobile-header">
            <strong>Translation sources</strong>
            <button ref={sourcesCloseRef} type="button" aria-label="Close translation selector" onClick={() => { setSourcesOpen(false); sourcesTriggerRef.current?.focus() }}>×</button>
          </header>
          <TranslationSelector
            selected={selectedTranslations}
            baseTranslation={baseTranslation}
            onToggle={handleToggleTranslation}
          />
          <details className="comparison-note-panel">
            <summary>Comparison note <span>{noteStatus === 'saving' ? 'Saving…' : 'Saved locally'}</span></summary>
            <label>
              <span>Notes for {reference}</span>
              <textarea
                value={comparisonNote}
                onChange={handleNoteChange}
                placeholder="Record translation shifts or study observations…"
              />
            </label>
          </details>
        </div>

        <div className="comparison-reading-area">
          {requestStatus === 'ready' ? (
            viewMode === 'verse' ? (
              <>
                <ComparisonSummary
                  reference={reference}
                  summary={summary}
                  onShowDifferences={() => setHighlightDifferences(true)}
                  onExplainVerse={() => openStudyTools('insights')}
                  onViewOriginalWords={() => openStudyTools('words')}
                />
                <section
                  className="comparison-card-grid"
                  data-testid="comparison-grid"
                  aria-label={`${reference} translation comparison`}
                  style={{ '--comparison-columns': selectedTranslations.length }}
                >
                  {selectedTranslations.map((key) => {
                    const source = TRANSLATION_BY_KEY[key]
                    const text = textFor(key)
                    return (
                      <TranslationComparisonCard
                        key={key}
                        reference={reference}
                        source={source}
                        state={buildSourceState({ key, book, text })}
                        baseText={baseText}
                        isBase={key === baseTranslation}
                        highlightDifferences={highlightDifferences}
                        differenceCount={summary.differenceCount}
                        bookmarked={bookmarks.includes(referenceKey)}
                        onBookmark={handleBookmark}
                        onOpenNotes={() => openStudyTools('notes')}
                        onChooseSource={() => document.querySelector('.translation-search input')?.focus()}
                        onLearnMore={() => openStudyTools('insights')}
                      />
                    )
                  })}
                </section>
              </>
            ) : (
              <ChapterComparison
                book={book}
                chapter={chapter}
                verses={verseOptions}
                selectedTranslations={selectedTranslations}
                baseTranslation={baseTranslation}
                rows={rows}
                highlightDifferences={highlightDifferences}
              />
            )
          ) : (
            <RequestState status={requestStatus} onRetry={() => setRequestRevision((value) => value + 1)} />
          )}
        </div>
      </div>

      <p className="comparison-source-note">
        <span aria-hidden="true">i</span>
        Differences are highlighted against {TRANSLATION_BY_KEY[baseTranslation]?.name}. Source availability reflects the local research database.
      </p>

      <ComparisonStudyDrawer
        open={studyToolsOpen}
        triggerRef={studyTriggerRef}
        initialTool={studyTool}
        book={book}
        chapter={Number(chapter)}
        verse={Number(verse)}
        onClose={() => setStudyToolsOpen(false)}
        onAddNote={(note) => {
          const text = note?.text ?? note?.content
          if (text) setComparisonNote((current) => current ? `${current}\n- ${text}` : `- ${text}`)
        }}
      />

      <ShareStudyModal
        isOpen={shareOpen}
        onClose={() => setShareOpen(false)}
        shareData={shareData}
      />
    </div>
  )
}
