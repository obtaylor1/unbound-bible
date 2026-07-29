import { useState, useEffect, useRef } from 'react'
import './TextualComparisonWorkspace.css'
import StudyAssistantSidebar from './StudyAssistantSidebar'
import ShareStudyModal from './ShareStudyModal'

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
  '2 Peter': 3, '1 John': 5, '2 John': 1, '3 John': 1, 'Jude': 1, 'Revelation': 22,
  
  // Extra-Canonical
  '1 Enoch': 108, 'Enoch': 108,
  'Jubilees': 50,
  '1 Meqabyan': 36, 'Meqabyan 1': 36,
  '2 Meqabyan': 22, 'Meqabyan 2': 22,
  '3 Meqabyan': 10, 'Meqabyan 3': 10,
  'Tobit': 14, 'Judith': 16, 'Wisdom of Solomon': 19, 'Sirach': 51,
  'Baruch': 5, '1 Maccabees': 16, '2 Maccabees': 15, '1 Esdras': 9,
  '2 Esdras': 16, 'Letter of Jeremiah': 1, 'Prayer of Manasseh': 1,
  'Psalm 151': 1, 'Prayer of Azariah': 1, 'Susanna': 1, 'Bel and the Dragon': 1,
  'Esther (Greek Additions)': 6, 'Abtilis': 1, 'Tizaz': 1, 'Didesqelya': 1,
  'Metsihafe Kidan I': 1, 'Metsihafe Kidan II': 1, 'Qalëmentos': 1
}

const TRANSLATIONS_META = {
  kjv: { name: 'King James Version', code: 'KJV', tradition: 'Western Anglican / Protestant (1611)', language: 'English' },
  asv: { name: 'American Standard Version', code: 'ASV', tradition: 'Western Protestant (1901)', language: 'English' },
  web: { name: 'World English Bible', code: 'WEB', tradition: 'Modern English / Ecumenical', language: 'English' },
  webbe: { name: 'World English Bible (BE)', code: 'WEBBE', tradition: 'British English / Ecumenical', language: 'English' },
  bbe: { name: 'Bible in Basic English', code: 'BBE', tradition: 'Basic English Translation (1949)', language: 'English' },
  darby: { name: 'Darby Translation', code: 'DARBY', tradition: 'Literal / Darby (1890)', language: 'English' },
  dra: { name: 'Douay-Rheims Version', code: 'DRA', tradition: 'Catholic Vulgate Translation (1899)', language: 'English' },
  ylt: { name: 'Young\'s Literal Translation', code: 'YLT', tradition: 'Strict Literal / Young (1862)', language: 'English' },
  nlt: { name: 'New Living Translation', code: 'NLT', tradition: 'Modern Thought-for-Thought (1996/2004)', language: 'English' },
  erv: { name: 'Easy-to-Read Version', code: 'ERV', tradition: 'Modern Easy English (2006)', language: 'English' },
  eth81: { name: 'Ethiopian Orthodox Critical Text', code: 'ETH81', tradition: 'Ancient Orthodox / Ge\'ez Canon', language: 'Amharic/Ge\'ez' },
  '1en_ch': { name: '1 Enoch (Charles)', code: '1EN_CH', tradition: 'Ethiopian Pseudepigrapha', language: 'English Translation' },
  jub_ch: { name: 'Jubilees (Charles)', code: 'JUB_CH', tradition: 'Ethiopian Pseudepigrapha', language: 'English Translation' },
  meq1: { name: '1 Meqabyan (Maccabees)', code: 'MEQ1', tradition: 'Ethiopian Deuterocanon', language: 'English Translation' },
  meq2: { name: '2 Meqabyan', code: 'MEQ2', tradition: 'Ethiopian Deuterocanon', language: 'English Translation' },
  meq3: { name: '3 Meqabyan', code: 'MEQ3', tradition: 'Ethiopian Deuterocanon', language: 'English Translation' },
  targ_on: { name: 'Targum Onkelos', code: 'TARG_ON', tradition: 'Jewish Aramaic Translation', language: 'Aramaic' },
  josephus: { name: 'Josephus (Antiquities)', code: 'JOSEPHUS', tradition: 'Hellenistic Jewish Historical', language: 'English Translation' }
}

