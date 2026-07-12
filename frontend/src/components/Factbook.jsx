import { useState } from 'react'
import { MOCK_FACTBOOK_TOPICS } from '../data/factbookData'
import { DEMO_ENABLED } from '../config/runtime'
import './Factbook.css'

// Reusable FactbookTopicCard Component
function FactbookTopicCard({ topic, isActive, onClick }) {
  const getCategoryClass = (cat) => {
    switch (cat?.toLowerCase()) {
      case 'canon': return 'cat-canon'
      case 'geography': return 'cat-geography'
      case 'race & power': return 'cat-race'
      case 'manuscript': return 'cat-manuscript'
      case 'theology': return 'cat-theology'
      case 'history': return 'cat-history'
      default: return 'cat-history'
    }
  }

  const getThumbnail = (slug) => {
    switch (slug) {
      case 'cush-ethiopia': return '/assets/path_biblical_geography.png'
      case 'queen-of-sheba': return '/assets/path_african_people.png'
      case 'ethiopian-eunuch': return '/assets/path_african_people.png'
      case 'moses-cushite-wife': return '/assets/path_african_people.png'
      case '1-enoch': return '/assets/path_ethiopian_canon.png'
      case 'jubilees': return '/assets/path_ethiopian_canon.png'
      case 'meqabyan': return '/assets/path_ethiopian_canon.png'
      case 'axum': return '/assets/path_biblical_geography.png'
      case 'nubia': return '/assets/path_biblical_geography.png'
      case 'egypt-in-scripture': return '/assets/path_biblical_geography.png'
      case 'simon-of-cyrene': return '/assets/path_african_people.png'
      case 'african-church-fathers': return '/assets/path_ancient_terms.png'
      default: return '/assets/path_ethiopian_canon.png'
    }
  }

  return (
    <button 
      className={`topic-card-btn ${isActive ? 'active' : ''}`}
      onClick={onClick}
      aria-pressed={isActive}
    >
      <div className="topic-card-layout-row">
        <img src={getThumbnail(topic.slug)} alt={topic.title} className="topic-thumbnail-img" />
        <div className="topic-card-details-col">
          <div className="card-header-row">
            <span className="topic-title-txt">{topic.title}</span>
            <span className={`cat-badge ${getCategoryClass(topic.category)}`}>
              {topic.category}
            </span>
          </div>
          <p className="topic-summary-txt">{topic.summary}</p>
        </div>
        <span className="topic-star-icon" title="Bookmark research topic">☆</span>
      </div>
    </button>
  )
}

// Reusable ResearchPathCard Component
function ResearchPathCard({ title, desc, image, onClick }) {
  return (
    <button className="research-path-card" onClick={onClick}>
      <div className="path-glow-effect"></div>
      {image && (
        <div className="path-img-wrapper">
          <img src={image} alt={title} className="path-banner-img" />
        </div>
      )}
      <div className="path-card-content">
        <h4>{title}</h4>
        <p>{desc}</p>
        <span className="explore-path-arrow">Explore Path ➔</span>
      </div>
    </button>
  )
}

// Reusable CriticalAlertCard Component
function CriticalAlertCard({ title, desc, severity, onClick }) {
  const getSeverityClass = (sev) => {
    switch (sev?.toLowerCase()) {
      case 'severe': return 'sev-severe'
      case 'high': return 'sev-high'
      case 'medium': return 'sev-medium'
      default: return 'sev-medium'
    }
  }

  return (
    <button className={`critical-alert-card ${getSeverityClass(severity)}`} onClick={onClick}>
      <div className="alert-header">
        <span className="alert-icon">⚠️</span>
        <span className="alert-title">{title}</span>
        <span className="severity-lbl">{severity.toUpperCase()}</span>
      </div>
      <p className="alert-desc">{desc}</p>
    </button>
  )
}

