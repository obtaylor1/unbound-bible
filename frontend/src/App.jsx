import { useState, useEffect } from 'react'
import './App.css'
import Navigation from './components/Navigation'
import HomePage from './components/HomePage'
import TextualComparison from './components/TextualComparison'
import SermonAnalyzer from './components/SermonAnalyzer'
import InteractiveMap from './components/InteractiveMap'
import ForumPage from './components/ForumPage'
import ChatInterface from './components/ChatInterface'

function App() {
  const [currentPage, setCurrentPage] = useState('home')
  const [selectedVerse, setSelectedVerse] = useState({ book: 'Genesis', chapter: 1, verse: 1 })
  const [availableBooks, setAvailableBooks] = useState(['Genesis']) // Default fallback
  const [canonicalFilter, setCanonicalFilter] = useState('PROT66')
  
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

  const handlePageChange = (pageId) => {
    setCurrentPage(pageId)
  }

  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'home':
        return <HomePage onPageChange={handlePageChange} />
      
      case 'textual':
        return <TextualComparison 
          canonicalFilter={canonicalFilter} 
          setCanonicalFilter={setCanonicalFilter}
          availableBooks={availableBooks}
        />
      
      case 'sermon':
        return (
          <div className="page-container">
            <div className="page-header">
              <h1>Sermon Analysis</h1>
              <p>Upload and analyze sermons for biblical and historical context</p>
            </div>
            <SermonAnalyzer />
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
            <ChatInterface />
          </div>
        )
      
      default:
        return <HomePage />
    }
  }

  return (
    <div className="app">
      <Navigation currentPage={currentPage} onPageChange={handlePageChange} />
      <main className="app-main">
        {renderCurrentPage()}
      </main>
    </div>
  )
}

export default App
