import {
  createElement,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import SearchDialog from '../search/SearchDialog'
import SkipLink from '../components/SkipLink'
import { pageFromKnownHash } from '../routing/pageRoutes'
import BookPicker from './BookPicker'
import PassageToolbar from './PassageToolbar'
import ReaderBottomNavigation from './ReaderBottomNavigation'
import { useReaderPreferences } from './ReaderPreferences'
import ReaderStatus from './ReaderStatus'
import ScripturePane from './ScripturePane'
import StudyTools from './StudyTools'
import { parseReaderHash, readerHash } from './readerRoute'
import {
  getBookChapters,
  getBookCatalog,
  getChapter,
  getVerseDetails,
} from './scriptureApi'
import { studyReferenceKey } from './studyToolRegistry'
import './readerTokens.css'

function abortError(error) {
  return error?.name === 'AbortError'
}

function normalizedTranslations(rows) {
  const seen = new Set()
  return (Array.isArray(rows) ? rows : []).flatMap((row) => {
    const code = typeof row?.translation === 'string'
      ? row.translation.trim().toUpperCase()
      : ''
    if (!code || seen.has(code)) return []
    seen.add(code)
    return [{ code, name: code }]
  })
}

function normalizeRoute(route) {
  return parseReaderHash(readerHash(route))
}

export default function ScriptureReaderPage({
  onPageChange,
  navigateDocument = (url) => window.location.assign(url),
  SearchComponent = SearchDialog,
}) {
  const [route, setRoute] = useState(() => parseReaderHash())
  const [books, setBooks] = useState([])
  const [booksCanonKey, setBooksCanonKey] = useState(null)
  const [booksStatus, setBooksStatus] = useState('loading')
  const [booksRetryRevision, setBooksRetryRevision] = useState(0)
  const [chapters, setChapters] = useState([])
  const [chaptersBookKey, setChaptersBookKey] = useState(null)
  const [chaptersStatus, setChaptersStatus] = useState('loading')
  const [chaptersRetryRevision, setChaptersRetryRevision] = useState(0)
  const [chapterRows, setChapterRows] = useState([])
  const [chapterRowsKey, setChapterRowsKey] = useState(null)
  const [status, setStatus] = useState('loading')
  const [retryRevision, setRetryRevision] = useState(0)
  const [bookPickerOpen, setBookPickerOpen] = useState(false)
  const [studyToolsOpen, setStudyToolsOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [details, setDetails] = useState(null)
  const [detailsStatus, setDetailsStatus] = useState('ready')
  const [detailsReferenceKey, setDetailsReferenceKey] = useState()
  const [detailsRevision, setDetailsRevision] = useState(0)
  const booksGeneration = useRef(0)
  const chaptersGeneration = useRef(0)
  const chapterGeneration = useRef(0)
  const detailsGeneration = useRef(0)
  const chapterMetadataCache = useRef(new Map())
  const mainRef = useRef(null)
  const { fontSize, readingWidth } = useReaderPreferences()
  const selectedTranslationRef = useRef(route.translation)
  const routeRef = useRef(route)

  const loadChapterMetadata = useCallback(async (book, signal, canon) => {
    const key = `${canon ?? routeRef.current.canon}\u0000${book}`
    if (chapterMetadataCache.current.has(key)) {
      return chapterMetadataCache.current.get(key)
    }
    const loaded = await getBookChapters(book, signal)
    if (!signal?.aborted) chapterMetadataCache.current.set(key, loaded)
    return loaded
  }, [])

  const navigate = useCallback((next) => {
    const current = routeRef.current
    const normalized = normalizeRoute(
      typeof next === 'function' ? next(current) : { ...current, ...next },
    )
    setRoute(normalized)
  }, [])

  useLayoutEffect(() => {
    routeRef.current = route
    selectedTranslationRef.current = route.translation
    const hash = readerHash(route)
    if (window.location.hash !== hash) window.location.hash = hash
  }, [route])

  useEffect(() => {
    const onHashChange = () => {
      if (window.location.hash === '#main-content') return
      setRoute(parseReaderHash())
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const generation = ++booksGeneration.current
    setBooks([])
    setBooksCanonKey((current) => current === route.canon ? current : null)
    setBooksStatus('loading')
    getBookCatalog(route.canon, controller.signal)
      .then((nextBooks) => {
        if (generation !== booksGeneration.current || controller.signal.aborted) return
        setBooks(Array.isArray(nextBooks) ? nextBooks : [])
        setBooksCanonKey(route.canon)
        setBooksStatus('ready')
      })
      .catch(() => {
        if (generation === booksGeneration.current && !controller.signal.aborted) {
          setBooks([])
          setBooksCanonKey(route.canon)
          setBooksStatus('error')
        }
      })
    return () => {
      controller.abort()
      booksGeneration.current += 1
    }
  }, [route.canon, booksRetryRevision])

  const catalogOwnedByRoute = booksCanonKey === route.canon
  const currentBooks = useMemo(
    () => catalogOwnedByRoute ? books : [],
    [books, catalogOwnedByRoute],
  )
  const currentBooksStatus = catalogOwnedByRoute ? booksStatus : 'loading'
  const routeBookValid = currentBooks.some(
    (book) => (typeof book === 'string' ? book : book?.name)?.toLocaleLowerCase()
      === route.book.toLocaleLowerCase(),
  )
  const catalogReady = currentBooksStatus === 'ready'
  const routeLoadAllowed = (
    catalogOwnedByRoute && currentBooksStatus === 'loading'
  ) || currentBooksStatus === 'error' || (
    catalogReady && routeBookValid
  )

  useEffect(() => {
    if (!catalogReady || currentBooks.length === 0 || routeBookValid) return
    navigate({
      book: typeof currentBooks[0] === 'string' ? currentBooks[0] : currentBooks[0].name,
      chapter: 1,
      verse: null,
    })
  }, [catalogReady, currentBooks, navigate, routeBookValid])

  useEffect(() => {
    if (!routeLoadAllowed) {
      chaptersGeneration.current += 1
      setChapters([])
      setChaptersBookKey(null)
      setChaptersStatus('loading')
      return undefined
    }
    const controller = new AbortController()
    const generation = ++chaptersGeneration.current
    setChapters([])
    setChaptersBookKey(null)
    setChaptersStatus('loading')
    loadChapterMetadata(route.book, controller.signal, route.canon)
      .then((nextChapters) => {
        if (generation !== chaptersGeneration.current || controller.signal.aborted) return
        setChapters(nextChapters)
        setChaptersBookKey(route.book)
        setChaptersStatus('ready')
      })
      .catch(() => {
        if (generation === chaptersGeneration.current && !controller.signal.aborted) {
          setChapters([])
          setChaptersBookKey(route.book)
          setChaptersStatus('error')
        }
      })
    return () => {
      controller.abort()
      chaptersGeneration.current += 1
    }
  }, [route.book, route.canon, routeLoadAllowed, chaptersRetryRevision, loadChapterMetadata])

  useEffect(() => {
    if (!routeLoadAllowed) {
      chapterGeneration.current += 1
      setStatus(catalogReady && currentBooks.length === 0 ? 'empty' : 'loading')
      return undefined
    }
    const controller = new AbortController()
    const generation = ++chapterGeneration.current
    setStatus('loading')
    getChapter({
      book: route.book,
      chapter: route.chapter,
    }, controller.signal)
      .then((nextRows) => {
        if (generation !== chapterGeneration.current || controller.signal.aborted) return
        setChapterRows(Array.isArray(nextRows) ? nextRows : [])
        setChapterRowsKey(`${route.book}\u0000${route.chapter}`)
        const translations = normalizedTranslations(nextRows)
        const selectedTranslation = selectedTranslationRef.current
        if (
          translations.length
          && !translations.some(({ code }) => code === selectedTranslation)
        ) {
          navigate({ translation: translations[0].code })
        }
        const selectedRows = (Array.isArray(nextRows) ? nextRows : []).filter(
          (row) => String(row?.translation ?? '').trim().toUpperCase()
            === (translations.some(({ code }) => code === selectedTranslation)
              ? selectedTranslation
              : translations[0]?.code),
        )
        setStatus(selectedRows.length ? 'ready' : 'empty')
      })
      .catch((error) => {
        if (generation !== chapterGeneration.current || controller.signal.aborted || abortError(error)) return
        setStatus(navigator.onLine === false || error instanceof TypeError ? 'offline' : 'error')
      })
    return () => {
      controller.abort()
      chapterGeneration.current += 1
    }
  }, [
    catalogReady,
    currentBooks.length,
    route.book,
    route.chapter,
    routeLoadAllowed,
    retryRevision,
    navigate,
  ])

  useEffect(() => {
    if (
      chapterRowsKey !== `${route.book}\u0000${route.chapter}`
      || !['ready', 'empty'].includes(status)
    ) return
    const available = normalizedTranslations(chapterRows)
    if (available.length && !available.some(({ code }) => code === route.translation)) {
      navigate({ translation: available[0].code })
      return
    }
    const selectedRows = chapterRows.filter(
      (row) => String(row?.translation ?? '').trim().toUpperCase() === route.translation,
    )
    setStatus(selectedRows.length ? 'ready' : 'empty')
  }, [
    chapterRows,
    chapterRowsKey,
    navigate,
    route.book,
    route.chapter,
    route.translation,
    status,
  ])

  useEffect(() => {
    const markOffline = () => {
      setStatus((current) => current === 'empty' ? current : 'offline')
    }
    window.addEventListener('offline', markOffline)
    return () => window.removeEventListener('offline', markOffline)
  }, [])

  const reference = useMemo(() => ({
    book: route.book,
    chapter: route.chapter,
    ...(route.verse ? { verse: route.verse } : {}),
  }), [route.book, route.chapter, route.verse])
  const referenceKey = studyReferenceKey(reference)

  useEffect(() => {
    if (!studyToolsOpen || !route.verse) {
      detailsGeneration.current += 1
      setDetails(null)
      setDetailsReferenceKey(referenceKey)
      setDetailsStatus('ready')
      return undefined
    }
    const controller = new AbortController()
    const generation = ++detailsGeneration.current
    setDetails(null)
    setDetailsReferenceKey(referenceKey)
    setDetailsStatus('loading')
    setDetailsRevision((value) => value + 1)
    getVerseDetails({
      book: route.book,
      chapter: route.chapter,
      verse: route.verse,
    }, controller.signal)
      .then((nextDetails) => {
        if (generation !== detailsGeneration.current || controller.signal.aborted) return
        setDetails(nextDetails)
        setDetailsReferenceKey(referenceKey)
        setDetailsStatus('ready')
        setDetailsRevision((value) => value + 1)
      })
      .catch((error) => {
        if (generation !== detailsGeneration.current || controller.signal.aborted || abortError(error)) return
        setDetails(null)
        setDetailsReferenceKey(referenceKey)
        setDetailsStatus('error')
        setDetailsRevision((value) => value + 1)
      })
    return () => {
      controller.abort()
      detailsGeneration.current += 1
    }
  }, [
    studyToolsOpen,
    referenceKey,
    route.book,
    route.chapter,
    route.verse,
  ])

  const currentChapterKey = `${route.book}\u0000${route.chapter}`
  const currentChapterRows = chapterRowsKey === currentChapterKey ? chapterRows : []
  const translations = normalizedTranslations(currentChapterRows)
  const verses = currentChapterRows.filter(
    (row) => String(row?.translation ?? '').trim().toUpperCase() === route.translation,
  )
  const currentChapters = chaptersBookKey === route.book ? chapters : []
  const currentChaptersStatus = chaptersBookKey === route.book ? chaptersStatus : 'loading'
  const chapterIndex = currentChapters.indexOf(route.chapter)
  const canGoPrevious = currentChaptersStatus === 'ready' && chapterIndex > 0
  const canGoNext = (
    currentChaptersStatus === 'ready'
    && chapterIndex >= 0
    && chapterIndex < currentChapters.length - 1
  )
  const currentRowsLoaded = (
    verses.length > 0
  )

  const closeOverlays = () => {
    setBookPickerOpen(false)
    setStudyToolsOpen(false)
    setSearchOpen(false)
  }
  const openBooks = () => {
    closeOverlays()
    setBookPickerOpen(true)
  }
  const openStudyTools = () => {
    closeOverlays()
    setStudyToolsOpen(true)
  }
  const openSearch = () => {
    closeOverlays()
    setSearchOpen(true)
  }
  const changePage = (page, nextReference) => {
    closeOverlays()
    onPageChange?.(page, nextReference)
  }
  const navigateSearchResult = (url) => {
    closeOverlays()
    let target
    try {
      target = new URL(String(url), window.location.href)
    } catch {
      return
    }
    if (
      !['http:', 'https:'].includes(target.protocol)
      || target.origin !== window.location.origin
    ) return
    if (target.pathname !== '/') {
      navigateDocument(target.href)
      return
    }
    const page = pageFromKnownHash(target.hash)
    if (!page) return
    if (page === 'apocrypha') navigate(parseReaderHash(target.hash))
    else onPageChange?.(page)
  }

  return (
    <div
      className={`scripture-reader scripture-reader-shell reader-font-${fontSize} reader-width-${readingWidth}`}
      data-testid="scripture-reader"
    >
      <SkipLink />
      <PassageToolbar
        reference={`${route.book} ${route.chapter}`}
        translation={route.translation}
        translations={translations}
        onTranslationChange={(translation) => navigate({ translation, verse: null })}
        canGoPrevious={canGoPrevious}
        canGoNext={canGoNext}
        onPrevious={() => navigate({ chapter: currentChapters[chapterIndex - 1], verse: null })}
        onNext={() => navigate({ chapter: currentChapters[chapterIndex + 1], verse: null })}
        onOpenBooks={openBooks}
        onOpenStudyTools={openStudyTools}
      />
      {currentChaptersStatus === 'error' && (
        <section
          className="reader-metadata-status"
          role="status"
          aria-label="Chapter navigation unavailable"
        >
          <strong>Chapter navigation unavailable</strong>
          <button
            type="button"
            onClick={() => setChaptersRetryRevision((value) => value + 1)}
          >
            Try chapter navigation again
          </button>
        </section>
      )}
      <main ref={mainRef} id="main-content" className="scripture-reader-shell__main" tabIndex="-1">
        {status === 'ready' || (status === 'offline' && currentRowsLoaded) ? (
          <>
            {status === 'offline' && (
              <ReaderStatus
                state="offline"
                reference={`${route.book} ${route.chapter}`}
                hasLoadedContent
                compact
                onRetry={() => setRetryRevision((value) => value + 1)}
              />
            )}
            <ScripturePane
              book={route.book}
              chapter={route.chapter}
              verses={verses}
              selectedVerse={route.verse}
              onSelectVerse={(verse) => navigate({ verse })}
            />
          </>
        ) : (
          <ReaderStatus
            state={status}
            reference={`${route.book} ${route.chapter}`}
            onRetry={() => setRetryRevision((value) => value + 1)}
            onOpenBooks={openBooks}
          />
        )}
      </main>
      <ReaderBottomNavigation
        onNavigate={typeof onPageChange === 'function' ? changePage : undefined}
        onSearch={openSearch}
        onOpenBooks={openBooks}
      />
      <BookPicker
        open={bookPickerOpen}
        books={currentBooks}
        booksStatus={currentBooksStatus}
        selectedCanon={route.canon}
        loadChapters={(book, signal) => loadChapterMetadata(book, signal, route.canon)}
        onRetryBooks={() => setBooksRetryRevision((value) => value + 1)}
        onCanonChange={(canon) => navigate({ canon, chapter: 1, verse: null })}
        onChoose={({ book, chapter }) => {
          setBookPickerOpen(false)
          navigate({ book, chapter, verse: null })
        }}
        onClose={() => setBookPickerOpen(false)}
      />
      <StudyTools
        open={studyToolsOpen}
        reference={reference}
        details={details}
        detailsReferenceKey={detailsReferenceKey}
        detailsRevision={detailsRevision}
        detailsStatus={detailsStatus}
        onClose={() => setStudyToolsOpen(false)}
        onNavigate={typeof onPageChange === 'function' ? changePage : undefined}
      />
      {createElement(SearchComponent, {
        open: searchOpen,
        onClose: () => setSearchOpen(false),
        onNavigate: navigateSearchResult,
      })}
    </div>
  )
}
