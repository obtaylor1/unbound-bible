import { useState, useEffect } from 'react'
import './ResearchHub.css'
import { MOCK_RESEARCH_TOPICS } from '../data/mockData'
import { DEMO_ENABLED } from '../config/runtime'

const FEATURED_TOPICS = [
  { slug: "moses", name: "Moses", type: "👤 Person" },
  { slug: "ethiopia", name: "Ethiopia (Cush)", type: "🌍 Place" },
  { slug: "jerusalem", name: "Jerusalem", type: "🏛️ Place" },
  { slug: "covenant", name: "Covenant", type: "📜 Doctrine" },
  { slug: "enoch", name: "Book of Enoch", type: "📘 Book" },
  { slug: "translation_bias", name: "Translation Bias Explorer", type: "⚖️ Bias Audit" }
];

function ResearchHub({ initialTopicKey = 'moses' }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTopicKey, setActiveTopicKey] = useState(initialTopicKey)
  const [activeTab, setActiveTab] = useState('summary')

  // New features state
  const [activeGeoLocIndex, setActiveGeoLocIndex] = useState(0)
  const [selectedScripture, setSelectedScripture] = useState(null)
  const [scriptureDetails, setScriptureDetails] = useState(null)
  const [loadingScripture, setLoadingScripture] = useState(false)
  const [scriptureError, setScriptureError] = useState(null)

  const activeTopic = MOCK_RESEARCH_TOPICS[activeTopicKey]

  // Reset tab-specific state when topic changes
  useEffect(() => {
    setActiveGeoLocIndex(0)
    setSelectedScripture(null)
    setScriptureDetails(null)
  }, [activeTopicKey])

  if (!DEMO_ENABLED && initialTopicKey !== 'translation_bias') return <div className="empty-workspace-card"><h2>Research topics are not loaded</h2><p>Run the research-content ingestion workflow or enable the explicitly labeled demo dataset for this environment.</p></div>

  const parseScriptureRef = (refStr) => {
    const regex = /^([\d\s]*[A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(\d+):(\d+)(?:-(\d+))?$/;
    const match = refStr.trim().match(regex);
    if (match) {
      const start = parseInt(match[3])
      return {
        book: match[1].trim(),
        chapter: parseInt(match[2]),
        startVerse: start,
        endVerse: match[4] ? parseInt(match[4]) : start
      };
    }
    return null;
  }

  const handleInspectScripture = (refStr) => {
    const parsed = parseScriptureRef(refStr)
    if (parsed) {
      const scriptureInfo = {
        refString: refStr,
        book: parsed.book,
        chapter: parsed.chapter,
        startVerse: parsed.startVerse,
        endVerse: parsed.endVerse,
        activeVerse: parsed.startVerse
      }
      setSelectedScripture(scriptureInfo)
      fetchScriptureDetails(scriptureInfo.book, scriptureInfo.chapter, scriptureInfo.activeVerse)
    } else {
      // Fallback: If not standard parse (e.g. single verse range), try exact format or alert
      console.warn("Could not parse reference:", refStr)
    }
  }

  const fetchScriptureDetails = async (book, chapter, verse) => {
    setLoadingScripture(true)
    setScriptureError(null)
    setScriptureDetails(null)
    try {
      const response = await fetch(`/api/v1/texts/${encodeURIComponent(book.trim())}/${chapter}/${verse}/details`)
      if (response.ok) {
        const data = await response.json()
        setScriptureDetails(data)
      } else {
        throw new Error("Failed to fetch translation comparisons for this verse")
      }
    } catch (err) {
      console.error(err)
      setScriptureError(err.message)
    } finally {
      setLoadingScripture(false)
    }
  }

  const handleSelectInspectorVerse = (v) => {
    if (selectedScripture) {
      setSelectedScripture({ ...selectedScripture, activeVerse: v })
      fetchScriptureDetails(selectedScripture.book, selectedScripture.chapter, v)
    }
  }

  const projectCoordinates = (lat, lng) => {
    // Project linearly into SVG viewBox [0, 100] for bounding box Lat [10, 34] and Lng [30, 40]
    const x = ((lng - 30) / 10) * 100;
    const y = 100 - ((lat - 10) / 24) * 100;
    return { x, y };
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    const query = searchQuery.toLowerCase().trim()
    if (query.includes('bias') || query.includes('translation')) {
      setActiveTopicKey('translation_bias')
      setSearchQuery('')
      return
    }
    const foundKey = Object.keys(MOCK_RESEARCH_TOPICS).find(
      key => key.toLowerCase() === query ||
             MOCK_RESEARCH_TOPICS[key].name.toLowerCase().includes(query)
    )
    if (foundKey) {
      setActiveTopicKey(foundKey)
      setActiveTab('summary')
      setSearchQuery('')
    } else {
      alert(`Topic "${searchQuery}" is not cached. Try Moses, Ethiopia, Jerusalem, Covenant, Enoch, or Translation Bias!`)
    }
  }

  const handleSelectTopic = (key) => {
    setActiveTopicKey(key)
    setActiveTab('summary')
  }

  return (
    <div className="research-hub glass-panel">
      <div className="hub-header">
        <span className="hub-badge">🔬 CRITICAL AUDIT WORKSPACE</span>
        <h2>Biblical Research Hub</h2>
        <p className="subtitle">
          Factbook-style cross-referencing for major biblical figures, coordinates, manuscripts, and theological doctrines.
        </p>
        
        {/* Search Bar */}
        <form onSubmit={handleSearchSubmit} className="hub-search-form">
          <div className="search-input-wrapper">
            <span className="search-icon">🔍</span>
            <input 
              type="text" 
              placeholder="Search people, places, doctrines, or books (e.g. Moses, Ethiopia)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit">Research</button>
          </div>
        </form>
      </div>

      <div className="hub-layout">
        {/* Sidebar: Recommended Topic cards */}
        <div className="hub-sidebar">
          <h3>Featured Factbooks</h3>
          <div className="featured-list">
            {FEATURED_TOPICS.map((topic) => (
              <button 
                key={topic.slug}
                className={`featured-card ${activeTopicKey === topic.slug ? 'active' : ''}`}
                onClick={() => handleSelectTopic(topic.slug)}
              >
                <span className="feat-type">{topic.type}</span>
                <span className="feat-name">{topic.name}</span>
                <span className="feat-arrow">→</span>
              </button>
            ))}
          </div>
        </div>

        {/* Main Panel: Detailed Topic Workspace */}
        <div className="hub-main-workspace">
          {activeTopicKey === 'translation_bias' ? (
            <TranslationBiasExplorer />
          ) : activeTopic ? (
            <div className="topic-container">
              <div className="topic-title-bar">
                <div className="title-left">
                  <span className="topic-type-tag">{activeTopic.type.toUpperCase()}</span>
                  <h2>{activeTopic.name}</h2>
                </div>
                <div className="title-right">
                  <span className="source-info-badge">Logos Verified</span>
                </div>
              </div>

              {/* Navigation Tabs */}
              <div className="topic-tabs">
                <button className={`tab-btn ${activeTab === 'summary' ? 'active' : ''}`} onClick={() => setActiveTab('summary')}>
                  📋 Summary
                </button>
                <button className={`tab-btn ${activeTab === 'scriptures' ? 'active' : ''}`} onClick={() => setActiveTab('scriptures')}>
                  📖 References ({activeTopic.scriptureReferences?.length || 0})
                </button>
                <button className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`} onClick={() => setActiveTab('timeline')}>
                  ⏰ Timeline
                </button>
                <button className={`tab-btn ${activeTab === 'geography' ? 'active' : ''}`} onClick={() => setActiveTab('geography')}>
                  🗺️ Geography
                </button>
                <button className={`tab-btn ${activeTab === 'lexicon' ? 'active' : ''}`} onClick={() => setActiveTab('lexicon')}>
                  🔤 Original Languages
                </button>
                <button className={`tab-btn ${activeTab === 'manuscripts' ? 'active' : ''}`} onClick={() => setActiveTab('manuscripts')}>
                  📜 Manuscripts
                </button>
                <button className={`tab-btn ${activeTab === 'frameworks' ? 'active' : ''}`} onClick={() => setActiveTab('frameworks')}>
                  ⚖️ Frameworks
                </button>
                <button className={`tab-btn ${activeTab === 'commentary' ? 'active' : ''}`} onClick={() => setActiveTab('commentary')}>
                  📚 Commentary & Media
                </button>
              </div>

              {/* Tab Workspace Contents */}
              <div className="topic-tab-content glass-panel">
                
                {/* SUMMARY TAB */}
                {activeTab === 'summary' && (
                  <div className="summary-tab-content">
                    <h3>Biographical / Doctrinal Synthesis</h3>
                    <p className="synthesis-text">{activeTopic.summary}</p>
                    
                    <div className="summary-relations-grid">
                      <div className="relation-box">
                        <h4>Related Figures</h4>
                        <div className="tags-row">
                          {activeTopic.relatedPeople?.map(p => <span key={p} className="tag person">{p}</span>)}
                        </div>
                      </div>
                      <div className="relation-box">
                        <h4>Key Themes</h4>
                        <div className="tags-row">
                          {activeTopic.themes?.map(t => <span key={t} className="tag theme">{t}</span>)}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* SCRIPTURES TAB */}
                {activeTab === 'scriptures' && (
                  <div className="scriptures-tab-content">
                    <h3>Primary Biblical Passages</h3>
                    <p className="tab-instructions">Key scripture references documenting this topic. Click to inspect translations, original languages, and cross-references.</p>
                    <div className="scripture-refs-grid">
                      {activeTopic.scriptureReferences?.map((ref, idx) => (
                        <div key={idx} className="ref-link-card" onClick={() => handleInspectScripture(ref)}>
                          <span className="ref-icon">📖</span>
                          <span className="ref-name">{ref}</span>
                          <span className="ref-view-badge">Inspect Verse</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* TIMELINE TAB */}
                {activeTab === 'timeline' && (
                  <div className="timeline-tab-content">
                    <h3>Historical Timeline & Milestones</h3>
                    <div className="vertical-timeline">
                      {activeTopic.timelineEvents?.map((event, idx) => (
                        <div key={idx} className="timeline-row">
                          <div className="timeline-year">{event.year}</div>
                          <div className="timeline-divider">
                            <span className="dot"></span>
                            {idx < activeTopic.timelineEvents.length - 1 && <span className="line"></span>}
                          </div>
                          <div className="timeline-desc-card">
                            <p>{event.event}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* GEOGRAPHY TAB */}
                {activeTab === 'geography' && (
                  <div className="geography-tab-content">
                    <h3>Geographical Locations & Artifact Sites</h3>
                    {activeTopic.geographicalMaps && activeTopic.geographicalMaps.length > 0 ? (
                      <div className="geography-layout">
                        <div className="locations-sidebar-list">
                          {activeTopic.geographicalMaps.map((loc, idx) => (
                            <button 
                              key={idx} 
                              className={`location-item-btn ${activeGeoLocIndex === idx ? 'active' : ''}`}
                              onClick={() => setActiveGeoLocIndex(idx)}
                            >
                              <span className="loc-bullet">📍</span>
                              <div className="loc-text-info">
                                <h5>{loc.name}</h5>
                                <span className="loc-coords-badge">{loc.lat}° N, {loc.lng}° E</span>
                              </div>
                            </button>
                          ))}
                        </div>

                        {/* Middle: Active Location Detail Inspector */}
                        {activeTopic.geographicalMaps[activeGeoLocIndex] && (
                          <div className="location-detail-panel glass-panel">
                            <span className="panel-hdr-badge">📍 SELECTED SITE</span>
                            <h4>{activeTopic.geographicalMaps[activeGeoLocIndex].name}</h4>
                            <p className="loc-desc-text">{activeTopic.geographicalMaps[activeGeoLocIndex].description}</p>
                            
                            <div className="loc-details-meta">
                              <div className="meta-row">
                                <span className="lbl">Coordinates:</span>
                                <span className="val monospace">{activeTopic.geographicalMaps[activeGeoLocIndex].lat}° N, {activeTopic.geographicalMaps[activeGeoLocIndex].lng}° E</span>
                              </div>
                              <div className="meta-row">
                                <span className="lbl">Archaeological Status:</span>
                                <span className="val verified">Excavated / Documented</span>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Right: Premium Interactive SVG Map */}
                        <div className="map-panel-placeholder modern-svg-map">
                          <div className="map-coordinate-hud">
                            <span className="hud-coord lat-top">34° N</span>
                            <span className="hud-coord lat-bottom">10° N</span>
                            <span className="hud-coord lng-left">30° E</span>
                            <span className="hud-coord lng-right">40° E</span>
                            <span className="hud-compass-rose">🧭</span>
                          </div>
                          <div className="map-graphic">
                            <svg viewBox="0 0 100 100" className="regional-svg-map">
                              {/* Grid Lines */}
                              <line x1="20" y1="0" x2="20" y2="100" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
                              <line x1="40" y1="0" x2="40" y2="100" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
                              <line x1="60" y1="0" x2="60" y2="100" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
                              <line x1="80" y1="0" x2="80" y2="100" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
                              <line x1="0" y1="20" x2="100" y2="20" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
                              <line x1="0" y1="40" x2="100" y2="40" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
                              <line x1="0" y1="60" x2="100" y2="60" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />
                              <line x1="0" y1="80" x2="100" y2="80" className="grid-line" strokeDasharray="1,2" stroke="rgba(255,255,255,0.06)" strokeWidth="0.3" />

                              {/* Water bodies */}
                              <path d="M 0,0 L 100,0 L 100,2 L 60,3 Q 45,10 20,4 L 0,3 Z" className="map-water" fill="rgba(59, 130, 246, 0.08)" stroke="rgba(59, 130, 246, 0.15)" strokeWidth="0.4" />
                              <path d="M 18,100 Q 23,80 19,60 T 16,40 T 21,20 Q 23,12 21,4" className="map-river" fill="none" stroke="rgba(59, 130, 246, 0.15)" strokeWidth="0.5" strokeDasharray="1,1" />
                              <path d="M 45,45 Q 60,70 75,100 L 85,100 Q 70,70 52,42 Z" className="map-water" fill="rgba(59, 130, 246, 0.08)" stroke="rgba(59, 130, 246, 0.15)" strokeWidth="0.4" />
                              <path d="M 28,15 L 45,45 L 42,46 L 26,16 Z" className="map-water" fill="rgba(59, 130, 246, 0.05)" stroke="rgba(59, 130, 246, 0.1)" strokeWidth="0.3" />
                              <path d="M 52,18 L 45,45 L 47,45 L 53,19 Z" className="map-water" fill="rgba(59, 130, 246, 0.05)" stroke="rgba(59, 130, 246, 0.1)" strokeWidth="0.3" />
                              <ellipse cx="52.3" cy="9.3" rx="1.2" ry="2.2" className="map-water" fill="rgba(59, 130, 246, 0.12)" stroke="rgba(59, 130, 246, 0.25)" strokeWidth="0.4" />
                              <path d="M 52.3,7 L 52.3,1" className="map-river" fill="none" stroke="rgba(59, 130, 246, 0.15)" strokeWidth="0.4" />

                              {/* Projected Pins */}
                              {activeTopic.geographicalMaps.map((loc, i) => {
                                const { x, y } = projectCoordinates(loc.lat, loc.lng);
                                const isActive = activeGeoLocIndex === i;
                                return (
                                  <g key={i} className={`map-pin-group ${isActive ? 'active' : ''}`} style={{ cursor: 'pointer' }} onClick={() => setActiveGeoLocIndex(i)}>
                                    {isActive && <circle cx={x} cy={y} r="5" className="pin-pulse" fill="none" stroke="#D4AF37" strokeWidth="0.5" />}
                                    <circle cx={x} cy={y} r="1.8" className="pin-dot" fill={isActive ? '#D4AF37' : '#C084FC'} stroke="#0b132b" strokeWidth="0.4" />
                                    <text x={x} y={y - 3} className="pin-label" textAnchor="middle" fill={isActive ? '#D4AF37' : 'rgba(253, 251, 247, 0.65)'} fontSize="2.8" fontWeight={isActive ? 'bold' : 'normal'}>
                                      {loc.name}
                                    </text>
                                  </g>
                                );
                              })}
                            </svg>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="empty-geography">
                        <span className="geo-icon">🌍</span>
                        <p>No specific physical coordinates or maps mapped for this abstract theological doctrine.</p>
                      </div>
                    )}
                  </div>
                )}

                {/* LEXICON TAB */}
                {activeTab === 'lexicon' && (
                  <div className="lexicon-tab-content">
                    <h3>Linguistic Etymology & Translation Logs</h3>
                    <div className="original-words-flex">
                      {activeTopic.originalWords?.map((word, idx) => (
                        <div key={idx} className="orig-word-card">
                          <div className="word-card-header">
                            <span className="word-lang">{word.lang}</span>
                            <span className="word-strong">{word.strong}</span>
                          </div>
                          <h4>{word.word}</h4>
                          <p className="word-meaning"><strong>Definition:</strong> {word.def}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* MANUSCRIPTS TAB */}
                {activeTab === 'manuscripts' && (
                  <div className="manuscripts-tab-content">
                    <h3>Primary Manuscript Witnesses & Attestations</h3>
                    <p className="tab-instructions">Historical document registry tracking primary archaeological and textual witnesses.</p>
                    <div className="manuscripts-grid">
                      {activeTopic.manuscripts?.map((ms, idx) => (
                        <div key={idx} className="manuscript-card">
                          <div className="ms-card-header">
                            <span className="ms-lang">{ms.lang}</span>
                            <span className="ms-date">{ms.date}</span>
                          </div>
                          <h4>{ms.name}</h4>
                          <p className="ms-details">{ms.details}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* INTERPRETATIVE FRAMEWORKS TAB */}
                {activeTab === 'frameworks' && (
                  <div className="frameworks-tab-content">
                    <h3>Scholarly Interpretative Frameworks</h3>
                    <p className="tab-instructions">Comparative matrix presenting divergent cultural, historical, and theological methodologies.</p>
                    <div className="frameworks-matrix">
                      {activeTopic.interpretativeFrameworks?.map((fw, idx) => (
                        <div key={idx} className={`framework-card ${fw.framework.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}>
                          <div className="fw-header">
                            <span className="fw-icon">
                              {fw.framework.includes('Critical') ? '🔬' : fw.framework.includes('Orthodox') ? '⛪' : '⚖️'}
                            </span>
                            <h4>{fw.framework}</h4>
                          </div>
                          <p className="fw-perspective">{fw.perspective}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* COMMENTARY & MEDIA TAB */}
                {activeTab === 'commentary' && (
                  <div className="commentary-tab-content">
                    <div className="split-content-row">
                      
                      {/* Left: Scholar commentaries */}
                      <div className="commentaries-column">
                        <h3>Critical Exegesis Notes</h3>
                        <div className="comms-list">
                          {activeTopic.commentarySummaries?.map((comm, idx) => (
                            <div key={idx} className="comm-bubble">
                              <p>"{comm}"</p>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Right: Media links */}
                      <div className="media-column">
                        <h3>Visual Study Aids</h3>
                        <div className="media-list">
                          {activeTopic.mediaResources?.map((res, idx) => (
                            <div key={idx} className="media-item-card">
                              <span className="media-icon">
                                {res.type === 'map' ? '🗺️' : res.type === 'chart' ? '📊' : '🖼️'}
                              </span>
                              <div className="media-info">
                                <h5>{res.title}</h5>
                                <span className="media-type-tag">{res.type.toUpperCase()}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                    </div>
                  </div>
                )}

              </div>

              {/* Topic Suggested Questions footer */}
              <div className="topic-questions-footer">
                <h4>Suggested Follow-up Inquiries:</h4>
                <div className="questions-chips-row">
                  {activeTopic.suggestedQuestions?.map((q, idx) => (
                    <button key={idx} className="question-chip-btn" onClick={() => {
                      // Set search query and search if it looks like a verse reference or contains search keywords
                      setSearchQuery(q);
                    }}>
                      ❓ {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* Scripture Inspector Slide-over Drawer */}
              {selectedScripture && (
                <div className={`scripture-inspector-drawer ${selectedScripture ? 'open' : ''}`}>
                  <div className="drawer-header">
                    <div className="header-left">
                      <span className="drawer-title-badge">📖 TEXTUAL INSPECTOR</span>
                      <h3>{selectedScripture.book} {selectedScripture.chapter}:{selectedScripture.activeVerse}</h3>
                      {selectedScripture.startVerse !== selectedScripture.endVerse && (
                        <span className="ref-range-indicator">Range: {selectedScripture.refString}</span>
                      )}
                    </div>
                    <button className="close-btn" onClick={() => setSelectedScripture(null)}>✕ Close</button>
                  </div>

                  {/* Verse range navigation */}
                  {selectedScripture.startVerse !== selectedScripture.endVerse && (
                    <div className="inspector-verse-navigation">
                      <span className="nav-label">Select Verse:</span>
                      <div className="nav-buttons-row">
                        {Array.from(
                          { length: selectedScripture.endVerse - selectedScripture.startVerse + 1 },
                          (_, i) => selectedScripture.startVerse + i
                        ).map(v => (
                          <button 
                            key={v}
                            className={`nav-v-btn ${selectedScripture.activeVerse === v ? 'active' : ''}`}
                            onClick={() => handleSelectInspectorVerse(v)}
                          >
                            {v}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="drawer-body scrollable">
                    {loadingScripture ? (
                      <div className="inspector-loader">
                        <div className="spinner"></div>
                        <p>Fetching original languages and translation comparison...</p>
                      </div>
                    ) : scriptureError ? (
                      <div className="inspector-error">
                        <p>⚠️ Error: {scriptureError}</p>
                      </div>
                    ) : scriptureDetails ? (
                      <div className="inspector-details-content">
                        {/* Translation Comparisons list */}
                        <div className="details-section">
                          <h4>Translation Comparisons</h4>
                          <div className="translations-comparison-list">
                            {Object.entries(scriptureDetails.translations).map(([code, text]) => (
                              <div key={code} className="translation-inspect-card">
                                <div className="trans-header">
                                  <span className="trans-code">{code.toUpperCase()}</span>
                                </div>
                                <p className="trans-text">{text}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* original language insights */}
                        {scriptureDetails.original_language_insights && scriptureDetails.original_language_insights.length > 0 && (
                          <div className="details-section">
                            <h4>Linguistic Breakdowns (Strong's Concord concordance)</h4>
                            <div className="lexicon-insights-grid">
                              {scriptureDetails.original_language_insights.map((word, wIdx) => (
                                <div key={wIdx} className="lexicon-insight-card">
                                  <div className="lex-header">
                                    <span className="lex-lang">{word.language.toUpperCase()}</span>
                                    {word.strong_number && <span className="lex-strong">{word.strong_number}</span>}
                                  </div>
                                  <h5 className="lex-word">{word.text}</h5>
                                  {word.root && <p className="lex-root">Root: <em>{word.root}</em></p>}
                                  <p className="lex-def">{word.definition}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* bias alerts */}
                        {scriptureDetails.translation_bias_alerts && scriptureDetails.translation_bias_alerts.length > 0 && (
                          <div className="details-section alerts">
                            <h4>⚠️ Detected Translation Bias Shifts</h4>
                            <div className="bias-alerts-list">
                              {scriptureDetails.translation_bias_alerts.map((bias, bIdx) => (
                                <div key={bIdx} className={`bias-alert-card severity-${bias.severity}`}>
                                  <div className="bias-header">
                                    <span className="bias-title">{bias.title}</span>
                                    <span className={`bias-badge ${bias.severity}`}>{bias.severity.toUpperCase()}</span>
                                  </div>
                                  <p className="bias-desc">{bias.explanation}</p>
                                  {bias.scholar && <div className="bias-scholar">🎓 Reviewed by: {bias.scholar}</div>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* exegesis and analysis */}
                        {scriptureDetails.verse_meaning && (
                          <div className="details-section exegesis">
                            <h4>Exegesis & Synthesis</h4>
                            <div className="exegesis-box">
                              <p><strong>Verse Synthesis:</strong> {scriptureDetails.verse_meaning}</p>
                              {scriptureDetails.translation_comparison && (
                                <p><strong>Translation Commentary:</strong> {scriptureDetails.translation_comparison}</p>
                              )}
                              {scriptureDetails.critical_analysis && (
                                <p className="critical-analysis-note"><strong>Scholarly Analysis:</strong> {scriptureDetails.critical_analysis}</p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* cross references */}
                        {scriptureDetails.cross_references && scriptureDetails.cross_references.length > 0 && (
                          <div className="details-section">
                            <h4>Cross References</h4>
                            <div className="cross-references-list">
                              {scriptureDetails.cross_references.map((cross, cIdx) => (
                                <div key={cIdx} className="cross-ref-card" onClick={() => handleInspectScripture(`${cross.book} ${cross.chapter}:${cross.verse}`)}>
                                  <h5>📖 {cross.book} {cross.chapter}:{cross.verse}</h5>
                                  <p>"{cross.text}"</p>
                                  {cross.description && <p className="cross-desc"><em>{cross.description}</em></p>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="inspector-empty">
                        <p>No details found for this verse.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

            </div>
          ) : (
            <div className="workspace-empty">
              <p>Select a topic from the left Factbook panel or search above to begin your critical audit.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function TranslationBiasExplorer() {
  const [biases, setBiases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  
  // AI Sandbox state
  const [books, setBooks] = useState([])
  const [selectedBook, setSelectedBook] = useState('Genesis')
  const [selectedChapter, setSelectedChapter] = useState(3)
  const [selectedVerse, setSelectedVerse] = useState(16)
  const [auditResult, setAuditResult] = useState(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState(null)

  // Fetch all translation biases from backend
  useEffect(() => {
    const fetchBiases = async () => {
      try {
        setLoading(true)
        const response = await fetch('/api/v1/translation-biases')
        if (response.ok) {
          const data = await response.json()
          setBiases(data)
        } else {
          throw new Error('Failed to load documented biases')
        }
      } catch (err) {
        console.error(err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchBiases()
  }, [])

  // Fetch available books for dynamic dropdown
  useEffect(() => {
    const fetchBooks = async () => {
      try {
        const response = await fetch('/api/biblical-texts/available-books')
        if (response.ok) {
          const data = await response.json()
          setBooks(data.books || [])
          if (data.books && data.books.length > 0) {
            setSelectedBook(data.books[0])
          }
        }
      } catch (err) {
        console.error('Failed to load books:', err)
      }
    }
    fetchBooks()
  }, [])

  const handleRunAudit = async (e) => {
    e.preventDefault()
    setAuditLoading(true)
    setAuditError(null)
    setAuditResult(null)
    try {
      const response = await fetch('/api/v1/translation-bias/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book: selectedBook,
          chapter: parseInt(selectedChapter),
          verse: parseInt(selectedVerse)
        })
      })
      if (response.ok) {
        const data = await response.json()
        setAuditResult(data)
      } else {
        const errData = await response.json()
        throw new Error(errData.detail || 'Failed to analyze this verse')
      }
    } catch (err) {
      console.error(err)
      setAuditError(err.message)
    } finally {
      setAuditLoading(false)
    }
  }

  const filteredBiases = biases.filter(bias => 
    bias.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    bias.book.toLowerCase().includes(searchTerm.toLowerCase()) ||
    bias.explanation.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="bias-explorer-container">
      <div className="topic-title-bar">
        <div className="title-left">
          <span className="topic-type-tag">⚖️ BIAS AUDIT SYSTEM</span>
          <h2>Translation Bias Explorer</h2>
        </div>
        <div className="title-right">
          <span className="source-info-badge">Scholarly Audited</span>
        </div>
      </div>

      <p className="bias-intro-text">
        Modern Bible translations are shaped by theological commitments, historical contexts, and linguistic choices of translation committees. Below is a catalog of documented translation shifts, followed by an AI Sandbox to audit any verse in real-time.
      </p>

      <div className="bias-grid-layout">
        {/* Left: Documented bias catalog */}
        <div className="bias-catalog-panel">
          <div className="catalog-header-row">
            <h3>Documented Translation Biases ({filteredBiases.length})</h3>
            <input 
              type="text" 
              placeholder="Filter by book, title, keyword..." 
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="bias-search-input"
            />
          </div>

          {loading ? (
            <div className="bias-loader">
              <div className="spinner"></div>
              <p>Fetching documented translation biases...</p>
            </div>
          ) : error ? (
            <div className="bias-error-card">
              <p>⚠️ Error loading biases: {error}</p>
            </div>
          ) : filteredBiases.length === 0 ? (
            <div className="bias-empty-card">
              <p>No biases match your query.</p>
            </div>
          ) : (
            <div className="bias-scroll-list">
              {filteredBiases.map((bias) => (
                <div key={bias.id} className={`bias-detail-card severity-${bias.severity}`}>
                  <div className="bias-detail-header">
                    <span className="bias-ref">📖 {bias.book} {bias.chapter}:{bias.verse}</span>
                    <span className={`bias-severity-badge ${bias.severity}`}>
                      {bias.severity === 'high' ? '🔴 High Severity' : bias.severity === 'medium' ? '🟡 Medium Severity' : '🔵 Info/Context'}
                    </span>
                  </div>
                  
                  <h4>{bias.title}</h4>
                  
                  <div className="bias-linguistics-comparison">
                    {bias.original && (
                      <div className="bias-ling-row">
                        <span className="label">Original Term:</span>
                        <span className="value original-greek-hebrew">{bias.original}</span>
                      </div>
                    )}
                    {bias.literal && (
                      <div className="bias-ling-row">
                        <span className="label">Literal Meaning:</span>
                        <span className="value literal-trans">"{bias.literal}"</span>
                      </div>
                    )}
                    {bias.target_text && (
                      <div className="bias-ling-row">
                        <span className="label">Shifted Translation ({bias.target_translation || 'KJV'}):</span>
                        <span className="value shifted-trans">"{bias.target_text}"</span>
                      </div>
                    )}
                  </div>

                  <p className="bias-exp-desc">{bias.explanation}</p>
                  
                  {bias.scholar && (
                    <div className="bias-scholar-footer">
                      <span>🎓 Reviewed by: <strong>{bias.scholar}</strong></span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: AI Sandbox */}
        <div className="bias-sandbox-panel">
          <h3>🤖 AI Translation Bias Sandbox</h3>
          <p className="sandbox-desc">
            Select a verse from the database to run a real-time linguistic audit against original source texts.
          </p>

          <form onSubmit={handleRunAudit} className="bias-sandbox-form">
            <div className="form-group">
              <label>Select Book</label>
              <select value={selectedBook} onChange={e => setSelectedBook(e.target.value)}>
                {books.map(b => (
                  <option key={b} value={b}>{b}</option>
                ))}
              </select>
            </div>

            <div className="form-row-flex">
              <div className="form-group">
                <label>Chapter</label>
                <input 
                  type="number" 
                  min="1" 
                  value={selectedChapter} 
                  onChange={e => setSelectedChapter(e.target.value)} 
                />
              </div>
              <div className="form-group">
                <label>Verse</label>
                <input 
                  type="number" 
                  min="1" 
                  value={selectedVerse} 
                  onChange={e => setSelectedVerse(e.target.value)} 
                />
              </div>
            </div>

            <button type="submit" className="btn-run-audit" disabled={auditLoading}>
              {auditLoading ? 'Auditing Wording...' : '🔍 Run Translation Bias Audit'}
            </button>
          </form>

          {/* Audit Results display */}
          <div className="sandbox-results-area">
            {auditLoading && (
              <div className="sandbox-loader">
                <div className="spinner"></div>
                <p>Analyzing wordings and syntax variants...</p>
              </div>
            )}
            
            {auditError && (
              <div className="sandbox-error">
                <p>⚠️ Audit Error: {auditError}</p>
              </div>
            )}

            {auditResult && (
              <div className={`audit-result-card ${auditResult.detected ? 'detected' : 'not-detected'}`}>
                {auditResult.detected ? (
                  <>
                    <div className="result-header">
                      <span className="result-badge alert">⚠️ Bias Found</span>
                      <span className={`result-severity ${auditResult.severity}`}>{auditResult.severity.toUpperCase()}</span>
                    </div>
                    <h4>{auditResult.title}</h4>
                    
                    <div className="result-comparison">
                      {auditResult.original && auditResult.original !== 'N/A' && (
                        <div className="result-row">
                          <span className="res-lbl">Original Term:</span>
                          <span className="res-val greek-text">{auditResult.original}</span>
                        </div>
                      )}
                      {auditResult.literal && (
                        <div className="result-row">
                          <span className="res-lbl">Literal Meaning:</span>
                          <span className="res-val italic">"{auditResult.literal}"</span>
                        </div>
                      )}
                      {auditResult.target_text && (
                        <div className="result-row">
                          <span className="res-lbl">Shifted Translation ({auditResult.target_translation}):</span>
                          <span className="res-val shifted">"{auditResult.target_text}"</span>
                        </div>
                      )}
                    </div>

                    <p className="result-explanation">{auditResult.explanation}</p>
                    
                    {auditResult.scholar && (
                      <div className="result-scholar">
                        <span>🎓 Critic Citation: <strong>{auditResult.scholar}</strong></span>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="no-bias-detected">
                    <span className="ok-icon">✓</span>
                    <h4>No Significant Bias Detected</h4>
                    <p>{auditResult.explanation}</p>
                  </div>
                )}

                {/* Show dynamic translation comparisons fetched for the audited verse */}
                {auditResult.translations && Object.keys(auditResult.translations).length > 0 && (
                  <div className="audited-translations-comparison">
                    <h5>Verse Translations in Database:</h5>
                    <div className="audited-trans-grid">
                      {Object.entries(auditResult.translations).map(([code, text]) => (
                        <div key={code} className="audited-trans-item">
                          <span className="code-badge">{code.toUpperCase()}</span>
                          <p className="trans-text">{text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {!auditLoading && !auditResult && !auditError && (
              <div className="sandbox-prompt-placeholder">
                <span>🤖</span>
                <p>Results will be displayed here after audit.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ResearchHub;
