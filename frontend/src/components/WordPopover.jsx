import { useState, useEffect, useRef } from 'react'
import './WordPopover.css'

function WordPopover({ 
  isVisible, 
  position, 
  originalWord, 
  meaning, 
  contextBias, 
  onClose,
  loading = false 
}) {
  const popoverRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        onClose()
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    if (isVisible) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isVisible, onClose])

  if (!isVisible) return null

  return (
    <div 
      className="word-popover-overlay"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 1000,
        pointerEvents: 'auto'
      }}
    >
      <div 
        ref={popoverRef}
        className="word-popover"
        style={{
          position: 'absolute',
          left: `${position.x}px`,
          top: `${position.y}px`,
          transform: 'translate(-50%, -100%)',
          marginTop: '-10px'
        }}
      >
        <div className="word-popover-header">
          <h4 className="word-popover-title">Word Context</h4>
          <button 
            className="word-popover-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="word-popover-content">
          {loading ? (
            <div className="word-popover-loading">
              <div className="loading-spinner-small"></div>
              <span>Loading context...</span>
            </div>
          ) : (
            <>
              {originalWord && (
                <div className="word-section">
                  <label className="word-label">Original Word</label>
                  <div className="word-value original-word">{originalWord}</div>
                </div>
              )}

              {meaning && (
                <div className="word-section">
                  <label className="word-label">Meaning</label>
                  <div className="word-value meaning-text">{meaning}</div>
                </div>
              )}

              {contextBias && (
                <div className="word-section bias-section">
                  <label className="word-label bias-label">
                    <span className="bias-icon">⚠️</span>
                    Context/Bias Alert
                  </label>
                  <div className="word-value bias-text">{contextBias}</div>
                </div>
              )}

              {!originalWord && !meaning && !contextBias && !loading && (
                <div className="word-section">
                  <div className="word-value no-info">
                    No additional context available for this word.
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="word-popover-arrow"></div>
      </div>
    </div>
  )
}

export default WordPopover