// Reusable FactbookInspector Component
function FactbookInspector({ selectedTopic, onQuestionClick }) {
  const suggestedQuestions = [
    "Why does the Ethiopian Bible matter?",
    "What books are missing from Western canons?",
    "How was scripture used to justify slavery?",
    "Where does Africa appear in the Bible?",
    "What is the role of Ge’ez?"
  ]

  const keyFacts = [
    "The Ethiopian Orthodox Tewahedo tradition preserves one of Christianity’s broadest biblical canons.",
    "1 Enoch and Jubilees are preserved in the Ethiopian tradition and are important for understanding Second Temple Jewish and early Christian thought.",
    "Cush and Ethiopia should be treated as central biblical regions, not peripheral references.",
    "The so-called Curse of Ham was historically misused to justify anti-Black racism, even though the biblical text curses Canaan, not Ham."
  ]

  const checklist = [
    "Research deeply with historical context",
    "Compare translations and canons",
    "Identify bias and misuse of scripture",
    "Recover African voices and perspectives",
    "Build truth-centered study notes"
  ]

  if (!selectedTopic) {
    return (
      <div className="inspector-panel-wrapper">
        <div className="inspector-header">
          <span className="inspector-icon">📖</span>
          <h3>Start Here</h3>
        </div>

        <div className="inspector-section">
          <h4>Suggested Questions</h4>
          <div className="suggested-questions-list">
            {suggestedQuestions.map((q, idx) => (
              <button 
                key={idx} 
                className="question-link-btn"
                onClick={() => onQuestionClick(q)}
              >
                <span>{q}</span>
                <span className="arrow">➔</span>
              </button>
            ))}
          </div>
        </div>

        <div className="inspector-section">
          <h4>Key Facts</h4>
          <ul className="key-facts-ul">
            {keyFacts.map((fact, idx) => (
              <li key={idx}>
                <span className="fact-num">{idx + 1}</span>
                <p>{fact}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="inspector-section">
          <h4>What You Can Do Here</h4>
          <ul className="checklist-ul">
            {checklist.map((item, idx) => (
              <li key={idx}>
                <span className="check-box">✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  return (
    <div className="inspector-panel-wrapper active-topic">
      <div className="inspector-header">
        <span className="inspector-icon">🔍</span>
        <h3>Article Inspector</h3>
      </div>

      <div className="inspector-section">
        <h4>Summary</h4>
        <p className="topic-summary-detail font-serif">"{selectedTopic.summary}"</p>
      </div>

      <div className="inspector-section">
        <h4>Scripture References</h4>
        <div className="ref-pills-list">
          {selectedTopic.scripture_references?.map((ref, idx) => (
            <span key={idx} className="ref-pill">{ref}</span>
          )) || <span className="no-refs">None cataloged.</span>}
        </div>
      </div>

      <div className="inspector-section">
        <h4>Ethiopian Canon Relevance</h4>
        <p className="relevance-short-text">{selectedTopic.ethiopian_canon_relevance || 'Centrally integrated into classical EOTC scribal lineages.'}</p>
      </div>

      <div className="inspector-section">
        <h4>Related Bias Alerts</h4>
        <ul className="bias-alerts-ul">
          {selectedTopic.bias_alerts?.map((alert, idx) => (
            <li key={idx}>
              <span className="bullet">⚠️</span>
              <span>{alert}</span>
            </li>
          )) || <li>No bias warnings.</li>}
        </ul>
      </div>

      <div className="inspector-section">
        <h4>Related Map Locations</h4>
        <div className="location-chips-list">
          {selectedTopic.map_locations?.map((loc, idx) => (
            <span key={idx} className="location-chip">📍 {loc}</span>
          )) || <span className="no-locs">None cataloged.</span>}
        </div>
      </div>

      <div className="inspector-section">
        <h4>Related Study Questions</h4>
        <ul className="study-questions-ul">
          {selectedTopic.study_questions?.map((q, idx) => (
            <li key={idx}>{q}</li>
          )) || <li>None compiled yet.</li>}
        </ul>
      </div>
    </div>
  )
}

function Factbook() {
  const [searchTerm, setSearchTerm] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [selectedTopic, setSelectedTopic] = useState(null)
  const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'hermeneutics' | 'manuscripts'

  if (!DEMO_ENABLED) return <div className="empty-workspace-card"><h2>Factbook entries are not loaded</h2><p>Run the factbook ingestion workflow to publish verified production entries.</p></div>
  
  // Toggle filters
  const filters = [
    'Ethiopian Canon',
    'African Biblical Figures',
    'Geography',
    'Manuscripts',
    'Race & Scripture Misuse',
    'Translation Bias',
    'Early Church',
    'Empire & Colonization'
  ]

  const handleFilterClick = (filterName) => {
    setActiveFilter(prev => prev === filterName ? '' : filterName)
  }

  // Filter topics
  const filteredTopics = MOCK_FACTBOOK_TOPICS.filter(topic => {
    // Search matches title, summary or content
    const matchesSearch = 
      topic.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      topic.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
      topic.content.toLowerCase().includes(searchTerm.toLowerCase())

    if (!matchesSearch) return false
    
    // Category mapping filters
    if (!activeFilter) return true
    
    switch (activeFilter) {
      case 'Ethiopian Canon':
        return topic.category === 'Canon'
      case 'African Biblical Figures':
        return topic.category === 'History' || ['ethiopian-eunuch', 'moses-cushite-wife', 'queen-of-sheba', 'simon-of-cyrene', 'african-church-fathers'].includes(topic.slug)
      case 'Geography':
        return topic.category === 'Geography'
      case 'Manuscripts':
        return topic.category === 'Canon' || (topic.witnesses && topic.witnesses.length > 0)
      case 'Race & Scripture Misuse':
        return topic.category === 'Race & Power'
      case 'Translation Bias':
        return topic.bias_alerts && topic.bias_alerts.length > 0
      case 'Early Church':
        return topic.category === 'Theology' || topic.slug === 'african-church-fathers'
      case 'Empire & Colonization':
        return topic.category === 'Race & Power' || topic.slug === 'african-church-fathers'
      default:
        return true
    }
  })

  // Deep linking for suggested questions
  const handleQuestionClick = (question) => {
    if (question.includes('Ethiopian Bible matter')) {
      handleSelectTopic('1-enoch')
    } else if (question.includes('missing from Western canons')) {
      handleSelectTopic('1-enoch')
    } else if (question.includes('justify slavery')) {
      handleSelectTopic('moses-cushite-wife')
    } else if (question.includes('Africa appear')) {
      handleSelectTopic('cush-ethiopia')
    } else if (question.includes('role of Ge’ez')) {
      handleSelectTopic('axum')
    }
  }

  const handleSelectTopic = (slug) => {
    const topic = MOCK_FACTBOOK_TOPICS.find(t => t.slug === slug)
    if (topic) {
      setSelectedTopic(topic)
      setActiveTab('overview')
    }
  }

  // Dashboard card click mappings
  const handleFeatureCardClick = (type) => {
    if (type === 'canon') {
      setActiveFilter('Ethiopian Canon')
      setSearchTerm('')
    } else if (type === 'presence') {
      setActiveFilter('African Biblical Figures')
      setSearchTerm('')
    } else if (type === 'misuse') {
      setActiveFilter('Race & Scripture Misuse')
      setSearchTerm('')
    } else if (type === 'manuscripts') {
      setActiveFilter('Manuscripts')
      setSearchTerm('')
    }
  }

  const handleAlertClick = (type) => {
    if (type === 'ham') {
      handleSelectTopic('cush-ethiopia')
    } else if (type === 'solomon') {
      handleSelectTopic('cush-ethiopia')
      setSearchTerm('Song of Solomon')
    } else if (type === 'slavery') {
      handleSelectTopic('moses-cushite-wife')
    } else if (type === 'missionary') {
      handleSelectTopic('ethiopian-eunuch')
    } else if (type === 'codes') {
      handleSelectTopic('moses-cushite-wife')
      setSearchTerm('codes')
    }
  }

  const handlePathClick = (type) => {
    if (type === 'canon') {
      handleSelectTopic('1-enoch')
    } else if (type === 'people') {
      setActiveFilter('African Biblical Figures')
      setSearchTerm('')
    } else if (type === 'misuse') {
      setActiveFilter('Race & Scripture Misuse')
      setSearchTerm('')
    } else if (type === 'bias') {
      setActiveFilter('Translation Bias')
      setSearchTerm('')
    } else if (type === 'terms') {
      handleSelectTopic('1-enoch')
      setSearchTerm("Ge'ez")
    } else if (type === 'geography') {
      setActiveFilter('Geography')
      setSearchTerm('')
    }
  }

  return (
    <div className="factbook-container">
      <div className="factbook-layout">
        
        {/* LEFT SIDEBAR: Catalog Selector */}
        <div className="topics-sidebar">
          <div className="sidebar-header">
            <h3>Factbook Encyclopedia</h3>
            <p className="sidebar-desc">
              Scholarly biblical history grounded in the Ethiopian canon, East African monotheism, Nile Valley geography, and decolonial critique.
            </p>
            
            <div className="search-wrapper">
              <input 
                type="text" 
                placeholder="Search Cush, Ethiopia, Enoch, Sheba..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="topic-search-input"
              />
              {searchTerm && (
                <button className="clear-search-btn" onClick={() => setSearchTerm('')}>×</button>
              )}
            </div>

            <div className="filter-chips-grid">
              {filters.map(f => (
                <button 
                  key={f}
                  className={`filter-chip-btn ${activeFilter === f ? 'active' : ''}`}
                  onClick={() => handleFilterClick(f)}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="topics-catalog-section">
            <div className="catalog-header-row">
              <span>Catalog of Topics</span>
              <span className="sample-badge">Sample Research Data</span>
            </div>
            
            <div className="topics-list-scrollable">
              {filteredTopics.length > 0 ? (
                filteredTopics.map(t => (
                  <FactbookTopicCard 
                    key={t.slug}
                    topic={t}
                    isActive={selectedTopic?.slug === t.slug}
                    onClick={() => handleSelectTopic(t.slug)}
                  />
                ))
              ) : (
                <div className="empty-catalog-results">
                  <p>No matching topics found. Clear filters or search term to see all.</p>
                  <button className="reset-catalog-btn" onClick={() => { setSearchTerm(''); setActiveFilter(''); }}>
                    Reset Filters
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* CENTER PANEL: Dashboard or Article details */}
        <div className="center-workspace-panel">
          {!selectedTopic ? (
            <div className="dashboard-view-mode">
              
              {/* Hero Banner */}
              <div className="hero-banner-card">
                <div className="hero-glow-back"></div>
                <h2>Explore the Bible Through the Ethiopian Canon</h2>
                <p>
                  The Factbook connects scripture, canon history, African geography, translation bias, historical misuse, and decolonial interpretation into one research workspace.
                </p>
              </div>

              {/* Feature Cards Grid */}
              <div className="features-card-grid">
                <button className="dashboard-feat-card" onClick={() => handleFeatureCardClick('canon')}>
                  <div className="feat-icon">📜</div>
                  <h4>Ethiopian Canon</h4>
                  <p>Study books preserved in the Ethiopian tradition, including 1 Enoch, Jubilees, and Meqabyan.</p>
                </button>
                <button className="dashboard-feat-card" onClick={() => handleFeatureCardClick('presence')}>
                  <div className="feat-icon">🌍</div>
                  <h4>African Presence in Scripture</h4>
                  <p>Explore Cush, Ethiopia, Egypt, Nubia, Cyrene, the Queen of Sheba, and the Ethiopian eunuch.</p>
                </button>
                <button className="dashboard-feat-card" onClick={() => handleFeatureCardClick('misuse')}>
                  <div className="feat-icon">⚖️</div>
                  <h4>Race & Scripture Misuse</h4>
                  <p>Identify how selected passages were misused to justify slavery, segregation, colonization, and anti-Black theology.</p>
                </button>
                <button className="dashboard-feat-card" onClick={() => handleFeatureCardClick('manuscripts')}>
                  <div className="feat-icon">🗃️</div>
                  <h4>Manuscripts & Translation History</h4>
                  <p>Compare Ge’ez, Hebrew, Greek, Latin, and English traditions where available.</p>
                </button>
              </div>

              {/* Featured Research Paths */}
              <div className="dashboard-section">
                <div className="sec-header">
                  <h3>Featured Research Paths</h3>
                </div>
                <div className="paths-grid">
                  <ResearchPathCard 
                    title="Ethiopian Canon & Missing Books" 
                    desc="Understand what was preserved in East Africa and deleted in Western councils."
                    image="/assets/path_ethiopian_canon.png"
                    onClick={() => handlePathClick('canon')}
                  />
                  <ResearchPathCard 
                    title="African People in Scripture" 
                    desc="Discover the identity, role, and impact of Africans in the Bible."
                    image="/assets/path_african_people.png"
                    onClick={() => handlePathClick('people')}
                  />
                  <ResearchPathCard 
                    title="Scripture Used Against People of Color" 
                    desc="Exposing the misuse of scripture for power and oppression."
                    image="/assets/path_scripture_chains.png"
                    onClick={() => handlePathClick('misuse')}
                  />
                  <ResearchPathCard 
                    title="Translation Bias and Race" 
                    desc="See how translation choices shaped theology and ideology."
                    image="/assets/path_translation_bias.png"
                    onClick={() => handlePathClick('bias')}
                  />
                  <ResearchPathCard 
                    title="Ge’ez, Hebrew, Greek, and Aramaic Terms" 
                    desc="Study original words and their true meanings."
                    image="/assets/path_ancient_terms.png"
                    onClick={() => handlePathClick('terms')}
                  />
                  <ResearchPathCard 
                    title="Biblical Geography of Africa and the Nile Valley" 
                    desc="Explore sacred places, routes, and ancient kingdoms."
                    image="/assets/path_biblical_geography.png"
                    onClick={() => handlePathClick('geography')}
                  />
                </div>
              </div>

              {/* Critical Study Alerts */}
              <div className="dashboard-section">
                <div className="sec-header">
                  <h3>Critical Study Alerts</h3>
                </div>
                <div className="alerts-grid">
                  <CriticalAlertCard 
                    title="Curse of Ham / Canaan Misuse" 
                    desc="Historically used to justify anti-Black racism and chattel slavery."
                    severity="severe"
                    onClick={() => handleAlertClick('ham')}
                  />
                  <CriticalAlertCard 
                    title="Song of Solomon 1:5 and Colorism" 
                    desc="Mistranslated as 'black but comely' to promote colorist aesthetics."
                    severity="high"
                    onClick={() => handleAlertClick('solomon')}
                  />
                  <CriticalAlertCard 
                    title="Slavery and Servitude Texts" 
                    desc="Context often removed to justify chattel slavery and master-slave hierarchies."
                    severity="high"
                    onClick={() => handleAlertClick('slavery')}
                  />
                  <CriticalAlertCard 
                    title="Colonial Missionary Interpretation" 
                    desc="Used to legitimize conquest and cultural domination in Africa."
                    severity="medium"
                    onClick={() => handleAlertClick('missionary')}
                  />
                  <CriticalAlertCard 
                    title="Household Codes and Oppression" 
                    desc="Texts isolated to silence dissent and maintain imperial control."
                    severity="medium"
                    onClick={() => handleAlertClick('codes')}
                  />
                </div>
              </div>

            </div>
          ) : (
            <div className="article-view-mode">
              
              <div className="article-navigation-bar">
                <button className="back-to-dashboard-btn" onClick={() => setSelectedTopic(null)}>
                  🗎 Back to Research Dashboard
                </button>
              </div>

              <div className="article-header">
                <span className="region-badge">{selectedTopic.geographical_region}</span>
                <h2>{selectedTopic.title}</h2>
                <p className="article-summary-lead">"{selectedTopic.summary}"</p>
              </div>

              <div className="article-tabs">
                <button 
                  className={`tab-link ${activeTab === 'overview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('overview')}
                >
                  📜 Historical Overview
                </button>
                <button 
                  className={`tab-link ${activeTab === 'hermeneutics' ? 'active' : ''}`}
                  onClick={() => setActiveTab('hermeneutics')}
                >
                  ⚖️ Decolonial Hermeneutics
                </button>
                <button 
                  className={`tab-link ${activeTab === 'manuscripts' ? 'active' : ''}`}
                  onClick={() => setActiveTab('manuscripts')}
                >
                  🗄️ Manuscript Witnesses ({selectedTopic.witnesses?.length || 0})
                </button>
              </div>

              <div className="tab-pane-content">
                {activeTab === 'overview' && (
                  <div className="overview-pane animate-fade-in">
                    <div className="article-content-body font-serif">
                      <p>{selectedTopic.content}</p>
                    </div>

                    {selectedTopic.ethiopian_canon_relevance && (
                      <div className="relevance-callout">
                        <h4>Ethiopian Canon Relevance</h4>
                        <p>{selectedTopic.ethiopian_canon_relevance}</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'hermeneutics' && (
                  <div className="hermeneutics-pane animate-fade-in">
                    <div className="hermeneutics-grid">
                      <div className="hermeneutics-card western">
                        <span className="card-tag">Western Eurocentric Interpretation</span>
                        <p>{selectedTopic.western_interpretation || 'Historically marginalized or omitted from mainstream Western Bible study reference manuals.'}</p>
                      </div>
                      
                      <div className="hermeneutics-card orthodox">
                        <span className="card-tag">Ethiopian Orthodox Tradition</span>
                        <p>{selectedTopic.ethiopian_interpretation || 'Preserved in Ge\'ez liturgy, homilies, and manuscript commentary lines.'}</p>
                      </div>
                      
                      <div className="hermeneutics-card decolonial">
                        <span className="card-tag">Decolonial / Liberationist Reading</span>
                        <p>{selectedTopic.decolonial_interpretation || 'Reclaims the political, racial, and spiritual agency of the African continent.'}</p>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'manuscripts' && (
                  <div className="manuscripts-pane animate-fade-in">
                    <h4>Historical Manuscripts & Attestations</h4>
                    <p className="pane-intro">Archeological documents supporting the text's antiquity and independent preservation path:</p>
                    
                    <div className="witnesses-list">
                      {selectedTopic.witnesses && selectedTopic.witnesses.length > 0 ? (
                        selectedTopic.witnesses.map(w => (
                          <div key={w.id} className="witness-item-card">
                            <div className="witness-header">
                              <h5>{w.name}</h5>
                              <span className="witness-meta-tag">{w.type} · {w.date}</span>
                            </div>
                            <p><strong>Language:</strong> {w.language}</p>
                            <p className="witness-sig"><strong>Significance:</strong> {w.significance}</p>
                          </div>
                        ))
                      ) : (
                        <p className="empty-list-text">No specific manuscript witnesses cataloged for this entry.</p>
                      )}
                    </div>
                  </div>
                )}
              </div>

            </div>
          )}
        </div>

        {/* RIGHT SIDEBAR: Article Inspector */}
        <div className="inspector-sidebar-panel">
          <FactbookInspector 
            selectedTopic={selectedTopic} 
            onQuestionClick={handleQuestionClick}
          />
        </div>

      </div>
    </div>
  )
}

export default Factbook
