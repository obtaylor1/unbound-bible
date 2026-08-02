import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import useDialogFocus from './useDialogFocus'

const CANONS = [
  ['PROT66', 'Protestant'],
  ['CATH73', 'Catholic'],
  ['ETHIO81', 'Ethiopian Orthodox'],
  ['BROADER', 'Broader canon and scholarly texts'],
]

function normalizeBooks(books) {
  if (!Array.isArray(books)) return []

  const seen = new Set()
  return books.flatMap((book) => {
    const name = (typeof book === 'string' ? book : book?.name)?.trim()
    if (!name) return []
    const key = name.toLocaleLowerCase()
    if (seen.has(key)) return []
    seen.add(key)
    const metadata = typeof book === 'object' && book ? book : {}
    return [{
      name,
      testament: typeof metadata.testament === 'string' && metadata.testament.trim()
        ? metadata.testament.trim()
        : null,
      collection: typeof metadata.collection === 'string' && metadata.collection.trim()
        ? metadata.collection.trim()
        : null,
    }]
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
  booksStatus = 'ready',
  selectedCanon,
  loadChapters,
  onRetryBooks,
  onCanonChange,
  onChoose,
  onClose,
}) {
  const titleId = useId()
  const canonValue = CANONS.some(([value]) => value === selectedCanon)
    ? selectedCanon
    : 'PROT66'
  const dialogRef = useRef(null)
  const searchRef = useRef(null)
  const backRef = useRef(null)
  const firstChapterRef = useRef(null)
  const mountedRef = useRef(true)
  const openRef = useRef(open)
  const committedOpenRef = useRef(open)
  const previousCanonRef = useRef(canonValue)
  const requestSequence = useRef(0)
  const requestControllerRef = useRef(null)
  const wasOpenRef = useRef(false)
  const focusIntentRef = useRef(null)
  const [query, setQuery] = useState('')
  const [testament, setTestament] = useState('all')
  const [collection, setCollection] = useState('all')
  const [selectedBook, setSelectedBook] = useState(null)
  const [chapters, setChapters] = useState([])
  const [chapterState, setChapterState] = useState('idle')

  const closePicker = () => {
    requestControllerRef.current?.abort()
    requestControllerRef.current = null
    requestSequence.current += 1
    focusIntentRef.current = 'books'
    setQuery('')
    setTestament('all')
    setCollection('all')
    setSelectedBook(null)
    setChapters([])
    setChapterState('idle')
    if (typeof onClose === 'function') onClose()
  }

  useDialogFocus({
    open,
    containerRef: dialogRef,
    initialRef: searchRef,
    onClose: closePicker,
  })

  useLayoutEffect(() => {
    if (committedOpenRef.current === open) return

    committedOpenRef.current = open
    openRef.current = open
    requestControllerRef.current?.abort()
    requestControllerRef.current = null
    requestSequence.current += 1
  }, [open])

  useLayoutEffect(() => {
    if (previousCanonRef.current === canonValue) return

    previousCanonRef.current = canonValue
    if (!open) return

    requestControllerRef.current?.abort()
    requestControllerRef.current = null
    requestSequence.current += 1
    focusIntentRef.current = 'books'
    setQuery('')
    setTestament('all')
    setCollection('all')
    setSelectedBook(null)
    setChapters([])
    setChapterState('idle')
  }, [canonValue, open])

  useLayoutEffect(() => {
    const focusIntent = focusIntentRef.current

    if (!selectedBook && focusIntent === 'books') {
      searchRef.current?.focus()
      focusIntentRef.current = null
      return
    }

    if (selectedBook && chapterState === 'loading' && focusIntent === 'loading') {
      backRef.current?.focus()
      focusIntentRef.current = 'result'
      return
    }

    if (chapterState === 'ready' && (focusIntent === 'loading' || focusIntent === 'result')) {
      if (focusIntent === 'loading' || document.activeElement === backRef.current) {
        firstChapterRef.current?.focus()
      }
      focusIntentRef.current = null
      return
    }

    if ((chapterState === 'error' || chapterState === 'empty') && focusIntent === 'result') {
      focusIntentRef.current = null
    }
  }, [chapterState, selectedBook])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      requestControllerRef.current?.abort()
      requestControllerRef.current = null
      requestSequence.current += 1
    }
  }, [])

  useEffect(() => {
    if (open && !wasOpenRef.current) {
      setQuery('')
      setTestament('all')
      setCollection('all')
      setSelectedBook(null)
      setChapters([])
      setChapterState('idle')
    }

    wasOpenRef.current = open
  }, [open])

  const normalizedBooks = useMemo(() => normalizeBooks(books), [books])
  const testaments = useMemo(() => [...new Set(
    normalizedBooks.map((book) => book.testament).filter(Boolean),
  )].sort(), [normalizedBooks])
  const collections = useMemo(() => [...new Set(
    normalizedBooks
      .filter((book) => testament === 'all' || book.testament === testament)
      .map((book) => book.collection)
      .filter(Boolean),
  )].sort(), [normalizedBooks, testament])
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const filteredBooks = normalizedBooks.filter((book) => (
    (testament === 'all' || book.testament === testament)
    && (collection === 'all' || book.collection === collection)
    && book.name.toLocaleLowerCase().includes(normalizedQuery)
  ))
  const chooseBook = async (book) => {
    requestControllerRef.current?.abort()
    const controller = new AbortController()
    requestControllerRef.current = controller
    const requestId = requestSequence.current + 1
    requestSequence.current = requestId
    focusIntentRef.current = 'loading'
    setSelectedBook(book)
    setChapters([])
    setChapterState('loading')

    try {
      if (typeof loadChapters !== 'function') {
        throw new Error('No chapter loader is available')
      }

      const loadedChapters = await loadChapters(book, controller.signal)
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
    } finally {
      if (requestControllerRef.current === controller) {
        requestControllerRef.current = null
      }
    }
  }

  const backToBooks = () => {
    requestControllerRef.current?.abort()
    requestControllerRef.current = null
    requestSequence.current += 1
    focusIntentRef.current = 'books'
    setSelectedBook(null)
    setChapters([])
    setChapterState('idle')
  }

  const changeCanon = (event) => {
    requestControllerRef.current?.abort()
    requestControllerRef.current = null
    requestSequence.current += 1
    focusIntentRef.current = 'books'
    setQuery('')
    setTestament('all')
    setCollection('all')
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
        if (event.target === event.currentTarget) closePicker()
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
            onClick={closePicker}
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
            <>
              <label className="book-picker__field">
                <span>Testament</span>
                <select
                  className="book-picker__control"
                  value={testament}
                  onChange={(event) => {
                    setTestament(event.target.value)
                    setCollection('all')
                  }}
                >
                  <option value="all">All testaments</option>
                  {testaments.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <label className="book-picker__field">
                <span>Collection</span>
                <select
                  className="book-picker__control"
                  value={collection}
                  onChange={(event) => setCollection(event.target.value)}
                >
                  <option value="all">All collections</option>
                  {collections.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
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
            </>
          )}
        </div>

        {!selectedBook ? (
          <section className="book-picker__content" aria-label="Bible books">
            {booksStatus === 'loading' ? (
              <p className="book-picker__message" role="status">
                Loading Bible books…
              </p>
            ) : booksStatus === 'error' ? (
              <div className="book-picker__message">
                <p role="alert">Bible books could not load.</p>
                {typeof onRetryBooks === 'function' && (
                  <button
                    className="book-picker__retry book-picker__control"
                    type="button"
                    onClick={onRetryBooks}
                  >
                    Try loading books again
                  </button>
                )}
              </div>
            ) : filteredBooks.length > 0 ? (
              <div className="book-picker__books">
                {filteredBooks.map((book) => (
                  <button
                    className="book-picker__book book-picker__control"
                    type="button"
                    key={book.name}
                    onClick={() => chooseBook(book.name)}
                  >
                    {book.name}
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
                ref={backRef}
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
                {chapters.map((chapter, index) => (
                  <button
                    ref={index === 0 ? firstChapterRef : null}
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
