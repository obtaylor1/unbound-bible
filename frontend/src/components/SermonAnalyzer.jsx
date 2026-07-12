import { useState, useRef } from 'react'
import './SermonAnalyzer.css'
import { credentials } from '../api/client'

function SermonAnalyzer({ onPageChange }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [highlightedTime, setHighlightedTime] = useState(null)
  
  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      const allowedExtensions = ['.mp3', '.wav', '.m4a']
      const filename = selectedFile.name.toLowerCase()
      const isValidExt = allowedExtensions.some(ext => filename.endsWith(ext))
      
      if (!isValidExt) {
        setError('Please select a valid audio file (.mp3, .wav, .m4a)')
        return
      }
      setFile(selectedFile)
      setError(null)
      setAnalysis(null)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      const allowedExtensions = ['.mp3', '.wav', '.m4a']
      const filename = droppedFile.name.toLowerCase()
      const isValidExt = allowedExtensions.some(ext => filename.endsWith(ext))
      
      if (!isValidExt) {
        setError('Please select a valid audio file (.mp3, .wav, .m4a)')
        return
      }
      setFile(droppedFile)
      setError(null)
      setAnalysis(null)
    }
  }

  const analyzeSermon = async () => {
    if (!file) {
      setError('Please select an audio file first')
      return
    }

    setUploading(true)
    setError(null)
    setAnalysis(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/v1/analyze/sermon', {
          method: 'POST',
          headers: credentials.accessToken ? { 'Authorization': `Bearer ${credentials.accessToken}` } : {},
          body: formData
        })
      if (!response.ok) throw new Error(`Sermon analysis is unavailable (${response.status}). Your file was not saved.`)
      const result = await response.json()

      setAnalysis(result)
      setActiveTab('overview')
    } catch (err) {
      setError(err.message)
      console.error('Sermon analysis error:', err)
    } finally {
      setUploading(false)
    }
  }

  const formatTime = (seconds) => {
    return `${seconds.toFixed(1)}s`
  }

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'green': return 'badge-emerald'
      case 'yellow': return 'badge-warning'
      case 'red': return 'badge-red'
      case 'purple': return 'badge-purple'
      case 'blue': return 'badge-blue'
      default: return 'badge-purple'
    }
  }

  const getMetricColor = (score) => {
    if (score >= 80) return 'text-emerald'
    if (score >= 60) return 'text-warning'
    return 'text-red'
  }

  const triggerChooseFile = () => {
    fileInputRef.current?.click()
  }

  const resetAnalyzer = () => {
    setFile(null)
    setAnalysis(null)
    setError(null)
  }

  const handleRecentClick = (filename) => {
    setFile({ name: filename, size: 45000000 })
    setError('This prior analysis is not stored on the server yet. Upload the original file to analyze it again.')
    setAnalysis(null)
  }

  return (
    <div className="ub-sermon-layout">
      {/* Header */}
      <div className="sermon-header-block">
        <h1>Sermon Analysis <span className="sparkle-glow">✦</span></h1>
        <p>Upload and analyze sermons for biblical and historical context.</p>
        <div className="gold-glow-line"></div>
      </div>

      <div className="ub-content-grid">
        {/* Left Column */}
        <div className="ub-main-column">
          <section className="ub-main-card">
            <div className="card-header-row-sermon">
              <div className="card-title-grp">
                <span className="mic-icon">🎙️</span>
                <h2>Sermon Geography & Exegesis Auditor</h2>
              </div>
              <span className="ai-badge-purple">AI-Powered Context Analysis</span>
            </div>
            
            <p className="card-lead-subtitle">
              Upload a sermon audio file to respectfully cross-reference scripture quotes, linguistic translations, and geography claims.
            </p>

            {error && (
              <div className="error-message-banner">
                <p>⚠️ <strong>Error:</strong> {error}</p>
              </div>
            )}

            {/* Conditional Views */}
            {uploading ? (
              <div className="uploading-state-box">
                <div className="loading-spinner-circle"></div>
                <h4>🎙️ Transcribing and Fact-Checking Audio...</h4>
                <p>This may take a moment. We are converting the audio, checking scripture alignments, and auditing historical geography claims.</p>
              </div>
            ) : analysis ? (
              <div className="analysis-results-container">
                <div className="back-btn-row">
                  <button className="back-to-upload-btn" onClick={resetAnalyzer}>
                    ← Upload Another Sermon
                  </button>
                </div>

                {/* Dashboard Metrics */}
                <div className="metrics-dashboard-box">
                  <h3>📊 Visual Analysis Dashboard</h3>
                  <div className="metrics-grid">
                    <div className="metric-card-gauge">
                      <span className="metric-title">Accuracy Score</span>
                      <span className={`metric-value ${getMetricColor(analysis.metrics.accuracy_score)}`}>
                        {analysis.metrics.accuracy_score}%
                      </span>
                      <div className="metric-bar-outer">
                        <div className="metric-bar-fill" style={{ width: `${analysis.metrics.accuracy_score}%`, background: 'linear-gradient(90deg, #8B5CF6, #22C55E)' }}></div>
                      </div>
                    </div>

                    <div className="metric-card-gauge">
                      <span className="metric-title">Scripture Usage</span>
                      <span className={`metric-value ${getMetricColor(analysis.metrics.scripture_usage_score)}`}>
                        {analysis.metrics.scripture_usage_score}%
                      </span>
                      <div className="metric-bar-outer">
                        <div className="metric-bar-fill" style={{ width: `${analysis.metrics.scripture_usage_score}%`, background: 'linear-gradient(90deg, #8B5CF6, #22C55E)' }}></div>
                      </div>
                    </div>

                    <div className="metric-card-gauge">
                      <span className="metric-title">Context Score</span>
                      <span className={`metric-value ${getMetricColor(analysis.metrics.context_score)}`}>
                        {analysis.metrics.context_score}%
                      </span>
                      <div className="metric-bar-outer">
                        <div className="metric-bar-fill" style={{ width: `${analysis.metrics.context_score}%`, background: 'linear-gradient(90deg, #8B5CF6, #22C55E)' }}></div>
                      </div>
                    </div>

                    <div className="metric-card-gauge">
                      <span className="metric-title">Theological Coherence</span>
                      <span className={`metric-value ${getMetricColor(analysis.metrics.theology_consistency_score)}`}>
                        {analysis.metrics.theology_consistency_score}%
                      </span>
                      <div className="metric-bar-outer">
                        <div className="metric-bar-fill" style={{ width: `${analysis.metrics.theology_consistency_score}%`, background: 'linear-gradient(90deg, #8B5CF6, #22C55E)' }}></div>
                      </div>
                    </div>

                    <div className="metric-card-gauge">
                      <span className="metric-title">Fact-Check Confidence</span>
                      <span className="metric-value text-emerald">
                        {analysis.metrics.confidence_level}%
                      </span>
                      <div className="metric-bar-outer">
                        <div className="metric-bar-fill" style={{ width: `${analysis.metrics.confidence_level}%`, background: 'linear-gradient(90deg, #22C55E, #00C4B4)' }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Navigation Tabs */}
                <div className="results-navigation-tabs">
                  <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
                    📋 Overview & Summary
                  </button>
                  <button className={`tab-btn ${activeTab === 'claims' ? 'active' : ''}`} onClick={() => setActiveTab('claims')}>
                    🔍 Fact-Check & Biases ({analysis.claims.length})
                  </button>
                  <button className={`tab-btn ${activeTab === 'transcript' ? 'active' : ''}`} onClick={() => setActiveTab('transcript')}>
                    📝 Timestamps Transcript
                  </button>
                  <button className={`tab-btn ${activeTab === 'study' ? 'active' : ''}`} onClick={() => setActiveTab('study')}>
                    📚 Suggested Study
                  </button>
                </div>

                {/* Tab Contents */}
                <div className="tab-contents-area">
                  {activeTab === 'overview' && (
                    <div className="tab-overview">
                      <div className="overview-header-row">
                        <h3>Topic: {analysis.summary.topic}</h3>
                        <span className="badge-theme">Theme: {analysis.summary.theme}</span>
                      </div>

                      <div className="summary-boxes-grid">
                        <div className="summary-box">
                          <h4>Brief Overview</h4>
                          <p>{analysis.summary.short_summary}</p>
                        </div>

                        <div className="summary-box">
                          <h4>Detailed Analysis Summary</h4>
                          <p>{analysis.summary.detailed_summary}</p>
                        </div>
                      </div>

                      <div className="points-split-grid">
                        <div className="points-box">
                          <h4>Key Sermon Points</h4>
                          <ul>
                            {analysis.summary.key_points.map((point, i) => (
                              <li key={i}>🔹 {point}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="points-box">
                          <h4>Conclusion</h4>
                          <p>{analysis.summary.conclusion}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'claims' && (
                    <div className="tab-claims">
                      <div className="claims-timeline-header">
                        <h3>Verified Claims & Translation Audits</h3>
                        <p className="sub-claims-text">
                          Claims extracted from the sermon transcript compared against original languages and verified historical geography databases.
                        </p>
                      </div>

                      <div className="claims-timeline">
                        {analysis.claims.map((claim, idx) => (
                          <div key={idx} className="claim-timeline-card">
                            <div className="claim-card-header">
                              <span className="claim-timestamp">⏰ {claim.timestamp}</span>
                              <span className={`badge-severity ${getSeverityColor(claim.severity)}`}>
                                {claim.issue_type}
                              </span>
                            </div>
                            
                            <div className="claim-statement-box">
                              <strong>Sermon Statement:</strong>
                              <p className="sermon-quote">"{claim.statement}"</p>
                            </div>

                            <div className="claim-analysis-grid">
                              <div className="claim-explanation">
                                <strong>Scholarly Analysis:</strong>
                                <p>{claim.explanation}</p>
                              </div>
                              <div className="claim-correction">
                                <strong>Corrected Context:</strong>
                                <p className="corrective-emerald">{claim.correction}</p>
                              </div>
                            </div>

                            <div className="claim-references">
                              <strong>References / Scriptures Checked:</strong>
                              <div className="reference-pill-row">
                                {claim.references.map((ref, rIdx) => (
                                  <span key={rIdx} className="ref-pill-badge">{ref}</span>
                                ))}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activeTab === 'transcript' && (
                    <div className="tab-transcript">
                      <h3>Segmented Transcript with Timestamps</h3>
                      <p className="sub-claims-text">
                        Click on any segment's timestamp to highlight or study that section.
                      </p>

                      <div className="transcript-segments-list">
                        {analysis.transcript_segments.map((seg, i) => (
                          <div 
                            key={i} 
                            className={`transcript-segment-row ${highlightedTime === seg.timestamp ? 'highlighted' : ''}`}
                            onClick={() => setHighlightedTime(seg.timestamp)}
                          >
                            <button className="segment-timestamp-btn">
                              ⏰ {seg.timestamp}
                            </button>
                            <p className="segment-text">{seg.text}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activeTab === 'study' && (
                    <div className="tab-study">
                      <h3>Suggested Scholarly Resources</h3>
                      <p className="sub-claims-text">
                        Further reading recommended by academic researchers to verify sermon claims.
                      </p>

                      <div className="further-study-list">
                        {analysis.further_study.map((item, idx) => (
                          <div key={idx} className="further-study-item">
                            <span className="study-icon">🎓</span>
                            <p>{item}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="results-footer-row">
                  <span className="processing-time-badge">
                    Processed in {formatTime(analysis.processing_time)}
                  </span>
                </div>
              </div>
            ) : (
              <div className="upload-interactive-area">
                {/* Upload Zone */}
                <div 
                  className="ub-upload-zone"
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  onClick={triggerChooseFile}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept=".mp3,.wav,.m4a"
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                  />
                  <div className="upload-cloud-icon">☁️</div>
                  <h3>Drop your audio file here or click to browse</h3>
                  <p className="upload-subtext">Supports MP3, WAV, M4A (Max 500MB)</p>
                  
                  {file ? (
                    <div className="selected-sermon-file-box" onClick={(e) => e.stopPropagation()}>
                      <span className="file-name-label">📄 {file.name}</span>
                      <span className="file-size-badge">({(file.size / (1024 * 1024)).toFixed(2)} MB)</span>
                    </div>
                  ) : (
                    <button className="choose-file-btn" type="button">Choose Audio File</button>
                  )}
                </div>

                {file && (
                  <div className="start-audit-btn-container">
                    <button className="start-audit-action-btn" onClick={analyzeSermon}>
                      ⚡ Start Sermon Audit
                    </button>
                  </div>
                )}

                {/* Auditor Feature Cards */}
                <div className="auditor-features-grid">
                  <div className="auditor-feature-card">
                    <div className="feature-top-row">
                      <span className="feature-icon-box">🗺️</span>
                      <h3>Geography Auditor</h3>
                    </div>
                    <p className="feature-desc-text">
                      Detect and verify geographical claims in the sermon using biblical maps and historical records.
                    </p>
                    <div className="checks-label">Checks for:</div>
                    <ul className="checks-list">
                      <li><span className="checkmark-green">✓</span> Places and regions</li>
                      <li><span className="checkmark-green">✓</span> Ancient city references</li>
                      <li><span className="checkmark-green">✓</span> Historical accuracy</li>
                      <li><span className="checkmark-green">✓</span> Cultural context</li>
                    </ul>
                  </div>

                  <div className="auditor-feature-card">
                    <div className="feature-top-row">
                      <span className="feature-icon-box">📖</span>
                      <h3>Exegesis Analyzer</h3>
                    </div>
                    <p className="feature-desc-text">
                      Analyze scripture usage, interpretation methods, and cross-references within the sermon.
                    </p>
                    <div className="checks-label">Checks for:</div>
                    <ul className="checks-list">
                      <li><span className="checkmark-green">✓</span> Scripture accuracy</li>
                      <li><span className="checkmark-green">✓</span> Contextual alignment</li>
                      <li><span className="checkmark-green">✓</span> Cross-references</li>
                      <li><span className="checkmark-green">✓</span> Theological consistency</li>
                    </ul>
                  </div>

                  <div className="auditor-feature-card">
                    <div className="feature-top-row">
                      <span className="feature-icon-box">𐤀</span>
                      <h3>Language & Translation</h3>
                    </div>
                    <p className="feature-desc-text">
                      Evaluate original language terms, translation accuracy, and linguistic interpretation.
                    </p>
                    <div className="checks-label">Checks for:</div>
                    <ul className="checks-list">
                      <li><span className="checkmark-green">✓</span> Key Hebrew, Greek, Ge'ez terms</li>
                      <li><span className="checkmark-green">✓</span> Translation variations</li>
                      <li><span className="checkmark-green">✓</span> Meaning shifts</li>
                      <li><span className="checkmark-green">✓</span> Interpretation impact</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </section>

          {/* What you'll receive */}
          <section className="ub-main-card receive-outcomes-card">
            <h3>What You'll Receive</h3>
            <div className="outcomes-flex-row">
              <div className="outcome-item">
                <span className="outcome-icon">📊</span>
                <div className="outcome-info">
                  <h4>Comprehensive Report</h4>
                  <p>Detailed analysis with findings and recommendations.</p>
                </div>
              </div>
              <div className="outcome-divider"></div>

              <div className="outcome-item">
                <span className="outcome-icon">📍</span>
                <div className="outcome-info">
                  <h4>Interactive Maps</h4>
                  <p>Visualize locations and geographical references.</p>
                </div>
              </div>
              <div className="outcome-divider"></div>

              <div className="outcome-item">
                <span className="outcome-icon">📖</span>
                <div className="outcome-info">
                  <h4>Scripture Cross-Refs</h4>
                  <p>Related verses and contextual connections.</p>
                </div>
              </div>
              <div className="outcome-divider"></div>

              <div className="outcome-item">
                <span className="outcome-icon">💬</span>
                <div className="outcome-info">
                  <h4>Language Breakdown</h4>
                  <p>Original terms and translation comparisons.</p>
                </div>
              </div>
              <div className="outcome-divider"></div>

              <div className="outcome-item">
                <span className="outcome-icon">🛡️</span>
                <div className="outcome-info">
                  <h4>Theological Assessment</h4>
                  <p>Alignment with sound biblical hermeneutics.</p>
                </div>
              </div>
            </div>
          </section>

          {/* Bottom Warning Banner */}
          <div className="sermon-warning-banner">
            <span className="bulb-warning-icon">💡</span>
            <p>
              Our AI serves as a study aid, not a final authority. Always verify important teachings with scripture, prayer, and trusted scholarship.
            </p>
          </div>
        </div>

        {/* Right Column: Sidebar */}
        <aside className="ub-sidebar">
          {/* Card 1: How It Works */}
          <section className="ub-side-card">
            <h2>How It Works</h2>
            <div className="numbered-steps-list">
              <div className="step-row-item">
                <span className="step-num-circle">1</span>
                <p>Upload your sermon audio file.</p>
              </div>
              <div className="step-row-item">
                <span className="step-num-circle">2</span>
                <p>AI transcribes and extracts key scriptures and claims.</p>
              </div>
              <div className="step-row-item">
                <span className="step-num-circle">3</span>
                <p>Our engine analyzes geography, exegesis, and language.</p>
              </div>
              <div className="step-row-item">
                <span className="step-num-circle">4</span>
                <p>Receive a detailed report with insights and references.</p>
              </div>
            </div>
          </section>

          {/* Card 2: Analysis Includes */}
          <section className="ub-side-card">
            <h2>Analysis Includes</h2>
            <ul className="analysis-includes-list">
              <li><span className="include-icon">✓</span> Scripture Verification</li>
              <li><span className="include-icon">✓</span> Historical & Geographical Context</li>
              <li><span className="include-icon">✓</span> Linguistic & Translation Review</li>
              <li><span className="include-icon">✓</span> Theological Alignment</li>
              <li><span className="include-icon">✓</span> Cultural & Historical Sensitivity</li>
            </ul>
          </section>

          {/* Card 3: Recent Analyses */}
          <section className="ub-side-card">
            <div className="recent-header-row">
              <h2>Recent Analyses</h2>
              <button className="view-all-btn" onClick={() => onPageChange && onPageChange('notes')}>View All</button>
            </div>
            
            <div className="recent-analyses-list">
              <button className="recent-analysis-item-row" onClick={() => handleRecentClick("Sunday Morning Sermon.mp3")}>
                <span className="doc-icon-sermon">📄</span>
                <div className="recent-meta-col">
                  <h4>Sunday Morning Sermon.mp3</h4>
                  <p>May 18, 2026 • 10:32 AM</p>
                </div>
                <div className="badge-completed">Completed</div>
                <span className="recent-arrow">→</span>
              </button>

              <button className="recent-analysis-item-row" onClick={() => handleRecentClick("The Book of Acts Study.mp3")}>
                <span className="doc-icon-sermon">📄</span>
                <div className="recent-meta-col">
                  <h4>The Book of Acts Study.mp3</h4>
                  <p>May 16, 2026 • 9:15 AM</p>
                </div>
                <div className="badge-completed">Completed</div>
                <span className="recent-arrow">→</span>
              </button>

              <button className="recent-analysis-item-row" onClick={() => handleRecentClick("Grace & Truth Message.wav")}>
                <span className="doc-icon-sermon">📄</span>
                <div className="recent-meta-col">
                  <h4>Grace & Truth Message.wav</h4>
                  <p>May 14, 2026 • 4:48 PM</p>
                </div>
                <div className="badge-completed">Completed</div>
                <span className="recent-arrow">→</span>
              </button>
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}

export default SermonAnalyzer
