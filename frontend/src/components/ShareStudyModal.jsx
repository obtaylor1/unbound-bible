import { useEffect, useRef, useState } from 'react'
import './ShareStudyModal.css'

function ShareStudyModal({ isOpen, onClose, shareData }) {
  const [copied, setCopied] = useState(false)
  const [isPublic, setIsPublic] = useState(true)
  const [shareUrl] = useState(() => `https://unboundbible.app/share/study_${Date.now()}`)
  const closeButtonRef = useRef(null)
  const previousFocusRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return undefined
    previousFocusRef.current = document.activeElement
    closeButtonRef.current?.focus()
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previousFocusRef.current?.focus()
    }
  }, [isOpen, onClose])

  if (!isOpen || !shareData) return null

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error("Failed to copy share link:", err)
    }
  }

  return (
    <div className="share-modal-overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="share-modal-card glass-panel" role="dialog" aria-modal="true" aria-labelledby="share-dialog-title">
        <div className="modal-header">
          <h3 id="share-dialog-title">Share study session</h3>
          <button ref={closeButtonRef} className="close-btn" type="button" aria-label="Close sharing dialog" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="share-summary-box">
            <span className="summary-label">Session Type:</span>
            <span className="summary-val">{shareData.type}</span>
            
            <span className="summary-label">Title:</span>
            <span className="summary-val bold">{shareData.title}</span>

            {shareData.verses && shareData.verses.length > 0 && (
              <>
                <span className="summary-label">Scriptures Included:</span>
                <div className="summary-verses">
                  {shareData.verses.map(v => <span key={v} className="badge-verse">📖 {v}</span>)}
                </div>
              </>
            )}
          </div>

          {/* Visibility Toggle */}
          <div className="visibility-toggle-row">
            <label className="toggle-container">
              <input 
                type="checkbox" 
                checked={isPublic} 
                onChange={() => setIsPublic(!isPublic)}
              />
              <span className="toggle-slider"></span>
            </label>
            <div className="toggle-label-group">
              <span>{isPublic ? '🌐 Public Link' : '🔒 Private Link'}</span>
              <p>{isPublic ? 'Anyone with this link can view this study session.' : 'Only logged-in group members can view this session.'}</p>
            </div>
          </div>

          {/* Link output box */}
          <div className="link-output-box">
            <input 
              type="text" 
              value={shareUrl} 
              aria-label="Share link"
              readOnly 
              className="share-url-input"
            />
            <button 
              onClick={handleCopyLink} 
              type="button"
              className={`copy-btn ${copied ? 'success' : ''}`}
            >
              {copied ? 'Copied! ✓' : 'Copy Link'}
            </button>
          </div>

          <p className="share-availability-note" role="note">Copy the link above to share it. Direct email and community sharing will be available after account sign-in is connected.</p>
        </div>

        <div className="modal-footer">
          <p className="disclaimer-txt">Shared links preserve citations, translation comparisons, and annotations. The recipient does not need an account to view public links.</p>
        </div>
      </div>
    </div>
  )
}

export default ShareStudyModal
