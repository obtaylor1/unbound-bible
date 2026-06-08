import { useState } from 'react'
import './SermonAnalyzer.css'

// Token storage utility (same as ForumPage)
const TokenStorage = {
  get: () => {
    try {
      const token = localStorage.getItem('auth_token')
      if (!token) return null
      
      // Validate token format
      const parts = token.split('.')
      if (parts.length !== 3) {
        TokenStorage.remove()
        return null
      }
      
      return token
    } catch (error) {
      console.error('Failed to retrieve token:', error)
      return null
    }
  },
  remove: () => {
    try {
      localStorage.removeItem('auth_token')
      return true
    } catch (error) {
      console.error('Failed to remove token:', error)
      return false
    }
  }
}

function SermonAnalyzer() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      // Validate file type
      if (!selectedFile.type.startsWith('audio/')) {
        setError('Please select an audio file (MP3, WAV, M4A, etc.)')
        return
      }
      setFile(selectedFile)
      setError(null)
    }
  }

  const analyzeSermon = async () => {
    if (!file) {
      setError('Please select an audio file first')
      return
    }

    // Check authentication
    const token = TokenStorage.get()
    if (!token) {
      setError('Please log in to analyze sermons. Visit the Forum page to authenticate.')
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
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to analyze sermon')
      }

      const result = await response.json()
      setAnalysis(result)
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

  return (
    <div className="sermon-analyzer">
      <h2>Sermon Analysis</h2>
      <p>Upload an audio sermon file to get biblical themes, historical context, and cultural insights</p>

      <div className="upload-section">
        <div className="file-input-wrapper">
          <input
            type="file"
            id="audio-file"
            accept="audio/*"
            onChange={handleFileChange}
            disabled={uploading}
          />
          <label htmlFor="audio-file" className={`file-input-label ${uploading ? 'disabled' : ''}`}>
            {file ? file.name : 'Choose Audio File'}
          </label>
        </div>

        <button 
          onClick={analyzeSermon} 
          disabled={!file || uploading}
          className="analyze-button"
        >
          {uploading ? 'Analyzing...' : 'Analyze Sermon'}
        </button>
      </div>

      {error && (
        <div className="error-message">
          <p>{error}</p>
        </div>
      )}

      {uploading && (
        <div className="loading-message">
          <p>🎙️ Transcribing audio and analyzing content...</p>
          <p>This may take a few minutes depending on the file size.</p>
        </div>
      )}

      {analysis && (
        <div className="analysis-results">
          <div className="analysis-header">
            <h3>Analysis Results</h3>
            <span className="processing-time">
              Processed in {formatTime(analysis.processing_time)}
            </span>
          </div>

          <div className="transcription-section">
            <h4>📝 Transcription</h4>
            <div className="transcription-text">
              {analysis.transcription}
            </div>
          </div>

          <div className="analysis-grid">
            <div className="analysis-card">
              <h4>📖 Biblical Themes</h4>
              <ul>
                {analysis.biblical_themes.map((theme, index) => (
                  <li key={index}>{theme}</li>
                ))}
              </ul>
            </div>

            <div className="analysis-card">
              <h4>📜 Referenced Passages</h4>
              <ul>
                {analysis.referenced_passages.map((passage, index) => (
                  <li key={index}>{passage}</li>
                ))}
              </ul>
            </div>

            <div className="analysis-card">
              <h4>🏛️ Historical Connections</h4>
              <ul>
                {analysis.historical_connections.map((connection, index) => (
                  <li key={index}>{connection}</li>
                ))}
              </ul>
            </div>

            <div className="analysis-card full-width">
              <h4>🌍 Cultural Significance</h4>
              <p>{analysis.cultural_significance}</p>
            </div>

            <div className="analysis-card full-width">
              <h4>🔍 Accuracy Assessment</h4>
              <p>{analysis.accuracy_assessment}</p>
            </div>

            <div className="analysis-card full-width">
              <h4>💡 Suggestions for Additional Context</h4>
              <ul>
                {analysis.suggestions.map((suggestion, index) => (
                  <li key={index}>{suggestion}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SermonAnalyzer