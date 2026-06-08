import { useState, useEffect } from 'react'
import './WordContextPopover.css'

function WordContextPopover({ 
  isVisible, 
  position, 
  word, 
  verseRef, 
  onClose,
  contextData,
  loading = false
}) {
  
  if (!isVisible || !word) {
    return null
  }

  const renderLinguisticContext = (context) => (
    <div className="word-popover-content">
      <div className="popover-header">
        <h3 className="original-word-title">Original Word & Meaning</h3>
        <button className="close-btn" onClick={onClose} title="Close">×</button>
      </div>
      
      <div className="original-word-section">
        <div className="word-display">
          <span className="english-word">{context.word}</span>
          <span className="original-text">({context.original_name})</span>
        </div>
        
        <div className="word-details">
          <div className="language-info">
            <strong>{context.language}</strong>
            {context.strong_number && (
              <span className="strongs-number">Strong's {context.strong_number}</span>
            )}
          </div>
          
          <div className="meaning">
            <strong>Meaning:</strong> {context.meaning}
          </div>
          
          {context.lexicon_context && (
            <div className="detailed-context">
              {context.lexicon_context.part_of_speech && (
                <div><strong>Part of Speech:</strong> {context.lexicon_context.part_of_speech}</div>
              )}
              {context.lexicon_context.detailed_definition && (
                <div><strong>Context:</strong> {context.lexicon_context.detailed_definition}</div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {context.cross_references && context.cross_references.length > 0 && (
        <div className="cross-references-section">
          <button className="view-cross-refs-btn">
            View Cross-References
          </button>
          
          <div className="translation-comparison">
            <h4>Translation Comparison</h4>
            <div className="translation-variants">
              {context.cross_references.map((ref, index) => (
                <div key={index} className="translation-item">
                  <div className="translation-header">
                    <span className={`translation-code ${ref.translation.toLowerCase()}`}>
                      {ref.translation}
                    </span>
                  </div>
                  <div className="translation-text">
                    {ref.text}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )

  const renderBiasAlert = (context) => (
    <div className="word-popover-content bias-alert">
      <div className="popover-header">
        <div className="bias-alert-icon">⚠️</div>
        <h3 className="bias-alert-title">{context.title}</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>
      
      <div className="bias-content">
        <div className="bias-explanation">
          {context.note}
        </div>
        
        {context.original_text && (
          <div className="original-vs-translation">
            <div className="original-section">
              <strong>Original Text:</strong>
              <span className="original-script">{context.original_text}</span>
            </div>
            <div className="literal-section">
              <strong>Literal Translation:</strong>
              <span className="literal-text">{context.literal_translation}</span>
            </div>
          </div>
        )}
        
        <div className="click-details-note">
          <em>The KJV demonstrates bias. The verse celebrates themes that, whereever biases are shone, dark skin tone is valued.</em>
        </div>
      </div>
    </div>
  )

  const renderNotFound = () => (
    <div className="word-popover-content not-found">
      <div className="popover-header">
        <h3>No Context Available</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>
      <div className="not-found-message">
        <p>No additional contextual information is available for "{word}".</p>
      </div>
    </div>
  )

  const renderContent = () => {
    if (loading) {
      return (
        <div className="word-popover-content loading">
          <div className="loading-spinner"></div>
          <p>Loading context...</p>
        </div>
      )
    }

    if (!contextData || !contextData.context) {
      return renderNotFound()
    }

    const { context } = contextData

    switch (context.type) {
      case 'Linguistic':
        return renderLinguisticContext(context)
      case 'Bias Alert':
        return renderBiasAlert(context)
      default:
        return renderNotFound()
    }
  }

  return (
    <>
      <div className="popover-backdrop" onClick={onClose} />
      <div 
        className="word-context-popover word-popover"
        style={{
          left: `${position.x}px`,
          top: `${position.y}px`,
        }}
        onMouseEnter={() => {
          // Cancel any pending hide when mouse enters popover
          if (window.cancelPopoverHide) {
            window.cancelPopoverHide()
          }
        }}
        onMouseLeave={() => {
          // Hide after delay when mouse leaves popover 
          if (window.hidePopoverWithDelay) {
            window.hidePopoverWithDelay()
          }
        }}
      >
        {renderContent()}
      </div>
    </>
  )
}

export default WordContextPopover