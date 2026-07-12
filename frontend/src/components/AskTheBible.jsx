import { useState, useRef, useEffect } from 'react'
import './AskTheBible.css'
import ShareStudyModal from './ShareStudyModal'
import { askStudyQuestion } from '../services/studyApi'

const POPULAR_SUGGESTIONS = [
  "What does the Bible say about forgiveness?",
  "How does the Ethiopian Bible compare with the King James Version on this passage?",
  "What is the historical background of this chapter?",
  "What are the major cross-references for this theme?",
  "What does the original Hebrew, Greek, Aramaic, or Geʽez suggest?",
  "How would I explain this passage to a teenager?"
];

const TRENDING_QUESTIONS = [
  "Why is Enoch in the Ethiopian Bible but not in most Western Bibles?",
  "What does the Bible say about Cush and Ethiopia?",
  "How was the Curse of Ham misused historically?",
  "What does Song of Solomon 1:5 mean in the original languages?",
  "Who was the Ethiopian eunuch in Acts 8?"
];

const EXPLORE_TOPICS = [
  {
    title: "Faith & Theology",
    desc: "Truths, doctrines, and spiritual growth.",
    image: "/assets/faith_theology.png"
  },
  {
    title: "People & History",
    desc: "Key people, nations, and biblical events.",
    image: "/assets/people_history.png"
  },
  {
    title: "Scripture & Themes",
    desc: "Topics, parables, and biblical themes.",
    image: "/assets/scripture_themes.png"
  },
  {
    title: "Languages & Texts",
    desc: "Original languages, manuscripts, and texts.",
    image: "/assets/languages_texts.png"
  },
  {
    title: "Geography & Places",
    desc: "Maps, regions, and biblical locations.",
    image: "/assets/geography_places.png"
  },
  {
    title: "Prophecy & End Times",
    desc: "Prophetic scriptures and future hope.",
    image: "/assets/prophecy_end_times.png"
  }
];

