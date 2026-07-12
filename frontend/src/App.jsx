import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import './App.css'
import Navigation from './components/Navigation'
import HomePage from './components/HomePage'
import { hashForPage, pageFromHash, titleForPage } from './routing/pageRoutes'

const TextualComparisonWorkspace = lazy(() => import('./components/TextualComparisonWorkspace'))
const AncientTexts = lazy(() => import('./components/AncientTexts'))
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

function App() {
  const [currentPage, setCurrentPage] = useState(() => pageFromHash(window.location.hash))
  const [availableBooks, setAvailableBooks] = useState(['Genesis']) // Default fallback
  const [canonicalFilter, setCanonicalFilter] = useState('ETHIO81')
  const mainRef = useRef(null)
  
  // Fetch available books from the API
  useEffect(() => {
    const fetchBooks = async () => {
      try {
        const response = await fetch(`/api/v1/books?canon=${canonicalFilter}`)
        if (response.ok) {
          const data = await response.json()
          setAvailableBooks(data.books || ['Genesis'])
        }
      } catch (error) {
        console.error('Failed to fetch books:', error)
        // Keep the default fallback
      }
    }
    
    fetchBooks()
  }, [canonicalFilter])

  useEffect(() => {
    const handleHashChange = () => setCurrentPage(pageFromHash(window.location.hash))
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  useEffect(() => {
    document.title = `${titleForPage(currentPage)} · The Unbound Bible`
    window.requestAnimationFrame(() => {
      mainRef.current?.focus({ preventScroll: true })
    })
  }, [currentPage])

  const handlePageChange = (pageId) => {
    setCurrentPage(pageId)
    const nextHash = hashForPage(pageId)
    if (window.location.hash !== nextHash) window.location.hash = nextHash
    if (pageId === 'apocrypha') {
      setCanonicalFilter('BROADER')
    }
  }

  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'home':
        return <HomePage onPageChange={handlePageChange} />
      
      case 'textual':
        return <TextualComparisonWorkspace />
      case 'apocrypha':
        return <AncientTexts
          canonicalFilter={canonicalFilter} 
          setCanonicalFilter={setCanonicalFilter}
          availableBooks={availableBooks}
          onPageChange={handlePageChange}
        />
      
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
            <SavedStudies />
          </div>
        )
      
      default:
        return <HomePage />
    }
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      {currentPage !== 'apocrypha' && <Navigation currentPage={currentPage} onPageChange={handlePageChange} />}
      <main ref={mainRef} id="main-content" tabIndex="-1" aria-label={titleForPage(currentPage)} className={currentPage === 'apocrypha' ? "app-main full-screen" : "app-main"}>
        <Suspense fallback={<div className="page-loading" role="status">Opening study tools…</div>}>
          {renderCurrentPage()}
        </Suspense>
      </main>
    </div>
  )
}

export default App
