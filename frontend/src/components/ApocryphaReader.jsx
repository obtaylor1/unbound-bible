import { useState, useEffect } from 'react'
import './ApocryphaReader.css'
import WordPopover from './WordPopover'

function ApocryphaReader({ selectedBook, selectedChapter, selectedVerse }) {
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
  
  // Function to wrap words in clickable spans
  const wrapWordsInSpans = (text, chapterNum, verseNum) => {
    if (!text) return text
    
    return text.split(/\b/).map((part, index) => {
      // Check if the part is a word (contains letters)
      if (/[a-zA-Z]/.test(part) && part.length > 1) {
        return (
          <span 
            key={index}
            className="clickable-word"
            onClick={(e) => handleWordClick(part, e, chapterNum, verseNum)}
            style={{ cursor: 'pointer', padding: '1px' }}
          >
            {part}
          </span>
        )
      }
      return part
    })
  }

  if (loading) {
    return (
      <div className="apocrypha-reader-container">
        <div className="apocrypha-loading">
          <div className="loading-spinner"></div>
          <p>Loading {selectedBook}...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="apocrypha-reader-container">
        <div className="apocrypha-error">
          <h3>Error Loading Content</h3>
          <p>{error}</p>
          <button onClick={fetchBookContent} className="retry-button">
            Try Again
          </button>
        </div>
      </div>
    )
  }

  // Rich static content for major pseudepigraphal texts
  const RICH_CONTENT = {
    '1 Enoch': {
      tradition: 'Ethiopian Orthodox Canon | Preserved in Geʽez',
      summary: 'The Book of 1 Enoch (also called Ethiopic Enoch) is a collection of apocalyptic visions and revelations attributed to Enoch, the great-grandfather of Noah. It is one of the most significant pre-Christian Jewish texts and is quoted directly in the New Testament (Jude 14-15). It survives completely only in Ethiopic (Geʽez) manuscripts and is considered canonical by the Ethiopian Orthodox Tewahedo Church.',
      facts: [
        { label: 'Canonical Status', value: 'Ethiopian Orthodox Bible (81-book canon)' },
        { label: 'Language', value: 'Original Aramaic/Hebrew → Geʽez (Ethiopic)' },
        { label: 'Date Composed', value: 'c. 300 BC – 1st century AD (composite)' },
        { label: 'NT Quote', value: 'Jude 14-15 quotes 1 Enoch 1:9 directly' },
        { label: 'Discovery', value: 'Brought to Europe from Abyssinia by James Bruce (1773)' }
      ],
      sections: [
        {
          title: 'Book of the Watchers (Chapters 1–36)',
          content: 'The opening section describes the "Watchers" — divine beings who descended to earth, took human wives, and taught humanity forbidden knowledge including metallurgy, cosmetics, and weaponry. Their giant offspring, the Nephilim, spread corruption across the earth. This provides the backstory behind Genesis 6:1-4. Enoch is taken on a cosmic journey through the heavens and sees the thrones of God and the places prepared for the righteous and the wicked.'
        },
        {
          title: 'Book of Parables (Chapters 37–71)',
          content: 'Contains the "Son of Man" imagery that significantly influenced New Testament Christology. The Elect One/Son of Man sits on God\'s throne and judges all nations. Many scholars see direct parallels with Jesus\'s self-identification as the "Son of Man" in the Gospels. This section was absent from the Dead Sea Scrolls Enoch fragments, suggesting it may be a later addition.'
        },
        {
          title: 'Astronomical Book (Chapters 72–82)',
          content: 'An early scientific text describing the movements of the sun and moon, the 364-day solar calendar used by the Qumran community, and the six gates of heaven through which heavenly bodies travel. This calendar conflicts with the lunar calendar used by mainstream Judaism, explaining tensions in the Dead Sea Scrolls community.'
        },
        {
          title: 'Book of Dream Visions (Chapters 83–90)',
          content: 'Contains the "Animal Apocalypse" — a sweeping allegory of Israelite history from Adam to the Maccabean period in which humans are depicted as various animals. Bulls represent the patriarchs, sheep represent Israel, and various predatory animals represent oppressing nations. A white bull appears at the end representing a messianic figure.'
        },
        {
          title: 'Epistle of Enoch (Chapters 91–108)',
          content: 'A series of woes addressed to the wicked rich who oppress the righteous poor. Contains the "Apocalypse of Weeks" — a ten-week schematic history of the world from creation to final judgment. Remarkably resonant with prophetic literature about economic justice and the oppression of marginalized people.'
        }
      ],
      keyQuote: '"And behold! He cometh with ten thousands of His holy ones to execute judgment upon all, and to destroy all the ungodly: And to convict all flesh of all the works of their ungodliness which they have ungodly committed." — 1 Enoch 1:9 (quoted in Jude 14-15)'
    },
    'Enoch': {
      tradition: 'Ethiopian Orthodox Canon | Preserved in Geʽez',
      summary: 'The Book of Enoch is a collection of apocalyptic visions attributed to Enoch. Quoted in the New Testament (Jude 14-15), it survives complete only in Geʽez (Ethiopian) manuscripts.',
      facts: [
        { label: 'Canonical Status', value: 'Ethiopian Orthodox Bible' },
        { label: 'NT Reference', value: 'Jude 14-15 quotes it directly' }
      ],
      sections: [
        { title: 'The Watchers', content: 'Divine beings who descended to earth and corrupted humanity — the backstory behind Genesis 6:1-4.' },
        { title: 'Son of Man Visions', content: 'Apocalyptic imagery of the "Son of Man" on God\'s throne that shaped early Christology.' }
      ],
      keyQuote: '"And behold! He cometh with ten thousands of His holy ones to execute judgment upon all." — 1 Enoch 1:9 (quoted in Jude 14-15)'
    },
    'Jubilees': {
      tradition: 'Ethiopian Orthodox Canon | Dead Sea Scrolls | Geʽez Manuscripts',
      summary: 'The Book of Jubilees (also called "Little Genesis" or Kufale in Geʽez) is a 2nd-century BC retelling of Genesis and the first half of Exodus. It presents history divided into 49-year "jubilee" periods and emphasizes the eternal nature of God\'s laws. It is canonical in the Ethiopian Orthodox Church and was widely used at Qumran, with 15 manuscripts found among the Dead Sea Scrolls — more copies than most books of the Hebrew Bible.',
      facts: [
        { label: 'Canonical Status', value: 'Ethiopian Orthodox Bible; revered at Qumran' },
        { label: 'Language', value: 'Original Hebrew → Geʽez (Ethiopic), Dead Sea Scrolls fragments' },
        { label: 'Date Composed', value: 'c. 160-150 BC (Maccabean period)' },
        { label: 'Dead Sea Scrolls', value: '15 Jubilees manuscripts found at Qumran' },
        { label: 'Alternative Title', value: '"The Little Genesis" / Kufale ("Divisions")' }
      ],
      sections: [
        {
          title: 'The 364-Day Calendar',
          content: 'Jubilees insists on a 364-day solar calendar (exactly 52 weeks) rather than the lunar calendar used in Second Temple Judaism. The author argues that holy days must always fall on the same day of the week, which is impossible with a lunar calendar. The Qumran community adopted this calendar, putting them in constant conflict with Jerusalem Temple authorities.'
        },
        {
          title: 'Pre-Sinai Torah',
          content: 'One of Jubilees\' most radical claims is that the Mosaic law (Sabbath, circumcision, dietary laws) was already observed by the patriarchs before Sinai. Abraham kept the Feast of Tabernacles; Noah observed the Sabbath. This counters the argument that God\'s laws are relative or time-bound, presenting them as eternal cosmic principles.'
        },
        {
          title: 'Mastema — Prince of Evil',
          content: 'Jubilees introduces Mastema, a Satan-like figure who petitions God to keep evil spirits on earth (after the flood) to test humanity. One-tenth of demonic spirits are allowed to remain active. Mastema is responsible for hardening Pharaoh\'s heart and instigating the testing of Abraham. This theology influenced later Jewish and Christian demonology.'
        },
        {
          title: 'Expanded Patriarchal Narratives',
          content: 'Jubilees fills in gaps in Genesis — giving names to unnamed women (Dinah\'s mother, Cain\'s wife), explaining Abraham\'s early life and rejection of his father\'s idol worship, and providing detailed accounts of Enoch\'s scribal activities. These expansions appear in the Dead Sea Scrolls, the Talmud, and early Christian texts.'
        },
        {
          title: 'Angels and the Heavenly Tablets',
          content: 'The entire book is presented as dictated by "the Angel of the Presence" to Moses during his 40 days on Sinai. History is written on "Heavenly Tablets" and angels are divided into classes that govern natural phenomena. This angelology became foundational for later Jewish mysticism (Kabbalah) and early Christian thought.'
        }
      ],
      keyQuote: '"There will be those who will carefully observe the moon — now it distorts the seasons and comes in from year to year ten days too soon. For this reason the years will come upon them when they will disturb (the order), and make an abominable (day) the day of testimony, and an unclean day a feast day." — Jubilees 6:36-37 (on the lunar vs solar calendar)'
    },
    'Meqabyan 1': {
      tradition: 'Ethiopian Orthodox Canon | Unique to Ethiopia',
      summary: 'The Books of Meqabyan are three books found exclusively in the Ethiopian Orthodox Bible and have no relation to the Greek Maccabees. They tell of an Ethiopian hero named Meqabyan who leads a revolt against a pagan king and teaches resurrection faith.',
      facts: [
        { label: 'Canonical Status', value: 'Ethiopian Orthodox Bible only' },
        { label: 'Often confused with', value: '1-2 Maccabees (completely different texts)' }
      ],
      sections: [
        { title: 'The Revolt', content: 'Meqabyan leads faithful Israelites against an oppressive pagan king who forces idol worship.' },
        { title: 'Resurrection Theology', content: 'Strong emphasis on bodily resurrection and the faithfulness of martyrs — a cornerstone of Ethiopian Orthodox theology.' }
      ],
      keyQuote: '"Do not fear those who kill the body but cannot kill the soul." — Meqabyan (reflecting its central theological theme)'
    }
  }

  const richContent = RICH_CONTENT[selectedBook]

  if (!bookContent.length) {
    if (richContent) {
      return (
        <div className="apocrypha-reader-container">
          <div className="rich-content-panel">
            <div className="rich-header">
              <div className="rich-title-area">
                <h1 className="rich-book-title">{selectedBook}</h1>
                <div className="rich-tradition-badge">{richContent.tradition}</div>
              </div>
            </div>

            <div className="rich-summary-box">
              <p>{richContent.summary}</p>
            </div>

            {richContent.facts && (
              <div className="rich-facts-grid">
                {richContent.facts.map((fact, i) => (
                  <div key={i} className="rich-fact-item">
                    <span className="fact-label">{fact.label}</span>
                    <span className="fact-value">{fact.value}</span>
                  </div>
                ))}
              </div>
            )}

            {richContent.keyQuote && (
              <blockquote className="rich-key-quote">
                {richContent.keyQuote}
              </blockquote>
            )}

            <div className="rich-sections">
              <h2 className="rich-sections-title">Key Sections & Themes</h2>
              {richContent.sections.map((section, i) => (
                <div key={i} className="rich-section-card">
                  <h3 className="rich-section-title">{section.title}</h3>
                  <p className="rich-section-content">{section.content}</p>
                </div>
              ))}
            </div>

            <div className="rich-note">
              <span className="note-icon">📚</span>
              Full text integration coming soon. AI chat is available on the right panel to explore this text in depth.
            </div>
          </div>
        </div>
      )
    }

    return (
      <div className="apocrypha-reader-container">
        <div className="apocrypha-empty">
          <h3>No Content Available</h3>
          <p>No content found for {selectedBook}.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="apocrypha-reader-container">
      <div className="apocrypha-header">
        <div className="apocrypha-title">
          <h1>{selectedBook}</h1>
          {bookInfo && (
            <div className="book-metadata">
              <span className="book-tradition">{bookInfo.tradition || 'Extra-Canonical Text'}</span>
              {bookInfo.description && (
                <p className="book-description">{bookInfo.description}</p>
              )}
            </div>
          )}
        </div>
        <div className="reading-controls">
          <button className="control-btn" onClick={() => window.print()}>
            🖨️ Print
          </button>
          <button 
            className="control-btn"
            onClick={() => {
              const textContent = bookContent.map(t => t.text).join('\n\n')
              navigator.clipboard.writeText(`${selectedBook}\n\n${textContent}`)
            }}
          >
            📋 Copy All
          </button>
        </div>
      </div>

      <div className="apocrypha-content">
        {Object.entries(groupedContent).map(([bookName, chapters]) => (
          <div key={bookName} className="book-section">
            <h2 className="book-heading">{formatBookHeading(bookName)}</h2>
            
            {Object.entries(chapters).map(([chapterNum, verses]) => (
              <div key={chapterNum} className="chapter-section">
                <h3 className="chapter-heading">{formatChapterHeading(chapterNum)}</h3>
                
                <div className="chapter-content">
                  {verses.map((verseObj, index) => (
                    <div key={verseObj.id || index} className="verse-block">
                      <div className="verse-number">{verseObj.verse}</div>
                      <div className="verse-text">{wrapWordsInSpans(verseObj.text, chapterNum, verseObj.verse)}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Word Popover */}
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

export default ApocryphaReader