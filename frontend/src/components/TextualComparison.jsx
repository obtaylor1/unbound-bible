import { useState, useEffect, useRef } from 'react'
import './TextualComparison.css'
import WordContextPopover from './WordContextPopover'
import ApocryphaReader from './ApocryphaReader'
import PseudepigrahaReader from './PseudepigrahaReader'
import WordPopover from './WordPopover'

function TextualComparison({ canonicalFilter = 'PROT66', setCanonicalFilter, availableBooks = [] }) {
  const [selectedBook, setSelectedBook] = useState('John')
  const [selectedChapter, setSelectedChapter] = useState('3')
  const [selectedVerse, setSelectedVerse] = useState('16')
  const [selectedCanon, setSelectedCanon] = useState('Protestant')
  const [translations, setTranslations] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedWord, setSelectedWord] = useState(null)
  const [showWordPopup, setShowWordPopup] = useState(false)
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 })
  const [wordContextData, setWordContextData] = useState(null)
  const [wordContextLoading, setWordContextLoading] = useState(false)
  const [popularVerse, setPopularVerse] = useState('')
  
  // Myth-Buster state
  const [showMythBuster, setShowMythBuster] = useState(false)
  const [mythBusterContent, setMythBusterContent] = useState(null)
  const [mythBusterLoading, setMythBusterLoading] = useState(false)
  const [mythBusterError, setMythBusterError] = useState('')
  
  // AI Chat integration state
  const [aiMessages, setAIMessages] = useState([
    {
      type: 'assistant',
      content: 'What is the difference between agape and philos love?',
      timestamp: new Date().toISOString()
    },
    {
      type: 'user',
      content: 'Agape (ἀγάπη) refers to unconditional, divine love - the highest form of love that seeks the best for others regardless of personal affection or shared interests.',
      timestamp: new Date().toISOString()
    }
  ])
  const [aiInputValue, setAIInputValue] = useState('')
  const [aiLoading, setAILoading] = useState(false)
  const [aiError, setAIError] = useState('')
  
  // State for broader canon books
  const [broaderCanonBooks, setBroaderCanonBooks] = useState([])
  const [loadingBroaderBooks, setLoadingBroaderBooks] = useState(false)
  
  // WordPopover state
  const [wordPopover, setWordPopover] = useState({
    isVisible: false,
    position: { x: 0, y: 0 },
    originalWord: '',
    meaning: '',
    contextBias: '',
    loading: false
  })
  
  // Determine if current book is non-canonical (should use ApocryphaReader)
  const isNonCanonicalBook = (bookName) => {
    const nonCanonicalBooks = [
      '1 Enoch', 'Enoch',
      'Jubilees',
      'Adam and Eve 2', 'Adam and Eve 3',
      'Book of Adam and Eve',
      'Meqabyan 1', 'Meqabyan 2', 'Meqabyan 3',
      'Book of Abraham',
      'Ascension of Isaiah',
      'Book of Josephus',
      'Didascalia',
      'Gitsew',
      'Sirate Tsion',
      'Tizaz',
      '1st Book of Dominos', '2nd Book of Dominos',
      'Abtilis',
      'Book of Qäləmentos'
    ]
    return nonCanonicalBooks.includes(bookName) || bookName.includes('Adam and Eve')
  }
  
  // Determine which reader to show
  const shouldShowPseudepigrahaReader = selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' && selectedBook.includes('Adam and Eve')
  const shouldShowApocryphaReader = selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' && isNonCanonicalBook(selectedBook) && !shouldShowPseudepigrahaReader

  // Translation bias database for key verses
  const getBiasAlerts = () => {
    const verseRef = `${selectedBook} ${selectedChapter}:${selectedVerse}`
    const alerts = []

    if (selectedBook === 'Song of Solomon' && selectedChapter === '1' && selectedVerse === '5') {
      alerts.push({
        severity: 'high',
        title: 'KJV Conjunctive Bias — "but" vs "and"',
        original: 'שְׁחוֹרָה אֲנִי וְנָאוָה (sh\'chorah ani v\'na\'vah)',
        literal: '"I am black AND beautiful"',
        kjv: '"I am black BUT comely"',
        explanation: 'The Hebrew conjunction "וְ" (vav) means "and" — not "but." The KJV insertion of a contrast ("but comely") implies a tension between blackness and beauty that does not exist in the original Hebrew. Scholar Wilda Gafney notes this reflects the translators\' inability to regard blackness as beautiful without qualification.',
        scholar: 'Wilda Gafney, Hebrew Bible Scholar'
      })
    }

    if (selectedBook === 'Exodus' && selectedChapter === '12' && selectedVerse === '38') {
      alerts.push({
        severity: 'medium',
        title: 'KJV Obscures Ethnic Diversity',
        original: 'עֵרֶב רַב (erev rav)',
        literal: '"A great mixed multitude" — ethnically diverse crowd',
        kjv: '"A mixed multitude went up also with them"',
        explanation: 'Scholar Esau McCaulley argues the Hebrew phrase "erev rav" specifically emphasizes ethnic diversity — likely including Egyptians, Cushites (Africans), and others. The KJV\'s generic phrasing "mixed multitude" fails to communicate the multi-ethnic nature of the Exodus event, erasing the presence of African peoples who left Egypt alongside the Israelites.',
        scholar: 'Esau McCaulley, New Testament Scholar'
      })
    }

    // General bias note for all verses
    if (alerts.length === 0) {
      alerts.push({
        severity: 'info',
        title: 'Translation Bias Awareness',
        explanation: 'All translations reflect the cultural and theological perspectives of their translation committees. Key verses to examine: Song of Solomon 1:5 ("black AND beautiful" vs "black but comely") and Exodus 12:38 (ethnic diversity in the Exodus). For this verse, compare the KJV with modern translations for any significant word-choice differences.',
        scholar: null
      })
    }

    return alerts
  }
  
  // Effect to handle canon changes and book availability
  useEffect(() => {
    const currentBooks = getBooksForSelectedCanon()
    if (currentBooks.length > 0 && !currentBooks.includes(selectedBook)) {
      setSelectedBook(currentBooks[0])
      setSelectedChapter('1')
      setSelectedVerse('1')
    }
  }, [selectedCanon, broaderCanonBooks])

  // Effect to update AI messages when Adam and Eve is selected
  useEffect(() => {
    if (shouldShowPseudepigrahaReader) {
      const knowledgeBaseMessages = [
        {
          type: 'system',
          content: 'Knowledge Base Updated. I can now reference The Book of Adam and Eve.',
          timestamp: new Date().toISOString(),
          isSystemNotification: true
        },
        {
          type: 'user',
          content: 'Tell me about Adam\'s trials in the Cave of Treasures.',
          timestamp: new Date().toISOString()
        },
        {
          type: 'assistant',
          content: 'According to The Book of Adam and Eve, after being expelled from Paradise, Adam and Eve dwelt in the Cave of Treasures where they faced numerous trials. Satan repeatedly attempted to deceive them, appearing in various forms to tempt them back into sin. The cave became a place of both refuge and testing, where Adam struggled with despair over losing Paradise while slowly learning to trust in God\'s promise of future redemption through the coming Messiah.',
          timestamp: new Date().toISOString()
        }
      ]
      setAIMessages(knowledgeBaseMessages)
    } else {
      // Reset to default messages when not showing Adam and Eve
      setAIMessages([
        {
          type: 'assistant',
          content: 'What is the difference between agape and philos love?',
          timestamp: new Date().toISOString()
        },
        {
          type: 'user',
          content: 'Agape (ἀγάπη) refers to unconditional, divine love - the highest form of love that seeks the best for others regardless of personal affection or shared interests.',
          timestamp: new Date().toISOString()
        }
      ])
    }
  }, [shouldShowPseudepigrahaReader])
  
  // Effect to fetch broader canon books on initial load if needed
  useEffect(() => {
    if (selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' && broaderCanonBooks.length === 0) {
      fetchBroaderCanonBooks()
    }
  }, [selectedCanon])
  
  // Word click handler
  const handleWordClick = async (word, event) => {
    event.preventDefault()
    event.stopPropagation()
    
    const rect = event.target.getBoundingClientRect()
    const position = {
      x: rect.left + rect.width / 2,
      y: rect.top
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
      const verse_ref = `${selectedBook} ${selectedChapter}:${selectedVerse}`
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
  
  // Function to wrap words in clickable spans
  const wrapWordsInSpans = (text) => {
    if (!text) return text
    
    return text.split(/\b/).map((part, index) => {
      // Check if the part is a word (contains letters)
      if (/[a-zA-Z]/.test(part) && part.length > 1) {
        return (
          <span 
            key={index}
            className="clickable-word"
            onClick={(e) => handleWordClick(part, e)}
            style={{ cursor: 'pointer', padding: '1px' }}
          >
            {part}
          </span>
        )
      }
      return part
    })
  }

  // Biblical books list
  const books = [
    'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth',
    '1 Samuel', '2 Samuel', '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles', 'Ezra', 'Nehemiah',
    'Esther', 'Job', 'Psalms', 'Proverbs', 'Ecclesiastes', 'Song of Solomon', 'Isaiah', 'Jeremiah',
    'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos', 'Obadiah', 'Jonah', 'Micah',
    'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah', 'Malachi', 'Matthew', 'Mark', 'Luke',
    'John', 'Acts', 'Romans', '1 Corinthians', '2 Corinthians', 'Galatians', 'Ephesians',
    'Philippians', 'Colossians', '1 Thessalonians', '2 Thessalonians', '1 Timothy', '2 Timothy',
    'Titus', 'Philemon', 'Hebrews', 'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John',
    'Jude', 'Revelation'
  ]

  // Chapter counts for each book
  const bookChapters = {
    'Genesis': 50, 'Exodus': 40, 'Leviticus': 27, 'Numbers': 36, 'Deuteronomy': 34,
    'Joshua': 24, 'Judges': 21, 'Ruth': 4, '1 Samuel': 31, '2 Samuel': 24,
    '1 Kings': 22, '2 Kings': 25, '1 Chronicles': 29, '2 Chronicles': 36,
    'Ezra': 10, 'Nehemiah': 13, 'Esther': 10, 'Job': 42, 'Psalms': 150,
    'Proverbs': 31, 'Ecclesiastes': 12, 'Song of Solomon': 8, 'Isaiah': 66,
    'Jeremiah': 52, 'Lamentations': 5, 'Ezekiel': 48, 'Daniel': 12,
    'Hosea': 14, 'Joel': 3, 'Amos': 9, 'Obadiah': 1, 'Jonah': 4,
    'Micah': 7, 'Nahum': 3, 'Habakkuk': 3, 'Zephaniah': 3, 'Haggai': 2,
    'Zechariah': 14, 'Malachi': 4, 'Matthew': 28, 'Mark': 16, 'Luke': 24,
    'John': 21, 'Acts': 28, 'Romans': 16, '1 Corinthians': 16, '2 Corinthians': 13,
    'Galatians': 6, 'Ephesians': 6, 'Philippians': 4, 'Colossians': 4,
    '1 Thessalonians': 5, '2 Thessalonians': 3, '1 Timothy': 6, '2 Timothy': 4,
    'Titus': 3, 'Philemon': 1, 'Hebrews': 13, 'James': 5, '1 Peter': 5,
    '2 Peter': 3, '1 John': 5, '2 John': 1, '3 John': 1, 'Jude': 1, 'Revelation': 22
  }

  // Canonical traditions
  const canonOptions = [
    {
      name: 'Protestant',
      code: 'PROT66',
      bookCount: 66,
      description: 'Standard Protestant Bible used by most Western Christianity',
      tradition: 'Reformation Era',
      details: 'Most widely used canon in Western Christianity'
    },
    {
      name: 'Ethiopian Orthodox',
      code: 'ETHIO81',
      bookCount: 81,
      description: 'Ancient African Christian tradition with additional books',
      tradition: 'Ancient African Tradition',
      details: 'Includes Enoch, Jubilees, and other texts referenced by early Christians'
    },
    {
      name: 'Catholic',
      code: 'CATH73',
      bookCount: 73,
      description: 'Roman Catholic Bible including deuterocanonical books',
      tradition: 'Council of Trent 1546',
      details: 'Includes Wisdom literature and historical books from the Septuagint'
    },
    {
      name: 'Broader Canon or Scholarly Pseudepigrapha',
      code: 'BROADER',
      bookCount: '85+',
      description: 'Includes extra-canonical texts like Jubilees, Enoch, and the Book of Adam and Eve',
      tradition: 'Research Collection',
      details: 'Comprehensive collection including pseudepigraphal and apocryphal texts',
      isSpecial: true
    }
  ]

  // Sample translations for display
  const sampleTranslations = {
    'KJV': {
      name: 'King James Version',
      text: 'For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.',
      language: 'English'
    },
    'NLT': {
      name: 'New Living Translation',
      text: 'For this is how God loved the world: He gave his one and only Son, so that everyone who believes in him will not perish but have eternal life.',
      language: 'English'
    },
    'ESV': {
      name: 'Ethiopian Standard Version',
      text: 'For God so loved the world, that he gave his only Son, that whoever believes in him should not perish but have eternal life.',
      language: 'Ge\'ez/English'
    }
  }

  // Popular verses options
  const popularVerses = [
    { label: 'John 3:16', book: 'John', chapter: 3, verse: 16 },
    { label: 'Romans 8:28', book: 'Romans', chapter: 8, verse: 28 },
    { label: 'Psalms 23:1', book: 'Psalms', chapter: 23, verse: 1 },
    { label: 'Jeremiah 29:11', book: 'Jeremiah', chapter: 29, verse: 11 },
    { label: '1 John 4:8', book: '1 John', chapter: 4, verse: 8 }
  ]

  // Handle canon selection
  const handleCanonSelect = (canon) => {
    setSelectedCanon(canon.name)
    if (setCanonicalFilter) {
      setCanonicalFilter(canon.code)
    }
    
    // If Broader Canon is selected, fetch available books from database
    if (canon.code === 'BROADER') {
      fetchBroaderCanonBooks()
    }
  }
  
  // Fetch broader canon books from database
  const fetchBroaderCanonBooks = async () => {
    setLoadingBroaderBooks(true)
    try {
      const response = await fetch('/api/biblical-texts/available-books')
      if (response.ok) {
        const data = await response.json()
        setBroaderCanonBooks(data.books || [])
      } else {
        console.error('Failed to fetch broader canon books')
      }
    } catch (error) {
      console.error('Error fetching broader canon books:', error)
    } finally {
      setLoadingBroaderBooks(false)
    }
  }

  // Handle popular verse selection
  const handlePopularVerseSelect = (verse) => {
    if (verse) {
      const selected = popularVerses.find(v => v.label === verse)
      if (selected) {
        setSelectedBook(selected.book)
        setSelectedChapter(selected.chapter.toString())
        setSelectedVerse(selected.verse.toString())
      }
    }
  }

  // Myth-Buster functionality
  const handleMythBusterClick = async () => {
    setMythBusterLoading(true)
    setMythBusterError('')
    
    try {
      const response = await fetch(`/api/v1/myth-buster?book=${encodeURIComponent(selectedBook)}&chapter=${selectedChapter}&verse=${selectedVerse}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      })
      
      if (!response.ok) {
        throw new Error(`Failed to generate myth-buster content: ${response.statusText}`)
      }
      
      const data = await response.json()
      setMythBusterContent(data.myth_buster)
      setShowMythBuster(true)
    } catch (error) {
      setMythBusterError('Failed to generate myth-buster content. Please try again.')
      console.error('Myth-buster error:', error)
    } finally {
      setMythBusterLoading(false)
    }
  }

  // AI Chat functionality
  const handleAISubmit = async (e) => {
    e.preventDefault()
    if (!aiInputValue.trim() || aiLoading) return

    const userMessage = {
      type: 'user',
      content: aiInputValue,
      timestamp: new Date().toISOString()
    }

    setAIMessages(prev => [...prev, userMessage])
    setAIInputValue('')
    setAILoading(true)
    setAIError('')

    try {
      // Simulate AI response for now
      setTimeout(() => {
        const aiMessage = {
          type: 'assistant',
          content: `Great question about ${selectedBook} ${selectedChapter}:${selectedVerse}! This verse explores themes of divine love, sacrifice, and eternal life. The Greek word "agape" used here represents unconditional, divine love that transcends human emotions.`,
          timestamp: new Date().toISOString()
        }
        setAIMessages(prev => [...prev, aiMessage])
        setAILoading(false)
      }, 1500)
    } catch (error) {
      setAIError('Failed to get AI response')
      setAILoading(false)
    }
  }

  // Translation Box Button Handlers
  const handleCopyText = async () => {
    // Create text content with all translations
    let textToCopy = `${selectedBook} ${selectedChapter}:${selectedVerse}\n\n`
    
    Object.entries(sampleTranslations).forEach(([key, translation]) => {
      textToCopy += `${translation.name} (${translation.language}):\n`
      textToCopy += `${translation.text}\n\n`
    })
    
    try {
      await navigator.clipboard.writeText(textToCopy)
    } catch (error) {
      console.error('Failed to copy text:', error)
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = textToCopy
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
    }
  }

  const handlePrint = () => {
    window.print()
  }

  const handleExport = () => {
    // Create export content
    let exportContent = `Biblical Verse Analysis Export\n`
    exportContent += `Generated on: ${new Date().toLocaleString()}\n`
    exportContent += `Canon: ${selectedCanon}\n\n`
    exportContent += `========================================\n`
    exportContent += `${selectedBook} ${selectedChapter}:${selectedVerse}\n`
    exportContent += `========================================\n\n`
    
    // Add translations
    exportContent += `TRANSLATIONS:\n\n`
    Object.entries(sampleTranslations).forEach(([key, translation]) => {
      exportContent += `${translation.name} (${translation.language}):\n`
      exportContent += `${translation.text}\n\n`
    })
    
    // Add analysis content if available
    exportContent += `ANALYSIS:\n\n`
    exportContent += `Meaning of the Scripture:\n`
    exportContent += `This passage represents one of Christianity's most profound spiritual insights. The verse encapsulates themes of faith, redemption, and divine love, central to biblical teaching.\n\n`
    
    exportContent += `Translation Comparison:\n`
    exportContent += `Comparing the translations across the different versions shows consistency in core messaging while varying in linguistic style.\n\n`
    
    // Add myth-buster content if available
    if (mythBusterContent) {
      exportContent += `MYTH-BUSTER ANALYSIS:\n\n`
      exportContent += `${mythBusterContent.myth_title}\n`
      exportContent += `${mythBusterContent.myth_content}\n\n`
      exportContent += `Historical Facts:\n`
      exportContent += `${mythBusterContent.historical_facts}\n\n`
      if (mythBusterContent.verse_connection) {
        exportContent += `Verse Connection:\n`
        exportContent += `${mythBusterContent.verse_connection}\n\n`
      }
    }
    
    // Create and download file
    const blob = new Blob([exportContent], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${selectedBook}_${selectedChapter}_${selectedVerse}_Analysis.txt`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // Calculate statistics based on selected canon
  const getCanonStats = () => {
    const selectedCanonData = canonOptions.find(c => c.name === selectedCanon)
    let totalBooks = selectedCanonData ? selectedCanonData.bookCount : 66
    
    // For broader canon, use actual count from database if available
    if (selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' && broaderCanonBooks.length > 0) {
      totalBooks = broaderCanonBooks.length
    }
    
    return {
      totalBooks: totalBooks,
      availableForStudy: selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' ? broaderCanonBooks.length : 3,
      inProcesses: 0
    }
  }
  
  // Get books list based on selected canon
  const getBooksForSelectedCanon = () => {
    if (selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha') {
      return broaderCanonBooks.length > 0 ? broaderCanonBooks : books
    }
    return books
  }

  const stats = getCanonStats()

  // If we should show the PseudepigrahaReader or ApocryphaReader, render it instead of the normal view
  if (shouldShowPseudepigrahaReader || shouldShowApocryphaReader) {
    return (
      <div className="text-comparison-container">
        {/* Biblical Canon Selection - keep visible */}
        <div className="canon-selection-section">
          <div className="section-header">
            <div className="section-icon">📚</div>
            <h2>Biblical Canon Selection</h2>
            <div className="section-badge">+</div>
          </div>
          
          <div className="canon-cards-grid">
            {canonOptions.map((canon) => (
              <div 
                key={canon.code}
                className={`canon-card ${selectedCanon === canon.name ? 'selected' : ''} ${canon.isSpecial ? 'special-canon' : ''}`}
                onClick={() => handleCanonSelect(canon)}
              >
                <div className="canon-header">
                  <div className="canon-radio">
                    <div className={`radio-dot ${selectedCanon === canon.name ? 'active' : ''}`}></div>
                  </div>
                  <div className="canon-info">
                    <h3>{canon.name}</h3>
                    <div className="canon-count">{canon.bookCount} books</div>
                    <div className="canon-period">{canon.tradition}</div>
                  </div>
                </div>
                <p className="canon-description">{canon.description}</p>
                <div className="canon-details">
                  <div className="canon-tradition">{canon.tradition}</div>
                  <div className="canon-extra-info">{canon.details}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Statistics Section */}
        <div className="statistics-section">
          <div className="stat-item">
            <div className="stat-number">{stats.totalBooks}</div>
            <div className="stat-label">Total Books</div>
          </div>
          <div className="stat-item">
            <div className="stat-number available">{stats.availableForStudy}</div>
            <div className="stat-label">Available for Study</div>
          </div>
          <div className="stat-item">
            <div className="stat-number processes">{stats.inProcesses}</div>
            <div className="stat-label">In Processes</div>
          </div>
        </div>

        {/* Book Selection for Apocrypha */}
        <div className="popular-verses-section">
          <label htmlFor="apocrypha-book-select">Select Book to Read</label>
          <select 
            id="apocrypha-book-select"
            value={selectedBook}
            onChange={(e) => setSelectedBook(e.target.value)}
            className="popular-verses-dropdown"
            disabled={loadingBroaderBooks}
          >
            {loadingBroaderBooks ? (
              <option>Loading books...</option>
            ) : (
              getBooksForSelectedCanon().filter(book => isNonCanonicalBook(book)).map(book => (
                <option key={book} value={book}>{book}</option>
              ))
            )}
          </select>
        </div>
        
        {/* Pseudepigrapha or Apocrypha Reader Component */}
        {shouldShowPseudepigrahaReader ? (
          <PseudepigrahaReader 
            selectedBook={selectedBook}
            selectedChapter={selectedChapter}
            selectedVerse={selectedVerse}
          />
        ) : (
          <ApocryphaReader 
            selectedBook={selectedBook}
            selectedChapter={selectedChapter}
            selectedVerse={selectedVerse}
          />
        )}
      </div>
    )
  }

  return (
    <div className="text-comparison-container">
      {/* Introductory Text */}
      <div className="intro-section">
        <div className="intro-content">
          <h2 className="intro-title">Explore Biblical Texts with Enhanced Analysis</h2>
          <p className="intro-description">
            Select a text from the <strong>Broader Canon or Scholarly Pseudepigrapha</strong> to explore Apocryphal works like the Book of Adam and Eve, 
            1 Enoch, and Jubilees. Click any word in the main texts to uncover linguistic roots, original Hebrew/Greek meanings, 
            and historical context that reveals translation biases and cultural interpretations.
          </p>
        </div>
      </div>

      {/* Biblical Canon Selection */}
      <div className="canon-selection-section">
        <div className="section-header">
          <div className="section-icon">📚</div>
          <h2>Biblical Canon Selection</h2>
          <div className="section-badge">+</div>
        </div>
        
        <div className="canon-cards-grid">
          {canonOptions.map((canon) => (
            <div 
              key={canon.code}
              className={`canon-card ${selectedCanon === canon.name ? 'selected' : ''} ${canon.isSpecial ? 'special-canon' : ''}`}
              onClick={() => handleCanonSelect(canon)}
            >
              <div className="canon-header">
                <div className="canon-radio">
                  <div className={`radio-dot ${selectedCanon === canon.name ? 'active' : ''}`}></div>
                </div>
                <div className="canon-info">
                  <h3>{canon.name}</h3>
                  <div className="canon-count">{canon.bookCount} books</div>
                  <div className="canon-period">{canon.tradition}</div>
                </div>
              </div>
              <p className="canon-description">{canon.description}</p>
              <div className="canon-details">
                <div className="canon-tradition">{canon.tradition}</div>
                <div className="canon-extra-info">{canon.details}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Statistics Section */}
      <div className="statistics-section">
        <div className="stat-item">
          <div className="stat-number">{stats.totalBooks}</div>
          <div className="stat-label">Total Books</div>
        </div>
        <div className="stat-item">
          <div className="stat-number available">{stats.availableForStudy}</div>
          <div className="stat-label">Available for Study</div>
        </div>
        <div className="stat-item">
          <div className="stat-number processes">{stats.inProcesses}</div>
          <div className="stat-label">In Processes</div>
        </div>
      </div>

      {/* Popular Verses Section */}
      <div className="popular-verses-section">
        <label htmlFor="popular-verses">Popular Verses</label>
        <select 
          id="popular-verses"
          value={popularVerse}
          onChange={(e) => {
            setPopularVerse(e.target.value)
            handlePopularVerseSelect(e.target.value)
          }}
          className="popular-verses-dropdown"
        >
          <option value="">Select a popular verse...</option>
          {popularVerses.map((verse) => (
            <option key={verse.label} value={verse.label}>
              {verse.label}
            </option>
          ))}
        </select>
      </div>

      {/* Main Content Grid */}
      <div className="main-content-grid">
        {/* Textual Comparison Panel */}
        <div className="panel textual-comparison-panel">
          <div className="panel-header">
            <div className="panel-icon">📖</div>
            <h3>Textual Comparison & Linguistic Analysis</h3>
            <div className="panel-badge">Protestant</div>
          </div>
          
          <div className="verse-display">
            <h4>{selectedBook} {selectedChapter}:{selectedVerse}</h4>
            <div className="translations-list">
              {Object.entries(sampleTranslations).map(([key, translation]) => (
                <div key={key} className="translation-item">
                  <div className="translation-header">
                    <span className="translation-name">{translation.name}</span>
                    <span className="translation-language">{translation.language}</span>
                  </div>
                  <div className="translation-text">{wrapWordsInSpans(translation.text)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Verse Control Panel */}
        <div className="panel verse-control-panel">
          <div className="panel-header">
            <h3>Verse Control</h3>
          </div>
          
          <div className="verse-controls">
            <div className="control-group">
              <label>{selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' ? 'Book/Section' : 'Book'}</label>
              <select 
                value={selectedBook} 
                onChange={(e) => setSelectedBook(e.target.value)}
                className="verse-dropdown"
                disabled={selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' && loadingBroaderBooks}
              >
                {selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' && loadingBroaderBooks ? (
                  <option>Loading books...</option>
                ) : (
                  getBooksForSelectedCanon().map(book => (
                    <option key={book} value={book}>{book}</option>
                  ))
                )}
              </select>
            </div>
            
            <div className="control-row">
              <div className="control-group">
                <label>{selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' ? 'Ch/Para' : 'Ch'}</label>
                <select 
                  value={selectedChapter} 
                  onChange={(e) => setSelectedChapter(e.target.value)}
                  className="verse-dropdown small"
                >
                  {Array.from({ length: bookChapters[selectedBook] || 50 }, (_, i) => i + 1).map(num => (
                    <option key={num} value={num}>{num}</option>
                  ))}
                </select>
              </div>
              
              <div className="control-group">
                <label>V</label>
                <select 
                  value={selectedVerse} 
                  onChange={(e) => setSelectedVerse(e.target.value)}
                  className="verse-dropdown small"
                >
                  {Array.from({ length: 50 }, (_, i) => i + 1).map(num => (
                    <option key={num} value={num}>{num}</option>
                  ))}
                </select>
              </div>
            </div>
            
            <div className="action-buttons">
              <button 
                className="action-btn myth-buster" 
                onClick={handleMythBusterClick}
                disabled={mythBusterLoading}
              >
                {mythBusterLoading ? 'Analyzing...' : 'Myth-Buster'}
              </button>
              <button className="action-btn hide-analysis">Hide Analysis</button>
            </div>
            
            {/* Myth-Buster Content Section */}
            {showMythBuster && mythBusterContent && (
              <div className="myth-buster-section">
                <h4 className="myth-title">{mythBusterContent.myth_title}</h4>
                <p className="myth-content">{mythBusterContent.myth_content}</p>
                <p className="historical-facts">{mythBusterContent.historical_facts}</p>
                {mythBusterContent.verse_connection && (
                  <p className="verse-connection"><em>{mythBusterContent.verse_connection}</em></p>
                )}
              </div>
            )}
            
            {mythBusterError && (
              <div className="myth-buster-error">
                <p>{mythBusterError}</p>
              </div>
            )}
            
            <div className="translation-buttons">
              <button 
                className="translation-btn copy-btn" 
                onClick={handleCopyText}
                title="Copy verse text to clipboard"
              >
                <span className="btn-icon">📋</span>
                <span className="btn-text">Copy Text</span>
              </button>
              <button 
                className="translation-btn print-btn" 
                onClick={handlePrint}
                title="Print current page"
              >
                <span className="btn-icon">🖨️</span>
                <span className="btn-text">Print</span>
              </button>
              <button 
                className="translation-btn export-btn" 
                onClick={handleExport}
                title="Export verse and analysis to text file"
              >
                <span className="btn-icon">📤</span>
                <span className="btn-text">Export</span>
              </button>
            </div>
          </div>
        </div>

        {/* In-Depth Verse Analysis Panel */}
        <div className="panel analysis-panel">
          <div className="panel-header">
            <div className="panel-icon">📖</div>
            <h3>In-Depth Verse Analysis</h3>
            <div className="panel-close">×</div>
          </div>
          
          <div className="analysis-content">
            <div className="analysis-section">
              <h4>Meaning of the Scripture</h4>
              <p>This passage represents one of Christianity's most profound spiritual insights. The verse encapsulates themes of faith, redemption, and divine love, central to biblical teaching.</p>
            </div>
            
            <div className="analysis-section">
              <h4>Translation Comparison</h4>
              <p>Comparing the translations across the KJV and ASV show consistency in core messaging while varying in linguistic style.</p>
              
              <div className="comparison-verses">
                <div className="verse-comparison">
                  <strong>ASV</strong>
                  <p>For God so loved the world, that he gave his only begotten Son, that whosoever believeth on him should not perish, but have eternal life.</p>
                </div>
                <div className="verse-comparison">
                  <strong>KJV</strong>
                  <p>For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.</p>
                </div>
              </div>
            </div>
            
            {/* Translation Bias Alerts */}
            <div className="analysis-section bias-section">
              <h4 className="bias-section-title">
                <span className="bias-icon">⚠️</span>
                Translation Bias Alerts
              </h4>
              {getBiasAlerts().map((alert, i) => (
                <div key={i} className={`bias-alert bias-${alert.severity}`}>
                  <div className="bias-alert-header">
                    <span className={`bias-badge badge-${alert.severity}`}>
                      {alert.severity === 'high' ? '🔴 High' : alert.severity === 'medium' ? '🟡 Medium' : 'ℹ️ Note'}
                    </span>
                    <strong className="bias-title">{alert.title}</strong>
                  </div>
                  {alert.original && (
                    <div className="bias-original">
                      <span className="bias-label">Original:</span>
                      <span className="bias-hebrew">{alert.original}</span>
                    </div>
                  )}
                  {alert.literal && (
                    <div className="bias-row">
                      <span className="bias-label">Literal:</span>
                      <span className="bias-literal">{alert.literal}</span>
                    </div>
                  )}
                  {alert.kjv && (
                    <div className="bias-row">
                      <span className="bias-label">KJV:</span>
                      <span className="bias-kjv">{alert.kjv}</span>
                    </div>
                  )}
                  <p className="bias-explanation">{alert.explanation}</p>
                  {alert.scholar && (
                    <div className="bias-scholar">
                      <span className="scholar-icon">🎓</span>
                      <em>{alert.scholar}</em>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="analysis-section">
              <h4>Cross References</h4>
              <div className="cross-references">
                <div className="reference-item">
                  <strong>Genesis 6:1</strong>
                  <p>"But God demonstrates his own love for us in this: While we were still sinners, Christ died for us."</p>
                </div>
                <div className="reference-item">
                  <strong>1 John 4:9</strong>
                  <p>"This is how God showed his love among us: He sent his one and only Son into the world that we might live through him."</p>
                </div>
                <div className="reference-item">
                  <strong>Romans 5:8</strong>
                  <p>"He who did not spare his own Son, but gave him up for us all—how will he not also, along with him, graciously give us all things?"</p>
                </div>
              </div>
            </div>
            
            <div className="analysis-section">
              <h4>Key Themes</h4>
              <div className="theme-tags">
                <span className="theme-tag">Divine Love</span>
                <span className="theme-tag">Sacrifice</span>
                <span className="theme-tag">Faith</span>
                <span className="theme-tag">Eternal Life</span>
                <span className="theme-tag">Universal Salvation</span>
              </div>
            </div>
          </div>
        </div>

        {/* AI Study Assistant Panel */}
        <div className="panel ai-assistant-panel">
          <div className="panel-header">
            <div className="panel-icon">🤖</div>
            <h3>AI Study Assistant</h3>
            <div className="panel-badge vertical-chat">Vertical Chat</div>
          </div>
          
          <div className="ai-chat-container">
            <div className="ai-messages">
              {aiMessages.map((message, index) => (
                <div key={index} className={`ai-message ${message.type} ${message.isSystemNotification ? 'system-notification' : ''}`}>
                  {message.type === 'user' ? (
                    <div className="user-message">
                      <div className="message-avatar">👤</div>
                      <div className="message-content">{message.content}</div>
                    </div>
                  ) : message.type === 'system' ? (
                    <div className="system-message">
                      <div className="message-avatar">🔔</div>
                      <div className="message-content system-notification-content">{message.content}</div>
                    </div>
                  ) : (
                    <div className="assistant-message">
                      <div className="message-avatar">🤖</div>
                      <div className="message-content">{message.content}</div>
                    </div>
                  )}
                </div>
              ))}
              {aiLoading && (
                <div className="ai-message assistant">
                  <div className="assistant-message">
                    <div className="message-avatar">🤖</div>
                    <div className="message-content typing">Thinking...</div>
                  </div>
                </div>
              )}
            </div>
            
            <form onSubmit={handleAISubmit} className="ai-input-form">
              <div className="ai-input-container">
                <input
                  type="text"
                  value={aiInputValue}
                  onChange={(e) => setAIInputValue(e.target.value)}
                  placeholder="Ask about this verse, theology..."
                  className="ai-input"
                  disabled={aiLoading}
                />
                <button 
                  type="submit" 
                  className="ai-send-btn"
                  disabled={aiLoading || !aiInputValue.trim()}
                >
                  📤
                </button>
              </div>
              <div className="ai-input-hint">
                Click on for voice input or type your question
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* Word Context Popover */}
      {showWordPopup && selectedWord && (
        <WordContextPopover
          word={selectedWord}
          position={popupPosition}
          onClose={() => setShowWordPopup(false)}
          contextData={wordContextData}
          loading={wordContextLoading}
        />
      )}

      {/* New Word Popover */}
      <WordPopover
        isVisible={wordPopover.isVisible}
        position={wordPopover.position}
        originalWord={wordPopover.originalWord}
        meaning={wordPopover.meaning}
        contextBias={wordPopover.contextBias}
        onClose={closeWordPopover}
        loading={wordPopover.loading}
      />
    </div>
  )
}

export default TextualComparison