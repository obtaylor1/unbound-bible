import { useState, useEffect, useRef } from 'react'
import './AncientTexts.css'
import WordContextPopover from './WordContextPopover'
import WordPopover from './WordPopover'
import { canonsData } from '../data/bibleCanons'

const initialReadingPlans = {
  protestant: {
    id: 'protestant',
    name: 'Protestant Canonical Journey',
    tagline: 'Standard 66-Book Scripture Walk',
    duration: '365 Days',
    booksCount: 66,
    completedDays: [1],
    days: [
      { day: 1, title: 'Creation & Beginnings', book: 'Genesis', chapter: '1', readings: 'Genesis 1 & Matthew 1' },
      { day: 2, title: 'The Fall of Man', book: 'Genesis', chapter: '3', readings: 'Genesis 3 & Matthew 2' },
      { day: 3, title: 'Noah & The Ark', book: 'Genesis', chapter: '6', readings: 'Genesis 6 & Matthew 3' },
      { day: 4, title: 'Covenant with Abraham', book: 'Genesis', chapter: '12', readings: 'Genesis 12 & Matthew 4' },
      { day: 5, title: 'Sodom & Gomorrah', book: 'Genesis', chapter: '18', readings: 'Genesis 18 & Matthew 5' }
    ]
  },
  ethiopian: {
    id: 'ethiopian',
    name: 'Ancient Amharic Canon Walk',
    tagline: 'Ethiopian Orthodox 96-Book Study',
    duration: '400 Days',
    booksCount: 96,
    completedDays: [],
    days: [
      { day: 1, title: 'Creation of Heaven & Earth', book: 'Genesis', chapter: '1', readings: 'Genesis 1 & Jubilees 1' },
      { day: 2, title: 'Enoch\'s Heavenly Visions', book: '1 Enoch', chapter: '1', readings: '1 Enoch 1-5' },
      { day: 3, title: 'Secrets of the Watchers', book: '1 Enoch', chapter: '6', readings: '1 Enoch 6-11' },
      { day: 4, title: 'Jubilees Covenant', book: 'Jubilees', chapter: '1', readings: 'Jubilees 1 & Jubilees 2' },
      { day: 5, title: 'Meqabyan Martyrdom', book: 'Meqabyan 1', chapter: '1', readings: '1 Meqabyan 1-2' }
    ]
  },
  catholic: {
    id: 'catholic',
    name: 'Septuagint & Deuterocanon Study',
    tagline: 'Catholic 73-Book Devotional',
    duration: '365 Days',
    booksCount: 73,
    completedDays: [],
    days: [
      { day: 1, title: 'The Creation of Light', book: 'Genesis', chapter: '1', readings: 'Genesis 1 & Wisdom 1' },
      { day: 2, title: 'Tobit\'s Trial of Faith', book: 'Tobit', chapter: '1', readings: 'Tobit 1-2' },
      { day: 3, title: 'Judith\'s Courageous Act', book: 'Judith', chapter: '1', readings: 'Judith 1-3' },
      { day: 4, title: 'Wisdom\'s Pursuit of Righteousness', book: 'Wisdom', chapter: '1', readings: 'Wisdom 1-3' },
      { day: 5, title: 'Maccabean Revolt', book: '1 Maccabees', chapter: '1', readings: '1 Maccabees 1' }
    ]
  },
  broader: {
    id: 'broader',
    name: 'Pseudepigraphal & Historical Survey',
    tagline: 'Broader Canon 102-Book Academic Study',
    duration: '180 Days',
    booksCount: 102,
    completedDays: [],
    days: [
      { day: 1, title: 'The Creation Epic', book: 'Genesis', chapter: '1', readings: 'Genesis 1 & 1 Enoch 1' },
      { day: 2, title: 'Life of Adam and Eve', book: 'Book of Adam and Eve', chapter: '1', readings: 'Adam & Eve Cave of Treasures' },
      { day: 3, title: 'Testament of Abraham', book: 'Book of Abraham', chapter: '1', readings: 'Abraham 1-3' },
      { day: 4, title: 'Secrets of Enoch', book: 'Enoch', chapter: '1', readings: 'Enoch 1-4' },
      { day: 5, title: 'Historical Accounts of Josephus', book: 'Book of Josephus', chapter: '1', readings: 'Antiquities Book 1' }
    ]
  }
}

