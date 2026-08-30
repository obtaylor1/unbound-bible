import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import './App.css'
import Navigation from './components/Navigation'
import HomePage from './components/HomePage'
import SkipLink from './components/SkipLink'
import {
  hashForPage,
  pageFromHash,
  titleForPage,
} from './routing/pageRoutes'
import ReaderErrorBoundary from './reader/ReaderErrorBoundary'
import { ReaderPreferencesProvider } from './reader/ReaderPreferences'

const TextualComparisonWorkspace = lazy(() => import('./components/TextualComparisonWorkspace'))
const ScriptureReaderPage = lazy(() => import('./reader/ScriptureReaderPage'))
const SermonAnalyzer = lazy(() => import('./components/SermonAnalyzer'))
const InteractiveMap = lazy(() => import('./components/InteractiveMap'))
const ForumPage = lazy(() => import('./components/ForumPage'))
const AskTheBible = lazy(() => import('./components/AskTheBible'))
const ResearchHub = lazy(() => import('./components/ResearchHub'))
const InteractiveMedia = lazy(() => import('./components/InteractiveMedia'))
const SavedStudies = lazy(() => import('./components/SavedStudies'))
const CanonComparison = lazy(() => import('./components/CanonComparison'))
const RaceMisuse = lazy(() => import('./components/RaceMisuse'))
const Factbook = lazy(() => import('./components/Factbook'))
const ScriptureVerificationPage = lazy(() => import('./admin/ScriptureVerificationPage'))

export function ReaderLoadingFallback() {
  return (
    <>
      <SkipLink />
      <main
        id="main-content"
        className="page-loading"
        aria-label="Scripture Reader"
        tabIndex="-1"
      >
        <p role="status">Opening Scripture reader…</p>
        <div className="reader-loading-skeleton" aria-hidden="true">
          <span className="reader-loading-skeleton__title" />
          <span className="reader-loading-skeleton__line" />
          <span className="reader-loading-skeleton__line" />
          <span className="reader-loading-skeleton__line reader-loading-skeleton__line--short" />
          <span className="reader-loading-skeleton__line" />
        </div>
      </main>
    </>
  )
}

function App() {
  const [currentPage, setCurrentPage] = useState(() => pageFromHash(window.location.hash))
  const [currentHash, setCurrentHash] = useState(() => window.location.hash)
  const [pageContext, setPageContext] = useState(null)
  const mainRef = useRef(null)
  const pendingHashRef = useRef(null)
  const previousPageRef = useRef(currentPage)

  useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash === '#main-content') return
      const internalNavigation = pendingHashRef.current === window.location.hash
      pendingHashRef.current = null
      setCurrentHash(window.location.hash)
      setCurrentPage(pageFromHash(window.location.hash))
      if (!internalNavigation) setPageContext(null)
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  useEffect(() => {
    document.title = `${titleForPage(currentPage)} · The Unbound Bible`
    if (previousPageRef.current !== currentPage) {
      window.requestAnimationFrame(() => mainRef.current?.focus({ preventScroll: true }))
    }
    previousPageRef.current = currentPage
  }, [currentPage])

  const handlePageChange = (pageId, context = null) => {
    setCurrentPage(pageId)
    setPageContext(context)
    const nextHash = hashForPage(pageId)
    setCurrentHash(nextHash)
    if (window.location.hash !== nextHash) {
      pendingHashRef.current = nextHash
      window.location.hash = nextHash
    }
  }

  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'home':
        return <HomePage onPageChange={handlePageChange} />
      
      case 'textual':
        return <TextualComparisonWorkspace />
      case 'apocrypha':
        return (
          <ReaderErrorBoundary resetKey={currentHash}>
            <ReaderPreferencesProvider>
              <ScriptureReaderPage onPageChange={handlePageChange} />
            </ReaderPreferencesProvider>
          </ReaderErrorBoundary>
        )
      
      case 'canon-compare':
        return (
          <div className="page-container">
            <CanonComparison />
          </div>
        )

      case 'race-misuse':
        return (
          <div className="page-container">
            <RaceMisuse />
          </div>
        )

      case 'factbook':
        return (
          <div className="page-container">
            <Factbook />
          </div>
        )

      case 'bias-explorer':
        return (
          <div className="page-container">
            <ResearchHub initialTopicKey="translation_bias" />
          </div>
        )
      case 'sermon':
        return (
          <div className="page-container">
            <SermonAnalyzer onPageChange={handlePageChange} />
          </div>
        )
      
      case 'map':
        return (
          <div className="page-container">
            <div className="page-header">
              <h1>Interactive Biblical Map</h1>
              <p>Explore significant biblical locations and their modern-day equivalents with detailed historical context</p>
            </div>
            <InteractiveMap />
          </div>
        )
      
      case 'forum':
        return (
          <div className="page-container">
            <div className="page-header">
              <h1>Community Forum</h1>
              <p>Join discussions about biblical texts, historical context, and theological insights</p>
            </div>
            <ForumPage />
          </div>
        )
      
      case 'chat':
        return (
          <div className="page-container">
            <AskTheBible onPageChange={handlePageChange} />
          </div>
        )

      case 'research':
        return (
          <div className="page-container">
            <ResearchHub />
          </div>
        )

      case 'media':
        return (
          <div className="page-container">
            <InteractiveMedia />
          </div>
        )

      case 'notes':
        return (
          <div className="page-container">
            <SavedStudies reference={pageContext} />
          </div>
        )

      case 'scripture-verification-admin':
        return <ScriptureVerificationPage />
      
      default:
        return <HomePage />
    }
  }

  if (currentPage === 'apocrypha') {
    return (
      <div className="app">
        <header>
          <Navigation currentPage={currentPage} onPageChange={handlePageChange} />
        </header>
        <Suspense fallback={<ReaderLoadingFallback />}>
          {renderCurrentPage()}
        </Suspense>
      </div>
    )
  }

  return (
    <div className="app">
      <SkipLink />
      <Navigation currentPage={currentPage} onPageChange={handlePageChange} />
      <main ref={mainRef} id="main-content" tabIndex="-1" aria-label={titleForPage(currentPage)} className="app-main">
        <Suspense fallback={<div className="page-loading" role="status">Opening study tools…</div>}>
          {renderCurrentPage()}
        </Suspense>
      </main>
    </div>
  )
}

export default App
