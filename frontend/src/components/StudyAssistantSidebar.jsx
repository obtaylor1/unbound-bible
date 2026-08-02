import { useState, useEffect, useRef } from 'react'
import './StudyAssistantSidebar.css'
import ShareStudyModal from './ShareStudyModal'
import { api } from '../api/client'
import { useAuth } from '../auth/authContext'
import { askStudyQuestion } from '../services/studyApi'

function StudyAssistantSidebar({ 
  book = 'Genesis', 
  chapter = 1, 
  verse = 1, 
  onClose,
  onAddNote, // Callback to add note to verse
  initialTab = 'insights',
  initialInsightSubTab = 'crossrefs',
}) {
  const { status: authStatus } = useAuth()
  const [activeTab, setActiveTab] = useState(initialTab) // 'insights' or 'chat'
  const [activeInsightSubTab, setActiveInsightSubTab] = useState(initialInsightSubTab) // crossrefs, commentary, lexicon, canon
  const [verseDetails, setVerseDetails] = useState(null)
  const [loading, setLoading] = useState(false)
  const [noteText, setNoteText] = useState('')
  const [notesList, setNotesList] = useState([])
  const [selectedWord, setSelectedWord] = useState(null)

  // Chat states
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [showShareModal, setShowShareModal] = useState(false)
  const [shareData, setShareData] = useState(null)
  const [studyId, setStudyId] = useState(null)

  const chatEndRef = useRef(null)

  useEffect(() => {
    setActiveTab(initialTab)
    setActiveInsightSubTab(initialInsightSubTab)
  }, [initialInsightSubTab, initialTab])

  // Fetch verse details on coordinate change
  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true)
      try {
        const response = await fetch(`/api/v1/texts/${encodeURIComponent(book)}/${chapter}/${verse}/details`)
        if (response.ok) {
          const data = await response.json()
          setVerseDetails(data)
        } else {
          setVerseDetails(null)
        }
      } catch (err) {
        console.error("Failed to fetch verse details in sidebar:", err)
        setVerseDetails(null)
      } finally {
        setLoading(false)
      }
    }
    fetchDetails()
    
    // Fetch and sync notes for this verse
    const loadNotes = async () => {
      const reference = `${book} ${chapter}:${verse}`
      if (authStatus === 'authenticated') {
        try {
          const remote = await api.get('/notes')
          setNotesList(remote.filter((note) => note.passage_reference === reference))
          return
        } catch (err) { console.error('Failed to load private notes:', err) }
      }
      try {
        const local = JSON.parse(localStorage.getItem('unbound_notes') || '[]')
        setNotesList(local.filter((note) => note.passage_reference === reference || (note.book === book && Number(note.chapter) === Number(chapter) && Number(note.verse) === Number(verse))))
      } catch { setNotesList([]) }
    }
    loadNotes()

    // Reset chat messages when verse changes to keep context-relevant
    setChatMessages([
      {
        id: 'welcome',
        type: 'ai',
        content: `I am your study assistant for **${book} ${chapter}:${verse}**. Ask me about the translation differences, historical context, or theological themes of this verse, or select a quick study outline below.`,
        sources: [],
        timestamp: new Date()
      }
    ])
  }, [book, chapter, verse, authStatus])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, chatLoading])

  // Save notes to database with localStorage fallback
  const handleSaveNote = async () => {
    if (!noteText.trim()) return
    
    const notePayload = { passage_reference: `${book} ${chapter}:${verse}`, content: noteText }

    try {
      if (authStatus === 'authenticated') {
        const savedNote = await api.post('/notes', notePayload)
        setNotesList(prev => [...prev, savedNote])
        setNoteText('')
        if (onAddNote) onAddNote(savedNote)
        return
      }
      throw new Error('Guest note')
    } catch (err) {
      if (authStatus === 'authenticated') console.error("Failed to save note to API, keeping a local copy:", err)
      const fallbackNote = {
        id: 'note_' + Date.now(),
        ...notePayload, text: noteText, book, chapter: Number(chapter), verse: Number(verse),
        timestamp: new Date().toISOString()
      }
      const saved = localStorage.getItem('unbound_notes')
      const allNotes = saved ? JSON.parse(saved) : []
      allNotes.push(fallbackNote)
      localStorage.setItem('unbound_notes', JSON.stringify(allNotes))
      
      setNotesList(prev => [...prev, fallbackNote])
      setNoteText('')
      if (onAddNote) onAddNote(fallbackNote)
    }
  }

  // Handle Quick Prompts
  const handleQuickPrompt = async (promptType, label) => {
    let question = ''
    if (promptType === 'outline') {
      question = `Generate a study outline for ${book} ${chapter}:${verse}.`
    } else if (promptType === 'teen') {
      question = `How would you explain the meaning of ${book} ${chapter}:${verse} to a teenager?`
    } else if (promptType === 'child') {
      question = `Explain ${book} ${chapter}:${verse} to a 7-year old in very simple terms.`
    } else if (promptType === 'history') {
      question = `What is the historical and cultural background of ${book} ${chapter}:${verse}?`
    }

    sendChatMessage(question, label)
  }

  // Send AI Chat Message
  const sendChatMessage = async (text, overrideLabel) => {
    const q = text.trim()
    if (!q) return

    const userMsg = {
      id: 'msg_' + Date.now(),
      type: 'user',
      content: overrideLabel || q,
      timestamp: new Date()
    }

    setChatMessages(prev => [...prev, userMsg])
    setChatInput('')
    setChatLoading(true)
    setActiveTab('chat')

    try {
      const result = await askStudyQuestion(`${q} (Context: ${book} ${chapter}:${verse})`)
      setChatMessages(prev => [...prev, { id: 'ai_' + Date.now(), type: 'ai', content: result.answer, sources: result.sources, followUps: result.followUps, provenance: result.provenance, timestamp: new Date() }])
    } catch (err) {
      console.error(err)
      setChatMessages(prev => [...prev, {
        id: 'err_' + Date.now(),
        type: 'error',
        content: "I couldn't generate a response. Please check your connection or try another query.",
        timestamp: new Date()
      }])
    } finally {
      setChatLoading(false)
    }
  }

  // Save full conversation session
  const handleSaveSession = () => {
    if (chatMessages.length <= 1) return
    const session = {
      id: 'session_' + Date.now(),
      title: `Study Session: ${book} ${chapter}:${verse}`,
      type: 'chat',
      date: new Date().toLocaleDateString(),
      book,
      chapter,
      verse,
      messages: chatMessages,
      timestamp: new Date().toISOString()
    }

    const saved = localStorage.getItem('unbound_saved_studies')
    const allStudies = saved ? JSON.parse(saved) : []
    allStudies.push(session)
    localStorage.setItem('unbound_saved_studies', JSON.stringify(allStudies))
    alert('Study session saved to your Notes library!')
  }

  // Share conversation
  const handleShareSession = async () => {
    let persistedId = studyId
    if (authStatus === 'authenticated' && !persistedId) {
      try {
        const study = await api.post('/studies', { title: `Study of ${book} ${chapter}:${verse}` })
        for (const message of chatMessages.filter((item) => item.id !== 'welcome')) await api.post(`/studies/${study.id}/messages`, { role: message.type === 'ai' ? 'assistant' : 'user', content: message.content })
        persistedId = study.id; setStudyId(study.id)
      } catch (error) { console.error('Could not save study before sharing:', error); return }
    }
    setShareData({
      studyId: persistedId,
      title: `Decolonized Study of ${book} ${chapter}:${verse}`,
      verses: [`${book} ${chapter}:${verse}`],
      type: 'Study Assistant Conversation',
      content: chatMessages.filter(m => m.id !== 'welcome')
    })
    setShowShareModal(true)
  }

  // Helper to check if book is apocryphal / Ethiopian canon
  const isEthiopianCanonBook = () => {
    const ethiopianBooks = ['1 Enoch', 'Enoch', 'Jubilees', 'Meqabyan 1', 'Meqabyan 2', 'Meqabyan 3', 'Book of Qäləmentos', 'Didaskalia']
    return ethiopianBooks.includes(book)
  }

  return (
    <div className="study-assistant-sidebar glass-panel">
      <div className="sidebar-header">
        <div className="header-info">
          <h2>💡 Study Companion</h2>
          <span className="verse-badge">{book} {chapter}:{verse}</span>
        </div>
        <button className="close-sidebar-btn" onClick={onClose} title="Close Panel">✕</button>
      </div>

      <div className="sidebar-tabs">
        <button 
          className={`sidebar-tab-btn ${activeTab === 'insights' ? 'active' : ''}`}
          onClick={() => setActiveTab('insights')}
        >
          🔍 Passage Insights
        </button>
        <button 
          className={`sidebar-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          🤖 Study Assistant
        </button>
      </div>

      <div className="sidebar-content">
        {activeTab === 'insights' ? (
          <div className="insights-panel-layout">
            <div className="insights-subtabs">
              <button 
                className={`subtab-btn ${activeInsightSubTab === 'crossrefs' ? 'active' : ''}`}
                onClick={() => setActiveInsightSubTab('crossrefs')}
              >
                Cross-Refs
              </button>
              <button 
                className={`subtab-btn ${activeInsightSubTab === 'commentary' ? 'active' : ''}`}
                onClick={() => setActiveInsightSubTab('commentary')}
              >
                Commentary
              </button>
              <button 
                className={`subtab-btn ${activeInsightSubTab === 'lexicon' ? 'active' : ''}`}
                onClick={() => setActiveInsightSubTab('lexicon')}
              >
                Original Words
              </button>
              <button 
                className={`subtab-btn ${activeInsightSubTab === 'canon' ? 'active' : ''}`}
                onClick={() => setActiveInsightSubTab('canon')}
              >
                Canon Notes
              </button>
            </div>

            <div className="subtab-content-area">
              {loading ? (
                <div className="sidebar-loader">
                  <div className="spinner"></div>
                  <p>Analyzing context...</p>
                </div>
              ) : (
                <>
                  {/* CROSS-REFERENCES */}
                  {activeInsightSubTab === 'crossrefs' && (
                    <div className="insight-section">
                      <h4>Cross-References & Parallel Texts</h4>
                      {verseDetails?.cross_references && verseDetails.cross_references.length > 0 ? (
                        <div className="cross-refs-list">
                          {verseDetails.cross_references.map((ref, idx) => (
                            <div key={idx} className="cross-ref-card">
                              <span className="ref-citation">🔗 {ref.target_book} {ref.target_chapter}:{ref.target_verse}</span>
                              <p className="ref-text">{ref.target_text || 'Select this reference to study.'}</p>
                              {ref.description && <p className="ref-context"><em>Connection:</em> {ref.description}</p>}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">
                          <p>No direct cross-references cataloged for this verse yet.</p>
                          <button 
                            className="btn-action-outline" 
                            onClick={() => sendChatMessage(`What are some key thematic cross-references for ${book} ${chapter}:${verse}?`)}
                          >
                            🔍 Search themes via AI
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* COMMENTARY SUMMARIES */}
                  {activeInsightSubTab === 'commentary' && (
                    <div className="insight-section">
                      <h4>Scholarly Commentary Summaries</h4>
                      {verseDetails?.translation_biases && verseDetails.translation_biases.length > 0 ? (
                        <div className="biases-list">
                          {verseDetails.translation_biases.map((bias, idx) => (
                            <div key={idx} className="bias-card">
                              <div className="bias-card-header">
                                <span className="bias-badge warning">Translation Bias Audit</span>
                                <span className="bias-severity">{bias.severity.toUpperCase()}</span>
                              </div>
                              <h5>{bias.title}</h5>
                              <p><strong>Original Word:</strong> {bias.original}</p>
                              <p><strong>Literal Meaning:</strong> <em>{bias.literal}</em></p>
                              <p><strong>Explanation:</strong> {bias.explanation}</p>
                              {bias.scholar && <span className="bias-scholar">Reviewed by: {bias.scholar}</span>}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="commentary-list">
                          <div className="commentary-card">
                            <h5>Decolonized Commentary (Axum Studies)</h5>
                            <p>Exegesis on this verse points out the traditional Near Eastern agrarian setting, noting how local Ge'ez translations preserve active verbal structures compared to Western nominal translations.</p>
                          </div>
                          <div className="commentary-card">
                            <h5>Library Commentary (Standard Exegesis)</h5>
                            <p>Literary analysis indicates this chapter represents a covenant ratification formula standard in the Bronze-Age Levant.</p>
                          </div>
                          <button 
                            className="btn-action-outline"
                            onClick={() => sendChatMessage(`Can you summarize the major commentaries and scholarly debates on ${book} ${chapter}:${verse}?`)}
                          >
                            🤖 Generate Full Commentary Review
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ORIGINAL LANGUAGE LEXICON */}
                  {activeInsightSubTab === 'lexicon' && (
                    <div className="insight-section">
                      <h4>Original Language Words & Strong's Mappings</h4>
                      {verseDetails?.original_words && verseDetails.original_words.length > 0 ? (
                        <div className="words-grid">
                          {verseDetails.original_words.map((word, idx) => (
                            <div 
                              key={idx} 
                              className={`word-card ${selectedWord?.id === word.id ? 'active' : ''}`}
                              onClick={() => setSelectedWord(word)}
                            >
                              <div className="word-main">
                                <span className="word-text">{word.word_text}</span>
                                <span className="word-lang-badge">{word.language}</span>
                              </div>
                              <div className="word-details">
                                <span className="strongs-num">Strong's: {word.strong_number}</span>
                                <p className="word-def">{word.definition}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">
                          <p>No original language lexicon links parsed for this verse in the database.</p>
                          <button 
                            className="btn-action-outline"
                            onClick={() => sendChatMessage(`What are the key Hebrew/Greek words in ${book} ${chapter}:${verse} and their root meanings?`)}
                          >
                            🔤 Extract lexicon terms
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* CANON NOTES */}
                  {activeInsightSubTab === 'canon' && (
                    <div className="insight-section">
                      <h4>Multi-Canonical & Historical Context</h4>
                      {isEthiopianCanonBook() ? (
                        <div className="canon-warning-alert warning-glass">
                          <h5>⚠️ Broad Canon Text Notice</h5>
                          <p>
                            This book (<strong>{book}</strong>) is part of the Ethiopian Orthodox Tewahedo broader canon, 
                            but is considered apocryphal or pseudepigraphal in the Protestant and Catholic traditions.
                          </p>
                          <p className="note-detail">
                            Protestant translations (KJV, ASV, WEB) will not display verse content. You can study this text using 
                            the available Ge'ez manuscripts, Dillmann translations, or historical summaries.
                          </p>
                        </div>
                      ) : (
                        <div className="canon-info-notes">
                          <div className="canon-note-card">
                            <h5>Ethiopian Tradition (Axumite Canon)</h5>
                            <p>
                              In the Ge'ez Octateuch, this passage holds liturgical significance during the Season of Fasting. 
                              The sentence syntax is translated directly from the Alexandrian Septuagint (LXX) rather than the Masoretic Text.
                            </p>
                          </div>
                          <div className="canon-note-card">
                            <h5>Protestant / Catholic Canon Stability</h5>
                            <p>This verse is universally accepted across all major translations (66-book and 73-book lists) with identical numbering structures.</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Quick Note Pad inside insights */}
            <div className="verse-scratchpad">
              <h4>📝 Verse Note Pad</h4>
              {notesList.map((n, i) => (
                <div key={i} className="mini-note">
                  <p>{n.text}</p>
                  <span className="note-time">{new Date(n.timestamp).toLocaleDateString()}</span>
                </div>
              ))}
              <div className="note-input-wrapper">
                <textarea 
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Type notes on this verse to save..."
                  rows="2"
                />
                <button onClick={handleSaveNote} disabled={!noteText.trim()}>Save Note</button>
              </div>
            </div>
          </div>
        ) : (
          <div className="chat-panel-layout">
            <div className="chat-disclaimer">
              <span>⚠️ Study Aid:</span> AI answers are study aids. Always verify with Scripture and trusted sources.
            </div>

            <div className="chat-messages-container">
              {chatMessages.map((msg) => (
                <div key={msg.id} className={`chat-msg-row ${msg.type}`}>
                  <div className="msg-bubble">
                    <p className="msg-content">{msg.content}</p>
                    
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="msg-sources">
                        <span className="sources-label">Citations:</span>
                        {msg.sources.map((s, idx) => (
                          <div key={idx} className="source-pill" title={s.excerpt}>
                            📚 {s.title} ({s.citation})
                          </div>
                        ))}
                      </div>
                    )}

                    {msg.followUps && (
                      <div className="msg-followups">
                        {msg.followUps.map((f, idx) => (
                          <button 
                            key={idx} 
                            className="followup-btn"
                            onClick={() => sendChatMessage(f)}
                          >
                            {f}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="chat-msg-row ai loading">
                  <div className="msg-bubble">
                    <div className="typing-loader">
                      <span></span><span></span><span></span>
                    </div>
                    <p className="loading-txt">Searching library sources...</p>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Action Bar for Study outlines */}
            {chatMessages.length === 1 && (
              <div className="sidebar-quick-prompts">
                <p>Suggested Research Templates:</p>
                <div className="quick-prompts-grid">
                  <button onClick={() => handleQuickPrompt('outline', '📝 Study Outline')}>📝 Study Outline</button>
                  <button onClick={() => handleQuickPrompt('teen', '🧑 Explain to Teenager')}>🧑 Explain to Teen</button>
                  <button onClick={() => handleQuickPrompt('history', '🏛️ Historical Background')}>🏛️ History Context</button>
                  <button onClick={() => handleQuickPrompt('child', '👶 Explain to Child')}>👶 Simple Summary</button>
                </div>
              </div>
            )}

            <div className="chat-footer-actions">
              {chatMessages.length > 1 && (
                <div className="chat-utility-buttons">
                  <button onClick={handleSaveSession} className="btn-utility">💾 Save Session</button>
                  <button onClick={handleShareSession} className="btn-utility">🔗 Share Session</button>
                </div>
              )}

              <div className="chat-input-row">
                <input 
                  type="text" 
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendChatMessage(chatInput)}
                  placeholder={`Ask about ${book} ${chapter}:${verse}...`}
                  disabled={chatLoading}
                />
                <button onClick={() => sendChatMessage(chatInput)} disabled={!chatInput.trim() || chatLoading}>
                  ↑
                </button>
              </div>
            </div>
          </div>
        )}
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

export default StudyAssistantSidebar
