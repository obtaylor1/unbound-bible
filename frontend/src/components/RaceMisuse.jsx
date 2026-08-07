import { useState, useEffect } from 'react'
import './RaceMisuse.css'

function RaceMisuse() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [activeRecord, setActiveRecord] = useState(null)
  
  // Custom Sermon Auditor state
  const [sermonText, setSermonText] = useState('')
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditResult, setAuditResult] = useState(null)

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const res = await fetch('/api/v1/race-misuse')
        if (res.ok) {
          const data = await res.json()
          setRecords(data || [])
          if (data.length > 0) {
            setActiveRecord(data[0])
          }
        }
      } catch (err) {
        console.error('Failed to fetch race misuse records:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchRecords()
  }, [])

  const filteredRecords = records.filter(r => 
    r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.book.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.historical_misuse.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleSermonAudit = async (e) => {
    e.preventDefault()
    if (!sermonText.trim()) return
    
    setAuditLoading(true)
    setAuditResult(null)
    
    try {
      const res = await fetch('/api/v1/sermon/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript_text: sermonText,
          title: 'User Pasted Sermon Audit',
          speaker: 'Audited Sermon'
        })
      })
      if (res.ok) {
        const data = await res.json()
        setAuditResult(data)
      }
    } catch (err) {
      console.error('Sermon audit failed:', err)
    } finally {
      setAuditLoading(false)
    }
  }

  const loadSampleSermon = (type) => {
    if (type === 'ham') {
      setSermonText(`My brothers, when we look at the history of nations, we see God's design. In Genesis chapter 9, Noah pronounced a decree: 'Cursed be Canaan; a servant of servants shall he be.' This curse of Ham, my friends, was a divine setup. God marked Ham's descendants, who went to live in the dark continents, to serve the descendants of Shem and Japheth. It is a biological and theological truth that servitude is ordained for certain lines...`)
    } else if (type === 'slavery') {
      setSermonText(`Let us look to Ephesians 6:5, where the Apostle Paul commands us: 'Servants, be obedient to them that are your masters according to the flesh, with fear and trembling.' This shows that God supports order and structure. Slavery, as an institution, was blessed by scripture, and those who try to rebel or run away are violating the direct command of the Apostle to serve their masters as they would serve Christ...`)
    } else if (type === 'clean') {
      setSermonText(`Let us reflect on the great love of God. The scriptures teach us in John 3:16 that God so loved the world that He gave His only begotten Son. This love is not restricted by race, color, or nation. In Galatians, Paul declares that there is neither Jew nor Greek, slave nor free, for you are all one in Christ Jesus. Let us walk in justice and mutual love, honoring one another as brothers and sisters in Christ.`)
    }
  }

  const getSeverityLabel = (severity) => {
    switch (severity) {
      case 'red': return 'Critical (Chattel Slavery / White Supremacy)'
      case 'orange': return 'High (Colorism / Structural Oppression)'
      case 'purple': return 'Identity / Geographic Erasure'
      default: return 'Ideological Bias'
    }
  }

  return (
    <div className="race-misuse-container">
      <div className="race-layout">
        
        {/* Left Side: Records List & Sermon Auditor */}
        <div className="left-panel">
          <div className="panel-header">
            <h2>Race & Scripture Misuse</h2>
            <p>Auditing how translations and interpretations were weaponized historically to support white supremacy, colonization, and racial subjugation.</p>
          </div>

          <div className="search-box-container">
            <input 
              type="text" 
              placeholder="Search flagged passages or topics..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <span>Loading flagged scriptures...</span>
            </div>
          ) : (
            <div className="records-list">
              {filteredRecords.map(r => (
                <div 
                  key={r.id} 
                  className={`record-card ${activeRecord?.id === r.id ? 'active' : ''}`}
                  onClick={() => setActiveRecord(r)}
                >
                  <div className="card-header">
                    <span className="reference-tag">{r.book} {r.chapter}:{r.verse}</span>
                    <span className={`severity-badge ${r.severity}`}>{r.severity.toUpperCase()}</span>
                  </div>
                  <h4>{r.title}</h4>
                  <p>{r.historical_misuse.slice(0, 120)}...</p>
                </div>
              ))}
            </div>
          )}

          {/* Decolonial Sermon Auditor Section */}
          <div className="sermon-auditor-card">
            <h3>Decolonial Sermon Auditor</h3>
            <p className="section-desc">Paste a sermon transcript to scan it for scripture misuse, white supremacist theology, or translation errors.</p>
            
            <div className="sample-buttons">
              <button onClick={() => loadSampleSermon('ham')} className="sample-btn">Sample 1: Curse of Ham</button>
              <button onClick={() => loadSampleSermon('slavery')} className="sample-btn">Sample 2: Slavery Codes</button>
              <button onClick={() => loadSampleSermon('clean')} className="sample-btn">Sample 3: Egalitarian Message</button>
            </div>

            <form onSubmit={handleSermonAudit}>
              <textarea 
                value={sermonText}
                onChange={(e) => setSermonText(e.target.value)}
                placeholder="Enter sermon text here to audit..."
                rows={5}
                className="sermon-textarea"
              />
              <button type="submit" disabled={auditLoading || !sermonText} className="audit-submit-btn">
                {auditLoading ? 'Auditing Transcript...' : 'Run Decolonial Audit'}
              </button>
            </form>

            {auditResult && (
              <div className="audit-results-panel">
                {auditResult.grounding_status === 'insufficient_evidence' && (
                  <p className="section-desc" role="status">{auditResult.message}</p>
                )}
                <div className="audit-score-header">
                  <h4>Audit Report</h4>
                  <div className={`score-badge ${auditResult.metrics.accuracy_score >= 80 ? 'good' : auditResult.metrics.accuracy_score >= 60 ? 'warning' : 'bad'}`}>
                    Exegesis Score: {auditResult.metrics.accuracy_score}%
                  </div>
                </div>

                {auditResult.claims.map((claim, idx) => (
                  <div key={idx} className={`audit-claim-card ${claim.status}`}>
                    <div className="claim-header">
                      <span className="claim-category">{claim.category.toUpperCase()} CLAIM</span>
                      <span className={`claim-status-badge ${claim.status}`}>{claim.status.toUpperCase()}</span>
                    </div>
                    <p className="claim-text">"{claim.claim_text}"</p>
                    <div className="claim-explanation">
                      <strong>Auditor Alert:</strong> {claim.explanation}
                    </div>
                    <div className="claim-corrective">
                      <strong>Decolonial Corrective:</strong> {claim.correction}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Detailed Corrective Exegesis Panel */}
        <div className="right-panel">
          {activeRecord ? (
            <div className="details-view">
              <div className="details-header">
                <span className={`severity-tag ${activeRecord.severity}`}>
                  {getSeverityLabel(activeRecord.severity)}
                </span>
                <h2>{activeRecord.title}</h2>
                <div className="reference-header">
                  <span>Scripture Witness:</span>
                  <strong>{activeRecord.book} {activeRecord.chapter}:{activeRecord.verse}</strong>
                </div>
              </div>

              <div className="detail-section">
                <h3>Historical Misuse</h3>
                <div className="detail-box misuse-box">
                  <p>{activeRecord.historical_misuse}</p>
                </div>
              </div>

              <div className="detail-section">
                <h3>Harm Inflicted</h3>
                <div className="detail-box harm-box">
                  <p>{activeRecord.harm_caused || 'Reinforced systematic structural hierarchy, justification of race-based dominance, and colonization.'}</p>
                </div>
              </div>

              <div className="detail-section">
                <h3>Decolonial & Corrective Exegesis</h3>
                <div className="detail-box corrective-box">
                  <p>{activeRecord.corrective_interpretation}</p>
                </div>
              </div>

              {activeRecord.ethiopian_perspective && (
                <div className="detail-section">
                  <h3>Ethiopian Orthodox Perspective</h3>
                  <div className="detail-box ethiopian-box">
                    <p>{activeRecord.ethiopian_perspective}</p>
                  </div>
                </div>
              )}

              {activeRecord.decolonial_perspective && (
                <div className="detail-section">
                  <h3>Womanist / Decolonial Midrash</h3>
                  <div className="detail-box decolonial-box">
                    <p>{activeRecord.decolonial_perspective}</p>
                  </div>
                </div>
              )}

              {activeRecord.study_notes && (
                <div className="detail-section">
                  <h3>Study Notes & References</h3>
                  <p className="study-notes-text">{activeRecord.study_notes}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-details">
              <span className="huge-icon">⚖</span>
              <p>Select a flagged scripture card on the left to inspect its historical misuse, harm caused, and decolonial corrective exegesis.</p>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}

export default RaceMisuse