function AskTheBible({ onPageChange }) {
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [showShareModal, setShowShareModal] = useState(false)
  const [shareData, setShareData] = useState(null)
  const [statusMessage, setStatusMessage] = useState('')
  const [showHelp, setShowHelp] = useState(false)
  
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Suggestion descriptions helper
  const getSuggestionDesc = (q) => {
    if (q.includes("forgiveness")) return "Explore key verses and themes."
    if (q.includes("compare")) return "Compare translations and meaning."
    if (q.includes("historical")) return "Understand the people, places, and events."
    if (q.includes("cross-references")) return "Find connected scriptures."
    if (q.includes("original")) return "See original words and roots."
    if (q.includes("explain")) return "Simplify with clarity and truth."
    return "Study in-depth text queries."
  }

  // Process sending queries
  const handleQuery = async (queryText) => {
    const text = queryText.trim()
    if (!text || loading) return

    // Add user message
    const userMsg = {
      id: 'msg_' + Date.now(),
      type: 'user',
      content: text,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMsg])
    setInputValue('')
    setLoading(true)

    try {
      const result = await askStudyQuestion(text, { allowDemo: true })
      setMessages(prev => [...prev, {
        id: 'ai_' + Date.now(),
        type: 'ai',
        content: result.answer,
        sources: result.sources,
        followUps: result.followUps,
        provenance: result.provenance,
        groundingStatus: result.groundingStatus,
        provider: result.provider,
        model: result.model,
        timestamp: new Date()
      }])
    } catch (err) {
      console.error(err)
      setMessages(prev => [...prev, {
        id: 'err_' + Date.now(),
        type: 'error',
        content: "The study library could not answer that question right now. Your question is still here—please retry when the library reconnects.",
        retryQuery: text,
        timestamp: new Date()
      }])
    } finally {
      setLoading(false)
    }
  }

  // Save conversation
  const handleSaveConversation = () => {
    if (messages.length === 0) return
    const session = {
      id: 'session_' + Date.now(),
      title: `Grounded Q&A: ${messages[0].content.slice(0, 30)}...`,
      type: 'chat',
      date: new Date().toLocaleDateString(),
      messages,
      timestamp: new Date().toISOString()
    }

    const saved = localStorage.getItem('unbound_saved_studies')
    const allStudies = saved ? JSON.parse(saved) : []
    allStudies.push(session)
    localStorage.setItem('unbound_saved_studies', JSON.stringify(allStudies))
    setStatusMessage('Study session saved to My Library.')
  }

  // Trigger Share Modal
  const handleShare = () => {
    setShareData({
      title: "Library-Grounded Biblical Q&A Session",
      verses: [],
      type: 'Ask the Bible Q&A',
      content: messages
    })
    setShowShareModal(true)
  }

  // Parse markdown paragraph strings into HTML tags
  const renderFormattedAnswer = (text) => {
    if (!text) return null
    const paras = text.split(/\n\n+/)
    return paras.map((p, pIdx) => {
      // Handle simple markdown headers like ### Header
      if (p.startsWith('### ')) {
        return <h4 key={pIdx} className="answer-heading">{p.replace('### ', '')}</h4>
      }
      if (p.startsWith('* ')) {
        const items = p.split(/\n\* /)
        return (
          <ul key={pIdx} className="answer-list">
            {items.map((item, i) => {
              const cleanItem = item.replace(/^\* /, '')
              const boldParts = cleanItem.split(/\*\*(.*?)\*\*/g)
              const formattedItem = boldParts.map((part, idx) => idx % 2 === 1 ? <strong key={idx}>{part}</strong> : part)
              return <li key={i}>{formattedItem}</li>
            })}
          </ul>
        )
      }
      // Bold parts
      const parts = p.split(/\*\*(.*?)\*\*/g)
      const formatted = parts.map((part, idx) => idx % 2 === 1 ? <strong key={idx}>{part}</strong> : part)
      return <p key={pIdx} className="answer-p">{formatted}</p>
    })
  }

  return (
    <div className="ub-page-layout">
      {/* Hero Section */}
      <section className="ub-hero">
        <div className="ub-hero-copy">
          <div className="ub-gold-badge">🎧 LIBRARY-GROUNDED AI</div>
          <h1>Ask the Bible <span>✦</span></h1>
          <p>
            Submit natural-language queries regarding scriptures, textual variations, cultural history, and original languages.
          </p>

          <div className="ub-warning">
            <span className="ub-warning-icon">⚠</span>
            <div>
              <strong>AI Study Aid:</strong> Answers are drawn from verified libraries, lexicon indexes, and comparative canons. They are study aids, not final spiritual authorities. Always verify scripture.
            </div>
          </div>
        </div>

        <div className="ub-hero-features">
          <div className="ub-feature-stat">
            <div className="ub-feature-icon">📚</div>
            <h3>Library Grounded</h3>
            <p>Answers cite specific texts, avoiding general web hallucinations.</p>
          </div>
          <div className="ub-feature-stat">
            <div className="ub-feature-icon">🌍</div>
            <h3>Canon Aware</h3>
            <p>Distinguishes Ge’ez, Hebrew, and Western manuscripts and canons.</p>
          </div>
          <div className="ub-feature-stat">
            <div className="ub-feature-icon">𐤀</div>
            <h3>Original Languages</h3>
            <p>Pulls Strong’s roots and translation shifts dynamically.</p>
          </div>
        </div>
      </section>

      {/* Two Column Layout */}
      <div className="ub-content-grid">
        {/* Left Column: Scripture Inquirer */}
        <section className="ub-search-panel">
          <div className="ub-panel-heading">
            <div className="ub-shield">🛡️</div>
            <div>
              <h2>Intelligent Scripture Inquirer</h2>
              <p>Select a quick suggested question below or enter a custom search command.</p>
            </div>
            <button className="ub-how" type="button" aria-expanded={showHelp} onClick={() => setShowHelp((visible) => !visible)}>
              ? How It Works
            </button>
          </div>

          {showHelp && (
            <div className="ub-help-note">
              Questions are sent to the project’s biblical library and lexicon service. Live answers identify their sources. If the local service is offline and a matching demonstration answer exists, it is clearly labeled as a demo.
            </div>
          )}

          {messages.length === 0 ? (
            <div className="ub-question-grid">
              {POPULAR_SUGGESTIONS.map((q, idx) => (
                <button key={idx} className="ub-question-card" type="button" onClick={() => handleQuery(q)}>
                  <div className="ub-question-icon">?</div>
                  <div>
                    <h3>{q}</h3>
                    <p>{getSuggestionDesc(q)}</p>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="chat-viewport-scroller">
              {messages.map((msg) => (
                <div key={msg.id} className={`message-block ${msg.type}`}>
                  <div className="msg-info-row">
                    <span className="msg-sender">{msg.type === 'user' ? '👤 Study Inquirer' : '🎓 Grounded Assistant'}</span>
                    <span className="msg-time">{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  
                  <div className="msg-body">
                    {msg.type === 'ai' ? (
                      <div className="ai-response-wrapper">
                        <div className={`confidence-indicator-tag ${msg.provenance || 'unsourced'}`}>
                          {msg.provenance === 'demo'
                            ? 'Demonstration answer — local study preview'
                            : msg.groundingStatus === 'insufficient'
                              ? 'Insufficient verified evidence — no answer was invented'
                            : msg.sources?.length
                              ? `Verified library evidence · ${msg.provider || 'configured provider'}`
                              : 'No verified sources returned'}
                        </div>
                        
                        <div className="answer-text-area">{renderFormattedAnswer(msg.content)}</div>

                        {/* Source Citation Cards */}
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="sources-container">
                            <h4>📚 Citations & Grounded Texts</h4>
                            <div className="sources-flex-grid">
                              {msg.sources.map((src, sIdx) => (
                                <div key={sIdx} className="citation-card-expanded">
                                  <div className="cit-header">
                                    <span className="cit-badge">GROUNDED REFERENCE</span>
                                  </div>
                                  <h5>{src.title}</h5>
                                  <p className="cit-excerpt">"{src.excerpt}"</p>
                                  <span className="cit-citation-details">{src.citation}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Follow-up Prompts */}
                        {msg.followUps && msg.followUps.length > 0 && (
                          <div className="followups-container">
                            <h5>Further Inquiry:</h5>
                            <div className="followups-flex">
                              {msg.followUps.map((f, fIdx) => (
                                <button key={fIdx} className="followup-chip-btn" onClick={() => handleQuery(f)}>
                                  {f} →
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : msg.type === 'error' ? (
                      <div className="study-error" role="alert">
                        <p>{msg.content}</p>
                        <button type="button" onClick={() => handleQuery(msg.retryQuery)}>Retry question</button>
                      </div>
                    ) : (
                      <p className="user-query">{msg.content}</p>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="message-block ai loading">
                  <div className="typing-bar">
                    <span className="dot"></span>
                    <span className="dot"></span>
                    <span className="dot"></span>
                  </div>
                  <p className="loading-label-p">Consulting cross-references and lexicons...</p>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          )}

          {/* Chat Form Container */}
          <div className="ask-chat-input-area">
            {messages.length > 0 && (
              <div className="chat-actions-row">
                <button className="chat-action-btn-utility" onClick={handleSaveConversation}>💾 Save Study Session</button>
                <button className="chat-action-btn-utility" onClick={handleShare}>🔗 Share Study Session</button>
                <button className="chat-action-btn-utility clear" onClick={() => setMessages([])}>✕ Clear Chat</button>
              </div>
            )}
            <div className="ub-search-form">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleQuery(inputValue)}
                aria-label="Ask a biblical study question"
                placeholder="Search biblical questions (e.g. ‘Did Moses marry an Ethiopian?’) or type your own..."
                disabled={loading}
              />
              <button type="button" onClick={() => handleQuery(inputValue)} disabled={!inputValue.trim() || loading}>
                {loading ? '⏳' : '⌕ Search'}
              </button>
            </div>
          </div>
        </section>

        {/* Right Column: Sidebar */}
        <aside className="ub-sidebar">
          {/* Featured Study Paths */}
          <section className="ub-side-card">
            <h2>🗺 Featured Study Paths</h2>
            <div className="ub-side-list">
              <button className="ub-study-path" type="button" onClick={() => onPageChange && onPageChange('canon-compare')}>
                <div className="ub-path-icon purple">𓋹</div>
                <div className="path-details">
                  <h3>Understanding the Ethiopian Canon</h3>
                  <p>Books preserved, omitted, and why</p>
                </div>
                <span className="ub-arrow">→</span>
              </button>

              <button className="ub-study-path" type="button" onClick={() => onPageChange && onPageChange('race-misuse')}>
                <div className="ub-path-icon green">⚖</div>
                <div className="path-details">
                  <h3>Race & Scripture Misuse</h3>
                  <p>Verses used to justify oppression</p>
                </div>
                <span className="ub-arrow">→</span>
              </button>

              <button className="ub-study-path" type="button" onClick={() => onPageChange && onPageChange('factbook')}>
                <div className="ub-path-icon gold">🌍</div>
                <div className="path-details">
                  <h3>African Presence in Scripture</h3>
                  <p>Cush, Ethiopia, Egypt, Nubia & more</p>
                </div>
                <span className="ub-arrow">→</span>
              </button>

              <button className="ub-study-path" type="button" onClick={() => onPageChange && onPageChange('bias-explorer')}>
                <div className="ub-path-icon gray">⌬</div>
                <div className="path-details">
                  <h3>Translation Bias Explorer</h3>
                  <p>Compare translations and shifts</p>
                </div>
                <span className="ub-arrow">→</span>
              </button>

              <button className="ub-study-path" type="button" onClick={() => onPageChange && onPageChange('textual')}>
                <div className="ub-path-icon gold">𐤀</div>
                <div className="path-details">
                  <h3>Original Language Deep Dive</h3>
                  <p>Hebrew, Greek, Aramaic, Ge’ez</p>
                </div>
                <span className="ub-arrow">→</span>
              </button>
            </div>
          </section>

          {/* Trending Questions */}
          <section className="ub-side-card ub-trending">
            <h2>🔥 Trending Questions</h2>
            <ol>
              {TRENDING_QUESTIONS.map((item, index) => (
                <li key={item}>
                  <span>{index + 1}</span>
                  <button type="button" onClick={() => handleQuery(item)}>{item}</button>
                </li>
              ))}
            </ol>

            <div className="ub-callout">
              <h3>Ask Deeper. Study Smarter. Seek Truth.</h3>
              <p>
                Our AI is built for study, not opinion. Every answer points you back
                to scripture.
              </p>
              <span>✦</span>
            </div>
          </section>
        </aside>
      </div>

      {/* Explore Topics Section */}
      <section className="ub-explore">
        <div className="ub-section-title">
          <h2>✥ Explore by Topic</h2>
          <button type="button" onClick={() => onPageChange && onPageChange('factbook')}>View All Topics →</button>
        </div>

        <div className="ub-topic-grid">
          {EXPLORE_TOPICS.map((topic) => (
            <button key={topic.title} className="ub-topic-card" type="button" onClick={() => onPageChange && onPageChange('factbook')}>
              <div className="ub-topic-art">
                <img src={topic.image} alt={topic.title} className="ub-topic-art-img" />
              </div>
              <h3>{topic.title}</h3>
              <p>{topic.desc}</p>
            </button>
          ))}
        </div>
      </section>
      <div className="sr-only" aria-live="polite">{statusMessage}</div>
      <ShareStudyModal
        isOpen={showShareModal}
        onClose={() => setShowShareModal(false)}
        shareData={shareData}
      />
    </div>
  );
}

export default AskTheBible