function AncientTexts({ canonicalFilter = 'PROT66', setCanonicalFilter, availableBooks = [], onPageChange }) {
  const getTranslationName = (code) => {
    const names = {
      'KJV': 'King James Version (KJV)',
      'ETH81': 'Ethiopian English (ETH81)',
      'DRA': 'Douay-Rheims (DRA)',
      'WEBBE': 'World English Ecumenical (WEBBE)',
      'ASV': 'American Standard Version (ASV)',
      'WEB': 'World English Bible (WEB)',
      'BBE': 'Basic English (BBE)',
      'DARBY': 'Darby Translation (DARBY)',
      'YLT': "Young's Literal (YLT)",
      'NLT': 'New Living Translation (NLT)',
      'ERV': 'Easy-to-Read Version (ERV)',
      '1EN_CH': '1 Enoch Charles Translation',
      'JUB_CH': 'Jubilees Charles Translation',
      'MEQ1': '1 Meqabyan English',
      'MEQ2': '2 Meqabyan English',
      'MEQ3': '3 Meqabyan English',
      'JOSEPHUS': 'Antiquities Translation',
      'TARG_ON': 'Genesis Targum Translation'
    }
    return names[code.toUpperCase()] || code
  }

  const getShortTranslationName = (code) => {
    const names = {
      'KJV': 'KJV',
      'ETH81': 'Ethiopian',
      'DRA': 'DRA',
      'WEBBE': 'WEBBE',
      'ASV': 'ASV',
      'WEB': 'WEB',
      'BBE': 'BBE',
      'DARBY': 'Darby',
      'YLT': 'YLT',
      'NLT': 'NLT',
      'ERV': 'ERV',
      '1EN_CH': '1 Enoch',
      'JUB_CH': 'Jubilees',
      'MEQ1': '1 Meqabyan',
      'MEQ2': '2 Meqabyan',
      'MEQ3': '3 Meqabyan',
      'JOSEPHUS': 'Josephus',
      'TARG_ON': 'Targum'
    }
    return names[code.toUpperCase()] || code
  }

  const [selectedBook, setSelectedBook] = useState('Exodus')
  const [selectedChapter, setSelectedChapter] = useState('1')
  const [selectedVerse, setSelectedVerse] = useState('1')
  const [selectedCanon, setSelectedCanon] = useState('Protestant')
  const [translations, setTranslations] = useState({})
  const [selectedWord] = useState(null)
  const [showWordPopup, setShowWordPopup] = useState(false)
  const [popupPosition] = useState({ x: 0, y: 0 })
  const [wordContextData] = useState(null)
  const [wordContextLoading] = useState(false)
  const [selectedWordStudy, setSelectedWordStudy] = useState(null)
  const [wordStudyTab, setWordStudyTab] = useState('usage')

  // New Scripture Reader & Redesign States
  const [fontSize, setFontSize] = useState('md')
  const [readingWidth, setReadingWidth] = useState('wide')
  const [bookmarkedVerses, setBookmarkedVerses] = useState([])
  const [highlightedVerses, setHighlightedVerses] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [verseDetails, setVerseDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [bookContent, setBookContent] = useState([])
  const [bookContentLoading, setBookContentLoading] = useState(false)
  
  // Navigation & Tabs States
  const [booksSegment, setBooksSegment] = useState('OT') // 'OT' | 'NT' | 'Apoc'
  const [activeTranslation, setActiveTranslation] = useState('KJV')
  const [rightSidebarTab, setRightSidebarTab] = useState('insights') // 'insights' | 'resources' | 'notes'
  const [bottomTab, setBottomTab] = useState('notes') // 'notes' | 'bookmarks' | 'highlights'
  const [readingPlans, setReadingPlans] = useState(initialReadingPlans)
  const [activePlanId, setActivePlanId] = useState('protestant')
  const [openDropdown, setOpenDropdown] = useState(null)
  const [showRightSidebar, setShowRightSidebar] = useState(true)
  const [showTranslationDropdown, setShowTranslationDropdown] = useState(false)
  const [showFontDropdown, setShowFontDropdown] = useState(false)
  const [showAudioDropdown, setShowAudioDropdown] = useState(false)
  const [showOptionsDropdown, setShowOptionsDropdown] = useState(false)
  
  // Note Creation states
  const [notesList, setNotesList] = useState([
    {
      id: 'note_1',
      book: 'Exodus',
      chapter: 1,
      verse: '7-14',
      title: 'Reflections on Exodus 1',
      text: "Pharaoh's response reveals the fear of losing control. God's people...",
      timestamp: '2026-06-17T15:00:00.000Z',
      starred: true
    },
    {
      id: 'note_2',
      book: 'Exodus',
      chapter: 1,
      verse: '1-6',
      title: "God's Sovereign Plan",
      text: "Even in oppression, God's plan moves forward. This passage...",
      timestamp: '2026-06-16T15:00:00.000Z',
      starred: true
    },
    {
      id: 'note_3',
      book: 'Exodus',
      chapter: 1,
      verse: '7-12',
      title: 'The Power of Multiplication',
      text: "Growth can attract opposition, but also displays God's blessing.",
      timestamp: '2026-05-10T15:00:00.000Z',
      starred: true
    }
  ])
  const [noteText, setNoteText] = useState('')
  
  // Myth-Buster state
  const [, setShowMythBuster] = useState(false)
  const [mythBusterContent, setMythBusterContent] = useState(null)
  const [mythBusterLoading, setMythBusterLoading] = useState(false)
  const [mythBusterError, setMythBusterError] = useState('')
  
  // AI Chat integration state
  const [aiMessages, setAIMessages] = useState([
    {
      type: 'assistant',
      content: 'Welcome! I am your scholarly AI Study Assistant. Ask me anything about this passage, or select one of the suggested research questions below.',
      timestamp: new Date().toISOString()
    }
  ])
  const [aiInputValue, setAIInputValue] = useState('')
  const [aiLoading, setAILoading] = useState(false)
  const [, setAIError] = useState('')
  const [aiStudyMode, setAiStudyMode] = useState('scholarly')
  const [suggestedFollowUps, setSuggestedFollowUps] = useState([])
  const [copiedIndex, setCopiedIndex] = useState(null)
  
  // State for broader canon books
  const [broaderCanonBooks, setBroaderCanonBooks] = useState([])
  const [, setLoadingBroaderBooks] = useState(false)
  
  // WordPopover state
  const [wordPopover, setWordPopover] = useState({
    isVisible: false,
    position: { x: 0, y: 0 },
    originalWord: '',
    meaning: '',
    contextBias: '',
    loading: false
  })

  const noteInputRef = useRef(null)
  const chatEndRef = useRef(null)
  const searchInputRef = useRef(null)
  const companionRef = useRef(null)

  // Sync selectedCanon with canonicalFilter prop
  useEffect(() => {
    if (canonicalFilter === 'BROADER') {
      setSelectedCanon('Broader Canon or Scholarly Pseudepigrapha')
      fetchBroaderCanonBooks()
    } else if (canonicalFilter === 'ETHIO81') {
      setSelectedCanon('Ethiopian Orthodox')
      fetchBroaderCanonBooks()
    } else if (canonicalFilter === 'CATH73') {
      setSelectedCanon('Catholic')
    } else if (canonicalFilter === 'PROT66') {
      setSelectedCanon('Protestant')
    }
  }, [canonicalFilter])

  // Fetch book content when selectedBook changes
  useEffect(() => {
    const fetchBookContent = async () => {
      if (!selectedBook) return
      setBookContentLoading(true)
      try {
        const response = await fetch(`/api/biblical-texts/book-content?book=${encodeURIComponent(selectedBook)}`)
        if (response.ok) {
          const data = await response.json()
          setBookContent(data.content || [])
        } else {
          setBookContent([])
        }
      } catch (err) {
        console.error('Error fetching book content:', err)
        setBookContent([])
      } finally {
        setBookContentLoading(false)
      }
    }
    fetchBookContent()
  }, [selectedBook])

  // Sync active chapter/verse validity when book content changes
  useEffect(() => {
    if (bookContent.length > 0) {
      const chapters = Array.from(new Set(bookContent.map(v => v.chapter.toString())))
      if (!chapters.includes(selectedChapter)) {
        setSelectedChapter('1')
        setSelectedVerse('1')
      }
    } else {
      setSelectedChapter('1')
      setSelectedVerse('1')
    }
  }, [bookContent, selectedChapter])

  // Set default active translation when selectedCanon changes
  useEffect(() => {
    const preferred = selectedCanon === 'Ethiopian Orthodox' ? 'ETH81' : (selectedCanon === 'Catholic' ? 'DRA' : 'KJV')
    setActiveTranslation(preferred)
  }, [selectedCanon])

  // Fetch verse details dynamically from backend
  useEffect(() => {
    setSelectedWordStudy(null)
    setMythBusterContent(null)
    setMythBusterError('')
    const fetchVerseDetails = async () => {
      if (!selectedBook || !selectedChapter || !selectedVerse) return
      setDetailsLoading(true)
      try {
        const response = await fetch(`/api/v1/texts/${encodeURIComponent(selectedBook)}/${selectedChapter}/${selectedVerse}/details`)
        if (response.ok) {
          const data = await response.json()
          setVerseDetails(data)
          
          // Map translations to format used by Copy/Export
          const mappedTranslations = {}
          Object.entries(data.translations || {}).forEach(([key, val]) => {
            let name = key.toUpperCase()
            let lang = 'English'
            if (key === 'kjv') name = 'King James Version'
            else if (key === 'asv') name = 'American Standard Version'
            else if (key === 'web') name = 'World English Bible'
            else if (key === 'webbe') name = 'World English Bible Ecumenical'
            else if (key === '1en_ch') name = '1 Enoch (Charles)'
            else if (key === 'jub_ch') name = 'Jubilees (Charles)'
            else if (key === 'meq1') name = '1 Meqabyan (Wikisource)'
            else if (key === 'meq2') name = '2 Meqabyan (Wikisource)'
            else if (key === 'meq3') name = '3 Meqabyan (Wikisource)'
            else if (key === 'targ_on') { name = 'Targum Onkelos'; lang = 'Aramaic'; }
            else if (key === 'josephus') name = 'Josephus (Antiquities)'
            
            mappedTranslations[key] = {
              name: name,
              language: lang,
              text: val
            }
          })
          setTranslations(mappedTranslations)
        } else {
          setVerseDetails(null)
          setTranslations({})
        }
      } catch (err) {
        console.error('Error retrieving verse details:', err)
        setVerseDetails(null)
        setTranslations({})
      } finally {
        setDetailsLoading(false)
      }
    }
    fetchVerseDetails()
  }, [selectedBook, selectedChapter, selectedVerse])

  // Fetch all saved notes on mount
  const loadNotes = async () => {
    try {
      const response = await fetch('/api/v1/notes')
      if (response.ok) {
        const data = await response.json()
        setNotesList(data)
      }
    } catch (err) {
      console.error("Error loading notes:", err)
      const saved = localStorage.getItem('unbound_notes')
      if (saved) {
        setNotesList(JSON.parse(saved))
      }
    }
  }

  useEffect(() => {
    loadNotes()
  }, [])

  // Auto-scroll AI chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [aiMessages, aiLoading])

  // Click outside to close nav dropdowns
  useEffect(() => {
    const handleOutsideClick = () => {
      setOpenDropdown(null)
      setShowTranslationDropdown(false)
      setShowFontDropdown(false)
      setShowAudioDropdown(false)
      setShowOptionsDropdown(false)
    }
    window.addEventListener('click', handleOutsideClick)
    return () => window.removeEventListener('click', handleOutsideClick)
  }, [])

  const shouldShowPseudepigraphaReader = selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' && selectedBook && selectedBook.includes && selectedBook.includes('Adam and Eve')

  // Translation bias database for key verses
  const getBiasAlerts = () => {
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
  // Book availability is intentionally re-evaluated only when the canon data changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCanon, broaderCanonBooks, selectedBook])

  // Effect to update AI messages when Adam and Eve is selected
  useEffect(() => {
    if (shouldShowPseudepigraphaReader) {
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
  }, [shouldShowPseudepigraphaReader])
  
  // Effect to fetch broader canon books on initial load if needed
  useEffect(() => {
    if ((selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' || selectedCanon === 'Ethiopian Orthodox') && broaderCanonBooks.length === 0) {
      fetchBroaderCanonBooks()
    }
  }, [selectedCanon, broaderCanonBooks.length])
  
  // Word click handler
  const handleWordClick = async (word, event, verseNum) => {
    event.preventDefault()
    event.stopPropagation()
    setWordStudyTab('usage')
    
    const targetVerse = verseNum ? verseNum.toString() : selectedVerse
    if (verseNum && verseNum.toString() !== selectedVerse) {
      setSelectedVerse(verseNum.toString())
    }
    
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
      const verse_ref = `${selectedBook} ${selectedChapter}:${targetVerse}`
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
          
          // Sync with the floating popover state
          setWordPopover(prev => ({
            ...prev,
            originalWord,
            meaning,
            contextBias,
            loading: false
          }))

          // Also set the sidebar study card state
          setSelectedWordStudy({
            ...context,
            word: word
          })
        } else {
          setWordPopover(prev => ({
            ...prev,
            originalWord: '',
            meaning: `Definition for "${word}" not available`,
            contextBias: '',
            loading: false
          }))
          
          setSelectedWordStudy({
            type: 'Not Found',
            word: word,
            meaning: `Definition for "${word}" not available`
          })
        }
      } else {
        setWordPopover(prev => ({
          ...prev,
          originalWord: '',
          meaning: `Definition for "${word}" not available`,
          contextBias: '',
          loading: false
        }))

        setSelectedWordStudy({
          type: 'Not Found',
          word: word,
          meaning: `Definition for "${word}" not available`
        })
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

      setSelectedWordStudy({
        type: 'Not Found',
        word: word,
        meaning: 'Failed to load word information'
      })
    }
  }
  
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
  const wrapWordsInSpans = (text, verseNum) => {
    if (!text) return text
    return text.split(/\b/).map((part, index) => {
      if (/[a-zA-Z]/.test(part) && part.length > 1) {
        return (
          <span 
            key={index}
            className="clickable-word"
            onClick={(e) => handleWordClick(part, e, verseNum)}
            style={{ cursor: 'pointer' }}
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
    '2 Peter': 3, '1 John': 5, '2 John': 1, '3 John': 1, 'Jude': 1, 'Revelation': 22,
    // Apocryphal / Broader Canon books
    '1 Enoch': 108, 'Enoch': 108, 'Jubilees': 50, 'Meqabyan 1': 36, 'Meqabyan 2': 15, 'Meqabyan 3': 10,
    'Tobit': 14, 'Judith': 16, 'Wisdom': 19, 'Sirach': 51, 'Baruch': 5,
    '1 Maccabees': 16, '2 Maccabees': 15, '1 Esdras': 9, 'Prayer of Manasseh': 1,
    'Letter of Jeremiah': 1, 'Additions to Daniel': 3, 'Additions to Esther': 10,
    'Psalm 151': 1, '3 Maccabees': 7, '4 Maccabees': 18, '2 Esdras': 16,
    'Adam and Eve 2': 15, 'Adam and Eve 3': 10, 'Book of Adam and Eve': 79,
    'Book of Abraham': 5, 'Ascension of Isaiah': 11, 'Book of Josephus': 20,
    'Didascalia': 43, 'Sirate Tsion': 30, 'Tizaz': 20, '1st Book of Dominos': 10,
    '2nd Book of Dominos': 10, 'Abtilis': 8, 'Book of Qäləmentos': 12
  }

  // Canonical traditions
  const canonOptions = [
    {
      name: 'Protestant',
      code: 'PROT66',
      bookCount: 66,
      description: 'Standard Protestant Bible used by most Western Christian traditions.',
      tradition: '66 Books included',
      details: 'Most widely used canon in Western Christianity.',
      accent: 'purple',
      icon: '✝'
    },
    {
      name: 'Ethiopian Orthodox',
      code: 'ETHIO81',
      bookCount: 96,
      description: 'Ancient African tradition with additional historical and spiritual books (traditionally grouped as 81).',
      tradition: '96 Books included',
      details: 'Includes Enoch, Jubilees, and other texts referenced by early Christians.',
      accent: 'teal',
      icon: '𓋹'
    },
    {
      name: 'Catholic',
      code: 'CATH73',
      bookCount: 73,
      description: 'Sacred tradition of the Catholic Church including the Deuterocanonicals.',
      tradition: '73 Books included',
      details: 'Includes Wisdom literature and historical books from the Septuagint.',
      accent: 'blue',
      icon: '⛪'
    },
    {
      name: 'Broader Canon or Scholarly Pseudepigrapha',
      code: 'BROADER',
      bookCount: 102,
      description: 'Extra-biblical texts offering historical, cultural, and spiritual context.',
      tradition: '102 Books available',
      details: 'Comprehensive collection including pseudepigraphal and apocryphal texts.',
      accent: 'gold',
      icon: '📜',
      isSpecial: true
    }
  ]

  // Helper to resolve book category segment
  const getBookSegment = (bookName) => {
    const currentCanonData = canonsData.find(c => c.name === selectedCanon) || canonsData[0]
    for (const cat of currentCanonData.categories) {
      if (cat.books.includes(bookName)) {
        if (cat.name.includes("Old Testament")) return 'OT'
        if (cat.name.includes("New Testament")) return 'NT'
        return 'Apoc'
      }
    }
    return 'OT'
  }

  // Handle canon selection
  const handleCanonSelect = (canon) => {
    setSelectedCanon(canon.name)
    if (setCanonicalFilter) {
      setCanonicalFilter(canon.code)
    }
    
    // Get books for the selected canon and select the first one
    const canonData = canonsData.find(c => c.name === canon.name) || canonsData[0];
    const firstCategory = canonData.categories[0];
    if (firstCategory && firstCategory.books.length > 0) {
      const firstBook = firstCategory.books[0];
      setSelectedBook(firstBook);
      setSelectedChapter('1');
      setSelectedVerse('1');
      
      // Auto switch segmented filter based on category of first book
      const firstSegment = getBookSegment(firstBook)
      setBooksSegment(firstSegment)
    }
    
    if (canon.code === 'BROADER' || canon.code === 'ETHIO81') {
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
      setMythBusterError('Failed to generate summary audit.')
      console.error('Myth-buster error:', error)
    } finally {
      setMythBusterLoading(false)
    }
  }

  // AI Chat functionality
  const sendAIChatMessage = async (text) => {
    const query = text.trim()
    if (!query || aiLoading) return

    const userMessage = {
      type: 'user',
      content: query,
      timestamp: new Date().toISOString()
    }

    // Capture conversation history from current message stack (exclude welcome greeting)
    const history = aiMessages
      .filter(msg => !msg.content.startsWith('Welcome!'))
      .map(msg => ({
        role: msg.type === 'user' ? 'user' : 'assistant',
        content: msg.content
      }))

    setAIMessages(prev => [...prev, userMessage])
    setAILoading(true)
    setAIError('')

    try {
      const res = await fetch("/api/v1/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: `${query} (Context: ${selectedBook} ${selectedChapter}:${selectedVerse})`,
          study_mode: aiStudyMode,
          history: history
        })
      })
      if (res.ok) {
        const data = await res.json()
        const aiMessage = {
          type: 'assistant',
          content: data.answer,
          timestamp: new Date().toISOString()
        }
        setAIMessages(prev => [...prev, aiMessage])
        if (data.follow_ups && data.follow_ups.length > 0) {
          setSuggestedFollowUps(data.follow_ups)
        }
      } else {
        throw new Error("API call failed")
      }
    } catch (error) {
      console.error("AI Assistant API failed, using fallback:", error)
      setTimeout(() => {
        let fallbackText = `Scholarly context for ${selectedBook} ${selectedChapter}:${selectedVerse}: This verse explores themes of divine covenant, sacrifice, and translation nuances.`;
        if (aiStudyMode === 'kids') {
          fallbackText = `### 👶 Kids Bible Study: Let's explore ${selectedBook} ${selectedChapter}:${selectedVerse}!\n\nImagine you are going on a huge journey to a new country. That's exactly what is happening here! God was helping His family grow strong and stick together, even though they were in a strange land. No matter where we go or what happens, God is always with us!`;
        } else if (aiStudyMode === 'devotional') {
          fallbackText = `### 📖 Daily Devotional: Staying Faithful in the Storm\n\nIn this passage, we see God's people in a transition season. Trust that God is working in the background of your life. He is faithful to His promises even when the environment feels hostile.\n\n*Lord, help me trust Your promises today. Amen.*`;
        } else if (aiStudyMode === 'sermon') {
          fallbackText = `### 🎙️ Sermon Outline: 'Thriving Under Pressure'\n**Text:** ${selectedBook} ${selectedChapter}:${selectedVerse}\n\n* **Point 1: The Promise Outlives the Patriarchs** - God's covenant remains alive.\n* **Point 2: Opposition Cannot Halt God's Plan** - hardship spreads faith like seeds.\n* **Point 3: The Call to Quiet Faithfulness** - quiet trust keeps us firm.`;
        } else if (aiStudyMode === 'discussion') {
          fallbackText = `### 💬 Small Group Discussion Guide\n\n1. **Question:** The passage starts with the names of those who went. Why is it important to remember our history?\n2. **Question:** How do we handle situations where our beliefs are no longer respected?\n3. **Question:** Have you ever seen a situation where hardship led to spiritual growth?`;
        }

        const aiMessage = {
          type: 'assistant',
          content: fallbackText,
          timestamp: new Date().toISOString()
        }
        setAIMessages(prev => [...prev, aiMessage])
        
        // Mock dynamic follow-ups based on the book
        const book_lower = selectedBook.toLowerCase()
        if (book_lower.includes('genesis')) {
          setSuggestedFollowUps([
            "What is the historical context of the Enuma Elish?",
            "How does the covenant with Abraham relate to this?"
          ])
        } else {
          setSuggestedFollowUps([
            "Why did the new Pharaoh fear the Israelites?",
            "What is the significance of the midwives Shiphrah and Puah?"
          ])
        }
        setAILoading(false)
      }, 1000)
    } finally {
      setAILoading(false)
    }
  }

  const handleAISubmit = async (e) => {
    e?.preventDefault()
    const query = aiInputValue.trim()
    if (!query || aiLoading) return

    setAIInputValue('')
    await sendAIChatMessage(query)
  }

  const getPreviewQuestions = (book, chapter, verse) => {
    const ch = chapter || '1'
    const vs = verse || '1'
    
    if (book === 'Genesis') {
      return [
        `What is the theological significance of creation in Genesis ${ch}?`,
        `How do the Hebrew terms in Genesis ${ch} relate to the origin of the cosmos?`,
        `What are the major thematic cross-references for Genesis ${ch}:${vs}?`
      ]
    }
    if (book === 'Exodus') {
      return [
        `Why did Pharaoh fear the Israelites in Exodus ${ch}?`,
        `What can we learn about God's plan and deliverance in Exodus ${ch}?`,
        `How does Exodus ${ch}:${vs} connect to the call of Moses?`
      ]
    }
    if (book === 'Psalms' || book === 'Psalm') {
      return [
        `What genre of Psalm is Psalm ${ch} (e.g. Lament, Praise, Messianic)?`,
        `How does Psalm ${ch} express worship or crying out to God?`,
        `What is the literary structure of Psalm ${ch}:${vs}?`
      ]
    }
    if (book === 'Isaiah') {
      return [
        `What is the historical context of Isaiah ${ch} regarding the Southern Kingdom?`,
        `Are there Messianic prophecies in Isaiah ${ch}:${vs}?`,
        `How does this chapter contrast judgment and divine comfort?`
      ]
    }
    if (['Matthew', 'Mark', 'Luke', 'John'].includes(book)) {
      return [
        `How does ${book} ${ch} portray the ministry and identity of Jesus?`,
        `What is the original Greek term significance in ${book} ${ch}:${vs}?`,
        `How does this gospel passage connect to Jewish expectations?`
      ]
    }
    if (['Romans', '1 Corinthians', '2 Corinthians', 'Galatians', 'Ephesians', 'Philippians', 'Colossians'].includes(book)) {
      return [
        `What theological argument is Paul making in ${book} ${ch}?`,
        `What was the cultural setting of the church in ${book} when written?`,
        `How does ${book} ${ch}:${vs} apply to Christian life today?`
      ]
    }
    
    return [
      `What is the historical and cultural background of ${book} ${ch}?`,
      `What are the key theological themes in ${book} ${ch}:${vs}?`,
      `What do the original languages suggest for the terms in ${book} ${ch}:${vs}?`
    ]
  }

  // Save notes to database
  const handleSaveNote = async () => {
    if (!noteText.trim()) return
    const notePayload = {
      book: selectedBook,
      chapter: parseInt(selectedChapter),
      verse: parseInt(selectedVerse),
      text: noteText,
      tags: ['Study Session', selectedBook]
    }
    try {
      const res = await fetch('/api/v1/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(notePayload)
      })
      if (res.ok) {
        const savedNote = await res.json()
        setNotesList(prev => [
          {
            id: savedNote.id,
            book: savedNote.book,
            chapter: savedNote.chapter,
            verse: savedNote.verse,
            title: `Reflections on ${savedNote.book} ${savedNote.chapter}`,
            text: savedNote.text,
            timestamp: savedNote.timestamp || new Date().toISOString(),
            starred: true
          },
          ...prev
        ])
        setNoteText('')
      } else {
        throw new Error('Failed to save note to API')
      }
    } catch (err) {
      console.error("Failed to save note to API, falling back to local storage:", err)
      const fallbackNote = {
        id: 'note_' + Date.now(),
        ...notePayload,
        title: `Reflections on ${selectedBook} ${selectedChapter}`,
        timestamp: new Date().toISOString(),
        starred: true
      }
      const saved = localStorage.getItem('unbound_notes')
      const allNotes = saved ? JSON.parse(saved) : []
      allNotes.unshift(fallbackNote)
      localStorage.setItem('unbound_notes', JSON.stringify(allNotes))
      setNotesList(prev => [fallbackNote, ...prev])
      setNoteText('')
    }
  }

  const handleDeleteNote = async (id, event) => {
    event.stopPropagation()
    try {
      const res = await fetch(`/api/v1/notes/${id}`, {
        method: 'DELETE'
      })
      if (res.ok || res.status === 404) {
        setNotesList(prev => prev.filter(note => note.id !== id))
      }
    } catch (err) {
      console.error("Failed to delete note from API:", err)
      const saved = localStorage.getItem('unbound_notes')
      if (saved) {
        const allNotes = JSON.parse(saved).filter(note => note.id !== id)
        localStorage.setItem('unbound_notes', JSON.stringify(allNotes))
      }
      setNotesList(prev => prev.filter(note => note.id !== id))
    }
  }

  const handleCopyText = async () => {
    let textToCopy = `${selectedBook} ${selectedChapter}:${selectedVerse}\n\n`
    const activeTranslations = Object.keys(translations).length > 0 ? translations : {};
    Object.entries(activeTranslations).forEach(([, translation]) => {
      textToCopy += `${translation.name} (${translation.language}):\n`
      textToCopy += `${translation.text}\n\n`
    })
    try {
      await navigator.clipboard.writeText(textToCopy)
    } catch (error) {
      console.error('Failed to copy text:', error)
    }
  }

  const handlePrint = () => {
    window.print()
  }

  const handleExport = () => {
    let exportContent = `Biblical Verse Analysis Export\n`
    exportContent += `Generated on: ${new Date().toLocaleString()}\n`
    exportContent += `Canon: ${selectedCanon}\n\n`
    exportContent += `========================================\n`
    exportContent += `${selectedBook} ${selectedChapter}:${selectedVerse}\n`
    exportContent += `========================================\n\n`
    
    exportContent += `TRANSLATIONS:\n\n`
    const activeTranslations = Object.keys(translations).length > 0 ? translations : {};
    Object.entries(activeTranslations).forEach(([, translation]) => {
      exportContent += `${translation.name} (${translation.language}):\n`
      exportContent += `${translation.text}\n\n`
    })
    
    exportContent += `ANALYSIS:\n\n`
    if (verseDetails) {
      exportContent += `Meaning: ${verseDetails.verse_meaning}\n\n`
    }
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

  // Calculate statistics
  const getCanonStats = () => {
    const booksInCanon = getBooksForSelectedCanon()
    const totalBooks = booksInCanon.length
    const availableForStudy = booksInCanon.filter(b => isBookLoaded(b)).length
    
    const inProgressSet = new Set()
    inProgressSet.add(selectedBook)
    notesList.forEach(n => {
      if (booksInCanon.includes(n.book)) {
        inProgressSet.add(n.book)
      }
    })
    bookmarkedVerses.forEach(v => {
      const bName = v.split(' ')[0]
      if (booksInCanon.includes(bName)) {
        inProgressSet.add(bName)
      }
    })
    const inProgress = inProgressSet.size

    return {
      totalBooks,
      availableForStudy,
      inProgress
    }
  }
  
  const getBooksForSelectedCanon = () => {
    const canonData = canonsData.find(c => c.name === selectedCanon)
    if (canonData) {
      return canonData.categories.flatMap(cat => cat.books)
    }
    return books
  }

  const allAvailableBooks = [...(availableBooks || []), ...(broaderCanonBooks || [])]
  const isBookLoaded = (bookName) => {
    if (!bookName) return false
    return allAvailableBooks.some(b => {
      const name = typeof b === 'string' ? b : (b && b.name) ? b.name : ''
      return name.toLowerCase() === bookName.toLowerCase()
    })
  }

  const matchesSearch = (bookName) => {
    if (!searchQuery) return true
    return bookName.toLowerCase().includes(searchQuery.toLowerCase())
  }

  const getPrevBookAndChapter = () => {
    const ch = parseInt(selectedChapter)
    if (ch > 1) {
      return { book: selectedBook, chapter: (ch - 1).toString() }
    }
    const idx = booksList.indexOf(selectedBook)
    if (idx > 0) {
      const prevBook = booksList[idx - 1]
      const prevBookChCount = bookChapters[prevBook] || 1
      return { book: prevBook, chapter: prevBookChCount.toString() }
    }
    return null
  }

  const getNextBookAndChapter = () => {
    const ch = parseInt(selectedChapter)
    if (ch < maxChapters) {
      return { book: selectedBook, chapter: (ch + 1).toString() }
    }
    const idx = booksList.indexOf(selectedBook)
    if (idx !== -1 && idx < booksList.length - 1) {
      const nextBook = booksList[idx + 1]
      return { book: nextBook, chapter: '1' }
    }
    return null
  }

  const hasDecolonialAudit = (book, chapter, verseNum) => {
    const b = book.trim()
    const c = chapter.toString()
    const v = verseNum.toString()
    
    if (b === 'Genesis' && c === '9' && v === '25') return true
    if (b === 'Song of Solomon' && c === '1' && v === '5') return true
    if (b === 'Numbers' && c === '12' && (v === '1' || v === '10')) return true
    if (b === 'Acts' && c === '8' && (v === '27' || v === '37')) return true
    if (b === 'Ephesians' && c === '6' && v === '5') return true
    if (b === 'Galatians' && c === '4' && v === '25') return true
    if (b === '1 Peter' && c === '2' && v === '18') return true
    if (b === 'Colossians' && c === '3' && v === '22') return true
    return false
  }

  const getChapterVerses = () => {
    // 1. Get the baseline Ethiopian verses for this chapter
    let ethVerses = bookContent.filter(v => 
      v.chapter.toString() === selectedChapter.toString() && 
      ['ETH81', 'ETHIO81', 'ETH'].includes(v.translation.toUpperCase())
    )
    
    // Sort them
    ethVerses.sort((a, b) => a.verse - b.verse)
    
    // 2. If no Ethiopian verses are available (e.g. for a book not yet seeded in EOTC), fall back to the active translation
    if (ethVerses.length === 0) {
      let filtered = bookContent.filter(v => 
        v.chapter.toString() === selectedChapter.toString() && 
        v.translation.toUpperCase() === activeTranslation.toUpperCase()
      )
      if (filtered.length === 0) {
        const firstAvailableTrans = bookContent.find(v => v.chapter.toString() === selectedChapter.toString())?.translation
        if (firstAvailableTrans) {
          filtered = bookContent.filter(v => v.chapter.toString() === selectedChapter.toString() && v.translation === firstAvailableTrans)
        }
      }
      return filtered.sort((a, b) => a.verse - b.verse).map(v => ({
        id: v.id,
        verse: v.verse,
        text: v.text,
        eth_text: v.text,
        is_omitted: false
      }))
    }
    
    // 3. Map Ethiopian verses and align the active translation
    return ethVerses.map(ethV => {
      const activeV = bookContent.find(v => 
        v.chapter.toString() === selectedChapter.toString() && 
        v.verse.toString() === ethV.verse.toString() && 
        v.translation.toUpperCase() === activeTranslation.toUpperCase()
      )
      
      return {
        id: ethV.id,
        verse: ethV.verse,
        text: activeV ? activeV.text : null,
        eth_text: ethV.text,
        is_omitted: !activeV
      }
    })
  }

  const currentChapterVerses = getChapterVerses()

  const maxChapters = bookContent.length > 0
    ? Math.max(...bookContent.map((verse) => verse.chapter))
    : (bookChapters[selectedBook] || 50)

  const handleToggleBookmark = (verseRef) => {
    setBookmarkedVerses(prev => {
      if (prev.includes(verseRef)) {
        return prev.filter(ref => ref !== verseRef)
      } else {
        return [...prev, verseRef]
      }
    })
  }

  const handleToggleHighlight = (verseRef) => {
    setHighlightedVerses(prev => {
      if (prev.includes(verseRef)) {
        return prev.filter(ref => ref !== verseRef)
      } else {
        return [...prev, verseRef]
      }
    })
  }

  const handleCopySelectedVerse = async (vNum, vText) => {
    const textToCopy = `${selectedBook} ${selectedChapter}:${vNum} - ${vText}`
    try {
      await navigator.clipboard.writeText(textToCopy)
    } catch (err) {
      console.error("Failed to copy verse:", err)
    }
  }

  const handleShareVerse = (vNum) => {
    const shareUrl = `${window.location.origin}/scriptures?book=${encodeURIComponent(selectedBook)}&chapter=${selectedChapter}&verse=${vNum}`
    navigator.clipboard.writeText(shareUrl).then(() => {
      alert("Shareable link copied to clipboard!")
    }).catch(err => {
      console.error("Failed to copy link:", err)
    })
  }

  const scrollToCompanion = (tab = 'notes') => {
    setBottomTab(tab)
    setTimeout(() => {
      const container = document.querySelector('.center-workspace')
      const companion = document.querySelector('.bottom-study-companion')
      if (container && companion) {
        container.scrollTo({
          top: companion.offsetTop - 24,
          behavior: 'smooth'
        })
      } else {
        companionRef.current?.scrollIntoView({ behavior: 'smooth' })
      }
    }, 50)
  }

  const openNoteEditor = () => {
    setShowRightSidebar(true)
    setRightSidebarTab('notes')
    setTimeout(() => {
      noteInputRef.current?.focus()
    }, 100)
  }

  const handleNavClick = (pageId, event) => {
    event?.preventDefault()
    if (onPageChange) {
      onPageChange(pageId)
    }
  }

  const handleNavDropdownToggle = (dropdownName, event) => {
    event?.stopPropagation()
    setOpenDropdown(prev => prev === dropdownName ? null : dropdownName)
  }

  const focusSearch = () => {
    searchInputRef.current?.focus()
  }

  const stats = getCanonStats()
  const booksList = getBooksForSelectedCanon()

  // Filter book list based on search query and OT/NT/Apoc segmented filter
  const filteredBooks = booksList.filter(bookName => {
    const matchesQuery = matchesSearch(bookName)
    const matchesSeg = getBookSegment(bookName) === booksSegment
    return matchesQuery && matchesSeg
  })

  // Get active translation list for current chapter
  const getAvailableTranslations = () => {
    const avail = Array.from(new Set(bookContent.map(v => v.translation.toUpperCase())))
    const preferred = selectedCanon === 'Ethiopian Orthodox' ? 'ETH81' : (selectedCanon === 'Catholic' ? 'DRA' : 'KJV')
    if (preferred && !avail.includes(preferred)) {
      avail.unshift(preferred)
    }
    return avail
  }
  const availableTranslations = getAvailableTranslations()

  return (
    <div className="premium-bible-workspace">
      {/* 1. TOP NAVIGATION BAR */}
      <nav className="fixed-top-nav">
        <div className="nav-left">
          <div className="app-logo">
            <span className="logo-sparkle">✦</span>
            <span className="logo-text font-semibold">The Unbound Bible</span>
          </div>
        </div>

        <div className="nav-center">
          <ul className="nav-tabs">
            <li className="nav-tab-item">
              <a href="#home" onClick={(e) => handleNavClick('home', e)} className="nav-tab-link">
                🏠 Home
              </a>
            </li>
            
            <li className={`nav-tab-item dropdown ${openDropdown === 'scriptures' ? 'open' : ''}`}>
              <a href="#scriptures" onClick={(e) => handleNavDropdownToggle('scriptures', e)} className="nav-tab-link active">
                📖 Scriptures <span className="chevron-icon">▼</span>
              </a>
              <ul className="nav-dropdown-menu">
                <li>
                  <a href="#reader" onClick={(e) => { handleNavClick('apocrypha', e); setOpenDropdown(null); }} className="dropdown-link active">
                    📜 Scripture Reader
                  </a>
                </li>
                <li>
                  <a href="#comparison" onClick={(e) => { handleNavClick('textual', e); setOpenDropdown(null); }} className="dropdown-link">
                    🔄 Compare Scripture
                  </a>
                </li>
                <li>
                  <a href="#canon-compare" onClick={(e) => { handleNavClick('canon-compare', e); setOpenDropdown(null); }} className="dropdown-link">
                    ⚏ Canon Comparison
                  </a>
                </li>
              </ul>
            </li>

            <li className={`nav-tab-item dropdown ${openDropdown === 'decolonial' ? 'open' : ''}`}>
              <a href="#decolonial" onClick={(e) => handleNavDropdownToggle('decolonial', e)} className="nav-tab-link">
                ⚖️ Decolonial Audit <span className="chevron-icon">▼</span>
              </a>
              <ul className="nav-dropdown-menu">
                <li>
                  <a href="#race-misuse" onClick={(e) => { handleNavClick('race-misuse', e); setOpenDropdown(null); }} className="dropdown-link">
                    ✊ Race & Misuse
                  </a>
                </li>
                <li>
                  <a href="#bias-explorer" onClick={(e) => { handleNavClick('bias-explorer', e); setOpenDropdown(null); }} className="dropdown-link">
                    ⚖️ Translation Bias
                  </a>
                </li>
                <li>
                  <a href="#factbook" onClick={(e) => { handleNavClick('factbook', e); setOpenDropdown(null); }} className="dropdown-link">
                    📘 Factbook Encyclopedia
                  </a>
                </li>
              </ul>
            </li>

            <li className={`nav-tab-item dropdown ${openDropdown === 'aistudy' ? 'open' : ''}`}>
              <a href="#aistudy" onClick={(e) => handleNavDropdownToggle('aistudy', e)} className="nav-tab-link">
                🤖 AI Study <span className="chevron-icon">▼</span>
              </a>
              <ul className="nav-dropdown-menu">
                <li>
                  <a href="#chat" onClick={(e) => { handleNavClick('chat', e); setOpenDropdown(null); }} className="dropdown-link">
                    💬 Ask the Bible
                  </a>
                </li>
                <li>
                  <a href="#sermon" onClick={(e) => { handleNavClick('sermon', e); setOpenDropdown(null); }} className="dropdown-link">
                    🎤 Sermon Analysis
                  </a>
                </li>
              </ul>
            </li>

            <li className={`nav-tab-item dropdown ${openDropdown === 'research' ? 'open' : ''}`}>
              <a href="#research" onClick={(e) => handleNavDropdownToggle('research', e)} className="nav-tab-link">
                🔬 Research <span className="chevron-icon">▼</span>
              </a>
              <ul className="nav-dropdown-menu">
                <li>
                  <a href="#hub" onClick={(e) => { handleNavClick('research', e); setOpenDropdown(null); }} className="dropdown-link">
                    🔬 Research Hub
                  </a>
                </li>
                <li>
                  <a href="#media" onClick={(e) => { handleNavClick('media', e); setOpenDropdown(null); }} className="dropdown-link">
                    🎨 Interactive Media
                  </a>
                </li>
                <li>
                  <a href="#map" onClick={(e) => { handleNavClick('map', e); setOpenDropdown(null); }} className="dropdown-link">
                    🗺️ Biblical Map
                  </a>
                </li>
              </ul>
            </li>

            <li className={`nav-tab-item dropdown ${openDropdown === 'library' ? 'open' : ''}`}>
              <a href="#library" onClick={(e) => handleNavDropdownToggle('library', e)} className="nav-tab-link">
                📂 My Library <span className="chevron-icon">▼</span>
              </a>
              <ul className="nav-dropdown-menu">
                <li>
                  <a href="#notes" onClick={(e) => { handleNavClick('notes', e); setOpenDropdown(null); }} className="dropdown-link">
                    📂 Saved Notes
                  </a>
                </li>
                <li>
                  <a href="#forum" onClick={(e) => { handleNavClick('forum', e); setOpenDropdown(null); }} className="dropdown-link">
                    👥 Community Forum
                  </a>
                </li>
              </ul>
            </li>
          </ul>
        </div>

        <div className="nav-right">
          <button className="nav-icon-control" title="Toggle Theme">🌙</button>
          <button className="nav-icon-control relative" title="Notifications">
            🔔<span className="notification-badge"></span>
          </button>
          <button className="nav-profile-btn">
            <span className="profile-avatar">👤</span>
            <span>Sign In</span>
          </button>
          <div className="app-window-controls">
            <button className="win-control-btn" title="Minimize">－</button>
            <button className="win-control-btn" title="Maximize">⬜</button>
            <button className="win-control-btn close" title="Close">✕</button>
          </div>
        </div>
      </nav>

      {/* WORKSPACE LAYOUT CONTAINER */}
      <div className="workspace-layout">
        
        {/* 2. LEFT SIDEBAR — CANON LIBRARY */}
        <aside className="left-sidebar">
          <div className="sidebar-section">
            <h4 className="sidebar-section-title">Canon Library</h4>
            <ul className="canon-list">
              <li 
                className={`canon-item ${selectedCanon === 'Broader Canon or Scholarly Pseudepigrapha' ? 'active' : ''}`}
                onClick={() => handleCanonSelect(canonOptions[3])}
              >
                📂 All Canons
              </li>
              <li 
                className={`canon-item ${selectedCanon === 'Protestant' ? 'active' : ''}`}
                onClick={() => handleCanonSelect(canonOptions[0])}
              >
                ✝ Protestant
              </li>
              <li 
                className={`canon-item ${selectedCanon === 'Ethiopian Orthodox' ? 'active' : ''}`}
                onClick={() => handleCanonSelect(canonOptions[1])}
              >
                𓋹 Ethiopian Orthodox
              </li>
              <li 
                className={`canon-item ${selectedCanon === 'Catholic' ? 'active' : ''}`}
                onClick={() => handleCanonSelect(canonOptions[2])}
              >
                ⛪ Catholic
              </li>
              <li 
                className={`canon-item ${selectedCanon === 'Pseudepigrapha' ? 'active' : ''}`}
                onClick={() => handleCanonSelect(canonOptions[3])}
              >
                📜 Pseudepigrapha
              </li>
            </ul>
          </div>

          <div className="sidebar-section books-section">
            <h4 className="sidebar-section-title">Books</h4>
            <div className="search-box">
              <span className="search-icon">🔍</span>
              <input 
                ref={searchInputRef}
                type="text" 
                placeholder="Search books..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
              />
            </div>
            
            <div className="segmented-filter-bar">
              <button 
                className={`segment-btn ${booksSegment === 'OT' ? 'active' : ''}`}
                onClick={() => setBooksSegment('OT')}
              >
                OT
              </button>
              <button 
                className={`segment-btn ${booksSegment === 'NT' ? 'active' : ''}`}
                onClick={() => setBooksSegment('NT')}
              >
                NT
              </button>
              <button 
                className={`segment-btn ${booksSegment === 'Apoc' ? 'active' : ''}`}
                onClick={() => setBooksSegment('Apoc')}
              >
                Apoc.
              </button>
            </div>

            <div className="scrollable-books-container">
              {filteredBooks.length === 0 ? (
                <div className="empty-books-message">No books in this segment</div>
              ) : (
                filteredBooks.map((bookName) => (
                  <button
                    key={bookName}
                    onClick={() => {
                      setSelectedBook(bookName)
                      setSelectedChapter('1')
                      setSelectedVerse('1')
                    }}
                    className={`book-list-item ${selectedBook === bookName ? 'active' : ''} ${!isBookLoaded(bookName) ? 'summary-only' : ''}`}
                  >
                    <span className="book-name-text">{bookName}</span>
                    {!isBookLoaded(bookName) && <span className="badge-summary-only">Summary</span>}
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="sidebar-section workspace-shortcuts">
            <h4 className="sidebar-section-title">Workspace</h4>
            <ul className="shortcut-list">
              <li className="shortcut-item" onClick={() => { setShowRightSidebar(true); setRightSidebarTab('insights'); scrollToCompanion('notes'); }}>
                <span className="shortcut-icon-text">🗃️ Study Companion</span>
                {notesList.length > 0 && <span className="shortcut-badge">{notesList.length}</span>}
              </li>
              <li className="shortcut-item" onClick={() => { scrollToCompanion('notes'); openNoteEditor(); }}>
                <span className="shortcut-icon-text">⭐ Saved Notes</span>
              </li>
              <li className="shortcut-item" onClick={() => { scrollToCompanion('highlights'); }}>
                <span className="shortcut-icon-text">🖍️ Highlights</span>
              </li>
              <li className="shortcut-item" onClick={() => { scrollToCompanion('reading_plans'); }}>
                <span className="shortcut-icon-text">📋 Reading Plans</span>
              </li>
              <li className="shortcut-item">
                <span className="shortcut-icon-text">📂 Custom Collections</span>
              </li>
              <li className="shortcut-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="shortcut-icon-text">⚙️ Settings</span>
                <span style={{ fontSize: '10px', opacity: 0.5 }}>▼</span>
              </li>
            </ul>
          </div>
        </aside>

        {/* CENTER COLUMN: MAIN WORKSPACE */}
        <main className="center-workspace">
          
          {/* Top Intro Section */}
          <section className="workspace-intro">
            <h1 className="intro-heading">Explore Scripture with Depth & Context</h1>
            <p className="intro-subtext">
              Select a canon from the library to explore inspired texts with rich study tools. Read, compare, analyze words, cross-reference passages, and uncover timeless truth.
            </p>
          </section>

          {/* 4. CANON SELECTION CARDS */}
          <section className="canon-cards-section">
            <div className="canon-cards-grid">
              {canonOptions.map((canon) => (
                <div 
                  key={canon.code}
                  className={`canon-glass-card ${selectedCanon === canon.name ? 'selected' : ''} accent-${canon.accent}`}
                  onClick={() => handleCanonSelect(canon)}
                >
                  <div className="card-header-row">
                    <span className={`card-icon-container text-${canon.accent}`}>
                      {canon.icon}
                    </span>
                    <span className="card-book-count">{canon.bookCount} Books</span>
                  </div>
                  <h3 className="card-title">{canon.name}</h3>
                  <p className="card-description">{canon.description}</p>
                  <div className="card-footer-row">
                    <span className="card-status">{canon.tradition}</span>
                    <span className="card-arrow-indicator">➔</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* 5. STATS / PROGRESS STRIP */}
          {(() => {
            const progressPercent = stats.totalBooks > 0 ? Math.round((stats.inProgress / stats.totalBooks) * 100) : 0
            const circumference = 87.9
            const strokeDashoffset = circumference - (progressPercent / 100) * circumference
            
            return (
              <section className="stats-progress-strip">
                <div className="stat-pill">
                  <div className="stat-pill-row">
                    <span className="stat-icon-wrapper purple">🎵</span>
                    <div className="stat-pill-text-col">
                      <span className="stat-label">Total Books</span>
                      <span className="stat-value">{stats.totalBooks}</span>
                      <span className="stat-subtext">Across All Canons</span>
                    </div>
                  </div>
                </div>
                <div className="stat-pill">
                  <div className="stat-pill-row">
                    <span className="stat-icon-wrapper teal">🔋</span>
                    <div className="stat-pill-text-col">
                      <span className="stat-label">Available</span>
                      <span className="stat-value text-teal">{stats.availableForStudy}</span>
                      <span className="stat-subtext">Ready for Study</span>
                    </div>
                  </div>
                </div>
                <div className="stat-pill">
                  <div className="stat-pill-row">
                    <span className="stat-icon-wrapper gold">⏳</span>
                    <div className="stat-pill-text-col">
                      <span className="stat-label">In Progress</span>
                      <span className="stat-value text-gold">{stats.inProgress}</span>
                      <span className="stat-subtext">Continue Reading</span>
                    </div>
                  </div>
                </div>
                <div className="stat-progress-pill">
                  <div className="progress-ring-container">
                    <svg className="progress-ring" width="36" height="36">
                      <circle className="progress-ring-bg" stroke="rgba(255,255,255,0.06)" strokeWidth="3" fill="transparent" r="14" cx="18" cy="18"/>
                      <circle className="progress-ring-fill" stroke="#8B5CF6" strokeWidth="3" fill="transparent" r="14" cx="18" cy="18" strokeDasharray="87.9" strokeDashoffset={strokeDashoffset}/>
                    </svg>
                    <span className="progress-value">{progressPercent}%</span>
                  </div>
                  <div className="progress-text-col">
                    <span className="progress-title">Your Progress</span>
                    <span className="progress-status">{progressPercent > 0 ? "Keep studying!" : "Keep going!"}</span>
                  </div>
                </div>
              </section>
            )
          })()}

          {/* 6. SCRIPTURE READER PANEL */}
          <section className="scripture-reader-panel">
            
            {/* Sticky Reader Toolbar */}
            <div className="reader-toolbar">
              <div className="toolbar-left">
                <select 
                  value={`${selectedBook} ${selectedChapter}`}
                  onChange={(e) => {
                    const val = e.target.value
                    const lastSpaceIndex = val.lastIndexOf(' ')
                    if (lastSpaceIndex !== -1) {
                      const book = val.substring(0, lastSpaceIndex)
                      const chapter = val.substring(lastSpaceIndex + 1)
                      setSelectedBook(book)
                      setSelectedChapter(chapter)
                      setSelectedVerse('1')
                    }
                  }}
                  className="selector-dropdown combined-book-chapter-dropdown font-serif font-semibold"
                >
                  {booksList.flatMap(b => {
                    const chCount = bookChapters[b] || 1
                    return Array.from({ length: chCount }, (_, i) => {
                      const chNum = (i + 1).toString()
                      const combo = `${b} ${chNum}`
                      return (
                        <option key={combo} value={combo}>
                          {combo}
                        </option>
                      )
                    })
                  })}
                </select>
              </div>

              <div className="toolbar-right">
                {/* Translation Capsule Dropdown */}
                <div className="custom-dropdown-container">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowTranslationDropdown(!showTranslationDropdown)
                      setShowFontDropdown(false)
                      setShowAudioDropdown(false)
                      setShowOptionsDropdown(false)
                    }} 
                    className="capsule-btn translation-btn font-bold"
                  >
                    <span className="doc-icon">📄</span>
                    <span className="btn-text">{getShortTranslationName(activeTranslation)}</span>
                    <span className="chevron-v">v</span>
                  </button>
                  {showTranslationDropdown && (
                    <ul className="custom-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                      {(availableTranslations.length > 0 ? availableTranslations : ['KJV', 'NRSVUE', 'ETH81']).map(transCode => (
                        <li 
                          key={transCode}
                          className={`dropdown-item ${activeTranslation === transCode ? 'active' : ''}`}
                          onClick={() => {
                            setActiveTranslation(transCode)
                            setShowTranslationDropdown(false)
                          }}
                        >
                          {getTranslationName(transCode)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Font Capsule Dropdown */}
                <div className="custom-dropdown-container">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowFontDropdown(!showFontDropdown)
                      setShowTranslationDropdown(false)
                      setShowAudioDropdown(false)
                      setShowOptionsDropdown(false)
                    }} 
                    className="capsule-btn font-btn"
                  >
                    <span className="btn-text">Aa</span>
                    <span className="chevron-v">v</span>
                  </button>
                  {showFontDropdown && (
                    <ul className="custom-dropdown-menu font-dropdown" onClick={(e) => e.stopPropagation()}>
                      <li className="dropdown-section-title" style={{ padding: '4px 12px 2px 12px', fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600', letterSpacing: '0.05em' }}>FONT SIZE</li>
                      {[
                        { code: 'sm', name: 'Small' },
                        { code: 'md', name: 'Medium' },
                        { code: 'lg', name: 'Large' },
                        { code: 'xl', name: 'Extra Large' },
                        { code: 'xxl', name: 'Double Extra Large' }
                      ].map(size => (
                        <li 
                          key={size.code}
                          className={`dropdown-item ${fontSize === size.code ? 'active' : ''}`}
                          onClick={() => {
                            setFontSize(size.code)
                            setShowFontDropdown(false)
                          }}
                        >
                          {size.name}
                        </li>
                      ))}
                      <li className="dropdown-divider-item" style={{ height: '1px', backgroundColor: 'var(--border-soft)', margin: '8px 0' }}></li>
                      <li className="dropdown-section-title" style={{ padding: '4px 12px 2px 12px', fontSize: '11px', color: 'var(--text-muted)', fontWeight: '600', letterSpacing: '0.05em' }}>READING WIDTH</li>
                      {[
                        { code: 'centered', name: 'Centered (720px)' },
                        { code: 'wide', name: 'Wide (1080px)' },
                        { code: 'full', name: 'Full Width (100%)' }
                      ].map(widthOption => (
                        <li 
                          key={widthOption.code}
                          className={`dropdown-item ${readingWidth === widthOption.code ? 'active' : ''}`}
                          onClick={() => {
                            setReadingWidth(widthOption.code)
                            setShowFontDropdown(false)
                          }}
                        >
                          {widthOption.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Audio Capsule Dropdown */}
                <div className="custom-dropdown-container">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowAudioDropdown(!showAudioDropdown)
                      setShowTranslationDropdown(false)
                      setShowFontDropdown(false)
                      setShowOptionsDropdown(false)
                    }} 
                    className="capsule-btn audio-btn"
                  >
                    <span className="audio-icon">🔊</span>
                    <span className="chevron-v">v</span>
                  </button>
                  {showAudioDropdown && (
                    <ul className="custom-dropdown-menu audio-dropdown" onClick={(e) => e.stopPropagation()}>
                      <li className="dropdown-item" onClick={() => { alert("Audio Playback: Play"); setShowAudioDropdown(false); }}>▶ Play</li>
                      <li className="dropdown-item" onClick={() => { alert("Audio Playback: Pause"); setShowAudioDropdown(false); }}>⏸ Pause</li>
                      <li className="dropdown-item" onClick={() => { alert("Audio Playback: Speed 1.0x"); setShowAudioDropdown(false); }}>Speed: 1.0x</li>
                    </ul>
                  )}
                </div>

                {/* Options Capsule Dropdown */}
                <div className="custom-dropdown-container">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowOptionsDropdown(!showOptionsDropdown)
                      setShowTranslationDropdown(false)
                      setShowFontDropdown(false)
                      setShowAudioDropdown(false)
                    }} 
                    className="capsule-btn options-btn"
                  >
                    <span className="btn-text">...</span>
                  </button>
                  {showOptionsDropdown && (
                    <ul className="custom-dropdown-menu options-dropdown" onClick={(e) => e.stopPropagation()}>
                      <li className="dropdown-item" onClick={() => { handleExport(); setShowOptionsDropdown(false); }}>📤 Export Analysis</li>
                      <li className="dropdown-item" onClick={() => { handlePrint(); setShowOptionsDropdown(false); }}>🖨️ Print</li>
                    </ul>
                  )}
                </div>

                {/* Bookmark Ribbon Button */}
                <button 
                  onClick={() => handleToggleBookmark(`${selectedBook} ${selectedChapter}:${selectedVerse}`)} 
                  className={`bookmark-ribbon-btn ${bookmarkedVerses.includes(`${selectedBook} ${selectedChapter}:${selectedVerse}`) ? 'active' : ''}`}
                  title="Bookmark verse"
                >
                  <svg width="14" height="18" viewBox="0 0 16 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M1 18.5V1.5C1 1.22386 1.22386 1 1.5 1H14.5C14.7761 1 15 1.22386 15 1.5V18.5L8 14.5L1 18.5Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
                  </svg>
                </button>
              </div>
            </div>

            {/* Scripture Reader split body */}
            <div className="reader-body-split">
              {/* Left Ribbon vertical icon bar */}
              <div className="reader-vertical-bar">
                <button 
                  onClick={() => setShowRightSidebar(!showRightSidebar)} 
                  className="vbar-btn" 
                  title={showRightSidebar ? "Close Sidebar" : "Open Study Companion"}
                >
                  {showRightSidebar ? '✕' : '💡'}
                </button>
                <div className="vbar-btn-wrapper active">
                  <button onClick={(e) => handleNavClick('apocrypha', e)} className="vbar-btn" title="Home Study View">🏠</button>
                </div>
                <button onClick={focusSearch} className="vbar-btn" title="Linguistic Search">🔍</button>
                <button onClick={() => handleToggleHighlight(`${selectedBook} ${selectedChapter}:${selectedVerse}`)} className="vbar-btn" title="Highlighter">✏️</button>
                <button onClick={openNoteEditor} className="vbar-btn" title="Sticky Note">📝</button>
                <button onClick={() => { setShowRightSidebar(true); setRightSidebarTab('insights'); }} className="vbar-btn" title="Compare Versions">⇄</button>
                <button onClick={handleCopyText} className="vbar-btn" title="Copy Text">📋</button>
                <button onClick={() => handleShareVerse(selectedVerse)} className="vbar-btn" title="Share Verse">🔗</button>
                
                {/* Spacer to push controls to the bottom */}
                <div className="vbar-spacer" style={{ flexGrow: 1 }}></div>
                
                <button onClick={handleExport} className="vbar-btn" title="Publish / Export">⇡</button>
                <button onClick={(e) => handleNavClick('chat', e)} className="vbar-btn" title="AI Chat Assistant">💬</button>
              </div>

              {/* Scripture text content */}
              <div className={`scripture-text-area font-${fontSize}`}>
                {bookContentLoading ? (
                  <div className="reader-loading-spinner">
                    <div className="spinner"></div>
                    <p>Loading scriptures...</p>
                  </div>
                ) : currentChapterVerses.length === 0 ? (
                  <div className="canon-notice-card">
                    <div className="notice-icon">📜</div>
                    <h4>Canon-Aware Study Notice</h4>
                    <p>
                      This passage (<strong>{selectedBook} {selectedChapter}</strong>) appears in the Ethiopian Orthodox broader canon but may not appear in standard Protestant or Catholic canons. You can still study this text using available Orthodox or historical sources.
                    </p>
                    <div className="notice-actions">
                      <button className="notice-action-btn" onClick={() => setRightSidebarTab('notes')}>Open Study Notes</button>
                      <button className="notice-action-btn" onClick={() => handleToggleBookmark(`${selectedBook} ${selectedChapter}:1`)}>Bookmark Place</button>
                    </div>
                  </div>
                ) : (
                  <div className={`chapter-reading-flow width-${readingWidth}`}>
                    <div className="large-chapter-bg font-serif">{selectedChapter}</div>
                    
                    <div className="verses-column">
                      {currentChapterVerses.map((verse) => {
                        const verseRef = `${selectedBook} ${selectedChapter}:${verse.verse}`
                        const isSelected = selectedVerse.toString() === verse.verse.toString()
                        const isHighlighted = highlightedVerses.includes(verseRef)

                        return (
                          <div
                            key={verse.id}
                            className={`verse-row-container ${isSelected ? 'selected' : ''} ${isHighlighted ? 'highlighted' : ''} ${verse.is_omitted ? 'omitted-warning-row' : ''}`}
                            onClick={() => setSelectedVerse(selectedVerse === verse.verse.toString() ? '' : verse.verse.toString())}
                          >
                            <span className="verse-number-anchor font-serif">
                              {verse.verse}
                              {hasDecolonialAudit(selectedBook, selectedChapter, verse.verse) && (
                                <span className="decolonial-audit-indicator-icon" title="Decolonial Audit Available">⚖️</span>
                              )}
                            </span>
                            {verse.is_omitted ? (
                              <div className="omitted-verse-container">
                                <span className="omission-warning-tag">⚠️ Omitted in Western Translation</span>
                                <p className="omitted-baseline-text font-serif">"{verse.eth_text}"</p>
                              </div>
                            ) : (
                              <>
                                <span className="verse-text-content font-serif">
                                  {wrapWordsInSpans(verse.text || '', verse.verse)}
                                </span>
                                {activeTranslation.toUpperCase() !== 'ETH81' && (
                                  <div className="ethiopian-pinned-subpane">
                                    <span className="pinned-lbl">Ethiopian Reference:</span>
                                    <p className="pinned-text font-serif">"{verse.eth_text}"</p>
                                  </div>
                                )}
                              </>
                            )}

                            {/* Floating Verse Action Toolbar Capsule */}
                            {isSelected && (
                              <div className="floating-verse-toolbar">
                                <button 
                                  onClick={(e) => { e.stopPropagation(); handleToggleHighlight(verseRef); }} 
                                  className={`action-btn ${isHighlighted ? 'active' : ''}`} 
                                  title="Highlight"
                                >
                                  <span className="icon">✏️</span>
                                  <span className="label">Highlight</span>
                                </button>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); openNoteEditor(); }} 
                                  className="action-btn" 
                                  title="Note"
                                >
                                  <span className="icon">📄</span>
                                  <span className="label">Note</span>
                                </button>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); setRightSidebarTab('insights'); }} 
                                  className="action-btn" 
                                  title="Compare Translations"
                                >
                                  <span className="icon">⇄</span>
                                  <span className="label">Compare</span>
                                </button>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); handleCopySelectedVerse(verse.verse, verse.text); }} 
                                  className="action-btn" 
                                  title="Copy Text"
                                >
                                  <span className="icon">📋</span>
                                  <span className="label">Copy</span>
                                </button>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); handleShareVerse(verse.verse); }} 
                                  className="action-btn" 
                                  title="Share Verse"
                                >
                                  <span className="icon">🔗</span>
                                  <span className="label">Share</span>
                                </button>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); setRightSidebarTab('resources'); }}
                                  className="action-btn" 
                                  title="More Options"
                                >
                                  <span className="icon">⋯</span>
                                  <span className="label">More</span>
                                </button>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Chapter navigation */}
            {(() => {
              const prevPage = getPrevBookAndChapter()
              const nextPage = getNextBookAndChapter()
              
              return (
                <div className="reader-footer-nav">
                  <button 
                    onClick={() => {
                      if (prevPage) {
                        setSelectedBook(prevPage.book)
                        setSelectedChapter(prevPage.chapter)
                        setSelectedVerse('1')
                      }
                    }} 
                    disabled={!prevPage}
                    className="chapter-nav-btn font-serif"
                  >
                    {prevPage ? `< ${prevPage.book} ${prevPage.chapter}` : `< -- --`}
                  </button>
                  
                  <div className="chapter-nav-center font-serif font-bold">
                    <span className="grid-icon font-sans">㗊</span> {selectedBook} {selectedChapter}
                  </div>
                  
                  <button 
                    onClick={() => {
                      if (nextPage) {
                        setSelectedBook(nextPage.book)
                        setSelectedChapter(nextPage.chapter)
                        setSelectedVerse('1')
                      }
                    }} 
                    disabled={!nextPage}
                    className="chapter-nav-btn font-serif"
                  >
                    {nextPage ? `< ${nextPage.book} ${nextPage.chapter}` : `< -- --`}
                  </button>
                </div>
              )
            })()}
          </section>

          {/* 8. BOTTOM STUDY COMPANION PANEL */}
          <section ref={companionRef} className="bottom-study-companion">
            <div className="companion-tabs-row">
              <div className="companion-tabs">
                <button 
                  className={`companion-tab ${bottomTab === 'notes' ? 'active' : ''}`}
                  onClick={() => setBottomTab('notes')}
                >
                  My Notes
                </button>
                <button 
                  className={`companion-tab ${bottomTab === 'bookmarks' ? 'active' : ''}`}
                  onClick={() => setBottomTab('bookmarks')}
                >
                  Bookmarks ({bookmarkedVerses.length})
                </button>
                <button 
                  className={`companion-tab ${bottomTab === 'highlights' ? 'active' : ''}`}
                  onClick={() => setBottomTab('highlights')}
                >
                  Highlights ({highlightedVerses.length})
                </button>
                <button 
                  className={`companion-tab ${bottomTab === 'reading_plans' ? 'active' : ''}`}
                  onClick={() => setBottomTab('reading_plans')}
                >
                  📅 Reading Plans
                </button>
              </div>
              
              <a href="#viewallnotes" onClick={(e) => { e.preventDefault(); handleNavClick('notes', e); }} className="view-all-notes-link">
                View all notes ➔
              </a>
            </div>

            <div className="companion-content-split">
              {/* Left card with generated space Nebula background */}
              <div className="companion-promo-col">
                {bottomTab === 'reading_plans' ? (
                  <div className="promo-glass-card plans-sidebar-card">
                    <h4>Study Roadmaps</h4>
                    <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                      Select a structured plan to guide your canonical studies.
                    </p>
                    <div className="plan-buttons-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
                      {Object.values(readingPlans).map((plan) => {
                        const pctObj = Math.round((plan.completedDays.length / plan.days.length) * 100)
                        const isActive = activePlanId === plan.id
                        return (
                          <button
                            key={plan.id}
                            onClick={() => setActivePlanId(plan.id)}
                            className={`plan-select-btn ${isActive ? 'active' : ''}`}
                            style={{
                              display: 'flex',
                              flexDirection: 'column',
                              alignItems: 'flex-start',
                              padding: '8px 12px',
                              borderRadius: '8px',
                              border: isActive ? '1px solid var(--purple)' : '1px solid var(--border-soft)',
                              background: isActive ? 'rgba(139, 92, 246, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                              color: '#FFFFFF',
                              cursor: 'pointer',
                              textAlign: 'left',
                              transition: 'all 0.2s ease',
                              width: '100%'
                            }}
                          >
                            <span style={{ fontSize: '12px', fontWeight: '700' }}>{plan.name}</span>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                              {plan.booksCount} Books · {plan.duration} · {pctObj}% Done
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="promo-glass-card">
                    <h4>Your thoughts.<br/>Organized for insight.</h4>
                    <p>Capture, connect, and return to what matters.</p>
                    <button onClick={openNoteEditor} className="new-note-btn">
                      <span>✨ New Note</span> <span>+</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Right list cards container */}
              <div className="companion-items-col">
                {bottomTab === 'notes' && (
                  <div className="cards-grid">
                    {notesList.length === 0 ? (
                      <div className="empty-state">No notes recorded yet. Write one in the Notes tab!</div>
                    ) : (
                      notesList.map((note) => {
                        const noteDateStr = note.timestamp 
                          ? new Date(note.timestamp).toLocaleDateString(undefined, {month: 'short', day: 'numeric', year: 'numeric'}) 
                          : 'Today'
                        
                        return (
                          <div key={note.id} className="note-row-item">
                            <div className="note-row-left">
                              <h4 className="note-row-title">{note.title || `Reflection on ${note.book}`}</h4>
                              <p className="note-row-preview">{note.text}</p>
                            </div>
                            <div className="note-row-right">
                              <span className="scripture-badge">
                                {note.book} {note.chapter}:{note.verse}
                              </span>
                              <span className="note-row-date">
                                {note.timestamp && note.timestamp.includes('2026-06-17') 
                                  ? 'Today' 
                                  : note.timestamp && note.timestamp.includes('2026-06-16') 
                                    ? 'Yesterday' 
                                    : noteDateStr}
                              </span>
                              <button className={`note-star-btn ${note.starred ? 'starred' : ''}`} title="Favorite">★</button>
                              <button onClick={(e) => handleDeleteNote(note.id, e)} className="note-row-delete-btn" title="Delete note">🗑</button>
                            </div>
                          </div>
                        )
                      })
                    )}
                  </div>
                )}

                {bottomTab === 'bookmarks' && (
                  <div className="cards-grid">
                    {bookmarkedVerses.length === 0 ? (
                      <div className="empty-state">No verses bookmarked in this study session.</div>
                    ) : (
                      bookmarkedVerses.map((bookmark) => {
                        const [bBook, chVerse] = bookmark.split(/(?=\d)/)
                        const [bCh, bVer] = chVerse ? chVerse.split(':') : ['1', '1']
                        
                        return (
                          <div 
                            key={bookmark} 
                            onClick={() => {
                              setSelectedBook(bBook.trim())
                              setSelectedChapter(bCh.trim())
                              setSelectedVerse(bVer.trim())
                            }}
                            className="bookmark-glass-card cursor-pointer hover-glow"
                          >
                            <div className="bookmark-header">
                              <span className="scripture-badge">{bookmark}</span>
                              <span className="bookmark-nav-icon">➔</span>
                            </div>
                            <p className="bookmark-preview">Jump directly to {bookmark} in the scripture reading flow.</p>
                          </div>
                        )
                      })
                    )}
                  </div>
                )}

                {bottomTab === 'highlights' && (
                  <div className="cards-grid">
                    {highlightedVerses.length === 0 ? (
                      <div className="empty-state">No highlighted verses. Select any verse in the reader to highlight it.</div>
                    ) : (
                      highlightedVerses.map((highlight) => {
                        const [hBook, chVerse] = highlight.split(/(?=\d)/)
                        const [hCh, hVer] = chVerse ? chVerse.split(':') : ['1', '1']
                        
                        return (
                          <div 
                            key={highlight} 
                            onClick={() => {
                              setSelectedBook(hBook.trim())
                              setSelectedChapter(hCh.trim())
                              setSelectedVerse(hVer.trim())
                            }}
                            className="highlight-glass-card cursor-pointer hover-glow"
                          >
                            <div className="highlight-header">
                              <span className="scripture-badge highlight-purple">{highlight}</span>
                              <span className="bookmark-nav-icon">➔</span>
                            </div>
                            <p className="bookmark-preview">Jump to highlighted text in the scripture reading flow.</p>
                          </div>
                        )
                      })
                    )}
                  </div>
                )}

                {bottomTab === 'reading_plans' && (
                  <div className="plans-main-view" style={{ display: 'flex', flexDirection: 'column', gap: '14px', width: '100%', height: '100%' }}>
                    {(() => {
                      const activePlan = readingPlans[activePlanId]
                      const totalDays = activePlan.days.length
                      const completedCount = activePlan.completedDays.length
                      const pct = totalDays > 0 ? Math.round((completedCount / totalDays) * 100) : 0
                      
                      return (
                        <>
                          <div className="plan-progress-header" style={{
                            display: 'flex', 
                            flexDirection: 'column', 
                            gap: '6px', 
                            background: 'rgba(255,255,255,0.02)', 
                            border: '1px solid var(--border-soft)',
                            padding: '12px 16px',
                            borderRadius: '10px'
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div>
                                <h3 style={{ margin: 0, fontSize: '15px', color: '#FFFFFF', fontWeight: '700' }}>{activePlan.name}</h3>
                                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{activePlan.tagline}</span>
                              </div>
                              <span style={{ fontSize: '16px', fontWeight: '700', color: '#06FFA5' }}>{pct}% Complete</span>
                            </div>
                            <div className="plan-progress-bar-container" style={{
                              height: '6px',
                              backgroundColor: 'rgba(255,255,255,0.06)',
                              borderRadius: '3px',
                              overflow: 'hidden',
                              marginTop: '4px',
                              position: 'relative'
                            }}>
                              <div style={{
                                width: `${pct}%`,
                                height: '100%',
                                background: 'linear-gradient(90deg, #8B5CF6, #06FFA5)',
                                borderRadius: '3px',
                                transition: 'width 0.3s ease'
                              }}></div>
                            </div>
                          </div>
                          
                          <div className="plan-days-grid" style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                            gap: '10px',
                            overflowY: 'auto',
                            maxHeight: '260px',
                            paddingRight: '4px'
                          }}>
                            {activePlan.days.map((day) => {
                              const isCompleted = activePlan.completedDays.includes(day.day)
                              return (
                                <div
                                  key={day.day}
                                  onClick={() => {
                                    setSelectedBook(day.book)
                                    setSelectedChapter(day.chapter)
                                    setSelectedVerse('1')
                                  }}
                                  className={`plan-day-card ${isCompleted ? 'completed' : ''}`}
                                  style={{
                                    border: isCompleted ? '1px solid rgba(6, 255, 165, 0.25)' : '1px solid var(--border-soft)',
                                    background: isCompleted ? 'rgba(6, 255, 165, 0.04)' : 'rgba(255,255,255,0.01)',
                                    borderRadius: '8px',
                                    padding: '10px 12px',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '6px',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease',
                                    position: 'relative'
                                  }}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontSize: '10px', fontWeight: '700', color: isCompleted ? '#06FFA5' : '#8B5CF6', textTransform: 'uppercase' }}>
                                      Day {day.day}
                                    </span>
                                    <input
                                      type="checkbox"
                                      checked={isCompleted}
                                      onChange={(e) => {
                                        e.stopPropagation();
                                        setReadingPlans(prev => {
                                          const plan = prev[activePlanId]
                                          const nextCompleted = isCompleted 
                                            ? plan.completedDays.filter(d => d !== day.day)
                                            : [...plan.completedDays, day.day]
                                          return {
                                            ...prev,
                                            [activePlanId]: {
                                              ...plan,
                                              completedDays: nextCompleted
                                            }
                                          }
                                        })
                                      }}
                                      style={{
                                        cursor: 'pointer',
                                        width: '14px',
                                        height: '14px',
                                        accentColor: '#06FFA5'
                                      }}
                                    />
                                  </div>
                                  <h4 style={{ margin: 0, fontSize: '12px', color: '#FFFFFF', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {day.title}
                                  </h4>
                                  <span className="scripture-badge" style={{ alignSelf: 'flex-start', fontSize: '9px', padding: '2px 6px' }}>
                                    {day.readings}
                                  </span>
                                </div>
                              )
                            })}
                          </div>
                        </>
                      )
                    })()}
                  </div>
                )}
              </div>
            </div>
          </section>
        </main>

        {/* 7. RIGHT SIDEBAR — INSIGHTS & AI */}
        {showRightSidebar && (
          <aside className="right-sidebar">
            
            {/* Tab Headers */}
            <div className="sidebar-tabs-row">
              <button 
                className={`sidebar-tab ${rightSidebarTab === 'insights' ? 'active' : ''}`}
                onClick={() => setRightSidebarTab('insights')}
              >
                Decolonial Audit
              </button>
              <button 
                className={`sidebar-tab ${rightSidebarTab === 'resources' ? 'active' : ''}`}
                onClick={() => setRightSidebarTab('resources')}
              >
                Resources
              </button>
              <button 
                className={`sidebar-tab ${rightSidebarTab === 'notes' ? 'active' : ''}`}
                onClick={() => setRightSidebarTab('notes')}
              >
                Notes
              </button>
            </div>

            <div className="sidebar-scrollable-content">
              
              {/* TAB 1: INSIGHTS */}
              {rightSidebarTab === 'insights' && (
                <div className="insights-tab-content">
                  
                  {/* Key Insights Card */}
                  <div className="sidebar-glass-card">
                    <div className="card-top-row">
                      <span className="card-lbl-title">Key Insights</span>
                      <span className="badge-ai-stars">AI</span>
                    </div>
                    {detailsLoading ? (
                      <div className="insight-loading">Loading insights...</div>
                    ) : verseDetails ? (
                      <div>
                        <p className="insight-text-detail">{verseDetails.verse_meaning}</p>
                        {verseDetails.critical_analysis && (
                          <div className="critical-analysis-block">
                            <span className="analysis-lbl">Critical Scholarly Notes</span>
                            <p className="analysis-txt">{verseDetails.critical_analysis}</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="insight-text-detail">Themes of faith, covenant, and historical context shape the narrative of {selectedBook} {selectedChapter}.</p>
                    )}
                  </div>

                  {/* Decolonial Scripture Misuse Audits */}
                  {verseDetails && verseDetails.race_misuse_records && verseDetails.race_misuse_records.length > 0 && (
                    <div className="sidebar-glass-card scripture-misuse-warning-card">
                      <div className="card-top-row">
                        <span className="card-lbl-title status-misuse">Decolonial Audit Alert</span>
                        <span className="warning-blinking-dot"></span>
                      </div>
                      {verseDetails.race_misuse_records.map((r, idx) => (
                        <div key={idx} className="misuse-audit-detail">
                          <span className={`severity-badge ${r.severity}`}>{r.severity.toUpperCase()} MISUSE REPORT</span>
                          <h5>{r.title}</h5>
                          <div className="audit-section-p">
                            <strong>Historical Misuse:</strong>
                            <p>{r.historical_misuse}</p>
                          </div>
                          <div className="audit-section-p">
                            <strong>Decolonial Corrective:</strong>
                            <p className="corrective-highlight">{r.corrective_interpretation}</p>
                          </div>
                          {r.ethiopian_perspective && (
                            <div className="audit-section-p">
                              <strong>Ethiopian Orthodox:</strong>
                              <p>{r.ethiopian_perspective}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Translation Bias Warnings */}
                  {verseDetails && verseDetails.translation_bias_alerts && verseDetails.translation_bias_alerts.length > 0 && (
                    <div className="sidebar-glass-card translation-bias-warning-card">
                      <div className="card-top-row">
                        <span className="card-lbl-title status-bias">Translation Bias Detected</span>
                        <span className="bias-icon">⚠️</span>
                      </div>
                      {verseDetails.translation_bias_alerts.map((bias, idx) => (
                        <div key={idx} className="bias-audit-detail">
                          <h5>{bias.title}</h5>
                          <p><strong>Original Root:</strong> <code>{bias.original}</code> ({bias.literal})</p>
                          <p><strong>Western Target:</strong> <code>{bias.target_text}</code> ({bias.target_translation})</p>
                          <p className="bias-explanation-p">{bias.explanation}</p>
                          <p className="bias-scholar-p"><em>Scholar: {bias.scholar}</em></p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Related Passages Card */}
                  <div className="sidebar-glass-card">
                    <div className="card-top-row">
                      <span className="card-lbl-title">Related Passages</span>
                      <a href="#viewall" onClick={(e) => { e.preventDefault(); setRightSidebarTab('resources'); }} className="view-all-link">View all ➔</a>
                    </div>
                    
                    <div className="related-references-list">
                      {verseDetails && verseDetails.cross_references && verseDetails.cross_references.length > 0 ? (
                        verseDetails.cross_references.slice(0, 3).map((ref, idx) => (
                          <div 
                            key={idx} 
                            onClick={() => {
                              setSelectedBook(ref.book)
                              setSelectedChapter(ref.chapter.toString())
                              setSelectedVerse(ref.verse.toString())
                            }}
                            className="reference-item-link cursor-pointer"
                          >
                            <span className="ref-tag font-serif">{ref.book} {ref.chapter}:{ref.verse}</span>
                            <p className="ref-preview font-serif">"{ref.text}"</p>
                          </div>
                        ))
                      ) : (
                        <>
                          <div className="reference-item-link">
                            <span className="ref-tag">Genesis 37:5–10</span>
                            <p className="ref-preview">Dreams and rising influence.</p>
                          </div>
                          <div className="reference-item-link">
                            <span className="ref-tag">Deuteronomy 10:22</span>
                            <p className="ref-preview">God remembers His people.</p>
                          </div>
                          <div className="reference-item-link">
                            <span className="ref-tag">Psalm 105:24–25</span>
                            <p className="ref-preview">God multiplied His people.</p>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Word Study Card */}
                  <div className="sidebar-glass-card word-study-card">
                    <div className="card-top-row">
                      <span className="card-lbl-title">Word Study</span>
                      <span className="badge-ai-stars font-semibold">AI</span>
                    </div>

                    {selectedWordStudy ? (
                      <div className="word-details-container">
                        <div className="original-term-row">
                          <span className="hebrew-term font-serif">
                            {selectedWordStudy.original_name || selectedWordStudy.original_text || selectedWordStudy.word}
                          </span>
                          <span className="term-translit">
                            ({selectedWordStudy.transliteration || selectedWordStudy.language || (selectedWordStudy.type === 'Bias Alert' ? 'Bias Alert' : '')})
                          </span>
                        </div>
                        
                        <span className="strongs-number">
                          {selectedWordStudy.type === 'Bias Alert' 
                            ? `Bias Alert · ${selectedWordStudy.title}`
                            : `Strong's ${selectedWordStudy.strong_number || 'N/A'} · ${selectedWordStudy.part_of_speech || 'Linguistic'} · ${selectedWordStudy.language || 'Original'}`
                          }
                        </span>

                        <div className="word-study-tab-chips">
                          <span 
                            className={`word-tab ${wordStudyTab === 'usage' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('usage')}
                          >
                            Usage
                          </span>
                          <span 
                            className={`word-tab ${wordStudyTab === 'forms' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('forms')}
                          >
                            Forms
                          </span>
                          <span 
                            className={`word-tab ${wordStudyTab === 'root' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('root')}
                          >
                            Root
                          </span>
                          <span 
                            className={`word-tab ${wordStudyTab === 'lexicon' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('lexicon')}
                          >
                            Lexicon
                          </span>
                        </div>

                        {wordStudyTab === 'usage' && (
                          <p className="word-definition-text">
                            {selectedWordStudy.type === 'Bias Alert' 
                              ? selectedWordStudy.note 
                              : (selectedWordStudy.meaning || selectedWordStudy.detailed_definition || `Definition for "${selectedWordStudy.word}" not available.`)
                            }
                          </p>
                        )}

                        {wordStudyTab === 'forms' && (
                          <p className="word-definition-text">
                            <strong>Part of Speech:</strong> {selectedWordStudy.part_of_speech || 'Linguistic Entry'}<br />
                            <strong>Language:</strong> {selectedWordStudy.language || 'Original Language'}<br />
                            {selectedWordStudy.type === 'Bias Alert' && (
                              <>
                                <strong>Severity:</strong> High Bias Alert Warning<br />
                              </>
                            )}
                          </p>
                        )}

                        {wordStudyTab === 'root' && (
                          <p className="word-definition-text">
                            <strong>Root Word / Origin:</strong> {selectedWordStudy.root || 'Derived directly from original context.'}<br />
                            <strong>Reference Key:</strong> {selectedWordStudy.strong_number ? `Strong's ${selectedWordStudy.strong_number}` : 'N/A'}
                          </p>
                        )}

                        {wordStudyTab === 'lexicon' && (
                          <p className="word-definition-text">
                            {selectedWordStudy.detailed_definition || selectedWordStudy.meaning || selectedWordStudy.note || 'No detailed lexicon entry available.'}
                          </p>
                        )}
                        
                        {selectedWordStudy.literal_translation && (
                          <div style={{ marginTop: '8px', fontSize: '11px', color: '#06FFA5' }}>
                            <strong>Literal Translation:</strong> {selectedWordStudy.literal_translation}
                          </div>
                        )}
                        
                        {selectedWordStudy.occurrence_count && (
                          <span className="word-occurrence-info">
                            Occurs {selectedWordStudy.occurrence_count} times.
                          </span>
                        )}
                      </div>
                    ) : verseDetails && verseDetails.original_language_insights && verseDetails.original_language_insights.length > 0 ? (
                      verseDetails.original_language_insights.map((wordInfo, idx) => (
                        <div key={idx} className="word-details-container">
                          <div className="original-term-row">
                            <span className="hebrew-term font-serif">{wordInfo.text}</span>
                            <span className="term-translit">({wordInfo.transliteration || wordInfo.language})</span>
                          </div>
                          <span className="strongs-number">
                            Strong's {wordInfo.strong_number || 'N/A'} · {wordInfo.language || 'Hebrew'} · Insight
                          </span>
                          
                          <div className="word-study-tab-chips">
                            <span 
                              className={`word-tab ${wordStudyTab === 'usage' ? 'active' : ''}`}
                              onClick={() => setWordStudyTab('usage')}
                            >
                              Usage
                            </span>
                            <span 
                              className={`word-tab ${wordStudyTab === 'forms' ? 'active' : ''}`}
                              onClick={() => setWordStudyTab('forms')}
                            >
                              Forms
                            </span>
                            <span 
                              className={`word-tab ${wordStudyTab === 'root' ? 'active' : ''}`}
                              onClick={() => setWordStudyTab('root')}
                            >
                              Root
                            </span>
                            <span 
                              className={`word-tab ${wordStudyTab === 'lexicon' ? 'active' : ''}`}
                              onClick={() => setWordStudyTab('lexicon')}
                            >
                              Lexicon
                            </span>
                          </div>

                          {wordStudyTab === 'usage' && (
                            <p className="word-definition-text">
                              {wordInfo.definition}
                            </p>
                          )}

                          {wordStudyTab === 'forms' && (
                            <p className="word-definition-text">
                              <strong>Language:</strong> {wordInfo.language || 'Hebrew'}<br />
                              <strong>Translation Key:</strong> {wordInfo.strong_number || 'N/A'}
                            </p>
                          )}

                          {wordStudyTab === 'root' && (
                            <p className="word-definition-text">
                              <strong>Root:</strong> {wordInfo.root || 'Derived directly from text.'}
                            </p>
                          )}

                          {wordStudyTab === 'lexicon' && (
                            <p className="word-definition-text">
                              {wordInfo.definition}
                            </p>
                          )}
                          
                          {wordInfo.occurrence_count && (
                            <span className="word-occurrence-info">
                              Occurs {wordInfo.occurrence_count} times.
                            </span>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="word-details-container">
                        <div className="original-term-row">
                          <span className="hebrew-term font-serif">רָבָה</span>
                          <span className="term-translit">(rabbâ)</span>
                        </div>
                        <span className="strongs-number">Strong’s H7235 · Verb (Qal) · to increase, multiply</span>
                        
                        <div className="word-study-tab-chips">
                          <span 
                            className={`word-tab ${wordStudyTab === 'usage' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('usage')}
                          >
                            Usage
                          </span>
                          <span 
                            className={`word-tab ${wordStudyTab === 'forms' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('forms')}
                          >
                            Forms
                          </span>
                          <span 
                            className={`word-tab ${wordStudyTab === 'root' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('root')}
                          >
                            Root
                          </span>
                          <span 
                            className={`word-tab ${wordStudyTab === 'lexicon' ? 'active' : ''}`}
                            onClick={() => setWordStudyTab('lexicon')}
                          >
                            Lexicon
                          </span>
                        </div>
                        
                        {wordStudyTab === 'usage' && (
                          <p className="word-definition-text">
                            To increase in number, to grow, to be many.
                          </p>
                        )}

                        {wordStudyTab === 'forms' && (
                          <p className="word-definition-text">
                            <strong>Part of Speech:</strong> Verb (Qal)<br />
                            <strong>Language:</strong> Hebrew
                          </p>
                        )}

                        {wordStudyTab === 'root' && (
                          <p className="word-definition-text">
                            <strong>Root:</strong> רָבָה (rabbâ)
                          </p>
                        )}

                        {wordStudyTab === 'lexicon' && (
                          <p className="word-definition-text">
                            To increase in number, to grow, to be many, multiply.
                          </p>
                        )}
                        
                        <span className="word-occurrence-info">Occurs 23 times in OT.</span>
                      </div>
                    )}
                  </div>

                  {/* AI Study Assistant Card */}
                  <div className="sidebar-glass-card ai-assistant-card">
                    <div className="card-top-row flex justify-between items-center">
                      <span className="card-lbl-title">AI Study Assistant</span>
                      <select 
                        value={aiStudyMode} 
                        onChange={(e) => {
                          setAiStudyMode(e.target.value);
                          setSuggestedFollowUps([]); // Reset dynamic suggestions on mode switch
                        }} 
                        className="ai-mode-selector-dropdown"
                      >
                        <option value="scholarly">🎓 Scholarly</option>
                        <option value="kids">👶 Kids Mode</option>
                        <option value="devotional">📖 Devotional</option>
                        <option value="sermon">🎙️ Sermon Outline</option>
                        <option value="discussion">💬 Discussion Qs</option>
                      </select>
                    </div>

                    <div className="ai-chat-thread">
                      {aiMessages.map((msg, index) => (
                        <div key={index} className={`chat-bubble-row ${msg.type}`}>
                          <div className="chat-avatar">{msg.type === 'user' ? '👤' : '🤖'}</div>
                          <div className="chat-content">
                            <div className="chat-content-text" style={{ whiteSpace: 'pre-line' }}>
                              {msg.content}
                            </div>
                            {msg.type === 'assistant' && (
                              <div className="chat-message-actions-row">
                                <button 
                                  type="button" 
                                  onClick={() => {
                                    navigator.clipboard.writeText(msg.content);
                                    setCopiedIndex(index);
                                    setTimeout(() => setCopiedIndex(null), 2000);
                                  }}
                                  className="chat-action-btn"
                                  title="Copy insight to clipboard"
                                >
                                  {copiedIndex === index ? "✅ Copied!" : "📋 Copy"}
                                </button>
                                <button 
                                  type="button" 
                                  onClick={() => {
                                    const simulatedLink = `${window.location.origin}/share/insight/${Math.random().toString(36).substring(7)}`;
                                    navigator.clipboard.writeText(`Check out this Bible Study insight: "${msg.content.substring(0, 100)}..." Shared from The Unbound Bible: ${simulatedLink}`);
                                    setCopiedIndex(`share-${index}`);
                                    setTimeout(() => setCopiedIndex(null), 2000);
                                  }}
                                  className="chat-action-btn"
                                  title="Share study link"
                                >
                                  {copiedIndex === `share-${index}` ? "🔗 Link Copied!" : "🔗 Share"}
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                      {aiLoading && (
                        <div className="chat-bubble-row assistant">
                          <div className="chat-avatar">🤖</div>
                          <div className="chat-content typing">Thinking...</div>
                        </div>
                      )}
                      <div ref={chatEndRef}></div>
                    </div>

                    <form onSubmit={handleAISubmit} className="chat-input-form-control">
                      <input 
                        type="text" 
                        placeholder="Ask anything about this passage..." 
                        value={aiInputValue}
                        onChange={(e) => setAIInputValue(e.target.value)}
                        className="chat-field"
                        disabled={aiLoading}
                      />
                      <button type="submit" className="chat-send-btn-icon" disabled={aiLoading || !aiInputValue.trim()}>
                        ➔
                      </button>
                    </form>

                    <div className="chat-question-chips">
                      {(suggestedFollowUps.length > 0 
                        ? suggestedFollowUps 
                        : getPreviewQuestions(selectedBook, selectedChapter, selectedVerse)
                      ).map((qText, index) => (
                        <button 
                          key={index}
                          onClick={() => sendAIChatMessage(qText)}
                          className="question-chip"
                        >
                          {qText}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Quick Summary Card */}
                  <div className="sidebar-glass-card">
                    <div className="card-top-row">
                      <span className="card-lbl-title">Quick Summary</span>
                      <span className="badge-ai-stars">AI</span>
                    </div>
                    {detailsLoading ? (
                      <div className="insight-loading">Loading summary...</div>
                    ) : verseDetails ? (
                      <p className="insight-text-detail">{verseDetails.translation_comparison}</p>
                    ) : (
                      <p className="insight-text-detail">{selectedBook} {selectedChapter} introduces the biblical narrative for this passage. Select a verse or click the audit button to generate deeper contextual analysis.</p>
                    )}
                    
                  {mythBusterLoading ? (
                    <div className="summary-generating">Auditing scripture context...</div>
                  ) : mythBusterContent ? (
                    <div className="myth-buster-result-embed">
                      <h5>🛡️ Context Audit Result</h5>
                      <p><strong>Myth:</strong> {mythBusterContent.myth_title}</p>
                      <p>{mythBusterContent.myth_content}</p>
                      <p className="highlight-text"><strong>Scholar Fact:</strong> {mythBusterContent.historical_facts}</p>
                    </div>
                  ) : (
                    <button onClick={handleMythBusterClick} className="deeper-summary-btn">
                      Generate Deeper Summary ➔
                    </button>
                  )}
                    {mythBusterError && <p className="myth-error-txt">{mythBusterError}</p>}
                  </div>
                </div>
              )}

              {/* TAB 2: RESOURCES */}
              {rightSidebarTab === 'resources' && (
                <div className="resources-tab-content">
                  
                  {/* Related Passages Card (Detailed) */}
                  <div className="sidebar-glass-card">
                    <span className="card-lbl-title">Cross References</span>
                    <div className="related-references-list">
                      {verseDetails && verseDetails.cross_references && verseDetails.cross_references.length > 0 ? (
                        verseDetails.cross_references.map((ref, idx) => (
                          <div 
                            key={idx} 
                            onClick={() => {
                              setSelectedBook(ref.book)
                              setSelectedChapter(ref.chapter.toString())
                              setSelectedVerse(ref.verse.toString())
                            }}
                            className="reference-item-link cursor-pointer"
                          >
                            <span className="ref-tag font-serif">{ref.book} {ref.chapter}:{ref.verse}</span>
                            <p className="ref-preview font-serif">"{ref.text}"</p>
                          </div>
                        ))
                      ) : (
                        <div className="empty-state">No cross references loaded.</div>
                      )}
                    </div>
                  </div>

                  {/* Translation Bias Card */}
                  <div className="sidebar-glass-card translation-bias-warnings">
                    <div className="card-top-row">
                      <span className="card-lbl-title">Translation Bias Alert</span>
                      <span className="badge-severity-note">ℹ️ Note</span>
                    </div>

                    {(() => {
                      const biasAlertsToRender = (verseDetails && verseDetails.translation_bias_alerts && verseDetails.translation_bias_alerts.length > 0)
                        ? verseDetails.translation_bias_alerts
                        : getBiasAlerts()
                      
                      return biasAlertsToRender.map((alert, i) => {
                        const targetLabel = alert.target_translation || 'KJV'
                        const targetText = alert.kjv || alert.target_text
                        
                        return (
                          <div key={i} className={`bias-card-alert bias-${alert.severity}`}>
                            <strong className="bias-alert-title">{alert.title}</strong>
                            
                            {alert.original && (
                              <div className="bias-alert-row">
                                <span className="label">Original:</span>
                                <span className="value text-gold font-serif">{alert.original}</span>
                              </div>
                            )}
                            {alert.literal && (
                              <div className="bias-alert-row">
                                <span className="label">Literal:</span>
                                <span className="value text-teal font-serif">{alert.literal}</span>
                              </div>
                            )}
                            {targetText && (
                              <div className="bias-alert-row">
                                <span className="label">{targetLabel}:</span>
                                <span className="value text-danger font-serif">{targetText}</span>
                              </div>
                            )}
                            
                            <p className="bias-alert-explanation">{alert.explanation}</p>
                            {alert.scholar && (
                              <div className="scholar-quote-row font-serif">
                                🎓 <em>{alert.scholar}</em>
                              </div>
                            )}
                          </div>
                        )
                      })
                    })()}
                  </div>
                </div>
              )}

              {/* TAB 3: NOTES */}
              {rightSidebarTab === 'notes' && (
                <div className="notes-tab-content">
                  
                  {/* Note Editor Card */}
                  <div className="sidebar-glass-card">
                    <span className="card-lbl-title">Write Verse Note</span>
                    <div className="active-verse-tag">
                      Active Verse: <span className="scripture-badge">{selectedBook} {selectedChapter}:{selectedVerse}</span>
                    </div>
                    
                    <textarea 
                      ref={noteInputRef}
                      placeholder="Capture insights, personal reflections, sermon draft thoughts..."
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      className="note-textarea-control"
                    />
                    
                    <button onClick={handleSaveNote} className="note-save-action-btn">
                      Save Note to Study Companion
                    </button>
                  </div>

                  {/* Notes list for active verse */}
                  <div className="active-verse-notes-section">
                    <h4 className="notes-list-title">Notes for this Verse</h4>
                    {notesList.filter(n => n.book === selectedBook && n.chapter === parseInt(selectedChapter) && n.verse === parseInt(selectedVerse)).length === 0 ? (
                      <div className="empty-verse-notes-state">No notes written for this verse yet.</div>
                    ) : (
                      notesList
                        .filter(n => n.book === selectedBook && n.chapter === parseInt(selectedChapter) && n.verse === parseInt(selectedVerse))
                        .map((note) => (
                          <div key={note.id} className="small-note-card">
                            <span className="note-date">
                              {note.timestamp ? new Date(note.timestamp).toLocaleDateString() : 'Today'}
                            </span>
                            <p className="small-note-text">{note.text}</p>
                            <button onClick={(e) => handleDeleteNote(note.id, e)} className="note-card-delete-icon">🗑</button>
                          </div>
                        ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* 9. WORD CONTEXT POPUPS (preserved from original) */}
      {showWordPopup && selectedWord && (
        <WordContextPopover
          word={selectedWord}
          position={popupPosition}
          onClose={() => setShowWordPopup(false)}
          contextData={wordContextData}
          loading={wordContextLoading}
        />
      )}

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

export default AncientTexts
