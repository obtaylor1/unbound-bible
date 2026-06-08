import './Navigation.css'

function Navigation({ currentPage, onPageChange }) {
  return (
    <nav className="navigation">
      <div className="nav-container">
        <div className="nav-left">
          <button className="nav-logo" onClick={() => onPageChange('home')}>
            <span className="logo-text">The Unbound Bible</span>
          </button>
        </div>
        
        <div className="nav-center">
          <button 
            className={`nav-item ${currentPage === 'home' ? 'active' : ''}`}
            onClick={() => onPageChange('home')}
          >
            <span className="nav-icon">🏠</span>
            <span className="nav-text">Home</span>
          </button>
          
          <button 
            className={`nav-item ${currentPage === 'textual' ? 'active' : ''}`}
            onClick={() => onPageChange('textual')}
          >
            <span className="nav-icon">📖</span>
            <span className="nav-text">Textual Comparison</span>
            <span className="nav-tag ai-powered">AI Powered</span>
          </button>
          
          <button 
            className={`nav-item ${currentPage === 'sermon' ? 'active' : ''}`}
            onClick={() => onPageChange('sermon')}
          >
            <span className="nav-icon">🎤</span>
            <span className="nav-text">Sermon Analysis</span>
            <span className="nav-tag beta">Beta</span>
          </button>
          
          <button 
            className={`nav-item ${currentPage === 'map' ? 'active' : ''}`}
            onClick={() => onPageChange('map')}
          >
            <span className="nav-icon">🗺️</span>
            <span className="nav-text">Biblical Map</span>
            <span className="nav-tag interactive">INTERACTIVE</span>
          </button>
          
          <button 
            className={`nav-item ${currentPage === 'forum' ? 'active' : ''}`}
            onClick={() => onPageChange('forum')}
          >
            <span className="nav-icon">👥</span>
            <span className="nav-text">Community</span>
          </button>
        </div>
        
        <div className="nav-right">
          <button className="nav-action-btn">
            <span className="action-icon">🔍</span>
          </button>
          <button className="nav-action-btn">
            <span className="action-icon">🔔</span>
          </button>
          <button className="nav-signin">
            <span className="signin-icon">👤</span>
            <span className="signin-text">Sign In</span>
          </button>
        </div>
      </div>
    </nav>
  )
}

export default Navigation