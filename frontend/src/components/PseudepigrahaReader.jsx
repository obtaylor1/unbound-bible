import { useState, useEffect } from 'react'
import './PseudepigrahaReader.css'
import WordPopover from './WordPopover'

function PseudepigrahaReader({ selectedBook, selectedChapter, selectedVerse, onWordClick }) {
  const [bookContent, setBookContent] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [bookInfo, setBookInfo] = useState(null)
  
  // WordPopover state
  const [wordPopover, setWordPopover] = useState({
    isVisible: false,
    position: { x: 0, y: 0 },
    originalWord: '',
    meaning: '',
    contextBias: '',
    loading: false
  })

  useEffect(() => {
    if (selectedBook) {
      fetchBookContent()
    }
  }, [selectedBook])

  const fetchBookContent = async () => {
    setLoading(true)
    setError('')
    
    try {
      const response = await fetch(`/api/biblical-texts/book-content?book=${encodeURIComponent(selectedBook)}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch book content: ${response.statusText}`)
      }
      
      const data = await response.json()
      setBookContent(data.content || [])
      setBookInfo(data.book_info || null)
    } catch (err) {
      setError('Failed to load book content. Please try again.')
      console.error('Error fetching book content:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatChapterHeading = (chapter) => {
    // Handle different chapter numbering formats
    if (typeof chapter === 'number') {
      return `CHAPTER ${chapter}`
    }
    return chapter.toString().toUpperCase()
  }

  const formatBookHeading = (bookName) => {
    // Extract book number/name for heading
    if (bookName.includes('Adam and Eve')) {
      const match = bookName.match(/Adam and Eve (\d+)/)
      if (match) {
        return `BOOK ${match[1]}`
      }
    }
    
    // For other books, use the full name
    return bookName.toUpperCase()
  }

  const groupContentByStructure = () => {
    if (!bookContent.length) return {}
    
    const grouped = {}
    
    bookContent.forEach(text => {
      const bookKey = text.book
      const chapter = text.chapter || 1
      const verse = text.verse || 1
      
      if (!grouped[bookKey]) {
        grouped[bookKey] = {}
      }
      if (!grouped[bookKey][chapter]) {
        grouped[bookKey][chapter] = []
      }
      
      grouped[bookKey][chapter].push({
        verse: verse,
        text: text.text,
        id: text.id
      })
    })
    
    return grouped
  }

  const groupedContent = groupContentByStructure()
  
  // Word click handler
  const handleWordClick = async (word, event, chapterNum, verseNum) => {
    event.preventDefault()
    event.stopPropagation()
    
    const rect = event.target.getBoundingClientRect()
    const position = {
      x: rect.left + rect.width / 2,
      y: rect.top + window.scrollY
    }
    
    setWordPopover({
      isVisible: true,
      position,
      originalWord: '',
      meaning: '',
      contextBias: '',
      loading: true
    })
    
    try {
      // Create verse reference for the existing API
      const verse_ref = `${selectedBook} ${chapterNum}:${verseNum}`
      const response = await fetch(`/api/v1/context/word?word=${encodeURIComponent(word)}&verse_ref=${encodeURIComponent(verse_ref)}`)
      
      if (response.ok) {
        const data = await response.json()
        
        if (data.success && data.context) {
          const context = data.context
          let originalWord = ''
          let meaning = ''
          let contextBias = ''
          
          if (context.type === 'Linguistic') {
            originalWord = context.original_name || ''
            meaning = context.meaning || context.detailed_definition || ''
          } else if (context.type === 'Bias Alert') {
            contextBias = `${context.title}: ${context.note}`
            if (context.original_text) {
              originalWord = context.original_text
              meaning = context.literal_translation || ''
            }
          } else {
            meaning = context.message || `No context available for "${word}"`
          }
          
          setWordPopover(prev => ({
            ...prev,
            originalWord,
            meaning,
            contextBias,
            loading: false
          }))
        } else {
          setWordPopover(prev => ({
            ...prev,
            originalWord: '',
            meaning: `Definition for "${word}" not available`,
            contextBias: '',
            loading: false
          }))
        }
      } else {
        setWordPopover(prev => ({
          ...prev,
          originalWord: '',
          meaning: `Definition for "${word}" not available`,
          contextBias: '',
          loading: false
        }))
      }
    } catch (error) {
      console.error('Error fetching word context:', error)
      setWordPopover(prev => ({
        ...prev,
        originalWord: '',
        meaning: 'Failed to load word information',
        contextBias: '',
        loading: false
      }))
    }
  }
  
  // Close word popover
  const closeWordPopover = () => {
    setWordPopover({
      isVisible: false,
      position: { x: 0, y: 0 },
      originalWord: '',
      meaning: '',
      contextBias: '',
      loading: false
    })
  }
  
  // Function to wrap words in clickable spans with visual indicators
  const wrapWordsInClickableSpans = (text, chapterNum, verseNum) => {
    if (!text) return ''
    
    // Split text into words, preserving punctuation and spacing
    const words = text.split(/(\s+|[^\w\s])/g)
    
    return words.map((segment, index) => {
      // Skip whitespace and punctuation
      if (/^\s*$/.test(segment) || /^[^\w\s]*$/.test(segment)) {
        return segment
      }
      
      // Clean the word for processing (remove punctuation)
      const cleanWord = segment.replace(/[^\w]/g, '')
      if (cleanWord.length < 2) return segment
      
      // Check if word should be highlighted (proper nouns, key terms)
      const shouldHighlight = /^[A-Z]/.test(cleanWord) || 
                             ['Satan', 'Adam', 'Eve', 'God', 'Lord', 'Cave', 'Treasures', 'Ethiopic', 'Geez'].some(term => 
                               cleanWord.toLowerCase().includes(term.toLowerCase()))
      
      return (
        <span
          key={index}
          className={`pseudepigrapha-clickable-word ${shouldHighlight ? 'highlighted-word' : ''}`}
          onClick={(e) => handleWordClick(cleanWord, e, chapterNum, verseNum)}
        >
          {segment}
        </span>
      )
    })
  }

  if (loading) {
    return (
      <div className="pseudepigrapha-reader">
        <div className="pseudepigrapha-loading">
          <div className="loading-spinner"></div>
          <p>Loading Pseudepigraphal text...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="pseudepigrapha-reader">
        <div className="pseudepigrapha-error">
          <h3>Error Loading Content</h3>
          <p>{error}</p>
          <button className="retry-button" onClick={fetchBookContent}>
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="pseudepigrapha-reader">
      {/* Panel Header with Title and Tags */}
      <div className="pseudepigrapha-header">
        <div className="title-section">
          <h2 className="pseudepigrapha-title">The Book of Adam and Eve (Conflict with Satan)</h2>
          <div className="source-tags">
            <span className="tag ethiopic-tag">Ethiopic Source</span>
            <span className="tag translation-tag">PD Translation</span>
          </div>
        </div>
        <div className="book-stats">
          <span className="content-count">{bookContent.length} sections</span>
        </div>
      </div>

      {/* Scrollable Content Area */}
      <div className="pseudepigrapha-content">
        {Object.keys(groupedContent).length === 0 ? (
          <div className="no-content">
            <p>No content available for this selection.</p>
          </div>
        ) : (
          Object.entries(groupedContent).map(([book, chapters]) => (
            <div key={book} className="book-section">
              <h2 className="book-heading">{formatBookHeading(book)}</h2>
              
              {Object.entries(chapters)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([chapter, verses]) => (
                  <div key={chapter} className="chapter-section">
                    <h3 className="chapter-heading">{formatChapterHeading(chapter)}</h3>
                    
                    <div className="verses-container">
                      {verses
                        .sort((a, b) => a.verse - b.verse)
                        .map(({ verse, text, id }) => (
                          <div key={id} className="verse-block">
                            <span className="verse-number">{verse}</span>
                            <div className="verse-text">
                              {wrapWordsInClickableSpans(text, parseInt(chapter), verse)}
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  </div>
                ))
              }
            </div>
          ))
        )}
      </div>

      {/* Word Popover */}
      <WordPopover
        isVisible={wordPopover.isVisible}
        position={wordPopover.position}
        originalWord={wordPopover.originalWord}
        meaning={wordPopover.meaning}
        contextBias={wordPopover.contextBias}
        loading={wordPopover.loading}
        onClose={closeWordPopover}
      />
    </div>
  )
}

export default PseudepigrahaReader