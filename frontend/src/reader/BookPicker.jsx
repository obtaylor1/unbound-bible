import { useEffect, useId, useMemo, useRef, useState } from 'react'
import useDialogFocus from './useDialogFocus'

const CANONS = [
  ['PROT66', 'Protestant'],
  ['CATH73', 'Catholic'],
  ['ETHIO81', 'Ethiopian Orthodox'],
  ['BROADER', 'Broader canon and scholarly texts'],
]

function normalizeBooks(books) {
  if (!Array.isArray(books)) return []

  const names = books
    .map((book) => (typeof book === 'string' ? book : book?.name))
    .filter((name) => typeof name === 'string')
    .map((name) => name.trim())
    .filter(Boolean)

  const seen = new Set()
  return names.filter((name) => {
    const key = name.toLocaleLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function normalizeChapters(chapters) {
  if (!Array.isArray(chapters)) return []

  return [...new Set(
    chapters
      .map((chapter) => (
        typeof chapter === 'string' && chapter.trim()
          ? Number(chapter)
          : chapter
      ))
      .filter((chapter) => Number.isInteger(chapter) && chapter > 0),
  )].sort((first, second) => first - second)
}

export default function BookPicker({
  open,
  books,
  selectedCanon,
  loadChapters,
  onCanonChange,
  onChoose,
  onClose,
}) {
  const titleId = useId()
  const dialogRef = useRef(null)
  const searchRef = useRef(null)
  const mountedRef = useRef(true)
  const openRef = useRef(open)
  const requestSequence = useRef(0)
  const wasOpenRef = useRef(false)
  const [query, setQuery] = useState('')
  const [selectedBook, setSelectedBook] = useState(null)
  const [chapters, setChapters] = useState([])
  const [chapterState, setChapterState] = useState('idle')

  useDialogFocus({
    open,
    containerRef: dialogRef,
    initialRef: searchRef,
    onClose,
  })

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      requestSequence.current += 1
    }
  }, [])

  useEffect(() => {
    openRef.current = open
    requestSequence.current += 1

    if (open && !wasOpenRef.current) {
      setQuery('')
      setSelectedBook(null)
      setChapters([])
      setChapterState('idle')
    }

    wasOpenRef.current = open
  }, [open])

  const normalizedBooks = useMemo(() => normalizeBooks(books), [books])
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const filteredBooks = normalizedBooks.filter((book) => (
    book.toLocaleLowerCase().includes(normalizedQuery)
  ))
  const canonValue = CANONS.some(([value]) => value === selectedCanon)
    ? selectedCanon
    : 'PROT66'

  const chooseBook = async (book) => {
    const requestId = requestSequence.current + 1
    requestSequence.current = requestId
    setSelectedBook(book)
    setChapters([])
    setChapterState('loading')

    try {
      if (typeof loadChapters !== 'function') {
        throw new Error('No chapter loader is available')
      }

      const loadedChapters = await loadChapters(book)
      if (
        !mountedRef.current
        || !openRef.current
        || requestSequence.current !== requestId
      ) return

      const normalized = normalizeChapters(loadedChapters)
      setChapters(normalized)
      setChapterState(normalized.length ? 'ready' : 'empty')
    } catch {
      if (
        !mountedRef.current
        || !openRef.current
        || requestSequence.current !== requestId
      ) return

      setChapters([])
      setChapterState('error')
    }
  }

  const backToBooks = () => {
    requestSequence.current += 1
    setSelectedBook(null)
    setChapters([])
    setChapterState('idle')
  }

  const changeCanon = (event) => {
    requestSequence.current += 1
    setQuery('')
    setSelectedBook(null)
    setChapters([])
    setChapterState('idle')
    if (typeof onCanonChange === 'function') {
      onCanonChange(event.target.value)
    }
  }

  if (!open) return null

  return (
    <div
      className="book-picker"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && typeof onClose === 'function') {
          onClose()
        }
      }}
    >
      <aside
        ref={dialogRef}
        className="book-picker__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="book-picker__header">
          <div>
            <p className="book-picker__eyebrow">Scripture library</p>
            <h2 id={titleId}>Choose a book and chapter</h2>
          </div>
          <button
            className="book-picker__close book-picker__control"
            type="button"
            aria-label="Close book picker"
            onClick={() => {
              if (typeof onClose === 'function') onClose()
            }}
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <div className="book-picker__filters">
          <label className="book-picker__field">
            <span>Canon</span>
            <select
              className="book-picker__control"
              value={canonValue}
              onChange={changeCanon}
            >
              {CANONS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          {!selectedBook && (
            <label className="book-picker__field">
              <span>Search Bible books</span>
              <input
                ref={searchRef}
                className="book-picker__control"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Try Genesis or Romans"
              />
            </label>
          )}
        </div>

        {!selectedBook ? (
          <section className="book-picker__content" aria-label="Bible books">
            {filteredBooks.length > 0 ? (
              <div className="book-picker__books">
                {filteredBooks.map((book) => (
                  <button
                    className="book-picker__book book-picker__control"
                    type="button"
                    key={book}
                    onClick={() => chooseBook(book)}
                  >
                    {book}
                  </button>
                ))}
              </div>
            ) : (
              <p className="book-picker__message">
                {normalizedBooks.length === 0
                  ? 'No Bible books are available for this canon.'
                  : `No books match “${query.trim()}”.`}
              </p>
            )}
          </section>
        ) : (
          <section className="book-picker__content book-picker__chapters-view">
            <div className="book-picker__section-header">
              <button
                className="book-picker__back book-picker__control"
                type="button"
                onClick={backToBooks}
              >
                <span aria-hidden="true">←</span> Back to books
              </button>
              <h3>{selectedBook} chapters</h3>
            </div>

            {chapterState === 'loading' && (
              <p className="book-picker__message" role="status">
                Loading chapters for {selectedBook}…
              </p>
            )}

            {chapterState === 'error' && (
              <div className="book-picker__message">
                <p role="alert">We could not load chapters for {selectedBook}.</p>
                <button
                  className="book-picker__retry book-picker__control"
                  type="button"
                  onClick={() => chooseBook(selectedBook)}
                >
                  Try again
                </button>
              </div>
            )}

            {chapterState === 'empty' && (
              <div className="book-picker__message">
                <p role="status">No chapters are available for {selectedBook}.</p>
                <button
                  className="book-picker__retry book-picker__control"
                  type="button"
                  onClick={() => chooseBook(selectedBook)}
                >
                  Try again
                </button>
              </div>
            )}

            {chapterState === 'ready' && (
              <div
                className="book-picker__chapters"
                role="group"
                aria-label={`${selectedBook} chapters`}
              >
                {chapters.map((chapter) => (
                  <button
                    className="book-picker__chapter book-picker__control"
                    type="button"
                    key={chapter}
                    onClick={() => {
                      if (typeof onChoose === 'function') {
                        onChoose({ book: selectedBook, chapter })
                      }
                    }}
                  >
                    Chapter {chapter}
                  </button>
                ))}
              </div>
            )}
          </section>
        )}
      </aside>
    </div>
  )
}