const CANON_GROUPS = {
  protestant: {
    name: 'Protestant Standard',
    description: 'Translations adhering to the 66-book Protestant canon.',
    keys: ['kjv', 'asv', 'web', 'webbe', 'bbe', 'darby', 'dra', 'ylt', 'nlt', 'erv']
  },
  deuterocanon: {
    name: 'Deuterocanonical & Ancient',
    description: 'Rabbinic Aramaic Targums and Hellenistic Jewish history.',
    keys: ['targ_on', 'josephus']
  },
  ethiopian: {
    name: 'Ethiopian Orthodox Canon',
    description: 'Unique scriptures conserved in the ancient Orthodox tradition of East Africa.',
    keys: ['eth81', '1en_ch', 'jub_ch', 'meq1', 'meq2', 'meq3']
  }
}

function TextualComparisonWorkspace() {
  const [selectedBook, setSelectedBook] = useState('Genesis')
  const [selectedChapter, setSelectedChapter] = useState('1')
  const [selectedVerse, setSelectedVerse] = useState('1')
  const [availableBooks, setAvailableBooks] = useState([])
  const [bookContent, setBookContent] = useState([])
  const [loadingBooks, setLoadingBooks] = useState(false)
  const [loadingContent, setLoadingContent] = useState(false)
  
  // Selection of translations to compare (default to ETH81, KJV, ASV, WEB)
  const [selectedTranslations, setSelectedTranslations] = useState(['eth81', 'kjv', 'asv', 'web'])
  // Base translation used for difference highlighting
  const [baseTranslation, setBaseTranslation] = useState('eth81')
  // Difference highlighting active state
  const [highlightActive, setHighlightActive] = useState(true)
  // View mode: 'single' (verse deep-dive) or 'chapter' (aligned chapter)
  const [viewMode, setViewMode] = useState('single')
  
  // Collapsible AI insights sidebar state
  const [showInsights, setShowInsights] = useState(true)
  const [, setVerseDetails] = useState(null)
  const [, setLoadingDetails] = useState(false)
  
  // Share Session States
  const [showShareModal, setShowShareModal] = useState(false)
  const [shareData, setShareData] = useState(null)

  const handleShareWorkspaceSession = () => {
    setShareData({
      title: `Translation Study: ${selectedBook} ${selectedChapter}:${selectedVerse}`,
      verses: [`${selectedBook} ${selectedChapter}:${selectedVerse}`],
      type: 'Textual Comparison Workspace',
      content: {
        translationsCompared: selectedTranslations.map(k => TRANSLATIONS_META[k]?.name || k),
        baseTranslation: TRANSLATIONS_META[baseTranslation]?.name || baseTranslation,
        notes: userNote
      }
    })
    setShowShareModal(true)
  }
  
  // User note state
  const [userNote, setUserNote] = useState('')
  const [noteSaving, setNoteSaving] = useState(false)
  const [noteSavedFeedback, setNoteSavedFeedback] = useState(false)
  const autoSaveTimerRef = useRef(null)

  // Search input state for left translation panel
  const [searchTerm, setSearchTerm] = useState('')

  // Local bookmarks state
  const [bookmarkedVerses, setBookmarkedVerses] = useState(() => {
    const saved = localStorage.getItem('unbound_bookmarks')
    return saved ? JSON.parse(saved) : []
  })

  const handleToggleBookmark = (verseRef) => {
    setBookmarkedVerses(prev => {
      const updated = prev.includes(verseRef)
        ? prev.filter(ref => ref !== verseRef)
        : [...prev, verseRef]
      localStorage.setItem('unbound_bookmarks', JSON.stringify(updated))
      return updated
    })
  }

  // Clear scratchpad note helper
  const handleNewNote = () => {
    setUserNote('')
    const noteKey = `note-${selectedBook}-${selectedChapter}-${selectedVerse}`
    localStorage.removeItem(noteKey)
  }

  // Fetch available books on component mount
  useEffect(() => {
    const fetchAvailableBooks = async () => {
      setLoadingBooks(true)
      try {
        const response = await fetch('/api/biblical-texts/available-books')
        if (response.ok) {
          const data = await response.json()
          setAvailableBooks(data.books || [])
        }
      } catch (err) {
        console.error('Failed to load available books:', err)
      } finally {
        setLoadingBooks(false)
      }
    }
    fetchAvailableBooks()
  }, [])

  // Reset chapter/verse when book changes
  useEffect(() => {
    setSelectedChapter('1')
    setSelectedVerse('1')
  }, [selectedBook])

  // Fetch chapter content when selectedBook or selectedChapter changes
  useEffect(() => {
    const fetchChapterContent = async () => {
      if (!selectedBook || !selectedChapter) return
      setLoadingContent(true)
      try {
        const response = await fetch(`/api/biblical-texts/chapter-content?book=${encodeURIComponent(selectedBook)}&chapter=${selectedChapter}`)
        if (response.ok) {
          const data = await response.json()
          setBookContent(data.content || [])
        } else {
          setBookContent([])
        }
      } catch (err) {
        console.error('Error fetching chapter content:', err)
        setBookContent([])
      } finally {
        setLoadingContent(false)
      }
    }
    fetchChapterContent()
  }, [selectedBook, selectedChapter])

  // Fetch dynamic verse details when book, chapter, or verse changes
  useEffect(() => {
    const fetchVerseDetails = async () => {
      if (!selectedBook || !selectedChapter || !selectedVerse || viewMode === 'chapter') return
      setLoadingDetails(true)
      try {
        const response = await fetch(`/api/v1/texts/${encodeURIComponent(selectedBook)}/${selectedChapter}/${selectedVerse}/details`)
        if (response.ok) {
          const data = await response.json()
          setVerseDetails(data)
        } else {
          setVerseDetails(null)
        }
      } catch (err) {
        console.error('Error fetching verse details:', err)
        setVerseDetails(null)
      } finally {
        setLoadingDetails(false)
      }
    }
    fetchVerseDetails()
  }, [selectedBook, selectedChapter, selectedVerse, viewMode])

  // Sync selected verse validity when book content changes
  useEffect(() => {
    if (bookContent.length > 0) {
      const uniqueVerses = Array.from(new Set(bookContent.map(v => v.verse.toString())))
      if (uniqueVerses.length > 0 && !uniqueVerses.includes(selectedVerse)) {
        setSelectedVerse(uniqueVerses[0])
      }
    }
  }, [bookContent, selectedVerse])

  // Load and manage user notes
  useEffect(() => {
    const noteKey = `note-${selectedBook}-${selectedChapter}-${selectedVerse}`
    const savedNote = localStorage.getItem(noteKey) || ''
    setUserNote(savedNote)
  }, [selectedBook, selectedChapter, selectedVerse])

  // Auto-save user note
  const handleNoteChange = (e) => {
    const value = e.target.value
    setUserNote(value)
    setNoteSavedFeedback(false)
    setNoteSaving(true)

    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current)
    }

    autoSaveTimerRef.current = setTimeout(() => {
      const noteKey = `note-${selectedBook}-${selectedChapter}-${selectedVerse}`
      if (value.trim() === '') {
        localStorage.removeItem(noteKey)
      } else {
        localStorage.setItem(noteKey, value)
      }
      setNoteSaving(false)
      setNoteSavedFeedback(true)
    }, 1000)
  }

  // Clear note timer on unmount
  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    }
  }, [])

  // Calculate unique chapters in book statically
  const bookList = availableBooks.length > 0 ? availableBooks : Object.keys(bookChapters)
  const chaptersCount = bookChapters[selectedBook] || 50
  const chaptersList = Array.from({ length: chaptersCount }, (_, i) => i + 1)
  
  // Calculate unique verses in currently selected chapter
  const versesList = Array.from(new Set(bookContent.map(v => v.verse))).sort((a, b) => a - b)

  // Toggle selected translations
  const handleToggleTranslation = (key) => {
    setSelectedTranslations(prev => {
      if (prev.includes(key)) {
        // Keep at least one translation selected
        if (prev.length === 1) return prev
        const filtered = prev.filter(t => t !== key)
        // Adjust base translation if it was removed
        if (baseTranslation === key) {
          setBaseTranslation(filtered[0])
        }
        return filtered
      } else {
        return [...prev, key]
      }
    })
  }

  // Client-side word-difference highlighter relative to base translation
  const renderTextWithDiff = (text, baseText) => {
    if (!highlightActive || !baseText || !text || baseText === text) {
      return text
    }

    // Normalization helper
    const cleanWord = (w) => w.toLowerCase().replace(/[.,/#!$%^&*;:{}=_`~()?"'’[\]-]/g, "")
    const baseWordsSet = new Set(baseText.split(/\s+/).map(cleanWord).filter(Boolean))

    return text.split(/(\s+)/).map((part, index) => {
      if (part.trim() === '') return part // Keep whitespace unchanged
      const cleaned = cleanWord(part)
      if (cleaned && !baseWordsSet.has(cleaned)) {
        return (
          <span key={index} className="diff-highlight-word" title="Differs from base translation">
            {part}
          </span>
        )
      }
      return part
    })
  }

  // Check if a book is canonical in Protestant, Catholic, or Ethiopian traditions
  const getCanonAffiliation = (bookName) => {
    const protestantBooks = [
      "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
      "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah",
      "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
      "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
      "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
      "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
      "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
      "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
      "1 John", "2 John", "3 John", "Jude", "Revelation"
    ]
    const catholicBooks = [
      ...protestantBooks,
      "Tobit", "Judith", "Wisdom of Solomon", "Sirach", "Baruch", "1 Maccabees", "2 Maccabees"
    ]

    if (protestantBooks.includes(bookName)) return 'all'
    if (catholicBooks.includes(bookName)) return 'catholic'
    return 'ethiopian' // Apocryphal / pseudepigraphal / unique Ethiopian books
  }

  // Get verse text for a specific translation
  const getVerseText = (transKey, verseNum = selectedVerse) => {
    const match = bookContent.find(
      v => v.chapter.toString() === selectedChapter &&
           v.verse.toString() === verseNum.toString() &&
           v.translation.toLowerCase() === transKey.toLowerCase()
    )
    return match ? match.text : null
  }

  // Render Canon warning block
  const renderCanonWarning = (transKey) => {
    const meta = TRANSLATIONS_META[transKey]
    const affiliation = getCanonAffiliation(selectedBook)
    const explanation = affiliation === 'catholic'
      ? `"${selectedBook}" is a deuterocanonical book recognized in the Catholic and Orthodox traditions, but omitted from Protestant versions like ${meta.code}.`
      : affiliation === 'ethiopian'
        ? `"${selectedBook}" is an ancient scripture conserved in the Ethiopian Orthodox canon or early Christian collections, but absent from Protestant and Catholic translations.`
        : `This verse may not be seeded or is unavailable in the database for ${meta.name}.`

    return (
      <div className="compare-canon-warning">
        <span className="warning-icon">⚠️</span>
        <h5 className="warning-title">Canon Exclusion</h5>
        <p className="warning-desc">{explanation}</p>
        <span className="warning-tradition">Tradition: {meta.tradition}</span>
      </div>
    )
  }

  // Get base text for comparison
  const getBaseText = (verseNum = selectedVerse) => {
    return getVerseText(baseTranslation, verseNum) || ''
  }

  return (
    <div className="workspace-container">
      <div className="workspace-page-wrapper">
        {/* Top Selector Panel */}
        <header className="workspace-header-controls">
          <div className="selector-group search-container">
            <label>Book</label>
            <select value={selectedBook} onChange={(e) => setSelectedBook(e.target.value)}>
              {loadingBooks && availableBooks.length === 0 ? (
                <option>Loading books...</option>
              ) : (
                bookList.map(b => (
                  <option key={b} value={b}>{b}</option>
                ))
              )}
            </select>
          </div>

          <div className="selector-group">
            <label>Chapter</label>
            <select value={selectedChapter} onChange={(e) => setSelectedChapter(e.target.value)}>
              {chaptersList.map(ch => (
                <option key={ch} value={ch}>{ch}</option>
              ))}
            </select>
          </div>

          <div className="selector-group">
            <label>Verse</label>
            <select 
              value={selectedVerse} 
              onChange={(e) => setSelectedVerse(e.target.value)}
              disabled={viewMode === 'chapter'}
            >
              {versesList.map(v => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>

          <div className="selector-group">
            <label>Compare View</label>
            <div className="toggle-btn-group">
              <button 
                className={`toggle-btn ${viewMode === 'single' ? 'active' : ''}`}
                onClick={() => setViewMode('single')}
              >
                Single Verse
              </button>
              <button 
                className={`toggle-btn ${viewMode === 'chapter' ? 'active' : ''}`}
                onClick={() => setViewMode('chapter')}
              >
                Parallel Chapter
              </button>
            </div>
          </div>

          <div className="selector-group divider-left">
            <label>Base Reference</label>
            <select value={baseTranslation} onChange={(e) => setBaseTranslation(e.target.value)}>
              {Object.keys(TRANSLATIONS_META).map(key => (
                <option key={key} value={key}>
                  {TRANSLATIONS_META[key]?.name || key.toUpperCase()} ({TRANSLATIONS_META[key]?.code || key.toUpperCase()})
                </option>
              ))}
            </select>
          </div>

          <div className="selector-group checkbox-toggle-wrapper">
            <button 
              className={`btn-diff-toggle ${highlightActive ? 'active' : ''}`}
              onClick={() => setHighlightActive(!highlightActive)}
              title="Toggle color highlights on differing words"
            >
              Highlight Differences
            </button>

            <button 
              className={`btn-insights-toggle ${showInsights ? 'active' : ''}`}
              onClick={() => setShowInsights(!showInsights)}
              title="Toggle AI Insights Companion"
              style={{ marginLeft: '10px' }}
            >
              {showInsights ? 'Hide Companion' : 'Study Companion'}
            </button>
          </div>
        </header>

        {/* Main Workspace Split Layout */}
        <div className={`workspace-main-layout ${showInsights ? 'has-sidebar' : 'no-sidebar'}`}>
          {/* Left Control Panel & Sidebar */}
          <aside className="workspace-sidebar">
            {/* Translation Selection Card */}
            <div className="sidebar-card">
              <h4>Select Translations</h4>
              <p className="card-subtitle">Choose versions to compare side-by-side</p>
              
              <input 
                type="text"
                placeholder="Search translations..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="translation-search-input"
              />
              
              <div className="canon-selection-scroll">
                {Object.entries(CANON_GROUPS).map(([groupId, group]) => {
                  const filteredKeys = group.keys.filter(key => {
                    const meta = TRANSLATIONS_META[key]
                    if (!meta) return false
                    return meta.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                           meta.code.toLowerCase().includes(searchTerm.toLowerCase())
                  })
                  
                  if (filteredKeys.length === 0) return null
                  
                  return (
                    <div key={groupId} className="canon-selector-group">
                      <h5>{group.name}</h5>
                      <div className="checkbox-list">
                        {filteredKeys.map(key => {
                          const meta = TRANSLATIONS_META[key]
                          const isChecked = selectedTranslations.includes(key)
                          return (
                            <label key={key} className={`checkbox-label ${isChecked ? 'checked' : ''}`}>
                              <input 
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => handleToggleTranslation(key)}
                                className="hidden-checkbox"
                              />
                              <span className="custom-checkbox-box"></span>
                              <div className="checkbox-custom-details">
                                <span className="trans-code">{meta.code}</span>
                                <span className="trans-name">{meta.name}</span>
                              </div>
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="manage-translations-wrapper">
                <a href="#manage" className="manage-translations-link" onClick={(e) => { e.preventDefault(); alert("Manage Translations dialog coming soon!"); }}>
                  <span className="manage-icon">⚙️</span> Manage Translations
                </a>
              </div>
            </div>

            {/* User Notes Persistence Box */}
            <div className="sidebar-card note-scratchpad-card">
              <div className="notes-header-flex">
                <h4>Study Scratchpad</h4>
                <div className="saving-status-indicator">
                  {noteSaving && <span className="saving-spinner">✍️ saving...</span>}
                  {noteSavedFeedback && <span className="saved-check">✅ saved</span>}
                </div>
              </div>
              <p className="card-subtitle">Write translations notes for {selectedBook} {selectedChapter}:{selectedVerse}</p>
              <textarea
                className="notes-textarea"
                placeholder="Record structural details, translation shifts, or cultural context findings..."
                value={userNote}
                onChange={handleNoteChange}
              />
              <div className="scratchpad-actions">
                <button className="btn-new-note" onClick={handleNewNote}>
                  + New Note
                </button>
                <button 
                  className="btn-share-notes"
                  onClick={handleShareWorkspaceSession}
                >
                  🔗 Share Comparison
                </button>
              </div>
            </div>
          </aside>

          {/* Right Main Panel Grid */}
          <main className="workspace-comparison-viewport">
            {loadingContent ? (
              <div className="workspace-loading-placeholder">
                <div className="spinner"></div>
                <p>Loading scripture translations...</p>
              </div>
            ) : viewMode === 'single' ? (
              /* SIDE-BY-SIDE SINGLE VERSE COLUMNS */
              <div 
                className="workspace-columns-grid" 
                style={{ gridTemplateColumns: `repeat(${selectedTranslations.length}, minmax(300px, 1fr))` }}
              >
                {selectedTranslations.map(transKey => {
                  const meta = TRANSLATIONS_META[transKey]
                  const text = getVerseText(transKey)
                  const baseText = getBaseText()
                  const isBase = transKey === baseTranslation

                  return (
                    <div key={transKey} className={`compare-column-card ${isBase ? 'is-base-column' : ''}`}>
                      <div className="column-card-header">
                        <div className="header-meta-title">
                          <span className="card-badge">{meta.code}</span>
                          <h3>{meta.name}</h3>
                        </div>
                        <span className="card-subtitle">{meta.tradition}</span>
                      </div>

                      <div className="column-card-body">
                        {text ? (
                          <div className="verse-display-box">
                            <span className="verse-num-badge">v.{selectedVerse}</span>
                            <p className="verse-text-styled">
                              {renderTextWithDiff(text, baseText)}
                            </p>
                          </div>
                        ) : (
                          renderCanonWarning(transKey)
                        )}
                      </div>

                      <div className="column-card-actions">
                        <button 
                          className={`card-action-btn ${bookmarkedVerses.includes(`${selectedBook} ${selectedChapter}:${selectedVerse}`) ? 'active' : ''}`}
                          onClick={() => handleToggleBookmark(`${selectedBook} ${selectedChapter}:${selectedVerse}`)}
                          aria-label="Bookmark verse"
                          title="Bookmark verse"
                        >
                          🔖
                        </button>
                        <button className="card-action-btn" aria-label="More actions" title="More actions">
                          ⋮
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              /* CHAPTER VIEW PARALLEL LIST */
              <div className="workspace-chapter-parallel-list">
                <div className="chapter-header-bar">
                  <h4>{selectedBook} Chapter {selectedChapter} Aligned Parallel</h4>
                  <p>Scroll vertically to compare line-by-line</p>
                </div>

                {versesList.length === 0 ? (
                  <div className="empty-chapter-fallback">
                    <p>No verse data available for this chapter.</p>
                  </div>
                ) : (
                  versesList.map(vNum => {
                    const baseText = getBaseText(vNum)
                    return (
                      <div key={vNum} className="parallel-verse-row">
                        <div className="parallel-verse-number">Verse {vNum}</div>
                        <div 
                          className="parallel-verse-translations-grid"
                          style={{ gridTemplateColumns: `repeat(${selectedTranslations.length}, minmax(240px, 1fr))` }}
                        >
                          {selectedTranslations.map(transKey => {
                            const text = getVerseText(transKey, vNum)
                            const isBase = transKey === baseTranslation

                            return (
                              <div key={transKey} className={`parallel-cell ${isBase ? 'is-base-cell' : ''}`}>
                                <span className="cell-trans-indicator">{TRANSLATIONS_META[transKey]?.code}</span>
                                {text ? (
                                  <p className="cell-text">
                                    {renderTextWithDiff(text, baseText)}
                                  </p>
                                ) : (
                                  <p className="cell-empty-text">Not present in canon</p>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            )}
          </main>
          
          {/* Collapsible right sidebar */}
          {showInsights && (
            <StudyAssistantSidebar 
              book={selectedBook}
              chapter={parseInt(selectedChapter)}
              verse={parseInt(selectedVerse)}
              onClose={() => setShowInsights(false)}
              onAddNote={(note) => {
                setUserNote(prev => prev ? `${prev}\n- ${note.text}` : `- ${note.text}`)
              }}
            />
          )}
        </div>
      </div>

      {showShareModal && (
        <ShareStudyModal 
          isOpen={showShareModal}
          onClose={() => setShowShareModal(false)}
          shareData={shareData}
        />
      )}
    </div>
  )
}

export default TextualComparisonWorkspace
